#!/usr/bin/env python3
"""Benchmark suite for GA pipeline optimization.

30 tasks across 6 categories with reference answers and multi-model judge grading.
Judges are isolated from pipeline models to prevent self-evaluation bias.
"""
import json
import logging
import os
import statistics
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('benchmark')

API_BASE = os.environ.get('API_BASE', 'http://aio-01:5000')

JUDGE_MODELS = [
    'anthropic/claude-sonnet-4',
    'google/gemini-2.5-flash-preview-05-20',
    'meta-llama/llama-3.3-70b-instruct:free',
]

JUDGE_PROMPT = """You are an expert evaluator. Score the following answer on a scale of 1-10 for each dimension.

QUESTION: {question}

REFERENCE (key points that should appear): {reference}

ANSWER TO EVALUATE: {answer}

Score each dimension (1=terrible, 10=perfect):
- correctness: Does the answer contain accurate information matching the reference?
- completeness: Does it cover all key points from the reference?
- relevance: Is the answer focused on the question asked?
- coherence: Is it well-structured and clear?

Respond ONLY with JSON: {{"correctness": N, "completeness": N, "relevance": N, "coherence": N}}"""


@dataclass
class BenchmarkTask:
    query: str
    reference_answer: str
    category: str
    difficulty: str
    expected_techniques: List[str] = field(default_factory=list)
    task_id: str = ""


@dataclass
class JudgeScore:
    correctness: float = 0.0
    completeness: float = 0.0
    relevance: float = 0.0
    coherence: float = 0.0

    @property
    def overall(self) -> float:
        return (self.correctness * 0.35 + self.completeness * 0.25 +
                self.relevance * 0.20 + self.coherence * 0.20)


@dataclass
class BenchmarkResult:
    task_id: str
    category: str
    difficulty: str
    answer: str
    judge_scores: List[JudgeScore]
    median_score: float
    latency_ms: float
    cost_estimate: float
    success: bool
    error: Optional[str] = None
    techniques_used: List[str] = field(default_factory=list)


