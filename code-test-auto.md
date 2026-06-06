# code-test-auto - Autonomous Application Testing

**Fully automated comprehensive testing with auto-issue creation**

## Overview

`code-test-auto` autonomously:
- Detects application type
- Generates comprehensive test plans (multi-AI)
- Runs UI, integration, and unit tests
- Validates open issues (checks if reproducible)
- Verifies failures with multi-AI consensus
- **Auto-creates issues** for verified failures
- **NO manual intervention**

## Usage

```bash
# Full autonomous testing
claude run code-test-auto

# Custom test count
claude run code-test-auto --maxTests 30

# Validate more issues
claude run code-test-auto --maxIssues 20
```

## How It Works

### Workflow Phases

1. **Setup**: Detect platform, app type, frameworks
2. **Fetch Open Issues**: Get issues to validate
3. **Generate Test Plans**: Multi-AI test strategies
4. **Execute Tests**: Run comprehensive test suite
5. **Validate Issues**: Check if issues reproduce
6. **Multi-Model Verification**: Verify failures (3 AIs)
7. **Impact Analysis**: Prioritize by severity
8. **Create Issues**: Auto-create for verified failures

### Auto-Create Issue Criteria (ALL must be true)

- ✅ Consensus ≥ 70% (models agree it's real)
- ✅ Confidence ≥ 75%
- ✅ Severity ≥ medium
- ✅ Verified as real bug (not test issue)
- ✅ Reproducible

## Configuration

```javascript
const CONFIG = {
  workers: ['opus', 'sonnet', 'haiku'],
  arbiterModel: 'opus',
  
  autoCreate: {
    minConsensus: 70,
    minConfidence: 75,
    minSeverity: 'medium',
    realBugRequired: true,
    mustBeReproducible: true,
  },
  
  maxTestCases: 20,
  maxIssues: 10,
}
```

## Test Coverage

**Automatically detects and tests**:
- Node.js / JavaScript apps
- Python apps
- Java apps
- Go apps
- React / Vue / Angular UIs
- REST APIs
- CLI tools

**Test types**:
- Unit tests
- Integration tests
- UI tests (if has UI)
- API tests
- Edge cases
- Performance tests

## Example Output

```
═══════════════════════════════════════════
🧪 AUTONOMOUS APPLICATION TESTING
═══════════════════════════════════════════
Workers: opus, sonnet, haiku
Scope: 20 test cases, 10 issues to validate
Auto-Create: Consensus ≥ 70%, Real bugs only
═══════════════════════════════════════════

🔍 Detecting app type...
✅ App: web (javascript)
   Has UI: true
   Frameworks: react, express

📋 Fetching open issues...
📊 12 open issues

📝 Generating test plans...
✅ 3 test plans generated
✅ Selected plan 1
   Test cases: 15

🧪 Running tests...
  Running: Login form validation
  Running: API authentication
  Running: User dashboard load
  ...
✅ Tests complete
   Passed: 12
   Failed: 3

🔍 Validating open issues...
  Validating issue #42
    ✅ Reproduced
  Validating issue #43
    ❌ Could not reproduce
✅ Issue validation complete

🤖 Verifying failures...
  Verifying: Login form validation
    ✅ VERIFIED (85% consensus)
  Verifying: API authentication
    ❌ Rejected (test config issue)
✅ 2 failures verified

🎯 Analyzing impact...
✅ 2 failures prioritized

📝 Creating issues...
  ✅ Created issue #101
  ✅ Created issue #102
✅ 2 issues created

═══════════════════════════════════════════
📊 TESTING SUMMARY
═══════════════════════════════════════════
Tests run: 15
Passed: 12
Failed: 3
Verified failures: 2
Issues created: 2

By Severity:
  🚨 Critical: 0
  ⚠️  High: 1
  📋 Medium: 1
  ℹ️  Low: 0

Issue Validations:
  Reproducible: 1
  Not reproducible: 11

⚠️ #101: Test failure - Login form validation
📋 #102: Test failure - User dashboard load
```

## Issue Format

```markdown
## Test Failure: Login form validation

**Severity**: high
**Category**: UI
**Consensus**: 85%

### Test Details
**Expected**: Form should validate email format
**Actual**: Invalid emails accepted
**Error**: Email regex pattern incorrect

### AI Verification
The email validation regex allows invalid formats.
This is a real security/UX issue.

**Impact**: 75/100
**Reproducible**: Yes

### How to Reproduce
1. Navigate to login page
2. Enter invalid email (e.g., "test@")
3. Form accepts and submits

---

*Auto-created by code-test-auto*
*Verified by 3 AI models*
```

## Comparison: code-test vs code-test-auto

| Feature | code-test | code-test-auto |
|---------|-----------|----------------|
| **Autonomy** | User oversight | Fully autonomous |
| **Test Plan** | User selects | Auto-selected |
| **Issue Creation** | User decides | Auto for verified |
| **Verification** | Optional | Always (3 AIs) |
| **Use Case** | Interactive | CI/CD, scheduled |

## Verification Process

Each test failure verified by:
1. **Multiple AIs** independently verify
2. **Arbiter consensus** decides if real bug
3. **Severity assessment** from all models
4. **Reproducibility check**
5. **Impact analysis** for prioritization

Only verified failures become issues.

## Issue Validation

Also validates existing open issues:
- Attempts to reproduce each issue
- Reports: reproducible / not reproducible / no longer valid
- Helps identify stale/fixed issues
- Provides evidence for closing issues

## Safety Features

1. **Multi-AI Verification**: 3 models must agree
2. **False Positive Filter**: Rejects test config issues
3. **Consensus Threshold**: 70%+ required
4. **Reproducibility Check**: Must be reproducible
5. **Impact Scoring**: Prioritizes critical issues

## Use Cases

- **CI/CD**: Auto-test on every push
- **Scheduled**: Nightly comprehensive testing
- **Pre-Release**: Full validation before release
- **Issue Triage**: Validate backlog of issues
- **Regression Testing**: Continuous validation

---

**Status**: ✅ Production ready
**Autonomy**: 100%
**Verification**: Multi-AI consensus
