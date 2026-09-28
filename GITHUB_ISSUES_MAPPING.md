# GitHub Issues Mapping: RH → Claude Ensemble

GitHub issue titles use old `rh-pr-review` naming, but the **generic codebase** uses `code-pr-review`.

This document clarifies the mapping for future workers.

## Issue Renaming Reference

| GitHub Issue # | Old Title (GitHub) | Generic Intent | Notes |
|---|---|---|---|
| #3 | Automate rh-pr-review: Convert to MCP service | **Autonomous Code Review MCP Service** | Review any artifact (code, docs, design), not just PRs |
| #4 | Build Code Search MCP service | Code Search Service | ripgrep wrapper, finds patterns |
| #5 | Build Git History MCP service | Git History Service | git blame, log, commit context |
| #6 | Build Documentation MCP service | Doc Search Service | markdown/spec retrieval |
| #7 | Build Knowledge Base MCP service | Knowledge Base Service | JSONL learnings storage |
| #8 | Build Build/CI MCP service | CI Context Service | test results, build logs |

## Code Artifact Names (Post-Genericization)

These are the **current names** in the codebase (not RH-specific):

- **Skill files:** `code-pr-review.js`, `code-pr-review-auto.js`, `code-doc.js`, `code-doc-auto.js`, `code-release-notes.js`
- **Config:** `toolkit-models.yaml` (not `rh-toolkit-models.yaml`)
- **Services:** `claude-memory`, `claude-thompson`, `claude-learning`, `claude-alert` (not `rh-*`)
- **Sockets:** `/tmp/claude-*.sock` (not `/tmp/rh-*.sock`)

## When Working on These Issues

1. **Refer to generic names** in your code and documentation
   - ✅ "code-pr-review" or "autonomous code review"
   - ❌ "rh-pr-review"

2. **These are NOT Red Hat-specific**
   - They should work for any codebase
   - Optional: Red Hat-specific adapters can exist separately
   - But the core tool is generic

3. **Use generic terminology**
   - "code review" or "artifact review" (not just PR review)
   - "toolkit" or "ensemble" (not "rh-toolkit")
   - "Claude services" (not "RH services")

4. **Reference this document** if GitHub issue titles are confusing

## Why This Matters

The toolkit is now **public on GitHub** and should be usable by anyone, not just Red Hat employees. The issue titles are historical artifacts that can't be changed from the repo, but the actual implementation must be generic.

