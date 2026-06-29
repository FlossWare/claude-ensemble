export const meta = {
  name: 'fleet-implements-all-parallel',
  description: 'All 5 phases implemented in parallel across full 8-node fleet',
  phases: [
    { title: 'Parallel Implementation', detail: '15 tasks across 8 workers simultaneously' },
    { title: 'Fleet Review', detail: '4 models review all implementations' }
  ]
};

// All 15 tasks from all 5 phases - distribute across 8 workers
const ALL_TASKS = [
  // Phase 0: Experiment Framework (3 tasks)
  { phase: 0, name: 'Experiment DB Schema', file: 'db/migrations/020_experiment_framework.sql', worker: 'laptop-01' },
  { phase: 0, name: 'Experiment Manager', file: 'shared/experiment-manager.cjs', worker: 'server-01' },
  { phase: 0, name: 'A/B Runner', file: 'shared/ab-runner.cjs', worker: 'server-02' },

  // Phase 1: Capability Architecture (3 tasks)
  { phase: 1, name: 'Capability Interfaces', file: 'shared/capabilities.cjs', worker: 'server-03' },
  { phase: 1, name: 'Capability Registry', file: 'shared/capability-registry.cjs', worker: 'pi-01' },
  { phase: 1, name: 'Role-Based Routing', file: 'shared/role-based-routing.cjs', worker: 'pi-02' },

  // Phase 2: Strategy Learning (3 tasks)
  { phase: 2, name: 'Strategy Taxonomy', file: 'shared/strategy-taxonomy.cjs', worker: 'desktop-ap' },
  { phase: 2, name: 'Strategy Tracking', file: 'shared/strategy-tracker.cjs', worker: 'server-ap' },
  { phase: 2, name: 'Multi-Dimensional Learning', file: 'shared/multi-dimensional-learning.cjs', worker: 'laptop-01' },

  // Phase 3: Modular Services (3 tasks)
  { phase: 3, name: 'Service Interface Contracts', file: 'shared/service-interface.cjs', worker: 'server-01' },
  { phase: 3, name: 'Graceful Degradation', file: 'shared/graceful-degradation.cjs', worker: 'server-02' },
  { phase: 3, name: 'Service Health Monitoring', file: 'monitoring/service-health.cjs', worker: 'server-03' },

  // Phase 4: Evaluation Harness (3 tasks)
  { phase: 4, name: 'Benchmark Dataset', file: 'evaluation/benchmark-dataset.json', worker: 'pi-01' },
  { phase: 4, name: 'Evaluation Pipeline', file: 'evaluation/evaluation-pipeline.cjs', worker: 'pi-02' },
  { phase: 4, name: 'Ablation Study', file: 'evaluation/ablation-study.cjs', worker: 'desktop-ap' }
];

phase('Parallel Implementation');

log(`Distributing all 15 tasks across 8 workers in parallel...`);
log(`Worker assignments: laptop-01(2), server-01(2), server-02(2), server-03(2), pi-01(2), pi-02(2), desktop-ap(2), server-ap(1)`);

