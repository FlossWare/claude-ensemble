# Autonomous Discovery Round 2: Advanced Orchestration Techniques

**Date:** 2026-07-26
**Researcher:** Claude Opus 4.6 (autonomous research agent)
**Scope:** 4 research areas, 12 techniques evaluated, 30+ papers reviewed
**System Context:** Distributed LLM orchestration with Thompson Sampling, Contextual Retrieval, Mixture of Agents, LLM Cascading, LLM-Guided Evolution, RAG with pgvector, 200+ API models, 8-worker fleet

---

## Area 1: RLAIF / Constitutional AI Patterns

### Background

RLAIF (Reinforcement Learning from AI Feedback) replaces expensive human feedback with AI-generated preference signals. Originally developed by Anthropic as Constitutional AI (2022), the field has matured significantly in 2024-2025. Our system already does multi-AI consensus voting -- RLAIF techniques go further by structuring this feedback into systematic quality improvement loops.

**Key difference from our existing multi-AI consensus:** Our current system asks multiple models for answers and picks the best one (selection). RLAIF/Constitutional patterns instead use AI feedback to *improve* outputs iteratively (refinement). Selection picks the best existing answer; refinement generates better answers that did not exist before.

---

### Technique 1.1: Multi-Agent Verification (MAV) with Aspect Verifiers

**Paper:** "Multi-Agent Verification: Scaling Test-Time Compute with Multiple Verifiers" (Lifshitz, McIlraith, Du, Feb 2025) -- COLM 2025 / ICLR 2025 VerifAI Workshop
**Code:** https://github.com/Shalev-Lifshitz/MultiAgentVerification

**What it is:** Instead of a single reward model or a single LLM-as-judge, MAV uses N off-the-shelf LLMs as "aspect verifiers" -- each prompted to check a specific quality dimension (correctness, completeness, code style, security, etc.) with a binary True/False vote. Candidate outputs are scored by total approval votes across all verifiers.

**The BoN-MAV Algorithm:**
1. Generate N candidate outputs from a generator model
2. Each of M aspect verifiers gives binary True/False approval to each candidate
3. Select candidate with highest total approvals (simple sum voting)

**Key findings:**
- Outperforms self-consistency and reward model verification on most benchmarks
- Demonstrates weak-to-strong generalization: combining weak verifiers improves even stronger LLMs
- Self-improvement: same model can both generate and verify (different aspects)
- Up to 10% accuracy gains for large models by increasing verifier count
- No training required -- purely prompt-based, uses off-the-shelf models

**Implementation complexity:** LOW (1-2 days)
- We already have multi-model dispatch infrastructure
- Each aspect verifier is just a model + a specialized prompt
- Binary voting with sum aggregation is trivial to implement
- Natural extension of our existing arbiter pattern

**Expected benefit:**
- Structured quality signals instead of unstructured consensus
- Catches different failure modes (security verifier vs. correctness verifier vs. style verifier)
- Quantitative quality scores per dimension for analytics/learning
- Better than our current "ask all models, arbiter picks best" because verifiers focus on orthogonal aspects

**Integration with existing system:**
- Bolt onto code review workflow: define aspect verifiers for {correctness, security, performance, maintainability, test coverage}
- Bolt onto research workflow: define aspect verifiers for {factual accuracy, completeness, source quality, relevance, logical coherence}
- Feed MAV scores into Thompson Sampling to track which models are best at which verification aspects
- Store aspect scores in PostgreSQL for long-term model capability profiling

---

### Technique 1.2: Automated Constitution Discovery (IterAlign)

**Paper:** "IterAlign: Iterative Constitutional Alignment of Large Language Models" (Chen et al., 2024) -- NAACL 2024
**Code:** https://github.com/xiusic/IterAlign

**What it is:** Instead of manually writing quality rules/constitutions, IterAlign automatically discovers them through a red-teaming cycle:
1. Red-team the system to find failure modes (adversarial probing)
2. Use a stronger "oracle" LLM to analyze failures and propose new rules/principles
3. Apply rules as self-reflection prompts for the base model to self-correct
4. Iterate: new rules target gaps from the previous round

**Key results:**
- 13.5% improvement in harmlessness metrics using automatically discovered principles
- No human-written rules needed -- the system discovers its own quality criteria
- Iterative process covers an expanding range of failure modes over time

**Implementation complexity:** MEDIUM (3-5 days)
- Build a red-teaming pipeline: send adversarial/edge-case queries to the system
- Collect outputs that fail quality checks (using existing arbiter disagreement as signal)
- Run a strong model (Opus/GPT-4o) to analyze failures and generate rules
- Store discovered rules in PostgreSQL, apply as system prompts in future runs
- Iterate periodically (daily/weekly cron) to discover new rules

