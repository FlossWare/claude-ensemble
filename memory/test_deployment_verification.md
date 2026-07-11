---
name: test-deployment-verification
description: "Test file to verify fixed autostorage is actually running and processing files"
type: test
date: 2026-07-10
---

# Deployment Verification Test

Created at 18:19 to verify the fixed autostorage (v2) is running and processing new memory files.

Expected behavior:
1. Autostorage detects this file within 10 seconds
2. Parses frontmatter
3. Calls POST /learning/memory
4. Generates embedding via 5-provider cascade
5. Stores in PostgreSQL with pgvector
6. Creates OrientDB graph vertex

This file should appear in the database within 30 seconds.
