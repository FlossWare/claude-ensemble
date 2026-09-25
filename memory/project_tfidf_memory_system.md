---
name: tfidf-memory-system
description: TF-IDF semantic memory cache system — lightweight, no ML models, integrated via session hooks
metadata:
  type: project
---

# TF-IDF Memory System (In Progress)

## Current Status

**Phase 1 Create:** Building TF-IDF indexer + cache loader + hook integration
- 4 workers (Haiku, Sonnet, Opus 4.8, Gemini)
- Target: `/tmp/cpsearch-10981-keyset-fixes` worktree
- Still in progress (launched 2026-09-25)

## Architecture

**Components:**
1. **TF-IDF Indexer** — Python script that reads all memory files, builds searchable index, outputs `~/.claude/cache/memory-index.json`
2. **Cache Loader** — Loads JSON at session start, provides `search(query, limit=5)` function
3. **Hook Integration** — Updates `~/.claude/hooks/ingest-prompt` to display top 3 matching memory files on every prompt
4. **Performance** — Benchmarking sub-10ms searches on 30 files

## Design Decisions

- **Why TF-IDF, not ML models?** Zero CPU overhead, no GPU, lightweight (1-2MB cache), milliseconds per search
- **Why not sentence-transformers?** Would require 300MB+ model download, 100-500ms per query, unnecessary for RH memory size
- **Cache format:** JSON with metadata + TF-IDF vectors, easy to debug and version-control
- **Hook integration:** Display top 3 matches on stderr with each prompt, leverage existing ingest-prompt hook

## Future: loom-ai Integration

**Decision (2026-09-25):** Do NOT share memory system separately. Integrate as core feature of loom-ai project instead.

**Why:** loom-ai will be the "real deal" — a complete AI system. Memory improvements should ship as part of that product, not standalone.

**Next steps:** Once TF-IDF system is verified (Phase 2 Create + Phase 1/2 Review complete), integrate into loom-ai architecture.

## Related Memories

- [[memory-first-decision-making]] — Rule that prompted this work
- [[parallel-phase-launches]] — How to organize creation/review phases
- [[mr-comments-all-phases]] — MR comment format for multi-phase work
