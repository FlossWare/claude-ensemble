#!/usr/bin/env node

/**
 * Simple Fleet Test - Direct SSH execution
 *
 * Tests fleet distribution by directly SSH'ing to each worker
 * and running a simple hostname command.
 *
 * Created: 2026-06-28
 */

import { execSync } from 'child_process';

const WORKERS = [
  'server-01',
  'server-02',
  'server-03',
  'laptop-01',
  'pi-01',
  'pi-02',
  'desktop-ap',
  'server-ap'
];

console.log('\n🧪 Testing Fleet SSH Access\n');
console.log(`Testing ${WORKERS.length} workers...\n`);

const results = [];

for (const worker of WORKERS) {
  const taskNum = WORKERS.indexOf(worker) + 1;
  try {
    // Use single quotes to prevent local shell expansion of $(hostname)
    const cmd = `ssh -o ConnectTimeout=5 claude@${worker} 'echo "Worker ${taskNum}: $(hostname)"' 2>&1`;
    const output = execSync(cmd, { encoding: 'utf8', timeout: 10000 });
    results.push({ worker, success: true, output: output.trim() });
    console.log(`✅ ${worker}: ${output.trim()}`);
  } catch (error) {
    results.push({ worker, success: false, error: error.message });
    console.log(`❌ ${worker}: ${error.message}`);
  }
}

console.log('\n📊 SUMMARY:\n');
const successCount = results.filter(r => r.success).length;
console.log(`  Total workers: ${WORKERS.length}`);
console.log(`  Successful: ${successCount}`);
console.log(`  Failed: ${WORKERS.length - successCount}`);
console.log(`  Success rate: ${(successCount / WORKERS.length * 100).toFixed(1)}%`);

if (successCount === WORKERS.length) {
  console.log('\n✅ TEST PASSED: All workers accessible via SSH\n');
} else {
  console.log('\n⚠️  TEST WARNING: Some workers unreachable\n');
  console.log('Failed workers:');
  results.filter(r => !r.success).forEach(r => {
    console.log(`  - ${r.worker}: ${r.error}`);
  });
}

// Show distribution
console.log('\n📈 DISTRIBUTION:\n');
results.forEach((r, i) => {
  if (r.success) {
    console.log(`  Task ${i + 1} → ${r.worker}: ${r.output}`);
  }
});

console.log('');
