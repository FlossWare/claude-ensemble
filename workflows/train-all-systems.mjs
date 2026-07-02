export const meta = {
  name: 'train-all-systems',
  description: 'Train Thompson Sampling, Auto-Profiler, and CPU Fine-Tuning',
  phases: [
    { title: 'Thompson Sampling', detail: 'Train contextual bandit on 914 tasks' },
    { title: 'Auto-Profiler', detail: 'Profile unprofiled models via real tasks' },
    { title: 'Fine-Tuning Check', detail: 'Verify CPU fine-tuning infrastructure' },
    { title: 'Validate', detail: 'Test all trained systems' }
  ]
}

export default async function({ phase, parallel, agent, log }) {

  // Phase 1: Train Thompson Sampling
  log('Training contextual Thompson Sampling bandit...')

  const thompsonResult = await phase('Thompson Sampling', async () => {
    const result = await agent(`Train contextual Thompson Sampling bandit.

Run this Python script:

python3 /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/contextual_bandit_trainer.py

This will:
1. Load 914 task execution records from PostgreSQL
2. Extract context features (task type, complexity, urgency)
3. Train LinUCB algorithm for contextual strategy selection
4. Save model to ~/.claude/learning/contextual_bandit.json
5. Store metadata in learning.bandit_models table

Return the output including:
- Number of strategies
- Training records used
- Accuracy percentage
- Model save path`, {
      label: 'train-thompson',
      schema: {
        type: 'object',
        properties: {
          strategies: { type: 'number' },
          training_records: { type: 'number' },
          accuracy: { type: 'number' },
          model_path: { type: 'string' },
          success: { type: 'boolean' }
        }
      }
    })

    return { thompson: result }
  })

  log(`Thompson Sampling trained: ${thompsonResult.thompson.accuracy * 100}% accuracy on ${thompsonResult.thompson.training_records} records`)

  // Phase 2: Run Auto-Profiler Demo
  log('Running auto-profiler to test model selection...')

  const profilerResult = await phase('Auto-Profiler', async () => {
    const result = await agent(`Run auto-profiler demo.

Execute:

python3 /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/auto_profiler.py

This will:
1. Check current profiling coverage (should be ~6%)
2. Simulate 20 task executions with epsilon-greedy exploration
3. Profile unprofiled models during execution
4. Show final coverage improvement

Return:
- Initial coverage (models/total)
- Final coverage (models/total)
- Models profiled during demo
- Average tests per model`, {
      label: 'run-profiler',
      schema: {
        type: 'object',
        properties: {
          initial_coverage: { type: 'string' },
          final_coverage: { type: 'string' },
          models_added: { type: 'number' },
          avg_tests: { type: 'number' },
          success: { type: 'boolean' }
        }
      }
    })

    return { profiler: result }
  })

  log(`Auto-profiler coverage: ${profilerResult.profiler.initial_coverage} → ${profilerResult.profiler.final_coverage}`)

  // Phase 3: Check Fine-Tuning Infrastructure
  log('Checking CPU fine-tuning readiness...')

  const finetuneResult = await phase('Fine-Tuning Check', async () => {
    const result = await agent(`Check CPU fine-tuning infrastructure readiness.

Run these checks:

1. Check if infrastructure exists:
   ls -la ~/fine-tuning/

2. Check datasets:
   ls -la ~/fine-tuning/datasets/

3. Check training scripts:
   ls ~/fine-tuning/scripts/*.py | head -5

4. Check if dependencies installed:
   python3 -c "import transformers, peft, bitsandbytes; print('OK')" 2>&1 || echo "MISSING"

5. Check training script exists:
   test -f ~/fine-tuning/scripts/run_parallel_training.sh && echo "READY" || echo "NOT_FOUND"

Report:
- Infrastructure status (exists/missing)
- Datasets available
- Scripts ready
- Dependencies status
- Estimated training time (from ~/fine-tuning/README.md if exists)`, {
      label: 'check-finetune',
      schema: {
        type: 'object',
        properties: {
          infrastructure_ready: { type: 'boolean' },
          datasets_available: { type: 'boolean' },
          scripts_ready: { type: 'boolean' },
          dependencies_ok: { type: 'boolean' },
          estimated_hours: { type: 'number' },
          notes: { type: 'string' }
        }
      }
    })

    return { finetune: result }
  })

  log(`Fine-tuning infrastructure: ${finetuneResult.finetune.infrastructure_ready ? 'READY' : 'NEEDS SETUP'}`)

  // Phase 4: Validate All Systems
  log('Validating all trained systems...')

  const validation = await phase('Validate', async () => {
    const checks = await parallel([
      // Check 1: Thompson Sampling model exists
      () => agent(`Check Thompson Sampling model was saved:

ls -lh ~/.claude/learning/contextual_bandit.json

Query PostgreSQL to verify metadata:
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT model_name, training_records, accuracy, trained_at FROM learning.bandit_models WHERE model_name = 'contextual_thompson';"

Return: model size, training records, accuracy`, {
        label: 'validate-thompson',
        schema: {
          type: 'object',
          properties: {
            model_exists: { type: 'boolean' },
            file_size_kb: { type: 'number' },
            accuracy: { type: 'number' },
            training_records: { type: 'number' }
          }
        }
      }),

      // Check 2: Auto-profiler improved coverage
      () => agent(`Check auto-profiler increased model coverage:

psql -h aio-01 -p 5433 -U sfloess -d learning << 'EOF'
SELECT
  COUNT(DISTINCT model_id) as profiled_models,
  (SELECT COUNT(*) FROM learning.free_models) as total_models,
  ROUND((COUNT(DISTINCT model_id)::numeric / (SELECT COUNT(*) FROM learning.free_models) * 100), 1) as coverage_pct
FROM learning.model_capabilities;
EOF

Return: profiled count, total count, coverage %`, {
        label: 'validate-profiler',
        schema: {
          type: 'object',
          properties: {
            profiled_models: { type: 'number' },
            total_models: { type: 'number' },
            coverage_pct: { type: 'number' },
            improved: { type: 'boolean' }
          }
        }
      }),

      // Check 3: Fine-tuning command ready
      () => agent(`Generate fine-tuning launch command:

Check if run script exists:
test -f ~/fine-tuning/scripts/run_parallel_training.sh && echo "EXISTS" || echo "MISSING"

If exists, show the command to launch training:
echo "Command: cd ~/fine-tuning && ./scripts/run_parallel_training.sh"
echo "Runtime: ~10 hours (4-6h deepseek-coder + 2-3h phi-4-mini + 3-4h mistral-7b)"
echo "Models: 3 (deepseek-coder-java, phi-4-mini-routing, mistral-arbiter)"

Return: command, estimated time, models to train`, {
        label: 'validate-finetune',
        schema: {
          type: 'object',
          properties: {
            script_exists: { type: 'boolean' },
            command: { type: 'string' },
            estimated_hours: { type: 'number' },
            models_to_train: { type: 'array', items: { type: 'string' } }
          }
        }
      })
    ])

    return { validations: checks.filter(Boolean) }
  })

  // Summary
  log('\n=== TRAINING SUMMARY ===')
  log(`✅ Thompson Sampling: ${thompsonResult.thompson.accuracy * 100}% accuracy`)
  log(`✅ Auto-Profiler: ${profilerResult.profiler.final_coverage} coverage`)
  log(`${finetuneResult.finetune.infrastructure_ready ? '✅' : '⚠️'} Fine-Tuning: ${finetuneResult.finetune.infrastructure_ready ? 'Ready to launch' : 'Needs setup'}`)

  return {
    thompson_sampling: {
      trained: thompsonResult.thompson.success,
      accuracy: thompsonResult.thompson.accuracy,
      model_path: thompsonResult.thompson.model_path,
      training_records: thompsonResult.thompson.training_records
    },
    auto_profiler: {
      ran: profilerResult.profiler.success,
      coverage_improvement: profilerResult.profiler.final_coverage,
      models_added: profilerResult.profiler.models_added
    },
    fine_tuning: {
      ready: finetuneResult.finetune.infrastructure_ready,
      estimated_hours: finetuneResult.finetune.estimated_hours,
      command: validation.validations[2]?.command || 'cd ~/fine-tuning && ./scripts/run_parallel_training.sh'
    },
    validation: {
      all_systems_validated: validation.validations.length === 3
    }
  }
}
