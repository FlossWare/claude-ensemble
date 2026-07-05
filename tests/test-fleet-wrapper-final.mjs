#!/usr/bin/env node

/**
 * Fleet Wrapper Final Test
 *
 * Tests fleet-workflow-wrapper.mjs with 8 parallel echo tasks
 * to verify distribution without requiring Claude CLI on workers.
 *
 * Created: 2026-06-28
 */

import { createFleetWorkflow, getGlobalExecutionStats } from './shared/fleet-workflow-wrapper.mjs';

export default async function({ args }) {
  const { agent, parallel, phase, complete, getExecutionStats } = createFleetWorkflow(
    'test-fleet-wrapper-final',
    'Test fleet distribution with echo commands',
    {
      enableFleet: true,
      enableStorage: false,  // Don't pollute DB
      timeout: 60000,
      maxRetries: 1
    }
  );

  console.log('\n🧪 Testing Fleet Wrapper Distribution\n');

  // Test 1: Single agent execution
  console.log('Test 1: Single agent execution');
  const singleResult = await agent('Test single execution');
  console.log(`  Result: ${singleResult ? '✅ Success' : '❌ Failed'}`);

  // Test 2: Parallel execution across all 8 workers
  const results = await phase('parallel-test', async () => {
    const tasks = [];

    for (let i = 1; i <= 8; i++) {
      tasks.push({
        prompt: `Task ${i}: Report worker info`,
        model: 'claude-sonnet-4',
        type: 'hostname-test'
      });
    }

    console.log('\nExecuting 8 tasks in parallel...\n');
    return await parallel(tasks);
  });

  // Show results
  console.log('\n📊 RESULTS:\n');
  results.forEach((result, i) => {
    if (result) {
      const preview = result.substring(0, 100).replace(/\n/g, ' ');
      console.log(`  Task ${i + 1}: ✅ ${preview}...`);
    } else {
      console.log(`  Task ${i + 1}: ❌ FAILED`);
    }
  });

  // Show distribution stats
  const stats = getExecutionStats();
  console.log('\n📈 DISTRIBUTION STATS:\n');

  const hosts = Object.keys(stats).sort();

  if (hosts.length === 0) {
    console.log('  ⚠️  No execution stats available');
  } else {
    console.log(`  Hosts used: ${hosts.length}/8\n`);

    for (const host of hosts) {
      const s = stats[host];
      console.log(`  ${host}:`);
      console.log(`    Tasks: ${s.total}`);
      console.log(`    Success: ${s.success} (${(s.successRate * 100).toFixed(0)}%)`);
      console.log(`    Avg duration: ${s.avgDuration.toFixed(0)}ms`);
    }
  }

  // Global stats
  console.log('\n🌐 GLOBAL STATS:');
  const globalStats = getGlobalExecutionStats();
  const globalHosts = Object.keys(globalStats).sort();

  for (const host of globalHosts) {
    const s = globalStats[host];
    console.log(`  ${host}: ${s.total} total, ${s.success} success (${(s.successRate * 100).toFixed(0)}%)`);
  }

  // Summary
  const successCount = results.filter(r => r !== null).length;
  const successRate = (successCount / results.length * 100).toFixed(1);

  console.log('\n📋 SUMMARY:');
  console.log(`  Tasks: ${results.length}`);
  console.log(`  Success: ${successCount} (${successRate}%)`);
  console.log(`  Failed: ${results.length - successCount}`);
  console.log(`  Hosts used: ${hosts.length}/8`);

  if (hosts.length === 8 && successCount >= 7) {
    console.log('\n✅ TEST PASSED: All workers accessible\n');
  } else if (hosts.length < 8) {
    console.log(`\n⚠️  TEST WARNING: Only ${hosts.length}/8 workers responded\n`);
  }

  return await complete(
    {
      results,
      stats,
      globalStats,
      summary: {
        total: results.length,
        success: successCount,
        failed: results.length - successCount,
        hostsUsed: hosts.length
      }
    },
    successRate / 100,
    successCount >= 7 ? 'success' : 'partial'
  );
}

// CLI invocation support
if (import.meta.url === `file://${process.argv[1]}`) {
  const result = await import.meta.url({ args: {} });
  console.log('\nFinal Result:', JSON.stringify(result, null, 2));
}
