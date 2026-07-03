/**
 * Example: Feedback Loop Integrated Workflow
 *
 * Demonstrates how to integrate feedback loop monitoring into multi-AI workflows
 *
 * Features:
 * - Pre-flight check for critical risks
 * - Post-execution analysis
 * - Automatic mitigation on detection
 *
 * Created: 2026-07-03
 */

import { beforeWorkflow, afterWorkflow, getRisksByType } from '../shared/feedback-loop-adapter.cjs';
import { getWorkflowStorage } from '../shared/workflow-storage-adapter.cjs';

export default async function exampleFeedbackLoopIntegration({ parallel, agent, log }) {
  const db = getWorkflowStorage();

  log('Starting feedback loop integrated workflow...');

  // PHASE 0: Pre-flight check
  log('Phase 0: Checking for feedback loop risks...');

  try {
    // Only fail on critical risks (severity > 0.8)
    await beforeWorkflow({ criticalOnly: true, windowDays: 7 });
    log('✓ No critical feedback loop risks detected');
  } catch (err) {
    log('✗ Critical feedback loop risks detected:');
    log(err.message);

    // Optional: continue with mitigation, or fail
    throw new Error('Aborting workflow due to critical feedback loop risks');
  }

  // Get model distribution for adaptive routing
  const { getModelDistribution } = await import('../shared/feedback-loop-adapter.cjs');
  const distribution = await getModelDistribution(7);

  log('Model distribution (7 days):', distribution);

  // Identify minority models (< 15% usage)
  const minorityModels = Object.entries(distribution)
    .filter(([model, pct]) => pct < 0.15)
    .map(([model]) => model);

  if (minorityModels.length > 0) {
    log('Boosting minority models to prevent dominance:', minorityModels);
  }

  // PHASE 1: Task decomposition
  log('Phase 1: Decomposing task...');

  const taskDescription = 'Example multi-AI research task with feedback loop monitoring';

  const execId = await db.storeExecution({
    workflow_id: 'feedback-loop-example-' + Date.now(),
    workflow_name: 'example-feedback-loop-integration',
    task_description: taskDescription,
    total_workers: 3,
    total_duration_ms: 0,
    outcome: 'pending'
  });

  await db.storePhase({
    workflow_execution_id: execId,
    phase_name: 'decomposition',
    phase_order: 1,
    duration_ms: 100,
    outcome: 'success'
  });

  // PHASE 2: Parallel workers (with diversity enforcement)
  log('Phase 2: Spawning workers with diversity enforcement...');

  const models = ['opus', 'sonnet', 'haiku'];

  // Boost minority models by preferring them
  const selectedModels = models.filter(m => {
    if (minorityModels.includes(m)) {
      return Math.random() < 0.8; // 80% chance to use minority model
    }
    return Math.random() < 0.5; // 50% chance to use majority model
  });

  log('Selected models (diversity-aware):', selectedModels);

  const workers = await parallel(
    selectedModels.map((model, i) => ({
      name: `worker-${i}`,
      model,
      prompt: `Research aspect ${i + 1} of: ${taskDescription}`,
      onResult: async (result) => {
        await db.storeWorkerResult({
          workflow_execution_id: execId,
          worker_id: `worker-${i}`,
          model,
          task_assigned: `Research aspect ${i + 1}`,
          result: result.output || 'No output',
          confidence: 0.85,
          duration_ms: result.duration || 1000,
          input_tokens: 500,
          output_tokens: 300,
          cost_usd: 0.01,
          outcome: 'success'
        });
      }
    }))
  );

  await db.storePhase({
    workflow_execution_id: execId,
    phase_name: 'workers',
    phase_order: 2,
    duration_ms: 5000,
    outcome: 'success'
  });

  // PHASE 3: Arbiter (with coupling prevention)
  log('Phase 3: Selecting arbiter with coupling prevention...');

  // Check for eval-gen coupling risks
  const couplingRisks = await getRisksByType('eval_gen_coupling', 7);

  const problematicModels = couplingRisks
    .filter(r => r.severity > 0.6)
    .map(r => r.evidence.model);

  log('Models with high self-eval coupling:', problematicModels);

  // Select arbiter: must differ from all workers AND not in problematic list
  const arbiterCandidates = ['gemini', 'gpt4o', 'fable'].filter(
    m => !selectedModels.includes(m) && !problematicModels.includes(m)
  );

  const arbiterModel = arbiterCandidates[0] || 'gemini'; // Fallback to gemini

  log('Selected arbiter:', arbiterModel);

  const arbiter = await agent({
    name: 'arbiter',
    model: arbiterModel,
    prompt: `Synthesize these worker results:\n${workers.map(w => w.output).join('\n\n')}`,
  });

  await db.storeArbiterDecision({
    workflow_execution_id: execId,
    arbiter_model: arbiterModel,
    worker_result_ids: workers.map((_, i) => i + 1),
    decision: arbiter.output || 'Synthesis complete',
    reasoning: 'Multi-model consensus with coupling prevention',
    confidence: 0.90,
    duration_ms: 2000,
    input_tokens: 1500,
    output_tokens: 800,
    cost_usd: 0.02
  });

  await db.storePhase({
    workflow_execution_id: execId,
    phase_name: 'arbiter',
    phase_order: 3,
    duration_ms: 2000,
    outcome: 'success'
  });

  // PHASE 4: Post-execution analysis
  log('Phase 4: Post-execution feedback loop analysis...');

  const analysis = await afterWorkflow({ workflowId: execId, warnOnly: true });

  log('Post-execution analysis:', {
    total_risks: analysis.summary.total_risks,
    critical: analysis.summary.critical,
    high: analysis.summary.high
  });

  if (analysis.summary.critical > 0) {
    log('⚠ WARNING: Workflow may have introduced critical feedback loop risks!');

    // Store feedback
    await db.storeFeedback({
      workflow_execution_id: execId,
      feedback_type: 'automated',
      quality_score: 0.5, // Downgrade quality due to risk
      feedback_text: 'Critical feedback loop risks detected post-execution',
      metadata: { analysis: analysis.summary }
    });
  }

  // Store learnings
  await db.storeLearnings({
    workflow_execution_id: execId,
    learning_type: 'pattern',
    description: 'Feedback loop monitoring integrated successfully',
    actionable_insight: `Diversity enforcement selected models: ${selectedModels.join(', ')}. Arbiter selected with coupling prevention: ${arbiterModel}`,
    importance: 0.7,
    metadata: {
      minority_models: minorityModels,
      selected_models: selectedModels,
      arbiter_model: arbiterModel,
      problematic_models: problematicModels
    }
  });

  log('✓ Workflow complete with feedback loop monitoring');

  return {
    arbiter_decision: arbiter.output,
    model_distribution: distribution,
    risks_detected: analysis.summary.total_risks,
    diversity_enforced: minorityModels.length > 0
  };
}
