/**
 * code-review-bulk.js
 *
 * Fleet-distributed code review for large PRs or codebases.
 * Use case: Review 200+ changed files in parallel.
 *
 * Multi-session orchestration:
 *   - Controller: Gets list of changed files (from git diff or explicit list)
 *   - Splits files into 3 batches
 *   - Worker-01-03: Reviews each batch via independent Claude Code session
 *   - Workers call code-review for their file batch
 *   - Workers output JSON findings
 *   - Controller deduplicates and aggregates issues
 *
 * Per-file timing:
 *   - Multi-model code review: 10-15s per file
 *   - Issue classification: 5s
 *   - Total: ~30s per file
 *   - Sequential (200 files): 100 minutes
 *   - Fleet (3 workers): 33 minutes
 *
 * Challenges & solutions:
 *   - Workers need access to full repo context (not just file diffs)
 *     Solution: Clone repo on each worker from NFS
 *   - Avoid duplicate findings across workers
 *     Solution: Deduplicate by file:line:issue_type key
 *   - File-by-file output
 *     Solution: Each worker outputs JSON, controller merges
 */

export const meta = {
  name: 'code-review-bulk',
  description: 'Fleet-distributed code review - review 200+ files in parallel',
  whenToUse: 'When you need comprehensive multi-AI code review of large PRs or codebases',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'File Discovery', detail: 'Get list of files to review' },
    { title: 'Batch Distribution', detail: 'Split files across workers' },
    { title: 'Parallel Review', detail: 'Each worker reviews its files' },
    { title: 'Issue Aggregation', detail: 'Deduplicate and prioritize issues' },
    { title: 'Issue Report', detail: 'Generate review summary' },
  ],
};

import { bulkOrchestrate, mergeAndDedupFindings } from '../shared/fleet-bulk-orchestration.js';
import fs from 'fs';
import path from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const DRY_RUN = args?.dryRun === true;
const REVIEW_EFFORT = args?.effort || 'medium'; // 'low', 'medium', 'high'
const REVIEW_TYPE = args?.type || 'issues'; // 'issues', 'style', 'security', 'performance'

log('');
log('='.repeat(70));
log('Bulk Code Review - Fleet Distribution');
log('='.repeat(70));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`Effort: ${REVIEW_EFFORT}`);
log(`Review type: ${REVIEW_TYPE}`);
if (DRY_RUN) log('DRY RUN MODE');
log('');

// ============================================================================
// PHASE 1: File Discovery
// ============================================================================

phase('File Discovery');

const projectDir = process.cwd();
log(`Project: ${projectDir}`);

let filesToReview = [];

if (args?.files && Array.isArray(args.files)) {
  filesToReview = args.files;
  log(`Using ${filesToReview.length} files from args.files`);
} else if (args?.prNumber) {
  // GitHub PR - get changed files
  log(`Getting changed files from PR #${args.prNumber}...`);

  const prResult = await _agent(`Get list of changed files in GitHub PR #${args.prNumber}.

Use gh CLI:
gh pr view ${args.prNumber} --json files --jq '.files[].path'

Return array of file paths.`, {
    label: 'Get PR Files',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' } },
      }
    }
  });

  filesToReview = prResult.files || [];
  log(`PR #${args.prNumber}: ${filesToReview.length} files changed`);
} else if (args?.gitRef) {
  // Git diff - get files changed between refs
  log(`Getting files changed between ${args.gitRef}...`);

  const gitResult = await _agent(`Get list of files changed by git commit/ref.

Use: git diff --name-only ${args.gitRef}

Return array of file paths.`, {
    label: 'Get Git Diff',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' } },
      }
    }
  });

  filesToReview = gitResult.files || [];
  log(`Commit/ref: ${filesToReview.length} files changed`);
} else {
  // Default: review all source files
  log('No specific files specified, discovering all source files...');

  const discoveryResult = await _agent(`Discover all source files for review.

Project: ${projectDir}

Find source files (same patterns as code-security-bulk):
- **/*.js, **/*.ts, **/*.tsx, **/*.jsx
- **/*.py, **/*.java, **/*.go, **/*.rs

Exclude: node_modules, .git, dist, build, test fixtures, minified files

Return: { files: [...] }`, {
    label: 'Discover Source Files',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' } },
      }
    }
  });

  filesToReview = discoveryResult.files || [];
  log(`Discovered ${filesToReview.length} source files`);
}

if (filesToReview.length === 0) {
  return {
    status: 'error',
    message: 'No files to review',
  };
}

log(`Total files to review: ${filesToReview.length}`);
log('');

// ============================================================================
// PHASE 2: Bulk Orchestration
// ============================================================================

phase('Fleet Orchestration');

