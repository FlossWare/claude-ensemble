export const meta = {
  name: 'cpu-fine-tuning-parallel',
  description: 'Train 3 models in parallel across fleet (10 hours total)',
  phases: [
    { title: 'Prepare Datasets', detail: 'Extract training data from PostgreSQL' },
    { title: 'Parallel Training', detail: '2 models in parallel (laptop-01 + server-03)' },
    { title: 'Sequential Training', detail: 'mistral-7b on server-03 after deepseek completes' },
    { title: 'Validate Models', detail: 'Test all 3 trained models' }
  ]
}

// Phase 1: Prepare Datasets
phase('Prepare Datasets')

log('Preparing training datasets from PostgreSQL and codebase...')

const datasetPrep = await agent(`Prepare training datasets for CPU fine-tuning.

3 datasets needed:

1. Java/Salesforce corpus (deepseek-coder-v2-lite):
   - Extract from Solenopsis, FlossWare, JCollections repos
   - Target: ~/fine-tuning/datasets/java_salesforce_corpus.jsonl
   - Format: {"text": "...", "metadata": {"source": "..."}}

2. Routing decisions (phi-4-mini):
   - Extract from PostgreSQL workflow.worker_results
   - Target: ~/fine-tuning/datasets/routing_decisions.jsonl
   - Include context features + model selection + outcome

3. Consensus patterns (mistral-7b):
   - Extract high-quality consensus workflows (reward > 0.75)
   - Target: ~/fine-tuning/datasets/consensus_patterns.jsonl
   - Include multi-AI interactions

Run: python3 ~/fine-tuning/scripts/prepare_datasets.py

Return JSON with:
- datasets_created (array of filenames)
- record_counts (object with counts per dataset)
- total_size_mb (number)
- status: "SUCCESS" | "FAILED"`, {
  label: 'prepare-datasets',
  phase: 'Prepare Datasets',
  schema: {
    type: 'object',
    properties: {
      datasets_created: { type: 'array', items: { type: 'string' } },
      record_counts: { type: 'object' },
      total_size_mb: { type: 'number' },
      status: { type: 'string', enum: ['SUCCESS', 'FAILED'] }
    },
    required: ['datasets_created', 'record_counts', 'total_size_mb', 'status']
  }
})

if (datasetPrep.status !== 'SUCCESS') {
  log('❌ Dataset preparation failed!')
  return { error: 'Dataset preparation failed', datasets: datasetPrep }
}

log(`✓ Datasets ready: ${datasetPrep.datasets_created.join(', ')}`)
log(`✓ Total records: ${JSON.stringify(datasetPrep.record_counts)}`)

// Phase 2: Parallel Training (laptop-01 + server-03)
phase('Parallel Training')

log('Launching parallel training on 2 workers...')

const parallelTraining = await parallel([
  // Worker 1: phi-4-mini on laptop-01 (2-3 hours)
  () => agent(`Train phi-4-mini model on laptop-01 for routing optimization.

Model: microsoft/phi-4
Dataset: ~/fine-tuning/datasets/routing_decisions.jsonl
Output: ~/fine-tuning/checkpoints/phi-4-mini-routing
Config: ~/fine-tuning/configs/qdora_config.yaml

Instructions:
1. SSH to laptop-01
2. Run training script:
   cd ~/fine-tuning
   python3 scripts/train_cpu.py \\
     --model microsoft/phi-4 \\
     --dataset datasets/routing_decisions.jsonl \\
     --output checkpoints/phi-4-mini-routing \\
     --config configs/qdora_config.yaml \\
     --steps 1000 \\
     --batch-size 4 \\
     > logs/phi-4-mini.log 2>&1

3. Monitor logs: tail -f ~/fine-tuning/logs/phi-4-mini.log
4. Verify checkpoint saved
5. Test model with sample routing task

Expected duration: 2-3 hours
This runs in BACKGROUND on laptop-01.

Return JSON with:
- model: "phi-4-mini"
- host: "laptop-01"
- status: "SUCCESS" | "FAILED" | "RUNNING"
- checkpoint_path (string)
- training_duration_hours (number)
- final_loss (number)
- log_snippet (string - last 10 lines)`, {
    label: 'train-phi4-laptop01',
    phase: 'Parallel Training',
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        host: { type: 'string' },
        status: { type: 'string', enum: ['SUCCESS', 'FAILED', 'RUNNING'] },
        checkpoint_path: { type: 'string' },
        training_duration_hours: { type: 'number' },
        final_loss: { type: 'number' },
        log_snippet: { type: 'string' }
      },
      required: ['model', 'host', 'status']
    }
  }),

  // Worker 2: deepseek-coder on server-03 (4-6 hours)
  () => agent(`Train deepseek-coder-v2-lite on server-03 for Java code generation.

Model: deepseek-ai/deepseek-coder-6.7b-instruct
Dataset: ~/fine-tuning/datasets/java_salesforce_corpus.jsonl
Output: ~/fine-tuning/checkpoints/deepseek-coder-java
Config: ~/fine-tuning/configs/qdora_config.yaml

Instructions:
1. SSH to server-03
2. Run training script:
   cd ~/fine-tuning
   python3 scripts/train_cpu.py \\
     --model deepseek-ai/deepseek-coder-6.7b-instruct \\
     --dataset datasets/java_salesforce_corpus.jsonl \\
     --output checkpoints/deepseek-coder-java \\
     --config configs/qdora_config.yaml \\
     --steps 1000 \\
     --batch-size 4 \\
     > logs/deepseek-coder.log 2>&1

3. Monitor: tail -f ~/fine-tuning/logs/deepseek-coder.log
4. Verify checkpoint
5. Test with Java code generation task

Expected duration: 4-6 hours
This runs in BACKGROUND on server-03.

Return JSON with same schema as phi-4 worker.`, {
    label: 'train-deepseek-server03',
    phase: 'Parallel Training',
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        host: { type: 'string' },
        status: { type: 'string', enum: ['SUCCESS', 'FAILED', 'RUNNING'] },
        checkpoint_path: { type: 'string' },
        training_duration_hours: { type: 'number' },
        final_loss: { type: 'number' },
        log_snippet: { type: 'string' }
      },
      required: ['model', 'host', 'status']
    }
  })
])

