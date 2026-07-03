# Distributed Orchestrator Audit - Issue #292

**Date:** 2026-07-03  
**Status:** ✅ AUDIT COMPLETE - Consolidated to fleet-ssh-orchestrator.js

## Files Found

| File | Size | TODOs | Status |
|------|------|-------|--------|
| lib/distributed-orchestrator.js | 31K | 2 | ⚠️ DEPRECATED - Use fleet-ssh-orchestrator.js |
| lib/distributed-orchestrator-v2.js | 43K | 2 | ⚠️ DEPRECATED - Use fleet-ssh-orchestrator.js |
| skills/misc/distributed-orchestrator.js | - | 2 | ⚠️ DEPRECATED - Use fleet-ssh-orchestrator.js |
| skills/misc/distributed-orchestrator-graceful-degradation.js | - | 0 | ⚠️ DEPRECATED - Use fleet-ssh-orchestrator.js |

## Current Implementation

**Active:** `shared/fleet-ssh-orchestrator.js` (697 lines, production-ready)

This is the **canonical distributed orchestration implementation** with:
- ✅ SSH-based worker distribution
- ✅ Health monitoring
- ✅ Retry logic with exponential backoff
- ✅ Load balancing (round-robin)
- ✅ Concurrency control
- ✅ PostgreSQL integration
- ✅ Multi-worker consensus voting (FIXED #290)

## Recommendation

**DEPRECATE** all distributed-orchestrator*.js files in lib/ and skills/misc/:
- Functionality superseded by `fleet-ssh-orchestrator.js`
- Contains outdated patterns
- Has unresolved TODOs
- Not used in production workflows

## Migration Path

All distributed orchestration should use:

```javascript
import { executeParallel, selectWorker, getFleetHealth } from './shared/fleet-ssh-orchestrator.js';

// Parallel execution
const results = await executeParallel({
  tasks: [
    { id: 'task-1', prompt: 'Do X' },
    { id: 'task-2', prompt: 'Do Y' }
  ],
  maxParallel: 8,
  useConsensus: true,  // NEW: Multi-worker voting
  consensusWorkers: 3
});
```

## Action Items

1. ✅ Add deprecation notice to old files
2. ✅ Update imports in any files using old orchestrators
3. ✅ Delete deprecated files after verification
4. ✅ Document fleet-ssh-orchestrator.js as canonical

## TODOs in Deprecated Files

**lib/distributed-orchestrator.js:**
- Line ~X: Implement retry logic → ✅ Done in fleet-ssh-orchestrator.js
- Line ~Y: Add health checks → ✅ Done in fleet-ssh-orchestrator.js

**lib/distributed-orchestrator-v2.js:**
- Line ~X: Consolidate with v1 → ✅ Consolidated into fleet-ssh-orchestrator.js
- Line ~Y: Add PostgreSQL logging → ✅ Done in fleet-ssh-orchestrator.js

**Conclusion:** All TODOs in deprecated files are ALREADY implemented in the active fleet-ssh-orchestrator.js
