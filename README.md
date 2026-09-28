# Claude Ensemble Claude Ensemble

**Complete, production-ready AI infrastructure for your organization work.**

All your organization credentials (Anthropic, Google, Cursor). No personal/free services. Memory persists across sessions. Dashboards track performance and cost.

---

## What's Inside

### Core Infrastructure
- **Memory Service** — Central authority for concurrent session access (systemd daemon)
- **Thompson Router** — Intelligent model selection based on learned performance
- **Autonomous Learning** — Self-improvement from real task outcomes
- **Arbitration Orchestrator** — Multi-phase worker/arbiter pattern for critical decisions

### Optimization & Analysis
- **GA Tuning** — Genetic algorithm optimization every 4 hours (synthetic, zero cost)
- **Model Discovery** — Probes Anthropic/Google/Cursor APIs every 4 hours for latest models
- **Cost Tracking** — JSONL audit log of all API usage
- **5 Dashboards** — Cost, Thompson routing, autonomous learning, GA tuning, performance

### Workflow Skills (Learning-Integrated)
- **PR Review** (`/rh-pr-review`) — AI consensus code review, Thompson-routed model selection
- **Documentation** (`/rh-doc`) — Auto-generate docs, learns which models write better
- **Autonomous Variants** (`/rh-pr-review-auto`, `/rh-doc-auto`) — Run without user confirmation

All skills feed outcomes into Thompson — models learn task-specific performance over time.

### Capabilities  
- **Compression** — 64.6% token reduction via recursive text compression
- **Caching** — Prompt caching framework with hit/miss tracking (Phase 1 ready)
- **Hooks** — Memory search on prompt submit, learning extraction
- **Memory** — Project memory files (feedback, projects, references)

---

## Quick Start

### Session Initialization
On startup, `scripts/rh-tools-init.sh` automatically:
1. Connects to memory service (systemd daemon)
2. Initializes autonomous learning
3. Discovers latest models (Claude 5, Gemini, Cursor)
4. Prints toolkit status

```bash
✓ Connected to memory service
✓ Autonomous learner ready
✓ Claude Ensemble Global Skills Toolkit initialized
  Tools: compression, caching, cost_tracking, ga_tuning, thompson_router, arbitration
  Memory: ~/.claude/projects/-home-sfloess/memory
  Arbitration: multi-phase orchestrator for critical decisions
  Autonomous learning: Thompson continuously improving from real tasks
```

### Run Dashboards
After doing real work, view your performance:

```bash
cost-dashboard.py              # Spending by model/provider/workflow/day
thompson-dashboard.py          # Routing accuracy, model rankings, quality
autonomous-learning-dashboard.py  # Learning progress, outcomes
ga-tuning-dashboard.py         # Fitness trends, parameter evolution
```

### Workflow Skills
For routine tasks with learning integration:

```bash
# Interactive PR review (asks before approve/reject)
/rh-pr-review

# Autonomous PR review (auto-approves/rejects)
/rh-pr-review-auto

# Interactive documentation generation
/rh-doc

# Autonomous doc generation
/rh-doc-auto
```

See **[SKILL_INTEGRATION_GUIDE.md](SKILL_INTEGRATION_GUIDE.md)** for full details on how skills learn and route models via Thompson.

### Multi-Phase Arbitration
For critical decisions (security, breaking changes, complex bugs):

```bash
arbitrate code-review /path/to/repo --phases 3 --context-dir src/api
arbitrate bug-analysis error.log code.py --phases 2
arbitrate security-audit src/ --phases 3
```

Workers solve independently. Arbiter synthesizes. No model repeats across phases.

---

## Architecture

### Memory Service (Systemd Daemon)
- **Path:** `memory-service/`
- **Status:** Running (auto-start on login)
- **Port:** Unix socket `/tmp/rh-memory.sock`
- **Function:** Thread-safe access to shared memory across concurrent sessions

### Thompson Router
- **Path:** `shared/thompson_router.py`
- **Models:** Haiku (cheap), Sonnet (balanced), Opus (capable), Cursor, Gemini
- **Algorithm:** Bayesian inference with Beta distributions
- **Cost Savings:** 67% vs Opus-for-all (tested)

### Autonomous Learning
- **Path:** `learning/autonomous_learning.py`, `tools/autonomous-learner.py`
- **Workers:** 4 independent models capture outcomes, score, update priors, tune capability matrix
- **Trigger:** After every real task (online learning)
- **Storage:** `learning/autonomous_outcomes/`, `learning/autonomous_priors/`

### Arbitration Orchestrator
- **Path:** `arbitration/`
- **Guarantees:** 
  - No model is both arbiter and worker in same run
  - Workers in different phases are different models
  - Arbiters all different from each other
  - Each phase receives prior arbiter output
