#!/usr/bin/env node
/**
 * Merge Conflict Check Workflow Example
 * Demonstrates integration of merge conflict predictor in CI/CD
 *
 * Use cases:
 * 1. Pre-merge safety check (before creating PR)
 * 2. CI/CD gate (fail pipeline on high-risk conflicts)
 * 3. Code review prioritization (review high-risk files first)
 */

import { execSync } from 'child_process';
import { readFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

// Use CommonJS adapter
const { predictConflicts, isMergeSafe, formatReport } = await (async () => {
  const module = await import('module');
  const require = module.createRequire(import.meta.url);
  return require('../shared/merge-conflict-predictor-adapter.cjs');
})();

/**
 * Example 1: Pre-merge safety check
 */
async function preMergeCheck(targetBranch = 'main', sourceBranch = 'HEAD') {
  console.log('╔═══════════════════════════════════════════════════════════╗');
  console.log('║          PRE-MERGE CONFLICT SAFETY CHECK                  ║');
  console.log('╚═══════════════════════════════════════════════════════════╝');
  console.log('');

  const safety = await isMergeSafe(targetBranch, sourceBranch, {
    maxHighRisk: 0,      // No high-risk conflicts allowed
    maxRiskScore: 40     // Overall risk must be low
  });

  if (safety.safe) {
    console.log('✅ SAFE TO MERGE');
    console.log('   No significant conflict risk detected.');
    console.log('');
    return true;
  } else {
    console.log('❌ MERGE NOT RECOMMENDED');
    console.log(`   Reason: ${safety.reason}`);
    console.log('');

    if (safety.results) {
      console.log(formatReport(safety.results));
    }

    return false;
  }
}

/**
 * Example 2: CI/CD pipeline integration
 */
async function ciPipelineCheck(targetBranch, sourceBranch) {
  console.log('╔═══════════════════════════════════════════════════════════╗');
  console.log('║          CI/CD MERGE CONFLICT GATE                        ║');
  console.log('╚═══════════════════════════════════════════════════════════╝');
  console.log('');

  const results = await predictConflicts(targetBranch, sourceBranch);

  if (!results.success) {
    console.error('❌ Conflict prediction failed');
    console.error(`   Error: ${results.error}`);
    process.exit(1);
  }

  // Metrics for CI system
  const metrics = {
    total_predictions: results.totalPredictions,
    high_risk_count: results.highRisk.length,
    medium_risk_count: results.mediumRisk.length,
    low_risk_count: results.lowRisk.length,
    risk_score: results.summary.riskScore,
    timestamp: results.timestamp
  };

  console.log('📊 Conflict Metrics:');
  console.log(`   Total predictions: ${metrics.total_predictions}`);
  console.log(`   High-risk:         ${metrics.high_risk_count}`);
  console.log(`   Medium-risk:       ${metrics.medium_risk_count}`);
  console.log(`   Low-risk:          ${metrics.low_risk_count}`);
  console.log(`   Risk score:        ${metrics.risk_score}/100`);
  console.log('');

  // Decision logic
  const FAIL_ON_HIGH_RISK = 3;    // Fail if >3 high-risk conflicts
  const WARN_ON_MEDIUM_RISK = 10; // Warn if >10 medium-risk conflicts

  if (results.highRisk.length > FAIL_ON_HIGH_RISK) {
    console.log('❌ PIPELINE FAILED: Too many high-risk conflicts');
    console.log(`   Found ${results.highRisk.length}, maximum allowed: ${FAIL_ON_HIGH_RISK}`);
    console.log('');
    console.log('   Recommended actions:');
    console.log('   1. Rebase on latest target branch');
    console.log('   2. Review high-risk files for conflicts');
    console.log('   3. Consider breaking into smaller PRs');
    console.log('');

    // Output for CI system (JSON)
    console.log('::set-output name=conflict_check::failed');
    console.log(`::set-output name=high_risk_count::${results.highRisk.length}`);

    process.exit(1);
  }

  if (results.mediumRisk.length > WARN_ON_MEDIUM_RISK) {
    console.log('⚠️  WARNING: Many medium-risk conflicts detected');
    console.log(`   Found ${results.mediumRisk.length}, threshold: ${WARN_ON_MEDIUM_RISK}`);
    console.log('   Recommend careful review during merge.');
    console.log('');
  }

  console.log('✅ PIPELINE PASSED: Conflict risk acceptable');
  console.log('::set-output name=conflict_check::passed');
  console.log(`::set-output name=risk_score::${metrics.risk_score}`);

  return true;
}

/**
 * Example 3: Code review prioritization
 */
async function generateReviewPriority(targetBranch, sourceBranch) {
  console.log('╔═══════════════════════════════════════════════════════════╗');
  console.log('║          CODE REVIEW PRIORITY REPORT                      ║');
  console.log('╚═══════════════════════════════════════════════════════════╝');
  console.log('');

  const results = await predictConflicts(targetBranch, sourceBranch);

  if (!results.success) {
    console.error('Failed to generate review priorities');
    return;
  }

  // Group files by risk
  const fileRisks = new Map();

  for (const pred of results.predictions) {
    // Track highest risk for each file
    for (const file of [pred.file1, pred.file2]) {
      const current = fileRisks.get(file) || { risk: 'LOW', prob: 0, count: 0 };

      if (pred.conflict_probability > current.prob) {
        fileRisks.set(file, {
          risk: pred.risk,
          prob: pred.conflict_probability,
          count: current.count + 1
        });
      } else {
        current.count++;
      }
    }
  }

  // Sort by risk (highest first)
  const sortedFiles = Array.from(fileRisks.entries())
    .sort((a, b) => b[1].prob - a[1].prob);

  console.log('📋 Review Priority List:');
  console.log('   (Files with highest conflict risk first)');
  console.log('');

  let priority = 1;
  for (const [file, info] of sortedFiles.slice(0, 20)) {
    const icon = info.risk === 'HIGH' ? '🔴' : info.risk === 'MEDIUM' ? '🟡' : '🟢';
    const probStr = `${(info.prob * 100).toFixed(0)}%`;

    console.log(`   ${priority.toString().padStart(2)}. ${icon} [${probStr.padStart(4)}] ${file}`);
    console.log(`       ${info.count} potential conflict(s)`);

    priority++;
  }

  console.log('');
  console.log('   💡 Tip: Review high-risk files first to catch conflicts early');
  console.log('');
}

/**
 * Example 4: Branch comparison matrix
 */
async function compareBranches(baseBranch, ...branches) {
  console.log('╔═══════════════════════════════════════════════════════════╗');
  console.log('║          BRANCH COMPARISON MATRIX                         ║');
  console.log('╚═══════════════════════════════════════════════════════════╝');
  console.log('');

  const matrix = [];

  for (const branch of branches) {
    const results = await predictConflicts(baseBranch, branch);

    if (results.success) {
      matrix.push({
        branch,
        totalConflicts: results.totalPredictions,
        highRisk: results.highRisk.length,
        mediumRisk: results.mediumRisk.length,
        riskScore: results.summary.riskScore,
        safe: results.highRisk.length === 0 && results.summary.riskScore < 40
      });
    }
  }

  // Sort by risk score (safest first)
  matrix.sort((a, b) => a.riskScore - b.riskScore);

  console.log(`Merging into: ${baseBranch}`);
  console.log('');
  console.log('Branch'.padEnd(40) + ' | Risk  | High | Med  | Total | Status');
  console.log('─'.repeat(80));

  for (const row of matrix) {
    const status = row.safe ? '✅ Safe' : '⚠️  Review';
    const line = [
      row.branch.padEnd(40),
      row.riskScore.toString().padStart(5),
      row.highRisk.toString().padStart(4),
      row.mediumRisk.toString().padStart(4),
      row.totalConflicts.toString().padStart(5),
      status
    ].join(' | ');

    console.log(line);
  }

  console.log('');
  console.log('💡 Merge order recommendation:');

  let mergeOrder = 1;
  for (const row of matrix.filter(r => r.safe)) {
    console.log(`   ${mergeOrder}. ${row.branch} (risk: ${row.riskScore})`);
    mergeOrder++;
  }

  if (matrix.some(r => !r.safe)) {
    console.log('');
    console.log('⚠️  Requires review before merge:');
    for (const row of matrix.filter(r => !r.safe)) {
      console.log(`   - ${row.branch} (${row.highRisk} high-risk conflicts)`);
    }
  }

  console.log('');
}

/**
 * Main CLI handler
 */
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'pre-merge') {
    const target = args[1] || 'main';
    const source = args[2] || 'HEAD';
    const safe = await preMergeCheck(target, source);
    process.exit(safe ? 0 : 1);

  } else if (command === 'ci-check') {
    const target = args[1] || 'main';
    const source = args[2] || 'HEAD';
    await ciPipelineCheck(target, source);

  } else if (command === 'review-priority') {
    const target = args[1] || 'main';
    const source = args[2] || 'HEAD';
    await generateReviewPriority(target, source);

  } else if (command === 'compare') {
    const base = args[1] || 'main';
    const branches = args.slice(2);

    if (branches.length === 0) {
      // Get all local branches except base
      const branchList = execSync('git branch --format="%(refname:short)"', { encoding: 'utf8' })
        .trim()
        .split('\n')
        .filter(b => b !== base && !b.includes('worktree-'));

      await compareBranches(base, ...branchList.slice(0, 10)); // Limit to 10
    } else {
      await compareBranches(base, ...branches);
    }

  } else {
    console.log('Merge Conflict Check Workflow Examples');
    console.log('');
    console.log('Usage:');
    console.log('  node workflows/merge-conflict-check-example.mjs <command> [args...]');
    console.log('');
    console.log('Commands:');
    console.log('  pre-merge [target] [source]');
    console.log('    Check if merge is safe (default: main HEAD)');
    console.log('');
    console.log('  ci-check [target] [source]');
    console.log('    CI/CD pipeline integration (default: main HEAD)');
    console.log('');
    console.log('  review-priority [target] [source]');
    console.log('    Generate code review priority list (default: main HEAD)');
    console.log('');
    console.log('  compare [base] [branch1] [branch2] ...');
    console.log('    Compare multiple branches for conflict risk');
    console.log('    (if no branches given, compares all local branches)');
    console.log('');
    console.log('Examples:');
    console.log('  node workflows/merge-conflict-check-example.mjs pre-merge main feature-branch');
    console.log('  node workflows/merge-conflict-check-example.mjs ci-check main HEAD');
    console.log('  node workflows/merge-conflict-check-example.mjs review-priority main fix/issue-273');
    console.log('  node workflows/merge-conflict-check-example.mjs compare main feature-1 feature-2');
    console.log('');
  }
}

// Run if called directly
main().catch(error => {
  console.error('Error:', error.message);
  process.exit(1);
});

export default main;
