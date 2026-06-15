---
name: use-orchestrator
description: Use the operational pi-02 orchestrator instead of doing orchestration myself
metadata:
  type: feedback
  created: 2026-06-15
  priority: high
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Use Orchestrator - Don't Do Orchestration Myself

**Rule:** Since the orchestrator is operational on pi-02, DO NOT do orchestration tasks myself.

**Why:** The orchestrator system is deployed, tested (10/10 tests passing), and production-ready on pi-02. It exists to handle work orchestration, so I should use it rather than duplicating its functionality.

**How to apply:**
- When work needs to be orchestrated/distributed, use the orchestrator system on pi-02
- Submit work via the orchestrator's HTTP API endpoints
- Query orchestrator status via HTTP API (NOT direct PostgreSQL queries)
- Do NOT manually distribute work, manage sessions, or implement orchestration logic myself
- Do NOT hit PostgreSQL directly - the persistence layer could change (Redis, SQLite, etc.)

**Orchestrator Access (API only):**
- Health: `ssh root@pi-02 "curl -s http://127.0.0.1:7340/health"`
- Metrics: `ssh root@pi-02 "curl -s http://127.0.0.1:7340/metrics"`
- Submit work: Use HTTP POST to work queue endpoint (if available)
- **Never use:** Direct PostgreSQL queries for orchestrator operations

**Why API only:** PostgreSQL is an implementation detail. Could be swapped for Redis, SQLite, or any other backend. API provides stable interface regardless of persistence layer.

**Context:** Orchestrator deployed 2026-06-15, fully tested, all issues resolved, production ready on pi-02.
