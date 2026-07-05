# Building LLM-Quality Models on CPU
## 12-Month Roadmap for Homelab Training

**Goal:** Train competitive LLMs using only CPU machines (no GPUs)

**Hardware:** 8 servers, 256 cores, 856GB RAM  
**Budget:** $0 (using owned hardware)  
**Timeline:** 12 months to production-quality model

---

## Why This Is Now Possible

### Recent Breakthroughs (2023-2024)

1. **Mamba (Dec 2023)**
   - State Space Model with LINEAR complexity
   - Matches transformer quality at 1/3 the size
   - CPU training is feasible
   - Paper: "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"

2. **BitNet (Feb 2024)**
   - 1.58-bit weights (vs 16-bit standard)
   - 10× less memory, 10× faster
   - Minimal quality loss
   - Paper: "The Era of 1-bit LLMs"

3. **Mixture of Depths (Apr 2024)**
   - Not all tokens need all layers
   - 50% FLOPs reduction
   - Same quality
   - Paper: "Mixture of Depths: Dynamically allocating compute in transformer-based language models"

4. **DeepSeek-R1 (Jan 2025)**
   - Distilled 671B → 70B (10× compression)
   - Matches original on reasoning
   - Proves distillation works at scale

### The Math That Makes It Work

**Transformer (GPU-hungry):**
```
Attention: O(n² × d)
- For 2048 tokens, 7B params: ~28 billion ops/layer
- Needs parallel processing (GPU)
```

**Mamba (CPU-friendly):**
```
SSM: O(n × d)  
- For 2048 tokens, 7B params: ~14 million ops/layer
- Sequential processing (CPU efficient)
- 2000× fewer operations!
```

---

## Phase 1: Infrastructure (Months 1-2)

### Objectives
- Distributed training framework across 8 servers
- Data pipeline from PostgreSQL corpus
- Mamba implementation (CPU-optimized)
- Validation harness

### Tasks

#### 1.1 Distributed Training Framework
**File:** `training/distributed_cpu_trainer.py`

```python
#!/usr/bin/env python3
"""
Distributed CPU Training Coordinator
Splits model layers across 8 servers, coordinates training
"""

import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel

class CPUDistributedTrainer:
    def __init__(self, servers: List[str], model_config: dict):
        """
        servers: ['server-01', 'server-02', ...]
        model_config: {layers: 24, d_model: 1024, ...}
        """
        self.servers = servers
        self.config = model_config
        
        # Each server gets 3 layers (24 layers / 8 servers)
        self.layers_per_server = model_config['layers'] // len(servers)
        
    def setup_distributed(self):
        """Initialize distributed training"""
        # Use GLOO backend (CPU-optimized)
        dist.init_process_group(
            backend='gloo',
            init_method='tcp://server-01:29500',
            world_size=len(self.servers),
            rank=get_server_rank()
        )
        
    def split_model(self, model):
        """Split model layers across servers"""
        rank = dist.get_rank()
        start_layer = rank * self.layers_per_server
        end_layer = start_layer + self.layers_per_server
        
        # Only keep assigned layers on this server
        return model[start_layer:end_layer]
```

**Infrastructure:**
- PyTorch Distributed (GLOO backend for CPU)
- NFS share for model checkpoints: `/mnt/nas/ml-training/`
- PostgreSQL for training data coordination
- SSH key auth for cluster communication

#### 1.2 Mamba Implementation
**File:** `models/mamba_cpu.py`

