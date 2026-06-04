# Complete Workflow Guide

Detailed documentation for all Claude Code workflows.

## Quick Reference

| Workflow | Purpose | Cost | Time | Agents |
|----------|---------|------|------|--------|
| `/code-review` | 5-type code review | $15-25 | 10-15min | ~60 |
| `/code-solve` | Fix single issue | $2-4 | 2-5min | ~5 |
| `/code-solve loop` | Fix all issues | $20-30 | 20-30min | ~50 |
| `/code-test-review` | Test quality | $10-15 | 8-12min | ~30 |
| `/code-hygiene-review` | Repo cleanup | $2-5 | 5-8min | ~5 |
| `/code-review-and-solve` | Complete loop | $40-50 | 25-35min | ~70 |
| `/pr-review` | Monitor PRs | $7/day | Continuous | Variable |
| `/workflow-cleanup` | Clean history | Free | 1min | 1 |

---

## `/code-review` - Comprehensive 5-Type Review

**Description:** Finds issues across commits, codebase, dependencies, and security.

### What It Reviews

1. **Recent Commits** (Last 30 days, up to 5)
   - 3 AI workers per commit (Opus, Sonnet, Haiku - rotated)
   - Security, logic bugs, performance, code quality

2. **Closed Issues** (Recently closed, up to 5)
   - Checks if issues still broken
   - Finds incomplete fixes, regressions
   - Auto-reopens broken issues

3. **Full Codebase** (Up to 10 files)
   - 3 AI workers review each file
   - Comprehensive issue detection

4. **Dependencies** ⭐ NEW
   - npm audit, pip-audit, bundle audit, cargo audit, mvn dependency-check
   - Finds CVEs, outdated packages

5. **Security Scan** ⭐ NEW
   - Secrets in code/git history
   - OWASP Top 10 (SQL injection, XSS, command injection)
   - Exposed endpoints without auth
   - CORS misconfigurations

### Usage

```bash
/code-review                          # Full review (all 5 types)
/code-review --days=60                # Review last 60 days
/code-review --maxCommits=10          # Review more commits
/code-review --maxFiles=20            # Review more files
/code-review --autonomous=false       # Interactive mode
/code-review --multiModel=false       # Single model (faster)
```

### Output

Creates GitHub/GitLab issues for all findings with:
- Severity labels (critical, major, minor)
- Confidence scores
- Which AI model found it
- Source (commit, codebase, dependency, security)

---

## `/code-solve` - Auto-Resolve Issues

**Description:** Automatically fixes GitHub/GitLab issues with multi-AI consensus.

### How It Works

1. Fetches issue from GitHub/GitLab
2. 3 AI workers generate independent fixes
3. Arbiter selects best fix via consensus
4. Applies fix in **isolated worktree** (parallel-safe)
5. Creates PR with fix
6. Links PR to original issue

### Usage

```bash
/code-solve 123                # Fix issue #123
/code-solve loop               # Fix all open issues continuously
/code-solve all --maxIssues=5  # Fix up to 5 issues
```

### Worktree Isolation

Each fix runs in isolated git worktree:
- Creates `.claude/worktrees/code-solve-<random>/`
- Creates branch `fix/issue-123`
- No conflicts with main working tree
- Parallel-safe (run multiple simultaneously)
- Auto-cleanup after PR created

---

## `/code-test-review` - Test Quality Analysis

**Description:** Analyzes test suite quality, coverage, flakiness, and performance.

### What It Checks

1. **Test Coverage**
   - Overall coverage percentage
   - Untested critical files
   - Coverage gaps by module

2. **Flaky Test Detection**
   - Timing/sleep dependencies
   - Random data without seeds
   - External service calls without mocks
   - Race conditions in async tests
   - Network/filesystem dependencies

3. **Test Quality**
   - Mock overuse (testing mocks vs real behavior)
   - Assertion quality
   - Edge case coverage
   - Test brittleness

4. **Performance**
   - Slow tests (>1s unit, >5s integration)
   - Test suite bottlenecks
   - Parallelization opportunities

### Usage

```bash
/code-test-review                    # Full test analysis
/code-test-review --maxFiles=50      # Review more test files
```

---

## `/code-hygiene-review` - Repository Cleanup

**Description:** Finds cleanup opportunities across branches, issues, PRs, dependencies.

### What It Finds

