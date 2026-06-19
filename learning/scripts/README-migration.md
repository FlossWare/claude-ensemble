# Workflow History Migration

This directory contains scripts for migrating historical workflow session data into PostgreSQL for continual learning and Thompson Sampling baseline.

## Files

- **migrate-workflow-history.js** - Main migration script
- **test-migration.js** - Test script with sample data
- **README-migration.md** - This file

## Usage

### Basic Migration

Migrate all workflow sessions from default directory:

```bash
node migrate-workflow-history.js
```

### Dry Run

Preview what would be migrated without writing to database:

```bash
node migrate-workflow-history.js --dry-run
```

### Custom Session Directory

Migrate from a specific directory:

```bash
node migrate-workflow-history.js --session-dir /path/to/sessions
```

### Force Re-migration

Re-migrate sessions that were already processed:

```bash
node migrate-workflow-history.js --force
```

### Combined Options

```bash
node migrate-workflow-history.js --dry-run --force --session-dir /tmp/test-sessions
```

## What Gets Migrated

The migration script processes session JSON files (e.g., from `deep-research.mjs`) and extracts:

1. **Workflow Run Metadata** → `workflows.runs` table
   - Run ID, workflow name, status
   - Input arguments, output result
   - Error messages, duration

2. **Workflow Learnings** → `workflows.learnings` table
   - Task difficulty (easy/moderate/hard)
   - Quality score (claim acceptance ratio)
   - Outcome (success/failed/error)
   - Model count, duration, cost
   - Metadata (phases completed, error details)
   - Embedding vector (128-dim, generated from query)

3. **Thompson Sampling Strategy** → `learning.strategy_performance` table
   - Strategy name: `deep-research-workflow`
   - Success/failure counts
   - Reward (quality score)
   - Alpha/beta parameters for Thompson Sampling

## Migration State

The script tracks migrated sessions in:

```
~/.claude/learning/migration-state.json
```

This prevents duplicate migrations. Use `--force` to override.

## Data Extraction

### Quality Score

Calculated from session data:

1. **If verify phase completed:** `acceptedClaims / totalClaims`
2. **Otherwise:** `completedPhases / totalPhases`

### Task Difficulty

Assessment based on completion:

- **easy**: ≥80% phases completed, no errors
- **moderate**: 50-80% phases completed
- **hard**: <50% phases completed OR has errors

### Outcome

- **success**: Session completed successfully
- **failed**: Incomplete or phase failed
- **error**: Session failed with error

### Worker Models

Extracted from phase data:

- **Verify phase**: Uses `opus`, `sonnet`, `haiku` for 3-vote verification
- Future: Extract from other multi-model phases

### Embedding Generation

Simple character frequency embedding (placeholder):

- 128-dimensional vector
- Character frequency distribution
- Normalized to unit length
- **TODO**: Replace with proper embedding model (e.g., Sentence-BERT)

## Testing

Run the test script to verify migration with sample data:

```bash
node test-migration.js
```

This creates 3 test sessions:
1. Successful deep research (all phases completed)
2. Failed research (verification timeout)
3. Partial completion (stopped at fetch)

Test sessions are created in `~/.claude/learning/test-sessions/`

## Integration with Workflows

To automatically migrate new sessions, add a completion hook to workflows:

```javascript
// In deep-research.mjs (or other workflow)
import { execSync } from 'child_process';

// After workflow completes
execSync('node ~/.claude/learning/scripts/migrate-workflow-history.js');
```

Or use a cron job:

```bash
# Migrate new sessions every hour
0 * * * * node ~/.claude/learning/scripts/migrate-workflow-history.js >> /tmp/migration.log 2>&1
```

## Database Schema

### workflows.runs

```sql
CREATE TABLE workflows.runs (
  run_id TEXT PRIMARY KEY,
  workflow_name TEXT NOT NULL,
  status TEXT NOT NULL, -- 'running', 'completed', 'failed'
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  input_args JSONB,
  output_result JSONB,
  error_message TEXT,
  duration_ms INTEGER
);
```

### workflows.learnings

```sql
CREATE TABLE workflows.learnings (
  id SERIAL PRIMARY KEY,
  run_id TEXT REFERENCES workflows.runs(run_id),
  workflow_name TEXT NOT NULL,
  learning_type TEXT NOT NULL, -- 'task_difficulty', 'model_behavior', etc.
  task_difficulty TEXT, -- 'easy', 'moderate', 'hard'
  task_type TEXT,
  task_summary TEXT,
  quality_score FLOAT,
  outcome TEXT, -- 'success', 'failed', 'error'
  model_count INTEGER,
  polarization_index FLOAT,
  behavioral_agreement FLOAT,
  duration_ms INTEGER,
  cost_usd FLOAT,
  metadata JSONB,
  embedding vector(128), -- pgvector extension
  timestamp TIMESTAMP DEFAULT NOW()
);
```

### learning.strategy_performance

```sql
CREATE TABLE learning.strategy_performance (
  strategy TEXT PRIMARY KEY,
  successes INTEGER DEFAULT 0,
  failures INTEGER DEFAULT 0,
  alpha FLOAT DEFAULT 1.0,
  beta FLOAT DEFAULT 1.0,
  total_reward FLOAT DEFAULT 0.0,
  avg_reward FLOAT DEFAULT 0.0,
  last_updated TIMESTAMP DEFAULT NOW()
);
```

## Troubleshooting

### Error: "Session directory does not exist"

This is normal if workflows haven't been run yet. The migration script will exit cleanly with status 0.

### Error: "Failed to load migration state"

The migration state file is corrupted. The script will start fresh automatically.

### Error: "Migration failed: <database error>"

Check PostgreSQL connection:

```bash
psql -h /var/run/postgresql -U $USER -d learning -c "SELECT 1"
```

Ensure tables exist:

```bash
psql -h /var/run/postgresql -U $USER -d learning -c "\dt workflows.*"
```

### Sessions not being migrated

Check migration state:

```bash
cat ~/.claude/learning/migration-state.json | jq .
```

Use `--force` to re-migrate:

```bash
node migrate-workflow-history.js --force
```

## Performance

- **Embedding generation**: ~1ms per session (simple character frequency)
- **Database insert**: ~10ms per session (2 tables + strategy update)
- **Expected throughput**: ~100 sessions per second

For large migrations (>1000 sessions), consider batch processing:

```javascript
// TODO: Add batch insert support for large migrations
```

## Future Enhancements

1. **Proper embedding model**: Replace character frequency with Sentence-BERT or similar
2. **Batch inserts**: Improve performance for large migrations
3. **Incremental migration**: Watch session directory for new files
4. **Reaction signals**: Extract model behavior signals from multi-model phases
5. **Cost tracking**: Parse token usage from Claude API responses
6. **Polarization index**: Calculate disagreement from multi-model votes
7. **Graph relationships**: Build knowledge graph from session linkages

## See Also

- `postgres-adapter.js` - Database adapter with workflows learning methods
- `deep-research.mjs` - Example workflow that generates session files
- `workflow-storage-adapter.js` - Automatic storage on workflow completion
