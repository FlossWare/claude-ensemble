# GitHub Issue Integration for Validation Workflows

Complete guide to integrating GitHub issue tracking into fleet validation workflows.

## Overview

When fleet validation finds issues, automatically create GitHub issues with full traceability. When fixes are applied and validated, update and close the issues.

### Key Features

- **Automatic Issue Creation**: Create GitHub issues directly from validation results
- **Workflow Traceability**: Link issues to workflow run IDs for full audit trail
- **Fix Tracking**: Update issues with fix details and linked commits
- **State Persistence**: Track workflow state in `.claude/workflow-issue-state.json`
- **Async Non-Blocking**: Issue creation doesn't block validation workflow
- **Dry Run Support**: Test without creating actual GitHub issues
- **Multi-Issue Support**: Batch create multiple issues from fleet results
- **Auto-Close**: Automatically close issues when validation passes

## Files

### Core Implementation

1. **github-issue-integration.js** (550 lines)
   - Core module for GitHub issue operations
   - Functions: `createValidationIssue()`, `updateIssueWithFix()`, `closeIssue()`
   - Auto-detects repository from git remote
   - Uses GitHub CLI (`gh` command)
   - Persists workflow state to `.claude/workflow-issue-state.json`

2. **validation-workflow-wrapper.js** (400 lines)
   - Wraps validation workflows to auto-track issues
   - Functions: `wrapValidationWorkflow()`, `wrapFixWorkflow()`, `queryWorkflowState()`
   - Generates unique workflow run IDs
   - Processes test results and creates issues
   - Supports async issue creation

3. **validation-workflow-example.js** (400 lines)
   - 7 complete integration patterns
   - Copy-paste examples for different use cases
   - Integration checklist

## Quick Start

### 1. Ensure GitHub CLI is installed

```bash
# macOS
brew install gh

# Linux (Ubuntu/Debian)
sudo apt-get install gh

# Verify installation and authentication
gh auth status
```

### 2. Wrap existing validation workflow

**Before:**
```javascript
export default async function validateApp() {
  const testResults = await runTests();
  return testResults;
}
```

**After:**
```javascript
import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';

export default wrapValidationWorkflow(
  async () => {
    const testResults = await runTests();
    return testResults;
  },
  {
    workflowName: 'smoke-test',
    trackIssues: true,
    autoCloseOnPass: true
  }
);
```

### 3. Structure your test results

Return test results with this schema:

```javascript
{
  status: 'PASS' | 'FAIL',
  testName: 'name of test',
  error: 'error message (if FAIL)',
  failure_details: { /* context */ },
  isBlocker: false,    // for severity
  labels: ['tag1']     // optional
}
```

### 4. Create issues manually

