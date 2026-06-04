---
name: code-test-review
description: Comprehensive test quality review - coverage gaps, flaky tests, test value, performance (AUTONOMOUS)
tags: [testing, quality, autonomous]
---

# Code Test Review - Test Suite Quality Analysis

Autonomous multi-AI review of test quality, coverage, flakiness, and performance.

## Usage

```bash
/code-test-review                    # Full test quality analysis
/code-test-review --maxFiles=50      # Review more test files
/code-test-review --autonomous=false # Interactive mode
```

## What It Reviews

### 1. **Test Coverage**
- Overall coverage percentage
- Untested critical files
- Coverage gaps by module
- Missing edge case tests

### 2. **Flaky Test Detection**
- Timing/sleep dependencies
- Random data without seeds
- External service calls without mocks
- Race conditions in async tests
- Hardcoded dates/times
- Network/filesystem dependencies

### 3. **Test Quality**
- Mock overuse (testing mocks vs real behavior)
- Assertion quality (meaningful vs trivial)
- Edge case coverage
- Test brittleness (implementation coupling)
- Readability and maintainability

### 4. **Performance**
- Slow tests (>1s unit, >5s integration)
- Test suite bottlenecks
- Parallelization opportunities

## Multi-AI Consensus

- **3 AI models** review each test file (Opus, Sonnet, Haiku)
- **Rotating arbiters** verify findings
- **Confidence scoring** filters low-quality findings
- **Auto-deduplication** of similar issues

## Output

Creates GitHub/GitLab issues for:
- Critical coverage gaps
- Flaky test indicators
- Poor test quality
- Slow tests

## Example

```bash
$ /code-test-review

🧪 TEST QUALITY REVIEW
═══════════════════════════════════════
Mode: AUTONOMOUS
Analyzing: Test coverage, quality, flakiness, performance
═══════════════════════════════════════

🔍 Discovering test files...
✅ Found 45 test files
   Framework: Jest

📊 Analyzing test coverage...
✅ Coverage: 68%
   Untested files: 12

🔄 Detecting flaky tests...
✅ Found 3 potentially flaky test files

⚖️  Assessing test quality...
✅ Reviewed 45 test files for quality

⚡ Analyzing test performance...
✅ Found 7 slow tests

⚖️  Running consensus verification...
✅ 23 unique findings

📝 Creating issues for 23 findings...
✓ Created issue #101
✓ Created issue #102
...

═══════════════════════════════════════
✅ TEST QUALITY REVIEW COMPLETE
   Total findings: 23
   Issues created: 23
═══════════════════════════════════════
```

## Options

- `--maxFiles=N` - Max test files to review (default: 20)
- `--autonomous=false` - Interactive mode (no auto-issue creation)
- `--multiModel=false` - Single model (faster, less thorough)

## When to Run

- **After major refactors** - Ensure tests still valuable
- **Before releases** - Verify test quality
- **Monthly** - Catch flaky/slow tests early
- **CI/CD** - Automated quality gates

---

**Version**: 1.0  
**Created**: 2026-06-04  
**Global**: Works on all projects
