# Perimeter Control - Port Architecture & Configuration

## Overview 

The Perimeter Control system uses a well-defined port architecture to separate different services and provide clean network boundaries between components. This document outlines all ports used, their purposes, and configuration options.

## Port Assignment Scheme

### Core System Ports

| Port | Service | Purpose | Configurable | Default Source |
|------|---------|---------|--------------|----------------|
| 22   | SSH     | Device management, deployment | Yes (per device) | `DEFAULT_SSH_PORT` |
| 8080 | Supervisor API  | Main FastAPI for Home Assistant | Yes (per device) | `DEFAULT_API_PORT` |

### Service Web Dashboard Ports

| Port | Service | Purpose | Status |
|------|---------|---------|--------|
| 5006 | Network Isolator | Network isolation web dashboard | Active |
| 8091 | BLE GATT Repeater | BLE scanning and GATT monitoring dashboard | Active |
| 8092 | ESL Access Point | Electronic Shelf Label management dashboard | Active |
| 8093 | Photo Booth | Camera control and photo management dashboard | Active |
| 8094 | Wildlife Monitor | Environmental monitoring and wildlife tracking dashboard | Active |

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
  port: 8091  # Service web dashboard port
  tls_mode: off
  auth_mode: none
  allowed_origins: []
  exposure_scope: lan_only
```

Each service descriptor defines the port for its dedicated web dashboard interface.

## Architecture Design

### Port Separation Strategy

1. **Management Layer** (22, 8080): Used by Home Assistant for device control
2. **Service Dashboard Layer** (5006, 8091-8094): Individual service web interfaces
   - Each service has its own dedicated web dashboard
   - Bokeh-based interactive dashboards with real-time monitoring
   - Service-specific monitoring, control, and configuration UIs

### Network Flow

```
Home Assistant  →  8080 (Supervisor API)  →  Pi Services
     ↓
User Browser   →  5006 (Network Isolator Dashboard)  →  Network Management UI
     ↓  
User Browser   →  8091 (BLE Dashboard)  →  BLE Scanning & GATT Monitor UI
     ↓
User Browser   →  8092 (ESL Dashboard)  →  Electronic Shelf Label Management UI  
     ↓
User Browser   →  8093 (Photo Booth Dashboard)  →  Camera Control & Gallery UI
     ↓
User Browser   →  8094 (Wildlife Dashboard)  →  Environmental Data & Wildlife Tracking UI
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
   - Network Isolator dashboard port
3. **Service Descriptors** (per-service)
   - Individual service web dashboard ports
4. **Service Dashboard Configs** (per-service component)
   - Service-specific dashboard configurations
5. **Code Defaults** (lowest priority)
   - Fallback when no config provided

## Common Port Issues & Solutions

### Issue: "No entities showing up"

**Likely Cause**: Supervisor API port connectivity problems

**Diagnostic Steps**:
1. Test Pi network connectivity: `ping 192.168.50.47`
2. Test Supervisor API: `Test-NetConnection -ComputerName 192.168.50.47 -Port 8080`
3. Check logs in Home Assistant for connection errors to supervisor

### Issue: "Service dashboards not accessible"

**Likely Cause**: Service dashboard web servers not running or port conflicts

**Diagnostic Steps**:
1. Test individual service dashboard ports:
   ```powershell
   Test-NetConnection -ComputerName 192.168.50.47 -Port 5006  # Network Isolator
   Test-NetConnection -ComputerName 192.168.50.47 -Port 8091  # BLE GATT Repeater  
   Test-NetConnection -ComputerName 192.168.50.47 -Port 8092  # ESL Access Point
   Test-NetConnection -ComputerName 192.168.50.47 -Port 8093  # Photo Booth
   Test-NetConnection -ComputerName 192.168.50.47 -Port 8094  # Wildlife Monitor
   ```
2. Check service configurations match service descriptors
3. Verify Bokeh servers are running for each service
4. Check firewall allows all service dashboard ports

### Issue: "Dashboard shows wrong service"

**Likely Cause**: Port configuration mismatch between service descriptor and component config

**Solutions**:
- Verify `dashboard_config.yaml` port matches service descriptor port
- Check component service implementations for correct port assignments
- Ensure no port conflicts between services

### Issue: "Supervisor API timeout"

**Likely Cause**: Wrong supervisor port configuration

**Solutions**:
- Verify supervisor_port in HA config matches Pi config
- Default should be 8080 unless explicitly changed
- Check supervisor service: `systemctl status PerimeterControl-supervisor`

## Service Dashboard Features

Each service provides a dedicated web dashboard with service-specific functionality:

### Network Isolator Dashboard (Port 5006) 
- **Technology**: Bokeh/Tornado web server
- **Features**: Network device monitoring, firewall rule management, traffic visualization
- **Real-time**: Live bandwidth graphs, connection status, firewall alerts

