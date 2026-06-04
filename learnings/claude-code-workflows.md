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

### Root Cause

**File existence ≠ Workflow registration**

Workflows must be in Claude Code's internal registry to be invoked by name. Files in `~/.claude/workflows/` are just storage, not automatic registration.

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

**CORRECT** structure that code-review.js uses (and IS registered):
```javascript
// Comments allowed here
import { modules } from './shared/file.js'  // Imports allowed BEFORE meta

export const meta = {
  name: 'workflow-name',
  description: 'What it does',
  phases: [...]
}

// Script body using agent(), parallel(), pipeline(), etc.
```

**INCORRECT** claim from error message:
"meta must be FIRST statement" - This is misleading. Imports CAN come before meta.

### Import Statements

✅ **Workflows CAN use import statements**
- Example: code-review.js uses imports and works fine
- Shared modules in `~/.claude/workflows/shared/` work correctly
- Import syntax: `import { thing } from './shared/module.js'`

### How Workflows Get Registered

**Partially Unknown as of 2026-06-03**:

**Confirmed working**:
- code-review.js - ✅ Registered and works
- doc-review.js - ✅ Registered (appears in available list)
- deep-research - ✅ Registered (built-in)
- pr-verify - ✅ Registered
- multi-model-code-review - ✅ Registered
- virtos-4-model-review - ✅ Registered
- virtos-4-model-review-enhanced - ✅ Registered

**NOT registered (same directory, same structure)**:
- code-solve.js - ❌ Not discovered
- ai-prompt.js - ❌ Not discovered
- code-improve.js - ❌ Not discovered
- pr-review.js - ❌ Not discovered (though similar named ones work)

**Key finding**: Workflows in `~/.claude/workflows/` are NOT automatically registered just by existing there. Some mechanism selectively registers certain workflows but not others. The registration criteria is unknown.

**Theories to investigate**:
1. Workflows may need to be registered at Claude Code startup
2. Certain workflow names might be on an allowed list
3. Project-specific workflows might have different registration  
4. May need to restart Claude Code after adding new workflows
5. Registration might be tied to plugin system in some cases

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
1. ✅ Create the `.js` file with proper meta block
2. ✅ Test shared imports resolve correctly
3. ❓ **Determine registration method** (still unknown)
4. ✅ Verify via Workflow tool that it's discoverable
5. If not discoverable, use scriptPath as fallback

### Files That Exist But Aren't Registered

As of 2026-06-03, these workflow files exist but are NOT registered:
- `~/.claude/workflows/code-solve.js`
- `~/.claude/workflows/ai-prompt.js`
- `~/.claude/workflows/doc-review.js` (exists in shared/ but might be registered under different name)
- `~/.claude/workflows/pr-review.js`
- `~/.claude/workflows/code-improve.js`

Need to either:
- Figure out how to register them
- Use scriptPath invocation
- Recreate as self-contained scripts

---

**Lesson**: Always verify workflows are REGISTERED, not just that files exist. File presence is necessary but not sufficient.
