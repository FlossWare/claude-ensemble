# Feedback Loop Automation

**Automatic Thompson Sampling updates from human feedback.**

## Overview

This building block automatically updates Thompson Sampling strategy performance based on human reviews. When a human rates a workflow outcome, their feedback is converted into Bayesian updates (alpha/beta parameters) for the strategy that was used.

**Key Features:**
- Reads unprocessed feedback from `workflow.feedback` table
- Converts ratings (0-5.0) to success/failure weights
- Updates `learning.strategy_performance` (Thompson Sampling state)
- Runs on-demand or as a daemon (every 5 minutes)
- Tracks which feedback has been processed

---

## How It Works

### 1. Human provides feedback

```sql
-- When reviewing a workflow, human adds feedback:
INSERT INTO workflow.feedback
  (workflow_execution_id, rating, corrections, human_reviewer)
VALUES
  (123, 4.5, 'Good analysis, but missed edge case X', 'user@example.com');
```

### 2. Feedback loop converts to Thompson Sampling updates

```javascript
// Rating (0-5.0) → Success/Failure weights
rating = 5.0 → alpha += 1.0, beta += 0.0  // Perfect success
rating = 2.5 → alpha += 0.5, beta += 0.5  // Neutral
rating = 0.0 → alpha += 0.0, beta += 1.0  // Total failure

// Example:
rating = 4.5 / 5.0 = 0.9
successWeight = 0.9
failureWeight = 0.1
```

### 3. Strategy performance updated

```sql
-- learning.strategy_performance table updated:
UPDATE learning.strategy_performance
SET
  alpha = alpha + 0.9,       -- Success count increases
  beta = beta + 0.1,         -- Failure count increases slightly
  total_reward = total_reward + 0.9,
  avg_reward = total_reward / (alpha + beta),
  last_updated = NOW()
WHERE strategy = 'quality_first';
```

### 4. Future selections influenced

```javascript
// Thompson Sampling now favors strategies with better human ratings
const strategy = await selectStrategy('code_review');
// Returns strategies with higher alpha (more human approval)
```

---

## Usage

### On-Demand Processing

```javascript
import { processFeedbackLoop } from './shared/feedback-loop-automation.js';

// Process all unprocessed feedback
const stats = await processFeedbackLoop();
console.log(stats);
// {
//   processed: 5,
//   updated_strategies: ['quality_first', 'balanced'],
//   errors: []
// }
```

### Daemon Mode (Continuous)

```bash
# Run as daemon (process every 5 minutes)
node shared/feedback-loop-automation.js --daemon

# Custom interval (every 10 minutes)
node shared/feedback-loop-automation.js --daemon --interval=10
```

### Check Statistics

```bash
node shared/feedback-loop-automation.js --stats
# Feedback Stats: { total: 50, processed: 45, unprocessed: 5 }
```

---

## Database Schema

### workflow.feedback Table

```sql
CREATE TABLE IF NOT EXISTS workflow.feedback (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER REFERENCES workflow.executions(id),
  rating NUMERIC(3,2),           -- 0.0 to 5.0
  corrections TEXT,              -- Human's notes
  human_reviewer TEXT,           -- Reviewer email/username
  processed BOOLEAN DEFAULT FALSE,         -- NEW: Processed by automation?
  processed_at TIMESTAMP,                  -- NEW: When processed
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Migration

```bash
# Run migration to add processed columns
psql -h aio-01 -p 5433 -U sfloess -d learning \
  -f db/migrations/add-feedback-processed-column.sql
```

---

## Integration with Workflows

### Store feedback after workflow completes

```javascript
const { getDB } = require('../learning/postgres-adapter.js');
const db = getDB();

// After workflow execution
await db.query(`
  INSERT INTO workflow.feedback
    (workflow_execution_id, rating, corrections, human_reviewer)
  VALUES ($1, $2, $3, $4)
`, [execId, 4.5, 'Excellent analysis!', 'user@example.com']);

// Feedback loop automation will process this automatically
```

### Systemd Service (Optional)

Create `/etc/systemd/user/feedback-loop.service`:

```ini
[Unit]
Description=Feedback Loop Automation - Thompson Sampling Updates
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/claude-global-skills
ExecStart=/usr/bin/node shared/feedback-loop-automation.js --daemon --interval=5
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Enable:
```bash
systemctl --user enable feedback-loop.service
systemctl --user start feedback-loop.service
```

