# Grafana JSON Datasource API - Complete Reference

## Overview

This document provides complete technical reference for the Grafana JSON Datasource API serving AI Learning System metrics.

**Server**: `http://localhost:3000`
**Port**: `3000` (configurable in code)
**Database**: `/home/sfloess/.claude/learning/db/learning.db` (SQLite3)
**Protocol**: HTTP/REST + Grafana JSON Plugin format

## HTTP Headers

All responses include CORS headers:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

All successful responses return:
```
Content-Type: application/json
HTTP 200 OK
```

## Endpoint Reference

### 1. Health Check

**Endpoint**: `GET /health`

**Purpose**: Verify server is running and database is connected

**Response**:
```json
{
  "status": "ok",
  "db": "connected"
}
```

**Status Codes**:
- `200 OK` - Server and database are operational
- `500 Error` - Server or database issue

**Example**:
```bash
curl http://localhost:3000/health
```

---

### 2. LIS Metrics

**Endpoint**: `GET /metrics/lis`

**Purpose**: Get current LIS Score and 7-day trend

**Response Schema**:
```json
{
  "current": {
    "lis_score": number (0-100),
    "quality_pct": number (0-100),
    "success_rate_pct": number (0-100),
    "avg_cost_usd": number,
    "avg_duration_sec": number,
    "samples": integer
  },
  "trend": [
    {
      "date": "YYYY-MM-DD",
      "timestamp": milliseconds,
      "lis_score": number
    }
  ]
}
```

**Query Parameters**: None (uses last 7 days)

**Example**:
```bash
curl http://localhost:3000/metrics/lis | jq '.current'
```

**Sample Response**:
```json
{
  "current": {
    "lis_score": 78,
    "quality_pct": 92.5,
    "success_rate_pct": 98,
    "avg_cost_usd": 0.0042,
    "avg_duration_sec": 8.7,
    "samples": 245
  },
  "trend": [
    { "date": "2024-06-07", "timestamp": 1717728000000, "lis_score": 72 },
    { "date": "2024-06-08", "timestamp": 1717814400000, "lis_score": 75 },
    { "date": "2024-06-13", "timestamp": 1718332800000, "lis_score": 78 }
  ]
}
```

---

### 3. Quality Metrics

**Endpoint**: `GET /metrics/quality`

**Purpose**: Get quality scores grouped by model and overall

**Response Schema**:
```json
{
  "by_model": [
    {
      "timestamp": milliseconds,
      "model": string,
      "quality": number (0-1),
      "executions": integer
    }
  ],
  "overall": [
    {
      "timestamp": milliseconds,
      "quality": number (0-1),
      "min_quality": number (0-1),
      "max_quality": number (0-1),
      "samples": integer
    }
  ]
}
```

**Query Parameters**: None (uses last 7 days)

**Example**:
```bash
curl http://localhost:3000/metrics/quality | jq '.overall[] | {timestamp, quality}'
```

**Sample Response**:
```json
{
  "by_model": [
    { "timestamp": 1717728000000, "model": "claude-opus", "quality": 0.94, "executions": 12 },
    { "timestamp": 1717728000000, "model": "claude-sonnet", "quality": 0.88, "executions": 15 }
  ],
  "overall": [
    { "timestamp": 1717728000000, "quality": 0.91, "min_quality": 0.75, "max_quality": 1.0, "samples": 27 }
  ]
}
```

---

### 4. Cost Metrics

**Endpoint**: `GET /metrics/cost`

**Purpose**: Get daily cost data and cost savings analysis

**Response Schema**:
```json
{
  "daily": [
    {
      "timestamp": milliseconds,
      "date": "YYYY-MM-DD",
      "daily_cost": number,
      "executions": integer,
      "avg_cost_per_exec": number
    }
  ],
  "baseline": {
    "baseline_cost_per_exec": number,
    "baseline_daily_cost": number
  },
  "summary": {
    "total_7day": number,
    "avg_daily": number
  }
}
```

**Query Parameters**: None (uses last 30 days for history, last 7 days baseline)

**Example**:
```bash
curl http://localhost:3000/metrics/cost | jq '.summary'
```

**Sample Response**:
```json
{
  "daily": [
    { "timestamp": 1715136000000, "date": "2024-05-08", "daily_cost": 0.156, "executions": 45, "avg_cost_per_exec": 0.00347 },
    { "timestamp": 1715222400000, "date": "2024-05-09", "daily_cost": 0.142, "executions": 48, "avg_cost_per_exec": 0.00296 }
  ],
  "baseline": {
    "baseline_cost_per_exec": 0.00425,
    "baseline_daily_cost": 0.195
  },
  "summary": {
    "total_7day": 0.892,
    "avg_daily": 0.128
  }
}
```

**Note**: Baseline is calculated from 6-7 days ago for comparing with current performance

---

### 5. Discoveries (Learnings)

**Endpoint**: `GET /metrics/discoveries`

**Purpose**: Get recent model tuning discoveries and effective model combinations