const [phi4Result, deepseekResult] = parallelTraining.filter(Boolean)

log(`✓ Parallel training launched:`)
log(`  phi-4-mini on laptop-01: ${phi4Result.status}`)
log(`  deepseek-coder on server-03: ${deepseekResult.status}`)

// Phase 3: Sequential Training (mistral-7b after deepseek completes)
phase('Sequential Training')

log('Waiting for deepseek to complete, then training mistral-7b...')

const mistralTraining = await agent(`Train mistral-7b-instruct on server-03 for consensus arbitration.

IMPORTANT: Only start AFTER deepseek-coder completes on server-03.

Model: mistralai/Mistral-7B-Instruct-v0.2
Dataset: ~/fine-tuning/datasets/consensus_patterns.jsonl
Output: ~/fine-tuning/checkpoints/mistral-arbiter
Config: ~/fine-tuning/configs/qdora_config.yaml

Instructions:
1. Wait for deepseek-coder to finish (check logs/deepseek-coder.log)
2. SSH to server-03
3. Run training script:
   cd ~/fine-tuning
   python3 scripts/train_cpu.py \\
     --model mistralai/Mistral-7B-Instruct-v0.2 \\
     --dataset datasets/consensus_patterns.jsonl \\
     --output checkpoints/mistral-arbiter \\
     --config configs/qdora_config.yaml \\
     --steps 1000 \\
     --batch-size 4 \\
     > logs/mistral-7b.log 2>&1

4. Monitor: tail -f ~/fine-tuning/logs/mistral-7b.log
5. Verify checkpoint
6. Test with consensus task

Expected duration: 3-4 hours (after deepseek completes)
Sequential because server-03 can only train one model at a time.

Return JSON with same schema.`, {
  label: 'train-mistral-server03',
  phase: 'Sequential Training',
  schema: {
    type: 'object',
    properties: {
      model: { type: 'string' },
      host: { type: 'string' },
      status: { type: 'string', enum: ['SUCCESS', 'FAILED', 'RUNNING'] },
      checkpoint_path: { type: 'string' },
      training_duration_hours: { type: 'number' },
      final_loss: { type: 'number' },
      log_snippet: { type: 'string' }
    },
    required: ['model', 'host', 'status']
  }
})

log(`✓ Sequential training: mistral-7b on server-03: ${mistralTraining.status}`)

// Phase 4: Validate Models
phase('Validate Models')

const allResults = [phi4Result, deepseekResult, mistralTraining].filter(Boolean)
const successful = allResults.filter(r => r.status === 'SUCCESS')
const running = allResults.filter(r => r.status === 'RUNNING')
const failed = allResults.filter(r => r.status === 'FAILED')

log(`Training complete:`)
log(`  Success: ${successful.length}`)
log(`  Running: ${running.length}`)
log(`  Failed: ${failed.length}`)

// Return summary
return {
  training_summary: {
    total_models: 3,
    successful: successful.length,
    running: running.length,
    failed: failed.length,
    total_duration_estimate_hours: 10
  },
  datasets: datasetPrep,
  phi4: phi4Result,
  deepseek: deepseekResult,
  mistral: mistralTraining,
  checkpoints: allResults.map(r => r.checkpoint_path).filter(Boolean),
  next_steps: successful.length === 3
    ? "All models trained! Load into Ollama and update orchestrator routing."
    : running.length > 0
    ? `${running.length} model(s) still training. Monitor logs.`
    : `${failed.length} model(s) failed. Check logs for errors.`
}
