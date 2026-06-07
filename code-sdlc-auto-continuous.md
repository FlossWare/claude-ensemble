Run the "code-sdlc-auto-continuous" workflow.

Autonomous continuous SDLC loop - scan for bugs/security/quality, fix, test, commit until clean

When you want fully automated code fixing that loops until all issues (including critical security vulns) are resolved

**What It Scans:**
- **Bugs**: null pointer exceptions, resource leaks, race conditions, logic errors, infinite loops
- **Security**: SQL injection, XSS, command injection, path traversal, hardcoded secrets, weak crypto
- **Code Quality**: unused variables, duplicate code, complex methods, missing null checks

**How It Works:**
1. Scans codebase for critical/high severity issues across all dimensions
2. Auto-fixes up to 5 issues per iteration with suggested code changes
3. Tests each fix to verify it works
4. Commits successful fixes automatically
5. Loops until codebase is clean or max 10 iterations

**Output:**
- Commits fixes directly to current branch
- Reports total issues found/fixed across all iterations
- Stops when no more critical/high issues remain

Phases:
- Scan: Find bugs, security vulns, code quality issues
- Fix: Apply code fixes with suggested changes
- Test: Verify fixes work (smoke tests)
- Commit: Commit successful fixes
- Summary: Report results

Invoke: Workflow({ name: "code-sdlc-auto-continuous" })
