# AI Performance Monitor - Real-time Metrics, Anomaly Detection & Reporting

Comprehensive performance monitoring for AI models and workflows. Tracks accuracy, latency, cost over time; detects anomalies via statistical analysis; generates interactive dashboards and performance reports.

## Features

- **Real-time Performance Tracking** - Record accuracy, latency, cost, token usage per call
- **Anomaly Detection** - Automatic detection of outliers via standard deviation analysis (configurable threshold)
- **Multi-metric Dashboards** - Visual summaries with charts and model comparisons
- **Comprehensive Reports** - Executive summaries, detailed metrics, trends, and actionable recommendations
- **Trend Analysis** - Compare first vs second half of observation period to detect drift
- **Model Comparison** - Benchmark models against each other across all metrics
- **Time Windows** - Flexible analysis windows (1 hour to 30 days)
- **Persistent Storage** - All performance data saved to JSON for cross-session analysis
- **Health Monitoring** - System health status (healthy/degraded/unhealthy) with issue detection
- **Smart Alerts** - Real-time alerts for latency, cost, accuracy, and error thresholds

## Quick Start

```bash
# Track a single performance observation
/ai-performance-monitor { "action": "track", "model": "opus", "latency_ms": 2500, "cost_usd": 0.08, "accuracy": 0.95, "success": true }

# Get current metrics for a model
/ai-performance-monitor { "action": "getMetrics", "model": "opus", "time_window_hours": 24 }

# Generate interactive dashboard
/ai-performance-monitor { "action": "getDashboard", "include_charts": true }

# Generate comprehensive report
/ai-performance-monitor { "action": "generateReport", "time_window_hours": 168 }

# Detect performance anomalies
/ai-performance-monitor { "action": "detectAnomalies", "model": "opus" }

# Compare models
/ai-performance-monitor { "action": "compareModels", "models": ["opus", "sonnet", "haiku"] }
```

## Actions Reference

### track

Record a performance observation with detailed metrics.

```javascript
const result = await workflow('ai-performance-monitor', {
  action: 'track',
  model: 'opus',                    // required - model identifier
  workflow_id: 'code-review-run-42', // optional - groups by workflow
  task_type: 'code-review',         // optional - groups by task type
  latency_ms: 2500,                 // request-response time in milliseconds
  input_tokens: 1500,               // tokens sent to model
  output_tokens: 800,               // tokens received from model
  cost_usd: 0.0825,                 // cost in USD (auto-compute if needed)
  accuracy: 0.95,                   // 0-1 score if applicable
  success: true,                    // was execution successful?
  error: null,                      // error message if failed
  metadata: { severity: 'high' },   // optional custom metadata
})
```

Returns:
```json
{
  "recorded": true,
  "timestamp": "2026-06-10T12:00:00.000Z",
  "alerts": [
    { "type": "latency_high", "severity": "warning", "message": "..." }
  ],
  "total_records": 142
}
```

### getMetrics

Retrieve aggregated performance metrics for a model or all models.

```javascript
const metrics = await workflow('ai-performance-monitor', {
  action: 'getMetrics',
  model: 'opus',                    // optional - filter by model
  time_window_hours: 24,            // optional, default 24
})
```

Returns:
```json
{
  "model": "opus",
  "time_window_hours": 24,
  "record_count": 42,
  "metrics": {
    "latency": {
      "min": 500,
      "p25": 1200,
      "p50": 1800,
      "p75": 2300,
      "p95": 3500,
      "p99": 5000,
      "max": 6200,
      "avg": 1950,
      "stddev": 1200
    },
    "cost": {
      "total": 3.45,
      "avg": 0.082,
      "min": 0.05,
      "max": 0.15,
      "stddev": 0.032
    },
    "accuracy": {
      "avg": 0.92,
      "min": 0.75,
      "max": 1.0,
      "stddev": 0.08
    },
    "tokens": {
      "total_input": 63000,
      "total_output": 33600,
      "avg_input": 1500,
      "avg_output": 800
    },
    "success_rate": 97.6,
    "call_count": 42
  },
  "observation_period": {
    "start": "2026-06-09T12:00:00.000Z",
    "end": "2026-06-10T12:00:00.000Z"
  }
}
```

### getDashboard

Generate an interactive dashboard with charts and model breakdowns.

```javascript
const dashboard = await workflow('ai-performance-monitor', {
  action: 'getDashboard',
  include_charts: true,  // optional, default true
})
```

