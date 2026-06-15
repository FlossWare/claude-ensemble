# Collaboration Model

**Version**: 1.0
**Date**: 2026-06-13

Human-AI collaboration model for claude-global-skills. Defines the four actors, how decisions flow, and how the system improves over time.

---

## 1. Overview

This system is a human-AI collaboration where a single user (Scot) directs an AI analysis engine (Claude) that decomposes work through an orchestration layer and executes it across a distributed fleet of machines. Every meaningful decision passes through multi-AI consensus with 6+ models from 3 providers. The system learns from every execution and improves autonomously.

---

## 2. The Four Actors

```
+-----------+     direction      +----------+     decompose     +-------------+
|           |  ----------------> |          |  ---------------> |             |
|   User    |                    |  Claude  |                   | Orchestrator|
|  (Vision) |  <---------------- | (Analysis|  <--------------- |  (Routing)  |
|           |  suggestions/results|  Engine) |  task results     |             |
+-----------+                    +----------+                   +------+------+
                                                                       |
                                                              fan-out  |
                                                                       v
                                                          +------------+----------+
                                                          |    Fleet Workers      |
                                                          |  server-01  (16C/32G) |
                                                          |  server-02  (32C/64G) |
                                                          |  server-03  (16C/32G) |
                                                          |  aio-01     (controller)|
                                                          |  pi-02      (sentinel) |
                                                          +------------------------+
```

### User (Scot)

Vision holder and direction setter. Communicates with terse commands: `go`, numbered selections (`1`, `2`), `perfect`. Values quality over cost. Prefers code over documentation, minimal docs, aggressive learning. Every session preference is captured in `~/.claude/memory/` for persistence.

### Claude (Session AI)

Analysis engine and suggestion generator. Reads memory files and learnings at session start, applies multi-AI consensus to decisions, executes code, and adapts to user preferences. Operates in interactive mode (prompts before acting) or autonomous mode (auto-creates issues, PRs, fixes).

### Orchestrator

Coordination layer that makes structural decisions: how to decompose tasks, which workflows to invoke, what skill combinations apply. Implemented in workflow `.js` files using Claude Code's workflow API (`phase()`, `parallel()`, `agent()`, `log()`). The orchestrator selects models, distributes work, and synthesizes results.

Key file: `orchestrator.js` -- consults the learning database to select the best model(s) for a given task based on historical performance.

### Fleet Workers

Execution engines distributed across 5 machines connected via NFS-shared `/home/sfloess/Development`. Run independent Claude Code sessions via SSH. Each worker processes its assigned batch independently -- no inter-worker coordination needed.

| Machine | Role | Specs | Purpose |
|---------|------|-------|---------|
| aio-01 | Controller | 4C/7G | NFS server, Prometheus, Grafana, orchestration |
| server-01 | Worker | 16C/32G | Primary compute |
| server-02 | Worker | 32C/64G | High-memory (gets largest batches) |
| server-03 | Worker | 16C/32G | General compute |
| pi-02 | Sentinel | 4C/1G ARM | Health monitoring only (too small for compute) |

---

## 3. Decision Flow

```
  User Request
       |
       v
  Claude Analyzes
  (reads memory, context)
       |
       v
  Orchestrator Decomposes
  (task routing, skill selection)
       |
       v
  +----+----+----+----+----+----+
  |    |    |    |    |    |    |
  v    v    v    v    v    v    v
 Fable Opus Son. Haiku GPT  Gem.
  |    |    |    |    |    |    |
  +----+----+----+----+----+----+
       |
       v
  Arbiter Synthesizes
  (fallback: Fable->Opus->Sonnet)
       |
       v
  Result to User
```

A request moves through these stages:

1. **User provides direction.** Terse: `go`, a number, a one-liner. Claude does not need lengthy instructions.

2. **Claude analyzes.** Reads `~/.claude/memory/MEMORY.md` (index), relevant `feedback_*.md` and `project_*.md` files, and the learning database. Determines what skills and workflows apply.

3. **Orchestrator decomposes.** Selects the right skill (e.g., `/code-review`, `/ai-pdf-deep-research`), determines fleet vs local mode via `resolveFleetMode()`, and fans out work to workers.

4. **Workers execute in parallel.** Each of 6 models (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) independently analyzes the same input. For bulk processing, batches are distributed across fleet machines via SSH.

