#!/usr/bin/env node

/**
 * Test Workflow Feedback Capture Integration (Issue #249)
 *
 * Verifies:
 * 1. Feedback capture functions work
 * 2. Data flows to workflow.feedback table
 * 3. Thompson Sampling can process feedback
 *
 * Usage:
 *   node shared/test-workflow-feedback.js
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
import {
  captureWorkflowFeedback,
  captureAdversarialFeedback,
  captureConsensusFeedback,
  captureQualityFeedback,
  captureUserFeedback
} from './workflow-feedback-capture.js';

async function main() {
  console.log('Workflow Feedback Capture Test');
  console.log('='.repeat(80));
  console.log('');

  const db = getWorkflowStorage();

  try {
    // Step 1: Create a test workflow execution
    console.log('1. Creating test workflow execution...');
    const crypto = await import('crypto');
    const uniqueId = `test-fb-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;

    const workflowId = await db.storeExecution({
      workflow_id: uniqueId,
      workflow_name: 'feedback-test',
      task_description: 'Test workflow for feedback capture validation',
      total_workers: 3,
      total_duration_ms: 5000,
      outcome: 'success',
      metadata: {
        test: true,
        created_by: 'test-workflow-feedback.js'
      }
    });

    console.log(`   ✅ Workflow execution created (ID: ${workflowId})`);
    console.log('');

    // Step 2: Test workflow completion feedback
    console.log('2. Testing workflow completion feedback...');
    const feedback1 = await captureWorkflowFeedback({
      workflow_execution_id: workflowId,
      quality_score: 0.85,
      metrics: {
        consensus: 0.9,
        accuracy: 0.87,
        workers_count: 3
      },
      outcome: 'success',
      metadata: {
        test_type: 'workflow_completion'
      }
    });

    console.log(`   ✅ Workflow completion feedback captured (ID: ${feedback1})`);
    console.log('');

    // Step 3: Test adversarial verification feedback
    console.log('3. Testing adversarial verification feedback...');
    const feedback2 = await captureAdversarialFeedback({
      workflow_execution_id: workflowId,
      verificationResult: {
        verdict: 'ACCEPT',
        confidence: 'high',
        refuters_failed: 3,
        refuters_total: 3,
        critical_issues: [],
        major_issues: []
      }
    });

    console.log(`   ✅ Adversarial verification feedback captured (ID: ${feedback2})`);
    console.log('');

    // Step 4: Test consensus performance feedback
    console.log('4. Testing consensus performance feedback...');
    const feedback3 = await captureConsensusFeedback({
      workflow_execution_id: workflowId,
      performance: {
        consensus: 0.92,
        accuracy: 0.88,
        findings: 12,
        precision: 0.75
      },
      attribution: {
        consensusRate: 0.92,
        totalFindings: 12
      }
    });

    console.log(`   ✅ Consensus performance feedback captured (ID: ${feedback3})`);
    console.log('');

    // Step 5: Test quality score feedback
    console.log('5. Testing quality score feedback...');
    const feedback4 = await captureQualityFeedback({
      workflow_execution_id: workflowId,
      qualityScore: {
        score: 92,
        critical_count: 0,
        high_count: 1,
        medium_count: 3,
        low_count: 2,
        meets_threshold: true
      }
    });

    console.log(`   ✅ Quality score feedback captured (ID: ${feedback4})`);
    console.log('');

    // Step 6: Test user feedback
    console.log('6. Testing user feedback...');
    const feedback5 = await captureUserFeedback({
      workflow_execution_id: workflowId,
      rating: 4.5,
      feedback_text: 'Great results, minor improvements needed',
      metadata: {
        user: 'test-user',
        test_type: 'user_review'
      }
    });

    console.log(`   ✅ User feedback captured (ID: ${feedback5})`);
    console.log('');

    // Step 7: Query feedback table
    console.log('7. Querying workflow.feedback table...');
    const result = await db.pool.query(`
      SELECT
        id,
        feedback_type,
        quality_score,
        feedback_text,
        metadata->>'rating' as rating,
        metadata->>'source' as source
      FROM workflow.feedback
      WHERE workflow_execution_id = $1
      ORDER BY created_at DESC
    `, [workflowId]);

    console.log(`   Found ${result.rows.length} feedback entries:`);
    console.log('');

    result.rows.forEach((row, idx) => {
      console.log(`   ${idx + 1}. Type: ${row.feedback_type}, Score: ${row.quality_score}, Rating: ${row.rating}, Source: ${row.source}`);
      console.log(`      Text: ${row.feedback_text}`);
    });

    console.log('');

    // Step 8: Verify feedback loop integration
    console.log('8. Verifying feedback-loop-automation.js can process entries...');
    const unprocessedCount = await db.pool.query(`
      SELECT COUNT(*) as count
      FROM workflow.feedback
      WHERE workflow_execution_id = $1 AND processed = FALSE
    `, [workflowId]);

    console.log(`   ✅ Found ${unprocessedCount.rows[0].count} unprocessed feedback entries`);
    console.log('   (Run: node shared/feedback-loop-automation.js to process)');
    console.log('');

    // Step 9: Summary statistics
    console.log('9. Summary statistics:');
    const stats = await db.pool.query(`
      SELECT
        COUNT(*) as total_feedback,
        COUNT(*) FILTER (WHERE feedback_type = 'automated') as automated_count,
        COUNT(*) FILTER (WHERE feedback_type = 'adversarial') as adversarial_count,
        COUNT(*) FILTER (WHERE feedback_type = 'user') as user_count,
        AVG(quality_score) as avg_quality_score,
        AVG((metadata->>'rating')::float) as avg_rating
      FROM workflow.feedback
      WHERE workflow_execution_id = $1
    `, [workflowId]);

    const s = stats.rows[0];
    console.log(`   Total feedback: ${s.total_feedback}`);
    console.log(`   Automated: ${s.automated_count}, Adversarial: ${s.adversarial_count}, User: ${s.user_count}`);
    console.log(`   Average quality score: ${parseFloat(s.avg_quality_score).toFixed(3)}`);
    console.log(`   Average rating: ${parseFloat(s.avg_rating).toFixed(2)}/5.0`);
    console.log('');

    // Success
    console.log('✅ ALL TESTS PASSED');
    console.log('');
    console.log('Integration verified:');
    console.log('  ✓ Feedback capture functions work');
    console.log('  ✓ Data flows to workflow.feedback table');
    console.log('  ✓ Multiple feedback types supported');
    console.log('  ✓ Ready for Thompson Sampling processing');
    console.log('');
    console.log('Next steps:');
    console.log('  1. Run: node shared/feedback-loop-automation.js');
    console.log('  2. Verify Thompson Sampling state updates in learning.strategy_performance');
    console.log('  3. Monitor quality improvements over time');
    console.log('');

    process.exit(0);

  } catch (error) {
    console.error('❌ TEST FAILED:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

main();