**Expected benefit:**
- Self-improving quality criteria without manual rule-writing
- Catches failure modes we did not think of in advance
- Rules accumulate over time -- the system gets better at catching its own weaknesses
- Discovered rules can be domain-specific (code review rules, research rules, etc.)

**Integration with existing system:**
- Use arbiter disagreement logs as a natural red-teaming signal (queries where models disagreed strongly = potential quality gaps)
- Store discovered constitutions in `learning.constitutions` table
- Apply constitutions as system prompt prefixes in workflow agents
- Track which constitutions improve outcomes via Thompson Sampling

---

### Technique 1.3: Structured Self-Refinement with External Verification

**Paper:** "Self-Refine: Iterative Refinement with Self-Feedback" (Madaan et al., 2023/2024) -- NeurIPS 2023, widely cited/extended in 2024-2025
**Critical counterpoint:** "When Can LLMs Actually Correct Their Own Mistakes?" (MIT Press TACL, 2024)

**What it is:** A 3-step loop: (1) Generate initial output, (2) Critique the output against specific criteria, (3) Revise based on critique. Repeat until convergence or max iterations.

**Critical insight from 2024 research:** Pure self-critique (same model critiques itself) is unreliable for reasoning tasks due to self-bias. But cross-model critique (different model critiques) and tool-augmented critique (compiler errors, test failures, search results) are highly effective.

**Our adaptation -- Cross-Model Refinement Loop:**
1. Model A generates initial output
2. Model B (different architecture/provider) critiques against aspect-specific rubric
3. Model A revises based on critique
4. Model C (third model) verifies improvement
5. If improved, accept; if not, try one more round or fall back

**Key 2025 advancement -- ProActive Self-Refinement (PASR):**
- Rather than refining only after full output, PASR enables in-process decisions about when to refine
- 42% token savings and +8.2% accuracy over post-hoc refinement
- Practical insight: biggest improvements come in first 1-2 refinement rounds; diminishing returns after

**Implementation complexity:** MEDIUM (3-5 days)
- Extend workflow agent pattern with a critique step between generation and acceptance
- Use a different model family for critique than for generation (our zero-overlap panel principle already supports this)
- Add tool-augmented verification where possible (run code, check URLs, verify math)
- Limit to 2 refinement rounds (research shows diminishing returns beyond this)

**Expected benefit:**
- ~20% average improvement in output quality (Self-Refine paper finding)
- Particularly effective for code generation (compiler feedback) and factual research (search verification)
- Complementary to our existing consensus -- consensus picks the best from N outputs, refinement makes each output better

**Integration with existing system:**
- Add as optional phase in deep-research and code-review workflows
- Use review panel models as critics, different from generation panel (already follows our zero-overlap principle)
- Feed refinement improvement rates into Thompson Sampling (which model pairs produce the best critique-revise cycles?)
- Track refinement iterations and quality deltas in workflow storage

---

## Area 2: Active Learning for Model Routing

### Background

Our Thompson Sampling router passively learns from outcomes: a model succeeds or fails, and we update its Beta distribution. Active Learning takes a deliberate approach: identify queries where the router is most uncertain, and actively test multiple models on those specific queries to learn faster.

**Key research direction (2024-2025):** Uncertainty-based LLM routing has become a major research area, with papers at ICLR 2025, COLM 2024, EMNLP 2025, and multiple benchmarks (RouterBench).

---

### Technique 2.1: Uncertainty-Driven Exploration Budget

**Papers:**
- "Confident or Seek Stronger: Exploring Uncertainty-Based On-device LLM Routing" (Chuang et al., 2025)
- "Leveraging Uncertainty Estimation for Efficient LLM Routing" (arXiv, Feb 2025)
- "Learning to Route LLMs with Confidence Tokens" (Self-REF, ICML 2025)

**What it is:** Allocate an "exploration budget" -- a percentage of queries (e.g., 10-20%) where the router deliberately tests multiple models instead of routing to the Thompson Sampling winner. Focus this budget on queries where router confidence is lowest.

**Uncertainty estimation methods for black-box API models (what we have):**
1. **Consistency-based (best for our setup):** Generate N responses from the same model; measure agreement. High disagreement = high uncertainty about this model's ability on this query type.
2. **Verbalized confidence:** Ask the model "How confident are you? (1-10)". Less reliable but cheapest.
3. **Cross-model disagreement:** If models A and B strongly disagree, the router should be uncertain about which is right -- perfect exploration candidate.

**The Exploration Protocol:**
1. For each incoming query, estimate router confidence (Thompson Sampling posterior variance)
2. If confidence is below threshold, enter "exploration mode":
   - Send query to top-K models (not just the Thompson winner)
   - Compare outputs using MAV aspect verifiers (Technique 1.1)
   - Update Thompson Sampling posteriors for ALL K models based on results
3. If confidence is above threshold, route normally (exploitation)

