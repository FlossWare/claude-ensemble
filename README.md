# Claude Global Skills and Workflows

Global skills and workflows for Claude Code, shareable across all projects.

## Contents

### Skills (`skills/`)

Global skills that can be invoked from any project:

- **ai-prompt** - Multi-model consensus for any question
- **arbiter** - Multi-model decision making with learning
- **code-improve** - Iterative code quality improvement
- **code-review-unified** - Unified multi-model review with 5 consensus strategies
- **code-solve** - Auto-resolve GitHub/GitLab issues (commits directly, closes with hash reference)
- **doc-improve** - Iterative documentation improvement
- **doc-review** - Multi-AI documentation review
- **doc-solve** - Autonomous documentation issue resolution
- **pr-review** - Continuous auto-discovery PR review

### Workflows (`workflows/`)

Self-contained workflow implementations:

- **ai-prompt.js** - Multi-model consensus workflow
- **code-improve.js** - Iterative improvement workflow
- **code-review.js** - Brutal comprehensive review (commits, closed issues, full codebase)
- **code-solve.js** - Issue resolution workflow (self-contained, commits directly)
- **pr-review.js** - PR review workflow
- **pr-verify.js** - PR verification workflow
- **doc-review.js** - Documentation review workflow

### Shared Modules (`workflows/shared/`)

Reusable modules for workflows (used by registered workflows):

- **consensus-engine.js** - Multi-model consensus implementation
- **schemas.js** - JSON schemas for structured output
- **platform-detector.js** - Platform detection (GitHub/GitLab/Bitbucket)
- **ai-attribution.js** - AI model attribution formatting
- **quality-scorer.js** - Code quality scoring
- **loop-controller.js** - Continuous monitoring loops

### Plugins (`plugins/code-workflows/`)

Claude Code plugin structure with SKILL.md files:

- Plugin definition and skill documentation
- Custom plugin marketplace structure

### Documentation (`docs/`)

User guides and workflow documentation:

- **AUTONOMOUS_WORKFLOW_GUIDE.md** - Autonomous workflow patterns
- **AUTO_RESOLVE_MODE.md** - Auto-resolve mode documentation
- **CONTINUOUS_REVIEW_GUIDE.md** - Continuous review setup
- **PR_VERIFY_GUIDE.md** - PR verification guide

### Templates (`templates/`)

Reusable template files for common configurations

### Learnings (`learnings/`)

Critical lessons learned about Claude Code:

- **claude-code-workflows.md** - Workflow registration and discovery
- **workflow-imports-lesson.md** - Import handling and scriptPath vs named invocation

## Installation

### Copy to Claude Code Global Directory

```bash
# Copy skills
cp -r skills/* ~/.claude/skills/

# Copy workflows
cp -r workflows/* ~/.claude/workflows/
```

### Or Symlink

```bash
# Symlink skills
ln -s $(pwd)/skills ~/.claude/skills

# Symlink workflows
ln -s $(pwd)/workflows ~/.claude/workflows
```

## Usage

Skills are available globally after installation:

```bash
# Code review with rotating consensus
/code-review --strategy=rotating

# Solve an issue
/code-solve 123

# Review PR
/pr-review 42

# Get multi-model consensus
/ai-prompt How should I architect this?
```

## Consensus Strategies

All skills support multiple consensus strategies:

- **rotating** - Different arbiter each time (most democratic, recommended)
- **single** - One arbiter judges all (fastest)
- **majority** - Simple vote count (no arbiter overhead)
- **weighted** - Confidence-based voting (quality-aware)
- **pairwise** - Workers in pairs (balanced)

## Requirements

- Claude Code CLI
- Git (for GitHub/GitLab integration)
- `gh` CLI (for GitHub operations)
- GitLab token (for GitLab operations)

## Key Learnings

### Workflow Structure

- Self-contained workflows (no imports) work via scriptPath
- Registered workflows can use imports from `shared/`
- Always put `export const meta` first for scriptPath workflows

### Testing Workflows

Named invocation:
```javascript
Workflow({name: "code-solve"})  // If registered
```

scriptPath invocation:
```javascript
Workflow({scriptPath: "/path/to/workflow.js"})  // Always works if self-contained
```

## Version

1.0.0 - 2026-06-03

## Author

sfloess

## License

Internal Use
<<<<<<< HEAD
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
=======
# Claude Global Skills and Workflows

