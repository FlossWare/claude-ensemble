export const meta = {
  name: 'train-all-6-systems',
  description: 'Train all 6 ML systems in parallel: Thompson Sampling, Auto-Profiler, Prompt Optimizer, Novelty Detector, Complexity Estimator, CPU Fine-Tuning',
  phases: [
    { title: 'Train All Systems', detail: '6 parallel training tasks' },
    { title: 'Validate Results', detail: 'Verify each training completed successfully' },
    { title: 'Store Metrics', detail: 'Save training results to PostgreSQL' }
  ]
}

// Phase 1: Train All Systems in Parallel
phase('Train All Systems');

log('Launching 6 training tasks in parallel...');

const trainingTasks = [
  {
    name: 'Thompson Sampling',
    script: 'tools/contextual_bandit_trainer.py',
    duration: '2-3 hours',
    expected: '20-30% better strategy selection'
  },
  {
    name: 'Auto-Profiler',
    script: 'tools/auto_profiler.py',
    duration: '2-3 hours setup',
    expected: '100% model coverage (252/252)'
  },
  {
    name: 'Prompt Optimizer',
    script: 'tools/prompt_optimizer.py',
    duration: '3-4 hours',
    expected: '15-25% success rate improvement'
  },
  {
    name: 'Novelty Detector',
    script: 'tools/novelty_detector.py',
    duration: '1-2 hours',
    expected: '10-15% better exploration balance'
  },
  {
    name: 'Complexity Estimator',
    script: 'tools/complexity_estimator.py',
    duration: '2-3 hours',
    expected: 'Better resource allocation'
  },
  {
    name: 'CPU Fine-Tuning',
    script: 'fine-tuning/scripts/run_parallel_training.sh',
    duration: '10 hours',
    expected: '30-40% Java quality improvement'
  }
];

const results = await parallel(
  trainingTasks.map(task => () =>
    agent(`Train ${task.name} system.

Script: ${task.script}
Expected Duration: ${task.duration}
Expected Gain: ${task.expected}

Instructions:
1. Check if script exists at ${task.script}
2. If script doesn't exist yet, CREATE IT based on the training plan in docs/TRAINING-OPPORTUNITIES.md
3. Run the training script
4. Capture output (accuracy, loss, metrics, etc.)
5. Verify training completed successfully
6. Return results

For scripts that need to be created, use these algorithms:
- Thompson Sampling: LinUCB contextual bandit (ALREADY EXISTS - just run it)
- Auto-Profiler: Epsilon-greedy exploration 30% (ALREADY EXISTS - just run it)
- Prompt Optimizer: Pattern mining + CMA-ES (CREATE if needed)
- Novelty Detector: Isolation Forest (CREATE if needed)
- Complexity Estimator: Random Forest regression (CREATE if needed)
- CPU Fine-Tuning: Scripts exist in ~/fine-tuning/ (just run)

Return JSON with:
- system_name (string)
- status: "SUCCESS" | "FAILED" | "CREATED_AND_RAN" | "NEEDS_MANUAL_REVIEW"
- metrics (object - training metrics like accuracy, loss, coverage, etc.)
- output (string - key results)
- files_created (array - scripts created)
- next_steps (string - what to do with trained model)`, {
      label: task.name,
      phase: 'Train All Systems',
      schema: {
        type: 'object',
        properties: {
          system_name: { type: 'string' },
          status: { type: 'string', enum: ['SUCCESS', 'FAILED', 'CREATED_AND_RAN', 'NEEDS_MANUAL_REVIEW'] },
          metrics: { type: 'object' },
          output: { type: 'string' },
          files_created: { type: 'array', items: { type: 'string' } },
          next_steps: { type: 'string' }
        },
        required: ['system_name', 'status', 'metrics', 'output', 'files_created', 'next_steps']
      }
    })
  )
);

// Phase 2: Validate Results
phase('Validate Results');