### BLE GATT Repeater Dashboard (Port 8091)
- **Technology**: Bokeh interactive server  
- **Features**: BLE device scanning, GATT characteristic monitoring, connection management
- **Real-time**: Device discovery, characteristic value updates, connection status

### ESL Access Point Dashboard (Port 8092)
- **Technology**: Bokeh interactive server
- **Features**: Electronic Shelf Label management, layout editor, display synchronization
- **Real-time**: Connected displays, advertising status, layout updates

### Photo Booth Dashboard (Port 8093)
- **Technology**: Bokeh interactive server
- **Features**: Camera control, live stream, photo gallery, motion detection
- **Real-time**: Live camera feed, motion alerts, capture management

### Wildlife Monitor Dashboard (Port 8094) 
- **Technology**: Bokeh interactive server
- **Features**: Environmental sensor data, wildlife detection, data analysis charts
- **Real-time**: Temperature/humidity graphs, motion timeline, sensor readings

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
- **Service Dashboards (5006, 8091-8094)**: Internal network only, web interfaces for service management
  - Each service runs its own Bokeh interactive server
  - Real-time dashboards with service-specific monitoring and control
  - Can be tunneled for secure remote access

### Firewall Configuration

Recommended firewall rules on Pi:
```bash
# Allow SSH from management network
iptables -A INPUT -p tcp --dport 22 -s 192.168.50.0/24 -j ACCEPT

# Allow supervisor API from internal network
iptables -A INPUT -p tcp --dport 8080 -s 192.168.111.0/24 -j ACCEPT

# Allow all service dashboards from internal network  
iptables -A INPUT -p tcp --dport 5006 -s 192.168.111.0/24 -j ACCEPT    # Network Isolator
iptables -A INPUT -p tcp --dport 8091 -s 192.168.111.0/24 -j ACCEPT    # BLE Dashboard
iptables -A INPUT -p tcp --dport 8092 -s 192.168.111.0/24 -j ACCEPT    # ESL Dashboard  
iptables -A INPUT -p tcp --dport 8093 -s 192.168.111.0/24 -j ACCEPT    # Photo Booth Dashboard
iptables -A INPUT -p tcp --dport 8094 -s 192.168.111.0/24 -j ACCEPT    # Wildlife Dashboard
```

## Remote Access

For secure remote access to all service dashboards:

```bash
# SSH tunnel for all service dashboards
ssh -i key -L 5006:localhost:5006 -L 8091:localhost:8091 -L 8092:localhost:8092 -L 8093:localhost:8093 -L 8094:localhost:8094 paul@192.168.50.47

# Then access dashboards at:
# http://localhost:5006  - Network Isolator Dashboard
# http://localhost:8091  - BLE GATT Repeater Dashboard  
# http://localhost:8092  - ESL Access Point Dashboard
# http://localhost:8093  - Photo Booth Dashboard
# http://localhost:8094  - Wildlife Monitor Dashboard
```

**Individual Service Tunnels** (if you only need specific services):
```bash
# Network Isolator only
ssh -i key -L 5006:localhost:5006 paul@192.168.50.47

# BLE GATT Repeater only
ssh -i key -L 8091:localhost:8091 paul@192.168.50.47

# Photo Booth only  
ssh -i key -L 8093:localhost:8093 paul@192.168.50.47
```

This setup provides secure remote access to all service dashboards without exposing them directly to the internet.

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

# Test SSH and supervisor
Test-NetConnection -ComputerName 192.168.50.47 -Port 22
Test-NetConnection -ComputerName 192.168.50.47 -Port 8080  

# Test all service dashboards
Test-NetConnection -ComputerName 192.168.50.47 -Port 5006   # Network Isolator
Test-NetConnection -ComputerName 192.168.50.47 -Port 8091   # BLE GATT Repeater
Test-NetConnection -ComputerName 192.168.50.47 -Port 8092   # ESL Access Point
Test-NetConnection -ComputerName 192.168.50.47 -Port 8093   # Photo Booth
Test-NetConnection -ComputerName 192.168.50.47 -Port 8094   # Wildlife Monitor
```

### Service Status (on Pi)
```bash
# Check all Perimeter Control services
systemctl status PerimeterControl-*

# Check specific services
systemctl status PerimeterControl-supervisor
systemctl status PerimeterControl-dashboard  # Network Isolator dashboard

# Check what processes are listening on dashboard ports
netstat -tlnp | grep -E "(5006|8091|8092|8093|8094|8080)"

# Check individual service processes
ps aux | grep -E "(fastapi|uvicorn|bokeh)"
```

This port architecture ensures clean separation of concerns while maintaining security and providing flexible configuration options for different deployment scenarios.