**Connection to Thompson Sampling:**
- Thompson Sampling already balances exploration/exploitation via random sampling from posteriors
- But TS explores uniformly across all uncertainty -- it does not focus exploration on the most informative queries
- Active Learning adds *targeted* exploration: focus extra compute on queries where learning is most valuable
- This is like the Upper Confidence Bound (UCB) approach but applied at query-level instead of arm-level

**Implementation complexity:** MEDIUM (3-5 days)
- Compute posterior variance from existing Thompson Sampling Beta distributions (trivial math)
- Define exploration budget as a configurable percentage
- When in exploration mode, dispatch to K models instead of 1
- Use existing multi-model dispatch infrastructure
- Feed all K results back into Thompson Sampling updates

**Expected benefit:**
- Faster convergence of Thompson Sampling posteriors (learn more from each exploration query)
- Better model selection on edge cases / unusual query types
- Quantified confidence for every routing decision (useful for fallback logic)
- Can be cost-controlled: exploration budget caps the extra API spend

**Integration with existing system:**
- Wraps around Thompson Sampling, does not replace it
- Uses existing fleet dispatch for multi-model queries
- Exploration results feed into `learning.strategy_performance` table
- Exploration budget can be tuned per domain (higher for new/unfamiliar query types)

---

### Technique 2.2: AutoMix Self-Verification Cascading

**Paper:** "AutoMix: Automatically Mixing Language Models" (Aggarwal, Madaan et al., 2024) -- NeurIPS 2024
**Code:** https://github.com/automix-llm/automix

**What it is:** A lightweight self-verification cascade that routes queries between small/cheap and large/expensive models:
1. Small model generates an answer
2. Small model self-verifies: "Given [question] and [answer], is this answer correct? Yes/No/Unsure"
3. If self-verification passes, accept (cheap path)
4. If self-verification fails or is uncertain, route to larger model (expensive path)
5. POMDP-based router optimizes the confidence threshold for routing

**Key results:**
- 50%+ cost reduction for comparable performance
- Router trained with as few as 50 labeled samples
- Works with black-box API models (no weight access needed)
- Self-verification formulated as an entailment problem: "Does [answer] entail the correct response to [question]?"

**Our adaptation -- Tiered Verification Cascade:**
1. Fast/cheap model (Haiku, Groq Llama) generates initial answer
2. Same model self-verifies (few-shot entailment check)
3. If confident: accept (saves 80% of API cost on easy queries)
4. If uncertain: route to medium model (Sonnet, Gemini Pro)
5. If still uncertain: route to strong model (Opus, GPT-4o)
6. At each tier, track self-verification accuracy to calibrate confidence thresholds

**Implementation complexity:** LOW-MEDIUM (2-3 days)
- We already have LLM cascading infrastructure
- Self-verification is a single additional API call with a templated prompt
- POMDP router can start simple (threshold-based) and evolve later
- Calibration data comes from our existing workflow logs

**Expected benefit:**
- Dramatic cost reduction (50%+ per AutoMix paper) while maintaining quality
- Faster response times on easy queries (single cheap model call)
- Graceful fallback to stronger models on hard queries
- Works with our existing cascade infrastructure -- this is a smarter routing layer on top

**Integration with existing system:**
- Enhances existing LLM cascading with an intelligent routing decision
- Self-verification accuracy feeds into Thompson Sampling (which models self-verify well?)
- POMDP state can incorporate query type embeddings from pgvector for context-aware routing
- Store cascade decisions and outcomes in `workflow.worker_results` for analysis

---

### Technique 2.3: Semantic Entropy for Routing Confidence

**Papers:**
- "Do LLMs Estimate Uncertainty Well?" (ICLR 2025)
- "On Verbalized Confidence Scores for LLMs" (Dec 2024)
- RouterBench (Hu et al., 2024) -- Benchmark for routing methods

**What it is:** Instead of asking a model "are you confident?", measure confidence by sampling N responses to the same query and computing semantic entropy across responses. If all N responses are semantically similar, the model is confident. If responses vary widely, the model is uncertain.

**Practical implementation:**
1. For a query, sample 3-5 responses from the candidate model (using temperature > 0)
2. Embed each response using our existing pgvector embeddings
3. Compute pairwise cosine similarity
4. If average similarity is high (>0.85): model is confident, accept the response
5. If average similarity is low (<0.70): model is uncertain, route to a different/stronger model

**Key advantage over verbalized confidence:** Research shows models are systematically overconfident when asked to self-assess (72.9% average self-reported confidence vs. 50% rational baseline). Semantic entropy measures actual response consistency, which is a more reliable signal.

**Implementation complexity:** LOW (1-2 days)
- We already have pgvector embeddings infrastructure
- Sampling multiple responses is a standard API parameter (n=5)
- Cosine similarity computation is trivial
- Threshold calibration from historical data

