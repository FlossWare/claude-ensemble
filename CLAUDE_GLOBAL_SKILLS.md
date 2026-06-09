# Claude Global Skills - Testing Ground for FlossWare AI

**Repository:** https://gitlab.cee.redhat.com/sfloess/claude-global-skills  
**Purpose:** Prototype AI concepts → Proven ideas flow to FlossWare AI production libraries

---

## What is This?

`.claude` is the **testing ground** for FlossWare AI concepts:

1. **Prototype HERE** (in claude-global-skills git repo)
2. **Test it** with real workflows and memory
3. **If it works well** → migrate to FlossWare AI production libraries

**NOT integration** - we borrow concepts, implement/test here, then concepts flow back.

---

## Concepts Proven Here

### ✅ Multi-AI Consensus (consensus-ai concepts)
- **Attribution tracking** (`shared/attribution.js`)
  - Which AI said what
  - Consensus vs unique findings
  - Markdown reports
  - **Issue:** FlossWare/consensus-ai#11

- **Model performance tracking** (`shared/model-performance.js`)
  - Track which models excel at which tasks
  - Smart model assignment
  - Continuous learning
  - **Issue:** FlossWare/consensus-ai#12

- **Arbiter rotation** (`shared/workflow-helpers.js`)
  - Different arbiters for different phases
  - Prevents bias
  - Role-swap validation
  - **Issue:** FlossWare/consensus-ai#13

### ✅ RAG + Knowledge (knowledge-ai concepts)
- **RAG with citations** (`shared/rag.py`)
  - Query → retrieve → generate with sources
  - Hybrid search (semantic + keyword)
  - Reranking for precision
  - Cross-session learning
  - **Issue:** FlossWare/knowledge-ai#2

- **Knowledge ingestion** (`workflows/knowledge-ingest.js`)
  - Universal doc format detection
  - Multi-AI fact extraction
  - Semantic chunking

### ✅ Semantic Search (semantic-search-ai concepts)
- **Hybrid search** (`shared/semantic-search.py`)
  - RRF algorithm (semantic + keyword)
  - Reranking (bi-encoder → cross-encoder)
  - MongoDB-style filtering
  - Already matches production API!

### ✅ Visual Indicators (skills-ai concepts)
- **Colored consensus output** (`shared/visual-indicators.sh`)
  - Model-specific colors
  - Progress indicators
  - Consensus quality visualization
  - **Demo:** `skills/demo-consensus.sh`
  - **Issue:** FlossWare/skills-ai#1

### ✅ Vector Storage (vectordb-ai concepts)
- **ChromaDB prototype** (`shared/vector-store.py`)
  - Local vector storage
  - Semantic embeddings
  - Metadata filtering

---

## Directory Structure

```
claude-global-skills/
├── skills/              # Executable skills (symlinked to ~/.claude/skills)
│   ├── ai-learn.*      # Extract learnings to global memory
│   ├── ai-prompt.*     # Multi-model consensus prompts
│   ├── code-*.*        # Code review, solve, improve
│   └── demo-consensus.sh  # Visual indicators demo
│
├── workflows/           # Multi-AI workflows
│   ├── extract-learning.js        # Learn from sessions/skills/workflows
│   ├── extract-session-learnings.js  # Learn from transcripts
│   ├── knowledge-ingest.js        # Universal doc ingestion
│   ├── code-review-and-solve.js   # Review + solve with arbiter rotation
│   └── TEMPLATE-arbiter-worker.js # Best practices template
│
├── shared/              # Reusable components (for symlinking)
│   ├── attribution.js              # Which AI said what
│   ├── model-performance.js        # Performance tracking
│   ├── smart-consensus.js          # Performance-aware consensus
│   ├── workflow-helpers.js         # Arbiter patterns, schemas
│   ├── rag.py                      # RAG with citations
│   ├── semantic-search.py          # Hybrid search, reranking
│   ├── vector-store.py             # ChromaDB storage
│   ├── visual-indicators.sh        # Colored consensus output
│   └── skill-helpers.sh            # Common utilities
│
├── memory/              # Global memory (version controlled)
│   ├── MEMORY.md                   # Index of memories
│   ├── README.md                   # Memory system docs
│   ├── feedback_*.md               # User corrections/confirmations
│   ├── project_*.md                # Project context
│   └── (learnings from sessions)
│
├── docs/                # Documentation
└── learnings/           # Case studies and lessons
```

