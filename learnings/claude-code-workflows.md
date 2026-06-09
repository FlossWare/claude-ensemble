---
name: claude-code-workflows
description: "Critical learnings about Claude Code workflow registration, imports, and the difference between workflow files existing vs being discoverable"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 492f95ca-eb43-4b52-960e-5130fcf5f46a
---

# Claude Code Workflow System - Critical Learnings

**Rule**: Workflow files existing in `~/.claude/workflows/` does NOT automatically make them available to Claude Code.

**Why**: Claude Code maintains a separate registry of named workflows. Only registered workflows appear in the available workflows list.

**How to apply**: When creating or troubleshooting custom workflows, always check both:
1. Does the `.js` file exist? (`~/.claude/workflows/my-workflow.js`)
2. Is it registered/discoverable? (Check with Workflow tool error message)

## Key Findings from 2026-06-03

### Problem Encountered

Created `code-solve.js` workflow with proper structure:
- ✅ File exists at `~/.claude/workflows/code-solve.js`
- ✅ Has proper `export const meta` block
- ✅ Has all shared dependencies in `~/.claude/workflows/shared/`
- ❌ **NOT available** when trying to invoke via `Workflow({name: "code-solve"})`

### Error Received

```
Workflow "code-solve" not found. Available: deep-research, code-review, doc-review, 
multi-model-code-review, pr-verify, virtos-4-model-review, virtos-4-model-review-enhanced
```

### Root Cause - DISCOVERED 2026-06-05

**The `export const meta` block MUST be the FIRST statement in a workflow file (after comments).**

Evidence:
- code-solve.js had meta at line 148 (after 147 lines of helper functions)
- Error message from harness: "export const meta must be the FIRST statement"
- Working workflows (code-hygiene-review, code-test-review) all have meta at line 3-5
- The harness explicitly checks for this pattern and rejects workflows that don't follow it

**File existence ≠ Workflow registration**

Workflows must be in Claude Code's internal registry to be invoked by name. Files in `~/.claude/workflows/` are just storage, not automatic registration.

**The harness VALIDATES the structure of workflow files during registration and rejects those with meta not at the top.**

### Registered Workflows (2026-06-03)

Available named workflows:
- deep-research (built-in)
- code-review (custom but registered)
- doc-review (custom but registered)
- multi-model-code-review (custom but registered)
- pr-verify (built-in)
- virtos-4-model-review (custom but registered)
- virtos-4-model-review-enhanced (custom but registered)

### Workflow File Structure Requirements

**CRITICAL RULE (2026-06-05)**: `export const meta` MUST be the FIRST statement (after comments).

**CORRECT** structure for registration:
```javascript
// Comments allowed here at the top

export const meta = {
  name: 'workflow-name',
  description: 'What it does',
  phases: [...]
}

// Helper functions AFTER meta
function helperOne() { ... }
function helperTwo() { ... }

// Script body using agent(), parallel(), pipeline(), etc.
// These can reference the helper functions defined above
```

**INCORRECT** structure (will NOT register):
```javascript
// Helper functions at top
function helperOne() { ... }
function helperTwo() { ... }

export const meta = {  // ❌ TOO LATE - must be FIRST
  name: 'workflow-name',
  ...
}
```

**Note on imports**: Earlier testing suggested imports could come before meta, but the harness validation requires meta to be the FIRST executable statement. If imports are needed, they may need to be handled differently or the workflow restructured.

### Import Statements

✅ **Workflows CAN use import statements**
- Example: code-review.js uses imports and works fine
- Shared modules in `~/.claude/workflows/shared/` work correctly
- Import syntax: `import { thing } from './shared/module.js'`

### How Workflows Get Registered

**DISCOVERED 2026-06-05**: The harness scans `~/.claude/workflows/*.js` and validates structure.

**Registration Requirements**:
1. ✅ File must exist in `~/.claude/workflows/` directory
2. ✅ File must have `export const meta` as the FIRST statement (after comments)
3. ✅ Meta must include valid `name`, `description`, and `phases`
4. ❌ Files with meta NOT at the top are silently rejected from registration

**Why some workflows were NOT registered**:
- code-solve.js - ❌ Had meta at line 148 (after helper functions)
- ai-prompt.js - ❌ Likely has code before meta
- code-improve.js - ❌ Likely has code before meta
- pr-review.js - ❌ Likely has code before meta

**Solution**: Move `export const meta` to line 1-5 (after comments), put all helper functions AFTER meta.

**Confirmed working** (all have meta at top):
- code-review.js - ✅ Registered (meta at top)
- doc-review.js - ✅ Registered (meta at top)
- deep-research - ✅ Registered (built-in)
- pr-verify - ✅ Registered (built-in)
- code-hygiene-review - ✅ Registered (meta at line 3)
- code-test-review - ✅ Registered (meta at line 3)
- multi-model-code-review - ✅ Registered (meta at top)
- virtos-4-model-review - ✅ Registered (meta at top)
- virtos-4-model-review-enhanced - ✅ Registered (meta at top)

### Workarounds

**Option 1**: Invoke via scriptPath instead of name
```javascript
Workflow({
  scriptPath: "/home/sfloess/.claude/workflows/code-solve.js",
  description: "...",
  args: [...]
})
```
- Works if script is self-contained or imports resolve
- Bypasses registration requirement

**Option 2**: Create self-contained version (no imports)
- Inline all shared code
- No dependencies on `./shared/` modules
- More maintainable as single file but duplicates code

**Option 3**: Figure out registration mechanism
- Find how code-review got registered
- Apply same method to code-solve
- Best long-term solution

### Related Discovery: Custom Skills vs Built-in Skills

Similar issue with skills:
- Custom skills in `~/.claude/skills/` exist but don't appear in system-reminder
- Only built-in Claude Code skills show in the skills list
- Created plugin system workaround at `~/.claude/plugins/marketplaces/custom/`

### Action Items for Future

When creating workflows:
1. ✅ Create the `.js` file with `export const meta` as FIRST statement (after comments)
2. ✅ Put ALL helper functions AFTER the meta block
3. ✅ Test shared imports resolve correctly (if using imports, validate placement)
4. ✅ Verify via Workflow tool that it's discoverable
5. If not discoverable, check meta position FIRST before other debugging
6. If still not working, use scriptPath as fallback

### Files That Exist But Aren't Registered

As of 2026-06-03, these workflow files exist but are NOT registered:
- `~/.claude/workflows/code-solve.js` - ❌ meta at line 148
- `~/.claude/workflows/ai-prompt.js` - ❌ likely has code before meta
- `~/.claude/workflows/doc-review.js` (exists in shared/ but might be registered under different name)
- `~/.claude/workflows/pr-review.js` - ❌ likely has code before meta
- `~/.claude/workflows/code-improve.js` - ❌ likely has code before meta

**Fix (2026-06-05)**: Restructure each file to move `export const meta` to the top (line 1-5 after comments), then move all helper functions below the meta block.

---

## Summary: Critical Registration Rule

**LESSON**: The harness REQUIRES `export const meta` to be the FIRST statement (after comments).

**Why this matters**:
- Workflow files are scanned at startup
- Files with meta not at top are silently rejected
- No warning is given - they just don't appear in available workflows
- This is a validation requirement, not a preference

**How to fix non-registering workflows**:
1. Open the workflow file
2. Find the `export const meta` block
3. Move it to line 1-5 (after any initial comments)
4. Move ALL other code (helpers, imports, etc.) AFTER meta
5. Restart Claude Code to re-scan workflows

**Verification**: After restructuring, invoke with `Workflow({name: "workflow-name"})` to confirm registration worked.
