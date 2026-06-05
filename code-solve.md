---
name: code-solve
description: Autonomous code issue resolution with multi-AI consensus (AUTONOMOUS)
tags: [autonomous, issues, fixes, consensus, multi-ai]
---

# Code Solve - Auto-Resolve GitHub/GitLab Issues 🔒

Autonomously resolve GitHub/GitLab issues using multi-model AI consensus.

**Version**: 1.1.2 (Security Hardened)  
**Status**: ✅ Production Ready  
**Security**: Hardened against shell injection attacks

## Features

- **Multi-Model Fix Generation** - Opus, Sonnet, Haiku generate solutions (rotated)
- **Arbiter Selection** - Best fix chosen by consensus (rotated by issue number)
- **Auto-PR Creation** - Creates pull request with fix
- **Loop Mode** - Continuously resolves open issues
- **Platform Agnostic** - Works with GitHub, GitLab, Bitbucket
- **Worktree Isolation** - Parallel-safe execution
- 🔒 **Security Hardened** - Input validation, shell injection prevention (2026-06-05)

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

1. **Validate Inputs** - Ensure issue ID is safe (positive integer 1-999999999)
2. **Fetch Issue** - Get issue details from GitHub/GitLab
3. **Generate Fixes** - 3 AI models propose solutions (workers rotated by issue #)
4. **Arbiter Decision** - Select best fix (arbiter rotated by issue #)
5. **Apply Fix** - In isolated worktree (parallel-safe)
6. **Create PR** - Generate pull request with fix
7. **Close Issue** - Links PR and closes #{issue_number}

## Security Features (v1.1.2)

### Protection Against Attacks

- ✅ **Shell Injection Prevention**
  - Issue IDs validated as positive integers (1-999999999)
  - Labels validated as alphanumeric + dash/underscore only
  - Shell variables properly quoted
  - JSON parsing with jq instead of grep
  
- ✅ **Input Validation**
  - Throws clear errors for missing/invalid data
  - Prevents undefined behavior
  - Range checks on all numeric inputs

- ✅ **Race Condition Mitigation**
  - Improved atomic claim operations
  - Better separation of check vs update
  - JSON-based state verification

### What Was Fixed (2026-06-05)

Critical vulnerabilities patched:
1. **RCE via issueId**: Now validates as safe integer
2. **RCE via label**: Now validates alphanumeric pattern
3. **Missing validation**: Clear error messages
4. **Race conditions**: Improved atomicity

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

- `~/.claude/repos/claude-global-skills/code-solve.js` (703 lines)
- `~/.claude/repos/claude-global-skills/code-solve.md` (this file)
- Symlinked to `~/.claude/skills/` for skill discovery

## Registration Requirements

For workflow to appear in skills list:
- ✅ `export const meta` must be FIRST statement (line 3-6, after comments)
- ✅ YAML frontmatter in .md file
- ✅ No `workflow()` calls in the script
- ✅ No ES6 imports (all functions inlined)

**Current status**: ✅ Properly registered, appears as `/code-solve`

---

**Version**: 1.1.2  
**Created**: 2026-06-03  
**Security Hardened**: 2026-06-05  
**Global**: Works on all projects  
**Production Ready**: Yes
