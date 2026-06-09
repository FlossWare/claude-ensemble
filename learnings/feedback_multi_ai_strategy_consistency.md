---
name: multi-ai-strategy-consistency
description: All new arbiter/worker-AI workflows must support the 5 consensus and 5 execution strategies
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c675ffde-ae08-47ca-8485-84ad6f9fe3e7
---

All new global workflows that use the arbiter/worker-AI pattern must support the same strategy options as existing multi-AI features.

**Why:** Consistency across the Universal AI platform. Users expect to have the same 25 strategy combinations (5 consensus × 5 execution) available for any multi-AI workflow, whether it's code-solve, pr-review, or any new feature.

**How to apply:** When implementing any new workflow or skill that uses multiple AIs in an arbiter/worker pattern:

1. Add `--consensus` flag with options: rotating, single, majority, pairwise, weighted
2. Add `--execution` flag with options: parallel, sequential, batched, cascade, weighted-parallel
3. Default to `--consensus=rotating --execution=parallel` (same as existing workflows)
4. Ensure all 25 combinations work correctly
5. Document the strategies in the skill's help text

Related: [[project_universal_ai_capabilities]] for the complete strategy definitions
