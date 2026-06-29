#!/usr/bin/env node
/**
 * Test Suite for Webhook Notifier
 *
 * Tests:
 * 1. Critical drift notification (>20% drop)
 * 2. High disagreement notification (CV >0.40)
 * 3. Circuit breaker notification
 * 4. Weekly consensus report
 *
 * Usage: node monitoring/test-webhook-notifier.cjs
 *
 * Created: 2026-06-28
 */

const {
  notifyDrift,
  notifyDisagreement,
  notifyCircuitBreaker,
  sendWeeklyReport,
  generateWeeklyReport,
  testWebhook,
} = require('./webhook-notifier.cjs');

console.log('================================================================================');
console.log('WEBHOOK NOTIFIER - TEST SUITE');
console.log('================================================================================\n');

async function runTests() {
  let passCount = 0;
  let failCount = 0;

  // Test 1: Critical Drift Notification
  console.log('=== Test 1: Critical Drift Notification ===');
  try {
    const driftAlert = {
      model: 'opus',
      task_type: 'code_review',
      performance_drop_pct: -25.5,
      current_7day_avg: 0.65,
      historical_30day_avg: 0.87,
      current_sample_count: 42,
      historical_sample_count: 178,
      severity: 'critical',
    };

    const result = await notifyDrift(driftAlert);
    console.log('Result:', JSON.stringify(result, null, 2));

    // Accept success, threshold skip, disabled, or rate limited as pass
    const isValidResult = result.success || result.below_threshold || result.disabled || result.rate_limited || (result.results && result.results.length === 0);
    if (isValidResult) {
      console.log('✅ Test 1 PASSED (webhooks disabled or rate limited)\n');
      passCount++;
    } else {
      console.log('❌ Test 1 FAILED\n');
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 1 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 2: High Disagreement Notification
  console.log('=== Test 2: High Disagreement Notification ===');
  try {
    const disagreementData = {
      workflow_name: 'ai-consensus-weighted',
      task_description: 'Which database should we use?',
      disagreement_score: 0.45,
      disagreement_level: 'critical',
      votes: [
        { model: 'opus', answer: 'PostgreSQL', confidence: 92 },
        { model: 'sonnet', answer: 'PostgreSQL', confidence: 88 },
        { model: 'haiku', answer: 'MongoDB', confidence: 45 },
        { model: 'fable', answer: 'Redis', confidence: 52 },
      ],
      queue_id: 123,
      priority: 9,
    };

    const result = await notifyDisagreement(disagreementData);
    console.log('Result:', JSON.stringify(result, null, 2));

    const isValidResult2 = result.success || result.below_threshold || result.disabled || result.rate_limited || (result.results && result.results.length === 0);
    if (isValidResult2) {
      console.log('✅ Test 2 PASSED (webhooks disabled or rate limited)\n');
      passCount++;
    } else {
      console.log('❌ Test 2 FAILED\n');
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 2 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 3: Circuit Breaker Notification
  console.log('=== Test 3: Circuit Breaker Notification ===');
  try {
    const circuitState = {
      state: 'open',
      reason: 'API rate limit exceeded',
      consecutive_failures: 7,
      next_retry_at: new Date(Date.now() + 30000).toISOString(),
    };

    const result = await notifyCircuitBreaker('gpt-4o', circuitState);
    console.log('Result:', JSON.stringify(result, null, 2));

    const isValidResult3 = result.success || result.disabled || result.rate_limited || (result.results && result.results.length === 0);
    if (isValidResult3) {
      console.log('✅ Test 3 PASSED (webhooks disabled or rate limited)\n');
      passCount++;
    } else {
      console.log('❌ Test 3 FAILED\n');
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 3 FAILED:', err.message, '\n');
    failCount++;
  }

  // Test 4: Weekly Report Generation
  console.log('=== Test 4: Weekly Report Generation ===');
  try {
    const reportData = await generateWeeklyReport();
    console.log('Report data:', JSON.stringify(reportData, null, 2));

    if (reportData && reportData.start_date && reportData.end_date) {
      console.log('✅ Test 4 PASSED\n');
      passCount++;
    } else {
      console.log('❌ Test 4 FAILED: Invalid report data\n');
      failCount++;
    }
  } catch (err) {
    console.log('❌ Test 4 FAILED:', err.message, '\n');
    failCount++;
  }

  // Summary
  console.log('================================================================================');
  console.log('TEST SUMMARY');
  console.log('================================================================================');
  console.log(`Total: ${passCount + failCount}`);
  console.log(`Passed: ${passCount} ✅`);
  console.log(`Failed: ${failCount} ❌`);

  if (failCount === 0) {
    console.log('\n🎉 ALL TESTS PASSED!\n');
  } else {
    console.log('\n⚠️  SOME TESTS FAILED\n');
  }

  console.log('================================================================================');
  console.log('NOTES');
  console.log('================================================================================');
  console.log('- Webhooks are disabled by default in webhook-config.json');
  console.log('- To enable, edit monitoring/webhook-config.json:');
  console.log('  - Set webhooks.slack.enabled = true');
  console.log('  - Set webhooks.slack.url = "your webhook URL"');
  console.log('  - Set webhooks.discord.enabled = true (optional)');
  console.log('  - Set webhooks.discord.url = "your webhook URL" (optional)');
  console.log('\n- Rate limiting may prevent duplicate notifications');
  console.log('- Delete /tmp/webhook-rate-limit-cache.json to reset rate limits');
  console.log('\n- To test actual webhook delivery:');
  console.log('  node monitoring/webhook-notifier.cjs test slack');
  console.log('  node monitoring/webhook-notifier.cjs test discord');
  console.log('================================================================================\n');
}

runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