```javascript
import { createValidationIssue } from './github-issue-integration.js';

const issue = await createValidationIssue({
  title: 'Deploy validation failed',
  body: 'App crashed on startup',
  severity: 'blocker',
  workflowRunId: 'workflow-123',
  failureDetails: { error: 'Segfault', line: 42 }
});

console.log(`Issue #${issue.number}: ${issue.url}`);
```

## API Reference

### `createValidationIssue(options)`

Creates a GitHub issue for a validation failure.

**Parameters:**
- `title` (string, required): Issue title
- `body` (string, required): Issue description
- `severity` (string): 'blocker' | 'bug' | 'flaky' | 'performance' | 'security'
- `workflowRunId` (string): Unique workflow identifier for traceability
- `failureDetails` (object): Structured failure metadata
- `labels` (string[]): Additional labels to apply
- `dryRun` (boolean): Don't create actual issue

**Returns:**
```javascript
{
  number: 42,
  url: 'https://github.com/owner/repo/issues/42',
  title: '...',
  severity: 'blocker',
  workflowRunId: 'workflow-123'
}
```

**Example:**
```javascript
const issue = await createValidationIssue({
  title: 'Smoke test: API endpoint timeout',
  body: 'GET /api/health returns 504 Gateway Timeout',
  severity: 'blocker',
  workflowRunId: 'smoke-test-2024-01-15-abc123',
  failureDetails: {
    endpoint: '/api/health',
    statusCode: 504,
    responseTime: 30000
  }
});
```

### `updateIssueWithFix(options)`

Add a fix comment to an issue and link commits.

**Parameters:**
- `issueNumber` (number, required): GitHub issue number
- `fixDetails` (string, required): Description of what was fixed
- `commitShas` (string[]): Array of commit SHAs that fix the issue
- `dryRun` (boolean): Test without creating comment

**Returns:**
```javascript
{
  issueNumber: 42,
  comment: '... comment body ...',
  output: '... gh CLI output ...'
}
```

**Example:**
```javascript
await updateIssueWithFix({
  issueNumber: 42,
  fixDetails: 'Updated health check endpoint to return 200',
  commitShas: ['abc123def456', 'ghi789jkl012']
});
```

### `closeIssue(options)`

Close a GitHub issue after validation passes.

**Parameters:**
- `issueNumber` (number, required): GitHub issue number
- `reason` (string): Closing comment
- `dryRun` (boolean): Test without closing

**Returns:**
```javascript
{
  issueNumber: 42,
  url: 'https://github.com/owner/repo/issues/42',
  closed: true
}
```

**Example:**
```javascript
await closeIssue({
  issueNumber: 42,
  reason: 'Fixed in commit abc123, validation passed'
});
```

### `wrapValidationWorkflow(workflowFn, options)`

Wraps a validation workflow to auto-track GitHub issues.

**Parameters:**
- `workflowFn` (function): Your validation function
- `options.workflowName` (string): Name for tracking
- `options.trackIssues` (boolean): Enable GitHub tracking
- `options.autoCloseOnPass` (boolean): Auto-close on success
- `options.dryRun` (boolean): Don't create actual issues

**Returns:** Wrapped function that returns enhanced results with issue metadata

**Example:**
```javascript
export default wrapValidationWorkflow(
  async () => {
    const results = await runTests();
    return results;
  },
  {
    workflowName: 'unit-tests',
    trackIssues: true,
    autoCloseOnPass: true
  }
);
```

### `wrapFixWorkflow(fixFn, options)`

Wraps a fix workflow to update and close GitHub issues.

**Parameters:**
- `fixFn` (function): Your fix workflow function
- `options.workflowName` (string): Name for tracking
- `options.trackIssues` (boolean): Enable GitHub tracking
- `options.dryRun` (boolean): Don't update actual issues

**Returns:** Wrapped function that handles issue updates automatically

**Example:**
```javascript
export default wrapFixWorkflow(
  async (context) => {
    const fixes = await applyFixes();
    return { fixes, validationPassed: true };
  },
  { workflowName: 'fix-tests' }
);
```

### `getWorkflowState(workflowRunId?)`

Query the state of tracked issues.

**Parameters:**
- `workflowRunId` (string, optional): Query specific workflow

**Returns:**
```javascript
{
  issues: [
    {
      number: 42,
      url: '...',
      severity: 'blocker',
      status: 'open',
      createdAt: '2024-01-15T10:30:00Z',
      linkedCommits: ['abc123']
    }
  ],
  workflows: {
    'workflow-123': {
      issues: [42, 43],
      status: 'in-progress',
      createdAt: '2024-01-15T10:30:00Z'
    }
  }
}
```

## Integration Patterns

### Pattern 1: Simple Validation with Issues

```javascript
import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';

export default wrapValidationWorkflow(
  async () => {
    const tests = await parallel([
      () => agent('Run unit tests'),
      () => agent('Run integration tests')
    ]);
    return tests;
  },
  { workflowName: 'tests', trackIssues: true }
);
```

### Pattern 2: Fleet Validation with Blockers

```javascript
import { createValidationIssue } from './github-issue-integration.js';

export default async function fleetValidate() {
  const workflowRunId = `fleet-${Date.now()}`;
  const results = [];

  const tests = await parallel([
    () => agent('Run on agent-1'),
    () => agent('Run on agent-2'),
    () => agent('Run on agent-3')
  ]);

  for (const test of tests.filter(t => t.status === 'FAIL')) {
    const issue = await createValidationIssue({
      title: `Fleet validation failed: ${test.agent}`,
      body: test.error,
      severity: test.isCritical ? 'blocker' : 'bug',
      workflowRunId
    });
    results.push(issue);
  }

  return { workflowRunId, issues: results };
}
```

### Pattern 3: Fix Workflow with Issue Closure

```javascript
import { wrapFixWorkflow } from './validation-workflow-wrapper.js';

