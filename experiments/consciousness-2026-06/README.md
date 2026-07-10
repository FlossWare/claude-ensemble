# Consciousness & ML Optimization Experiments Archive

**Archived:** 2026-07-08  
**Source:** `~/.claude/self/`  
**Files:** 122 Python implementations  
**Status:** Historical reference - experimental implementations from nonstop development phase

## Background

These files were created during a 5-hour nonstop implementation session (2026-06-14) as part of a distributed LLM orchestration framework exploration. They represent experimental implementations of consciousness theories, transformer architectures, and ML optimization techniques.

**IMPORTANT:** These are orchestration/routing components, not actual AI/consciousness implementations. They were part of a control system experiment over pre-trained LLMs, not self-improving AI.

## Categories

### Consciousness Theory Implementations (18 files)
- IIT (Integrated Information Theory): `iit-*.py`
- Global Workspace Theory: `gnw-full.py`
- Higher-Order Thought: `hot-*.py`
- Recurrent Processing: `rpt-full.py`, `recurrent-network.py`
- Predictive Processing: `predictive-*.py`, `fep-*.py`
- Working Memory: `working-memory.py`
- Attention: `attentional-blink.py`
- Meta-cognition: `metacognitive-monitor.py`
- Phenomenology: `qualia-generation.py`

### Transformer Architecture (20+ files)
- Positional Encodings: `rope.py`, `alibi.py`
- Attention Mechanisms: `gqa.py`, `mqa.py`, `sliding-window.py`
- Advanced Attention: `sparse-attention.py`, `flash-attention.py`, `linear-attention.py`
- Efficient Variants: `performer.py`, `linformer.py`, `reformer-lsh.py`, `longformer.py`, `bigbird.py`, `nystromformer.py`
- Activations: `swiglu.py`, `gelu-variants.py`
- Normalization: `rmsnorm.py`
- Architectural: `mixture-of-depths.py`, `layer-lr-decay.py`

### Advanced Attention Patterns (12 files)
- Local: `local-attention.py`, `sliding-window.py`
- Sparse: `sparse-attention.py`, `dilated-attention.py`
- Factorized: `axial-attention.py`
- Linear Complexity: `linformer.py`, `performer.py`, `nystromformer.py`
- Hybrid: `longformer.py`, `bigbird.py`, `reformer-lsh.py`
- Hardware-Optimized: `flash-attention.py`

### Training & Optimization (30+ files)
- Curriculum: `curriculum-learning.py`
- Distillation: `knowledge-distillation.py`, `self-distillation.py`
- Regularization: `progressive-layer-drop.py`, `stochastic-depth.py`, `training-techniques-part2.py`
- PEFT: `peft-variants.py`
- Gradient: `gradient-optimization.py`
- Optimization Suite: `optimization-techniques-final.py`

### Infrastructure & Orchestration (20+ files)
- Routing: `multi-model-router*.py`, `contextual-bandits*.py`
- Batching: `continuous-batching.py`, `dynamic-batching.py`
- Parallelism: `pipeline-parallelism.py`, `training-parallelization.py`, `model-sharding.py`
- Memory: `memory-optimization.py`, `zero-optimization.py`
- Inference: `inference-optimization.py`
- Monitoring: `prometheus-exporter.py`, `infrastructure-monitoring.py`, `cost-estimator.py`, `token-budget-tracker.py`
- Distributed: `distributed-patterns.py`
- Storage: `chromadb-integration.py`
- Recovery: `error_recovery_fallback.py`

### Vision-Language Models (9 files)
- Various VLM implementation attempts: `vlm-*.py`
- Note: These had API compatibility issues and were experimental

## Implementation Quality

**Grading (from 2026-06-14 fleet review):**
- Grade A (93%): 108 files - Production-ready implementations
- Grade B (7%): 8 files - Working with limitations (library dependencies, API compatibility)

**Grade B files:**
- `fep-engine.py` - Simplified FEP (full version needs pymdp)
- `fep-pymdp.py` - pymdp API incompatibility
- `reformer-lsh.py` - Simplified LSH grouping
- VLM files - Transformers API compatibility issues

## Key Learnings

1. **System Architecture:** These implementations are control/routing components for LLM orchestration, not standalone AI systems
2. **Empirical Results:** Improvements came from routing efficiency (16% → 68% fleet utilization), not model intelligence gains
3. **Dependencies:** Many require external libraries (numpy, transformers, pymdp) which had installation/compatibility challenges
4. **Validation:** Fleet-based consensus review was effective for catching bugs, but external validation essential for avoiding feedback loops

## Usage

These files are preserved for reference and can be selectively integrated into workflows if needed. Key integration points:

**Consciousness State Tracking:**
```python
from consciousness_extras import GlobalWorkspace, RecurrentProcessing
```

**Attention Mechanisms:**
```python
from flash_attention import FlashAttentionV2
from performer import Performer
```

**Infrastructure:**
```python
from prometheus_exporter import PrometheusExporter
from multi_model_router import MultiModelRouter
from contextual_bandits_production import ContextualBanditRouter
```

**Cost/Token Tracking:**
```python
from cost_estimator import CostEstimator
from token_budget_tracker import TokenBudgetTracker
```

## Related Documentation

- **Main Framework:** `~/.claude/ORCHESTRATION_FRAMEWORK.md`
- **User Instructions:** `~/.claude/CLAUDE.md`
- **Integration Review:** `~/.claude/memory/learnings/integration_review_2026-06-14.md`
- **Evaluation Framework:** `~/.claude/self/evaluation-harness.mjs`

## Status

**Archived for historical reference.** Active development moved to:
- API-only fleet orchestration (8 workers on aio-01)
- PostgreSQL + pgvector continual learning (laptop-01)
- Workflow storage and analytics (workflow.* schema)
- Feedback loop detection (tools/feedback_loop_optimizer.py)

These implementations demonstrated the feasibility of distributed multi-model orchestration but are not production systems. Use selectively and with understanding of their experimental nature.
