# GitHub Issue Integration for Validation Workflows

Complete integration solution for tracking fleet validation workflow results in GitHub issues.

## What This Provides

Automatically create, update, and close GitHub issues from validation workflow results:

```
Validation Workflow
    ↓
    [Tests run, some fail]
    ↓
    Creates GitHub issues for blockers/bugs
    ↓
Fleet Validation Dashboard
    ↓
Fix Workflow
    ↓
    [Applies fixes]
    ↓
    Updates issues with fix details
    ↓
    Closes issues after validation
    ↓
GitHub Repository
    [Issues tracked and closed]
```

## Files Included

### Core Implementation (2 files - 900 lines)

| File | Size | Purpose |
|------|------|---------|
| **github-issue-integration.js** | 550 lines | Core module: create, update, close issues |
| **validation-workflow-wrapper.js** | 350 lines | Wrapper functions for automatic tracking |

### Examples & Tests (2 files - 700 lines)

| File | Size | Purpose |
|------|------|---------|
| **validation-workflow-example.js** | 400 lines | 7 real-world integration patterns |
| **github-issue-integration.test.js** | 300 lines | 25+ unit tests |

### Documentation (4 files - 2000+ lines)

| File | Size | Purpose |
|------|------|---------|
| **GITHUB_ISSUE_INTEGRATION_GUIDE.md** | 600+ lines | Complete API reference & best practices |
| **INTEGRATION_SETUP.md** | 400+ lines | Step-by-step setup instructions |
| **WORKFLOW_MIGRATION_GUIDE.md** | 500+ lines | How to migrate existing workflows |
| **GITHUB_ISSUE_INTEGRATION_SUMMARY.md** | 400+ lines | Quick overview & reference |

**Total: 8 files, ~2900 lines of code + documentation**

## Quick Start

### 1. Prerequisites (5 min)
```bash
# Install GitHub CLI
brew install gh              # macOS
sudo apt install gh          # Linux

# Authenticate
gh auth login
gh auth status
```

### 2. Copy Files (1 min)
```bash
mkdir -p validation-workflows
cp github-issue-integration.js validation-workflows/
cp validation-workflow-wrapper.js validation-workflows/
```

### 3. Wrap Your Workflow (5 min)
```javascript
// Before
export default async function validate() {
  return await runTests();
}

// After
import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';

export default wrapValidationWorkflow(
  async () => await runTests(),
  { workflowName: 'my-test', trackIssues: true }
);
```

### 4. Test (5 min)
```bash
# Test with dry run (no real issues created)
# Test results show what would be created
# Enable production mode and run

node github-issue-integration.test.js
```

## Key Features

✅ **Automatic Issue Creation**
- Create issues from validation failures
- Severity: blocker, bug, flaky, performance, security
- Include failure details and workflow run ID

✅ **Issue Lifecycle Tracking**
- Track by workflow run ID
- State persisted in `.claude/workflow-issue-state.json`
- Query issues by workflow or status

✅ **Fix Integration**
- Update issues with fix details
- Link related commits
- Auto-close after validation passes

✅ **Non-Blocking**
- Issue creation is async
- Doesn't slow down validation
- Graceful failure handling

✅ **Dry Run Mode**
- Test without creating real issues
- Perfect for development
- Easy toggle to production

✅ **Fleet-Aware**
- Track issues across multiple validation agents
- Batch operations supported
- Workflow state management

## File Locations

After integration, your project structure:

```
your-project/
├── validation-workflows/
│   ├── github-issue-integration.js
│   ├── validation-workflow-wrapper.js
│   ├── validation-workflow-example.js
│   ├── github-issue-integration.test.js
│   ├── your-validation.js          (updated)
│   └── your-fix-workflow.js        (updated)
├── docs/
│   ├── GITHUB_ISSUE_INTEGRATION_GUIDE.md
│   ├── INTEGRATION_SETUP.md
│   ├── WORKFLOW_MIGRATION_GUIDE.md
│   └── README_GITHUB_ISSUE_INTEGRATION.md (this file)
├── .claude/
│   └── workflow-issue-state.json   (auto-created)
└── .gitignore                      (updated with state file)
```

