# Changelog

## [10] - 2026-06-09

### Feature - Memory RAG System + Multi-AI Consensus Pattern

**Added**
- **memory-rag-index.js** (450+ lines, updated with multi-AI)
  - Index all 156+ memories in ChromaDB with semantic embeddings
  - Multi-AI file discovery (opus/sonnet/haiku + arbiter)
  - Multi-AI parsing validation on sample files
  - Multi-AI quality verification (3 workers rate search quality + arbiter verdict)
  - Persistent vector DB at ~/.claude/chroma/claude-memories
  
- **memory-rag-search.js** (365 lines)
  - Semantic search across memories using embeddings
  - Multi-AI consensus with arbiter/worker pattern
  - 3 workers (opus/sonnet/haiku) analyze relevance in parallel
  - Arbiter selects best analysis with attribution
  - Top 3 results with relevance ratings + key insights + related topics

- **ai-consensus.js** (136 lines)
  - Reusable multi-AI consensus helper workflow
  - Shows standard pattern: 3 workers (opus/sonnet/haiku) + arbiter
  - Can't nest workflows, but documents the pattern
  
- **MULTI_AI_PATTERN.md**
  - Standard template for all workflows
  - Every phase should use multi-AI workers + arbiter
  - Benefits: higher accuracy, reduced false positives, better coverage
  - Cost: 4x per phase (3 workers + 1 arbiter)

**Impact**
- **BREAKING PATTERN**: All meaningful phases now use multi-AI consensus
- File discovery, parsing, verification all use 3 workers + arbiter
- 30 total workflows (26→30), 13,500+ lines (10,000→13,500)
- Multi-AI is now the standard, not the exception
- README updated to v10, simplified changelog to pure X versioning (v10, v9, v8...)

---

## [9] - 2026-06-07

### Major Enhancements

**Added**
- Continuous SDLC loop (code-sdlc-auto-continuous)
- Full parallelization across all workflows (75-90% faster)
- Worktree isolation for parallel issue fixing
- Enhanced phase banners and progress tracking
- Date.now() fixes for deterministic workflow execution
- Security auto-fix in continuous mode
- Infinite loop prevention with MAX_CONSECUTIVE_FAILURES

**Impact**
- All batch-processing workflows fully parallelized
- Safer continuous operation
- Better platform detection (github/gitlab/bitbucket)
- 26 workflows, 10,000+ lines

**Technical Details**
- Uses `parallel()` workflow primitive for concurrent execution
- Graceful error handling with `.filter(Boolean)` 
- Maintains per-item progress logging
- Failed agents don't block others

---

## [9.1.1] - 2026-06-07

### Bug Fix - Removed Duplicate Log Line

**Fixed**
- **Removed duplicate log line in `code-sdlc-auto-continuous.js`**
  - Line 176 referenced undefined variable `fixableIssues`
  - Should have been `findingsToFix` (correct variable)
  - Removed duplicate empty log lines and duplicate fix message

**Impact**
- Prevents runtime error when continuous loop executes fix phase
- Cleaner console output (no duplicate messages)

---

## [9.1] - 2026-06-07

### Bug Fix - Restored code-review.js Workflow

**Fixed**
- **Restored `code-review.js` base workflow** (26 workflows total, was 25)
  - Required by `code-sdlc.js` on line 58: `workflow('code-review', { autonomous: AUTONOMOUS })`
  - Was deleted in commit 81260f3 due to ES6 imports breaking scriptPath registration
  - Restored as simplified 441-line version without imports (inlined platform detection)
- **Added security scanning to continuous loop**
  - `code-sdlc-auto-continuous` now scans for critical security vulnerabilities
  - Auto-fixes SQL injection, XSS, command injection, path traversal, etc.
  - Prevents critical vulns from blocking continuous auto-fix mode
- **Removed 13 outdated documentation files**
  - Old pr-review.md docs (renamed to code-pr-review)
  - Deprecated workflow docs (code-improve, doc-*, arbiter)
  - Old summary/release docs

**Impact**
- Fixes "calling non-existent workflow" error when running `code-sdlc-auto`
- Enables auto-fixing of critical security vulnerabilities in continuous mode
- Complete base workflow set: code-review, code-solve, code-test (all required by code-sdlc)
- Clean documentation with no outdated references

---

## [9] - 2026-06-07

### Enhancement - Continuous Loop & Phase Visibility

**Added**
- **`code-sdlc-auto-continuous.js`** - Autonomous continuous SDLC loop
  - Scans for bugs and code quality issues
  - Auto-fixes high/critical severity issues
  - Tests fixes before committing
  - Loops until codebase is clean (max 10 iterations)
