# Lesson: Workflow Nesting Limitation and Recursive Calls

**Date:** 2026-06-04  
**Issue:** Code-solve workflow failed to solve any issues when run in "solve all" mode  
**Root Cause:** Recursive `workflow()` calls hit the one-level nesting limit

## The Problem

The code-solve workflow had this pattern:

```javascript
// WRONG - Causes nesting error
const results = await pipeline(
  issueNumbers,
  (num) => workflow({
    scriptPath: '/home/sfloess/.claude/workflows/code-solve.js',
    args: [String(num)]  // Recursive call - FAILS!
  })
)
```

**What happened:**
1. User runs `/code-solve` (default mode: "all")
2. Workflow finds N open issues
3. Tries to spawn N child workflows, one per issue
4. **ALL FAIL** with error: `workflow() cannot be called from within a child workflow — nesting is limited to one level`
5. Result: 0 issues solved

## The Solution

Extract the single-issue solving logic into a reusable function and call it directly:

```javascript
// CORRECT - Direct function call
async function solveSingleIssue(issueNumber, isGitLab, isGitHub) {
  // All the single-issue solving logic here
}

const results = await pipeline(
  issueNumbers,
  async (num) => {
    try {
      return await solveSingleIssue(num, isGitLab, isGitHub)
    } catch (error) {
      return { status: 'error', issue_number: num, message: error.message }
    }
  }
)
```

## Key Learnings

### 1. Workflow Nesting is Limited to One Level
- A workflow can call `workflow()` to spawn child workflows
- Child workflows **CANNOT** call `workflow()` again
- This prevents infinite recursion and resource exhaustion

### 2. Pattern: Extract and Reuse Instead of Recurse
When you need to process multiple items with the same logic:

**DON'T:**
```javascript
pipeline(items, (item) => workflow({ scriptPath: 'same-script.js', args: [item] }))
```

**DO:**
```javascript
async function processItem(item, ...context) {
  // Processing logic here
}

pipeline(items, (item) => processItem(item, ...context))
```

### 3. Both Modes Use Same Function
The refactored code now has:
- **Solve one mode:** Calls `solveSingleIssue(issueNumber, ...)`
- **Solve all mode:** Calls `pipeline(nums, (num) => solveSingleIssue(num, ...))`

This eliminates code duplication and ensures consistency.

### 4. Error Handling in Pipeline
Wrap direct function calls with try/catch to prevent one failure from breaking the entire pipeline:

```javascript
pipeline(items, async (item) => {
  try {
    return await processItem(item)
  } catch (error) {
    log(`Error processing ${item}: ${error.message}`)
    return { status: 'error', item, message: error.message }
  }
})
```

## Related Commits

- `c743cf4` - fix: remove duplicate function definition
- `7fcca90` - fix: eliminate recursive workflow() calls in code-solve
- `edfe939` - docs: fix misleading claims in code-review-and-solve documentation
- `c973bce` - fix: resolve ReferenceError in verification phase

## When to Use Workflows vs Functions

**Use `workflow()` when:**
- You need complete isolation (different repo, different state)
- The child work is truly independent and could run on a different machine
- You want the child to be resumable via runId

**Use direct function calls when:**
- Processing multiple items with the same logic (like solving multiple issues)
- The work is part of the same conceptual task
- You need to process items in parallel within one workflow

## Impact

Before the fix:
- Running `/code-solve` on repo with 48 issues: **0 solved** ❌

After the fix:
- Running `/code-solve` can solve all issues in parallel ✅
- No nesting errors
- Proper error handling per issue
- Clean, maintainable code

## Links

- Issue: https://gitlab.cee.redhat.com/sfloess/claude-global-skills/-/work_items/3
- File: `code-solve.js`
- Function: `solveSingleIssue()`
