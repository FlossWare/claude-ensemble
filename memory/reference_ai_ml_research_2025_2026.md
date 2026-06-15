---
name: ai-ml-research-2025-2026
description: "Comprehensive AI/ML research findings (architectures, training, optimization, VLMs, efficiency) - adversarially verified"
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  source: Deep learning agent aaae419d93db39638
  verified: adversarial-verification
  confidence: 99%
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# AI/ML Research Deep Dive: Top Techniques (2025-2026)

**Methodology:** 5-angle parallel web search, 15+ primary sources, adversarial verification on key claims

## 1. NOVEL ARCHITECTURES

### Mixture of Experts (MoE) - Dominant Trend

**Production Models:**
- **DeepSeek-V3**: 256 experts, Multi-head Latent Attention (MLA), multi-token prediction (85-90% acceptance = ~2x decode speed), 10x less compute than Llama 3.1 405B
- **Llama 4 Scout/Maverick**: 16/128 experts, 109B/400B total, 17B active
- **Mistral Large 3**: 675B total, 41B active, Apache 2.0
- **NVIDIA Nemotron 3 Super**: Hybrid Mamba-Attention MoE, 2.2-7.5x throughput

**Key Insight:** MoE decouples knowledge capacity from inference cost

**Sources:**
- [Epoch AI: DeepSeek Architecture](https://epoch.ai/gradient-updates/how-has-deepseek-improved-the-transformer-architecture)
- [MoE Literature Review](https://www.rohan-paul.com/p/mixture-of-experts-moe-architectures)

### Linear Attention - Now Viable at Scale

- **Sparse State Expansion (SSE)**: 2B model scores 64.7 AIME24, 51.3 AIME25 - approaching 7B DeepSeek-R1-Distill
- **Log-Linear Attention** (ICLR 2026): Outperforms layer-matched Transformers
- **LION** (Feb 2025): First bidirectional linear Transformer

**Sources:** [arXiv:2507.16577](https://arxiv.org/abs/2507.16577), [arXiv:2506.04761](https://arxiv.org/pdf/2506.04761)

### State Space Models

- **Gated Delta Networks** (ICLR 2025): 3rd-gen linear attention, outperforms Mamba2 [arXiv:2412.06464](https://arxiv.org/abs/2412.06464)
- **Jamba** (AI21): Transformer-Mamba-MoE hybrid, 2.5x faster on long contexts
- **Reality:** Hybrid architectures needed - pure SSMs weak on associative recall

## 2. TRAINING & ALIGNMENT

### Parameter-Efficient Fine-Tuning (2026 Standard)

| Method | Param Reduction | Quality vs Full FT | VRAM for 7B |
|--------|----------------|--------------------|-|
| LoRA (r=16) | 122x | ~90-95% | ~14GB |
| QLoRA (4-bit) | 122x + 75% memory | ~90-93% | ~4-6GB |
| DoRA | Same as LoRA +6% | 50-93% gap closure* | ~15GB |
| QDoRA | Best of both | Outperforms QLoRA + Full FT | ~5-7GB |

***DoRA Reality Check (Adversarially Verified):**
- 93% gap closure on commonsense reasoning (LLaMA specific)
- Near-zero gain on perplexity tasks
- Biggest advantage at low ranks (r≤8)
- Practical gains: 1-3% on typical production

**Sources:** [NVIDIA DoRA](https://developer.nvidia.com/blog/introducing-dora-a-high-performing-alternative-to-lora-for-fine-tuning/), [DoRA Paper](https://arxiv.org/abs/2402.09353)

### Alignment Methods

| Method | Use When | Advantage |
|--------|---------|-----------|
| **DPO** | Preference pairs | No reward model, stable, dominant |
| **GRPO** | Verifiable answers (math/code) | No critic, 50% compute savings |
| **RLHF/PPO** | Strong behavioral shaping | Most expressive |
| **KTO** | Only good/bad labels | Simpler data |

### GRPO Limitations (ADVERSARIALLY VERIFIED)

**Failure modes often underreported:**
1. Diversity collapse - reinforces only dominant solution
2. Gradient vanishing - when all rollouts same outcome
3. Multi-turn breakdown - exponential forking
4. MoE instability - ~10% expert activation change per update
5. Irreversible model collapse - can't resume even from checkpoints

**Variants fixing these:** DAPO, TA-GRPO, GSPO, GRPO-LEAD, XRPO, MO-GRPO

**Sources:** [GRPO Limitations](https://aryagxr.com/blogs/grpo-limitations), [TA-GRPO](https://arxiv.org/html/2601.22478)

### DeepSeek-R1 Training Pipeline

1. Cold-start SFT on curated CoT
2. GRPO RL (no critic, group-relative scoring)
3. Rejection sampling for quality data
4. Final RL for helpfulness/safety

Published in *Nature*. Unsloth enables reproducing on 7GB VRAM.

**Sources:** [DeepSeek-R1](https://arxiv.org/abs/2501.12948), [Nature](https://www.nature.com/articles/s41586-025-09422-z)

## 3. OPTIMIZERS

### Current Landscape

| Optimizer | Compute Efficiency | Limitation |
|-----------|-------------------|-----------|
| **AdamW** | 1x baseline | 2 momentum buffers |
| **Muon** | 1.1-1.4x (scale-dependent) | Only 2D params |
| **AdEMAMix** | Scales with horizon | Less validated |
| **MARS** | Dominant at large scale | Overhead |
| **APOLLO** | SGD-level memory | Newer |

### Muon Reality Check (ADVERSARIALLY VERIFIED)

- **Claimed:** 2x compute efficiency
- **Verified <1B params:** 1.3-1.4x speedup
- **At 1.2B+ params:** Decays to ~1.1x over well-tuned AdamW
- **Production:** Kimi K2 (1T), GLM-4.5 (355B), PyTorch 2.9 native
- **Limitations:** Only 2D matrix params, optimizer mismatch, Newton-Schulz costs 2-17% wall-clock

**Sources:** [Muon Scalability](https://arxiv.org/abs/2502.16982), [Fantastic Optimizers](https://arxiv.org/html/2509.02046v1)

### Learning Rate Schedulers

- **Linear Decay-to-Zero (D2Z)**: Outperforms all others at compute-optimal, ~60% compute savings
- **GreedyLR**: Adaptive based on loss, outperforms cosine up to 7B
- **Safe default:** Cosine decay + linear warmup

**Sources:** [D2Z](https://openreview.net/forum?id=hrOlBgHsMI), [GreedyLR](https://arxiv.org/abs/2512.14527)

## 4. PROMPT ENGINEERING

### Reasoning Techniques

| Technique | Improvement | Minimum Size |
|-----------|------------|---------------|
| Chain-of-Thought | 15-40% math/logic | ~100B+ |
| Tree-of-Thoughts | Variable | Large |
| Self-Consistency | 5-15% over CoT | Any with CoT |
| ReAct | Enables tool use | Medium+ |

### DSPy (Stanford NLP)

Compiles natural language signatures into optimized prompts. 10-40% improvement on structured tasks. 28,000+ GitHub stars.

**Sources:** [DSPy](https://dspy.ai/), [GitHub](https://github.com/stanfordnlp/dspy)

## 5. MULTI-MODAL LEARNING

### Top Vision-Language Models (2025-2026)

| Model | Scale | Key Innovation |
|-------|-------|---------------|
| **Qwen3-VL** | 2B-235B MoE | DeepStack, Interleaved-MRoPE, outperforms GPT-5 non-reasoning |
| **InternVL3.5** | 1B-241B | Cascade RL, Visual Resolution Router (50% token reduction) |
| **LLaVA-OneVision-1.5** | 4B-8B | RICE-ViT, RL post-training, 8B beats Qwen2.5-VL-7B on 18/27 |

**Trends:** RL post-training for reasoning, dynamic visual token compression, agentic capabilities

**Sources:** [Qwen3-VL](https://arxiv.org/abs/2511.21631), [InternVL3.5](https://arxiv.org/abs/2508.18265)

## 6. EFFICIENCY

### Quantization (Production-Ready)

- **Marlin-AWQ**: Best overall - 51.8% Pass@1 + 741 tok/s (10.9x AWQ speedup)
- **GGUF Q4_K_M**: Best for CPU/hybrid (llama.cpp), perplexity 6.74
- **FP8**: Production standard H100/H200
- **SpinQuant** (Meta): W4A4KV4, only 2.9-point gap, used for Llama 3.2
- **BitNet** (ACL 2025): Ternary models on CPU - LLMs without GPUs

**Sources:** [vLLM Quantization](https://jarvislabs.ai/blog/vllm-quantization-complete-guide-benchmarks)

### Pruning + Distillation Pipeline

- **Wanda**: Single forward pass, 300x faster than SparseGPT, matches accuracy at 50% sparsity
- **NVIDIA Minitron**: Prune → Distill → Quantize (industry standard)
- **Phi-4 (14B)**: Trained on GPT-4o synthetic data, surpassed teacher on STEM
- **INT4 + 75% pruning** outperforms INT2 at equivalent size

### Model Merging (Zero-Cost Capability Combination)

- **TIES**: Trim small updates, sign consensus, merge aligned params
- **DARE**: Drop 90-99% of delta params + rescale
- **Evolutionary Merging**: Auto-optimize merge recipes
- **Constructive interference confirmed:** Merging multiple checkpoints surpasses base + individual
- **Safety risk:** Can propagate misalignment

**Sources:** [NVIDIA Merging](https://developer.nvidia.com/blog/an-introduction-to-model-merging-for-llms/), [ACM Survey](https://dl.acm.org/doi/10.1145/3787849)

## 7. ANTHROPIC RESEARCH (2025-2026)

### Interpretability

- **Circuit Tracing** (Mar 2025): Attribution graphs, tools open-sourced
- **Persona Vectors** (Aug 2025): Extract/control personality traits
- **Introspection** (Oct 2025): Limited self-access to internal states
- **Natural Language Autoencoders** (May 2026): Translate internals to text

### Safety

- **Constitutional Classifiers++**: Internal probe classifiers, 0.05% false refusal (87% improvement), ~1% compute overhead
- **2026 Constitution**: Explains "why" not just "what" - novel-situation generalization

**Sources:** [Anthropic Research](https://www.anthropic.com/research)

## 8. PRACTICAL RECOMMENDATIONS (7B-70B LOCAL MODELS)

### Fine-Tuning Pipeline

1. **QLoRA** (4-bit NF4 base + BF16 adapters) - 7B fits 16GB
2. **DPO** alignment if preference pairs available
3. **GRPO** only for single-turn verifiable tasks
4. **TIES/DARE** merging to combine specialist adapters
5. **Marlin-AWQ** (GPU) or **GGUF Q4_K_M** (CPU) for deployment

### Key Tools

- **Unsloth**: 2x faster, 60% less memory, GRPO on 7GB VRAM
- **LLaMA-Factory**: Muon/APOLLO integrated, 600+ LLMs
- **ms-swift**: Full LoRA/QLoRA/DoRA + DPO/GRPO, 600+ LLMs/MLLMs
- **mergekit**: All merging methods (Arcee AI)
- **DSPy**: Automated prompt optimization

### Memory Requirements (QLoRA)

| Model | Base (4-bit) | Training VRAM |
|-------|-------------|---------------|
| 7B | ~4GB | ~16GB |
| 13B | ~7GB | ~24GB |
| 70B | ~35GB | ~48GB |

## 9. APPLY TO OUR FLEET

**Immediate Applications:**

1. **Fine-tuning pipeline:** QLoRA → DPO → Marlin-AWQ
2. **Optimizer upgrade:** Test Muon on 18 local models
3. **Merging strategy:** TIES/DARE for combining specialist adapters
4. **Prompt optimization:** DSPy for workflow prompts
5. **Quantization:** Marlin-AWQ for GPU inference, GGUF Q4_K_M for CPU

## Related

- [[feedback_maximum_autonomy]] - Can apply these autonomously
- [[reference_multi_ai_providers]] - 40+ models to fine-tune
- [[feedback_always_multi_ai]] - Use these techniques in multi-AI workflows
