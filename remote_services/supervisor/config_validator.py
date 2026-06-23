"""
PerimeterControl Configuration Schema Validator

Validates YAML configuration structure against PerimeterControl schema.
Bridges current nested dict format with future ESPHome-like list format.

Current Format (supported today):
  services:
    gpio_control:
      relays:
        pins: [...]
      inputs:
        pins: [...]

Future Format (design doc, not yet implemented):
  gpio_control:
    - name: relays
      pins: [...]
    - name: inputs
      pins: [...]

Both formats validate identically; conversion happens in deployer if needed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("perimetercontrol.config_validator")


class ConfigValidationError(Exception):
    """Raised when config validation fails."""
    pass


class PerimeterControlSchema:
    """Schema validator for perimeterControl.conf.yaml files."""
    
    # Known capability types
    KNOWN_CAPABILITIES = {
        "gpio_control",
        "photo_booth",
        "network_isolator",
        "ble_gatt_repeater",
        "esl_access_point",
        "wildlife_monitor",
    }
    
    # Mapping of capability type → validation function
    # Each should accept (config_dict) and return List[error_strings]
    _capability_validators: Dict[str, callable] = {}
    
    @classmethod
    def register_validator(cls, capability_type: str, validator: callable) -> None:
        """Register a validation function for a capability type."""
        cls._capability_validators[capability_type] = validator
    
    @staticmethod
    def validate_top_level(config: Dict[str, Any]) -> List[str]:
        """Validate top-level config structure."""
        errors = []
        
        if not isinstance(config, dict):
            return ["Config must be a YAML mapping (dict)"]
        
        # Check for required sections
        if "services" not in config and "nodes" not in config:
            # Allow either old format (services at root) or new format (nodes)
            logger.debug("Config has no 'services' or 'nodes' section")
        
        return errors
    
    @staticmethod
    def validate_services(services: Dict[str, Any]) -> List[str]:
        """Validate services section structure.
        
        Expected format:
        {
          "gpio_control": {
            "relays": {...},        # instance name → instance config
            "inputs": {...}
          },
          "photo_booth": {
            "booth1": {...}
          }
        }
        """
        errors = []
        
        if not isinstance(services, dict):
            return ["'services' must be a mapping"]
        
        for cap_type, instances in services.items():
            if not isinstance(instances, dict):
                errors.append(
                    f"services.{cap_type} must be a mapping "
                    f"(instance_name → config), got {type(instances).__name__}"
                )
                continue
            
            # Each instance should have a name (the key) and config (the value)
            for instance_name, instance_config in instances.items():
                if not isinstance(instance_config, dict):
                    errors.append(
                        f"services.{cap_type}.{instance_name} must be a mapping, "
                        f"got {type(instance_config).__name__}"
                    )
        
        return errors
    
    @classmethod
    def validate_capability(cls, cap_type: str, cap_config: Dict[str, Any]) -> List[str]:
        """Validate a single capability type's configuration.
        
        Args:
            cap_type: Capability type (e.g., "gpio_control")
            cap_config: Full config dict with 'services' section
                       (capabilities receive this format)
        
        Returns:
            List of error strings (empty = valid)
        """
        errors = []
        
        # Check if capability is known
        if cap_type not in cls.KNOWN_CAPABILITIES:
            logger.warning("Unknown capability type: %s", cap_type)
            # Don't error on unknown types—allows forward compatibility
        
        # Use registered validator if available
        if cap_type in cls._capability_validators:
            validator = cls._capability_validators[cap_type]
            validator_errors = validator(cap_config)
            errors.extend([f"{cap_type}: {e}" for e in validator_errors])
        
        return errors
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> List[str]:
        """Validate entire configuration file.
        
        Returns list of error strings. Empty list = valid config.
        """
        errors = []
        
        # Layer 1: Top-level structure
        errors.extend(cls.validate_top_level(config))
        if errors:
            return errors  # Stop early if structure is wrong
        
        # Layer 2: Services section
        services = config.get("services", {})
        if services:
            errors.extend(cls.validate_services(services))
        
        # Layer 3: Per-capability validation
        for cap_type, instances in services.items():
            if not isinstance(instances, dict):
                continue  # Already caught by validate_services
            
            # Build config dict for this capability
            # (format expected by capability.validate_config)
            cap_config = {
                "type": cap_type,
                "services": {
                    cap_type: instances
                }
            }
            
            errors.extend(cls.validate_capability(cap_type, cap_config))
        
        return errors
    
    @classmethod
    def validate_file(cls, config_path: Path) -> List[str]:
        """Load and validate a YAML config file.
        
        Args:
            config_path: Path to perimeterControl.conf.yaml
        
        Returns:
            List of error strings
        """
        import yaml
        
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            return [f"Config file not found: {config_path}"]
        except yaml.YAMLError as e:
            return [f"YAML parse error in {config_path}: {e}"]
        except Exception as e:
            return [f"Failed to read {config_path}: {e}"]
        
        return cls.validate_config(config)


def validate_and_report(config_path: Path, raise_on_error: bool = False) -> bool:
    """Validate config and log results.
    
    Args:
        config_path: Path to config file
        raise_on_error: If True, raise ConfigValidationError on validation failure
    
    Returns:
        True if valid, False otherwise
    """
    errors = PerimeterControlSchema.validate_file(config_path)
    
    if errors:
        logger.error(f"Config validation failed for {config_path}:")
        for error in errors:
            logger.error(f"  • {error}")
        
        if raise_on_error:
            raise ConfigValidationError(
                f"Config validation failed: {'; '.join(errors)}"
            )
        return False
    
    logger.info(f"Config validation passed: {config_path}")
    return True
