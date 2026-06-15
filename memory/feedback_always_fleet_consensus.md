---
name: always-fleet-consensus
description: Always get fleet (multi-AI) approval or consensus before making decisions
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

**ALWAYS get fleet approval or consensus before making decisions.**

Never make architectural decisions, implementation choices, or significant changes with a single AI model. Always use multi-AI consensus (the fleet) to validate approaches.

**How:** [[feedback_always_multi_ai]]
- Use multi-AI consensus with all 6 models (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)
- Get independent perspectives, challenge assumptions
- Synthesize consensus ranking/recommendation

**When to apply:**
- Architecture decisions
- Implementation approach choices
- Technology selection
- Design tradeoffs
- Production deployments
- Any non-trivial decision

**Example:** Session orchestration decision - ran through multi-AI consensus, got unanimous recommendation for Git LFS Locks over custom infrastructure.

**Why:**
- Single model has blind spots
- Multi-model consensus catches hidden risks
- Diverse perspectives = better decisions
- Reduces regret/rework

**Related:** [[feedback_always_multi_ai]], [[feedback_multi_model_arbiter_workers]]
