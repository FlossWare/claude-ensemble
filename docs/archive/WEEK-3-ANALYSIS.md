# Week 3 Workflow Analysis

**Total Lines**: 1,657 across 6 workflows  
**Status**: Pre-analysis for refactoring

## Workflows to Refactor

### 1. doc-review.js
**Current State**: Unknown size  
**Potential Patterns**:
- Platform detection (likely needed for issue creation)
- Issue operations (create issues for doc problems)
- Schema duplication
- AI attribution missing

**Refactoring Approach**:
- Copy detectPlatform inline
- Copy createIssue inline
- Add AI attribution for doc quality findings
- Use schemas from shared/inline/schemas.js

**Estimated Impact**: Medium (likely 200-300 lines)

---

### 2. pr-review.js
**Current State**: Already imports from shared/platform-detector.js  
**Imports**: detectPlatform, syncWithRemote, fetchPR, postComment  

**Problem**: Can't use imports with scriptPath!

**Refactoring Approach**:
- Remove import statement
- Copy detectPlatform, fetchPR, postComment inline
- Add NO_BASH_INSTRUCTION to all prompts
- Add AI attribution for PR review findings
- Use inline schemas

**Estimated Impact**: High (imports need conversion + attribution)

---

### 3. pr-verify.js
**Current State**: Unknown size  
**Potential Patterns**:
- Platform detection
- PR verification operations
- Build/test verification
- Schema duplication

**Refactoring Approach**:
- Copy detectPlatform inline
- Copy PR operations inline
- Add AI attribution
- Add progress logging

**Estimated Impact**: Medium

---

### 4. code-improve.js
**Current State**: Already imports from shared/platform-detector.js  
**Imports**: detectPlatform, syncWithRemote, createPR  

**Problem**: Can't use imports with scriptPath!

**Refactoring Approach**:
- Remove import statement
- Copy detectPlatform, syncWithRemote, createPR inline
- Add NO_BASH_INSTRUCTION
- Add AI attribution for improvement suggestions
- Use inline schemas

**Estimated Impact**: High (imports + attribution)

---

### 5. ai-prompt.js
**Current State**: Unknown size  
**Potential Patterns**:
- Likely arbiter-based consensus
- AI attribution already present?
- Schema duplication

**Refactoring Approach**:
- Check if AI attribution needed
- Add NO_BASH_INSTRUCTION
- Minimal changes (likely smallest refactor)
- Use inline schemas

**Estimated Impact**: Low (special purpose workflow)

---

### 6. workflow-cleanup.js
**Current State**: Unknown size  
**Potential Patterns**:
- File operations (cleanup old workflows)
- No platform detection needed
- Simple utility workflow

**Refactoring Approach**:
- Add NO_BASH_INSTRUCTION
- Minimal inline functions
- Add progress logging if missing
- Keep simple

**Estimated Impact**: Low (utility workflow)

---

## Refactoring Strategy

### Phase 1: High-Import Workflows (2 workflows)
Focus on workflows that already use imports (broken pattern):
1. **pr-review.js** - Convert imports to inline
2. **code-improve.js** - Convert imports to inline

**Why First**: These are currently broken if used with scriptPath

### Phase 2: Medium Complexity (3 workflows)
Platform detection + issue operations:
3. **doc-review.js** - Add platform detection + attribution
4. **pr-verify.js** - Add platform detection + attribution
5. **workflow-cleanup.js** - Minimal changes

### Phase 3: Low Complexity (1 workflow)
6. **ai-prompt.js** - Special purpose, minimal changes

---

## Common Patterns to Apply

### 1. Replace Imports with Inline Functions
```javascript
// ❌ REMOVE
import { detectPlatform } from './shared/platform-detector.js'

// ✅ ADD (copy from shared/inline/platform-detector.js)
async function detectPlatform(agent) {
  // ... (inline code)
}
```

### 2. Add NO_BASH_INSTRUCTION to All Prompts
```javascript
const NO_BASH_INSTRUCTION = `
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
`.trim()

// Use in every agent call
const result = await agent(`Task.

${NO_BASH_INSTRUCTION}

Return results.`, { schema })
```

### 3. Add AI Attribution
- For single-model workflows: Simple attribution
- For multi-model workflows: Full consensus tracking
- Include in issue bodies / PR comments

### 4. Add Progress Logging
```javascript
log(`🔄 ${count} workers ${action}...`)
// ... parallel operation
log(`✅ Received ${results.filter(Boolean).length}/${count}`)
```

---

## Estimated Effort

| Workflow | Complexity | Lines | Effort | Priority |
|----------|-----------|-------|--------|----------|
| pr-review.js | High | ~300? | 3h | P0 (broken imports) |
| code-improve.js | High | ~250? | 3h | P0 (broken imports) |
| doc-review.js | Medium | ~200? | 2h | P1 |
| pr-verify.js | Medium | ~200? | 2h | P1 |
| workflow-cleanup.js | Low | ~100? | 1h | P2 |
| ai-prompt.js | Low | ~100? | 1h | P2 |

**Total Estimated Effort**: ~12 hours  
**With Multi-AI Pattern**: Could parallelize and reduce to ~4-6 hours

---

## Recommended Approach

### Option A: Multi-AI Automated (Like Week 2)
- Use refactor-all-workflows.js on all 6
- Workers propose, arbiter selects, role swap validates
- Iterate until consensus
- **Pros**: Thorough, validated, catches bugs
- **Cons**: Token-intensive (~2-3M), takes time

### Option B: Template-Based Manual
- Use TEMPLATE-arbiter-worker.js as base
- Manually refactor each workflow
- Apply lessons from Week 2
- **Pros**: Fast, controlled, less tokens
- **Cons**: Manual work, might miss edge cases

### Option C: Hybrid
- **Phase 1**: Multi-AI for high-complexity (pr-review, code-improve)
- **Phase 2**: Manual for medium (doc-review, pr-verify, workflow-cleanup)
- **Phase 3**: Manual for low (ai-prompt)
- **Pros**: Balance of validation and speed
- **Cons**: Mixed approach

---

## Next Steps

1. **Read each workflow** to understand current state
2. **Identify exact duplication** (line numbers)
3. **Choose approach** (automated vs manual vs hybrid)
4. **Execute refactoring** (start with P0 broken imports)
5. **Test each workflow** after refactoring
6. **Commit changes** with full attribution

---

**Status**: Analysis complete, ready to start Week 3  
**Recommendation**: Start with pr-review.js and code-improve.js (broken imports)  
**Approach**: Use template + manual (faster than multi-AI for 6 workflows)
