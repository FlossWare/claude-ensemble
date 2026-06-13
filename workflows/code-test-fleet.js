// Code Test Fleet - Distributed test execution via file sharding
//
// Pattern A: Test File Sharding
//   1. Discover test files (jest, pytest, junit, cargo, go, etc.)
//   2. Split into N chunks (round-robin by file)
//   3. Distribute: remoteExec(worker, 'cd <project> && <test-runner> <files>')
//   4. Collect: test results (pass/fail/skip counts + failure details) from each worker
//   5. Merge: Unified test report with aggregated counts
//   6. Graceful fallback: If fleet unavailable, run all tests locally
//
// Speedup: 2.5-3x with 3 workers (test execution is embarrassingly parallel)

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'code-test-fleet',
  description: 'Fleet-distributed test execution - shards test files across workers for 2.5-3x speedup',
  whenToUse: 'When running tests on a project with many test files and fleet is available',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'Detect Test Setup', detail: 'Identify test runner and test files' },
    { title: 'Build Application', detail: 'Build before testing (fail fast)' },
    { title: 'Distribute Tests', detail: 'Shard test files across workers' },
    { title: 'Execute Tests', detail: 'Run tests in parallel on fleet' },
    { title: 'Merge Results', detail: 'Collect and merge test reports' },
    { title: 'Multi-AI Review', detail: 'Consensus review of failures' },
  ],
};

import { getWorkers, remoteExec } from '../shared/fleet-utils.js';
import {
  distributeItems,
  mergeTestResults,
  gracefulFallback,
  nfsProjectPath,
  isOnNfs,
  workerTempDir,
  getFleetSummary,
} from '../shared/fleet-workflow-patterns.js';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const MAX_RETRIES = 1;
const TEST_TIMEOUT_MS = args?.timeout || 300000;  // 5 min per worker
const DRY_RUN = args?.dryRun === true;

log('');
log('='.repeat(60));
log('Fleet-Distributed Test Execution');
log('='.repeat(60));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
if (DRY_RUN) log('DRY RUN: Will show distribution plan without executing');
log('');

// ============================================================================
// PHASE 1: Fleet Discovery
// ============================================================================

phase('Fleet Discovery');

let workers = [];
let useFleet = false;

try {
  workers = getWorkers({ capabilities: ['test'] });
  useFleet = workers.length >= 2;  // Need at least 2 workers for benefit

  if (useFleet) {
    log(`Fleet available: ${workers.length} workers`);
    workers.forEach(w => log(`  - ${w.hostname} (${w.cpus}C/${w.memory_gb}GB)`));
  } else if (workers.length === 1) {
    log('Only 1 worker available, running locally (no sharding benefit)');
  } else {
    log('No fleet workers available, running locally');
  }
} catch (error) {
  log(`Fleet unavailable (${error.message}), running locally`);
}

// Check NFS visibility
const projectDir = nfsProjectPath();
const nfsAvailable = isOnNfs(projectDir);

if (useFleet && !nfsAvailable) {
  log(`Project not on NFS (${projectDir}), falling back to local`);
  useFleet = false;
}

log('');

// ============================================================================
// PHASE 2: Detect Test Setup
// ============================================================================

phase('Detect Test Setup');

log('Analyzing test infrastructure...');

const testSetup = await _agent(`Detect the test setup for this project.

Execute these commands to gather information:
ls package.json setup.py setup.cfg pyproject.toml pom.xml build.gradle Cargo.toml go.mod Makefile 2>/dev/null
if [ -f package.json ]; then cat package.json | grep -A5 '"scripts"' | head -20; fi
if [ -f package.json ]; then cat package.json | grep -E '"jest|mocha|vitest|ava"' | head -5; fi

Find all test files:
find . -maxdepth 5 -type f \\( \
  -name "*.test.js" -o -name "*.spec.js" -o \
  -name "*.test.ts" -o -name "*.spec.ts" -o \
  -name "*.test.tsx" -o -name "*.spec.tsx" -o \
  -name "*.test.jsx" -o -name "*.spec.jsx" -o \
  -name "test_*.py" -o -name "*_test.py" -o \
  -name "*Test.java" -o -name "*_test.go" -o \
  -name "*_test.rs" \\) \
  -not -path "*/node_modules/*" \
  -not -path "*/.git/*" \
  -not -path "*/dist/*" \
  -not -path "*/build/*" \
  -not -path "*/target/*" \
  2>/dev/null | sort

Return structured test setup data.`, {
  label: 'Detect Tests',
  schema: {
    type: 'object',
    properties: {
      test_runner: {
        type: 'string',
        description: 'Test runner name: jest, pytest, junit, cargo-test, go-test, mocha, vitest, ava, make-test, unknown'
      },
      test_command: {
        type: 'string',
        description: 'Full command to run all tests (e.g., npx jest, pytest, mvn test)'
      },
      test_file_pattern: {
        type: 'string',
        description: 'Glob pattern for test files'
      },
      test_files: {
        type: 'array',
        items: { type: 'string' },
        description: 'List of discovered test file paths'
      },
      build_command: {
        type: 'string',
        description: 'Build command if needed before testing'
      },
      supports_file_args: {
        type: 'boolean',
        description: 'Can test runner accept specific file paths as arguments?'
      },
      parallel_safe: {
        type: 'boolean',
        description: 'Can tests run in parallel safely (no shared state)?'
      },
      language: { type: 'string' },
    },
    required: ['test_runner', 'test_command', 'test_files', 'supports_file_args']
  }
});

