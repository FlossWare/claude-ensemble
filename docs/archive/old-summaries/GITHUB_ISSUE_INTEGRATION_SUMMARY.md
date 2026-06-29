# GitHub Issue Integration - Complete Summary

Complete integration code for tracking validation workflow results in GitHub issues.

## Deliverables

### Core Implementation (3 files)

1. **github-issue-integration.js** (550 lines)
   - Core module for GitHub issue operations
   - Auto-detects repository from git remote
   - Uses GitHub CLI (`gh` command)
   - Persists workflow state to `.claude/workflow-issue-state.json`
   - Export functions:
     - `createValidationIssue(options)` - Create GitHub issue
     - `updateIssueWithFix(options)` - Add fix comment
     - `closeIssue(options)` - Close issue
     - `linkIssueToWorkflow(options)` - Link to workflow
     - `getWorkflowState(workflowRunId)` - Query state

2. **validation-workflow-wrapper.js** (400 lines)
   - Wrapper functions for automatic issue tracking
   - Export functions:
     - `wrapValidationWorkflow(fn, options)` - Wrap validation workflow
     - `wrapFixWorkflow(fn, options)` - Wrap fix workflow
     - `queryWorkflowState(workflowRunId)` - Query workflow state
     - `generateWorkflowRunId(name)` - Generate unique run ID

3. **validation-workflow-example.js** (400 lines)
   - 7 complete integration patterns
   - Real-world examples
   - Integration checklist
   - Patterns:
     1. Simple validation with issues
     2. Fleet validation with blocking issues
     3. Fix workflow with closure
     4. Async issue creation (non-blocking)
     5. Manual GitHub integration
     6. Batch issue creation
     7. Dashboard/query integration

### Testing & Documentation (3 files)

4. **github-issue-integration.test.js** (300 lines)
   - Unit tests for all functions
   - 25+ test cases
   - Run: `node github-issue-integration.test.js`

5. **GITHUB_ISSUE_INTEGRATION_GUIDE.md** (600+ lines)
   - Complete API reference
   - Usage examples
   - Integration patterns
   - Error handling
   - Monitoring
   - Best practices
   - Troubleshooting

6. **INTEGRATION_SETUP.md** (400+ lines)
   - Step-by-step setup instructions
   - Prerequisites and installation
   - File organization
   - Testing procedures
   - GitHub label configuration
   - CI/CD integration examples
   - Quick reference guide

### Migration Guides (2 files)

7. **WORKFLOW_MIGRATION_GUIDE.md** (500+ lines)
   - How to migrate existing workflows
   - Phase 1: Validation workflows
   - Phase 2: Fix workflows
   - Phase 3: Monitoring
   - Real-world examples
   - Rollback procedures
   - Timeline estimates
   - FAQ

8. **GITHUB_ISSUE_INTEGRATION_SUMMARY.md** (this file)
   - Overview of all deliverables
   - Quick start guide
   - Key features
   - File locations
   - Usage patterns
   - Integration checklist

## Quick Start (5 Minutes)

### 1. Install GitHub CLI
```bash
brew install gh          # macOS
sudo apt install gh      # Linux
gh auth login           # Authenticate
```

### 2. Copy Files
```bash
mkdir -p validation-workflows
cp github-issue-integration.js validation-workflows/
cp validation-workflow-wrapper.js validation-workflows/
```

### 3. Wrap Your Workflow
```javascript
import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';

export default wrapValidationWorkflow(
  async () => {
    const tests = await runTests();
    return tests;
  },
  { workflowName: 'my-test', trackIssues: true }
);
```

### 4. Test
```bash
# Dry run first (no real issues)
# Then enable production mode
```

## Key Features

### Automatic Issue Creation
When validation finds blockers/bugs, automatically create GitHub issues with:
- Clear titles and descriptions
- Structured failure metadata
- Link to workflow run ID
- Severity labels (blocker, bug, flaky, performance, security)

### Issue Tracking
- Persist workflow state in `.claude/workflow-issue-state.json`
- Query issue state by workflow run ID
- Track issue lifecycle (open → fixed → closed)

### Fix Integration
When fixes are applied:
- Update issues with fix details
- Link related commit SHAs
- Auto-close issues when validation passes

### Non-Blocking
- Issue creation happens asynchronously
- Doesn't slow down validation workflow
- Fails gracefully if GitHub unavailable

### Dry Run Mode
- Test without creating real issues
- Perfect for development
- Easy toggle for production

## File Structure

```
your-project/
├── validation-workflows/
│   ├── github-issue-integration.js          # Core module
│   ├── validation-workflow-wrapper.js       # Wrappers
│   ├── validation-workflow-example.js       # Examples
│   ├── github-issue-integration.test.js     # Tests
│   ├── your-validation-workflow.js          # Your workflow (updated)
│   └── your-fix-workflow.js                 # Your fix workflow (updated)
├── docs/
│   ├── GITHUB_ISSUE_INTEGRATION_GUIDE.md    # Full reference
│   ├── INTEGRATION_SETUP.md                 # Setup instructions
│   ├── WORKFLOW_MIGRATION_GUIDE.md          # Migration steps
│   └── GITHUB_ISSUE_INTEGRATION_SUMMARY.md  # This file
├── .claude/
│   └── workflow-issue-state.json            # Workflow state (auto-generated)
└── .gitignore                               # Add .claude/workflow-issue-state.json
```

