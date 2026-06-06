# code-review-auto - Autonomous Code Review

**Fully automated brutal code review with auto-issue creation**

## Overview

`code-review-auto` autonomously:
- Reviews recent commits
- Analyzes open/closed issues
- Scans entire codebase
- Verifies findings with multi-AI consensus
- **Auto-creates issues** for verified bugs
- Runs until complete
- **NO manual intervention**

## Usage

```bash
# Full code review (all phases)
claude run code-review-auto

# Review last 60 days
claude run code-review-auto --days 60

# More thorough scan
claude run code-review-auto --maxIssues 20
```

## How It Works

### Workflow Phases

1. **Setup**: Detect platform, sync
2. **Recent Commits**: Review last N days
3. **Open Issues**: Analyze for missed bugs
4. **Closed Issues**: Check for regressions
5. **Full Codebase**: Brutal scan
6. **Impact Analysis**: Prioritize by severity
7. **Multi-Model Verification**: Verify findings
8. **Create Issues**: Auto-create for real bugs

### Auto-Create Issue Criteria (ALL must be true)

- ✅ Consensus ≥ 70% (models agree it's real)
- ✅ Confidence ≥ 75%
- ✅ Severity ≥ medium
- ✅ Verified as real bug (not false positive)
- ✅ At least 2 models verified

## Configuration

```javascript
const CONFIG = {
  workers: ['opus', 'sonnet', 'haiku'],
  arbiterModel: 'opus',
  
  // Review scope
  daysBack: 30,
  maxCommits: 10,
  maxOpenIssues: 10,
  maxClosedIssues: 5,
  maxFilesToScan: 20,
  
  // Auto-create criteria
  autoCreate: {
    minConsensus: 70,
    minConfidence: 75,
    minSeverity: 'medium',
    realBugRequired: true,
  },
}
```

## Example Output

```
═══════════════════════════════════════════
🔥 AUTONOMOUS BRUTAL CODE REVIEW
═══════════════════════════════════════════
Workers: opus, sonnet, haiku
Scope: Last 30 days + 15 issues + full scan
Auto-Create: Consensus ≥ 70%, Real bugs only
═══════════════════════════════════════════

📅 Reviewing commits...
📊 Found 25 commits
  ⚠️ Found 3 issues in commit abc123
✅ Commit review complete (8 findings)

📋 Reviewing open issues...
📊 12 open issues found
  ⚠️ Found 2 additional issues
✅ Issue review complete (10 total findings)

🔍 Checking closed issues...
📊 10 closed issues found
  ⚠️ Regression detected in issue #5
✅ Regression check complete (12 total)

🔍 Brutal codebase scan...
📊 Scanning 20 files
  ⚠️ auth.js: 4 issues
  ⚠️ api.js: 2 issues
✅ Codebase scan complete (25 total findings)

🎯 Analyzing impact...
✅ 25 findings prioritized

🤖 Verifying findings...
  Verifying: SQL injection in login handler...
    ✅ VERIFIED (85% consensus)
  Verifying: Missing input validation...
    ✅ VERIFIED (92% consensus)
  Verifying: Unused variable x...
    ❌ Rejected (not a real bug)
✅ 15 findings verified

📝 Creating issues...
  ✅ Created issue #101
  ✅ Created issue #102
  ...
✅ 15 issues created

═══════════════════════════════════════════
📊 CODE REVIEW SUMMARY
═══════════════════════════════════════════
Total findings: 25
Verified: 15
Issues created: 15

By Severity:
  🚨 Critical: 2
  ⚠️  High: 5
  📋 Medium: 6
  ℹ️  Low: 2

🚨 #101: SQL injection in login handler
⚠️ #102: Missing auth check in API endpoint
...
```

## Finding Sources

1. **Recent Commits**: Bugs introduced recently
2. **Open Issues**: Additional related bugs
3. **Closed Issues**: Regressions, incomplete fixes
4. **Codebase Scan**: Deep security/quality audit

## Verification Process

Each finding verified by:
1. **Multiple AIs** (opus/sonnet/haiku) independently verify
2. **Arbiter consensus** decides if real bug
3. **Severity assessment** from all models
4. **Impact analysis** for prioritization

Only findings that pass verification become issues.

## Issue Format

```markdown
## 🚨 CRITICAL: SQL injection in login handler

**Severity**: critical
**Source**: codebase_scan
**Consensus**: 92%

**File**: src/auth/login.js
**Line**: 42

```javascript
// Vulnerable code
const query = `SELECT * FROM users WHERE username='${username}'`
```

**AI Reasoning**: Direct string concatenation with user input
allows SQL injection attacks. Use parameterized queries.

**Impact**: 100/100

---

*Auto-created by code-review-auto*
*Verified by 3 AI models*
```

## Comparison: code-review vs code-review-auto

| Feature | code-review | code-review-auto |
|---------|-------------|------------------|
| **Autonomy** | User oversight | Fully autonomous |
| **Verification** | Optional | Always (3 AIs) |
| **Issue Creation** | Manual | Auto for verified |
| **Scope** | Configurable | Comprehensive |
| **Use Case** | Interactive | CI/CD, audits |

## Safety Features

1. **Multi-AI Verification**: 3 models must agree
2. **Consensus Threshold**: 70%+ agreement required
3. **False Positive Filter**: Arbiter rejects non-bugs
4. **Severity Assessment**: Prioritizes critical issues
5. **Evidence Required**: Must have code snippets/proof

## Use Cases

- **Security Audits**: Find vulnerabilities automatically
- **Quality Gates**: Pre-release code review
- **Regression Detection**: Check closed issues
- **CI/CD**: Auto-review on every push
- **Scheduled Audits**: Weekly/monthly scans

---

**Status**: ✅ Production ready
**Autonomy**: 100%
**Verification**: Multi-AI consensus