Global skills and workflows for Claude Code, shareable across all projects.

## Contents

### Skills (`skills/`)

Global skills that can be invoked from any project:

- **ai-prompt** - Multi-model consensus for any question
- **arbiter** - Multi-model decision making with learning
- **code-improve** - Iterative code quality improvement
- **code-review-unified** - Unified multi-model review with 5 consensus strategies
- **code-solve** - Auto-resolve GitHub/GitLab issues (commits directly, closes with hash reference)
- **doc-improve** - Iterative documentation improvement
- **doc-review** - Multi-AI documentation review
- **doc-solve** - Autonomous documentation issue resolution
- **pr-review** - Continuous auto-discovery PR review

### Workflows (`workflows/`)

Self-contained workflow implementations:

- **ai-prompt.js** - Multi-model consensus workflow
- **code-improve.js** - Iterative improvement workflow
- **code-review.js** - Brutal comprehensive review (commits, closed issues, full codebase)
- **code-solve.js** - Issue resolution workflow (self-contained, commits directly)
- **pr-review.js** - PR review workflow
- **pr-verify.js** - PR verification workflow
- **doc-review.js** - Documentation review workflow

### Shared Modules (`workflows/shared/`)

Reusable modules for workflows (used by registered workflows):

- **consensus-engine.js** - Multi-model consensus implementation
- **schemas.js** - JSON schemas for structured output
- **platform-detector.js** - Platform detection (GitHub/GitLab/Bitbucket)
- **ai-attribution.js** - AI model attribution formatting
- **quality-scorer.js** - Code quality scoring
- **loop-controller.js** - Continuous monitoring loops

### Plugins (`plugins/code-workflows/`)

Claude Code plugin structure with SKILL.md files:

- Plugin definition and skill documentation
- Custom plugin marketplace structure

### Documentation (`docs/`)

User guides and workflow documentation:

- **AUTONOMOUS_WORKFLOW_GUIDE.md** - Autonomous workflow patterns
- **AUTO_RESOLVE_MODE.md** - Auto-resolve mode documentation
- **CONTINUOUS_REVIEW_GUIDE.md** - Continuous review setup
- **PR_VERIFY_GUIDE.md** - PR verification guide

### Templates (`templates/`)

Reusable template files for common configurations

### Learnings (`learnings/`)

Critical lessons learned about Claude Code:

- **claude-code-workflows.md** - Workflow registration and discovery
- **workflow-imports-lesson.md** - Import handling and scriptPath vs named invocation

## Installation

### Copy to Claude Code Global Directory

```bash
# Copy skills
cp -r skills/* ~/.claude/skills/

# Copy workflows
cp -r workflows/* ~/.claude/workflows/
```

### Or Symlink

```bash
# Symlink skills
ln -s $(pwd)/skills ~/.claude/skills

# Symlink workflows
ln -s $(pwd)/workflows ~/.claude/workflows
>>>>>>> c3de3f80dfd7dfd5aad9a220e10fe975e4386b2c
```

## Usage

<<<<<<< HEAD
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
=======
Skills are available globally after installation:

```bash
# Code review with rotating consensus
/code-review --strategy=rotating

# Solve an issue
/code-solve 123

# Review PR
/pr-review 42

# Get multi-model consensus
/ai-prompt How should I architect this?
```

## Consensus Strategies

All skills support multiple consensus strategies:

- **rotating** - Different arbiter each time (most democratic, recommended)
- **single** - One arbiter judges all (fastest)
- **majority** - Simple vote count (no arbiter overhead)
- **weighted** - Confidence-based voting (quality-aware)
- **pairwise** - Workers in pairs (balanced)

## Requirements

- Claude Code CLI
- Git (for GitHub/GitLab integration)
- `gh` CLI (for GitHub operations)
- GitLab token (for GitLab operations)

## Key Learnings

### Workflow Structure

- Self-contained workflows (no imports) work via scriptPath
- Registered workflows can use imports from `shared/`
- Always put `export const meta` first for scriptPath workflows

### Testing Workflows

Named invocation:
```javascript
Workflow({name: "code-solve"})  // If registered
```

scriptPath invocation:
```javascript
Workflow({scriptPath: "/path/to/workflow.js"})  // Always works if self-contained
```

## Version

1.0.0 - 2026-06-03

## Author

sfloess

## License

Internal Use
>>>>>>> c3de3f80dfd7dfd5aad9a220e10fe975e4386b2c
