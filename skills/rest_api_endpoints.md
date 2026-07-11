# REST API Endpoints Reference

**Last Updated:** 2026-07-10  
**API Server:** http://aio-01:5000  
**Status:** ✅ OPERATIONAL

---

## Critical Architecture Principle

**ALL database access MUST go through REST API endpoints.**

- ❌ NO component should connect to PostgreSQL directly (aio-01:5433)
- ✅ ALL components use REST API (http://aio-01:5000)
- ✅ Single point of database access
- ✅ Enables caching, rate limiting, auth in future

---

## Knowledge Endpoints

### GET /knowledge/scraped_data/stats

Get scraping statistics.

**Response:**
```json
{
  "total_docs": 8040,
  "last_hour": 1112,
  "last_5min": 0,
  "first_doc": "Wed, 08 Jul 2026 19:23:44 GMT",
  "latest_doc": "Fri, 10 Jul 2026 16:15:54 GMT"
}
```

**Usage:**
```bash
curl -s http://aio-01:5000/knowledge/scraped_data/stats | jq .
```

---

## Monitoring Endpoints

### GET /monitoring/scrapers

Check active scrapers across fleet.

**Response:**
```json
{
  "total_active": 0,
  "workers": [
    {"hostname": "server-01", "active_scrapers": 0},
    {"hostname": "server-02", "active_scrapers": 0}
  ]
}
```

**Usage:**
```bash
curl -s http://aio-01:5000/monitoring/scrapers | jq .
```

### GET /monitoring/health

Overall system health check.

**Response:**
```json
{
  "services": {
    "postgresql_learning": "healthy",
    "postgresql_monitoring": "healthy",
    "redis": "unavailable"
  },
  "timestamp": "..."
}
```

### GET /monitoring/metrics

System metrics (Prometheus-compatible).

**Query params:** None

**Response:**
```json
{
  "metrics": {
    "executions_last_hour": 42,
    "avg_duration_ms": 1234.5,
    "total_cost_usd": 0.12,
    "model_distribution": {"opus": 10, "sonnet": 32}
  }
}
```

### GET /monitoring/executions/stats

Execution statistics with filters.

**Query params:**
- `window`: 1h | 24h | 7d | 30d (default: 24h)
- `model`: Filter by model name
- `outcome`: success | error | partial

**Example:**
```bash
curl -s "http://aio-01:5000/monitoring/executions/stats?window=1h&model=opus" | jq .
```

### GET /monitoring/costs

Cost analysis by model and time period.

**Query params:**
- `window`: 1h | 24h | 7d | 30d (default: 24h)
- `group_by`: model | workflow | hour | day

**Example:**
```bash
curl -s "http://aio-01:5000/monitoring/costs?window=7d&group_by=model" | jq .
```

### GET /monitoring/alerts

Recent diversity/feedback loop alerts.

**Response:**
```json
{
  "total_alerts": 3,
  "alerts": [
    {
      "alert_type": "model_dominance",
      "severity": 0.75,
      "description": "Model X >70% usage",
      "metadata": {...},
      "timestamp": "..."
    }
  ]
}
```

---

## Secrets Endpoints

### GET /secrets/{key_name}

Get API key securely.

**Example:**
```bash
GOOGLE_KEY=$(curl -s http://aio-01:5000/secrets/GOOGLE_API_KEY | jq -r .value)
```

---

## Learning Endpoints

### GET /learning/experiences

Get learning experiences with vector similarity.

### POST /learning/experiences

Store new learning experience.

### GET /learning/strategies

Get strategy performance (Thompson Sampling bandit).

---

## Workflow Endpoints

### GET /workflows/executions

List workflow executions with filters.

### POST /workflows/executions

Create new workflow execution record.

### GET /workflows/executions/{id}

Get specific workflow execution details.

---

## Fleet Endpoints

### GET /fleet/workers

List available workers and their status.

### POST /fleet/tasks

Submit task to fleet for execution.

---

## Implementation Details

**Blueprints Location:** `/mnt/aio-01/claude-orchestrator/api/app/blueprints/`

**Key Files:**
- `knowledge.py` - Knowledge/scraping endpoints
- `monitoring.py` - Monitoring and metrics
- `secrets.py` - Secure credential storage
- `learning.py` - Learning data and strategies
- `workflows.py` - Workflow tracking
- `fleet.py` - Worker management

**Main Application:** `/mnt/aio-01/claude-orchestrator/api/application.py`

---

## Adding New Endpoints

1. **Create/modify blueprint** in `app/blueprints/{name}.py`
2. **Add to application.py** optional blueprints list:
   ```python
   ('name', 'app.blueprints.name', 'name_bp', '/name'),
   ```
3. **Restart API:** 
   ```bash
   ssh claude@aio-01"cd /mnt/aio-01/claude-orchestrator/api && pkill -f application.py; nohup python3 application.py > /tmp/api.log 2>&1 &"
   ```
4. **Test endpoint:**
   ```bash
   curl -s http://aio-01:5000/name/endpoint | jq .
   ```

---

## Migration Guide

**From direct PostgreSQL:**
```python
# OLD - Direct database access
import psycopg2
conn = psycopg2.connect(host='aio-01', port=5433, database='learning')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM knowledge.scraped_data")
count = cursor.fetchone()[0]
```

**To REST API:**
```python
# NEW - REST API access
import requests
response = requests.get('http://aio-01:5000/knowledge/scraped_data/stats')
data = response.json()
count = data['total_docs']
```

---

## Troubleshooting

**API not responding:**
```bash
ssh claude@aio-01 "ps aux | grep 'python.*application.py'"
```

**Check logs:**
```bash
ssh claude@aio-01 "tail -100 /tmp/api.log"
```

**Restart API:**
```bash
ssh claude@aio-01 "cd /mnt/aio-01/claude-orchestrator/api && pkill -f application.py; python3 application.py > /tmp/api.log 2>&1 &"
```

---

## References

- Full API documentation: `/mnt/aio-01/claude-orchestrator/api/ORCHESTRATOR_SERVICES.md`
- Architecture: `~/.claude/FLEET.md`
- Database schemas: PostgreSQL on aio-01:5433, database `learning`
