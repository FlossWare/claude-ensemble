// Code SDLC Fleet - Phase-level distributed SDLC automation
//
// Pattern C: Phase-Level Distribution
//
//   Phases 1-3: SEQUENTIAL with decision gates (must pass before continuing)
//     Phase 1: code-review + code-solve (Development)
//     Phase 2: code-test-fleet (Testing - uses fleet internally for test sharding)
//     Phase 3: code-pr-review (PR Review)
//
//   Decision Gate: If tests pass and no breaking changes, proceed
//
//   Phases 4-6: PARALLEL across fleet workers
//     server-01: code-security (or code-security-fleet)
//     server-02: code-doc
//     server-03: code-release-notes
//
//   Phase 7: Merge final SDLC report
//
// The key insight: phases 4-6 are independent and can run simultaneously.
// Phases 1-3 have data dependencies (review->solve->test) so must be sequential.
//
// Speedup: 2-2.5x overall (parallel phase block saves ~60% of phase 4-6 time)

export const meta = {
  name: 'code-sdlc-fleet',
  description: 'Fleet-distributed SDLC pipeline - parallelizes independent phases for 2-2.5x speedup',
  whenToUse: 'When running full SDLC pipeline and fleet is available',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover fleet and plan phase distribution' },
    { title: 'Development', detail: 'code-review + code-solve (sequential)' },
    { title: 'Testing', detail: 'code-test-fleet (fleet-aware test sharding)' },
    { title: 'PR Review', detail: 'code-pr-review (sequential)' },
    { title: 'Decision Gate', detail: 'Check if safe to proceed to parallel phases' },
    { title: 'Parallel Phases', detail: 'Security + Docs + Release in parallel' },
    { title: 'Summary', detail: 'Merge and report final SDLC results' },
  ],
};

import { getWorkers } from '../shared/fleet-utils.js';
import { parallelPhases } from '../shared/fleet-workflow-patterns.js';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const AUTO_CRITERIA = args?.AUTO_CRITERIA || {
  continue_on_breaking: false,
  continue_on_critical_vulns: false,
  continue_on_test_failures: false,
  max_issues_to_fix: 10,
  release_if_commits: false,
};

log('');
log('='.repeat(60));
log('Fleet-Distributed SDLC Pipeline');
log('='.repeat(60));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`Budget: ${budget.total ? `${Math.round(budget.total/1000)}k tokens` : 'unlimited'}`);
log('');

// Track results across all phases
const results = {
  development: null,
  testing: null,
  pr_review: null,
  security: null,
  documentation: null,
  release: null,
  phases_run: [],
  phases_skipped: [],
  breaking_changes: false,
  critical_issues: [],
  fleet_used: false,
  parallel_phases_used: false,
};

// ============================================================================
// PHASE 1: Fleet Discovery
// ============================================================================

phase('Fleet Discovery');

let workers = [];
let useFleet = false;

try {
  workers = getWorkers();
  useFleet = workers.length >= 2;

  if (useFleet) {
    log(`Fleet available: ${workers.length} workers`);
    workers.forEach(w => log(`  - ${w.hostname} (${w.cpus}C/${w.memory_gb}GB)`));
    log('');
    log('Phase distribution plan:');
    log('  Phases 1-3: Sequential (data dependencies)');
    log('    1. Development: code-review + code-solve');
    log('    2. Testing: code-test-fleet (fleet-sharded tests)');
    log('    3. PR Review: code-pr-review');
    log('  Decision Gate: Tests pass? No breaking changes?');
    log('  Phases 4-6: Parallel across fleet');

    if (workers.length >= 3) {
      log(`    ${workers[0].hostname}: code-security`);
      log(`    ${workers[1].hostname}: code-doc`);
      log(`    ${workers[2].hostname}: code-release-notes`);
    } else {
      log(`    ${workers[0].hostname}: code-security`);
      log(`    ${workers[1 % workers.length].hostname}: code-doc + code-release-notes`);
    }
  } else {
    log('Insufficient fleet workers, will run sequential pipeline');
  }
} catch (error) {
  log(`Fleet unavailable (${error.message}), will run sequential pipeline`);
}

results.fleet_used = useFleet;
log('');

// ============================================================================
// PHASE 2: DEVELOPMENT (Sequential - code-review + code-solve)
// ============================================================================

phase('Development');

