# Knowledge Sync Quick Start

## 5-Minute Setup

### 1. Verify Integration
```bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
node scripts/verify-knowledge-sync.js
```

**Expected output:**
```
✅ Passed: 7
❌ Failed: 0
🎉 ALL TESTS PASSED
```

### 2. Start Background Daemon
```bash
# Terminal 1 (aio-01)
node services/knowledge-sync-daemon.js
```

**Expected output:**
```
[2026-07-01T12:00:00.000Z] Knowledge Sync Daemon starting...
[2026-07-01T12:00:00.100Z] Connected to PostgreSQL
[2026-07-01T12:00:00.150Z] Connected to Neo4j
[2026-07-01T12:00:05.000Z] Found 0 verified discoveries to sync
[2026-07-01T12:00:05.010Z] Sync cycle complete: 0 synced, 0 failed
```

### 3. Run a Workflow (Generate Discoveries)
```javascript
// In any workflow file
const { onWorkflowComplete } = require('./shared/workflow-completion-hook');

// At workflow end
await onWorkflowComplete({
  workflow_id: 'test-001',
  workflow_name: 'test-workflow',
  task: 'Test task',
  workers: [{
    worker_id: 'worker-01',
    model: 'opus',
    quality_score: 0.85, // > 0.8 triggers discovery extraction
    result: { finding: 'Interesting insight' }
  }],
  arbiter: {
    model: 'sonnet',
    reasoning: 'Selected opus for detail',
    confidence: 0.8
  },
  outcome: 'success',
  duration_ms: 5000
});
```

**Expected log:**
```
[workflow-storage] Shared 2 discoveries with fleet via knowledge_sync.py
```

### 4. Check Status
```bash
node services/knowledge-sync-daemon.js --status | jq .
```

**Output:**
```json
{
  "daemon": {
    "discoveries_synced": 2,
    "last_sync": "2026-07-01T12:05:00.000Z"
  },
  "database": {
    "pending": 2,
    "verified": 0,
    "total": 2,
    "unsynced": 0
  }
}
```

### 5. Verify Discoveries (Multi-Worker Voting)
```javascript
const { verifyDiscovery, getPendingDiscoveries } = require('./shared/knowledge-sync-integration');

// Get pending
const pending = await getPendingDiscoveries();
console.log(pending);
// [{ id: 1, content: "...", verifications: 0, rejections: 0 }]

// Vote (need 3 approvals for verification)
await verifyDiscovery({
  discoveryId: 1,
  workerId: 'worker-02',
  approve: true,
  reasoning: 'Confirmed in testing'
});

await verifyDiscovery({
  discoveryId: 1,
  workerId: 'worker-03',
  approve: true
});

await verifyDiscovery({
  discoveryId: 1,
  workerId: 'worker-04',
  approve: true
});
// After 3rd approval: status changes to 'verified'
```

### 6. Query Fleet Knowledge
```javascript
const { getFleetKnowledge } = require('./shared/knowledge-sync-integration');

const knowledge = await getFleetKnowledge({
  minConfidence: 0.8,
  type: 'optimization',
  limit: 10
});

console.log(knowledge);
// [
//   {
//     id: 1,
//     type: 'optimization',
//     content: 'HNSW index provides 2x faster similarity search',
//     confidence: 0.9,
//     verifications: 3,
//     verified_by: ['worker-02', 'worker-03', 'worker-04']
//   }
// ]
```

## Common Commands

### Check Logs
```bash
tail -f ~/.claude/learning/logs/knowledge-sync-daemon.log
```

### Manual Sync (One-Time)
```bash
node services/knowledge-sync-daemon.js --once
```

### PostgreSQL Queries
```bash
psql -h aio-01 -p 5433 -U claude -d learning

-- Pending discoveries
SELECT id, worker_id, discovery_type, content, verification_count
FROM knowledge.discoveries
WHERE status = 'pending'
ORDER BY created_at DESC;

-- Verified knowledge
SELECT id, content, confidence, verification_count, verified_at
FROM knowledge.discoveries
WHERE status = 'verified'
ORDER BY verified_at DESC;
```

### Neo4j Queries
```bash
# Connect to Neo4j Browser: http://aio-01:7474

// All discoveries
MATCH (d:Discovery)
RETURN d
ORDER BY d.verifiedAt DESC
LIMIT 20;

// Discovery network
MATCH (w:Worker)-[:DISCOVERED]->(d:Discovery)<-[:VERIFIED]-(v:Worker)
RETURN w, d, v
LIMIT 50;
```

## Integration Points Summary

| Component | File | Purpose |
|-----------|------|---------|
| Core Logic | `tools/knowledge_sync.py` | PostgreSQL storage, verification voting |
| Node.js Adapter | `shared/knowledge-sync-integration.js` | JavaScript wrapper for Python |
| Auto-Extraction | `shared/workflow-completion-hook.js` | Extract discoveries from workflows |
| Background Sync | `services/knowledge-sync-daemon.js` | Poll + sync to Neo4j |
| Verification | `scripts/verify-knowledge-sync.js` | Integration tests |

## Troubleshooting

**No discoveries extracted?**
- Check worker `quality_score > 0.8`
- Verify workflow data includes `workers` array

**Verification stuck at 2 votes?**
- Need 3+ workers to vote
- Auto-verification not yet implemented (manual for now)

**Neo4j sync not working?**
- Check `NEO4J_PASSWORD` env var set
- Daemon continues in PostgreSQL-only mode if Neo4j unavailable

**Daemon not starting?**
- Check PostgreSQL running: `systemctl status postgresql`
- Check logs: `~/.claude/learning/logs/knowledge-sync-daemon.log`

## Next Steps

1. **Production deployment:** Setup systemd service (see KNOWLEDGE_SYNC_INTEGRATION.md)
2. **Auto-verification:** Implement Thompson Sampling verifier selection
3. **Knowledge RAG:** Use verified discoveries in semantic search
4. **Monitoring:** Add Prometheus metrics to daemon
5. **Alerts:** Slack notifications for high-confidence discoveries

## API Reference

### shareDiscovery
```javascript
await shareDiscovery({
  workerId: string,
  type: 'optimization' | 'pattern' | 'bug' | 'insight' | 'technique',
  content: string,
  confidence: number // 0.0-1.0
});
// Returns: discoveryId
```

### verifyDiscovery
```javascript
await verifyDiscovery({
  discoveryId: number,
  workerId: string,
  approve: boolean,
  reasoning?: string
});
// Returns: { verifications, rejections, status }
```

### getFleetKnowledge
```javascript
await getFleetKnowledge({
  minConfidence?: number, // default: 0.7
  type?: string,
  limit?: number // default: 20
});
// Returns: Array<Discovery>
```

### getPendingDiscoveries
```javascript
await getPendingDiscoveries({
  limit?: number // default: 10
});
// Returns: Array<Discovery>
```

### getStats
```javascript
await getStats();
// Returns: { total, verified, pending, rejected, active_workers, total_votes }
```

## Success Criteria

- ✅ Daemon running continuously
- ✅ Discoveries auto-extracted from workflows
- ✅ Multi-worker verification working
- ✅ Fleet knowledge queryable
- ✅ Neo4j graph synchronized

**Status:** Integration complete, ready for production use
