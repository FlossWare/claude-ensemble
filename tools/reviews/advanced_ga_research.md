# Advanced GA & Evolutionary Computation Research

**Date:** 2026-07-26
**Researcher:** Claude Opus 4.6 (autonomous research agent)
**Purpose:** Identify advanced EC techniques applicable to LLM orchestration system
**Existing Infrastructure:** ga_engine.py, llm_guided_evolution.py, map_elites.py, ga_rag_retrieval_optimizer.py, Thompson Sampling, 8-worker fleet, 200+ API models, PostgreSQL + pgvector

---

## Table of Contents

1. [Coevolution](#1-coevolution)
2. [Novelty Search](#2-novelty-search)
3. [NSGA-II / NSGA-III Multi-Objective](#3-nsga-ii--nsga-iii-multi-objective)
4. [CMA-ES](#4-cma-es-covariance-matrix-adaptation)
5. [Island Model / Migration](#5-island-model--migration)
6. [Memetic Algorithms](#6-memetic-algorithms)
7. [Genetic Programming](#7-genetic-programming)
8. [Surrogate-Assisted Evolution](#8-surrogate-assisted-evolution)
9. [Differential Evolution (L-SHADE)](#9-differential-evolution-l-shade)
10. [Neuroevolution / NEAT](#10-neuroevolution--neat)
11. [Conference & Framework Survey](#11-conference--framework-survey)
12. [LLM + Evolution Hybrids](#12-llm--evolution-hybrids)
13. [Fitness Landscape Analysis](#13-fitness-landscape-analysis)
14. [Top 8 Most Implementable Techniques](#14-top-8-most-implementable-techniques)

---

## 1. Coevolution

### What It Is

Coevolution maintains **multiple interacting populations** that evolve simultaneously, with fitness of individuals in one population depending on individuals in other populations. In **competitive coevolution**, populations have conflicting objectives (attacker vs. defender, prompt vs. evaluator). In **cooperative coevolution**, populations represent subcomponents that must work together (each population evolves a different part of the solution).

The key insight is that there is no single fixed fitness function -- fitness emerges from interactions between co-evolving populations. This creates an evolutionary arms race that prevents premature convergence and continuously drives improvement.

### Key Papers & References

- Hemberg, Moskal, O'Reilly, Liu, Fuller -- "Evolutionary and Coevolutionary Multi-Agent Design Choices and Dynamics" (GECCO 2025). Defines CCAs as two EAs with conflicting objectives coupled only at fitness evaluation. [MIT/GECCO](https://dspace.mit.edu/bitstream/handle/1721.1/162637/3712255.3726712.pdf)
- MPCMO -- "Multi-Population Co-evolutionary Algorithm for Many-Objective Optimization" (2025). M subpopulations + external archive for rapid Pareto front approximation. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0020025525008047)
- CMEA -- "Co-evolutionary Multi-population EA for Dynamic Multi-Objective Optimization" (2024). Each population focuses on one objective, co-evolves with others. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S221065022400186X)
- DESCA -- "Co-evolutionary Algorithm with Region-Based Diversity Enhancement" (2025). Regional mating between main/auxiliary populations with constraint relaxation. [Springer](https://link.springer.com/article/10.1007/s40747-025-01819-7)
- MART -- "Multi-Round Automatic Red-Teaming" (Ge et al., 2024). Coevolutionary fine-tuning of attacker and defender LLMs.

### Implementation Complexity: **Medium**

### Specific Use Cases in Our System

1. **Prompt vs. Evaluator Coevolution:** One population evolves task prompts, another evolves evaluation criteria. The evaluators create pressure for prompts to improve, while prompts create pressure for evaluators to become more discriminating. Directly applicable to our review panel design.
2. **Attacker vs. Defender Prompts:** Red-team population generates adversarial prompts, blue-team population evolves robust system prompts. Maps to our security review workflow.
3. **Router vs. Task Coevolution:** Routing rules evolve against a population of increasingly difficult tasks.

### Builds On Existing

- Extends `ga_engine.py` tournament selection and crossover -- just applied to multiple populations
- Extends `llm_guided_evolution.py` -- LLM-generated crossover/mutation applied per-population
- Aligns with existing review panel vs. meta-review panel separation (zero-overlap constraint)

### Open Source Implementations

- **DEAP** has cooperative coevolution example: [deap.readthedocs.io/en/master/examples/coev_coop.html](https://deap.readthedocs.io/en/master/examples/coev_coop.html)
- **pymoo** supports multi-population frameworks
- **CoDeepNEAT** (Uber Research) for cooperative neuroevolution

---

## 2. Novelty Search

### What It Is

Novelty search **completely abandons objective-based fitness** and instead rewards individuals based on how behaviorally different they are from all previously seen solutions. The counterintuitive insight (Lehman & Stanley, 2011) is that objectives can be deceptive -- the stepping stones to a goal may look nothing like the goal itself. By rewarding novelty, the algorithm discovers diverse behavioral strategies that often include high-quality solutions the objective-driven search would never find.

A novelty archive stores previously encountered behaviors. Each individual's "novelty score" is the average distance to its k-nearest neighbors in behavior space. This naturally creates exploration pressure without requiring a fitness function.

### Key Papers & References

- Lehman & Stanley -- "Abandoning Objectives: Evolution Through the Search for Novelty Alone" (Evolutionary Computation, 2011, 19(2):189-223). The foundational paper. [MIT Press](https://direct.mit.edu/evco/article-abstract/19/2/189/1365)
- Lehman & Stanley -- "Evolving a Diversity of Creatures through Novelty Search and Local Competition" (GECCO 2011). Extends to multi-objective: novelty + performance. [ACM](https://dl.acm.org/doi/10.1145/2001576.2001606)
- Pugh, Soros, Stanley -- "Quality-Diversity: A New Frontier for Evolutionary Computation" (Frontiers in Robotics and AI, 2016). Unifies novelty search + MAP-Elites.
- Marrero, Segredo, Leon, Hart -- "Synthesising Diverse and Discriminatory Sets of Instances Using Novelty Search" (Evolutionary Computation, 33(1):55-90, March 2025).
- Hufkens, Vos, Marin -- "Novelty-Driven Evolutionary Scriptless Testing" (RCIS, May 2024).

### Implementation Complexity: **Low-Medium**

### Specific Use Cases in Our System

1. **Prompt Diversity Generation:** Instead of optimizing prompts for fitness alone, use novelty search to generate maximally diverse prompts. Feed into MAP-Elites archive. Prevents the common failure mode of all prompts converging to the same phrasing.
2. **Model Routing Exploration:** Novelty search over routing configurations to discover unexpected model-task pairings that would never emerge from fitness-driven optimization.
3. **Test Case Generation:** Generate behaviorally diverse test cases for evaluating prompts and models, ensuring coverage across the input space.

### Builds On Existing

- **Directly extends `map_elites.py`** -- MAP-Elites is the primary Quality-Diversity algorithm that builds on novelty search concepts. Adding a novelty metric to our existing MAP-Elites would be straightforward.
- Can use pgvector for behavior space distance calculations (already deployed)
- Behavior characterization dimensions already defined in map_elites.py (length, style, specificity)

### Open Source Implementations

- **DEAP** supports novelty search via custom fitness functions
- **QDax** (Google DeepMind) -- JAX-based quality-diversity library
- **pyribs** -- Python library specifically for Quality-Diversity algorithms including MAP-Elites and CMA-ME

---

## 3. NSGA-II / NSGA-III Multi-Objective

### What It Is

NSGA-II (Non-dominated Sorting Genetic Algorithm II, Deb et al. 2002) finds the **Pareto-optimal front** -- the set of solutions where no solution is strictly better than another on all objectives. Instead of weighting objectives into a single fitness, NSGA-II preserves trade-offs. Solutions are ranked by "non-domination" (front 1 = not dominated by anyone, front 2 = dominated only by front 1, etc.) and spread is maintained via crowding distance.

NSGA-III (Deb & Jain, 2014) extends this to many objectives (>3) using reference points instead of crowding distance, distributing solutions evenly across the Pareto front.

**This is extremely applicable to our system** because we naturally have multiple competing objectives: quality, cost, latency, diversity, model utilization.

### Key Papers & References

- Deb, Pratap, Agarwal, Meyarivan -- "A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II" (IEEE TEVC, 2002). The foundational paper, 40K+ citations. [IEEE](https://ieeexplore.ieee.org/document/996017)
- Deb & Jain -- "An Evolutionary Many-Objective Optimization Algorithm Using Reference-Point-Based Nondominated Sorting" (IEEE TEVC, 2014). NSGA-III.
- Doerr et al. -- "Why Dominance Is Not Enough: Lessons from Practical Evolutionary Multi-Objective Algorithms" (GECCO 2025, Best Paper). [GECCO](https://gecco-2025.sigevo.org/Best-Paper-Awards)
- "GPU-Accelerated Evolutionary Many-Objective Optimization Using Tensorized NSGA-III" (2025). Full tensorization for GPU acceleration. [arXiv](https://arxiv.org/html/2504.06067v1)
- "Enhanced NSGA-II Algorithm for Solving Real-world Multi-objective Optimization Problems" (2025). Sobol sequence initialization for better convergence. [MECS Press](https://www.mecs-press.org/ijisa/ijisa-v17-n6/v17n6-8.html)
- "Proven Approximation Guarantees in Multi-Objective Optimization" (IJCAI 2025). First formal runtime guarantees. [IJCAI](https://www.ijcai.org/proceedings/2025/0982.pdf)

### Implementation Complexity: **Low** (pymoo provides production-ready implementation)

### Specific Use Cases in Our System

1. **Prompt Optimization:** Simultaneously optimize for quality, brevity (cost), response consistency, and model-independence. The Pareto front reveals the trade-off curve: "this prompt costs 2x more but is 30% better."
2. **Model Routing:** Multi-objective: maximize quality + minimize cost + minimize latency + maximize diversity. Each point on the Pareto front is a valid routing strategy for different use cases.
3. **RAG Configuration:** Optimize chunk_size x overlap x top_k x embedding_dim for relevance x latency x cost. **Replaces the weighted fitness in `ga_rag_retrieval_optimizer.py`** with true Pareto optimization.
4. **Fleet Strategy:** Workers x timeout x consensus_type optimized for speed x quality x cost. Replaces the single fitness in `ga_engine.py`.

### Builds On Existing

- **Direct upgrade path from `ga_engine.py`** -- replace single fitness with multi-objective fitness, replace tournament selection with non-dominated sorting
- **Direct upgrade path from `ga_rag_retrieval_optimizer.py`** -- currently uses weighted combination of 5 objectives; NSGA-II would find the full Pareto front instead
- All existing crossover/mutation operators work unchanged
- `llm_guided_evolution.py` LLM-based operators work as drop-in replacements

### Open Source Implementations

- **pymoo** -- Production-ready NSGA-II, NSGA-III, R-NSGA-II, U-NSGA-III. [pymoo.org](https://pymoo.org/algorithms/moo/nsga2.html). Created by Deb's student. Gold standard.
- **DEAP** -- NSGA-II built-in (`deap.tools.selNSGA2`)
- **Platypus** -- Python multi-objective optimization library
- **jMetalPy** -- Python port of jMetal framework

**pymoo minimal example:**

```python
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.optimize import minimize
import numpy as np

class PromptOptProblem(Problem):
    def __init__(self):
        super().__init__(n_var=4, n_obj=3, n_constr=0,
                         xl=np.array([0.0, 0.0, 0.0, 0.0]),
                         xu=np.array([1.0, 1.0, 1.0, 1.0]))

    def _evaluate(self, X, out, *args, **kwargs):
        # Objectives: minimize -quality, cost, latency
        out["F"] = np.column_stack([
            -quality_score(X),
            cost_score(X),
            latency_score(X)
        ])

algorithm = NSGA2(pop_size=100)
res = minimize(PromptOptProblem(), algorithm, ('n_gen', 200))
# res.F = Pareto front, res.X = corresponding solutions
```

---

## 4. CMA-ES (Covariance Matrix Adaptation)

### What It Is

CMA-ES is the **state-of-the-art evolution strategy for continuous (real-valued) optimization**. It maintains a multivariate normal distribution over the search space and adapts both its mean (toward successful solutions) and its covariance matrix (to learn the shape and orientation of the fitness landscape). This is essentially learning the inverse Hessian without computing gradients -- a second-order method using only fitness evaluations.

Key advantages: no hyperparameters to tune (self-adaptive step size and covariance), works on non-smooth/non-convex/noisy problems, and has strong theoretical convergence guarantees.

### Key Papers & References

- Hansen & Ostermeier -- "Completely Derandomized Self-Adaptation in Evolution Strategies" (Evolutionary Computation, 2001). The foundational CMA-ES paper.
- Hansen -- "The CMA Evolution Strategy: A Tutorial" (arXiv:1604.00772). Comprehensive guide. [arXiv](https://arxiv.org/pdf/1604.00772)
- "CMA-ES: Comprehensive Survey of Variants and Hybridizations" (Archives of Computational Methods in Engineering, 2026). Latest survey. [Springer](https://link.springer.com/article/10.1007/s11831-026-10557-z)
- Nakagawa et al. -- "Learning Rate Adaptation CMA-ES for Multimodal and Noisy Problems" (GECCO 2025). [cma-es.github.io](https://cma-es.github.io/)
- Gharafi et al. -- "Rank-based Linear-Quadratic Surrogate Assisted CMA-ES" (GECCO 2025). Combines CMA-ES with surrogate models.
- Ajani et al. -- "CMA-ES Based on Correlated Evolution Paths with Application to RL" (Expert Systems with Applications, 2024).

### Implementation Complexity: **Low** (pycma is production-ready)

### Specific Use Cases in Our System

1. **Embedding Parameter Optimization:** Optimize embedding dimensions, chunk sizes, overlap ratios, temperature, top_p -- all continuous parameters. CMA-ES will learn correlations between parameters (e.g., larger chunks need higher overlap).
2. **RAG Continuous Parameters:** Replace the discrete grid search in `ga_rag_retrieval_optimizer.py` for continuous parameters (chunk_size, overlap_ratio, top_k as continuous then rounded).
3. **Thompson Sampling Hyperparameters:** Optimize decay rates, prior strengths, exploration bonuses for our non-stationary Thompson Sampling.
4. **LLM Temperature/Sampling Optimization:** Optimize temperature, top_p, top_k, frequency_penalty across model-task pairs.

### Builds On Existing

- Complements `ga_engine.py` for continuous parameters (GA better for discrete/categorical, CMA-ES better for continuous)
- Can optimize the continuous hyperparameters of our other GA tools (mutation rates, crossover probabilities, tournament sizes)
- Uses same REST API for fitness evaluation

### Open Source Implementations

- **pycma** -- Nikolaus Hansen's official Python implementation. `pip install cma`. [cma-es.github.io](https://cma-es.github.io/)
- **Nevergrad** (Meta) -- Includes CMA-ES among many algorithms. [GitHub](https://github.com/facebookresearch/nevergrad)
- **pymoo** -- Includes CMA-ES. [pymoo.org](https://pymoo.org/)
- **EvoTorch** -- GPU-accelerated CMA-ES via PyTorch

**pycma minimal example:**

```python
import cma

def evaluate_rag_config(x):
    chunk_size = int(x[0] * 1000 + 200)  # 200-1200
    overlap = x[1]                         # 0.0-1.0
    top_k = int(x[2] * 20 + 1)           # 1-21
    temperature = x[3]                     # 0.0-1.0
    # Call REST API for fitness evaluation
    return -quality_score(chunk_size, overlap, top_k, temperature)

es = cma.CMAEvolutionStrategy([0.5, 0.3, 0.5, 0.7], 0.3)
es.optimize(evaluate_rag_config, iterations=100)
best = es.result.xbest
```

---

## 5. Island Model / Migration

### What It Is

The island model divides the population into **sub-populations (islands)** that evolve independently in parallel, with periodic **migration** of individuals between islands. Each island can use different evolutionary strategies, selection pressures, or parameters. This naturally maintains diversity (islands diverge) while sharing good solutions (migration mixes). It is an inherently parallel architecture.

This is a **natural fit for our 8-worker fleet** -- each worker is an island.

### Key Papers & References

- "Trackable Island-Model Genetic Algorithms at Wafer Scale" (GECCO 2024). Scaled to 16 million population across wafer-scale engine, 1M+ generations/minute. [arXiv](https://arxiv.org/html/2405.03605v1)
- "DSKT-DDEA: Island-Based Evolutionary Computation with Diverse Surrogates" (ACM TELO, 2024). Each island uses different surrogate model, adaptive knowledge transfer between islands. [arXiv](https://arxiv.org/html/2503.12856v1)
- "On the Behavior of Parallel Island Models" (Applied Soft Computing, 2024). Analyzes sync vs. async migration, population balancing via fitness/stdev. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1568494623008980)
- "Dynamic Island Model based on Spectral Clustering" (2024). Adaptive island topology via clustering. [arXiv](https://arxiv.org/pdf/1801.01620)

### Implementation Complexity: **Medium**

### Specific Use Cases in Our System

1. **Fleet-Parallel Prompt Evolution:** 8 islands on 8 workers, each evolving prompts with different strategies (one island uses aggressive mutation, another conservative, another novelty-driven). Every N generations, best prompts migrate. **This is the single most natural architectural fit for our fleet.**
2. **Multi-Strategy GA:** Island 1 runs standard GA, Island 2 runs LLM-guided evolution, Island 3 runs MAP-Elites, Island 4 runs CMA-ES. Migration shares best solutions across strategies.
3. **Heterogeneous Model Evolution:** Each island evolves routing strategies using different LLM providers. Island 1 uses OpenRouter models, Island 2 uses Anthropic models, etc. Migration shares winning configurations.

### Builds On Existing

- **Direct extension of `ga_engine.py`** -- each island runs a GA instance
- **Direct extension of `llm_guided_evolution.py`** -- different islands use different evolution models
- Fleet SSH infrastructure already supports distributing work to 8 workers
- REST API at aio-01:5000 provides natural migration hub (store/retrieve migrants)
- Redis on aio-01 can serve as migration queue between islands

### Open Source Implementations

- **DEAP** has island model support via `multiprocessing` and `scoop`
- **pymoo** supports parallel evaluation
- **EvoX** (JAX) has distributed island model. [arXiv](https://arxiv.org/html/2301.12457v10)
- Custom implementation is straightforward given our existing fleet infrastructure

---

## 6. Memetic Algorithms

### What It Is

Memetic algorithms combine **global evolutionary search (GA) with local refinement**. After crossover and mutation produce offspring, a local search operator improves each offspring before it enters the population. The name comes from Dawkins' "meme" concept -- cultural transmission of learned improvements.

In our context, the "local search" is an **LLM-based refinement step**: after GA produces a rough offspring prompt, an LLM polishes it. This combines the exploration power of GA with the semantic understanding of LLMs.

### Key Papers & References

- Moscato -- "On Evolution, Search, Optimization, Genetic Algorithms and Martial Arts: Towards Memetic Algorithms" (1989). Original paper coining the term.
- "Memetic and Reflective Evolution Framework for Automatic Heuristic Design Using LLMs" (Applied Sciences, 2025). LLM-driven exploration + domain-specific local refinement + memory-aware reflection. [MDPI](https://www.mdpi.com/2076-3417/15/15/8735)
- "Framework for Integrating LLMs into Memetic Algorithms" (Biomimetics, 2026). LLMs as optimizers, surrogate predictors, and algorithm designers simultaneously. [Biomimetics](https://doi.org/10.3390/biomimetics11060383)
- "LAMA: Automatic Memetic Algorithm Enhanced by LLMs" (IEEE TEVC, 2025). LLM designs heuristics, EA evolves them.
- "Self-Adaptive Memetic Algorithm Using Population Diversity Control" (Scientific Reports, 2025). DE + controlled local search for multi-objective problems. [Nature](https://www.nature.com/articles/s41598-025-89289-2)
- "Genetic Improvement for LLM-Generated Code" (SN Computer Science, 2025). Iterative GI refinement of LLM code using test case feedback. [Springer](https://link.springer.com/article/10.1007/s42979-025-04281-x)

### Implementation Complexity: **Low** (we already have the pieces)

### Specific Use Cases in Our System

1. **GA + LLM Polish:** Standard crossover/mutation produces rough prompts, then an LLM call refines grammar, coherence, and specificity. This is essentially what `llm_guided_evolution.py` already does, but formalized as a memetic framework.
2. **Code Generation + GI:** Evolve workflow code via GA, then use LLM to locally improve each variant. Test against evaluation suite. The GI paper shows this works well.
3. **Prompt Evolution + Gradient-Free Local Search:** After LLM mutation, try small perturbations (synonym swaps, reorderings) and keep improvements. Hill-climbing as the local search.

### Builds On Existing

- **`llm_guided_evolution.py` IS essentially a memetic algorithm** -- it uses LLM-based operators as both global and local search. Formalizing it as a memetic framework would add:
  - Explicit separation of global (crossover/mutation) and local (LLM polish) phases
  - Configurable local search intensity (how many LLM refinement steps per individual)
  - Adaptive switching between exploration (more global) and exploitation (more local)
- `ga_engine.py` provides the GA backbone

### Open Source Implementations

- **DEAP** supports custom local search integration
- **pymoo** supports custom repair/local search operators via `Repair` class
- No dedicated memetic library needed -- it's GA + local search wrapper

---

## 7. Genetic Programming (GP)

### What It Is

Genetic Programming evolves **programs represented as tree structures** (or DAGs) rather than fixed-length strings. Crossover swaps subtrees, mutation replaces subtrees. GP can evolve arbitrarily complex programs, including conditionals, loops, and function compositions.

For our system, GP could evolve **workflow DAGs, routing decision trees, or pipeline configurations** as tree structures, where internal nodes are operations and leaves are parameters.

### Key Papers & References

- Koza -- "Genetic Programming: On the Programming of Computers by Means of Natural Selection" (1992). The foundational work.
- Anthes, Sobania, Rothlauf -- "Transformer Semantic Genetic Programming for Symbolic Regression" (GECCO 2025, Best Paper GP Track). Uses transformers to improve GP crossover semantics. [GECCO](https://gecco-2025.sigevo.org/Best-Paper-Awards)
- "GraphEvol: DAG-based Genetic Programming for Web Service Composition" (2024). Evolves DAGs directly instead of trees. Relevant for workflow evolution.
- Huang et al. -- "Multi-Representation GP (MRGP-TL)" (2024). Co-evolves tree and linear GP representations, cross-representation crossover.
- "Imperative Genetic Programming" (Symmetry, 2024). Evolves syntactically correct Python programs from scratch. [MDPI](https://doi.org/10.3390/sym16091146)
- "LLM-Supervised GP for Behavior Trees" (2025). LLM guides mutation rates and seeds underrepresented behavioral archetypes.

### Implementation Complexity: **High**

### Specific Use Cases in Our System

1. **Workflow DAG Evolution:** Evolve the structure of multi-AI workflows as DAGs. Nodes = agent calls, edges = data flow. GP discovers optimal workflow topologies.
2. **Routing Rule Evolution:** Evolve routing decision trees: `IF task_type == 'code' AND complexity > 0.7 THEN use_model('opus') ELSE ...`. Trees naturally represent conditional routing logic.
3. **Evaluation Pipeline Evolution:** Evolve the evaluation pipeline itself as a program tree.

### Builds On Existing

- Would require new tree-based representation (significant new code)
- Could reuse fitness evaluation infrastructure from `llm_guided_evolution.py`
- Workflow DAG representation connects to existing `workflow-storage-adapter.js`
- DEAP has extensive GP support including typed GP

### Open Source Implementations

- **DEAP** -- Full GP support with strongly-typed GP, tree visualization. [DEAP GP Tutorial](https://deap.readthedocs.io/en/master/tutorials/advanced/gp.html)
- **gplearn** -- Sklearn-compatible symbolic regression via GP
- **TensorGP** -- GPU-accelerated GP
- **PonyGE2** -- Grammar-based GP in Python

---

## 8. Surrogate-Assisted Evolution

### What It Is

Surrogate-assisted evolutionary algorithms (SAEAs) build a **cheap ML model (surrogate) that approximates the expensive fitness function**. Instead of evaluating every individual with expensive API calls, the surrogate pre-screens candidates, and only the most promising are evaluated with the real fitness function. This can reduce fitness evaluations by 10-100x.

This is **extremely relevant** because our fitness evaluations require LLM API calls (slow, rate-limited, costly).

### Key Papers & References

- "Survey: SAEAs for Expensive Combinatorial Optimization" (Complex & Intelligent Systems, May 2024). Comprehensive survey focused on combinatorial problems. [Springer](https://link.springer.com/article/10.1007/s40747-024-01465-5)
- "Survey: SAEAs for Expensive Optimization" (Journal of Membrane Computing, Aug 2024). Introduces framework, construction methods, management strategies. [Springer](https://link.springer.com/article/10.1007/s41965-024-00165-w)
- "SAGPE: Surrogate-Assisted Gray Prediction Evolution" (MDPI Mathematics, March 2025). Global + local surrogate models alternating. [MDPI](https://www.mdpi.com/2227-7390/13/6/1007)
- "SEAMS: Metric-Based Dynamic Strategy for Expensive MOPs" (Expert Systems with Applications, Dec 2024). [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0957417424029178)
- "DSKT-DDEA: Island-Based EA with Diverse Surrogates" (ACM TELO, 2024). Different surrogate per island. [ACM](https://dl.acm.org/doi/10.1145/3700886)
- Gharafi et al. -- "Rank-based Linear-Quadratic Surrogate Assisted CMA-ES" (GECCO 2025). Combines CMA-ES with surrogate.

### Implementation Complexity: **Medium**

### Specific Use Cases in Our System

1. **Prompt Fitness Prediction:** Train a surrogate on (prompt_embedding, fitness_score) pairs from PostgreSQL history. Use pgvector embeddings as input features. The surrogate predicts fitness without making API calls, pre-screening 90% of candidates.
2. **RAG Config Prediction:** Train surrogate on historical (config, quality) pairs from `ga_rag_retrieval_optimizer.py` runs. Predict quality of new configs without running full retrieval pipelines.
3. **Model Selection Prediction:** Given task features, predict which model will perform best without actually querying all models. Train on `monitoring.execution_summary` data.

### Builds On Existing

- **PostgreSQL stores all historical evaluations** -- natural training data for surrogates
- **pgvector provides embeddings** -- can train surrogate on embedding-space features
- `learning.experiences` table contains past fitness evaluations
- `monitoring.execution_summary` has model performance data
- Scikit-learn RandomForest or XGBoost as surrogate (lightweight, fast inference)

### Open Source Implementations

- **pymoo** supports surrogate-assisted optimization
- **scikit-learn** for surrogate model training (RandomForest, GP, SVR)
- **GPyOpt** -- Bayesian optimization (Gaussian Process surrogate)
- **SMAC3** -- Sequential Model-based Algorithm Configuration
- **Optuna** -- Hyperparameter optimization with TPE surrogate

**Sketch implementation:**

```python
from sklearn.ensemble import RandomForestRegressor
import numpy as np

class SurrogateEvaluator:
    def __init__(self, real_evaluator, retrain_every=50):
        self.real_eval = real_evaluator
        self.surrogate = RandomForestRegressor(n_estimators=100)
        self.X_train, self.y_train = [], []
        self.eval_count = 0

    def evaluate(self, individual):
        embedding = get_embedding(individual)

        # Use surrogate if trained and not due for retraining
        if len(self.X_train) > 30 and self.eval_count % self.retrain_every != 0:
            predicted = self.surrogate.predict([embedding])[0]
            if predicted < threshold:  # Skip low-predicted individuals
                return predicted

        # Real evaluation for promising candidates
        real_fitness = self.real_eval(individual)
        self.X_train.append(embedding)
        self.y_train.append(real_fitness)

        # Retrain surrogate periodically
        if len(self.X_train) % 30 == 0:
            self.surrogate.fit(np.array(self.X_train), np.array(self.y_train))

        self.eval_count += 1
        return real_fitness
```

---

## 9. Differential Evolution (L-SHADE)

### What It Is

Differential Evolution (DE) is a population-based optimizer for continuous spaces that creates new candidates by adding **weighted differences between existing population members** to a target vector. Unlike GA, DE has no explicit crossover operator -- the difference vectors naturally encode landscape information.

**L-SHADE** (Linear Population Size Reduction with Success-History based Adaptive DE) is the state-of-the-art variant that **self-adapts all control parameters** (mutation factor F, crossover rate CR) based on a history of successful values, and linearly reduces population size as the search progresses. No hyperparameter tuning required.

### Key Papers & References

- Storn & Price -- "Differential Evolution: A Simple and Efficient Heuristic for Global Optimization" (Journal of Global Optimization, 1997). Original DE paper.
- Tanabe & Fukunaga -- "Success-History Based Parameter Adaptation for DE" (CEC 2013). SHADE.
- Tanabe & Fukunaga -- "Improving the Search Performance of SHADE Using Linear Population Size Reduction" (CEC 2014). L-SHADE.
- "Modified LSHADE-SPACMA with New Mutation Strategy" (Artificial Intelligence Review, Jan 2025). Precise elimination + generation mechanism for better local exploitation. [Springer](https://link.springer.com/article/10.1007/s10462-024-11053-1)
- "Experimental Survey of L-SHADE and SHADE-based Adaptive DE Algorithms" (Swarm and Evolutionary Computation, 2026). Compares 32 L-SHADE variants on CEC benchmarks. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2210650226000064)
- "Fractional-Order Differential Evolution (FCDE)" (CEC 2025). Adds Caputo fractional derivatives for non-local search. Tested on CEC 2025 suite.
- "Novel Hybrid Adaptive DE (APDSDE)" (Scientific Reports, 2024). Adaptive switching between two mutation strategies + cosine similarity parameter adaptation. [Nature](https://www.nature.com/articles/s41598-024-70731-w)

### Implementation Complexity: **Low**

### Specific Use Cases in Our System

1. **Drop-in replacement for GA** in `ga_rag_retrieval_optimizer.py` for continuous parameters (chunk_size, overlap, temperature, top_k). L-SHADE self-adapts F and CR, eliminating tuning.
2. **Embedding Dimension Optimization:** Optimize continuous embedding and retrieval parameters more efficiently than grid search or standard GA.
3. **Thompson Sampling Hyperparameter Optimization:** Tune decay rates, exploration bonuses, prior parameters.

### Builds On Existing

- Can share fitness evaluation infrastructure with `ga_engine.py` and `ga_rag_retrieval_optimizer.py`
- Same REST API integration pattern
- L-SHADE's self-adaptation aligns with our philosophy of minimal hyperparameter tuning

### Open Source Implementations

- **SciPy** `scipy.optimize.differential_evolution` -- basic DE built into SciPy
- **pymoo** includes DE variants
- **DEAP** supports DE
- **Nevergrad** includes multiple DE variants
- **L-SHADE reference implementation** in C++/Python available from CEC competition repos

---

## 10. Neuroevolution / NEAT

### What It Is

NeuroEvolution of Augmenting Topologies (NEAT, Stanley & Miikkulainen 2002) evolves **both the weights and topology** of neural networks. It starts from minimal networks (just inputs and outputs) and incrementally adds complexity (nodes, connections) only when needed. Three key innovations: historical markings enable crossover between different topologies, speciation protects structural innovations, and complexification grows from simple to complex.

### Key Papers & References

- Stanley & Miikkulainen -- "Evolving Neural Networks Through Augmenting Topologies" (Evolutionary Computation, 2002). Original NEAT paper. [MIT Press](https://dl.acm.org/doi/10.1162/106365602320169811)
- "When Does Neuroevolution Outcompete Reinforcement Learning in Transfer Learning Tasks?" (GECCO 2025, Best Paper CS+NE). Key finding: NE beats RL in transfer scenarios. [GECCO](https://gecco-2025.sigevo.org/Best-Paper-Awards)
- "Biologically-Inspired Homeostasis for Neuroevolution: Alternating Growth and Pruning" (2025). Grow-then-prune cycles inspired by neuroscience.
- odNEAT -- "Online and Decentralized NEAT for Multi-Robot Systems." Continuous adaptation during execution. Relevant for fleet-based evolution.

### Implementation Complexity: **High**

### Specific Use Cases in Our System

1. **Routing Network Evolution:** Evolve a small neural network that takes task features (complexity, type, length) as input and outputs model selection weights. NEAT discovers the minimal network topology needed.
2. **Fitness Function Evolution:** Evolve the fitness evaluation network itself -- inputs are prompt features, outputs are fitness scores.

### Builds On Existing

- Would require significant new infrastructure (neural network representation, evaluation)
- Less immediately useful than other techniques given our existing architecture
- Better suited for future iteration when simpler approaches plateau

### Open Source Implementations

- **neat-python** -- Python implementation of NEAT. [neat-python.readthedocs.io](https://neat-python.readthedocs.io/en/latest/neat_overview.html)
- **goNEAT** -- Go implementation (updated Sep 2024). [GitHub](https://github.com/yaricom/goNEAT)
- **DEAP** supports neuroevolution via custom representations
- **EvoTorch** -- GPU-accelerated neuroevolution via PyTorch

---

## 11. Conference & Framework Survey

### GECCO 2025 (Malaga, Spain, July 2025)

The premier EC conference. Key highlights relevant to our system:

- **Best Paper (GP):** "Transformer Semantic Genetic Programming for Symbolic Regression" -- transformers improve GP crossover semantics
- **Best Paper (GECH+Theory):** "Why Dominance Is Not Enough" -- practical lessons for multi-objective algorithms
- **Best Paper (L4EC):** "Importance of Reward Design in RL-based Dynamic Algorithm Configuration" -- RL for adaptive GA parameter tuning
- **Best Paper (CS+NE):** "When Does Neuroevolution Outcompete RL in Transfer Learning?"
- **Competition:** LLM-Designed Evolutionary Algorithms -- growing intersection of LLMs and EC
- **Keynote:** AI Safety through Evolutionary Computation -- diversity, adaptability, robustness
- **1,670-page proceedings + 2,615-page companion volume**

Source: [gecco-2025.sigevo.org](https://gecco-2025.sigevo.org/Best-Paper-Awards)

### CEC 2025 (Hangzhou, China, June 2025)

IEEE's premier EC event. Topics: coevolutionary systems, differential evolution, multi-objective EA, evolutionary NAS, automated metaheuristic design, fairness-aware optimization.

Source: [IEEE Xplore](https://ieeexplore.ieee.org/xpl/conhome/11042929/proceeding)

### PPSN 2024 (Hagenberg, Austria, September 2024)

101 papers from 294 submissions across 4 volumes. Key topics:
- Fitness Landscape Modeling and Analysis
- Bayesian- and Surrogate-Assisted Optimization
- Neuroevolution and Evolutionary Robotics
- Multi-Objective Optimization
- **FunSearch Keynote** (Romera-Paredes, DeepMind): LLM + evaluator in evolutionary loop to discover new mathematics. Directly relevant to our LLM-guided evolution pattern.

Source: [ppsn2024.fh-ooe.at](https://ppsn2024.fh-ooe.at/)

### Framework Comparison

| Framework | Language | Best For | GPU | Multi-Obj | Community |
|-----------|----------|----------|-----|-----------|-----------|
| **pymoo** | Python | Multi-objective (NSGA-II/III) | No | Excellent | High |
| **DEAP** | Python | General-purpose, GP, coevolution | No | Good | Highest |
| **PyGAD** | Python | Simple GA + ML integration | PyTorch | No | Medium |
| **Nevergrad** | Python | Broad algorithm selection, benchmarking | No | Limited | High |
| **EvoTorch** | Python | GPU-accelerated ES, NE | PyTorch | Limited | Medium |
| **EvoX** | Python | Distributed GPU-accelerated | JAX | Good | Growing |
| **pycma** | Python | CMA-ES specifically | No | No | Medium |
| **pyribs** | Python | Quality-Diversity (MAP-Elites) | No | N/A | Growing |

**Recommendation for our system:** `pymoo` for multi-objective, `DEAP` for GP/coevolution, `pycma` for CMA-ES, `pyribs` for MAP-Elites enhancements.

Sources: [pymoo.org](https://pymoo.org/), [DEAP GitHub](https://github.com/DEAP/deap), [Framework Comparison Paper](https://www.informatica.vu.lt/journal/INFORMATICA/article/1384/text)

---

## 12. LLM + Evolution Hybrids

This is the **most active and directly relevant research frontier** for our system.

### Key Frameworks & Papers

1. **EvoPrompt** (Guo et al., ICLR 2024): LLM-based crossover and mutation for discrete prompt optimization. Up to 25% improvement over human-engineered prompts on BBH benchmarks. [arXiv](https://arxiv.org/abs/2309.08532), [GitHub](https://github.com/beeevita/EvoPrompt)

2. **Promptbreeder** (Fernando et al., 2024): **Co-evolutionary** approach that simultaneously evolves task prompts AND mutation instructions. The mutation operators themselves evolve. Highly relevant to our system.

3. **ReEvo** (Ye et al., 2024): "Large Language Models as Hyper-Heuristics with Reflective Evolution." LLMs generate and refine heuristics via evolutionary search with reflection. [arXiv:2402.01145](https://arxiv.org/abs/2402.01145)

4. **FunSearch** (Romera-Paredes et al., DeepMind, Nature 2024): LLM paired with evaluator in evolutionary loop discovers new mathematical constructs. The LLM generates candidate functions as code, the evaluator scores them, and evolution selects the best. **This is exactly our architecture** (LLM-guided evolution + fitness evaluation).

5. **LLMs as Evolution Strategies** (Lange et al., 2024): Treats LLMs themselves as evolution strategies -- the LLM implicitly performs selection, crossover, and mutation in a single forward pass. [arXiv:2402.18381](https://arxiv.org/abs/2402.18381)

6. **PhaseEvo** (Cui, 2024): Multi-phase pipeline alternating between instruction refinement and exemplar selection.

7. **LLaMoCo** (Ma et al., 2024): Instruction-tuned LLMs for optimization code generation. The LLM generates optimization algorithms. [arXiv:2403.01131](https://arxiv.org/abs/2403.01131)

8. **Comprehensive Survey** (May 2025): "Evolutionary Computation and Large Language Models: A Survey of Methods, Synergies, and Applications." Catalogs four categories: LLMs for Modeling, LLMs as Optimizers, Low-level LLMs for Optimization, High-level LLMs for Optimization. [arXiv](https://arxiv.org/html/2505.15741v1)

### MAP-Elites + LLM

9. **Diverse Prompts** (April 2025): MAP-Elites + context-free grammar to explore prompt space with quality AND diversity. [arXiv](https://arxiv.org/abs/2504.14367)

10. **Rainbow Teaming** (Samvelyan et al., 2024): MAP-Elites for diverse adversarial prompt generation. Evolves over learned embedding space.

11. **CycleQD** (ICLR 2025): Quality-Diversity with cyclic MAP-Elites for multi-skill LLM agents. Model merging as crossover, SVD-based mutation. [ICLR](https://proceedings.iclr.cc/paper_files/paper/2025/file/755acd0c7c07180d78959b6d89768207-Paper-Conference.pdf)

12. **QD-LLM** (May 2025): Quality-Diversity via prompt embedding evolution. CVT-MAP-Elites with adaptive expansion. [arXiv](https://arxiv.org/html/2605.09781)

### Community & Events

- **EvoLLMs Special Session at EvoStar 2025** -- Dedicated to LLM+EC synergies. [evostar.org](https://www.evostar.org/2025/evoapps/evollms/)
- **LLM4EC GitHub** -- Curated paper list. [GitHub](https://github.com/wuxingyu-ai/LLM4EC)
- **LLM_EA GitHub** -- Evolutionary Algorithm + LLM paper collection. [GitHub](https://github.com/xiaofangxd/LLM_EA)

### Key Insight

Our `llm_guided_evolution.py` and `map_elites.py` are already implementing patterns from the cutting edge of this field. The next natural steps are:
- Add **Promptbreeder-style mutation operator evolution** (evolve the mutation instructions themselves)
- Add **CycleQD-style multi-skill optimization** (each behavior dimension gets its own optimization cycle)
- Add **surrogate pre-screening** to reduce API calls

---

## 13. Fitness Landscape Analysis

### What It Is

Fitness Landscape Analysis (FLA) characterizes the structure of the search space to guide algorithm selection and parameter tuning. It answers: Is the landscape smooth or rugged? How many local optima? How deceptive?

### Key Techniques

1. **Autocorrelation Analysis:** Measures how fitness correlates across nearby solutions. High autocorrelation = smooth landscape (CMA-ES good). Low = rugged (GA/novelty search better).
2. **Local Optima Networks (LONs):** Graphs connecting local optima, visualizing the landscape structure. Shows basin sizes, transition probabilities.
3. **Search Trajectory Networks (STNs):** Track algorithm behavior through the landscape. Identify stagnation zones.
4. **Exploratory Landscape Analysis (ELA):** Suite of features characterizing black-box problems. Used for automated algorithm selection.
5. **NK Models:** Tunable landscapes with varying epistasis (interaction between genes). Good for controlled experiments.

### Key Papers

- "Characterizing Fitness Landscape Structures in Prompt Engineering" (arXiv, 2025). **Directly relevant** -- measures ruggedness of prompt optimization landscapes. Found that evolutionary algorithms outperform local optimization precisely because prompt landscapes are rugged and epistatic. [arXiv](https://arxiv.org/html/2509.05375v1)
- "Fitness Landscape Optimization Makes Stochastic Symbolic Search by GP Easier" (IEEE TEVC, 2025). Optimizing the landscape itself to help GP.
- "Fitness Landscape Analysis for Malware Evolution" (GECCO 2024). Uses STNs for novel domain.
- "From Valleys to Peaks: Role of Evolvability in Fitness Landscape Navigation" (PNAS Nexus, 2025). Computational NK model framework. [Oxford](https://academic.oup.com/pnasnexus/article/4/8/pgaf221/8206746)

### Use Cases for Our System

1. **Algorithm Selection:** Analyze whether prompt fitness landscapes are smooth (use CMA-ES) or rugged (use GA/novelty search). The 2025 prompt landscape paper suggests rugged.
2. **Convergence Monitoring:** Track landscape features over generations to detect stagnation or convergence.
3. **Adaptive Strategy Switching:** Switch between algorithms based on landscape characteristics (smooth region -> CMA-ES, rugged -> GA).

---

## 14. Top 8 Most Implementable Techniques

Ranked by (impact on our system) x (implementation feasibility) / (effort required):

### Rank 1: NSGA-II Multi-Objective Optimization

**Priority: IMMEDIATE (this week)**
**Estimated Time: 1-2 days**
**Impact: Very High**

- **Why #1:** We already optimize multiple objectives (quality, cost, latency, diversity) but collapse them into weighted sums. NSGA-II gives the full Pareto front -- dramatically better decision-making.
- **Implementation:** Use `pymoo` (production-ready, Deb's own student's code). Replace weighted fitness in `ga_rag_retrieval_optimizer.py` and `ga_engine.py` with multi-objective fitness. Existing crossover/mutation operators work unchanged.
- **Dependencies:** `pip install pymoo`
- **Builds on:** `ga_engine.py`, `ga_rag_retrieval_optimizer.py`
- **Reference:** [pymoo NSGA-II docs](https://pymoo.org/algorithms/moo/nsga2.html)

### Rank 2: Island Model for Fleet-Parallel Evolution

**Priority: HIGH (next sprint)**
**Estimated Time: 2-3 days**
**Impact: Very High**

- **Why #2:** Our 8-worker fleet is literally 8 islands waiting to happen. Each worker evolves a sub-population independently, Redis handles migration. 8x speedup with better diversity.
- **Implementation:** Wrap `ga_engine.py` in island coordinator. Each worker runs GA independently via SSH. Redis pub/sub for migration events. aio-01 REST API stores global archive.
- **Dependencies:** Existing fleet infrastructure, Redis
- **Builds on:** `ga_engine.py`, fleet SSH, Redis on aio-01
- **Reference:** [DEAP coevolution](https://deap.readthedocs.io/en/master/examples/coev_coop.html)

### Rank 3: Surrogate-Assisted Evolution

**Priority: HIGH (next sprint)**
**Estimated Time: 2-3 days**
**Impact: High**

- **Why #3:** Every fitness evaluation costs API calls. A surrogate model trained on PostgreSQL history can pre-screen 90% of candidates, reducing API usage by 10x.
- **Implementation:** Train RandomForest/XGBoost on (prompt_embedding, fitness) pairs from `learning.experiences`. Pre-screen candidates, only evaluate top 10% with real API calls.
- **Dependencies:** `scikit-learn` (likely already installed), existing PostgreSQL data
- **Builds on:** `llm_guided_evolution.py`, PostgreSQL history, pgvector embeddings
- **Reference:** [SAGPE paper](https://www.mdpi.com/2227-7390/13/6/1007)

### Rank 4: CMA-ES for Continuous Parameters

**Priority: MEDIUM (2-week horizon)**
**Estimated Time: 1 day**
**Impact: Medium-High**

- **Why #4:** Optimal for continuous parameter tuning (temperatures, chunk sizes, overlap ratios). Zero hyperparameter tuning needed. Drop-in for `ga_rag_retrieval_optimizer.py` continuous params.
- **Implementation:** `pip install cma`, wrap existing fitness functions, run. Literally a few dozen lines of code.
- **Dependencies:** `pip install cma`
- **Builds on:** `ga_rag_retrieval_optimizer.py` fitness functions
- **Reference:** [pycma](https://cma-es.github.io/)

### Rank 5: Coevolution (Prompts vs. Evaluators)

**Priority: MEDIUM (2-week horizon)**
**Estimated Time: 3-4 days**
**Impact: High**

- **Why #5:** Creates an evolutionary arms race between prompts and evaluation criteria. Prevents evaluator gaming and drives genuine quality improvement. Aligns with our review/meta-review panel architecture.
- **Implementation:** Two populations in `llm_guided_evolution.py`. Population A = prompts, Population B = evaluation rubrics. Fitness of prompts = how well they score on evolved evaluators. Fitness of evaluators = how discriminating they are.
- **Dependencies:** Extends existing `llm_guided_evolution.py`
- **Builds on:** `llm_guided_evolution.py`, review/meta-review panel separation
- **Reference:** [GECCO 2025 coevolution paper](https://dspace.mit.edu/bitstream/handle/1721.1/162637/3712255.3726712.pdf)

### Rank 6: L-SHADE Self-Adaptive DE

**Priority: MEDIUM (3-week horizon)**
**Estimated Time: 1-2 days**
**Impact: Medium**

- **Why #6:** Drop-in replacement for standard GA on continuous problems. Self-adapts mutation/crossover rates -- no tuning. Good for comparison benchmarking against our existing GA.
- **Implementation:** Implement SHADE parameter adaptation over existing DE framework, or use `scipy.optimize.differential_evolution` with custom callbacks.
- **Dependencies:** `scipy` (already installed)
- **Builds on:** Can share fitness functions with `ga_engine.py`
- **Reference:** [Experimental Survey](https://www.sciencedirect.com/science/article/abs/pii/S2210650226000064)

### Rank 7: Novelty Search + MAP-Elites Enhancement

**Priority: MEDIUM (3-week horizon)**
**Estimated Time: 2 days**
**Impact: Medium**

- **Why #7:** We already have MAP-Elites. Adding explicit novelty scoring (k-nearest-neighbor distance in behavior space via pgvector) prevents archive stagnation and improves diversity.
- **Implementation:** Add novelty score calculation to `map_elites.py`. Use pgvector for fast k-NN queries in behavior space. Combine with existing fitness as multi-objective (quality + novelty).
- **Dependencies:** Existing pgvector infrastructure
- **Builds on:** `map_elites.py`, pgvector
- **Reference:** [Diverse Prompts paper](https://arxiv.org/abs/2504.14367)

### Rank 8: Memetic Algorithm Formalization

**Priority: LOW (backlog)**
**Estimated Time: 1 day**
**Impact: Medium**

- **Why #8:** We essentially already have a memetic algorithm in `llm_guided_evolution.py` (GA + LLM local search). Formalizing it adds explicit separation of global/local phases and configurable local search intensity.
- **Implementation:** Refactor `llm_guided_evolution.py` to have explicit `global_search()` (crossover/mutation) and `local_search()` (LLM polish) phases. Add configurable `local_search_steps` parameter.
- **Dependencies:** None new
- **Builds on:** `llm_guided_evolution.py` directly
- **Reference:** [MDPI memetic paper](https://www.mdpi.com/2076-3417/15/15/8735)

---

### Techniques Deferred (High Complexity, Lower Immediate ROI)

| Technique | Why Deferred | Revisit When |
|-----------|-------------|--------------|
| **Genetic Programming** | High complexity, needs tree representation, new crossover/mutation operators | After simpler techniques plateau; for workflow DAG evolution |
| **NEAT / Neuroevolution** | Very high complexity, needs NN infrastructure, limited immediate use case | When we need to evolve the routing network architecture itself |

---

### Implementation Dependency Graph

```
Phase 1 (Immediate):
  NSGA-II  -----> replaces weighted fitness in ga_engine.py + ga_rag_retrieval_optimizer.py

Phase 2 (Next Sprint):
  Island Model -----> wraps ga_engine.py for 8-worker parallel evolution
  Surrogate   -----> pre-screens candidates for llm_guided_evolution.py

Phase 3 (2-Week Horizon):
  CMA-ES      -----> continuous params in ga_rag_retrieval_optimizer.py
  Coevolution -----> extends llm_guided_evolution.py with dual populations

Phase 4 (3-Week Horizon):
  L-SHADE     -----> benchmarking alternative to GA for continuous
  Novelty     -----> enhances map_elites.py with explicit novelty scoring
  Memetic     -----> formalizes llm_guided_evolution.py structure
```

---

### Total Estimated Implementation Time

- Phase 1: 1-2 days
- Phase 2: 4-6 days
- Phase 3: 4-5 days
- Phase 4: 4-5 days
- **Total: ~13-18 days for all 8 techniques**

### Key Dependencies to Install

```bash
pip install pymoo        # NSGA-II/III multi-objective
pip install cma          # CMA-ES
pip install pyribs       # Quality-Diversity enhancements
pip install scikit-learn # Surrogate models (likely already installed)
# scipy already available for differential_evolution
# DEAP for GP/coevolution if needed later
```

---

*Research compiled 2026-07-26 by autonomous research agent. Sources verified via web search. All implementation estimates assume existing infrastructure (fleet, REST API, PostgreSQL, Redis) is operational.*
