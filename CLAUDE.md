# Project Guide for Claude Code

**Project:** Distributed LLM Orchestration Framework  
**Repository:** `sfloess/claude-global-skills`  
**Architecture:** API-only (200+ models via OpenRouter, Anthropic, Google, Groq, etc.)  
**Fleet:** 9 nodes (8 workers + 1 controller/worker)  
**Last Updated:** 2026-07-14

---

## Quick Start

```bash
# Run a workflow
node workflows/example-workflow.mjs

# Run integration tests
npm test

# Check fleet health
./scripts/check-fleet-health.sh
```

---

## Project Structure

```
├── workflows/           # 171 multi-AI workflow scripts (.mjs/.js)
├── skills/              # 12 user-invocable skills + 75 JS modules
│   ├── ai/              # AI consensus, web learning, PDF research (27 files)
│   ├── code/            # Code review, security, SDLC, testing (20 files)
│   └── misc/            # Fleet dispatch, orchestration, RAG (50+ files)
├── shared/              # Common utilities and adapters
│   ├── postgres-adapter.js        # Database access (ALWAYS USE THIS)
│   ├── workflow-storage-adapter.js # Workflow tracking
│   └── feedback-loop-adapter.cjs  # Feedback loop monitoring
├── tools/               # CLI tools and GA evolution
│   ├── feedback_loop_optimizer.py # Feedback loop analysis
│   ├── genetic_model_optimizer.py # GA model routing evolution
│   ├── ga_rag_retrieval_optimizer.py # GA RAG parameter evolution
│   ├── ga_team_selection_fixed.py # GA team composition evolution
│   └── ga_training_data_curator.py # GA training data curation
├── scripts/             # Utility scripts
├── docs/                # Documentation
├── learning/            # ML data, GA engine, training scripts
│   └── ga_engine.py     # Core GA engine (crossover, mutation, selection)
└── api/                 # REST API (optional, separate service)
```

---

## Architecture

### API-Only Fleet (Since 2026-06-28)

**What this means:**
- ✅ Access to 200+ models via API calls
- ✅ No local model hosting costs
- ✅ Always latest model versions
- ❌ No local Ollama models
- ❌ No local model inference

**Model Providers:**
- **OpenRouter:** 150+ models (primary)
- **Anthropic:** Claude family (Opus, Sonnet, Haiku, Fable)
- **Google:** Gemini family
- **Groq:** Ultra-fast LPU inference
- **Cerebras, DeepSeek, others:** ~40+ additional models

### Fleet Configuration

**9 Nodes:**
- laptop-01 (Primary, 4C/8T, 31GB)
- aio-01 (Controller + worker, 2C, 7GB)
- server-01 (Worker, 8C, 15GB)
- server-02 (Worker, 8C, 31GB)
- server-03 (Worker, 8C, 31GB)
- desktop-ap (Worker, 1GB)
- server-ap (Worker, 1GB)
- pi-01 (Worker, low-power)
- pi-02 (Worker, 1GB, low-power)

**Execution:** Distributed across fleet via SSH

### Databases

| Database | Location | Purpose |
|----------|----------|---------|
| PostgreSQL | aio-01:5433 | Learning, workflows, monitoring, costs |
| OrientDB | aio-01:2424 | Knowledge graph, infrastructure relationships |
| Redis Sentinel | 3 nodes | Caching, rate limiting |

**Schemas:**
- `learning.*` - Model capabilities, strategy performance, experiences
- `workflow.*` - Workflow executions, worker results, arbiter decisions
- `monitoring.*` - Execution logs, costs, alerts, diversity alerts
- `costs.*` - Cost tracking

---

## Coding Standards

### JavaScript

- **ES Modules:** Always use `.mjs` extension
- **Async/Await:** Prefer over callbacks/promises chains
- **Error Handling:** Catch and log, don't fail silently
- **Imports:** Use ES6 imports (`import`/`export`)