BENCHMARKS: List[BenchmarkTask] = [
    # === Code Review (5) ===
    BenchmarkTask(
        task_id="code_01",
        query="Review this Python function for bugs:\n```python\ndef transfer(from_acct, to_acct, amount, db):\n    from_balance = db.get_balance(from_acct)\n    if from_balance >= amount:\n        db.set_balance(from_acct, from_balance - amount)\n        to_balance = db.get_balance(to_acct)\n        db.set_balance(to_acct, to_balance + amount)\n    return True\n```",
        reference_answer="Race condition: no transaction/lock between read and write. Returns True even on insufficient funds. No input validation on amount (negative transfers). No error handling if db calls fail.",
        category="code_review",
        difficulty="medium",
        expected_techniques=["cascade", "crag"],
    ),
    BenchmarkTask(
        task_id="code_02",
        query="Review this authentication code:\n```python\ndef login(username, password, db):\n    user = db.query(f\"SELECT * FROM users WHERE username='{username}' AND password='{password}'\")\n    if user:\n        token = hashlib.md5(username.encode()).hexdigest()\n        return {'token': token, 'user': user[0]}\n    return None\n```",
        reference_answer="SQL injection via f-string interpolation. Plaintext password comparison (no hashing). MD5 token is deterministic and predictable. Token doesn't expire. Returns full user object potentially leaking sensitive fields.",
        category="code_review",
        difficulty="easy",
        expected_techniques=["cascade"],
    ),
    BenchmarkTask(
        task_id="code_03",
        query="Review this async rate limiter:\n```python\nimport time\nclass RateLimiter:\n    def __init__(self, rpm=60):\n        self.rpm = rpm\n        self.calls = []\n    def acquire(self):\n        now = time.time()\n        self.calls = [t for t in self.calls if now - t < 60]\n        if len(self.calls) >= self.rpm:\n            time.sleep(60 - (now - self.calls[0]))\n        self.calls.append(time.time())\n```",
        reference_answer="Not thread-safe: concurrent access to self.calls without locking. time.sleep blocks the event loop if used in async context. Sleep duration can be negative if calls[0] is stale. Memory grows unbounded if rpm is very high.",
        category="code_review",
        difficulty="hard",
        expected_techniques=["cascade", "moa"],
    ),
    BenchmarkTask(
        task_id="code_04",
        query="Review this caching implementation:\n```python\ncache = {}\ndef cached_fetch(url, ttl=300):\n    if url in cache:\n        data, ts = cache[url]\n        if time.time() - ts < ttl:\n            return data\n    resp = requests.get(url)\n    cache[url] = (resp.json(), time.time())\n    return cache[url][0]\n```",
        reference_answer="Unbounded cache growth (no eviction). Not thread-safe. No error handling on requests.get or resp.json(). Cache poisoning if response is an error. Global mutable state.",
        category="code_review",
        difficulty="medium",
        expected_techniques=["cascade"],
    ),
    BenchmarkTask(
        task_id="code_05",
        query="Review this file upload handler:\n```python\n@app.route('/upload', methods=['POST'])\ndef upload():\n    f = request.files['file']\n    path = os.path.join('/uploads', f.filename)\n    f.save(path)\n    return {'path': path}\n```",
        reference_answer="Path traversal via filename (../../etc/passwd). No file size limit. No file type validation. No authentication. Returns server path to client. Directory may not exist.",
        category="code_review",
        difficulty="easy",
        expected_techniques=["cascade"],
    ),

    # === Research (5) ===
    BenchmarkTask(
        task_id="research_01",
        query="Explain Thompson Sampling for model selection in a multi-model orchestration system. Include the mathematical foundation and practical considerations.",
        reference_answer="Thompson Sampling uses Beta(alpha, beta) distributions per arm. Sample from each, pick highest. Alpha increments on success, beta on failure. For model selection: each model is an arm, reward is task quality. Exploration-exploitation balance is automatic. Non-stationary variant uses decay factor to forget old observations.",
        category="research",
        difficulty="medium",
        expected_techniques=["crag", "graph_rag", "thompson"],
    ),
    BenchmarkTask(
        task_id="research_02",
        query="What is Corrective RAG and how does it improve over standard RAG pipelines?",
        reference_answer="CRAG adds a grading step after retrieval. An LLM grades each retrieved document as CORRECT, AMBIGUOUS, or INCORRECT. Correct docs are used directly. Ambiguous docs are refined. If all docs are incorrect, the system falls back to query reformulation or web search. This prevents hallucination from irrelevant retrieved content.",
        category="research",
        difficulty="medium",
        expected_techniques=["crag", "graph_rag"],
    ),
    BenchmarkTask(
        task_id="research_03",
        query="Compare LinUCB contextual bandits with Thompson Sampling for LLM model routing. When should you use each?",
        reference_answer="Thompson Sampling: context-free, uses success/failure counts, good when task types are uniform. LinUCB: context-aware, uses feature vectors (task type, complexity, domain), good when different tasks need different models. LinUCB handles heterogeneous workloads better. Thompson Sampling is simpler and converges faster for homogeneous workloads. Both are online learning algorithms.",
        category="research",
        difficulty="hard",
        expected_techniques=["crag", "graph_rag", "thompson", "contextual_bandits"],
    ),
    BenchmarkTask(
        task_id="research_04",
        query="Explain MAP-Elites quality-diversity optimization and why it matters for orchestration.",
        reference_answer="MAP-Elites maintains an archive grid where each cell stores the best solution for a specific behavior niche. Unlike standard GA that converges to one optimum, MAP-Elites finds diverse high-quality solutions across the behavior space. For orchestration: different niches (fast/cheap/quality) need different configs. MAP-Elites finds optimal config per niche simultaneously.",
        category="research",
        difficulty="hard",
        expected_techniques=["crag", "graph_rag"],
    ),
    BenchmarkTask(
        task_id="research_05",
        query="What is Mixture of Agents and how does multi-layer aggregation improve LLM outputs?",
        reference_answer="MoA uses multiple layers: Layer 1 proposers generate independent responses, Layer 2 aggregators synthesize them, and an arbiter produces the final answer. This improves quality because: diverse perspectives catch different aspects, aggregation filters noise, and the arbiter resolves contradictions. Position bias is mitigated by shuffling input order.",
        category="research",
        difficulty="medium",
        expected_techniques=["crag", "moa"],
    ),

    # === Factual Q&A (5) ===
    BenchmarkTask(
        task_id="factual_01",
        query="What port does OrientDB use by default for its binary protocol?",
        reference_answer="OrientDB uses port 2424 for its binary protocol and port 2480 for the HTTP/REST API.",
        category="factual_qa",
        difficulty="easy",
        expected_techniques=["crag", "graph_rag"],
    ),
    BenchmarkTask(
        task_id="factual_02",
        query="What is the difference between pgvector's ivfflat and hnsw index types?",
        reference_answer="IVFFlat partitions vectors into lists using k-means clustering, faster to build but less accurate. HNSW builds a hierarchical navigable small world graph, slower to build but more accurate recall. HNSW is generally preferred for production use. IVFFlat requires training on existing data.",
        category="factual_qa",
        difficulty="medium",
        expected_techniques=["crag"],
    ),
    BenchmarkTask(
        task_id="factual_03",
        query="What are the three tiers in an LLM cascade architecture?",
        reference_answer="Tier 1: Small/free models (fast, cheap, handle easy queries). Tier 2: Large/free models (more capable, handle medium queries). Tier 3: Paid/premium models (highest quality, handle hard queries). Queries start at Tier 1 and escalate based on confidence thresholds.",
        category="factual_qa",
        difficulty="easy",
        expected_techniques=["cascade"],
    ),
    BenchmarkTask(
        task_id="factual_04",
        query="What is the UCB formula used in LinUCB contextual bandits?",
        reference_answer="score = theta^T * x + alpha * sqrt(x^T * A_inverse * x). theta is the learned parameter vector. x is the context feature vector. A is the design matrix (regularized). alpha controls exploration-exploitation tradeoff. The first term is exploitation (predicted reward), the second is exploration (uncertainty bonus).",
        category="factual_qa",
        difficulty="hard",
        expected_techniques=["crag", "graph_rag", "contextual_bandits"],
    ),
    BenchmarkTask(
        task_id="factual_05",
        query="What does the decay_factor parameter do in non-stationary Thompson Sampling?",
        reference_answer="decay_factor (0 to 1) applies exponential decay to alpha and beta parameters over time. A value of 0.995 means each round multiplies parameters by 0.995. This makes the algorithm 'forget' old observations, allowing it to adapt to changing model performance. Lower values forget faster. Parameters are floored at MIN_PARAM (1.0) to prevent degenerate distributions.",
        category="factual_qa",
        difficulty="medium",
        expected_techniques=["thompson", "crag"],
    ),

    # === Complex Analysis (5) ===
    BenchmarkTask(
        task_id="analysis_01",
        query="Analyze the cost-quality tradeoff of using MoA with 6 proposers vs a single paid model (Claude Opus). Consider latency, cost, and quality dimensions.",
        reference_answer="MoA with 6 free proposers: zero API cost, higher latency (parallel but still 6 calls + aggregation), quality from diversity of perspectives. Single Opus: ~$15/1M output tokens, lowest latency (one call), highest single-model quality. MoA may match or exceed Opus quality through synthesis while being free. But latency is 3-5x higher. Best choice depends on task: cost-sensitive batch processing favors MoA, latency-sensitive interactive use favors Opus.",
        category="complex_analysis",
        difficulty="hard",
        expected_techniques=["moa", "cascade", "crag"],
    ),
    BenchmarkTask(
        task_id="analysis_02",
        query="What are the failure modes when combining CRAG with Graph RAG? How can they interfere with each other?",
        reference_answer="CRAG may grade Graph RAG expanded results as INCORRECT because the graph-derived context is tangential to the original query. Graph RAG entity extraction may fail on queries that CRAG has already reformulated. Double latency if both run sequentially. CRAG fallback to web search bypasses the graph entirely. Solution: run in parallel, merge results, let CRAG grade both sources.",
        category="complex_analysis",
        difficulty="hard",
        expected_techniques=["crag", "graph_rag"],
    ),
    BenchmarkTask(
        task_id="analysis_03",
        query="How does adaptive mutation rate in a GA interact with elitism? What happens if both are too aggressive?",
        reference_answer="High elitism (keeping many top individuals) preserves good solutions but reduces diversity. High mutation rate introduces diversity but can destroy good solutions. If both are aggressive: elites survive but mutated offspring are too random to improve on them, stalling convergence. The GA oscillates between preserving elites and producing random noise. Optimal: moderate elitism (10-20%) with adaptive mutation that decreases as fitness improves.",
        category="complex_analysis",
        difficulty="hard",
        expected_techniques=["crag", "graph_rag"],
    ),
    BenchmarkTask(
        task_id="analysis_04",
        query="Design a strategy for routing queries to either cascade (cheap/fast) or MoA (expensive/quality) based on query characteristics.",
        reference_answer="Use a difficulty classifier: measure query length, domain complexity, code presence, multi-part structure. Easy queries (short, single-topic, factual) go to cascade. Hard queries (long, multi-domain, analytical, code-heavy) go to MoA. Medium queries start at cascade, escalate to MoA if confidence is below threshold. Track outcomes per routing decision to improve the classifier over time using Thompson Sampling or LinUCB.",
        category="complex_analysis",
        difficulty="medium",
        expected_techniques=["cascade", "moa", "contextual_bandits"],
    ),
    BenchmarkTask(
        task_id="analysis_05",
        query="What is the risk of using the same models for evaluation that you use for generation? How does this create feedback loops?",
        reference_answer="Self-evaluation bias: models rate their own style higher. Circular validation: generation optimizes for what the evaluator rewards, evaluator confirms the pattern. Metric overfitting: the system converges on outputs that score well on its own evaluation but don't actually improve. Detection: monitor model diversity, check if evaluation scores increase while external quality doesn't. Mitigation: use zero-overlap judge panels, external benchmarks, adversarial evaluation.",
        category="complex_analysis",
        difficulty="medium",
        expected_techniques=["crag"],
    ),

    # === Creative/Synthesis (5) ===
    BenchmarkTask(
        task_id="creative_01",
        query="Design a monitoring dashboard for a 200+ model orchestration system. What metrics should be tracked and what alerts should fire?",
        reference_answer="Metrics: per-model success rate, latency p50/p95/p99, cost per query, error rate by tier, Thompson Sampling arm distribution, LinUCB exploration ratio, CRAG fallback rate, MoA layer timing, queue depth. Alerts: model error rate >10%, latency p99 >30s, cost spike >2x baseline, Thompson Sampling arm dominance >70%, cascade escalation rate >50%, CRAG fallback rate >30%. Dashboard: real-time model health grid, cost over time, quality trend, diversity heatmap.",
        category="creative_synthesis",
        difficulty="medium",
        expected_techniques=["crag", "moa"],
    ),
    BenchmarkTask(
        task_id="creative_02",
        query="Propose a testing strategy to validate that the combination of Thompson Sampling + LinUCB + Cascade produces better results than any single technique alone.",
        reference_answer="A/B testing: run identical queries through 4 configurations (TS-only, LinUCB-only, Cascade-only, all-three). Measure quality via judge panel, cost, latency across 1000+ queries. Statistical significance via paired t-test or Wilcoxon. Control for query difficulty distribution. Track convergence speed: how quickly each config reaches peak quality. Include holdout set to test generalization. Run for at least 7 days to capture non-stationary effects.",
        category="creative_synthesis",
        difficulty="hard",
        expected_techniques=["thompson", "contextual_bandits", "cascade", "moa"],
    ),
    BenchmarkTask(
        task_id="creative_03",
        query="Design a self-healing mechanism for when the orchestration system detects degraded model performance.",
        reference_answer="Detection: Thompson Sampling decay surfaces degraded models via dropping effective_mean. LinUCB exploration bonus increases for underperforming arms. Alert on: 3 consecutive failures, avg_reward drop >20%, latency spike >3x. Response: automatic tier escalation, remove degraded model from candidate pool, increase exploration rate to find alternatives, log incident for analysis. Recovery: gradual re-introduction with small traffic share, monitored via canary queries.",
        category="creative_synthesis",
        difficulty="hard",
        expected_techniques=["thompson", "contextual_bandits", "cascade"],
    ),
    BenchmarkTask(
        task_id="creative_04",
        query="How would you extend MAP-Elites to automatically discover new behavior dimensions that matter for orchestration quality?",
        reference_answer="Start with predefined dimensions (cost, latency, technique count). After initial evolution, analyze which genes correlate most with fitness variation. Use PCA or mutual information on the archive to find latent dimensions. Create new bins along discovered dimensions. Example: might discover that 'retrieval depth' (CRAG limit * graph hops) is a meaningful dimension not initially tracked. Iterate: evolve, analyze, add dimensions, re-evolve.",
        category="creative_synthesis",
        difficulty="hard",
        expected_techniques=["map_elites", "crag", "graph_rag"],
    ),
    BenchmarkTask(
        task_id="creative_05",
        query="Design a cost budget system that dynamically adjusts which techniques are active based on remaining daily budget.",
        reference_answer="Set daily budget. Track cumulative cost via API cost estimates. At 0-50% budget: all techniques available including paid tier. At 50-80%: disable paid tier cascade, switch to free-only. At 80-95%: disable MoA (most expensive free technique due to multiple calls), use cascade with free_small tier only. At 95%+: direct single-model queries with cheapest available. Use Thompson Sampling to select the best model within the current budget tier. Reset daily.",
        category="creative_synthesis",
        difficulty="medium",
        expected_techniques=["cascade", "thompson"],
    ),

    # === Multi-hop Reasoning (5) ===
    BenchmarkTask(
        task_id="multihop_01",
        query="If Thompson Sampling selects model A for a code review task, but LinUCB's feature vector suggests model B is better for code tasks, how should the system resolve the conflict?",
        reference_answer="Use routing_strategy to determine priority. In 'bandit_first' mode: LinUCB wins because it uses richer context (15-dim features vs TS's context-free selection). In 'cascade_first' mode: cascade handles routing, both bandits inform tier selection. Resolution: let LinUCB route since it has task-type awareness, but use Thompson Sampling's decay to update LinUCB's reward signals over time. Track which resolver produces better outcomes.",
        category="multi_hop",
        difficulty="hard",
        expected_techniques=["thompson", "contextual_bandits", "cascade"],
    ),
    BenchmarkTask(
        task_id="multihop_02",
        query="A CRAG pipeline grades a retrieved document about 'attention mechanisms' as AMBIGUOUS for a query about 'self-attention in transformers'. Graph RAG finds entity links from 'self-attention' to 'scaled dot-product'. How should the pipeline combine these signals?",
        reference_answer="The graph link confirms the document IS relevant (self-attention → scaled dot-product → attention mechanisms). Override CRAG's AMBIGUOUS grade to CORRECT based on graph evidence. Use the graph-expanded context to refine the CRAG result. This is an interaction effect: CRAG alone might discard relevant content, but Graph RAG's entity traversal provides the missing link. The combined signal is stronger than either alone.",
        category="multi_hop",
        difficulty="hard",
        expected_techniques=["crag", "graph_rag"],
    ),
    BenchmarkTask(
        task_id="multihop_03",
        query="If the GA evolves a configuration where cascade_threshold=0.3 and moa_num_proposers=6, what happens to cost and quality? Trace through the pipeline.",
        reference_answer="Low cascade threshold (0.3) means almost any response is accepted without escalation — most queries resolve at free_small tier. MoA with 6 proposers is expensive (6 API calls) but rarely triggered because cascade accepts early. Result: low cost (cascade handles most queries cheaply), potentially low quality (accepting low-confidence responses), MoA is wasted. The GA should discover this: either raise the threshold so more queries reach MoA, or reduce proposers since MoA is rarely used.",
        category="multi_hop",
        difficulty="hard",
        expected_techniques=["cascade", "moa"],
    ),
    BenchmarkTask(
        task_id="multihop_04",
        query="Explain how decay_factor in Thompson Sampling interacts with window_size. What happens when decay is fast (0.9) but window is large (500)?",
        reference_answer="Fast decay (0.9) aggressively forgets old observations — after 10 rounds, alpha/beta are multiplied by 0.9^10 = 0.35. Large window (500) caps total effective observations. With fast decay, parameters shrink below the window cap quickly, so window has no effect. The window only matters when decay is slow (0.999) and observations accumulate above the window threshold. Fast decay + large window = decay dominates, window is irrelevant. Slow decay + small window = window dominates, decay is irrelevant.",
        category="multi_hop",
        difficulty="hard",
        expected_techniques=["thompson"],
    ),
    BenchmarkTask(
        task_id="multihop_05",
        query="If MAP-Elites finds that the optimal config for the 'fast+cheap' niche uses only cascade, but the 'quality' niche uses MoA+CRAG+GraphRAG, how should LinUCB learn to route between these configurations?",
        reference_answer="LinUCB's 15-dim feature vector encodes task type, complexity, domain. Map these features to MAP-Elites niche selection: low complexity + factual domain → 'fast+cheap' niche → cascade config. High complexity + technical domain → 'quality' niche → MoA+CRAG+GraphRAG config. LinUCB arms become the MAP-Elites niche configs, not individual models. Reward is task quality. Over time, LinUCB learns which feature patterns map to which niche. This is the meta-learning loop: GA evolves configs, MAP-Elites finds niches, LinUCB routes to niches.",
        category="multi_hop",
        difficulty="hard",
        expected_techniques=["map_elites", "contextual_bandits", "cascade", "moa", "crag", "graph_rag"],
    ),
]


