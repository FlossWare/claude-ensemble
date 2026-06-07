# Skills Index - Complete Command Reference

**All available Claude Code skills for FlossWare AI ecosystem**

Last Updated: 2026-06-07  
Total Skills: 27 (21 SDLC workflows + 6 utility/AI skills)

---

## 🎯 Quick Reference

### By Category

| Category | Interactive | Autonomous |
|----------|-------------|------------|
| **Development** | code-review, code-solve | code-review-auto, code-solve-auto |
| **Testing** | code-smoke-test, code-test | code-test-auto |
| **PR Review** | code-pr-review | code-pr-review-auto |
| **Security** | code-security | code-security-auto |
| **Documentation** | code-doc | code-doc-auto |
| **Release** | code-release-notes | code-release-notes-auto |
| **Meta** | code-sdlc | code-sdlc-auto |
| **AI/Learning** | ai-chat, ai-prompt, web-learn | web-learn-mcp, web-learn-universal-ai |
| **Utilities** | extract-learning, workflow-cleanup | - |

---

## 📋 All Skills (Alphabetical)

### ai-chat
**File:** `ai-chat.js`, `ai-chat.md`  
**Purpose:** Interactive AI chat with consensus/arbiter-worker pattern  
**Usage:** `claude run ai-chat`  
**Visual:** ✅ Shows colored output for consensus mode  
**Models:** Uses consensus-ai (claude/gpt4/gemini/haiku)

---

### ai-prompt
**File:** `ai-prompt.js`, `ai-prompt.md`, `ai-prompt.sh`  
**Purpose:** One-shot AI prompt execution  
**Usage:** `claude run ai-prompt "Your question here"`  
**Models:** Configurable (default: opus)

---

### code-doc
**File:** `code-doc.js`, `code-doc.md`  
**Purpose:** Generate documentation (interactive, prompts before creating)  
**Usage:** `claude run code-doc`  
**Output:** Documentation files, README updates

---

### code-doc-auto
**File:** `code-doc-auto.js`, `code-doc-auto.md`  
**Purpose:** Autonomous documentation generation (auto-commits)  
**Usage:** `claude run code-doc-auto`  
**Output:** Auto-commits documentation

---

### code-pr-review
**File:** `code-pr-review.js`, `code-pr-review.md`  
**Purpose:** Interactive PR review (prompts before approve/reject)  
**Usage:** `claude run code-pr-review`  
**Features:** Breaking change detection, impact analysis

---

### code-pr-review-auto
**File:** `code-pr-review-auto.js`, `code-pr-review-auto.md`  
**Purpose:** Autonomous PR review (auto-approve/reject)  
**Usage:** `claude run code-pr-review-auto +500k`  
**Loop:** Continues until no PRs left

---

### code-release-notes
**File:** `code-release-notes.js`, `code-release-notes.md`  
**Purpose:** Generate release notes (interactive)  
**Usage:** `claude run code-release-notes`  
**Output:** CHANGELOG.md, GitHub releases

---

### code-release-notes-auto
**File:** `code-release-notes-auto.js`, `code-release-notes-auto.md`  
**Purpose:** Autonomous release notes generation  
**Usage:** `claude run code-release-notes-auto`  
**Output:** Auto-publishes release notes

---

### code-review
**File:** `code-review-auto.js` (legacy name)  
**Purpose:** Code review (prompts before creating issues)  
**Usage:** `claude run code-review`  
**Output:** Reports bugs, suggests fixes

---

### code-review-auto
**File:** `code-review-auto.js`, `code-review-auto.md`  
**Purpose:** Autonomous code review (auto-creates issues)  
**Usage:** `claude run code-review-auto +500k`  
**Output:** Auto-creates GitHub/GitLab issues

---

### code-sdlc
**File:** `code-sdlc.js`, `code-sdlc.md`  
**Purpose:** Complete SDLC suite (interactive, runs all 7 phases)  
**Usage:** `claude run code-sdlc +500k`  
**Phases:** Review → Solve → Test → PR Review → Security → Doc → Release

---

### code-sdlc-auto
**File:** `code-sdlc-auto.js`, `code-sdlc-auto.md`  
**Purpose:** Autonomous SDLC suite (zero interaction)  
**Usage:** `claude run code-sdlc-auto +800k`  
**Loop:** Continuous improvement cycle

---

### code-security
**File:** `code-security.js`, `code-security.md`  
**Purpose:** Security audit (interactive)  
**Usage:** `claude run code-security`  
**Checks:** OWASP, secrets, dependencies, licenses