- **Phase entry banners** across all SDLC workflows
  - ═ bordered headers for better visibility in long-running workflows
  - Uppercase phase names (e.g., "📋 PHASE 1/6: DEVELOPMENT")
  - Added to code-sdlc, code-sdlc-auto, code-sdlc-auto-continuous

**Fixed**
- **Date.now() violations** in 9 workflows (breaks resume/caching feature)
  - `ai-extract-learning.js` - removed timestamp from return value
  - `code-release-notes.js` - removed date from release notes header
  - `code-sdlc.js` - removed start_time/elapsed time tracking
  - `code-doc.js` - changed dynamic branch names to fixed/args-based
  - `ai-web-learn*.js` (4 files) - removed timestamps from temp files and returns
- **AUTO_CRITERIA initialization error** in `code-sdlc-auto.js`
  - Moved definition from line 41 to line 17 (before usage in log statements)

**Changed**
- **Renamed workflows** to consistent `ai-*` prefix for utilities
  - `extract-learning.js` → `ai-extract-learning.js`
  - `web-learn*.js` → `ai-web-learn*.js` (4 workflows)
  - Total: 7 AI utilities, 18 SDLC workflows, 1 cleanup utility (25 total)

**Impact**
- Workflow resume/caching now works correctly (no Date.now() blocking)
- Better visibility in long-running autonomous pipelines
- Continuous loop enables "fix until clean" automation
- Consistent naming improves discoverability

---

## [8] - 2026-06-06

### Enhancement - Libvirt/VM Management Support

**Added**
- **Global libvirt/virsh permissions** for VM infrastructure management
  - `Bash(virsh *)` - All virsh commands (user session)
  - `Bash(sudo virsh *)` - System session virsh commands
  - `Bash(virt-manager *)` - VM GUI management
  - `Bash(virt-install *)` - VM creation from command line
  - `Bash(virt-viewer *)` - VM console viewer
  - `Bash(virt-clone *)` - VM cloning operations
  - `Bash(qemu-img *)` - Disk image management
  - `Bash(qemu-system-* *)` - QEMU emulator access

**Features**
- Complete KVM/QEMU/libvirt infrastructure support
- System and user session management
- VM lifecycle operations (create, start, stop, destroy)
- Disk image manipulation
- Network configuration
- Cloud-init integration support

**Impact**
- Enables VM-based development and testing workflows
- Supports cloud-init VM provisioning
- Full libvirt group member operations
- No permission prompts for VM management

---

## [7] - 2026-06-06

### Major Enhancement - Dynamic Model Detection & Web Learning

**Added**
- **Dynamic model detection** across all workflows
  - Auto-detects available models (Opus, Sonnet, Haiku, Gemini, Grok, Ollama)
  - Graceful fallback when models fail (null results filtered out)
  - Custom worker override via `--workers` flag
  - Rotation patterns adapt to available worker count
- **Web learning workflows** (3 new workflows)
  - `web-learn.js` - Core web content learning with arbiter/worker pattern
  - `web-learn-mcp.js` - Production version with MCP tool discovery
  - `web-learn-universal-ai.js` - Integration with Universal AI RAG system
- **Model configuration utilities**
  - `shared/model-detection.js` - Reusable model detection logic
  - `sync-universal-ai.sh` - Sync script for Universal AI integration
- **Comprehensive documentation**
  - `ADDING_MODELS.md` - Guide for adding Grok, Ollama, OpenAI, etc.
  - `WEB_LEARNING_INTEGRATION.md` - Universal AI integration patterns

**Updated** (10 workflows enhanced)
- `ai-prompt.js` - Dynamic worker selection, Gemini support
- `code-solve.js` - Dynamic rotation patterns, custom worker override
- `code-solve-auto.js` - Model detection integration
- `code-pr-review.js` - Multi-model support
- `code-pr-review-auto.js` - Model detection
- `code-release-notes.js` - Enhanced model selection
- `code-review-auto.js` - Dynamic workers
- `code-security.js` - Model detection
- `code-doc.js` - Multi-model enhancement
- `code-test-auto.js` - Worker detection

**Features**
- All workflows now default to 4 workers: opus, sonnet, haiku, gemini
- Easy model addition - just uncomment in workflow files
- No configuration required - models auto-detect and fallback gracefully
- Worker pools scale from 3 (Claude only) to 10+ (with Grok/Ollama/OpenAI)

**Documentation**
- Added model addition guide (ADDING_MODELS.md - 275 lines)
- Added Universal AI integration docs (WEB_LEARNING_INTEGRATION.md - 462 lines)
- Updated workflow descriptions with model count