def _get_api_key() -> Optional[str]:
    try:
        resp = requests.get(f'{API_BASE}/secrets/PERSONAL_OPENROUTER_API_KEY', timeout=5)
        if resp.ok:
            return resp.json().get('value')
    except Exception:
        pass
    return os.environ.get('PERSONAL_OPENROUTER_API_KEY')


def _call_model(model: str, prompt: str, api_key: str, max_tokens: int = 512) -> Optional[str]:
    try:
        if model.startswith('anthropic/'):
            anthropic_key = None
            try:
                resp = requests.get(f'{API_BASE}/secrets/ANTHROPIC_API_KEY', timeout=5)
                if resp.ok:
                    anthropic_key = resp.json().get('value')
            except Exception:
                pass
            if not anthropic_key:
                return None
            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': anthropic_key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model.replace('anthropic/', ''),
                    'max_tokens': max_tokens,
                    'messages': [{'role': 'user', 'content': prompt}],
                },
                timeout=60,
            )
            if resp.ok:
                return resp.json()['content'][0]['text']
            return None

        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': max_tokens,
                'temperature': 0.1,
            },
            timeout=60,
        )
        if resp.ok:
            return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.warning(f'Model call failed ({model}): {e}')
    return None


def grade_answer(question: str, reference: str, answer: str, api_key: str) -> JudgeScore:
    """Grade an answer using the multi-model judge panel. Returns median scores."""
    if not answer or not answer.strip():
        return JudgeScore()

    prompt = JUDGE_PROMPT.format(question=question, reference=reference, answer=answer[:3000])
    scores = []

    for model in JUDGE_MODELS:
        raw = _call_model(model, prompt, api_key, max_tokens=200)
        if not raw:
            continue
        try:
            raw = raw.strip()
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                parsed = json.loads(raw[start:end])
                scores.append(JudgeScore(
                    correctness=min(10, max(1, float(parsed.get('correctness', 5)))),
                    completeness=min(10, max(1, float(parsed.get('completeness', 5)))),
                    relevance=min(10, max(1, float(parsed.get('relevance', 5)))),
                    coherence=min(10, max(1, float(parsed.get('coherence', 5)))),
                ))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    if not scores:
        return JudgeScore(correctness=3, completeness=3, relevance=3, coherence=3)

    return JudgeScore(
        correctness=statistics.median([s.correctness for s in scores]),
        completeness=statistics.median([s.completeness for s in scores]),
        relevance=statistics.median([s.relevance for s in scores]),
        coherence=statistics.median([s.coherence for s in scores]),
    )