log(`Test runner: ${testSetup.test_runner}`);
log(`Test command: ${testSetup.test_command}`);
log(`Test files found: ${testSetup.test_files?.length || 0}`);
log(`Supports file args: ${testSetup.supports_file_args}`);
log(`Parallel safe: ${testSetup.parallel_safe}`);
log('');

if (!testSetup.test_files || testSetup.test_files.length === 0) {
  log('No test files found');
  return {
    status: 'no_tests',
    message: 'No test files discovered in project',
    test_runner: testSetup.test_runner,
  };
}

// Decide if fleet sharding is viable
const canShard = useFleet &&
  testSetup.supports_file_args &&
  testSetup.test_files.length >= workers.length &&
  testSetup.parallel_safe !== false;

if (useFleet && !canShard) {
  if (!testSetup.supports_file_args) {
    log('Test runner does not support file args, cannot shard');
  } else if (testSetup.test_files.length < workers.length) {
    log(`Too few test files (${testSetup.test_files.length}) for ${workers.length} workers`);
  } else if (testSetup.parallel_safe === false) {
    log('Tests not safe for parallel execution (shared state)');
  }
  useFleet = false;
}

// ============================================================================
// PHASE 3: Build Application
// ============================================================================

phase('Build Application');

if (testSetup.build_command && testSetup.build_command !== 'none') {
  log(`Building: ${testSetup.build_command}`);

  const buildResult = await _agent(`Build the application before testing.

Execute: ${testSetup.build_command}

Report success/failure with exit code and any errors.`, {
    label: 'Build',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['success', 'failure'] },
        errors: { type: 'array', items: { type: 'string' } },
      },
      required: ['status']
    }
  });

  if (buildResult.status === 'failure') {
    log('Build failed - cannot proceed with tests');
    return {
      status: 'build_failed',
      build_errors: buildResult.errors,
      message: 'Fix build errors before running tests',
    };
  }

  log('Build successful');
} else {
  log('No build step required');
}

log('');

// ============================================================================
// PHASE 4-5: Distribute and Execute Tests
// ============================================================================

