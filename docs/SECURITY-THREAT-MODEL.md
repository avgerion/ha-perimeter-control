# Security & Threat Model

Attack surface analysis and defense strategy for Pi running network policies and BLE control.

## Threat Model

### Threat Actors

| Actor | Capability | Goal | Impact |
|-------|-----------|------|--------|
| **Local User** | SSH access, local scripts | Bypass network policies, detect BLE devices | High |
| **Network Attacker** | Routing to Pi, spoofed packets | Inject policies, disrupt network isolation | High |
| **Nearby BLE Attacker** | BLE radio, sniffer | MITM GATT, fake commands, DoS scanner | Medium |
| **HA Integrator** | REST API access | Trigger unwanted actions, read entity state | Medium |
| **Supply Chain** | Compromised package, Git repo | Inject malicious capability module | High |

### Attack Vectors

#### 1. SSH / Local Access

**Threat:** Attacker with SSH access can:
- Read nftables rules → learn policies
- Modify systemd services → inject code
- Restart supervisor → cause DoS
- Read SQLite DB → extract entity history

**Defense:**
```yaml
# /etc/sshd_config additions
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers isolator-admin  # Only specific users
Match User isolator-admin
  X11Forwarding no
  AllowTcpForwarding no
AllowAgentForwarding no
AllowStreamLocalForwarding no
```

Supervisor runs as unprivileged `isolator` user:
```bash
sudo useradd -r -s /usr/sbin/nologin isolator
chown isolator:isolator /opt/isolator
chmod 700 /opt/isolator/state  # Private DB
chmod 700 /opt/isolator/config  # Private config
```

Root-only operations (nftables, systemd) via sudo:
```bash
# /etc/sudoers.d/isolator
isolator ALL=(root) NOPASSWD: /usr/sbin/nft
isolator ALL=(root) NOPASSWD: /bin/systemctl reload isolator
isolator ALL=(root) NOPASSWD: /bin/systemctl restart isolator-*
```

#### 2. Network Policy Injection

**Threat:** Attacker can:
- Send crafted YAML to supervisor REST API
- Inject malicious nftables rules
- Disable network isolation

**Defense:**
```python
# Input validation (strict schema)
from pydantic import BaseModel, validator

class NetworkIsolationPolicy(BaseModel):
    devices: List[Device]
    policies: List[Policy]
    
    @validator('devices')
    def validate_devices(v):
        for device in v:
            # Only allow whitelisted device types
            assert device.type in ["ethernet", "wifi", "mobile"]
            # No shell escapes
            assert device.mac.match(r'^[0-9a-f]{2}:[0-9a-f]{2}:')
        return v
    
    @validator('policies')
    def validate_policies(v):
        for policy in v:
            # Only allow specific actions
            assert policy.action in ["allow", "block", "limit"]
            # Max rate limit to prevent DoS
            assert policy.rate_limit_mbps >= 1 and <= 1000
        return v
```

REST API requires authentication:
```python
@app.post("/api/v1/capabilities/network_isolation/deploy")
@require_auth
@require_capability("deploy", "network_isolation")
async def deploy_network_isolation(request):
    # Auth header checked, token issued by Pi
    pass
```

#### 3. BLE MITM & Eavesdropping

**Threat:** Nearby attacker with BLE sniffer can:
- Observe GATT packets in plaintext
- Inject fake characteristic values
- DoS BLE scanner with fake advertisements

**Defense:**

```yaml
# supervisor.yaml - BLE security settings
ble_gatt_translator:
  encryption: true              # Require LE Encryption
  authentication: none          # BLE v5.0+
  channel_map: [37, 38, 39]    # Only use all channels (harder to jam)
  
  # Whitelist known devices
  known_devices:
    - mac: "aa:bb:cc:dd:ee:ff"
      profile: kitchen_scale@1.0.0
      encryption: true
      bond: true  # Permanent pairing
    
  # Reject unknown manufacturers to limit surface
  reject_manufacturer_ids: [0xffff]  # Placeholder mfg
  
  # Scanner DoS limits
  max_advertisements_per_mac_per_minute: 60
  max_unique_addresses_per_minute: 1000
```