// Create one agent per task - all run in parallel
const implementationResults = await parallel(
  ALL_TASKS.map(task => () =>
    agent(
      `**CRITICAL: Execute on fleet worker ${task.worker} via SSH**

**Task:** ${task.name} (Phase ${task.phase})
**Output file:** ${task.file}

**Implementation requirements:**

${task.phase === 0 && task.name === 'Experiment DB Schema' ? `
Create database migration:
- Tables: experiments.registry (id, name, hypothesis, metric, success_criteria, status, created_at)
- Tables: experiments.runs (id, experiment_id, baseline_config, treatment_config, result, verdict, run_date)
- Indexes for fast lookups
` : ''}

${task.phase === 0 && task.name === 'Experiment Manager' ? `
Create experiment manager with:
- runExperiment(config) - Runs baseline vs treatment
- compareResults(baseline, treatment) - Statistical testing (t-test, bootstrap)
- recordExperiment(name, hypothesis, result) - Store in PostgreSQL
- Include comprehensive tests
` : ''}

${task.phase === 0 && task.name === 'A/B Runner' ? `
Create A/B testing infrastructure:
- runABTest(experimentName, configs) - Multiple variants
- computeStatistics(results) - p-value, effect size, confidence intervals
- generateReport(results) - Markdown summary
- Feature toggle support
- Include tests
` : ''}

${task.phase === 1 && task.name === 'Capability Interfaces' ? `
Define 6 capability types:
- reasoner, verifier, critic, planner, summarizer, code_reviewer
- Each with: min_quality, max_cost_per_1k, max_latency_ms
- Export as const CAPABILITIES object
` : ''}

${task.phase === 1 && task.name === 'Capability Registry' ? `
Create capability registry:
- Database migration: learning.model_capabilities table
- registerCapability(model, capability, metrics)
- getCapableModels(capability, requirements)
- Auto-populate from execution history
` : ''}

${task.phase === 1 && task.name === 'Role-Based Routing' ? `
Create vendor-neutral routing:
- selectCapability(role, options) - Returns best model for capability
- Integration with Thompson Sampling
- Quality/cost/latency optimization
- Fallback logic if no models meet requirements
` : ''}

${task.phase === 2 && task.name === 'Strategy Taxonomy' ? `
Define 4 strategy dimensions:
- prompts: [zero_shot, few_shot, chain_of_thought, tree_of_thought]
- orchestration: [single_model, consensus, adversarial, cascading]
- verification: [self_check, peer_review, adversarial_refute]
- sequences: [analyze_then_verify, parallel_then_merge, iterative_refine]
` : ''}

${task.phase === 2 && task.name === 'Strategy Tracking' ? `
Extend database for strategy tracking:
- Migration: Add columns to learning.strategy_performance
- recordStrategyResult(strategy, task_type, outcome)
- getStrategyPerformance(strategyDimensions, taskType)
- getBestStrategy(taskType, constraints)
` : ''}

${task.phase === 2 && task.name === 'Multi-Dimensional Learning' ? `
Thompson Sampling per (capability, task_type, strategy):
- selectStrategy(capability, taskType, constraints)
- updateStrategyBandit(capability, taskType, strategy, reward)
- Multi-dimensional performance tracking
- Integration with postgres-adapter.js
` : ''}

${task.phase === 3 && task.name === 'Service Interface Contracts' ? `
Base Service class and ServiceRegistry:
- Service.initialize(), execute(), healthCheck(), shutdown()
- ServiceRegistry.register(), get(), getOptional(), list()
- Singleton pattern for registry
` : ''}

${task.phase === 3 && task.name === 'Graceful Degradation' ? `
Fallback logic for unavailable services:
- executeWithFallback(serviceName, input, fallbackFn)
- getServiceOrFallback(serviceName, fallbackService)
- Logging and Prometheus metrics for degradation
` : ''}

${task.phase === 3 && task.name === 'Service Health Monitoring' ? `
Health monitoring for all services:
- checkServiceHealth(serviceName) - Returns health status
- checkAllServices() - Health map
- autoDisableUnhealthy(threshold) - Auto-disable if unhealthy
- Prometheus metrics integration
` : ''}

${task.phase === 4 && task.name === 'Benchmark Dataset' ? `
Create 1,000 question benchmark:
- 7 task types: code_review(200), research(150), math(150), security(150), creative(100), legal(100), networking(150)
- Each with ground truth (human-verified or established facts)
- Difficulty: easy(30%), medium(50%), hard(20%)
- JSON format
` : ''}

${task.phase === 4 && task.name === 'Evaluation Pipeline' ? `
Automated benchmark runner:
- runBenchmark(config) - Full suite execution
- compareConfigs(baseline, treatment) - A/B comparison
- detectRegression(current, historical) - Alert if quality drops >5%
- Metrics: accuracy, precision, recall, F1, cost, latency
` : ''}

${task.phase === 4 && task.name === 'Ablation Study' ? `
Feature ablation testing:
- runAblation(features) - Test with feature subsets
- quantifyContribution(feature) - Isolate impact
- generateAblationReport(results) - Statistical analysis
- Feature toggles for thompson_sampling, adversarial_verification, etc.
` : ''}

**Working directory:** /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

**Instructions:**
1. SSH to ${task.worker}: ssh claude@${task.worker}
2. cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
3. Create ${task.file} with full implementation
4. Create test file (${task.file.replace('.cjs', '.test.cjs').replace('.sql', '-test.sql').replace('.json', '-test.js')})
5. Run tests to verify
6. Return results

**Return JSON:**
{
  "task": "${task.name}",
  "worker": "${task.worker}",
  "file_created": "${task.file}",
  "tests_passing": true,
  "lines_of_code": 0,
  "issues": []
}`,
      {
        label: `${task.name} (${task.worker})`,
        phase: 'Parallel Implementation',
        model: task.phase === 0 || task.phase === 3 ? 'opus' : task.phase === 1 || task.phase === 4 ? 'sonnet' : 'haiku',
        effort: task.phase === 4 && task.name === 'Benchmark Dataset' ? 'xhigh' : 'high',
        schema: {
          type: 'object',
          properties: {
            task: { type: 'string' },
            worker: { type: 'string' },
            file_created: { type: 'string' },
            tests_passing: { type: 'boolean' },
            lines_of_code: { type: 'number' },
            issues: { type: 'array', items: { type: 'string' } }
          },
          required: ['task', 'worker', 'file_created', 'tests_passing']
        }
      }
    )
  )
);

