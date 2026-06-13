# Performance Tuning Guide

## Overview

The fleet dispatcher system includes **AI-driven auto-tuning** that monitors performance metrics and automatically adjusts configuration when degradation is detected.

---

## Auto-Tuning Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│               AI-DRIVEN AUTO-TUNING ORCHESTRATOR                 │
└─────────────────────────────────────────────────────────────────┘

  Prometheus Metrics
        |
        | (every 15s)
        v
  ┌────────────────────┐
  │ Metric Collector   │
  │ • p95 latency      │
  │ • Error rate       │
  │ • Circuit breaker  │
  │ • Queue depth      │
  └────────────────────┘
        |
        | (every 5 minutes)
        v
  ┌────────────────────┐
  │ Anomaly Detector   │
  │ Is tuning needed?  │
  └────────────────────┘
        |
        | YES: Degradation detected
        v
  ┌───────────────────────────────────────┐
  │ AI Tuning Orchestrator                │
  │ • Analyzes metrics with Opus          │
  │ • Proposes config changes             │
  │ • Validates with Sonnet (independent) │
  │ • If consensus: Apply changes         │
  │ • Record to tuning history            │
  └───────────────────────────────────────┘
        |
        | Config changes
        v
  ┌────────────────────┐
  │ Dispatcher Config  │
  │ • Backoff tiers    │
  │ • Load weights     │
  │ • Job type RAM     │
  │ • Thresholds       │
  └────────────────────┘
        |
        | (wait 15 minutes)
        v
  ┌────────────────────┐
  │ Validation Check   │
  │ Did it help?       │
  └────────────────────┘
        |
        ├─── YES: Keep changes, record success
        └─── NO: Rollback, record failure
```

---

## Tuning Triggers

The auto-tuning orchestrator runs when **any** of these conditions are met:

### 1. Latency Degradation

```sql
# p95 latency increased >50% over 15-minute window
avg_over_time(
  fleet_agent_duration_seconds{quantile="0.95"}[15m]
) > 1.5 * avg_over_time(
  fleet_agent_duration_seconds{quantile="0.95"}[1h] offset 1h
)
```

**Example Trigger**:
- 1 hour ago: p95 = 30s
- Now (15m avg): p95 = 50s
- 50s > 1.5 × 30s → **TUNE**

---

### 2. Error Rate Spike

```sql
# Error rate >10% over 5-minute window
sum(rate(fleet_agent_errors_total[5m])) 
/ 
sum(rate(fleet_agent_requests_total[5m])) 
> 0.10
```

**Example Trigger**:
- Requests: 100/min
- Errors: 12/min
- 12/100 = 12% > 10% → **TUNE**

---

### 3. Circuit Breaker Thrashing

```sql
# More than 3 circuit breaker state changes in 15 minutes
changes(fleet_circuit_breaker_state[15m]) > 3
```

**Example Trigger**:
- 00:00 - closed
- 00:02 - open (failure)
- 00:03 - half_open (backoff expired)
- 00:03 - closed (success)
- 00:05 - open (failure again)
- 5 changes in 5 minutes → **TUNE**

---

### 4. Queue Saturation

```sql
# Pending jobs >50 for more than 5 minutes
fleet_pending_jobs > 50 for 5m
```

**Example Trigger**:
- Pending jobs stays above 50 for 5+ minutes
- Fleet overloaded → **TUNE**

---

### 5. Server Imbalance

```sql
# One server handling >70% of all jobs
max(fleet_jobs_by_server) / sum(fleet_jobs_by_server) > 0.70
```

**Example Trigger**:
- server-03: 140 jobs
- server-02: 30 jobs
- server-01: 20 jobs
- server-03 is 140/190 = 74% → **TUNE**

---

## AI Tuning Process

### Step 1: Gather Evidence

**Prometheus queries executed**:
```python
queries = {
    "p95_latency": "histogram_quantile(0.95, fleet_agent_duration_seconds)",
    "error_rate": "sum(rate(fleet_agent_errors_total[5m])) / sum(rate(fleet_agent_requests_total[5m]))",
    "circuit_breaker_states": "fleet_circuit_breaker_state",
    "pending_jobs": "fleet_pending_jobs",
    "jobs_by_server": "sum by (instance) (fleet_jobs_total)",
    "jobs_by_type": "sum by (job_type) (fleet_jobs_total)",
    "historical_avg": "avg_over_time(fleet_agent_duration_seconds[1h])",
}
```

**Example Evidence Collected**:
```json
{
  "timestamp": "2026-06-13T02:15:00Z",
  "trigger": "latency_degradation",
  "metrics": {
    "p95_latency_current": 52.3,
    "p95_latency_baseline": 28.5,
    "error_rate": 0.08,
    "circuit_breaker": {
      "model:gemini": "open",
      "model:opus": "half_open",
      "model:sonnet": "closed"
    },
    "pending_jobs": 23,
    "jobs_by_server": {
      "server-01": 45,
      "server-02": 38,
      "server-03": 71
    },
    "jobs_by_type": {
      "ai-consensus": 89,
      "code-review": 42,
      "ai-heavy": 23
    }
  }
}
```

---

### Step 2: AI Analysis (Opus)

**Prompt sent to Opus**:
```
You are a performance tuning expert for a distributed AI agent fleet dispatcher.