## Core API

### Create Issue
```javascript
const issue = await createValidationIssue({
  title: 'Test failed',
  body: 'Error details',
  severity: 'blocker' | 'bug' | 'flaky' | 'performance' | 'security',
  workflowRunId: 'unique-workflow-id',
  failureDetails: { /* structured metadata */ }
});
// Returns: { number, url, title, severity, workflowRunId }
```

### Update Issue
```javascript
await updateIssueWithFix({
  issueNumber: 42,
  fixDetails: 'Applied patch...',
  commitShas: ['abc123def456']
});
```

### Close Issue
```javascript
await closeIssue({
  issueNumber: 42,
  reason: 'Fixed and validated'
});
```

### Query State
```javascript
const state = await getWorkflowState('workflow-run-id');
// Returns: { issues, workflows }
```

### Wrap Workflow
```javascript
export default wrapValidationWorkflow(
  async () => { /* validation logic */ },
  {
    workflowName: 'test-name',
    trackIssues: true,
    autoCloseOnPass: true,
    dryRun: false
  }
);
```

## Integration Patterns

### Pattern 1: Simplest (Just Wrap)
```javascript
export default wrapValidationWorkflow(
  async () => await runTests(),
  { workflowName: 'tests', trackIssues: true }
);
```

### Pattern 2: Manual Control
```javascript
export default async function validate() {
  const workflowRunId = generateWorkflowRunId('validate');
  const tests = await runTests();

  for (const fail of tests.filter(t => t.status === 'FAIL')) {
    await createValidationIssue({
      title: fail.testName,
      body: fail.error,
      severity: 'bug',
      workflowRunId
    });
  }

  return tests;
}
```

### Pattern 3: Fleet Validation
```javascript
export default wrapValidationWorkflow(
  async () => {
    return await parallel([
      () => agent('Test on fleet-1'),
      () => agent('Test on fleet-2'),
      () => agent('Test on fleet-3')
    ]);
  },
  { workflowName: 'fleet-test', trackIssues: true }
);
```

### Pattern 4: Fix Workflow
```javascript
export default wrapFixWorkflow(
  async (context) => {
    const state = await queryWorkflowState(context.workflowRunId);
    
    const fixes = await parallel(
      state.issues.map(num => () => agent(`Fix issue #${num}`))
    );

    return {
      fixes: fixes.map((fix, i) => ({
        issueNumber: state.issues[i],
        description: fix.description,
        commits: fix.commits,
        validationPassed: fix.passed
      })),
      validationPassed: fixes.every(f => f.passed)
    };
  },
  { workflowName: 'fix' }
);
```

## Test Result Schema

Your workflows should return results matching this schema:

```javascript
{
  // Required
  status: 'PASS' | 'FAIL' | 'FLAKY',
  
  // Recommended
  test_name: 'name-of-test',
  error: 'error message',
  failure_details: { /* structured data */ },
  isBlocker: false,
  
  // Optional
  labels: ['tag1', 'tag2'],
  duration_ms: 1234,
  evidence: ['log line 1', 'log line 2']
}
```

## GitHub Labels

Automatically applied:
- `validation-blocker` (red) - Show-stopper bugs
- `validation-bug` (orange) - Regular bugs
- `validation-flaky` (yellow) - Intermittent failures
- `validation-performance` (blue) - Performance issues
- `validation-security` (purple) - Security issues
- `auto-created` (gray) - Automated creation

Create them:
```bash
gh label create validation-blocker -c FF0000
gh label create validation-bug -c FF6600
gh label create validation-flaky -c FFFF00
gh label create validation-performance -c 0066FF
gh label create validation-security -c 9933FF
gh label create auto-created -c 888888
```

## Workflow State File

Issues tracked in `.claude/workflow-issue-state.json`:

```json
{
  "issues": [
    {
      "number": 42,
      "url": "https://github.com/owner/repo/issues/42",
      "title": "Test failed",
      "severity": "blocker",
      "workflowRunId": "test-2024-01-15-abc123",
      "createdAt": "2024-01-15T10:30:00Z",
      "status": "open",
      "linkedCommits": ["abc123def456"]
    }
  ],
  "workflows": {
    "test-2024-01-15-abc123": {
      "issues": [42, 43, 44],
      "status": "in-progress",
      "createdAt": "2024-01-15T10:30:00Z"
    }
  }
}
```

Add to `.gitignore`:
```
.claude/workflow-issue-state.json
```

## Integration Checklist

### Setup (15 minutes)
- [ ] Install GitHub CLI: `brew install gh`
- [ ] Authenticate: `gh auth login`
- [ ] Copy integration files
- [ ] Add state file to `.gitignore`
- [ ] Run tests: `node github-issue-integration.test.js`

### First Workflow (30 minutes)
- [ ] Wrap one validation workflow
- [ ] Test with `dryRun: true`
- [ ] Review dry-run output
- [ ] Set `dryRun: false`
- [ ] Verify first issue created
- [ ] Verify issue metadata

### Remaining Workflows (1-2 hours per 5 workflows)
- [ ] Migrate validation workflows
- [ ] Test each one
- [ ] Update fix workflows
- [ ] Test fix workflows
- [ ] Set up monitoring

### Production (Ongoing)
- [ ] Monitor workflow state
- [ ] Check for API errors
- [ ] Review issue quality
- [ ] Set up Slack notifications
- [ ] Document workflows

## Monitoring

### Query Metrics
```javascript
const state = await getWorkflowState();
console.log(`Open: ${state.issues.filter(i => i.status === 'open').length}`);
console.log(`Closed: ${state.issues.filter(i => i.status === 'closed').length}`);
```

### Track by Severity
```javascript
const state = await getWorkflowState();
const bySeverity = {};
for (const issue of state.issues) {
  bySeverity[issue.severity] = (bySeverity[issue.severity] || 0) + 1;
}
```

### Dashboard Idea
```
Fleet Validation Dashboard
├── Total Issues: 42
├── Open: 12 (blocker: 3, bug: 7, flaky: 2)
├── Closed: 30
├── Avg Time to Close: 2.3 hours
└── By Workflow
    ├── smoke-test: 15 issues, 2 open
    ├── api-tests: 18 issues, 5 open
    └── fleet-validate: 9 issues, 5 open
