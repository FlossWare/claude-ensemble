// Demo: Workflow Phase Tracking
// Shows how to wire in PostgreSQL phase tracking to any workflow

import { PhaseTracker } from '../shared/phase-tracker.js';

export const meta = {
  name: 'demo-phase-tracking',
  description: 'Demonstration of automatic phase tracking to PostgreSQL',
  whenToUse: 'Demo/test workflow for Issue #250',
  phases: [
    { title: 'Setup', detail: 'Initialize phase tracker' },
    { title: 'Work Phase 1', detail: 'Do some work' },
    { title: 'Work Phase 2', detail: 'Do more work' },
    { title: 'Completion', detail: 'Finalize and store' },
  ],
};

export default async function({ args, phase, log, agent }) {

  // === PHASE TRACKING INTEGRATION ===
  // Step 1: Create tracker instance
  const tracker = new PhaseTracker(
    'demo-phase-tracking',
    `Demo run: ${new Date().toISOString()}`,
    { enableStorage: true }
  );

  // Step 2: Initialize (creates workflow.executions record)
  await tracker.init();

  // Step 3: Wrap the original phase() function
  const trackedPhase = tracker.createPhaseWrapper(phase);

  // === END PHASE TRACKING INTEGRATION ===


  // Now use trackedPhase() instead of phase()
  // It automatically tracks timing and stores to PostgreSQL

  trackedPhase('Setup');
  log('Setting up demo workflow...');
  await new Promise(resolve => setTimeout(resolve, 500)); // Simulate work


  trackedPhase('Work Phase 1');
  log('Doing some work...');

  const result1 = await agent('What is 2+2?', {
    label: 'Simple Math',
    model: 'haiku',
    schema: {
      type: 'object',
      properties: {
        answer: { type: 'number' },
        reasoning: { type: 'string' }
      },
      required: ['answer']
    }
  });

  log(`Result 1: ${result1.answer} (${result1.reasoning || 'no reasoning'})`);


  trackedPhase('Work Phase 2');
  log('Doing more work...');

  const result2 = await agent('What is the capital of France?', {
    label: 'Simple Geography',
    model: 'haiku',
    schema: {
      type: 'object',
      properties: {
        answer: { type: 'string' },
        confidence: { type: 'number', minimum: 0, maximum: 100 }
      },
      required: ['answer']
    }
  });

  log(`Result 2: ${result2.answer} (${result2.confidence}% confident)`);


  trackedPhase('Completion');
  log('Finalizing workflow...');
  await new Promise(resolve => setTimeout(resolve, 300)); // Simulate finalization


  // Complete the workflow (updates workflow.executions record)
  await tracker.complete('success', {
    demo_results: {
      math: result1.answer,
      geography: result2.answer
    }
  });

  // Show statistics
  const stats = tracker.getStats();
  log('');
  log('='.repeat(60));
  log('📊 Phase Tracking Statistics');
  log('='.repeat(60));
  log(`Total phases: ${stats.total}`);
  log(`Completed: ${stats.completed}`);
  log(`Total duration: ${stats.totalDuration}ms`);
  log(`Avg phase duration: ${Math.round(stats.avgDuration)}ms`);
  log('');
  log('Per-phase breakdown:');
  stats.phases.forEach(p => {
    log(`  ${p.order + 1}. ${p.name}: ${p.durationMs}ms (${p.outcome || 'pending'})`);
  });
  log('='.repeat(60));
  log('');

  return {
    status: 'success',
    workflow_execution_id: tracker.workflowExecutionId,
    phases: stats.phases,
    total_duration_ms: stats.totalDuration
  };
}
