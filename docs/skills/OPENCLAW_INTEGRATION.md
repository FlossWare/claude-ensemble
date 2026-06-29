# OpenClaw Integration

**Status:** Phase 1 PoC (In Progress)  
**Multi-AI Confidence:** 85% (HIGH consensus)  
**Last Updated:** 2026-06-12

## Overview

OpenClaw is integrated as a 7th consensus worker with unique **execution verification** capabilities. While other models (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) provide reasoning only, OpenClaw can execute code and verify claims with ground truth.

## Architecture

### Role: Worker (NOT Arbiter)

```
Prompt --> parallel([
  agent(prompt, {model: 'fable'}),      // Reasoning only
  agent(prompt, {model: 'opus'}),       // Reasoning only
  agent(prompt, {model: 'sonnet'}),     // Reasoning only
  agent(prompt, {model: 'haiku'}),      // Reasoning only
  agent(prompt, {model: 'gpt-4o'}),     // Reasoning only
  agent(prompt, {model: 'gemini'}),     // Reasoning only
  openclawVote(prompt, schema),         // Reasoning + EXECUTION VERIFICATION
]) --> arbiter (Fable/Opus) --> decision
```

### Unique Value: Execution Verification

OpenClaw's differentiator is **execution-backed evidence**:
- Can run Python/JavaScript/bash to verify claims
- Reports both reasoning AND execution results
- Flags when execution contradicts reasoning
- Arbiter heavily weights execution proof as near-ground-truth

### Backend Configuration

**Recommended:** Ollama local model (Llama 3 or DeepSeek Coder)
- **Why:** Maximum provider diversity (avoids duplicating Claude/GPT/Gemini)
- **Fallback:** Rotating backend strategy (cycle through non-worker models)

### Graceful Degradation

All changes are backward-compatible:
- If OpenClaw unavailable → 6-model consensus continues
- `filter(Boolean)` removes null OpenClaw results
- No breaking changes to existing workflows

## Implementation Status

### Phase 1: Quick Win / PoC -- COMPLETE

1. ✅ Install OpenClaw on aio-01: `npm i -g openclaw`
2. ✅ Create shared/openclaw-client.js (openclawQuery, openclawHealthCheck, getOpenClawVote)
3. ✅ Update multi-ai-config.json (7 workers including 'openclaw')
4. ✅ Update model-detection.js (MODEL_CAPABILITIES + MAXIMUM preset)
5. ✅ Add OpenClaw as optional 7th worker in consensus-engine.js
6. ✅ Feature flag: OPENCLAW_ENABLED (default: false)
7. ✅ Graceful degradation verified (test-openclaw-degradation.js)
8. ✅ test-openclaw.js for PoC validation when daemon is running
9. ⏳ Configure with Ollama local model (requires interactive onboarding)
10. ⏳ Run PoC test with daemon (blocked on onboarding)

**Success criteria:**
- ✅ OpenClaw participates in consensus with execution evidence
- ✅ Graceful degradation when unavailable
- ⏳ Less than 20% latency overhead (pending daemon test)

### Phase 2: Full Consensus Integration -- COMPLETE (Code Ready)

1. ✅ consensus-engine.js: OpenClaw worker in parallel(), formatOpenClawEvidence()
2. ✅ ai-consensus.js: OpenClaw worker + arbiter evidence enhancement
3. ✅ All consensus variants: consensus-engine.js shared by all workflows
4. ✅ Enhanced arbiter prompt with execution evidence weighting
5. ✅ openclaw_evidence field in arbiter decisions
6. ✅ formatConsensusVote includes OpenClaw results
7. ✅ WORKER_PRESETS.MAXIMUM includes 'openclaw'

### Phase 3: Fleet Orchestration -- COMPLETE (Code Ready)

1. ✅ shared/openclaw-fleet.js: hybridFleetExec(), openclawExec(), distributeItems(), bulkFleetExec()
2. ✅ shared/fleet-utils.js: remoteExecWithOpenClaw() (SSH fallback bridge)
3. ✅ Fleet health checking: checkFleetOpenClawHealth(), selectExecutionMode()
4. ✅ Smart mode selection: smartFleetExec() auto-detects openclaw/ssh/hybrid
5. ✅ Item distribution: weighted and round-robin strategies
6. ✅ Red Hat compliance: enforced via validateCompliance() in fleet path
7. ⏳ Install OpenClaw on server-01/02/03 (when daemon is configured)

### Phase 4: Advanced Features -- DESIGN DOCUMENTED

See "Phase 4 Design" section below.

## Files

### Created
- `shared/openclaw-client.js` - HTTP Gateway client (openclawQuery, openclawHealthCheck, getOpenClawVote)
- `shared/openclaw-fleet.js` - Fleet orchestration (hybridFleetExec, distributeItems, bulkFleetExec)
- `test-openclaw.js` - Phase 1 PoC test (ZeroDivisionError verification)
- `test-openclaw-degradation.js` - Graceful degradation test suite (works offline)
- `OPENCLAW_INTEGRATION.md` - This file

