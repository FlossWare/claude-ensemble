---
name: code-solve
description: Autonomous code issue resolution with multi-AI consensus (AUTONOMOUS)
tags: [autonomous, issues, fixes, consensus, multi-ai]
---

# Code Solve - Auto-Resolve GitHub/GitLab Issues

Autonomously resolve GitHub/GitLab issues using multi-model AI consensus.

## Features

- **Multi-Model Fix Generation** - Opus, Sonnet, Haiku generate solutions
- **Arbiter Selection** - Best fix chosen by consensus
- **Auto-PR Creation** - Creates pull request with fix
- **Loop Mode** - Continuously resolves open issues
- **Platform Agnostic** - Works with GitHub, GitLab, Bitbucket
- **Review-Only by Default** - Creates PRs, doesn't push to main

## Usage

```bash
# Resolve single issue
/code-solve 326

# Resolve and create PR
/code-solve 326 --create-pr

# Continuous issue resolution
/code-solve loop
```

## Options

- `<issue_number>` - Issue number to resolve
- `loop` - Continuous monitoring mode
- `--create-pr` - Create pull request (default: true)
- `--apply` - Apply fix directly (default: false)

## Workflow

1. **Fetch Issue** - Get issue details
2. **Generate Fixes** - 3 AI models propose solutions
3. **Arbiter Decision** - Select best fix
4. **Create PR** - Generate pull request with fix
5. **Link Issue** - Closes #{issue_number}

## Loop Mode

```bash
/code-solve loop
```

Continuously resolves ALL open issues:
- Checks every 10 minutes
- Prioritizes bugs over enhancements
- Resolves up to 3 issues per iteration
- Stops when no issues remain

## Example

```bash
$ /code-solve 326

Fetching issue #326...
  ✓ "Command injection in virtos-database"

Generating fixes...
  ✓ Opus: Add hostname validation
  ✓ Sonnet: Use parameterized queries
  ✓ Haiku: Sanitize input

Arbiter decision:
  ✓ Selected: Opus (95% consensus)
  
Creating PR...
  ✓ Branch: fix/issue-326
  ✓ PR: https://github.com/.../pull/330
  
✅ Issue #326 resolved!
```

## Files

- `~/.claude/workflows/code-solve.js`
- `~/.claude/skills/code-solve.md`
- `~/.claude/workflows/shared/` (uses all modules)

---

**Version**: 1.0  
**Created**: 2026-06-03  
**Global**: Works on all projects