1. **Stale Branches**
   - Merged but not deleted
   - No activity for 90+ days
   - No remote tracking

2. **Stale Issues**
   - No activity for 90+ days
   - No comments (abandoned)
   - Duplicates

3. **Stale PRs**
   - No activity for 90+ days
   - Abandoned drafts
   - PRs with merge conflicts

4. **Git History Problems**
   - Large binaries (>1MB)
   - Potential secrets in history
   - Force push history

5. **Dependencies**
   - Outdated packages
   - Security vulnerabilities
   - Unused dependencies

### Usage

```bash
/code-hygiene-review                  # Full hygiene analysis
/code-hygiene-review --staleDays=180  # Different stale threshold
```

### Output

Creates single hygiene report issue with:
- All findings categorized
- Recommended actions
- Severity levels
- Cleanup checklist

---

## `/code-review-and-solve` - Complete Quality Loop

**Description:** Runs code-review to find issues, then code-solve to fix them.

### Workflow

1. **Code Review** - Finds all issues (5 types)
2. **Wait** - 30 seconds for GitHub/GitLab to process issues
3. **Code Solve** - Auto-resolves up to 10 issues
4. **Summary** - Reports findings and fixes

### Usage

```bash
/code-review-and-solve              # Full loop
/code-review-and-solve --maxSolve=5 # Limit fixes to 5 issues
```

### When to Use

- Weekly continuous improvement
- Before releases (find and fix automatically)
- After major refactors
- CI/CD automated quality gates

---

## `/pr-review` - Continuous PR Monitoring

**Description:** Auto-discovers and reviews all open PRs continuously.

### Features

- Auto-discovers all open PRs
- Reviews each with multi-AI consensus
- Posts review comments automatically
- Optional auto-approve (with quality threshold)
- Checks every 5 minutes
- Runs forever (Ctrl+C to stop)

### Usage

```bash
/pr-review                          # Continuous mode
/pr-review --approve --threshold=90 # Auto-approve clean PRs
/pr-review 42                       # Review only PR #42
```

---

## `/workflow-cleanup` - Clean Workflow History

**Description:** Cleans accumulated workflow conversation transcripts.

### What It Does

1. Scans for workflow transcript directories
2. Analyzes sizes and patterns
3. Extracts learnings (saves to memory)
4. Clears accumulated transcripts

### Usage

```bash
/workflow-cleanup              # Interactive
/workflow-cleanup --dry-run    # Show what would be cleared
/workflow-cleanup --auto       # Auto-clear without confirmation
```

### When to Run

- Monthly routine cleanup
- Before large workflow runs
- When context limits hit

---

## Multi-AI Consensus

All workflows use the same pattern:

1. **Workers** (Opus, Sonnet, Haiku) work independently
2. **Arbiter** (rotating) selects best result
3. **Confidence scoring** filters low-quality findings
4. **Deduplication** removes duplicates

### Consensus Strategies

- **rotating** - Different arbiter each time (recommended)
- **single** - One arbiter judges all (faster)
- **majority** - Simple vote count (no arbiter)
- **weighted** - Confidence-based voting

---

## Best Practices

### Cost Management

**Run frequently (low cost):**
- `/workflow-cleanup` - Free
- `/code-solve` single issue - $2-4

**Run weekly (medium cost):**
- `/code-review` - $15-25
- `/code-test-review` - $10-15

**Run monthly (high cost):**
- `/code-review-and-solve` - $40-50
- `/code-hygiene-review` - $2-5

### Scheduling

```bash
# Weekly code review (Monday 9am)
0 9 * * 1 /code-review

# Monthly test review (1st of month)
0 9 1 * * /code-test-review

# Monthly hygiene (1st of month, 10am)
0 10 1 * * /code-hygiene-review

# Continuous PR review (always on)
/pr-review &
```

### Safety

- All workflows create PRs, don't auto-merge
- Human approval required for merging
- Worktree isolation prevents conflicts
- Max issue caps prevent runaway costs

---

## Troubleshooting

### Workflow transcripts filling disk

```bash
/workflow-cleanup
```

### Too many issues created

Adjust thresholds:
```bash
/code-review --maxCommits=2 --maxFiles=5
```

### Rate limits hit

Run sequentially instead of parallel:
```bash
/code-review
# Wait for completion
/code-solve loop
```

---

## Version

2.0.0 - 2026-06-04
