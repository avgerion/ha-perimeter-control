"""Service Framework - Base classes for modular service architecture.

This module provides the foundation for the component-based service architecture,
allowing services to compose functionality from shared, reusable components.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

from .ssh_client import SshClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class ResourceRequirement:
    """Resource requirement specification for components and services."""
    cpu_cores: float = 0.1  # CPU cores required
    memory_mb: int = 64     # Memory in MB
    disk_mb: int = 50       # Disk space in MB
    
    def __add__(self, other: 'ResourceRequirement') -> 'ResourceRequirement':
        """Add two resource requirements together."""
        return ResourceRequirement(
            cpu_cores=self.cpu_cores + other.cpu_cores,
            memory_mb=self.memory_mb + other.memory_mb,
            disk_mb=self.disk_mb + other.disk_mb
        )


@dataclass 
class ComponentConfig:
    """Configuration for a service component."""
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


class ServiceComponent(ABC):
    """Base class for all service components (hardware, features, dependencies)."""
    
    def __init__(self, name: str, config: Optional[ComponentConfig] = None):
        self.name = name
        self.config = config or ComponentConfig()
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._dependencies: Set[str] = set()
        self._conflicts: Set[str] = set()
    
    @property
    @abstractmethod
    def resource_requirements(self) -> ResourceRequirement:
        """Return resource requirements for this component."""
        pass
    
    @property
    def dependencies(self) -> Set[str]:
        """Return set of component names this depends on."""
        return self._dependencies
        
    @property  
    def conflicts(self) -> Set[str]:
        """Return set of component names this conflicts with."""
        return self._conflicts
    
    @abstractmethod
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Validate that this component can be deployed on the target system."""
        pass
    
    @abstractmethod
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy this component to the target system."""
        pass
    
    async def cleanup(self, ssh_client: SshClient) -> bool:
        """Clean up component resources. Override if needed."""
        return True


class HardwareInterface(ServiceComponent):
    """Base class for hardware interface components with automatic HA entity generation."""
    
    def __init__(self, name: str, config: Optional[ComponentConfig] = None):
        super().__init__(name, config)
        self._detected_devices: List[Dict[str, Any]] = []
    
    @abstractmethod
    async def detect_hardware(self, ssh_client: SshClient) -> List[Dict[str, Any]]:
        """Detect available hardware and return device information."""
        pass
    
    @abstractmethod  
    async def generate_entities(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate HA entity schemas for detected devices."""
        pass
    
    async def get_auto_entities(self, ssh_client: SshClient) -> List[Dict[str, Any]]:
        """Get automatically generated entities for this hardware interface."""
        devices = await self.detect_hardware(ssh_client)
        self._detected_devices = devices
        return await self.generate_entities(devices)


