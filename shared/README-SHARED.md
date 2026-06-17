# Shared Components

Reusable components for workflows and skills - all in git for symlinking.

## JavaScript Components

### workflow-helpers.js
Reusable patterns for arbiter/worker workflows.

**What's inside:**
- Standard instructions (NO_BASH, STRUCTURED_OUTPUT, ARBITER_ROTATION, etc.)
- Common schemas (FINDING_SCHEMA, PROPOSAL_SCHEMA, DECISION_SCHEMA, VERDICT_SCHEMA)
- Helper functions (role swap validation, graceful fallback, progress logging, consensus scoring)

**Usage:** Copy inline into workflows (workflows using scriptPath can't use ES6 imports)

### Other JS Modules
- `consensus-engine.js` - Multi-AI consensus coordination
- `schemas.js` - Shared JSON schemas
- `chunking-utils.js`, `clustering-utils.js`, `quality-scorer.js`, `learning-system.js`

## Shell Components

### skill-helpers.sh
Common utilities for skills.

**Functions:** Path helpers, workflow execution, memory operations, git operations, interactive prompts

**Usage:**
```bash
source shared/skill-helpers.sh
run_workflow "extract-learning"
search_memory "multi-model"
```

### visual-indicators.sh
Visual feedback for multi-AI workflows.

**Functions:** Colored output, progress bars, consensus quality, model comparisons

**Demo:** `./skills/demo-consensus.sh`

## Python Components

### vector-store.py
ChromaDB vector storage (vectordb-ai concepts)

### semantic-search.py
Hybrid search, reranking, filtering (semantic-search-ai concepts)

## All in Git for Symlinking

```bash
ln -s ~/path/to/claude-global-skills/shared ~/my-project/shared
```

Concepts tested here flow back to FlossWare AI libraries.