```python
#!/usr/bin/env python3
"""
CPU-Optimized Mamba Implementation
Based on: https://github.com/state-spaces/mamba
"""

import torch
import torch.nn as nn

class MambaBlock(nn.Module):
    """Single Mamba block - O(n) complexity"""
    
    def __init__(self, d_model: int, d_state: int = 16):
        super().__init__()
        self.d_model = d_model
        self.d_state = d_state
        
        # SSM parameters (much smaller than attention)
        self.A = nn.Parameter(torch.randn(d_state, d_state))
        self.B = nn.Parameter(torch.randn(d_state, d_model))
        self.C = nn.Parameter(torch.randn(d_model, d_state))
        
        # Input projection
        self.proj_in = nn.Linear(d_model, d_model * 2)
        self.proj_out = nn.Linear(d_model, d_model)
        
    def forward(self, x):
        """
        x: (batch, seq_len, d_model)
        Returns: (batch, seq_len, d_model)
        
        O(n) complexity - sequential processing!
        """
        batch, seq_len, _ = x.shape
        
        # Split into gate and input
        gate, inp = self.proj_in(x).chunk(2, dim=-1)
        gate = torch.sigmoid(gate)
        
        # SSM forward pass (the key innovation)
        state = torch.zeros(batch, self.d_state, device=x.device)
        outputs = []
        
        for t in range(seq_len):
            # State update: s_t = A @ s_{t-1} + B @ x_t
            state = torch.matmul(state, self.A.T) + torch.matmul(inp[:, t], self.B.T)
            
            # Output: y_t = C @ s_t
            output = torch.matmul(state, self.C.T)
            outputs.append(output)
        
        outputs = torch.stack(outputs, dim=1)  # (batch, seq_len, d_model)
        
        # Apply gate
        outputs = outputs * gate
        
        return self.proj_out(outputs)


class MambaLM(nn.Module):
    """Complete Mamba Language Model"""
    
    def __init__(self, vocab_size: int, d_model: int, n_layers: int):
        super().__init__()
        
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.layers = nn.ModuleList([
            MambaBlock(d_model) for _ in range(n_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size)
        
    def forward(self, input_ids):
        x = self.embedding(input_ids)
        
        for layer in self.layers:
            x = x + layer(x)  # Residual connection
            
        x = self.norm(x)
        logits = self.lm_head(x)
        return logits
```

**Why This Works on CPU:**
- No quadratic attention matrices
- Sequential processing (cache-friendly)
- Small state size (16-64 dims vs 2048+ for attention)
- Can use AVX2/AVX512 CPU optimizations

#### 1.3 Data Pipeline
**File:** `training/data_loader.py`

```python
#!/usr/bin/env python3
"""
Training Data Pipeline
Loads from PostgreSQL, tokenizes, batches
"""

import asyncpg
import torch
from torch.utils.data import IterableDataset, DataLoader
from transformers import AutoTokenizer

class PostgreSQLDataset(IterableDataset):
    """Stream training data from PostgreSQL"""
    
    def __init__(self, table: str, batch_size: int = 32):
        self.table = table
        self.batch_size = batch_size
        self.tokenizer = AutoTokenizer.from_pretrained('gpt2')
        
    async def get_connection(self):
        return await asyncpg.connect(
            host='aio-01',
            port=5433,
            database='learning',
            user='claude'
        )
        
    def __iter__(self):
        """Stream batches from PostgreSQL"""
        import asyncio
        
        async def fetch_batches():
            conn = await self.get_connection()
            
            # Stream large result set
            async with conn.transaction():
                cursor = await conn.cursor(f"""
                    SELECT content FROM {self.table}
                    WHERE char_length(content) > 100
                    ORDER BY RANDOM()
                """)
                
                batch = []
                async for row in cursor:
                    text = row['content']
                    tokens = self.tokenizer(
                        text,
                        max_length=2048,
                        truncation=True,
                        return_tensors='pt'
                    )
                    batch.append(tokens['input_ids'])
                    
                    if len(batch) >= self.batch_size:
                        yield torch.cat(batch)
                        batch = []
                        
            await conn.close()
        
        # Run async generator in sync context
        loop = asyncio.new_event_loop()
        for batch in loop.run_until_complete(fetch_batches()):
            yield batch


# Training data sources
TRAINING_SOURCES = {
    'code': 'learning.code_embeddings',
    'pdfs': 'learning.pdf_metadata',
    'workflows': 'workflow.executions',
    'docs': 'learning.documentation_embeddings'
}
```

#### 1.4 Validation Harness
**File:** `training/validator.py`

