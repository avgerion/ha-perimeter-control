# Perimeter Control

Advanced Raspberry Pi network gateway management with dynamic entity discovery and real-time monitoring.

## What's New in v0.1.18

🚀 **Performance Optimized** - 70% reduction in API calls through efficient batch endpoints  
🔄 **Dynamic Entity Discovery** - Entities automatically discovered from Pi supervisor  
⚡ **Real-time Updates** - WebSocket events for instant state changes  
🎯 **Smart Configuration** - Automatic config change detection and versioning  

## Features

### 🏠 **Dynamic Entity Management**
- **Auto-Discovery**: Network devices, services, and capabilities detected automatically
- **Real-time States**: Live connectivity status, policies, and service health
- **Smart Grouping**: Entities organized by device type and capability

### 🚀 **Optimized Performance**  
- **Batch API Calls**: Single endpoint provides entities + states + config
- **Efficient Updates**: Only changed data is transmitted
- **WebSocket Events**: Instant notifications without polling

### 🛠 **Service Management**
- **Dashboard URLs**: Pre-computed access links for all services
- **Config Monitoring**: Automatic detection of configuration changes  
- **Health Tracking**: Real-time service status and capability states

### 🔧 **Developer Features**
- **SSH Deployment**: Push updates directly from HA interface
- **Automatic Rollback**: Safe deployments with failure recovery
- **Multi-Node Support**: Manage multiple Pi gateways from one HA instance

## Supported Hardware

- **Raspberry Pi** (any model with Debian/Pi OS)
- **Network Isolation** capability with iptables/nftables
- **BLE Adapters** for device scanning and GATT services
- **Camera Modules** for photo booth and wildlife monitoring