const successfulTasks = implementationResults.filter(Boolean);
log(`Implementation complete: ${successfulTasks.length}/15 tasks successful`);

// Group by phase for summary
const byPhase = {
  phase0: successfulTasks.filter(t => t.task.includes('Experiment') || t.task.includes('A/B')),
  phase1: successfulTasks.filter(t => t.task.includes('Capability') || t.task.includes('Role')),
  phase2: successfulTasks.filter(t => t.task.includes('Strategy') || t.task.includes('Learning')),
  phase3: successfulTasks.filter(t => t.task.includes('Service') || t.task.includes('Degradation') || t.task.includes('Health')),
  phase4: successfulTasks.filter(t => t.task.includes('Benchmark') || t.task.includes('Evaluation') || t.task.includes('Ablation'))
};

log(`By phase: P0=${byPhase.phase0.length}/3, P1=${byPhase.phase1.length}/3, P2=${byPhase.phase2.length}/3, P3=${byPhase.phase3.length}/3, P4=${byPhase.phase4.length}/3`);

// Fleet Review
phase('Fleet Review');

log('4-model fleet review of all implementations...');

const reviewResults = await parallel([
  () => agent(
    `Review Phase 0 (Experiment Framework):
${byPhase.phase0.map(t => `- ${t.file_created} (${t.lines_of_code} lines)`).join('\n')}

Grade A/B/C/F. Check: code quality, tests, database integration, security.`,
    {
      label: 'Review Phase 0',
      model: 'opus',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          phase: { type: 'string' },
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          issues: { type: 'array', items: { type: 'string' } },
          strengths: { type: 'array', items: { type: 'string' } }
        },
        required: ['phase', 'grade']
      }
    }
  ),

  () => agent(
    `Review Phase 1 (Capability Architecture):
${byPhase.phase1.map(t => `- ${t.file_created}`).join('\n')}

Grade A/B/C/F. Check: vendor neutrality, future-proof, quality optimization.`,
    {
      label: 'Review Phase 1',
      model: 'sonnet',
      schema: { type: 'object', properties: { phase: { type: 'string' }, grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] }, issues: { type: 'array' } }, required: ['phase', 'grade'] }
    }
  ),

  () => agent(
    `Review Phase 2 (Strategy Learning):
${byPhase.phase2.map(t => `- ${t.file_created}`).join('\n')}

Grade A/B/C/F. Check: learns strategies not models, multi-dimensional correct.`,
    {
      label: 'Review Phase 2',
      model: 'haiku',
      schema: { type: 'object', properties: { phase: { type: 'string' }, grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] }, issues: { type: 'array' } }, required: ['phase', 'grade'] }
    }
  ),

  () => agent(
    `Review Phase 3 (Modular Services):
${byPhase.phase3.map(t => `- ${t.file_created}`).join('\n')}

Grade A/B/C/F. Check: services removable, fallback correct, health monitoring.`,
    {
      label: 'Review Phase 3',
      model: 'opus',
      schema: { type: 'object', properties: { phase: { type: 'string' }, grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] }, issues: { type: 'array' } }, required: ['phase', 'grade'] }
    }
  ),

  () => agent(
    `Review Phase 4 (Evaluation Harness):
${byPhase.phase4.map(t => `- ${t.file_created}`).join('\n')}

Grade A/B/C/F. Check: benchmark quality, regression detection, statistical validity.`,
    {
      label: 'Review Phase 4',
      model: 'sonnet',
      schema: { type: 'object', properties: { phase: { type: 'string' }, grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] }, issues: { type: 'array' } }, required: ['phase', 'grade'] }
    }
  )
]);

const allGradeA = reviewResults.filter(Boolean).every(r => r.grade === 'A');
log(`Fleet review: ${reviewResults.filter(r => r?.grade === 'A').length}/5 phases graded A`);

return {
  workflow: 'fleet-implements-all-parallel',
  total_tasks: 15,
  successful_tasks: successfulTasks.length,
  by_phase: {
    phase0: byPhase.phase0.length,
    phase1: byPhase.phase1.length,
    phase2: byPhase.phase2.length,
    phase3: byPhase.phase3.length,
    phase4: byPhase.phase4.length
  },
  files_created: successfulTasks.map(t => t.file_created),
  total_lines_of_code: successfulTasks.reduce((sum, t) => sum + (t.lines_of_code || 0), 0),
  fleet_review: reviewResults.filter(Boolean),
  production_ready: allGradeA,
  all_issues: [
    ...successfulTasks.flatMap(t => t.issues || []),
    ...reviewResults.filter(Boolean).flatMap(r => r.issues || [])
  ]
};