```javascript
// Good
import { getWorkflowStorage } from './shared/workflow-storage-adapter.js';

const db = getWorkflowStorage();
const execId = await db.storeExecution({ ... });
```

### Python

- **Type Hints:** For public functions
- **Docstrings:** For modules and public functions
- **Error Handling:** Use try/except with specific exceptions

```python
from typing import Dict, List
from postgres_adapter import get_db

def analyze_feedback_loops(window_days: int = 7) -> Dict:
    """Analyze feedback loops over specified window."""
    db = get_db()
    # ...
```

### Database Access

**ALWAYS use adapters, NEVER raw connections:**

```javascript
// JavaScript
const { getDB } = require('./shared/postgres-adapter.js');
const db = getDB();
const rows = await db.query('SELECT * FROM learning.experiences');
```

```python
# Python
from postgres_adapter import get_db
db = get_db()
rows = db.query("SELECT * FROM learning.experiences")
```

### Workflow Storage

**ALWAYS track multi-AI workflows:**

```javascript
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.js');
const db = getWorkflowStorage();

const execId = await db.storeExecution({
  workflow_id: 'wf-' + Date.now(),
  workflow_name: 'my-workflow',
  task_description: 'Research topic',
  total_workers: 6
});

// ... execute workers ...

await db.storeWorkerResult({
  workflow_execution_id: execId,
  worker_id: 'worker-1',
  model: 'opus',
  result: 'Analysis complete'
});
```

---

## Common Patterns

### 1. Review-Fix Cycle with Meta-Review

The standard pattern for code review uses two independent model panels with **zero overlap**:

```javascript
// REVIEW PANEL: Find issues (strongest code-reasoning models)
const REVIEW_MODELS = [
  { name: 'opus',           type: 'claude' },
  { name: 'sonnet',         type: 'claude' },
  { name: 'deepseek-chat',  type: 'fleet', provider: 'deepseek' },
  { name: 'qwen/qwen3-coder:free', type: 'fleet', provider: 'openrouter' },
]

// META-REVIEW PANEL: Adversarially validate (ZERO overlap with review)
const META_REVIEW_MODELS = [
  { name: 'fable',          type: 'claude' },
  { name: 'nousresearch/hermes-3-llama-3.1-405b:free', type: 'fleet', provider: 'openrouter' },
  { name: 'nvidia/nemotron-3-ultra-550b-a55b:free',    type: 'fleet', provider: 'openrouter' },
  { name: 'qwen/qwen3-next-80b-a3b-instruct:free',    type: 'fleet', provider: 'openrouter' },
]

// Each phase uses a DIFFERENT arbiter
const REVIEW_ARBITER = 'opus'
const META_REVIEW_ARBITER = 'sonnet'
const SOLVE_ARBITER = 'fable'
const VERIFY_ARBITER = 'haiku'
```

Non-Claude models are called via OpenRouter API from within workflow agents. See `workflows/code-review-and-solve.js` for the full implementation.

### 2. Workflow Structure

```javascript
export const meta = {
  name: 'my-workflow',
  description: 'One-line description',
  phases: [
    { title: 'Research', detail: 'Gather information' },
    { title: 'Analyze', detail: 'Process findings' }
  ]
};

export default async function({ phase, parallel, agent, log }) {
  phase('Research');
  const findings = await parallel([...]);
  
  phase('Analyze');
  const analysis = await agent('Analyze findings', { schema: SCHEMA });
  
  return { findings, analysis };
}
```

### 3. Database Queries

```javascript
// Get strategy performance
const db = getDB();
const strategies = await db.query(`
  SELECT strategy, avg_reward, successes, failures
  FROM learning.strategy_performance
  ORDER BY avg_reward DESC
`);
```

### 4. Feedback Loop Monitoring

