# Learning Infrastructure

AI model selection, performance tracking, and continuous learning for the Claude Global Skills harness.

## 🚀 Quick Start: Auto-Discovery System

**Self-improving AI that learns optimization patterns from execution history.**

```bash
# 1. Bootstrap Thompson Sampling
node learning/validate-thompson-sampling.js --bootstrap

# 2. Generate initial discoveries
node learning/discover-patterns.js --apply

# 3. Start auto-discovery daemon (runs every 6 hours)
node learning/discovery-scheduler.js --daemon

# 4. Monitor progress
node learning/update-discovery-metadata.js --stats
```

**See:** [AUTO_DISCOVERY_QUICKSTART.md](AUTO_DISCOVERY_QUICKSTART.md) for details.

---

## Components

### 1. Database (`db.js`)

SQLite database with execution logging, model performance tracking, and quality ratings.

**Schema:**
- `execution_log` - All executions with model, quality, cost, duration
- `model_performance` - Aggregated metrics per model/task/time-window
- `parameter_tuning` - Optimal parameters per model/task
- `quality_ratings` - Human and automated quality ratings

**Usage:**
```javascript
import * as db from './learning/db.js';

db.logOrchestration({
  model: 'opus',
  workflow: 'code-review',
  quality_score: 0.92,
  cost_usd: 0.0045
});

const best = db.getBestModel('code-review', 'week');
```

### 2. Thompson Sampling (`thompson-sampling.js`)

Bayesian multi-armed bandit for exploration/exploitation balance in model selection.

**Features:**
- Beta distribution posteriors
- Automatic exploration of uncertain models
- Persistent state across sessions
- Production-ready (bootstrapped from 1,155+ executions)

**Usage:**
```javascript
import { selectModel, updateModel } from './learning/thompson-sampling.js';

const model = selectModel(['haiku', 'opus', 'sonnet']);
// Execute with model...
updateModel(model, qualityScore);
```

**State:** `~/.claude/learning/bandit-state.json`

### 3. Auto-Discovery System (NEW)

**Autonomous learning pipeline that discovers optimization patterns and applies them.**

**Components:**
- `discover-patterns.js` - Analyzes Thompson Sampling trends and execution logs to find patterns
- `update-discovery-metadata.js` - Tracks discovery usage and updates confidence scores
- `discovery-scheduler.js` - Runs discovery generation every 6 hours
- `apply-discoveries.js` - Applies discoveries during model selection

**Pattern Types:**
- Model preferences (e.g., "sonnet outperforms haiku by 15%")
- Model filters (e.g., "fable fails on JSON output")
- Task routing (e.g., "opus best for security reviews")
- Cost optimization (e.g., "haiku matches sonnet at 10% cost")

**Usage:**
```bash
# Generate patterns
node learning/discover-patterns.js --apply

# Start auto-discovery daemon
node learning/discovery-scheduler.js --daemon

# View statistics
node learning/update-discovery-metadata.js --stats
```

**State:** `~/.claude/learning/discoveries.json`

**Documentation:**
- [AUTO_DISCOVERY_QUICKSTART.md](AUTO_DISCOVERY_QUICKSTART.md) - Get started in 5 minutes
- [AUTO_DISCOVERY_SYSTEM.md](AUTO_DISCOVERY_SYSTEM.md) - Complete system documentation
- [AUTO_DISCOVERY_IMPLEMENTATION.md](AUTO_DISCOVERY_IMPLEMENTATION.md) - Implementation details

See [THOMPSON_SAMPLING.md](./THOMPSON_SAMPLING.md) for details.

### 3. Orchestrator (`../orchestrator.js`)

High-level model selection with multiple strategies.

**Strategies:**
- `greedy` (default): Highest historical performance
- `thompson`: Thompson Sampling for exploration/exploitation

**Usage:**
```javascript
import { selectModel, recordResult } from '../orchestrator.js';

// Thompson Sampling
const model = await selectModel('code-review', {
  strategy: 'thompson'
});

// Execute task...
recordResult(model, qualityScore);
```

## Quick Start

### Install

```bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
npm install  # Installs better-sqlite3
```

### Bootstrap Thompson Sampling

Already done! The bandit state was bootstrapped from 1,155 historical executions:

```bash
node learning/validate-thompson-sampling.js
```

### Use Thompson Sampling

