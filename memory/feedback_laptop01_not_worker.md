---
name: laptop01-not-worker
description: "laptop-01 is dev workstation only - NOT part of the worker fleet"
metadata:
  type: feedback
  date: 2026-07-10
---

# laptop-01 is NOT a Worker

**Decision:** 2026-07-10

**laptop-01 should NOT be used as a fleet worker.**

## Why

- It's the primary dev workstation (where Claude Code sessions run)
- Running worker tasks would interfere with development work
- User uses this machine actively - don't want background fleet work consuming resources

## Fleet Configuration

**7 workers (NOT 8):**
1. server-01 (192.168.1.14) - Heavy compute
2. server-02 (192.168.1.15) - Heavy compute
3. server-03 (192.168.1.16) - Heavy compute
4. pi-01 (192.168.1.9) - Light worker
5. pi-02 (no IP) - Light worker
6. server-ap (192.168.1.4) - Light worker
7. desktop-ap (192.168.1.5) - Light worker

**NOT workers:**
- aio-01 - Orchestrator only
- laptop-01 - Dev workstation only
- admin-ap, util-ap, nas - Infrastructure only

## How to Apply

**When distributing fleet work:**
- Use 7 workers, not 8
- Skip laptop-01 in all parallel() and pipeline() calls
- Query PostgreSQL or REST API for active workers, don't hardcode

**Updated in:**
- PostgreSQL: `inventory.machines` (primary_role updated, device_type = 'dev-workstation')
- Fleet API: `/exports/claude-orchestrator/api/app/blueprints/fleet.py` (removed from FLEET_NODES)

## Related

- [[reference_fleet_architecture_AUTHORITATIVE]] - Fleet architecture (needs update)
- [[reference_home_network_AUTHORITATIVE]] - Network topology
