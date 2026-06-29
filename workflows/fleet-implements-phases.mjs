export const meta = {
  name: 'fleet-implements-phases',
  description: 'Fleet collectively implements 5 phases using SSH distribution across 8 workers',
  phases: [
    { title: 'Phase 0: Experiment Framework', detail: '3 workers implement DB + manager + A/B runner', model: 'opus' },
    { title: 'Phase 1: Capability Architecture', detail: '3 workers implement interfaces + registry + routing', model: 'sonnet' },
    { title: 'Phase 2: Strategy Learning', detail: '3 workers implement taxonomy + tracking + learning', model: 'haiku' },
    { title: 'Phase 3: Modular Services', detail: '3 workers implement contracts + degradation + health', model: 'opus' },
    { title: 'Phase 4: Evaluation Harness', detail: '3 workers implement dataset + pipeline + ablation', model: 'sonnet' },
    { title: 'Fleet Review', detail: '4 models review all implementations' }
  ]
};

// Use bulkOrchestrate pattern for true SSH distribution
// This bypasses the workflow tool's agent() limitation

phase('Phase 0: Experiment Framework');

log('Distributing Phase 0 tasks across fleet via SSH...');

const phase0Tasks = [
  {
    name: 'Experiment DB Schema',
    description: 'Create db/migrations/020_experiment_framework.sql with experiments.registry and experiments.runs tables',
    output_file: 'db/migrations/020_experiment_framework.sql',
    test_command: 'psql -h aio-01 -U sfloess -d learning -f db/migrations/020_experiment_framework.sql --dry-run'
  },
  {
    name: 'Experiment Manager',
    description: 'Create shared/experiment-manager.cjs with runExperiment(), compareResults(), recordExperiment() functions. Include statistical testing (t-test, bootstrap).',
    output_file: 'shared/experiment-manager.cjs',
    test_command: 'node shared/experiment-manager.test.cjs'
  },
  {
    name: 'A/B Runner',
    description: 'Create shared/ab-runner.cjs with runABTest(), computeStatistics(), generateReport() functions. Feature toggle support.',
    output_file: 'shared/ab-runner.cjs',
    test_command: 'node shared/ab-runner.test.cjs'
  }
];

// Call fleet orchestrator via agent (it will handle SSH distribution internally)
const phase0Result = await agent(
  `You are the fleet orchestrator. Distribute these 3 implementation tasks across available workers using SSH:

${JSON.stringify(phase0Tasks, null, 2)}

**Your task:**
1. Use fleet-utils.js getWorkers() to find available nodes
2. Use remoteExec() to SSH to each worker
3. Each worker should create the specified file with full implementation
4. Run tests on each worker to verify
5. Return summary of which worker did what and test results

**Working directory:** /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

**Return JSON:**
{
  "tasks_completed": 3,
  "worker_assignments": [
    {"worker": "server-01", "task": "Experiment DB Schema", "status": "success", "tests_passing": true},
    {"worker": "server-02", "task": "Experiment Manager", "status": "success", "tests_passing": true},
    {"worker": "server-03", "task": "A/B Runner", "status": "success", "tests_passing": true}
  ],
  "files_created": ["db/migrations/020_experiment_framework.sql", "shared/experiment-manager.cjs", "shared/ab-runner.cjs"],
  "issues": []
}`,
  {
    label: 'Phase 0: Fleet Orchestration',
    phase: 'Phase 0: Experiment Framework',
    model: 'opus',
    effort: 'high',
    schema: {
      type: 'object',
      properties: {
        tasks_completed: { type: 'number' },
        worker_assignments: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              worker: { type: 'string' },
              task: { type: 'string' },
              status: { type: 'string' },
              tests_passing: { type: 'boolean' }
            }
          }
        },
        files_created: { type: 'array', items: { type: 'string' } },
        issues: { type: 'array', items: { type: 'string' } }
      },
      required: ['tasks_completed', 'worker_assignments', 'files_created']
    }
  }
);

log(`Phase 0: ${phase0Result.tasks_completed}/3 tasks completed across fleet`);

// Phase 1: Capability Architecture
phase('Phase 1: Capability Architecture');

const phase1Tasks = [
  {
    name: 'Capability Interfaces',
    description: 'Create shared/capabilities.cjs defining 6 capability types: reasoner, verifier, critic, planner, summarizer, code_reviewer. Each with quality thresholds, cost limits, latency limits.',
    output_file: 'shared/capabilities.cjs',
    test_command: 'node shared/capabilities.test.cjs'
  },
  {
    name: 'Capability Registry',
    description: 'Create db/migrations/021_capability_registry.sql and shared/capability-registry.cjs for tracking which models can fill which capabilities. Auto-populate from execution history.',
    output_file: 'shared/capability-registry.cjs',
    test_command: 'node shared/capability-registry.test.cjs'
  },
  {
    name: 'Role-Based Routing',
    description: 'Create shared/role-based-routing.cjs with selectCapability(role, options) function. Vendor-neutral selection, integrates with Thompson Sampling.',
    output_file: 'shared/role-based-routing.cjs',
    test_command: 'node shared/role-based-routing.test.cjs'
  }
];

