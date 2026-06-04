# Lesson: TOCTOU Race Condition in Parallel Workflow Execution

**Date:** 2026-06-04  
**Issue:** Multiple code-solve workflows racing to process the same issues  
**Root Cause:** Time-of-check to time-of-use (TOCTOU) gap between fetching and claiming issues

## The Problem

When multiple code-solve workflows run simultaneously, they experience a classic TOCTOU race condition:

### Current Flawed Pattern

```javascript
// Step 1: TIME-OF-CHECK (lines 87-116)
const allIssues = await agent(`Get all open issues...`)
const unclaimedIssues = allIssues.issues?.filter(issue =>
  !issue.labels?.some(l => l.name === 'code-solve-in-progress')
) || []

const issueNumbers = unclaimedIssues.map(i => i.number)
// GAP: All workflows have the same list now!

// Step 2: Process in parallel
const results = await pipeline(
  issueNumbers,
  async (num) => {
    // Step 3: TIME-OF-USE (lines 173-180) - CLAIM the issue
    await agent(`Claim issue #${issueNumber}...
      glab issue update ${issueNumber} --add-label "code-solve-in-progress"
    `)
    // Too late! Multiple workflows already started processing this issue
  }
)
```

### What Happens

**Scenario:** 3 workflows start simultaneously with 99 open issues

1. **T=0s:** All 3 workflows fetch issue list
2. **T=0s:** All 3 filter out claimed issues (none claimed yet)
3. **T=0s:** All 3 get the same 99 issues
4. **T=1s:** All 3 start processing all 99 issues in parallel
5. **T=2s:** Race to claim each issue
6. **T=2s:** First workflow to add label wins
7. **T=2-60s:** Other 2 workflows waste resources on duplicate work

**Impact:**
- 3× token cost (all 3 generate fixes for same issues)
- 3× agent count (all 3 spawn workers for same issues)
- Potential conflicts if claims aren't truly atomic
- Resource exhaustion

## The Solution

### Fix: Claim-Before-Fetch (Atomic Claim)

Change the pattern to claim issues atomically during fetch, not after:

```javascript
// NEW PATTERN: Claim first, process later
const results = await pipeline(
  issueNumbers,
  async (num) => {
    // Step 1: Try to claim FIRST (atomic)
    const claimed = await agent(`Atomically claim issue #${num}...
      # Only succeed if not already labeled
      if ! glab issue view ${num} --json labels | grep -q "code-solve-in-progress"; then
        glab issue update ${num} --add-label "code-solve-in-progress"
        echo "CLAIMED"
      else
        echo "ALREADY_CLAIMED"
      fi
    `)
    
    // Step 2: Only process if we successfully claimed it
    if (!claimed.includes('CLAIMED')) {
      return { status: 'skipped', reason: 'Already claimed by another workflow' }
    }
    
    // Step 3: Now safely process this issue
    return await solveSingleIssue(num, isGitLab, isGitHub)
  }
)
```

### Better Fix: API-Level Atomic Operations

Use GitLab/GitHub API features for true atomicity:

```javascript
// GitLab API: Update issue with conditional check
const response = await fetch(`/api/v4/issues/${num}`, {
  method: 'PUT',
  headers: { 'If-Match': currentETag }, // Only update if not changed
  body: JSON.stringify({ labels: [...existing, 'code-solve-in-progress'] })
})

if (response.status === 412) {
  // Precondition failed - someone else modified it
  return { status: 'skipped', reason: 'Claimed by another workflow' }
}
```

## Key Learnings

### 1. TOCTOU is Common in Distributed Systems

Any time you:
- Check a condition
- Take action based on that check
- With a gap in between

You have a potential race condition.

### 2. Claim Before Process

For competitive resource allocation:
- **DON'T:** fetch → filter → process → claim
- **DO:** fetch → claim (atomic) → process

### 3. Make Claims Atomic

Use platform features for atomicity:
- **GitLab:** Conditional updates with `If-Match` headers
- **GitHub:** `gh issue edit` with `--add-label` (check exit code)
- **Database:** `UPDATE WHERE status='unclaimed'` (returns affected rows)

### 4. Early Exit on Failure

If claim fails:
```javascript
if (!claimed) {
  return { status: 'skipped', issue_number: num }
}
// Don't waste resources on duplicate work
```

### 5. Add Retry Logic for Transient Failures

```javascript
for (let attempt = 0; attempt < 3; attempt++) {
  try {
    const claimed = await attemptClaim(num)
    if (claimed) break
    if (attempt < 2) await sleep(1000 * (attempt + 1)) // Exponential backoff
  } catch (error) {
    if (attempt === 2) throw error
  }
}
```

## Implementation Plan

1. ✅ Document the race condition (this file)
2. ✅ Create GitLab issue to track the fix (#4)
3. ✅ Implement atomic claim-before-process pattern
4. ✅ Add skip logic for already-claimed issues
5. ✅ **IMPROVED:** Implemented coordinator pattern (see `coordinator-pattern.md`)
6. ✅ Update documentation to mention concurrent-safe behavior

## Final Solution: Coordinator Pattern

The atomic claim-before-process pattern was good, but we improved it further with a **reusable coordinator pattern**:

- ✅ Centralized work fetching (happens once)
- ✅ Coordinator claims all work atomically
- ✅ Distributes claimed work to parallel workers
- ✅ Reusable for other workflows (see `shared/work-coordinator.js`)

See `learnings/coordinator-pattern.md` for full details.

## Related Patterns

### Optimistic Locking
```javascript
// Read with version
const issue = await getIssue(num) // { version: 42, ... }

// Update with version check
const updated = await updateIssue(num, {
  labels: [...issue.labels, 'claimed'],
  expectedVersion: issue.version
})

if (!updated) {
  // Someone else updated it - retry or skip
}
```

### Pessimistic Locking
```javascript
// Lock the issue (blocking)
await lockIssue(num)
try {
  // Process while locked
  await processIssue(num)
} finally {
  await unlockIssue(num)
}
```

### Leader Election
```javascript
// Only one workflow becomes the leader
const isLeader = await tryBecomeLeader()
if (isLeader) {
  // Only the leader processes issues
  await processAllIssues()
}
```

## Impact

**Before fix:**
- Running 3 code-solve workflows on 99 issues → 297 duplicate attempts
- Wasted resources: ~200% overhead
- Unpredictable which workflow wins

**After fix:**
- Running 3 code-solve workflows on 99 issues → 99 successful claims + 198 skips
- No wasted resources: each issue processed exactly once
- Graceful handling of claim failures

## Links

- Issue: (to be created)
- File: `code-solve.js`
- Lines: 87-180 (fetch and claim logic)
- Pattern: Claim-before-process with atomic operations
