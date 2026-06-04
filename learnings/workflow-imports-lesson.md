---
name: workflow-imports-lesson
description: "Critical lesson about workflow imports, scriptPath invocation, and the difference between registered vs file-based workflows"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 492f95ca-eb43-4b52-960e-5130fcf5f46a
---

# Workflow Imports and Registration - Key Lesson (2026-06-03)

**Rule**: Workflows with ES6 import statements CANNOT be invoked via scriptPath, even though registered workflows CAN use imports.

**Why**: The scriptPath invocation method executes workflows differently than the name-based method. Imports don't resolve properly in scriptPath mode.

**How to apply**: When creating workflows:
1. If targeting registration (name-based invocation): imports are OK
2. If targeting scriptPath invocation: must be self-contained, no imports
3. For maximum compatibility: always create self-contained versions

## The Problem Encountered

### Initial State
- `code-solve.js` existed with proper structure
- Had ES6 imports from `./shared/` modules
- Was NOT registered as a named workflow
- Attempted to invoke via scriptPath - **FAILED**

### Error Message (Misleading)
```
Invalid workflow script: `export const meta = { name, description, phases }` 
must be the FIRST statement in the script
```

**This error is misleading** - The real issue is the imports, not the meta position.

### What Actually Works

**Named/Registered Workflows** (like code-review):
```javascript
// Imports are OK
import { module } from './shared/file.js'

export const meta = { ... }

// Script body
```
✅ **Works** when invoked: `Workflow({name: "code-review"})`

**scriptPath Workflows**:
```javascript
// NO imports allowed
export const meta = { ... }

// All code must be inline
const helper = () => { ... }
```
✅ **Works** when invoked: `Workflow({scriptPath: "/path/to/file.js"})`

## The Solution

Created self-contained version:
1. Removed all import statements
2. Inlined necessary schemas
3. Used built-in `agent()`, `parallel()`, `phase()` functions
4. Kept all logic in single file

**Result**: code-solve now works via scriptPath ✅

## Key Learnings

### 1. Two Types of Workflow Invocation

| Method | Imports? | Registration? | Example |
|--------|----------|---------------|---------|
| **Named** | ✅ Yes | Required | `Workflow({name: "code-review"})` |
| **scriptPath** | ❌ No | Not needed | `Workflow({scriptPath: "..."})` |

### 2. Registration is Mysterious

Some workflows register automatically:
- code-review ✅
- doc-review ✅
- deep-research ✅
- pr-verify ✅

Others don't:
- code-solve ❌
- ai-prompt ❌
- code-improve ❌
- pr-review ❌

**Criteria unknown** - appears arbitrary or based on startup state.

### 3. Self-Contained is Always Safer

When in doubt, create workflows without imports:
- More portable
- Works via scriptPath
- No dependency resolution issues
- Easier to debug

### 4. Plugin System is Different

Plugins (`.claude/plugins/`) work differently:
- Use SKILL.md format, not .js
- Have different discovery mechanism
- Don't execute JavaScript directly
- More for documentation/guidance than execution

### 5. Skills vs Workflows vs Plugins vs Commands

**Skills** (`~/.claude/skills/*.sh`):
- Shell scripts with help text
- Not auto-discovered by Claude Code
- Can be invoked manually
- Show up in some contexts but not system-reminders

**Workflows** (`~/.claude/workflows/*.js`):
- JavaScript files with meta blocks
- Some get registered (name-based invocation)
- All can use scriptPath invocation (if self-contained)
- Appear in skills list when registered

**Plugins** (`~/.claude/plugins/marketplaces/*/plugins/*/`):
- Directory structure with .claude-plugin/plugin.json
- Contains skills/, commands/, etc.
- SKILL.md format for skills
- Provide context/guidance to Claude

**Commands**:
- Different from workflows entirely
- Defined in plugin command directories
- .md files with frontmatter
- Used by built-in command system

## What Worked

**Final Solution**:
1. Created self-contained `code-solve.js` (no imports)
2. Used scriptPath invocation
3. Inlined all necessary logic
4. Used built-in workflow functions only

**Code Structure**:
```javascript
export const meta = {
  name: 'code-solve',
  description: '...',
  phases: [...]
}

// All logic inline
const issueNumber = args?.[0]

// Use built-in functions
await agent(prompt, {schema, model})
await parallel([...])
phase('Phase Name')
log('Message')
```

## Lessons for Future

1. **Start with self-contained workflows** - avoid imports unless specifically targeting registration
2. **Test both invocation methods** - name and scriptPath
3. **Don't assume file existence = discoverability** - verify with actual invocation
4. **When debugging workflow issues** - try scriptPath first, it's more predictable
5. **Keep shared code minimal** - only use shared modules for registered workflows
6. **Document which workflows are registered** - maintain a list of what works where

## The Meta Position Mystery Explained

The error "meta must be FIRST statement" is **technically correct for scriptPath** but **misleading about the cause**:

- scriptPath workflows are executed in a restricted environment
- Imports don't resolve in this environment
- The error triggers when imports are present
- But the message blames meta position, not imports

**Real requirement**: For scriptPath, no imports + meta first.

**For named workflows**: Imports OK + meta after imports.

---

**Date**: 2026-06-03
**Context**: Debugging why code-solve workflow wouldn't invoke
**Resolution**: Created self-contained version, works via scriptPath
**Status**: Working ✅