class BaseService:
    """Base service class with component composition and lifecycle management."""
    
    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(f"{__name__}.{service_id}")
        self._components: Dict[str, ServiceComponent] = {}
        self._deployment_order: List[str] = []
    
    def add_component(self, component: ServiceComponent, deploy_order: Optional[int] = None) -> None:
        """Add a component to this service."""
        self._components[component.name] = component
        
        # Insert into deployment order at specified position or append
        if deploy_order is not None:
            self._deployment_order.insert(deploy_order, component.name)
        else:
            self._deployment_order.append(component.name)
    
    def get_component(self, name: str) -> Optional[ServiceComponent]:
        """Get a component by name."""
        return self._components.get(name)
    
    @property
    def total_resource_requirements(self) -> ResourceRequirement:
        """Calculate total resource requirements for all components."""
        total = ResourceRequirement()
        for component in self._components.values():
            if component.config.enabled:
                total += component.resource_requirements
        return total
    
    def check_component_conflicts(self) -> List[str]:
        """Check for conflicts between enabled components."""
        conflicts = []
        enabled_components = {name: comp for name, comp in self._components.items() 
                            if comp.config.enabled}
        
        for comp_name, component in enabled_components.items():
            for conflict_name in component.conflicts:
                if conflict_name in enabled_components:
                    conflicts.append(f"{comp_name} conflicts with {conflict_name}")
        
        return conflicts
    
    def resolve_dependencies(self) -> List[str]:
        """Resolve component dependencies and return deployment order."""
        # Simple topological sort for dependency resolution
        enabled_components = {name: comp for name, comp in self._components.items() 
                            if comp.config.enabled}
        
        visited = set()
        temp_visited = set()
        result = []
        
        def visit(comp_name: str) -> None:
            if comp_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {comp_name}")
            if comp_name in visited:
                return
                
            temp_visited.add(comp_name)
            
            # Visit dependencies first
            if comp_name in enabled_components:
                component = enabled_components[comp_name]
                for dep_name in component.dependencies:
                    if dep_name in enabled_components:
                        visit(dep_name)
                    else:
                        self.logger.warning(f"Missing dependency: {dep_name} for {comp_name}")
            
            temp_visited.remove(comp_name)
            visited.add(comp_name)
            if comp_name in enabled_components:
                result.append(comp_name)
        
        # Visit all enabled components
        for comp_name in enabled_components:
            visit(comp_name)
        
        return result
    
    async def validate_deployment(self, ssh_client: SshClient) -> bool:
        """Validate that this service can be deployed."""
        # Check component conflicts
        conflicts = self.check_component_conflicts()
        if conflicts:
            self.logger.error(f"Component conflicts detected: {conflicts}")
            return False
        
        # Validate each component
        deployment_order = self.resolve_dependencies()
        for comp_name in deployment_order:
            component = self._components[comp_name]
            if not await component.validate_requirements(ssh_client):
                self.logger.error(f"Component {comp_name} validation failed")
                return False
        
        return True
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy this service using component composition."""
        try:
            # Validate before deployment
            if not await self.validate_deployment(ssh_client):
                return False
            
            # Deploy components in dependency order
            deployment_order = self.resolve_dependencies()
            self.logger.info(f"Deploying {self.service_id} components in order: {deployment_order}")
            
            for comp_name in deployment_order:
                component = self._components[comp_name]
                self.logger.info(f"Deploying component: {comp_name}")
                
                if not await component.deploy(ssh_client, deployment_path):
                    self.logger.error(f"Component {comp_name} deployment failed")
                    return False
            
            self.logger.info(f"Service {self.service_id} deployed successfully")
            return True
            
        except Exception as exc:
            self.logger.error(f"Service {self.service_id} deployment failed: {exc}")
            return False
    
    async def get_hardware_entities(self, ssh_client: SshClient, deployed_services: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """Get all automatically generated entities from hardware interfaces.
        
        Args:
            ssh_client: SSH client for hardware detection
            deployed_services: Set of service IDs that are actually deployed (for entity assignment)
        """
        entities = []
        for component in self._components.values():
            if isinstance(component, HardwareInterface) and component.config.enabled:
                try:
                    component_entities = await component.get_auto_entities(ssh_client)
                    entities.extend(component_entities)
                except Exception as exc:
                    self.logger.warning(f"Failed to get entities from {component.name}: {exc}")
        
        # Assign capability IDs based on hardware type registration and deployed services
        entities = hardware_registry.assign_capability_ids(entities, deployed_services)
        
        return entities


class HardwareRegistry:
    """Registry for mapping hardware types to services and capabilities."""
    
    def __init__(self):
        self._hardware_to_services: Dict[str, Set[str]] = {}  # Hardware type -> set of service IDs
        self._service_capabilities: Dict[str, Set[str]] = {}  # Service ID -> set of hardware types
        self._priority_handlers: Dict[str, str] = {}  # Hardware type -> preferred service ID
    
    def register_hardware_handler(self, hardware_type: str, service_id: str, priority: bool = False) -> None:
        """Register which service handles a specific hardware type.
        
        Args:
            hardware_type: Type of hardware (e.g., 'bluetooth', 'camera')
            service_id: Service that handles this hardware
            priority: If True, this service is the preferred handler for this hardware type
        """
        if hardware_type not in self._hardware_to_services:
            self._hardware_to_services[hardware_type] = set()
        self._hardware_to_services[hardware_type].add(service_id)
        
        if service_id not in self._service_capabilities:
            self._service_capabilities[service_id] = set()
        self._service_capabilities[service_id].add(hardware_type)
        
        if priority or hardware_type not in self._priority_handlers:
            self._priority_handlers[hardware_type] = service_id
    
    def get_services_for_hardware(self, hardware_type: str) -> Set[str]:
        """Get all services that can handle a specific hardware type."""
        return self._hardware_to_services.get(hardware_type, set())
    
    def get_primary_service_for_hardware(self, hardware_type: str) -> Optional[str]:
        """Get the preferred service for a specific hardware type."""
        return self._priority_handlers.get(hardware_type)
    
    def get_hardware_for_service(self, service_id: str) -> Set[str]:
        """Get all hardware types handled by a service."""
        return self._service_capabilities.get(service_id, set())
    
    def assign_capability_ids(self, entities: List[Dict[str, Any]], preferred_services: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """Assign capability_id to entities based on their hardware_type.
        
        Args:
            entities: List of entity dictionaries with hardware_type
            preferred_services: Set of service IDs to prefer when multiple services handle the same hardware
        """
        preferred_services = preferred_services or set()
        
        for entity in entities:
            hardware_type = entity.get("hardware_type")
            if not hardware_type:
                continue
                
            # Get possible services for this hardware type
            possible_services = self.get_services_for_hardware(hardware_type)
            
            if not possible_services:
                # No registered handler, skip assignment
                entity.pop("hardware_type", None)
                continue
            
            # Choose service based on priority
            chosen_service = None
            
            # First, try preferred services
            preferred_matches = possible_services & preferred_services
            if preferred_matches:
                chosen_service = next(iter(preferred_matches))  # Pick first match
            else:
                # Fall back to primary service for this hardware type
                chosen_service = self.get_primary_service_for_hardware(hardware_type)
                if chosen_service not in possible_services:
                    # Primary not available, pick any available
                    chosen_service = next(iter(possible_services))
            
            if chosen_service:
                entity["capability_id"] = chosen_service
            
            # Remove hardware_type as it's no longer needed
            entity.pop("hardware_type", None)
            
        return entities


class ComponentRegistry:
    """Registry for managing shared components across services."""
    
    def __init__(self):
        self._component_types: Dict[str, type] = {}
        self._shared_instances: Dict[str, ServiceComponent] = {}
    
    def register_component_type(self, name: str, component_class: type) -> None:
        """Register a component type for reuse."""
        self._component_types[name] = component_class
    
    def create_component(self, name: str, config: Optional[ComponentConfig] = None) -> ServiceComponent:
        """Create a component instance, reusing shared instances where appropriate."""
        if name not in self._component_types:
            raise ValueError(f"Unknown component type: {name}")
        
        # For now, create new instances. Later we can add sharing logic for appropriate components.
        component_class = self._component_types[name]
        return component_class(name, config)
    
    def get_shared_component(self, name: str) -> Optional[ServiceComponent]:
        """Get a shared component instance."""
        return self._shared_instances.get(name)
    
    def set_shared_component(self, name: str, component: ServiceComponent) -> None:
        """Set a shared component instance."""
        self._shared_instances[name] = component


# Global registries
component_registry = ComponentRegistry()
hardware_registry = HardwareRegistry()


# Utility Functions

async def robust_system_package_install(ssh_client: SshClient, packages: List[str], logger: Optional[logging.Logger] = None) -> bool:
    """
    Robust system package installation with automatic dpkg recovery.
    
    Args:
        ssh_client: SSH client for remote execution
        packages: List of package names to install
        logger: Logger instance (defaults to module logger)
        
    Returns:
        bool: True if installation succeeded, False otherwise
    """
    if not packages:
        return True
        
    if logger is None:
        logger = _LOGGER
    
    try:
        # Check and fix dpkg state first
        await _ensure_dpkg_ready(ssh_client, logger)
        
        # Update package list
        logger.info("Updating package lists...")
        await ssh_client.async_run("sudo apt-get update")
        
        # Install packages with retry logic
        packages_str = ' '.join(packages)
        install_cmd = f"sudo apt-get install -y {packages_str}"
        
        for attempt in range(3):  # Try up to 3 times
            try:
                logger.info(f"Installing system packages (attempt {attempt + 1}/3): {packages_str}")
                await ssh_client.async_run(install_cmd)
                logger.info(f"Successfully installed system packages: {packages_str}")
                return True
            except Exception as install_exc:
                logger.warning(f"Package install attempt {attempt + 1} failed: {install_exc}")
                
                if attempt < 2:  # Not the last attempt
                    # Try to fix dpkg issues before retry
                    await _fix_dpkg_issues(ssh_client, logger)
                    await asyncio.sleep(2)  # Brief delay before retry
                else:
                    # Last attempt failed, log comprehensive error
                    logger.error(f"All package installation attempts failed: {install_exc}")
                    return False
        
        return False
    except Exception as exc:
        logger.error(f"System package installation failed: {exc}")
        return False


async def _ensure_dpkg_ready(ssh_client: SshClient, logger: logging.Logger) -> None:
    """Ensure dpkg is in a ready state before package operations."""
    try:
        # Check if dpkg is interrupted - catch errors since dpkg --audit may fail
        from .ssh_client import SshCommandError
        try:
            result = await ssh_client.async_run("sudo dpkg --audit")
            if result and "broken due to failed removal or installation" in result:
                logger.info("Detected interrupted dpkg state, attempting repair...")
                await _fix_dpkg_issues(ssh_client, logger)
        except SshCommandError:
            # dpkg --audit failed, likely means dpkg is in bad state - try to fix
            logger.info("dpkg --audit failed, attempting repair...")
            await _fix_dpkg_issues(ssh_client, logger)
    except Exception as e:
        logger.warning(f"Could not check dpkg status: {e}")


async def _fix_dpkg_issues(ssh_client: SshClient, logger: logging.Logger) -> None:
    """Attempt to fix common dpkg issues."""
    from .ssh_client import SshCommandError
    
    dpkg_fixes = [
        ("sudo dpkg --configure -a", "Configuring interrupted packages"),
        ("sudo apt-get -f install", "Fixing broken dependencies"),
        ("sudo apt-get clean", "Cleaning package cache"),
        ("sudo apt-get autoremove", "Removing unused packages")
    ]
    
    for fix_cmd, description in dpkg_fixes:
        try:
            logger.info(f"Running dpkg fix: {description}")
            await ssh_client.async_run(fix_cmd)  # Allow errors to be caught
        except SshCommandError as e:
            logger.warning(f"Dpkg fix command failed ({fix_cmd}): {e}")
        except Exception as e:
            logger.warning(f"Dpkg fix command failed ({fix_cmd}): {e}")