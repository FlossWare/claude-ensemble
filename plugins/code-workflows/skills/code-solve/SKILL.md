---
name: code-solve
description: This skill should be used when the user asks to "resolve issues", "auto-fix bugs", "solve GitHub issues", "fix GitLab issues", "autonomous issue resolution", or discusses automatically resolving code issues with multi-AI consensus.
version: 1.0.0
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
- `--consensus=MODE` - Consensus strategy (rotating/single/majority/pairwise/weighted)
- `--execution=MODE` - Execution strategy (parallel/sequential/batched/cascade)
- `--workers=N` - Number of AI workers (default: 6)
- `--comment-ai` - Show AI attribution in comments

## Workflow

1. **Fetch Issue** - Get issue details
2. **Generate Fixes** - 3+ AI models propose solutions
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

## Consensus Strategies

- **rotating** - Democratic, different arbiter each time (default, most thorough)
- **single** - One arbiter judges all (fast)
- **majority** - Simple majority vote (no arbiter overhead)
- **pairwise** - Workers in pairs (balanced)
- **weighted** - Confidence-based voting (quality-aware)

## Execution Strategies

- **parallel** - All workers simultaneously (fastest, default)
- **sequential** - One at a time (resource-friendly)
- **batched** - Process in batches (balanced)
- **cascade** - Fast workers first, escalate if needed (adaptive, recommended)
- **weighted-parallel** - Priority-based parallel (smart)

## Files

- `~/.claude/workflows/code-solve.js`
- `~/.claude/skills/code-solve.md`
- `~/.claude/workflows/shared/` (uses all modules)

---

**Version**: 1.0  
**Created**: 2026-06-03  
**Global**: Works on all projects
