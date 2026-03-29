# Monitoring & Observability

Structured logging, metrics, and alerting for fleet visibility and troubleshooting.

## Logging Strategy

### Log Levels
- `DEBUG`: Low-level tracing, variable inspection, reconciliation steps
- `INFO`: Significant events (deploy start/end, capability transitions, health checks)
- `WARN`: Recoverable issues (probe failure, retry in progress)
- `ERROR`: Unrecoverable errors (deploy fail, health check max retries)
- `CRITICAL`: System-wide failures (persistent rollback failure, data corruption)

### Structured Logging Format

Every log entry has metadata for querying and correlation:

```json
{
  "timestamp": "2026-03-28T10:30:00.123456Z",
  "level": "INFO",
  "logger": "isolator.supervisor",
  "correlation_id": "cid_abc123",
  "deployment_id": "dep_001",
  "component": "network_isolation",
  "message": "Capability deployed successfully",
  "context": {
    "version": "1.0.0",
    "duration_ms": 5000,
    "services_started": ["isolator", "isolator-traffic"]
  }
}
```

Log to:
- **Local file**: `/var/log/isolator/supervisor.log` (rotated daily, 30-day retention)
- **Standard output**: Journald (for systemd integration)
- **Remote**: Optional syslog/ELK stack for fleet centralization

### Python Logging Configuration

```python
import logging
import json
from pythonjsonlogger import jsonlogger

# JSON formatter for machine parsing
logHandler = logging.FileHandler('/var/log/isolator/supervisor.log')
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Every function gets correlation_id from context
def deploy(deployment_config):
    cid = uuid.uuid4().hex
    logger = logging.LoggerAdapter(logger, {"correlation_id": cid})
    
    logger.info("Deploy started", extra={
        "deployment_id": deployment_id,
        "capabilities": list(deployment_config.keys())
    })
```

### Log Query Examples

All logs queryable via `/api/v1/logs`:

```bash
# Get failed deployments
curl "http://localhost:8080/api/v1/logs?level=ERROR&component=deployment"

# Get all events for correlation ID
curl "http://localhost:8080/api/v1/logs?correlation_id=cid_abc123"

# Get warnings from last hour
curl "http://localhost:8080/api/v1/logs?level=WARN&since=1h&until=now"
```

## Metrics Collection

Prometheus-compatible metrics exposed on `/metrics`:

```
# HELP isolator_deployments_total Total deployments
# TYPE isolator_deployments_total counter
isolator_deployments_total{status="succeeded"} 42
isolator_deployments_total{status="failed"} 2
isolator_deployments_total{status="rolled_back"} 1

# HELP isolator_capability_health Capability health status
# TYPE isolator_capability_health gauge
isolator_capability_health{capability="network_isolation"} 1  # 1=ok, 0=failed
isolator_capability_health{capability="ble_gatt_translator"} 1

# HELP isolator_reconciliation_duration_ms Reconciliation loop duration
# TYPE isolator_reconciliation_duration_ms histogram
isolator_reconciliation_duration_ms_bucket{le="100"} 50
isolator_reconciliation_duration_ms_bucket{le="500"} 125
isolator_reconciliation_duration_ms_bucket{le="1000"} 150
isolator_reconciliation_duration_ms_sum 45000
isolator_reconciliation_duration_ms_count 150

# HELP isolator_resource_cpu_percent CPU usage percent
# TYPE isolator_resource_cpu_percent gauge
isolator_resource_cpu_percent 35

# HELP isolator_resource_ram_mb RAM used in MB
# TYPE isolator_resource_ram_mb gauge
isolator_resource_ram_mb 512

# HELP isolator_entity_update_latency_ms Entity state update latency
# TYPE isolator_entity_update_latency_ms histogram
isolator_entity_update_latency_ms_bucket{entity="traffic_logger_running"} ...
```

## Alerting Rules

Supervisor evaluates alert conditions and sends events:

