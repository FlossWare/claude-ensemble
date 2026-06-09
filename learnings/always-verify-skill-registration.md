---
name: always-verify-skill-registration
description: When modifying skills/workflows, ALWAYS verify registration still works afterward
metadata:
  type: feedback
  originSessionId: current
---

# Always Verify Skill Registration After Modifications

**Rule**: After modifying any skill or workflow file, ALWAYS verify it still registers properly.

**Why**: Structural changes can break registration even if the code logic is correct. The harness silently rejects workflows that don't meet strict structural requirements.

**How to apply**: After ANY modification to a `.js` workflow file, perform these verification steps:

## Verification Checklist

### 1. Check Meta Block Position
```bash
grep -n "export const meta" path/to/workflow.js | head -1
```
**Expected**: Line 3-6 (must be FIRST statement after comments)
**If not**: Move meta block to top immediately

### 2. Verify File Syntax
```bash
node --check path/to/workflow.js
```
**Expected**: No output (syntax valid)
**If errors**: Fix syntax before proceeding

### 3. Restart Claude Code
Meta changes and structural fixes require restart to take effect.

### 4. Confirm Skill Appears
Check system-reminder in a new conversation:
```
The following skills are available for use with the Skill tool:
- your-skill-name: Description here
```
**Expected**: Skill appears in the list
**If missing**: Meta block position issue or other structural problem

### 5. Test Invocation
```javascript
Skill({skill: "your-skill-name", args: "test"})
```
**Expected**: Skill loads without "meta must be first" error
**If error**: Structural issue remains

## What Can Break Registration

### Always Breaks Registration
- ❌ Meta block NOT at top (after comments)
- ❌ Meta block missing required fields (name, description, phases)
- ❌ Syntax errors in the file

### Sometimes Breaks Registration
- ⚠️ Workflow contains `workflow()` calls (separate filter)
- ⚠️ ES6 imports in some contexts (depends on invocation mode)
- ⚠️ Missing `.md` file with frontmatter

### Never Breaks Registration
- ✅ Code changes inside helper functions
- ✅ Validation logic additions
- ✅ Security fixes
- ✅ Comment changes
- ✅ Variable renaming

## Safe Modification Pattern

**For ANY change to a workflow file:**

1. **Before**: Note current meta position
   ```bash
   grep -n "export const meta" workflow.js
   ```

2. **Make changes**: Edit the file (security fixes, logic updates, etc.)

3. **After**: Verify meta position unchanged
   ```bash
   grep -n "export const meta" workflow.js
   ```
   Should be SAME line number as before

4. **Test**: Run syntax check
   ```bash
   node --check workflow.js
   ```

5. **Commit**: If all checks pass

6. **Restart**: Restart Claude Code

7. **Verify**: Confirm skill appears in available list

## Example: Security Fix Workflow

```bash
# 1. Check meta position BEFORE
grep -n "export const meta" code-solve.js
# Output: 4:export const meta = {

# 2. Make security fixes (inside helper functions)
# ... edit file ...

# 3. Check meta position AFTER  
grep -n "export const meta" code-solve.js
# Output: 4:export const meta = {
# ✅ SAME LINE - registration preserved

# 4. Verify syntax
node --check code-solve.js
# (no output = success)

# 5. Commit
git add code-solve.js
git commit -m "security: fix XYZ"
git push

# 6. Restart Claude Code

# 7. Verify in new session
# Check system-reminder includes "code-solve"
```

## When Meta Position Changes

If you MUST move code that affects meta position:

1. **Plan the restructure** - know where meta will land
2. **Make the change** - move code carefully
3. **Verify meta is FIRST** - grep for position
4. **If not first** - move meta to line 3-4 immediately
5. **Test thoroughly** - syntax check + registration check
6. **Document in commit** - note registration was preserved/fixed

## Real-World Example (2026-06-05)

### Security Fixes to code-solve.js

**Changes made**:
- Added validation in `createIssueClaimer()` (lines 188-245)
- Fixed shell injection vulnerabilities
- Added error checking
- Improved shell quoting

**Verification performed**:
```bash
# Before: meta at line 4
grep -n "export const meta" code-solve.js
4:export const meta = {

# After security fixes: meta STILL at line 4
grep -n "export const meta" code-solve.js  
4:export const meta = {

# Syntax valid
node --check code-solve.js
# (no errors)

# Skill still appears in list after restart
# ✅ Registration preserved
```

**Result**: All security fixes applied, registration intact, skill still usable.

## Memory Integration

This rule complements:
- [[workflow-meta-first-requirement]] - WHY meta must be first
- [[claude-code-workflows]] - How registration works
- [[workflow-registration-filter]] - What else can break registration

## Future Process

**Every time you modify a workflow/skill**:

1. ✅ Check meta position before (should be line 3-6)
2. ✅ Make your changes
3. ✅ Check meta position after (should be SAME line)
4. ✅ Run syntax check
5. ✅ Commit only if checks pass
6. ✅ Restart Claude Code
7. ✅ Verify skill appears in list

**Don't skip steps** - registration breakage is silent and confusing to debug later.

---

**Key Insight**: Registration is STRUCTURAL, not logical. The code can be perfect but invisible if structure is wrong.

**Time cost**: 30 seconds per verification

**Benefit**: Never push a broken workflow that silently disappears from the skills list