const successful = results.filter(r => r?.status === 'SUCCESS' || r?.status === 'CREATED_AND_RAN');
const failed = results.filter(r => r?.status === 'FAILED');
const needsReview = results.filter(r => r?.status === 'NEEDS_MANUAL_REVIEW');

log(`Training complete: ${successful.length} succeeded, ${failed.length} failed, ${needsReview.length} need review`);

// Validate each successful training
const validations = await parallel(
  successful.map(result => () =>
    agent(`Validate training results for ${result.system_name}.

Training Output: ${result.output}
Metrics: ${JSON.stringify(result.metrics)}

Instructions:
1. Check if trained model/data was saved correctly
2. Run a quick test to verify the model works
3. Compare metrics to expected gains from TRAINING-OPPORTUNITIES.md
4. Determine if training met expectations

Return JSON with:
- system_name (string)
- validation_status: "PASS" | "FAIL"
- actual_vs_expected (string - comparison)
- test_results (array of strings - test outputs)
- ready_for_production (boolean)`, {
      label: `validate-${result.system_name}`,
      phase: 'Validate Results',
      schema: {
        type: 'object',
        properties: {
          system_name: { type: 'string' },
          validation_status: { type: 'string', enum: ['PASS', 'FAIL'] },
          actual_vs_expected: { type: 'string' },
          test_results: { type: 'array', items: { type: 'string' } },
          ready_for_production: { type: 'boolean' }
        },
        required: ['system_name', 'validation_status', 'actual_vs_expected', 'test_results', 'ready_for_production']
      }
    })
  )
);

const validated = validations.filter(v => v?.validation_status === 'PASS');

log(`Validation complete: ${validated.length}/${successful.length} systems passed validation`);

// Phase 3: Store Metrics
phase('Store Metrics');

const metricsAgent = await agent(`Store all training metrics to PostgreSQL.

Training Results:
${JSON.stringify(results.filter(Boolean), null, 2)}

Validation Results:
${JSON.stringify(validations.filter(Boolean), null, 2)}

Instructions:
1. Use workflow-storage-adapter.js to connect to PostgreSQL
2. Store each system's training metrics in appropriate tables
3. Create learnings for successful trainings
4. Update model_capabilities with new profiling data
5. Store bandit models if Thompson Sampling succeeded

PostgreSQL Tables to Update:
- learning.model_capabilities (auto-profiler results)
- learning.bandit_models (Thompson Sampling model)
- learning.prompt_patterns (prompt optimizer patterns - may need to create table)
- workflow.learnings (insights from all trainings)

Return JSON with:
- records_inserted (number)
- tables_updated (array of table names)
- storage_status: "SUCCESS" | "PARTIAL" | "FAILED"
- summary (string)`, {
  label: 'store-metrics',
  phase: 'Store Metrics',
  schema: {
    type: 'object',
    properties: {
      records_inserted: { type: 'number' },
      tables_updated: { type: 'array', items: { type: 'string' } },
      storage_status: { type: 'string', enum: ['SUCCESS', 'PARTIAL', 'FAILED'] },
      summary: { type: 'string' }
    },
    required: ['records_inserted', 'tables_updated', 'storage_status', 'summary']
  }
});

log(`Metrics stored: ${metricsAgent.records_inserted} records across ${metricsAgent.tables_updated.length} tables`);

// Final Summary
return {
  training_summary: {
    total_systems: trainingTasks.length,
    succeeded: successful.length,
    failed: failed.length,
    needs_review: needsReview.length,
    validated: validated.length,
    ready_for_production: validations.filter(v => v?.ready_for_production).length
  },
  results: results.filter(Boolean),
  validations: validations.filter(Boolean),
  metrics_storage: metricsAgent,
  failed_systems: failed.map(f => f?.system_name || 'unknown'),
  next_steps: validated.filter(v => v?.ready_for_production).map(v =>
    `Deploy ${v.system_name} to production`
  )
};
