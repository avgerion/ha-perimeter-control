"""
Pytest configuration for PerimeterControl tests.
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Test fixtures


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_ssh_client():
    """Mock SSH client for testing deployment functionality."""
    mock_client = Mock()
    mock_client.async_run = AsyncMock()
    mock_client.async_run.return_value = "success"
    mock_client.async_close = AsyncMock()
    return mock_client


@pytest.fixture
def mock_supervisor():
    """Mock supervisor instance for testing coordinator."""
    mock_supervisor = Mock()
    mock_supervisor.get_entities = Mock(return_value=[])
    mock_supervisor.get_health = Mock(return_value={"status": "ok"})
    return mock_supervisor


@pytest.fixture 
def sample_entity():
    """Sample entity for testing."""
    return {
        "id": "test:sensor:temperature",
        "type": "sensor",
        "friendly_name": "Test Temperature",
        "capability": "test_capability",
        "state": "23.5",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "icon": "mdi:thermometer",
        "attributes": {
            "last_updated": "2026-04-03T04:46:47Z"
        }
    }


@pytest.fixture
def sample_service_descriptor():
    """Sample service descriptor YAML."""
    return {
        "id": "test_service",
        "name": "Test Service", 
        "version": "1.0.0",
        "description": "Test service for pytest",
        "port": 8080,
        "access_mode": "localhost",
        "dependencies": [],
        "config": {
            "enable_logging": True,
            "log_level": "INFO"
        }
    }


# Async test support
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Test markers
pytest_plugins = ["pytest_asyncio"]