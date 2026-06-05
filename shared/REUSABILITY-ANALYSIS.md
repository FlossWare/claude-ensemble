# Reusability Analysis & Refactoring Plan

Analysis of all workflows to identify duplication and extract reusable patterns.

## Current State

### Shared Modules (Already Exist)
- ✅ `ai-attribution.js` - AI transparency (2 patterns: arbiter + threshold)
- ✅ `consensus-engine.js` - Multi-AI consensus algorithms
- ✅ `loop-controller.js` - Loop-until-dry patterns
- ✅ `platform-detector.js` - **UNUSED!** Platform detection + unified API
- ✅ `quality-scorer.js` - Quality scoring
- ✅ `schemas.js` - Common JSON schemas
- ✅ `work-coordinator.js` - Distributed work coordination

### Workflows (11 total)
1. `code-review.js` - Comprehensive code review (✅ has AI attribution)
2. `code-solve.js` - Auto-resolve issues (✅ has AI attribution)
3. `code-hygiene-review.js` - Repo cleanup
4. `code-test-review.js` - Test quality review
5. `doc-review.js` - Documentation review
6. `pr-review.js` - PR review
7. `pr-verify.js` - PR verification
8. `code-improve.js` - Code improvements
9. `ai-prompt.js` - AI prompt testing
10. `workflow-cleanup.js` - Workflow maintenance
11. `code-review-and-solve.js` - Combined (⚠️ has parse errors)

## Duplication Analysis

### Pattern 1: Platform Detection (100% duplication)

**Found in**: ALL workflows (code-review, code-solve, code-hygiene-review, code-test-review)

**Current approach** (duplicated):
```javascript
const platformDetect = await agent(`Detect platform.
Execute:
if git remote -v | grep -q 'github.com'; then echo "github"
elif git remote -v | grep -q 'gitlab'; then echo "gitlab"
...`, {schema})

const isGitLab = platformDetect.platform === 'gitlab'
const isGitHub = platformDetect.platform === 'github'
const isBitbucket = platformDetect.platform === 'bitbucket'
```

**Reusable module exists**: `shared/platform-detector.js`

**Should be**:
```javascript
// For workflows (inline version):
function detectPlatform() {
  // ... (copy from platform-detector.js)
}
const platform = await detectPlatform(agent)
```

**Impact**:
- **Lines duplicated**: ~20 lines × 11 workflows = 220 lines
- **Maintenance burden**: Every platform change needs 11 updates
- **Inconsistency risk**: High (already have different implementations)

### Pattern 2: Issue Operations (80% duplication)

**Found in**: code-review, code-solve, code-hygiene-review, code-test-review

**Current approach** (duplicated):
```javascript
// List issues
const fetchCmd = isGitLab
  ? `glab issue list --state opened --per-page ${N}`
  : isBitbucket
  ? `echo "[]"`
  : `gh issue list --state open --limit ${N} --json number,title,body,labels`

// Create issue
const createCmd = isGitLab
  ? `glab issue create --title "${title}" --description "${body}" --label "${labels}"`
  : `gh issue create --title "${title}" --body "${body}" --label "${labels}"`

// Reopen issue  
const reopenCmd = isGitLab
  ? `glab issue reopen ${num} && glab issue note ${num} --message "${msg}"`
  : `gh issue reopen ${num} && gh issue comment ${num} --body "${msg}"`

// Close issue
const closeCmd = isGitLab
  ? `glab issue note ${num} -m "${msg}" && glab issue close ${num}`
  : `gh issue close ${num} --comment "${msg}"`
```

**Reusable module exists**: `shared/platform-detector.js` (has createIssue, fetchIssue, postComment)

**Missing functions**:
- `listIssues(platform, state, limit)`
- `reopenIssue(platform, number, comment)`
- `closeIssue(platform, number, comment)`
- `updateLabels(platform, number, add, remove)`

**Should be**:
```javascript
const issues = await listIssues(agent, platform, 'open', 100)
await createIssue(agent, platform, title, body, labels)
await reopenIssue(agent, platform, num, comment)
await closeIssue(agent, platform, num, comment)
```

**Impact**:
- **Lines duplicated**: ~60 lines × 8 workflows = 480 lines
- **Maintenance burden**: Every CLI change needs multiple updates
- **Inconsistency**: GitLab/Bitbucket support varies by workflow

### Pattern 3: Multi-AI Consensus (50% duplication)

**Found in**: code-review, code-solve, pr-review

**Current approaches**:
1. **Arbiter-based** (code-solve, pr-review):
   ```javascript
   const workers = await parallel([opus, sonnet, haiku])
   const arbiter = await agent('Pick best', {model: 'opus'})
   ```

