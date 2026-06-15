# Production Workflows Using Grade A Implementations

Built on 108 Grade A implementations from the distributed LLM orchestration framework.

## Workflows

### 1. Model Optimization (`model-optimization.js`)

Demonstrates transformer optimizations for memory/compute efficiency.

**Components:**
- GQA (4× KV cache reduction)
- RMSNorm (efficient normalization)
- SwiGLU (modern activation)
- Cost estimator (savings tracking)

**Run:** `node ~/.claude/workflows/model-optimization.js`

**Output:** Component verification, optimization demo, ~15% cost savings estimate

### 2. Continual Learning Monitor (`continual-learning-monitor.js`)

Records experiences to PostgreSQL with Prometheus metrics and Thompson Sampling.

**Components:**
- PostgreSQL + pgvector (0.4ms queries)
- 128-dim embedding storage
- Thompson Sampling strategy selection
- Prometheus metrics exporter

**Run:** `node ~/.claude/workflows/continual-learning-monitor.js`

**Metrics:** http://localhost:9100/metrics, Dashboard: http://pi-02:3000

### 3. Multi-AI Consensus (`multi-ai-consensus.js`)

6-model consensus (Opus/Sonnet/Haiku/Fable/GPT-4o/Gemini) with cost tracking.

**Components:**
- Multi-model router (6 models)
- Parallel worker execution
- Arbiter synthesis
- PostgreSQL cost tracking

**Run:** `node ~/.claude/workflows/multi-ai-consensus.js --task "Your question"`

**Output:** 6 worker analyses, arbiter decision, per-model costs, total cost

## Architecture

1. **Phase-based execution** - Progress tracking via meta.phases
2. **Python implementations** - ML/AI code in ~/.claude/self/
3. **JavaScript orchestration** - Workflow coordination
4. **PostgreSQL storage** - Persistent learning (laptop-01)
5. **Prometheus metrics** - Observable behavior

## Performance

- **Database:** 0.4ms avg (pgvector HNSW index)
- **Workflow exec:** 2-5s (Python computation)
- **Multi-AI consensus:** ~30s (6 models + arbiter)

## Available Grade A Components

**Transformer:** rope, alibi, gqa, mqa, sliding-window, swiglu, rmsnorm, layer-lr-decay, mixture-of-depths

**Attention:** sparse-attention, local-attention, dilated-attention, axial-attention, linformer, longformer, performer, bigbird, nystromformer

**Training:** curriculum-learning, knowledge-distillation, self-distillation

**Infrastructure:** prometheus-exporter, multi-model-router, token-budget-tracker, cost-estimator

**Consciousness:** recurrent-network, predictive-coding, attentional-blink, working-memory, iit-phi-corrected, hot-enhanced

See `~/.claude/CLAUDE.md` for full list (108 Grade A + 8 Grade B = 116 total).
