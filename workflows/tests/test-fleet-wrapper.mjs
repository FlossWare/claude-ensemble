#!/usr/bin/env node

/**
 * Fleet Wrapper Test
 *
 * Tests the fleet-workflow-wrapper.mjs with 8 simple parallel tasks.
 * Verifies all workers respond and shows which host executed each task.
 *
 * Expected: All 8 workers (server-01/02/03, laptop-01, pi-01/02, desktop-ap, server-ap)
 * should execute exactly one task in round-robin fashion.
 *
 * Created: 2026-06-28
 */

import { createFleetWorkflow } from '../shared/fleet-workflow-wrapper.mjs';

export default async function({ args }) {
  const { agent, parallel, phase, complete, getExecutionStats } = createFleetWorkflow(
    'test-fleet-wrapper',
    'Test fleet distribution with hostname reporting',
    {
      enableFleet: true,
      enableStorage: false,  // Don't pollute DB with test data
      timeout: 30000,        // 30s timeout
      maxRetries: 1          // Single retry
    }
  );

  console.log('\n🧪 Testing Fleet Wrapper with 8 Parallel Tasks\n');

  // Phase 1: Simple hostname reporting
  const results = await phase('hostname-test', async () => {
    const tasks = [];

    // Create 8 tasks - one per worker
    for (let i = 1; i <= 8; i++) {
      tasks.push({
        prompt: `Task ${i}: Echo your hostname. Respond with ONLY the output of: echo "Worker ${i}: $(hostname)"`,
        model: 'claude-sonnet-4',
        type: 'hostname-test'
      });
    }

    console.log('Executing 8 tasks in parallel across fleet...\n');

    const taskResults = await parallel(tasks);

    return taskResults;
  });

  // Show results
  console.log('\n📊 RESULTS:\n');
  results.forEach((result, i) => {
    if (result) {
      console.log(`  Task ${i + 1}: ${result.trim()}`);
    } else {
      console.log(`  Task ${i + 1}: ❌ FAILED`);
    }
  });

  // Show distribution stats
  const stats = getExecutionStats();
  console.log('\n📈 DISTRIBUTION STATS:\n');

  const hosts = Object.keys(stats).sort();

  if (hosts.length === 0) {
    console.log('  ⚠️  No execution stats available (fleet may be disabled)');
  } else {
    console.log(`  Total hosts used: ${hosts.length}`);
    console.log(`  Expected: 8 workers\n`);

    for (const host of hosts) {
      const s = stats[host];
      console.log(`  ${host}:`);
      console.log(`    Total tasks: ${s.total}`);
      console.log(`    Success: ${s.success} (${(s.successRate * 100).toFixed(1)}%)`);
      console.log(`    Avg duration: ${s.avgDuration.toFixed(0)}ms`);
    }
  }

  // Summary
  const successCount = results.filter(r => r !== null).length;
  const successRate = (successCount / results.length * 100).toFixed(1);

  console.log('\n📋 SUMMARY:');
  console.log(`  Tasks: ${results.length}`);
  console.log(`  Success: ${successCount} (${successRate}%)`);
  console.log(`  Failed: ${results.length - successCount}`);
  console.log(`  Hosts used: ${hosts.length}/8`);

  // Verify all 8 workers responded
  if (hosts.length === 8 && successCount === 8) {
    console.log('\n✅ TEST PASSED: All 8 workers responded successfully\n');
  } else if (hosts.length < 8) {
    console.log(`\n⚠️  TEST WARNING: Only ${hosts.length}/8 workers responded\n`);
  } else if (successCount < 8) {
    console.log(`\n⚠️  TEST WARNING: Only ${successCount}/8 tasks succeeded\n`);
  }

  return await complete(
    {
      results,
      stats,
      summary: {
        total: results.length,
        success: successCount,
        failed: results.length - successCount,
        hostsUsed: hosts.length
      }
    },
    successRate / 100,
    successCount === 8 ? 'success' : 'partial'
  );
}