if (useFleet && canShard) {
  // === FLEET EXECUTION PATH ===

  phase('Distribute Tests');

  const testFiles = testSetup.test_files;
  const distribution = distributeItems(testFiles, workers);

  log(`Sharding ${testFiles.length} test files across ${workers.length} workers:`);
  for (const [hostname, files] of distribution.entries()) {
    log(`  ${hostname}: ${files.length} files`);
    files.slice(0, 3).forEach(f => log(`    - ${f}`));
    if (files.length > 3) log(`    ... and ${files.length - 3} more`);
  }
  log('');

  if (DRY_RUN) {
    return {
      status: 'dry_run',
      distribution: Object.fromEntries(distribution),
      workers: workers.map(w => w.hostname),
      total_files: testFiles.length,
      message: 'Dry run complete - no tests executed',
    };
  }

  phase('Execute Tests');

  log('Executing tests on fleet workers...');

  // Build test commands per worker
  const buildTestCommand = (files) => {
    const fileList = files.join(' ');

    switch (testSetup.test_runner) {
      case 'jest':
      case 'vitest':
        return `cd '${projectDir}' && npx ${testSetup.test_runner} --forceExit --json ${fileList} 2>&1 || true`;
      case 'pytest':
        return `cd '${projectDir}' && python -m pytest --tb=short -q ${fileList} 2>&1 || true`;
      case 'go-test':
        return `cd '${projectDir}' && go test -v ${fileList} 2>&1 || true`;
      case 'cargo-test':
        return `cd '${projectDir}' && cargo test ${fileList} 2>&1 || true`;
      case 'mocha':
        return `cd '${projectDir}' && npx mocha ${fileList} 2>&1 || true`;
      default:
        // Generic: append files to test command
        return `cd '${projectDir}' && ${testSetup.test_command} ${fileList} 2>&1 || true`;
    }
  };

  // Execute on each worker via SSH
  const workerPromises = workers.map(async (worker) => {
    const files = distribution.get(worker.hostname);
    if (!files || files.length === 0) return null;

    const testCmd = buildTestCommand(files);

    log(`  Starting on ${worker.hostname} (${files.length} files)...`);

    let lastError = null;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      if (attempt > 0) {
        log(`  Retrying ${worker.hostname} (attempt ${attempt + 1})...`);
      }

      const result = remoteExec(worker.hostname, testCmd, {
        timeout: TEST_TIMEOUT_MS,
      });

      if (result.success || result.stdout) {
        log(`  ${worker.hostname}: execution complete (exit ${result.exitCode})`);

        // Parse test output into structured results
        return await _agent(`Parse test output from ${worker.hostname} and extract results.

Test runner: ${testSetup.test_runner}
Files tested: ${files.length}

Output:
${(result.stdout || '').slice(0, 5000)}

${result.stderr ? `Stderr:\n${result.stderr.slice(0, 2000)}` : ''}

Return structured test results with pass/fail/skip counts and failure details.`, {
          label: `Parse ${worker.hostname}`,
          schema: {
            type: 'object',
            properties: {
              hostname: { type: 'string' },
              total: { type: 'number' },
              passed: { type: 'number' },
              failed: { type: 'number' },
              skipped: { type: 'number' },
              failures: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    test_name: { type: 'string' },
                    file: { type: 'string' },
                    error: { type: 'string' },
                    status: { type: 'string' },
                  },
                },
              },
              raw_output_snippet: { type: 'string' },
            },
            required: ['hostname', 'total', 'passed', 'failed']
          }
        });
      }

      lastError = result.stderr || 'Unknown error';
    }

    log(`  ${worker.hostname}: FAILED after ${MAX_RETRIES + 1} attempts`);
    return {
      hostname: worker.hostname,
      total: 0,
      passed: 0,
      failed: 0,
      skipped: 0,
      error: lastError,
      failures: [],
    };
  });

  const workerResults = (await Promise.all(workerPromises)).filter(Boolean);

  // ============================================================================
  // PHASE 6: Merge Results
  // ============================================================================

  phase('Merge Results');

  const merged = mergeTestResults(workerResults);

  log('');
  log('Merged Test Results:');
  log(`  Total:   ${merged.total}`);
  log(`  Passed:  ${merged.passed}`);
  log(`  Failed:  ${merged.failed}`);
  log(`  Skipped: ${merged.skipped}`);
  log('');
  log('Per-Worker Breakdown:');
  merged.per_worker.forEach(w => {
    log(`  ${w.hostname}: ${w.passed} passed, ${w.failed} failed, ${w.skipped} skipped`);
  });

  // ============================================================================
  // PHASE 7: Multi-AI Review of Failures
  // ============================================================================

  if (merged.failed > 0) {
    phase('Multi-AI Review');

    log(`Reviewing ${merged.failed} test failures with multi-AI consensus...`);

    const failureDetails = merged.details
      .filter(d => d.status === 'fail')
      .slice(0, 10);  // Cap at 10 failures for review

    const reviewModels = ['opus', 'sonnet', 'haiku'];

    const reviews = await parallel(reviewModels.map(model => () =>
      agent(`Review these test failures and classify each:

${failureDetails.map((f, i) => `
Failure ${i + 1}: ${f.test_name || 'unknown'}
  File: ${f.file || 'unknown'}
  Error: ${f.error || 'no error message'}
`).join('\n')}

For each failure, determine:
1. Is this a real bug or a flaky/infrastructure issue?
2. Severity: critical, high, medium, low
3. Root cause hypothesis

Return classifications.`, {
        label: `Review (${model})`,
        model,
        schema: {
          type: 'object',
          properties: {
            classifications: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  index: { type: 'number' },
                  is_real_bug: { type: 'boolean' },
                  severity: { type: 'string' },
                  root_cause: { type: 'string' },
                },
              },
            },
          },
        }
      })
    ));

    const validReviews = reviews.filter(Boolean);
    log(`Multi-AI review: ${validReviews.length} models responded`);

    merged.ai_review = {
      models: reviewModels,
      reviews: validReviews,
    };
  }

  // Final summary
  log('');
  log('='.repeat(60));
  log('FLEET TEST EXECUTION COMPLETE');
  log('='.repeat(60));
  log(`Workers used: ${workerResults.length}`);
  log(`Total tests: ${merged.total}`);
  log(`Passed: ${merged.passed}, Failed: ${merged.failed}, Skipped: ${merged.skipped}`);
  log('='.repeat(60));

  return {
    status: merged.failed > 0 ? 'failures_found' : 'complete',
    fleet_used: true,
    workers_used: workerResults.length,
    test_runner: testSetup.test_runner,
    test_summary: {
      total: merged.total,
      passed: merged.passed,
      failed: merged.failed,
      skipped: merged.skipped,
    },
    per_worker: merged.per_worker,
    failures: merged.details.filter(d => d.status === 'fail'),
    ai_review: merged.ai_review || null,
  };

} else {
  // === LOCAL EXECUTION PATH ===

  phase('Execute Tests');

  log('Running tests locally (fleet not available or not suitable for sharding)...');

  const localResult = await workflow('code-test', {
    autonomous: AUTONOMOUS,
    ...args,
  });

  return {
    ...localResult,
    fleet_used: false,
    fleet_reason: !useFleet
      ? 'fleet_unavailable'
      : !canShard
        ? 'cannot_shard'
        : 'unknown',
  };
}
