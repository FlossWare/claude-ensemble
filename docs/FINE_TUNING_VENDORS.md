# Fine-Tuning Vendors Comparison (2026)

**Last Updated:** 2026-07-03  
**Status:** Active research

---

## **Quick Comparison Table:**

| Vendor | Cost | Hardware | Quality | Ease | Best For |
|--------|------|----------|---------|------|----------|
| **Together AI** | $$ | Cloud GPU | High | Easy | Production fine-tuning |
| **Hugging Face AutoTrain** | $ | Cloud GPU | High | Easy | Quick experiments |
| **RunPod** | $ | Rent GPU | High | Medium | DIY control |
| **Lambda Labs** | $$ | Rent GPU | High | Medium | Long training runs |
| **Replicate** | $$$ | Cloud | High | Very Easy | No-code fine-tuning |
| **OpenAI** | $$$$ | API | Highest | Very Easy | GPT-3.5/4 fine-tuning |
| **Anthropic** | N/A | N/A | N/A | N/A | No fine-tuning available |
| **Our CPU (QLoRA)** | FREE | Local CPU | Medium | Hard | Learning/testing |

---

## **1. Together AI ⭐⭐⭐⭐⭐ (BEST OVERALL)**

**What:** Serverless fine-tuning platform with 100+ open models

**Pricing:**
```
Training: $0.60 per 1M tokens
Inference: $0.20 per 1M tokens (fine-tuned model)

Example (1000 examples, mistral-7b):
  Training data: ~2M tokens
  Cost: $1.20 (one-time)
  Inference: Same as base model
```

**Models Available:**
- Mistral 7B/8x7B
- LLaMA 3 70B/8B
- Qwen 2.5
- DeepSeek
- All major open models

**API Example:**
```python
import together

# Fine-tune
job = together.Fine_tuning.create(
    training_file='training_data.jsonl',
    model='mistralai/Mistral-7B-Instruct-v0.2',
    n_epochs=3,
    learning_rate=1e-5
)

# Use fine-tuned model
response = together.Complete.create(
    model=job.fine_tuned_model,
    prompt="Debug this code..."
)
```

**Pros:**
- ✅ Cheapest cloud fine-tuning
- ✅ Fast (2-4 hours typical)
- ✅ 100+ models available
- ✅ Simple API
- ✅ Pay only for training

**Cons:**
- ⚠️ Model hosted on their servers
- ⚠️ Inference costs (but cheap)

**Best For:** Production fine-tuning with budget constraints

---

## **2. Hugging Face AutoTrain ⭐⭐⭐⭐⭐**

**What:** AutoML for LLM fine-tuning (minimal config needed)

**Pricing:**
```
Compute:
  CPU: $0.06/hour (too slow)
  T4 GPU: $0.60/hour (~4 hours = $2.40)
  A100 GPU: $3.00/hour (~2 hours = $6.00)

Total: $2-6 per fine-tuning run
```

**How It Works:**
```python
from autotrain import AutoTrain

# Automatic fine-tuning (detects best settings)
model = AutoTrain.train(
    model_name="mistralai/Mistral-7B-Instruct-v0.2",
    data="training_data.csv",
    task="text-generation",
    # That's it! Auto-detects everything else
)

# Download to local
model.push_to_hub("your-username/mistral-7b-finetuned")
```

**Pros:**
- ✅ Extremely easy (auto-config)
- ✅ Download model after training
- ✅ No inference costs (run locally)
- ✅ Integrated with HF ecosystem

**Cons:**
- ⚠️ Less control than manual
- ⚠️ GPU rental costs

**Best For:** Quick experiments, prototyping

---

## **3. RunPod ⭐⭐⭐⭐ (BEST FOR DIY)**

**What:** Rent cloud GPUs, run your own training code

**Pricing:**
```
GPU Rental:
  RTX 3090 (24GB): $0.34/hour
  RTX 4090 (24GB): $0.69/hour
  A100 (80GB): $1.89/hour

Example (mistral-7b, 4 hours on RTX 4090):
  Cost: $2.76
```

**How It Works:**
```bash
# 1. Rent GPU via web UI
# 2. SSH into instance
# 3. Run your training code

ssh root@runpod-instance
cd /workspace
git clone your-training-repo
python qlora_trainer.py --model mistral-7b
```

**Pros:**
- ✅ Full control (use any code)
- ✅ Cheap GPU access
- ✅ Download model after
- ✅ Pay per second

**Cons:**
- ⚠️ Manual setup required
- ⚠️ Need to write training code

**Best For:** Developers who want full control

---

## **4. Lambda Labs ⭐⭐⭐⭐**

**What:** Long-term GPU rental for serious training

**Pricing:**
```
On-Demand GPUs:
  A10 (24GB): $0.60/hour
  A100 (40GB): $1.29/hour
  A100 (80GB): $2.49/hour

Reserved (1 month minimum):
  A100: $1,200/month (vs $929 on-demand)
```

**When to Use:**
- Long training runs (days/weeks)
- Multiple experiments
- Need persistent environment

**Pros:**
- ✅ More reliable than RunPod
- ✅ Better network speeds
- ✅ Reserved instances = cheaper

**Cons:**
- ⚠️ More expensive than RunPod
- ⚠️ Minimum commitments for discounts

**Best For:** Serious research, production training

---

## **5. Replicate ⭐⭐⭐ (EASIEST)**

**What:** No-code fine-tuning via web UI

**Pricing:**
```
Training: $0.000725 per second (A100)
Example (4 hour training): $10.44

Inference: Pay per prediction
  $0.00025 per prediction (typical)
```

**How It Works:**
```
1. Upload training_data.jsonl via web UI
2. Select base model (mistral-7b, llama-3, etc.)
3. Click "Train"
4. Use via API:

import replicate
output = replicate.run(
    "your-username/mistral-finetuned",
    input={"prompt": "Debug this code..."}
)
```