**Expected benefit:**
- More reliable confidence estimates than self-reported confidence
- Natural integration with Thompson Sampling (use semantic entropy as a Bayesian prior)
- Identifies "uncertain but overconfident" models before they produce wrong answers
- Zero additional model access needed -- works with any black-box API

**Integration with existing system:**
- Use existing embedding pipeline for response similarity
- Integrate with Thompson Sampling as an additional signal
- Store confidence scores in `monitoring.execution_summary`
- Use as input to exploration budget decisions (Technique 2.1)

---

## Area 3: Self-Play and Debate Protocols

### Background

AI debate is a scalable oversight mechanism: two models argue opposing positions, and a judge (possibly weaker) picks the winner. The theory is that finding flaws in an argument is easier than constructing a flawless argument, so even weak judges can benefit from structured debate between strong models.

**Critical finding (NeurIPS 2025 Spotlight):** "Debate or Vote" (Choi, Zhu, Li, 2025) proved that majority voting alone accounts for most performance gains attributed to multi-agent debate. Debate induces a martingale over belief trajectories -- it does not improve *expected* correctness. However, debate *does* help in specific scenarios: information asymmetry, adversarial detection, and weak-to-strong oversight.

**Implication for our system:** We should NOT replace our consensus voting with debate (voting works). Instead, we should ADD debate for specific high-value tasks where adversarial probing matters: security review, adversarial red-teaming, and catching subtle bugs.

---

### Technique 3.1: Adversarial Code Review Debate Protocol

**Papers/Tools:**
- "Adversarial Review: Cooperative Code Review through Structured Disagreement" (OpenReview, 2025)
- GitHub: https://github.com/alecnielsen/adversarial-review (Claude + GPT Codex adversarial review)
- "Training Language Models to Win Debates with Self-Play Improves Judge Accuracy" (Arnesen et al., Sep 2024)

**What it is:** Instead of N models independently reviewing code (our current approach), structure the review as an adversarial debate:
- **Advocate:** "This code is correct and well-designed. Here is why..."
- **Challenger:** "This code has critical issues. Here is why..."
- **Judge:** Reads both arguments, asks clarifying questions, renders verdict

**The 3-Round Protocol:**
1. **Round 1 (Independent):** Both Advocate and Challenger independently analyze the code
2. **Round 2 (Cross-Examination):** Each reads the other's analysis and responds to specific points, trying to rebut or support claims
3. **Round 3 (Final Arguments):** Each presents consolidated findings addressing all rebuttals
4. **Judgment:** Judge model reads all 3 rounds, produces structured verdict with confidence scores

**Why this is better than independent review for certain tasks:**
- A model asked to defend code and a model asked to attack it explore different parts of the problem
- Disagreement between advocate and challenger surfaces issues neither would find alone
- Code review is an ideal fit: finding issues and filtering false positives are in tension (one agent cannot serve both honestly)
- 4% absolute increase in judge accuracy with debate-trained models (Arnesen et al.)

**Implementation complexity:** MEDIUM (3-5 days)
- Define Advocate and Challenger system prompts (role assignments)
- Implement 3-round message passing between agents
- Judge evaluates the full debate transcript
- Different model families for each role (zero overlap with our existing principle)

**Expected benefit:**
- Catches subtle bugs that consensus review misses (adversarial pressure)
- Reduces false positives (cross-examination filters incorrect claims)
- Produces richer, more detailed review output (arguments + rebuttals)
- Works as a complement to our existing consensus review for high-stakes code

**Integration with existing system:**
- Add as an optional "deep review" mode in code-review-and-solve.js workflow
- Use review panel models as Challengers, different panel as Advocates (our zero-overlap principle)
- Judge can be the current arbiter model
- Track debate outcomes (did debate find issues that consensus missed?) in workflow storage
- Feed win rates into Thompson Sampling (which models are best advocates? best challengers?)

---

### Technique 3.2: Structured Oversight via Weak-to-Strong Debate

**Papers:**
- "On Scalable Oversight with Weak LLMs Judging Strong LLMs" (Kenton et al., NeurIPS 2024)
- "Debate Helps Weak-to-Strong Generalization" (arXiv:2501.13124, Jan 2025)
- "Scaling Laws For Scalable Oversight" (arXiv:2504.18530, Apr 2025)

**What it is:** Use debate between strong models to help a weaker (cheaper) model make better judgments. Two strong models argue opposing positions on a complex question, and a weak model (acting as judge) picks the winner. The debate structure compensates for the judge's limited capability.

**Key findings from NeurIPS 2024:**
- Debate outperforms consultancy (single model advising a judge) across all tasks
- Stronger debater models increase judge accuracy
- Information asymmetry scenarios benefit most from debate
- Weak judges can supervise strong models through structured debate

