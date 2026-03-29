# PAwR Campaign Engine

Dynamic ESL (Electronic Shelf Label) content scheduling and deployment via PAwR (Periodic Advertising with Responses).

## Campaign Model

A **campaign** is a scheduled broadcast task that sends content to a group of ESL tags.

```
Campaign
├── Schedule (CRON)
├── Target Group (tags)
├── Payload
│   ├── Static (e.g., "Fresh Produce")
│   ├── Dynamic (fetch from API)
│   ├── Time-based (sunrise/sunset, business hours)
│   └── Conditional (if stock < 5, show "Low Stock")
├── Retry Policy
└── Metrics
```

## Campaign Definition

```yaml
# campaigns/daily_price_update.yaml

id: daily_price_update
name: Daily Price Update
description: Update all retail shelf prices at 9 AM

# Scheduling
schedule:
  # CRON expression (runs at 9:00 AM daily)
  cron: "0 9 * * *"
  # Or: interval_sec: 3600
  # Or: timestamp: "2026-03-28T09:00:00Z"

# Target tags/groups
targets:
  - group_id: grocery_produce
    tags:
      - esl_001
      - esl_002
      - esl_003
  - group_id: grocery_meat
    tags:
      - esl_010
      - esl_011

# Content specification
content:
  - field: line_1
    type: static
    value: "Fresh Produce"

  - field: line_2
    type: dynamic
    source: api
    endpoint: "https://api.example.com/prices/produce"
    json_path: "$.current_price"  # Extract from response
    format: "Price: ${value:.2f}"
    refresh_interval_sec: 3600    # Re-fetch every hour
    fallback: "Call for price"    # If API fails

  - field: image
    type: static_url
    url: "https://cdn.example.com/produce.png"

# Retry logic
retry:
  max_attempts: 3
  backoff_base_sec: 2
  backoff_max_sec: 30
  on_failure: use_fallback

# Monitoring
monitoring:
  enabled: true
  success_threshold_percent: 95  # Alert if < 95% tags updated
  metric_collection:
    enabled: true
    include_latency: true
    include_tag_responses: true
```

## Campaign Execution

Supervisor manages campaign lifecycle:

```python
class CampaignEngine:
    def __init__(self, pawr_runtime):
        self.pawr = pawr_runtime
        self.campaigns = {}
        self.scheduler = APScheduler()
        
    def load_campaigns(self, campaign_dir):
        """Load all campaigns from directory."""
        for campaign_file in Path(campaign_dir).glob("*.yaml"):
            campaign = yaml.safe_load(campaign_file)
            self.register_campaign(campaign)
    
    def register_campaign(self, campaign_config):
        """Register campaign with scheduler."""
        cid = campaign_config["id"]
        
        # Parse schedule
        trigger = self._parse_schedule(campaign_config["schedule"])
        
        # Schedule execution
        self.scheduler.add_job(
            self.execute_campaign,
            trigger=trigger,
            args=[cid],
            id=cid,
            name=campaign_config["name"]
        )
        
        self.campaigns[cid] = campaign_config
    
    def execute_campaign(self, campaign_id):
        """Execute a campaign: prepare payload and broadcast."""
        campaign = self.campaigns[campaign_id]
        correlation_id = uuid.uuid4().hex
        
        logger.info(f"[{correlation_id}] Campaign {campaign_id} starting")
        
        try:
            # 1. Build payload
            payload = self._build_payload(campaign, correlation_id)
            
            # 2. Broadcast to all target tags
            results = self._broadcast_to_tags(
                campaign["targets"],
                payload,
                correlation_id
            )
            
            # 3. Collect metrics
            success_count = sum(1 for r in results if r["success"])
            success_rate = success_count / len(results)
            
            logger.info(f"[{correlation_id}] Campaign complete: {success_rate*100:.1f}% success")
            
            # 4. Record campaign execution
            self._record_campaign_execution(campaign_id, results, correlation_id)
            
            # 5. Check alert thresholds
            threshold = campaign["monitoring"]["success_threshold_percent"]
            if success_rate * 100 < threshold:
                logger.warn(f"[{correlation_id}] Success rate {success_rate*100}% below threshold {threshold}%")
                emit_alert("campaign_low_success", campaign_id, success_rate)
        
        except Exception as e:
            logger.error(f"[{correlation_id}] Campaign failed: {e}")
            emit_alert("campaign_execution_failed", campaign_id, str(e))
```

