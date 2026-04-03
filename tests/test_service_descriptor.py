"""
Tests for service descriptor functionality.
"""
import pytest
from pathlib import Path
import yaml
from unittest.mock import Mock, patch

# Import from root directory
import sys
sys.path.append('.')
from service_descriptor import ServiceDescriptor, ServiceDescriptorError


class TestServiceDescriptor:
    """Test service descriptor loading and validation."""

    @pytest.fixture
    def valid_service_yaml(self):
        """Valid service descriptor YAML content."""
        return """
id: test_service
name: Test Service
version: 1.0.0
description: A test service for pytest
port: 8080
access_mode: localhost
dependencies:
  - python3
  - systemd
config:
  enable_logging: true
  log_level: INFO
  max_connections: 100
health_check:
  endpoint: /health
  interval: 30
  timeout: 5
capabilities:
  - network_monitoring
  - data_collection
"""

    @pytest.fixture
    def invalid_service_yaml(self):
        """Invalid service descriptor YAML content."""
        return """
name: Test Service
# Missing required 'id' field
version: 1.0.0
port: 8080
"""

    @pytest.fixture
    def service_descriptor_file(self, temp_dir, valid_service_yaml):
        """Create temporary service descriptor file."""
        descriptor_file = temp_dir / "test_service.yaml"
        descriptor_file.write_text(valid_service_yaml)
        return descriptor_file

    def test_load_valid_service_descriptor(self, service_descriptor_file):
        """Test loading a valid service descriptor."""
        descriptor = ServiceDescriptor.from_file(service_descriptor_file)
        
        assert descriptor.id == "test_service"
        assert descriptor.name == "Test Service"
        assert descriptor.version == "1.0.0"
        assert descriptor.port == 8080
        assert descriptor.access_mode == "localhost"
        assert "python3" in descriptor.dependencies
        assert descriptor.config["enable_logging"] is True

    def test_load_invalid_service_descriptor(self, temp_dir, invalid_service_yaml):
        """Test loading an invalid service descriptor."""
        descriptor_file = temp_dir / "invalid_service.yaml"
        descriptor_file.write_text(invalid_service_yaml)
        
        with pytest.raises(ServiceDescriptorError, match="Required field 'id' is missing"):
            ServiceDescriptor.from_file(descriptor_file)

    def test_service_descriptor_validation(self):
        """Test service descriptor field validation."""
        # Test valid descriptor
        valid_data = {
            "id": "test_service",
            "name": "Test Service",
            "version": "1.0.0",
            "port": 8080,
            "access_mode": "localhost"
        }
        
        descriptor = ServiceDescriptor(**valid_data)
        assert descriptor.is_valid()

    def test_service_descriptor_invalid_port(self):
        """Test service descriptor with invalid port."""
        invalid_data = {
            "id": "test_service",
            "name": "Test Service", 
            "version": "1.0.0",
            "port": -1,  # Invalid port
            "access_mode": "localhost"
        }
        
        with pytest.raises(ServiceDescriptorError, match="Port must be between 1 and 65535"):
            ServiceDescriptor(**invalid_data)

    def test_service_descriptor_invalid_access_mode(self):
        """Test service descriptor with invalid access mode."""
        invalid_data = {
            "id": "test_service",
            "name": "Test Service",
            "version": "1.0.0", 
            "port": 8080,
            "access_mode": "invalid_mode"  # Invalid access mode
        }
        
        with pytest.raises(ServiceDescriptorError, match="Access mode must be one of"):
            ServiceDescriptor(**invalid_data)

    def test_service_descriptor_to_dict(self, service_descriptor_file):
        """Test converting service descriptor to dictionary."""
        descriptor = ServiceDescriptor.from_file(service_descriptor_file)
        data = descriptor.to_dict()
        
        assert isinstance(data, dict)
        assert data["id"] == "test_service"
        assert data["name"] == "Test Service"
        assert data["port"] == 8080
        assert "config" in data
        assert "health_check" in data

    def test_service_descriptor_merge_config(self):
        """Test merging service descriptor configurations."""
        base_config = {
            "id": "test_service",
            "name": "Test Service",
            "version": "1.0.0",
            "port": 8080,
            "access_mode": "localhost",
            "config": {"setting1": "value1", "setting2": "value2"}
        }
        
        override_config = {
            "config": {"setting2": "overridden", "setting3": "value3"}
        }
        
        descriptor = ServiceDescriptor(**base_config)
        descriptor.merge_config(override_config)
        
        assert descriptor.config["setting1"] == "value1"  # Preserved
        assert descriptor.config["setting2"] == "overridden"  # Overridden
        assert descriptor.config["setting3"] == "value3"  # Added

    def test_service_descriptor_yaml_parsing_error(self, temp_dir):
        """Test handling YAML parsing errors."""
        invalid_yaml_file = temp_dir / "invalid.yaml"
        invalid_yaml_file.write_text("invalid: yaml: content: [unclosed")
        
        with pytest.raises(ServiceDescriptorError, match="Failed to parse YAML"):
            ServiceDescriptor.from_file(invalid_yaml_file)

    def test_service_descriptor_file_not_found(self):
        """Test handling missing service descriptor file."""
        nonexistent_file = Path("nonexistent.yaml")
        
        with pytest.raises(ServiceDescriptorError, match="Service descriptor file not found"):
            ServiceDescriptor.from_file(nonexistent_file)


