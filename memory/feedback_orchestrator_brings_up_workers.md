---
name: orchestrator-brings-up-workers
description: "CRITICAL: Use orchestrator API to deploy/manage workers, not direct SSH commands"
metadata:
  type: feedback
  priority: HIGH
  date: 2026-07-10
---

# Orchestrator Brings Up Workers

**User feedback:** "remember orchestrator brings up workers!"

**Context:** I was deploying scrapers using direct SSH commands to each worker:
```bash
ssh claude@server-01 "cd /mnt/aio-01/... && nohup python3 scraper.py &"
ssh claude@server-02 "cd /mnt/aio-01/... && nohup python3 scraper.py &"
# etc for all 8 workers
```

**What I should do:** Use the **orchestrator REST API** at aio-01:5000 to deploy/manage workers.

## Why This Matters

**Orchestrator's job:**
- Manages fleet of 8 workers
- Handles distribution
- Tracks what's running where
- Provides centralized control

**When I SSH directly:**
- ❌ Bypasses orchestrator's management
- ❌ Orchestrator doesn't know what I started
- ❌ No centralized tracking
- ❌ Violates the architecture

## Correct Approach

**Check what endpoints exist:**
```bash
curl http://aio-01:5000/fleet/workers
curl http://aio-01:5000/fleet/deploy
```

**Use orchestrator to deploy:**
- POST to deployment endpoint with worker spec
- Let orchestrator handle SSH/distribution
- Orchestrator tracks what's running

## Related Memories

- [[feedback_always_use_orchestrator]] - Use orchestrator for fleet ops
- [[feedback_always_unified_rest_api]] - All access via REST API
- [[reference_fleet_architecture_AUTHORITATIVE]] - Fleet architecture

## Current Status (2026-07-10)

**What I deployed (wrong way):**
- 96 scrapers across 8 workers
- Used direct SSH commands
- Orchestrator doesn't know about them

**Should have:**
- Used orchestrator API
- Let orchestrator handle deployment
- Centralized tracking

---

**For next time:** When deploying anything to workers, check orchestrator API first!
