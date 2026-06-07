# Changelog

## [5.0.0] - 2026-06-06

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
