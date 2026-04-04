"""Network Isolator service deployer.

Handles deployment of Network Isolator service including:
- Network configuration and iptables rules
- Network topology scripts
- Core isolation functionality
"""
from __future__ import annotations

import logging

from .base_deployer import BaseDeployer, ProgressCallback
from .const import PHASE_SUPERVISOR
from .ssh_client import SshClient

_LOGGER = logging.getLogger(__name__)


class NetworkDeployer(BaseDeployer):
    """Deployer for Network Isolator service."""

    def __init__(
        self,
        client: SshClient,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        super().__init__(client, progress_cb)
        self.service_id = "network_isolator"

    async def deploy(self) -> bool:
        """Deploy Network Isolator service."""
        deployment_id = id(self)
        _LOGGER.warning("=== NETWORK DEPLOYER STARTED === (ID: %s)", deployment_id)
        
        try:
            # Phase 1: Preflight with network-specific resource requirements
            _LOGGER.info("Network Phase 1: Preflight checks (ID: %s)", deployment_id)
            await self.phase_preflight(
                required_cpu=0.1,      # Network operations are very lightweight
                required_memory=48,    # Very minimal memory footprint
                required_disk=20       # Tiny disk usage
            )
            
            # Phase 2: Upload network-specific files
            _LOGGER.info("Network Phase 2: Upload network files (ID: %s)", deployment_id)
            await self.phase_upload_files({
                'scripts': [
                    'apply-rules.py',
                    'network-topology.py',
                    'topology_config.py',
                ]
            })
            
            # Phase 3: Install files
            _LOGGER.info("Network Phase 3: Install files (ID: %s)", deployment_id)
            await self.phase_install()
            
            # Phase 4: Deploy network configuration
            _LOGGER.info("Network Phase 4: Deploy config (ID: %s)", deployment_id)
            await self.phase_config(['perimeterControl.conf.yaml'])
            
            # Phase 5: Configure network capabilities
            _LOGGER.info("Network Phase 5: Configure network capabilities (ID: %s)", deployment_id)
            await self._configure_network_capabilities()
            
            # Phase 6: Install network Python packages
            _LOGGER.info("Network Phase 6: Install network packages (ID: %s)", deployment_id)
            await self.install_python_packages(['psutil', 'netaddr'], 'Network Isolator')
            
            # Phase 7: Deploy service descriptors
            _LOGGER.info("Network Phase 7: Deploy service descriptors (ID: %s)", deployment_id)
            await self.deploy_service_descriptors([self.service_id])
            
            # Phase 8: Install systemd services
            _LOGGER.info("Network Phase 8: Install systemd services (ID: %s)", deployment_id)
            await self.install_systemd_services(['PerimeterControl-supervisor.service.template'])
            
            _LOGGER.warning("=== NETWORK DEPLOYMENT COMPLETED === (ID: %s)", deployment_id)
            return True
            
        except Exception as exc:
            _LOGGER.error("Network deployment failed (ID: %s): %s", deployment_id, exc)
            self._emit_error("network_deploy", f"Network deployment error: {exc}")
            return False

    async def _configure_network_capabilities(self) -> None:
        """Configure network capabilities and iptables rules."""
        self._emit(PHASE_SUPERVISOR, "Configuring network isolation capabilities...", 75)
        
        try:
            # Check if iptables is available
            iptables_check = await self._client.async_run(
                "which iptables >/dev/null 2>&1 && echo AVAILABLE || echo MISSING"
            )
            
            if "MISSING" in iptables_check:
                _LOGGER.warning("iptables not found, network isolation may not work properly")
                self._emit(PHASE_SUPERVISOR, "iptables not available, limited functionality", 76)
            else:
                _LOGGER.info("iptables found, network isolation will be fully functional")
                self._emit(PHASE_SUPERVISOR, "Network tools verified", 76)
            
            # Check network interfaces
            try:
                interfaces_output = await self._client.async_run("ip link show | grep '^[0-9]' | cut -d: -f2")
                interfaces = [iface.strip() for iface in interfaces_output.strip().split('\n') if iface.strip()]
                _LOGGER.info("Network interfaces detected: %s", interfaces)
                self._emit(PHASE_SUPERVISOR, f"Found {len(interfaces)} network interfaces", 77)
                
            except Exception as if_exc:
                _LOGGER.warning("Could not enumerate network interfaces: %s", if_exc)
            
            # Verify IP forwarding capability (needed for some isolation modes)
            try:
                ip_forward_status = await self._client.async_run("cat /proc/sys/net/ipv4/ip_forward")
                if "1" in ip_forward_status:
                    _LOGGER.info("IP forwarding is enabled")
                else:
                    _LOGGER.info("IP forwarding is disabled (may need enabling for some features)")
                self._emit(PHASE_SUPERVISOR, "Network configuration verified", 77)
                
            except Exception as forward_exc:
                _LOGGER.debug("Could not check IP forwarding status: %s", forward_exc)
                
        except Exception as exc:
            _LOGGER.warning("Network capability configuration failed (non-critical): %s", exc)
            self._emit(PHASE_SUPERVISOR, "Network configuration incomplete, continuing...", 77)

    def get_required_services(self) -> list[str]:
        """Return list of systemd services required for network functionality."""
        return ["networking.service", "systemd-networkd.service"]

    def get_hardware_requirements(self) -> dict[str, str]:
        """Return hardware requirements for network functionality."""
        return {
            "network_interfaces": "required",
            "iptables": "preferred",
            "ip_forwarding": "optional",
        }

    def get_package_dependencies(self) -> list[str]:
        """Return Python package dependencies for network functionality."""
        return ["psutil", "netaddr"]

    def get_system_dependencies(self) -> list[str]:
        """Return system package dependencies for network functionality."""
        return ["iptables", "iproute2", "netbase"]