**Response Schema**:
```json
{
  "tuning": [
    {
      "model": string,
      "task_type": string,
      "quality": number (0-1),
      "cost_usd": number,
      "sample_count": integer,
      "success_rate_pct": number,
      "selection_rate_pct": number,
      "temperature": number,
      "top_p": number,
      "max_tokens": number,
      "updated_at": "YYYY-MM-DDTHH:MM:SSZ"
    }
  ],
  "combinations": [
    {
      "task_type": string,
      "worker_models": string,
      "arbiter_model": string,
      "quality": number (0-1),
      "consensus": number (0-1),
      "synergy": number (0-1),
      "diversity": number (0-1),
      "usage_count": integer,
      "cost_usd": number,
      "updated_at": "YYYY-MM-DDTHH:MM:SSZ"
    }
  ],
  "stats": {
    "total_tuned": integer,
    "total_combos": integer,
    "best_quality": { model, task_type, quality },
    "best_combo": { worker_models, arbiter_model, synergy }
  }
}
```

**Query Parameters**: None (returns latest 20 tuning records, 15 combinations)

**Example**:
```bash
curl http://localhost:3000/metrics/discoveries | jq '.stats'
```

**Sample Response**:
```json
{
  "tuning": [
    {
      "model": "claude-opus",
      "task_type": "code-review",
      "quality": 0.94,
      "cost_usd": 0.0052,
      "sample_count": 128,
      "success_rate_pct": 99.2,
      "selection_rate_pct": 87.5,
      "temperature": 0.3,
      "top_p": 0.95,
      "max_tokens": 2048,
      "updated_at": "2024-06-13T11:30:00Z"
    }
  ],
  "combinations": [
    {
      "task_type": "code-review",
      "worker_models": "claude-sonnet,claude-haiku",
      "arbiter_model": "claude-opus",
      "quality": 0.91,
      "consensus": 0.88,
      "synergy": 0.89,
      "diversity": 0.75,
      "usage_count": 234,
      "cost_usd": 0.0038,
      "updated_at": "2024-06-13T10:15:00Z"
    }
  ],
  "stats": {
    "total_tuned": 42,
    "total_combos": 18,
    "best_quality": { "model": "claude-opus", "task_type": "code-review", "quality": 0.94 },
    "best_combo": { "worker_models": "sonnet,haiku", "arbiter_model": "opus", "synergy": 0.89 }
  }
}
```

---

### 6. Grafana Search API

**Endpoint**: `POST /search`

**Purpose**: Return list of available metrics for Grafana metric selector

**Request Format**:
```json
{}
```

**Response Format**:
```json
[
  { "text": "Display Name", "value": "api_target_name" }
]
```

**Example Response**:
```json
[
  { "text": "LIS Score", "value": "lis_score" },
  { "text": "LIS Trend", "value": "lis_trend" },
  { "text": "Quality Score", "value": "quality_score" },
  { "text": "Quality by Model", "value": "quality_by_model" },
  { "text": "Cost Daily", "value": "cost_daily" },
  { "text": "Cost Savings", "value": "cost_savings" },
  { "text": "Discoveries", "value": "discoveries" },
  { "text": "Model Tuning", "value": "model_tuning" },
  { "text": "Model Combinations", "value": "model_combinations" }
]
```

**cURL Example**:
```bash
curl -X POST http://localhost:3000/search \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### 7. Grafana Query API

**Endpoint**: `POST /query`

**Purpose**: Main data endpoint for Grafana queries (used by JSON datasource plugin)

**Request Format**:
```json
{
  "targets": [
    {
      "target": "lis_score",
      "refId": "A"
    },
    {
      "target": "quality_score",
      "refId": "B"
    }
  ]
}
```

**Response Format**:

For time series data:
```json
[
  {
    "target": "Series Name",
    "datapoints": [
      [value, timestamp_ms],
      [value, timestamp_ms]
    ]
  }
]
```

For table data:
```json
[
  {
    "target": "Table Name",
    "type": "table",
    "rows": [
      ["Column1", "Column2", "Column3"],
      ["value1", "value2", "value3"]
    ]
  }
]
```

**Supported Target Names**:
- `lis_score` - Current LIS score (single value)
- `lis_trend` - LIS score over time (time series)
- `quality_score` - Overall quality (time series)
- `quality_by_model` - Quality per model (multiple series)
- `cost_daily` - Daily cost (time series)
- `cost_savings` - Calculated savings vs baseline (time series)
- `discoveries` - Recent learnings (table)
- `model_tuning` - Detailed tuning data (array)
- `model_combinations` - Model combo data (array)

**Example Request**:
```bash
curl -X POST http://localhost:3000/query \
  -H "Content-Type: application/json" \
  -d '{
    "targets": [
      {"target": "lis_score", "refId": "A"},
      {"target": "quality_score", "refId": "B"},
      {"target": "cost_daily", "refId": "C"}
    ]
  }'