log('');
log('='.repeat(50));
log('PHASE 1/6: DEVELOPMENT');
log('='.repeat(50));

if (budget.total && budget.remaining() < 50_000) {
  log('Insufficient budget for development phase');
  return { status: 'budget_exhausted', results };
}

log('Running code-review...');
const reviewResults = await workflow('code-review', { autonomous: AUTONOMOUS });
results.development = reviewResults;
results.phases_run.push('development');

log(`Review complete: ${reviewResults.issues_created || 0} issues created`);

let solveResults = null;
if (reviewResults.issues_created > 0) {
  if (budget.total && budget.remaining() < 100_000) {
    log('Insufficient budget for code-solve (skipping)');
  } else {
    log(`Running code-solve for ${reviewResults.issues_created} issues...`);
    solveResults = await workflow('code-solve', {
      autonomous: AUTONOMOUS,
      max_issues: AUTONOMOUS ? AUTO_CRITERIA.max_issues_to_fix : undefined,
    });
    results.development.solve_results = solveResults;
    log(`Solve complete: ${solveResults.solved || 0} issues fixed`);
  }
} else {
  log('No issues found, skipping code-solve');
}

// ============================================================================
// PHASE 3: TESTING (Fleet-aware - uses code-test-fleet for test sharding)
// ============================================================================

phase('Testing');

log('');
log('='.repeat(50));
log('PHASE 2/6: TESTING');
log('='.repeat(50));

const shouldTest = solveResults || AUTONOMOUS;

if (!shouldTest) {
  log('No fixes applied, skipping testing');
  results.phases_skipped.push('testing');
} else {
  if (budget.total && budget.remaining() < 80_000) {
    log('Insufficient budget for testing (skipping)');
    results.phases_skipped.push('testing');
  } else {
    log('Running tests (fleet-aware)...');

    // Use code-test-fleet if fleet is available, otherwise standard code-test
    const testWorkflow = useFleet ? 'code-test-fleet' : 'code-test';
    const testResults = await workflow(testWorkflow, { autonomous: AUTONOMOUS });
    results.testing = testResults;
    results.phases_run.push('testing');

    if (testResults.test_summary?.failed > 0) {
      results.critical_issues.push(`${testResults.test_summary.failed} test failures`);
      log(`${testResults.test_summary.failed} test failures detected!`);
    }

    log(`Testing complete: ${testResults.test_summary?.total || 0} tests run`);
    if (testResults.fleet_used) {
      log(`  (Fleet-sharded across ${testResults.workers_used || '?'} workers)`);
    }
  }
}

// ============================================================================
// PHASE 4: PR REVIEW (Sequential)
// ============================================================================

phase('PR Review');

log('');
log('='.repeat(50));
log('PHASE 3/6: PR REVIEW');
log('='.repeat(50));

const prCheck = await agent(`Check for open PRs/MRs.

Run: gh pr list --json number 2>/dev/null || glab mr list --json iid 2>/dev/null || echo "[]"

Return count of open PRs.`, {
  label: 'Check PRs',
  schema: {
    type: 'object',
    properties: {
      open_prs: { type: 'number' },
      platform: { type: 'string' },
    },
  },
});

if (prCheck.open_prs === 0) {
  log('No open PRs/MRs, skipping');
  results.phases_skipped.push('pr_review');
} else {
  if (budget.total && budget.remaining() < 100_000) {
    log('Insufficient budget for PR review (skipping)');
    results.phases_skipped.push('pr_review');
  } else {
    log(`Reviewing ${prCheck.open_prs} open PRs...`);
    const prResults = await workflow('code-pr-review', { autonomous: AUTONOMOUS });
    results.pr_review = prResults;
    results.phases_run.push('pr_review');

    if (prResults.breaking_changes > 0) {
      results.breaking_changes = true;
      log('BREAKING CHANGES detected in PRs!');
    }

    log(`PR Review complete: ${prResults.approved || 0} approved, ${prResults.rejected || 0} rejected`);
  }
}

// ============================================================================
// DECISION GATE: Proceed to parallel phases?
// ============================================================================

phase('Decision Gate');

log('');
log('='.repeat(50));
log('DECISION GATE');
log('='.repeat(50));

const shouldContinue =
  (AUTONOMOUS ? AUTO_CRITERIA.continue_on_breaking : !results.breaking_changes) &&
  results.critical_issues.length === 0 &&
  (budget.total ? budget.remaining() > 150_000 : true);

