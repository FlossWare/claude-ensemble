---
name: pr-impact-analysis
description: "pr-review detects breaking changes and cross-codebase impacts automatically"
metadata:
  type: project
  priority: high
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# PR Review Impact Analysis

**Rule**: pr-review now automatically detects breaking changes and cross-codebase impacts

**Why**: User asked "would it be possible as part of the review, it see if those changes might break other parts of the code base" - impact analysis prevents production incidents from breaking changes

**How to apply**: Impact analysis runs automatically in pr-review workflow (no configuration needed)

## What It Does

**Impact Analysis detects**:
1. Breaking changes (function signatures, removed exports, type changes)
2. High-risk changes (affecting many files or core functionality)
3. Dependencies (which files import/use the changed code)
4. Missing tests (areas lacking coverage after changes)
5. Actionable recommendations

## Auto-Decision Logic

```javascript
if (breaking_changes > 0) → REQUEST_CHANGES
if (AI approve + no breaking + low risk) → APPROVE  
if (AI request_changes) → REQUEST_CHANGES
else → COMMENT
```

## Workflow Phases

```
1. Fetch PR + Diff
2. Impact Analysis ← NEW!
   - Identify what changed
   - Find dependencies
   - Detect breaking changes
   - Assess risk
   - Check tests
3. Multi-AI Review (includes impact findings)
4. Arbiter Decision
5. Auto-Decision (based on impact + AI)
6. Post Results (review + impact report)
```

## Example Output

```
⚠️ Breaking Changes (2):
  - processPayment: Parameter removed (5 files affected)
  - UserAuth: Export removed (3 imports broken)

🔥 High Risk (1):
  - fetchUserData: 8 files impacted

📊 Impacted Files: 12
📝 Missing Tests: 2

🤖 Auto-Decision: REQUEST_CHANGES
   Reasoning: Breaking changes detected
```

## Files

- **shared/impact-analysis.js**: Core engine (450 lines)
- **shared/IMPACT_ANALYSIS.md**: Documentation
- **pr-review.js**: Enhanced with impact integration

## User Requests Fulfilled

✅ "would it be possible as part of the review, it see if those changes might break other parts of the code base"
✅ "can we make it so pr-review asks the user to reject or accept the pr/mr"

## Related

- [[ai-attribution-tracking]] - Full AI transparency in reviews
- [[arbiter-worker-pattern]] - Multi-AI consensus for reviews
- [[parallel-by-default]] - Parallel execution for performance
