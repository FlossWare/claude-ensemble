---
name: code-review-and-solve
description: Complete quality loop - review finds issues, solve fixes them automatically (AUTONOMOUS)
tags: [review, solve, autonomous, workflow]
---

# Code Review + Solve - Complete Quality Loop

Runs `/code-review` to find all issues, then `/code-solve` to automatically fix them.

## Usage

```bash
/code-review-and-solve              # Full loop
/code-review-and-solve --maxSolve=5 # Limit fixes to 5 issues
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
Auto-resolves up to 10 issues:
- Fetches all open issues
- 3 AI models generate fixes per issue
- Arbiter selects best fix
- Creates PR with fix
- Links PR to original issue

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
═══════════════════════════════════════

🔍 Running comprehensive code review...
✅ Code review complete
   Issues found: 23
   Critical: 3
   Major: 12
   Minor: 8

⏳ Waiting 30 seconds for GitHub/GitLab...
✅ Wait complete

🔧 Auto-resolving issues...
📝 Will attempt to solve up to 10 issues
✅ Code solve complete
   Issues attempted: 10
   PRs created: 8

═══════════════════════════════════════
✅ CODE REVIEW + SOLVE COMPLETE
═══════════════════════════════════════

📊 REVIEW RESULTS:
   Total findings: 23
   Critical: 3
   Major: 12
   Minor: 8

🔧 SOLVE RESULTS:
   Issues attempted: 10
   PRs created: 8
   Success rate: 80%

═══════════════════════════════════════
```

## Options

- `--maxSolve=N` - Max issues to fix (default: 10)
- `--days=N` - Review last N days of commits (default: 30)
- `--maxCommits=N` - Max commits to review (default: 5)
- `--maxFiles=N` - Max files to review (default: 10)

## When to Run

- **Weekly:** Continuous improvement loop
- **Before releases:** Find and fix issues automatically
- **After major changes:** Cleanup after refactors
- **CI/CD:** Automated quality maintenance

## Cost Estimate

**Per run:**
- Code review: ~$15-25 (60 agents)
- Code solve: ~$24 (10 issues × 3 workers + arbiters)
- **Total: ~$40-50**

## Safety

- Creates PRs, doesn't auto-merge
- All fixes reviewed by arbiters
- Human approval required for merging
- Max issues capped to prevent runaway

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

**Version**: 1.0  
**Created**: 2026-06-04  
**Global**: Works on all projects