const phase1Result = await agent(
  `Fleet orchestrator: Distribute these 3 capability architecture tasks across workers:

${JSON.stringify(phase1Tasks, null, 2)}

Use SSH via fleet-utils.js to distribute work. Return same JSON format as Phase 0.`,
  {
    label: 'Phase 1: Fleet Orchestration',
    phase: 'Phase 1: Capability Architecture',
    model: 'sonnet',
    effort: 'high',
    schema: {
      type: 'object',
      properties: {
        tasks_completed: { type: 'number' },
        worker_assignments: { type: 'array' },
        files_created: { type: 'array', items: { type: 'string' } },
        issues: { type: 'array', items: { type: 'string' } }
      },
      required: ['tasks_completed', 'files_created']
    }
  }
);

log(`Phase 1: ${phase1Result.tasks_completed}/3 tasks completed`);

// Phase 2: Strategy Learning
phase('Phase 2: Strategy Learning');

const phase2Tasks = [
  {
    name: 'Strategy Taxonomy',
    description: 'Create shared/strategy-taxonomy.cjs defining 4 strategy dimensions: prompts (zero_shot, few_shot, chain_of_thought, tree_of_thought), orchestration (single, consensus, adversarial, cascading), verification (self_check, peer_review, adversarial_refute), sequences (analyze_then_verify, parallel_then_merge, iterative_refine).',
    output_file: 'shared/strategy-taxonomy.cjs',
    test_command: 'node shared/strategy-taxonomy.test.cjs'
  },
  {
    name: 'Strategy Tracking',
    description: 'Create db/migrations/022_strategy_tracking.sql extending learning.strategy_performance with columns: prompt_template_id, orchestration_pattern, verification_method, reasoning_sequence. Create shared/strategy-tracker.cjs for recording strategy results.',
    output_file: 'shared/strategy-tracker.cjs',
    test_command: 'node shared/strategy-tracker.test.cjs'
  },
  {
    name: 'Multi-Dimensional Learning',
    description: 'Create shared/multi-dimensional-learning.cjs implementing Thompson Sampling per (capability, task_type, strategy). Learns which strategies work best for which tasks.',
    output_file: 'shared/multi-dimensional-learning.cjs',
    test_command: 'node shared/multi-dimensional-learning.test.cjs'
  }
];

const phase2Result = await agent(
  `Fleet orchestrator: Distribute these 3 strategy learning tasks:

${JSON.stringify(phase2Tasks, null, 2)}`,
  {
    label: 'Phase 2: Fleet Orchestration',
    phase: 'Phase 2: Strategy Learning',
    model: 'haiku',
    effort: 'high',
    schema: {
      type: 'object',
      properties: {
        tasks_completed: { type: 'number' },
        files_created: { type: 'array', items: { type: 'string' } },
        issues: { type: 'array', items: { type: 'string' } }
      },
      required: ['tasks_completed', 'files_created']
    }
  }
);

log(`Phase 2: ${phase2Result.tasks_completed}/3 tasks completed`);

// Phase 3: Modular Services
phase('Phase 3: Modular Services');

const phase3Tasks = [
  {
    name: 'Service Interface Contracts',
    description: 'Create shared/service-interface.cjs with base Service class (initialize(), execute(), healthCheck(), shutdown()) and ServiceRegistry singleton (register(), get(), getOptional(), list()).',
    output_file: 'shared/service-interface.cjs',
    test_command: 'node shared/service-interface.test.cjs'
  },
  {
    name: 'Graceful Degradation',
    description: 'Create shared/graceful-degradation.cjs with executeWithFallback(), getServiceOrFallback(), requireService() functions. Logging and Prometheus metrics for degradation events.',
    output_file: 'shared/graceful-degradation.cjs',
    test_command: 'node shared/graceful-degradation.test.cjs'
  },
  {
    name: 'Service Health Monitoring',
    description: 'Create monitoring/service-health.cjs with checkServiceHealth(), checkAllServices(), autoDisableUnhealthy(), getHealthMetrics() functions. 60-second health check interval.',
    output_file: 'monitoring/service-health.cjs',
    test_command: 'node monitoring/service-health.test.cjs'
  }
];

const phase3Result = await agent(
  `Fleet orchestrator: Distribute these 3 modular service tasks:

${JSON.stringify(phase3Tasks, null, 2)}`,
  {
    label: 'Phase 3: Fleet Orchestration',
    phase: 'Phase 3: Modular Services',
    model: 'opus',
    effort: 'high',
    schema: {
      type: 'object',
      properties: {
        tasks_completed: { type: 'number' },
        files_created: { type: 'array', items: { type: 'string' } },
        issues: { type: 'array', items: { type: 'string' } }
      },
      required: ['tasks_completed', 'files_created']
    }
  }
);

