# Perimeter Control - Port Architecture & Configuration

## Overview 

The Perimeter Control system uses a well-defined port architecture to separate different services and provide clean network boundaries between components. This document outlines all ports used, their purposes, and configuration options.

## Port Assignment Scheme

### Core System Ports

| Port | Service | Purpose | Configurable | Default Source |
|------|---------|---------|--------------|----------------|
| 22   | SSH     | Device management, deployment | Yes (per device) | `DEFAULT_SSH_PORT` |
| 5006 | Dashboard Web UI | Network Isolator web interface | Yes (config file) | `DEFAULT_DASHBOARD_PORT` |
| 8080 | Supervisor API  | Main API for Home Assistant | Yes (per device) | `DEFAULT_API_PORT` |

### Service-Specific API Ports

| Port | Service | Purpose | Status |
|------|---------|---------|--------|
| 8091 | BLE GATT Repeater | BLE service API | Active |
| 8092 | ESL Access Point | ESL service API | Active |
| 8093 | Photo Booth | Camera service API | Active |
| 8094 | Wildlife Monitor | Monitoring service API | Active |

## Port Configuration Sources

### 1. Home Assistant Integration Config

**Location**: Home Assistant UI → Integrations → Perimeter Control → Configure

**Configurable Ports**:
- `host`: Pi device IP address
- `port`: SSH port (default: 22)
- `supervisor_port`: Supervisor API port (default: 8080)
- `user`: SSH username (default: "pi")

**Example Entry**:
```yaml
host: "192.168.50.47"
port: 22
supervisor_port: 8080
user: "paul"
ssh_key: "-----BEGIN OPENSSH PRIVATE KEY-----..."
```

### 2. Pi Configuration File

**Location**: `/etc/perimeterControl.conf.yaml` on Pi

**Dashboard Port Configuration**:
```yaml
dashboard:
  port: 5006
  exposure:
    mode: upstream
    bind_address: ""
    allow_websocket_origins: []
```

### 3. Service Descriptors

**Location**: `service_descriptors/` directory

**Individual Service Ports** (in each `.service.yaml`):
```yaml
access_profile:
  mode: upstream
  bind_address: ""
  port: 8091  # Service-specific port
  tls_mode: off
  auth_mode: none
  allowed_origins: []
  exposure_scope: lan_only
```

## Architecture Design

### Port Separation Strategy

1. **Management Layer** (22, 8080): Used by Home Assistant for device control
2. **User Interface Layer** (5006): Direct user access to dashboard
3. **Service API Layer** (8091-8094): Individual service endpoints

### Network Flow

```
Home Assistant  →  8080 (Supervisor API)  →  Pi Services
     ↓
User Browser   →  5006 (Dashboard UI)    →  Pi Web Interface
     ↓
External APIs  →  809X (Service APIs)   →  Individual Services
```

## Default Port Constants

**File**: `const.py`

```python
DEFAULT_SSH_PORT = 22
DEFAULT_API_PORT = 8080          # Supervisor API port  
DEFAULT_DASHBOARD_PORT = 5006    # Network Isolator dashboard port
```

## Configuration Override Hierarchy

1. **Home Assistant Config Entry** (highest priority)
   - SSH port, Supervisor API port
2. **Pi Config File** (`perimeterControl.conf.yaml`)
   - Dashboard port, network settings
3. **Service Descriptors** (per-service)
   - Individual service API ports
4. **Code Defaults** (lowest priority)
   - Fallback when no config provided

## Common Port Issues & Solutions

### Issue: "No entities showing up"

**Likely Cause**: Port connectivity problems

**Diagnostic Steps**:
1. Test Pi network connectivity: `ping 192.168.50.47`
2. Test Supervisor API: `Test-NetConnection -ComputerName 192.168.50.47 -Port 8080`
3. Test Dashboard: `Test-NetConnection -ComputerName 192.168.50.47 -Port 5006` 
4. Check logs in Home Assistant for connection errors

### Issue: "Dashboard not accessible"

**Likely Cause**: Dashboard service not running or port mismatch

**Solutions**:
- Verify dashboard port in Pi config: `cat /etc/perimeterControl.conf.yaml`
- Check dashboard service: `systemctl status PerimeterControl-dashboard`
- Ensure firewall allows port 5006

### Issue: "Supervisor API timeout"

**Likely Cause**: Wrong supervisor port configuration

**Solutions**:
- Verify supervisor_port in HA config matches Pi config
- Default should be 8080 unless explicitly changed
- Check supervisor service: `systemctl status PerimeterControl-supervisor`

## Development Notes

### Adding New Services

When adding new services that need API endpoints:

1. Assign next available port in 809X range
2. Update service descriptor with port configuration
3. Document port in this architecture guide
4. Ensure firewall rules allow the port

### Port Validation

The coordinator performs health checks on:
- **Supervisor API** (8080): For Home Assistant communication
- **Dashboard** (5006): For web interface availability

## Security Considerations

### Port Exposure

- **SSH (22)**: Secured with key-based authentication
- **Supervisor API (8080)**: Internal network only, no external exposure
- **Dashboard (5006)**: Internal network only, can be tunneled for remote access
- **Service APIs (809X)**: Internal network only, used by supervisor

### Firewall Configuration

Recommended firewall rules on Pi:
```bash
# Allow SSH from management network
iptables -A INPUT -p tcp --dport 22 -s 192.168.50.0/24 -j ACCEPT

# Allow supervisor API from internal network
iptables -A INPUT -p tcp --dport 8080 -s 192.168.111.0/24 -j ACCEPT

# Allow dashboard from internal network  
iptables -A INPUT -p tcp --dport 5006 -s 192.168.111.0/24 -j ACCEPT

# Allow service APIs from localhost only (supervisor access)
iptables -A INPUT -p tcp --dport 8091:8094 -s 127.0.0.1 -j ACCEPT
```

## Remote Access

For secure remote access to dashboard:

```bash
# SSH tunnel from your machine to Pi
ssh -i key -L 5006:localhost:5006 paul@192.168.50.47

# Then access dashboard at: http://localhost:5006
```

This setup provides secure remote access without exposing the dashboard directly to the internet.

## Configuration Examples

### Minimal HA Configuration
```yaml
# Only required fields
host: "192.168.50.47"
user: "paul"  
ssh_key: "..."  # SSH private key content
```

### Full HA Configuration  
```yaml
# All configurable fields
host: "192.168.50.47"
port: 22
supervisor_port: 8080
user: "paul"
ssh_key: "..."
```

### Custom Pi Configuration
```yaml
# In /etc/perimeterControl.conf.yaml
dashboard:
  port: 5007  # Custom dashboard port
  exposure:
    mode: upstream
    bind_address: "0.0.0.0"  # Allow external access (not recommended)
```

## Troubleshooting Commands

### Network Connectivity
```powershell
# Test basic connectivity
ping 192.168.50.47

# Test specific ports
Test-NetConnection -ComputerName 192.168.50.47 -Port 22
Test-NetConnection -ComputerName 192.168.50.47 -Port 8080  
Test-NetConnection -ComputerName 192.168.50.47 -Port 5006
```

### Service Status (on Pi)
```bash
# Check all Perimeter Control services
systemctl status PerimeterControl-*

# Check specific services
systemctl status PerimeterControl-supervisor
systemctl status PerimeterControl-dashboard

# Check what processes are listening
netstat -tlnp | grep -E "(5006|8080|809[0-9])"
```

This port architecture ensures clean separation of concerns while maintaining security and providing flexible configuration options for different deployment scenarios.