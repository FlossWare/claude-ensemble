# GitHub Issue Integration - Setup & Migration Guide

Complete step-by-step guide to integrate GitHub issue tracking into your validation workflows.

## Files Provided

1. **github-issue-integration.js** (550 lines)
   - Core module for GitHub issue operations
   - Location: `/validation-workflows/github-issue-integration.js`

2. **validation-workflow-wrapper.js** (400 lines)
   - Wrapper functions for automatic issue tracking
   - Location: `/validation-workflows/validation-workflow-wrapper.js`

3. **validation-workflow-example.js** (400 lines)
   - 7 complete integration patterns with examples
   - Location: `/validation-workflows/validation-workflow-example.js`

4. **github-issue-integration.test.js** (300 lines)
   - Unit tests for the integration module
   - Location: `/validation-workflows/github-issue-integration.test.js`

5. **GITHUB_ISSUE_INTEGRATION_GUIDE.md**
   - Complete API reference and best practices
   - Location: `/docs/GITHUB_ISSUE_INTEGRATION_GUIDE.md`

6. **INTEGRATION_SETUP.md** (this file)
   - Step-by-step setup instructions
   - Location: `/docs/INTEGRATION_SETUP.md`

## Prerequisites

### 1. GitHub CLI Installation

```bash
# macOS
brew install gh

# Linux (Ubuntu/Debian)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Windows (Chocolatey)
choco install gh

# Verify
gh --version
```

### 2. GitHub Authentication

```bash
# Log in to GitHub
gh auth login

# Select:
# ? What is your preferred protocol for Git operations? > HTTPS
# ? Authenticate with your GitHub credentials? > Y
# ? How would you like to authenticate GitHub CLI? > Paste an authentication token
# (create token at https://github.com/settings/tokens)

# Verify
gh auth status
```

### 3. Git Repository

Ensure your project is in a git repository with GitHub as remote:

```bash
cd /path/to/project

# If not a git repo
git init
git remote add origin https://github.com/owner/repo.git

# Verify
git remote -v
# origin  https://github.com/owner/repo.git (fetch)
# origin  https://github.com/owner/repo.git (push)
```

## Step 1: Install Files

Copy the integration files to your project:

```bash
# Create validation workflows directory if not exists
mkdir -p validation-workflows

# Copy core modules
cp github-issue-integration.js validation-workflows/
cp validation-workflow-wrapper.js validation-workflows/
cp validation-workflow-example.js validation-workflows/
cp github-issue-integration.test.js validation-workflows/

# Copy documentation
mkdir -p docs
cp GITHUB_ISSUE_INTEGRATION_GUIDE.md docs/
cp INTEGRATION_SETUP.md docs/
```

## Step 2: Run Tests

Verify the integration module works:

```bash
cd validation-workflows
node github-issue-integration.test.js
```

Expected output:
```
============================================================
Tests: 25 passed, 0 failed
============================================================

All tests passed!
```

## Step 3: Configure .gitignore

Add workflow state file to `.gitignore`:

```bash
# Add to .gitignore
echo ".claude/workflow-issue-state.json" >> .gitignore

# Or manually edit .gitignore and add:
# .claude/workflow-issue-state.json
```

## Step 4: Create GitHub Labels (Optional but Recommended)

```bash
# Create validation labels
gh label create validation-blocker -c FF0000 -d "Show-stopper bug blocking deployment"
gh label create validation-bug -c FF6600 -d "Regular bug found by validation"
gh label create validation-flaky -c FFFF00 -d "Intermittent failure"
gh label create validation-performance -c 0066FF -d "Performance degradation"
gh label create validation-security -c 9933FF -d "Security issue found"
gh label create auto-created -c 888888 -d "Automatically created by fleet validation"
```

## Step 5: Migrate Existing Validation Workflows

### Before (Original Workflow)

```javascript
// code-smoke-test.js
export const meta = {
  name: 'code-smoke-test',
  description: 'Run smoke tests'
};

export default async function smokeTest() {
  const results = await runTests();
  return results;
}
```

### After (With GitHub Integration)

```javascript
// code-smoke-test.js
import {
  wrapValidationWorkflow
} from './validation-workflow-wrapper.js';

export const meta = {
  name: 'code-smoke-test',
  description: 'Run smoke tests and track issues on GitHub'
};

export default wrapValidationWorkflow(
  async () => {
    const results = await runTests();
    return results;
  },
  {
    workflowName: 'smoke-test',
    trackIssues: true,           // Enable GitHub integration
    autoCloseOnPass: true,       // Auto-close issues on success
    dryRun: false                // Set to true for testing
  }
);
```

