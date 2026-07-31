# Fleet Dispatcher Architecture - ASCII Diagrams

## Complete System Architecture

```
                        WORKSTATION (laptop-01)
                        ========================
                        Multi-AI Workflows
                              |
                              | HTTP fetch()
                              v
       ┌──────────────────────────────────────────────────┐
       │      aio-01 (Controller, x86_64, 2C/7GB)         │
       │                                                   │
       │  ┌─────────────────────────────────────────┐    │
       │  │  Port 5000: REST API (Flask)            │    │
       │  │  • All DB access via REST               │    │
       │  │  • /models/, /graph/*, /fleet/*         │    │
       │  ├─────────────────────────────────────────┤    │
       │  │  Port 3004: Fleet Dispatcher Service    │    │
       │  │  (fleet-dispatcher-with-circuit-        │    │
       │  │   breaker.py)                           │    │
       │  ├─────────────────────────────────────────┤    │
       │  │  Endpoints:                              │    │
       │  │  • POST /agent/execute                   │    │
       │  │  • POST /agent/complete                  │    │
       │  │  • GET  /fleet/status                    │    │
       │  │  • GET  /health                          │    │
       │  └─────────────────────────────────────────┘    │
       │                    |                             │
       │                    | PromQL queries              │
       │                    v                             │
       │  ┌─────────────────────────────────────────┐    │
       │  │  Port 9090: Prometheus                  │    │
       │  │  • Scrapes node_exporter :9100          │    │
       │  │  • 15-day retention                     │    │
       │  │  • 3GB storage                          │    │
       │  └─────────────────────────────────────────┘    │
       │                    |                             │
       │                    | /api/v1/targets             │
       │                    | /api/v1/query               │
       │                    |                             │
       │  ┌─────────────────────────────────────────┐    │
       │  │  Port 3000: Grafana                     │    │
       │  │  • 4 Fleet Dashboards                   │    │
       │  │  • Fleet visualization                  │    │
       │  └─────────────────────────────────────────┘    │
       │                                                   │
       │  ┌─────────────────────────────────────────┐    │
       │  │  Port 9093: Alertmanager                │    │
       │  │  • Alert forwarding to ntfy.sh          │    │
       │  └─────────────────────────────────────────┘    │
       │                                                   │
       │  ┌─────────────────────────────────────────┐    │
       │  │  Port 6379: Redis 8.0.2 (standalone)    │    │
       │  │  • All queues (ingestion, embedding)    │    │
       │  │  • No auth, no Sentinel                 │    │
       │  └─────────────────────────────────────────┘    │
       │                                                   │
       │  ┌─────────────────────────────────────────┐    │
       │  │  Databases (Docker):                    │    │
       │  │  • PostgreSQL :5433 (learning DB)       │    │
       │  │  • OrientDB :2424 (knowledge graph)     │    │
       │  └─────────────────────────────────────────┘    │
       └──────────────────────────────────────────────────┘
                              |
              Prometheus scrape (every 15s)
                              |
       ┌──────────────────────┼──────────────────────┐
       |                      |                      |
       v                      v                      v
  ┌─────────┐          ┌─────────┐          ┌─────────┐
  │server-01│          │server-02│          │server-03│
  │ :9100   │          │ :9100   │          │ :9100   │
  │ Worker  │          │ Worker  │          │ Worker  │
  │ 15GB/8C │          │ 31GB/8C │          │ 31GB/8C │
  │ x86_64  │          │ x86_64  │          │ x86_64  │
  └─────────┘          └─────────┘          └─────────┘
       |                      |                      |
  ┌─────────┐          ┌─────────┐          ┌─────────┐
  │desktopap│          │serverap │          │  pi-01  │
  │ :9100   │          │ :9100   │          │ :9100   │
  │ Worker  │          │ Worker  │          │ Worker  │
  │  1GB    │          │  1GB    │          │  1GB    │
  └─────────┘          └─────────┘          └─────────┘
       |                      |                      |
       └──────────────────────┼──────────────────────┘
                              |
                   NFS: ~/Development (475GB)
                   (shared from workstation)
                              |
                        ┌─────────┐
                        │  pi-02  │
                        │ :9100   │
                        │ Worker  │
                        │  1GB    │
                        └─────────┘

Legend:
  :9100 = node_exporter (hardware/OS metrics)
  :9090 = Prometheus (metrics aggregation, on aio-01)
  :5000 = REST API (all DB access, on aio-01)
  :3004 = Fleet Dispatcher (job routing API, on aio-01)
  :3000 = Grafana (monitoring dashboards, on aio-01)
  :9093 = Alertmanager (alert forwarding, on aio-01)
  :6379 = Redis 8.0.2 (queues, on aio-01)
  :5433 = PostgreSQL (learning DB, on aio-01)
  :2424 = OrientDB (knowledge graph, on aio-01)
  NFS   = Network File System (shared code)
  SSH   = Secure Shell (remote execution)
```

