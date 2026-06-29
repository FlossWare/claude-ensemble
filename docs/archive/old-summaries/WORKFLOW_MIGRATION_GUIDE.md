# Workflow Migration Guide

Complete guide for migrating your validation and fix workflows to use GitHub issue tracking.

## Overview

This guide shows how to update existing workflows to automatically create, update, and close GitHub issues.

## Migration Strategy

1. **Phase 1**: Migrate validation workflows first (issue creation)
2. **Phase 2**: Migrate fix workflows (issue updates/closure)
3. **Phase 3**: Monitor and optimize

## Phase 1: Validation Workflow Migration

### Step 1.1: Identify Validation Workflows

Find all validation workflows in your codebase:

```bash
find . -name "*validation*.js" -o -name "*smoke-test*.js" -o -name "*test*.js" | grep -E "(validation|smoke|test)" | head -20
```

Common patterns:
- `code-smoke-test.js`
- `ai-cross-validation.js`
- `validation-*` workflows
- `*-test` workflows

### Step 1.2: Analyze Current Test Result Structure

Look at what your current workflows return:

```javascript
// Current workflow returns:
async function currentWorkflow() {
  const results = await runTests();
  
  // Check what structure is returned
  console.log(JSON.stringify(results[0], null, 2));
  
  return results;
}
```

**Typical structures:**

Option A - Array of results:
```javascript
[
  { status: 'PASS', test_name: 'launch', duration_ms: 1234 },
  { status: 'FAIL', test_name: 'api-health', error: 'Timeout', issues: ['...'] }
]
```

Option B - Single result object:
```javascript
{
  overall_status: 'FAIL',
  passed_tests: 5,
  failed_tests: 2,
  critical_issues: ['...']
}
```

Option C - Custom structure - adapt as needed.

### Step 1.3: Update Imports

Add imports to your validation workflow:

```javascript
// Before
// (no imports needed)

// After
import {
  wrapValidationWorkflow
} from './validation-workflow-wrapper.js';
// OR for manual control:
import {
  createValidationIssue,
  getWorkflowState
} from './github-issue-integration.js';
```

### Step 1.4: Wrap the Workflow

**Option A: Simple Wrap (Easiest)**

```javascript
// OLD
export default async function smokeTest() {
  const results = await runAllTests();
  return results;
}

// NEW
export default wrapValidationWorkflow(
  async () => {
    const results = await runAllTests();
    return results;
  },
  {
    workflowName: 'smoke-test',
    trackIssues: true,
    autoCloseOnPass: true
  }
);
```

**Option B: Manual Control (More Flexible)**

```javascript
// OLD
export default async function smokeTest() {
  const results = await runAllTests();
  return results;
}

// NEW
import { createValidationIssue } from './github-issue-integration.js';

export default async function smokeTest() {
  const workflowRunId = `smoke-test-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const results = await runAllTests();

  // Create issues for failures
  const createdIssues = [];
  for (const result of results.filter(r => r.status === 'FAIL')) {
    try {
      const issue = await createValidationIssue({
        title: `Smoke test failed: ${result.test_name}`,
        body: result.error || 'Test failed',
        severity: result.isBlocker ? 'blocker' : 'bug',
        workflowRunId,
        failureDetails: result
      });
      createdIssues.push(issue);
    } catch (err) {
      console.error(`Failed to create issue: ${err.message}`);
    }
  }

  return {
    ...results,
    workflowRunId,
    createdIssues
  };
}
```

### Step 1.5: Test Result Structure Requirements

Ensure your test results match expected schema:

```javascript
// Required fields
{
  status: 'PASS' | 'FAIL'  // Required
}

// Recommended fields (for better issues)
{
  status: 'PASS' | 'FAIL',
  test_name: 'name-of-test',     // For issue titles
  error: 'error message',         // Shown in issue body
  failure_details: { /* ... */ }, // Structured metadata
  isBlocker: false,               // Severity: true = blocker, false = bug
  labels: ['tag1', 'tag2']        // Additional GitHub labels
}
```

### Step 1.6: Update Test Execution

Modify your test execution to return proper schema:

```javascript
// Before
const testResult = await agent('Run tests...');
// Returns: { label, value, ... }

