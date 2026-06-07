Run the "code-sdlc-auto-continuous" workflow.

Autonomous continuous SDLC loop - scan, fix code, test, commit until clean

When you want fully automated code fixing that loops until all issues are resolved

Phases:
- Scan: Find code issues
- Fix: Apply code fixes
- Test: Verify fixes work
- Commit: Commit successful fixes
- Summary: Report results

Invoke: Workflow({ name: "code-sdlc-auto-continuous" })
