---
name: expert-feedback-python-expert-use-asynciogather-instead-of-sequential
description: Use asyncio.gather() instead of sequential await calls for concurrent operations
metadata:
  type: feedback
  expert: python-expert
  timestamp: 2026-06-03T09:27:33.852685
---

# Expert Feedback: Python Expert

Use asyncio.gather() instead of sequential await calls for concurrent operations

**Why:** Performance optimization for I/O-bound tasks

**How to apply:** When you have multiple independent async operations, use gather() to run them concurrently