export default wrapFixWorkflow(
  async (context) => {
    const { workflowRunId } = context;
    
    // Fix the issues
    const fixes = await parallel([
      () => agent('Fix issue #1'),
      () => agent('Fix issue #2')
    ]);

    return {
      fixes: fixes.map((fix, i) => ({
        issueNumber: validationIssues[i],
        description: fix.description,
        commits: fix.commits,
        validationPassed: fix.passed
      })),
      validationPassed: fixes.every(f => f.passed)
    };
  },
  { workflowName: 'fix-validation' }
);
```

### Pattern 4: Async Issue Creation (Non-Blocking)

```javascript
// Don't await issue creation - it happens in background
export default async function fastValidation() {
  const results = await runTests();

  // Return immediately; issues created asynchronously
  for (const fail of results.filter(r => r.status === 'FAIL')) {
    createValidationIssue({ /* ... */ })
      .catch(err => console.error('Issue creation failed:', err));
  }

  return { status: 'validated', results };
}
```

## Workflow State File

Issues are tracked in `.claude/workflow-issue-state.json`:

```json
{
  "issues": [
    {
      "number": 42,
      "url": "https://github.com/owner/repo/issues/42",
      "title": "Smoke test failed",
      "severity": "blocker",
      "workflowRunId": "smoke-test-2024-01-15-abc123",
      "createdAt": "2024-01-15T10:30:00Z",
      "status": "open",
      "linkedCommits": ["abc123def456"]
    }
  ],
  "workflows": {
    "smoke-test-2024-01-15-abc123": {
      "issues": [42, 43],
      "status": "in-progress",
      "createdAt": "2024-01-15T10:30:00Z"
    }
  }
}
```

**Add to `.gitignore`:**
```
.claude/workflow-issue-state.json
```

## Label Strategy

Recommended GitHub labels:

| Label | Color | Use Case |
|-------|-------|----------|
| `validation-blocker` | Red | Show-stopper bugs preventing deployment |
| `validation-bug` | Orange | Regular bugs found by validation |
| `validation-flaky` | Yellow | Intermittent failures |
| `validation-performance` | Blue | Performance degradation |
| `validation-security` | Purple | Security issues found |
| `auto-created` | Gray | Automated creation marker |

**Create labels via CLI:**
```bash
gh label create validation-blocker -c FF0000
gh label create validation-bug -c FF6600
gh label create validation-flaky -c FFFF00
gh label create validation-performance -c 0066FF
gh label create validation-security -c 9933FF
gh label create auto-created -c 888888
```

## Error Handling

### GitHub CLI Not Available

```
Error: GitHub CLI (gh) not available. Install with: brew install gh
```

**Fix:**
```bash
brew install gh
gh auth login
gh auth status
```

### Not in a Git Repository

```
Error: Could not detect GitHub repository. Ensure you are in a git repo...
```

**Fix:**
```bash
git init
git remote add origin https://github.com/owner/repo.git
```

### Authentication Failed

```
Error: gh CLI error: HTTP 403 Forbidden
```

**Fix:**
```bash
gh auth logout
gh auth login
# Select HTTPS, paste personal access token
```

### Issue Creation Rate Limited

```
Error: gh CLI error: API rate limit exceeded
```

**Fix:**
- Wait 1 hour for limit reset
- Or increase rate limit with GitHub Pro
- Or batch issues with lower frequency

## Dry Run Mode

Test integration without creating actual GitHub issues:

```javascript
const issue = await createValidationIssue({
  title: 'Test issue',
  body: 'This is a test',
  severity: 'bug',
  workflowRunId: 'test-run',
  dryRun: true  // No actual issue created
});

// Output:
// [DRY RUN] Would create GitHub issue:
//   Title: Test issue
//   Labels: validation-bug, auto-created
//   Body length: 125 chars
```

## Monitoring and Dashboards

### Query Workflow State

```javascript
import { getWorkflowState } from './github-issue-integration.js';

const state = await getWorkflowState();
console.log(`Open issues: ${state.issues.filter(i => i.status === 'open').length}`);
console.log(`Closed issues: ${state.issues.filter(i => i.status === 'closed').length}`);
```

### Track Issue Metrics

```javascript
const state = await getWorkflowState();