**Our adaptation -- Cost-Efficient Quality Gates:**
1. Two strong models (Opus, GPT-4o) debate whether a complex output is correct
2. A cheap model (Haiku, Llama-8B via Groq) judges the debate
3. The cheap judge with debate context makes better decisions than the cheap judge alone
4. This is cheaper than having the strong models directly evaluate, because debate is a one-time cost that the cheap judge can leverage repeatedly

**Implementation complexity:** MEDIUM (3-5 days)
- Reuses debate infrastructure from Technique 3.1
- Key addition: using cheap models as judges with debate transcripts as context
- Track whether weak-judge-with-debate matches strong-judge-without-debate
- Calibrate which query types benefit from debate overhead vs. direct strong evaluation

**Expected benefit:**
- Significant cost reduction on quality evaluation (cheap judge + debate < expensive direct evaluation)
- Better oversight on complex tasks where single-model evaluation is unreliable
- Validates whether our cheap fleet workers (pi-01, pi-02) can serve as effective judges with debate context
- Alignment with latest AI safety research direction (scalable oversight)

**Integration with existing system:**
- Deploy debate infrastructure on strong workers (server-01/02/03), judging on cheap workers
- Store debate transcripts for analysis and training data
- Compare weak-judge-with-debate vs. strong-judge-without-debate in A/B tests
- Track quality correlation in `monitoring.execution_summary`

---

### Technique 3.3: PROClaim Courtroom-Style Verification

**Reference:** PROClaim (Hugging Face, 2025) -- courtroom-style multi-agent verification

**What it is:** A courtroom metaphor for verification: specialized roles (Plaintiff, Defense, Judge) with Progressive RAG to dynamically expand the evidence pool during deliberation. The key innovation is that evidence is gathered *during* the debate, not before.

**Protocol:**
1. **Plaintiff** (model A): Presents the claim with supporting evidence
2. **Defense** (model B): Challenges the claim, presents counter-evidence
3. **Progressive RAG:** Both sides can request additional evidence retrieval during the debate
4. **Judge** (model C): Evaluates arguments, evidence quality, and renders verdict

**Key result:** 81.7% accuracy in zero-shot verification, outperforming standard multi-agent debate by 10 percentage points on claim verification benchmarks.

**Implementation complexity:** MEDIUM-HIGH (5-7 days)
- Requires debate infrastructure + RAG integration
- Progressive evidence retrieval adds complexity
- Most valuable for research verification and fact-checking workflows

**Expected benefit:**
- Substantial accuracy improvement on factual verification tasks
- Dynamic evidence gathering prevents pre-commitment bias
- Natural fit for our deep-research workflows where factual accuracy matters

**Integration with existing system:**
- Extends deep-research workflow with verification phase
- Uses existing pgvector RAG for evidence retrieval during debate
- Plaintiff/Defense use different model families
- Evidence retrieval triggers can be stored for analysis

---

## Area 4: Speculative Decoding / Parallel Generation Patterns

### Background

Speculative decoding at the model level (draft tokens + verify) is well-established. But the same *principle* can be applied at the orchestration level: generate with fast/cheap models, verify with strong/expensive models. Our existing LLM cascading is sequential (try cheap, fall back to expensive). The parallel approach runs them simultaneously.

---

### Technique 4.1: Orchestration-Level Speculative Cascade

**Papers:**
- "Speculative Cascades" (Google Research, 2025) -- hybrid cascading + speculative execution
- M1-Parallel (Jul 2025, arXiv:2507.08944) -- parallel agent teams with early termination

**What it is:** Apply the speculative decoding principle at the orchestration level:
1. Send query to fast/cheap model AND strong/expensive model simultaneously
2. Fast model returns first (typically 2-5x faster)
3. Strong model verifies the fast model's output
4. If verified: accept fast answer, cancel remaining strong computation (if streaming API supports it)
5. If not verified: use strong model's answer instead

**Key difference from our current cascade:**
- Current cascade: try cheap first, WAIT for result, THEN decide whether to try expensive (sequential, additive latency)
- Speculative cascade: try BOTH in parallel, strong model verifies cheap answer (parallel, latency of max not sum)

**M1-Parallel findings:**
- 2.2x speedup with early termination while preserving accuracy
- Run N parallel agent teams, first to finish wins
- No benefit from encouraging diverse execution plans -- repeated sampling is sufficient

**Implementation complexity:** LOW-MEDIUM (2-3 days)
- Use existing parallel dispatch infrastructure
- Send to fast model (Groq Llama -- sub-second latency) and strong model (Opus/Sonnet) simultaneously
- Strong model prompt includes: "Verify this answer: [fast_answer]. Is it correct? If yes, confirm. If no, provide correct answer."
- If strong model confirms: use fast answer (arrived first)
- If strong model corrects: use strong answer

