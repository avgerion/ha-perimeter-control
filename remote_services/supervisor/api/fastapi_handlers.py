"""
FastAPI REST API handlers for the PerimeterControl Supervisor.

This replaces the Tornado-based handlers with FastAPI for better documentation,
type safety, and modern async patterns.

Route map
---------
GET  /api/v1/node/info                          → get_node_info()
GET  /api/v1/entities                           → get_entities()
GET  /api/v1/entities/{entity_id}               → get_entity_state(entity_id)
POST /api/v1/entities/states/query              → query_entity_states(entity_query)
GET  /api/v1/ha/integration                     → get_ha_integration()
GET  /api/v1/ha/dashboard-urls                  → get_ha_dashboard_urls()
GET  /api/v1/ha/config-status                   → get_ha_config_status()
GET  /api/v1/capabilities                       → get_capabilities()
POST /api/v1/capabilities/{capability_id}/deploy → deploy_capability(capability_id)
POST /api/v1/capabilities/{capability_id}/actions/{action} → capability_action(capability_id, action)
GET  /api/v1/deployments                        → get_deployments()
POST /api/v1/deployments                        → bulk_deploy(deployment_spec)
GET  /api/v1/health                             → get_health()
GET  /api/v1/metrics                            → get_metrics()
GET  /api/v1/services                           → get_services()
GET  /api/v1/services/{service_id}/config       → get_service_config(service_id)
PUT  /api/v1/services/{service_id}/config       → update_service_config(service_id, config)
GET  /api/v1/services/{service_id}/access       → get_service_access(service_id)
PUT  /api/v1/services/{service_id}/access       → update_service_access(service_id, access_config)
GET  /api/v1/node/features                      → get_node_features()
WS   /api/v1/events                             → websocket_events() [WebSocket endpoint]
"""

from __future__ import annotations

import glob
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
import yaml

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Pydantic Models for Request/Response
# ------------------------------------------------------------------

class NodeInfo(BaseModel):
    """Node information response model."""
    hostname: str
    platform: str
    version: str
    uptime_seconds: float
    cpu_count: int
    memory_total: int
    disk_free: int

class EntityState(BaseModel):
    """Entity state model."""
    entity_id: str
    state: Any
    attributes: Dict[str, Any] = Field(default_factory=dict)
    last_changed: str
    last_updated: str

class EntityQuery(BaseModel):
    """Entity states bulk query model."""
    entity_ids: List[str]

class ServiceInfo(BaseModel):
    """Service information model."""
    id: str
    name: str
    version: Optional[str] = None
    descriptor_file: str
    runtime: Optional[str] = None
    config_file: Optional[str] = None
    error: Optional[str] = None

class ServiceConfig(BaseModel):
    """Service configuration model."""
    config: Dict[str, Any]

class DashboardUrl(BaseModel):
    """Dashboard URL information model."""
    url: str
    name: str
    port: int
    mode: str
    status: str

class DashboardUrls(BaseModel):
    """Dashboard URLs response model."""
    services: Dict[str, DashboardUrl]
    timestamp: str

class HealthCheck(BaseModel):
    """Health check response model."""
    status: str = "healthy"
    timestamp: str
    services: Dict[str, str] = Field(default_factory=dict)

class DeploymentSpec(BaseModel):
    """Deployment specification model."""
    capabilities: List[str]
    target_node: Optional[str] = None
    force: bool = False

# ------------------------------------------------------------------
# Dependency Injection
# ------------------------------------------------------------------

def get_supervisor():
    """Dependency to get supervisor instance from app state."""
    # This will be set during app creation
    from .main import app_supervisor
    return app_supervisor

def get_services_dir(supervisor = Depends(get_supervisor)) -> Path:
    """Get services directory path."""
    return supervisor.config_dir / "services"

def get_runtime_dir(supervisor = Depends(get_supervisor)) -> Path:
    """Get runtime directory path.""" 
    return supervisor.state_dir / "runtime"

# ------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------