2. **Threshold-based** (code-review):
   ```javascript
   const workers = await parallel([opus, sonnet, haiku])
   const accepted = workers.filter(w => w.confidence >= THRESHOLD)
   ```

**Reusable module exists**: `shared/consensus-engine.js`

**Should be**:
```javascript
// Arbiter pattern
const result = await arbiterConsensus(agent, prompts, models, arbiterModel)

// Threshold pattern
const results = await thresholdConsensus(agent, prompts, models, threshold)
```

**Impact**:
- **Lines duplicated**: ~80 lines × 3 workflows = 240 lines
- **Pattern inconsistency**: Each workflow implements differently
- **Testing burden**: Same logic tested in multiple places

### Pattern 4: Git Operations (40% duplication)

**Found in**: code-review, code-solve, code-hygiene-review

**Current approach** (duplicated):
```javascript
// Get commit history
git log --since="30 days ago" --pretty=format:"%H|%an|%ad|%s"

// Get diff
git show ${hash} --stat
git diff ${hash}^..${hash}

// Find files
find . -type f \\( -name "*.js" -o -name "*.ts" ... \\) | grep -v node_modules
```

**Should extract**:
```javascript
// shared/git-operations.js
export function getCommitHistory(agent, days, limit)
export function getDiff(agent, hash)
export function findSourceFiles(agent, patterns, exclude, limit)
export function getFileHistory(agent, filepath)
```

**Impact**:
- **Lines duplicated**: ~40 lines × 6 workflows = 240 lines
- **Inconsistency**: Different file patterns, different exclusions

### Pattern 5: AI Attribution (NEW - only in 2 workflows)

**Found in**: code-review ✅, code-solve ✅

**Not yet in**: code-hygiene-review, code-test-review, doc-review, pr-review

**Reusable module exists**: `shared/ai-attribution.js` ✅

**Status**: **NEEDS ROLLOUT** to all workflows with multi-AI

**Impact**:
- **Missing transparency**: 9 workflows lack full AI attribution
- **Inconsistent user experience**: Some workflows show AI decisions, others don't

### Pattern 6: Schema Definitions (30% duplication)

**Found in**: ALL workflows

**Current approach** (duplicated):
```javascript
// Every workflow defines similar schemas inline
schema: {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string' },
          description: { type: 'string' },
          confidence: { type: 'number' },
          // ... repeated everywhere
        }
      }
    }
  }
}
```

**Reusable module exists**: `shared/schemas.js` ✅

**Should be**:
```javascript
// Import inline (copy from schemas.js)
const ISSUE_SCHEMA = { ... }
const REVIEW_SCHEMA = { ... }
const FIX_SCHEMA = { ... }

// Use in agent calls
await agent(prompt, {schema: ISSUE_SCHEMA})
```

**Impact**:
- **Lines duplicated**: ~200 lines across all workflows
- **Schema drift**: Workflows use slightly different field names
- **Validation inconsistency**: Some require fields, others don't

## Refactoring Plan

### Phase 1: Extract Inline Helpers (Low Risk)

**Goal**: Create inline-ready versions of shared modules

**Tasks**:
1. ✅ Create `ai-attribution.js` inline version (DONE)
2. Create `platform-detector-inline.js` with copy-paste functions
3. Create `issue-operations-inline.js` for common issue operations
4. Create `git-operations-inline.js` for common git commands
5. Create `schemas-inline.js` with all schemas

**Files to create**:
```
shared/
  inline/
    platform-detector.js    # Copy-paste platform detection
    issue-operations.js     # Copy-paste issue operations
    git-operations.js       # Copy-paste git commands
    schemas.js              # Copy-paste all schemas
    ai-attribution.js       # Already exists!
    README.md               # Usage guide for inline functions
```

### Phase 2: Refactor Workflows to Use Inline (Medium Risk)

**Priority order** (most duplicated first):
1. **Platform Detection** (all 11 workflows)
   - Extract inline `detectPlatform()` function
   - Replace 220 lines of duplicated code
   - Test each workflow after refactoring

2. **Issue Operations** (8 workflows)
   - Extract inline issue operation functions
   - Replace 480 lines of duplicated code
   - Standardize GitHub/GitLab/Bitbucket support

3. **Git Operations** (6 workflows)
   - Extract inline git helper functions
   - Replace 240 lines of duplicated code
   - Standardize file finding patterns

4. **Schema Definitions** (all 11 workflows)
   - Copy schemas from `shared/schemas.js`
   - Replace 200 lines of duplicated schemas
   - Ensure consistency across workflows

