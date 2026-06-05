# Changelog

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
