---
name: code-skills-autonomous
description: /code-solve and /code-review must run autonomously without user prompts or confirmation
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 492f95ca-eb43-4b52-960e-5130fcf5f46a
---

# Code Skills Must Be Autonomous

**/code-solve and /code-review are autonomous skills** - they must run completely without user interaction.

**Why:** These skills are designed for automated workflows, continuous integration, and background processing. User prompts break automation.

**How to apply:**
- Never add `AskUserQuestion` to these workflows
- Never prompt for confirmation before taking action
- Default to sensible behavior (e.g., solve all issues, review all commits)
- Use args for configuration, not interactive prompts
- Only fail with clear error messages if prerequisites missing

## Current Implementation

### /code-solve
✅ **Autonomous** - Defaults to solving all open issues
- No issue number? Solves all
- Claims issues automatically
- Commits fixes automatically
- Closes issues automatically
- Works in parallel with worktree isolation

### /code-review  
✅ **Autonomous** - Reviews commits/issues/codebase
- Multi-platform: GitHub, GitLab, Bitbucket (GitHub/GitLab fully supported)
- Reviews: recent commits, open issues, closed issues, full codebase
- Multi-model by default (Opus, Sonnet, Haiku rotation)
- **Smart issue handling:**
  - Checks closed issues before creating new ones
  - Reopens matching closed issues instead of creating duplicates
  - Auto-reopens issues that weren't truly fixed
- Creates issues automatically (GitHub/GitLab)
- No confirmation needed
- Configurable via args: days, maxCommits, maxFiles, maxIssues

### /code-review-and-solve
✅ **Autonomous** - Full loop: review → create issues → solve → verify
- Self-contained (no nested workflow() calls)
- Uses pipeline with inline agent calls
- Simplified issue solving vs full code-solve
- No multi-AI consensus (uses single agent per stage)
- Must avoid nested workflow() calls for skill registration

## Anti-Patterns to Avoid

❌ Don't ask: "Should I solve issue #X?"
✅ Do: Just solve it

❌ Don't ask: "Create GitHub issue for this finding?"
✅ Do: Create it (with confidence threshold)

❌ Don't prompt: "Apply fix? (y/n)"
✅ Do: Apply and commit

❌ Don't confirm: "Push to remote?"
✅ Do: Commit locally (let user push manually or via git hooks)

## Edge Cases

**When it's OK to fail fast:**
- Missing GITLAB_TOKEN/gh auth
- Git repository not found
- No open issues to solve

**Return status instead of prompting:**
```javascript
return {
  status: 'success',
  issues_solved: 5,
  issues_failed: 0
}
```

## Multi-Agent Pattern: Console Output

**Always emit issue numbers to console for tracking:**

```javascript
// When closing issues
console.log(`CLOSED_ISSUE: #${issueNumber}`)

// When reopening issues  
console.log(`REOPENED_ISSUE: #${issueNumber}`)
```

**Why:** Enables external tools/scripts to parse workflow output and track which issues were affected. Critical for CI/CD integration and automation pipelines.

**Implementation:**
- code-solve: Emits `CLOSED_ISSUE: #N` when closing
- code-review: Emits `REOPENED_ISSUE: #N` when reopening broken issues

Both also echo to bash output for dual-channel visibility.

---

**Created**: 2026-06-03
**Context**: User reminder that these skills must be autonomous
**Related**: [[workflow-imports-lesson]]
