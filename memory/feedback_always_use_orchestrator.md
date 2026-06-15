---
name: always-use-orchestrator
description: "ALWAYS use pi-02 fleet orchestrator for ALL job execution - never bypass with direct SSH"
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  updated: 2026-06-14T06:35:00Z
  priority: critical
  relates_to: 
    - - reference_distributed_fleet
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

# ALWAYS Use Fleet Orchestrator for ALL Work

**Rule:** Submit ALL work to pi-02 orchestrator via job queue. Never bypass with direct SSH/execution.

**Why:** 
- User explicitly mandated: "always use orchestrator please" + "option B" (2026-06-14)
- Enables coordination across all 9 Claude sessions running simultaneously
- Provides job tracking, load balancing, failure recovery
- Makes work visible to entire fleet
- Prevents duplicate work across sessions
- Sessions can run on different nodes and still coordinate

**How to apply:**

## ❌ WRONG (Direct execution - NEVER do this):
```bash
ssh server-01 "curl -fsSL https://ollama.com/install.sh | sh"
ssh root@laptop-01 "rsync ..."
wget -O /mnt/nas/model.gguf https://...
```

## ✅ CORRECT (Orchestrator-based - ALWAYS do this):
```javascript
const response = await fetch('http://pi-02:3002/jobs/submit', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    type: 'install-ollama',
    target: 'server-01',
    payload: { version: 'latest' }
  })
});
const job = await response.json();
// Returns: { job_id, assigned_to, status: 'queued' }
```

## Orchestrator Endpoints (Verified 2026-06-14)

**Job Queue (port 3002):**
- `POST /jobs/submit` - Submit new job ✅ WORKING
- `GET /workers` - List available workers ✅ WORKING

**Fleet Dispatcher (port 3004):**
- `GET /fleet/status` - Model health, worker status ✅ WORKING
- `GET /health` - System health ✅ WORKING

**Status API (port 3001):**
- Health monitoring ✅ RUNNING

## Registered Workers (as of 2026-06-14)
- **laptop-01:** 4 CPU, 31 GB RAM - heavy workloads
- **server-01:** 8 CPU, 15 GB RAM - fast tasks
- **server-02:** 8 CPU, 31 GB RAM - heavy workloads
- **server-03:** 8 CPU, 31 GB RAM - heavy workloads

## Exception (RARE)

**ONLY exception:** Work already in-progress before this rule was established.
- Example: Task #162 rsync already running 8+ hours → let it complete
- Do NOT interrupt running jobs to migrate them
- This exception applies ONLY to pre-existing work

**For everything else: USE ORCHESTRATOR. No exceptions.**

**Related:** [[reference_distributed_fleet]] - Fleet architecture and infrastructure
