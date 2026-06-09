---
name: workflow-registration-filter
description: Workflows with nested workflow() calls are filtered from skill registration
metadata: 
  node_type: memory
  type: feedback
  originSessionId: current
---

# Workflow Registration Filtering Rule

**Rule**: Workflows containing `workflow()` calls are **excluded from skill registration**, even though nested workflows ARE supported at runtime.

**Why**: The harness filters workflows during discovery/registration phase. Any workflow that calls `workflow({...})` internally will not appear in the skills list or be invokable via `Workflow({name: "..."})`.

**How to apply**: When creating workflows intended to be registered skills:
1. ✅ **Do NOT** include `workflow()` calls inside the script
2. ✅ **Do** inline all logic or use `agent()` calls instead
3. ❌ **Avoid** nesting workflows if the parent needs to be a registered skill

## Evidence

### Discovery Pattern
Checked all workflows in `~/.claude/repos/claude-global-skills/`:
- ✅ Registered: `code-hygiene-review`, `code-solve`, `code-test-review`, `doc-review`, `pr-verify`, `workflow-cleanup`
- ❌ NOT Registered: `code-review-and-solve` (was the ONLY one with `workflow()` call)

### Test Results
```bash
$ grep -l "workflow({" ~/.claude/repos/claude-global-skills/*.js
/home/sfloess/.claude/repos/claude-global-skills/code-review-and-solve.js

$ Workflow({name: "code-review-and-solve"})
Error: Workflow "code-review-and-solve" not found
```

### Available Workflows (from error message)
- deep-research
- code-review
- code-hygiene-review
- code-solve
- code-test-review
- doc-review
- pr-verify
- workflow-cleanup

Notably MISSING: `code-review-and-solve`

## The Fix

Replaced nested workflow call:
```javascript
// ❌ BEFORE - Calls workflow() internally (line 369)
return workflow({
  scriptPath: '/home/sfloess/.claude/workflows/code-solve.js',
  args: [String(issueNum)]
})
```

With inline pipeline:
```javascript
// ✅ AFTER - Uses agent() calls in pipeline
solveResults = await pipeline(
  issueNumbers,
  (issueNum) => agent(`Fetch issue #${issueNum}...`, {schema}),
  (issue) => agent(`Generate fix...`, {schema}),
  (fix) => agent(`Apply fix and close...`, {schema})
)
```

## Runtime vs Registration

**Important distinction**:
- **Runtime**: Nested `workflow()` calls ARE supported (one level deep)
- **Registration**: Workflows with `workflow()` calls are FILTERED OUT

This means:
- ✅ You CAN call `workflow()` from another workflow at runtime via scriptPath
- ❌ You CANNOT register a workflow as a skill if it contains `workflow()` calls

## Workarounds

### Option 1: Inline the Logic (Recommended)
Replace the nested workflow call with equivalent agent() calls.

### Option 2: Use scriptPath Invocation
Don't register it as a skill. Invoke via:
```javascript
Workflow({
  scriptPath: "/path/to/code-review-and-solve.js",
  args: {...}
})
```

### Option 3: Split into Two Steps
Run workflows sequentially in the conversation:
1. First: `Workflow({name: "code-review"})` 
2. Then: `Workflow({name: "code-solve"})`

## code-review-and-solve Status

### Parse Error Issue

Even after removing the nested `workflow()` call, `code-review-and-solve.js` **fails to parse** when invoked via scriptPath:

```
Error: Invalid workflow script: Script parse error: Unexpected token (315:2)
```

**Tested**:
- ❌ Original committed version: Parse error
- ❌ Version without workflow() call: Parse error  
- ❌ Version with simplified template strings: Parse error

**Conclusion**: The harness workflow parser rejects this file for unknown reasons, even though it's valid JavaScript (Node validates it fine).

### Recommended Approach

**Use the workflows separately in sequence:**

1. **First**: `/code-review` - finds issues, creates GitHub issues
2. **Then**: `/code-solve` - auto-resolves all open issues

This achieves the same result without the combined workflow.

### Alternative: Manual Orchestration

You can also orchestrate them in the conversation:
```javascript
// Review first
Workflow({name: "code-review", args: {/*...*/}})

// Then solve
Workflow({name: "code-solve"})
```

## Related Memories
- [[workflow-imports-lesson]] - scriptPath vs named workflow differences
- [[code-skills-autonomous]] - Autonomous workflow patterns

---

**Date**: 2026-06-04
**Context**: Investigating why code-review-and-solve wasn't appearing in /code list
**Resolution**: Use code-review and code-solve separately in sequence
**Status**: Workaround documented ✅
