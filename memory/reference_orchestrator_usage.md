---
name: orchestrator-usage
description: How to use the pi-02 orchestrator for model routing decisions
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4feb3522-355a-4346-ae03-e690a9d9a11a
  modified: 2026-07-24T17:17:31.907Z
---

# Orchestrator Service on pi-02

**Service:** Fleet Orchestrator (production-router based)
**Endpoint:** `http://aio-01:5000` (on 192.168.1.x network) or `ssh aio-01` then local access (when off-network)
**Status:** Active (systemd service `orchestrator.service`)
**Purpose:** Model routing decisions based on task type, cost, and fleet utilization

## Remote Access (off-network)

When not on the 192.168.1.x/24 network, access the orchestrator via SSH tunnel:
```bash
ssh aio-01   # then run curl commands locally on aio-01
```

## What It Does

The orchestrator is a **routing service**, NOT a task execution service:
- ✅ Decides which model to use for a task
- ✅ Considers fleet utilization, cost constraints, task type
- ✅ Returns optimal model + host recommendation
- ✗ Does NOT execute tasks directly (you still use Workflow tool)

## API Endpoints

### Health Check
```bash
curl http://pi-02:8888/health
# Returns: status, uptime, models_available, request/error counts
```

### Model Routing
```bash
curl -X POST http://pi-02:8888/route \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "opus",  # Required: model name or category
    "task": "Review documentation",
    "taskType": "code-review",
    "constraints": {
      "maxCost": 0.10,
      "preferLocal": true
    }
  }'
# Returns: selected model, host, reasoning
```

### Available Models
```bash
curl http://pi-02:8888/models
# Returns: list of 12 available models across fleet
```

### Fleet Utilization
```bash
curl http://pi-02:8888/utilization
# Returns: per-host utilization stats
```

### Refresh Registry
```bash
curl -X POST http://pi-02:8888/refresh
# Forces immediate registry refresh (normally auto-refreshes every 5min)
```

## Proper Usage Pattern

**BEFORE (what I was doing):**
```javascript
// Directly executing workflow without consulting orchestrator
const result = await workflow('doc-review', { ... })
```

**AFTER (what I should do):**
```javascript
// 1. Ask orchestrator for routing decision
const routing = await fetch('http://pi-02:8888/route', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'opus',  // or category like 'code-reviewer'
    task: 'Review documentation for accuracy',
    taskType: 'code-review',
    constraints: { maxCost: 0.10, preferLocal: true }
  })
}).then(r => r.json())

// 2. Execute task using recommended model
const result = await workflow('doc-review', {
  model: routing.selectedModel,
  host: routing.selectedHost
})
```

## When to Use

- ✅ Multi-AI consensus workflows (let orchestrator pick diverse models)
- ✅ Cost-sensitive tasks (set maxCost constraint)
- ✅ Load balancing across fleet (orchestrator knows current utilization)
- ✅ Local-first routing (preferLocal: true for Red Hat compliance)
- ✗ Simple single-model tasks (overhead not justified)

## Related

- See [[reference_distributed_fleet]] for fleet topology
- See [[feedback_use_orchestrator]] for user preference to use orchestrator