Returns:
```json
{
  "timestamp": "2026-06-10T12:00:00.000Z",
  "summary": {
    "total_records": 142,
    "unique_models": 3,
    "unique_workflows": 5,
    "unique_tasks": 8
  },
  "overall_metrics": { "..." },
  "by_model": {
    "opus": {
      "record_count": 60,
      "metrics": { "..." },
      "recent_anomalies": []
    },
    "sonnet": { "..." }
  },
  "system_health": {
    "status": "healthy",
    "success_rate": "97.2%",
    "issues": ["No issues detected"]
  },
  "charts": {
    "latency_over_time": [
      { "timestamp": "2026-06-10T10:00:00.000Z", "value": 2100 },
      { "timestamp": "2026-06-10T11:00:00.000Z", "value": 2350 }
    ],
    "cost_over_time": [ "..." ],
    "accuracy_over_time": [ "..." ],
    "model_distribution": [
      { "model": "opus", "count": 60, "percentage": "42.3" }
    ]
  }
}
```

### generateReport

Generate a comprehensive performance analysis report.

```javascript
const report = await workflow('ai-performance-monitor', {
  action: 'generateReport',
  model: 'opus',                    // optional - filter by model
  time_window_hours: 168,           // 1 week, default 24
})
```

Includes:
- **Executive Summary** - High-level overview with key metrics
- **Detailed Metrics** - Full percentile analysis, totals, averages
- **Anomalies** - List of detected outliers with severity
- **Trends** - Direction and magnitude of change across metrics
- **Recommendations** - Actionable next steps based on data
- **Tables** - Breakdowns by workflow, task type, model, and recent calls

Returns comprehensive report object with all sections.

### detectAnomalies

Find performance outliers based on statistical deviation.

```javascript
const anomalies = await workflow('ai-performance-monitor', {
  action: 'detectAnomalies',
  model: 'opus',  // optional - filter by model
})
```

Returns:
```json
{
  "model": "opus",
  "anomaly_count": 3,
  "anomalies": [
    {
      "timestamp": "2026-06-10T11:30:00.000Z",
      "metric": "latency_ms",
      "value": 8500,
      "baseline_mean": 2000,
      "baseline_stddev": 800,
      "threshold": 4000,
      "deviation_sigmas": 8.125,
      "severity": "critical"
    }
  ],
  "alert_threshold": "2.5 σ",
  "confidence": "high"
}
```

Severity levels:
- `critical` - > 4 standard deviations
- `high` - > 3 standard deviations
- `medium` - > 2.5 standard deviations
- `low` - > 2.5 standard deviations (threshold)

### getTrends

Analyze performance direction and magnitude of change.

```javascript
const trends = await workflow('ai-performance-monitor', {
  action: 'getTrends',
  model: 'opus',                 // optional
  time_window_hours: 168,
  metrics: ['latency_ms', 'cost_usd', 'accuracy'],  // optional
})
```

Returns:
```json
{
  "model": "opus",
  "time_window_hours": 168,
  "observation_count": 142,
  "trends": [
    {
      "metric": "latency",
      "direction": "increasing",
      "change_percent": "12.5",
      "interpretation": "Performance degradation"
    },
    {
      "metric": "cost",
      "direction": "decreasing",
      "change_percent": "-3.2",
      "interpretation": "Cost per call decreasing"
    }
  ]
}
```

### compareModels

Benchmark models side-by-side across all performance dimensions.

```javascript
const comparison = await workflow('ai-performance-monitor', {
  action: 'compareModels',
  models: ['opus', 'sonnet', 'haiku'],  // optional - all models if not specified
  time_window_hours: 24,
})
```

Returns:
```json
{
  "timestamp": "2026-06-10T12:00:00.000Z",
  "time_window_hours": 24,
  "models_compared": ["opus", "sonnet", "haiku"],
  "comparison_table": {
    "opus": {
      "record_count": 42,
      "latency": { "avg_ms": 2100, "p95_ms": 3500, "p99_ms": 5000 },
      "cost": { "total_usd": 3.45, "avg_per_call": 0.082 },
      "accuracy": { "avg": 0.92, "min": 0.75, "max": 1.0 },
      "success_rate": 97.6
    },
    "sonnet": { "..." },
    "haiku": { "..." }
  },
  "rankings": {
    "fastest": ["haiku", "sonnet", "opus"],
    "cheapest": ["haiku", "sonnet", "opus"],
    "most_accurate": ["opus", "sonnet"],
    "most_reliable": ["opus", "sonnet", "haiku"]
  }
}
```

### reset

Clear all performance data and start fresh.

```javascript
const reset = await workflow('ai-performance-monitor', { action: 'reset' })
```

Returns:
```json
{
  "reset": true,
  "message": "All performance data cleared",
  "new_session_id": "session_1718020800000_abc123def"
}
```

## Configuration

Default configuration (can be overridden in code):

### Anomaly Detection

```javascript
anomaly_detection: {
  enabled: true,
  std_dev_threshold: 2.5,        // Alert if > 2.5 σ from mean
  min_samples_for_baseline: 10,  // Need 10+ samples to detect
  metrics: ['latency_ms', 'cost_usd', 'accuracy']
}
```

### Alert Thresholds