---

## Global Memory System

**Location:** `memory/` (in git)

**Purpose:** Cross-session learning for all Claude sessions, arbiters, and workers

**Memory Types:**
- **Feedback** - User corrections and confirmations
- **User** - Role, preferences, knowledge
- **Project** - Ongoing work, constraints
- **Reference** - External system pointers
- **Technical** - Code patterns, decisions

**Access:**
```bash
# Symlink to session
ln -s ~/path/to/claude-global-skills/memory ~/.claude/projects/<project>/memory

# Or query via RAG
from shared.rag import RAG
rag = RAG(collection='claude-memory')
result = rag.query('How does consensus work?')
```

---

## Learning Extraction

**Extract learnings from everything:**

```bash
# Run learning extraction (multi-AI consensus)
claude workflow run extract-learning

# What it extracts:
# - Session transcripts (user corrections, confirmations, preferences)
# - Skills (patterns, best practices)
# - Workflows (orchestration strategies)
# - Multi-AI consensus decisions
```

**Stores in:** `memory/` (git tracked, cross-session accessible)

---

## Multi-AI Consensus

**All workflows use multi-AI by default:**

- **Workers:** 3+ different models (Opus, Sonnet, GPT-4o, Gemini)
- **Arbiter:** Different model for synthesis
- **Rotation:** Different arbiters per phase
- **Attribution:** Track which AI said what
- **Performance:** Learn which models excel at what

**Example workflow structure:**
```javascript
// Phase 1: Workers analyze
const results = await parallel([
  () => agent(prompt, { model: 'opus' }),
  () => agent(prompt, { model: 'sonnet' }),
  () => agent(prompt, { model: 'gpt-4o' })
])

// Phase 2: Arbiter synthesizes
const consensus = await agent(synthesizePrompt, { model: 'opus' })
```

---

## Migration Path

**Concepts proven here → FlossWare AI production:**

1. **Test in .claude** - Prototype with real workflows
2. **Validate with multi-AI** - Consensus ensures quality
3. **Document results** - What works, what doesn't
4. **Open issue** - Link to working code in GitLab
5. **Port to production** - Clean implementation in FlossWare AI

**All issues reference working code:**
- Full implementations available
- Demos and examples included
- Benefits documented
- No guesswork - just port the proven code

---

## Symlinking

**Share components across projects:**

```bash
# Skills
ln -s ~/path/to/claude-global-skills/skills ~/.claude/skills

# Workflows  
ln -s ~/path/to/claude-global-skills/workflows ~/.claude/workflows

# Shared components
ln -s ~/path/to/claude-global-skills/shared ~/my-project/shared

# Memory
ln -s ~/path/to/claude-global-skills/memory ~/.claude/projects/<project>/memory
```

---

## Related

- **FlossWare AI Projects:** https://github.com/FlossWare/
  - consensus-ai - Multi-AI orchestration
  - knowledge-ai - Universal knowledge ingestion
  - semantic-search-ai - Advanced search
  - vectordb-ai - Vector database adapter
  - skills-ai - Executable workflows
  
- **Migration Issues:**
  - consensus-ai: #11 (attribution), #12 (performance), #13 (rotation)
  - knowledge-ai: #2 (RAG)
  - skills-ai: #1 (visual indicators)

---

## Status

**Current:**
- ✅ 14 workflows
- ✅ 10 skills
- ✅ 12 shared components
- ✅ Global memory system
- ✅ Multi-AI consensus everywhere
- ✅ Performance tracking
- ✅ Attribution tracking
- ✅ RAG with citations

**Next:**
- Port proven concepts to FlossWare AI
- Expand learning extraction
- Add more performance metrics
- Test backend switching (vectordb-ai)