**Pros:**
- ✅ Zero code required
- ✅ Beautiful web UI
- ✅ Auto-scaling inference
- ✅ Version control

**Cons:**
- ⚠️ More expensive than alternatives
- ⚠️ Less control
- ⚠️ Can't download model

**Best For:** Non-technical users, demos

---

## **6. OpenAI Fine-Tuning ⭐⭐⭐**

**What:** Fine-tune GPT-3.5-turbo or GPT-4

**Pricing:**
```
GPT-3.5-turbo:
  Training: $8.00 per 1M tokens
  Inference: $12.00 per 1M tokens (vs $0.50 base)

GPT-4o-mini:
  Training: $3.00 per 1M tokens
  Inference: $3.75 per 1M tokens (vs $0.15 base)

Example (1000 examples = 2M tokens):
  Training cost: $16 (GPT-3.5) or $6 (GPT-4o-mini)
```

**API:**
```python
import openai

# Create fine-tuning job
job = openai.FineTuning.create(
    training_file="file-abc123",
    model="gpt-3.5-turbo"
)

# Use fine-tuned model
response = openai.ChatCompletion.create(
    model=job.fine_tuned_model,
    messages=[{"role": "user", "content": "..."}]
)
```

**Pros:**
- ✅ Highest quality base models
- ✅ Simple API
- ✅ Reliable infrastructure

**Cons:**
- ⚠️ Expensive (24× inference cost!)
- ⚠️ Can't download model
- ⚠️ Locked into OpenAI

**Best For:** When quality matters more than cost

---

## **7. Our CPU (QLoRA) ⭐⭐⭐**

**What:** Run locally with QLoRA on CPU

**Pricing:**
```
Hardware: FREE (use existing servers)
Electricity: ~$0.50 per 24-hour run
Time: 12-24 hours

Total cost: $0.50
```

**Process:**
```bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 tools/qlora_trainer.py \
  --model mistralai/Mistral-7B-Instruct-v0.2 \
  --task debugging \
  --examples 1000 \
  --epochs 3
```

**Pros:**
- ✅ FREE (no cloud costs)
- ✅ Full control
- ✅ Own the model
- ✅ No vendor lock-in
- ✅ Privacy (data stays local)

**Cons:**
- ⚠️ SLOW (12-24 hours vs 2-4 hours GPU)
- ⚠️ Lower quality than GPU training
- ⚠️ Manual setup

**Best For:**
- Learning/experimentation
- Privacy-sensitive data
- Budget = $0

---

## **Recommendations by Use Case:**

### **Quick Experiment / Proof of Concept:**
→ **Hugging Face AutoTrain** ($2-6, 2-4 hours)

### **Production Fine-Tuning (Budget):**
→ **Together AI** ($1-5, 2-4 hours, cheapest ongoing inference)

### **Production Fine-Tuning (Quality):**
→ **OpenAI GPT-3.5** ($16+ but highest quality)

### **DIY / Full Control:**
→ **RunPod** ($2-5, rent GPU by hour)

### **Long-Term Research:**
→ **Lambda Labs** (reserved instances, $1200/month)

### **Non-Technical Users:**
→ **Replicate** ($10+, no code needed)

### **Zero Budget / Learning:**
→ **Our CPU (QLoRA)** (FREE, slow but works!)

---

## **What We Should Try:**

### **Immediate (This Week):**
1. **CPU QLoRA Test** - Prove it works locally (FREE)
2. **Together AI Trial** - Compare quality vs CPU ($1-2)

### **If CPU Works:**
- Use for learning/testing
- Use Together AI for production

### **If CPU Too Slow:**
- RunPod for experiments ($2-5 per run)
- Together AI for production ($1-5)

---

## **Action Plan:**

**Step 1: Test CPU QLoRA (Tonight)**
```bash
# Install dependencies
pip install transformers peft bitsandbytes accelerate

# Test training (small dataset)
python3 tools/qlora_trainer.py --examples 100 --epochs 1

# Estimate time for full run
# If < 24 hours: Acceptable
# If > 24 hours: Use cloud GPU
```

**Step 2: If CPU Works (Use It!)**
```bash
# Full training run
python3 tools/qlora_trainer.py --examples 1000 --epochs 3

# Test quality
# If quality good: FREE fine-tuning solved!
# If quality bad: Need GPU cloud
```

**Step 3: If CPU Too Slow (Cloud Backup)**
```python
# Together AI (cheapest cloud)
import together

job = together.Fine_tuning.create(
    training_file='data.jsonl',
    model='mistralai/Mistral-7B-Instruct-v0.2'
)
```

---

## **Cost Comparison (1000 examples, mistral-7b):**

| Option | Training Cost | Inference Cost | Total (1 year) | Owner |
|--------|--------------|----------------|----------------|-------|
| **CPU QLoRA** | $0 | $0 | **$0** | You |
| **Together AI** | $1.20 | $0.20/1M | **$1.20 + usage** | Together |
| **HF AutoTrain** | $2.40 | $0 | **$2.40** | You |
| **RunPod** | $2.76 | $0 | **$2.76** | You |
| **OpenAI** | $16.00 | $12/1M | **$16 + 24× usage** | OpenAI |

**Winner:** CPU QLoRA if time acceptable, Together AI if need speed!

---

## **Next Steps:**

Want me to:
1. ✅ **Test CPU QLoRA NOW** (see if it works on server-03)
2. ✅ **Setup Together AI account** (backup if CPU too slow)
3. ✅ **Create training data from PostgreSQL** (1000 debugging examples)

**Should I start the CPU test?** It will tell us if we need cloud GPUs or not!
