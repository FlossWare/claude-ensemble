---
name: session-learnings-2026-06-04
description: Key learnings from arbiter/worker pattern implementation and workflow refactoring session
metadata:
  node_type: memory
  type: feedback
  originSessionId: current
  date: 2026-06-04
---

# Session Learnings: Arbiter/Worker Pattern & Workflow Refactoring

## 1. Arbiter/Worker Pattern is HIGHLY Effective at Catching Bugs

**What happened**: Initial refactoring workflow with 8 workflows, all 8 proposals rejected by role swap validation.

**Why important**: The pattern worked EXACTLY as designed:
1. Workers proposed refactorings
2. Arbiter selected "best" proposals
3. **Role swap validation caught critical flaws in ALL 8**
4. Consensus correctly NOT reached

**Critical bugs caught**:
- Runtime crashes (undefined variables)
- Shell injection vulnerabilities
- Export syntax in inline code (parse errors)
- Logic bugs in tracking
- Claims to save lines but actually adds lines
- Unused dead code (80+ lines)

**Learning**: Role swap validation is the **most valuable phase** - it prevents bad solutions from being applied. Don't skip it!

## 2. For Solve/Refactor Phases: ALWAYS Use `parallel()`

**User feedback**: "for solving parallel should always be used by default"

**Why**: In solve/refactor phases, workers should propose independently without seeing each other's work. This gives diverse perspectives and prevents groupthink.

**Applied to**:
- Updated arbiter-worker-pattern memory
- Added rule #7: "Use `parallel()` for solve/refactor phases"
- Updated all examples to show `parallel()` for solve/refactor

**When to use `pipeline()`**: Only for multi-stage analysis where stages are dependent (e.g., analyze → fix based on analysis for EACH item).

## 3. Progress Logging is Critical for User Experience

**User feedback**: "when running in parallel itd be nice to have some periodic info"

**Problem**: Parallel operations take a long time. Without logging, users see nothing and wonder if it's frozen.

**Solution**: Three-step pattern:
```javascript
// 1. Log BEFORE
log(`🔄 ${count} workers ${action} in parallel...`)

// 2. Use descriptive labels (shows in /workflows UI)
const results = await parallel(items.map(item =>
  () => agent('Task', {
    label: `${model} ${task}`,  // ← Key for visibility
    model, schema
  })
))

// 3. Log AFTER with count
log(`✅ Received ${results.filter(Boolean).length}/${items.length} results`)
```

**Created**:
- `progress-logging-parallel.md` memory
- `shared/PROGRESS-LOGGING-PATTERN.md` documentation
- Updated arbiter-worker-pattern with logging examples

## 4. Different Arbiters for Different Phases (CRITICAL RULE)

**Rule**: When using arbiter/worker for BOTH review and solve, **NEVER use the same arbiter for both**.

**Why**: Same arbiter creates bias - they'd favor their own review findings when solving.

**Example**:
```javascript
// REVIEW PHASE
const REVIEW_ARBITER = 'opus'
// ... review happens

// SOLVE PHASE - DIFFERENT ARBITER
const SOLVE_ARBITER = 'sonnet'  // ⚠️ DIFFERENT!
// ... solve happens
```

**Applied to**: All multi-phase workflows and iteration logic.

## 5. Iteration with Concern Feedback Works

**Pattern**: 
1. Initial proposals fail validation
2. Feed validation concerns back to workers
3. Workers propose REVISED solutions addressing concerns
4. Different arbiter selects
5. Role swap validates again
6. Repeat until consensus or max iterations

**Implementation**: Created `refactor-iterate.js` workflow that:
- Loads failed refactorings automatically
- Iterates up to 3 times
- Rotates arbiters each iteration (Haiku → Opus → Sonnet)
- Tracks which concerns are addressed vs remaining
- Auto-stops when consensus reached

## 6. Automation Preferences for Power Users

**User feedback**: "when running against ~/.claude please auto accept everything for claude perms inckuding running commands"

**Learning**: Power users developing workflows want:
- No permission dialogs blocking progress
- 100% automated workflows
- Fast iteration speed
- Transparency (logging) but no blocking prompts