**Expected benefit:**
- Latency reduction: get fast-model speed on easy queries while maintaining strong-model quality
- Cost optimization: strong model verification call is shorter than full generation (just confirm/deny)
- Works with existing API infrastructure -- no special streaming support needed
- ~60-70% of queries may be confirmable (easy queries), saving significant time

**Integration with existing system:**
- Enhances LLM cascading with parallel execution
- Verification outcomes feed Thompson Sampling (track which fast models produce verifiable outputs for which query types)
- Fast model + strong verifier pairs can be optimized over time
- Store verification rates in `monitoring.execution_summary`

---

### Technique 4.2: Parallel Race with First-Good-Result Termination

**Papers:**
- M1-Parallel (Jul 2025, arXiv:2507.08944) -- 2.2x speedup with early termination
- ParaThinker: "First-Finish" (Sep 2025, arXiv:2509.04475) -- best accuracy + latency among parallel strategies

**What it is:** For latency-critical tasks, dispatch the same query to N models simultaneously and take the first result that passes a quality gate:
1. Send query to 3-5 models in parallel (diverse providers for latency diversity)
2. As each result arrives, run it through a quick quality check (MAV aspect verifiers from Technique 1.1)
3. First result that passes all quality checks is accepted
4. Cancel remaining pending requests (or let them complete for learning data)

**Quality gate options:**
- Simple: Does the response contain the expected format/structure?
- Medium: Quick LLM-as-judge scoring (single fast model)
- Full: MAV aspect verification (multiple verifiers)

**ParaThinker "First-Finish" findings:**
- First-Finish outperformed Last-Finish and Half-Finish strategies in both accuracy and latency
- +12.3% accuracy over sequential baselines on math benchmarks
- Diversity of parallel paths naturally explores different solution approaches

**Implementation complexity:** LOW (1-2 days)
- We already have parallel dispatch infrastructure
- Quality gate can start simple (format check) and evolve (add MAV)
- Use Promise.race() or similar for first-result selection
- Remaining results provide free learning data

**Expected benefit:**
- Dramatic latency reduction (latency of fastest model, not slowest)
- Quality maintained via quality gate
- Free exploration data from "losing" responses (update Thompson Sampling)
- Natural fit for user-facing queries where response time matters

**Integration with existing system:**
- Add as a "race mode" option for latency-sensitive workflows
- All results (winner and losers) feed into Thompson Sampling
- Quality gate reuses MAV infrastructure (Technique 1.1)
- Track latency distributions per model/provider in `monitoring.execution_summary`

---

### Technique 4.3: Speculative Action Pipelining for Multi-Step Workflows

**Papers:**
- PASTE: "Parallelizing Tool Execution and LLM Generation" (Jun 2026, arXiv:2603.18897)
- PipeSpec: Hierarchical pipelining for multi-stage verification

**What it is:** In multi-step workflows (research -> analyze -> synthesize), start the next step speculatively before the current step finishes:
1. Step 1 (Research) starts generating output
2. As soon as Step 1 produces a partial result (first few paragraphs), speculatively start Step 2 (Analysis) with that partial input
3. If Step 1's final output is consistent with the partial result used to start Step 2, Step 2 is ahead of schedule
4. If Step 1's final output diverges, discard speculative Step 2 and restart with correct input

**Pipeline structure for deep-research workflow:**
```
Time -->
Step 1: [====Research====]
Step 2:        [===Speculative Analysis===] --> if Step 1 consistent: KEEP
Step 3:              [===Speculative Synthesis===] --> verify when Step 2 done
```

**Implementation complexity:** HIGH (5-7 days)
- Requires partial result streaming and consistency checking
- Speculative execution logic is complex (when to start, when to discard)
- Most beneficial for long multi-step workflows
- Needs careful cost analysis (speculative work may be wasted)

**Expected benefit:**
- Significant end-to-end latency reduction for multi-step workflows
- Most valuable for deep-research (3-5 phase) workflows
- Progressive refinement: each step can refine speculative output from prior step

**Integration with existing system:**
- Applies to existing multi-phase workflows (deep-research, code-review-and-solve)
- Requires streaming API support (available from Anthropic, OpenAI, Google)
- Speculation waste rate tracked in `workflow.phases` for optimization
- Most advanced technique -- implement after simpler parallel patterns prove value

---

## Cross-Cutting Analysis: How Techniques Interact

```
                      MAV Aspect Verifiers (1.1)
                     /          |            \
                    /           |             \
  Self-Refinement (1.3)   Quality Gate    Routing Confidence
        |                 for Race (4.2)    Signal (2.1)
        |                      |                |
  Debate Protocol (3.1)  Parallel Race (4.2)  Thompson Sampling
        |                      |                |
  Constitution Discovery  Speculative       AutoMix
  (1.2) -- feeds rules    Cascade (4.1)    Cascade (2.2)
  back into all verifiers
```