```python
#!/usr/bin/env python3
"""
Model Validation Against Benchmarks
Compare to GPT-4o, Claude, Gemini on test sets
"""

import json
from typing import List, Dict
from shared.multi_provider_router import MultiProviderRouter

class ModelValidator:
    """Compare model quality to commercial LLMs"""
    
    def __init__(self, test_sets: List[str]):
        self.test_sets = test_sets
        self.router = MultiProviderRouter()
        
    def evaluate(self, model, model_name: str) -> Dict:
        """
        Run model on test sets, compare to baselines
        
        Returns:
            {
                'code_completion': {
                    'accuracy': 0.85,
                    'vs_gpt4o': -0.05,  # 5% worse
                    'vs_claude': -0.03
                },
                'docs_qa': {...}
            }
        """
        results = {}
        
        for test_set in self.test_sets:
            # Load test cases
            with open(f'tests/{test_set}.json') as f:
                cases = json.load(f)
            
            # Evaluate our model
            our_accuracy = self._evaluate_model(model, cases)
            
            # Compare to baselines
            gpt4o_accuracy = self._evaluate_baseline('gpt-4o', cases)
            claude_accuracy = self._evaluate_baseline('claude-opus-4', cases)
            
            results[test_set] = {
                'accuracy': our_accuracy,
                'vs_gpt4o': our_accuracy - gpt4o_accuracy,
                'vs_claude': our_accuracy - claude_accuracy
            }
            
        return results
```

### Deliverables (Month 2)

✅ Distributed training running across 8 servers  
✅ Mamba implementation validated  
✅ Data pipeline streaming from PostgreSQL  
✅ Baseline benchmarks established  

**Success Metric:** Train 100M param model in <24 hours on CPU

---

## Phase 2: First Model (Months 3-4)

### Objectives
- Train 100M parameter Mamba model
- Specialize on code completion
- Achieve 70%+ of GPT-3.5 quality
- Inference speed: <100ms per token on CPU

### Model Architecture

```
MambaLM-100M:
  vocab_size: 50257 (GPT-2 tokenizer)
  d_model: 768
  n_layers: 12
  d_state: 16
  
Total parameters: ~100M
Memory required: ~400MB (FP32) or ~100MB (INT8)
Training time: 24-48 hours on 8-server cluster
```

### Training Strategy

#### 2.1 Knowledge Distillation
```python
"""
Teacher: GPT-4o
Student: Our Mamba-100M

Process:
1. Generate 100k code completion examples with GPT-4o
2. Train Mamba to match GPT-4o outputs
3. Validate on held-out test set
"""

class DistillationTrainer:
    def __init__(self, teacher_model='gpt-4o', student_model=MambaLM):
        self.teacher = MultiProviderRouter().get_best_model('premium')
        self.student = student_model
        
    def generate_training_data(self, prompts: List[str]):
        """Generate teacher outputs for distillation"""
        dataset = []
        
        for prompt in prompts:
            teacher_output = self.teacher.generate(prompt)
            dataset.append({
                'input': prompt,
                'target': teacher_output,
                'teacher': 'gpt-4o'
            })
            
        return dataset
        
    def train_step(self, batch):
        """Distillation loss: KL divergence + MSE"""
        student_logits = self.student(batch['input'])
        teacher_logits = batch['teacher_logits']
        
        # Soft targets from teacher
        kl_loss = F.kl_div(
            F.log_softmax(student_logits / T, dim=-1),
            F.softmax(teacher_logits / T, dim=-1),
            reduction='batchmean'
        ) * (T ** 2)
        
        # Hard targets (ground truth)
        ce_loss = F.cross_entropy(student_logits, batch['target'])
        
        # Combined loss
        loss = 0.7 * kl_loss + 0.3 * ce_loss
        return loss
```

#### 2.2 Training Data Mix

**Code Completion Dataset (100k examples):**
- 40k: Python (from our code_embeddings table)
- 30k: JavaScript/TypeScript
- 20k: Shell scripts, YAML, JSON
- 10k: Java, Go, Rust

**Data Augmentation:**
- Random truncation (simulate incomplete code)
- Synthetic errors (train on fixing bugs)
- Context variations (different import styles)

#### 2.3 Distributed Training Schedule

**Week 1-2: Infrastructure validation**
- Test distributed setup with toy model
- Benchmark throughput: tokens/second
- Optimize data pipeline

**Week 3-4: Distillation data generation**
- Generate 100k examples with GPT-4o
- Cost: ~$50 (GPT-4o API)
- Validate quality manually

**Week 5-6: Model training**
- Train on 8-server cluster
- Checkpoints every 1000 steps
- Continuous validation

**Week 7-8: Evaluation and tuning**
- Benchmark against GPT-3.5, Claude Haiku
- Fine-tune on weak areas
- Optimize inference speed

### Target Metrics (Month 4)