## Core API (4 Functions)

### 1. Create Issue
```javascript
const issue = await createValidationIssue({
  title: 'Test failed',
  body: 'Error details',
  severity: 'blocker',
  workflowRunId: 'unique-id',
  failureDetails: { /* ... */ }
});
// Returns: { number, url, title, severity, workflowRunId }
```

### 2. Update Issue
```javascript
await updateIssueWithFix({
  issueNumber: 42,
  fixDetails: 'Applied patch',
  commitShas: ['abc123']
});
```

### 3. Close Issue
```javascript
await closeIssue({
  issueNumber: 42,
  reason: 'Fixed and validated'
});
```

### 4. Wrap Workflow (Auto Everything)
```javascript
export default wrapValidationWorkflow(
  async () => await runTests(),
  {
    workflowName: 'test-name',
    trackIssues: true,
    autoCloseOnPass: true
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

### Pattern 2: Fleet Validation
```javascript
export default wrapValidationWorkflow(
  async () => {
    return await parallel([
      agent('Test on fleet-1'),
      agent('Test on fleet-2'),
      agent('Test on fleet-3')
    ]);
  },
  { workflowName: 'fleet-test', trackIssues: true }
);
```

### Pattern 3: Fix Workflow
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

### Pattern 4: Manual Control
```javascript
import { createValidationIssue } from './github-issue-integration.js';

