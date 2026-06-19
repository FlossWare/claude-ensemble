# Workflow Storage Adapter - Automated View Refresh

**Implementation Date:** 2026-06-19  
**Step:** 8 of Deep Research Workflow Integration  
**Status:** READY FOR TESTING

## Overview

Automated materialized view refresh system that keeps dashboard queries and Thompson Sampling state current after each workflow completion.

## Architecture

```
Workflow Completion
       ↓
storeExecution()
       ↓
   BEGIN TRANSACTION
       ↓
Insert execution_summary ──→ monitoring.execution_summary
       ↓
Update strategy_performance ──→ learning.strategy_performance
       ↓
   COMMIT TRANSACTION
       ↓
refreshViews() [CONCURRENTLY]
       ↓
Refresh 5 materialized views in parallel:
  - monitoring.model_performance_summary
  - monitoring.workflow_efficiency
  - monitoring.cost_analysis
  - learning.strategy_rankings
  - monitoring.recent_activity_summary
       ↓
   DONE (no blocking reads)
```

## Files Created

### 1. Workflow Storage Adapter
**Location:** `~/.claude/learning/workflow-storage-adapter.js`

**Key Features:**
- Stores workflow execution data
- Updates Thompson Sampling bandit state
- Automatically refreshes materialized views
- Uses CONCURRENTLY to avoid blocking reads
- Fallback to blocking refresh if CONCURRENTLY fails
- Vector similarity search for experience replay

**API:**
```javascript
const { WorkflowStorageAdapter } = require('~/.claude/learning/workflow-storage-adapter.js');

const storage = new WorkflowStorageAdapter();

// Store execution (auto-refreshes views)
await storage.storeExecution({
  workflow: 'deep-research',
  model: 'claude-opus-4',
  task_type: 'research_synthesis',
  quality_score: 0.85,
  input_tokens: 1000,
  output_tokens: 500,
  cost_usd: 0.015,
  duration_ms: 2500,
  outcome: 'success',
  metadata: { strategy: 'adversarial_verify' }
});

// Manual view refresh
await storage.refreshViews();

// Thompson Sampling selection
const bestStrategy = await storage.selectStrategy();

// Vector similarity search
const similar = await storage.findSimilarExperiences(embedding, 10, 0.7);
```

### 2. Database Migration
**Location:** `~/.claude/learning/migrations/002_create_materialized_views.sql`

**Creates:**
- 5 materialized views with UNIQUE indexes
- `workflows.refresh_views()` PostgreSQL function
- Permissions and comments

**Run:**
```bash
psql -h laptop-01 -U sfloess -d learning -f ~/.claude/learning/migrations/002_create_materialized_views.sql
```

### 3. Integration Example
**Location:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/deep-research.mjs`

**Changes:**
- Import `WorkflowStorageAdapter`
- Track execution metrics (quality, duration, tokens)
- Store execution on success/failure
- Auto-refresh views after completion

### 4. Test Suite
**Location:** `~/.claude/learning/test-view-refresh.js`

**Tests:**
- Schema initialization
- Execution storage
- View refresh (CONCURRENTLY)
- Thompson Sampling selection
- Vector similarity search

**Run:**
```bash
node ~/.claude/learning/test-view-refresh.js
```

## Materialized Views

### 1. model_performance_summary
**Purpose:** Grafana dashboard - model comparison  
**Metrics:** executions, avg_quality, total_cost, avg_duration, success_rate  
**Group By:** model

### 2. workflow_efficiency
**Purpose:** Workflow optimization insights  
**Metrics:** executions, avg_quality, median_duration, p95_duration, success_rate  
**Group By:** workflow, task_type

### 3. cost_analysis
**Purpose:** Budget monitoring  
**Metrics:** daily_cost, total_tokens, executions, avg_cost_per_execution  
**Group By:** date, model, workflow

### 4. strategy_rankings
**Purpose:** Thompson Sampling bandit state  
**Metrics:** successes, failures, avg_reward, expected_reward, rank  
**Group By:** strategy

### 5. recent_activity_summary
**Purpose:** Real-time monitoring (last 24h)  
**Metrics:** executions, avg_quality, total_cost  
**Group By:** hour, model, workflow

## Performance

### CONCURRENTLY Option
- **No blocking:** Reads continue during refresh
- **Requirement:** UNIQUE index on materialized view
- **Fallback:** Blocking refresh if CONCURRENTLY fails
- **Overhead:** ~10-20% slower than blocking refresh

### Refresh Times (Estimated)
| View | Rows | Refresh Time |
|------|------|--------------|
| model_performance_summary | 10-20 | <50ms |
| workflow_efficiency | 50-100 | <100ms |
| cost_analysis | 1000-5000 | <500ms |
| strategy_rankings | 10-50 | <50ms |
| recent_activity_summary | 100-500 | <200ms |

**Total:** <1 second for all 5 views

## Integration Workflow

### Step 1: Initialize Schema
```bash
# Run migration
psql -h laptop-01 -U sfloess -d learning \
  -f ~/.claude/learning/migrations/002_create_materialized_views.sql

