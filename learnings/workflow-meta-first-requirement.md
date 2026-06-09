---
name: workflow-meta-first-requirement
description: Critical requirement - export const meta MUST be first statement in workflow files for registration
metadata:
  type: feedback
  originSessionId: current
---

# Workflow Registration: Meta Block Must Be First

**Rule**: The `export const meta` block MUST be the FIRST statement in a workflow file (after comments only) for the workflow to register as a skill.

**Why**: The Claude Code workflow harness scans files and validates structure during registration. If meta is not first, the workflow is silently rejected with error "export const meta must be the FIRST statement in the script".

**How to apply**: When creating or debugging workflows that won't register:
1. Check meta position - it MUST be at line 3-5 (after opening comments)
2. Move ALL helper functions AFTER the meta block
3. Structure: comments → meta → main logic → helper functions

## Discovery Context (2026-06-05)

### The Problem

`code-solve` workflow existed with:
- ✅ Valid `export const meta` block
- ✅ No `workflow()` calls (which would filter it out)
- ✅ No syntax errors
- ✅ Proper `.md` file with frontmatter
- ❌ **Meta block at line 148** (after 147 lines of helper functions)

Result: Workflow file existed but was **invisible** to the skill system.

### The Error

When trying to invoke via scriptPath:
```
Invalid workflow script: `export const meta = { name, description, phases }` must be the FIRST statement in the script
```

### The Fix

Restructured file to move meta to line 4:
```javascript
// Line 1-2: Opening comments
// Line 3: blank
export const meta = {        // Line 4 - NOW FIRST STATEMENT
  name: 'code-solve',
  description: '...',
  phases: [...]
}

// Main workflow logic here
// ...

// Helper functions at END (lines 196-703)
function createIssueClaimer(...) { ... }
async function coordinateWork(...) { ... }
async function solveSingleIssue(...) { ... }
```

### Verification

After fix, `code-solve` immediately appeared in available skills:
```
- code-solve: Auto-resolve GitHub/GitLab issues with multi-AI consensus (AUTONOMOUS)
```

## File Structure Requirements

### ✅ CORRECT Structure

```javascript
// Opening comment
// More comments OK here

export const meta = {
  name: 'workflow-name',
  description: 'What it does',
  phases: [
    { title: 'Phase 1', detail: 'Step detail' }
  ]
}

// Main workflow logic
const config = args?.config || {}
phase('Phase 1')
const result = await agent('Do work...')

// Helper functions at END
function helperA() { ... }
function helperB() { ... }

return { status: 'success', result }
```

### ❌ INCORRECT Structure

```javascript
// Opening comment

// Helper functions BEFORE meta - BREAKS REGISTRATION
function helperA() { ... }
function helperB() { ... }

export const meta = {  // TOO LATE - won't register
  name: 'workflow-name',
  ...
}

// Main workflow logic
```

## Pattern for All Workflows

**Order that works**:
1. Comments (optional)
2. `export const meta = {...}` (REQUIRED FIRST)
3. Configuration parsing from `args`
4. Main workflow logic using `phase()`, `agent()`, `parallel()`, `pipeline()`
5. Helper function definitions
6. Final `return` statement

## Common Mistakes

### Mistake 1: Inlining helpers before meta
```javascript
// ❌ WRONG
function createHelper() { ... }  // Helper defined first

export const meta = { ... }      // Meta comes after
```

**Fix**: Move function definitions to END of file.

### Mistake 2: Imports before meta (depends on workflow)
```javascript
// ⚠️ May work, may not - depends on harness version
import { helper } from './shared/module.js'

export const meta = { ... }
```

**Safest**: Inline everything, no imports. If imports needed, they may need to come AFTER meta.

### Mistake 3: Complex logic before meta
```javascript
// ❌ WRONG
const CONFIG = parseConfig()     // Logic before meta

export const meta = { ... }
```

**Fix**: Move config parsing AFTER meta block.

## Validation Checklist

When workflow doesn't register:

1. ✅ Check meta position: `grep -n "export const meta" workflow.js`
   - Should be line 3-6, not line 100+
2. ✅ Check meta is complete: name, description, phases all present
3. ✅ Check no `workflow()` calls in the file (separate issue)
4. ✅ Check `.md` file has YAML frontmatter
5. ✅ Restart Claude Code after moving meta

## Related Memories

- [[claude-code-workflows]] - General workflow registration lessons
- [[workflow-registration-filter]] - Workflows with workflow() calls excluded
- [[broken-import-workflows]] - ES6 import compatibility issues

## Why This Matters

**Silent failure**: If meta is not first, the workflow:
- ❌ Won't appear in skills list
- ❌ Won't be invokable via Skill tool
- ❌ Won't be discoverable via `Workflow({name: "..."})`
- ✅ Will still exist as a file
- ✅ Will still work via `Workflow({scriptPath: "..."})`

Users see "workflow not found" with no indication of WHY.

## Examples from Real Workflows

### Working: code-hygiene-review.js
```javascript
// Line 1: // AUTONOMOUS WORKFLOW - Repository Hygiene Review
// Line 2: // Reviews branches, issues, PRs
// Line 3: (blank)
// Line 4: export const meta = {
//   name: 'code-hygiene-review',
//   ...
// }
```
✅ Registered successfully

### Broken (before fix): code-solve.js
```javascript
// Lines 1-147: Helper functions (coordinateWork, createIssueClaimer, etc.)
// Line 148: export const meta = { ... }
```
❌ Failed to register - meta too late

### Fixed: code-solve.js
```javascript
// Lines 1-2: Comments
// Line 4: export const meta = { ... }
// Lines 5-195: Main workflow logic
// Lines 196-703: Helper functions
```
✅ Now registered successfully

## Technical Details

The harness likely:
1. Reads first ~20 lines of each `.js` file
2. Looks for `export const meta = {`
3. Parses meta block for validation
4. If meta not found in first N lines → reject file
5. If meta valid → register workflow

This explains why position matters - it's a discovery optimization that becomes a hard requirement.

---

**Lesson**: Workflow file structure is strict. Meta first, everything else after. No exceptions.

**Impact**: High - determines whether workflow is discoverable at all

**Fix time**: 5 minutes (restructure file)

**Prevention**: Always start new workflows with meta block, add logic after
