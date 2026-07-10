---
name: test-pipeline-verification
description: "Test memory to verify complete pipeline: chunk → embed → vector → graph"
metadata:
  type: test
  date: 2026-07-10
  purpose: pipeline-verification
---

# Pipeline Verification Test Memory

This is a test memory file created to verify the complete autostorage pipeline works correctly.

## What Should Happen

When autostorage processes this file, it should:

1. **Detect the file** in the memory directory
2. **Parse frontmatter** (type: test, name: test-pipeline-verification)
3. **Call REST API** POST http://aio-01:5000/learning/memory
4. **Generate embedding** using 5-provider cascade (VoyageAI → Jina → Cohere → Google → Local)
5. **Store in PostgreSQL** learning.memory table with pgvector
6. **Create graph node** in OrientDB (if endpoint exists)

## Expected Results

- ✅ Record appears in PostgreSQL with has_embedding: true
- ✅ Semantic search finds this memory
- ✅ Graph relationships created (if applicable)
- ✅ Processed file hash saved to prevent re-processing

## Why This Test Matters

The user explicitly stated: "any memory needs to do: postgres, chunk, embed, vector, graph"

This test verifies ALL five components work together end-to-end.
