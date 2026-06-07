# Claude Code Workflow Permissions Guide

## Overview

This document provides a comprehensive guide to setting up permissions for all custom Claude Code workflows in this repository. Proper permissions prevent "don't ask mode" errors and enable autonomous workflow execution.

## Table of Contents

- [Quick Setup](#quick-setup)
- [Required Permissions by Platform](#required-permissions-by-platform)
- [Permissions by Workflow](#permissions-by-workflow)
- [Troubleshooting](#troubleshooting)

---

## Quick Setup

### Copy-Paste Complete Permissions

Add these to your `~/.claude/settings.json` under `permissions.allow`:

```json
{
  "permissions": {
    "allow": [
      // GitHub CLI
      "Bash(gh --version)",
      "Bash(gh auth *)",
      "Bash(gh repo *)",
      "Bash(gh issue *)",
      "Bash(gh issue create *)",
      "Bash(gh pr *)",
      "Bash(gh pr list *)",
      "Bash(gh pr view *)",
      "Bash(gh pr diff *)",
      "Bash(gh pr comment *)",
      "Bash(gh pr review *)",
      "Bash(gh release *)",
      "Bash(gh release create *)",
      "Bash(gh run *)",
      "Bash(gh org *)",

      // GitLab CLI
      "Bash(glab --version)",
      "Bash(glab auth *)",
      "Bash(glab issue *)",
      "Bash(glab issue create *)",
      "Bash(glab issue note *)",
      "Bash(glab pr *)",
      "Bash(glab pr list *)",
      "Bash(glab pr view *)",
      "Bash(glab pr diff *)",
      "Bash(glab pr comment *)",
      "Bash(glab pr review *)",
      "Bash(glab release *)",
      "Bash(glab release create *)",
      "Bash(glab mr *)",
      "Bash(glab mr list *)",

      // Bitbucket CLI (future-proofing)
      "Bash(bb --version)",
      "Bash(bb auth *)",
      "Bash(bb issue *)",
      "Bash(bb issue create *)",
      "Bash(bb pr *)",
      "Bash(bb pr list *)",
      "Bash(bb pr view *)",
      "Bash(bb pr diff *)",
      "Bash(bb pr comment *)",
      "Bash(bb pr review *)",
      "Bash(bb release *)",
      "Bash(bb release create *)",
      "Bash(bb mr *)",

      // Git commands
      "Bash(git *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git push *)",
      "Bash(git pull *)",
      "Bash(git checkout *)",
      "Bash(git branch *)",
      "Bash(git merge *)",
      "Bash(git tag *)",
      "Bash(git remote *)",
      "Bash(git fetch *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git init *)",
      "Bash(git config *)",

      // Node.js / NPM
      "Bash(npm audit *)",
      "Bash(npm *)",
      "Bash(npm run *)",
      "Bash(npm start *)",
      "Bash(npm test *)",
      "Bash(npm build *)",
      "Bash(npm install *)",

      // Yarn
      "Bash(yarn *)",
      "Bash(yarn run *)",
      "Bash(yarn test *)",
      "Bash(yarn build *)",

      // PNPM
      "Bash(pnpm *)",

      // Maven
      "Bash(mvn *)",
      "Bash(mvn clean *)",
      "Bash(mvn compile *)",
      "Bash(mvn test *)",
      "Bash(mvn package *)",
      "Bash(mvn install *)",
      "Bash(mvn verify *)",
      "Bash(mvn validate *)",
      "Bash(mvn javadoc:javadoc *)",
      "Bash(./mvnw *)",

      // Gradle
      "Bash(gradle *)",
      "Bash(gradle build *)",
      "Bash(gradle test *)",
      "Bash(gradle clean *)",
      "Bash(./gradlew *)",

      // Network/API
      "Bash(curl -s *)",
      "Bash(curl -H * https://*)",
      "Bash(curl -H \"PRIVATE-TOKEN: *\" *)",

      // Container & Orchestration
      "Bash(docker *)",
      "Bash(docker-compose *)",
      "Bash(kubectl *)",

      // Common utilities
      "Bash(grep *)",
      "Bash(cat)",
      "Bash(jq *)",
      "Bash(wc *)",
      "Bash(head *)",
      "Bash(tail *)",
      "Bash(awk *)",
      "Bash(sed *)",

      // Claude Code tools (REQUIRED for all workflows)
      "Workflow",              // Required for workflow execution engine
      "Skill(ai-prompt)"       // Optional: if you use /ai-prompt skill
    ],
    "defaultMode": "acceptEdits"
  }
}
```

---

## Required Permissions by Platform

### GitHub Repositories

**Minimum Required:**
```json
"Bash(gh --version)",
"Bash(gh auth *)",
"Bash(gh issue *)",
"Bash(gh pr *)",
"Bash(gh release *)",
"Bash(git *)"
```

**Workflows Enabled:**
- ✅ code-pr-review / code-pr-review-auto
- ✅ code-release-notes / code-release-notes-auto
- ✅ code-solve / code-solve-auto
- ✅ code-review-auto
- ✅ code-test / code-test-auto
- ✅ code-sdlc / code-sdlc-auto

---

### GitLab Repositories

**Minimum Required:**
```json
"Bash(glab --version)",
"Bash(glab auth *)",
"Bash(glab issue *)",
"Bash(glab issue note *)",
"Bash(glab pr *)",
"Bash(glab mr *)",
"Bash(glab release *)",
"Bash(git *)"
```

**Critical Commands:**
- `glab issue note` - Used for posting comments (different from GitHub's `gh issue comment`)
- `glab mr` - Merge Requests (GitLab's equivalent of Pull Requests)
- `glab release create` - Creating releases

**Workflows Enabled:**
- ✅ code-pr-review / code-pr-review-auto
- ✅ code-release-notes / code-release-notes-auto
- ✅ code-solve / code-solve-auto
- ✅ code-review-auto
- ✅ code-test / code-test-auto
- ✅ code-sdlc / code-sdlc-auto

---

### Node.js / JavaScript Projects

**Minimum Required:**
```json
"Bash(npm audit *)",
"Bash(npm run *)",
"Bash(npm test *)",
"Bash(npm *)"
```

**Optional (Alternative Package Managers):**
```json
"Bash(yarn *)",
"Bash(pnpm *)"
```

**Workflows Enabled:**
- ✅ code-security / code-security-auto (npm audit)
- ✅ code-smoke-test (npm test, npm run build)
- ✅ code-test / code-test-auto (npm test)

---

### Java Projects (Maven)

**Minimum Required:**
```json
"Bash(mvn *)",
"Bash(./mvnw *)"
```

**Workflows Enabled:**
- ✅ code-smoke-test (mvn compile, mvn test)
- ✅ code-test / code-test-auto (mvn test)

---

### Java/Kotlin Projects (Gradle)

**Minimum Required:**
```json
"Bash(gradle build *)",
"Bash(gradle test *)",
"Bash(./gradlew *)"
```

**Workflows Enabled:**
- ✅ code-smoke-test (gradle build, gradle test)
- ✅ code-test / code-test-auto (gradle test)

---

## Permissions by Workflow

### ai-prompt
**CLI Commands**: None (pure agent-based)  
**Required Permissions**: None

---

### code-pr-review / code-pr-review-auto

**Purpose**: Multi-AI consensus PR review with optional auto-approval

**Required Permissions:**

**GitHub:**
```json
"Bash(gh --version)",
"Bash(gh pr list *)",
"Bash(gh pr view *)",
"Bash(gh pr diff *)",
"Bash(gh pr comment *)",
"Bash(gh pr review *)"
```

**GitLab:**
```json
"Bash(glab --version)",
"Bash(glab pr list *)",
"Bash(glab pr view *)",
"Bash(glab pr diff *)",
"Bash(glab pr comment *)",
"Bash(glab pr review *)"
```

**Common:**
```json
"Bash(git fetch *)",
"Bash(git status)",
"Bash(grep *)"
```

**Impact Analysis Uses:**
- `grep -r` to find file dependencies
- `git fetch` to sync with remote
- Platform CLI for PR operations

---

### code-release-notes / code-release-notes-auto

**Purpose**: Generate release notes and create GitHub/GitLab releases

**Required Permissions:**

**GitHub:**
```json
"Bash(gh release create *)"
```

**GitLab:**
```json
"Bash(glab release create *)"
```

**Common:**
```json
"Bash(git fetch --tags)",
"Bash(git describe --tags *)",
"Bash(git log *)",
"Bash(git tag *)",
"Bash(git push origin *)"
```

**Critical**: Without `glab release create`, GitLab releases will fail!

---

### code-solve / code-solve-auto

**Purpose**: Autonomous issue resolution with multi-AI consensus

**Required Permissions:**

**GitHub:**
```json
"Bash(gh issue list *)",
"Bash(gh issue view *)",
"Bash(gh issue edit *)"
```

**GitLab:**
```json
"Bash(glab issue list *)",
"Bash(glab issue view *)",
"Bash(glab issue update *)",
"Bash(curl -H \"PRIVATE-TOKEN: *\" *)"
```

**Common:**
```json
"Bash(git add *)",
"Bash(git commit *)",
"Bash(git push *)",
"Bash(git checkout *)",
"Bash(git branch *)"
```

**GitLab Note**: Uses `curl` as API fallback when `glab` unavailable

---

### code-test / code-test-auto

**Purpose**: Comprehensive testing with automatic issue creation

**Required Permissions:**

**GitHub:**
```json
"Bash(gh issue create *)",
"Bash(gh issue comment *)"
```

**GitLab:**
```json
"Bash(glab issue create *)",
"Bash(glab issue note *)"
```

**Build Tools:**
```json
"Bash(npm test *)",
"Bash(mvn test *)",
"Bash(gradle test *)"
```

**Critical**: GitLab uses `glab issue note` (not `comment`) for posting!

---

### code-review-auto

**Purpose**: Autonomous code review with auto-issue creation

**Required Permissions:**

**GitHub:**
```json
"Bash(gh issue create *)",
"Bash(gh issue list *)"
```

**GitLab:**
```json
"Bash(glab issue create *)",
"Bash(glab issue list *)"
```

**Common:**
```json
"Bash(git log *)",
"Bash(git show *)"
```

---

### code-security / code-security-auto

**Purpose**: Security audit with vulnerability scanning

**Required Permissions:**

**Node.js:**
```json
"Bash(npm audit *)"
```

**Common:**
```json
"Bash(git remote -v)"
```

**Note**: Detects platform (GitHub/GitLab) for issue creation

---

### code-smoke-test

**Purpose**: Auto-detect project type and run smoke tests

**Required Permissions:**

**Maven:**
```json
"Bash(mvn compile *)",
"Bash(mvn test *)"
```

**Gradle:**
```json
"Bash(gradle build *)",
"Bash(gradle test *)"
```

**Node.js:**
```json
"Bash(npm run build)",
"Bash(npm test)",
"Bash(npm start)"
```

**Issue Creation:**
```json
"Bash(gh issue create *)",
"Bash(glab issue create *)"
```

---

### code-sdlc / code-sdlc-auto

**Purpose**: Complete SDLC automation (dev → test → release)

**Required Permissions:**

**GitHub:**
```json
"Bash(gh pr list *)"
```

**GitLab:**
```json
"Bash(glab mr list *)"
```

**Common:**
```json
"Bash(git log *)",
"Bash(git describe --tags *)"
```

**Critical**: GitLab uses `mr` (merge request) not `pr`!

---

### workflow-cleanup

**Purpose**: Clean workflow transcripts and extract learnings

**CLI Commands**: None (uses Read/Write tools only)  
**Required Permissions**: None

---

## Troubleshooting

### Error: "Permission to use Bash has been denied"

**Cause**: A command is not in your allow list

**Solution**:
1. Look at the error message - it shows the exact command
2. Add a permission rule matching that command
3. Example: If error shows `glab issue note`, add:
   ```json
   "Bash(glab issue note *)"
   ```

---

### Workflows Fail on GitLab but Work on GitHub

**Likely Missing**:
```json
"Bash(glab issue note *)",  // Comments
"Bash(glab mr *)",          // Merge requests
"Bash(glab release *)"      // Releases
```

**Why**: GitLab CLI uses different commands than GitHub:
- `gh issue comment` → `glab issue note`
- `gh pr` → `glab mr` (merge request)

---

### npm/yarn Commands Trigger Prompts

**Add**:
```json
"Bash(npm *)",
"Bash(yarn *)"
```

Or more specific:
```json
"Bash(npm run *)",
"Bash(npm test *)",
"Bash(yarn run *)",
"Bash(yarn test *)"
```

---

### Gradle Commands Trigger Prompts

**Add**:
```json
"Bash(gradle *)",
"Bash(./gradlew *)"
```

Or more specific:
```json
"Bash(gradle build *)",
"Bash(gradle test *)"
```

---

## Permission Patterns Explained

### Wildcard Matching

- `Bash(gh *)` - Matches **any** command starting with `gh`
- `Bash(gh pr *)` - Matches **any** command starting with `gh pr`
- `Bash(gh pr view *)` - Matches `gh pr view` with any arguments

### Specificity

More specific rules take precedence:
```json
"Bash(gh pr *)",        // General - allows all gh pr commands
"Bash(gh pr review *)"  // Specific - explicitly allows gh pr review
```

### Best Practice

Use broad permissions for tools you trust:
```json
"Bash(git *)",   // Trust all git commands
"Bash(npm *)"    // Trust all npm commands
```

Use specific permissions for sensitive operations:
```json
"Bash(gh pr review *)",           // Only PR reviews
"Bash(glab issue create *)"       // Only issue creation
```

---

## Platform Detection in Workflows

Most workflows auto-detect the platform:

```javascript
// Checks git remote to determine platform
git remote -v | grep -q 'github.com'    // GitHub
git remote -v | grep -q 'gitlab'        // GitLab
```

Then uses the appropriate CLI:
- GitHub → `gh` commands
- GitLab → `glab` commands

**This means you need permissions for BOTH platforms**, even if you primarily use one.

---

## Testing Your Permissions

### Quick Test

```bash
# In a GitHub repo:
/code-pr-review

# In a GitLab repo:
/code-pr-review

# Should run without permission prompts
```

### Comprehensive Test

1. **GitHub PR Review**: `/code-pr-review` in GitHub repo
2. **GitLab PR Review**: `/code-pr-review` in GitLab repo
3. **Release Notes**: `/code-release-notes`
4. **Security Audit**: `/code-security` in Node.js project
5. **Smoke Test**: `/code-smoke-test`
6. **Issue Solver**: `/code-solve`

If any trigger permission prompts, check this guide for the missing permission.

---

## Critical: Workflow Tool Permission

**REQUIRED FOR ALL WORKFLOWS**: You MUST enable the `Workflow` tool permission.

```json
"Workflow"
```

**Why it's needed**:
- All `.js` workflows run via the Workflow tool (internal execution engine)
- Skills invoke workflows using the Workflow tool
- Without this permission, **NO workflows will run** - you'll get "Permission denied" errors

**This is different from Bash permissions**:
- `Bash(gh *)` - Allows running `gh` CLI commands
- `Workflow` - Allows running workflow scripts (`.js` files)

**Even if you only use one workflow**, you still need `Workflow` permission enabled.

---

## Automated Workflows Note

Workflows ending in `-auto` are **fully autonomous**:
- `code-pr-review-auto` - Auto-approves/rejects PRs
- `code-solve-auto` - Auto-fixes issues
- `code-test-auto` - Auto-creates test failure issues
- `code-security-auto` - Auto-creates security issues

These require **comprehensive permissions** because they run without user intervention.

---

## Security Considerations

### Safe Permissions

These are safe to allow broadly:
- `git *` - Git is designed to be safe
- `gh *`, `glab *` - VCS CLIs are generally safe
- `npm test`, `mvn test` - Read-only operations
- `grep`, `cat`, `jq` - Read-only tools

### Careful Permissions

Consider more specific rules for:
- `npm install *` - Modifies node_modules
- `docker *` - Can affect containers
- `kubectl *` - Can affect Kubernetes clusters

### Dangerous Operations

These workflows **do not** use:
- `rm -rf` - File deletion
- `sudo` - Privilege escalation  
- `eval` - Code execution from strings
- Force push (`git push --force`)

---

## Advanced: Permission Scopes

### User Settings (~/.claude/settings.json)
- Applies to **all projects** globally
- Best for commonly-used commands

### Project Settings (.claude/settings.json)
- Applies to **this project only**
- Best for project-specific tools

### Local Settings (.claude/settings.local.json)
- Applies to **this project, this user only**
- Not committed to git
- Best for personal overrides

**Precedence**: User < Project < Local

---

## Support

If you encounter permission issues not covered here:

1. Check the error message for the exact command
2. Add a matching permission rule
3. Test again
4. If still failing, file an issue with:
   - The workflow name
   - The platform (GitHub/GitLab/Bitbucket)
   - The exact error message
   - Your project type (Node.js/Maven/Gradle/etc.)

---

## Changelog

### 2026-06-06
- Initial comprehensive permissions guide
- Added GitLab-specific commands
- Added Node.js/Gradle build tool permissions
- Added troubleshooting section
- Documented all 14 workflows