```python
ALERT_RULES = {
    "high_cpu_usage": {
        "condition": "cpu_load_avg > 0.8",
        "grace_period_sec": 300,
        "action": "emit_event",
    },
    "health_degraded": {
        "condition": "any_capability_health != 'ok'",
        "grace_period_sec": 60,
        "action": "emit_event + log_warn",
    },
    "deployment_failure": {
        "condition": "deployment_status == 'failed'",
        "grace_period_sec": 0,
        "action": "emit_event + log_error",
    },
    "rollback_failure": {
        "condition": "rollback_status == 'failed'",
        "grace_period_sec": 0,
        "action": "emit_event + log_critical + alert_ha",
    },
}
```

HA subscribes to `/api/v1/events/alerts` and creates HA alert entities.

## Dashboard Metrics

Example metrics exposed to Tornado/Bokeh dashboard:

```python
class MetricsDashboardHandler(tornado.web.RequestHandler):
    def get(self):
        metrics = {
            "system": {
                "uptime_sec": get_uptime(),
                "cpu_percent": get_cpu_usage(),
                "ram_mb": get_ram_usage(),
                "disk_free_mb": get_disk_free(),
            },
            "deployments": {
                "total": count_deployments(),
                "succeeded": count_successful_deployments(),
                "failed": count_failed_deployments(),
                "avg_duration_ms": avg_deploy_duration(),
            },
            "capabilities": {
                cap_id: {
                    "status": cap_status,
                    "health": cap_health,
                    "uptime_sec": cap_uptime,
                    "restarts": cap_restart_count,
                }
                for cap_id in all_capabilities()
            },
            "entities": {
                "total": count_exposed_entities(),
                "last_update_ago_sec": seconds_since_last_entity_update(),
            }
        }
        self.write(metrics)
```

## Performance Tracing

Optional detailed tracing for troubleshooting slow operations:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("deploy_capability")
def deploy(cap_id, config):
    with tracer.start_as_current_span("validate_config"):
        validate_config(cap_id, config)
    
    with tracer.start_as_current_span("stage_packages"):
        stage_deployment(cap_id)
    
    with tracer.start_as_current_span("apply_changes"):
        apply_capability_config(cap_id, config)
```

Traces exportable to Jaeger for visualization.

## Health Dashboards

Home Assistant can render Pi health:

```yaml
# ha_integration/dashboard.yaml
views:
  - title: Fleet Health
    cards:
      - type: entity
        entity: sensor.isolator_pi_kitchen_health
        
      - type: history_stats
        entity: binary_sensor.isolator_pi_kitchen_degraded
        period: day
        
      - type: gauge
        entity: sensor.isolator_pi_kitchen_cpu_percent
        
      - type: history_graph
        entities:
          - isolator_pi_kitchen_deployments_total
          - isolator_pi_kitchen_rollbacks_total
```

## Log Aggregation (Optional)

For multi-Pi fleet, centralize logs:

```yaml
# supervisor.yaml
logging:
  local_level: INFO
  remote_syslog:
    enabled: true
    server: syslog.example.com
    port: 514
    protocol: udp
  # Or push to ELK
  elasticsearch:
    enabled: true
    hosts: ["elasticsearch:9200"]
    index_prefix: "isolator"
```

## Diagnostic Bundle Export

User can export full diagnostics for troubleshooting:

```
GET /api/v1/capabilities/network_isolation/diagnostics?format=tar.gz

Response: (tar.gz file)
├── logs/
│   ├── supervisor.log (last 7 days)
│   ├── network_isolation.log
│   └── nftables.log
├── config/
│   ├── network_isolation.yaml
│   └── (active config)
├── state/
│   ├── supervisor.db (snapshot)
│   ├── health_checks.json (last 24h)
│   └── metrics.jsonl (last 24h)
├── system/
│   ├── uname -a
│   ├── systemctl status
│   └── nft list ruleset
└── metadata.json (bundle info + PI details)
```

Share for HA integration debugging.