**Impact**
- 33% more model diversity (3 → 4 default workers with Gemini)
- Zero-config model fallback (failed models auto-filtered)
- Extensible to unlimited models (Grok, Ollama, OpenAI ready)
- Web learning enables expert knowledge extraction like Universal AI

---

## [6] - 2026-06-06

### Critical Fix - Workflow Tool Permission

**Added**
- **"Workflow" permission** - Required for all .js workflows to execute

**Fixed**
- **CRITICAL**: All .js workflows were blocked in don't-ask mode
- ai-prompt workflow now works without permission errors
- code-sdlc/* workflows can now call sub-workflows
- All 18 workflows now functional in don't-ask mode

**Documentation**
- Added "Critical: Workflow Tool Permission" section to PERMISSIONS.md
- Explained why Workflow permission is required
- Clarified difference between Workflow tool and Bash permissions

**Root Cause**
- All .js workflows execute via the Workflow tool (execution engine)
- Skills invoke workflows using the Workflow tool
- Without "Workflow" permission, execution was blocked

**Impact**
- Single permission enables all 18 workflows
- No per-workflow configuration needed
- Simple one-time global setting

---

## [5] - 2026-06-06

### Major - Comprehensive Permissions Documentation

**Added**
- **PERMISSIONS.md** (747 lines) - Complete permissions setup guide
  - Quick copy-paste permissions block
  - Platform-specific sections (GitHub/GitLab/Bitbucket)
  - Build tool permissions (npm/yarn/gradle/maven)
  - Per-workflow permission requirements
  - Troubleshooting guide with common errors
  - Permission pattern explanations
  - Testing recommendations

**Updated**
- **README.md** - Added prominent permissions link in Quick Start
- **QUICK_START.md** - Added required permissions setup section
- **SDLC_WORKFLOWS_COMPLETE.md** - Added permissions prerequisite
- **CODE_SDLC_COMPLETE.md** - Added permissions prerequisite
- **User settings.json** - Added 25+ new permission rules

**Fixed**
- GitLab workflows now fully operational (added `glab` commands)
  - `glab pr *` - Pull request operations
  - `glab mr *` - Merge request operations
  - `glab release create` - Release creation
  - `glab issue note` - Issue comments
- Node.js projects no longer trigger permission prompts (added `npm`, `yarn`, `pnpm`)
- Gradle projects fully supported (added `gradle build/test/clean`)
- GitLab API fallback working (added `curl` commands)
- Bitbucket support added (added `bb` commands)

**Impact**
- All 18 workflows now work without permission prompts on GitHub/GitLab/Bitbucket
- 2-minute setup for new users
- Zero permission prompts during workflow execution
- Complete platform coverage (GitHub + GitLab + Bitbucket)

---

## [1.1.2] - 2026-06-05

### Security
- **CRITICAL**: Fixed 4 security vulnerabilities in `code-solve.js` createIssueClaimer function
  - **RCE Fix #1**: Shell injection on issueId - now validates as positive integer (1-999999999)
  - **RCE Fix #2**: Shell injection on label parameter - now validates alphanumeric + dash/underscore only
  - **Fix #3**: Missing validation - throws clear error if item.id/item.number missing
  - **Fix #4**: Race condition improvements - better variable quoting, JSON parsing with jq
  - Impact: Prevents remote code execution if attacker controls issue IDs or label values
  - Registration preserved: Meta block remains at line 4, workflow still appears in skills list

## [1.1.1] - 2026-06-05

### Fixed
- **code-solve.js**: Moved `export const meta` block to top of file (line 4) for proper workflow registration
  - Meta block must be FIRST statement (after comments) for harness to discover workflow
  - Previously at line 148, preventing skill registration
  - Now appears in available skills list as `/code-solve`
- **code-solve.md**: Added YAML frontmatter for skill discovery

### Documentation
- Updated memory: claude-code-workflows.md with root cause of registration failure
- Documented requirement: `export const meta` must be first statement in workflow files

## [1.1.0] - 2026-06-03

### Added
- Learnings directory with critical workflow lessons
- claude-code-workflows.md - Workflow registration documentation
- workflow-imports-lesson.md - Import handling and invocation modes

### Enhanced
- code-solve.js: Support for "all" mode (solve all open issues)
- code-solve.js: GitLab token detection and usage
- Plugin system with proper SKILL.md format in ~/.claude/plugins/

### Fixed
- code-solve workflow now works (self-contained, no imports)
- All skills have working --help implementation
- Removed universal-ai dependencies

## [1.0.0] - 2026-06-03

### Initial Release
- 9 global skills (code-solve, code-review-unified, pr-review, etc.)
- 7 workflow implementations
- Shared workflow modules
- Multi-model consensus support (5 strategies)
- GitHub/GitLab/Bitbucket platform detection