# Or use adapter CLI
node ~/.claude/learning/workflow-storage-adapter.js
```

### Step 2: Update Existing Workflows
```javascript
import { WorkflowStorageAdapter } from '~/.claude/learning/workflow-storage-adapter.js';

const storage = new WorkflowStorageAdapter();

// At workflow start
const startTime = Date.now();

try {
  // ... workflow logic ...

  // At workflow completion
  await storage.storeExecution({
    workflow: 'my-workflow',
    model: 'claude-sonnet-4',
    task_type: 'my_task',
    quality_score: 0.85,
    input_tokens: 1000,
    output_tokens: 500,
    cost_usd: 0.015,
    duration_ms: Date.now() - startTime,
    outcome: 'success',
    metadata: { /* custom data */ }
  });

  await storage.disconnect();
} catch (err) {
  // Store failure
  await storage.storeExecution({
    workflow: 'my-workflow',
    model: 'claude-sonnet-4',
    task_type: 'my_task',
    quality_score: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    duration_ms: Date.now() - startTime,
    outcome: 'failure',
    metadata: { error: err.message }
  });
  await storage.disconnect();
}
```

### Step 3: Query Materialized Views
```sql
-- Grafana dashboard query
SELECT model, avg_quality, success_rate, total_cost
FROM monitoring.model_performance_summary
ORDER BY avg_quality DESC;

-- Strategy selection
SELECT strategy, expected_reward, rank
FROM learning.strategy_rankings
ORDER BY rank
LIMIT 10;

-- Recent activity
SELECT hour, workflow, executions, avg_quality
FROM monitoring.recent_activity_summary
ORDER BY hour DESC;
```

### Step 4: Manual Refresh (if needed)
```sql
-- Refresh all views (PostgreSQL function)
SELECT * FROM workflows.refresh_views();

-- Refresh single view
REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.model_performance_summary;
```

## Thompson Sampling Integration

The storage adapter automatically updates bandit state when `metadata.strategy` is provided:

```javascript
await storage.storeExecution({
  workflow: 'code-review',
  model: 'claude-sonnet-4',
  task_type: 'review',
  quality_score: 0.87,
  // ... other fields ...
  metadata: {
    strategy: 'ast_analysis',  // Auto-updates learning.strategy_performance
    // ... other metadata ...
  }
});
```

**Bandit Update:**
- Success → `successes++`, `alpha++`, `total_reward += quality_score`
- Failure → `failures++`, `beta++`
- `avg_reward = total_reward / (successes + failures)`

**Strategy Selection:**
```javascript
const bestStrategy = await storage.selectStrategy();
// Returns: strategy with highest Thompson sample (Beta distribution)
```

## Vector Similarity Search

Store experiences with embeddings for experience replay:

```javascript
// Store experience
await storage.storeExperience({
  problem_type: 'code_refactor',
  problem_hash: 'sha256_of_problem',
  context: { language: 'java', complexity: 'high' },
  embedding: [0.123, 0.456, ...], // 128-dim or 768-dim vector
  strategy: 'ast_analysis',
  success: true,
  reward: 0.87,
  novelty_score: 0.65,
  importance: 0.80
});

