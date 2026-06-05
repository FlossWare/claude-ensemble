# Complete Workflow Guide

Detailed documentation for all Claude Code workflows.

## Usage Examples

### Natural Language (Recommended)

Just describe what you want:

```bash
# Review recent work
"code-review my last commit"
"review the last 3 commits for security issues"
"check my recent changes for bugs"

# Review specific files/directories
"review src/auth/login.js for security issues"
"code-review the src/api directory"
"check src/database/ for SQL injection"

# Fix issues
"solve issue #42"
"fix all open bugs"
"auto-resolve good-first-issue tickets"

# Complete quality loop
"review my code and fix everything"
"find and fix all issues from this week"

# Test quality
"review our test coverage"
"find flaky tests"

# Repository cleanup
"clean up stale branches"
"check for outdated dependencies"
```

### Slash Commands

```bash
/code-review              # Review: commits, codebase, deps, security
/code-solve 42            # Fix issue #42 with multi-AI consensus
/code-solve loop          # Fix all open issues
/code-review-and-solve    # Find ALL issues → fix ALL issues
/code-test-review         # Analyze test quality
/code-hygiene-review      # Repository cleanup
```

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
# Full codebase review
/code-review                          # Full review (all 5 types)
/code-review --days=60                # Review last 60 days
/code-review --maxCommits=10          # Review more commits
/code-review --maxFiles=20            # Review more files

# Review specific file or directory
/code-review --path=src/auth/login.js     # Single file
/code-review --file=utils/validator.js    # Single file (alias)
/code-review --dir=src/api                # Directory

# Options
/code-review --autonomous=false       # Interactive mode
/code-review --multiModel=false       # Single model (faster)
```

### Natural Language Examples

```bash
"code-review my recent commits"
"review the last 3 commits for bugs"
"review src/auth/login.js for security issues"
"code-review the src/api directory"
"check src/database/ for SQL injection vulnerabilities"
```

### Output

Creates GitHub/GitLab issues for all findings with:
- Severity labels (critical, major, minor)
- Confidence scores
- Which AI model found it
- Source (commit, codebase, dependency, security)

---

## `/code-solve` - Auto-Resolve Issues 🔒 Security Hardened

**Description:** Automatically fixes GitHub/GitLab issues with multi-AI consensus.

**Status:** ✅ Production ready, security hardened (v1.1.2)

### How It Works

1. Fetches issue from GitHub/GitLab
2. **Validates inputs** (prevents shell injection attacks)
3. 3 AI workers generate independent fixes (rotated: opus/sonnet/haiku)
4. Arbiter selects best fix via consensus (rotated based on issue number)
5. Applies fix in **isolated worktree** (parallel-safe)
6. Creates PR with fix
7. Links PR to original issue

### Security Features (2026-06-05)

- ✅ **Input validation**: Issue IDs must be positive integers (1-999999999)
- ✅ **Label validation**: Alphanumeric + dash/underscore only (prevents injection)
- ✅ **Shell injection prevention**: Quoted variables, jq parsing instead of grep
- ✅ **Error handling**: Clear errors for missing/invalid data

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

### Registration Requirements

- ✅ `export const meta` block at line 4 (must be FIRST statement)
- ✅ YAML frontmatter in code-solve.md
- ✅ No import statements (all functions inlined)
- ✅ Appears in skills list as `/code-solve`

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

**Description:** Runs code-review to find issues, then code-solve to fix **ALL** of them with full multi-AI consensus.

### Workflow

1. **Code Review** - Finds all issues (5 types: commits, codebase, closed issues, dependencies, security)
2. **Create Issues** - Creates GitHub/GitLab issues for all findings (max 20)
3. **Wait** - 10 seconds for GitHub/GitLab to process issues
4. **Code Solve** - Auto-resolves **ALL** created issues using full code-solve workflow
   - Each issue reviewed by 3 AI models (Opus, Sonnet, Haiku - rotated per issue)
   - Arbiter selects best fix via consensus
   - Applied in isolated worktree (parallel-safe)
5. **Summary** - Reports findings and fixes with detailed breakdown

### Key Features

✅ **No arbitrary caps** - Solves ALL issues found during review (not just 10)
✅ **Full multi-AI consensus** - Uses the complete code-solve workflow for each fix
✅ **Detailed progress updates** - See exactly what's happening at each step:
  - Which commits/files being reviewed
  - Issues found per commit/file
  - Severity breakdown (critical/major/minor)
  - Issue creation progress
  - Fix attempt progress with success/failure tracking
✅ **Correct metrics** - success_rate = issues_solved / issues_attempted (not broken calculation)

### Usage

```bash
/code-review-and-solve              # Full loop - review + fix ALL issues
/code-review-and-solve --days=60    # Review last 60 days
/code-review-and-solve --maxCommits=10  # Review more commits
```

### Example Output

```
⚙️  Configuration:
   Review window: Last 30 days
   Max commits: 5
   Max files: 10
   Confidence threshold: 70%
   Max issues to create: 20