5. **Arbiter synthesizes.** One model (default: Fable, with fallback chain Fable -> Opus -> Sonnet -> Haiku -> GPT-4o -> Gemini) reviews all worker outputs, selects or merges the best, assigns a confidence score.

6. **Role swap validates.** The arbiter becomes a skeptical worker; former workers become voting arbiters. This prevents bias. If consensus fails, roles rotate and the cycle repeats (max 10 iterations).

7. **User reviews.** In interactive mode, the user sees findings and chooses next steps. In autonomous mode (`*-auto` skills), the system auto-creates issues/PRs based on confidence thresholds.

### Interactive vs Autonomous

Interactive (`/code-review`): Shows findings, asks "Create issues for ALL/HIGH_ONLY/CRITICAL_ONLY/NONE?"

Autonomous (`/code-review-auto`): Auto-creates issues for findings with consensus >= 70%. Used in CI/CD and nightly cron jobs.

---

## 4. Multi-AI Consensus Layer

The arbiter/worker pattern underpins all decisions. Configuration lives in `multi-ai-config.json`.

### Models and Providers

| Provider | Models | Role |
|----------|--------|------|
| Anthropic | Fable, Opus, Sonnet, Haiku | Primary workers + arbiters |
| OpenAI | GPT-4o | Cross-provider diversity |
| Google | Gemini | Cross-provider diversity |

Cross-provider diversity reduces error correlation from ~60-70% (same-provider) to ~35-50%, achieving ~94% blind spot coverage.

### Consensus Strategies

| Strategy | Models | When |
|----------|--------|------|
| Maximum Coverage (default) | All 6+ | All decisions. Quality over cost. |
| Quad Consensus | 4 models | Good coverage, lower cost |
| Triple Consensus | 3 models | Minimum meaningful consensus |
| Quantized | Local Ollama + cloud arbiter | Zero API cost, private code |
| Quintuple Verification | 5 progressive stages | Security audits, production releases |

### Critical Rules

- **Different arbiters for different phases.** Review arbiter != solve arbiter != verify arbiter. Same arbiter would favor its own findings.
- **Always `parallel()` for workers.** Workers must propose independently without seeing each other's work.
- **Graceful degradation.** Failed models return `null` and are filtered with `.filter(Boolean)`. Workflows continue with remaining models.
- **Max 10 iterations.** If consensus is not reached after 10 role-swap cycles, the best available result is used.

### Pattern in Code

```javascript
// Workers propose in parallel
const proposals = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose solution', { model, label: `${model} Proposal`, schema })
))

// Arbiter selects best
const decision = await agent('Select best proposal', {
  model: 'fable', schema: DECISION_SCHEMA
})

// Role swap validates
const consensus = await validateWithRoleSwap(decision, 'fable', WORKER_MODELS)
```

---

## 5. Learning Loop

```
  Execute Task
       |
       v
  Record Outcome ---------> SQLite DB
  (quality, cost,           (execution_log,
   model, latency)           model_tuning)
       |                         |
       v                         v
  Memory Files              Meta-Optimizer
  (~/.claude/memory/)       (bandit selection,
  (preferences,              parameter tuning)
   project context)              |
       |                         v
       +-----> Next Session <----+
               (improved routing,
                better models,
                learned preferences)
```

Three layers of learning:

### Layer 1: Memory Files

Markdown files in `~/.claude/memory/` persist user preferences, project context, and feedback across sessions. Claude reads these at session start. Examples:

- `feedback_always_multi_ai.md` -- Always use maximum-coverage consensus
- `arbiter-worker-pattern.md` -- How to implement the consensus pattern
- `user_role.md` -- User is Scot, Red Hat Search Engineering team
- `parallel-by-default.md` -- Use `parallel()` not `pipeline()` by default

Currently 148+ learning files indexed in `MEMORY.md`.

### Layer 2: Learning Database

SQLite database at `~/.claude/learning/db/learning.db`. Tables include:

- `execution_log` -- Every `agent()` call: model, task type, quality score, confidence, duration, cost
- `model_tuning` -- Optimal parameters per model/task combination
- `prompt_patterns` -- Which prompt structures produce best results

The `orchestrator.js` module queries this database to select the best model for a given task type based on historical success rate and quality scores.

### Layer 3: Autonomous Learning Engine

