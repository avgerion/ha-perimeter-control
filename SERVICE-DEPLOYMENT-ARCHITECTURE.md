# Service-Specific Deployment Architecture

## Overview

The Perimeter Control deployment system has been completely refactored from a monolithic deployer into a modular service-specific deployment architecture. This provides better separation of concerns, more efficient resource management, and easier maintenance.

## Architecture Components

### Base Deployer (`base_deployer.py`)
- Provides core deployment infrastructure shared across all services
- Handles system resource checks, SSH operations, file uploads, and common installation phases  
- Base class for all service-specific deployers

### Service-Specific Deployers

#### BLE Deployer (`ble_deployer.py`)
- **Service**: BLE GATT Repeater (`ble_gatt_repeater`)
- **Hardware**: Bluetooth enablement and verification
- **Packages**: `bleak` for BLE operations
- **Files**: BLE scanning and debugging scripts
- **Resource Requirements**: 0.3 CPU cores, 128MB RAM, 50MB disk

#### Network Deployer (`network_deployer.py`) 
- **Service**: Network Isolator (`network_isolator`)
- **Hardware**: Network interface configuration, iptables verification
- **Packages**: `psutil`, `netaddr` for network operations
- **Files**: Network topology scripts, firewall rules
- **Resource Requirements**: 0.2 CPU cores, 96MB RAM, 30MB disk

#### Camera Deployer (`camera_deployer.py`)
- **Service**: Photo Booth (`photo_booth`)
- **Hardware**: Camera interface enablement, GPU memory check
- **Packages**: `pillow`, `opencv-python-headless`, `numpy` for image processing
- **Files**: Photo booth dashboard components  
- **Resource Requirements**: 0.4 CPU cores, 256MB RAM, 200MB disk

#### Wildlife Deployer (`wildlife_deployer.py`)
- **Service**: Wildlife Monitor (`wildlife_monitor`)
- **Hardware**: I2C/SPI sensor interface enablement, GPIO access
- **Packages**: `pandas`, `numpy`, `scipy`, `RPi.GPIO` for data analysis and sensors
- **Files**: Data visualization components
- **Resource Requirements**: 0.3 CPU cores, 200MB RAM, 150MB disk

#### ESL Deployer (`esl_deployer.py`)
- **Service**: ESL AP (`esl_ap`)
- **Hardware**: Advanced Bluetooth LE configuration, advertising capability checks
- **Packages**: `bleak`, `construct`, `cryptography` for ESL protocols
- **Files**: ESL layout and callback management
- **Resource Requirements**: 0.4 CPU cores, 160MB RAM, 80MB disk
- **Conflicts**: Cannot run with `ble_gatt_repeater` (Bluetooth advertising conflicts)

### Main Deployer (`deployer.py`)
- Orchestrates service-specific deployments
- Validates service selection and checks for conflicts
- Handles supervisor installation and service coordination
- Provides fallback legacy deployment for unknown services

## Deployment Flow

### Phase 1: Service Selection & Validation
1. Validate all selected services have deployers
2. Check for service conflicts (e.g., BLE services that can't coexist)
3. Log warnings for unknown services that will use legacy deployment

### Phase 2: Service-Specific Deployment
1. For each selected service, invoke its specialized deployer
2. Each deployer handles its own:
   - Resource requirement checks
   - File uploads (only service-relevant files)
   - Hardware enablement
   - Package installation
   - Configuration deployment
   - Service descriptor deployment

### Phase 3: Supervisor Installation
1. Install supervisor package and systemd services
2. Configure systemd service templates
3. Enable services for startup

### Phase 4: Service Restart
1. Restart supervisor service
2. Restart dashboard service
3. Verify service startup

### Phase 5: Service Verification
1. Check service health and status
2. Provide deployment summary with service-specific status

## Benefits

### Resource Efficiency
- **Targeted Package Installation**: Only packages needed by selected services are installed
- **Hardware-Specific Setup**: Only required hardware interfaces are enabled
- **Optimized Resource Checks**: Service-specific resource requirements instead of worst-case

### Maintainability  
- **Separation of Concerns**: Each service's deployment logic is isolated
- **easier Debugging**: Service-specific logs and error handling
- **Modular Testing**: Individual service deployers can be tested independently

### Conflict Management
- **Service Conflicts**: Automatic detection of conflicting services (e.g., multiple BLE advertisers)
- **Hardware Conflicts**: Prevent enabling conflicting hardware configurations
- **Resource Conflicts**: Accurate resource planning based on actual service requirements

### Development Benefits
- **Focused Development**: Changes to one service don't affect others
- **Easier Extension**: New services can be added by creating new deployers
- **Better Error Messages**: Service-specific error messages and diagnostics

## Backward Compatibility

- **Legacy Fallback**: Unknown services use legacy monolithic deployment
- **Service Descriptors**: Existing service descriptor format is preserved
- **Configuration Files**: Existing configuration format is maintained
- **API Compatibility**: Coordinator interface remains unchanged

## Migration

Version 0.5.0 introduces this new architecture automatically. No manual migration is required:

1. Existing deployments continue to work with legacy fallback
2. New deployments automatically use service-specific deployers
3. Mixed deployments (known + unknown services) are supported

## Configuration

Service-specific deployment is automatic based on service selection. No additional configuration is required.

### Example Service Selection
```python
selected_services = [
    'ble_gatt_repeater',  # Uses BleDeployer
    'network_isolator',   # Uses NetworkDeployer  
    'photo_booth'         # Uses CameraDeployer
]
# wildlife_monitor conflicts would be detected
# esl_ap would conflict with ble_gatt_repeater
```

### Resource Planning Example
```
Base requirements: 0.2 CPU, 128MB RAM, 100MB disk
+ BLE: 0.3 CPU, 128MB RAM, 50MB disk
+ Network: 0.2 CPU, 96MB RAM, 30MB disk  
+ Camera: 0.4 CPU, 256MB RAM, 200MB disk
= Total: 1.1 CPU, 608MB RAM, 380MB disk
```

## Future Enhancements

1. **Service Dependencies**: Automatic service dependency resolution
2. **Dynamic Scaling**: Resource adjustment based on service load
3. **Health Monitoring**: Service-specific health checks and recovery
4. **Update Management**: Service-specific update and rollback capabilities