---

## Phase 3 Remote Execution Flow

```
┌──────────────────────────────────────────────────────────────┐
│ MULTI-AI WORKFLOW EXECUTION (Phase 3)                        │
└──────────────────────────────────────────────────────────────┘

  Workstation: Multi-AI Workflow Starts
        |
        | (1) Worker 1: Opus (request)
        v
  ┌────────────────────────────────────┐
  │ fleet-agent-wrapper.js             │
  │ _agent() intercepts                │
  └────────────────────────────────────┘
        |
        | (1b) Check Model Compliance
        v
  ┌────────────────────────────────────┐
  │ checkModelCompliance("opus")       │
  │ • Get current working directory    │
  │ • Load path_restrictions           │
  │ • Match against denied/allowed     │
  └────────────────────────────────────┘
        |
        ├─ Model denied? → Fallback to local
        └─ Model allowed? → Continue
                |
                | (2) POST /agent/execute
                v
  ┌────────────────────────────────────┐
  │ Dispatcher (aio-01:3004)            │
  │ • Queries Prometheus for metrics   │
  │ • Scores servers by RAM/CPU/load   │
  │ • Checks circuit breaker           │
  │ • Selects: server-03 (heavy)       │
  └────────────────────────────────────┘
        |
        | (3) Returns: {job_id, server: "server-03", model: "opus"}
        v
  ┌────────────────────────┐
  │ fleet-remote-executor  │
  │ SSH execution engine   │
  └────────────────────────┘
        |
        | (4) SSH server-03 "claude --model opus -p '...'"
        v
  ┌─────────────────────────────────┐
  │ server-03 (Worker, 31GB)         │
  │ Executes: claude --model opus   │
  │ Returns: JSON result            │
  └─────────────────────────────────┘
        |
        | (5) Result returned via SSH
        v
  ┌────────────────────────┐
  │ fleet-agent-wrapper.js │
  │ Receives result        │
  └────────────────────────┘
        |
        | (6) POST /agent/complete {job_id, success, duration}
        v
  ┌────────────────────────────────────┐
  │ Dispatcher (aio-01:3004)            │
  │ • Records telemetry                │
  │ • Updates historical learning      │
  │ • Updates circuit breaker          │
  └────────────────────────────────────┘
        |
        | (7) Result returned to workflow
        v
  Multi-AI Workflow (Worker 1 complete)


PARALLEL EXECUTION:

  Worker 1 (Opus)   → server-03  ─┐
  Worker 2 (Sonnet) → server-02  ─┤
  Worker 3 (Haiku)  → server-01  ─┼─> All run simultaneously
  Worker 4 (Gemini) → pi-01      ─┘
        |
        | All complete
        v
  Arbiter (Fable)   → server-03 (most RAM available)
        |
        | Synthesis complete
        v
  Final Result

Performance: 3-5x faster than local execution
```

---

## Circuit Breaker State Machine

