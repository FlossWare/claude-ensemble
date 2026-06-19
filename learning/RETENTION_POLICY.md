# Workflow Embeddings Retention Policy

**Implementation Date:** 2026-06-19  
**Status:** Production Ready  
**Automation:** Daily at 3 AM (via backup script)

## Overview

Automatically clears workflow embeddings older than 90 days while preserving metadata. Embeddings consume 2× storage due to HNSW index overhead (3KB vector + 3KB index = 6KB per row).

## Architecture

### Database Schema
- **Table:** `learning.workflow_completions`
- **Embedding:** 768-dim vector (all-mpnet-base-v2)
- **Index:** HNSW for O(log n) similarity search
- **Retention:** 90 days (configurable)

### Storage Impact
- **Per embedding:** 6KB (3KB vector + 3KB HNSW index)
- **1000 workflows:** ~6MB
- **10,000 workflows:** ~60MB
- **Retention at 90 days:** Clears ~25MB/year (assuming 100 workflows/month)

### Cleanup Function
```sql
SELECT * FROM learning.cleanup_old_workflow_embeddings(90);
```

Returns:
- `deleted_count`: Number of embeddings cleared
- `freed_mb`: Approximate storage freed

## Files Created

### Database Schema
- `/home/sfloess/.claude/learning/schema_workflow_completions.sql`
  - Creates `learning.workflow_completions` table
  - HNSW index for fast similarity search
  - Indexes for retention cleanup

### Cleanup Function
- `/home/sfloess/.claude/learning/cleanup_workflow_embeddings.sql`
  - PostgreSQL function for retention policy
  - Clears embeddings, preserves metadata
  - Returns statistics (deleted_count, freed_mb)

### JavaScript Integration
- `/home/sfloess/.claude/learning/workflow-completion-tracker.js`
  - `trackWorkflowStart()` - Log workflow start
  - `trackWorkflowCompletion()` - Log completion + generate embedding
  - `searchSimilar()` - Semantic search over workflows
  - `getStats()` - Workflow statistics

### Example Workflow
- `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/deep-research-with-tracking.mjs`
  - Updated deep-research workflow with completion tracking
  - Demonstrates integration pattern

### Installation
- `/home/sfloess/.claude/learning/install_embeddings.sh`
  - Installs sentence-transformers (all-mpnet-base-v2)
  - Pre-downloads 420MB model

### Backup Script Update
- `/home/sfloess/bin/backup-learning-db.sh`
  - Runs retention cleanup BEFORE daily backup (3 AM)
  - Logs cleanup statistics

## Setup Instructions

### 1. Install Dependencies
```bash
bash /home/sfloess/.claude/learning/install_embeddings.sh
```

### 2. Create Database Schema
```bash
psql -h aio-01 -U postgres -d learning < /home/sfloess/.claude/learning/schema_workflow_completions.sql
psql -h aio-01 -U postgres -d learning < /home/sfloess/.claude/learning/cleanup_workflow_embeddings.sql
```

### 3. Verify Backup Script
```bash
# Check cron schedule (should run daily at 2 AM)
crontab -l | grep backup-learning-db.sh

# Test retention cleanup manually
psql -h aio-01 -U postgres -d learning -c "SELECT * FROM learning.cleanup_old_workflow_embeddings(90);"
```

## Integration Pattern

### Workflow Start
```javascript
const { getWorkflowTracker } = require('~/.claude/learning/workflow-completion-tracker.js');

const tracker = getWorkflowTracker();
await tracker.trackWorkflowStart({
  workflowName: 'my-workflow',
  sessionId: 'session_xyz',
  query: 'user query here',
  metadata: { version: '1.0' }
});
```

### Workflow Completion
```javascript
await tracker.trackWorkflowCompletion({
  sessionId: 'session_xyz',
  status: 'completed', // or 'failed'
  phases: { /* phase data */ },
  resultSummary: 'Summary of results for embedding',
  durationMs: 12345
});
```

### Semantic Search
```javascript
const similar = await tracker.searchSimilar('find workflows about X', limit=10);
console.log(similar); // Returns top 10 similar workflows
```

## Monitoring

### Check Statistics
```javascript
const stats = await tracker.getStats('deep-research');
console.log(stats);
// {
//   total_workflows: 150,
//   completed: 142,
//   failed: 8,
//   avg_duration_ms: 45000,
//   with_embeddings: 50,      // Recent workflows (< 90 days)
//   embeddings_cleared: 100   // Older than 90 days
// }
```

### Manual Cleanup Test
```bash
# Run cleanup manually (returns deleted_count, freed_mb)
psql -h aio-01 -U postgres -d learning -c "SELECT * FROM learning.cleanup_old_workflow_embeddings(90);"

# Example output:
#  deleted_count | freed_mb
# ---------------+----------
#            150 |     0.88
```

## Retention Policy Parameters

### Default: 90 Days
```sql
SELECT * FROM learning.cleanup_old_workflow_embeddings(90);
```

### Custom Retention (30 days)
```sql
SELECT * FROM learning.cleanup_old_workflow_embeddings(30);
```

### Disable Retention (365 days)
```sql
SELECT * FROM learning.cleanup_old_workflow_embeddings(365);
```

## Why 90 Days?

1. **Storage Efficiency:** HNSW index doubles storage cost (6KB per embedding)
2. **Semantic Search Value:** Recent workflows most relevant for similarity search
3. **Metadata Preservation:** All workflow data retained (query, phases, results)
4. **Cost-Benefit:** 90 days = ~3 months of searchable history, ~25MB freed/year

## Backup Integration

The retention cleanup runs BEFORE the daily PostgreSQL backup:

```bash
# Existing backup script (runs at 2 AM daily)
/home/sfloess/bin/backup-learning-db.sh

# Cleanup sequence:
# 1. Run retention cleanup (3 AM)
# 2. Dump PostgreSQL database
# 3. Distribute to 5 backup destinations
```

## Troubleshooting

### Cleanup Not Running
```bash
# Check backup script logs
grep "retention policy" /var/log/backup-learning-db.log

# Test manually
psql -h aio-01 -U postgres -d learning -c "SELECT * FROM learning.cleanup_old_workflow_embeddings(90);"
```

### Embeddings Not Generated
```bash
# Check sentence-transformers installation
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-mpnet-base-v2')"

# Test embedding generation
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-mpnet-base-v2')
embedding = model.encode('test query')
print(f'Embedding dim: {len(embedding)}')  # Should be 768
"
```

### Storage Not Freed
```bash
# Check HNSW index size
psql -h aio-01 -U postgres -d learning -c "
SELECT
  pg_size_pretty(pg_total_relation_size('learning.workflow_completions')) as total_size,
  pg_size_pretty(pg_indexes_size('learning.workflow_completions')) as index_size;
"

# VACUUM to reclaim space
psql -h aio-01 -U postgres -d learning -c "VACUUM FULL learning.workflow_completions;"
```

## Future Enhancements

1. **Adaptive Retention:** Adjust retention based on storage capacity
2. **Importance Scoring:** Preserve high-value workflows longer
3. **Compression:** Archive old embeddings to cold storage
4. **Neo4j Integration:** Store workflow relationships in graph database