CURRENT METRICS:
{evidence}

CURRENT CONFIGURATION:
{current_config}

PROBLEM:
{trigger_description}

ANALYZE:
1. Root cause of the performance degradation
2. Which configuration parameters should change
3. Proposed new values with rationale
4. Expected improvement

RESPOND IN JSON:
{
  "root_cause": "...",
  "proposed_changes": [
    {"parameter": "...", "current": ..., "proposed": ..., "rationale": "..."}
  ],
  "expected_improvement": "...",
  "confidence": 0.0-1.0
}
```

**Example Opus Response**:
```json
{
  "root_cause": "Gemini model circuit breaker is open (quota exhausted), causing all gemini jobs to fallback to opus. Opus is now overloaded (p95=52s vs baseline 28s). server-03 is handling 46% of jobs (should be ~33% for 3 servers).",
  
  "proposed_changes": [
    {
      "parameter": "circuit_breaker_backoff_tier_1",
      "current": 60,
      "proposed": 300,
      "rationale": "Increase first-tier backoff from 1min to 5min to reduce circuit breaker thrashing. Gemini quota resets hourly, so 1min backoff causes unnecessary retry storms."
    },
    {
      "parameter": "load_balance_weight_pending_jobs",
      "current": 50,
      "proposed": 75,
      "rationale": "Increase pending jobs penalty from 50 to 75 points to more aggressively avoid server-03 (which has 71 pending vs 38/45 for other servers)."
    },
    {
      "parameter": "model_fallback_chain",
      "current": ["gemini", "gpt-4o", "opus", "sonnet"],
      "proposed": ["gemini", "sonnet", "haiku", "opus"],
      "rationale": "Change fallback to prefer sonnet over opus when gemini is down, since opus is slower and currently overloaded. Save opus as last resort."
    }
  ],
  
  "expected_improvement": "Reduce p95 latency from 52s to ~35s by distributing gemini fallback load to sonnet/haiku instead of opus. Reduce server-03 load from 46% to ~35%.",
  
  "confidence": 0.85
}
```

---

### Step 3: Independent Validation (Sonnet)

**Prompt sent to Sonnet** (does NOT see Opus response):
```
You are an independent performance validator for a distributed AI agent fleet dispatcher.

CURRENT METRICS:
{evidence}

CURRENT CONFIGURATION:
{current_config}

PROBLEM:
{trigger_description}

PROPOSED CHANGES:
{opus_proposed_changes}

YOUR TASK:
Independently validate these proposed changes. Do NOT rubber-stamp.

ANALYZE:
1. Are the proposed changes correct?
2. Will they actually fix the problem?
3. Are there any risks or side effects?
4. Should we apply them?

RESPOND IN JSON:
{
  "validation": "approve" | "reject" | "modify",
  "risks": ["...", "..."],
  "side_effects": ["...", "..."],
  "alternative_changes": [...],
  "confidence": 0.0-1.0
}
```

**Example Sonnet Response**:
```json
{
  "validation": "approve_with_modification",
  
  "risks": [
    "Increasing tier-1 backoff from 60s to 300s means if gemini comes back online, we won't notice for 5 minutes instead of 1 minute. Could waste 4 minutes of idle capacity.",
    "Changing fallback chain could break workflows that explicitly request opus and expect consistent quality."
  ],
  
  "side_effects": [
    "Sonnet will handle more gemini fallback → sonnet p95 will increase slightly.",
    "Haiku in fallback chain → lower quality responses for gemini fallback cases."
  ],
  
  "alternative_changes": [
    {
      "parameter": "circuit_breaker_backoff_tier_1",
      "value": 180,
      "rationale": "Compromise: 3 minutes instead of 5. Reduces thrashing while keeping recovery time reasonable."
    }
  ],
  
  "confidence": 0.78
}
```

---

### Step 4: Consensus Decision

**Apply changes if:**
1. Opus confidence ≥ 0.70 **AND**
2. Sonnet validation = "approve" or "approve_with_modification" **AND**
3. Sonnet confidence ≥ 0.70

**Result**:
- Opus confidence: 0.85 ✅
- Sonnet validation: approve_with_modification ✅
- Sonnet confidence: 0.78 ✅
- **DECISION: APPLY CHANGES (with Sonnet modifications)**

**Final Config Changes**:
```json
{
  "circuit_breaker_backoff_tier_1": 180,  // Sonnet modification
  "load_balance_weight_pending_jobs": 75,
  "model_fallback_chain": ["gemini", "sonnet", "haiku", "opus"]
}
```

---

### Step 5: Apply Changes

**Configuration update**:
```python
# Load current config
config = load_config("/home/sfloess/Development/fleet-dispatcher/config.json")

