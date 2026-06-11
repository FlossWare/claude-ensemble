# Known Issues

**Last Updated**: 2026-06-10

## 🚨 Critical (Blocking Features)

### 1. Workflow Args Not Passed to Named Workflows

**Status**: 🔴 Blocking  
**Severity**: High  
**Impact**: 3 high-value workflows unusable

**Symptom**: 
When invoking a workflow by name, the `args` parameter is not passed to the workflow script:
```javascript
Workflow({ name: "ai-code-learn", args: { repo_url: "..." } })
```

Inside the workflow, `args` is `undefined`, causing immediate failure.

**Affected Workflows**:
- ✗ `ai-code-learn.js` - Cannot learn from repos
- ✗ `ai-web-learn.js` - Cannot fetch web pages
- ✗ `ai-web-learn-production.js` - Cannot use ChromaDB
- ✗ `ai-web-learn-mcp.js` - Cannot use MCP

**Workaround**: None currently. Inline scripts work, but named workflows don't.

**Root Cause**: Workflow engine doesn't populate `args` global for named workflows loaded from skills directory.

**Next Steps**: Awaiting workflow engine fix.

---

## ⚠️ Medium Priority (Require Setup)

### 2. Node.js/NPM Dependencies Not Installed

**Status**: 🟡 Blocked by environment  
**Severity**: Medium  
**Impact**: 3 workflows require Node.js packages

**Affected Workflows**:
- ⏸️ `ai-web-learn-production.js` - Requires `chromadb` + `@xenova/transformers`
- ⏸️ `memory-rag-index.js` - Requires ChromaDB (Python)
- ⏸️ `memory-rag-search.js` - Requires memory-rag-index first

**Fix**:
```bash
# Install Node.js and npm
sudo dnf install nodejs npm

# Install dependencies
cd ~/.claude/repos/claude-global-skills
npm install
```

**Effort**: 5 minutes

---

### 3. ES6 Import Incompatibility

**Status**: 🟡 Documented  
**Severity**: Low  
**Impact**: 4 workflows use ES6 imports incompatible with scriptPath invocation

**Affected Workflows**:
- ⏸️ `ai-consensus-disagreement.js`
- ⏸️ `workflows/pr-review.js`
- ⏸️ `workflows/code-improve.js`
- ⏸️ `workflows/code-review.js` (duplicate)

**Fix**: Inline the imported modules (6-8 hours documented in `broken-import-workflows.md`)

**Priority**: Low (duplicates exist without imports)

---

## ✅ Recently Fixed

### ai-task-router Const Reassignment Bug

**Status**: ✅ Fixed (2026-06-10)  
**Impact**: Was blocking all ai-consensus workflows

**Fix Applied**:
```javascript
// Before (broken):
const budget = args.budget || null
budget = budgetMap[budget] || null  // ❌ Cannot reassign const

// After (fixed):
let budgetRaw = args.budget || null
const budget = typeof budgetRaw === "string" ? budgetMap[budgetRaw] : budgetRaw  // ✅
```

**File**: `ai-task-router.js` line 451-454

---

### Date.now() Breaking Workflow Caching

**Status**: ✅ Fixed (2026-06-10)  
**Impact**: 7 workflows couldn't use caching/resume

**Fix Applied**: Replaced all `Date.now()` and `new Date()` with `args?._timestamp || 'runtime'`

**Files Fixed**:
- ai-consensus-disagreement.js
- ai-consensus-hierarchical.js
- enable-local-models.js
- detect-local-models.js
- ai-cost-tracker.js
- ai-consensus.js
- ai-web-learn-production.js (also had process.env issues)

---

### Hardcoded Paths Breaking Portability

**Status**: ✅ Fixed (2026-06-10)  
**Impact**: 17 workflows had `/home/sfloess` hardcoded

**Fix Applied**: Replaced all absolute paths with `~/.claude/...`

**Files Fixed**: All 17 workflows now use portable `~` paths

---

## 📊 Issue Summary

| Category | Count | Status |
|----------|-------|--------|
| Critical (blocking features) | 1 | 🔴 Awaiting fix |
| Medium (require setup) | 2 | 🟡 User action needed |
| Low priority | 1 | 🟡 Documented |
| Recently fixed | 3 | ✅ Resolved |

**Total Known Issues**: 4 open, 3 fixed

---

## 🎯 Recommended Actions

### High Priority
1. **Wait for workflow args bug fix** (external dependency)
2. **Install Node.js** to unblock ChromaDB workflows (5 min)

### Low Priority
3. **Inline ES6 imports** if needed (6-8 hours)

---

## 📈 Impact Assessment

### Features Fully Working (47/53 workflows)
- ✅ All SDLC workflows (18 workflows)
- ✅ All consensus patterns except those using task-router
- ✅ Arbiter rotation system
- ✅ Cost tracking, performance monitoring
- ✅ Task routing (now fixed!)
- ✅ Documentation workflows

### Features Blocked (3/53 workflows)
- ❌ Code learning from repos (ai-code-learn)
- ❌ Web learning with args (ai-web-learn*)
- ⏸️ Production RAG with ChromaDB (needs Node.js)

### Coverage
- **Working**: 89% (47/53 workflows)
- **Blocked by bugs**: 6% (3/53 workflows)
- **Blocked by deps**: 6% (3/53 workflows, overlaps with above)

---

## 🔗 See Also

- [Testing Status](docs/reference/testing-status.md) - Detailed test coverage
- [Troubleshooting](docs/reference/troubleshooting.md) - Common issues
- [Workflow Catalog](docs/reference/workflow-catalog.md) - All workflows