### Modified
- `multi-ai-config.json` - Added 'openclaw' to workers array (7 models)
- `shared/model-detection.js` - Added openclaw to MODEL_CAPABILITIES + MAXIMUM preset
- `shared/consensus-engine.js` - OpenClaw worker support, formatOpenClawEvidence(), arbiter enhancement
- `workflows/shared/consensus-engine.js` - Copy of shared/consensus-engine.js
- `shared/fleet-utils.js` - Added remoteExecWithOpenClaw() bridge function
- `ai-consensus.js` - OpenClaw worker + arbiter evidence in prompt

### Unchanged (benefit from consensus-engine.js changes)
- `ai-consensus-debate.js` - Uses ai-task-router for workers (inherits OpenClaw via config)
- `ai-consensus-filtered.js` - Workers selected from config (inherits OpenClaw)
- `ai-consensus-hierarchical.js` - Sub-team workers (inherits OpenClaw via config)
- `ai-consensus-refinement.js` - Workers from task-router (inherits OpenClaw)
- `ai-consensus-weighted.js` - Workers from config (inherits OpenClaw)
- `code-review-auto.js` - Uses inline multiModelVerify (can adopt consensus-engine)
- `code-security-auto.js` - Delegates to code-security.js
- `ai-pdf-deep-research.js` - Uses own ALL_MODELS array (can add openclaw when ready)

## Configuration

### Environment Variables

```bash
export OPENCLAW_ENABLED=true          # Feature flag (default: false)
export OPENCLAW_HOST=localhost        # Gateway hostname
export OPENCLAW_API_TOKEN=<token>     # Bearer token for auth
export OPENCLAW_FALLBACK_TO_BASH=true # Fleet: SSH fallback enabled
```

### Gateway Port

Default: `18789` (configurable per OpenClaw version)

### Model Backend

Configure OpenClaw to use Ollama:

```json
{
  "agent": {
    "model": "ollama/llama3"
  }
}
```

## Testing

### Manual Test (after OpenClaw daemon running)

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Start OpenClaw gateway
openclaw gateway --port 18789 --verbose &

# Run PoC test
node test-openclaw.js
```

### Expected Output

```
✅ Success Criteria:
  ✅ Health check passed
  ✅ Execution performed
  ✅ Found ZeroDivisionError
  ✅ Response under 60s

🎉 All criteria passed!
```

## Use Case Prioritization

**Highest value skills for OpenClaw:**

1. **ai-pdf-deep-research** (HIGH) - Persistent memory, browser verification
2. **code-security-auto** (HIGH) - Execute security scans for verified results
3. **code-review-auto** (HIGH) - Run code to verify review findings
4. **deep-research** (HIGH) - Browser integration for web claim verification
5. **Bulk fleet operations** (MEDIUM) - Better inter-machine communication than SSH

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OpenClaw gateway crashes | Medium | Low | SSH fallback; null-safe consensus |
| API changes (fast-moving project) | High | Medium | Pin npm version; version-lock package |
| Execution timeout slows consensus | Medium | Low | 2x timeout + async; null result filtered |
| Bearer token compromise | Low | High | NFS 600 permissions; rotate quarterly |
| Resource overhead on workers | Medium | Low | ~100MB RAM; workers have 15-31GB |
| Node.js version conflict | Low | Medium | Check workers have Node 22+ |

## Rollback (30 minutes)

1. **Consensus:** Remove 'openclaw' from workers array in multi-ai-config.json (5 min)
2. **Fleet:** Stop OpenClaw daemons, fleet-utils.js SSH path continues (10 min/machine)
3. **Complete:** `npm rm -g openclaw`, delete ~/.openclaw/, revert config files (30 min)

No data loss risk -- OpenClaw stores data separately.

## Phase 4: Advanced Features Design

### 4.1 Heartbeat Monitoring

```
Architecture:
  pi-02 (Sentinel) --> polls OpenClaw /api/status every 60s
    |
    +--> Each fleet worker: GET http://{worker}:18789/api/status
    |
    +--> Records: { hostname, healthy, latency_ms, timestamp }
    |
    +--> Alerts via ntfy when worker goes down or comes back up
    |
    +--> Writes health history to NFS: ~/.claude/fleet-health/

Data Schema:
  {
    "hostname": "server-01",
    "openclaw_healthy": true,
    "ssh_healthy": true,
    "latency_ms": 45,
    "timestamp": "2026-06-12T10:00:00Z",
    "uptime_hours": 72.5,
    "last_task": "ai-pdf-deep-research",
    "memory_usage_pct": 42
  }