log(`Phase 3: ${phase3Result.tasks_completed}/3 tasks completed`);

// Phase 4: Evaluation Harness
phase('Phase 4: Evaluation Harness');

const phase4Tasks = [
  {
    name: 'Benchmark Dataset',
    description: 'Create evaluation/benchmark-dataset.json with 1,000 questions across 7 task types (code_review, research, math, security, creative, legal, networking). Each with ground truth. Create db/migrations/023_evaluation_schema.sql.',
    output_file: 'evaluation/benchmark-dataset.json',
    test_command: 'jq length evaluation/benchmark-dataset.json | grep 1000'
  },
  {
    name: 'Evaluation Pipeline',
    description: 'Create evaluation/evaluation-pipeline.cjs with runBenchmark(), compareConfigs(), detectRegression(), generateReport() functions. Weekly automated runs, regression alerts if quality drops >5%.',
    output_file: 'evaluation/evaluation-pipeline.cjs',
    test_command: 'node evaluation/evaluation-pipeline.test.cjs'
  },
  {
    name: 'Feature Ablation Study',
    description: 'Create evaluation/ablation-study.cjs with runAblation(), quantifyContribution(), generateAblationReport() functions. Tests each feature in isolation with statistical significance.',
    output_file: 'evaluation/ablation-study.cjs',
    test_command: 'node evaluation/ablation-study.test.cjs'
  }
];

const phase4Result = await agent(
  `Fleet orchestrator: Distribute these 3 evaluation harness tasks:

${JSON.stringify(phase4Tasks, null, 2)}`,
  {
    label: 'Phase 4: Fleet Orchestration',
    phase: 'Phase 4: Evaluation Harness',
    model: 'sonnet',
    effort: 'xhigh',
    schema: {
      type: 'object',
      properties: {
        tasks_completed: { type: 'number' },
        files_created: { type: 'array', items: { type: 'string' } },
        issues: { type: 'array', items: { type: 'string' } }
      },
      required: ['tasks_completed', 'files_created']
    }
  }
);

log(`Phase 4: ${phase4Result.tasks_completed}/3 tasks completed`);

// Fleet Review
phase('Fleet Review');

log('Running 4-model fleet review of all implementations...');

const reviewResults = await parallel([
  () => agent(
    `Review Phase 0 (Experiment Framework) implementations:
- ${phase0Result.files_created.join(', ')}

Check: code quality, test coverage, database integration, security, performance.
Grade A/B/C/F and list issues.`,
    {
      label: 'Review Phase 0',
      model: 'opus',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          issues: { type: 'array', items: { type: 'string' } },
          strengths: { type: 'array', items: { type: 'string' } }
        },
        required: ['grade']
      }
    }
  ),

  () => agent(
    `Review Phase 1 (Capability Architecture):
- ${phase1Result.files_created.join(', ')}

Check: vendor neutrality, future-proof design, quality/cost/latency optimization.
Grade A/B/C/F.`,
    {
      label: 'Review Phase 1',
      model: 'sonnet',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['grade']
      }
    }
  ),

  () => agent(
    `Review Phase 2 (Strategy Learning):
- ${phase2Result.files_created.join(', ')}

Check: learns strategies not just models, multi-dimensional bandit correct, database efficient.
Grade A/B/C/F.`,
    {
      label: 'Review Phase 2',
      model: 'haiku',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['grade']
      }
    }
  ),

  () => agent(
    `Review Phase 3 (Modular Services):
- ${phase3Result.files_created.join(', ')}

Check: every service truly removable, fallback logic correct, health monitoring comprehensive.
Grade A/B/C/F.`,
    {
      label: 'Review Phase 3',
      model: 'opus',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['grade']
      }
    }
  )
]);

const allGradeA = reviewResults.filter(Boolean).every(r => r.grade === 'A');
log(`Fleet review: ${reviewResults.filter(r => r?.grade === 'A').length}/4 phases graded A`);

// Final Summary
return {
  workflow: 'fleet-implements-phases',
  status: 'complete',
  phases: {
    phase0: phase0Result,
    phase1: phase1Result,
    phase2: phase2Result,
    phase3: phase3Result,
    phase4: phase4Result
  },
  total_files_created: [
    ...phase0Result.files_created,
    ...phase1Result.files_created,
    ...phase2Result.files_created,
    ...phase3Result.files_created,
    ...phase4Result.files_created
  ].length,
  fleet_review: reviewResults.filter(Boolean),
  production_ready: allGradeA,
  all_issues: reviewResults.filter(Boolean).flatMap(r => r.issues || [])
};