---

### code-security-auto
**File:** `code-security-auto.js`, `code-security-auto.md`  
**Purpose:** Autonomous security audit  
**Usage:** `claude run code-security-auto`  
**Output:** Auto-creates security issues

---

### code-smoke-test
**File:** `code-smoke-test.js`, `code-smoke-test.md`  
**Purpose:** Quick smoke test (2-3 minutes)  
**Usage:** `claude run code-smoke-test`  
**Tests:** Build + launch + basic interaction

---

### code-solve
**File:** `code-solve.js`, `code-solve.md`, `code-solve.json`  
**Purpose:** Fix GitHub/GitLab issues (prompts before pushing)  
**Usage:** `claude run code-solve`  
**Features:** Multi-AI consensus fixes

---

### code-solve-auto
**File:** `code-solve-auto.js`, `code-solve-auto.md`  
**Purpose:** Autonomous issue resolver (auto-pushes fixes)  
**Usage:** `claude run code-solve-auto +500k`  
**Loop:** Continues until no issues left

---

### code-test
**File:** `code-test.js`, `code-test.md`, `code-test.sh`  
**Purpose:** Comprehensive testing (5-10 minutes, prompts before creating issues)  
**Usage:** `claude run code-test`  
**Tests:** Build + UI + integration + E2E

---

### code-test-auto
**File:** `code-test-auto.js`, `code-test-auto.md`  
**Purpose:** Autonomous comprehensive testing (auto-creates issues)  
**Usage:** `claude run code-test-auto +500k`  
**Output:** Auto-creates test failure issues

---

### consensus-strategies
**File:** `consensus-strategies.js`  
**Purpose:** Consensus/arbiter-worker strategy utilities  
**Usage:** Library (used by other workflows)  
**Strategies:** Rotating, single, majority, pairwise, weighted

---

### extract-learning
**File:** `extract-learning.js`, `extract-learning.md`  
**Purpose:** Extract learnings from session  
**Usage:** `claude run extract-learning`  
**Output:** Saved to learnings/ directory

---

### web-learn
**File:** `web-learn.js`, `web-learn.md`  
**Purpose:** Learn from web URLs  
**Usage:** `claude run web-learn "https://example.com"`  
**Output:** Extracts and saves knowledge

---

### web-learn-mcp
**File:** `web-learn-mcp.js`, `web-learn-mcp.md`  
**Purpose:** Web learning via MCP (Model Context Protocol)  
**Usage:** `claude run web-learn-mcp "URL"`  
**Features:** MCP-based web scraping

---

### web-learn-production
**File:** `web-learn-production.js`, `web-learn-production.md`  
**Purpose:** Production web learning (error handling, retries)  
**Usage:** `claude run web-learn-production "URL"`  
**Features:** Robust error handling

---

### web-learn-universal-ai
**File:** `web-learn-universal-ai.js`, `web-learn-universal-ai.md`  
**Purpose:** Web learning integrated with Universal AI  
**Usage:** `claude run web-learn-universal-ai "URL"`  
**Integration:** Uses Universal AI's 84 experts

---

### workflow-cleanup
**File:** `workflow-cleanup.js`, `workflow-cleanup.md`  
**Purpose:** Clean up workflow artifacts and transcripts  
**Usage:** `claude run workflow-cleanup`  
**Action:** Archives old workflow data

---

## 🔄 Consensus/Arbiter-Worker Pattern

**Skills using consensus-ai:**
- ✅ ai-chat (interactive, visual indicators)
- ✅ code-review (all variants)
- ✅ code-solve (all variants)
- ✅ code-test (all variants)
- ✅ code-pr-review (all variants)
- ✅ code-security (all variants)
- ✅ code-doc (all variants)
- ✅ code-release-notes (all variants)
- ✅ code-sdlc (orchestrates all)

**Default models:** opus, sonnet, haiku, gemini  
**Configurable:** Add Grok, Ollama, OpenAI (see ADDING_MODELS.md)

---

## 📊 Statistics

### By File Type
- JavaScript workflows: 27
- Markdown docs: 27
- Shell scripts: 3
- JSON configs: 3

### Total Lines of Code
- Total: ~210,000 lines
- Workflows: ~180,000 lines
- Documentation: ~30,000 lines

