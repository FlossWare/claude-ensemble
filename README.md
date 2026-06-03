# Claude Global Skills and Workflows

Global skills and workflows for Claude Code, shareable across all projects.

## Contents

### Skills (`skills/`)

Global skills that can be invoked from any project:

- **ai-prompt** - Multi-model consensus for any question
- **arbiter** - Multi-model decision making with learning
- **code-improve** - Iterative code quality improvement
- **code-review-unified** - Unified multi-model review with 5 consensus strategies
- **code-solve** - Auto-resolve GitHub/GitLab issues
- **doc-improve** - Iterative documentation improvement
- **doc-review** - Multi-AI documentation review
- **doc-solve** - Autonomous documentation issue resolution
- **pr-review** - Continuous auto-discovery PR review

### Workflows (`workflows/`)

Self-contained workflow implementations:

- **ai-prompt.js** - Multi-model consensus workflow
- **code-improve.js** - Iterative improvement workflow
- **code-review.js** - Code review with consensus
- **code-solve.js** - Issue resolution workflow (working, self-contained)
- **pr-review.js** - PR review workflow
- **pr-verify.js** - PR verification workflow
- **doc-review.js** - Documentation review workflow

### Shared Modules (`workflows/shared/`)

Reusable modules for workflows:

- **consensus-engine.js** - Multi-model consensus implementation
- **schemas.js** - JSON schemas for structured output
- **platform-detector.js** - Platform detection (GitHub/GitLab/Bitbucket)
- **ai-attribution.js** - AI model attribution formatting
- **quality-scorer.js** - Code quality scoring
- **loop-controller.js** - Continuous monitoring loops

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
