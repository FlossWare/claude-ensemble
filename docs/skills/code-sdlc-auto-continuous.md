Run the "code-sdlc-auto-continuous" workflow.

Autonomous continuous SDLC loop - runs all 7 phases repeatedly until codebase is clean

When you want fully automated SDLC pipeline that loops until no issues remain

**How It Works:**
This workflow delegates to `sdlc-loop.sh` to avoid workflow nesting limitations. The script runs all 7 SDLC phases in sequence:

1. **Development**: code-review-auto + code-solve-auto
2. **Testing**: code-test-auto
3. **PR Review**: code-pr-review-auto
4. **Security**: code-security-auto
5. **Documentation**: code-doc-auto
6. **Release**: code-release-notes-auto
7. **Summary**: Aggregate results

Loops until:
- ✅ No issues found
- ✅ No PRs to review
- ✅ No security vulnerabilities
- ✅ All code documented
- OR max iterations reached

**Usage:**
```bash
# Via workflow (default: 5 iterations, 200k tokens each)
claude run code-sdlc-auto-continuous

# Custom iterations/budget
claude run code-sdlc-auto-continuous iterations=10 budget=500k

# Via shell script directly
sdlc-loop.sh 10 500k
```

**Output:**
- Commits fixes directly to current branch
- Creates issues/PRs for all findings
- Comprehensive final summary

**Note:** Each workflow runs in a fresh Claude session to avoid nesting errors. The script is installed in your PATH and works from any project directory.

Invoke: Workflow({ name: "code-sdlc-auto-continuous", args: { iterations: 5, budget: "200k" } })