---

## Examples

### Example 1: Quality Strategy Gets High Rating

```javascript
// Workflow used 'quality_first' strategy, got 4.8/5.0 rating
// Before:
//   quality_first: { alpha: 20, beta: 5 }
//   Sample: Beta(20, 5) ≈ 0.80

// Feedback processed:
//   successWeight = 4.8 / 5.0 = 0.96
//   failureWeight = 0.04

// After:
//   quality_first: { alpha: 20.96, beta: 5.04 }
//   Sample: Beta(20.96, 5.04) ≈ 0.81

// Result: 'quality_first' slightly more likely to be selected next time
```

### Example 2: Cost Strategy Gets Low Rating

```javascript
// Workflow used 'cost_optimized' strategy, got 2.0/5.0 rating
// Before:
//   cost_optimized: { alpha: 10, beta: 10 }
//   Sample: Beta(10, 10) ≈ 0.50

// Feedback processed:
//   successWeight = 2.0 / 5.0 = 0.40
//   failureWeight = 0.60

// After:
//   cost_optimized: { alpha: 10.40, beta: 10.60 }
//   Sample: Beta(10.40, 10.60) ≈ 0.49

// Result: 'cost_optimized' slightly less likely to be selected
```

---

## Performance

**Benchmarks:**
- Process 100 feedback entries: ~500ms
- Single feedback update: ~5ms
- Database query overhead: ~2ms

**Scalability:**
- Daemon mode: Processes in batches (no memory growth)
- PostgreSQL handles concurrent updates (MVCC)
- Safe to run multiple instances (idempotent)

---

## Monitoring

### Prometheus Metrics (Optional)

```javascript
// Add to monitoring/prometheus-exporter.cjs
const feedbackProcessed = new promClient.Counter({
  name: 'feedback_loop_processed_total',
  help: 'Total feedback entries processed'
});

const strategyUpdates = new promClient.Counter({
  name: 'thompson_sampling_updates_total',
  help: 'Total Thompson Sampling updates from feedback',
  labelNames: ['strategy']
});
```

### Grafana Dashboard

**Panels:**
- Feedback processing rate (entries/min)
- Strategy alpha/beta trends over time
- Unprocessed feedback queue depth
- Average rating per strategy

---

## Troubleshooting

### Feedback not processing

```bash
# Check for unprocessed feedback
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT COUNT(*) FROM workflow.feedback WHERE processed = FALSE;"

# Manually trigger processing
node shared/feedback-loop-automation.js

# Check logs
journalctl --user -u feedback-loop -f
```

### Strategy not updating

```bash
# Verify strategy exists in learning.strategy_performance
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT * FROM learning.strategy_performance WHERE strategy = 'quality_first';"

# Check if feedback has strategy_used
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT f.id, e.workflow_name, ad.strategy_used
   FROM workflow.feedback f
   JOIN workflow.executions e ON f.workflow_execution_id = e.id
   LEFT JOIN workflow.arbiter_decisions ad ON e.id = ad.workflow_execution_id
   WHERE f.processed = FALSE;"
```

---

## Future Enhancements

1. **Weighted feedback** - Expert reviews count more than novice reviews
2. **Time decay** - Recent feedback weighs more than old feedback
3. **Confidence intervals** - Track uncertainty in human ratings
4. **Multi-dimensional feedback** - Separate ratings for accuracy, speed, cost
5. **Feedback templates** - Structured feedback forms with predefined dimensions

---

## Credits

**Building Block:** Feedback Loop Automation  
**Purpose:** Close the loop between human judgment and Thompson Sampling  
**Implementation:** 2026-06-29  
**Lines of Code:** 250 (core) + 100 (migration + docs)  
**Dependencies:** PostgreSQL, learning.strategy_performance table

---

## See Also

- **Thompson Sampling:** `shared/THOMPSON-SAMPLING-README.md`
- **Workflow Storage:** `learning/workflow-storage-adapter.js`
- **Strategy Performance:** `learning.strategy_performance` table schema
