# PerimeterControl Architecture & Service Registry Conventions

## Coordinator and Service Registry: Generic, Config-Driven Design

### Principle
- **All orchestration and integration logic (including the coordinator) must be generic and service-agnostic.**
- **No hardcoded service IDs or special-case logic in code.**
- **All service-specific behavior must be driven by configuration in `const.py` (the service registry).**

### How to Special-Case a Service
- If a service (e.g., a dashboard, supervisor, or health check) requires special handling, add a config flag to its entry in `SERVICE_REGISTRY` in `const.py`.
    - Example: `"is_default_dashboard": True`, `"special_handling": True`, `"health_check": {...}`
- The coordinator and deployer should iterate all services and use these flags to determine behavior.
- Never hardcode service names like `"network_isolator"` in the coordinator or deployer logic.

### Example: Default Dashboard Service
```python
SERVICE_REGISTRY = {
    "network_isolator": {
        "unit": "PerimeterControl-dashboard",
        "port": 5006,
        ...
        "is_default_dashboard": True,  # This service is the default dashboard
    },
    ...
}
```

In the coordinator:
```python
def _get_default_dashboard_service_id(self):
    for sid, sinfo in SERVICE_REGISTRY.items():
        if sinfo.get("is_default_dashboard"):
            return sid
    return None
```

### Documentation Rule
- **All documentation, guides, and code comments must reinforce this config-driven, generic pattern.**
- If you see a hardcoded service ID, refactor it to use a config flag.

## Best Practices
- Add new service types by updating `SERVICE_REGISTRY` and config flags, not by patching logic.
- Use per-service config for all ports, units, health checks, and special behaviors.
- Document any new config flags in `const.py` and reference them in relevant guides.

---

_Last updated: 2026-05-24_