class TestServiceDescriptorLoader:
    """Test service descriptor loading functionality."""

    def test_load_multiple_descriptors(self, temp_dir):
        """Test loading multiple service descriptors from directory."""
        # Create multiple descriptor files
        services = [
            {"id": "service1", "name": "Service 1", "port": 8080},
            {"id": "service2", "name": "Service 2", "port": 8081},
            {"id": "service3", "name": "Service 3", "port": 8082}
        ]
        
        for service in services:
            service_file = temp_dir / f"{service['id']}.yaml"
            service_data = {
                **service,
                "version": "1.0.0",
                "access_mode": "localhost"
            }
            service_file.write_text(yaml.safe_dump(service_data))
        
        # Load all descriptors
        descriptors = ServiceDescriptor.load_from_directory(temp_dir)
        
        assert len(descriptors) == 3
        assert all(desc.is_valid() for desc in descriptors)
        service_ids = {desc.id for desc in descriptors}
        assert service_ids == {"service1", "service2", "service3"}

    def test_load_descriptors_skip_invalid(self, temp_dir):
        """Test loading descriptors while skipping invalid ones."""
        # Create one valid and one invalid descriptor
        valid_service = temp_dir / "valid.yaml"
        valid_service.write_text(yaml.safe_dump({
            "id": "valid_service",
            "name": "Valid Service",
            "version": "1.0.0",
            "port": 8080,
            "access_mode": "localhost"
        }))
        
        invalid_service = temp_dir / "invalid.yaml"
        invalid_service.write_text(yaml.safe_dump({
            "name": "Invalid Service",  # Missing 'id'
            "version": "1.0.0",
            "port": 8080
        }))
        
        # Load with skip_invalid=True
        descriptors = ServiceDescriptor.load_from_directory(temp_dir, skip_invalid=True)
        
        assert len(descriptors) == 1
        assert descriptors[0].id == "valid_service"

    def test_load_descriptors_fail_on_invalid(self, temp_dir):
        """Test loading descriptors that fails on invalid ones."""
        # Create invalid descriptor
        invalid_service = temp_dir / "invalid.yaml"
        invalid_service.write_text(yaml.safe_dump({
            "name": "Invalid Service",  # Missing 'id'
            "version": "1.0.0", 
            "port": 8080
        }))
        
        # Load with skip_invalid=False (default)
        with pytest.raises(ServiceDescriptorError):
            ServiceDescriptor.load_from_directory(temp_dir, skip_invalid=False)


class TestServiceDescriptorGeneration:
    """Test service descriptor generation and templating."""

    def test_generate_descriptor_template(self):
        """Test generating a service descriptor template."""
        template = ServiceDescriptor.generate_template(
            service_id="new_service",
            service_name="New Service",
            port=8090
        )
        
        assert template["id"] == "new_service"
        assert template["name"] == "New Service"
        assert template["port"] == 8090
        assert template["version"] == "1.0.0"  # Default
        assert template["access_mode"] == "localhost"  # Default
        assert "config" in template
        assert "health_check" in template

    def test_validate_descriptor_schema(self, sample_service_descriptor):
        """Test validating descriptor against schema."""
        # This assumes a schema validation function exists
        is_valid = ServiceDescriptor.validate_schema(sample_service_descriptor)
        assert is_valid is True

    def test_descriptor_with_custom_fields(self):
        """Test service descriptor with custom/extension fields."""
        custom_data = {
            "id": "custom_service",
            "name": "Custom Service",
            "version": "1.0.0",
            "port": 8080,
            "access_mode": "localhost",
            "custom_field": "custom_value",  # Custom extension field
            "metadata": {
                "author": "pytest",
                "category": "testing"
            }
        }
        
        descriptor = ServiceDescriptor(**custom_data)
        assert descriptor.is_valid()
        assert hasattr(descriptor, 'custom_field')
        assert descriptor.custom_field == "custom_value"