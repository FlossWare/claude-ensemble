# Lesson: Auto-Sync with Remote Before Code Review

**Date:** 2026-06-05  
**Issue:** Code reviews were being performed on stale local code  
**Solution:** Add automatic git fetch/rebase before starting review

## The Problem

The `code-review` workflow would review whatever was in the local working directory without checking if it was up-to-date with the remote repository. This caused several issues:

### Issues Identified
1. **Stale Code Reviews**: Reviewing code that was already updated upstream
2. **Missed Recent Changes**: Not catching bugs in commits that were pushed after local checkout
3. **Duplicate Issue Creation**: Creating issues for problems already fixed in newer commits
4. **Wasted Resources**: AI models reviewing outdated code
5. **Confusion**: Review results didn't match current state of remote branch

### Example Scenario

```bash
# Developer A pushes fix at 10am
git push origin main

# Developer B's local repo (not updated)
cd ~/project
/code-review  # Runs at 11am

# Problem: Reviews code from before 10am fix
# Creates duplicate issue for already-fixed bug
```

## The Solution

### Implementation

Added automatic sync before review using shared platform-detector module:

```javascript
// Import shared sync function
import { detectPlatform, syncWithRemote } from './shared/platform-detector.js'

// Early in workflow, before any review
log('🔧 Detecting platform and syncing with remote...')
const platformDetect = await detectPlatform(agent)
log(`✅ Platform: ${platformDetect.platform} (using ${platformDetect.cli})`)

// Sync with remote before starting review
const syncResult = await syncWithRemote(agent)
if (syncResult.status === 'conflicts') {
  log(`⚠️ Rebase conflicts detected: ${syncResult.conflicts?.join(', ')}`)
  return {
    status: 'conflicts',
    message: 'Cannot proceed with review - resolve conflicts first',
    conflicts: syncResult.conflicts
  }
}
log(`✅ ${syncResult.status === 'up_to_date' ? 'Already up to date' : 'Synced with remote'}`)
```

### What `syncWithRemote()` Does

From `shared/platform-detector.js`:

```javascript
export async function syncWithRemote(agent, options = {}) {
  const { branch = 'main' } = options

  const result = await agent(`Sync with remote repository.

Execute these commands:
git fetch origin
git rebase origin/${branch}

Return the status of the sync operation.
If there are conflicts, list them.`, {
    label: 'Sync with Remote',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['success', 'conflicts', 'failed', 'up_to_date'] },
        message: { type: 'string' },
        conflicts: { type: 'array', items: { type: 'string' } },
        branch: { type: 'string' },
      },
      required: ['status'],
    }
  })

  return result
}
```

## Key Learnings

### 1. Always Sync Before Reviewing

For any code review workflow:
- **DON'T:** Start reviewing immediately
- **DO:** Fetch and rebase first

### 2. Handle Conflicts Gracefully

```javascript
if (syncResult.status === 'conflicts') {
  // Stop early, don't proceed with review
  return { status: 'conflicts', message: '...', conflicts: [...] }
}
```

### 3. Use Shared Functions

Don't duplicate sync logic across workflows:
- **Platform detection**: `detectPlatform(agent)`
- **Remote sync**: `syncWithRemote(agent)`
- **Issue creation**: `createIssue(agent, platform, ...)`

All in `shared/platform-detector.js` for reuse.

### 4. Inform the User

Clear logging about sync status:
```javascript
log('🔧 Detecting platform and syncing with remote...')
log(`✅ Platform: ${platform} (using ${cli})`)
log(`✅ Successfully synced with remote`)
```

### 5. Different Sync States