if (!shouldContinue) {
  log('STOPPING PIPELINE');
  if (results.breaking_changes) log('  Reason: Breaking changes');
  if (results.critical_issues.length > 0) log(`  Reason: ${results.critical_issues.length} critical issues`);
  if (budget.total && budget.remaining() < 150_000) log('  Reason: Insufficient budget');

  return {
    status: 'stopped_at_gate',
    reason: results.breaking_changes ? 'breaking_changes' : 'critical_issues',
    results,
  };
}

log('Gate PASSED - proceeding to parallel phases');
log('');

// ============================================================================
// PHASES 5-7: PARALLEL across fleet (Security, Docs, Release Notes)
// ============================================================================

phase('Parallel Phases');

log('');
log('='.repeat(50));
log('PHASES 4-6: PARALLEL EXECUTION');
log('='.repeat(50));

if (useFleet && workers.length >= 2) {
  // === FLEET PARALLEL EXECUTION ===

  results.parallel_phases_used = true;

  log('Running Security + Docs + Release Notes in PARALLEL on fleet...');
  log('');

  const phaseDefinitions = [
    {
      name: 'security',
      preferredWorker: workers[0]?.hostname,  // server-01
      fn: async (worker) => {
        log(`  Security scan starting on ${worker.hostname}...`);
        // Use fleet security if multiple workers available, otherwise regular
        const secWorkflow = workers.length >= 3 ? 'code-security-fleet' : 'code-security';
        const secResults = await workflow(secWorkflow, { autonomous: AUTONOMOUS });
        log(`  Security scan complete on ${worker.hostname}`);
        return secResults;
      },
    },
    {
      name: 'documentation',
      preferredWorker: workers[1 % workers.length]?.hostname,  // server-02
      fn: async (worker) => {
        log(`  Documentation starting on ${worker.hostname}...`);
        const docResults = await workflow('code-doc', { autonomous: AUTONOMOUS });
        log(`  Documentation complete on ${worker.hostname}`);
        return docResults;
      },
    },
    {
      name: 'release',
      preferredWorker: workers[2 % workers.length]?.hostname,  // server-03
      fn: async (worker) => {
        // Check if there are commits to release
        const commitCheck = await agent(`Check for unreleased commits.
Run: git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~10")..HEAD | wc -l
Return count.`, {
          label: 'Check Commits',
          schema: { type: 'object', properties: { unreleased_commits: { type: 'number' } } },
        });

        if (commitCheck.unreleased_commits === 0) {
          log(`  No unreleased commits, skipping release notes`);
          return { status: 'skipped', reason: 'no_commits' };
        }

        log(`  Release notes starting on ${worker.hostname}...`);
        const releaseResults = await workflow('code-release-notes', { autonomous: AUTONOMOUS });
        log(`  Release notes complete on ${worker.hostname}`);
        return releaseResults;
      },
    },
  ];

  // Check budget for each phase
  const budgetSufficientPhases = phaseDefinitions.filter(() => {
    if (!budget.total) return true;
    return budget.remaining() > 50_000;
  });

  if (budgetSufficientPhases.length < phaseDefinitions.length) {
    log(`Budget limits: running ${budgetSufficientPhases.length}/${phaseDefinitions.length} phases`);
  }

  const parallelResult = await parallelPhases({
    phases: budgetSufficientPhases,
    workers,
    log,
    timeout: 600000,  // 10 min per phase
  });

  // Collect results
  if (parallelResult.results.has('security')) {
    results.security = parallelResult.results.get('security');
    results.phases_run.push('security');

    if (results.security?.verified_findings > 0) {
      results.critical_issues.push(`${results.security.verified_findings} verified vulnerabilities`);
    }
  }

  if (parallelResult.results.has('documentation')) {
    results.documentation = parallelResult.results.get('documentation');
    results.phases_run.push('documentation');
  }

  if (parallelResult.results.has('release')) {
    const releaseResult = parallelResult.results.get('release');
    if (releaseResult?.status !== 'skipped') {
      results.release = releaseResult;
      results.phases_run.push('release');
    } else {
      results.phases_skipped.push('release');
    }
  }

  // Report phase errors
  if (parallelResult.errors.size > 0) {
    for (const [phaseName, error] of parallelResult.errors.entries()) {
      log(`  Phase "${phaseName}" failed: ${error}`);
      results.phases_skipped.push(phaseName);
    }
  }

  log('');
  log('Parallel phases complete');

} else {
  // === SEQUENTIAL EXECUTION (no fleet) ===

  log('Running Security, Docs, Release Notes SEQUENTIALLY (no fleet)...');

  // Security
  if (budget.total && budget.remaining() < 80_000) {
    log('Insufficient budget for security (skipping)');
    results.phases_skipped.push('security');
  } else {
    log('Running security audit...');
    results.security = await workflow('code-security', { autonomous: AUTONOMOUS });
    results.phases_run.push('security');

    if (results.security?.verified_findings > 0) {
      results.critical_issues.push(`${results.security.verified_findings} verified vulnerabilities`);
    }
  }

  // Documentation
  if (budget.total && budget.remaining() < 80_000) {
    log('Insufficient budget for documentation (skipping)');
    results.phases_skipped.push('documentation');
  } else {
    log('Generating documentation...');
    results.documentation = await workflow('code-doc', { autonomous: AUTONOMOUS });
    results.phases_run.push('documentation');
  }

  // Release
  if (budget.total && budget.remaining() < 50_000) {
    log('Insufficient budget for release (skipping)');
    results.phases_skipped.push('release');
  } else {
    const commitCheck = await agent(`Check unreleased commits.
Run: git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~10")..HEAD | wc -l`, {
      label: 'Check Commits',
      schema: { type: 'object', properties: { unreleased_commits: { type: 'number' } } },
    });

    if (commitCheck.unreleased_commits === 0) {
      log('No unreleased commits, skipping release');
      results.phases_skipped.push('release');
    } else {
      log('Creating release notes...');
      results.release = await workflow('code-release-notes', { autonomous: AUTONOMOUS });
      results.phases_run.push('release');
    }
  }
}