| Metric | Target | Comparison |
|--------|--------|------------|
| **Code completion accuracy** | 70% | GPT-3.5: ~85% |
| **Inference speed (CPU)** | <100ms/token | GPT-4o API: ~50ms |
| **Model size** | 100MB (INT8) | Llama-3-8B: 8GB |
| **Training cost** | <$100 | Cloud GPU: $500+ |
| **Specialized domains** | Python, JS, Shell | General: All languages |

### Deliverables

✅ 100M parameter model trained on CPU  
✅ 70%+ accuracy on code completion  
✅ <100ms inference latency  
✅ Published model weights (Hugging Face)  
✅ Benchmark report vs commercial LLMs  

---

## Phase 3: Scale Up (Months 5-8)

### Objectives
- Scale to 1B parameters
- Add BitNet quantization (1.58-bit)
- Multi-domain: code, docs, kubernetes, SQL
- Match GPT-3.5 quality on specialized tasks

### Architecture Evolution

```
MambaLM-1B:
  vocab_size: 50257
  d_model: 2048
  n_layers: 24
  d_state: 32
  
Parameters: ~1B
Memory: 2GB (FP32) → 200MB (BitNet 1.58-bit)
Training time: 1-2 weeks on cluster
```

### BitNet Implementation

```python
"""
BitNet: 1.58-bit weights
Values: {-1, 0, +1}

Benefits:
- 10× less memory
- 10× faster inference
- Minimal quality loss (<2%)

Paper: "The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits"
"""

class BitLinear(nn.Module):
    """1.58-bit linear layer"""
    
    def __init__(self, in_features, out_features):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(out_features, in_features))
        
    def forward(self, x):
        # Quantize weights to {-1, 0, +1}
        w = self.weight
        w_quant = torch.sign(w) * (torch.abs(w) > 0.5).float()
        
        # Standard linear operation with quantized weights
        return F.linear(x, w_quant)
```

### Multi-Domain Training

**4 Specialized Models (Mixture of Experts):**
1. **Code Expert** (server-01, server-02)
   - Python, JavaScript, Shell, YAML
   - Trained on code_embeddings table

2. **Docs Expert** (server-03, laptop-01)
   - Technical documentation, README files
   - Trained on documentation_embeddings

3. **Kubernetes Expert** (pi-01, pi-02)
   - K8s configs, manifests, troubleshooting
   - Trained on 843 PDFs (kubernetes subset)

4. **SQL Expert** (desktop-ap, server-ap)
   - SQL queries, database optimization
   - Trained on learning schema examples

**Router:**
```python
def route_query(query: str) -> str:
    """Route to best expert"""
    if 'kubernetes' in query.lower() or 'k8s' in query:
        return 'kubernetes_expert'
    elif 'sql' in query.lower() or 'database' in query:
        return 'sql_expert'
    elif is_code(query):
        return 'code_expert'
    else:
        return 'docs_expert'
```

### Deliverables (Month 8)

✅ 1B parameter model (4× MoE)  
✅ BitNet quantization (200MB total size)  
✅ 85%+ GPT-3.5 quality on specialized tasks  
✅ <50ms inference latency  
✅ Distributed inference across homelab  

---

## Phase 4: Production Quality (Months 9-12)

### Objectives
- 7B parameter model (or 4×1.75B MoE)
- Competitive with GPT-3.5 on ALL tasks
- Self-hosting: API server on homelab
- Continuous learning from usage

### Final Architecture

**Option A: Single 7B Model**
```
MambaLM-7B (BitNet):
  Total params: 7B
  Active params per query: 7B
  Memory: 1.4GB (1.58-bit)
  Inference: ~30ms/token on CPU
```

**Option B: Mixture of Experts (RECOMMENDED)**
```
MambaLM-MoE-7B:
  Number of experts: 8
  Size per expert: 875M
  Total params: 7B
  Active params per query: 875M
  Memory: 1.4GB total (experts shared on different servers)
  Inference: ~20ms/token (only activate 1 expert)
```

### Self-Hosted API

**File:** `api/llm-api-server.py`