5. **AI Attribution** (9 workflows missing it)
   - Add inline AI attribution to all multi-AI workflows
   - Ensure consistent transparency

### Phase 3: Enhance Shared Modules (Low Risk)

**Goal**: Add missing common operations

**Tasks**:
1. **Extend `platform-detector.js`**:
   ```javascript
   export async function listIssues(agent, platform, state, limit)
   export async function reopenIssue(agent, platform, number, comment)
   export async function closeIssue(agent, platform, number, comment)
   export async function updateLabels(agent, platform, number, add, remove)
   export async function searchIssues(agent, platform, query)
   ```

2. **Create `git-operations.js`**:
   ```javascript
   export async function getCommitHistory(agent, days, limit)
   export async function getDiff(agent, hash)
   export async function findSourceFiles(agent, patterns, exclude, limit)
   export async function getFileHistory(agent, filepath)
   export async function getBlame(agent, filepath)
   ```

3. **Extend `ai-attribution.js`**:
   ```javascript
   // Already has arbiter + threshold patterns ✅
   // Add: formatForCommitMessage(attribution)
   // Add: formatForSlackMessage(attribution)
   ```

### Phase 4: Create Inline Guide (Documentation)

**File**: `shared/inline/README.md`

**Contents**:
- Why inline? (workflows can't use imports with scriptPath)
- How to copy functions
- Which functions to use when
- Examples from each pattern
- Migration guide per workflow type

### Phase 5: Test & Validate (High Priority)

**For each refactored workflow**:
1. Validate syntax: `node --check workflow.js`
2. Test via scriptPath: `Workflow({scriptPath: "..."})`
3. Test via name: `Workflow({name: "..."})`
4. Verify AI attribution appears in issues
5. Test on GitHub, GitLab (if possible)

## Impact Summary

### Lines of Code Reduction
- Platform detection: **-220 lines** (100% duplication eliminated)
- Issue operations: **-480 lines** (80% duplication eliminated)
- Git operations: **-240 lines** (40% duplication eliminated)
- Schema definitions: **-200 lines** (30% duplication eliminated)
- AI consensus: **-240 lines** (50% duplication eliminated)

**Total**: **~1,380 lines** of duplicated code eliminated

### Maintenance Benefits
- **One place to update** platform detection logic
- **Consistent** GitHub/GitLab/Bitbucket support
- **Standardized** schema definitions
- **Universal** AI attribution
- **Easier testing** of common operations

### Risks
- ✅ **Low risk**: Using inline functions (copy-paste) maintains independence
- ✅ **Gradual rollout**: Can refactor one workflow at a time
- ✅ **Backward compatible**: Old workflows keep working during migration
- ⚠️ **Testing required**: Each refactored workflow needs validation

## Recommended Approach

### Week 1: Create Inline Modules
1. Create `shared/inline/` directory
2. Extract platform detection inline functions
3. Extract issue operations inline functions
4. Extract git operations inline functions
5. Copy schemas for inline use
6. Write `shared/inline/README.md` guide

### Week 2: Refactor High-Impact Workflows
1. code-review.js (platform + issues + git)
2. code-solve.js (platform + issues)
3. code-hygiene-review.js (platform + issues + git)
4. code-test-review.js (platform + issues)

### Week 3: Refactor Remaining Workflows
1. doc-review.js
2. pr-review.js
3. pr-verify.js
4. code-improve.js
5. ai-prompt.js
6. workflow-cleanup.js

### Week 4: Add Missing AI Attribution
1. code-hygiene-review.js
2. code-test-review.js
3. doc-review.js
4. pr-review.js
5. pr-verify.js
6. code-improve.js

## Success Metrics

- [ ] All 11 workflows use inline platform detection
- [ ] All 11 workflows use inline schemas
- [ ] All 9 multi-AI workflows have AI attribution
- [ ] All 8 issue-creating workflows use inline issue operations
- [ ] All 6 git-using workflows use inline git operations
- [ ] Zero syntax errors across all workflows
- [ ] All workflows testable via scriptPath + name
- [ ] Documentation complete in `shared/inline/README.md`

## Next Steps

1. **Review this analysis** with stakeholders
2. **Approve refactoring plan** (phases 1-4)
3. **Create inline modules** (phase 1)
4. **Begin gradual rollout** (phase 2)
5. **Track progress** via task list
6. **Test each workflow** after refactoring
7. **Update documentation** as we go

---

**Status**: Analysis complete, awaiting approval  
**Date**: 2026-06-04  
**Estimated effort**: 4 weeks for complete rollout  
**Risk level**: Low (inline functions maintain independence)  
**Impact**: High (eliminate 1,380+ lines of duplication)
