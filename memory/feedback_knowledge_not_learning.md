---
name: knowledge-not-learning
description: "System stores knowledge for retrieval — it does NOT learn or train models. Knowledge != learning."
metadata:
  type: feedback
---

Knowledge != learning. The system stores knowledge for fast retrieval, it does NOT learn or train models.

**Why:** User explicitly corrected: "knowledge != learning." When I said "I want your knowledge to increase," the user clarified this means storing and retrieving facts/decisions/context — NOT model training, weight updates, or self-improvement.

**How to apply:**
- Say "knowledge store" or "knowledge base" — never "learning system" or "self-improving"
- PostgreSQL + pgvector + OrientDB = knowledge store for semantic retrieval
- Embeddings enable fast lookup by meaning — this is search infrastructure, not training data
- When storing decisions/facts, frame it as "increasing available knowledge" not "learning from experience"
- The system's value is in retrieval speed and completeness, not in model capability changes

**Related:** [[accountability-paper-trail]]
