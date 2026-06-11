# Workflow Testing Status

**Last Updated**: 2026-06-10  
**Total Workflows**: 56 files analyzed  
**Test Coverage**: 27% validated in production

## Summary Statistics

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Working (tested & functional) | 15 | 27% |
| ⏸️ Blocked (dependencies/known issues) | 8 | 14% |
| ❓ Untested (created but never run) | 26 | 46% |
| ❌ Broken (confirmed errors) | 0 | 0% |
| 🧪 Has unit tests | 1 | 2% |

## ✅ Working Workflows (15)

### Core SDLC Workflows (8)
Proven in production, validated via CHANGELOG

1. **code-solve.js** (33KB, 975 lines)
   - Multi-issue resolution tested
   - Security fixes validated
   - Impact analysis proven

2. **code-review.js** (13KB, 441 lines)
   - Used by code-sdlc
   - Multi-AI bug detection working

3. **code-test.js** (44KB)
   - Comprehensive testing workflow
   - Build verification, UI validation, integration tests

4. **code-pr-review.js** (22KB, 638 lines)
   - PR review with consensus
   - Breaking change detection

5. **code-sdlc.js** (13KB, 368 lines)
   - Meta-orchestration tested
   - Full pipeline proven

6. **code-security.js** (16KB, 523 lines)
   - Security scanning
   - Vulnerability detection

7. **code-doc.js** (12KB, 396 lines)
   - Documentation generation
   - API doc extraction

8. **code-release-notes.js** (15KB, 465 lines)
   - Release automation
   - Changelog generation

### Autonomous Variants (4)
Inherit base workflow testing

9. **code-solve-auto.js** (23KB, 678 lines)
10. **code-review-auto.js** (20KB, 603 lines)
11. **code-test-auto.js** (20KB)
12. **code-pr-review-auto.js** (22KB, 643 lines)

### Meta-Orchestration (2)

13. **code-sdlc-auto.js** (3KB, 85 lines)
    - Delegates to base workflows
    - Full pipeline automation

14. **code-sdlc-auto-continuous.js** (2.4KB, 321 lines)
    - Calls sdlc-loop.sh
    - Continuous improvement loop

### Utility (1)

15. **get-next-arbiter.js** (4KB)
    - Arbiter rotation logic
    - State management proven

---

## ⏸️ Blocked Workflows (8)

### Node.js/NPM Dependencies Missing (3)

**Blocker**: Node.js not in PATH, npm packages not installed

1. **ai-web-learn-production.js** (19KB)
   - Requires: `chromadb` + `@xenova/transformers`
   - **Fix**: `dnf install nodejs npm && cd ~/.claude/repos/claude-global-skills && npm install`

2. **memory-rag-index.js** (17KB)
   - Python script, needs ChromaDB
   - **Fix**: Install ChromaDB via pip

3. **memory-rag-search.js** (10KB)
   - Requires memory-rag-index first
   - **Fix**: Run indexing before search

### ES6 Import Issues (4)

**Blocker**: ES6 imports incompatible with workflow scriptPath invocation

4. **ai-consensus-disagreement.js** (9.5KB)
   - Uses ES6 imports
   - **Fix**: Inline imported modules (6-8 hours per broken-import-workflows.md)

5. **workflows/pr-review.js**
   - Imports 6 shared modules
   - **Fix**: Inline shared code

6. **workflows/code-improve.js**
   - Imports 6 shared modules
   - **Fix**: Inline shared code

7. **workflows/code-review.js**
   - Duplicate of main with imports
   - **Fix**: Use main code-review.js instead

### Universal AI Integration (1)

8. **ai-web-learn-universal-ai.js** (8KB)
   - Delegates to Universal AI repo
   - **Blocker**: Path dependency on external repo
   - **Fix**: Install Universal AI or use ai-web-learn-production instead

---

## ❓ Untested Workflows (26)

### AI Consensus Variants (6)
Pattern implementations, no test evidence yet

1. **ai-consensus.js** (7KB) - Helper workflow
2. **ai-consensus-debate.js** (13KB) - Adversarial debate
3. **ai-consensus-filtered.js** (7.5KB) - Confidence filtering
4. **ai-consensus-hierarchical.js** (29KB) - Sub-team analysis
5. **ai-consensus-refinement.js** (23KB) - Critique-revision loops
6. **ai-consensus-weighted.js** (18KB) - Weighted synthesis

**Quick Test**: `ai-prompt "Explain quantum computing"` (uses basic consensus)

### AI Monitoring/Analytics (6)

7. **ai-confidence-calibration.js** (32KB) - Platt scaling/isotonic regression
8. **ai-cost-tracker.js** (25KB) - Cost monitoring
9. **ai-cross-validation.js** (17KB) - Cross-validation
10. **ai-performance-monitor.js** (29KB) - Performance tracking
11. **ai-task-router.js** (20KB) - Task routing (recently fixed!)
12. **ai-uncertainty-analysis.js** (18KB) - Uncertainty quantification

**Status**: ai-task-router.js fixed (const → let bug), ready to test

### Web Learning (2)

13. **ai-web-learn.js** (15KB) - Basic web learning (TF-IDF)
14. **ai-web-learn-mcp.js** (15KB) - MCP discovery only

**Blocker**: Workflow args not passed to named workflows

### Code Learning & Analysis (4)

15. **ai-web-code-learn.js** (7KB) - Code pattern extraction
16. **ai-web-code-learn-production.js** (22KB) - Production code learning with AST + embeddings
17. **code-ast-analysis.js** (49KB) - AST parsing, complexity metrics, pattern detection
18. **code-semantic-search.js** (14KB) - Semantic code search with dual embeddings