```

**Example Response**:
```json
[
  {
    "target": "LIS Score",
    "datapoints": [[78, 1718200800000]]
  },
  {
    "target": "Quality Score (Overall)",
    "datapoints": [
      [0.915, 1717728000000],
      [0.92, 1717814400000]
    ]
  },
  {
    "target": "Daily Cost ($)",
    "datapoints": [
      [0.142, 1717728000000],
      [0.128, 1717814400000]
    ]
  }
]
```

---

## Response Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| `200` | OK | All successful requests |
| `400` | Bad Request | Invalid JSON in POST body |
| `404` | Not Found | Unknown endpoint |
| `500` | Server Error | Database connection lost, SQL error |

**Error Response Format**:
```json
{
  "error": "Error description message"
}
```

---

## Data Format Notes

### Timestamps
- All timestamps are in **milliseconds since epoch** (Unix time * 1000)
- Compatible with Grafana's time handling
- Suitable for JavaScript Date objects: `new Date(timestamp)`

### Numbers
- Percentages returned as decimals: `0.92` = 92%
- Costs in USD as decimals: `0.0042` = $0.0042
- Quality/confidence scores: 0-1 range
- Durations in seconds: `8.7` = 8.7 seconds

### Date Strings
- ISO 8601 format: `2024-06-13T11:30:00Z`
- Date only: `YYYY-MM-DD` format `2024-06-13`

---

## Query Performance

### Response Times (Typical)
| Endpoint | Time | Notes |
|----------|------|-------|
| `/health` | ~5ms | Direct status |
| `/metrics/lis` | ~50ms | Simple aggregation |
| `/metrics/quality` | ~100ms | Multi-model rollup |
| `/metrics/cost` | ~150ms | 30-day history |
| `/metrics/discoveries` | ~200ms | Large tuning table |
| `/query` (multi-target) | ~300ms | Multiple aggregations |

### Database Queries

Each endpoint runs specific SQL queries optimized with indexes:

**LIS Score Query** (~50ms):
```sql
SELECT ROUND((
  COALESCE(AVG(quality_score), 0) * 40 +
  COALESCE(AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END), 0) * 20 +
  ...
) as lis_score
FROM execution_log
WHERE timestamp >= datetime('now', '-7 days')
```

**Quality Query** (~100ms):
```sql
SELECT
  strftime('%s', MIN(timestamp)) * 1000 as timestamp,
  model,
  ROUND(AVG(quality_score), 4) as quality
FROM execution_log
WHERE quality_score IS NOT NULL
  AND timestamp >= datetime('now', '-7 days')
GROUP BY strftime('%Y-%m-%d', timestamp), model
```

---

## Integration Examples

### JavaScript (Node.js)

```javascript
const http = require('http');

async function getLISScore() {
  return new Promise((resolve, reject) => {
    http.get('http://localhost:3000/metrics/lis', (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(JSON.parse(data)));
    }).on('error', reject);
  });
}

const metrics = await getLISScore();
console.log(`Current LIS Score: ${metrics.current.lis_score}`);
```

### Python

```python
import requests
import json

def get_quality_metrics():
    response = requests.get('http://localhost:3000/metrics/quality')
    return response.json()

metrics = get_quality_metrics()
print(f"Overall quality: {metrics['overall']}")
```

### Bash/cURL

```bash
# Fetch and parse LIS score
curl -s http://localhost:3000/metrics/lis | \
  jq '.current | {lis_score, quality_pct, samples}'

# Stream cost data
curl -s http://localhost:3000/metrics/cost | \
  jq -r '.daily[] | "\(.date): $\(.daily_cost)"'
```

### Grafana JSON Datasource

```
Data Source URL: http://localhost:3000
Access: Browser (CORS enabled)
Http Method: GET (for direct metrics), POST (for /query)
```

---

## Error Handling

### Connection Errors

If server is unavailable:
```
curl: (7) Failed to connect to localhost port 3000: Connection refused
```

Solution: Start the server with `node grafana-api.js`

### Database Errors

If database file is missing:
```json
{
  "error": "Database connection error: ENOENT: no such file or directory"
}
```

Solution: Ensure `/home/sfloess/.claude/learning/db/learning.db` exists

### Query Timeout

If query takes >5 seconds:
```json
{
  "error": "Query timeout"
}
```

Solution: Check database indexes, run `VACUUM; ANALYZE;`

---

## Security Considerations

### CORS

API allows requests from any origin (`Access-Control-Allow-Origin: *`). 

In production, restrict to specific Grafana domains:
```javascript
res.setHeader('Access-Control-Allow-Origin', 'https://grafana.example.com');
```

### Database Access

- API runs with same permissions as Node.js process
- Database file should be readable but not writable via API
- In production, use read-only database connections

### Authentication

Current implementation has no authentication. In production, add:
- API Key validation
- Bearer token support
- HMAC request signing

---

## Changelog

### v1.0.0 (2024-06-13)
- Initial release
- 5 REST endpoints + Grafana plugin support
- SQLite backend with 7-day metrics
- CORS enabled

---

## License

Part of the Autonomous AI Learning System.
