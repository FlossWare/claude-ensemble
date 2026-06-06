# Workflow Interaction Patterns

**Consistent interaction patterns across all workflows**

## The Pattern

**Base workflows**: Interactive - prompt user before taking action  
**Auto workflows**: Autonomous - no prompts, fully automated

## Complete Workflow Matrix

| Base (Interactive) | Auto (Autonomous) | What They Do |
|--------------------|-------------------|--------------|
| **pr-review** | **pr-review-auto** | Review PRs |
| **code-solve** | **code-solve-auto** | Resolve issues |
| **code-review** | **code-review-auto** | Audit codebase |
| **code-test** | **code-test-auto** | Test application |

## Interaction Details

### pr-review (base)
- Reviews PR with multi-AI
- Runs impact analysis
- **Prompts**: "Approve or request changes?"
- User decides action
- Posts review based on user choice

### pr-review-auto
- Reviews PR with multi-AI
- Runs impact analysis
- **Auto-decides**: Based on criteria (quality ≥ 90, no breaking)
- Auto-approves or auto-rejects
- NO user interaction

---

### code-solve (base)
- Generates fix with multi-AI
- Commits fix locally
- Runs impact analysis
- **Prompts**: "Push this fix to remote?"
- User decides to push or keep local
- Only pushes if user approves

### code-solve-auto
- Generates fix with multi-AI
- Commits fix locally
- Runs impact analysis
- **Auto-decides**: Based on criteria (confidence ≥ 85, no breaking)
- Auto-pushes to remote
- NO user interaction

---

### code-review (base)
- Scans codebase for bugs
- Runs impact analysis on findings
- **Prompts**: "Create issues for these findings?"
- User chooses: ALL / HIGH_ONLY / CRITICAL_ONLY / NONE
- Only creates issues user approves

### code-review-auto
- Scans codebase for bugs
- Runs impact analysis + multi-AI verification
- **Auto-decides**: Based on criteria (consensus ≥ 70%, real bug)
- Auto-creates issues for verified findings
- NO user interaction

---

### code-test (base)
- Runs comprehensive tests
- Validates open issues
- **Prompts**: "Create issues for test failures?"
- User decides which failures to report
- Only creates issues user approves

### code-test-auto
- Runs comprehensive tests
- Validates open issues
- Multi-AI verification of failures
- **Auto-decides**: Based on criteria (consensus ≥ 70%, reproducible)
- Auto-creates issues for verified failures
- NO user interaction

## When to Use Which

### Use Base Workflows When:
- You want oversight before actions
- You're testing/experimenting
- You want to review findings first
- You're working on critical code
- You need to explain decisions to team

### Use Auto Workflows When:
- Running in CI/CD pipelines
- Scheduled automated tasks
- Batch processing many items
- You trust the AI criteria
- You want zero-touch automation

## Impact Analysis Integration

**ALL workflows now have impact analysis**:

- **pr-review / pr-review-auto**: Detect breaking changes in PRs
- **code-solve / code-solve-auto**: Analyze impact of fixes
- **code-review / code-review-auto**: Assess severity of findings
- **code-test / code-test-auto**: Evaluate impact of failures

Impact analysis provides:
- Breaking change detection
- Risk assessment (low/medium/high/critical)
- Dependency tracking (what files affected)
- Missing test identification
- Recommendations

## User Decision Points

### pr-review
```
Review Summary →
  Quality: 92/100
  Impact: Low risk, no breaking changes
  AI: Approve (95% consensus)

👤 User: Approve or request changes? → User decides
```

### code-solve
```
Fix Summary →
  Commit: abc123
  Impact: Low risk, no breaking changes
  Confidence: 88%

👤 User: Push to remote? → User decides
```

### code-review
```
Findings Summary →
  Critical: 2
  High: 5
  Medium: 10
  Impact: See detailed scores

👤 User: Create issues for which? → ALL / HIGH_ONLY / CRITICAL_ONLY / NONE
```

### code-test
```
Test Results →
  Passed: 12
  Failed: 3
  Verified failures: 2

👤 User: Create issues for failures? → User decides
```

## Auto-Decision Criteria

### pr-review-auto
```
if quality ≥ 90 AND consensus ≥ 85% AND no breaking changes
  → APPROVE ✅
if breaking changes OR quality < 60
  → REQUEST_CHANGES ⚠️
else
  → COMMENT 💬
```

### code-solve-auto
```
if confidence ≥ 85% AND risk ≤ medium AND no breaking AND compiles
  → COMMIT + PUSH ✅
if breaking OR high risk OR doesn't compile
  → DISCARD ⚠️
```

### code-review-auto
```
if consensus ≥ 70% AND confidence ≥ 75% AND severity ≥ medium AND real bug
  → CREATE ISSUE ✅
else
  → SKIP
```

### code-test-auto
```
if consensus ≥ 70% AND confidence ≥ 75% AND reproducible AND real bug
  → CREATE ISSUE ✅
else
  → SKIP
```

## Configuration

All workflows respect the `autonomous` flag:

```bash
# Interactive mode (default for base workflows)
claude run code-review

# Force autonomous mode on base workflow
claude run code-review autonomous=true

# Autonomous mode (default for -auto workflows)
claude run code-review-auto
```

## Migration from Old Behavior

**Before** (all workflows autonomous):
- code-review: Auto-created issues (no prompt)
- code-solve: Auto-committed (no prompt before push)
- pr-review: Mixed (had some prompting)

**After** (consistent pattern):
- **Base**: All prompt before taking action
- **Auto**: All fully autonomous

**Benefits**:
- Predictable behavior
- Clear naming (-auto = autonomous)
- User control when needed
- Full automation when wanted

## Safety

**Base workflows** (safer):
- User reviews before action
- Can abort/modify decisions
- Learn from AI suggestions
- Full transparency

**Auto workflows** (faster):
- Strict safety criteria
- Multi-AI verification
- Impact analysis guards
- Full audit trail

---

**Status**: ✅ Complete
**Applies to**: All 8 workflows (4 base + 4 auto)
**Consistency**: 100% - all follow same pattern
