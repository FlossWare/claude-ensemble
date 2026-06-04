---
name: code-review-and-solve
description: This skill should be used when the user asks to "review and fix all code", "find and fix everything", "complete quality loop", "review then solve", "full code cleanup", or discusses finding ALL issues and fixing ALL of them automatically.
version: 2.0.0
---

# Code Review + Solve - Complete Quality Loop

Complete autonomous loop: review finds ALL issues → solve fixes ALL of them → verify fixes didn't introduce bugs.

## Features

- **5-Type Code Review** - Commits, codebase, closed issues, dependencies, security
- **Auto-Create Issues** - GitHub/GitLab issues for all findings
- **Solve ALL Issues** - No arbitrary caps, fixes everything found
- **Multi-AI Consensus** - 3 models (Opus, Sonnet, Haiku) + arbiter per fix
- **Verification Phase** - Re-reviews fixes to catch regressions
- **Detailed Progress** - Real-time logging of every step
- **Platform Agnostic** - Works with GitHub, GitLab, Bitbucket

## Usage

```bash
# Full loop - review + fix + verify ALL issues
/code-review-and-solve

# Review last 60 days
/code-review-and-solve --days=60

# Review more commits
/code-review-and-solve --maxCommits=10
```

## Natural Language

```bash
"review my code and fix everything you find"
"find and fix all issues from this week"
"complete quality loop on my branch"
```

## Workflow Phases

1. **Code Review** - Find ALL issues across:
   - Recent commits (last 30 days)
   - Closed issues (check for regressions)
   - Full codebase (up to 10 files)
   - Dependencies (npm, pip, maven, cargo, bundle)
   - Security scan (secrets, OWASP Top 10, exposed endpoints)

2. **Create Issues** - Creates GitHub/GitLab issues for all findings (max 20)

3. **Wait** - 10 seconds for GitHub/GitLab to process

4. **Code Solve** - Auto-resolves **ALL** created issues:
   - Each issue reviewed by 3 AI models independently
   - Rotating arbiter selects best fix
   - Applied in isolated worktree (parallel-safe)
   - Commits created and issues closed

5. **Verify Fixes** - Reviews modified files:
   - Checks fixes didn't introduce new bugs
   - Looks for syntax errors, regressions
   - Reports pass/fail status

6. **Summary** - Complete report:
   - Issues found by severity
   - Issues solved vs attempted
   - Verification results

## Options

- `--days=N` - Review last N days of commits (default: 30)
- `--maxCommits=N` - Max commits to review (default: 5)
- `--maxFiles=N` - Max files to review (default: 10)

## Example Output

```
⚙️  Configuration:
   Review window: Last 30 days
   Max commits: 5
   Max files: 10

📝 [1/5] Getting diff for a1b2c3d4...
🔍 [1/5] Reviewing commit a1b2c3d4...
✅ Commit review complete: 3 issues found

✅ Deduplicated: 8 unique issues
   Severity: critical=1, major=4, minor=3

📝 Creating 8 GitHub issues...
✅ Created 8/8 issues
   Issue numbers: 101, 102, 103, 104, 105, 106, 107, 108

🔧 Auto-resolving 8 issues...
🔧 [1/8] Starting code-solve for issue #101...
✅ Code solve complete: 6/8 issues resolved
   ✅ Solved: 101, 102, 104, 105, 107, 108
   ❌ Failed: 103, 106

🔍 Verifying 6 fixes...
✅ Verification passed - no new issues

📊 REVIEW RESULTS:
   Total findings: 8
   Critical: 1, Major: 4, Minor: 3
   Issues created: 8

🔧 SOLVE RESULTS:
   Issues attempted: 8
   Issues solved: 6
   Success rate: 75%

🔍 VERIFICATION RESULTS:
   Files verified: 6
   New issues introduced: 0
   Verification: ✅ PASSED
```

## When to Use

- **Before PR** - Clean branch before review
- **Weekly** - Continuous improvement loop
- **Before Release** - Comprehensive cleanup
- **After Refactor** - Verify quality maintained

## Cost Estimate

**Variable based on issues found:**
- Code review: ~$15-25 (60 agents)
- Code solve: ~$3-4 per issue
- Verification: ~$5-10 (reviews modified files)
- **Total: $40-100+** (depends on issue count)

Example: 10 issues = ~$20 review + ~$40 solve + ~$7 verify = **~$67 total**

## Files

- `~/.claude/workflows/code-review-and-solve.js`
- `~/.claude/workflows/code-solve.js` (called for each fix)
- `~/.claude/workflows/shared/` (consensus modules)

---

**Version**: 2.0  
**Updated**: 2026-06-04  
**Global**: Works on all projects
