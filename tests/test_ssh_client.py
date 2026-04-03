"""
Tests for SSH client functionality.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import asyncssh

# Import the SSH client from the root directory
import sys
sys.path.append('.')
from ssh_client import SshClient, SshConnectionError


class TestSshClient:
    """Test SSH client functionality."""

    @pytest.fixture
    def ssh_client(self):
        """Create SSH client instance for testing."""
        return SshClient(
            host="192.168.1.100",
            port=22,
            user="testuser",
            private_key="fake_key_content"
        )

    @pytest.mark.asyncio
    async def test_connection_success(self, ssh_client):
        """Test successful SSH connection."""
        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            with patch('asyncssh.import_private_key') as mock_import_key:
                mock_import_key.return_value = "mock_key"
                
                result = await ssh_client._connect()
                
                assert result == mock_conn
                mock_connect.assert_called_once()
                mock_import_key.assert_called_once_with("fake_key_content")

    @pytest.mark.asyncio
    async def test_connection_timeout(self, ssh_client):
        """Test SSH connection timeout."""
        with patch('asyncssh.connect') as mock_connect:
            mock_connect.side_effect = asyncio.TimeoutError()
            
            with patch('asyncssh.import_private_key'):
                with pytest.raises(SshConnectionError):
                    await ssh_client._connect()

    @pytest.mark.asyncio
    async def test_connection_error(self, ssh_client):
        """Test SSH connection error."""
        with patch('asyncssh.connect') as mock_connect:
            mock_connect.side_effect = OSError("Connection refused")
            
            with patch('asyncssh.import_private_key'):
                with pytest.raises(SshConnectionError):
                    await ssh_client._connect()

    @pytest.mark.asyncio
    async def test_async_run_command(self, ssh_client):
        """Test running a command via SSH."""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.stdout = "command output"
        mock_result.returncode = 0
        mock_conn.run.return_value = mock_result
        
        ssh_client._conn = mock_conn
        
        result = await ssh_client.async_run("echo test")
        
        assert result == "command output"
        mock_conn.run.assert_called_once_with("echo test")

    @pytest.mark.asyncio 
    async def test_async_run_command_failure(self, ssh_client):
        """Test SSH command failure."""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_result.returncode = 1
        mock_conn.run.return_value = mock_result
        
        ssh_client._conn = mock_conn
        
        with pytest.raises(SshConnectionError, match="command failed"):
            await ssh_client.async_run("false")

    @pytest.mark.asyncio
    async def test_async_close(self, ssh_client):
        """Test closing SSH connection."""
        mock_conn = AsyncMock()
        ssh_client._conn = mock_conn
        
        await ssh_client.async_close()
        
        mock_conn.close.assert_called_once()
        mock_conn.wait_closed.assert_called_once()
        assert ssh_client._conn is None


class TestSshClientIntegration:
    """Integration tests for SSH client (requires mock SSH server)."""

    @pytest.mark.asyncio
    async def test_full_command_cycle(self):
        """Test complete SSH command execution cycle."""
        # This would require a mock SSH server or real SSH connection
        # For now, this is a placeholder for integration tests
        assert True  # TODO: Implement with test SSH server


class TestSshConnectionError:
    """Test SSH connection error handling."""

    def test_ssh_connection_error_creation(self):
        """Test creating SSH connection error."""
        error = SshConnectionError("test error")
        assert str(error) == "test error"
        assert isinstance(error, Exception)

    def test_ssh_connection_error_from_exception(self):
        """Test creating SSH connection error from another exception."""
        original = ConnectionRefusedError("Connection refused")
        error = SshConnectionError(str(original))
        assert "Connection refused" in str(error)