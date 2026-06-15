/**
 * Validation Workflow Integration Example
 *
 * This file shows how to integrate GitHub issue tracking into validation workflows.
 *
 * PATTERNS:
 *   1. Standalone validation workflow with GitHub integration
 *   2. Fleet validation with issue creation and tracking
 *   3. Fix workflow with issue closure
 *   4. Async issue tracking (non-blocking)
 */

// ============================================================================
// PATTERN 1: Simple Standalone Validation Workflow
// ============================================================================

export const meta = {
  name: 'validation-with-issues',
  description: 'Run validation and create GitHub issues for blockers',
};

import {
  createValidationIssue,
  getWorkflowState
} from './github-issue-integration.js';

export default async function validateWithIssueTracking(context) {
  const workflowRunId = `validate-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const results = [];

  log(`Starting validation run: ${workflowRunId}`);

  // Run smoke tests
  phase('Validation');
  const testResults = await parallel([
    () => agent('Run smoke test...', { label: 'test-1' }),
    () => agent('Run unit tests...', { label: 'test-2' }),
    () => agent('Run integration tests...', { label: 'test-3' })
  ]);

  // Process results and create issues
  const createdIssues = [];
  for (const result of testResults) {
    if (result.status === 'FAIL') {
      try {
        const issue = await createValidationIssue({
          title: `Validation failed: ${result.testName}`,
          body: `Test "${result.testName}" failed\n\nError: ${result.error}`,
          severity: result.isBlocker ? 'blocker' : 'bug',
          workflowRunId,
          failureDetails: result,
          labels: ['validation', 'auto-created']
        });

        createdIssues.push(issue);
        log(`Created issue #${issue.number} for ${result.testName}`);
      } catch (err) {
        log(`Warning: Could not create issue: ${err.message}`);
      }
    }
  }

  return {
    workflowRunId,
    passed: testResults.filter(r => r.status === 'PASS').length,
    failed: testResults.filter(r => r.status === 'FAIL').length,
    issues: createdIssues,
    status: createdIssues.length === 0 ? 'PASS' : 'FAIL'
  };
}

// ============================================================================
// PATTERN 2: Fleet Validation with Issue Tracking
// ============================================================================

import {
  wrapValidationWorkflow
} from './validation-workflow-wrapper.js';

/**
 * Validation workflow that automatically tracks issues
 */
const fleetValidationWorkflow = wrapValidationWorkflow(
  async (context) => {
    phase('Smoke Tests');

    const tests = await parallel([
      () => agent(`
        Run smoke tests on deployed app.
        Return: { status: 'PASS'|'FAIL', testName, error?, failure_details? }
      `, { label: 'smoke-deploy' }),

      () => agent(`
        Run API endpoint tests.
        Return: { status: 'PASS'|'FAIL', testName, error?, isBlocker? }
      `, { label: 'smoke-api' }),

      () => agent(`
        Run database health checks.
        Return: { status: 'PASS'|'FAIL', testName, error? }
      `, { label: 'smoke-db' })
    ]);

    return tests;
  },
  {
    workflowName: 'fleet-smoke-test',
    trackIssues: true,         // Create GitHub issues
    autoCloseOnPass: true,     // Close issues when validation passes
    dryRun: false
  }
);

export { fleetValidationWorkflow };

// ============================================================================
// PATTERN 3: Fix Workflow with Issue Closure
// ============================================================================

import {
  wrapFixWorkflow,
  queryWorkflowState
} from './validation-workflow-wrapper.js';

/**
 * Fix workflow that updates and closes GitHub issues
 */
const fixFleetIssuesWorkflow = wrapFixWorkflow(
  async (context) => {
    const { workflowRunId } = context || {};

    if (!workflowRunId) {
      throw new Error('Fix workflow requires workflowRunId from validation context');
    }

    // Get issues from validation workflow
    const state = await queryWorkflowState(workflowRunId);

    if (!state.issues || state.issues.length === 0) {
      log('No issues to fix');
      return { fixes: [], validationPassed: true };
    }

    log(`Fixing ${state.issues.length} issues from validation...`);

    const fixes = await parallel(
      state.issues.map(issueNum => () =>
        agent(`
          Fix the issue that caused test failure.
          Issue #${issueNum}

          Steps:
          1. Identify root cause
          2. Apply minimal fix
          3. Validate fix resolves issue
          4. Return: { description, commits: ['sha1', ...], validationPassed: bool }
        `, { label: `fix-${issueNum}` })
      )
    );

    return {
      fixes: fixes.map((fix, idx) => ({
        issueNumber: state.issues[idx],
        description: fix.description || 'Applied fix',
        commits: fix.commits || [],
        validationPassed: fix.validationPassed === true
      })),
      validationPassed: fixes.every(f => f.validationPassed)
    };
  },
  {
    workflowName: 'fleet-fix',
    trackIssues: true,
    dryRun: false
  }
);

export { fixFleetIssuesWorkflow };

// ============================================================================
// PATTERN 4: Async Issue Tracking (Non-Blocking)
// ============================================================================

/**
 * Validation that creates issues asynchronously (doesn't block on issue creation)
 */
