---
name: multi-model-arbiter-workers
description: "Multi-AI consensus pattern using arbiter to orchestrate workers, synthesize results, and make decisions"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 182b6e77-c86f-414b-bd2a-462aaf609ee7
---

Multi-model arbiter/worker pattern achieves better results than single-model approaches by using multiple AI perspectives with synthesis.

**Why:** User successfully resolved 100 GitHub issues in 2h53m using multi-AI consensus (2026-06-05). Pattern provides diverse perspectives, catches errors one model would miss, and produces higher-quality outputs.

**How to apply:**

**Pattern structure:**
1. **Arbiter** (orchestrator) - coordinates workers, synthesizes results, makes final decisions
2. **Workers** (diverse models) - each provides independent perspective on same task
3. **Synthesis** - arbiter combines worker outputs, resolves conflicts, produces final result

**Worker diversity strategies:**
- Different models (Claude, GPT-4, Gemini, etc.)
- Different prompts (optimistic vs pessimistic, security-focused vs performance-focused)
- Different contexts (with/without certain information)
- Different reasoning approaches (step-by-step vs intuitive)

**When to use:**
- Code review (security, performance, correctness workers)
- Issue resolution (multiple solution approaches)
- Decision making (diverse perspectives needed)
- Quality verification (multiple validators)
- Research (multiple search strategies)

**Implementation patterns:**

**Parallel workers (concurrent):**
```javascript
const results = await parallel(
  workers.map(w => () => agent(w.prompt, {schema: OUTPUT_SCHEMA}))
);
const synthesis = arbiter.synthesize(results.filter(Boolean));
```

**Sequential workers (pipeline):**
```javascript
const results = await pipeline(
  items,
  item => findIssues(item),      // Worker 1: Find
  issues => verifyIssues(issues), // Worker 2: Verify
  verified => fixIssues(verified) // Worker 3: Fix
);
```

**Adversarial verification:**
```javascript
// Worker 1: Generate solution
const solution = await agent("Solve this problem", {schema: SOLUTION});

// Workers 2-4: Try to break it (adversarial)
const critiques = await parallel([
  () => agent("Find security holes in this solution", {schema: CRITIQUE}),
  () => agent("Find performance issues in this solution", {schema: CRITIQUE}),
  () => agent("Find edge cases that break this solution", {schema: CRITIQUE})
]);

// Arbiter: Synthesize and decide
const valid = critiques.filter(Boolean).filter(c => c.isValid).length < 2; // Majority vote
```

**Common pitfalls:**
- **Too many workers**: Diminishing returns after ~3-5 workers, increases cost
- **Identical workers**: Workers must have diverse perspectives or it's just redundant
- **No synthesis**: Must combine results intelligently, not just concatenate
- **Ignoring minority views**: Sometimes the outlier worker catches the critical issue
- **No schema validation**: Workers should return structured data for easier synthesis

**Quality patterns:**
- **Judge panel**: Multiple independent solutions → arbiter scores → synthesize best
- **Adversarial verify**: Claim → multiple refuters → survives if majority can't refute
- **Multi-modal sweep**: Different search strategies in parallel → merge unique findings
- **Loop-until-dry**: Keep spawning finders until K consecutive rounds find nothing new

**Metrics from actual use:**
- Code-solve: 100 issues resolved in 2h53m (multi-AI consensus)
- Average: 1.73 minutes per issue
- Quality: Higher than single-model (fewer regressions)

**Cost considerations:**
- More expensive than single-model (3-5x tokens typically)
- Trade-off: Higher quality vs higher cost
- Use for important decisions, not trivial tasks

**Related patterns:**
- Workflows (orchestration at scale)
- Agent tool (single subagent delegation)
- Pipeline vs parallel (sequential vs concurrent)

Related: [[feedback_claude_code_permissions]], [[project_code_solve_success]]