// ============================================================================
// PHASE 8: SUMMARY
// ============================================================================

phase('Summary');

log('');
log('='.repeat(60));
log('FLEET SDLC PIPELINE COMPLETE');
log('='.repeat(60));
log('');

const tokensUsed = budget.total ? budget.spent() : 'unknown';

log(`Tokens: ${tokensUsed === 'unknown' ? 'unlimited' : Math.round(tokensUsed/1000) + 'k'}`);
log(`Fleet used: ${results.fleet_used}`);
log(`Parallel phases: ${results.parallel_phases_used}`);
log(`Phases run: ${results.phases_run.length}`);
log(`Phases skipped: ${results.phases_skipped.length}`);
log('');

if (results.development) {
  log(`Development: ${results.development.issues_created || 0} issues, ${results.development.solve_results?.solved || 0} fixed`);
}
if (results.testing) {
  log(`Testing: ${results.testing.test_summary?.total || 0} tests, ${results.testing.test_summary?.failed || 0} failures`);
  if (results.testing.fleet_used) log(`  (Fleet-sharded: ${results.testing.workers_used} workers)`);
}
if (results.pr_review) {
  log(`PR Review: ${results.pr_review.prs_reviewed || 0} reviewed`);
}
if (results.security) {
  log(`Security: ${results.security.total_findings || results.security.total_verified || 0} findings`);
}
if (results.documentation) {
  log(`Documentation: ${results.documentation.documented || 0} items`);
}
if (results.release) {
  log(`Release: ${results.release.version || 'created'}`);
}

if (results.phases_skipped.length > 0) {
  log(`Skipped: ${results.phases_skipped.join(', ')}`);
}

if (results.critical_issues.length > 0) {
  log('');
  log('CRITICAL ISSUES:');
  results.critical_issues.forEach(issue => log(`  - ${issue}`));
}

log('');
log('='.repeat(60));

const finalResult = {
  status: 'complete',
  fleet_used: results.fleet_used,
  parallel_phases_used: results.parallel_phases_used,
  workers_used: workers.length,
  elapsed_minutes: elapsed,
  tokens_used: tokensUsed,
  phases_run: results.phases_run,
  phases_skipped: results.phases_skipped,
  breaking_changes: results.breaking_changes,
  critical_issues: results.critical_issues,
  results,
};

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'code-sdlc-fleet',
    execution_data: finalResult,
  });
} catch (error) {
  log(`Learning extraction failed: ${error.message}`);
}

return finalResult;