# Apply changes
config["circuit_breaker"]["backoff_tiers"][0] = 180
config["load_balancing"]["weights"]["pending_jobs"] = 75
config["models"]["fallback_chains"]["gemini"] = ["gemini", "sonnet", "haiku", "opus"]

# Save config
save_config(config)

# Reload dispatcher (HUP signal, no downtime)
subprocess.run(["ssh", "pi-02", "pkill", "-HUP", "fleet-dispatcher"])
```

---

### Step 6: Validation (15-minute wait)

**Wait 15 minutes, then check**:
```python
# Query metrics again
new_metrics = query_prometheus(same_queries_as_before)

# Compare to baseline
improvement = {
    "p95_latency": baseline["p95"] - new_metrics["p95"],
    "error_rate": baseline["error_rate"] - new_metrics["error_rate"],
    "pending_jobs": baseline["pending_jobs"] - new_metrics["pending_jobs"],
}

# Did it help?
if improvement["p95_latency"] > 5.0:  # At least 5s improvement
    status = "success"
    action = "keep_changes"
else:
    status = "failure"
    action = "rollback"
```

**Example Validation**:
```json
{
  "tuning_id": "tune-20260613-021500",
  "trigger": "latency_degradation",
  "applied_at": "2026-06-13T02:15:00Z",
  "validated_at": "2026-06-13T02:30:00Z",
  "baseline": {
    "p95_latency": 52.3,
    "error_rate": 0.08,
    "pending_jobs": 23
  },
  "after_tuning": {
    "p95_latency": 34.8,
    "error_rate": 0.03,
    "pending_jobs": 12
  },
  "improvement": {
    "p95_latency": 17.5,  // 17.5s improvement ✅
    "error_rate": 0.05,   // 5% error rate reduction ✅
    "pending_jobs": 11    // 11 fewer pending jobs ✅
  },
  "status": "success",
  "action": "keep_changes"
}
```

**Rollback Example** (if validation fails):
```bash
# Restore previous config
ssh pi-02 'cp /home/sfloess/Development/fleet-dispatcher/config.json.backup-20260613-021500 /home/sfloess/Development/fleet-dispatcher/config.json'

# Reload dispatcher
ssh pi-02 'pkill -HUP fleet-dispatcher'

# Record rollback
echo '{"status": "rollback", "reason": "no_improvement"}' >> tuning-history.jsonl
```

---

## Manual Tuning

### Circuit Breaker Tuning

**Problem**: Circuit breaker opens too frequently (thrashing)

**Symptoms**:
- `changes(fleet_circuit_breaker_state[15m]) > 3`
- Logs show: `circuit_breaker: open → half_open → closed → open`

**Fix**: Increase backoff tiers
```json
{
  "circuit_breaker": {
    "backoff_tiers": [180, 600, 1800, 7200, 28800, 86400]
    // OLD: [60, 300, 900, 3600, 14400, 43200]
    // NEW: 3min, 10min, 30min, 2hr, 8hr, 24hr (longer backoffs)
  }
}
```

---

### Load Balancing Tuning

**Problem**: One server is overloaded, others idle

**Symptoms**:
- `max(fleet_jobs_by_server) / sum(fleet_jobs_by_server) > 0.70`
- server-03 has 70% of jobs, server-01/02 idle

**Fix**: Increase pending jobs penalty
```json
{
  "load_balancing": {
    "weights": {
      "available_ram_gb": 10,
      "cpu_available_pct": 1,
      "cores": 5,
      "load_1m": -10,
      "pending_jobs": 100  // OLD: 50, NEW: 100 (stronger penalty)
    }
  }
}
```

**Effect**:
- Server with 10 pending jobs: -1000 score penalty
- Server with 1 pending job: -100 score penalty
- More aggressive load distribution

---

### Job Type RAM Tuning

**Problem**: Jobs timing out due to insufficient RAM

**Symptoms**:
- Logs show: `OOM killed` or `MemoryError`
- Jobs assigned to aio-01 (4GB) failing, but would succeed on server-01 (16GB)

**Fix**: Increase job type RAM requirements
```json
{
  "job_types": {
    "ai-consensus": {
      "min_ram_gb": 2.0,  // OLD: 1.0, NEW: 2.0
      "avg_duration_sec": 30
    },
    "ai-heavy": {
      "min_ram_gb": 8.0,  // OLD: 2.0, NEW: 8.0
      "avg_duration_sec": 60
    }
  }
}
```

**Effect**:
- ai-consensus jobs won't be assigned to aio-01 (4GB) anymore
- Only server-01/02/03 (16-33GB) will handle ai-heavy jobs

---

### Historical Learning Window Tuning

**Problem**: Historical averages not adapting to recent changes

**Symptoms**:
- Model performance changed (e.g., gemini got faster), but scores lag
- Server upgraded RAM, but dispatcher still treats it as low-capacity

**Fix**: Reduce sliding window size
```python
# In fleet-dispatcher-with-circuit-breaker.py
HISTORICAL_WINDOW_SIZE = 10  # OLD: 20, NEW: 10