```
┌──────────────────────────────────────────────────────────────┐
│                   CIRCUIT BREAKER                             │
└──────────────────────────────────────────────────────────────┘

                        ┌─────────┐
                        │ CLOSED  │
                        │ (Normal)│
                        └─────────┘
                             │
                Failure      │      Success
             ┌───────────────┼───────────────┐
             │               │               │
             v               │               │
        ┌─────────┐          │          All good
        │  OPEN   │          │               │
        │(Backed  │          │               │
        │  Off)   │          │               │
        └─────────┘          │               │
             │               │               │
     Backoff │               │               │
     expires │               │               │
             │               │               │
             v               v               v
        ┌──────────────────────────────────────┐
        │       HALF-OPEN (Probing)            │
        │  Single test request                 │
        └──────────────────────────────────────┘
                  │                      │
         Success  │                      │ Failure
                  v                      v
             ┌─────────┐            ┌─────────┐
             │ CLOSED  │            │  OPEN   │
             │         │            │         │
             └─────────┘            └─────────┘

Backoff Tiers (Exponential):
  Tier 1:    60s (1 minute)
  Tier 2:   300s (5 minutes)
  Tier 3:   900s (15 minutes)
  Tier 4:  3600s (1 hour)
  Tier 5: 14400s (4 hours)
  Tier 6: 43200s (12 hours)

Model Fallback Chain:
  gemini → gpt-4o → opus → sonnet → haiku

Compliance Enforcement:
  ✓ path_restrictions checked before agent creation
  ✓ Models auto-filtered in multi-AI workflows
  ✓ Denied models rejected with clear error message
```

---

## Load Balancing Decision Tree

```
┌──────────────────────────────────────────────────────────────┐
│              SERVER SELECTION ALGORITHM                       │
└──────────────────────────────────────────────────────────────┘

  New Job Request
        |
        v
  ┌─────────────────────┐
  │ Query Prometheus    │
  │ for all nodes       │
  └─────────────────────┘
        |
        v
  ┌─────────────────────────────────────────┐
  │ For each server, collect metrics:       │
  │ • RAM available (GB)                    │
  │ • CPU usage (%)                         │
  │ • CPU cores (count)                     │
  │ • Load average (1m)                     │
  │ • Pending jobs (count)                  │
  └─────────────────────────────────────────┘
        |
        v
  ┌─────────────────────────────────────────┐
  │ Calculate Score:                        │
  │ score = (avail_ram_gb * 10)             │
  │       + (100 - cpu_usage_pct)           │
  │       + (cores * 5)                     │
  │       - (load_1m * 10)                  │
  │       - (pending_jobs * 50)             │
  │       + historical_bonus                │
  └─────────────────────────────────────────┘
        |
        v
  ┌─────────────────────────────────────────┐
  │ Filter Out:                             │
  │ • Models in circuit breaker open state  │
  │ • Servers with RAM pressure (>90%)      │
  │ • Servers overloaded (CPU >95%)         │
  └─────────────────────────────────────────┘
        |
        v
  ┌─────────────────────┐
  │ Select highest      │
  │ scoring server      │
  └─────────────────────┘
        |
        v
  Return: {server, model, job_id, score}
```

---

## Job Lifecycle State Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                      JOB LIFECYCLE                            │
└──────────────────────────────────────────────────────────────┘

  ┌──────────┐
  │  START   │
  └──────────┘
       |
       | Workflow calls agent()
       v
  ┌──────────────────┐
  │   DISPATCHED     │  POST /agent/execute
  │ (job_id created) │  {job_id, server, model}
  └──────────────────┘
       |
       | SSH to selected server
       v
  ┌──────────────────┐
  │   EXECUTING      │  claude --model X -p "..."
  │ (on remote       │  (or local if dispatch failed)
  │  server)         │
  └──────────────────┘
       |
       ├─────────────┬─────────────┐
       │             │             │
   Success       Timeout        Error
       │             │             │
       v             v             v
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │COMPLETED│  │ TIMEOUT │  │ FAILED  │
  │         │  │         │  │         │
  └─────────┘  └─────────┘  └─────────┘
       |             |             |
       └─────────────┼─────────────┘
                     |
                     | POST /agent/complete
                     | {job_id, success, duration, error}
                     v
              ┌──────────────┐
              │  RECORDED    │
              │ (telemetry   │
              │  persisted)  │
              └──────────────┘
                     |
                     v
              Update:
              • Historical learning
              • Circuit breaker state
              • Pending jobs count
