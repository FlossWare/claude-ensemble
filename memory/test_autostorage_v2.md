---
name: test-autostorage-v2
description: "Test file to verify fixed autostorage with complete pipeline"
type: test
tags: pipeline,verification
project: claude-global-skills
---

# Autostorage V2 Test Memory

This test verifies the complete pipeline works:

1. **Chunking** - If >1500 chars, use SemanticChunker
2. **Embedding** - 5-provider cascade (VoyageAI → Jina → Cohere → Google → Local)
3. **Vector** - Store in learning.memory with pgvector
4. **Graph** - Create OrientDB vertices and edges

## Security Fixes Verified

All 6 critical/high issues fixed:
- SQL injection prevention (sanitize_sql_value)
- Integer validation (validate_memory_id)
- Path traversal protection (symlink detection)
- Race condition handling (FileNotFoundError)
- JSON decode errors (JSONDecodeError)
- Embedding status logic (proper None handling)

## Expected Results

- ✅ Memory stored in PostgreSQL learning.memory table
- ✅ Embedding generated (has_embedding: true)
- ✅ Vector search works (384-dim)
- ✅ OrientDB vertex created
- ✅ Graph relationships established