// After
const testResult = await agent(`
  Run tests and return: {
    status: 'PASS' | 'FAIL',
    test_name: 'test-name',
    error?: 'error message',
    failure_details?: { /* context */ }
  }
`);
```

### Step 1.7: Test Dry Run

Test with dry run to avoid creating real issues:

```javascript
export default wrapValidationWorkflow(
  async () => { /* ... */ },
  {
    workflowName: 'smoke-test',
    trackIssues: true,
    dryRun: true  // <-- Enable dry run for testing
  }
);

// Run it
// Output will show:
// [DRY RUN] Would create GitHub issue: ...
// [smoke-test] Starting workflow run: smoke-test-2024-01-15-abc123
// [smoke-test] 5 passed, 2 failed
// [smoke-test] Would create 2 GitHub issues
```

### Step 1.8: Production Deployment

After testing, enable real issue creation:

```javascript
dryRun: false  // <-- Production mode
```

### Step 1.9: Migration Checklist

For **each** validation workflow:

- [ ] Import wrapper or integration functions
- [ ] Ensure test results have: `status`, `test_name`, `error`
- [ ] Add `failure_details` for context
- [ ] Test with `dryRun: true`
- [ ] Review dry-run output in logs
- [ ] Set `dryRun: false` for production
- [ ] Verify first few issues created on GitHub
- [ ] Add workflow to monitoring
- [ ] Document in README

## Phase 2: Fix Workflow Migration

### Step 2.1: Identify Fix Workflows

Find workflows that apply fixes:

```bash
grep -r "apply.*fix\|fix.*workflow" . --include="*.js" | head -20
```

Common patterns:
- Workflows that modify code
- Workflows that run with `--apply-fix`
- Workflows that create pull requests
- Workflows that auto-remediate

### Step 2.2: Analyze Fix Result Structure

Check what your fix workflows currently return:

```javascript
async function currentFixWorkflow(context) {
  const fixes = await applyFixes(context);
  
  console.log(JSON.stringify(fixes[0], null, 2));
  
  return fixes;
}
```

**Expected fix result structure:**

```javascript
{
  issueNumber: 42,           // GitHub issue number to update
  description: 'Fixed...',   // What was fixed
  commits: ['abc123', ...],  // Commit SHAs
  validationPassed: true     // Did validation pass?
}
```

### Step 2.3: Update Fix Workflow

**Option A: Simple Wrap (Easiest)**

```javascript
// OLD
export default async function fixValidationIssues(context) {
  const fixes = await applyAllFixes();
  return fixes;
}

// NEW
import { wrapFixWorkflow } from './validation-workflow-wrapper.js';

export default wrapFixWorkflow(
  async (context) => {
    const fixes = await applyAllFixes();
    return {
      fixes: fixes.map(fix => ({
        issueNumber: fix.issueNumber,
        description: fix.description,
        commits: fix.commits,
        validationPassed: fix.validationPassed
      })),
      validationPassed: fixes.every(f => f.validationPassed)
    };
  },
  {
    workflowName: 'fix-validation',
    trackIssues: true
  }
);
```

**Option B: Manual Control (More Flexible)**

```javascript
import {
  updateIssueWithFix,
  closeIssue,
  getWorkflowState
} from './github-issue-integration.js';