Research scrapers (`~/.claude/learning/research/`) pull from ArXiv, GitHub, Stack Overflow, and Hacker News. A meta-optimizer uses multi-armed bandit selection to route tasks to the historically best-performing model. Curriculum learning (`curriculum-learning.js`) identifies knowledge gaps and generates targeted learning plans.

See `AUTONOMOUS_AI_COLLABORATION.md` for the full vision. Currently implemented: research scrapers, bandit-based model selection, task embedding, active feedback loops, meta-optimization.

---

## 6. Compliance and Boundaries

### Fleet Compliance

Red Hat proprietary work is auto-blocked from fleet distribution. The compliance system uses `fs.realpathSync()` to prevent symlink bypasses.

```
Forbidden path: /home/sfloess/Development/redhat/
Effect: Fleet mode silently falls back to local processing
Why: Proprietary code must not leave controlled infrastructure
```

### Model Restrictions

Per-path model deny/allow lists in `~/.claude/fleet.json`:

- `/home/sfloess/Development/redhat/` -- Deny `gpt-*` (no OpenAI for Red Hat work)
- Wildcard patterns supported: `gpt-*`, `claude-*`, `ollama-*`, `gemini-*`
- Most specific path wins (longest prefix match)

Implementation: `shared/model-compliance.js` exports `isModelAllowed()`, `filterAllowedModels()`, `getCompliantWorkers()`, `getCompliantArbiter()`.

### Autonomous Learning Boundaries

Topic restrictions prevent the curiosity engine from wandering into irrelevant domains. Human review gates exist for novel techniques before they are deployed to production workflows.

---

## 7. Communication Protocol

### User Commands

The user communicates tersely. Claude adapts:

| User Says | Meaning |
|-----------|---------|
| `go` | Proceed with the suggested approach |
| `1`, `2`, `3` | Select numbered option |
| `perfect` | Approve and continue |
| `yeah` / `smart catch` | Affirm and proceed |
| `fix them now` | Act immediately, no further discussion |

### Claude Adapts

- Minimal docs: no bloat, no separate status/summary/roadmap files
- Code-first: code + inline comments > separate documentation
- Aggressive learning: save preferences without being asked
- No version management: never create git tags (user handles versioning)
- X.Y versioning: not X.Y.Z

### Orchestrator Communication

Workflows use `log()` for real-time status. Labels on `agent()` calls show in the `/workflows` progress UI:

```javascript
log(`6 workers proposing fixes in parallel...`)
const fixes = await parallel(WORKER_MODELS.map(model =>
  () => agent('Propose fix', { label: `${model} Fix`, model, schema })
))
log(`Received ${fixes.filter(Boolean).length} proposals`)
```

### Fleet Communication

Workers are launched via SSH and process batches independently. Results collected via SSH `cat` commands. Progress tracked via NFS-visible files or SSH polling. No inter-worker coordination.

---

## 8. Quick Reference

| Actor | Role | Communicates Via | Key Constraint |
|-------|------|-----------------|----------------|
| User | Vision, direction, approval | Terse commands | Quality over cost, minimal docs |
| Claude | Analysis, suggestions, execution | Memory files, structured output | Multi-AI consensus for all decisions |
| Orchestrator | Task decomposition, routing | Workflow API (`phase`, `parallel`, `agent`) | Different arbiters per phase |
| Fleet Workers | Parallel execution | SSH, NFS | No Red Hat code on fleet, no inter-worker coordination |

### Key File Paths

| Path | Purpose |
|------|---------|
| `~/.claude/memory/MEMORY.md` | Memory index (read at session start) |
| `~/.claude/learning/db/learning.db` | Execution history and model performance |
| `~/.claude/fleet.json` | Fleet machine definitions and compliance rules |
| `multi-ai-config.json` | Consensus strategy configuration |
| `orchestrator.js` | Model selection based on learning database |
| `shared/fleet-utils.js` | Fleet discovery, health checks, mode resolution |
| `shared/model-compliance.js` | Path-based model restriction enforcement |

### Invocation Patterns

```bash
# Interactive skill
/code-review

# Autonomous skill (CI/CD)
claude run code-review-auto

# Full SDLC pipeline
claude run code-sdlc +500k

# Continuous loop until clean
sdlc-loop.sh 5 500k

# Multi-AI consensus on any question
/ai-prompt "What is the best approach to X?"
```

For architecture details, see `README.md`. For fleet topology, see `~/.claude/fleet.json`. For consensus configuration, see `multi-ai-config.json`.
