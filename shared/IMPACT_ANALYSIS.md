# Impact Analysis System

**Detects breaking changes and cross-codebase impacts in PR reviews**

## Overview

The Impact Analysis system analyzes code changes to detect:
- **Breaking Changes**: API/function signature changes that break existing code
- **High-Risk Changes**: Modifications affecting many files or core functionality
- **Dependency Impact**: Which files depend on the changed code
- **Missing Tests**: Areas lacking test coverage after changes

## How It Works

### Phase 1: Identify What Changed
Analyzes the PR diff to extract:
- Functions added/modified/removed
- Classes and methods changed
- Exports added/removed
- Type/interface changes
- API signature changes

### Phase 2: Find Dependencies
Searches codebase for:
- Import statements referencing changed files
- Direct function/class references
- Files that depend on changed exports
- Usage patterns across the codebase

### Phase 3: Detect Breaking Changes
Checks if changes are backward compatible:
- Function signature changes (parameters added/removed/reordered)
- Removed exports that other files import
- Type changes that invalidate existing usage
- Method removals from classes

### Phase 4: Assess Risk
Categorizes changes by impact:
- **HIGH**: Affects many files, core functionality, or critical paths
- **MEDIUM**: Some downstream impact
- **LOW**: Isolated changes with minimal ripple effects

### Phase 5: Check Test Coverage
Verifies that impacted areas have tests:
- Looks for test files (*.test.js, *.spec.js, __tests__/)
- Checks if changed functions/classes are tested
- Identifies missing integration tests

### Phase 6: Generate Recommendations
Provides actionable guidance:
- Flag breaking changes for review
- Suggest adding tests for high-risk areas
- Recommend splitting large PRs
- Highlight files needing updates

## Integration with pr-review

Impact analysis runs **automatically** in pr-review workflow:

```bash
# Review PR with impact analysis
claude run pr-review 123

# The workflow will:
# 1. Fetch PR diff
# 2. Run impact analysis ← NEW!
# 3. Multi-AI review (includes impact findings)
# 4. Present summary to user
# 5. User decides: APPROVE / REQUEST_CHANGES / COMMENT / SKIP
# 6. Post results to PR
```

## Output Format

### In PR Comments

Impact analysis appears in the PR comment after the AI review:

```markdown
## 🎯 Impact Analysis

**Files Impacted**: 12
**Breaking Changes**: 2
**High Risk Changes**: 1

### ⚠️ Breaking Changes Detected

#### processPayment (high)
**Type**: function_signature
**Reason**: Parameter 'options' removed - existing callers will break
**Affected Files**: 5
  - src/checkout/cart.js
  - src/checkout/payment-flow.js
  - src/api/payment-handler.js
**Fix**: Add 'options' parameter back or provide default value

#### UserAuth (high)
**Type**: removed_export
**Reason**: Export "UserAuth" was removed, breaking any files that import it
**Affected Files**: 3

### 🔥 High Risk Changes

- **fetchUserData**: Changes affect 8 files across auth module
  - Mitigation: Add integration tests for auth flow

### 📊 Impacted Files (12)

**High Risk** (3):
- src/auth/login.js
- src/auth/session.js
- src/api/user-endpoints.js

<details>
<summary>Medium Risk (9)</summary>

- src/components/LoginForm.jsx
- src/hooks/useAuth.js
...
</details>

### 📝 Missing Test Coverage

- **src/api/payment-handler.js**: No test file found
  - Add: Unit tests for payment processing
- **src/checkout/cart.js**: Changed functions not tested
  - Add: Integration tests for cart + payment flow

### 💡 Recommendations

🚨 **⚠️ 2 breaking change(s) detected**
   Review breaking changes and update affected files or add deprecation warnings

⚠️ **🔥 1 high-risk change(s)**
   Add integration tests for high-risk changes

📋 **📝 2 file(s) lack test coverage**
   Add tests for impacted areas before merging
```

### In Workflow Results

```javascript
{
  status: 'success',
  pr_number: 123,
  quality_score: 85,
  ai_decision: 'request_changes',
  user_action: 'REQUEST_CHANGES',
  consensus: 87,
  approved: false,
  changes_requested: true,
  impact: {
    breaking_changes: 2,
    high_risk: 1,
    impacted_files: 12,
    missing_tests: 2,
    has_breaking_changes: true,
    has_high_risk: true
  }
}
```

## Auto-Decision Logic

pr-review uses impact analysis to inform decisions:

```javascript
if (ai_decision === 'approve' && no breaking changes && few high-risk) {
  → APPROVE (auto-merge safe)
}

if (breaking_changes > 0) {
  → REQUEST_CHANGES (requires fixes)
}

if (ai_decision === 'request_changes') {
  → REQUEST_CHANGES (AI found issues)
}

else {
  → COMMENT (provide feedback, don't approve/reject)
}
```

## Configuration Options

```javascript
await analyzeImpact(agent, changes, {
  includeTests: true,           // Check test coverage (default: true)
  maxDepth: 2,                  // How deep to analyze dependencies (default: 2)
  checkBreakingChanges: true    // Detect breaking changes (default: true)
})
```

## Example Scenarios