```javascript
const { isSystemHealthy } = require('./shared/feedback-loop-adapter.cjs');

// Pre-flight check
const healthy = await isSystemHealthy(7);
if (!healthy) {
  log('Warning: Feedback loop risks detected');
}
```

---

## Testing

### Integration Tests

```bash
npm test
```

### Workflow Execution

```bash
# Run specific workflow
node workflows/deep-research.mjs

# With arguments
node workflows/my-workflow.mjs --input "test data"
```

### Database Checks

```bash
# Check learning data
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT * FROM learning.strategy_performance;"

# Check workflow executions
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT COUNT(*) FROM workflow.executions;"
```

---

## Deployment

### Flask API (Optional)

```bash
# Deploy to aio-01
./scripts/deploy-api.sh

# Check status
systemctl status orchestrator-api
```

### Workflow Scripts

- Workflows run on-demand via node
- No deployment needed (just git pull)

---

## Important Files

### Configuration

- `~/.claude/FLEET.md` - Fleet hardware and network config
- `~/.claude/CLAUDE.md` - Personal Claude Code config (different from this file!)

### Adapters (ALWAYS USE THESE)

- `shared/postgres-adapter.js` - Database access
- `shared/workflow-storage-adapter.js` - Workflow tracking
- `shared/feedback-loop-adapter.cjs` - Feedback loop monitoring

### Documentation

- `README.md` - Full project documentation
- `docs/` - Detailed guides
- `docs/FEEDBACK_LOOP_OPTIMIZER.md` - Feedback loop system

---

## Anti-Patterns (DO NOT DO)

### ❌ Raw Database Connections

```javascript
// BAD
const { Pool } = require('pg');
const pool = new Pool({ ... });

// GOOD
const { getDB } = require('./shared/postgres-adapter.js');
const db = getDB();
```

### ❌ Skipping Workflow Storage

```javascript
// BAD - No tracking
const results = await parallel([...]);

// GOOD - Tracked
const db = getWorkflowStorage();
const execId = await db.storeExecution({ ... });
const results = await parallel([...]);
await db.storeWorkerResult({ workflow_execution_id: execId, ... });
```

### ❌ Hardcoded Model Names

```javascript
// BAD
const result = await agent('Task', { model: 'opus' });

// GOOD - Let routing decide
const result = await agent('Task'); // Auto-routed based on task type
```

### ❌ Same Models for Review and Meta-Review

```javascript
// BAD - Self-confirmation bias (same models reviewing their own findings)
const REVIEW = ['opus', 'sonnet', 'haiku']
const META_REVIEW = ['opus', 'sonnet', 'fable']  // opus+sonnet overlap!

// GOOD - Zero overlap between panels
const REVIEW = ['opus', 'sonnet', 'deepseek-chat', 'qwen3-coder']
const META_REVIEW = ['fable', 'hermes-405b', 'nemotron-ultra', 'qwen3-next']
```

### ❌ Using Weak Models for Meta-Review

```javascript
// BAD - haiku is too weak to adversarially challenge opus/sonnet findings
const META_REVIEW = ['haiku', 'haiku', 'haiku']

// GOOD - Meta-reviewers must be equally strong as reviewers
const META_REVIEW = ['fable', 'hermes-405b', 'nemotron-ultra-550b', 'qwen3-next-80b']
```

---

## Getting Help

1. **README.md** - Start here
2. **docs/** - Detailed guides
3. **GitLab Issues** - Report bugs, request features
4. **~/.claude/CLAUDE.md** - Personal Claude config (system-level)

---

## Key Differences: Project vs Personal CLAUDE.md

This file is in the **git repository** and contains **project-specific** guidance.

`~/.claude/CLAUDE.md` is **personal** and contains:
- System architecture
- Available components (46 ML/utility components)
- Continual learning configuration
- Feedback loop optimizer settings
- Personal preferences

**Don't confuse the two!**

---

**Last Updated:** 2026-07-14  
**Maintained by:** Development team  
**Questions?** Open a GitLab issue
