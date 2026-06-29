#!/usr/bin/env node

/**
 * Debug Fleet SSH - Show what commands are actually being executed
 */

import { execSync } from 'child_process';

const WORKERS = ['server-01', 'server-02', 'laptop-01'];

console.log('\n🔍 Debugging SSH Commands\n');

for (const worker of WORKERS) {
  const taskNum = WORKERS.indexOf(worker) + 1;

  // Method 1: Single quotes around whole command
  const cmd1 = `ssh -o ConnectTimeout=5 claude@${worker} "echo 'Worker ${taskNum}: $(hostname)'"`;
  console.log(`\nCommand 1 (double quotes): ${cmd1}`);

  try {
    const output1 = execSync(cmd1, { encoding: 'utf8' });
    console.log(`  Output: ${output1.trim()}`);
  } catch (error) {
    console.log(`  Error: ${error.message}`);
  }

  // Method 2: Escape the command differently
  const cmd2 = `ssh -o ConnectTimeout=5 claude@${worker} 'echo "Worker ${taskNum}: \\$(hostname)"'`;
  console.log(`\nCommand 2 (single quotes + escaped $): ${cmd2}`);

  try {
    const output2 = execSync(cmd2, { encoding: 'utf8' });
    console.log(`  Output: ${output2.trim()}`);
  } catch (error) {
    console.log(`  Error: ${error.message}`);
  }

  // Method 3: Simple hostname
  const cmd3 = `ssh -o ConnectTimeout=5 claude@${worker} hostname`;
  console.log(`\nCommand 3 (simple hostname): ${cmd3}`);

  try {
    const output3 = execSync(cmd3, { encoding: 'utf8' });
    console.log(`  Output: ${output3.trim()}`);
  } catch (error) {
    console.log(`  Error: ${error.message}`);
  }
}

console.log('');
