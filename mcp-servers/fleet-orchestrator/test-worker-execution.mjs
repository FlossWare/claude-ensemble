#!/usr/bin/env node

import { executeOnModel } from '../../shared/fleet-orchestrator-integrated.js';
import { execSync } from 'child_process';

console.log('=== TEST 1: Single worker execution ===');
console.log('Target: pi-02');

// Check before
console.log('\nProcesses BEFORE:');
try {
  const before = execSync('ssh claude@pi-02 "ps aux | grep -E \'node.*execute-task\' | grep -v grep"', { encoding: 'utf8' });
  console.log(before || '  (none)');
} catch (e) {
  console.log('  (none)');
}

// Execute task
console.log('\nExecuting task...');
const start = Date.now();
const result = await executeOnModel(
  'sonnet-4',
  'Return JSON with hostname and current timestamp',
  'pi-02'
);

const duration = Date.now() - start;
console.log(`\nResult (${duration}ms):`);
console.log(JSON.stringify(result, null, 2));

// Check after
console.log('\nProcesses AFTER:');
try {
  const after = execSync('ssh claude@pi-02 "ps aux | grep -E \'node.*execute-task\' | grep -v grep"', { encoding: 'utf8' });
  console.log(after || '  (none)');
} catch (e) {
  console.log('  (none)');
}

console.log('\n=== TEST 2: Round-robin distribution ===');

const tasks = [];
for (let i = 0; i < 8; i++) {
  tasks.push(
    executeOnModel(
      'haiku-4',
      `Task ${i + 1}: Return JSON with task_id=${i + 1} and execution_host`,
      'auto'
    )
  );
}

console.log('Executing 8 tasks with worker=auto...');
const results = await Promise.all(tasks);

const distribution = {};
for (const r of results) {
  const host = r.execution_host || 'unknown';
  distribution[host] = (distribution[host] || 0) + 1;
}

console.log('\nDistribution:');
for (const [host, count] of Object.entries(distribution).sort()) {
  console.log(`  ${host}: ${count} tasks`);
}

console.log('\n=== TEST 3: Network traffic verification ===');
console.log('Testing API call origin...');

// Execute on specific worker and check metadata
const apiTest = await executeOnModel(
  'opus-4',
  'Return JSON with message="API test from worker"',
  'desktop-ap'
);

console.log('\nAPI test result:');
console.log(JSON.stringify(apiTest, null, 2));

// Summary
console.log('\n=== VERIFICATION SUMMARY ===');
console.log(`Test 1 - Single worker: ${result.execution_host === 'pi-02' ? 'PASS' : 'FAIL'}`);
console.log(`Test 2 - Distribution: ${Object.keys(distribution).length >= 4 ? 'PASS (spread across ' + Object.keys(distribution).length + ' workers)' : 'FAIL (only ' + Object.keys(distribution).length + ' workers used)'}`);
console.log(`Test 3 - API origin: ${apiTest.execution_host === 'desktop-ap' ? 'PASS' : 'FAIL'}`);

const grade = (
  result.execution_host === 'pi-02' &&
  Object.keys(distribution).length >= 4 &&
  apiTest.execution_host === 'desktop-ap'
) ? 'A' : 'C';

const report = {
  workers_actually_execute: result.execution_host === 'pi-02',
  distribution_confirmed: Object.keys(distribution).length >= 4,
  evidence: {
    single_worker_test: {
      target: 'pi-02',
      actual: result.execution_host,
      duration_ms: duration
    },
    round_robin_test: {
      tasks: 8,
      workers_used: Object.keys(distribution).length,
      distribution
    },
    api_origin_test: {
      target: 'desktop-ap',
      actual: apiTest.execution_host
    }
  },
  grade
};

console.log('\n=== FINAL REPORT ===');
console.log(JSON.stringify(report, null, 2));

process.exit(grade === 'A' ? 0 : 1);