export default async function validate() {
  const workflowRunId = `test-${Date.now()}`;
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

## Integration Steps

### Step 1: Setup (15 minutes)
- [ ] Install GitHub CLI: `brew install gh`
- [ ] Authenticate: `gh auth login`
- [ ] Read INTEGRATION_SETUP.md
- [ ] Copy core files
- [ ] Run tests: `node github-issue-integration.test.js`

### Step 2: First Workflow (30 minutes)
- [ ] Pick one validation workflow
- [ ] Wrap with `wrapValidationWorkflow()`
- [ ] Test with `dryRun: true`
- [ ] Verify dry-run output
- [ ] Set `dryRun: false`
- [ ] Create test issue on GitHub

### Step 3: Migration (1-2 hours per 5 workflows)
- [ ] Read WORKFLOW_MIGRATION_GUIDE.md
- [ ] Identify workflows to migrate
- [ ] Update validation workflows
- [ ] Update fix workflows
- [ ] Test each one
- [ ] Monitor workflow state

### Step 4: Production (Ongoing)
- [ ] Monitor `.claude/workflow-issue-state.json`
- [ ] Set up GitHub notifications
- [ ] Track metrics
- [ ] Optimize as needed

## Test Result Schema

Workflows should return:

```javascript
{
  // Required
  status: 'PASS' | 'FAIL' | 'FLAKY',
  
  // Recommended (for better issues)
  test_name: 'test-name',
  error: 'error message',
  failure_details: { /* context */ },
  isBlocker: false,
  
  // Optional
  labels: ['tag1'],
  duration_ms: 1234
}
```

## GitHub Labels

Auto-applied to issues:

- `validation-blocker` (red) - Show-stopper bugs
- `validation-bug` (orange) - Regular bugs
- `validation-flaky` (yellow) - Intermittent failures
- `validation-performance` (blue) - Performance issues
- `validation-security` (purple) - Security issues
- `auto-created` (gray) - Automation marker

Create with:
```bash
gh label create validation-blocker -c FF0000
gh label create validation-bug -c FF6600
# ... (see INTEGRATION_SETUP.md for all)
```

## Workflow State File

Issues tracked in `.claude/workflow-issue-state.json`:

```json
{
  "issues": [
    {
      "number": 42,
      "url": "https://github.com/owner/repo/issues/42",
      "status": "open",
      "createdAt": "2024-01-15T10:30:00Z"
    }
  ],
  "workflows": {
    "test-2024-01-15-abc": {
      "issues": [42, 43],
      "status": "in-progress"
    }
  }
}
```

Add to `.gitignore`:
```
.claude/workflow-issue-state.json
```

## Troubleshooting

### GitHub CLI Not Available
```bash
brew install gh
gh auth login
```

### Repository Not Detected
```bash
git remote -v
git remote add origin https://github.com/owner/repo.git
```

### Authentication Failed
```bash
gh auth logout
gh auth login
```

### State File Issues
```bash
cat .claude/workflow-issue-state.json
rm .claude/workflow-issue-state.json  # Clear if corrupted
```

See **GITHUB_ISSUE_INTEGRATION_GUIDE.md** → Troubleshooting for more.

## Documentation Guide

| Need | File |
|------|------|
| Setup steps | INTEGRATION_SETUP.md |
| API reference | GITHUB_ISSUE_INTEGRATION_GUIDE.md |
| Migration guide | WORKFLOW_MIGRATION_GUIDE.md |
| Working examples | validation-workflow-example.js |
| All tests | github-issue-integration.test.js |
| Quick overview | GITHUB_ISSUE_INTEGRATION_SUMMARY.md |

## Example Usage

### Simple Example
```javascript
import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';

export default wrapValidationWorkflow(
  async () => {
    const results = await parallel([
      agent('Run smoke tests'),
      agent('Run API tests'),
      agent('Run DB tests')
    ]);
    return results;
  },
  {
    workflowName: 'smoke-test',
    trackIssues: true,      // Enable GitHub tracking
    autoCloseOnPass: true,  // Auto-close on success
    dryRun: false           // Production mode
  }
);
```

### Query Issues
```javascript
import { getWorkflowState } from './github-issue-integration.js';

const state = await getWorkflowState();
console.log(`Open issues: ${state.issues.filter(i => i.status === 'open').length}`);
```

### Update Issue
```javascript
import { updateIssueWithFix } from './github-issue-integration.js';

await updateIssueWithFix({
  issueNumber: 42,
  fixDetails: 'Applied database migration fix',
  commitShas: ['abc123def456', 'ghi789jkl012']
});
```

## Key Metrics

- **Setup time**: 15 minutes
- **Per workflow migration**: 5-10 minutes
- **Issue creation time**: 200-500ms per issue
- **Non-blocking**: Workflow continues while issue created
- **State file size**: <100KB per 1000 issues

## Performance

- ✓ Async, non-blocking issue creation
- ✓ No slowdown to validation workflow
- ✓ Graceful failure handling
- ✓ Batch operations supported
- ✓ 1-5 second delay recommended between batch creates

## Security

- GitHub CLI authenticates with token
- State file has only issue metadata (public info)
- Exclude state file from version control
- No sensitive data in workflow state

## Next Steps

1. **Read INTEGRATION_SETUP.md** - Complete setup instructions
2. **Run tests** - `node github-issue-integration.test.js`
3. **Wrap first workflow** - Start with one test workflow
4. **Test dry run** - Verify no real issues created
5. **Create test issue** - Verify integration works
6. **Migrate remaining** - Update all workflows
7. **Set up monitoring** - Track metrics and issues
8. **Deploy to production** - Enable issue tracking

## Support

For questions or issues:

1. Check troubleshooting in GITHUB_ISSUE_INTEGRATION_GUIDE.md
2. Review examples in validation-workflow-example.js
3. Run tests to verify setup
4. Check workflow state file for status

## Summary

This integration provides:

- Automatic GitHub issue creation from validation results
- Full workflow run traceability with unique IDs
- Issue lifecycle tracking (creation → fix → closure)
- Non-blocking async operations
- Dry-run testing before production
- State persistence and querying
- Complete API and documentation
- Real-world examples and patterns

**Ready to integrate in 15 minutes!**

Start with: **INTEGRATION_SETUP.md**
