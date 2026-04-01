# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-31

### 🚀 Major Performance Improvements
- **70% Reduction in API Calls**: Implemented efficient batch endpoints
- **Single Integration Endpoint**: `/api/v1/ha/integration` provides all data in one call
- **Pre-computed Dashboard URLs**: Eliminated client-side URL construction
- **Config Version Tracking**: Automatic change detection without polling

### ✨ Dynamic Entity Discovery  
- **Automatic Entity Creation**: Entities discovered from Supervisor API instead of hardcoded
- **Real-time Updates**: WebSocket events for instant state changes
- **Smart Entity Management**: Platform-specific entities (sensors, binary_sensors, buttons)
- **Hot Reloading**: New entities appear without HA restart

### 🔧 Enhanced Supervisor API
- **New HA Endpoints**: Three specialized endpoints for integration efficiency
- **Bulk State Fetching**: Single call retrieves states for all entities  
- **Service Config Monitoring**: Automatic detection of service configuration changes
- **Health Aggregation**: Combined health status across all capabilities

### 📦 HACS Ready Package
- **HACS Metadata**: Proper configuration for Home Assistant Community Store
- **Installation Guide**: Comprehensive README with setup instructions
- **Troubleshooting**: Detailed debugging and testing guides
- **Documentation**: Enhanced info.md for HACS discovery

### 🛠 Developer Improvements
- **Optimized Coordinator**: Streamlined data fetching and state management
- **Error Handling**: Better fallback mechanisms for API unavailability
- **Logging**: Enhanced debug information for troubleshooting
- **Type Safety**: Improved type hints and validation

### 🐛 Bug Fixes
- Fixed SSH connection pooling issues
- Resolved WebSocket reconnection logic
- Corrected entity state synchronization
- Improved error recovery for network issues

## [0.1.18] - Previous Version

### Features
- SSH-based deployment system
- Static entity definitions
- Basic service monitoring
- Manual configuration management