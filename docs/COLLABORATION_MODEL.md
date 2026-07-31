# Collaboration Model: Multi-AI Architecture in Claude Code Global Skills

**Version**: 2.6  
**Last Updated**: 2026-07-30  
**Scope**: End-to-end description of roles, collaboration patterns, consensus mechanisms, learning loops, and fleet orchestration

---

## Table of Contents

1. [Overview](#overview)
2. [The Four Roles](#the-four-roles)
3. [How Roles Collaborate](#how-roles-collaborate)
4. [Consensus Strategies](#consensus-strategies)
5. [When to Use What](#when-to-use-what)
6. [The Fleet: Multi-Model Diversity](#the-fleet-multi-model-diversity)
7. [Orchestration and Routing](#orchestration-and-routing)
8. [The Learning Pipeline](#the-learning-pipeline)
9. [Evolution: From Single-Agent to Self-Improving Fleet](#evolution-from-single-agent-to-self-improving-fleet)
10. [Architecture Diagram](#architecture-diagram)
11. [End-to-End Decision Flow](#end-to-end-decision-flow)
12. [Learning Loop Over Time](#learning-loop-over-time)
13. [Configuration and Cost Management](#configuration-and-cost-management)
14. [Constraints and Policies](#constraints-and-policies)
15. [Quick Reference](#quick-reference)

---

## Overview

The Claude Code Global Skills project implements a **multi-AI collaboration architecture** where multiple AI models work together under structured coordination to produce higher-quality outputs than any single model achieves alone. The architecture has four fundamental roles -- User, Claude Code (Main), Workers, and Arbiters -- that interact through an orchestration layer to form consensus, extract learnings, and continuously improve.

The core principle: **diverse perspectives produce better results**. By running the same task across different AI models (445+ models across 21 providers including OpenRouter, Anthropic, Google, Groq, Cerebras, DeepSeek, Pollinations, and others), the system cross-validates findings, catches blind spots, and filters noise through structured consensus.

---

## The Four Roles

### 1. User

The human operator who initiates requests and provides feedback.

**Responsibilities**:
- Defines tasks in natural language
- Provides project context, constraints, and preferences
- Reviews outputs and provides implicit/explicit feedback
- Sets policies via MEMORY.md (e.g., "always use multi-AI", "never create git tags")
- Configures cost/quality tradeoffs through multi-ai-config.json

**Interaction surface**: Claude Code CLI, slash commands (`/code-review`, `/deep-research`, `/ai-consensus`), direct prompts.

### 2. Claude Code (Main Agent)

The central intelligence that interprets intent, routes tasks, and manages the session.

**Responsibilities**:
- Parses user requirements and determines task type (coding, research, review, deployment)
- Checks memory and project context (MEMORY.md, learnings archive)
- Decides whether to execute directly or invoke a workflow
- Selects the appropriate skill or workflow for the task
- Manages context windows, file access, and tool invocation
- Returns results to the user

**Key decision point**: Task complexity assessment. Simple tasks (read a file, fix a typo) execute directly. Complex tasks (security audit, multi-file refactor, deep research) route to the orchestrator for multi-AI treatment.

### 3. Workers

Parallel AI agents that independently analyze the same task, each using a different model to provide diverse perspectives.

**Responsibilities**:
- Receive a structured prompt with task description, context, and output schema
- Produce independent solutions without seeing other workers' outputs
- Report confidence levels when using weighted consensus
- Return structured JSON matching the requested schema

**Key characteristic**: Workers run in parallel and do NOT communicate with each other. Their independence is essential -- it prevents groupthink and ensures genuine diversity of analysis.

**Typical worker set**: Selected from 445+ models across 21 API providers (Anthropic, OpenRouter, Google, Groq, Cerebras, DeepSeek, Pollinations, ZeroLimitAI, Eden AI, GitHub Models, Cohere, Cloudflare, Jina, DeepInfra, HuggingFace, Mistral, etc.). Common defaults include `[opus, sonnet, haiku, fable, deepseek-chat, qwen3-coder]` (configurable down to 2 for cost savings). Model registry is maintained in PostgreSQL `learning.free_models` and exposed via `/models/` REST endpoints.

### 4. Arbiters

Synthesis agents that review all worker outputs and produce a final, consolidated result.

**Responsibilities**:
- Receive all worker outputs as input
- Evaluate quality, correctness, and completeness of each worker's response
- Select the best response, synthesize a combined response, or orchestrate debate
- Provide confidence scores and reasoning for their selection
- Rotate across models to prevent arbiter bias (fable -> opus -> sonnet -> haiku -> gpt-4o -> gemini)

**Key characteristic**: Arbiters use a DIFFERENT model than the workers they judge. The arbiter rotation mechanism (`get-next-arbiter.js`) cycles through all available models, and state is persisted in `arbiter-state.json`.

**Fallback chain**: If the preferred arbiter is unavailable, the system falls back through the priority order: Fable -> Opus -> Sonnet.

---

## How Roles Collaborate

### The Standard Flow

Every multi-AI task follows this sequence:

1. **User** issues a request (natural language or slash command)
2. **Claude Code (Main)** analyzes intent, loads context from memory, selects a skill
3. **Orchestrator** (workflow-runner) spawns workers with the task prompt
4. **Workers** (3-6 models) execute in parallel, producing independent results
5. **Arbiter** receives all worker outputs, synthesizes a final answer
6. **Claude Code (Main)** returns the result to the user
7. **Learning pipeline** extracts insights and updates the knowledge base

### Phase-Based Collaboration

Workflows are organized into phases, and EVERY meaningful phase gets multi-AI treatment:

```
Phase 1: Gather    --> [Worker-Opus, Worker-Sonnet, Worker-Haiku] --> Arbiter
Phase 2: Analyze   --> [Worker-Opus, Worker-Sonnet, Worker-Haiku] --> Arbiter
Phase 3: Decide    --> [Worker-Opus, Worker-Sonnet, Worker-Haiku] --> Arbiter
Phase 4: Verify    --> [Worker-Opus, Worker-Sonnet, Worker-Haiku] --> Arbiter
```

The arbiter ROTATES between phases. The arbiter for Phase 1 must differ from the arbiter for Phase 2. This prevents a single model's biases from dominating the entire workflow.

### Worker-Arbiter Interaction Pattern

Workers and arbiters interact through structured schemas, not free-form text. A typical interaction:

```
Workers receive:
  - Task prompt with context
  - JSON schema defining expected output fields
  - Model-specific label (e.g., "opus-security-audit")

Workers return:
  - Structured JSON matching the schema
  - Model identifier
  - (Optionally) confidence score

Arbiter receives:
  - All worker outputs as a formatted list
  - Instructions to select best, synthesize, or debate
  - Schema for the final decision

Arbiter returns:
  - winning_worker (which worker's output was best)
  - why_selected (reasoning)
  - confidence (0-100)
  - result (final synthesized output)
```

---

## Consensus Strategies

The system implements five consensus strategies, each suited to different situations. The `consensus-strategies.js` module provides all five, plus an auto-selection function.

### Strategy 1: Rotating Arbiter (Democratic)

Each worker takes turns as arbiter, judging all other workers. Most thorough, catches the most issues.

**How it works**: All workers produce solutions, then each worker evaluates every OTHER worker's solution. Votes are tallied, and the solution with the most votes wins.

**When to use**: Critical tasks (security audits, production releases), when maximum confidence is needed.

**Cost**: Highest -- N workers producing solutions + N workers judging = 2N agent calls.

### Strategy 2: Single Arbiter (Fast)

One designated arbiter model judges all worker outputs.

**How it works**: Workers produce solutions in parallel, then a single arbiter (typically Opus or the next model in rotation) selects the best.

**When to use**: Standard workflow phases, code reviews, most everyday tasks.

**Cost**: Moderate -- N workers + 1 arbiter = N+1 agent calls.

### Strategy 3: Majority Vote (No Arbiter)

Workers vote directly, no arbiter overhead. The most common solution wins.

**How it works**: All workers produce solutions, solutions are grouped by equivalence, the group with the most members wins.

**When to use**: Tasks where solutions tend to converge (e.g., factual lookups, deterministic analysis), or when speed matters more than nuance.

**Cost**: Lowest -- N workers only, no arbiter call.

### Strategy 4: Pairwise Comparison (Tournament)

Solutions compete head-to-head in elimination rounds. A balanced approach between thoroughness and speed.

**How it works**: Workers produce solutions, then solutions are paired and a judge picks the winner. Winners advance until one remains.

**When to use**: Tasks with diverse expected solutions where direct comparison is more informative than aggregate voting.

**Cost**: Variable -- depends on number of rounds (log2 N comparisons).

### Strategy 5: Weighted Voting (Confidence-Aware)

Workers report confidence alongside their solutions. Solutions with higher total confidence weight win.

**How it works**: Workers produce solutions with explicit confidence scores (0.0-1.0). Solutions are grouped by equivalence, and the group with the highest total confidence weight wins.

**When to use**: Tasks where model uncertainty varies (some models are more confident than others on specific domains).

**Cost**: Same as majority vote -- N workers, no arbiter.

### Auto-Selection

The `autoSelectStrategy()` function picks the right strategy based on context:

| Context Flag | Selected Strategy |
|---|---|
| `critical: true` | Rotating Arbiter |
| `fast: true` | Majority Vote |
| `diverse: true` | Pairwise Comparison |
| Default | Rotating Arbiter (maximum quality) |

### Advanced Consensus Variants

Beyond the five core strategies, the system provides specialized consensus modules:

- **ai-consensus-debate.js** -- Adversarial debate: workers propose, exchange arguments, rebut, and an arbiter judges
- **ai-consensus-filtered.js** -- Only synthesizes from high-confidence worker results, discarding low-confidence noise
- **ai-consensus-hierarchical.js** -- Specialized sub-teams (e.g., security team + architecture team) with sub-arbiters feeding a meta-arbiter
- **ai-consensus-refinement.js** -- Iterative self-correction: arbiter critiques worker outputs, workers revise, cycle repeats until confidence threshold is met
- **ai-consensus-weighted.js** -- Extended weighted voting with confidence-weighted synthesis

---

## When to Use What

### Multi-AI (Workers + Arbiter) vs. Single Agent

| Situation | Approach | Reason |
|---|---|---|
| Security audit | Multi-AI (6 workers, rotating arbiter) | Critical -- missed vulnerabilities are costly |
| Code review | Multi-AI (3-4 workers, single arbiter) | Multiple perspectives catch different bug classes |
| Fix typo in README | Single agent (Haiku) | No benefit from consensus on trivial tasks |
| Deep research | Multi-AI + adversarial debate | Cross-validation of claims from multiple sources |
| Run a shell command | Single agent | Mechanical operation, no analysis needed |
| Production release validation | Multi-AI (6 workers, rotating arbiter) | Maximum confidence for irreversible actions |
| Test generation | Multi-AI (3 workers, single arbiter) | Different models test different edge cases |
| Reading a file | Direct execution | No AI reasoning needed |
| Architecture decision | Multi-AI hierarchical | Cross-domain expertise synthesis |

### Choosing a Consensus Strategy

| Requirement | Strategy |
|---|---|
| Maximum quality, cost not a concern | Rotating Arbiter |
| Standard production use | Single Arbiter |
| Speed-critical, solutions likely to agree | Majority Vote |
| Solutions will vary widely | Pairwise Tournament |
| Models have domain-specific confidence | Weighted Voting |
| Need adversarial stress-testing | Debate |
| Multi-domain task (security + architecture + testing) | Hierarchical |
| Must reach threshold confidence | Refinement (iterative) |

### Choosing a Skill

| Task Type | Primary Skill | Multi-AI Pattern |
|---|---|---|
| Bug fix / code problem | `/code-solve-auto` | Workers propose fixes, arbiter picks best |
| Test generation | `/code-test-auto` | Workers generate tests, arbiter merges coverage |
| PR review | `/code-pr-review-auto` | Workers review independently, arbiter synthesizes |
| Full SDLC pipeline | `/code-sdlc-auto-continuous` | Runs until codebase is clean |
| Fact-checked research | `/deep-research` | Fan-out searches, adversarial verification |
| Multi-perspective analysis | `/ai-consensus` | Direct consensus on any prompt |
| PDF document verification | `/ai-pdf-deep-research` | Extract claims, 3-vote refutation |
| Execution verification | `/verify` | Run app, observe behavior |
| Cost/performance monitoring | `/ai-cost-tracker`, `/ai-performance-monitor` | Track spending and model degradation |

---

## The Fleet: Multi-Model Diversity

### Available Models

The fleet has access to **445+ models across 21 API providers**. Model registry is stored in PostgreSQL `learning.free_models` and exposed via REST API at `aio-01:5000/models/`. Key providers and representative models:

| Provider | Example Models | Typical Role |
|---|---|---|
| **Anthropic** | Fable (4.5), Opus (3.7), Sonnet (4.5), Haiku (3.5) | Worker + Arbiter |
| **OpenRouter** | 150+ models (Qwen, Hermes, Nemotron, etc.) | Worker |
| **Google** | Gemini family | Worker |
| **Groq** | Ultra-fast LPU inference models | Worker (speed-critical) |
| **Cerebras** | Fast inference models | Worker |
| **DeepSeek** | DeepSeek-Chat, DeepSeek-Coder | Worker |
| **Pollinations** | No-auth models | Worker (free tier) |
| **ZeroLimitAI** | Free-tier models | Worker (free tier) |
| **Others** | Eden AI, GitHub Models, Cohere, Cloudflare, Jina, DeepInfra, HuggingFace, Mistral | Worker |

### Why Model Diversity Matters

Each model has different:
- **Training data** -- catches different patterns and references
- **Reasoning approach** -- some excel at formal logic, others at creative analysis
- **Blind spots** -- what one model misses, another often catches
- **Confidence calibration** -- some are overconfident, others conservative

The cross-validation between models is the core mechanism that makes multi-AI superior to single-model execution.

### Arbiter Rotation

To prevent arbiter bias, the system rotates the arbiter model using a persistent state file:

```
Rotation order: fable -> opus -> sonnet -> haiku -> gpt-4o -> gemini -> fable
State file: ~/.claude/repos/claude-global-skills/arbiter-state.json
```

The rotation is best-effort. Concurrent workflows may occasionally select the same arbiter, but the system self-corrects on the next invocation. Concurrency races are harmless by design.

### Distributed Fleet (Personal Infrastructure)

For compute-intensive tasks, work can be distributed across a 9-node personal fleet:

| Node | Role | Specs | Location |
|---|---|---|---|
| `aio-01` | Controller ONLY (orchestration, monitoring, databases) | 2C, 7GB | Local |
| `server-01` | Worker execution | 8C, 15GB | Remote |
| `server-02` | Worker execution | 8C, 31GB | Remote |
| `server-03` | Worker execution | 8C, 31GB | Remote |
| `laptop-01` | Primary workstation + embeddings | 4C/8T, 31GB | Local |
| `desktop-ap` | Worker execution | 1GB | Remote |
| `server-ap` | Worker execution | 1GB | Remote |
| `pi-01` | Worker execution (low-power) | 1GB | Remote |
| `pi-02` | Worker execution (low-power) | 1GB | Remote |

**Important**: aio-01 is the controller/orchestrator ONLY -- never run worker tasks on it. Embeddings (sentence-transformers) run ONLY on laptop-01/02, never on fleet workers.

The fleet dispatcher (`fleet-agent-dispatcher.js`) routes tasks to available nodes, with automatic fallback to local execution. The fleet wrapper (`fleet-agent-wrapper.js`) transparently upgrades `agent()` calls to fleet-distributed execution when `FLEET_DISPATCHER=true`.

---

## Orchestration and Routing

### The Orchestrator

The `orchestrator.js` module is the intelligence layer that selects which models to use based on historical performance data. It queries the learning database (PostgreSQL on aio-01:5433 via REST API at aio-01:5000) for past execution metrics and scores models on four weighted dimensions:

| Dimension | Weight | Description |
|---|---|---|
| Quality | 40% | Average quality score from past executions |
| Confidence | 30% | Average confidence in past outputs |
| Success Rate | 20% | Percentage of executions with quality > 0.5 |
| Cost | 10% | Lower cost is better (penalizes expensive models) |

Functions provided:
- `selectModel(taskType)` -- returns the single best model for a task type
- `selectWorkers(taskType, {count})` -- returns N models ranked by performance
- `compareModels(taskType)` -- returns performance comparison across all models
- `getModelTrend(model, taskType, days)` -- returns daily metrics for trend analysis

### Task Routing Logic

```
User Request
    |
    v
Claude Code Main
    |
    +-- Is it simple? (file read, shell command, typo fix)
    |       YES --> Direct execution (single agent, no workflow)
    |
    +-- Is it complex? (audit, review, refactor, research)
    |       YES --> Select skill/workflow
    |               |
    |               +-- Which skill? (based on task type and memory)
    |               |       /code-solve for bugs
    |               |       /code-review for PRs
    |               |       /deep-research for research
    |               |       /ai-consensus for multi-perspective
    |               |
    |               +-- How many workers? (from multi-ai-config.json)
    |               |       QualityFirst: 6 workers
    |               |       Balanced: 3 workers
    |               |       CostOptimized: 2 workers
    |               |
    |               +-- Which consensus strategy? (from context)
    |                       Critical --> Rotating Arbiter
    |                       Fast --> Majority Vote
    |                       Default --> Single Arbiter
    |
    v
Execute + Learn
```

### Multi-AI Configuration

Global settings in `~/.claude/workflows/multi-ai-config.json`:

| Mode | Workers | Arbiter | Cost Multiplier |
|---|---|---|---|
| Single-AI | 1 | No | 1x |
| Dual | 2 | Yes | 3x |
| Triple (default) | 3 | Yes | 4x |
| Quad | 4 | Yes | 5x |
| Full fleet | 6 | Yes | 7x |

---

## The Learning Pipeline

### What Gets Recorded

Every workflow execution captures:
- **Task metadata**: type, prompt, parameters, model selections
- **Execution metrics**: duration, token usage, cost
- **Quality signals**: confidence scores, success/failure, error types
- **AI reactions**: confidence markers, uncertainty markers, self-corrections
- **Consensus data**: agreement rates, vote distributions, arbiter reasoning

### Where It Is Stored

| Storage | Purpose | Location |
|---|---|---|
| **Learning Database** (PostgreSQL) | Execution metrics, model performance | aio-01:5433 via REST API at aio-01:5000 |
| **Learnings Archive** (Markdown) | Categorized insights, 148+ files | `~/.claude/learning/learnings/` |
| **Memory System** (MEMORY.md) | User preferences, project context, pattern index | `~/.claude/projects/*/memory/` |
| **Vector Search** (pgvector) | Semantic search over past tasks | PostgreSQL + pgvector via REST API at aio-01:5000 |
| **Arbiter State** (JSON) | Current position in arbiter rotation | `arbiter-state.json` |
| **Reaction DB** | AI behavioral signals (confidence, hesitation) | Learning database (PostgreSQL) |
| **Confidence Calibration** | Platt/isotonic scaling data | Learning database (PostgreSQL) |

### Feedback Loops

The system operates seven feedback cycles, from short-term to long-term:

**Cycle 1: Task Completion (Seconds)**
Task output -> success/failure signal -> immediate memory note -> next task benefits

**Cycle 2: Session Summary (Hours)**
Multiple task outputs -> extract learnings -> session-YYYY-MM-DD.md -> project history updated

**Cycle 3: Cross-Session Pattern Recognition (Days)**
Learnings archive (148+ files) -> pattern detection -> MEMORY.md update -> future sessions use refined heuristics

**Cycle 4: Performance Monitoring (Continuous)**
`/ai-performance-monitor` -> model degradation detected -> arbiter fallback triggered -> config adjusted

**Cycle 5: Cost Optimization (Continuous)**
`/ai-cost-tracker` -> overspend detected -> strategy switches to CostOptimized -> token budget enforced

**Cycle 6: Confidence Calibration (Continuous)**
`/ai-confidence-calibration` -> Platt scaling applied -> better confidence scores -> decision thresholds adjusted

**Cycle 7: Workflow Optimization (Continuous)**
`/code-sdlc-auto-continuous` -> issues found -> auto-fix applied -> commit -> re-run -> clean state

---

## Evolution: From Single-Agent to Self-Improving Fleet

### Phase 1: Single Agent (Baseline)

The starting point. One Claude instance handles everything sequentially.

```
User -> Claude -> Result
```

**Limitations**: Single perspective, no cross-validation, no learning, no specialization.

### Phase 2: Multi-Agent with Fixed Roles

Introduction of the worker/arbiter pattern with hardcoded model assignments.

```
User -> Claude -> [Opus-Worker, Sonnet-Worker, Haiku-Worker] -> Opus-Arbiter -> Result
```

**Improvements**: Diverse perspectives, consensus filtering.
**Limitations**: Fixed model assignments, no adaptation, static strategies, all tasks treated equally.

### Phase 3: Configurable Multi-AI with Rotation

Multi-ai-config.json enables cost/quality tradeoff. Arbiter rotation prevents bias.

```
User -> Claude -> Config -> [N Workers from config] -> Rotating Arbiter -> Result
```

**Improvements**: Configurable worker count, arbiter rotation, cost management.
**Limitations**: No learning from outcomes, manual strategy selection.

### Phase 4: Learning-Driven Orchestration (Current)

The orchestrator queries historical performance data to select optimal models. The learning pipeline captures every execution outcome.

```
User -> Claude -> Orchestrator (queries Learning DB) -> [Optimal Workers] -> Rotating Arbiter -> Result -> Learning Pipeline -> DB
```

**Improvements**: Data-driven model selection, performance tracking, cost tracking, confidence calibration.
**Capabilities emerging**: Task routing based on model strengths, automatic cost optimization, trend detection.

### Phase 5: Autonomous Self-Improvement (Vision)

AIs identify knowledge gaps, research solutions autonomously from web/PDFs/code, synthesize findings, validate improvements, and deploy them without human intervention.

```
Curiosity Engine -> [Parallel Research Agents] -> Knowledge Synthesis -> Validation -> Auto-Deployment -> Knowledge Graph
```

**Vision capabilities**: Omnivorous learning from any source, autonomous gap identification, self-directed research, automatic knowledge deployment, 24/7 continuous improvement.

---

## Architecture Diagram

```
                        CLAUDE CODE MULTI-AI ARCHITECTURE
===========================================================================

                                    +----------+
                                    |   USER   |
                                    +-----+----+
                                          |
                              +-----------+-----------+
                              |   Natural Language    |
                              |   Commands & Feedback |
                              +-----------+-----------+
                                          |
                                          v
                    +-----------------------------------------+
                    |           CLAUDE CODE (Main)            |
                    |  +------------------------------------+ |
                    |  |  - Interprets user intent          | |
                    |  |  - Routes to skills/workflows      | |
                    |  |  - Manages context & memory        | |
                    |  +------------------------------------+ |
                    +------+---------------------------+------+
                           |                           |
              +------------+----------+    +-----------+-----------+
              |   Direct Execution    |    |   Workflow Invocation |
              |   (Simple tasks)      |    |   (Complex tasks)     |
              +------------+----------+    +-----------+-----------+
                           |                           |
                           |                           v
                           |         +----------------------------------+
                           |         |  ORCHESTRATOR (orchestrator.js)  |
                           |         |  +----------------------------+  |
                           |         |  | - Queries learning DB      |  |
                           |         |  | - Scores model performance |  |
                           |         |  | - Spawns workers/arbiters  |  |
                           |         |  | - Manages parallel/pipeline|  |
                           |         |  | - Aggregates results       |  |
                           |         |  +----------------------------+  |
                           |         +----------+---+-------------------+
                           |                    |   |
                           |         +----------+   +---------+
                           |         |                        |
                           |         v                        v
                           |  +-------------+         +--------------+
                           |  |   WORKERS   |         |   ARBITERS   |
                           |  |  (Parallel) |         |  (Synthesis) |
                           |  +------+------+         +------+-------+
                           |         |                       |
                           +---------+-----------+-----------+
                                                 |
                    +----------------------------+--------------------+
                    |              AI FLEET (Multi-Model)             |
                    +----------------------------+--------------------+
                                                 |
        +---------------+---------------+--------+-----+----------+----------+
        |               |               |              |          |          |
        v               v               v              v          v          v
   +--------+      +--------+     +---------+    +---------+ +--------+ +---------+
   | FABLE  |      |  OPUS  |     | SONNET  |    |  HAIKU  | | GPT-4o | | GEMINI  |
   | (4.5)  |      |  (3.7) |     |  (4.5)  |    |  (3.5)  | |(OpenAI)| | (2.0)   |
   +---+----+      +---+----+     +----+----+    +----+----+ +---+----+ +----+----+
       |               |               |              |          |          |
       |               +---------------+--------------+----------+----------+
       |                                      |
       |                         +------------+------------+
       |                         |   Diverse Perspectives  |
       |                         |   - Different reasoning |
       |                         |   - Cross-validation    |
       |                         |   - Error detection     |
       |                         +------------+------------+
       |                                      |
       |                                      v
       |                         +-------------------------+
       |                         |  CONSENSUS FORMATION    |
       |                         |  +-------------------+  |
       |                         |  | - Vote/Weight     |  |
       |                         |  | - Debate/Refine   |  |
       |                         |  | - Hierarchical    |  |
       |                         |  | - Confidence up   |  |
       |                         |  +-------------------+  |
       |                         +----------+--------------+
       |                                    |
       +------------------------------------+
                                            |
                                            v
                              +--------------------------+
                              |    LEARNING PIPELINE     |
                              |  +--------------------+  |
                              |  | 1. Execution logs  |  |
                              |  | 2. Extract insight |  |
                              |  | 3. Store learning  |  |
                              |  | 4. Update memory   |  |
                              |  +--------------------+  |
                              +-----------+--------------+
                                          |
                    +---------------------+--------------------+
                    |                                          |
                    v                                          v
        +------------------------+              +-------------------------+
        |   LEARNINGS DATABASE   |              |    MEMORY SYSTEM        |
        |   ~/.claude/learning   |              |  MEMORY.md + feedback/* |
        |   - 148+ files         |<-------------|  - Project context      |
        |   - Categorized        |              |  - User preferences     |
        |   - Searchable         |              |  - Pattern index        |
        +------------+-----------+              +----------+--------------+
                     |                                     |
                     +-----------------+-------------------+
                                       |
                                       v
                            +--------------------+
                            |  FEEDBACK LOOP     |
                            |  +--------------+  |
                            |  | Improved:    |  |
                            |  | - Decisions  |  |
                            |  | - Routing    |  |
                            |  | - Quality    |  |
                            |  | - Accuracy   |  |
                            |  +--------------+  |
                            +----------+---------+
                                       |
                                       +-------> (Back to Claude Code Main)


===========================================================================

KEY INFORMATION FLOWS:

    ------->    Command/Request         ========>   Learning/Memory
    - - - ->    Result/Response          ......>    Context/Preference

DECISION POINTS:

    [D1] Task Complexity Assessment -> Direct execution vs. Workflow
    [D2] Multi-Model Strategy Selection -> QualityFirst/CostOptimized/Balanced
    [D3] Consensus Pattern -> Vote/Debate/Hierarchical/Refinement
    [D4] Learning Extraction -> What patterns/insights to preserve

LEARNING LOOPS:

    L1: User Feedback -> Memory -> Future Behavior
    L2: Execution Outcome -> Learnings DB -> Pattern Library
    L3: Multi-AI Results -> Confidence Calibration -> Better Routing
    L4: Workflow Performance -> Optimization -> Faster Execution
```

---

## End-to-End Decision Flow

```
CLAUDE CODE: END-TO-END DECISION FLOW WITH FEEDBACK LOOPS
===========================================================================


                                    +-------------------------+
                                    |   USER REQUEST INPUT    |
                                    |  (Task Description)     |
                                    +------------+------------+
                                                 |
                                                 v
                    +========================================================+
                    ||              CLAUDE ANALYSIS & DECISION MAKING        ||
                    ||  +--------------------------------------------------+||
                    ||  | - Parse user requirements                         |||
                    ||  | - Check memory & project context (MEMORY.md)     |||
                    ||  | - Identify task type (coding/research/review)    |||
                    ||  | - Read project constraints & versioning policies |||
                    ||  | - Determine if multi-AI consensus needed         |||
                    ||  | - Select strategy (QualityFirst/Balanced/CostOpt)|||
                    ||  | - Map to available skills & tools                |||
                    ||  +--------------------------------------------------+||
                    +========================+===============================+
                                             |
                                 +-----------+-----------+
                                 v                       v
                    +------------------------+  +------------------------+
                    |   SINGLE AI PATH       |  |  MULTI-AI CONSENSUS    |
                    |  (Simple Tasks)        |  |  (Complex Tasks)       |
                    |                        |  |                        |
                    | - Tool selection       |  | - Arbiter selection    |
                    | - Direct execution     |  | - Worker assignment    |
                    |                        |  | - Debate/verification  |
                    +-----------+------------+  +-----------+------------+
                                |                           |
                                +-----------+---------------+
                                            v
                    +========================================================+
                    ||         ORCHESTRATOR COORDINATION & TASK ROUTING      ||
                    ||  +--------------------------------------------------+||
                    ||  | SKILL DISPATCH MATRIX:                            |||
                    ||  |                                                   |||
                    ||  | +- /code-solve         -> Solver pattern for bugs |||
                    ||  | +- /code-test-auto     -> Test generation         |||
                    ||  | +- /code-review        -> PR review & findings    |||
                    ||  | +- /code-sdlc-auto     -> Full SDLC pipeline     |||
                    ||  | +- /deep-research      -> Multi-source research  |||
                    ||  | +- /ai-consensus       -> Multi-model consensus  |||
                    ||  | +- /ai-prompt          -> Multi-perspective      |||
                    ||  | +- /verify             -> Manual verification    |||
                    ||  | +- [30+ other skills]  -> Domain-specific tools  |||
                    ||  |                                                   |||
                    ||  | EXECUTION COORDINATION:                          |||
                    ||  | - Task dependency resolution (blockedBy)         |||
                    ||  | - Parallel vs sequential (pipeline/parallel)     |||
                    ||  | - Token budget tracking (/ai-cost-tracker)       |||
                    ||  | - Real-time status (/workflow-status)            |||
                    ||  +--------------------------------------------------+||
                    +========================+===============================+
                                             |
                                             v
                    +========================================================+
                    ||              FLEET EXECUTION ENVIRONMENT              ||
                    ||  +--------------------------------------------------+||
                    ||  |  COMPUTE RESOURCES:                               |||
                    ||  |  +----------------+----------------+-------------+|||
                    ||  |  | Local Machine  | Distributed    | Cloud       ||||
                    ||  |  |                | Fleet          | Workers     ||||
                    ||  |  | - Claude Haiku | - aio-01       | - LLM APIs ||||
                    ||  |  | - Bash/Git     | - server-01/02 | - GPU inst ||||
                    ||  |  | - File tools   | - server-03    | - Services ||||
                    ||  |  +----------------+----------------+-------------+|||
                    ||  +--------------------------------------------------+||
                    +========================+===============================+
                                             |
                                             v
                    +========================================================+
                    ||           RESULTS GENERATION & OUTPUT                 ||
                    ||  +--------------------------------------------------+||
                    ||  | OUTCOME TYPES:                                    |||
                    ||  |                                                   |||
                    ||  | - Code Changes        -> Git commits             |||
                    ||  | - Test Reports        -> Coverage metrics        |||
                    ||  | - Analysis Summaries  -> Findings, recommendations|||
                    ||  | - Research Reports    -> Fact-checked, sourced   |||
                    ||  | - PR Reviews          -> Inline comments         |||
                    ||  | - Verification        -> Execution logs          |||
                    ||  | - Consensus           -> Multi-AI synthesis      |||
                    ||  +--------------------------------------------------+||
                    +========================+===============================+
                                             |
                                             v
                    +========================================================+
                    ||          LEARNING EXTRACTION & FEEDBACK LOOP          ||
                    ||  +--------------------------------------------------+||
                    ||  | OBSERVATION CAPTURE:                              |||
                    ||  | - Execution outcome (success/error)              |||
                    ||  | - Decision effectiveness (time, quality, cost)   |||
                    ||  | - Model performance (accuracy, latency)          |||
                    ||  | - Strategy effectiveness (multi-AI vs single)    |||
                    ||  |                                                   |||
                    ||  | LEARNING ARTIFACTS:                              |||
                    ||  | - Session summaries (.md files)                  |||
                    ||  | - Project histories (per-project learnings)      |||
                    ||  | - Performance metrics (ai-performance-monitor)   |||
                    ||  | - Confidence calibration (Platt/isotonic)        |||
                    ||  | - Cost tracking (ai-cost-tracker)                |||
                    ||  +--------------------------------------------------+||
                    +========================+===============================+
                                             |
                    +------------------------+------------------------+
                    |                        |                        |
                    v                        v                        v
      +-------------------------+  +-------------------------+  +---------------------+
      |  MEMORY UPDATE LOOP     |  |  CONFIG REFINEMENT      |  |  STRATEGY ADJUST    |
      |                         |  |                         |  |                     |
      | - Update MEMORY.md      |  | - settings.json changes |  | - Model selection   |
      | - Add project histories |  | - Permission updates    |  | - Consensus method  |
      | - Archive learnings     |  | - Workflow hooks        |  | - Cost optimization |
      | - Extract patterns      |  | - Tool configuration    |  | - Next-task routing |
      +------------+------------+  +------------+------------+  +----------+----------+
                   |                            |                          |
                   +----------------------------+--------------------------+
                                                |
                                                v
                                +-------------------------------+
                                |  FEEDBACK LOOP CLOSURE        |
                                |  +-------------------------+  |
                                |  | Applies to NEXT run:    |  |
                                |  | - Better heuristics     |  |
                                |  | - Better tool selection |  |
                                |  | - Optimized multi-AI    |  |
                                |  | - Updated constraints   |  |
                                |  +-------------------------+  |
                                +---------------+---------------+
                                                |
                                                | [LOOP CYCLES]
                                                |
                                                v
                                +-------------------------------+
                                |  USER REQUEST INPUT           |
                                |  (Improved by prior learning) |
                                +-------------------------------+


===========================================================================

KEY DECISION POINTS:

+- MULTI-AI TRIGGER (MEMORY.md: ALWAYS Multi-AI) -------------------------+
|                                                                           |
| IF task_complexity > threshold OR user_asks_for_consensus:               |
|    +- workers = [Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini]            |
|    +- arbiter = rotating (Fable -> Opus -> Sonnet -> ...)                |
|    +- strategy = QualityFirst (6 workers)                                |
|    +- Result: High-confidence consensus output                           |
| ELSE:                                                                     |
|    +- Single model execution (Haiku for speed)                           |
|    +- Result: Fast, direct answer                                        |
+--------------------------------------------------------------------------+

+- SKILL SELECTION LOGIC --------------------------------------------------+
|                                                                           |
| Research task?        -> /deep-research                                  |
| Code bug/solve?       -> /code-solve or /code-solve-auto                 |
| PR review?            -> /code-pr-review-auto                            |
| Test needed?          -> /code-test-auto                                 |
| Need consensus?       -> /ai-consensus or /ai-consensus-hierarchical     |
| Verification?         -> /verify                                         |
| Full SDLC pipeline?   -> /code-sdlc-auto-continuous                     |
| Cost/performance?     -> /ai-cost-tracker or /ai-performance-monitor     |
+--------------------------------------------------------------------------+

+- CONSTRAINT ENFORCEMENT -------------------------------------------------+
|                                                                           |
| FROM MEMORY.md:                                                          |
| - [ALWAYS Multi-AI] -> Apply to complex tasks                           |
| - [No Version Management] -> Never create git tags                      |
| - [Arbiter/Worker Multi-Model] -> Different models for diversity        |
| - [Search Engineering Models] -> Restricted to 4 models only            |
| - Project versioning: X.Y format (not X.Y.Z)                            |
+--------------------------------------------------------------------------+
```

---

## Learning Loop Over Time

```
    ORCHESTRATOR LEARNING LOOP: CONTINUOUS IMPROVEMENT OVER TIME
    =============================================================

    Session 1                 Session 2                 Session N
    (Baseline)                (Improved)                (Optimized)
    +----------------+        +----------------+        +----------------+
    |  Execute Tasks |        |  Execute Tasks |        |  Execute Tasks |
    |  Quality: 72%  |        |  Quality: 86%  |        |  Quality: 97%  |
    +-------+--------+        +-------+--------+        +-------+--------+
            |                         |                         |
            v                         v                         v
    +----------------+        +----------------+        +----------------+
    | Collect Results|        | Collect Results|        | Collect Results|
    | & Feedback     |        | & Feedback     |        | & Feedback     |
    +-------+--------+        +-------+--------+        +-------+--------+
            |                         |                         |
            v                         v                         v
    +----------------+        +----------------+        +----------------+
    |Extract Learnings|       |Extract Learnings|       |Extract Learnings|
    | 12 new insights |       | 8 new insights  |       | 3 new insights  |
    +-------+--------+        +-------+--------+        +-------+--------+
            |                         |                         |
            v                         v                         v
    +----------------+        +----------------+        +----------------+
    | Update Memory  |        | Update Memory  |        | Update Memory  |
    | & Strategies   |        | & Strategies   |        | & Strategies   |
    +-------+--------+        +-------+--------+        +-------+--------+
            |                         |                         |
            +----------->-------------+----------->-------------+
                  CARRY FORWARD             CARRY FORWARD


    QUALITY TRAJECTORY
    ~~~~~~~~~~~~~~~~~~
    100% |                                          ............
         |                                   ......:
         |                              ....:
     90% |                          ...:
         |                      ...:
         |                  ...:
     80% |              ...:
         |          ...:
         |       ..:
     70% |   ...:
         |  :
         |.:
     60% +--+--------+--------+--------+--------+--------+-->
         S1       S2       S3       S4       S5       SN


    FEEDBACK LOOP DETAIL (each session)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

         +============+
         | START      |
         | SESSION    |
         +====+=======+
              |
              v
    +---------+----------+     +-------------------+
    | Load Prior Learnings|<----| Memory Store      |
    | & Calibration Data  |     | (learnings/*.md)  |
    +---------+----------+     +-------------------+
              |                         ^
              v                         |
    +---------+----------+              |
    | Route Tasks to     |              |
    | Best-Fit Models    |              |
    +---------+----------+              |
              |                         |
              v                         |
    +---------+----------+              |
    | Execute with       |              |
    | Multi-AI Consensus |              |
    +---------+----------+              |
              |                         |
              v                         |
    +---------+----------+              |
    | Score Outcomes      |             |
    | (accuracy, cost,    |             |
    |  latency, quality)  |             |
    +---------+----------+              |
              |                         |
              v                         |
    +---------+----------+              |
    | Extract Patterns:  |              |
    |  - What worked     |              |
    |  - What failed     |              |
    |  - Model strengths +--------------+
    |  - Cost tradeoffs  |   PERSIST
    +--------------------+


    WHAT IMPROVES ACROSS SESSIONS
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    +-------------------+------+------+------+------+------+
    | Metric            |  S1  |  S2  |  S3  |  S4  |  SN  |
    +-------------------+------+------+------+------+------+
    | Task routing acc. | 60%  | 75%  | 85%  | 92%  | 98%  |
    | Model selection   | rand | freq | cali | opti | opti |
    | Confidence calib. | raw  | Plat | isot | isot | isot |
    | Cost efficiency   | 1.0x | 0.8x | 0.6x | 0.5x | 0.4x|
    | Error rate        | 15%  |  9%  |  5%  |  2%  |  <1% |
    | Reuse of patterns | 0    | 12   | 28   | 45   | 148  |
    +-------------------+------+------+------+------+------+

    Legend: rand=random, freq=frequency, cali=calibrated,
            opti=optimized, Plat=Platt scaling, isot=isotonic
```

---

## Configuration and Cost Management

### Multi-AI Configuration Levels

**Level 1: Global config** (`~/.claude/workflows/multi-ai-config.json`)
Sets default worker count, model list, and arbiter settings for all workflows.

**Level 2: Per-workflow override**
Individual workflows can hardcode specific models or worker counts for phases that require it.

**Level 3: Per-invocation override** (planned)
Environment variables like `MULTI_AI=dual` to temporarily adjust for a single run.

### Cost Scaling

Assuming 50k tokens per agent per phase:

| Configuration | Agents per Phase | Tokens per Phase | Relative Cost |
|---|---|---|---|
| Single-AI | 1 | 50k | 1x (baseline) |
| Dual + Arbiter | 3 | 150k | 3x |
| Triple + Arbiter | 4 | 200k | 4x |
| Quad + Arbiter | 5 | 250k | 5x |
| Full fleet + Arbiter | 7 | 350k | 7x |

### Cost-Quality Strategy Matrix

Nine named strategies (from `consensus-strategies.js` and memory):

| Strategy | Workers | Arbiter | Use Case |
|---|---|---|---|
| **QualityFirst** | 6 (all models) | Rotating | Critical production decisions |
| **CostOptimized** | 2 (haiku + 1) | None (majority vote) | Development iteration |
| **Balanced** | 3 (opus/sonnet/haiku) | Single (opus) | Standard production |
| **FreeTier** | Free API models (Pollinations, ZeroLimitAI, OpenRouter free) | Free-tier arbiter | Zero-cost development iteration |
| **QuintupleVerification** | 5 (5-stage) | Multi-stage | Highest assurance |

---

## Constraints and Policies

These are enforced via MEMORY.md and are non-negotiable:

| Policy | Rule | Enforcement |
|---|---|---|
| **ALWAYS Multi-AI** | Use multi-AI with maximum coverage (6 models) for ALL decisions. Quality over cost. No exceptions. | MEMORY.md default behavior |
| **No Version Management** | Never create git tags; user handles all versioning | MEMORY.md constraint |
| **Arbiter/Worker Multi-Model** | Always use different AI models for workers to get diverse perspectives | MEMORY.md pattern |
| **Search Engineering Models** | `/search-engineering/` directory restricted to 4 models: Gemini, Opus, Sonnet, Haiku only | MEMORY.md project constraint |
| **Versioning Format** | X.Y format (not X.Y.Z); every main commit is a release candidate | MEMORY.md project policy |
| **Workflow parallel() vs pipeline()** | `parallel()` = concurrent (eliminates waits), `pipeline()` = sequential (adds waits) | MEMORY.md semantics |

---

## Quick Reference

### Terminology

| Term | Definition |
|---|---|
| **Worker** | AI agent that independently analyzes a task using a specific model |
| **Arbiter** | AI agent that synthesizes multiple worker outputs into a final result |
| **Consensus** | The process of combining multiple perspectives into a single high-confidence output |
| **Rotation** | Cycling the arbiter model to prevent bias (fable -> opus -> sonnet -> ...) |
| **Phase** | A discrete step in a workflow; each phase can have its own workers and arbiter |
| **Fleet** | The collection of distributed compute nodes for parallel execution |
| **Learning DB** | PostgreSQL database (aio-01:5433, accessed via REST API at aio-01:5000) storing execution metrics and model performance |
| **Learnings Archive** | 148+ categorized Markdown files containing extracted insights |
| **MEMORY.md** | Persistent user preferences and project context |
| **Strategy** | The consensus algorithm used (rotating, single, majority, pairwise, weighted) |
| **Orchestrator** | The module that selects optimal models based on historical performance |

### Key Files

| File | Purpose |
|---|---|
| `orchestrator.js` | Model selection based on historical performance |
| `consensus-strategies.js` | Five consensus algorithms |
| `get-next-arbiter.js` | Arbiter rotation state management |
| `update-arbiter-state.js` | Persists arbiter rotation state |
| `multi-ai-config.json` | Global worker/arbiter configuration |
| `load-multi-ai-config.js` | Configuration loading with defaults |
| `fleet-agent-dispatcher.js` | Routes tasks to fleet nodes |
| `fleet-agent-wrapper.js` | Transparent fleet-aware agent wrapper |
| `ai-extract-learning.js` | Extracts insights from workflow execution |
| `ai-confidence-calibration.js` | Platt/isotonic confidence correction |
| `ai-cost-tracker.js` | Token usage and cost monitoring |
| `ai-performance-monitor.js` | Model performance tracking and alerts |
| `ai-reaction-tracker.js` | Tracks AI behavioral signals |
| `workflows/TEMPLATE-arbiter-worker.js` | Reference template for new workflows |

### Common Slash Commands

| Command | What It Does |
|---|---|
| `/code-review` | Review current diff with multi-AI consensus |
| `/code-solve` | Fix a bug using worker/arbiter pattern |
| `/code-test-auto` | Generate and run tests autonomously |
| `/deep-research` | Multi-source, fact-checked research report |
| `/ai-consensus` | Run any task through multi-model consensus |
| `/ai-consensus-debate` | Adversarial debate between models |
| `/verify` | Run the app to confirm a change works |
| `/code-sdlc-auto-continuous` | Full SDLC pipeline until clean |
| `/workflow-status` | Show running workflows and workers |