def run_benchmarks(pipeline_fn, tasks: Optional[List[BenchmarkTask]] = None) -> List[BenchmarkResult]:
    """Run benchmark tasks through a pipeline function and grade results.

    Args:
        pipeline_fn: callable(query: str) -> dict with keys: answer, latency_ms, cost_estimate, techniques_used, error
        tasks: subset of tasks to run (default: all 30)
    """
    tasks = tasks or BENCHMARKS
    api_key = _get_api_key()
    results = []

    for task in tasks:
        logger.info(f'Benchmark {task.task_id} ({task.category}/{task.difficulty})')
        start = time.time()

        try:
            output = pipeline_fn(task.query)
            answer = output.get('answer', '')
            latency = output.get('latency_ms', (time.time() - start) * 1000)
            cost = output.get('cost_estimate', 0.0)
            techniques = output.get('techniques_used', [])
            error = output.get('error')
            success = bool(answer and not error)
        except Exception as e:
            answer = ''
            latency = (time.time() - start) * 1000
            cost = 0.0
            techniques = []
            error = str(e)
            success = False

        score = grade_answer(task.query, task.reference_answer, answer, api_key) if success else JudgeScore()

        results.append(BenchmarkResult(
            task_id=task.task_id,
            category=task.category,
            difficulty=task.difficulty,
            answer=answer[:1000],
            judge_scores=[score],
            median_score=score.overall,
            latency_ms=latency,
            cost_estimate=cost,
            success=success,
            error=error,
            techniques_used=techniques,
        ))
        logger.info(f'  Score: {score.overall:.2f} | Latency: {latency:.0f}ms | Success: {success}')

    return results


