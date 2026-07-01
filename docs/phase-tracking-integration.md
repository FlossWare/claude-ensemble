# Workflow Phase Tracking Integration

**Status:** ✅ COMPLETE (Issue #250)  
**Database:** `workflow.phases` on aio-01:5433  
**Created:** 2026-07-01

## Overview

Automatic phase tracking for workflows with PostgreSQL storage. Tracks timing, outcome, and metadata for each phase.

## Quick Start

### 1. Import the tracker

```javascript
import { PhaseTracker } from '../shared/phase-tracker.js';
```

### 2. Initialize in your workflow

```javascript
export default async function({ args, phase, log, agent }) {
  // Create tracker
  const tracker = new PhaseTracker(
    'my-workflow-name',
    'Task description',
    { enableStorage: true }
  );

  // Initialize (creates workflow.executions record)
  await tracker.init();

  // Wrap the phase() function
  const trackedPhase = tracker.createPhaseWrapper(phase);

  // Use trackedPhase() instead of phase()
  trackedPhase('Phase 1');
  // ... do work ...

  trackedPhase('Phase 2');
  // ... do work ...

  // Complete workflow (updates execution record)
  await tracker.complete('success', { custom_metadata: 'value' });

  return result;
}
```

## What Gets Stored

### workflow.executions table

- `workflow_id` - Unique workflow identifier
- `workflow_name` - Workflow name
- `task_description` - Original task/prompt
- `total_duration_ms` - Total execution time
- `outcome` - 'success' | 'failed' | 'error'
- `metadata` - Custom metadata (JSONB)
- `created_at` - Timestamp

### workflow.phases table

- `workflow_execution_id` - Parent workflow ID
- `phase_name` - Phase name (e.g., 'Read PDFs', 'Extract Claims')
- `phase_order` - Sequential order (0, 1, 2, ...)
- `duration_ms` - Phase execution time
- `outcome` - 'success' | 'failed' | 'error'
- `metadata` - Phase-specific metadata (JSONB)
- `created_at` - Timestamp

## Sample Queries

### Phase Performance by Workflow

```sql
SELECT 
  e.workflow_name,
  p.phase_name,
  AVG(p.duration_ms) as avg_duration_ms,
  COUNT(*) as executions,
  SUM(CASE WHEN p.outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as success_rate
FROM workflow.phases p
JOIN workflow.executions e ON p.workflow_execution_id = e.id
GROUP BY e.workflow_name, p.phase_name
ORDER BY e.workflow_name, p.phase_order;
```

### Slowest Phases (Last 30 days)

```sql
SELECT 
  e.workflow_name,
  p.phase_name,
  p.duration_ms,
  p.outcome,
  e.created_at
FROM workflow.phases p
JOIN workflow.executions e ON p.workflow_execution_id = e.id
WHERE e.created_at > NOW() - INTERVAL '30 days'
ORDER BY p.duration_ms DESC
LIMIT 20;
```

### Phase Failure Analysis

```sql
SELECT 
  e.workflow_name,
  p.phase_name,
  COUNT(*) as total_failures,
  p.metadata->'error' as error_message
FROM workflow.phases p
JOIN workflow.executions e ON p.workflow_execution_id = e.id
WHERE p.outcome = 'error'
GROUP BY e.workflow_name, p.phase_name, p.metadata->'error'
ORDER BY total_failures DESC;
```

### Workflow Completion Times

```sql
SELECT 
  workflow_name,
  AVG(total_duration_ms) as avg_duration_ms,
  MIN(total_duration_ms) as min_duration_ms,
  MAX(total_duration_ms) as max_duration_ms,
  COUNT(*) as executions
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY workflow_name
ORDER BY avg_duration_ms DESC;
```

## API Reference

### PhaseTracker Class

#### Constructor

```javascript
new PhaseTracker(workflowName, taskDescription, options)
```

**Parameters:**
- `workflowName` (string) - Workflow identifier
- `taskDescription` (string) - Task description for similarity search
- `options` (object) - Configuration
  - `enableStorage` (boolean) - Enable PostgreSQL storage (default: true)
  - `autoComplete` (boolean) - Auto-complete on process exit (default: true)

#### Methods

**`async init()`**
Initialize tracker and create workflow execution record.
Returns: `Promise<number>` - Workflow execution ID

**`startPhase(phaseName)`**
Start tracking a phase manually.
Returns: `Object` - Phase metadata

**`async endPhase(phaseName, outcome = 'success', metadata = {})`**
End tracking a phase and store to PostgreSQL.

**`async phase(phaseName, fn)`**
Track a phase with automatic timing (wrapper pattern).
Returns: `Promise<any>` - Result from fn

**`createPhaseWrapper(originalPhase)`**
Create a wrapper that replaces workflow's `phase()` parameter.
Returns: `Function` - Wrapped phase function

**`async complete(outcome = 'success', metadata = {})`**
Complete workflow and update execution record.

**`getStats()`**
Get phase statistics.
Returns: `Object` - Phase stats

## Example Workflows

See:
- `workflows/demo-phase-tracking.js` - Simple demonstration
- `shared/test-phase-tracker.js` - Test suite with verification

## Integration Patterns

### Pattern 1: Wrapper (Recommended)

Replace the `phase()` parameter with a tracked version:

```javascript
const tracker = new PhaseTracker('workflow', 'task');
await tracker.init();
const trackedPhase = tracker.createPhaseWrapper(phase);

// Use it like normal
trackedPhase('Phase 1');
// work...
trackedPhase('Phase 2');
// work...

await tracker.complete('success');
```

### Pattern 2: Manual Tracking

For complex workflows with conditional phases:

```javascript
const tracker = new PhaseTracker('workflow', 'task');
await tracker.init();

tracker.startPhase('Phase 1');
try {
  // work...
  await tracker.endPhase('Phase 1', 'success');
} catch (error) {
  await tracker.endPhase('Phase 1', 'error', { error: error.message });
  throw error;
}

await tracker.complete('success');
```

### Pattern 3: Async Function Wrapper

For phase-as-a-function pattern:

```javascript
const tracker = new PhaseTracker('workflow', 'task');
await tracker.init();

await tracker.phase('Phase 1', async () => {
  // work...
  return result;
});

await tracker.phase('Phase 2', async () => {
  // work...
  return result;
});

await tracker.complete('success');
```

## Migration Guide

To add phase tracking to an existing workflow:

1. Import `PhaseTracker` at the top
2. Create tracker instance before first phase
3. Initialize tracker with `await tracker.init()`
4. Replace `phase()` calls with `trackedPhase = tracker.createPhaseWrapper(phase)`
5. Add `await tracker.complete()` before return

**Before:**
```javascript
export default async function({ args, phase, log }) {
  phase('Work');
  // ... work ...
  return result;
}
```

**After:**
```javascript
import { PhaseTracker } from '../shared/phase-tracker.js';

export default async function({ args, phase, log }) {
  const tracker = new PhaseTracker('my-workflow', args);
  await tracker.init();
  const trackedPhase = tracker.createPhaseWrapper(phase);

  trackedPhase('Work');
  // ... work ...

  await tracker.complete('success');
  return result;
}
```

## Performance Impact

- **Overhead:** ~1-2ms per phase (PostgreSQL INSERT)
- **Storage:** ~200 bytes per phase record
- **Network:** Single query per phase (non-blocking)

Phase tracking is asynchronous and won't block workflow execution.

## Troubleshooting

### "sentence-transformers not installed" warning

This is expected and harmless. Embeddings are stored as NULL when unavailable.
To enable embeddings for similarity search:

```bash
pip3 install sentence-transformers
```

### "Phase tracking: storage disabled"

Check:
1. PostgreSQL is running: `psql -h aio-01 -p 5433 -U claude -d learning -c 'SELECT 1'`
2. Database credentials are correct
3. `workflow.phases` table exists

### Duplicate workflow_id error

The `workflow_id` must be unique. The tracker generates IDs like:
`{workflow-name}-{timestamp}-{pid}-{random}`

If you see duplicates, ensure you're creating a new PhaseTracker instance per execution.

## Testing

```bash
# Run test suite
node shared/test-phase-tracker.js

# Verify data in PostgreSQL
psql -h aio-01 -p 5433 -U claude -d learning -c \
  "SELECT * FROM workflow.phases ORDER BY created_at DESC LIMIT 10"
```

## Related

- **Issue #250** - Wire in workflow phases tracking
- **Database Schema** - `workflow.phases` table on aio-01:5433
- **Storage Adapter** - `shared/workflow-storage-adapter.cjs`