export default async function fixValidationIssues(context) {
  const { workflowRunId } = context || {};

  if (!workflowRunId) {
    throw new Error('Fix workflow requires workflowRunId from validation context');
  }

  // Get issues from validation workflow
  const state = await getWorkflowState(workflowRunId);

  if (!state.issues?.length) {
    return { fixed: 0, closed: 0 };
  }

  const fixed = [];
  const closed = [];

  // Fix each issue
  for (const issueNum of state.issues) {
    const fix = await agent(`Fix issue #${issueNum}...`);

    if (fix.success) {
      // Update issue with fix details
      await updateIssueWithFix({
        issueNumber: issueNum,
        fixDetails: fix.description,
        commitShas: fix.commits
      });
      fixed.push(issueNum);

      // Close if validation passed
      if (fix.validationPassed) {
        await closeIssue({
          issueNumber: issueNum,
          reason: 'Fixed and validated'
        });
        closed.push(issueNum);
      }
    }
  }

  return { fixed: fixed.length, closed: closed.length };
}
```

### Step 2.4: Connect Validation to Fix Workflow

Pass workflow run ID from validation to fix workflow:

```javascript
// validation-workflow.js
const validationResult = await wrapValidationWorkflow(
  async () => { /* ... */ },
  { workflowName: 'smoke-test' }
);

// Pass result to fix workflow
const fixResult = await agent('fix-issues', {
  context: { workflowRunId: validationResult.workflowRunId }
});
```

### Step 2.5: Test Fix Workflow

```bash
# 1. Create a test issue manually (or use validation workflow)
gh issue create --title "Test Fix Workflow" --body "This is a test"

# 2. Update fix workflow to use that issue
# (modify test to use that issue number)

# 3. Run with dry run
dryRun: true

# 4. Verify output
# [DRY RUN] Would add comment to issue #42
# [DRY RUN] Would close issue #42

# 5. Run for real
dryRun: false
```

### Step 2.6: Fix Workflow Checklist

For **each** fix workflow:

- [ ] Import wrapper or integration functions
- [ ] Accept `workflowRunId` from validation context
- [ ] Query validation workflow state
- [ ] Return fixes with: `issueNumber`, `description`, `commits`
- [ ] Test with dry run
- [ ] Test issue updates (comment creation)
- [ ] Test issue closure
- [ ] Verify commits linked in comments
- [ ] Set to production mode

## Phase 3: Monitoring & Optimization

### Monitor Workflow State

```javascript
import { getWorkflowState } from './github-issue-integration.js';

// Check what's tracked
async function monitorWorkflows() {
  const state = await getWorkflowState();

  console.log(`Total issues: ${state.issues.length}`);
  console.log(`Open issues: ${state.issues.filter(i => i.status === 'open').length}`);
  console.log(`Closed issues: ${state.issues.filter(i => i.status === 'closed').length}`);

  // By severity
  const bySeverity = {};
  for (const issue of state.issues) {
    bySeverity[issue.severity] = (bySeverity[issue.severity] || 0) + 1;
  }
  console.log('By Severity:', bySeverity);
}
```

### Add Metrics

```javascript
// Track metrics
const metrics = {
  issuesCreated: 0,
  issuesFixed: 0,
  issuesClosed: 0,
  avgTimeToFix: 0,
  avgTimeToClose: 0
};

// After each workflow run
const state = await getWorkflowState();
metrics.issuesCreated = state.issues.filter(i => i.status === 'open' || i.status === 'closed').length;
metrics.issuesClosed = state.issues.filter(i => i.status === 'closed').length;

// Calculate averages
const closed = state.issues.filter(i => i.status === 'closed' && i.closedAt);
if (closed.length > 0) {
  const times = closed.map(i => new Date(i.closedAt) - new Date(i.createdAt));
  metrics.avgTimeToClose = times.reduce((a, b) => a + b, 0) / times.length;
}
```

### Set Up Notifications

See `INTEGRATION_SETUP.md` → "Step 8: Set Up Notification Rules"

## Real-World Migration Examples

### Example 1: code-smoke-test.js

**Before:**
```javascript
// code-smoke-test.js
export default async function smokeTest() {
  const results = await parallel([
    /* test functions */
  ]);
  return results;
}
```

**After:**
```javascript
import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';

export default wrapValidationWorkflow(
  async () => {
    const results = await parallel([
      /* test functions */
    ]);
    return results;
  },
  {
    workflowName: 'smoke-test',
    trackIssues: true,
    autoCloseOnPass: true
  }
);
```

### Example 2: ai-cross-validation.js

**Before:**
```javascript
async function abTest(dataset, strategies, options) {
  // ... test code ...
  return {
    results,
    comparison,
    testSize: test.length
  };
}
```

**After:**
```javascript
import { createValidationIssue } from './github-issue-integration.js';