Handle all possible outcomes:
- **success**: Rebased successfully
- **up_to_date**: Already current
- **conflicts**: Rebase conflicts (stop and report)
- **failed**: Other errors (network failure, branch doesn't exist, etc.)

**Important**: Always check for both 'conflicts' AND 'failed' status:
```javascript
if (syncResult.status === 'conflicts') {
  // Handle conflicts
  return { status: 'conflicts', ... }
}
if (syncResult.status === 'failed') {
  // Handle failures
  return { status: 'failed', ... }
}
```

## Impact

**Before fix:**
- Reviews could be on stale code
- Duplicate issues created
- Confusion about review results

**After fix:**
- Always reviews latest remote code
- No duplicate issues for already-fixed bugs
- Clear user feedback about sync status
- Graceful handling of conflicts

## Example Output

### Successful Sync
```
🔧 Detecting platform and syncing with remote...
✅ Platform: gitlab (using glab)
✅ Successfully synced with remote

🔥 BRUTAL CODE REVIEW MODE 🔥
...
```

### Already Up-to-Date
```
🔧 Detecting platform and syncing with remote...
✅ Platform: github (using gh)
✅ Already up to date with remote

🔥 BRUTAL CODE REVIEW MODE 🔥
...
```

### Conflicts Detected
```
🔧 Detecting platform and syncing with remote...
✅ Platform: gitlab (using glab)
⚠️ Rebase conflicts detected: src/main.js, package.json

Cannot proceed with review - resolve conflicts first
```

### Sync Failed
```
🔧 Detecting platform and syncing with remote...
✅ Platform: github (using gh)
⚠️ Sync failed: unknown revision 'origin/main'

Cannot proceed with review - sync with remote failed
```

**Note**: The default branch is assumed to be `main`. If your repository uses a different default branch (e.g., `master`, `develop`), the sync will fail with an unknown revision error. In this case, manually sync to your default branch before running the review.

## Other Workflows That Should Sync

This pattern should be applied to any workflow that:
- Reviews code
- Analyzes commits
- Creates issues based on code state
- Makes changes to code

**Already has sync:**
- ✅ `pr-review.js` - Had sync from the start
- ✅ `code-review.js` - Added in this update

**Should consider adding:**
- `code-improve.js` - If it analyzes existing code
- `code-test-review.js` - If it reviews test files
- `doc-review.js` - If it reviews documentation in repo

## Related Patterns

### Git Worktrees for Isolation

For parallel work (like `pr-verify.js`), use worktrees instead:

```javascript
const verifications = await pipeline(
  prList.prs,
  pr => agent(verificationPrompt(pr), {
    isolation: 'worktree',  // Each PR in isolated worktree
    model: 'gemini'
  })
)
```

Worktrees provide:
- Isolated working directories
- No conflicts between parallel operations
- Clean separation of PR branches

### Platform Detection Pattern

Always use the shared `detectPlatform()`:

```javascript
const platform = await detectPlatform(agent)
// Returns: { platform: 'github'|'gitlab'|'bitbucket', cli: 'gh'|'glab'|'bb', ... }
```

Then use `platform.cli` for commands:
```javascript
const cmd = platform.platform === 'gitlab'
  ? `glab issue list ...`
  : `gh issue list ...`
```

## Files Changed

- `code-review.js` - Added import and sync call
- `code-review-unified.md` - Updated documentation
- `plugins/code-workflows/skills/code-review-unified/SKILL.md` - Updated skill docs
- `learnings/code-review-auto-sync.md` - This document

## Commit

```
feat: add git fetch/rebase to code-review workflow

Added automatic sync with remote before starting code review to ensure
the review is performed on the latest code:

- Import detectPlatform and syncWithRemote from shared/platform-detector.js
- Replace manual platform detection with detectPlatform() function
- Add syncWithRemote() call after platform detection
- Return early with conflicts status if rebase conflicts detected
- Log sync status to user

This ensures code-review always works with the latest remote changes
and avoids reviewing stale code.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Links

- Workflow: `code-review.js`
- Shared module: `shared/platform-detector.js`
- Documentation: `code-review-unified.md`
- GitLab commit: 3165afd
