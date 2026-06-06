# Reusable Opportunities in code-* Workflows

## Analysis of code-test, code-solve, code-review

### Already Created ✅

1. **shared/issue-operations.js** - Issue management functions
   - detectPlatform()
   - fetchIssues(), claimIssue(), unclaimIssue()
   - createIssue(), commentOnIssue(), closeIssue(), reopenIssue()
   - Used by: code-test ✅

2. **shared/model-discovery.js** - Dynamic AI model discovery
   - discoverModels() - auto-detect available AI providers
   - createModelRotations() - diverse rotation patterns
   - selectArbiter() - intelligent arbiter selection
   - Used by: code-test ✅

3. **shared/ai-attribution.js** - AI attribution tracking (PARTIAL)
   - createArbiterAttribution()
   - formatArbiterAttributionMarkdown()
   - selectArbiter()
   - Used by: code-solve (inline), code-test (inline)

### Opportunities for Shared Libraries

#### 1. **Work Coordinator Pattern** 🔥 HIGH PRIORITY

**Current State**: Duplicated in code-solve.js (250+ lines)

**Function**: `coordinateWork()` - atomic work claiming for parallel execution

**Used By**:
- code-solve: Parallel issue solving with atomic claiming
- Could be used by: code-review, code-test, any parallel workflow

**Proposal**: Create `shared/work-coordinator.js`

```javascript
export async function coordinateWork({
  fetchWork,       // () => Promise<WorkItem[]>
  filterWork,      // (item) => boolean
  claimWork,       // (item) => Promise<boolean>
  processWork,     // (item) => Promise<result>
  maxWorkers,      // number
  onProgress,      // (completed, total) => void
  onSkip,          // (item, reason) => void
  failFast         // boolean
})
```

**Benefits**:
- DRY: Remove 250+ lines of duplication
- Tested: Used in production by code-solve
- Reusable: Any workflow that needs parallel processing with claiming

#### 2. **Platform Detection & Operations** ✅ DONE

**Current State**: Duplicated in code-solve, code-review, code-test

**Already Created**: `shared/issue-operations.js`

**Refactoring Needed**:
- Update code-solve.js to use shared functions
- Update code-review.js to use shared functions

#### 3. **AI Attribution & Consensus** ⚠️ PARTIAL

**Current State**:
- createArbiterAttribution() duplicated in code-solve, code-test
- formatArbiterAttributionMarkdown() duplicated
- selectArbiter() duplicated in model-discovery AND ai-attribution

**Proposal**: Consolidate into `shared/ai-attribution.js` (already started)

**Functions Needed**:
- createArbiterAttribution() ✅
- formatArbiterAttributionMarkdown() ✅
- createConsensusMetadata() - NEW
- formatConsensusMarkdown() - NEW
- selectArbiter() ✅

#### 4. **Git Operations** 💡 MEDIUM PRIORITY

**Current Duplications**:
- Get commit hash
- Cherry-pick commits
- Branch operations
- Merge operations

**Found In**: code-solve, code-review

**Proposal**: Create `shared/git-operations.js`

```javascript
export async function getCommitHash(agent)
export async function cherryPick(agent, commitHash, targetBranch)
export async function getCurrentBranch(agent)
export async function checkoutBranch(agent, branch)
export async function getCommitHistory(agent, since)
```

#### 5. **Test Detection & Execution** 💡 LOW PRIORITY

**Current State**: code-test has app detection logic

**Potential**: Extract to `shared/app-detection.js`

```javascript
export async function detectAppType(agent)
export async function detectFramework(agent)
export async function detectTestFramework(agent)
export async function getBuildCommand(agent, appType)
export async function getRunCommand(agent, appType)
```

**Benefits**: Other workflows could benefit from knowing app type

### Refactoring Priority

**Phase 1 - High Impact** 🔥:
1. Create `shared/work-coordinator.js` - used by multiple workflows
2. Refactor code-solve to use shared issue-operations
3. Refactor code-review to use shared issue-operations

**Phase 2 - Consolidation** ⚠️:
4. Consolidate ai-attribution.js (already started)
5. Update all workflows to use shared ai-attribution

**Phase 3 - Nice to Have** 💡:
6. Create git-operations.js
7. Create app-detection.js

### Size Savings Estimate

**Current Duplication**:
- Issue operations: ~200 lines × 3 workflows = 600 lines
- AI attribution: ~100 lines × 2 workflows = 200 lines
- Work coordinator: ~250 lines (could be used by 3+ workflows)
- Git operations: ~50 lines × 2 workflows = 100 lines

**Total potential savings**: ~1,100 lines of duplicated code

**After refactoring**: ~400 lines in shared/ (reusable by all)

**Net reduction**: ~700 lines removed + improved maintainability

### Implementation Plan

```bash
# Phase 1: Critical shared libraries
1. Create shared/work-coordinator.js
2. Update code-solve to use shared/issue-operations
3. Update code-review to use shared/issue-operations

# Phase 2: Consolidation
4. Finish shared/ai-attribution.js
5. Update code-solve to use shared/ai-attribution
6. Update code-test to use shared/ai-attribution

# Phase 3: Optional enhancements
7. Create shared/git-operations.js (if needed)
8. Create shared/app-detection.js (if needed)
```

### Testing Strategy

For each shared library:
1. Extract function from existing workflow
2. Test with existing workflow (verify no regression)
3. Update other workflows to use shared version
4. Verify all workflows still work

### Shared Libraries Summary

**Already Created**:
- ✅ shared/model-discovery.js
- ✅ shared/issue-operations.js  
- ⚠️ shared/ai-attribution.js (partial)

**To Create**:
- 🔥 shared/work-coordinator.js (HIGH PRIORITY)
- 💡 shared/git-operations.js (optional)
- 💡 shared/app-detection.js (optional)

**Workflows to Refactor**:
- code-solve.js - use issue-operations, ai-attribution, work-coordinator
- code-review.js - use issue-operations, ai-attribution
- code-test.js - already using most shared libs ✅
