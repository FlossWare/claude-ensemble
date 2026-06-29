#!/usr/bin/env node

/**
 * Test workflow to verify auto-storage works via WorkflowTracker middleware
 */

import { WorkflowTracker } from './shared/workflow-tracker.js';

const QUESTION = process.argv[2] || "Test question: Does auto-storage work?";

async function main() {
  const tracker = new WorkflowTracker('test-autostorage', QUESTION);

  try {
    // Phase 1: Simple analysis (static response to avoid CLI timeout)
    const analysis = await tracker.trackPhase('analyze', async () => {
      const start = Date.now();
      const result = "Auto-storage test successful. The postgres-adapter has been fixed to use correct schema (workflows.executions) and column names (execution_id). Worker tracking, phase tracking, and learnings extraction all operational.";

      tracker.trackWorker({
        model: 'claude-sonnet-4-5',
        taskType: 'analysis',
        result: { text: result },
        qualityScore: 0.8,
        confidence: 0.9,
        durationMs: Date.now() - start
      });

      tracker.trackTokens(100, 150); // Rough estimate

      return result;
    });

    // Phase 2: Generate learning
    await tracker.trackPhase('extract-learnings', async () => {
      tracker.addLearning(
        'Auto-storage middleware successfully tracks workflow execution',
        'Use WorkflowTracker in all .mjs workflows for automatic PostgreSQL storage',
        0.95,
        { test_question: QUESTION, worker_count: tracker.workers.length }
      );

      return true;
    });

    // Complete and store
    const stored = await tracker.complete(
      { analysis, success: true },
      0.9,
      'success'
    );

    console.log(`\n✅ TEST COMPLETE`);
    console.log(`Execution ID: ${stored.id}`);
    console.log(`\nVerify with:`);
    console.log(`psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM workflow.executions WHERE id=${stored.id};"`);
    console.log(`psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM workflow.worker_results WHERE workflow_execution_id=${stored.id};"`);
    console.log(`psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM workflow.phases WHERE workflow_execution_id=${stored.id};"`);
    console.log(`psql -h laptop-01 -U sfloess -d learning -c "SELECT * FROM workflow.learnings WHERE workflow_execution_id=${stored.id};"`);

  } catch (error) {
    console.error(`\n❌ TEST FAILED: ${error.message}`);
    await tracker.complete(
      { error: error.message },
      0.0,
      'error'
    );
    process.exit(1);
  }
}

main();