### Checklist for Each Workflow

- [ ] Import `wrapValidationWorkflow` or integration functions
- [ ] Ensure test results have proper schema:
  - `status` (required): 'PASS' | 'FAIL'
  - `testName` (recommended): name of the test
  - `error` (optional): error message
  - `failure_details` (optional): structured details
  - `isBlocker` (optional): true if show-stopper
  - `labels` (optional): additional GitHub labels

## Step 6: Test Integration

### Test 1: Dry Run (No Real Issues)

```javascript
// test-validation-dry-run.js
import {
  wrapValidationWorkflow
} from './validation-workflow-wrapper.js';

const testWorkflow = wrapValidationWorkflow(
  async () => {
    return [
      { status: 'PASS', testName: 'test-1' },
      { status: 'FAIL', testName: 'test-2', error: 'Test error' }
    ];
  },
  {
    workflowName: 'test-validation',
    trackIssues: true,
    dryRun: true  // Dry run - no actual issues created
  }
);

// Run it
const result = await testWorkflow();
console.log(JSON.stringify(result, null, 2));
```

Expected output shows issue metadata without creating real issues:
```
[DRY RUN] Would create GitHub issue:
  Title: Test validation: test-2
  Labels: validation-bug, auto-created
  Body length: 250 chars
```

### Test 2: Create Real Issue

```javascript
// test-validation-real.js
import {
  createValidationIssue
} from './github-issue-integration.js';

const issue = await createValidationIssue({
  title: 'Integration Test: Sample Validation Failure',
  body: 'This is a test issue created by the integration setup.',
  severity: 'bug',
  workflowRunId: `setup-test-${Date.now()}`,
  failureDetails: {
    test: 'setup-validation',
    timestamp: new Date().toISOString()
  },
  labels: ['integration-test']
});

console.log(`✓ Created issue #${issue.number}: ${issue.url}`);
```

Run it:
```bash
node test-validation-real.js
```

Verify:
1. Issue appears in GitHub
2. Has correct title and labels
3. Contains metadata and workflow run ID
4. Can be manually closed for cleanup

## Step 7: Update Fix Workflows

### Before (Original Fix Workflow)

```javascript
// fix-failed-tests.js
export default async function fixFailedTests(context) {
  const fixes = await applyFixes();
  return { fixed: fixes.length };
}
```

### After (With Issue Tracking)

```javascript
// fix-failed-tests.js
import {
  wrapFixWorkflow,
  queryWorkflowState
} from './validation-workflow-wrapper.js';

export default wrapFixWorkflow(
  async (context) => {
    const { workflowRunId } = context || {};
    
    if (!workflowRunId) {
      throw new Error('Fix workflow requires workflowRunId from validation');
    }

    // Get issues from validation workflow
    const state = await queryWorkflowState(workflowRunId);
    
    if (!state.issues || state.issues.length === 0) {
      return { fixes: [], validationPassed: true };
    }

    // Apply fixes
    const fixes = await parallel(
      state.issues.map(issueNum => () =>
        agent(`Fix issue #${issueNum}`)
      )
    );

    return {
      fixes: fixes.map((fix, i) => ({
        issueNumber: state.issues[i],
        description: fix.description || 'Applied fix',
        commits: fix.commits || [],
        validationPassed: fix.validationPassed === true
      })),
      validationPassed: fixes.every(f => f.validationPassed)
    };
  },
  {
    workflowName: 'fix-tests',
    trackIssues: true
  }
);
```

## Step 8: Set Up Notification Rules (Optional)

### GitHub Web UI

1. Go to Settings → Notifications
2. Custom routing → New rule
3. Notification filters:
   - Label = "auto-created"
   - Label = "validation-blocker"
4. Routing: Send to Slack/Email

### Example Slack Integration

```bash
# Via GitHub Actions
on:
  issues:
    types: [opened]
    
jobs:
  notify:
    if: contains(github.event.issue.labels.*.name, 'auto-created')
    runs-on: ubuntu-latest
    steps:
      - name: Notify Slack
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "New validation issue: ${{ github.event.issue.title }}",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Fleet Validation Alert*\n${{ github.event.issue.title }}\n<${{ github.event.issue.html_url }}|View Issue>"
                  }
                }
              ]
            }
```

## Step 9: Document Workflow Run IDs

Create a shared document mapping workflow runs to issues:

**Example: workflow-run-log.json**
```json
{
  "smoke-test-2024-01-15-abc123": {
    "startTime": "2024-01-15T10:30:00Z",
    "endTime": "2024-01-15T10:35:00Z",
    "status": "FAIL",
    "issues": [42, 43, 44],
    "url": "https://github.com/owner/repo/actions/runs/12345"
  }
}
```

Or query programmatically:
```javascript
import { getWorkflowState } from './github-issue-integration.js';