# Effect: Faster adaptation to recent changes
# Tradeoff: More noise, less stable estimates
```

---

### Model Fallback Chain Tuning

**Problem**: Fallback chain not optimal for current availability

**Symptoms**:
- Gemini often down → all jobs fall back to opus → opus overloaded
- GPT-4o is faster than opus for current workload

**Fix**: Reorder fallback chain
```json
{
  "models": {
    "fallback_chains": {
      "gemini": ["gemini", "sonnet", "haiku", "opus"],
      // OLD: ["gemini", "gpt-4o", "opus", "sonnet"]
      // NEW: Prefer sonnet (faster, cheaper) before opus
      
      "opus": ["opus", "gpt-4o", "sonnet", "haiku"],
      // Fallback from opus → gpt-4o (similar quality)
    }
  }
}
```

### Model Compliance in Fallback Chains

**Problem**: Fallback chain includes models denied by path_restrictions

**Symptoms**:
- Workflow tries to use gpt-4o in Red Hat directory (should fail)
- Fallback chain not respecting compliance policies
- Error: "No compliant fallback model available"

**Fix**: Ensure fallback chain respects path_restrictions
```javascript
// In dispatcher or workflow:
import { isModelAllowed } from './shared/model-compliance.js';

async function selectFallbackModel(primaryModel) {
  const fallbackChain = config.models.fallback_chains[primaryModel] || [];
  
  // Filter fallback chain through compliance
  const compliantFallbacks = fallbackChain.filter(model => {
    const result = isModelAllowed(model);
    return result.allowed;
  });
  
  return compliantFallbacks[0] || null;
}
```

**Example**:
```
Directory: /home/sfloess/Development/redhat/ (denies gpt-*)
Primary: gpt-4o
Fallback chain: ["gpt-4o", "gpt-4-turbo", "opus", "sonnet"]

