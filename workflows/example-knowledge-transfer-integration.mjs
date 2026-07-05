#!/usr/bin/env node
/**
 * Example Workflow with Knowledge Transfer Integration
 *
 * Demonstrates how to use knowledge transfer optimizer to inject
 * prior learnings into new workflow executions.
 *
 * Pattern:
 * 1. Before workflow: Load similar workflows and extract learnings
 * 2. During workflow: Inject context into worker prompts
 * 3. After workflow: Record which context was used for effectiveness tracking
 *
 * Created: 2026-07-03
 */

import { getWorkflowStorage } from '../shared/workflow-storage-adapter.cjs';
import {
  beforeWorkflow,
  afterWorkflow,
  formatAsContext,
  evaluateEffectiveness
} from '../shared/knowledge-transfer-adapter.cjs';

/**
 * Example workflow with knowledge transfer
 */
export default async function exampleWorkflowWithKnowledgeTransfer({
  phase,
  parallel,
  agent,
  log,
  taskDescription = 'Fix authentication bug in OAuth2 flow'
}) {
  log('=' .repeat(80));
  log('WORKFLOW: Knowledge Transfer Integration Example');
  log('=' .repeat(80));

  const db = getWorkflowStorage();
  const workflowId = `wf-kt-example-${Date.now()}`;

  // =============================================================================
  // STEP 1: LOAD PRIOR KNOWLEDGE (before workflow execution)
  // =============================================================================

  log('\n[STEP 1] Loading prior knowledge from similar workflows...');

  const { plan, context } = await beforeWorkflow(taskDescription, {
    includeContext: true
  });

  log(`  Retrieved: ${plan.candidates_retrieved} candidates`);
  log(`  Positive transfers: ${plan.positive_transfers.length}`);
  log(`  Key learnings: ${plan.key_learnings.length}`);

  if (plan.estimated_duration_ms) {
    log(`  Estimated duration: ${(plan.estimated_duration_ms / 1000).toFixed(1)}s`);
  }
  log(`  Estimated confidence: ${(plan.estimated_confidence * 100).toFixed(0)}%`);

  // Print context that will be injected
  if (context) {
    log('\n[CONTEXT TO INJECT]');
    log(context);
  }

  // =============================================================================
  // STEP 2: EXECUTE WORKFLOW (with context injection)
  // =============================================================================

  log('\n[STEP 2] Executing workflow with context injection...');

  const workflowStartTime = Date.now();

  // Store execution metadata (before workers run)
  const execId = await db.storeExecution({
    workflow_id: workflowId,
    workflow_name: 'knowledge-transfer-example',
    task_description: taskDescription,
    total_workers: 3,
    total_duration_ms: 0, // Will update later
    outcome: 'pending',
    metadata: {
      has_knowledge_transfer: true,
      context_preview: context.substring(0, 200)
    }
  });

  log(`  Workflow execution ID: ${execId}`);

  // Phase 1: Analysis (with context)
  await phase('Analysis', async () => {
    const phaseStartTime = Date.now();

    // Worker 1: Code analysis
    const worker1 = await agent({
      model: 'opus',
      prompt: `
Task: ${taskDescription}

PRIOR KNOWLEDGE FROM SIMILAR TASKS:
${context}

Analyze the authentication flow and identify potential issues.
      `.trim()
    });

    await db.storeWorkerResult({
      workflow_execution_id: execId,
      worker_id: 'worker-1-analysis',
      model: 'opus',
      task_assigned: 'Analyze authentication flow',
      result: worker1.output || 'Analysis complete',
      confidence: 0.85,
      duration_ms: Date.now() - phaseStartTime,
      input_tokens: 1500,
      output_tokens: 800,
      cost_usd: 0.05,
      outcome: 'success',
      metadata: {
        used_context: true,
        context_lines: context.split('\n').length
      }
    });

    await db.storePhase({
      workflow_execution_id: execId,
      phase_name: 'analysis',
      phase_order: 1,
      duration_ms: Date.now() - phaseStartTime,
      outcome: 'success'
    });

    log('  Phase 1 (Analysis): Complete');
  });

  // Phase 2: Fix Implementation (with context)
  await phase('Implementation', async () => {
    const phaseStartTime = Date.now();

    const worker2 = await agent({
      model: 'sonnet',
      prompt: `
Task: ${taskDescription}

PRIOR KNOWLEDGE:
${context}

Implement the fix based on the analysis and prior learnings.
      `.trim()
    });

    await db.storeWorkerResult({
      workflow_execution_id: execId,
      worker_id: 'worker-2-implementation',
      model: 'sonnet',
      task_assigned: 'Implement authentication fix',
      result: worker2.output || 'Fix implemented',
      confidence: 0.80,
      duration_ms: Date.now() - phaseStartTime,
      input_tokens: 2000,
      output_tokens: 1200,
      cost_usd: 0.08,
      outcome: 'success',
      metadata: {
        used_context: true
      }
    });

    await db.storePhase({
      workflow_execution_id: execId,
      phase_name: 'implementation',
      phase_order: 2,
      duration_ms: Date.now() - phaseStartTime,
      outcome: 'success'
    });

    log('  Phase 2 (Implementation): Complete');
  });

  // Phase 3: Verification
  await phase('Verification', async () => {
    const phaseStartTime = Date.now();

    const worker3 = await agent({
      model: 'haiku',
      prompt: `
Task: Verify the authentication fix

CONTEXT:
${context}

Verify that the fix addresses the issue and doesn't introduce regressions.
      `.trim()
    });

    await db.storeWorkerResult({
      workflow_execution_id: execId,
      worker_id: 'worker-3-verification',
      model: 'haiku',
      task_assigned: 'Verify authentication fix',
      result: worker3.output || 'Verification passed',
      confidence: 0.90,
      duration_ms: Date.now() - phaseStartTime,
      input_tokens: 1000,
      output_tokens: 500,
      cost_usd: 0.02,
      outcome: 'success',
      metadata: {
        used_context: true
      }
    });

    await db.storePhase({
      workflow_execution_id: execId,
      phase_name: 'verification',
      phase_order: 3,
      duration_ms: Date.now() - phaseStartTime,
      outcome: 'success'
    });

    log('  Phase 3 (Verification): Complete');
  });

  const totalDuration = Date.now() - workflowStartTime;

  // =============================================================================
  // STEP 3: RECORD KNOWLEDGE TRANSFER (after workflow execution)
  // =============================================================================

  log('\n[STEP 3] Recording knowledge transfer usage...');

  await afterWorkflow(plan, execId);

  // Update execution with final outcome
  await db.pool.query(
    `UPDATE workflow.executions
     SET total_duration_ms = $1, outcome = $2
     WHERE id = $3`,
    [totalDuration, 'success', execId]
  );

  log(`  Transfer plan applied to execution ${execId}`);

  // Store learnings extracted from this execution
  if (plan.key_learnings.length > 0) {
    await db.storeLearnings({
      workflow_execution_id: execId,
      learning_type: 'pattern',
      description: `Applied knowledge transfer: ${plan.key_learnings.length} prior learnings used`,
      actionable_insight: `Context injection improved execution (estimated vs actual: ${plan.estimated_duration_ms}ms vs ${totalDuration}ms)`,
      importance: 0.8,
      metadata: {
        context_used: true,
        learnings_count: plan.key_learnings.length,
        estimated_duration_ms: plan.estimated_duration_ms,
        actual_duration_ms: totalDuration
      }
    });

    log('  Learnings recorded');
  }

  // =============================================================================
  // STEP 4: EVALUATE EFFECTIVENESS
  // =============================================================================

  log('\n[STEP 4] Evaluating knowledge transfer effectiveness...');

  const stats = await evaluateEffectiveness(30);

  if (stats.with_context) {
    log(`  With context: ${stats.with_context.total} workflows, ${(stats.with_context.success_rate * 100).toFixed(0)}% success`);
  }

  if (stats.no_context) {
    log(`  No context: ${stats.no_context.total} workflows, ${(stats.no_context.success_rate * 100).toFixed(0)}% success`);
  }

  if (stats.improvement) {
    log(`  Improvement: ${(stats.improvement.success_rate_delta * 100).toFixed(1)}% success rate delta`);

    if (stats.improvement.duration_delta_ms) {
      log(`              ${stats.improvement.duration_delta_ms.toFixed(0)}ms duration delta`);
    }
  }

  // =============================================================================
  // DONE
  // =============================================================================

  log('\n' + '='.repeat(80));
  log('WORKFLOW COMPLETE');
  log('='.repeat(80));
  log(`Execution ID: ${execId}`);
  log(`Total Duration: ${totalDuration}ms (${(totalDuration / 1000).toFixed(1)}s)`);
  log(`Context Used: ${plan.positive_transfers.length} workflows`);
  log(`Learnings Injected: ${plan.key_learnings.length}`);
  log('='.repeat(80));

  return {
    execId,
    totalDuration,
    plan,
    stats
  };
}

// CLI execution
if (import.meta.url === `file://${process.argv[1]}`) {
  const task = process.argv[2] || 'Fix authentication bug in OAuth2 flow';

  exampleWorkflowWithKnowledgeTransfer({
    phase: async (name, fn) => {
      console.log(`\n[PHASE] ${name}`);
      await fn();
    },
    parallel: async (tasks) => {
      return await Promise.all(tasks.map(t => t()));
    },
    agent: async ({ model, prompt }) => {
      // Mock agent for demo
      console.log(`  [AGENT:${model}] Executing...`);
      return { output: `Mock response from ${model}` };
    },
    log: console.log,
    taskDescription: task
  })
    .then((result) => {
      console.log('\nWorkflow result:', result);
      process.exit(0);
    })
    .catch((err) => {
      console.error('Workflow failed:', err);
      process.exit(1);
    });
}