```javascript
import { selectModel, recordResult } from './orchestrator.js';

async function executeWorkflow(taskType) {
  // Select model using Thompson Sampling
  const model = await selectModel(taskType, {
    strategy: 'thompson',
    models: ['haiku', 'opus', 'fable', 'sonnet']
  });

  // Execute your task
  const result = await yourExecutionFunction(model);

  // Record result for learning
  recordResult(model, result.qualityScore);

  return result;
}
```

## Files

```
learning/
├── db.js                           # Database helper (v2 schema)
├── thompson-sampling.js            # Thompson Sampling implementation
├── validate-thompson-sampling.js   # Validation script
├── THOMPSON_SAMPLING.md            # Thompson Sampling documentation
└── README.md                       # This file

~/.claude/learning/
├── db/
│   └── learning.db                 # SQLite database (1,159 executions)
├── bandit-state.json               # Thompson Sampling state
└── init-db.sql                     # Database schema
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Workflow                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   orchestrator.js                           │
│                                                             │
│  ┌──────────────┐              ┌──────────────┐           │
│  │   Greedy     │              │  Thompson    │           │
│  │  Strategy    │              │  Sampling    │           │
│  └──────┬───────┘              └──────┬───────┘           │
│         │                             │                    │
│         ▼                             ▼                    │
│  ┌──────────────┐              ┌──────────────┐           │
│  │     db.js    │              │ thompson-    │           │
│  │ (historical  │              │ sampling.js  │           │
│  │  metrics)    │              │ (Beta priors)│           │
│  └──────────────┘              └──────────────┘           │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │ learning.db   │
                │ bandit-state  │
                └───────────────┘
```

## Database Schema

### v2 Schema (Current)

```sql
-- execution_log: All executions with full orchestration context
CREATE TABLE execution_log (
    id INTEGER PRIMARY KEY,
    execution_id TEXT UNIQUE,
    model TEXT,
    model_role TEXT,              -- 'worker', 'arbiter'
    workflow TEXT,
    task_type TEXT,
    worker_models TEXT,           -- JSON array
    arbiter_model TEXT,
    strategy TEXT,                -- 'thompson', 'greedy', etc.
    quality_score REAL,
    confidence REAL,
    consensus_score REAL,
    cost_usd REAL,
    duration_ms INTEGER,
    -- ... (35+ columns total)
);

-- model_performance: Pre-computed metrics per model/task/window
CREATE TABLE model_performance (
    model TEXT,
    task_type TEXT,
    time_window TEXT,             -- 'day', 'week', 'month', 'all_time'
    avg_quality REAL,
    success_rate REAL,
    avg_cost_usd REAL,
    sample_count INTEGER,
    -- ... (30+ metrics)
);
```

## Current State

As of 2026-06-13:

### Database
- **1,159 executions** logged
- **6 models** tracked: haiku, opus, sonnet, fable, gpt-4o, gemini
- **Schema v2** (full orchestration support)

### Thompson Sampling
- **Bootstrapped** from 1,155 executions with quality scores
- **Models:**
  - haiku: 29.9% success rate (1,001 execs)
  - opus: 31.7% success rate (101 execs)
  - fable: 66.7% success rate (1 exec, high uncertainty)
  - sonnet: 75.0% success rate (2 execs, high uncertainty)

## Validation

Run the validation suite:

```bash
node learning/validate-thompson-sampling.js
```

**Output:**
- ✓ Thompson Sampling module loaded
- ✓ State bootstrapped from database (1,155+ executions)
- ✓ Model selection working (explores uncertain models)
- ✓ Result recording updates Beta posteriors
- ✓ Integration with orchestrator.js complete
- ✓ Greedy vs Thompson comparison shows exploration behavior

## Production Ready

All components are production-ready:

- **Zero human approval**: Fully autonomous
- **Persistent state**: Survives restarts
- **Multi-process safe**: File-based state with caching
- **Graceful degradation**: Falls back to defaults on errors
- **Battle-tested**: Bootstrapped from real execution history

## Future Enhancements

Potential improvements:

1. **Contextual bandits**: Use task features (time, complexity, etc.)
2. **Cost-aware selection**: Factor in model cost, not just quality
3. **Hierarchical learning**: Share information across related tasks
4. **Decay old observations**: Weight recent executions higher
5. **Ensemble selection**: Combine Thompson + greedy strategies
6. **A/B testing framework**: Systematic comparison of strategies

## References

- **Thompson Sampling**: Chapelle & Li (2011), "An Empirical Evaluation of Thompson Sampling"
- **Multi-Armed Bandits**: Lattimore & Szepesvári (2020), "Bandit Algorithms"
- **Beta-Bernoulli Model**: Classic conjugate prior for binary rewards
