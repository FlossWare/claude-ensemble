# code-review

**Interactive code review workflow** - finds issues via multi-AI consensus with impact analysis, prompts before creating issues.

## Usage

```bash
# Review entire codebase
claude run code-review

# Review specific directory
claude run code-review src/

# Review specific file
claude run code-review src/components/App.tsx
```

## What It Does

1. **Sync** - Syncs with remote repository (git fetch + rebase)
2. **Find Files** - Identifies files to review (supports directories and individual files)
3. **Multi-AI Review** - Parallel reviews across opus/sonnet/haiku workers
4. **Consensus** - Arbiter validates issues and rejects false positives
5. **Impact Analysis** - Analyzes breaking changes and affected areas
6. **User Confirmation** - Prompts before creating issues (YES/SELECTIVE/NO)

## Output

- Creates GitHub/GitLab issues for validated findings
- Issues include: severity, category, file/line, cross-reference count
- Labels: `code-review`, severity level, category

## Autonomous Mode

For fully automated code review without prompts:

```bash
claude run code-review-auto
```

## Integration

Called by `code-sdlc` workflow as Phase 1 (Development).

## Related

- **code-review-auto** - Autonomous version (auto-creates all issues)
- **code-solve** - Fix issues created by code-review
- **code-sdlc** - Complete SDLC pipeline including review
