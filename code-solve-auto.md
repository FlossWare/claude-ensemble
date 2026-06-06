# code-solve-auto - Autonomous Issue Solver

**Fully automated issue resolution with impact analysis**

## Overview

`code-solve-auto` autonomously:
- Discovers all open issues
- Analyzes impact BEFORE solving
- Generates multi-AI solutions
- Verifies fixes work
- **Auto-commits** high-confidence, safe fixes
- **Auto-discards** risky or broken fixes
- Runs until all issues processed
- **NO manual intervention**

## Usage

```bash
# Solve all open issues
claude run code-solve-auto

# Max 5 issues per run
claude run code-solve-auto --max 5

# Require 90%+ confidence
claude run code-solve-auto --confidence 90
```

## How It Works

### Workflow Phases

1. **Setup**: Detect platform, sync
2. **Discover Issues**: Find all open issues
3. **Fetch Issue**: Get details
4. **Impact Analysis**: Predict impact BEFORE solving
5. **Multi-Model Solutions**: Opus/Sonnet/Haiku propose fixes
6. **Arbiter Decision**: Select best solution
7. **Apply Fix**: Implement in worktree
8. **Verify Fix**: Test it works
9. **Auto-Decision**: Commit or discard

### Auto-Commit Criteria (ALL must be true)

- ✅ Confidence ≥ 85%
- ✅ Risk ≤ medium
- ✅ NO breaking changes
- ✅ Compiles/runs successfully
- ✅ Addresses the issue
- ✅ Verification passes

### Auto-Discard Criteria (ANY triggers)

- ❌ Breaking changes introduced
- ❌ High risk solution
- ❌ Doesn't compile
- ❌ Doesn't fix the issue
- ❌ Confidence < 70%

## Configuration

```javascript
const CONFIG = {
  workers: ['opus', 'sonnet', 'haiku'],
  arbiterModel: 'opus',
  
  autoCommit: {
    minConfidence: 85,
    maxRiskLevel: 'medium',
    noBreakingChanges: true,
  },
  
  maxIssuesPerRun: 10,
}
```

## Example Output

```
═══════════════════════════════════════════
🤖 AUTONOMOUS ISSUE SOLVER
═══════════════════════════════════════════
Workers: opus, sonnet, haiku
Arbiter: opus
Auto-Commit: Confidence ≥ 85%, No breaking
═══════════════════════════════════════════

📋 Finding open issues...
📊 Found 12 open issues
🎯 Solving 10 issues this run

═══════════════════════════════════════════
🐛 Issue #42
═══════════════════════════════════════════
✅ "Fix authentication timeout"

🎯 Analyzing impact before solving...
✅ Predicted impact:
   Risk: low
   Breaking changes likely: NO
   Files affected: ~2

🤖 3 models proposing solutions...
✅ 3 solutions proposed

⚖️ Arbiter selecting best solution...
✅ Selected solution 1
   Approach: Increase timeout to 30s
   Confidence: 92%

🔧 Applying fix...
✅ Fix applied
   Files modified: 2

🧪 Verifying fix...
✅ Verification PASSED
   Compiles: true
   Addresses issue: true

🤖 Auto-Action: COMMIT
   Reasoning: High confidence (92%), low risk

✅ Fix committed
✅ Issue #42 closed

═══════════════════════════════════════════
📊 SUMMARY
═══════════════════════════════════════════
Total: 10
Auto-resolved: 7
Discarded: 3
```

## Comparison: code-solve vs code-solve-auto

| Feature | code-solve | code-solve-auto |
|---------|------------|-----------------|
| **Autonomy** | User oversight | Fully autonomous |
| **Impact** | After solution | Before + after |
| **Decision** | Manual | Auto (criteria) |
| **Commit** | User confirms | Auto if safe |
| **Use Case** | Interactive | CI/CD, batch |

## Impact Analysis

**Before Solving**:
- Predicts files affected
- Estimates risk level
- Identifies breaking changes
- Plans tests needed

**After Solving**:
- Verifies fix compiles
- Checks addresses issue
- Detects side effects
- Validates no regressions

## Safety Features

1. **Pre-Fix Impact**: Analyze before implementing
2. **Multi-AI Verification**: 3 models verify each fix
3. **Compilation Check**: Must compile/run
4. **Issue Validation**: Must actually fix the issue
5. **Breaking Change Detection**: Never commits breaking changes
6. **Fallback to Comment**: Explains why discarded

## Use Cases

- **CI/CD**: Auto-fix issues in pipeline
- **Scheduled**: Cron job for daily issue processing
- **Bulk Fix**: Process all open issues at once
- **Conservative**: High confidence gates

---

**Status**: ✅ Production ready
**Autonomy**: 100%