const metrics = {
  totalCreated: state.issues.length,
  openCount: state.issues.filter(i => i.status === 'open').length,
  closedCount: state.issues.filter(i => i.status === 'closed').length,
  avgTimeToClose: calculateAvg(state.issues.map(i => 
    new Date(i.closedAt) - new Date(i.createdAt)
  )),
  bySeverity: groupBy(state.issues, 'severity')
};
```

## Best Practices

1. **Always include workflow run ID** for traceability
   ```javascript
   const workflowRunId = `${workflowName}-${Date.now()}-${randomId()}`;
   ```

2. **Use structured failure details** for better debugging
   ```javascript
   failureDetails: {
     testName: 'api-health-check',
     expectedCode: 200,
     actualCode: 504,
     duration: 30000
   }
   ```

3. **Tag issues with workflow context**
   ```javascript
   labels: ['fleet-validation', 'agent-123', 'deployment-staging']
   ```

4. **Link fixes to original issues**
   ```javascript
   await updateIssueWithFix({
     issueNumber: 42,
     fixDetails: 'Applied database migration fix',
     commitShas: ['abc123']  // Always include commits
   });
   ```

5. **Test with dry run first**
   ```javascript
   // Test locally
   dryRun: true
   
   // Then enable in production
   dryRun: false
   ```

6. **Store workflow state in version control (optional)**
   - Track state file changes to monitor validation metrics
   - Or exclude from version control for privacy

7. **Set up notifications** on GitHub for auto-created issues
   - Create notification rule: label = "auto-created"
   - Route to Slack/email for visibility

## Troubleshooting

### Issue Not Created But No Error

**Cause:** GitHub CLI silently failed

**Debug:**
```bash
gh issue create --title "Test" --body "Test" 2>&1
```

### Issues Created But Not Linked to Workflow

**Cause:** `workflowRunId` not tracked properly

**Debug:**
```bash
cat .claude/workflow-issue-state.json | jq '.issues[0]'
```

### Can't Find Commits to Link

**Cause:** Commits haven't been pushed yet

**Solution:**
```javascript
// Push before creating issue
execSync('git push origin HEAD');
await updateIssueWithFix({
  issueNumber: 42,
  commitShas: [getLatestCommitSha()]
});
```

### Rate Limiting on Multiple Creates

**Cause:** Creating too many issues too fast

**Solution:**
```javascript
// Add delay between creates
for (const failure of failures) {
  await createValidationIssue({ /* ... */ });
  await new Promise(r => setTimeout(r, 1000));
}
```

## Testing

### Unit Tests

```bash
node validation-workflow-wrapper.js --test
```

### Integration Test

```bash
# 1. Test with dry run
node -e "
  const { createValidationIssue } = require('./github-issue-integration.js');
  createValidationIssue({
    title: 'Test',
    body: 'Test issue',
    severity: 'bug',
    workflowRunId: 'test-123',
    dryRun: true
  });
"

# 2. Test with real issue creation
gh issue create --title "Integration Test" --body "This is a test"
```

## Next Steps

1. Review `validation-workflow-example.js` for complete patterns
2. Update your validation workflows to use `wrapValidationWorkflow()`
3. Update your fix workflows to use `wrapFixWorkflow()`
4. Run validation workflow with `--dryRun` to test
5. Set up GitHub labels for better organization
6. Configure notifications for auto-created issues
7. Monitor `.claude/workflow-issue-state.json` for metrics

## API Summary

```javascript
// Create issue
const issue = await createValidationIssue(options);
// Returns: { number, url, title, severity, workflowRunId }

// Update issue with fix
await updateIssueWithFix({
  issueNumber,
  fixDetails,
  commitShas
});

// Close issue
await closeIssue({
  issueNumber,
  reason
});

// Link to workflow
await linkIssueToWorkflow({
  issueNumber,
  workflowRunId,
  workflowUrl
});

// Query state
const state = await getWorkflowState(workflowRunId);
// Returns: { issues, workflows }

// Wrap validation workflow
export default wrapValidationWorkflow(
  async () => { /* ... */ },
  { workflowName, trackIssues, autoCloseOnPass }
);

// Wrap fix workflow
export default wrapFixWorkflow(
  async (context) => { /* ... */ },
  { workflowName, trackIssues }
);
```
