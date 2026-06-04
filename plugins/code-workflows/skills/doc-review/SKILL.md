---
name: doc-review
description: This skill should be used when the user asks to "review documentation", "check docs", "documentation review", "find doc issues", or discusses analyzing documentation quality with multiple AI models.
version: 1.0.0
---

# Doc Review - Multi-AI Documentation Review

Multi-agent documentation review with issue creation.

## Features

- **Multi-Model Review** - Multiple AIs review documentation
- **Issue Creation** - Creates GitHub/GitLab issues for problems found
- **Read-Only Mode** - Can report without creating issues
- **Comprehensive** - Checks accuracy, clarity, completeness, examples

## Usage

```bash
/doc-review [PATH] [OPTIONS]
```

## Options

- `PATH` - Target directory or file (default: current directory)
- `--create-issues` - Create GitHub/GitLab issues (default: false)
- `--workers=N` - Number of AI reviewers (default: 3)

## What It Reviews

- Accuracy - Technical correctness
- Clarity - Readability and understanding
- Completeness - Missing information
- Examples - Code examples quality
- Structure - Organization and flow

---

**Version**: 1.0  
**Created**: 2026-06-03
