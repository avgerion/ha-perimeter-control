# Service Architecture & Hardware-to-Home Assistant Integration

## Overview

This document outlines the planned architectural improvements for the Perimeter Control system, focusing on a modular service architecture with shared components and streamlined hardware-to-Home Assistant integration.

## Current Architecture Issues

### Deployment Layer
- **Code Duplication**: Each service deployer repeats similar deployment logic
- **Resource Conflicts**: No shared resource management between services
- **Hardware Detection**: Each service independently detects hardware capabilities
- **Dependency Management**: Redundant package installation across services

### Hardware-to-HA Integration Gap
- **Manual Entity Creation**: Capabilities must manually register entities with specific schemas
- **Hardware Discovery**: No automatic detection and entity generation for new hardware
- **Entity Lifecycle**: Manual management of entity creation, updates, and cleanup
- **Configuration Complexity**: Multi-step process to add new hardware types

## Proposed Architecture: Layered Service Framework

### 1. Base Service Framework

```python
# Base classes for all services
class BaseService:
    """Base service with common deployment, configuration, and lifecycle management."""
    
class ServiceComponent:
    """Base component class for features, hardware interfaces, and dependencies."""
    
class HardwareInterface:
    """Base hardware interface with automatic HA entity generation."""
```

### 2. Component Layer

#### Hardware Components
```python
class BluetoothInterface(HardwareInterface):
    """Bluetooth hardware management with automatic BLE device entity creation."""
    
class CameraInterface(HardwareInterface):
    """Camera hardware with automatic camera entity and controls."""
    
class NetworkInterface(HardwareInterface):
    """Network hardware with automatic connectivity and stats entities."""
    
class I2CSensorInterface(HardwareInterface):
    """I2C sensors with automatic sensor entity creation based on device IDs."""
```

#### Feature Components  
```python
class MotionDetection(ServiceComponent):
    """Motion detection feature that can be shared across camera services."""
    
class DataLogging(ServiceComponent):
    """Data logging feature shared by wildlife and network services."""
    
class AlertSystem(ServiceComponent):
    """Alert/notification system usable by any service."""
```

#### Dependency Components
```python
class PythonDependencies(ServiceComponent):
    """Manages pip packages with conflict resolution."""
    
class SystemDependencies(ServiceComponent):
    """Manages apt packages with dependency tracking."""
    
class ConfigurationManager(ServiceComponent):
    """Centralized configuration management."""
```

### 3. Service Implementation Layer

```python
class BleService(BaseService):
    def __init__(self):
        super().__init__()
        # Compose service from components
        self.bluetooth = BluetoothInterface()
        self.data_logging = DataLogging() 
        self.python_deps = PythonDependencies(['bleak', 'asyncio-mqtt'])
        
class PhotoBoothService(BaseService):
    def __init__(self):
        super().__init__()
        self.camera = CameraInterface()
        self.motion = MotionDetection()
        self.alerts = AlertSystem()
        self.system_deps = SystemDependencies(['v4l2-utils', 'ffmpeg'])
```

## Hardware-to-Home Assistant Integration

### Problem Statement
**Current Process** (8+ manual steps):
1. Detect hardware manually
2. Write capability module  
3. Define entity schemas manually
4. Implement `_publish_entity()` calls
5. Register with entity cache
6. Configure service descriptor
7. Deploy to Pi
8. Wait for HA integration refresh

### Proposed Solution: Auto-Discovery Framework

#### 1. Hardware Detection Engine
```python
class HardwareDetector:
    """Automatically scans system and identifies available hardware."""
    
    async def scan_system(self) -> List[HardwareDevice]:
        """Returns list of detected hardware with capabilities."""
        
    async def detect_bluetooth_devices(self) -> List[BleDevice]:
        """Auto-detect BLE devices and infer entity types from services."""
        
    async def detect_cameras(self) -> List[CameraDevice]:
        """Auto-detect cameras and generate appropriate controls."""
        
    async def detect_i2c_sensors(self) -> List[I2CSensor]:
        """Auto-detect I2C sensors and create sensor entities."""
```