const state = await getWorkflowState();
console.log(JSON.stringify(state, null, 2));
```

## Step 10: Configure CI/CD Integration (Optional)

### GitHub Actions Example

```yaml
# .github/workflows/validate-and-track.yml
name: Validate & Track Issues

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install dependencies
        run: npm install
      
      - name: Run validation with issue tracking
        run: node validation-workflows/run-validation.js
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Comment on PR
        if: always()
        uses: actions/github-script@v6
        with:
          script: |
            const state = require('./validation-workflows/get-workflow-state.js');
            const issues = await state.getOpenIssues();
            
            const comment = issues.length > 0
              ? `Found ${issues.length} validation issues:\n${issues.map(i => `- #${i.number}`).join('\n')}`
              : 'All validation checks passed!';
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

## Troubleshooting

### Issue: "GitHub CLI (gh) not available"

```bash
# Verify installation
which gh
gh --version

# Re-install if needed
brew install gh  # macOS
# or
sudo apt install gh  # Linux
```

### Issue: "Could not detect GitHub repository"

```bash
# Verify git remote
git remote -v

# Add if missing
git remote add origin https://github.com/owner/repo.git

# Verify it's correct
git remote set-url origin https://github.com/owner/repo.git
```

### Issue: "HTTP 403 Forbidden"

```bash
# Check authentication
gh auth status

# Re-authenticate
gh auth logout
gh auth login
```

### Issue: "Rate limit exceeded"

GitHub API rate limit: 60 requests/hour (unauthenticated) or 5000/hour (authenticated)

Solutions:
- Authenticate with personal access token (already done by default)
- Batch issue creation with delays:
  ```javascript
  for (const failure of failures) {
    await createValidationIssue({ /* ... */ });
    await new Promise(r => setTimeout(r, 1000));  // 1 second delay
  }
  ```

### Issue: "Workflow state file permission denied"

```bash
# Check file permissions
ls -la .claude/

# Create directory if missing
mkdir -p .claude

# Set correct permissions
chmod 755 .claude
```

## Next Steps

1. **Update validation workflows** - Wrap with `wrapValidationWorkflow()`
2. **Update fix workflows** - Wrap with `wrapFixWorkflow()`
3. **Run with dry run** - Test without creating real issues
4. **Create test issue** - Verify integration works
5. **Monitor workflow state** - Check `.claude/workflow-issue-state.json`
6. **Set up notifications** - Configure Slack/email alerts
7. **Document workflows** - Update README with issue tracking info
8. **Archive examples** - Keep `validation-workflow-example.js` for reference

## Documentation References

- **API Reference**: See `GITHUB_ISSUE_INTEGRATION_GUIDE.md`
- **Code Examples**: See `validation-workflow-example.js`
- **Integration Patterns**: See section "Integration Patterns" in guide
- **Best Practices**: See section "Best Practices" in guide

## Migration Checklist

- [ ] Install GitHub CLI and authenticate
- [ ] Add files to version control (except state JSON)
- [ ] Update `.gitignore` to exclude workflow state
- [ ] Create GitHub labels (optional)
- [ ] Test with dry run on one workflow
- [ ] Migrate first validation workflow
- [ ] Test issue creation and closure
- [ ] Migrate fix workflow
- [ ] Set up notifications (optional)
- [ ] Update project documentation
- [ ] Train team on new workflow
- [ ] Monitor in production

## Support

For issues or questions:

1. Check `GITHUB_ISSUE_INTEGRATION_GUIDE.md` → Troubleshooting section
2. Review `validation-workflow-example.js` for usage patterns
3. Run tests: `node github-issue-integration.test.js`
4. Check workflow state: `cat .claude/workflow-issue-state.json`

## Quick Reference

```javascript
// Create issue
const issue = await createValidationIssue({
  title: 'Validation failed',
  body: 'Error details...',
  severity: 'blocker',
  workflowRunId: 'run-123'
});

// Update issue with fix
await updateIssueWithFix({
  issueNumber: issue.number,
  fixDetails: 'Applied fix...',
  commitShas: ['abc123']
});

// Close issue
await closeIssue({
  issueNumber: issue.number,
  reason: 'Fixed and validated'
});

// Query state
const state = await getWorkflowState('run-123');

// Wrap workflow
export default wrapValidationWorkflow(
  async () => { /* validation logic */ },
  { workflowName: 'smoke-test', trackIssues: true }
);
```