BLE link layer encryption (BlueZ):
```bash
# Force BLE encryption on device pairing
sudo hciconfig hci0 le_set_addr_resolution_enable 1
# Persistent keys in /var/lib/bluetooth/
chmod 700 /var/lib/bluetooth/
```

#### 4. Supervisor Privilege Escalation

**Threat:** Escalate from `isolator` user to root

**Defense:**
- Supervisor runs unprivileged; only calls sudo for specific commands
- Systemd units run as `isolator:isolator`

```ini
# /etc/systemd/system/isolator-supervisor.service
[Service]
Type=simple
User=isolator
Group=isolator
ExecStart=/usr/bin/python3 /opt/isolator/supervisor.py
# Drop unneeded capabilities
CapabilityBoundingSet=~CAP_SYS_ADMIN CAP_NET_ADMIN CAP_SYS_MODULE
NoNewPrivileges=true
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/isolator/state /opt/isolator/logs
```

#### 5. HA Integration Abuse

**Threat:** Compromised HA instance can:
- Query all entity history
- Trigger unwanted actions
- Exfiltrate network policies

**Defense:**
```python
# REST API token-based auth + scoping
class HAIntegrationToken:
    scopes: List[str]  # e.g., ["entity:read:network_isolation"]
    expires_at: datetime
    rate_limit: int  # requests/sec
    allowed_entities: Optional[List[str]]  # None = all

# Token generation (one-time setup code)
pi.register_ha_instance(registration_code='XYZ123')
  → Returns time-limited token
  → HA stores token securely (encrypted)

# Per-request validation
@require_scope("entity:read")
def get_entities():
    if token.allowed_entities:
        return filter_by_allowed(all_entities, token.allowed_entities)
```

Rate limiting:
```python
# HA can query max 100 entities/sec
# Prevents exfiltration of large history

@app.get("/api/v1/entities/{entity_id}/history")
@rate_limit(100)
async def get_entity_history(entity_id: str):
    # Return last 24h by default
    # HA can paginate with "?since=T&until=T"
    pass
```

#### 6. Supply Chain / Capability Module Injection

**Threat:** Attacker compromises capability module code

**Defense:**

```yaml
# supervisor.yaml - capability module verification
capability_modules:
  sources:
    - type: local
      path: /opt/isolator/capabilities/built_in/
      verify_signature: true
      
    - type: remote
      url: "https://registry.isolator.dev/capabilities"
      verify_signature: true
      verify_checksum: true
      
  security:
    # Sandboxing (future: runc containers per capability)
    sandbox_enabled: false  # v1.1+
    
    # Code scanning
    scan_for_suspicious_patterns: true  # e.g., subprocess.call
    scan_for_network_access: true
    scan_for_file_access_outside_scope: true
    
    # Require explicit code review for non-standard library imports
    allowed_imports_whitelist:
      - bleak
      - pyyaml
      - prometheus_client
      - sqlalchemy
```

Digital signatures on capability packages:
```bash
# Sign capability module
openssl dgst -sha256 -sign key.pem capability_module.tar.gz > signature

# Verify before loading
openssl dgst -sha256 -verify key.pub -signature signature capability_module.tar.gz
```

#### 7. Configuration Tampering

**Threat:** Attacker modifies config files to change policies

**Defense:**

```yaml
# supervisor.yaml - config integrity
config:
  # Store in git (immutable, audited)
  git_repo: /opt/isolator/config/.git
  
  # All changes tracked with signature
  require_signature: true
  
  # Config as code: reviewed before deploy
  change_review_required: true
  
  # Each deployment creates checkpoint
  snapshot_every_deploy: true
  
  # Rollback capability
  max_snapshots: 10
```

