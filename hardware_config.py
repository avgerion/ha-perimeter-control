# ─── Configurable Constants ─────────────────────────────────────────────
import os

NETWORK_SERVICE_NAME = os.environ.get('PERIMETERCONTROL_NETWORK_SERVICE', 'network_isolator')
"""Hardware-to-Service mapping configuration.

This file defines which services handle which hardware types.
It can be customized to change how hardware is automatically 
assigned to capabilities and services.
"""

# Default hardware type mappings
# Format: hardware_type -> (primary_service, [alternative_services])
HARDWARE_MAPPINGS = {
    "bluetooth": ("ble_gatt_repeater", []),
    "camera": ("photo_booth", ["wildlife_monitor"]),  # Wildlife can also use cameras
    "network": (NETWORK_SERVICE_NAME, []),
    "i2c_sensor": ("wildlife_monitor", []),
    "bluetooth_advertising": ("esl_ap", []),
    "gpio": ("wildlife_monitor", []),
    "spi": ("wildlife_monitor", []),
}

# Service hardware requirements
# Services that REQUIRE specific hardware to function
SERVICE_HARDWARE_REQUIREMENTS = {
    "ble_gatt_repeater": ["bluetooth"],
    "photo_booth": ["camera"],
    NETWORK_SERVICE_NAME: ["network"],
    "wildlife_monitor": ["i2c_sensor", "camera"],  # Can work with either
    "esl_ap": ["bluetooth_advertising"],
}

# Hardware conflicts
# Hardware types that cannot be used simultaneously
HARDWARE_CONFLICTS = {
    "bluetooth": ["bluetooth_advertising"],  # Can't scan and advertise simultaneously
}

# Hardware detection priorities
# When multiple hardware interfaces detect the same device,
# use this priority order (higher number = higher priority)
DETECTION_PRIORITIES = {
    "bluetooth": 100,
    "camera": 90,
    "network": 80,
    "i2c_sensor": 70,
    "bluetooth_advertising": 60,
    "gpio": 50,
    "spi": 40,
}


def load_hardware_mappings():
    """Load hardware mappings from configuration.
    
    This function can be extended to load from external files,
    environment variables, or other configuration sources.
    """
    return {
        "mappings": HARDWARE_MAPPINGS,
        "requirements": SERVICE_HARDWARE_REQUIREMENTS,
        "conflicts": HARDWARE_CONFLICTS,
        "priorities": DETECTION_PRIORITIES,
    }