// Find similar past experiences
const similar = await storage.findSimilarExperiences(
  queryEmbedding,
  limit = 10,
  minReward = 0.7
);

// Returns: [{problem_type, strategy, reward, distance}, ...]
```

**Use Case:** Learn from past successes before attempting new task.

## Monitoring

### Logs
```bash
# View refresh logs
tail -f /var/log/postgresql/postgresql-*.log | grep "REFRESH MATERIALIZED VIEW"

# Workflow execution logs
psql -h laptop-01 -U sfloess -d learning -c \
  "SELECT workflow, outcome, quality_score, timestamp 
   FROM monitoring.execution_summary 
   ORDER BY timestamp DESC LIMIT 10"
```

### Performance Metrics
```sql
-- View refresh performance
SELECT
  matviewname,
  last_refresh,
  NOW() - last_refresh as staleness
FROM pg_matviews
WHERE schemaname IN ('monitoring', 'learning');
```

### Grafana Integration
```sql
-- Dashboard query example
SELECT
  $__timeGroup(timestamp, '1h') as time,
  model,
  AVG(quality_score) as quality
FROM monitoring.execution_summary
WHERE $__timeFilter(timestamp)
GROUP BY 1, 2
ORDER BY 1;
```

## Troubleshooting

### Error: "CONCURRENTLY cannot be used without a unique index"
**Solution:**
```sql
CREATE UNIQUE INDEX idx_my_view_key ON monitoring.my_view(key_column);
```

### Error: "materialized view does not exist"
**Solution:**
```bash
psql -h laptop-01 -U sfloess -d learning \
  -f ~/.claude/learning/migrations/002_create_materialized_views.sql
```

### Error: "permission denied for function refresh_views"
**Solution:**
```sql
GRANT EXECUTE ON FUNCTION workflows.refresh_views() TO sfloess;
```

### Slow View Refresh
**Check:**
```sql
SELECT schemaname || '.' || matviewname, pg_size_pretty(pg_total_relation_size(schemaname || '.' || matviewname))
FROM pg_matviews
WHERE schemaname IN ('monitoring', 'learning');
```

**If > 100MB:** Consider partitioning or archiving old data.

## Next Steps

1. **Run Migration:**
   ```bash
   psql -h laptop-01 -U sfloess -d learning -f ~/.claude/learning/migrations/002_create_materialized_views.sql
   ```

2. **Test:**
   ```bash
   node ~/.claude/learning/test-view-refresh.js
   ```

3. **Integrate Other Workflows:**
   - Update `workflows/*.mjs` to import `WorkflowStorageAdapter`
   - Add `storeExecution()` calls at completion
   - Track quality metrics

4. **Configure Grafana:**
   - Add datasource: PostgreSQL (laptop-01:5432/learning)
   - Import dashboard queries from materialized views
   - Set refresh interval: 30s

5. **Monitor:**
   - Check view staleness daily
   - Alert if refresh fails
   - Track storage growth

## Cost Estimate

**Storage:** ~10KB per execution × 10,000 executions = 100MB  
**Views:** ~5 views × 20KB each = 100KB  
**Total:** ~100MB for 10,000 workflow executions

**Refresh Overhead:** <1 second per workflow completion  
**Impact:** Negligible (<0.1% of typical workflow duration)

## Truth in Labeling

**What this system DOES:**
- ✅ Store workflow execution metrics
- ✅ Auto-refresh dashboard views (no stale data)
- ✅ Update Thompson Sampling bandit state
- ✅ Enable vector similarity search for experience replay
- ✅ Avoid blocking reads (CONCURRENTLY option)

**What this system DOES NOT:**
- ✗ Improve model intelligence (orchestration only)
- ✗ Guarantee real-time updates (<1s delay possible)
- ✗ Handle distributed transactions (single PostgreSQL instance)
- ✗ Scale beyond 100K executions/day (needs partitioning)

This is a **data layer** for workflow monitoring, not an intelligence layer.
