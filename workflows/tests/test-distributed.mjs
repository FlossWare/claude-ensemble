#!/usr/bin/env node

/**
 * Test Distributed Execution
 *
 * Uses fleet-utils to execute commands on 3 different workers.
 * Verifies distributed execution via hostname tracking.
 * Returns JSON with works:true/false.
 */

import { writeFileSync, readFileSync } from 'fs';
import { join } from 'path';
import { getWorkers, remoteExec } from '../shared/fleet-utils.js';

const TEST_ID = `dist_test_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
const RESULTS_FILE = join('/tmp', `${TEST_ID}.json`);

const testResults = {
  test_id: TEST_ID,
  started: new Date().toISOString(),
  workers: [],
  executions: [],
  works: false,
  errors: []
};

function saveResults() {
  writeFileSync(RESULTS_FILE, JSON.stringify(testResults, null, 2));
}

// Simple command to get worker info
const WORKER_COMMAND = 'hostname && echo "PID: $$" && date -Iseconds';

async function executeOnWorker(worker, id) {
  try {
    const result = remoteExec(worker.hostname, WORKER_COMMAND, {
      timeout: 10000
    });

    return {
      worker_id: id,
      hostname: worker.hostname,
      success: result.success,
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: result.exitCode
    };
  } catch (err) {
    return {
      worker_id: id,
      hostname: worker.hostname,
      success: false,
      error: err.message
    };
  }
}

async function main() {
  console.log(`Starting distributed execution test: ${TEST_ID}`);

  try {
    // Get available workers
    console.log('Discovering workers...');
    const workers = getWorkers({ roles: ['worker'] });

    if (workers.length === 0) {
      throw new Error('No workers available');
    }

    testResults.workers = workers.map(w => ({
      hostname: w.hostname,
      roles: w.roles,
      architecture: w.architecture
    }));

    console.log(`Found ${workers.length} workers`);

    // Select 3 workers (or all if fewer than 3)
    const selectedWorkers = workers.slice(0, 3);
    console.log(`Testing with ${selectedWorkers.length} workers: ${selectedWorkers.map(w => w.hostname).join(', ')}`);

    // Execute on workers in parallel
    console.log('Executing on workers...');
    const executionPromises = selectedWorkers.map((worker, idx) =>
      executeOnWorker(worker, idx + 1)
    );

    const results = await Promise.allSettled(executionPromises);

    // Collect execution results
    results.forEach((result, idx) => {
      if (result.status === 'fulfilled') {
        testResults.executions.push(result.value);
      } else {
        testResults.executions.push({
          worker_id: idx + 1,
          hostname: selectedWorkers[idx].hostname,
          success: false,
          error: result.reason.message
        });
        testResults.errors.push(`Worker ${idx + 1}: ${result.reason.message}`);
      }
    });

    // Analyze results
    const successful = testResults.executions.filter(e => e.success);
    const uniqueHosts = new Set(
      successful
        .map(e => e.stdout.split('\n')[0].trim())
        .filter(h => h)
    );

    testResults.unique_hosts = Array.from(uniqueHosts);
    testResults.total_executions = testResults.executions.length;
    testResults.successful_executions = successful.length;

    // Determine if distributed execution works
    const multipleHosts = uniqueHosts.size > 1;
    const allSuccessful = successful.length === selectedWorkers.length;

    testResults.works = multipleHosts && allSuccessful;
    testResults.reason = multipleHosts
      ? `Success: ${uniqueHosts.size} unique hosts executed successfully`
      : allSuccessful
        ? 'Partial: All executions succeeded but on same host (check fleet config)'
        : `Failed: Only ${successful.length}/${selectedWorkers.length} executions succeeded`;

    testResults.completed = new Date().toISOString();

  } catch (err) {
    testResults.errors.push(`Main error: ${err.message}`);
    testResults.works = false;
    testResults.reason = `Error: ${err.message}`;
  }

  // Save final results
  saveResults();

  // Output JSON result
  const output = {
    works: testResults.works,
    unique_hosts: testResults.unique_hosts || [],
    successful_executions: testResults.successful_executions || 0,
    total_executions: testResults.total_executions || 0,
    reason: testResults.reason,
    details_file: RESULTS_FILE
  };

  console.log(JSON.stringify(output, null, 2));

  process.exit(testResults.works ? 0 : 1);
}

main().catch(err => {
  testResults.errors.push(`Fatal: ${err.message}`);
  testResults.works = false;
  testResults.reason = `Fatal error: ${err.message}`;
  saveResults();
  console.error(JSON.stringify({ works: false, error: err.message }));
  process.exit(1);
});