def create_supervisor_api() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="PerimeterControl Supervisor API",
        description="REST API for managing PerimeterControl services and capabilities",
        version="1.0.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/node/info", response_model=NodeInfo)
    async def get_node_info(supervisor = Depends(get_supervisor)) -> NodeInfo:
        """Get basic node information."""
        import platform
        import psutil
        import shutil
        
        return NodeInfo(
            hostname=platform.node(),
            platform=f"{platform.system()} {platform.release()}",
            version="1.0.0",  # TODO: Get from supervisor version
            uptime_seconds=psutil.boot_time(),
            cpu_count=psutil.cpu_count(),
            memory_total=psutil.virtual_memory().total,
            disk_free=shutil.disk_usage("/").free
        )

    @app.get("/api/v1/node/features")
    async def get_node_features(supervisor = Depends(get_supervisor)) -> Dict[str, Any]:
        """Get node feature capabilities."""
        # TODO: Implement feature detection
        return {
            "bluetooth": True,
            "camera": True,
            "i2c": True,
            "gpio": True,
            "networking": True
        }

    @app.get("/api/v1/entities", response_model=List[EntityState])
    async def get_entities(supervisor = Depends(get_supervisor)) -> List[EntityState]:
        """Get all entity states."""
        entities = []
        try:
            for entity_data in supervisor.db.list_entities():
                entities.append(EntityState(
                    entity_id=entity_data["entity_id"],
                    state=entity_data.get("state"),
                    attributes=entity_data.get("attributes", {}),
                    last_changed=entity_data.get("last_changed", datetime.utcnow().isoformat()),
                    last_updated=entity_data.get("last_updated", datetime.utcnow().isoformat())
                ))
        except Exception as e:
            logger.error(f"Failed to get entities: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve entities")
        
        return entities

    @app.get("/api/v1/entities/{entity_id}", response_model=EntityState)
    async def get_entity_state(entity_id: str, supervisor = Depends(get_supervisor)) -> EntityState:
        """Get a specific entity's state."""
        try:
            entity_data = supervisor.db.get_entity_state(entity_id)
            if entity_data is None:
                raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
                
            return EntityState(
                entity_id=entity_id,
                state=entity_data.get("state"),
                attributes=entity_data.get("attributes", {}),
                last_changed=entity_data.get("last_changed", datetime.utcnow().isoformat()),
                last_updated=entity_data.get("last_updated", datetime.utcnow().isoformat())
            )
        except Exception as e:
            logger.error(f"Failed to get entity state for {entity_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve entity state")

    @app.post("/api/v1/entities/states/query", response_model=List[EntityState])
    async def query_entity_states(query: EntityQuery, supervisor = Depends(get_supervisor)) -> List[EntityState]:
        """Query multiple entity states."""
        entities = []
        try:
            for entity_id in query.entity_ids:
                entity_data = supervisor.db.get_entity_state(entity_id)
                if entity_data:
                    entities.append(EntityState(
                        entity_id=entity_id,
                        state=entity_data.get("state"),
                        attributes=entity_data.get("attributes", {}),
                        last_changed=entity_data.get("last_changed", datetime.utcnow().isoformat()),
                        last_updated=entity_data.get("last_updated", datetime.utcnow().isoformat())
                    ))
        except Exception as e:
            logger.error(f"Failed to query entity states: {e}")
            raise HTTPException(status_code=500, detail="Failed to query entity states")
            
        return entities

    @app.get("/api/v1/services", response_model=List[ServiceInfo])
    async def get_services(services_dir: Path = Depends(get_services_dir)) -> List[ServiceInfo]:
        """Get all service descriptors."""
        services = []
        
        if services_dir.exists():
            for path in sorted(services_dir.glob("*.service.yaml")):
                try:
                    descriptor = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    metadata = descriptor.get("metadata", {})
                    spec = descriptor.get("spec", {})
                    
                    services.append(ServiceInfo(
                        id=metadata.get("id") or path.stem.replace(".service", ""),
                        name=metadata.get("name", "unknown"),
                        version=metadata.get("version"),
                        descriptor_file=str(path),
                        runtime=(spec.get("runtime") or {}).get("type"),
                        config_file=(spec.get("config_file") or {}).get("path"),
                    ))
                except Exception as exc:
                    services.append(ServiceInfo(
                        id=path.stem.replace(".service", ""),
                        name="invalid_descriptor",
                        descriptor_file=str(path),
                        error=str(exc)
                    ))

        return services

    @app.get("/api/v1/services/{service_id}/config")
    async def get_service_config(service_id: str, supervisor = Depends(get_supervisor)) -> Dict[str, Any]:
        """Get service configuration."""
        descriptor = _load_service_descriptor(service_id, supervisor)
        if descriptor is None:
            raise HTTPException(status_code=404, detail=f"Service descriptor not found: {service_id}")

        cfg_path = _service_config_path(descriptor, supervisor)
        if cfg_path is None:
            raise HTTPException(status_code=422, detail="Descriptor missing spec.config_file.path")

        if not cfg_path.exists():
            return {
                "service_id": service_id,
                "config_file": str(cfg_path),
                "loaded": False,
                "config": {}
            }

        try:
            config_data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")

        return {
            "service_id": service_id,
            "config_file": str(cfg_path),
            "loaded": True,
            "config": config_data
        }

    @app.put("/api/v1/services/{service_id}/config")
    async def update_service_config(service_id: str, config_update: ServiceConfig, supervisor = Depends(get_supervisor)) -> Dict[str, Any]:
        """Update service configuration."""
        descriptor = _load_service_descriptor(service_id, supervisor)
        if descriptor is None:
            raise HTTPException(status_code=404, detail=f"Service descriptor not found: {service_id}")

        cfg_path = _service_config_path(descriptor, supervisor)
        if cfg_path is None:
            raise HTTPException(status_code=422, detail="Descriptor missing spec.config_file.path")

        try:
            # Create config directory if it doesn't exist
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write updated configuration
            config_content = yaml.dump(config_update.config, default_flow_style=False)
            cfg_path.write_text(config_content, encoding="utf-8")
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")

        return {
            "service_id": service_id,
            "config_file": str(cfg_path),
            "status": "updated",
            "timestamp": datetime.utcnow().isoformat()
        }

    @app.get("/api/v1/ha/dashboard-urls", response_model=DashboardUrls) 
    async def get_ha_dashboard_urls(services_dir: Path = Depends(get_services_dir), supervisor = Depends(get_supervisor)) -> DashboardUrls:
        """Get dashboard URLs for all services."""
        services = {}
        
        if services_dir.exists():
            for path in sorted(services_dir.glob("*.service.yaml")):
                try:
                    descriptor = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    metadata = descriptor.get("metadata", {})
                    spec = descriptor.get("spec", {})
                    access_profile = spec.get("access_profile", {})
                    
                    service_id = metadata.get("id") or path.stem.replace(".service", "")
                    dashboard_url = _compute_dashboard_url(access_profile)
                    
                    if dashboard_url:  # Only include accessible services
                        services[service_id] = DashboardUrl(
                            url=dashboard_url,
                            name=metadata.get("name", "unknown"),
                            port=access_profile.get("port", 8080),
                            mode=access_profile.get("mode", "localhost"),
                            status="active" if _service_is_active(service_id, supervisor) else "inactive"
                        )
                except Exception:
                    continue
                    
        return DashboardUrls(
            services=services,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    @app.get("/api/v1/health", response_model=HealthCheck)
    async def get_health() -> HealthCheck:
        """Get system health status."""
        return HealthCheck(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            services={"supervisor": "healthy"}  # TODO: Add service health checks
        )

    @app.get("/api/v1/metrics", response_class=PlainTextResponse)
    async def get_metrics() -> str:
        """Get Prometheus metrics."""
        # TODO: Implement Prometheus metrics collection
        return """# HELP perimetercontrol_supervisor_uptime_seconds Supervisor uptime in seconds
# TYPE perimetercontrol_supervisor_uptime_seconds counter
perimetercontrol_supervisor_uptime_seconds 3600
"""

    return app

# ------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------

def _load_service_descriptor(service_id: str, supervisor) -> Optional[Dict[str, Any]]:
    """Load service descriptor from file."""
    services_dir = supervisor.config_dir / "services"
    descriptor_path = services_dir / f"{service_id}.service.yaml"
    
    if not descriptor_path.exists():
        return None
    
    try:
        return yaml.safe_load(descriptor_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load service descriptor {service_id}: {e}")
        return None

def _service_config_path(descriptor: Dict[str, Any], supervisor) -> Optional[Path]:
    """Get service config file path from descriptor."""
    config_file_spec = descriptor.get("spec", {}).get("config_file")
    if not config_file_spec:
        return None
        
    config_path = config_file_spec.get("path")
    if not config_path:
        return None
        
    return supervisor.config_dir / config_path

def _compute_dashboard_url(access_profile: Dict[str, Any]) -> Optional[str]:
    """Compute dashboard URL from access profile."""
    mode = access_profile.get("mode", "localhost")
    if mode == "isolated":
        return None
        
    port = access_profile.get("port", 8080)
    return f"http://localhost:{port}/"

def _service_is_active(service_id: str, supervisor) -> bool:
    """Check if service is active."""
    try:
        capabilities = supervisor.db.list_capabilities()
        for cap in capabilities:
            if cap.get("id") == service_id:
                return cap.get("status") == "active"
    except Exception:
        pass
    return False