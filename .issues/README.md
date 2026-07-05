# Issues / Feature Requests

This directory contains feature requests and enhancement ideas for the project.

## Active Issues

### PDF Knowledge Base Enhancements

1. **[001-pdf-semantic-search-embeddings.md](001-pdf-semantic-search-embeddings.md)** - HIGH PRIORITY
   - Add vector embeddings for semantic search
   - Enable "find PDFs about X" by meaning, not keywords
   - Dependencies: None (pgvector already available)

2. **[002-connect-pdfs-to-workflows.md](002-connect-pdfs-to-workflows.md)** - MEDIUM PRIORITY
   - Track which PDFs workflows reference
   - Build knowledge provenance graph
   - Dependencies: Issue #001 recommended

3. **[003-link-pdfs-to-code-examples.md](003-link-pdfs-to-code-examples.md)** - LOW PRIORITY
   - Extract code snippets from PDFs
   - Create searchable code example library
   - Dependencies: None

4. **[004-personal-tech-library-assistant.md](004-personal-tech-library-assistant.md)** - HIGH PRIORITY
   - "What should I read about X?" recommendation engine
   - Learning path builder
   - Context-aware suggestions
   - Dependencies: Issues #001, #002

## Suggested Implementation Order

1. **Issue #001** (Semantic Search) - Foundation for others
2. **Issue #004** (Library Assistant) - High user value, depends on #001
3. **Issue #002** (Workflow Connections) - Improves recommendations
4. **Issue #003** (Code Examples) - Nice-to-have

## Current Status (2026-07-04)

- ✅ 243/849 PDFs processed into PostgreSQL
- ✅ Neo4j sync created (PDFDocument nodes with categories/topics)
- ✅ Parallel processing infrastructure (8 workers)
- ⏳ Processing still running (PID 1082296)
- ⏳ Neo4j backfill in progress

## How to Work on Issues

1. Pick an issue file
2. Review acceptance criteria
3. Implement features
4. Update issue status
5. Cross-reference related changes

## Adding New Issues

Create a new file: `.issues/XXX-short-title.md`

Template:
```markdown
# Title

**Status:** Open/In Progress/Done  
**Priority:** High/Medium/Low  
**Created:** YYYY-MM-DD  

## Goal
[What we want to achieve]

## Context
[Why this matters]

## Implementation
[How to build it]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
```
