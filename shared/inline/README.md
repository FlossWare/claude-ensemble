# Inline Functions Guide

**Purpose**: Copy-paste ready functions for workflows (workflows can't use `import` with scriptPath)

## Why Inline?

Workflows invoked via `scriptPath` cannot use ES6 `import` statements. To reuse code:
1. Copy functions from this directory into your workflow
2. Workflow remains self-contained
3. scriptPath invocation works

## Available Modules

### 1. platform-detector.js
Platform detection and issue operations (GitHub/GitLab/Bitbucket)

**Functions**:
- `detectPlatform(agent)` - Auto-detect platform
- `listIssues(agent, platform, state, limit)` - List issues
- `createIssue(agent, platform, title, body, labels)` - Create issue
- `reopenIssue(agent, platform, number, comment)` - Reopen issue  
- `closeIssue(agent, platform, number, comment)` - Close issue
- `commentOnIssue(agent, platform, number, comment)` - Add comment
- `updateLabels(agent, platform, number, add, remove)` - Update labels

**Usage**:
```javascript
// Copy the functions into your workflow, then:
const platform = await detectPlatform(agent)
const issues = await listIssues(agent, platform, 'open', 100)
```

### 2. git-operations.js
Common git operations

**Functions**:
- `getCommitHistory(agent, days, limit)` - Recent commits
- `getDiff(agent, hash)` - Commit diff
- `getCurrentBranch(agent)` - Current branch
- `getRemoteUrl(agent)` - Remote URL
- `findSourceFiles(agent, patterns, exclude, limit)` - Find files
- `getFileHistory(agent, filepath, limit)` - File history
- `getBlame(agent, filepath)` - Git blame
- `getStatus(agent)` - Working tree status
- `hasUncommittedChanges(agent)` - Check uncommitted

**Usage**:
```javascript
// Copy the functions into your workflow, then:
const history = await getCommitHistory(agent, 30, 50)
const files = await findSourceFiles(agent, ['*.js'], ['node_modules'], 100)
```

### 3. schemas.js
JSON schemas for structured agent output

**Schemas**:
- `ISSUE_SCHEMA` - Individual issue
- `FINDING_SCHEMA` - List of issues
- `REVIEW_SCHEMA` - Review result
- `ARBITER_SCHEMA` - Arbiter decision
- `FIX_SCHEMA` - Proposed fix
- `PR_REVIEW_SCHEMA` - PR review
- `COMMIT_HISTORY_SCHEMA` - Git commits
- `DIFF_SCHEMA` - Git diff
- `PLATFORM_SCHEMA` - Platform info
- `ISSUE_LIST_SCHEMA` - Issue list
- `ISSUE_CREATE_SCHEMA` - Created issue

**Usage**:
```javascript
// Copy the schemas into your workflow, then:
const result = await agent('Find bugs', {
  schema: FINDING_SCHEMA
})
```

### 4. ai-attribution.js
AI transparency and attribution (see parent directory)

**Functions**:
- `createThresholdAttribution(...)` - Threshold-based attribution
- `createArbiterAttribution(...)` - Arbiter-based attribution
- `formatThresholdAttributionMarkdown(...)` - Format as markdown
- `formatArbiterAttributionMarkdown(...)` - Format arbiter markdown

**Usage**: See `../ai-attribution.js` for inline code block

## How to Use

### Step 1: Copy Functions

Open the module you need and copy the functions into your workflow:

```javascript
export const meta = { ... }

// ============================================================================
// INLINE FUNCTIONS (copied from shared/inline/platform-detector.js)
// ============================================================================

async function detectPlatform(agent) {
  // ... (copied code)
}

async function listIssues(agent, platform, state, limit = 100) {
  // ... (copied code)
}

// ============================================================================
// WORKFLOW CODE
// ============================================================================

const platform = await detectPlatform(agent)
log(`Platform: ${platform.platform}`)
```

### Step 2: Use in Your Workflow

```javascript
// Platform detection
const platform = await detectPlatform(agent)

if (platform.isGitHub) {
  log('Running on GitHub')
} else if (platform.isGitLab) {
  log('Running on GitLab')
}

// List open issues
const openIssues = await listIssues(agent, platform, 'open', 50)
log(`Found ${openIssues.length} open issues`)

// Create issue with attribution
const attribution = createThresholdAttribution({ ... })
const markdown = formatThresholdAttributionMarkdown(attribution)

await createIssue(agent, platform,
  '[BUG] Issue title',
  `Description\n\n${markdown}`,
  ['bug', 'automated']
)
```

## Complete Example

```javascript
export const meta = {
  name: 'my-workflow',
  description: 'Example workflow using inline functions',
  phases: [
    { title: 'Setup', detail: 'Detect platform' },
    { title: 'Review', detail: 'Find issues' },
    { title: 'Report', detail: 'Create issues' }
  ]
}

// ============================================================================
// INLINE FUNCTIONS
// ============================================================================

// Copy detectPlatform, listIssues, createIssue from platform-detector.js
// Copy ISSUE_SCHEMA, FINDING_SCHEMA from schemas.js
// Copy getCommitHistory, findSourceFiles from git-operations.js

// ============================================================================
// WORKFLOW
// ============================================================================

phase('Setup')

const platform = await detectPlatform(agent)
log(`Platform: ${platform.platform}`)

phase('Review')

const history = await getCommitHistory(agent, 7, 10)
log(`Reviewing ${history.total_commits} commits`)

const findings = []

for (const commit of history.commits.slice(0, 5)) {
  const result = await agent(`Review commit ${commit.hash}`, {
    schema: FINDING_SCHEMA
  })
  
  findings.push(...result.issues)
}

log(`Found ${findings.length} issues`)

phase('Report')

for (const issue of findings) {
  await createIssue(agent, platform,
    `[${issue.severity.toUpperCase()}] ${issue.category}`,
    issue.description,
    ['bug', 'automated', issue.severity]
  )
}

log(`Created ${findings.length} issues`)
```

## Pattern: Multi-AI with Attribution

```javascript
// Copy createThresholdAttribution, formatThresholdAttributionMarkdown

const models = ['opus', 'sonnet', 'haiku']
const THRESHOLD = 70

// Collect proposals from all models
const allProposals = []

const reviews = await parallel(models.map(model =>
  () => agent('Find bugs', {
    model: model,
    schema: FINDING_SCHEMA
  })
))

// Tag proposals
reviews.forEach((review, idx) => {
  review.issues?.forEach(issue => {
    allProposals.push({
      model: models[idx],
      finding: issue,
      accepted: issue.confidence >= THRESHOLD,
      rejection_reason: issue.confidence < THRESHOLD
        ? `Confidence ${issue.confidence}% below threshold ${THRESHOLD}%`
        : null
    })
  })
})

// Add attribution to accepted findings
allProposals.filter(p => p.accepted).forEach(proposal => {
  const attribution = createThresholdAttribution({
    workerModel: proposal.model,
    confidence: proposal.finding.confidence,
    reasoning: proposal.finding.description,
    threshold: THRESHOLD,
    allProposals: allProposals,
    totalModels: models.length
  })

  const markdown = formatThresholdAttributionMarkdown(attribution)

  // Create issue with full attribution
  await createIssue(agent, platform,
    `[${proposal.finding.severity}] ${proposal.finding.category}`,
    `${proposal.finding.description}\n\n---\n\n${markdown}`,
    ['bug', proposal.finding.severity]
  )
})
```

## Best Practices

1. **Copy what you need** - Don't copy all functions, only what you use
2. **Keep functions together** - Put all inline functions in one section
3. **Comment the source** - Note where functions came from for future reference
4. **Update periodically** - Check shared/inline/ for improvements
5. **Test after copying** - Validate syntax with `node --check workflow.js`

## Updating Inline Functions

When shared/inline/ modules are updated:

1. Check the git diff to see what changed
2. Copy the updated functions into your workflow
3. Test your workflow
4. Commit the update

## Reference Implementation

See parent directory (`../`) for the original modules with full documentation:
- `../platform-detector.js` - Platform detection with exports
- `../schemas.js` - All schemas with exports
- `../ai-attribution.js` - AI attribution (has inline block)
- `../consensus-engine.js` - Consensus algorithms
- `../work-coordinator.js` - Work coordination

## Migration Guide

### Before (duplicated code):
```javascript
const platformDetect = await agent(`Detect platform.
Execute:
if git remote -v | grep -q 'github.com'; then echo "github"
elif git remote -v | grep -q 'gitlab'; then echo "gitlab"
...`, {schema})

const isGitHub = platformDetect.platform === 'github'
```

### After (using inline):
```javascript
// Copy detectPlatform from shared/inline/platform-detector.js
const platform = await detectPlatform(agent)
const isGitHub = platform.isGitHub
```

**Result**: Consistent, tested, multi-platform support with less code

---

**Status**: Production ready  
**Last Updated**: 2026-06-04  
**Modules**: 4 (platform-detector, git-operations, schemas, ai-attribution)