async function abTest(dataset, strategies, options) {
  const workflowRunId = `cv-${Date.now()}`;
  const results = {};

  // ... test code ...

  // Create issue if winner differs from previous
  if (comparison.winner !== options.previousWinner) {
    await createValidationIssue({
      title: `Cross-validation: Winner changed to ${comparison.winner}`,
      body: `Previous winner: ${options.previousWinner}\nNew winner: ${comparison.winner}`,
      severity: 'bug',
      workflowRunId,
      failureDetails: comparison
    });
  }

  return { results, comparison, workflowRunId };
}
```

### Example 3: Fleet Validation Workflow

**Before:**
```javascript
async function fleetValidate() {
  const results = await parallel([
    agent('Run on agent-1'),
    agent('Run on agent-2'),
    agent('Run on agent-3')
  ]);
  return results;
}
```

**After:**
```javascript
import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';

const fleetValidate = wrapValidationWorkflow(
  async () => {
    const results = await parallel([
      agent('Run tests and return { status, error?, failure_details? }'),
      agent('Run tests and return { status, error?, failure_details? }'),
      agent('Run tests and return { status, error?, failure_details? }')
    ]);
    return results;
  },
  {
    workflowName: 'fleet-validation',
    trackIssues: true
  }
);
```

## Testing & Validation

### Pre-Migration Checklist

Before migrating a workflow:

- [ ] Understand current test result structure
- [ ] Review existing test results in logs
- [ ] Identify required fields for issues
- [ ] Plan issue title format
- [ ] Plan failure detail structure
- [ ] Test imports in local env
- [ ] Create backup of original workflow

### Post-Migration Validation

After migrating a workflow:

- [ ] Run with dry run
- [ ] Verify output format
- [ ] Check workflow state file
- [ ] Create test issue on GitHub
- [ ] Verify issue metadata
- [ ] Verify issue closure (if applicable)
- [ ] Monitor for 24 hours
- [ ] Verify workflow state file growth

## Rollback Plan

If issues arise during migration:

```bash
# 1. Revert to original workflow
git checkout original-workflow.js

# 2. Remove test issues from GitHub
gh issue close <issue-number>

# 3. Clear workflow state
rm .claude/workflow-issue-state.json

# 4. Re-plan and retry
```

## Timeline Estimate

- **Small project (1-3 workflows)**: 1-2 hours
- **Medium project (4-10 workflows)**: 4-6 hours
- **Large project (10+ workflows)**: 1-2 days
- **Testing & monitoring**: 1-7 days

## FAQ

**Q: Do I have to wrap ALL workflows?**
A: No, wrap only validation and fix workflows. Other workflows don't need integration.

**Q: Can I use manual control instead of wrapper?**
A: Yes, both approaches work. Wrapper is easier, manual control is more flexible.

**Q: What if my test results don't match schema?**
A: Transform them in your agent call:
```javascript
const result = await agent('Run tests...');
return {
  status: result.passed ? 'PASS' : 'FAIL',
  test_name: result.name,
  error: result.errorMessage
};
```

**Q: Will this slow down workflows?**
A: Minimal impact. Issue creation is async and non-blocking by default.

**Q: Can I disable tracking temporarily?**
A: Yes, set `trackIssues: false` or `dryRun: true`

**Q: How do I test without GitHub access?**
A: Use `dryRun: true` to test locally without GitHub CLI.

## Next Steps

1. Identify workflows to migrate
2. Read this guide fully
3. Test with one small workflow first
4. Get team feedback
5. Migrate remaining workflows
6. Set up monitoring
7. Document in team wiki

## References

- Full API: `GITHUB_ISSUE_INTEGRATION_GUIDE.md`
- Examples: `validation-workflow-example.js`
- Setup: `INTEGRATION_SETUP.md`
- Tests: `github-issue-integration.test.js`
