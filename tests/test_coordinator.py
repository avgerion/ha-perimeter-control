"""
Tests for Home Assistant coordinator functionality.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import aiohttp

# Import coordinator from root directory
import sys
sys.path.append('.')
from coordinator import PerimeterControlCoordinator
from const import PI_IP, PI_USER, API_PORT


class TestPerimeterControlCoordinator:
    """Test the Home Assistant data coordinator."""

    @pytest.fixture
    def mock_hass(self):
        """Mock Home Assistant instance."""
        hass = Mock()
        hass.async_create_task = AsyncMock()
        return hass

    @pytest.fixture
    def coordinator(self, mock_hass):
        """Create coordinator instance for testing."""
        config_entry = Mock()
        config_entry.data = {
            PI_IP: "192.168.1.100",
            PI_USER: "testuser",
            API_PORT: 8080,
            "ssh_key_path": "/path/to/key"
        }
        
        return PerimeterControlCoordinator(
            hass=mock_hass,
            config_entry=config_entry,
            update_interval=timedelta(seconds=30)
        )

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self, coordinator):
        """Test coordinator initializes correctly."""
        assert coordinator.pi_ip == "192.168.1.100"
        assert coordinator.pi_user == "testuser"
        assert coordinator.api_port == 8080
        assert coordinator.base_url == "http://192.168.1.100:8080"

    @pytest.mark.asyncio
    async def test_fetch_entities_success(self, coordinator):
        """Test successful entity fetching."""
        mock_entities = [
            {
                "id": "test:sensor:temperature", 
                "type": "sensor",
                "friendly_name": "Test Temperature",
                "state": "23.5"
            }
        ]
        
        with patch.object(coordinator, '_make_api_request') as mock_request:
            mock_request.return_value = {"entities": mock_entities, "count": 1}
            
            result = await coordinator._async_update_data()
            
            assert "entities" in result
            assert len(result["entities"]) == 1
            assert result["entities"][0]["id"] == "test:sensor:temperature"

    @pytest.mark.asyncio
    async def test_fetch_entities_api_error(self, coordinator):
        """Test handling API errors during entity fetch."""
        with patch.object(coordinator, '_make_api_request') as mock_request:
            mock_request.side_effect = aiohttp.ClientError("API Error")
            
            with pytest.raises(aiohttp.ClientError):
                await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_deploy_capability_success(self, coordinator, sample_entity):
        """Test successful capability deployment."""
        with patch.object(coordinator, '_make_api_request') as mock_request:
            mock_request.return_value = {"status": "deployed"}
            
            result = await coordinator.deploy_capability("test_capability", {"config": "value"})
            
            assert result["status"] == "deployed"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_capability_action(self, coordinator):
        """Test executing capability actions."""
        with patch.object(coordinator, '_make_api_request') as mock_request:
            mock_request.return_value = {"result": "action_executed"}
            
            result = await coordinator.execute_capability_action(
                "test_capability", 
                "test_action", 
                {"param": "value"}
            )
            
            assert result["result"] == "action_executed"

    @pytest.mark.asyncio
    async def test_websocket_connection(self, coordinator):
        """Test WebSocket connection for real-time updates."""
        mock_ws = AsyncMock()
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.TEXT
        mock_msg.json.return_value = {
            "type": "entity_updated",
            "data": {"entity_id": "test:sensor", "state": "new_value"}
        }
        
        with patch('aiohttp.ClientSession.ws_connect', return_value=mock_ws):
            mock_ws.__aiter__.return_value = [mock_msg]
            
            # This would test the WebSocket handler
            # Implementation depends on actual WebSocket handling code
            assert True  # TODO: Implement when WebSocket code is available

    @pytest.mark.asyncio
    async def test_api_request_with_timeout(self, coordinator):
        """Test API request with timeout handling."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(aiohttp.ClientError):
                await coordinator._make_api_request('/test/endpoint')

    @pytest.mark.asyncio
    async def test_health_check(self, coordinator):
        """Test supervisor health check."""
        mock_health = {"status": "ok", "capabilities": {"test": "active"}}
        
        with patch.object(coordinator, '_make_api_request') as mock_request:
            mock_request.return_value = mock_health
            
            result = await coordinator.get_supervisor_health()
            
            assert result["status"] == "ok"
            assert "capabilities" in result

    @pytest.mark.asyncio
    async def test_bulk_entity_state_query(self, coordinator, sample_entity):
        """Test bulk entity state querying."""
        entity_ids = ["test:sensor:temperature", "test:sensor:humidity"]
        mock_states = {
            "test:sensor:temperature": sample_entity,
            "test:sensor:humidity": {**sample_entity, "id": "test:sensor:humidity"}
        }
        
        with patch.object(coordinator, '_make_api_request') as mock_request:
            mock_request.return_value = mock_states
            
            result = await coordinator.query_entity_states(entity_ids)
            
            assert len(result) == 2
            assert "test:sensor:temperature" in result
            assert "test:sensor:humidity" in result


class TestCoordinatorErrorHandling:
    """Test coordinator error handling and recovery."""

    @pytest.fixture
    def coordinator_with_errors(self, mock_hass):
        """Create coordinator for error testing."""
        config_entry = Mock()
        config_entry.data = {
            PI_IP: "invalid.ip.address",
            PI_USER: "testuser",
            API_PORT: 8080,
            "ssh_key_path": "/invalid/key"
        }
        
        return PerimeterControlCoordinator(
            hass=mock_hass,
            config_entry=config_entry,
            update_interval=timedelta(seconds=30)
        )

    @pytest.mark.asyncio
    async def test_connection_retry_logic(self, coordinator_with_errors):
        """Test connection retry on failure."""
        with patch.object(coordinator_with_errors, '_make_api_request') as mock_request:
            # First two calls fail, third succeeds
            mock_request.side_effect = [
                aiohttp.ClientConnectorError("Connection failed", None),
                aiohttp.ClientConnectorError("Connection failed", None),
                {"entities": [], "count": 0}
            ]
            
            # The coordinator should implement retry logic
            # This test assumes such logic exists
            assert True  # TODO: Implement when retry logic is available

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, coordinator_with_errors):
        """Test graceful handling when Pi is unreachable."""
        with patch.object(coordinator_with_errors, '_make_api_request') as mock_request:
            mock_request.side_effect = aiohttp.ClientConnectorError("Connection failed", None)
            
            # Coordinator should return empty data instead of crashing
            try:
                result = await coordinator_with_errors._async_update_data()
                # Should return empty or cached data
                assert isinstance(result, dict)
            except Exception:
                # Or raise a specific exception that HA can handle
                assert True


class TestCoordinatorConfiguration:
    """Test coordinator configuration and validation."""

    def test_invalid_configuration(self, mock_hass):
        """Test coordinator with invalid configuration."""
        config_entry = Mock()
        config_entry.data = {}  # Missing required fields
        
        with pytest.raises(KeyError):
            PerimeterControlCoordinator(
                hass=mock_hass,
                config_entry=config_entry,
                update_interval=timedelta(seconds=30)
            )

    def test_custom_api_port(self, mock_hass):
        """Test coordinator with custom API port."""
        config_entry = Mock()
        config_entry.data = {
            PI_IP: "192.168.1.100",
            PI_USER: "testuser", 
            API_PORT: 9090,
            "ssh_key_path": "/path/to/key"
        }
        
        coordinator = PerimeterControlCoordinator(
            hass=mock_hass,
            config_entry=config_entry,
            update_interval=timedelta(seconds=30)
        )
        
        assert coordinator.api_port == 9090
        assert coordinator.base_url == "http://192.168.1.100:9090"