Config verification on startup:
```python
def verify_config_integrity():
    # Check hashes match DB
    for config_file in Path(/opt/isolator/config).glob("*.yaml"):
        stored_hash = supervisor.db.get_config_hash(config_file)
        actual_hash = sha256(config_file.read_bytes())
        
        if stored_hash != actual_hash:
            logger.critical(f"Config tampering detected: {config_file}")
            raise ConfigTamperingAlertError()
```

#### 8. DoS on Supervisor

**Threat:** Attacker DoS the REST API or reconciliation loop

**Defense:**

```python
# Rate limiting on REST API
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Limit: 1000 req/min per IP
    # Burst: max 50 req/sec
    
    client_ip = request.client.host
    limiter.check_rate(client_ip, limit=1000/60, burst=50)
    
    response = await call_next(request)
    return response

# Reconciliation loop max 30s

@timed_operation("reconciliation", max_duration_sec=30)
def reconcile():
    # If takes > 30s, alert and skip this cycle
    ...
```

Resource limits for capabilities:
```yaml
# Each capability has hard limits
network_isolation:
  resources:
    cpu_cores_max: 1.0
    memory_mb_max: 200
    disk_mb_max: 100
    timeout_sec: 30
```

## Secrets Management

### API Tokens

- Generated via one-time setup code
- Stored in SQLite encrypted column
- Rotatable (HA setup flow generates new tokens)
- Short-lived option (expire in 24h, auto-refresh)

```python
# Token storage (encrypted at rest in DB)
class APIToken:
    token_hash = sha256(token)  # Hash stored, never plaintext
    created_at = now()
    expires_at = now() + 24h
    scopes = ["entity:read", "action:trigger"]
    rate_limit = 1000/60
```

### SSH Keys

```bash
# Pi generates strong ephemeral SSH key pair
ssh-keygen -t ed25519 -f /opt/isolator/.ssh/id_ed25519

# Public key deployed to HA (optional, for Pi→HA callback)
# Private key never seen by HA

chmod 600 /opt/isolator/.ssh/id_ed25519
chmod 644 /opt/isolator/.ssh/id_ed25519.pub
```

### BLE Pairing Keys

```bash
# Stored by BlueZ in system keyring
/var/lib/bluetooth/<adapter_mac>/<device_mac>/
├── info (pairing key, encrypted)
└── cache (GATT attributes)

chmod 700 /var/lib/bluetooth/  # Only root/supervisor can read
```

## Audit Logging

Every security event logged:

```python
logger.warning(
    "Failed auth attempt",
    extra={
        "event_type": "auth_failure",
        "api_client_ip": "192.168.1.100",
        "token_id": "tok_abc123",
        "reason": "invalid_scope",
        "timestamp": now(),
    }
)
```

Queryable audit log:
```bash
curl "http://localhost:8080/api/v1/audit?event_type=auth_failure&since=7d"
```

## Compliance & Standards

- **CWE-79 (Injection):** Input validation + YAML schema
- **CWE-94 (Code Injection):** No eval(), strict capability modules
- **CWE-79 (XSS):** REST API returns JSON (no HTML templating)
- **CWE-639 (Authorization):** Token-based auth + scopes
- **CWE-307 (Weak Authentication):** SSH keys only, no passwords
- **OWASP Top 10:**
  - A1 (Injection): Pydantic validation
  - A2 (Auth): Token + scope-based auth
  - A3 (Sensitive data): Encrypted at-rest secrets
  - A5 (Access control): Role-based + token scopes
  - A6 (Misconfiguration): Hardened defaults, explicit allow list

## Future Hardening (v1.2+)

- **Capability Sandboxing:** Run each capability in runc container
- **Hardware Security Module (HSM):** Store keys on USB HSM (optional)
- **Verified Boot:** Secureboot + dm-verity for root filesystem
- **Mandatory Access Control:** SELinux or AppArmor profiles
- **Hardware Attestation:** TPM2.0 quotes for HA trust verification