```

---

## Data Flow: Multi-AI Consensus

```
┌──────────────────────────────────────────────────────────────┐
│         MULTI-AI WORKFLOW DATA FLOW                           │
└──────────────────────────────────────────────────────────────┘

User Prompt
    |
    v
┌────────────────────────────────────────────┐
│ Multi-AI Workflow (e.g., ai-prompt.js)    │
│ parallel([...6 workers...])                │
└────────────────────────────────────────────┘
    |
    ├──────┬──────┬──────┬──────┬──────┐
    v      v      v      v      v      v
  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐
  │W1 │ │W2 │ │W3 │ │W4 │ │W5 │ │W6 │
  │Opu│ │Son│ │Hai│ │Fab│ │Gem│ │GPT│
  │s  │ │net│ │ku │ │le │ │ini│ │-4o│
  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘
    |      |      |      |      |      |
    | Each worker:                     |
    | 1. Calls _agent()                |
    | 2. Dispatches to fleet           |
    | 3. Executes remotely via SSH     |
    | 4. Returns result                |
    |                                  |
    v      v      v      v      v      v
  ┌────────────────────────────────────┐
  │ Results Array:                     │
  │ [result1, result2, result3, ...]   │
  └────────────────────────────────────┘
    |
    | All workers complete
    v
┌────────────────────────────────────────┐
│ Arbiter Agent                          │
│ • Receives all worker results          │
│ • Analyzes agreements/disagreements    │
│ • Synthesizes best answer              │
│ • Dispatched to fleet (server-03)      │
└────────────────────────────────────────┘
    |
    v
  Final Answer
```

---

## Network Topology

```
                    Internet
                       │
                       │
              ┌────────┴────────┐
              │   Router/NAT    │
              └────────┬────────┘
                       │
              192.168.1.0/24 (Home LAN)
                       │
    ┌──────────┬───────┼───────┬──────────┐
    │          │       │       │          │
┌───┴────┐ ┌──┴───┐ ┌─┴──┐ ┌──┴───┐ ┌───┴────┐
│laptop01│ │srv-01│ │srv │ │srv-03│ │ aio-01 │
│  .126  │ │ .150 │ │-02 │ │ .152 │ │ Contrl │
│Workstat│ │Worker│ │.151│ │Worker│ │  2C/7G │
│  4C/8T │ │8C/15G│ │Wrkr│ │8C/31G│ │ :5000  │
│  31GB  │ │      │ │8C/ │ │      │ │ :9090  │
│        │ │      │ │31G │ │      │ │ :3000  │
└───┬────┘ └──────┘ └────┘ └──────┘ └────────┘
    │
    │  ┌──────────┬──────────┬──────────┬──────────┐
    │  │          │          │          │          │
    │  │  ┌──────┴──┐ ┌────┴────┐ ┌───┴───┐ ┌───┴───┐
    │  │  │desktopap│ │serverap │ │ pi-01 │ │ pi-02 │
    │  │  │ Worker  │ │ Worker  │ │Worker │ │Worker │
    │  │  │  1GB    │ │  1GB    │ │ 1GB   │ │ 1GB   │
    │  │  └─────────┘ └─────────┘ └───────┘ └───────┘
    │  │
    │  └── All workers: SSH :22, node_exporter :9100
    │
    │             192.168.2.0/24 (Cabin LAN, SSH tunnel)
    │                    │
    │          ┌─────────┼─────────┐
    │          │                   │
    │   ┌─────┴──────┐  ┌────────┴───────┐
    │   │cabin-lap-01│  │ cabin-lap-02   │
    │   │ .2.4       │  │ .2.5           │
    │   │ Gateway    │  │ Dev workstation│
    │   └────────────┘  └────────────────┘
    │
    └── aio-01 monitors all via Prometheus

