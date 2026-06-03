---
name: doc-solve
description: This skill should be used when the user asks to "resolve doc issues", "fix documentation", "auto-fix doc problems", "solve documentation issues", or discusses automatically resolving documentation issues with multi-AI consensus.
version: 1.0.0
---

# Doc Solve - Autonomous Documentation Issue Resolution

Autonomously resolve documentation issues using multi-model AI consensus.

## Features

- **Multi-Model Fix Generation** - Multiple AIs propose doc fixes
- **Arbiter Selection** - Best fix chosen by consensus
- **Auto-PR Creation** - Creates pull request with fixes
- **Loop Mode** - Continuously resolves open doc issues
- **Platform Agnostic** - Works with GitHub, GitLab, Bitbucket

## Usage

```bash
# Resolve single doc issue
/doc-solve 123

# Resolve and create PR
/doc-solve 123 --create-pr

# Continuous issue resolution
/doc-solve loop
```

## Options

- `<issue_number>` - Issue number to resolve
- `loop` - Continuous monitoring mode
- `--create-pr` - Create pull request (default: true)
- `--consensus=MODE` - Consensus strategy
- `--workers=N` - Number of AI workers

## Loop Mode

Continuously resolves ALL open documentation issues:
- Checks every 10 minutes
- Prioritizes documentation over other labels
- Resolves multiple issues per iteration
- Stops when no doc issues remain

---

**Version**: 1.0  
**Created**: 2026-06-03