**Key synergies:**
1. MAV (1.1) provides quality signals for EVERYTHING else -- race quality gates, routing confidence, refinement evaluation
2. Thompson Sampling connects to ALL techniques -- every technique produces data that improves routing
3. Constitution Discovery (1.2) improves MAV verifier prompts over time
4. Parallel Race (4.2) and Speculative Cascade (4.1) share infrastructure but serve different needs (latency vs. cost)
5. Debate (3.1) and Self-Refinement (1.3) share the cross-model critique infrastructure

---

## Top 5 Most Actionable Techniques (Ranked by Impact/Effort Ratio)

### Rank 1: Multi-Agent Verification with Aspect Verifiers (Technique 1.1)

**Priority:** IMPLEMENT FIRST
**Effort:** 1-2 days
**Impact:** HIGH -- foundation for 4 other techniques
**Why #1:** Lowest implementation effort, highest reuse value. MAV provides structured quality signals that feed into race quality gates (4.2), routing confidence (2.1), refinement evaluation (1.3), and debate judging (3.1). Every other technique gets better when MAV exists. Off-the-shelf models with specialized prompts -- no training, no new infrastructure.

**Implementation sketch:**
- Define 5-7 aspect verifier prompts per domain (code review: correctness, security, performance, style, tests; research: accuracy, completeness, sources, logic, relevance)
- Wrap existing multi-model dispatch to run aspect verifiers in parallel
- Aggregate binary votes with simple sum scoring
- Store per-aspect scores in PostgreSQL for analytics

---

### Rank 2: Parallel Race with First-Good-Result (Technique 4.2)

**Priority:** IMPLEMENT SECOND
**Effort:** 1-2 days
**Impact:** HIGH -- immediate latency improvement
**Why #2:** We already have parallel dispatch. Adding a quality gate (using MAV from #1) and first-result selection is trivial. Immediate, measurable latency reduction. All "losing" responses provide free exploration data for Thompson Sampling. Most impactful for latency-sensitive workflows.

**Implementation sketch:**
- Dispatch to 3-5 models in parallel using existing infrastructure
- Quick quality check on each arriving result (MAV aspect verifiers)
- Accept first result passing quality threshold
- Store all results for Thompson Sampling updates

---

### Rank 3: Uncertainty-Driven Exploration Budget (Technique 2.1)

**Priority:** IMPLEMENT THIRD
**Effort:** 3-5 days
**Impact:** MEDIUM-HIGH -- accelerates Thompson Sampling convergence
**Why #3:** Thompson Sampling already works but explores uniformly. Targeted exploration on uncertain queries makes every exploration API call maximally informative. Moderate implementation effort (compute posterior variance, define exploration threshold). The exploration budget parameter provides direct cost control.