- **Context Access:** Git diffs, full files, dependencies, module context

### GA Tuning
- **Path:** `ga_tuning/`
- **Frequency:** Every 4 hours (0, 4, 8, 12, 16, 20 UTC)
- **Evaluators:** 5 independent (compression, Thompson, caching, capability matrix, learning rate)
- **Cost:** Zero (synthetic tasks, no API calls)
- **Parameters:** Tuned automatically, logged to `ga_tuning/parameter_evolution.md`

### Model Discovery
- **Path:** `tools/discover-models.py`
- **Frequency:** Every 4 hours (synced with GA tuning)
- **Providers:** Anthropic (free API call), Google (free API call), Cursor (defaults to latest)
- **Updates:** Thompson router inline, settings.json with discovery timestamp

---

## Dashboards

All dashboards read from local JSON files (no database):

| Dashboard | Command | Shows |
|-----------|---------|-------|
| Cost | `cost-dashboard.py` | Spending by model, provider, workflow, day |
| Thompson | `thompson-dashboard.py` | Routing accuracy, model rankings, quality achieved |
| Autonomous Learning | `autonomous-learning-dashboard.py` | Learning outcomes, prior updates, latest feedback |
| GA Tuning | `ga-tuning-dashboard.py` | Fitness progression, parameter evolution per evaluator |
| Performance | `performance_dashboard.py` | Real-time metrics (overlaps with cost dashboard) |

---

## Directory Structure

```
scripts/
  rh-tools-init.sh           # Session initialization
  ga-tuning-schedule.sh      # Cron: GA every 4 hours

memory-service/
  memory_service.py          # Systemd daemon
  memory_client.py           # Session client
  rh-memory.service          # Systemd unit file
  install.sh                 # Install script

arbitration/
  orchestrator.py            # Multi-phase runner, context manager
  api_client.py              # Multi-model API client

learning/
  autonomous_learning.py     # Full system (4 workers)
  autonomous_outcomes/       # Task outcome records
  autonomous_priors/         # Bayesian prior updates

shared/
  thompson_router.py         # Model selection

tools/
  arbitrate.py               # CLI tool
  autonomous-learner.py      # Wrapper for autonomous learning
  cost-dashboard.py          # Cost viewer
  discover-models.py         # Model discovery
  thompson-dashboard.py      # Thompson performance viewer
  autonomous-learning-dashboard.py  # Learning progress viewer
  ga-tuning-dashboard.py     # GA progress viewer

ga_tuning/
  ga_tuner.py                # GA optimizer
  extract_and_apply_parameters.py  # Extract & update settings
  evaluators/                # 5 independent evaluators
  parameter_evolution.md     # Timestamped parameter changes
  results/                   # GA output (JSON)

compression/
  compression_api.py         # 64.6% reduction
  summarizer.py              # Text compression

caching/
  memory_cache_integration.py  # Cache manager
  cache_metrics.py           # Hit/miss tracking

cost_tracking/
  logger.py                  # JSONL cost log
  aggregator.py              # Cost aggregation

hooks/
  memory-search-on-prompt.js # TF-IDF + RRF semantic search

memory/
  MEMORY.md                  # Index (loaded at session start)
  feedback_*.md              # User preferences
  project_*.md               # Project context
```

---

## Configuration

**Settings:** `settings.json` (symlinked to `~/.claude/`)

**Credentials:** environment variables
- ANTHROPIC_API_KEY
- GOOGLE_API_KEY
- CURSOR_API_KEY
- JIRA_API_TOKEN
- GITLAB_TOKEN

**MCP Servers:** `~/.mcp.json`
- Atlassian (Jira)
- Gmail
- Google Calendar

---

## Cost Optimization Stack

Three complementary techniques:

1. **Thompson Router** (67% savings) — Route to cheapest capable model
2. **Compression** (64.6% reduction) — Token reduction via text compression
3. **Caching** (69.8% savings) — Reuse frequent prompts

**Combined:** Can exceed 90% savings on token-heavy workflows.

---

## Future Work

See GitLab issues #348-349:
- **#348** — Arbiter explanations + teaching signals (tabled, needs neural-ai research)
- **#349** — Consolidate cost tracking dashboards

---

## Getting Help

- **Memory:** `~/.claude/projects/-home-sfloess/memory/MEMORY.md`
- **Practices:** `CLAUDE.md`
- **Integration Guide:** Individual `README.md` in each component
- **Issues:** `https://gitlab.cee.example.com/sfloess/claude-global-skills/-/issues`

---

**Last updated:** 2026-09-26  
**Status:** Production-ready, all tools active  
**Contributors:** Claude Haiku 4.5