#### 2. Entity Schema Generator
```python
class EntitySchemaGenerator:
    """Generates HA entity schemas from hardware detection."""
    
    def generate_entities_for_device(self, device: HardwareDevice) -> List[EntitySchema]:
        """Auto-generate appropriate entities based on device type and capabilities."""
```

#### 3. Automatic Entity Registration
```python
class AutoEntityManager:
    """Manages automatic entity lifecycle based on hardware state."""
    
    async def sync_hardware_to_entities(self):
        """Automatically create/update/remove entities based on current hardware."""
```

### Target Flow: Hardware-to-HA in 2 Steps

**New Process** (2 steps):
1. **Plug in hardware** → System auto-detects
2. **Refresh integration** → Entities appear in HA automatically

#### Example: BLE Temperature Sensor
```python
# 1. Hardware plugged in → Auto-detected
detected_device = BleDevice(
    address="AA:BB:CC:DD:EE:FF",
    name="Weather Station",
    services=["1809"],  # Health Thermometer Service  
    device_class="thermometer"
)

# 2. Entities auto-generated
entities = [
    BinarySensorEntity(
        id="ble:weather_station:connected", 
        device_class="connectivity"
    ),
    SensorEntity(
        id="ble:weather_station:temperature",
        device_class="temperature", 
        unit="°C"
    ),
    SensorEntity(
        id="ble:weather_station:battery",
        device_class="battery",
        unit="%"  
    )
]
```

## Implementation Plan

### Phase 1: Component Architecture (Current Priority)
- [ ] Create base service and component classes
- [ ] Refactor existing deployers to use component composition
- [ ] Implement shared resource management
- [ ] Add dependency conflict resolution

### Phase 2: Hardware Interfaces  
- [ ] Create hardware interface base class
- [ ] Implement Bluetooth, Camera, Network, I2C interfaces
- [ ] Add hardware detection engines
- [ ] Test with existing hardware

### Phase 3: Auto-Discovery Framework
- [ ] Build entity schema generator
- [ ] Implement automatic entity registration
- [ ] Create hardware-to-entity mapping system
- [ ] Test end-to-end auto-discovery

### Phase 4: Integration & Testing
- [ ] Integration testing with multiple services
- [ ] Performance optimization
- [ ] Documentation and examples
- [ ] Migration guide for existing deployments

## Benefits

### For Developers
- **Reduced Code Duplication**: Shared components eliminate repeated logic
- **Faster Development**: New services compose existing components
- **Better Testing**: Components can be unit tested independently
- **Cleaner Architecture**: Clear separation of concerns

### For Users  
- **Plug-and-Play Experience**: Hardware automatically appears in HA
- **Fewer Configuration Errors**: Auto-generated entities reduce manual setup
- **Better Reliability**: Shared resource management prevents conflicts
- **Easier Troubleshooting**: Components provide better error isolation

### For System
- **Resource Efficiency**: Shared components reduce memory/CPU usage
- **Deployment Reliability**: Better dependency management prevents conflicts
- **Scalability**: Easy to add new hardware types and services
- **Maintainability**: Changes to shared logic benefit all services

## Next Steps

1. **Complete Current Bug Fixes** - Finish entity registration and deployment issues
2. **Design Component Interfaces** - Define contracts for hardware/feature components  
3. **Create Proof of Concept** - Build one service using new architecture
4. **Implement Auto-Discovery** - Start with simple hardware types (BLE, cameras)
5. **Migrate Existing Services** - Gradually refactor current services to new architecture

## Success Metrics

- **Development Time**: 75% reduction in time to add new hardware support
- **Configuration Complexity**: 90% reduction in manual HA entity setup
- **Resource Efficiency**: 50% reduction in memory usage through component sharing
- **Reliability**: 95% reduction in deployment failures due to resource conflicts
- **User Experience**: Hardware-to-HA integration in under 2 minutes