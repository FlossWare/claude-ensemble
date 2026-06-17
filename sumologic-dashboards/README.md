# Sumo Logic AI Observability Dashboards

**Created:** 2026-06-16  
**Location:** `/Library/Admin Recommended/Disseminator/dashboards`  
**Sumo Logic Instance:** https://rhcorporate.sumologic.com

---

## Dashboard Files

1. **sumo-dashboard-1-ai-latency.json** - AI Service Latency & Performance
2. **sumo-dashboard-2-ai-errors.json** - AI Error Monitoring & Alerts
3. **sumo-dashboard-3-ai-cost.json** - AI Cost Tracking & Budget

---

## Import Instructions

### Step 1: Access Red Hat Sumo Logic
```
https://rhcorporate.sumologic.com
```

### Step 2: Navigate to Dashboards Folder
```
Library → Admin Recommended → Disseminator → dashboards
```

### Step 3: Import Each Dashboard

1. Click **"+ New"** → **"Import"**
2. Copy the JSON content from one of the files above
3. Paste into the import dialog
4. Click **"Import"**
5. Repeat for all 3 dashboards

---

## Dashboard 1: AI Service Latency & Performance

**Panels:**
- **AI Service Latency (p50/p95/p99)** - Line chart showing latency percentiles over time by service
- **AI Service Throughput (queries/min)** - Area chart showing request volume by service and endpoint
- **Top 10 Slowest Queries** - Table of slowest queries with latency and service info
- **Average Latency by Service** - Bar chart comparing average latency across services

**Refresh:** Every 5 minutes  
**Time Range:** Last 1 hour (default)

**Query Pattern:**
```
_sourceCategory=disseminator_ai
| parse "latency_ms=*" as latency
| parse "service=*" as service
| timeslice 5m
| pct(latency, 50, 95, 99) as (p50, p95, p99) by _timeslice, service
```

---

## Dashboard 2: AI Error Monitoring & Alerts

**Panels:**
- **Error Count (last hour)** - Single value metric with color thresholds (green <10, yellow <50, red >50)
- **Success Rate %** - Single value metric with gauge (green >99%, yellow >95%, red <95%)
- **Total Queries** - Single value showing total query count
- **Error Patterns (AI-Powered LogReduce)** - Table using Sumo Logic's AI to automatically group similar errors

**Refresh:** Every 1 minute  
**Time Range:** Last 1 hour (default)

**Key Feature:** LogReduce automatically detects error patterns without manual regex!

**Query Pattern:**
```
_sourceCategory=disseminator_ai
| where status="error"
| parse "error=*" as error_message
| logreduce error_message
| count by _signature
| sort by _count desc
| limit 10
```

---

## Dashboard 3: AI Cost Tracking & Budget

**Panels:**
- **Cost Today** - Single value with thresholds (green <$50, yellow <$100, red >$100)
- **Cost This Week** - Single value showing 7-day total
- **Projected Monthly Cost** - Calculated from 7-day average × 30
- **Daily Cost Trend** - Stacked area chart showing cost over time by service
- **Cost by Service (Last 7 Days)** - Pie chart showing cost breakdown

**Refresh:** Every 1 hour  
**Time Range:** Last 7 days (default)

**Query Pattern:**
```
_sourceCategory=disseminator_ai
| parse "cost_usd=*" as cost
| parse "service=*" as service
| timeslice 1d
| sum(cost) as daily_cost by _timeslice, service
```

---

## Required Log Format

For these dashboards to work, AI services must send logs to Sumo Logic with this format:

```python
# Example log line
logger.info("service=vector-search endpoint=/search latency_ms=45 status=success cost_usd=0.001 query=test")
```

**Required Fields:**
- `service` - Service name (e.g., "vector-search", "rerank", "intent-detection")
- `endpoint` - API endpoint (e.g., "/search", "/rerank")
- `latency_ms` - Request latency in milliseconds
- `status` - "success" or "error"
- `cost_usd` - Cost per request (use 0 for free services)
- `query` - (Optional) Search query text
- `error` - (Optional) Error message if status="error"

**Log Destination:**
- Sumo Logic Source Category: `disseminator_ai`

---

## Configure AI Services to Send Logs

### Option 1: Via Splunk Forwarder (Recommended)

Use existing tower-playbooks pattern:

**Create:** `tower-playbooks/roles/disseminator_install_ai_splunkforwarder/files/inputs.conf`

```ini
[monitor:///var/log/ai-service/*.log]
disabled = false
index = disseminator_ai
sourcetype = python_json
```

**Deploy:**
```bash
ansible-playbook -i inventory/prod disseminator_install_ai_splunkforwarder.yml
```

### Option 2: Direct Logging in Python

```python
import logging

logger = logging.getLogger(__name__)

def log_ai_request(service, endpoint, latency_ms, status, cost_usd=0, query="", error=""):
    log_data = f"service={service} endpoint={endpoint} latency_ms={latency_ms} status={status} cost_usd={cost_usd}"
    if query:
        log_data += f" query={query}"
    if error:
        log_data += f" error={error}"
    
    if status == "error":
        logger.error(log_data)
    else:
        logger.info(log_data)

# Usage
import time
start = time.time()
try:
    result = vector_search(query)
    latency_ms = (time.time() - start) * 1000
    log_ai_request("vector-search", "/search", latency_ms, "success", cost_usd=0.001, query=query)
except Exception as e:
    latency_ms = (time.time() - start) * 1000
    log_ai_request("vector-search", "/search", latency_ms, "error", error=str(e))
```

---

## Next Steps After Import

### 1. Set Up Alerts (Recommended)

In Sumo Logic UI, create monitors based on dashboard queries:

**High Latency Alert:**
```
_sourceCategory=disseminator_ai
| parse "latency_ms=*" as latency
| where latency > 1000
| count
```
- Trigger: Count > 10 in 5 minutes
- Action: Email + Slack

**High Error Rate Alert:**
```
_sourceCategory=disseminator_ai
| where status="error"
| count
```
- Trigger: Count > 50 in 5 minutes (>1% error rate)
- Action: PagerDuty + Email

**Daily Cost Exceeded Alert:**
```
_sourceCategory=disseminator_ai
| parse "cost_usd=*" as cost
| where _messagetime >= now() - 1d
| sum(cost) as daily_cost
| where daily_cost > 50
```
- Trigger: Daily cost > $50
- Action: Email to engineering + finance

### 2. Enable Sumo Logic Dojo AI (Optional)

Sumo Logic has built-in AI for anomaly detection:

1. Go to **AI/ML** tab in Sumo Logic
2. Enable **Dojo AI** for `disseminator_ai` source category
3. Configure sensitivity: Medium (recommended)

**What you get:**
- Automatic anomaly detection ("latency increased 300% vs last week")
- Root cause analysis ("error spike correlated with deployment at 14:32")
- Predictive alerting (warns BEFORE problems happen)

### 3. Test with Sample Data

Send a test log to verify dashboards work:

```bash
# On an AI service server
echo "service=vector-search endpoint=/search latency_ms=45 status=success cost_usd=0.001 query=test" >> /var/log/ai-service/app.log
```

Wait 1-2 minutes, then check dashboards in Sumo Logic.

---

## Troubleshooting

### Dashboards are empty / "No data"

**Check 1:** Verify logs are reaching Sumo Logic
```
_sourceCategory=disseminator_ai
| count
```

If count = 0, logs aren't flowing. Check:
- Splunk forwarder is running
- Log files exist at `/var/log/ai-service/*.log`
- Source category is configured as `disseminator_ai`

**Check 2:** Verify log format
```
_sourceCategory=disseminator_ai
| limit 10
```

Logs should have `service=`, `latency_ms=`, `status=` fields.

### Parse errors in dashboards

If you see parse errors, your log format doesn't match. Verify logs use:
```
key=value key2=value2
```

NOT JSON format:
```json
{"key": "value"}
```

### Dashboards show wrong time range

Default time range is 1 hour (latency/errors) or 7 days (cost).
Click the time picker in top-right to adjust.

---

## Support

**Questions?** See research documents:
- `research/2026-06/sumo-logic-platform-research.md` - Sumo Logic platform overview
- `research/2026-06/ai-initiatives-assessment-2026-06-16.md` - AI observability strategy
- `research/2026-06/tower-playbooks-analysis-2026-06-16.md` - Ansible deployment guide

---

**Document Status:** Complete  
**Last Updated:** 2026-06-16  
**Maintained By:** Search Engineering Team
