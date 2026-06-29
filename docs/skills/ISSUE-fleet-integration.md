# Add fleet support to orchestrator for distributed Thompson Sampling

**Labels:** enhancement, orchestrator, fleet  
**Priority:** Medium

## Problem

Orchestrator is local-only. Thompson Sampling doesn't leverage the fleet infrastructure for distributed execution.

## Current State

- ✅ Fleet infrastructure exists (5 servers: server-01 through server-05)
- ✅ NFS-shared code at `~/Development/`
- ✅ Thompson Sampling state is file-based (can be shared)
- ❌ Orchestrator has NO fleet integration
- ❌ All model selection happens locally

## Missing Integration

```javascript
// orchestrator.js needs fleet support:
import { executeOnFleet } from './shared/fleet-executor.js'

export async function selectWorkers(taskType, options = {}) {
  const models = await selectWithThompson(taskType, options)
  
  // If fleet enabled, distribute workers across servers
  if (options.useFleet && isFleetAvailable()) {
    return {
      models,
      executor: 'fleet',
      servers: distributeWorkersToServers(models)
    }
  }
  
  return { models, executor: 'local' }
}
```

## Benefits

- **5x parallel execution** - Distribute 6 models across 5 servers
- **Faster consensus** - Parallel worker execution instead of sequential
- **Shared learning** - Fleet shares Thompson Sampling state via NFS
- **Load distribution** - Balance work across available servers

## Architecture

```
orchestrator.selectWorkers()
  ↓
Thompson Sampling selects models (local)
  ↓
Distribute models → Fleet servers
  ↓
  server-01: opus     ← SSH/HTTP
  server-02: sonnet   ← SSH/HTTP
  server-03: haiku    ← SSH/HTTP
  server-04: fable    ← SSH/HTTP
  server-05: gpt-4o   ← SSH/HTTP
  ↓
Collect results → Arbiter synthesis (local)
  ↓
Record quality → Thompson state (shared NFS)
```

## Acceptance Criteria

- [ ] Orchestrator detects fleet availability (`isFleetAvailable()`)
- [ ] `selectWorkers()` accepts `useFleet: true` option
- [ ] Distributes workers across available servers
- [ ] Executes workers in parallel via SSH or HTTP
- [ ] Collects results from all fleet nodes
- [ ] Falls back to local if fleet unavailable
- [ ] Thompson state updates are visible across fleet (NFS)
- [ ] Test: 6-model consensus runs on 5 servers in parallel
- [ ] Documentation: Fleet execution pattern

## Implementation Notes

- Reuse existing fleet infrastructure (don't rebuild)
- Use SSH for simple execution, HTTP for complex workflows
- Thompson state file is already NFS-shared at `~/.claude/learning/bandit-state.json`
- Fleet servers: server-01, server-02, server-03, server-04, server-05
- Check `~/.ssh/config` for fleet SSH aliases

## Dependencies

- Requires: Fleet infrastructure operational
- Blocks: None (independent of discoveries integration)
- Related: Could combine with discoveries for intelligent fleet routing
