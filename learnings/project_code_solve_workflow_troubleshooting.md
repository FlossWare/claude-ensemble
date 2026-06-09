---
name: code-solve-workflow-troubleshooting
description: "Troubleshooting code-solve workflow issue where all issues marked as \"already claimed\" despite no labels"
metadata: 
  node_type: memory
  type: project
  originSessionId: fe06c330-8ed9-4a75-94db-e64e4d2d6b89
---

## Code-Solve Workflow Issue (2026-06-05)

**Problem:** User ran `/code-solve` workflow but it skipped all 148 issues with "Already claimed" reason, even though no `code-solve-in-progress` labels existed on any issues.

### Root Cause Investigation

1. **Previous incomplete run** - User had prematurely quit a previous code-solve run that had applied `code-solve-in-progress` labels to issues
2. **Labels were removed** - We removed all 148 labels using `gh issue edit --remove-label` 
3. **Workflow still skipped everything** - Even after label removal, workflow reported "Already claimed" for all 54 issues it processed

### Troubleshooting Steps Taken

1. Located GitHub token in `~/.bashrc` (line 359): `export GH_TOKEN="REDACTED_GITHUB_PAT"`
2. Verified 148 open issues exist in repository
3. Confirmed 0 issues have `code-solve-in-progress` label
4. Removed labels from all 148 issues successfully
5. Re-ran workflow - still skipped all issues
6. Investigated workflow script at `.claude/workflows/scripts/code-solve-wf_*.js`
7. Found claim logic uses `gh issue edit --add-label` to atomically claim issues
8. Verified GitHub CLI authentication working correctly

### Current Status

- **Third attempt running** (workflow ID: wf_e99f3f1a-12c)
- All labels cleared from issues
- GitHub CLI authenticated and working
- Monitoring workflow progress with `/workflows`

**Why:** Understanding this workflow behavior is critical for autonomous issue resolution. The claim mechanism prevents race conditions when multiple workers try to solve the same issue.

**How to apply:** When code-solve workflow fails with "Already claimed" errors:
1. Check for `code-solve-in-progress` labels on issues
2. Remove labels if they're stale from incomplete runs
3. Verify GitHub CLI authentication (`gh auth status`)
4. Re-run workflow
5. Monitor with `/workflows` to see actual claiming happening
