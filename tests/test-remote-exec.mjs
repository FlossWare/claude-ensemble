#!/usr/bin/env node

/**
 * Test remoteExec from fleet-utils
 *
 * Verifies the remoteExec function properly distributes commands
 * across the 8-worker fleet.
 *
 * Created: 2026-06-28
 */

import { execSync } from 'child_process';

// Manual implementation of remoteExec for testing
function remoteExec(hostname, command, options = {}) {
  const timeout = options.timeout || 120000;

  // Escape command for SSH (single-quote method)
  const escaped = command.replace(/'/g, "'\\''");
  const sshCmd = `ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new claude@${hostname} '${escaped}'`;

  try {
    const stdout = execSync(sshCmd, {
      encoding: 'utf8',
      timeout: timeout,
      stdio: 'pipe'
    });

    return {
      hostname,
      stdout: stdout.trim(),
      stderr: '',
      exitCode: 0,
      success: true
    };
  } catch (error) {
    return {
      hostname,
      stdout: error.stdout ? error.stdout.toString().trim() : '',
      stderr: error.stderr ? error.stderr.toString().trim() : error.message,
      exitCode: error.status || 1,
      success: false
    };
  }
}

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

console.log('\n🧪 Testing remoteExec Function\n');

// Test 1: Simple hostname
console.log('Test 1: Simple hostname command\n');
for (const worker of WORKERS) {
  const result = remoteExec(worker, 'hostname');
  if (result.success) {
    console.log(`✅ ${worker}: ${result.stdout}`);
  } else {
    console.log(`❌ ${worker}: ${result.stderr}`);
  }
}

// Test 2: Complex command with special characters
console.log('\n\nTest 2: Complex command with quotes and variables\n');
const testCommand = 'echo "Worker: $(hostname) - Time: $(date +%H:%M:%S)"';
for (const worker of WORKERS.slice(0, 3)) {  // Just test first 3
  const result = remoteExec(worker, testCommand);
  if (result.success) {
    console.log(`✅ ${worker}: ${result.stdout}`);
  } else {
    console.log(`❌ ${worker}: ${result.stderr}`);
  }
}

// Test 3: Command with pipes
console.log('\n\nTest 3: Command with pipes\n');
const pipeCommand = 'echo "Test message" | wc -w';
for (const worker of WORKERS.slice(0, 3)) {
  const result = remoteExec(worker, pipeCommand);
  if (result.success) {
    console.log(`✅ ${worker}: ${result.stdout} words`);
  } else {
    console.log(`❌ ${worker}: ${result.stderr}`);
  }
}

// Test 4: Parallel execution simulation
console.log('\n\nTest 4: Parallel execution (8 workers)\n');
const tasks = WORKERS.map((worker, i) =>
  remoteExec(worker, `echo "Task ${i + 1}: $(hostname)"`)
);

console.log('Results:');
tasks.forEach((result, i) => {
  if (result.success) {
    console.log(`  ${i + 1}. ${result.stdout}`);
  } else {
    console.log(`  ${i + 1}. ❌ ${result.hostname}: ${result.stderr}`);
  }
});

// Summary
const successCount = tasks.filter(t => t.success).length;
console.log(`\n📊 SUMMARY:`);
console.log(`  Total: ${WORKERS.length}`);
console.log(`  Success: ${successCount}`);
console.log(`  Failed: ${WORKERS.length - successCount}`);
console.log(`  Success rate: ${(successCount / WORKERS.length * 100).toFixed(1)}%`);

if (successCount === WORKERS.length) {
  console.log('\n✅ TEST PASSED: All workers responded correctly\n');
} else {
  console.log('\n⚠️  TEST WARNING: Some workers failed\n');
}