```javascript
alerts: {
  enabled: true,
  latency_warning_ms: 5000,      // Warn if > 5 seconds
  cost_warning_usd: 0.50,        // Warn if > $0.50 per call
  accuracy_warning: 0.70,        // Warn if < 70%
  error_rate_warning: 0.10       // Warn if > 10% failures
}
```

### Time Windows

```javascript
time_windows: {
  default_hours: 24,   // Default analysis window
  min_hours: 1,        // Minimum allowed
  max_hours: 720       // Maximum (30 days)
}
```

## Data Storage

Performance data is persisted to:

```
~/.claude/repos/claude-global-skills/memory/performance-data.json
```

File structure:

```json
{
  "version": "1.0",
  "created_at": "2026-06-10T12:00:00.000Z",
  "updated_at": "2026-06-10T12:05:00.000Z",
  "session_id": "session_1718020800000_abc123def",
  "records": [
    {
      "timestamp": "2026-06-10T12:00:00.000Z",
      "session_id": "session_1718020800000_abc123def",
      "model": "opus",
      "workflow_id": "code-review-run-42",
      "task_type": "code-review",
      "latency_ms": 2500,
      "input_tokens": 1500,
      "output_tokens": 800,
      "cost_usd": 0.0825,
      "accuracy": 0.95,
      "success": true,
      "error": null,
      "metadata": {}
    }
  ],
  "model_stats": {},
  "last_analysis": null
}
```

## Integration Examples

### Auto-tracking in workflows

```javascript
async function executeTask(prompt, model) {
  const start = Date.now()
  const response = await agent(prompt, { model })
  const latency = Date.now() - start

  await workflow('ai-performance-monitor', {
    action: 'track',
    model: model,
    workflow_id: globalWorkflowId,
    task_type: 'code-review',
    latency_ms: latency,
    input_tokens: response.usage?.input_tokens || 0,
    output_tokens: response.usage?.output_tokens || 0,
    accuracy: response.metadata?.accuracy || null,
    success: response.success !== false,
    error: response.error || null,
  })

  return response
}
```

### Conditional model selection based on performance

```javascript
const metrics = await workflow('ai-performance-monitor', {
  action: 'getMetrics',
  model: 'opus',
  time_window_hours: 24,
})

if (metrics.metrics.latency.p95 > 3000) {
  log('Opus p95 latency high, switching to sonnet')
  model = 'sonnet'
}
```

### Health monitoring loop

```javascript
const health = (await workflow('ai-performance-monitor', {
  action: 'getDashboard',
})).system_health

if (health.status === 'unhealthy') {
  log('ERROR: System health critical!')
  // Trigger incident response
}
```

### Model selection optimization

```javascript
const comparison = await workflow('ai-performance-monitor', {
  action: 'compareModels',
  time_window_hours: 168,
})

// Use fastest model for time-critical tasks
const fastestModel = comparison.rankings.fastest[0]

// Use cheapest for cost-sensitive
const cheapestModel = comparison.rankings.cheapest[0]

// Use most accurate for quality-critical
const bestModel = comparison.rankings.most_accurate[0]
```

## Metrics Reference

### Latency Metrics

- **min/max** - Minimum and maximum observed latency
- **p25/p50/p75/p95/p99** - Percentiles (25th, 50th, etc.)
- **avg** - Arithmetic mean
- **stddev** - Standard deviation

### Cost Metrics

- **total** - Sum of all costs in USD
- **avg** - Mean cost per call
- **min/max** - Range of costs
- **stddev** - Cost variance

### Accuracy Metrics

- **avg** - Mean accuracy score (0-1)
- **min/max** - Range of accuracy
- **stddev** - Accuracy variance

### Token Metrics

- **total_input/total_output** - Total tokens consumed
- **avg_input/avg_output** - Average per call

### System Metrics

- **success_rate** - Percentage of successful calls
- **call_count** - Total observations recorded

## Best Practices

1. **Track Everything** - Record all model calls to get comprehensive data
2. **Use Workflow IDs** - Group related calls by workflow_id for better analysis
3. **Include Accuracy** - When available, track accuracy for performance evaluation
4. **Regular Reports** - Generate reports at regular intervals (daily/weekly)
5. **Monitor Anomalies** - Check for anomalies at least once per shift
6. **Act on Trends** - When latency/cost trends up, investigate root causes
7. **Compare Models** - Weekly model comparisons to optimize cost/quality
8. **Alert on Health** - Set up monitoring for system_health status changes

## Files

- `~/.claude/repos/claude-global-skills/ai-performance-monitor.js` - Main monitoring system
- `~/.claude/repos/claude-global-skills/ai-performance-monitor.md` - This documentation
- `~/.claude/repos/claude-global-skills/memory/performance-data.json` - Persisted metrics

---

**Version**: 1.0
**Created**: 2026-06-10
**Dependencies**: None (standalone, uses Node.js fs module)
