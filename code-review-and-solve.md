---
name: code-review-and-solve
description: Complete quality loop - review finds ALL issues, solve fixes ALL of them with detailed progress updates (AUTONOMOUS)
tags: [review, solve, autonomous, workflow, multi-ai]
---

# Code Review + Solve - Complete Quality Loop

Runs `/code-review` to find all issues, then `/code-solve` to automatically fix **ALL** of them using full multi-AI consensus.

## Usage

```bash
/code-review-and-solve              # Full loop - review + fix ALL issues
/code-review-and-solve --days=60    # Review last 60 days
/code-review-and-solve --maxCommits=10  # Review more commits
```

## What It Does

### Phase 1: Code Review
Runs comprehensive review:
- Recent commits
- Closed issues
- Full codebase
- Dependencies
- Security scan

Creates GitHub/GitLab issues for all findings.

### Phase 2: Wait
Waits 30 seconds for GitHub/GitLab to process issue creation.

### Phase 3: Code Solve
Auto-resolves **ALL** created issues (no cap):
- Uses full `code-solve.js` workflow for each issue
- 3 AI models generate fixes per issue (Opus, Sonnet, Haiku - rotated)
- Arbiter selects best fix via consensus
- Applied in isolated worktree (parallel-safe)
- Creates commits and closes issues
- Detailed progress: see each issue being solved

### Phase 4: Summary
Reports:
- Total issues found
- Issues fixed
- PRs created
- Success rate

## Example

```bash
$ /code-review-and-solve

🔄 CODE REVIEW + SOLVE WORKFLOW
════════════════════════════════════════════════════════════════════════════════
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

🔍 [1/10] Reviewing file: src/auth/login.js
✅ File review complete: 5 issues found (8 total so far)

✅ Deduplicated: 8 unique issues (removed 0 duplicates)
   Severity: critical=1, major=4, minor=3

📝 Creating 8 GitHub issues...
📝 [1/8] Creating issue: [CRITICAL] Security - SQL injection in user query...
✅ Created 8/8 issues
   Issue numbers: 101, 102, 103, 104, 105, 106, 107, 108

🔧 Auto-resolving 8 issues using code-solve workflow...
   Each issue reviewed by 3 AI models (Opus, Sonnet, Haiku) with arbiter consensus
📝 Will attempt to solve: 101, 102, 103, 104, 105, 106, 107, 108

🔧 [1/8] Starting code-solve for issue #101...
🔧 [2/8] Starting code-solve for issue #102...
...
✅ Code solve complete: 6/8 issues resolved (2 failed)
   ✅ Solved: 101, 102, 104, 105, 107, 108
   ❌ Failed: 103, 106

════════════════════════════════════════════════════════════════════════════════
✅ CODE REVIEW + SOLVE COMPLETE
════════════════════════════════════════════════════════════════════════════════

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

════════════════════════════════════════════════════════════════════════════════
```

## Options

- `--days=N` - Review last N days of commits (default: 30)
- `--maxCommits=N` - Max commits to review (default: 5)
- `--maxFiles=N` - Max files to review (default: 10)

**Note:** No `--maxSolve` option - solves ALL issues found (max 20 created)

## When to Run

- **Weekly:** Continuous improvement loop
- **Before releases:** Find and fix issues automatically
- **After major changes:** Cleanup after refactors
- **CI/CD:** Automated quality maintenance

## Cost Estimate

**Variable based on issues found:**
- Code review: ~$15-25 (60 agents)
- Code solve: ~$3-4 per issue (3 workers + arbiter per issue)
- **Total: $40-100+** (depends on issue count)

Example: 10 issues found = ~$20 review + ~$40 solve = **~$60 total**

## Safety

- Creates commits with fixes, closes issues automatically
- All fixes reviewed by 3 AI models + arbiter consensus
- Applied in isolated worktrees (parallel-safe, no conflicts)
- Max 20 issues created per run to prevent runaway
- Full visibility with detailed progress logging

## Alternatives

**Sequential manual:**
```bash
/code-review        # Find issues
/code-solve loop    # Fix all issues
```

**Scheduled:**
```bash
# Monday 9am: Find issues
0 9 * * 1 /code-review

# Monday 10am: Fix issues
0 10 * * 1 /code-solve loop
```

---

**Version**: 2.0  
**Updated**: 2026-06-04  
**Changes**: Solves ALL issues (no 10-issue cap), detailed progress logging, uses full code-solve workflow  
**Global**: Works on all projects