**Implementation sketch:**
- Compute Beta distribution variance for each model-task pair (trivial math)
- When variance exceeds threshold, enter exploration mode: dispatch to top-K models
- Use MAV (from #1) to evaluate all K results
- Update Thompson Sampling posteriors for all K models
- Configurable exploration budget (% of queries)

---

### Rank 4: Orchestration-Level Speculative Cascade (Technique 4.1)

**Priority:** IMPLEMENT FOURTH
**Effort:** 2-3 days
**Impact:** MEDIUM-HIGH -- latency + cost optimization
**Why #4:** Upgrades our sequential cascade to parallel. On easy queries (~60-70% of workload), the fast model answer is verified by the strong model and accepted at fast-model latency. On hard queries, the strong model answer is used directly. Moderate effort, clear cost/latency benefit. Requires strong model verification prompt design.

**Implementation sketch:**
- Parallel dispatch: fast model (Groq Llama, sub-second) + strong model (Opus/Sonnet)
- Strong model prompt: "Verify: [fast_answer]. Correct? If no, provide correct answer."
- If verified: use fast answer (arrived first)
- If not: use strong answer
- Track verification rates per model pair

---

### Rank 5: Adversarial Code Review Debate (Technique 3.1)

**Priority:** IMPLEMENT FIFTH
**Effort:** 3-5 days
**Impact:** MEDIUM -- targeted quality improvement for code review
**Why #5:** Not a replacement for consensus (voting works better for most tasks per NeurIPS 2025 findings), but a valuable addition for high-stakes code review where adversarial probing catches subtle bugs. Requires debate infrastructure (3-round message passing), but role-assignment prompts are straightforward. Most valuable when combined with MAV for debate judging.

**Implementation sketch:**
- Define Advocate and Challenger system prompts
- 3-round debate: independent analysis -> cross-examination -> final arguments
- Judge (different model) evaluates full debate transcript
- Add as optional "deep review" mode for high-stakes PRs
- Track debate vs. consensus finding rates for ROI measurement

---

## Techniques NOT Recommended (with reasoning)

### Automated Constitution Discovery (1.2)
**Verdict:** Defer -- valuable but dependent on having enough failure data to analyze. Wait until MAV and debate are generating structured quality data, then mine that data for constitution discovery. Implement in Round 3.

### Structured Self-Refinement (1.3)
**Verdict:** Defer -- research shows pure self-refinement has diminishing returns and self-bias risks. The cross-model refinement variant is valuable but requires MAV infrastructure first. Implement after MAV (Technique 1.1) is proven.

### Weak-to-Strong Debate Oversight (3.2)
**Verdict:** Defer -- interesting for cost reduction but requires debate infrastructure (3.1) first. The research is promising but our cheap workers may not be capable enough to judge effectively even with debate context. Validate with Technique 3.1 first.

### PROClaim Courtroom Verification (3.3)
**Verdict:** Defer -- high complexity, requires RAG + debate integration. Most valuable for fact-checking workflows that we have not built yet. Implement when we have a dedicated fact-verification use case.

### Speculative Action Pipelining (4.3)
**Verdict:** Defer -- highest complexity technique. Requires streaming support, speculation consistency checking, and waste management. Implement only after simpler parallel patterns (4.1, 4.2) prove their value.

---

## Key References

### Area 1: RLAIF / Constitutional AI
- Lifshitz et al. "Multi-Agent Verification" (COLM 2025) -- https://arxiv.org/abs/2502.20379
- Chen et al. "IterAlign" (NAACL 2024) -- https://arxiv.org/abs/2403.18341
- Madaan et al. "Self-Refine" (NeurIPS 2023) -- https://arxiv.org/abs/2303.17651
- Huang et al. "When Can LLMs Actually Correct Their Own Mistakes?" (TACL, 2024)
- Lee et al. "RLAIF vs. RLHF" (ICML 2024) -- https://arxiv.org/abs/2309.00267
- Menke et al. "Constitutional AI in Small LLMs" (ICLR 2025) -- https://arxiv.org/abs/2503.17365

### Area 2: Active Learning for Model Routing
- Chuang et al. "Confident or Seek Stronger" (Feb 2025) -- https://arxiv.org/html/2502.04428v1
- Aggarwal, Madaan et al. "AutoMix" (NeurIPS 2024) -- https://arxiv.org/abs/2310.12963
- "Learning to Route LLMs with Confidence Tokens" (Self-REF, ICML 2025) -- https://arxiv.org/html/2410.13284v3
- Hu et al. "RouterBench" (2024) -- routing benchmark with 405K precomputed outputs
- "Leveraging Uncertainty Estimation for Efficient LLM Routing" (Feb 2025) -- https://arxiv.org/html/2502.11021

### Area 3: Self-Play and Debate
- Arnesen et al. "Training Language Models to Win Debates with Self-Play" (Sep 2024) -- https://arxiv.org/abs/2409.16636
- Choi et al. "Debate or Vote" (NeurIPS 2025 Spotlight) -- https://arxiv.org/abs/2508.17536
- Kenton et al. "Scalable Oversight with Weak LLMs" (NeurIPS 2024) -- https://arxiv.org/abs/2407.04622
- "Debate Helps Weak-to-Strong Generalization" (Jan 2025) -- https://arxiv.org/abs/2501.13124
- "Scaling Laws For Scalable Oversight" (Apr 2025) -- https://arxiv.org/html/2504.18530v1
- Nielsen. "adversarial-review" (GitHub) -- https://github.com/alecnielsen/adversarial-review

### Area 4: Speculative/Parallel Generation
- Google Research. "Speculative Cascades" (2025) -- https://research.google/blog/speculative-cascades-a-hybrid-approach-for-smarter-faster-llm-inference/
- "M1-Parallel" (Jul 2025) -- https://arxiv.org/html/2507.08944v1
- "ParaThinker: First-Finish" (Sep 2025) -- https://arxiv.org/html/2509.04475v1
- PASTE (Jun 2026) -- https://arxiv.org/html/2603.18897v3
- SpecExec (NeurIPS 2024) -- https://arxiv.org/abs/2406.02532

---

## Implementation Roadmap

```
Week 1: MAV Aspect Verifiers (1.1) + Parallel Race (4.2)
         [Foundation layer -- everything else builds on this]

Week 2: Uncertainty-Driven Exploration (2.1)
         [Enhanced Thompson Sampling -- uses MAV for evaluation]

Week 3: Speculative Cascade (4.1) + AutoMix (2.2)
         [Cost/latency optimization -- uses MAV for verification]

Week 4: Adversarial Debate (3.1)
         [Quality improvement for code review -- uses MAV for judging]

Future: Constitution Discovery (1.2), Weak-to-Strong Oversight (3.2),
        Speculative Pipelining (4.3)
        [Wait for data from earlier techniques before implementing]
```

---

*Research conducted via web search across 30+ papers, blog posts, and open-source repositories. All techniques evaluated for compatibility with existing API-only fleet architecture (no local model weight access required).*