Network Services (all on aio-01 unless noted):
  • SSH: port 22 (fleet execution, all nodes)
  • REST API: port 5000 (all DB access)
  • Prometheus: port 9090 (metrics)
  • Grafana: port 3000 (dashboards)
  • Dispatcher: port 3004 (fleet API)
  • Alertmanager: port 9093 (alerts)
  • Redis: port 6379 (queues, standalone, no auth)
  • PostgreSQL: port 5433 (learning DB)
  • OrientDB: port 2424 (knowledge graph, Docker)
  • node_exporter: port 9100 (system metrics, all nodes)

NFS Shares:
  • laptop-01:/home/sfloess/Development → All servers
  • Shared codebase for remote execution

Fleet Roles:
  • aio-01: Controller ONLY (never runs worker tasks)
  • 8 Workers: server-01/02/03, desktop-ap, server-ap, pi-01, pi-02, laptop-01
  • Embeddings: ONLY on laptop-01/02 (never fleet workers)
```

---

## Model Compliance Enforcement

```
┌──────────────────────────────────────────────────────────────┐
│          MODEL COMPLIANCE CHECKING (Path Restrictions)        │
└──────────────────────────────────────────────────────────────┘

  Workflow creates agent()
        |
        v
  ┌────────────────────────┐
  │ fleet-agent-wrapper.js │
  │ checkModelCompliance() │
  └────────────────────────┘
        |
        | Load ~/.claude/fleet.json
        v
  ┌──────────────────────────────────────┐
  │ compliance:                          │
  │   path_restrictions:                 │
  │     - path: /home/.../redhat/        │
  │       denied_models: [gpt-*]         │
  │       reason: "Red Hat compliance"   │
  └──────────────────────────────────────┘
        |
        | Get current working directory
        | Find longest matching restriction path
        v
  ┌────────────────────┐
  │ Pattern Matching   │
  │ gpt-* → gpt-4o?    │
  └────────────────────┘
        |
        ├──────────┬──────────┐
        │          │          │
     DENIED     ALLOWED    NO MATCH
        │          │          │
        v          v          v
   ┌────────┐ ┌────────┐ ┌────────┐
   │ REJECT │ │CONTINUE│ │CONTINUE│
   │ Error  │ │ Agent  │ │ Agent  │
   │ Message│ │Creation│ │Creation│
   └────────┘ └────────┘ └────────┘

Error Message Example:
  ❌ Model gpt-4o not allowed in /home/sfloess/Development/redhat/
     Reason: Red Hat compliance - no OpenAI
     Allowed models: claude-*

Workflow Auto-Filtering:
  multi-AI workflows (ai-prompt.js, ai-consensus.js):
    workers = filterAllowedModels(["opus", "sonnet", "gpt-4o"])
    → returns ["opus", "sonnet"]  // gpt-* filtered out
    
    arbiter = getCompliantArbiter("fable", ["fable", "opus"])
    → returns "fable"  // First allowed model
```

---

## Historical Learning

```
┌──────────────────────────────────────────────────────────────┐
│        HISTORICAL LEARNING (20-job sliding window)            │
└──────────────────────────────────────────────────────────────┘

Job Completion:
  job_id: abc123
  instance: server-03
  job_type: ai-consensus
  duration: 28.5s
  success: true
        |
        v
  ┌─────────────────────────────────────────┐
  │ Record in History:                      │
  │ key: (server-03, ai-consensus)          │
  │ deque: [28.5, 30.1, 25.3, ...]          │
  │ max length: 20 jobs                     │
  └─────────────────────────────────────────┘
        |
        v
  ┌─────────────────────────────────────────┐
  │ Calculate Average:                      │
  │ avg = sum(deque) / len(deque)           │
  │ avg = 27.8s for (server-03, ai-consensus)│
  └─────────────────────────────────────────┘
        |
        v
  ┌─────────────────────────────────────────┐
  │ Apply Bonus to Score:                   │
  │ bonus = min(50, 100 / max(avg, 0.1))    │
  │ bonus = min(50, 100 / 27.8)             │
  │ bonus = 3.6                             │
  └─────────────────────────────────────────┘
        |
        v
  Server score increased by 3.6 points
  (Faster servers get higher bonus)

History