export const asyncValidationExample = wrapValidationWorkflow(
  async (context) => {
    phase('Testing');

    const testResults = await parallel([
      () => agent('Run tests and return { status, issues[], evidence[] }'),
      () => agent('Run performance tests'),
      () => agent('Run security checks')
    ]);

    // Results returned immediately; issue creation happens in background
    return testResults;
  },
  {
    workflowName: 'async-validation',
    trackIssues: true,
    autoCloseOnPass: true
  }
);

// ============================================================================
// PATTERN 5: Manual GitHub Integration
// ============================================================================

import {
  createValidationIssue,
  updateIssueWithFix,
  closeIssue,
  linkIssueToWorkflow
} from './github-issue-integration.js';

/**
 * Fully manual control over issue lifecycle
 */
export async function manualIssueTrackingExample() {
  const workflowRunId = 'manual-validation-123';

  // Create an issue for a blocker
  const issue = await createValidationIssue({
    title: 'Deployment validation failed',
    body: 'Database migration failed on startup',
    severity: 'blocker',
    workflowRunId,
    failureDetails: {
      test: 'database-migration',
      error: 'Foreign key constraint violation',
      table: 'users_roles'
    }
  });

  log(`Created issue #${issue.number}`);

  // Link to workflow for traceability
  await linkIssueToWorkflow({
    issueNumber: issue.number,
    workflowRunId,
    workflowUrl: 'https://github.com/.../actions/runs/12345'
  });

  // Later: Apply fix and update issue
  await updateIssueWithFix({
    issueNumber: issue.number,
    fixDetails: 'Applied data migration fix in commit abc123',
    commitShas: ['abc123def456']
  });

  // After fix is verified, close the issue
  await closeIssue({
    issueNumber: issue.number,
    reason: 'Fixed in commit abc123, validation passed'
  });
}

// ============================================================================
// PATTERN 6: Batch Issue Creation from Fleet Results
// ============================================================================

/**
 * Process fleet validation results and create issues in batch
 */
export async function batchIssueCreationExample(fleetResults) {
  const workflowRunId = fleetResults.workflowRunId || `batch-${Date.now()}`;
  const createdIssues = [];

  for (const agentResult of fleetResults.failures || []) {
    // Group related failures
    const severity = agentResult.isCritical ? 'blocker' : 'bug';

    const issue = await createValidationIssue({
      title: `Fleet validation: ${agentResult.agent} failed`,
      body: `Agent: ${agentResult.agent}\n\n${agentResult.error}`,
      severity,
      workflowRunId,
      failureDetails: {
        agent: agentResult.agent,
        error: agentResult.error,
        returnCode: agentResult.returnCode
      },
      labels: ['fleet-validation', `agent-${agentResult.agent}`]
    });

    createdIssues.push(issue);
  }

  return {
    workflowRunId,
    issuesCreated: createdIssues.length,
    issues: createdIssues
  };
}

// ============================================================================
// PATTERN 7: Dashboard/Query Integration
// ============================================================================

import {
  getWorkflowState,
  CONFIG
} from './github-issue-integration.js';

/**
 * Query workflow state for dashboard display
 */
export async function getValidationDashboard() {
  const state = await getWorkflowState();

  const dashboard = {
    totalIssues: state.issues.length,
    openIssues: state.issues.filter(i => i.status === 'open').length,
    closedIssues: state.issues.filter(i => i.status === 'closed').length,
    byWorkflow: {}
  };

  // Group by workflow
  for (const [workflowRunId, workflowData] of Object.entries(state.workflows)) {
    dashboard.byWorkflow[workflowRunId] = {
      status: workflowData.status,
      issueCount: workflowData.issues.length,
      createdAt: workflowData.createdAt
    };
  }

  return dashboard;
}

// ============================================================================
// INTEGRATION CHECKLIST
// ============================================================================

/**
 * INTEGRATION CHECKLIST:
 *
 * [ ] 1. Install dependencies
 *       - Ensure `gh` CLI is installed: https://cli.github.com
 *       - Ensure authenticated: `gh auth status`
 *
 * [ ] 2. Update existing validation workflows
 *       - Replace workflow function with wrapValidationWorkflow()
 *       - Ensure test results have proper structure: { status, error?, ... }
 *       - Set trackIssues: true
 *
 * [ ] 3. Update fix workflows
 *       - Wrap with wrapFixWorkflow()
 *       - Accept workflowRunId from validation context
 *       - Return fixes with { issueNumber, description, commits, validationPassed }
 *
 * [ ] 4. Configure workflow state storage
 *       - Check .claude/workflow-issue-state.json is in .gitignore
 *       - Ensure directory permissions allow read/write
 *
 * [ ] 5. Set up GitHub labels (optional but recommended)
 *       - validation-blocker (red)
 *       - validation-bug (orange)
 *       - validation-flaky (yellow)
 *       - validation-performance (blue)
 *       - validation-security (purple)
 *       - auto-created (gray)
 *
 * [ ] 6. Test integration
 *       - Run validation workflow with --dryRun first
 *       - Verify issues appear on GitHub
 *       - Test fix workflow with real issue
 *       - Verify issue closure
 *
 * [ ] 7. Monitor in production
 *       - Check workflow-issue-state.json for correctness
 *       - Monitor failed issue creations in logs
 *       - Track issue lifecycle metrics
 */