def compute_fitness(results: List[BenchmarkResult]) -> Dict:
    """Compute composite fitness from benchmark results."""
    if not results:
        return {'quality': 0, 'cost_efficiency': 0, 'latency': 0, 'reliability': 0, 'total': 0}

    successful = [r for r in results if r.success]
    quality = statistics.mean([r.median_score for r in successful]) / 10.0 if successful else 0.0

    total_cost = sum(r.cost_estimate for r in results)
    cost_score = max(0, 1.0 - total_cost / 0.10) if total_cost < 0.10 else 0.0

    avg_latency = statistics.mean([r.latency_ms for r in results])
    latency_score = max(0, 1.0 - avg_latency / 30000.0)

    reliability = len(successful) / len(results) if results else 0.0

    total = quality * 0.40 + cost_score * 0.25 + latency_score * 0.20 + reliability * 0.15

    return {
        'quality': round(quality, 4),
        'cost_efficiency': round(cost_score, 4),
        'latency': round(latency_score, 4),
        'reliability': round(reliability, 4),
        'total': round(total, 4),
        'avg_latency_ms': round(avg_latency, 1),
        'total_cost': round(total_cost, 6),
        'tasks_run': len(results),
        'tasks_succeeded': len(successful),
        'by_category': _scores_by_category(results),
        'by_difficulty': _scores_by_difficulty(results),
    }


def _scores_by_category(results: List[BenchmarkResult]) -> Dict:
    cats = {}
    for r in results:
        if r.category not in cats:
            cats[r.category] = []
        cats[r.category].append(r.median_score / 10.0 if r.success else 0.0)
    return {k: round(statistics.mean(v), 4) for k, v in cats.items()}


def _scores_by_difficulty(results: List[BenchmarkResult]) -> Dict:
    diffs = {}
    for r in results:
        if r.difficulty not in diffs:
            diffs[r.difficulty] = []
        diffs[r.difficulty].append(r.median_score / 10.0 if r.success else 0.0)
    return {k: round(statistics.mean(v), 4) for k, v in diffs.items()}


if __name__ == '__main__':
    print(f'Benchmark suite: {len(BENCHMARKS)} tasks')
    for cat in set(t.category for t in BENCHMARKS):
        count = sum(1 for t in BENCHMARKS if t.category == cat)
        print(f'  {cat}: {count} tasks')