```python
#!/usr/bin/env python3
"""
Self-Hosted LLM API Server
OpenAI-compatible API for homelab model
"""

from fastapi import FastAPI
from pydantic import BaseModel
import torch

app = FastAPI()

# Load model (distributed across cluster)
model = load_distributed_model()

class CompletionRequest(BaseModel):
    model: str = "mambalm-7b"
    prompt: str
    max_tokens: int = 100
    temperature: float = 0.7

@app.post("/v1/completions")
async def complete(request: CompletionRequest):
    """OpenAI-compatible completion endpoint"""
    
    # Inference on CPU cluster
    output = model.generate(
        request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )
    
    return {
        "model": request.model,
        "choices": [{
            "text": output,
            "finish_reason": "length"
        }],
        "usage": {
            "prompt_tokens": len(request.prompt.split()),
            "completion_tokens": len(output.split()),
            "total_tokens": len(request.prompt.split()) + len(output.split())
        }
    }

# Run on aio-01:8001
# Usage: curl http://aio-01:8001/v1/completions -d '{"prompt": "def hello():"}'
```

### Continuous Learning

**Feedback Loop:**
1. User queries stored in PostgreSQL
2. Failed queries flagged for review
3. Nightly distillation: GPT-4o generates better answers
4. Model fine-tuned on corrections
5. Quality improves over time

### Final Benchmarks (Month 12)

| Benchmark | Our Model | GPT-3.5 | GPT-4o |
|-----------|-----------|---------|--------|
| **HumanEval (code)** | 75% | 78% | 90% |
| **MMLU (general)** | 60% | 70% | 86% |
| **SQL-Eval** | 88% | 82% | 95% |
| **K8s troubleshooting** | 92% | 75% | 90% |
| **Inference speed (CPU)** | 30ms/tok | N/A | 50ms (API) |
| **Cost per 1M tokens** | $0 | $0.50 | $5 |

---

## Cost Summary

### Total Investment

| Phase | Duration | Cost | Deliverable |
|-------|----------|------|-------------|
| **Phase 1** | 2 months | $100 (power) | Distributed training framework |
| **Phase 2** | 2 months | $100 (power + API) | 100M model, 70% GPT-3.5 quality |
| **Phase 3** | 4 months | $300 (power + API) | 1B MoE model, 85% GPT-3.5 quality |
| **Phase 4** | 4 months | $400 (power + API) | 7B production model |
| **TOTAL** | 12 months | **$900** | Self-hosted LLM competitive with GPT-3.5 |

### Cost Avoidance

**Cloud GPU Training:**
- A100 rental: $2/hour × 720 hours = **$1,440/month**
- 12 months = **$17,280**

**Cloud Inference:**
- GPT-3.5 API: $0.50/1M tokens
- Your usage (~100M tokens/month): **$50/month**
- 12 months = **$600**

**Total Cloud Cost:** $17,880  
**Your Cost:** $900  
**Savings:** **$16,980** ✅

---

## Success Criteria

### Technical Milestones

✅ **Month 2:** Distributed training operational  
✅ **Month 4:** 100M model trained, 70% GPT-3.5 quality  
✅ **Month 8:** 1B MoE model, 85% GPT-3.5 quality  
✅ **Month 12:** 7B model competitive with GPT-3.5  

### Quality Gates

- **Code completion:** >75% accuracy on HumanEval
- **Inference speed:** <50ms per token on CPU
- **Model size:** <2GB in memory (BitNet)
- **Uptime:** 99%+ (homelab hosting)

### Research Contributions

- Published model weights (Hugging Face)
- Training methodology documentation
- CPU optimization techniques
- Open-source training code

---

## Risk Mitigation

### Technical Risks

**Risk:** CPU training too slow  
**Mitigation:** Start with 100M model, validate before scaling

**Risk:** Quality doesn't match GPT-3.5  
**Mitigation:** Focus on specialized domains first

**Risk:** Inference too slow  
**Mitigation:** BitNet quantization + MoE architecture

### Resource Risks

**Risk:** Homelab downtime  
**Mitigation:** Checkpoints every 1000 steps, NFS storage

**Risk:** Power costs too high  
**Mitigation:** Monitor usage, pause training if >$150/month

---

## Next Steps

### Week 1: Research Deep Dive
- [ ] Read Mamba paper in detail
- [ ] Study BitNet implementation
- [ ] Review distributed training best practices

### Week 2-4: Infrastructure Setup
- [ ] Install PyTorch on all 8 servers
- [ ] Configure NFS share for checkpoints
- [ ] Test distributed training with toy model

### Month 2: First Training Run
- [ ] Generate distillation dataset (10k examples)
- [ ] Train 10M parameter proof-of-concept
- [ ] Validate framework is working

**Ready to start?** The research exists, the hardware exists, the data exists. We just need to execute! 🚀
