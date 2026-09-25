---
name: headroom-redhat-critical
description: "Headroom token compression is critical for Red Hat approved models where tokens cost real money (Vertex Claude, Cursor, Gemini API)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 83d636b4-6ac1-4a35-8e16-504fa9dc050d
  modified: 2026-08-05T13:51:50.099Z
---

Token compression (Headroom) evaluation differs completely between personal and Red Hat contexts.

- **Personal (free models):** Value is context window fitting + speed. Cost savings = $0.
- **Red Hat (Vertex Claude, Cursor, Gemini API):** Value is ALL THREE — context, speed, AND direct cost savings. Every compressed token = real money saved.

Features that scored "contested" or "maybe" for free models become **critical** for Red Hat:
- CCR (reversible compression): preserves fidelity while cutting costs
- Output reduction: directly reduces billing on metered APIs
- Kompress-v2-base: text compression saves on large prompts
- CacheAligner: KV cache hits reduce recomputation costs on Vertex

**Why:** User corrected the free-model-only framing — "for Red Hat approved models, this is extremely needed"

**How to apply:** When evaluating tools/libraries for the orchestration system, always score separately for Red Hat (paid/metered) vs personal (free) contexts. [[reference_model_classification_redhat_vs_personal]] [[reference_redhat_ai_compliance]]
