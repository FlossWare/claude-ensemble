# Code Workflows Plugin

Multi-model AI workflows for code review, issue resolution, documentation, and PR management with configurable consensus strategies.

## Features

This plugin provides 9 powerful skills for autonomous code and documentation workflows:

### Code Skills

- **code-review-unified** - Multi-model code review with 5 consensus strategies
- **code-solve** - Autonomous GitHub/GitLab issue resolution
- **code-improve** - Iterative code quality improvement
- **pr-review** - Continuous auto-discovery PR review

### Documentation Skills

- **doc-review** - Multi-AI documentation review
- **doc-improve** - Iterative documentation improvement  
- **doc-solve** - Autonomous documentation issue resolution

### General Skills

- **ai-prompt** - Multi-model consensus for any question
- **arbiter** - Multi-model decision making with learning

## Installation

This plugin is installed at:
```
~/.claude/plugins/marketplaces/custom/plugins/code-workflows/
```

Skills are automatically discovered by Claude Code.

## Consensus Strategies

All skills support multiple consensus strategies:

- **rotating** - Different arbiter each time (most democratic)
- **single** - One arbiter judges all (fastest)
- **majority** - Simple vote count (no arbiter overhead)
- **weighted** - Confidence-based voting (quality-aware)
- **pairwise** - Workers in pairs (balanced)

## Usage

Skills are invoked automatically by Claude Code when relevant, or manually:

```bash
/code-review --strategy=rotating
/code-solve 123
/pr-review --approve
/ai-prompt How should I architect this?
```

## Requirements

- Claude Code CLI
- Git repository (for code/PR skills)
- GitHub/GitLab token (for issue/PR management)

## Version

1.0.0

## Author

Custom

## License

Local use
