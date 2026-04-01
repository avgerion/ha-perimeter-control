# Network Architecture

## Overview

The Perimeter Control system operates across **two separate networked devices**:

## Device Roles

### 🏠 Home Assistant Server
- **Purpose**: Runs the custom integration that provides UI and orchestration
- **Location**: Your existing Home Assistant installation (any device)  
- **Software**: `custom_components/perimeter_control/` integration
- **Network Role**: SSH client, HTTP API client

### 🥧 Raspberry Pi Target Device  
- **Purpose**: Runs the supervisor API and actual services
- **Location**: Remote Pi device (example: `192.168.50.47`)
- **Software**: Supervisor API, dashboard web UI, service runtime
- **Network Role**: SSH server, HTTP API server

## Communication Flows

### 1. Initial Deployment
```
Home Assistant ──SSH──► Pi Target
               (user: pi, key auth)
               
Deploy Process:
1. HA connects to Pi via SSH  
2. HA uploads supervisor + services code via SFTP
3. HA runs setup commands on Pi via SSH
4. Pi starts systemd services (supervisor on port 8080)
```

### 2. Runtime Communication  
```
Home Assistant ──HTTP API──► Pi Target:8080
               ◄────────────── (entity states, actions)
               
Home Assistant ──WebSocket──► Pi Target:8080  
               ◄──────────────── (real-time events)
```

### 3. User Access
```
User Browser ──► Pi Target:3000 (dashboard web UI)
User Browser ──► Home Assistant UI (entity controls)
```

## Network Requirements

- **SSH Access**: HA server must be able to SSH to Pi target device
- **HTTP Access**: HA server must be able to reach Pi target on port 8080
- **Ports on Pi**: 
  - Port 22: SSH (for deployment)
  - Port 8080: Supervisor API (for HA communication)  
  - Port 3000: Dashboard Web UI (for user access)

## Example Network Setup

```
Router (192.168.50.0/24)
├── Home Assistant Server (192.168.50.10)
└── Pi Target Device (192.168.50.47)
    ├── SSH server :22
    ├── Supervisor API :8080  
    └── Dashboard Web :3000
```

## Security Model

- **SSH Key Authentication**: HA uses keypair authentication to connect to Pi
- **Local Network**: All communication stays within local network
- **No Incoming**: Pi doesn't initiate connections to HA, only responds
- **API Security**: Supervisor API can be secured with tokens if needed

## Alternative Deployments

**Single Device Mode** (development/testing):
- Run HA and Pi services on same device
- SSH to localhost, API calls to localhost:8080

**Multi-Pi Fleet**:
- One HA server manages multiple Pi targets
- Each Pi gets separate SSH connection + API endpoint
- Example: 192.168.50.47, 192.168.50.48, 192.168.50.49

**Remote Pi over VPN**:
- Pi target accessible via VPN tunnel  
- HA connects via VPN IP address
- Same SSH + API communication patterns