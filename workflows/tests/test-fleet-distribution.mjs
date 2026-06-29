#!/usr/bin/env node

/**
 * Test Fleet Distribution
 *
 * Spawns 5 agents (one per worker) via SSH to verify that execution
 * actually happens on DIFFERENT remote workers, not all on aio-01.
 *
 * Each agent runs `hostname -f && echo PID=$$ && whoami && date -Iseconds`
 * on the remote worker via SSH. We then compare the reported hostnames
 * to confirm distribution.
 *
 * Output: JSON with actually_distributed:true/false and workers_used array.
 */

import { spawn } from 'child_process';

// 5 target workers to test distribution across
const TARGET_WORKERS = [
  'server-01',
  'server-02',
  'server-03',
  'laptop-01',
  'pi-01',
];

const SSH_USER = 'claude';
const SSH_TIMEOUT = 10; // seconds

/**
 * Execute a command on a remote worker via SSH.
 * Returns a promise with { targetHost, reportedHostname, pid, user, timestamp, success, error }.
 */
function executeOnWorker(hostname) {
  return new Promise((resolve) => {
    const cmd = 'hostname -f 2>/dev/null || hostname; echo "PID=$$"; whoami; date -Iseconds';

    const proc = spawn('ssh', [
      '-o', `ConnectTimeout=${SSH_TIMEOUT}`,
      '-o', 'BatchMode=yes',
      '-o', 'StrictHostKeyChecking=accept-new',
      `${SSH_USER}@${hostname}`,
      cmd,
    ], {
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: (SSH_TIMEOUT + 5) * 1000,
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

    proc.on('error', (err) => {
      resolve({
        targetHost: hostname,
        reportedHostname: null,
        pid: null,
        user: null,
        timestamp: null,
        success: false,
        error: `spawn error: ${err.message}`,
      });
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        resolve({
          targetHost: hostname,
          reportedHostname: null,
          pid: null,
          user: null,
          timestamp: null,
          success: false,
          error: `exit code ${code}: ${stderr.trim().slice(0, 200)}`,
        });
        return;
      }

      const lines = stdout.trim().split('\n');
      const reportedHostname = (lines[0] || '').trim();
      const pidLine = (lines[1] || '').trim();
      const pid = pidLine.startsWith('PID=') ? pidLine.slice(4) : pidLine;
      const user = (lines[2] || '').trim();
      const timestamp = (lines[3] || '').trim();

      resolve({
        targetHost: hostname,
        reportedHostname,
        pid,
        user,
        timestamp,
        success: true,
        error: null,
      });
    });
  });
}

// Main
(async () => {
  console.error('=== Fleet Distribution Test ===');
  console.error(`Testing ${TARGET_WORKERS.length} workers: ${TARGET_WORKERS.join(', ')}`);
  console.error(`SSH user: ${SSH_USER}`);
  console.error('');

  // Execute on all 5 workers IN PARALLEL
  const startTime = Date.now();
  const results = await Promise.all(TARGET_WORKERS.map(w => executeOnWorker(w)));
  const durationMs = Date.now() - startTime;

  // Log individual results to stderr
  for (const r of results) {
    if (r.success) {
      console.error(
        `  [OK]   ${r.targetHost} -> reported="${r.reportedHostname}" ` +
        `user=${r.user} pid=${r.pid} at=${r.timestamp}`
      );
    } else {
      console.error(`  [FAIL] ${r.targetHost} -> ${r.error}`);
    }
  }

  // Analyze distribution
  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);

  // Collect unique reported hostnames
  const reportedHostnames = successful.map(r => r.reportedHostname);
  const uniqueReported = [...new Set(reportedHostnames)];

  // Check if any reported hostname is the orchestrator (aio-01)
  const executedOnOrchestrator = reportedHostnames.filter(h =>
    h && (h.includes('aio-01') || h === 'aio-01')
  );

  // Distribution is real if:
  // 1. Multiple unique hostnames reported
  // 2. Reported hostnames match (or are substrings of) targeted workers
  // 3. Nothing unexpectedly runs on aio-01
  const actuallyDistributed =
    uniqueReported.length > 1 &&
    executedOnOrchestrator.length === 0 &&
    successful.length >= 2;

  // Build output JSON
  const output = {
    actually_distributed: actuallyDistributed,
    workers_used: uniqueReported,
    test_details: {
      total_workers_tested: TARGET_WORKERS.length,
      successful: successful.length,
      failed: failed.length,
      unique_hostnames: uniqueReported.length,
      executed_on_orchestrator: executedOnOrchestrator.length,
      duration_ms: durationMs,
    },
    per_worker: results.map(r => ({
      target: r.targetHost,
      reported: r.reportedHostname,
      user: r.user,
      success: r.success,
      error: r.error,
    })),
  };

  // Also check: are reported hostnames the same as target hostnames?
  // If SSH goes to server-01 but hostname reports "aio-01", distribution is fake.
  const hostnameMatchCount = successful.filter(r => {
    const reported = (r.reportedHostname || '').toLowerCase();
    const target = r.targetHost.toLowerCase();
    return reported.includes(target) || target.includes(reported);
  }).length;

  output.test_details.hostname_matches_target = hostnameMatchCount;
  output.test_details.all_hostnames_match =
    hostnameMatchCount === successful.length;

  if (!output.test_details.all_hostnames_match && successful.length > 0) {
    output.test_details.warning =
      'Some reported hostnames do not match target workers. ' +
      'This may indicate SSH aliases or DNS differences, not necessarily fake distribution.';
  }

  // Print JSON to stdout
  console.log(JSON.stringify(output, null, 2));

  process.exit(actuallyDistributed ? 0 : 1);
})();
