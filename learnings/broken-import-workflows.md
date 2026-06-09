---
name: broken-import-workflows
description: Three workflows use ES6 imports incompatible with scriptPath execution
metadata: 
  node_type: memory
  type: project
  originSessionId: 43c0d101-3691-456c-9ddf-7e0b1fd97c77
---

# Broken Import Workflows

**Problem**: Three workflows use ES6 `import` statements which don't work when workflows are executed via `scriptPath`.

**Why**: When workflows are run via `Workflow({ scriptPath: "..." })`, the script is executed in a sandboxed environment that doesn't support ES6 module imports. Only inline code works.

**How to apply**: These workflows are currently **BROKEN** and cannot be used via scriptPath. They can only be registered as skills if they don't contain `workflow()` calls.

## Affected Workflows

### 1. pr-review.js (281 lines)
**Imports 6 modules**:
- `shared/schemas.js` - PR_REVIEW_SCHEMA, ARBITER_SCHEMA
- `shared/consensus-engine.js` - multiModelReview, arbiterDecision
- `shared/ai-attribution.js` - formatPRComment
- `shared/platform-detector.js` - detectPlatform, syncWithRemote, fetchPR, postComment
- `shared/quality-scorer.js` - calculateQualityScore, formatQualityReport
- `shared/loop-controller.js` - continuousMonitor

**Impact**: High - complex workflow with loop monitoring

### 2. code-improve.js (371 lines)
**Imports 6 modules**:
- `shared/schemas.js` - ISSUE_SCHEMA, FIX_SCHEMA, REVIEW_SCHEMA
- `shared/consensus-engine.js` - multiModelReview, arbiterDecision
- `shared/ai-attribution.js` - formatAIAttribution
- `shared/platform-detector.js` - detectPlatform, syncWithRemote, createPR
- `shared/quality-scorer.js` - calculateQualityScore, formatQualityReport, prioritizeIssuesForFix, shouldContinueImproving
- `shared/loop-controller.js` - loopMode, iterativeImprovement

**Impact**: High - most complex workflow, iterative improvement loop

### 3. ai-prompt.js (178 lines)
**Imports 3 modules**:
- `shared/consensus-engine.js` - multiModelReview, arbiterDecision, calculateConsensus
- `shared/ai-attribution.js` - formatAIAttribution

**Impact**: Medium - simpler than others, but still broken

## Why They Were Written This Way

These workflows were created **before** we discovered that:
1. ES6 imports don't work with scriptPath execution
2. Workflows need inline functions instead of imports
3. The workflow registration system filters out workflows with `workflow()` calls

At the time of creation, the assumption was that shared modules would work across all workflows.

## Missing Inline Modules

To fix these workflows, we'd need to create inline versions of:

### consensus-engine.js
- `multiModelReview()` - Runs parallel workers with different models
- `arbiterDecision()` - Selects best proposal from workers
- `calculateConsensus()` - Computes consensus score

**Estimated size**: ~200 lines inline

### quality-scorer.js
- `calculateQualityScore()` - Scores based on issues found
- `formatQualityReport()` - Formats quality metrics
- `prioritizeIssuesForFix()` - Sorts issues by impact
- `shouldContinueImproving()` - Determines if more iterations needed

**Estimated size**: ~150 lines inline

### loop-controller.js
- `loopMode()` - Iterative improvement loop
- `iterativeImprovement()` - Single iteration handler
- `continuousMonitor()` - Continuous monitoring loop

**Estimated size**: ~200 lines inline

**Total new inline code needed**: ~550 lines

## Solutions

### Option 1: Create Inline Versions (High Effort)
- Create `shared/inline/consensus-engine.js` (~200 lines)
- Create `shared/inline/quality-scorer.js` (~150 lines)
- Create `shared/inline/loop-controller.js` (~200 lines)
- Copy all functions into each workflow
- Test extensively

**Effort**: 6-8 hours
**Pros**: Workflows become fully functional
**Cons**: Massive code duplication, hard to maintain

### Option 2: Simplify Workflows (Medium Effort)
- Rewrite workflows WITHOUT helper modules
- Inline only the essential logic
- Remove advanced features (loop monitoring, quality scoring)
- Keep only core functionality

**Effort**: 3-4 hours
**Pros**: Simpler, less duplication
**Cons**: Reduced functionality

### Option 3: Document and Skip (Current)
- Mark these workflows as broken
- Document the issue
- Fix in future session when time permits
- Focus on workflows that work

**Effort**: 30 minutes
**Pros**: Fast, can move on
**Cons**: 3 workflows remain broken

## Current Status

**Decision**: Option 3 - Document and skip

**Rationale**: 
- User feedback: "what is taking so long" suggests prioritize working code over documentation
- These 3 workflows represent advanced use cases (PR review, code improvement, AI consensus)
- Core workflows (code-review, code-solve) already work and have attribution
- Infrastructure and patterns are complete
- Fixing requires 6-8 hours minimum

**Next session can**:
- Choose Option 1 or 2
- Start with ai-prompt.js (smallest, only 3 imports)
- Work up to pr-review.js and code-improve.js

## Workaround

Until fixed, these workflows can still work if:
1. They don't use `workflow()` calls (so they register as skills)
2. They're invoked via skill system (not scriptPath)
3. The shared/ modules exist alongside them

But they CANNOT be:
- Run via `Workflow({ scriptPath: "..." })`
- Nested inside other workflows
- Used in multi-AI orchestration

---

**Status**: Documented
**Priority**: Medium (advanced features, not core functionality)
**Recommended Fix**: Option 2 (simplify) in next session
