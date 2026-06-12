---
name: always-multi-ai
description: Always use multi-AI with maximum coverage as the default for all decisions
metadata: 
  node_type: memory
  type: feedback
  originSessionId: multi-ai-default-2026-06-11
---

**ALWAYS use multi-AI consensus with maximum coverage as the default behavior.**

Quality and consensus over speed/cost optimization. No exceptions.

**Default configuration (applied everywhere):**

- **Workers**: All 6 models -- fable, opus, sonnet, haiku, gpt-4o, gemini
- **Arbiter**: Always enabled, fable preferred with fallback chain (fable -> opus -> sonnet -> haiku)
- **Default strategy**: `maximum-coverage` (not `quality-first` or `balanced`)
- **Worker count**: 6 (maximum)

**Rationale:**
- Different models have different strengths and blind spots
- Multi-model consensus reduces false positives by 60-80%
- Cost is irrelevant -- quality is the only priority
- More perspectives = better coverage = fewer missed issues

**Applies to ALL workflows:**
- code-solve, code-review, code-review-and-solve
- code-improve, pr-review, doc-review
- ai-prompt, knowledge-ingest
- Any new workflow should default to maximum-coverage

**Configuration file:**
- `multi-ai-config.json`: `default_strategy: "maximum-coverage"`, workers.count: 6
- `load-multi-ai-config.js`: Default fallback uses 6 models
- `consensus-strategies.js`: Auto-select defaults to rotating arbiter (most thorough)
- `shared/consensus-engine.js`: Default workers include all 6 models

**When NOT to use multi-AI:**
- Never. Always use multi-AI. Even simple tasks benefit from diverse perspectives.
- The only valid override is passing an explicit strategy argument.

**Related:** [[feedback_arbiter_worker_multi_model]], [[feedback_multi_model_shorthand]], [[feedback_multi_model_strategy]]