// Custom merge for code review findings
const mergeCodeReviewFindings = (results) => {
  const allIssues = results.flatMap(r => r.issues || []);

  // Deduplicate by file:line:issue_type
  const deduped = mergeAndDedupFindings(
    results.map(r => ({ findings: r.issues || [] })),
    (issue) => `${issue.file}:${issue.line || 0}:${issue.type || 'unknown'}`
  );

  // Sort by priority
  const priorityRank = { critical: 4, high: 3, medium: 2, low: 1 };
  deduped.sort((a, b) => (priorityRank[b.severity] || 0) - (priorityRank[a.severity] || 0));

  return {
    issues: deduped,
    total: deduped.length,
    by_severity: {
      critical: deduped.filter(i => i.severity === 'critical').length,
      high: deduped.filter(i => i.severity === 'high').length,
      medium: deduped.filter(i => i.severity === 'medium').length,
      low: deduped.filter(i => i.severity === 'low').length,
    }
  };
};

const orchestrationResult = await bulkOrchestrate({
  skill: 'code-review-bulk',
  items: filesToReview,
  workerScript: 'workflows/code-review.js',
  mergeStrategy: mergeCodeReviewFindings,
  itemSerializer: (files) => JSON.stringify({
    files,
    effort: REVIEW_EFFORT,
    type: REVIEW_TYPE,
  }),
  resultDeserializer: (stdout) => {
    try {
      return JSON.parse(stdout);
    } catch {
      return { issues: [] };
    }
  },
  log,
  fleetOptions: { capabilities: ['code-review'] },
  minWorkers: 2,
  timeout: 600000,
  dryRun: DRY_RUN,
  useWeightedDistribution: true,
});

log('');

if (orchestrationResult.status === 'failed') {
  return {
    status: 'failed',
    message: 'All workers failed',
    filesReviewed: orchestrationResult.itemsProcessed,
    totalFiles: orchestrationResult.totalItems,
    errors: orchestrationResult.errors,
  };
}

// ============================================================================
// PHASE 3: Generate Review Report
// ============================================================================

phase('Generate Report');

const reviewData = orchestrationResult.result || { issues: [], total: 0, by_severity: {} };
const totalIssues = reviewData.total || 0;

log(`Total issues: ${totalIssues}`);
log('By severity:');
log(`  Critical: ${reviewData.by_severity?.critical || 0}`);
log(`  High:     ${reviewData.by_severity?.high || 0}`);
log(`  Medium:   ${reviewData.by_severity?.medium || 0}`);
log(`  Low:      ${reviewData.by_severity?.low || 0}`);

// Generate report
const reportResult = await _agent(`Generate code review report from issues.

Total issues: ${totalIssues}
Critical: ${reviewData.by_severity?.critical || 0}
High: ${reviewData.by_severity?.high || 0}

Top 20 issues:
${JSON.stringify(reviewData.issues?.slice(0, 20) || [], null, 2)}

Create professional report with:
1. Executive summary
2. Issue breakdown by severity
3. Top issues with context
4. Actionable recommendations
5. Priority areas for fixes

Return as markdown.`, {
  label: 'Generate Report',
  schema: {
    type: 'object',
    properties: {
      report: { type: 'string' },
    }
  }
});

log('Report generated');
log('');

// ============================================================================
// PHASE 4: Save Results
// ============================================================================

phase('Save Results');

const reportDir = path.join(projectDir, '.claude', 'bulk-reports');
if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

// Save markdown report
const reportFile = path.join(reportDir, `code-review-${Date.now()}.md`);
fs.writeFileSync(reportFile, reportResult.report || '');
log(`Report saved: ${reportFile}`);

// Save detailed issues JSON
const issuesFile = path.join(reportDir, `code-review-issues-${Date.now()}.json`);
const issuesData = {
  timestamp: new Date().toISOString(),
  totalFiles: orchestrationResult.totalItems,
  filesReviewed: orchestrationResult.itemsProcessed,
  totalIssues,
  bySeverity: reviewData.by_severity,
  issues: reviewData.issues || [],
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  errors: orchestrationResult.errors,
};

fs.writeFileSync(issuesFile, JSON.stringify(issuesData, null, 2));
log(`Issues saved: ${issuesFile}`);
log('');

log('='.repeat(70));
log('BULK CODE REVIEW COMPLETE');
log('='.repeat(70));
log(`Files reviewed: ${orchestrationResult.itemsProcessed}/${orchestrationResult.totalItems}`);
log(`Issues found: ${totalIssues}`);
log(`  Critical: ${reviewData.by_severity?.critical || 0}`);
log(`  High: ${reviewData.by_severity?.high || 0}`);
log(`Fleet used: ${orchestrationResult.fleetUsed ? 'YES' : 'NO'}`);
log(`Workers: ${orchestrationResult.workersUsed}`);
log('='.repeat(70));

return {
  status: orchestrationResult.status,
  totalFiles: orchestrationResult.totalItems,
  filesReviewed: orchestrationResult.itemsProcessed,
  totalIssues,
  bySeverity: reviewData.by_severity,
  topIssues: reviewData.issues?.slice(0, 10) || [],
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  reportFile,
  issuesFile,
  errors: orchestrationResult.errors,
};
