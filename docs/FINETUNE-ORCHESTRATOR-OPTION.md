# CPU Fine-Tuning: Bash vs Orchestrator

## Current Approach: Bash Script ✅

**File:** `~/fine-tuning/scripts/run_parallel_training.sh`

**Method:**
```bash
ssh laptop-01 "python3 train_cpu.py --model phi-4 ..." &
ssh server-03 "python3 train_cpu.py --model deepseek-coder ..." &
wait
ssh server-03 "python3 train_cpu.py --model mistral-7b ..." 
```

**Pros:**
- ✅ Simple (one command)
- ✅ Deterministic (no LLM decisions needed)
- ✅ Already working
- ✅ Logs to files automatically
- ✅ Easy to monitor (`tail -f logs/*.log`)

**Cons:**
- ❌ No multi-AI validation
- ❌ No automatic retry on failures
- ❌ No PostgreSQL tracking
- ❌ No cost/quality analysis

---

## Alternative: Orchestrator Workflow

**Could create:** `workflows/cpu-finetune-orchestrated.mjs`

**Method:**
```javascript
// Phase 1: Validate datasets
const datasets = await agent('Check datasets ready...')

// Phase 2: Launch parallel training
const parallel_results = await parallel([
  () => agent('SSH laptop-01 and train phi-4-mini...'),
  () => agent('SSH server-03 and train deepseek-coder...')
])

// Phase 3: Sequential training
const mistral = await agent('SSH server-03 and train mistral-7b...')

// Phase 4: Multi-AI validation
const validation = await parallel([
  () => agent('Test deepseek-coder on Java code...', {model: 'opus'}),
  () => agent('Test phi-4-mini on routing...', {model: 'sonnet'}),
  () => agent('Test mistral-7b on consensus...', {model: 'haiku'})
])
```

**Pros:**
- ✅ Multi-AI validation (6-model consensus on quality)
- ✅ PostgreSQL tracking (store results in workflow.executions)
- ✅ Automatic retry on failures
- ✅ Cost/quality analysis
- ✅ Better error handling

**Cons:**
- ❌ More complex
- ❌ Adds LLM overhead (for decisions we don't need)
- ❌ Harder to debug (workflow abstraction)

---

## Recommendation

**For CPU fine-tuning: Keep using bash script** ✅

**Why:**
1. Fine-tuning is deterministic (no decisions needed)
2. Runs for 10 hours (LLM doesn't add value during training)
3. Simple is better (easy to debug, monitor, restart)
4. Already working infrastructure

**Where orchestrator DOES help:**
- **Before training:** Dataset preparation (agent finds Java files)
- **After training:** Multi-AI validation (test fine-tuned vs base models)
- **Integration:** Updating routing logic to use fine-tuned models

---

## Hybrid Approach (Best of Both)

Use **bash for training**, **orchestrator for validation**:

### Step 1: Train (Bash)
```bash
cd ~/fine-tuning
./scripts/run_parallel_training.sh
# Runs for ~10 hours, logs to files
```

### Step 2: Validate (Orchestrator)
```bash
# After training completes
workflows/validate-finetuned-models.mjs
```

**Orchestrator workflow:**
```javascript
// Test each fine-tuned model with multi-AI consensus

// deepseek-coder: Generate Java code
const java_tests = await parallel([
  () => agent('Test deepseek-coder-java on Salesforce pattern...', {model: 'opus'}),
  () => agent('Test deepseek-coder-java on Maven config...', {model: 'sonnet'}),
  () => agent('Compare to base deepseek-coder quality...', {model: 'haiku'})
])

// phi-4-mini: Test routing decisions
const routing_tests = await parallel([
  () => agent('Test phi-4-mini-routing on strategy selection...', {model: 'fable'}),
  () => agent('Compare to Thompson Sampling bandit...', {model: 'opus'})
])

// mistral-7b: Test arbiter consensus
const arbiter_tests = await parallel([
  () => agent('Test mistral-arbiter on multi-AI synthesis...', {model: 'sonnet'}),
  () => agent('Compare to paid API arbiters (Opus/Sonnet)...', {model: 'haiku'})
])

// Store validation results in PostgreSQL
await storeValidation(java_tests, routing_tests, arbiter_tests)
```

---

## What You Get

### Bash-Only Approach:
- ✅ Training completes
- ✅ Checkpoints saved
- ❌ No validation
- ❌ No quality comparison
- ❌ No PostgreSQL tracking

### Bash + Orchestrator Validation:
- ✅ Training completes (bash)
- ✅ Checkpoints saved (bash)
- ✅ Multi-AI validation (orchestrator)
- ✅ Quality comparison vs base models (orchestrator)
- ✅ PostgreSQL tracking (orchestrator)

---

## Files

**Current (Bash):**
- `~/fine-tuning/scripts/run_parallel_training.sh` - Training orchestration
- `~/fine-tuning/scripts/train_cpu.py` - Actual training code

**Could Add (Orchestrator Validation):**
- `workflows/validate-finetuned-models.mjs` - Post-training validation
- `workflows/prepare-finetune-datasets.mjs` - Pre-training dataset prep

---

## Answer to Your Question

**"Will the orchestrator be used for CPU tuning?"**

**Current answer:** NO - simple bash script is used

**Could it be?** YES - but not recommended for the training itself

**Best approach:** 
1. **Bash** for training (simple, deterministic, working)
2. **Orchestrator** for validation (multi-AI testing, quality comparison)

**Want me to create the validation workflow?** It would:
- Test fine-tuned models with real tasks
- Compare to base models (quality improvement %)
- Get 6-model consensus on each test
- Store results in PostgreSQL
- Generate quality report

This way you get:
- ✅ Simple training (bash)
- ✅ Rigorous validation (orchestrator)
- ✅ Best of both worlds