📝 [1/5] Getting diff for a1b2c3d4: "fix: resolve authentication bug..."
🔍 [1/5] Reviewing commit a1b2c3d4...
✅ Commit review complete: 3 issues found (3 total so far)
   Breakdown: a1b2c3d4: 2, e5f6g7h8: 1

✅ Deduplicated: 8 unique issues (removed 2 duplicates)
   Severity: critical=1, major=4, minor=3

📝 Creating 8 GitHub issues...
✅ Created 8/8 issues
   Issue numbers: 101, 102, 103, 104, 105, 106, 107, 108

🔧 Auto-resolving 8 issues using code-solve workflow...
   Each issue reviewed by 3 AI models (Opus, Sonnet, Haiku) with arbiter consensus
🔧 [1/8] Starting code-solve for issue #101...
...
✅ Code solve complete: 6/8 issues resolved (2 failed)
   ✅ Solved: 101, 102, 104, 105, 107, 108
   ❌ Failed: 103, 106

📊 REVIEW RESULTS:
   Total findings: 8
   Critical: 1
   Major: 4
   Minor: 3
   Issues created: 8

🔧 SOLVE RESULTS:
   Issues attempted: 8
   Issues solved: 6
   Success rate: 75%
```

### When to Use

- Weekly continuous improvement (finds and fixes everything automatically)
- Before releases (comprehensive review + auto-fix)
- After major refactors (verify quality)
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

## Common Workflows

### Scenario 1: Before Committing

**Goal:** Catch issues before they enter git history

```bash
# Natural language
"review my uncommitted changes for bugs"
"check this code for security issues"

# Or just commit - Claude will review automatically if hooks configured
git add .
git commit -m "feat: new feature"
```

**What happens:**
- Reviews working tree changes
- Finds bugs, security issues, code quality problems
- You can fix issues before committing

---

### Scenario 2: After Committing

**Goal:** Review recent work

```bash
# Natural language
"code-review my last commit"
"review commits from today"
"check the last 3 commits for issues"

# Slash command
/code-review --days=1           # Last 24 hours
/code-review --maxCommits=3     # Last 3 commits
```

**What happens:**
- Reviews specified commits
- Creates GitHub/GitLab issues for findings
- You decide which to fix

---

### Scenario 3: Before Creating PR

**Goal:** Clean branch before review

```bash
# Natural language (BEST - finds AND fixes)
"review my branch and fix everything you find"

# Slash command
/code-review-and-solve

# Manual two-step
/code-review              # Find issues
/code-solve loop          # Fix all issues
```

**What happens:**
- Reviews all changes on branch
- Finds all issues (commits + codebase + security + deps)
- Auto-fixes all issues with multi-AI consensus
- Creates commits with fixes
- Branch is clean and ready for PR

---

### Scenario 4: Weekly Maintenance

**Goal:** Keep codebase healthy

```bash
# Monday morning routine
"review all commits from last week"
/code-review --days=7

# Fix everything found
"fix all open bugs"
/code-solve loop

# Check test quality monthly
/code-test-review

# Clean up repo quarterly
/code-hygiene-review
```

---

### Scenario 5: Before Release

**Goal:** Comprehensive quality check

```bash
# Step 1: Find and fix everything
/code-review-and-solve

# Step 2: Check test quality
/code-test-review

# Step 3: Clean up repository
/code-hygiene-review

# Step 4: Verify all PRs pass
/pr-verify
```

**Cost:** ~$50-75 total for comprehensive pre-release check

---

### Scenario 6: Fixing Specific Issues

**Goal:** Auto-resolve GitHub/GitLab issues

```bash
# Single issue
"solve issue #42"
/code-solve 42

# All issues with label
"fix all bugs labeled 'good-first-issue'"

# All open issues (careful!)
/code-solve loop
```

**What happens:**
- 3 AI models generate fixes independently
- Arbiter selects best fix
- Applied in isolated worktree (parallel-safe)
- Commit created and issue closed

---

### Scenario 7: Review Specific Files/Directories

**Goal:** Focus review on specific code

```bash
# Single file
"review src/auth/login.js for security issues"
"check utils/validator.js for bugs"

# With slash command
/code-review --path=src/api/users.js

# Directory
"review the src/database directory"
"code-review src/api/ for SQL injection"

# With slash command
/code-review --dir=src/auth

# Multiple related files (natural language)
"review all authentication-related files"
"check all API endpoint handlers for security issues"
```

**What happens:**
- Reviews only the specified file(s) or directory
- Skips commit and closed issue reviews
- Full multi-AI consensus on target files
- Creates issues for findings in those files only

**When to use:**
- After working on specific module
- Before committing changes to critical files
- Security audit of authentication/payment code
- New developer wants to understand a module

---

### Scenario 8: Continuous Quality

**Goal:** Always-on quality monitoring

```bash
# Set up continuous PR review (runs forever)
/pr-review

# Or schedule periodic reviews (cron)
# Every Monday 9am
0 9 * * 1 /code-review

# Every Monday 10am
0 10 * * 1 /code-solve loop
```

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
