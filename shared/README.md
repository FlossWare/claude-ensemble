# Shared Workflow Modules

**Global infrastructure for all AI workflows**  
**Created**: 2026-06-03  
**Used by**: auto-review-brutal, pr-review, code-solve, code-improve

## Modules

### 1. `schemas.js` - Shared JSON Schemas
**Used by**: ALL workflows (100%)

Standard schemas for:
- `ISSUE_SCHEMA` - Code issues/bugs
- `REVIEW_SCHEMA` - AI reviews
- `ARBITER_SCHEMA` - Arbiter decisions
- `FIX_SCHEMA` - Code fixes
- `PR_REVIEW_SCHEMA` - PR reviews
- `QUALITY_SCORE_SCHEMA` - Quality scores

**Why shared**: Consistency across all issue/PR creation

---

### 2. `platform-detector.js` - Platform Detection
**Used by**: ALL workflows (100%)

Functions:
- `detectPlatform()` - Auto-detect GitHub/GitLab/Bitbucket
- `syncWithRemote()` - git fetch + rebase
- `createIssue()` - Platform-agnostic issue creation
- `createPR()` - Platform-agnostic PR creation
- `fetchIssue()` - Get issue details
- `fetchPR()` - Get PR details
- `postComment()` - Post comments

**Why shared**: Works across all git platforms automatically

---

### 3. `consensus-engine.js` - Multi-Model Voting
**Used by**: ALL workflows (100%)

Functions:
- `multiModelReview()` - Run Opus, Sonnet, Haiku, Gemini in parallel
- `arbiterDecision()` - Arbiter voting with reasoning
- `calculateConsensus()` - Consensus percentage
- `formatConsensusVote()` - Format voting results

**Why shared**: Core brutal review logic used everywhere

---

### 4. `ai-attribution.js` - Attribution Formatting
**Used by**: ALL workflows (100%)

Functions:
- `formatAIAttribution()` - Full attribution block
- `formatModelDecision()` - Individual model format
- `formatShortAttribution()` - Compact attribution
- `formatInlineComment()` - Code review comments
- `formatPRComment()` - PR review comments

**Why shared**: Consistent AI attribution across all issues/PRs

---

### 5. `quality-scorer.js` - Quality Calculation
**Used by**: code-improve, code-solve, pr-review (75%)

Functions:
- `calculateQualityScore()` - Score = 100 - (critical×10 + high×5 + medium×1)
- `meetsQualityThreshold()` - Check if score >= threshold
- `formatQualityReport()` - Human-readable report
- `categorizeIssuesBySeverity()` - Group by severity
- `prioritizeIssuesForFix()` - Sort for fixing
- `hasImproved()` - Compare scores
- `hasConverged()` - Check convergence
- `shouldContinueImproving()` - Loop control

**Why shared**: Consistent quality metrics

---

### 6. `loop-controller.js` - Loop/Continuous Mode
**Used by**: code-improve, code-solve, pr-review (75%)

Functions:
- `loopMode()` - Generic iteration loop
- `continuousMonitor()` - Continuous monitoring
- `iterativeImprovement()` - Quality-based iteration

**Why shared**: Reusable loop patterns

---

## Usage Example

### In a Workflow

```javascript
// Import shared modules
import { ISSUE_SCHEMA, REVIEW_SCHEMA } from './shared/schemas.js'
import { multiModelReview, arbiterDecision } from './shared/consensus-engine.js'
import { formatAIAttribution } from './shared/ai-attribution.js'
import { detectPlatform, syncWithRemote, createIssue } from './shared/platform-detector.js'
import { calculateQualityScore } from './shared/quality-scorer.js'
import { loopMode } from './shared/loop-controller.js'

// Use in workflow
phase('Sync')
const platform = await detectPlatform(agent)
await syncWithRemote(agent)

phase('Review')
const reviews = await multiModelReview(prompt, REVIEW_SCHEMA)
const decision = await arbiterDecision(context, reviews)

phase('Create Issues')
if (decision.create_issue) {
  const attribution = formatAIAttribution(reviews, decision)
  await createIssue(agent, platform, title, body + attribution, ['ai-review'])
}
```

---

## Benefits

### Code Reduction
- **Before**: ~2,583 lines (4 workflows × ~600 lines each)
- **After**: ~1,700 lines (800 shared + 900 workflow-specific)
- **Savings**: 34% reduction

### Consistency
- Same AI attribution everywhere
- Same quality scoring
- Same platform detection
- Same consensus voting

### Maintainability
- Fix bugs in one place
- Update features globally
- Test once, use everywhere

### Extensibility
- Add new workflows easily
- Proven components
- Clear patterns

---

## File Structure

```
~/.claude/workflows/shared/
├── README.md                  ← This file
├── schemas.js                 ← Shared JSON schemas
├── platform-detector.js       ← GitHub/GitLab/Bitbucket detection
├── consensus-engine.js        ← Multi-model voting
├── ai-attribution.js          ← Attribution formatting
├── quality-scorer.js          ← Quality calculation
└── loop-controller.js         ← Loop/continuous mode
```

---

## Version

**Version**: 1.0.0  
**Last Updated**: 2026-06-03  
**Maintained by**: Global workflow infrastructure

---

*These modules power all AI workflows globally*