After compliance filter:
Compliant fallbacks: ["opus", "sonnet"]  // gpt-* removed
Selected: "opus"
```

---

---

## Tuning Metrics

### Key Performance Indicators (KPIs)

| Metric | Target | Alarm Threshold | Query |
|--------|--------|-----------------|-------|
| **p95 Latency** | <30s | >45s | `histogram_quantile(0.95, fleet_agent_duration_seconds)` |
| **Error Rate** | <2% | >10% | `sum(rate(errors[5m])) / sum(rate(requests[5m]))` |
| **Circuit Breaker Changes** | <1/hour | >3/15min | `changes(fleet_circuit_breaker_state[1h])` |
| **Pending Jobs** | <20 | >50 | `fleet_pending_jobs` |
| **Server Imbalance** | <50% | >70% | `max(jobs_by_server) / sum(jobs_by_server)` |

---

### Grafana Dashboards for Tuning

**Capacity Planning Dashboard**:
- URL: http://pi-02:3000/d/capacity-plan
- Panels:
  - Server CPU/Memory trends (24h)
  - Queue depth forecast
  - Saturation levels
  - Growth projections

**Multi-AI Performance Dashboard**:
- URL: http://pi-02:3000/d/multi-ai-perf
- Panels:
  - Worker execution timeline (Gantt chart)
  - Arbiter synthesis time
  - Model agreement rates
  - Parallel speedup ratio

**Cost Optimization Dashboard**:
- URL: http://pi-02:3000/d/cost-optimize
- Panels:
  - Total cost (24h/30d)
  - Cost per model
  - Budget tracking
  - Token usage by job type

---

## Auto-Tuning Configuration

### Enable Auto-Tuning

**File**: `/home/sfloess/Development/fleet-dispatcher/auto-tuning-config.json`

```json
{
  "enabled": true,
  "check_interval_seconds": 300,  // Check every 5 minutes
  "triggers": {
    "latency_degradation": {
      "enabled": true,
      "threshold_multiplier": 1.5,  // 50% increase
      "window": "15m"
    },
    "error_rate_spike": {
      "enabled": true,
      "threshold": 0.10,  // 10% error rate
      "window": "5m"
    },
    "circuit_breaker_thrashing": {
      "enabled": true,
      "changes_threshold": 3,
      "window": "15m"
    },
    "queue_saturation": {
      "enabled": true,
      "pending_jobs_threshold": 50,
      "duration": "5m"
    },
    "server_imbalance": {
      "enabled": true,
      "max_server_pct": 0.70  // 70% of jobs
    }
  },
  "ai_tuning": {
    "analyzer_model": "opus",
    "validator_model": "sonnet",
    "min_confidence": 0.70,
    "require_consensus": true
  },
  "validation": {
    "wait_minutes": 15,
    "min_improvement_seconds": 5.0,  // p95 latency improvement
    "rollback_on_failure": true
  },
  "history": {
    "file": "/home/sfloess/Development/fleet-dispatcher/tuning-history.jsonl",
    "max_entries": 1000
  }
}
```

---

### Disable Auto-Tuning (Manual Only)

```json
{
  "enabled": false
}
```

---

### Monitor Auto-Tuning Activity

**View tuning history**:
```bash
tail -f /home/sfloess/Development/fleet-dispatcher/tuning-history.jsonl | jq
```

**Example History Entry**:
```json
{
  "timestamp": "2026-06-13T02:15:00Z",
  "trigger": "latency_degradation",
  "evidence": {
    "p95_latency_current": 52.3,
    "p95_latency_baseline": 28.5
  },
  "opus_analysis": {
    "root_cause": "Gemini circuit breaker open, fallback to opus overload",
    "confidence": 0.85
  },
  "sonnet_validation": {
    "validation": "approve_with_modification",
    "confidence": 0.78
  },
  "applied_changes": [
    {"parameter": "circuit_breaker_backoff_tier_1", "old": 60, "new": 180},
    {"parameter": "load_balance_weight_pending_jobs", "old": 50, "new": 75}
  ],
  "validation_result": {
    "p95_before": 52.3,
    "p95_after": 34.8,
    "improvement": 17.5,
    "status": "success"
  },
  "action": "keep_changes"
}
```

---

## Best Practices

### When to Use Auto-Tuning

✅ **Use auto-tuning for**:
- Production fleets with variable load
- Multi-model deployments (complex fallback chains)
- Long-running services (days/weeks)
- Unpredictable traffic patterns

❌ **Don't use auto-tuning for**:
- Development/testing
- Short-lived experiments
- Single-model setups (nothing to tune)
- Predictable workloads (manual tuning once is enough)

---

### Tuning Cadence

| Trigger | Check Interval | Typical Frequency |
|---------|----------------|-------------------|
| Latency degradation | 5 minutes | 1-2x per day |
| Error rate spike | 5 minutes | 0-1x per day |
| Circuit breaker thrashing | 5 minutes | 1-3x per week |
| Queue saturation | 5 minutes | 0-1x per week |
| Server imbalance | 5 minutes | 1x per week |

**Total**: Expect 1-3 auto-tuning runs per day on average

---

### Rollback Strategy

**Automatic rollback if**:
- Improvement < 5s (p95 latency)
- Error rate increases
- Pending jobs increases

**Manual rollback**:
```bash
# List recent tuning changes
jq -r '.timestamp + " " + .action + " " + (.applied_changes | length | tostring) + " changes"' tuning-history.jsonl | tail -5

# Rollback to specific timestamp
TIMESTAMP="2026-06-13T02:15:00Z"
ssh pi-02 "cp ~/fleet-dispatcher/config.json.backup-${TIMESTAMP} ~/fleet-dispatcher/config.json && pkill -HUP fleet-dispatcher"
```

---

## Documentation References

- **Model Catalog**: `docs/MODEL_CATALOG.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Operations**: `docs/OPERATIONS.md`
- **Grafana Dashboards**: http://pi-02:3000
- **Prometheus Queries**: http://pi-02:9090

---

**Status**: Auto-tuning is READY for deployment. Set `"enabled": true` in auto-tuning-config.json to activate AI-driven performance optimization.