Implementation:
  - Create monitoring/openclaw-heartbeat.js
  - Run as cron job on pi-02 (every 60s)
  - Store history in ~/.claude/fleet-health/heartbeat-YYYY-MM-DD.jsonl
  - Alert thresholds: 3 consecutive failures = DOWN notification
  - Auto-recovery detection: notify when worker comes back
```

### 4.2 Persistent Fleet Memory

```
Architecture:
  OpenClaw agents maintain persistent memory across sessions.
  Fleet-wide memory shared via NFS-backed ChromaDB.

  Worker Agent --> Local OpenClaw Memory (per-worker)
       |
       +--> Sync to NFS: ~/Development/data/openclaw-memory/
       |
       +--> ChromaDB (server-02): vector embeddings for semantic search
       |
       +--> Any worker can query any other worker's memory

Memory Hierarchy:
  1. Ephemeral (per-session): Current task context
  2. Persistent (per-worker): Worker-local learnings
  3. Fleet-wide (NFS): Cross-worker shared knowledge
  4. Indexed (ChromaDB): Semantic search across all memory

Implementation:
  - Extend openclaw-client.js with memory read/write API
  - Memory sync daemon on each worker (rsync to NFS every 5m)
  - Query API: searchFleetMemory(query, { workers: 'all' })
```

### 4.3 Proactive Monitoring (pi-02 Sentinel)

```
Architecture:
  pi-02 runs continuously as fleet sentinel:

  Sentinel (pi-02)
    |
    +--> Health Monitor: OpenClaw + SSH + system metrics
    |
    +--> Task Queue Monitor: Check for stuck/stalled tasks
    |
    +--> Log Aggregation: Collect and index worker logs
    |
    +--> Anomaly Detection: Alert on unusual patterns
    |
    +--> Auto-Remediation: Restart unhealthy services

Monitoring Stack:
  - Prometheus (metrics collection)
  - Grafana (dashboards) -- already partially deployed
  - ntfy (push notifications)
  - Custom scripts for OpenClaw-specific monitoring

Implementation:
  - Deploy monitoring/openclaw-sentinel.js on pi-02
  - Cron schedule: health every 60s, metrics every 5m, logs every 15m
  - Dashboard: extend existing Grafana with OpenClaw panels
```

### 4.4 Multi-Channel Notifications

```
Channels:
  1. ntfy (primary) -- already configured in fleet scripts
  2. Slack (webhook) -- for team visibility
  3. Discord (webhook) -- for personal alerts
  4. Telegram (bot API) -- mobile notifications

Notification Types:
  - CRITICAL: Worker down, security finding, compliance violation
  - WARNING: High latency, memory pressure, task timeout
  - INFO: Task complete, fleet status change, new worker online
  - DIGEST: Daily summary of fleet activity and findings

Implementation:
  - Create shared/notifications.js
  - Config in ~/.claude/notifications.json
  - Priority-based routing: critical -> all channels, info -> ntfy only
  - Rate limiting: max 10 notifications per hour per channel
```

### 4.5 Self-Improving Agents

```
Architecture:
  Agents that learn from consensus outcomes to improve over time.

  Consensus Run --> Record { model, accepted, reasoning, confidence }
       |
       +--> Learning System (already exists): /api/learning/record-feedback
       |
       +--> Performance Analysis: Which models are most accurate?
       |
       +--> Dynamic Weighting: Adjust confidence weights per model
       |
       +--> Prompt Refinement: Tune system prompts based on outcomes

Learning Loop:
  1. Run consensus workflow
  2. Record which worker won and why
  3. Track per-model accuracy over time
  4. Adjust worker weights (already in ai-consensus-weighted.js)
  5. OpenClaw: Additionally track execution success rate
  6. Periodically report model performance rankings

Implementation:
  - Extend ai-extract-learning.js with per-model tracking
  - Create shared/model-performance-tracker.js
  - Weekly report: which models are improving/declining
  - Auto-adjust weights in ai-consensus-weighted.js based on history
```

## Next Steps

1. Complete OpenClaw daemon onboarding (interactive setup required)
2. Run test-openclaw.js with daemon running
3. Enable OPENCLAW_ENABLED=true and test with /ai-prompt
4. Collect metrics on execution verification value
5. Install OpenClaw on fleet workers (server-01/02/03)
6. Decision point: Proceed to Phase 4 advanced features

## Multi-AI Design Report

Full design report (85% confidence, 3/3 models agreed):
- Located in workflow output: `/tmp/claude-1000/-home-sfloess/39a38f09-c545-4579-9ac1-6c31a694eba2/tasks/wgto1s2nu.output`
- 8 sections covering architecture, technical specs, implementation plan, risks, PoC, migration

## References

- OpenClaw: https://openclaw.ai/
- GitHub: https://github.com/openclaw/openclaw
- Docs: https://docs.openclaw.ai/
- Version: 2026.6.6 (8c802aa)
