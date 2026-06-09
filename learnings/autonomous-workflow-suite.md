---
name: autonomous-workflow-suite
description: "Complete suite of autonomous workflows: pr-review-auto, code-solve-auto, code-review-auto, code-test-auto"
metadata:
  type: project
  priority: high
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# Autonomous Workflow Suite

**Rule**: We have 4 fully autonomous workflows that require ZERO user interaction

**Why**: User requested autonomous versions of pr-review, code-solve, and code-review with impact analysis

**How to apply**: Run any workflow with `-auto` suffix for full automation

## The Suite

### 1. pr-review-auto

**Purpose**: Auto-approve/reject PRs based on quality + impact

**Auto-Approve Criteria** (ALL):
- Quality ≥ 90
- Consensus ≥ 85%
- NO breaking changes
- ≤ 2 high-risk changes
- ≤ 50 files impacted

**Auto-Reject Criteria** (ANY):
- Breaking changes detected
- Critical issues
- Quality < 60
- Risk = critical

**Usage**:
```bash
claude run pr-review-auto              # All open PRs
claude run pr-review-auto --max 5      # Max 5 PRs
claude run pr-review-auto --quality 95 # Stricter
```

### 2. code-solve-auto

**Purpose**: Auto-resolve issues with impact analysis

**Auto-Commit Criteria** (ALL):
- Confidence ≥ 85%
- Risk ≤ medium
- NO breaking changes
- Compiles/runs
- Addresses issue

**Auto-Discard Criteria** (ANY):
- Breaking changes
- High risk
- Doesn't compile
- Doesn't fix issue
- Confidence < 70%

**Usage**:
```bash
claude run code-solve-auto                 # All issues
claude run code-solve-auto --max 5         # Max 5
claude run code-solve-auto --confidence 90 # Stricter
```

### 3. code-review-auto

**Purpose**: Brutal code audit + auto-create issues

**Auto-Create Issue Criteria** (ALL):
- Consensus ≥ 70%
- Confidence ≥ 75%
- Severity ≥ medium
- Real bug (not false positive)
- ≥ 2 models verified

**Review Scope**:
- Recent commits (last N days)
- Open issues analysis
- Closed issues (regression check)
- Full codebase scan

**Usage**:
```bash
claude run code-review-auto           # Full audit
claude run code-review-auto --days 60 # Last 60 days
```

### 4. code-test-auto

**Purpose**: Comprehensive testing + auto-create issues for failures

**Auto-Create Issue Criteria** (ALL):
- Consensus ≥ 70%
- Confidence ≥ 75%
- Severity ≥ medium
- Real bug (not test config issue)
- Reproducible

**Test Scope**:
- UI tests (if applicable)
- Integration tests
- Unit tests
- API tests
- Open issue validation

**Usage**:
```bash
claude run code-test-auto                # Full test suite
claude run code-test-auto --maxTests 30  # More tests
```

## Common Features

**All 4 workflows share**:
1. **100% Autonomous**: Zero user interaction
2. **Multi-AI Consensus**: opus/sonnet/haiku
3. **Impact Analysis**: Before and after changes
4. **Strict Safety**: Conservative criteria
5. **Full Transparency**: All decisions documented
6. **Verification**: Multiple AIs verify findings

## Decision Matrix

| Workflow | What It Decides | Criteria | Action |
|----------|----------------|----------|--------|
| pr-review-auto | Approve/Reject PR | Quality + Impact | Approve or Request Changes |
| code-solve-auto | Commit/Discard Fix | Confidence + Risk | Commit or Discard |
| code-review-auto | Create Issue | Consensus + Severity | Create Issue or Skip |
| code-test-auto | Create Issue | Consensus + Reproducible | Create Issue or Skip |

## Comparison: Interactive vs Auto

| Feature | Interactive (base) | Autonomous (-auto) |
|---------|-------------------|-------------------|
| **User Input** | Required | None (100% auto) |
| **Decision** | User decides | Criteria-based |
| **Impact** | Post-action | Pre + post |
| **Verification** | Optional | Always (3 AIs) |
| **Use Case** | Manual review | CI/CD, batch |

## Impact Analysis Integration

All 3 workflows use impact analysis:

**pr-review-auto**:
- Detects breaking changes in PR
- Analyzes cross-codebase impact
- Auto-rejects if breaking

**code-solve-auto**:
- Predicts impact BEFORE solving
- Verifies fix doesn't break things
- Auto-discards if risky

**code-review-auto**:
- Assesses severity of findings
- Prioritizes by impact score
- Only creates high-impact issues

## Use Cases

### CI/CD Integration
```bash
# In .github/workflows/ai-review.yml
- run: claude run pr-review-auto --max 20
- run: claude run code-solve-auto --max 10
- run: claude run code-review-auto
```

### Scheduled Audits
```bash
# Daily cron
0 9 * * * claude run code-review-auto
0 10 * * * claude run code-solve-auto
0 11 * * * claude run pr-review-auto
```

### Bulk Processing
```bash
# Process everything at once
claude run pr-review-auto
claude run code-solve-auto
claude run code-review-auto
```

## Safety Philosophy

**Conservative by Default**:
- High confidence thresholds (70-90%)
- Breaking changes never auto-approved/committed
- Multi-AI verification required
- Full transparency in all decisions
- Fallback to safe action when uncertain

**Trust but Verify**:
- All findings verified by 3 AIs
- Consensus required (not single model)
- Arbiter makes final decision
- Every action documented

## Files

- **pr-review-auto.js** (650 lines)
- **pr-review-auto.md** (400 lines)
- **code-solve-auto.js** (600 lines)
- **code-solve-auto.md** (200 lines)
- **code-review-auto.js** (550 lines)
- **code-review-auto.md** (250 lines)
- **code-test-auto.js** (600 lines)
- **code-test-auto.md** (200 lines)

**Total**: ~3,450 lines of autonomous AI workflows

## Related

- [[pr-impact-analysis]] - Impact analysis system
- [[ai-attribution-tracking]] - Full AI transparency
- [[arbiter-worker-pattern]] - Multi-AI consensus
- [[automation-preferences]] - User prefers 100% automation
- [[pr-review-auto-autonomous]] - PR review bot details

## User Requests Fulfilled

✅ "would it be possible as part of the review, it see if those changes might break other parts of the code base"
✅ "can we make it so pr-review asks the user to reject or accept the pr/mr"
✅ "can we have a pr-review-auto that autonomously do pr-review until none are left"
✅ "let's do likewise for code-review and code-solve"

**Result**: Complete autonomous workflow suite with impact analysis!