### Scenario 1: Harmless Refactor
**Changes**: Rename internal variable, update comments
**Impact**:
- 0 breaking changes
- 0 high-risk
- 1 file impacted
**Decision**: APPROVE ✅

### Scenario 2: API Signature Change
**Changes**: Add required parameter to public function
**Impact**:
- 1 breaking change (function signature)
- 15 files impacted
- 5 missing tests
**Decision**: REQUEST_CHANGES ⚠️

### Scenario 3: Safe Feature Add
**Changes**: New function, new export, new test
**Impact**:
- 0 breaking changes
- 0 high-risk
- 0 files impacted (new code, no dependencies yet)
**Decision**: APPROVE ✅

### Scenario 4: Core Utility Update
**Changes**: Modify widely-used utility function
**Impact**:
- 0 breaking changes (backward compatible)
- 1 high-risk (used in 50+ files)
- 10 missing tests
**Decision**: REQUEST_CHANGES (needs more tests) ⚠️

## Benefits

1. **Catch Breaking Changes Early**
   - Detect API breakage before merge
   - Prevent production incidents
   - Save debugging time

2. **Understand Impact Scope**
   - See how many files affected
   - Identify high-risk changes
   - Make informed merge decisions

3. **Improve Test Coverage**
   - Highlight untested areas
   - Ensure changes are verified
   - Reduce regression risk

4. **Better Code Reviews**
   - AI reviewers see impact data
   - More informed recommendations
   - Context-aware quality assessment

5. **Transparent Decisions**
   - Clear reasoning for approve/reject
   - Actionable recommendations
   - Full visibility into analysis

## Architecture

```
┌─────────────┐
│   PR Diff   │
└──────┬──────┘
       │
       v
┌─────────────────────┐
│ Phase 1: Identify   │
│ What Changed        │
│ (functions, exports)│
└──────┬──────────────┘
       │
       v
┌─────────────────────┐
│ Phase 2: Find       │
│ Dependencies        │
│ (grep imports/refs) │
└──────┬──────────────┘
       │
       v
┌─────────────────────┐
│ Phase 3: Detect     │
│ Breaking Changes    │
│ (signature checks)  │
└──────┬──────────────┘
       │
       v
┌─────────────────────┐
│ Phase 4: Assess     │
│ Risk Level          │
│ (impact analysis)   │
└──────┬──────────────┘
       │
       v
┌─────────────────────┐
│ Phase 5: Check      │
│ Test Coverage       │
│ (find test files)   │
└──────┬──────────────┘
       │
       v
┌─────────────────────┐
│ Phase 6: Generate   │
│ Recommendations     │
│ (actionable items)  │
└─────────────────────┘
```

## Performance

- **Fast**: Uses grep for dependency search (no full AST parsing)
- **Scalable**: Handles large PRs (truncates at 5000 lines)
- **Efficient**: Parallel AI analysis where possible
- **Accurate**: Multi-phase approach catches edge cases

## Limitations

1. **Language Support**: Best for JavaScript/TypeScript (can extend to other languages)
2. **Dynamic Imports**: May miss runtime-generated imports
3. **Indirect Dependencies**: Only checks direct dependencies (configurable with maxDepth)
4. **Test Detection**: Relies on naming conventions (*.test.js, *.spec.js)

## Future Enhancements

- [ ] Support for Python, Go, Rust, Java
- [ ] AST-based analysis for 100% accuracy
- [ ] Indirect dependency tracking (N-level deep)
- [ ] Integration test suggestions
- [ ] Historical impact correlation (similar PRs)
- [ ] Auto-fix generation for breaking changes
- [ ] Visual impact graph in PR comments

## API Reference

### analyzeImpact(agent, changes, options)

**Parameters**:
- `agent` (Function): The agent function for AI analysis
- `changes` (Object):
  - `files` (string[]): List of changed files
  - `diff` (string): Full PR diff
- `options` (Object):
  - `includeTests` (boolean): Check test coverage (default: true)
  - `maxDepth` (number): Dependency search depth (default: 2)
  - `checkBreakingChanges` (boolean): Detect breaking changes (default: true)

**Returns**: Promise<Object>
```javascript
{
  high_risk_changes: [...],
  impacted_files: [...],
  breaking_changes: [...],
  missing_tests: [...],
  recommendations: [...]
}
```

### formatImpactAnalysis(impact)

**Parameters**:
- `impact` (Object): Result from analyzeImpact()

**Returns**: string (markdown formatted report)

## Usage in Other Workflows

```javascript
import { analyzeImpact, formatImpactAnalysis } from './shared/impact-analysis.js'

// In your workflow
const impact = await analyzeImpact(agent, {
  files: changedFiles,
  diff: diffContent
})

log(formatImpactAnalysis(impact))

// Use impact data
if (impact.breaking_changes.length > 0) {
  log('⚠️ Breaking changes detected!')
}
```

## Related Systems

- **pr-review**: Primary integration (auto-runs impact analysis)
- **code-review**: Could benefit from impact analysis for commit reviews
- **code-test**: Uses impact to prioritize test areas
- **ai-attribution**: Shows which AI detected each impact

---

**Status**: ✅ Implemented and integrated into pr-review
**Author**: AI-Powered Development System
**Version**: 1.0.0
