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
  - **Fixed issues #100-102**: Subagent isolation, embeddings package checks, graceful degradation
  - Production-ready for memory-rag-index and ai-web-learn-production workflows

### ✅ PDF Deep Research (skills-ai concepts)
- **Adversarial verification** (`workflows/ai-pdf-deep-research.js`, 710 lines)
  - 6-model consensus extraction (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)
  - 3-vote refutation protocol (2/3 refutations kill a claim)
  - Challenger exclusion (models that proposed a claim cannot vote on it)
  - Arbiter rotation per phase (Fable for extraction, Opus for verification, Sonnet for synthesis)
  - Smart chunking (20-page PDF segments for thorough reading)
  - Importance ranking before verification (central > supporting > tangential)
  - Memory persistence with YAML frontmatter (compatible with memory-rag-index)
  - Graceful degradation (unreadable PDFs, failed chunks, insufficient workers handled without aborting)
  - **Skill documentation**: `skills/ai-pdf-deep-research.md` (505 lines)
  - **Issue**: FlossWare/skills-ai#TBD (pending migration to production)

---

## Directory Structure

```
claude-global-skills/
├── skills/              # Executable skills (symlinked to ~/.claude/skills)
│   ├── ai-learn.*      # Extract learnings to global memory
│   ├── ai-pdf-deep-research.*  # Adversarial PDF verification skill (505 lines doc)
│   ├── ai-prompt.*     # Multi-model consensus prompts
│   ├── code-*.*        # Code review, solve, improve
│   └── demo-consensus.sh  # Visual indicators demo
│
├── workflows/           # Multi-AI workflows
│   ├── ai-pdf-deep-research.js    # Adversarial PDF verification (6-model consensus)
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

- **Workers:** 6 different models (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) for maximum coverage
- **Arbiter:** Different model for synthesis (6-model fallback chain)
- **Rotation:** Different arbiters per phase
- **Attribution:** Track which AI said what
- **Performance:** Learn which models excel at what
- **Cross-provider diversity:** 3 providers (Anthropic, OpenAI, Google) for ~94% blind spot coverage

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
- ✅ 18 workflows (added ai-pdf-deep-research, refactor-*, fix-quantized-strategy, build-pdf-research-workflow)
- ✅ 13 skills (added ai-pdf-deep-research skill - 505 lines doc + 710 lines workflow)
- ✅ 25 shared components (consensus-engine, quality-scorer, work-coordinator, chunking-utils, clustering-utils, platform-detector, model-discovery, impact-analysis, learning-system, and more)
- ✅ Global memory system
- ✅ Multi-AI consensus everywhere (6-model maximum coverage: Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)
- ✅ Performance tracking
- ✅ Attribution tracking
- ✅ RAG with citations
- ✅ ChromaDB production fixes (issues #100-102 - subagent isolation, embeddings package checks)

**Next:**
- Port proven concepts to FlossWare AI
- Expand learning extraction
- Add more performance metrics
- Test backend switching (vectordb-ai)