**Scope**: Auto-accept for `~/.claude/` operations only. Still confirm for:
- Operations outside `~/.claude/`
- Destructive git operations on non-test repos
- System directories

**Applied**: Saved to `automation-preferences.md` memory.

## 7. Critical Bugs Found in work-coordinator.js Refactoring

**From code review workflow that ran in parallel**:

### Shell Injection Vulnerability (FIXED)
- **Issue**: Used unescaped `${label}` in grep command
- **Fix**: Switched to structured JSON output with jq
- **Impact**: Prevents arbitrary command execution

### ALREADY_CLAIMED Logic Bug (FIXED)
- **Issue**: Used `.includes('CLAIMED')` which matched both 'CLAIMED' and 'ALREADY_CLAIMED'
- **Fix**: Use structured schema `{claimed: boolean, alreadyClaimed: boolean}`
- **Impact**: Correctly detects when issues already claimed

### Contract Mismatch (FIXED)
- **Issue**: Returned different fields when no work vs when work completed
- **Fix**: Always return `{status, total, successful, skipped, failed, results}`
- **Impact**: code-solve.js gets expected fields, no more `undefined` in logs

### Efficiency Improvements (FIXED)
- Removed unnecessary `.slice()` that discarded work items
- Changed triple-filter to single `.reduce()` pass (3x faster)

## 8. Inline Functions Pattern for Workflows

**Problem**: Workflows using `scriptPath` cannot use ES6 `import` statements.

**Solution**: Copy functions directly into workflow files (inline pattern).

**Created**:
- `shared/inline/platform-detector.js` (290 lines)
- `shared/inline/git-operations.js` (215 lines)
- `shared/inline/schemas.js` (210 lines)
- `shared/inline/README.md` (300 lines usage guide)

**Pattern**:
```javascript
// ============================================================================
// INLINE FUNCTIONS (copied from shared/inline/platform-detector.js)
// ============================================================================

async function detectPlatform(agent) {
  // ... (copied code)
}

// ============================================================================
// WORKFLOW CODE
// ============================================================================

const platform = await detectPlatform(agent)
```

**Trade-off**: Code duplication vs import restrictions. Chose duplication because workflows need to work with `scriptPath`.

## 9. Multi-AI Workflows Consume Significant Tokens

**Observation**: 
- First refactoring workflow: 88 agents, 2.9M tokens
- Code review workflow: 32 agents, 925K tokens

**Implication**: Multi-AI patterns are expensive but highly effective. Use when:
- ✅ Decision quality is critical
- ✅ Multiple valid approaches exist
- ✅ Need consensus validation
- ❌ Don't use for trivial decisions

**Best practice**: Start with 2-3 workflows to test pattern, then scale to all.

## 10. Workflow Args Don't Work Reliably

**Problem**: Passing `args` to workflows via Workflow tool doesn't work - `args` is undefined in the workflow.

**Workaround**: Load data from files instead:
```javascript
const data = await agent(`cat workflows/data.json`, { schema })
const parsed = JSON.parse(data.json_content)
```

**Better**: Use file-based state for workflow inputs instead of relying on `args` parameter.

## Key Takeaways

### Patterns That Work
1. ✅ Arbiter/worker with role swap validation
2. ✅ Different arbiters for different phases
3. ✅ Parallel for solve, pipeline for dependent stages
4. ✅ Progress logging before/after parallel operations
5. ✅ Iterative refinement with concern feedback
6. ✅ Inline functions for scriptPath workflows

### Patterns to Avoid
1. ❌ Same arbiter for review AND solve
2. ❌ Silent parallel operations (no logging)
3. ❌ Skipping role swap validation
4. ❌ Using workflow args (unreliable)
5. ❌ Export syntax in inline code
6. ❌ Claiming to save lines when actually adding

### What to Remember
- Role swap validation is the MOST valuable phase - it catches bugs the arbiter missed
- Progress logging transforms user experience from "is it frozen?" to "I can see exactly what's happening"
- 100% automation is achievable with proper iteration and validation
- Multi-AI patterns are expensive but worth it for critical decisions
- Power users want speed - auto-accept for development workflows in `~/.claude/`

---

**Status**: Session complete, patterns validated  
**Date**: 2026-06-04  
**Next**: Apply approved refactorings once iteration workflow completes
