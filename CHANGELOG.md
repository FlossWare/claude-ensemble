# Changelog

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
