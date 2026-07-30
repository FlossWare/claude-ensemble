---
name: accountability-paper-trail
description: Every decision must have Model|API|Recommendation traceability, triple-stored in DECISIONS.md + PostgreSQL/pgvector + OrientDB
metadata:
  type: feedback
---

Every decision must have a full accountability paper trail. No exceptions.

**Why:** User said "I want 100% accountability and a good paper trail" and "I also want us to ingest this (queueing, embedding, chunking, etc)" and "we need to be able to look this up fast! when we interact I want your knowledge to increase."

**How to apply:**

1. **DECISIONS.md** — Every AI-reviewed decision gets a `Model | API | Recommendation` table with one row per model consulted. User-only decisions still get logged but marked "User decision (no AI review needed)."

2. **PostgreSQL + pgvector** — Every decision stored via `POST /learning/memory` at aio-01:5000. Full text chunked for semantic search. Embeddings auto-generated (768-dim).

3. **OrientDB** — Decision graph relationships stored for cross-referencing (which decisions relate to which repos, which models agreed/disagreed).

4. **Semantic retrieval** — Must be searchable by meaning, not just keywords. Test with queries like "what naming convention" or "which repos need BATS" after storing.

**Triple-store requirement:** DECISIONS.md + PostgreSQL/pgvector + OrientDB. All three, every time.

**Related:** [[flossware-naming-convention]], [[knowledge-not-learning]]
