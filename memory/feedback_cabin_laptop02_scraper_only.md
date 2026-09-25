---
name: cabin-laptop02-scraper-only
description: cabin-laptop-02 is primarily for scraping; lightweight API-call workloads (GA experiments) are OK but avoid CPU-heavy compute (sentence-transformers)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6f87bc58-4f10-47f9-9498-5f2acdf19130
  modified: 2026-08-03T21:29:47.995Z
---

cabin-laptop-02 (aka laptop-02, 16C/62GB) is primarily a scraper node but can also run GA experiments and routing tests since those are lightweight API calls.

**What's OK:** GA experiments, routing experiments, API-call-based workloads (low CPU)
**What's NOT OK:** CPU-heavy compute like sentence-transformers, local model inference, fine-tuning — these caused the overheating (load 16.26 on 16C)

**Why updated:** User identified sentence-transformers (embedding inference) as the actual culprit for thermal issues, not GA experiments. GA experiments are just HTTP requests to external APIs.

**How to apply:** cabin-laptop-02 is available for GA/routing experiments alongside cabin-laptop-01. Still skip it for CPU-heavy workloads (embeddings, model inference, training).
