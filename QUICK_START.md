# SDLC Workflows - Quick Start Guide

**TL;DR**: Use `code-sdlc` for complete end-to-end automation.

## ⚡ FIRST: Setup Permissions (30 seconds)

**Before running any workflows**, enable autonomous execution:

```bash
~/.claude/workflows/fix-permissions.sh
```

This sets `dontAsk` mode - no permission prompts, ever.

**Then restart all Claude sessions.**

👉 **See [PERMISSIONS.md](PERMISSIONS.md)** for manual setup or details.

---

## The "Run Everything" Button

```bash
# Interactive (with approval gates)
claude run code-sdlc +500k

# Autonomous (zero interaction)
claude run code-sdlc-auto +800k
```

That's it! This runs all 7 SDLC phases from development through release.

## What Happens

```
Phase 1: Development (code-review + code-solve)
  ├─ Find bugs → Create issues → Fix issues
  └─ Time: ~8 min, Tokens: ~150k

Phase 2: Testing (code-test)
  ├─ Run comprehensive tests → Verify fixes
  └─ Time: ~5 min, Tokens: ~80k

Phase 3: PR Review (code-pr-review)
  ├─ Review open PRs → Approve/reject
  └─ Time: ~4 min, Tokens: ~100k

🚦 DECISION GATE (stops if breaking changes or critical issues)

Phase 4: Security (code-security)
  ├─ OWASP scan + secrets + dependencies
  └─ Time: ~6 min, Tokens: ~80k

Phase 5: Documentation (code-doc)
  ├─ Find undocumented code → Generate docs
  └─ Time: ~5 min, Tokens: ~80k

Phase 6: Release (code-release-notes)
  ├─ Generate changelog → Publish release
  └─ Time: ~3 min, Tokens: ~50k

Total: ~30 min, ~540k tokens
```

## When to Use What

### Use `code-sdlc` when:
- ✅ You want complete SDLC automation in one command
- ✅ You trust the AI but want approval gates at critical points
- ✅ You want a full pre-release checklist
- ✅ You're doing nightly automation with human review

### Use `code-sdlc-auto` when:
- ✅ You want zero-interaction automation
- ✅ You're running in CI/CD pipelines
- ✅ You want nightly autonomous runs
- ✅ You trust the decision gates

### Use individual workflows when:
- ✅ You only need one phase (e.g., just security audit)
- ✅ You're debugging a specific workflow
- ✅ You want finer control over each phase

## Individual Workflows

### Interactive (manual approval)

```bash
claude run code-review          # Find bugs
claude run code-solve           # Fix issues
claude run code-smoke-test      # Smoke tests (build + launch)
claude run code-test            # Comprehensive tests
claude run code-pr-review       # Review PRs
claude run code-security        # Security audit
claude run code-doc             # Generate docs
claude run code-release-notes        # Publish release
```

### Autonomous (auto-execute)

```bash
claude run code-review-auto     # Auto-create issues
claude run code-solve-auto      # Auto-fix issues
claude run code-test-auto       # Auto-create test issues
claude run code-pr-review-auto       # Auto-approve/reject PRs
claude run code-security-auto   # Auto-create security issues
claude run code-doc-auto        # Auto-generate docs
claude run code-release-notes-auto   # Auto-publish release
```

## Budget Guidelines

| Repo Size | Recommended Budget | What You Get |
|-----------|-------------------|--------------|
| Small (<1k files) | +300k-500k | All phases, moderate depth |
| Medium (1k-5k) | +500k-800k | All phases, full depth |
| Large (5k+) | +800k-1.5M | All phases, maximum thoroughness |

## Decision Gates (What Stops the Pipeline)

### Gate 1: After Development/Testing/PR
Stops if:
- 🛑 Breaking changes detected
- 🛑 Critical test failures
- 🛑 Budget <150k remaining

### Gate 2: Before Release
Stops if:
- 🛑 Critical security vulnerabilities
- 🛑 Breaking changes in any phase
- 🛑 Critical issues unresolved

## Common Use Cases

### 1. Nightly Automation
```bash
# Add to crontab
0 2 * * * cd ~/repo && claude run code-sdlc-auto +800k
```

### 2. Pre-Release Checklist
```bash
# Before releasing v2.0
claude run code-sdlc +500k
```

### 3. New Repo Onboarding
```bash
# Just inherited a codebase
claude run code-sdlc-auto +1M
```

### 4. Weekly Health Check
```bash
# Every Monday
claude run code-sdlc +300k
```

## Tips

1. **Start interactive** - First run should be `code-sdlc` (with approval gates)
2. **Right-size budget** - Small repos: 300k, Medium: 600k, Large: 1M
3. **Monitor first run** - Use `/workflows` in another terminal to watch
4. **Review critical issues** - Always check security and breaking changes
5. **Go autonomous gradually** - Once you trust it, use `code-sdlc-auto`

## Troubleshooting

### Pipeline stops at gate?
**Reason**: Breaking changes or critical issues found.
**Fix**: Review and fix manually, then re-run.

### Budget exhausted?
**Reason**: Token budget too low for repo size.
**Fix**: Increase budget (`+1M` instead of `+500k`).

### Phase skipped?
**Reason**: Insufficient budget remaining for that phase.
**Fix**: Start with higher budget.

## Full Documentation

- **CODE_SDLC_COMPLETE.md** - Complete documentation for code-sdlc
- **SDLC_WORKFLOWS_COMPLETE.md** - Documentation for all 16 workflows
- **NEW_SDLC_WORKFLOWS.md** - Implementation notes

## Summary

**One command for complete SDLC automation:**

```bash
claude run code-sdlc +500k
```

That's all you need! 🚀
