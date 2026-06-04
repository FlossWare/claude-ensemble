# Claude Code Global Workflows

Autonomous multi-AI workflows for code quality, testing, and maintenance.

## Workflows

### Code Quality
- **code-review** - 5-type review: commits, issues, codebase, dependencies, security
- **code-solve** - Auto-resolve GitHub/GitLab issues with multi-AI consensus
- **code-review-and-solve** - Complete loop: review finds issues, solve fixes them

### Testing & Quality
- **code-test-review** - Test quality analysis: coverage, flaky tests, performance
- **code-hygiene-review** - Repository cleanup: stale branches, issues, PRs, dependencies

### Documentation & PRs
- **pr-review** - Continuous PR monitoring and auto-review
- **doc-review** - Multi-agent documentation review

### Utilities
- **workflow-cleanup** - Clean accumulated workflow transcripts
- **ai-prompt** - Multi-model consensus for any question

## Installation

```bash
cp -r workflows ~/.claude/
cp -r skills ~/.claude/
```

## Usage

All workflows available as skills:

```bash
/code-review              # Comprehensive 5-type code review
/code-solve loop          # Auto-resolve all open issues  
/code-test-review         # Analyze test quality
/code-hygiene-review      # Repository cleanup
/code-review-and-solve    # Full quality loop
/workflow-cleanup         # Clean workflow history
```

## Architecture

- **Multi-AI Consensus** - Opus, Sonnet, Haiku workers + rotating arbiters
- **Worktree Isolation** - Safe parallel execution
- **Autonomous** - No manual approval required
- **Platform Agnostic** - Works with GitHub, GitLab, Bitbucket
