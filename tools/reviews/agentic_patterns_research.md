# Agentic Patterns Research for LLM Orchestration Fleet

**Date:** 2026-07-26
**Reviewed by:** Groq/Llama-3.3-70B, Cohere/Command-A
**System context:** 200+ API models, 8-worker fleet, PostgreSQL+pgvector, OrientDB, Redis
**Already implemented:** Thompson Sampling, MoA, LLM Cascading, Contextual Retrieval, CRAG, Graph RAG, LLM-Guided Evolution, MAP-Elites, Contextual Bandits, Prompt Caching

---

## Table of Contents

1. [ReAct / Tool-Use Patterns](#1-react--tool-use-patterns)
2. [Self-Correction / Reflexion](#2-self-correction--reflexion)
3. [Planning Agents](#3-planning-agents)
4. [Memory-Augmented Agents](#4-memory-augmented-agents)
5. [Multi-Agent Orchestration Frameworks](#5-multi-agent-orchestration-frameworks)
6. [Self-Play / Constitutional AI](#6-self-play--constitutional-ai)
7. [Fleet Reviewer Feedback](#7-fleet-reviewer-feedback)
8. [Prioritized Implementation Roadmap](#8-prioritized-implementation-roadmap)

---

## 1. ReAct / Tool-Use Patterns

### What It Is

ReAct (Reasoning + Acting) interleaves LLM reasoning traces with tool actions in a Thought-Action-Observation loop. The model reasons about what to do, executes a tool call, reads the result, and reasons again. This grounds the LLM in external reality, reducing hallucination compared to pure Chain-of-Thought.

### Key Papers

| Paper | Venue | Approach | Key Result |
|-------|-------|----------|------------|
| **ReAct** (Yao et al.) | ICLR 2023 | Prompting-based Thought-Action-Observation loop | +34% ALFWorld, +10% WebShop vs RL baselines |
| **Toolformer** (Schick et al.) | NeurIPS 2023 | Self-supervised training to insert API calls | Competitive with larger models, zero-shot |
| **Gorilla** (Patil et al.) | NeurIPS 2024 | Fine-tuned LLaMA with retriever-aware training (RAT) | Surpasses GPT-4 on API calling; handles API versioning |

### How They Differ

- **ReAct**: Prompting-based. Any tools at inference time. Maximum flexibility.
- **Toolformer**: Training-based. Model learns WHEN to call tools autonomously. Fixed to trained tools.
- **Gorilla**: Fine-tuning + retrieval. Handles massive API catalogs (1000+). Adapts to API version changes via retrieval.

### Error Recovery (Production Critical)

Production tool-calling failures divide into four categories requiring different handling:

1. **Transport/Network errors** (TCP drops, DNS timeouts, 503): Orchestration layer retries silently. LLM never sees these.
2. **Service-level errors** (rate limits 429, server crashes 500): Orchestration layer extracts throttling headers, applies exponential backoff with jitter.
3. **Semantic/Validation errors** (schema mismatch, missing params, 400): LLM must read error, adjust reasoning, produce corrected request.
4. **Tool hallucination** (LLM invents non-existent tools): In naive implementations, 90.8% of retries are wasted on hallucinated tool names. Fix: per-tool circuit breakers, separate retry budgets per error class.

**Production patterns:**
- Exponential backoff with jitter (1-2s base, 2x per retry, max 5-7 attempts)
- Circuit breaker pattern (Closed -> Open -> Half-Open)
- Multi-LLM fallback (primary fails -> cheaper backup)
- State checkpointing for long workflows (resume from checkpoint on crash)
- Tiered degradation: Tier 1 (retry and win), Tier 2 (switch to backup)

### Implementation Complexity

Medium. ReAct prompting is straightforward. Error recovery architecture requires engineering.

### Use Case for Our System

Our fleet already routes tasks to 200+ models. ReAct patterns would formalize the tool-calling interface:
- **Structured tool registry** with schema validation per tool
- **Two-layer error handler**: orchestrator handles transport/rate-limit errors; model handles semantic errors
- **Per-tool circuit breakers** (we already have circuit breakers in `distributed-patterns.py`)
- **Tool hallucination budget**: separate retry counter for hallucinated tools vs real failures

### Open Source References

- [ReAct official repo](https://github.com/ysymyth/ReAct)
- [Gorilla + BFCL Leaderboard](https://github.com/ShishirPatil/gorilla)
- [LangGraph create_react_agent](https://langchain-ai.github.io/langgraph/)
- [agent-patterns library](https://agent-patterns.readthedocs.io/)

---

## 2. Self-Correction / Reflexion

### What It Is

LLMs critique and improve their own outputs iteratively. Two foundational approaches:

1. **Self-Refine**: Same model generates output, critiques it, and revises. No external feedback needed. Generate -> Critique -> Revise loop.
2. **Reflexion**: After task failure, agent generates verbal self-reflection stored in memory. Uses reflections to improve next attempt. "Verbal reinforcement learning."

### Key Papers

| Paper | Venue | Approach | Key Result |
|-------|-------|----------|------------|
| **Self-Refine** (Madaan et al.) | NeurIPS 2023 | Generate-critique-revise, same model | ~20% avg improvement, up to 49.2% absolute |
| **Reflexion** (Shinn et al.) | NeurIPS 2023 | Verbal RL with persistent memory | GPT-4 HumanEval 80% -> 91% |
| **LLMs Cannot Self-Correct** (Huang et al.) | ICLR 2024 | Analysis of self-correction limits | Self-correction degrades performance without external feedback |
| **Self-Correction as Feedback Control** | arXiv 2024 | Error dynamics, stability thresholds | EIR threshold diagnostic for beneficial vs harmful correction |

### Critical Findings

**When self-correction HELPS:**
- Tasks with verifiable outputs (code, math with tests)
- When external feedback signals are available (test results, API responses, ground truth)
- First 2-4 iterations only

**When self-correction HURTS:**
- Pure reasoning without external grounding
- High-accuracy models (accuracy-correction paradox: high baseline accuracy = less benefit)
- Beyond 4 iterations (degeneration-of-thought: model reinforces earlier mistakes)
- Without external feedback signals

**Two-Tier Capability Model:**
1. **EIR suppression** (Error Introduction Rate): Prevents model from changing correct answers. Achievable via prompt engineering.
2. **ECR enhancement** (Error Correction Rate): Enables actual improvement. Likely requires RL training with verifiable rewards.

**Optimal iteration count:** 2-4 iterations. Measure EIR on calibration set first. If equilibrium accuracy is below baseline, self-correction is compute waste.

### Implementation Complexity

Low-Medium. Self-Refine is pure prompting. Reflexion requires persistent memory (we have PostgreSQL).

### Use Case for Our System

Integrate self-correction into existing multi-AI review pipeline:
- **Post-generation quality gate**: After fleet generates output, run 2-3 Self-Refine iterations with external feedback (test execution, schema validation)
- **Reflexion for recurring tasks**: Store reflections from failed workflow executions in `learning.experiences` table. Feed back on retry.
- **EIR monitoring**: Track error introduction rate per model. Flag models where self-correction degrades output.
- **Calibrated iteration budgets**: Different iteration counts per task type (code: 3-4, prose: 2, math: 2 with tests)

### Open Source References

- [Self-Refine official](https://github.com/madaan/self-refine)
- [Reflexion official](https://github.com/noahshinn/reflexion)
- [LLM Self-Correction Papers List](https://github.com/ryokamoi/llm-self-correction-papers)

---

## 3. Planning Agents

### What It Is

Structured approaches to decomposing complex tasks into sub-tasks, exploring multiple solution paths, and verifying plan quality. Evolved from linear Chain-of-Thought to tree and graph structures.

### Key Papers

| Paper | Venue | Approach | Key Result |
|-------|-------|----------|------------|
| **Tree of Thoughts** (Yao/Long) | NeurIPS 2023 | DFS/BFS/beam search over reasoning paths | Multi-path exploration vs single-path CoT |
| **Graph of Thoughts** (Besta et al.) | 2023 | Aggregation, refinement, decomposition ops | Generalizes tree to arbitrary graph |
| **LATS** (Zhou et al.) | ICML 2024 | Monte Carlo Tree Search + LLM value function + reflection | 92.7% pass@1 HumanEval (SOTA); 75.9 on WebShop |
| **GAP** (2025) | arXiv | Dependency-aware sub-task graphs for parallel tool execution | +0.9% on multi-hop benchmarks |
| **ReAcTree** (2024/2025) | OpenReview | Hierarchical planning with episodic memory | 63% vs 24% (ReAct) on WAH-NL |
| **MAP** (2025) | Nature Communications | Brain-inspired modular planner | Superior transfer across task types |

### LATS Deep Dive (Most Relevant)

LATS (Language Agent Tree Search) unifies reasoning, acting, and planning via Monte Carlo Tree Search. The LLM plays three roles:

1. **Action generator**: Samples plausible actions at each tree node
2. **Value function**: Estimates expected reward for each candidate state (LLM-powered scoring)
3. **Reflection mechanism**: Self-critiques on failed trajectories, added as context for next iterations

Key insight: Many LLM tasks allow reverting to earlier steps, making tree search natural.

### GAP: Parallel Task Execution

GAP trains models to decompose complex tasks into dependency-aware sub-task graphs, determining which tools run in parallel vs sequentially. Directly applicable to our 8-worker fleet for maximizing parallelism.

### Implementation Complexity

Medium-High. Tree/graph search requires state management. LATS requires multiple LLM calls per node (action generation + value estimation). GAP requires dependency graph construction.

### Use Case for Our System

- **LATS for complex tasks**: When a task requires exploration (debugging, research, multi-hop QA), use MCTS to explore multiple solution paths across fleet workers. LLM value function scores each path.
- **GAP for workflow planning**: Before dispatching tasks to 8 workers, use GAP to build a dependency graph. Run independent sub-tasks in parallel, chain dependent ones.
- **Integration with Thompson Sampling**: Use TS to select which model plays the "value function" role in LATS. Track which models produce best value estimates.
- **Tree search + MoA**: Each tree branch explored by a different fleet model. Aggregate via MoA consensus.

### Open Source References

- [LATS official (ICML 2024)](https://github.com/lapisrocks/LanguageAgentTreeSearch)
- [LangGraph LATS implementation](https://langchain-ai.github.io/langgraph/)
- [Tree of Thoughts](https://github.com/princeton-nlp/tree-of-thought-llm)

---

## 4. Memory-Augmented Agents

### What It Is

Architectures that give LLM agents persistent memory beyond their context window, enabling long-term learning, relationship building, and accumulated expertise. Inspired by cognitive science models of human memory.

### Key Papers

| Paper | Venue | Approach | Key Result |
|-------|-------|----------|------------|
| **MemGPT** (Packer et al.) | ICLR 2024 | OS-inspired virtual context paging, 3-tier memory | 93.4% on Deep Memory Retrieval |
| **Zep/Graphiti** (Rasmussen et al.) | arXiv 2025 | Temporally-aware knowledge graph with bitemporal edges | 94.8% on DMR (beats MemGPT) |
| **CoALA** (Sumers et al.) | arXiv 2024 | Cognitive architecture blueprint for LLM agents | Framework: working + episodic + semantic + procedural |
| **A-MEM** | arXiv 2025 | Agentic memory with self-organizing capabilities | Autonomous memory management |
| **Mem^p** | arXiv 2025 | Exploration of procedural memory for agents | Skills/routines as executable subroutines |

### Memory Taxonomy (Convergent Across Frameworks)

| Memory Type | What It Stores | Retrieval Method | Our Equivalent |
|-------------|---------------|------------------|----------------|
| **Working** (Core) | Current task context, always in-context | Direct (in prompt) | Context window |
| **Episodic** (Recall) | Specific past events with timestamps | Temporal + semantic search | `learning.experiences` table |
| **Semantic** (Archival) | General facts, rules, knowledge | Vector similarity search | pgvector embeddings |
| **Procedural** | Skills, routines, workflows | Pattern matching | `learning.strategy_performance` |

### MemGPT/Letta Architecture

Three-tier virtual context management (inspired by OS virtual memory):
1. **Core Memory**: Always in-context. Essential facts, user preferences. LLM-managed via function calls.
2. **Recall Memory**: Searchable conversation history. Semantic search over past interactions.
3. **Archival Memory**: Long-term vector storage. Large-scale knowledge base.

The LLM itself manages paging between tiers using function calls (search, write, evict). When context exceeds threshold, older messages are evicted with summarization.

### Zep/Graphiti: Temporal Knowledge Graphs

Key innovation: **bitemporal edge annotation** -- every relationship carries both event time and ingestion time. Handles contradictory/updated facts without information loss. Built on Neo4j (note: we use OrientDB, same concept applies).

### Strategic Forgetting

Not a bug but a feature. Summarization + targeted deletion prevents context bloat. Critical for long-running agents that would otherwise accumulate unbounded context.

### Key Challenge: Confirmation Loops

Wrong memories become "ground truth." System treats incorrect memory as fact, affecting all future decisions. Directly relevant to our feedback loop optimizer.

### Implementation Complexity

Medium. Core concept maps to our existing PostgreSQL + pgvector. OrientDB provides the temporal graph layer.

### Use Case for Our System

We already have many pieces -- this is about connecting them:
- **Map existing tables to memory taxonomy**: `learning.experiences` = episodic, pgvector embeddings = semantic, `learning.strategy_performance` = procedural
- **Add context paging**: When context exceeds threshold, evict older items to archival with summarization. Retrieve on demand.
- **Temporal edge annotation in OrientDB**: Add bitemporal timestamps to all relationships (event_time, ingestion_time). Enables "what did we know at time T?" queries.
- **Strategic forgetting policy**: Auto-summarize experiences older than N days. Delete low-quality embeddings. Track memory freshness.
- **Confirmation loop detection**: Cross-reference with feedback loop optimizer. Flag memories that consistently lead to wrong decisions.

### Open Source References

- [Letta (MemGPT production)](https://github.com/letta-ai/letta)
- [Mem0](https://github.com/mem0ai/mem0) (~48K stars)
- [Zep/Graphiti](https://github.com/getzep/graphiti)
- [Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)
- [Agent-Memory-Paper-List](https://github.com/Shichun-Liu/Agent-Memory-Paper-List)

---

## 5. Multi-Agent Orchestration Frameworks

### What It Is

Frameworks for coordinating multiple LLM agents working together on complex tasks. The field has consolidated around four orchestration styles: graph-based, role-based, handoff-based, and hierarchical.

### Key Frameworks (2024-2026)

| Framework | Style | Status | Key Pattern |
|-----------|-------|--------|-------------|
| **LangGraph** | Graph-based state machine | Dominant in enterprise (2026) | Supervisor pattern, Pydantic state, PostgreSQL checkpointing |
| **CrewAI** | Role-based teams | $18M Series A, 100K+ exec/day | Agent roles/backstories/goals, rapid prototyping |
| **AutoGen/MS Agent Framework** | Conversational multi-agent | v1.0 GA April 2026 | GroupChat, event-driven, debate |
| **OpenAI Agents SDK** | Handoff-based | Replaced Swarm (March 2025) | Explicit agent-to-agent handoffs |
| **Google ADK** | Hierarchical tree | April 2025 | Root agent delegates, native A2A protocol |

### Critical Production Patterns

**Evaluator-Optimizer Pattern:**
Secondary validation agent checks primary agent's output against domain rules before returning. Improves accuracy from ~74% to 97%+ in regulated domains at 2-3x LLM call cost. We already do this with our two-panel review + meta-review approach.

**State Checkpointing:**
PostgreSQL checkpointer stores complete graph state (conversation history, tool results, user preferences). Restores via thread_id. Critical for long-running workflows that may crash.

**Circuit Breakers:**
Most expensive production mistake: supervisor loop with no circuit breaker. If LLM never returns "FINISH", graph runs until API budget is zero. Always set hard caps on retry counts.

### Multi-Agent Debate Research

**NeurIPS 2025 Spotlight finding:** Majority voting alone accounts for most performance gains attributed to multi-agent debate. Debate forms a **martingale** -- it doesn't improve expected correctness without targeted interventions (biasing belief updates toward correction).

**Practical implication:** Simple majority voting across fleet models may be as good as elaborate debate protocols for most tasks. Reserve debate for high-stakes decisions where the 2-3x cost is justified.

### Key Protocols

- **MCP (Model Context Protocol)**: Now under Linux Foundation. All major frameworks support it. Standard for tool/context integration.
- **A2A (Agent-to-Agent)**: Google-originated protocol for cross-framework agent communication.

### Implementation Complexity

Low (we already have most patterns). Our system IS a multi-agent orchestration system.

### Use Case for Our System

Our system already implements many of these patterns. Key gaps to address:
- **Formal state machine**: Our workflows are procedural scripts. Converting to LangGraph-style state machines would add checkpoint/resume, conditional branching, and better observability.
- **Evaluator-Optimizer integration**: Formalize our review+meta-review as an Evaluator-Optimizer pattern with explicit accuracy targets.
- **Voting vs debate selection**: Use simple majority voting for routine tasks (cheaper). Reserve full debate for high-stakes tasks identified by complexity estimation.
- **Circuit breaker on all workflow loops**: Audit all workflows for unbounded loops. Add hard caps.

### Open Source References

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [AutoGen/AG2](https://github.com/ag2ai/ag2)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)

---

## 6. Self-Play / Constitutional AI

### What It Is

Models evaluating, attacking, and improving their own outputs. Three sub-areas:
1. **Constitutional AI**: Models self-critique against defined principles
2. **Self-Play Red-Teaming**: Model attacks itself to find vulnerabilities
3. **Automated Prompt Injection Defense**: Systematic defense against the #1 OWASP LLM threat

### Key Papers

| Paper | Source | Approach | Key Result |
|-------|--------|----------|------------|
| **Constitutional Classifiers** | Anthropic 2025 | Defense against universal jailbreaks | Jailbreak success: 86% -> 4.4% |
| **GPT-Red** | OpenAI 2026 | Self-play RL red-teaming | 84% attack success vs 13% for humans |
| **Safety Self-Play (SSP)** | arXiv 2026 | Single LLM as attacker + defender | Reflective Experience Replay |
| **Self-RedTeam** | arXiv 2025 | Online multi-agent RL with Hidden CoT | Theoretical guarantees from zero-sum games |
| **JBFuzz** | 2025 | Fuzzing-based jailbreak framework | ~99% ASR across GPT-4o, Gemini, DeepSeek |

### Anthropic Constitutional Classifiers

Trained classifiers that filter inputs/outputs against constitutional principles. 183 red-teamers, 3000+ hours, $95K in bounties. No universal jailbreak found. Key: defense-in-depth (alignment + system prompts + guardrails + continuous red-teaming).

### OpenAI GPT-Red

Self-play RL where attacker model and defender model train simultaneously. Attacker rewarded for eliciting failures; defender rewarded for resisting. GPT-Red discovered novel attack classes (fake chain-of-thought) that humans missed. Used to harden GPT-5.6.

### Prompt Injection: The Fundamental Problem

LLMs process system instructions, user input, and retrieved content as a single token stream. No built-in mechanism separates "instructions to follow" from "content to read." This makes prompt injection fundamentally difficult to prevent.

### Implementation Complexity

Medium-High for self-play RL. Low for constitutional filtering and defense-in-depth.

### Use Case for Our System

- **Constitutional filtering layer**: Add input/output classifiers before and after fleet model responses. Define constitutional principles for our use cases.
- **Self-play for prompt hardening**: Use one fleet model as attacker, another as defender. Iterate to harden system prompts and tool descriptions.
- **Defense-in-depth for multi-model orchestration**: When routing tasks to 200+ models, some may be more vulnerable to injection than others. Use the most robust models for tasks involving untrusted input.
- **Red-team workflows**: Periodic automated red-teaming of our fleet. Store attack/defense results in `learning.experiences` for continuous improvement.

### Open Source References

- [Promptfoo Red Team Guide](https://www.promptfoo.dev/docs/red-team/)
- [JBFuzz](https://github.com/jbfuzz/jbfuzz)
- [Constitutional AI (Anthropic)](https://www.anthropic.com/research/constitutional-classifiers)

---

## 7. Fleet Reviewer Feedback

### Review 1: Groq / Llama-3.3-70B

**Prioritization for our fleet:**
1. Multi-agent orchestration framework (LangGraph/CrewAI) for workflow management
2. Memory-augmented agents (MemGPT/Zep) for individual model performance
3. Planning agents (LATS/ToT) for multi-step reasoning
4. Self-correction with 2-4 iteration budget

**Integration suggestions:**
- Thompson Sampling for tool/model selection within ReAct loops
- MoA for framework-level agent interaction management
- CRAG and Graph RAG for structured reasoning and knowledge representation
- Modular architecture for easy component addition/removal

**Missing areas flagged:**
- Cognitive architectures (SOAR, LIDA) applied to LLM orchestration
- Transfer learning / meta-learning for multi-task settings
- Hybrid symbolic-connectionist approaches

### Review 2: Cohere / Command-A

**Additional papers flagged (2024-2025):**
- **ToolSwitch** (ICML 2025): Adaptive tool selection during inference, switching tools mid-task based on real-time performance
- **SubAgent** (ACL 2025): Specialized sub-agents (reasoning vs execution) with coordinator LLM
- **NS-Agent** (NeurIPS 2024): Neurosymbolic integration combining LLMs with symbolic reasoning
- **BudgetRAG** (EMNLP 2025): Cost-performance tradeoff optimization, dynamically selecting cheaper models when high accuracy is not critical
- **MAESTRO** (ICLR 2025): Emergent multi-agent problem-solving without explicit coordination
- **Chain-of-Hindsight** (CoH, ICLR 2025): Retrospective analysis of failed attempts
- **Multi-Modal Tool Use** (MMTU, CVPR 2025): Orchestrating vision, speech, and text APIs
- **Adaptive Prompt Caching** (APC, ACL 2025): Dynamic caching based on task similarity, 40-60% reduction in redundant LLM calls
- **LLM-as-Compiler** (NeurIPS 2024): Natural language to executable workflow translation

**Integration with existing components:**
- Thompson Sampling + Gorilla/ToolSwitch for dynamic model/tool selection
- MoA + SubAgent for task-specific agent ensembles with Evaluator-Optimizer validation
- CRAG + Graph of Thoughts + GAP for better task decomposition and dependency management
- LATS for Monte Carlo exploration within Graph RAG knowledge graphs
- Prompt Caching + APC for reducing redundant calls across 200+ models

**Cost-aware recommendation:** Use BudgetRAG principles to allocate cheaper models for low-risk tasks, reserve expensive models for high-stakes decisions.

---

## 8. Prioritized Implementation Roadmap

Based on research + fleet reviews, ranked by impact-to-effort ratio for our specific system:

### Tier 1: High Impact, Low-Medium Effort (Implement First)

| Pattern | Why | Effort | Dependencies |
|---------|-----|--------|--------------|
| **Self-Refine integration** | 2-4 iteration post-generation quality gate. No training needed. | Low | Existing fleet infrastructure |
| **Reflexion memory** | Store task reflections in `learning.experiences`. Feed back on retries. | Low | PostgreSQL (have it) |
| **Two-layer error recovery** | Separate transport vs semantic error handling in fleet dispatch. | Medium | `distributed-patterns.py` (have it) |
| **Voting vs debate selector** | Simple majority for routine, full debate for complex. Save 60%+ on routine tasks. | Low | Complexity estimator (have it) |
| **Circuit breaker audit** | Add hard caps to ALL workflow loops. Prevent runaway API spend. | Low | All workflow files |

### Tier 2: High Impact, Medium Effort (Implement Next)

| Pattern | Why | Effort | Dependencies |
|---------|-----|--------|--------------|
| **Memory taxonomy formalization** | Map existing tables to episodic/semantic/procedural. Add paging. | Medium | PostgreSQL + pgvector (have both) |
| **GAP-style parallel planning** | Dependency-aware task graphs for 8-worker fleet. Maximize parallelism. | Medium | Workflow engine |
| **Evaluator-Optimizer formalization** | Explicit accuracy targets on review+meta-review pipeline. | Medium | Existing review panels |
| **Cost-aware routing** | BudgetRAG-inspired dynamic model selection based on task criticality. | Medium | Thompson Sampling + LLM Cascading (have both) |
| **Temporal edge annotation** | Add bitemporal timestamps to OrientDB relationships. | Medium | OrientDB (have it) |

### Tier 3: High Impact, High Effort (Plan for Later)

| Pattern | Why | Effort | Dependencies |
|---------|-----|--------|--------------|
| **LATS (Monte Carlo Tree Search)** | Explore multiple solution paths for complex tasks. SOTA on code generation. | High | Multiple LLM calls per node |
| **State machine workflows** | Convert procedural workflows to LangGraph-style state machines. | High | Workflow engine rewrite |
| **Self-play red-teaming** | Automated security hardening of fleet prompts/tools. | High | Dedicated compute budget |
| **Constitutional filtering layer** | Input/output classifiers for all fleet model responses. | High | Classifier training or API integration |
| **Adaptive prompt caching** | Dynamic caching based on task similarity. 40-60% call reduction. | Medium-High | Embedding similarity infrastructure |

### Integration Matrix: New Patterns x Existing Components

| New Pattern | Thompson Sampling | MoA | CRAG | Graph RAG | LLM Cascading | MAP-Elites |
|-------------|:-:|:-:|:-:|:-:|:-:|:-:|
| **ReAct/Tools** | Select tool-calling model | Aggregate tool results | Validate tool outputs | Tool discovery via graph | Escalate on tool failure | Evolve tool prompts |
| **Self-Refine** | Select refinement model | Multi-model critique | Verify refined output | -- | Cascade on refinement failure | Evolve critique prompts |
| **Reflexion** | Track reflection quality | -- | Store in retrieval | Reflect on graph paths | -- | Evolve reflection templates |
| **LATS** | Select value function model | Aggregate branch results | Validate search results | Navigate knowledge graph | Escalate on search failure | Evolve search heuristics |
| **Memory/Paging** | Select memory models | -- | Memory-augmented retrieval | Temporal knowledge graph | -- | Evolve memory policies |
| **GAP Planning** | Select planner model | Parallel worker aggregation | Validate sub-task outputs | Dependency graph from knowledge | -- | Evolve decomposition strategies |

---

## Key Research Sources

### ReAct / Tool-Use
- [ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629)
- [Toolformer: Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761)
- [Gorilla: Large Language Model Connected with Massive APIs](https://arxiv.org/abs/2305.15334)
- [ReAct Pattern Documentation](https://agent-patterns.readthedocs.io/en/stable/patterns/react.html)
- [Handling Tool Errors and Agent Recovery](https://apxml.com/courses/langchain-production-llm/chapter-2-sophisticated-agents-tools/agent-error-handling)
- [Your ReAct Agent Is Wasting 90% of Its Retries](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/)
- [AI Agent Retry Patterns](https://fast.io/resources/ai-agent-retry-patterns/)

### Self-Correction / Reflexion
- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- [Large Language Models Cannot Self-Correct Reasoning](https://openreview.net/forum?id=IkmD3fKBPQ)
- [Self-Correction as Feedback Control](https://arxiv.org/html/2604.22273v2)
- [LLM Self-Correction Papers List](https://github.com/ryokamoi/llm-self-correction-papers)

### Planning Agents
- [LATS: Language Agent Tree Search (ICML 2024)](https://arxiv.org/abs/2310.04406)
- [Tree of Thoughts (NeurIPS 2023)](https://www.promptingguide.ai/techniques/tot)
- [GAP: Graph-based Agent Planning](https://arxiv.org/html/2510.25320v1)
- [ReAcTree: Hierarchical Task Planning](https://openreview.net/forum?id=KgKN7F0PyQ)
- [Brain-Inspired Modular Agentic Planner (Nature Communications)](https://www.nature.com/articles/s41467-025-63804-5)
- [Demystifying Chains, Trees, and Graphs of Thoughts](https://arxiv.org/html/2401.14295v3)

### Memory-Augmented Agents
- [MemGPT: Towards LLMs as Operating Systems](https://research.memgpt.ai/)
- [Letta Documentation](https://docs.letta.com/concepts/memgpt/)
- [Zep/Graphiti Temporal Knowledge Graph](https://github.com/getzep/graphiti)
- [Mem0 vs Letta Comparison](https://vectorize.io/articles/mem0-vs-letta)
- [Memory for Autonomous LLM Agents: Survey](https://arxiv.org/html/2603.07670v1)
- [Practical Guide to Memory for Autonomous LLM Agents](https://towardsdatascience.com/a-practical-guide-to-memory-for-autonomous-llm-agents/)
- [Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)

### Multi-Agent Orchestration
- [LangGraph Multi-Agent Orchestration Guide](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/)
- [LangGraph Production Patterns](https://markaicode.com/langgraph-production-agent/)
- [Framework Comparison 2026](https://tensoria.fr/en/blog/multi-agent-orchestration-comparison)
- [Voting or Consensus? (ACL Findings 2025)](https://aclanthology.org/2025.findings-acl.606.pdf)
- [Debate or Vote? (NeurIPS 2025)](https://arxiv.org/abs/2508.17536)
- [Multi-Agent Debate with Adaptive Stability Detection](https://arxiv.org/html/2510.12697v1)

### Self-Play / Constitutional AI
- [Constitutional Classifiers (Anthropic)](https://www.anthropic.com/research/constitutional-classifiers)
- [GPT-Red: Self-Improvement for Robustness (OpenAI)](https://openai.com/index/unlocking-self-improvement-gpt-red/)
- [Be Your Own Red Teamer: Safety Self-Play](https://arxiv.org/html/2601.10589)
- [Self-RedTeam: Online Multi-Agent RL](https://arxiv.org/html/2506.07468v4)
- [Promptfoo Red Team Guide](https://www.promptfoo.dev/docs/red-team/)

---

*Research conducted 2026-07-26. Fleet review by Groq/Llama-3.3-70B and Cohere/Command-A.*
