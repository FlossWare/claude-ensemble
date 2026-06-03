# Changelog

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