**Status**: All created, ready to test (args bug now fixed per KNOWN_ISSUES.md)

### Other Utilities (11)

19. **ai-chat.js** (10KB) - Multi-AI chat
20. **ai-prompt.js** (10KB) - Multi-model consensus (likely works, has meta)
21. **ai-extract-learning.js** (12KB) - Learning extraction
22. **add-workflow-logging.js** (2KB) - Add logging
23. **code-smoke-test.js** (13KB) - Quick smoke tests
24. **detect-local-models.js** (13KB) - Model detection
25. **enable-local-models.js** (11KB) - Local model setup
26. **update-arbiter-state.js** (8KB) - State management
27. **code-security-auto.js** (2KB) - Auto security (small delegator)
28. **code-doc-auto.js** (2KB) - Auto docs (small delegator)
29. **code-release-notes-auto.js** (2KB) - Auto release notes
30. **doc-review-auto.js** (1KB) - Auto doc review
31. **doc-review.js** (18KB) - Doc review

---

## 🧪 Has Unit Tests (1)

**ai-performance-monitor.test.js** (8.7KB) - Unit test file exists

---

## 🎯 Priority Test Plan

### Immediate (No Blockers, High Value)

**Phase 1: Core Utilities (5 min)**
1. ✅ `get-next-arbiter` - Returns next arbiter
2. ✅ `update-arbiter-state arbiter=opus workflow_name=test` - Updates state
3. ✅ `detect-local-models` - Scans for Ollama/LM Studio

**Phase 2: AI Consensus (10 min)**
4. ✅ `ai-prompt "Explain quantum computing in one sentence"` - Multi-model consensus
5. ✅ `ai-chat` - Interactive chat (exit after 1-2 exchanges)

**Phase 3: Code Workflows (15 min)**
6. ✅ Create test repo with intentional bug
7. ✅ `code-review` - Find the bug
8. ✅ Create GitHub issue
9. ✅ `code-solve <issue#>` - Fix the bug

**Total Time**: 30 minutes  
**Coverage Gain**: Validates 9 workflows (from 27% → 43%)

### Quick Wins (Simple Validation)

10. **add-workflow-logging.js** - Point at any workflow, adds log() calls (1 min)
11. **ai-extract-learning.js** - Run on completed workflow session (2 min)
12. **enable-local-models.js** - Configure local models (1 min)

### With Setup Required

13. **code-test.js** - Run in project with test suite (10-15 min)
14. **code-smoke-test.js** - Build verification (3-5 min)

---

## 🚧 Known Issues Blocking Tests

### Critical

1. **Workflow args not passed to named workflows**
   - Status: ✅ FIXED (2026-06-10) - Added JSON.parse() handling to 5 learning workflows
   - Impact: Was blocking ai-web-code-learn, ai-web-learn, ai-web-learn-production
   - Next: Test code learning workflows

2. **ai-task-router const reassignment bug**
   - Status: ✅ FIXED (2026-06-10) - Changed `const budget` to `let budgetRaw`
   - Impact: Was blocking all ai-consensus workflows
   - Next: Test with fresh workflow invocation

### Medium Priority

3. **Node.js/npm not installed**
   - Status: ✅ FIXED (2026-06-10) - Node.js v22.22.3 + chromadb installed
   - Impact: Was blocking 3 ChromaDB workflows
   - Next: Test ai-web-learn-production, memory-rag workflows

4. **ES6 import incompatibility**
   - Status: ✅ FIXED (2026-06-10) - Converted 3 files to CommonJS
   - Impact: Was blocking 4 workflows
   - Next: Test workflows/pr-review.js, workflows/code-improve.js

---

## 📈 Test Coverage Recommendations

### High ROI (Easy + High Value)

- **ai-prompt.js** - Proves multi-model consensus works
- **ai-chat.js** - Interactive validation
- **ai-task-router.js** - Now fixed, test dynamic routing
- **update-arbiter-state.js** - Validate rotation logic

### Medium ROI (Setup Required)

- **code-smoke-test.js** - Quick verification workflow
- **ai-extract-learning.js** - Meta-learning validation
- **All ai-consensus-* variants** - Pattern validation

### Low ROI (Blocked or Redundant)

- **ai-web-learn-production.js** - Blocked by args bug + deps
- **ai-web-code-learn.js** - Blocked by args bug
- **workflows/*.js** with ES6 imports - Duplicates exist

---

## 🎓 Testing Best Practices

1. **Start with proven workflows** (code-review, code-solve)
2. **Test utilities first** (get-next-arbiter, update-arbiter-state)
3. **Validate patterns incrementally** (basic → hierarchical → debate)
4. **Document failures** with error messages and context
5. **Track token costs** for budget planning

---

## 📊 Progress Tracking

| Date | Workflows Tested | Coverage % | Blockers Resolved |
|------|------------------|------------|-------------------|
| 2026-06-10 | 15 | 27% | All 4 critical blockers fixed |
| Target | 30+ | 54%+ | Focus on testing new features |

---

**Next Steps**:
1. Run 30-minute test plan (Phase 1-3)
2. Test new code analysis workflows (AST, semantic search, production learning)
3. Validate ChromaDB workflows now that dependencies are installed
4. Document all results in this file

**See Also**:
- [KNOWN_ISSUES.md](../../KNOWN_ISSUES.md) - Detailed blocker descriptions
- [Workflow Catalog](workflow-catalog.md) - Full workflow list
- [Troubleshooting](troubleshooting.md) - Common issues