## Payload Building

Build content with fallbacks:

```python
def _build_payload(self, campaign, correlation_id):
    """Build ESL payload from campaign definition."""
    
    payload = {}
    
    for field_spec in campaign["content"]:
        field_name = field_spec["field"]
        field_type = field_spec["type"]
        
        try:
            if field_type == "static":
                value = field_spec["value"]
                
            elif field_type == "dynamic":
                value = self._fetch_dynamic_value(
                    field_spec,
                    correlation_id
                )
                if "format" in field_spec:
                    value = field_spec["format"].format(value=value)
            
            elif field_type == "static_url":
                value = field_spec["url"]
            
            elif field_type == "time_based":
                value = self._compute_time_based_value(field_spec)
            
            elif field_type == "conditional":
                value = self._evaluate_conditional(field_spec)
            
            payload[field_name] = value
            
        except Exception as e:
            logger.warn(f"[{correlation_id}] Field {field_name} failed: {e}")
            payload[field_name] = field_spec.get("fallback", "")
    
    return payload

def _fetch_dynamic_value(self, spec, correlation_id):
    """Fetch value from API with timeout."""
    
    endpoint = spec["endpoint"]
    json_path = spec["json_path"]
    timeout = spec.get("timeout_sec", 10)
    
    try:
        response = requests.get(endpoint, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        value = jmespath.search(json_path, data)
        
        logger.debug(f"[{correlation_id}] Fetched {endpoint} → {value}")
        
        return value
    
    except requests.RequestException as e:
        logger.warn(f"[{correlation_id}] API fetch failed: {e}")
        raise
```

## Multi-Tag Broadcasting

Send payload to tags with response tracking:

```python
def _broadcast_to_tags(self, target_groups, payload, correlation_id):
    """Broadcast payload to all target tags and collect responses."""
    
    all_tags = []
    for target_group in target_groups:
        all_tags.extend(target_group["tags"])
    
    results = []
    
    for tag_id in all_tags:
        try:
            # Convert to 48-bit PAwR address
            pawr_addr = self.tag_registry.get_pawr_address(tag_id)
            
            # Send async, but collect response
            response = self.pawr.send_payload_with_response(
                pawr_addr,
                payload,
                timeout_sec=30
            )
            
            results.append({
                "tag_id": tag_id,
                "success": response["status"] == "ack",
                "latency_ms": response["latency_ms"],
                "response_pattern": response.get("response_data"),
            })
            
            logger.debug(f"[{correlation_id}] Tag {tag_id}: {response['status']}")
            
        except Exception as e:
            logger.warn(f"[{correlation_id}] Tag {tag_id} failed: {e}")
            results.append({
                "tag_id": tag_id,
                "success": False,
                "error": str(e),
            })
    
    return results
```

## Campaign Metrics

Store campaign execution history:

```sql
CREATE TABLE campaign_executions (
    id INTEGER PRIMARY KEY,
    campaign_id TEXT,
    execution_time DATETIME,
    correlation_id TEXT,
    total_tags INTEGER,
    successful_tags INTEGER,
    failed_tags INTEGER,
    success_rate REAL,
    avg_latency_ms REAL,
    duration_ms INTEGER,
    errors TEXT,
    payload_hash TEXT
);

CREATE TABLE tag_responses (
    id INTEGER PRIMARY KEY,
    execution_id INTEGER,
    tag_id TEXT,
    success BOOLEAN,
    latency_ms INTEGER,
    response_data BLOB,
    timestamp DATETIME,
    FOREIGN KEY (execution_id) REFERENCES campaign_executions(id)
);
```

Query metrics:

```bash
# Campaign success rate over time
curl "http://localhost:8080/api/v1/capabilities/pawr_esl_advertiser/metrics?campaign_id=daily_price_update&since=7d"

# Response:
{
  "campaign_id": "daily_price_update",
  "executions": [
    {
      "timestamp": "2026-03-28T09:00:00Z",
      "total_tags": 50,
      "success_rate": 0.98,
      "avg_latency_ms": 250
    },
    {
      "timestamp": "2026-03-27T09:00:00Z",
      "total_tags": 50,
      "success_rate": 0.96,
      "avg_latency_ms": 320
    }
  ],
  "trend": "stable"
}
```

## Dynamic Content Examples

### Stock-based pricing

```yaml
content:
  - field: status_line
    type: conditional
    conditions:
      - if: "stock_level < 5"
        then: "LOW STOCK"
      - if: "stock_level == 0"
        then: "OUT OF STOCK"
      - else: "In Stock"
    source: api
    endpoint: "https://api.example.com/inventory"
```

### Time-based display

```yaml
content:
  - field: promotion_line
    type: time_based
    times:
      - start_time: "09:00"
        end_time: "12:00"
        value: "MORNING DEAL: 20% off"
      - start_time: "12:00"
        end_time: "18:00"
        value: "AFTERNOON SPECIAL"
      - start_time: "18:00"
        end_time: "23:00"
        value: "EVENING CLOSING SALE"
```

### Fallback chain

```yaml
content:
  - field: price
    type: dynamic
    sources:
      - endpoint: "https://api.example.com/prices"
        fallback_to_next: true
      - endpoint: "https://backup.example.com/prices"
        fallback_to_next: true
    fallback: "Call store"
```

## Campaign Management API

Control campaigns via REST:

```
# List all campaigns
GET /api/v1/capabilities/pawr_esl_advertiser/campaigns
  → Returns: [daily_price_update, stock_monitor, ...]

# Get campaign details
GET /api/v1/capabilities/pawr_esl_advertiser/campaigns/daily_price_update
  → Returns: campaign config + metrics

# Manually trigger campaign
POST /api/v1/capabilities/pawr_esl_advertiser/campaigns/daily_price_update/execute

# Pause campaign
POST /api/v1/capabilities/pawr_esl_advertiser/campaigns/daily_price_update/pause

# Update campaign (redeploy without restart)
PUT /api/v1/capabilities/pawr_esl_advertiser/campaigns/daily_price_update
  → Reloads config, reschedules

# Dry-run (show what would be broadcast)
POST /api/v1/capabilities/pawr_esl_advertiser/campaigns/daily_price_update/dry_run
  → Returns: payload preview + tag list
```

## Tag Registry & Pairing

Manage which physical tags are known:

```yaml
# data/esl/tag_registry.yaml

tags:
  - id: esl_001
    pawr_address: "AA:BB:CC:DD:EE:01"
    location: "Aisle 3, Shelf 2"
    group: grocery_produce
    
  - id: esl_002
    pawr_address: "AA:BB:CC:DD:EE:02"
    location: "Aisle 3, Shelf 3"
    group: grocery_produce
```

Discovery/pairing workflow in dashboard:

1. **Scan for tags** — detect PAwR advertisers in range
2. **Pair tag** — establish connection, get permanent address
3. **Register** — assign group + location
4. **Test** — send test payload to verify

## Observability

Monitor campaign health in Tornado/Bokeh dashboard:

```
Campaign Status Board
├── daily_price_update
│   Status: Active
│   Last run: 2026-03-28 09:00 (29 minutes ago)
│   Success rate: 98% (49/50 tags)
│   Next run: 2026-03-29 09:00 (23 hours, 31 minutes)
│   Recipients: 50 tags (grocery_produce, grocery_meat)
│
├── stock_monitor
│   Status: Active
│   Last run: 2026-03-28 10:30 (1 minute ago)
│   Success rate: 100% (20/20 tags)
│   Next run: 2026-03-28 10:35 (4 minutes, 59 seconds)
│   Recipients: 20 tags (electronics)
```
