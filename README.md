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
- **code-improve** - Iterative code quality improvement loop

### Documentation & PRs
- **pr-review** - Continuous PR monitoring and auto-review
- **pr-verify** - Verify open PRs: build, test, quality checks
- **doc-review** - Multi-agent documentation review

### Utilities
- **workflow-cleanup** - Clean accumulated workflow transcripts
- **ai-prompt** - Multi-model consensus for any question

## Installation

```bash
# Copy workflows and skills
cp -r workflows ~/.claude/
cp -r skills ~/.claude/
```

## Usage

All workflows available as `/skill-name` commands:

```bash
# Code Quality
/code-review              # Comprehensive 5-type code review
/code-solve loop          # Auto-resolve all open issues  
/code-test-review         # Analyze test quality
/code-hygiene-review      # Repository cleanup
/code-review-and-solve    # Full quality loop
/code-improve             # Iterative code quality improvement

# Documentation & PRs
/doc-review               # Multi-agent documentation review
/pr-review                # Continuous PR monitoring
/pr-verify                # Verify open PRs: build, test, quality

# Utilities
/ai-prompt                # Multi-model consensus for any question
/workflow-cleanup         # Clean workflow history
```

## Features

### Multi-AI Consensus
- **Workers**: Opus, Sonnet, Haiku review independently
- **Arbiters**: Rotating arbiters prevent single-model bias
- **Confidence Scoring**: Filter low-quality findings
- **Deduplication**: Remove duplicate issues

### Worktree Isolation
- **Parallel Safe**: Multiple workflows run simultaneously
- **No Conflicts**: Each fix in isolated git worktree
- **Auto Cleanup**: Temporary worktrees cleaned automatically

### Autonomous Operation
- **No Manual Approval**: Runs completely unattended
- **Auto-Create Issues**: Creates GitHub/GitLab issues
- **Auto-Create PRs**: Creates pull requests with fixes
- **Platform Agnostic**: Works with GitHub, GitLab, Bitbucket

## Code Review (5 Types)

### 1. Recent Commits (Last 30 days)
- Security vulnerabilities
- Logic bugs
- Performance issues
- Code quality
- Error handling gaps

### 2. Closed Issues
- Issues still broken
- Incomplete fixes
- Regressions

### 3. Full Codebase
- Comprehensive scan (up to 10 files)
- Security, logic, performance

### 4. Dependencies ⭐ NEW
- Security vulnerabilities (CVEs)
- Outdated packages
- Breaking changes
- npm, pip, maven, cargo, bundle support

### 5. Security Deep Dive ⭐ NEW
- Secrets in code/git history
- OWASP Top 10 vulnerabilities
- Exposed endpoints without auth
- CORS misconfigurations
- SQL injection, XSS, command injection

## Requirements

- Claude Code CLI
- Git (for GitHub/GitLab integration)
- `gh` CLI (for GitHub operations) OR
- `glab` CLI (for GitLab operations)

## Shared Modules

Reusable modules in `workflows/shared/`:
- **consensus-engine.js** - Multi-model consensus implementation
- **schemas.js** - JSON schemas for structured output
- **platform-detector.js** - Platform detection (GitHub/GitLab/Bitbucket)
- **ai-attribution.js** - AI model attribution formatting
- **quality-scorer.js** - Code quality scoring
- **loop-controller.js** - Continuous monitoring loops

## Cost Estimates (Approximate)

| Workflow | Agents | Cost/Run |
|----------|--------|----------|
| /code-review | ~60 | $15-25 |
| /code-solve (single) | ~5 | $2-4 |
| /code-solve loop (10) | ~50 | $20-30 |
| /code-test-review | ~30 | $10-15 |
| /code-hygiene-review | ~5 | $2-5 |
| /code-review-and-solve | ~70 | $40-50 |

## When to Run

- **Daily/Weekly**: `/code-review` - Continuous quality
- **On Demand**: `/code-solve` - Fix specific issues
- **Monthly**: `/code-test-review`, `/code-hygiene-review` - Maintenance
- **Pre-Release**: `/code-review-and-solve` - Complete cleanup

## Version

2.0.0 - 2026-06-04

**Changelog:**
- Added dependencies review to `/code-review`
- Added security deep dive to `/code-review`
- Added `/code-test-review` workflow
- Added `/code-hygiene-review` workflow
- Added `/code-review-and-solve` orchestrator

## Author

sfloess

## License

Internal Use - Red Hat