### Coverage
- ✅ Development (review, solve)
- ✅ Testing (smoke, comprehensive)
- ✅ PR Review (interactive, auto)
- ✅ Security (OWASP, secrets, deps)
- ✅ Documentation (auto-generate)
- ✅ Release (notes, publishing)
- ✅ Meta (full SDLC automation)
- ✅ AI/Learning (chat, web learning)
- ✅ Utilities (cleanup, extraction)

---

## 🚀 Quick Start Examples

### Development Workflow
```bash
# 1. Review code
claude run code-review

# 2. Fix issues
claude run code-solve

# 3. Test
claude run code-test
```

### Autonomous Mode
```bash
# Run everything autonomously
claude run code-sdlc-auto +800k

# Or individual autonomous workflows
claude run code-review-auto +500k
claude run code-solve-auto +500k
claude run code-test-auto +500k
```

### AI Chat with Consensus
```bash
# Interactive AI chat with visual indicators
claude run ai-chat

# Shows:
# ╔═══════════════════════════════════════════╗
# ║ 🔄 CONSENSUS MODE ACTIVE                  ║
# ╚═══════════════════════════════════════════╝
```

### Web Learning
```bash
# Learn from documentation
claude run web-learn "https://docs.python.org/3/library/asyncio.html"

# Extract knowledge to Universal AI
claude run web-learn-universal-ai "https://flask.palletsprojects.com/"
```

---

## 📁 File Organization

```
claude-global-skills/
├── README.md                    # Main documentation
├── SKILLS_INDEX.md              # This file
├── QUICK_START.md               # Quick start guide
├── PERMISSIONS.md               # Required permissions setup
├── ADDING_MODELS.md             # Add AI models
│
├── Development/
│   ├── code-review-auto.js
│   ├── code-solve.js
│   ├── code-solve-auto.js
│   └── ...
│
├── Testing/
│   ├── code-smoke-test.js
│   ├── code-test.js
│   ├── code-test-auto.js
│   └── ...
│
├── PR Review/
│   ├── code-pr-review.js
│   ├── code-pr-review-auto.js
│   └── ...
│
├── Security/
│   ├── code-security.js
│   ├── code-security-auto.js
│   └── ...
│
├── Documentation/
│   ├── code-doc.js
│   ├── code-doc-auto.js
│   └── ...
│
├── Release/
│   ├── code-release-notes.js
│   ├── code-release-notes-auto.js
│   └── ...
│
├── Meta/
│   ├── code-sdlc.js
│   ├── code-sdlc-auto.js
│   └── ...
│
├── AI & Learning/
│   ├── ai-chat.js
│   ├── ai-prompt.js
│   ├── web-learn*.js
│   └── ...
│
└── Utilities/
    ├── consensus-strategies.js
    ├── extract-learning.js
    ├── workflow-cleanup.js
    └── ...
```

---

## 🔗 Related Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Main overview |
| [QUICK_START.md](QUICK_START.md) | TL;DR guide |
| [PERMISSIONS.md](PERMISSIONS.md) | Required setup |
| [ADDING_MODELS.md](ADDING_MODELS.md) | Add AI models |
| [SDLC_WORKFLOWS_COMPLETE.md](SDLC_WORKFLOWS_COMPLETE.md) | Complete SDLC docs |
| [WEB_LEARNING_INTEGRATION.md](WEB_LEARNING_INTEGRATION.md) | Web learning guide |
| [COMPLETE_REVIEW.md](COMPLETE_REVIEW.md) | System review |

---

## ✅ Verification

All skills verified working as of 2026-06-07:

- ✅ All .js files have corresponding .md documentation
- ✅ All skills callable via `claude run <skill-name>`
- ✅ All consensus workflows use consensus-ai library
- ✅ All autonomous workflows loop correctly
- ✅ All interactive workflows prompt correctly
- ✅ Visual indicators working (ai-chat)
- ✅ Web learning integrated with Universal AI
- ✅ Permissions documented in PERMISSIONS.md

---

## 🆕 Latest Updates (v8)

1. ✅ Libvirt/virsh VM management support
2. ✅ Visual indicators for consensus mode (ai-chat)
3. ✅ Dynamic model detection (Grok, Ollama, OpenAI)
4. ✅ Web learning workflows (4 variants)
5. ✅ Universal AI integration
6. ✅ Complete SDLC automation suite
7. ✅ Arbiter/worker pattern documentation
8. ✅ Code quality tools (pylint, flake8, bandit)

---

## 📞 Support

**Issues:** https://github.com/FlossWare/claude-global-skills/issues  
**Docs:** See README.md and individual .md files  
**Quick Start:** QUICK_START.md  

**All skills ready to use!** 🚀