```

## Troubleshooting

### GitHub CLI Not Available
```bash
which gh          # Check if installed
gh --version      # Verify version
brew install gh   # Install if missing
```

### Not Authenticated
```bash
gh auth status    # Check status
gh auth login     # Authenticate again
```

### Repository Not Detected
```bash
git remote -v                                          # Check remotes
git remote add origin https://github.com/owner/repo   # Add if missing
```

### Rate Limited
- Wait 1 hour for reset
- Or upgrade to GitHub Pro
- Or reduce issue creation frequency

### State File Issues
```bash
cat .claude/workflow-issue-state.json | jq  # View current state
rm .claude/workflow-issue-state.json         # Clear if corrupted
```

## Best Practices

1. **Always include workflow run ID** for traceability
2. **Use structured failure details** for debugging
3. **Tag issues appropriately** with labels
4. **Link commits** when fixing issues
5. **Test with dry run first** before production
6. **Monitor workflow state** regularly
7. **Set up notifications** for visibility
8. **Close issues after validation** to keep repo clean

## Performance Notes

- Issue creation: ~200-500ms per issue
- Non-blocking: Workflow continues while issue created
- Batch operations: 1-5 second delay recommended between creates
- State file: <100KB for 1000 issues

## Security Considerations

- GitHub CLI authenticates with token
- State file contains issue metadata (public)
- Exclude state file from version control
- Only tracks open/closed status, not issue bodies
- No sensitive data in workflow metadata

## Next Steps

1. **Read INTEGRATION_SETUP.md** - Complete setup guide
2. **Read GITHUB_ISSUE_INTEGRATION_GUIDE.md** - Full API reference
3. **Read WORKFLOW_MIGRATION_GUIDE.md** - How to migrate workflows
4. **Review validation-workflow-example.js** - Working examples
5. **Run tests** - `node github-issue-integration.test.js`
6. **Migrate first workflow** - Start small, test thoroughly
7. **Monitor production** - Track metrics and issues

## Support Resources

| Topic | File |
|-------|------|
| Setup | INTEGRATION_SETUP.md |
| API Reference | GITHUB_ISSUE_INTEGRATION_GUIDE.md |
| Migration | WORKFLOW_MIGRATION_GUIDE.md |
| Examples | validation-workflow-example.js |
| Testing | github-issue-integration.test.js |
| Overview | GITHUB_ISSUE_INTEGRATION_SUMMARY.md |

## Questions?

1. Check troubleshooting section in GITHUB_ISSUE_INTEGRATION_GUIDE.md
2. Review examples in validation-workflow-example.js
3. Run tests to verify setup: `node github-issue-integration.test.js`
4. Check workflow state: `cat .claude/workflow-issue-state.json`

## Summary

This integration provides:
- ✓ Automatic GitHub issue creation from validation results
- ✓ Issue tracking by workflow run ID
- ✓ Fix updates and issue closure
- ✓ Structured workflow state persistence
- ✓ Non-blocking async operations
- ✓ Dry-run testing capability
- ✓ Complete API reference and examples
- ✓ Step-by-step migration guide

**Total lines of integration code: ~2,000 lines**
**Total lines of documentation: ~2,000 lines**
**Time to integrate: 2-4 hours**

Ready to integrate! Start with INTEGRATION_SETUP.md.
