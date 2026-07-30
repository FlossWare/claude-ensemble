# Knowledge Distillation & Inference Optimization Research

**Date:** 2026-07-26
**Researcher:** Claude Opus 4.6 (autonomous research agent)
**Fleet Reviewers:** NVIDIA Nemotron 3 Super 120B, Google Gemma 4 26B (via OpenRouter)
**System Context:** 8 workers + controller, 200+ API models, Thompson Sampling routing, LLM cascading, PostgreSQL+pgvector, Redis

---

## Table of Contents

1. [Knowledge Distillation for APIs](#1-knowledge-distillation-for-apis)
2. [Inference Optimization](#2-inference-optimization)
3. [RAG Advances 2024-2025](#3-rag-advances-2024-2025)
4. [Evaluation Frameworks](#4-evaluation-frameworks)
5. [Cost Optimization Beyond Caching](#5-cost-optimization-beyond-caching)
6. [Fleet Review Feedback](#6-fleet-review-feedback)
7. [Prioritized Implementation Roadmap](#7-prioritized-implementation-roadmap)
8. [References](#8-references)

---

## 1. Knowledge Distillation for APIs

### What It Is

Knowledge distillation transfers capabilities from expensive "teacher" models to cheaper "student" models. For API-based systems (where logits are not exposed), this means **black-box distillation**: collecting (prompt, teacher-output) pairs and fine-tuning students via supervised fine-tuning (SFT), often followed by reinforcement learning.

### Key Techniques

#### Chain-of-Thought (CoT) Distillation

Traditional distillation transfers only final answers. CoT distillation transfers the **reasoning process** itself.

- **CoTCD (Chain-of-Thought Curriculum Distillation, 2025):** Uses both CoT rationales and final answers as supervisory signals. Incorporates curriculum learning (easy-to-hard progression) for smoother acquisition of reasoning patterns.
- **ACoTD (Adaptive CoT Distillation, MDPI 2024):** Dynamically customizes distillation data based on student model performance on original problems -- teaching students according to their aptitude.
- **Key Finding (ACL Findings 2025):** Original CoT format outperforms complex/modified structures for smaller models (<7B parameters). Added complexity increases cognitive load without improving performance.

#### Symbolic Chain-of-Thought Distillation

- **SCoTD:** Translates natural language reasoning into symbolic expressions for step-by-step logical deduction. Trains 125M-1.3B parameter models on rationalizations from larger teachers.
- **IEEE Survey (Dec 2024):** Comprehensive survey on distilling implicit LLM knowledge into explicit symbolic form for interpretability and efficiency.

#### API-Based (Black-Box) Distillation

- Collect text outputs from teacher API, build synthetic dataset, fine-tune student with SFT+RL
- **Managed services:** OpenAI (GPT-4o -> 4o-mini with `store: true`), AWS Bedrock (500% faster, 75% cost reduction), Vertex AI (Gemini Pro -> Flash/Flash Lite)
- **DeepSeek R1:** Landmark case -- distilled 671B model to 1.5B-70B students; 32B/70B set SOTA on math/coding benchmarks

#### Optimal Compression Ordering

2025 study found **Pruning -> Distillation -> Quantization (P-KD-Q)** is the optimal sequence.

### Economics

- One team: $4,200/month -> $84/month (1B model doing 98% of 70B's work)
- Stanford HAI 2025: GPT-3.5-level inference cost fell 280x between Nov 2022 and Oct 2024 ($20 -> $0.07/M tokens)
- TensorZero: fine-tuning on curated teacher outputs can beat large-model performance at 5-30x lower inference cost

### Legal Considerations

- OpenAI/Anthropic TOS prohibit using outputs to train competing models
- Safe routes: distill within provider's platform OR use open-source teachers (Llama, Qwen, DeepSeek)
- Gartner predicts by 2027: organizations will use task-specific small models 3x more than general-purpose LLMs

### Implementation for Our System

| Approach | Complexity | Expected Benefit | Use Case |
|----------|-----------|------------------|----------|
| Synthetic data collection from Opus/GPT-4o | Low | Build training corpus for open models | Collect high-quality outputs during normal cascading |
| Managed distillation (Vertex AI) | Low | Gemini Pro quality at Flash cost | Google model tier optimization |
| CoT distillation for free-tier models | Medium | Improve reasoning in cheap cascade layers | Thompson Sampling routes more to cheap models |
| Task-specific specialist distillation | Medium | 80% traffic handled by 5 specialist models | Top 5 task types (classification, extraction, summarization, QA, code) |

---

## 2. Inference Optimization

### Speculative Decoding

**What it is:** A smaller, fast "draft" model generates 5-8 candidate tokens; a larger "verifier" model checks/accepts/rejects them in parallel. Output quality unchanged, latency reduced 2-3x.

**Production status (2025-2026):** Now standard practice. Native support in vLLM, TensorRT-LLM. NVIDIA demonstrated 3.6x throughput improvements on H200 GPUs.

#### Key Variants

| Variant | Innovation | Speedup | Source |
|---------|-----------|---------|--------|
| AdaSpec | Predictive config based on draft confidence | +66% over prior spec systems | 2025 |
| TurboSpec (Berkeley) | Closed-loop control maximizing goodput | Optimal across diverse workloads | UC Berkeley 2025 |
| OSD (Online Spec Decoding) | Continuously adapts draft models via KD | Improves acceptance rates on-the-fly | 2024 |
| DeepSpec/DSpark (DeepSeek) | Open-source training stack for custom drafts | 60-85% faster (V4-Flash) | June 2026 |
| EAGLE-3 | Lightweight autoregressive head, no separate draft | Eliminates draft model overhead | 2025 |
| Saguaro | Parallel drafting and verification | +30% over optimized baselines, up to 5x | 2025 |
| SpecReason | Drafts entire reasoning steps, not tokens | Better for reasoning models | 2025 |

#### API-Level Speculative Decoding (Critical for Our System)

In an API-orchestrated system, speculative decoding can be implemented at the routing layer:
1. Route draft request to fast/cheap API (e.g., Groq Llama-8B at 750 tok/s)
2. If draft confidence is high, accept without verification
3. If confidence is low, verify with expensive model (Opus/GPT-4o)
4. This combines cascade logic with speculative patterns

**Fleet reviewer warning (Nemotron):** API call overhead and worker contention could reduce theoretical 2-3x speedup to 1.2x in practice. Must colocate draft/verify on same worker and model API call costs.

### Request Batching Strategies

| Strategy | Innovation | Source |
|----------|-----------|--------|
| Decode-maximal batching (Microsoft 2025) | Hybrid micro-batch with prefill chunks filling decode headroom | Patented |
| Selective operation batching (FriendliAI 2025) | Batches only length-invariant operations, processes attention per-request | Patented |
| In-flight batching (NVIDIA) | Evicts finished sequences immediately, begins new requests mid-batch | Production |
| Continuous batching | Insert new requests into active batch at any point | Standard practice |

### Hardware Speed Leaders

| Provider | Architecture | Llama 70B Speed | Best For |
|----------|-------------|-----------------|----------|
| Cerebras WSE-3 | Wafer-scale, 4T transistors, 900K cores | ~2,100 tok/s | Maximum throughput, large models |
| Groq LPU | On-chip SRAM, deterministic execution | ~750 tok/s | Lowest time-to-first-token, real-time |
| NVIDIA Blackwell | GPU (improved Hopper) | 2-3x over Hopper | General purpose |

- Cerebras with speculative decoding: up to 4,000 tok/s on 70B
- Cerebras on 405B: 969 tok/s (impossible for GPU clusters without massive parallelism)
- Both are 10-20x faster than standard GPU inference
- Deloitte projects inference = 2/3 of all AI compute in 2026 (up from 1/3 in 2023)

### API Orchestration Frameworks

- **NVIDIA Dynamo (GTC 2025):** Disaggregated prefill/decode across separate GPU pools
- **AIBrix:** Hybrid orchestration with adapter scheduling and KV cache locality
- **Symphony:** Contextual hints for KV reuse, minimizes redundant decoding
- **ServerlessLLM:** Checkpoint-aware migration for serverless inference
- **Fluid Scheduling:** WAIT algorithm for latency-sensitive vs throughput-bound balancing

### Implementation for Our System

| Approach | Complexity | Expected Benefit | Use Case |
|----------|-----------|------------------|----------|
| API-level speculative decoding | Medium | 1.5-2x latency reduction | Use Groq as draft, expensive model as verifier |
| Request batching across workers | Medium | 30-50% throughput improvement | Group similar requests across fleet |
| Preferential routing to Groq/Cerebras | Low | Fastest responses for latency-sensitive tasks | Real-time and streaming use cases |

---

## 3. RAG Advances 2024-2025

### Current State

- SOTA RAG systems: 63% factual accuracy
- Basic retrieval without advanced techniques: 44%
- Advanced RAG adds quality-control layers across four stages: pre-retrieval, retrieval-time, post-retrieval, and architecture-level

### Key Techniques

#### HyDE (Hypothetical Document Embeddings)

- **What:** Generate a hypothetical answer document first, use its embedding for retrieval
- **Strength:** Excellent for short/vague queries against technical corpora
- **Limitation:** Limited benefit for precise numerical queries
- **Framework support:** LlamaIndex (HyDEQueryTransform), Haystack (native)

#### HyPE (Hypothetical Prompt Embeddings) -- Evolution of HyDE

- **What:** Precomputes hypothetical prompts at indexing time (not query time)
- **Key advantage:** No LLM calls at query time -- transforms retrieval into question-question matching
- **Benefit:** Faster and cheaper than HyDE while improving retrieval alignment

#### RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval)

- **What:** Builds hierarchical tree over documents: recursively embed, cluster, summarize
- **Performance:** 20% absolute accuracy increase on QuALITY benchmark with GPT-4
- **Published:** ICLR 2024
- **Best for:** Complex, multi-step reasoning tasks requiring context at multiple abstraction levels

#### Self-RAG (Self-Reflective RAG)

- **What:** Model decides WHEN to retrieve using special reflection tokens (IsREL, IsSUP, IsUSE)
- **Performance:** 7B/13B significantly outperform Llama2 + standard RAG
- **Published:** ICLR 2024 Oral (top 1%)
- **Key stat:** Only 2% of correct predictions came from outside retrieved passages (vs 15-20% in baselines)

#### CRAG (Corrective RAG)

- **What:** Lightweight evaluator scores relevance of retrieved documents
- **Action:** Use documents, ignore them, or fall back to web search based on score
- **Benefit:** Prevents low-quality retrievals from poisoning generation

#### GraphRAG (Microsoft, 2024)

- **What:** Knowledge graph + RAG, combining entity/relationship extraction with graph-based retrieval
- **Impact:** 10K+ GitHub stars, widely adopted
- **Best for:** Complex multi-hop queries over structured knowledge

#### Contextual Retrieval (Anthropic, 2024)

- **What:** Adds contextual information to chunks before embedding
- **Performance:** 67% reduction in retrieval failure rates
- **Best for:** Production RAG systems seeking easy wins

### Emerging Trends (2025)

- **Agentic RAG:** Reasoning + memory + multimodality, LLMs as autonomous retrieval agents
- **SimRAG:** Self-training over synthetic QA pairs for domain generalization
- **RankRAG/uRAG:** Unified reranking and generation within single backbone
- **Hybrid Retrieval:** Merging dense semantic + sparse lexical retrieval

### Fleet Reviewer Addition (Gemma)

- **MemGPT / Generative Agents:** Essential for understanding long-term state management in orchestration -- moving beyond simple RAG to memory hierarchies
- **"Lost in the Middle" problem:** Critical to address as RAG contexts grow longer
- **Context/KV-cache reuse:** Prefix caching across similar queries on same worker

### Implementation for Our System

| Approach | Complexity | Expected Benefit | Use Case |
|----------|-----------|------------------|----------|
| Contextual Retrieval | Low | 67% fewer retrieval failures | Add context to pgvector chunks |
| HyPE (indexing-time) | Low | Faster retrieval, no runtime LLM cost | Replace HyDE for our knowledge base |
| Self-RAG reflection | Medium | Avoid unnecessary retrieval calls | Only retrieve when needed, save API costs |
| RAPTOR hierarchical summaries | Medium | +20% accuracy on complex queries | Multi-step reasoning over documentation |
| CRAG fallback to web search | Medium | Handle knowledge gaps gracefully | When internal KB lacks coverage |
| GraphRAG integration | High | Multi-hop query support | Leverage existing OrientDB graph |

---

## 4. Evaluation Frameworks

### LLM-as-a-Judge

- GPT-4 matches human agreement at 80%+ (same as inter-human agreement)
- **Known biases:** Position bias, verbosity bias, self-enhancement bias, limited reasoning
- **2025 finding:** LLM-as-judge systems are "shortcut-prone and unfaithful" -- undermines reliability

### Benchmark Comparison

| Benchmark | Source | Separability | Arena Correlation | Strengths | Weaknesses |
|-----------|--------|-------------|-------------------|-----------|------------|
| MT-Bench | Multi-turn questions | Low at 95% CI | 91.3% (drops to 22.6% at 95% CI) | Multi-turn evaluation | Statistical unreliability |
| Chatbot Arena | Crowdsourced battles | High (with scale) | Ground truth | Real human preferences, massive scale | English-biased, short prompts |
| Arena-Hard | Derived from Arena | 87.4% | 89.1% | Cheap ($25), fast | 57% coding tasks |
| AlpacaEval | Instruction-following | Moderate | ~0.87 Pearson | Length-controlled version | Low coding/math coverage |
| WildBench (ICLR 2025) | Real user queries | High | 0.98 Pearson | Highest correlation, 1024 diverse tasks | Newer, less established |

### Key Papers

- **JudgeBench (ICLR 2025):** Evaluates LLM judges themselves on challenging response pairs spanning knowledge, reasoning, math, coding
- **WildBench (ICLR 2025):** 0.98 Pearson correlation with Chatbot Arena -- best available automated benchmark
- **Growing consensus:** Use deterministic evidence (unit tests, exact scorers, execution checks) first; LLM judges only when no stronger evidence applies

### Fleet Reviewer Additions

**Nemotron -- Routing-specific metrics (critical gap):**
- **Routing Stability Score:** KL-divergence of routing decisions for semantically similar inputs
- **Worker Utilization Entropy:** Higher = better load balancing (target: >0.85 for 8 workers)
- **Cascade Efficiency:** (Useful work done) / (Total API calls) -- isolates routing value from model quality
- **Cascade depth distribution:** % of requests exiting at worker 1 vs worker 8

**Gemma -- Operational evaluation:**
- **Semantic Drift Monitoring:** Detect distribution shift in user queries that might break Thompson Sampling weights
- **Unit Testing for LLMs:** Move from evaluation to integration testing (Promptfoo, DeepEval)

### Implementation for Our System

| Approach | Complexity | Expected Benefit | Use Case |
|----------|-----------|------------------|----------|
| Deterministic checks before LLM-judge | Low | More reliable evaluation | Unit tests, exact match, code execution |
| Routing-specific metrics | Medium | Measure orchestration quality | Stability, utilization entropy, cascade depth |
| WildBench-style evaluation | Medium | 0.98 correlation with human judgment | Automated quality dashboards |
| JudgeBench for arbiter validation | Medium | Validate our arbiter models | Ensure 6-model consensus is reliable |
| Semantic drift monitoring | Medium | Detect routing degradation early | Alert when query distribution shifts |
| Automated regression detection | High | Catch quality drops across model versions | CI/CD for model routing changes |

---

## 5. Cost Optimization Beyond Caching

### Prompt Compression

#### LLMLingua Family (Microsoft Research)

| Variant | Method | Compression | Performance Loss | Speed | Published |
|---------|--------|-------------|-----------------|-------|-----------|
| LLMLingua | Coarse-to-fine with budget controller | Up to 20x | Minimal | Good | EMNLP 2023 |
| LongLLMLingua | Query-aware contrastive perplexity | ~4x | +17.1% improvement | Good | 2024 |
| LLMLingua-2 | Token classification via BERT (GPT-4 distilled) | 2-5x | Better than v1 | 2.9x faster | ACL 2024 |

**Key findings:**
- Context compression saves 60-80% on LLM costs with minimal quality loss
- 2-5% accuracy loss at 10x compression; often zero loss at 2-3x
- Extractive compression can **improve** accuracy: +7.89 F1 at 4.5x compression (filters noise)
- Abstractive compression at similar ratios **decreases** performance by 4.69 F1

**Integration:** Already available in LangChain, LlamaIndex, Microsoft Prompt Flow

#### Other Compression Approaches

- **500xCompressor:** Compress entire context to single special token (extreme)
- **DSPy:** Automatically rewrites prompts (300 tokens -> 120 tokens without changing intent)
- **Semantic Bundling:** Distill conversations into structured bundles (decisions, outcomes, key facts)
- **SecurityLingua (CoLM 2025):** Safety guardrail via compression, 100x less token costs than SOTA guardrails

### Model Routing & Cascading

#### FrugalGPT (TMLR 2024)

- **Method:** Sequential query of LLMs based on confidence -- cheap model first, escalate if unsatisfied
- **Components:** LLM router + answer scorer + stop judger
- **Results:** Match GPT-4 quality with 98% cost reduction OR improve accuracy 4% at same cost
- **Critical finding:** LLM self-reported confidence is poorly calibrated -- biggest practical problem with naive cascades

#### RouteLLM (UC Berkeley, ICLR 2025)

- **Method:** Learning framework for training router models (binary: strong vs weak)
- **Results:** 85% cost reduction maintaining 95% GPT-4 quality, sends only 14% to strong model
- **Innovation:** Win prediction model estimating probability strong model outperforms weak

#### Advanced Routing (2025-2026)

- **IRT-Router (2025):** Item response theory for query difficulty + LLM ability, interpretable routing
- **CP-Router (2025):** Conformal prediction for uncertainty-based routing between standard and reasoning models
- **Router-R1 / R2-Reasoner:** Policy optimization for multi-step routing decisions
- **"Cluster, Route, Escalate" (2026):** Cascaded framework for cost-aware LLM serving
- **Lyra (NSDI 2024):** Cost-efficient routing via adaptive routing with latency awareness

### Fleet Reviewer Addition (Nemotron)

**Uncertainty-aware routing is critical:** Distillation alters model confidence calibration. If a distilled model's uncertainty estimates become miscalibrated, Thompson Sampling routes poorly, causing cascading accuracy drops *despite* lower per-call cost.

**Worker-aware cost optimization:** FrugalGPT/RouteLLM optimize per-request cost but ignore fleet constraints. If 90% of requests route to a cheap-but-slow API, it saturates 1-2 workers while others idle. Theoretical 85% savings could drop to 40% due to worker imbalance.

### Implementation for Our System

| Approach | Complexity | Expected Benefit | Use Case |
|----------|-----------|------------------|----------|
| LLMLingua-2 compression | Low | 2-5x token reduction, 60-80% cost savings | Compress before every API call |
| DSPy prompt optimization | Low | 40-60% reduction in system prompt tokens | Optimize static prompts |
| Improve cascade confidence scoring | Medium | Better early-exit decisions | Calibrate Thompson Sampling rewards |
| RouteLLM-style learned routing | Medium | 85% cost reduction (theoretical) | Complement Thompson Sampling |
| Worker-aware constrained routing | High | Balanced cost + utilization | Co-optimize routing and load balancing |

---

## 6. Fleet Review Feedback

### Reviewer 1: NVIDIA Nemotron 3 Super 120B

**Critical gaps identified:**

1. **No integration of distillation with routing dynamics:** Distillation alters model confidence calibration, breaking Thompson Sampling. Need uncertainty-preserving distillation (temperature scaling + conformal prediction).

2. **API call overhead in speculative decoding:** Network latency between workers for draft/verify steps could negate gains. Must colocate draft/target on same worker.

3. **RAG latency conflicts with cascading:** Self-RAG reflection tokens or RAPTOR recursion may trigger 2-3 extra LLM calls, blocking worker queues. Need latency-bounded RAG variants.

4. **Missing routing-specific evaluation metrics:** WildBench/Arena-Hard don't measure routing efficiency. Need: routing stability score, worker utilization entropy, cascade depth distribution, API cost variance.

5. **Worker-aware cost optimization missing:** RouteLLM/FrugalGPT optimize per-request, not per-fleet. Need constrained Thompson Sampling with worker queue depth as state variable.

**Additional papers cited:**
- SpecInfer: Ensemble drafting for black-box LLMs (MICRO 2024)
- Calibrated KD for Black-Box LLMs (EMNLP 2024)
- Lyra: Cost-efficient adaptive routing (NSDI 2024)
- RAPTOR-Lite: Early-exit conditions for latency-bounded RAG (ACL 2024)

### Reviewer 2: Google Gemma 4 26B

**Key additions:**

1. **Contextual Bandits over Thompson Sampling:** With 200+ models, the action space is too large for standard Thompson Sampling. Need contextual bandits conditioned on input query features.

2. **Memory hierarchies:** Move from simple RAG to MemGPT-style long-term/short-term memory architectures.

3. **Semantic drift monitoring:** Distribution shift in user queries can silently break Thompson Sampling weights.

4. **Task-specific specialist distillation:** Don't distill all 200 models. Identify top 5 tasks, distill 5 specialist workers for 80% of traffic.

**Priority ranking:**
1. Contextual routing and cascading (ROI driver)
2. API-level speculative decoding (UX driver)
3. Task-specific specialist distillation (margin driver)

**Additional references:**
- MemGPT / Generative Agents (2023/24) -- long-term state management
- "Leave No Context Behind" (2024) -- KV-cache management
- Phi series / "Textbooks Are All You Need" (Microsoft) -- synthetic data quality over quantity
- G-Eval (2023/24) -- CoT-based LLM judging
- JudgeLM (2024) -- more reliable LLM-as-judge

---

## 7. Prioritized Implementation Roadmap

Based on research findings and fleet review consensus, prioritized by impact-to-effort ratio for our specific system:

### Tier 1: High Impact, Low-Medium Complexity (Do First)

| # | Initiative | Expected Benefit | Effort | Dependencies |
|---|-----------|------------------|--------|-------------|
| 1 | **LLMLingua-2 prompt compression** | 60-80% token cost reduction | Low | pip install llmlingua, integrate before API calls |
| 2 | **Contextual Retrieval for pgvector** | 67% fewer retrieval failures | Low | Add context to chunks during ingestion |
| 3 | **Contextual Bandits upgrade** | Better routing for 200+ model space | Medium | Extend Thompson Sampling with query features |
| 4 | **Deterministic eval checks** | More reliable quality measurement | Low | Add unit tests, exact match before LLM-judge |
| 5 | **Cascade confidence calibration** | Fewer unnecessary escalations | Medium | Temperature scaling on cascade stop-judge |

### Tier 2: High Impact, Medium-High Complexity (Do Next)

| # | Initiative | Expected Benefit | Effort | Dependencies |
|---|-----------|------------------|--------|-------------|
| 6 | **API-level speculative decoding** | 1.5-2x latency reduction | Medium | Route draft to Groq, verify with expensive model |
| 7 | **Task-specific specialist distillation** | 80% traffic on cheap specialists | High | Identify top 5 tasks, collect training data, fine-tune |
| 8 | **Self-RAG reflection tokens** | Avoid unnecessary retrieval | Medium | Implement retrieve/critic decision logic |
| 9 | **Routing-specific metrics dashboard** | Measure orchestration quality | Medium | Stability score, utilization entropy, cascade depth |
| 10 | **HyPE indexing-time embeddings** | Faster retrieval, no runtime LLM cost | Medium | Precompute hypothetical prompts for all chunks |

### Tier 3: Transformative but Complex (Strategic)

| # | Initiative | Expected Benefit | Effort | Dependencies |
|---|-----------|------------------|--------|-------------|
| 11 | **Worker-aware constrained routing** | Balanced cost + fleet utilization | High | Co-optimize routing, load balancing, queue depth |
| 12 | **RAPTOR hierarchical summaries** | +20% accuracy on complex queries | High | Recursive clustering + summarization pipeline |
| 13 | **MemGPT-style memory hierarchy** | Long-term context management | High | Short-term/long-term memory architecture |
| 14 | **Semantic drift monitoring** | Early detection of routing degradation | High | Query distribution tracking + alerting |
| 15 | **RouteLLM learned routing** | 85% cost reduction potential | High | Train router model, integrate with Thompson Sampling |

### Quick Wins (Implement Immediately)

1. **DSPy prompt optimization** on system prompts (40-60% token reduction, zero quality loss)
2. **Preferential routing to Groq** for latency-sensitive tasks (already free, 750 tok/s)
3. **Extractive compression** on RAG contexts (can actually improve accuracy by filtering noise)
4. **Synthetic data collection** during normal cascading (save Opus/GPT-4o outputs for future distillation)

---

## 8. References

### Knowledge Distillation

- [Chain-of-Thought Curriculum Distillation (CoTCD)](https://dl.acm.org/doi/10.1145/3775073.3775200) -- ACM 2025
- [Adaptive Chain-of-Thought Distillation (ACoTD)](https://www.mdpi.com/2227-7390/13/22/3646) -- MDPI Mathematics 2024
- [Unveiling Key Factors for CoT Distillation](https://arxiv.org/html/2502.18001v1) -- ACL Findings 2025
- [Survey on Symbolic Knowledge Distillation of LLMs](https://www.computer.org/csdl/journal/ai/2024/12/10597596/1YBtvHkLRqU) -- IEEE 2024
- [Symbolic Chain-of-Thought Distillation (SCoTD)](https://www.semanticscholar.org/paper/Symbolic-Chain-of-Thought-Distillation:-Small-Can-Li-Hessel/7a6a298efb965ce9a351a3212f6f536e94dbbb03) -- Semantic Scholar
- [Model Distillation for LLMs](https://redis.io/blog/model-distillation-llm-guide/) -- Redis 2026
- [Distillation with Programmatic Data Curation](https://www.tensorzero.com/blog/distillation-programmatic-data-curation-smarter-llms-5-30x-cheaper-inference/) -- TensorZero
- [LLM Distillation Explained](https://www.adaline.ai/blog/llm-distillation-explained) -- Adaline AI

### Inference Optimization

- [Speculative Decoding: 2-3x Speedup Guide](https://introl.com/blog/speculative-decoding-llm-inference-speedup-guide-2025) -- Introl 2025
- [TurboSpec: Efficient LLM System with Speculative Decoding](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2025/EECS-2025-224.html) -- UC Berkeley 2025
- [Batch Speculative Decoding Done Right](https://arxiv.org/html/2510.22876v1) -- ArXiv
- [DeepSpec/DSpark: Speculative Decoding for V4](https://www.techtimes.com/articles/319236/20260628/deepseek-releases-dspark-speculative-decoding-makes-v4-85-percent-faster.htm) -- TechTimes 2026
- [Red Hat Speculators](https://developers.redhat.com/articles/2025/11/19/speculators-standardized-production-ready-speculative-decoding) -- Red Hat Developer 2025
- [Mastering LLM Techniques: Inference Optimization](https://developer.nvidia.com/blog/mastering-llm-techniques-inference-optimization/) -- NVIDIA
- [Cerebras CS-3 vs Groq LPU](https://www.cerebras.ai/blog/cerebras-cs-3-vs-groq-lpu) -- Cerebras
- [LLM Inference Optimization Techniques](https://www.clarifai.com/blog/llm-inference-optimization/) -- Clarifai
- [Speculative Decoding: How It Works](https://redis.io/blog/speculative-decoding-llm/) -- Redis

### RAG Advances

- [RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval](https://ragflow.io/blog/the-rise-and-evolution-of-rag-in-2024-a-year-in-review) -- ICLR 2024
- [Self-RAG: Learning to Retrieve, Generate, and Critique](https://arxiv.org/html/2506.00054v1) -- ICLR 2024 Oral
- [12 Advanced RAG Techniques](https://atlan.com/know/advanced-rag-techniques/) -- Atlan 2026
- [Beyond Vector Search: 5 Next-Gen RAG Strategies](https://machinelearningmastery.com/beyond-vector-search-5-next-gen-rag-retrieval-strategies/) -- MLMastery
- [RAG at the Crossroads: Mid-2025 Reflections](https://ragflow.io/blog/rag-at-the-crossroads-mid-2025-reflections-on-ai-evolution) -- RAGFlow
- [RAG Techniques Repository](https://github.com/NirDiamant/RAG_Techniques) -- GitHub (NirDiamant)
- [Hybrid RAG Systems for Knowledge-Intensive Tasks](https://medium.com/@adnanmasood/hybrid-retrieval-augmented-generation-systems-for-knowledge-intensive-tasks-10347cbe83ab) -- Medium

### Evaluation Frameworks

- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685) -- NeurIPS 2023
- [Arena-Hard Pipeline](https://www.lmsys.org/blog/2024-04-19-arena-hard/) -- LMSYS 2024
- [WildBench: Benchmarking LLMs](https://proceedings.iclr.cc/paper_files/paper/2025/file/771155abaae744e08576f1f3b4b7ac0d-Paper-Conference.pdf) -- ICLR 2025
- [LLM Evaluation Framework Guide](https://www.meta-intelligence.tech/en/insight-llm-evaluation) -- Meta Intelligence 2026
- [Awesome LLM Evaluation](https://alopatenko.github.io/LLMEvaluation/) -- GitHub

### Cost Optimization

- [LLMLingua: Compressing Prompts](https://arxiv.org/html/2310.05736v2) -- EMNLP 2023
- [LLMLingua-2: Data Distillation for Prompt Compression](https://llmlingua.com/llmlingua2.html) -- ACL 2024
- [LLMLingua GitHub](https://github.com/microsoft/LLMLingua) -- Microsoft
- [Context Compression Saves 60-80%](https://thread-transfer.com/blog/2025-03-07-context-compression-cost-savings/) -- Thread Transfer
- [Prompt Compression Guide](https://neuraltrust.ai/blog/prompt-compression-guide) -- NeuralTrust
- [FrugalGPT](https://arxiv.org/abs/2305.05176) -- TMLR 2024
- [RouteLLM: Router-based Cascades](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades) -- ICLR 2025
- [Cluster, Route, Escalate](https://arxiv.org/html/2606.27457) -- ArXiv 2026
- [Dynamic Model Routing and Cascading Survey](https://arxiv.org/html/2603.04445v2) -- ArXiv 2025
- [FrugalGPT Implementation](https://portkey.ai/blog/implementing-frugalgpt-smarter-llm-usage-for-lower-costs/) -- Portkey
