# ai-consensus-refinement

Self-correcting multi-AI consensus with iterative refinement loops.

## Overview

Unlike standard consensus workflows that make a single pass, `ai-consensus-refinement` implements a critique-revision loop: after workers produce initial responses, the arbiter evaluates them against a confidence threshold. Workers whose responses fall short receive specific critique and must revise. This repeats until the arbiter's confidence exceeds the threshold or the maximum number of rounds is reached.

## When to Use

- Tasks where initial responses are likely to be incomplete or imprecise (security audits, architectural reviews, complex analysis)
- When you need confidence guarantees rather than best-effort consensus
- When iterative improvement is more valuable than parallel diversity
- When the cost of a wrong answer exceeds the cost of additional LLM calls

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `task` | string | *required* | The question or task for workers to answer |
| `context` | string | `''` | Additional context provided to all workers |
| `schema` | object | `{ answer: string }` | JSON Schema for the answer portion of worker responses |
| `arbiter_instructions` | string | `'Select and synthesize...'` | Custom instructions for the arbiter during final synthesis |
| `confidenceThreshold` | number | `80` | Target arbiter confidence (0-100) to stop refining |
| `maxRefinementRounds` | number | `3` | Maximum critique-revision cycles before forcing synthesis |
| `models` | string[] | task-router selection | Worker model names (e.g., `['opus', 'sonnet', 'haiku']`) |
| `budget` | string | `'medium'` | Budget tier passed to the task router when `models` is not specified |

Both camelCase (`confidenceThreshold`) and snake_case (`confidence_threshold`) parameter names are accepted.

## How It Works

```
Round 0: Workers produce initial answers with confidence scores
         |
         v
Round 1+: Arbiter evaluates all responses
         |
         +-- Confidence >= threshold? --> Final Synthesis
         |
         +-- Below threshold:
              |
              +-- Identify workers needing revision
              |
              +-- Send per-worker critique back
              |
              +-- Workers revise and resubmit
              |
              +-- Loop (up to maxRefinementRounds)
```

### Phase Details

1. **Get Arbiter** -- Selects the arbiter model via rotation (same system as other consensus workflows).
2. **Workers** -- All worker models execute in parallel. Each produces a structured answer, confidence score (0-100), reasoning, and caveats.
3. **Arbiter Evaluation** -- The arbiter reviews all worker responses and decides whether they collectively meet the confidence threshold. For each worker that falls short, it produces specific, actionable critique and a list of weaknesses.
4. **Refinement Loop** -- Workers that received critique revise their answers. Only flagged workers are re-invoked (unflagged workers keep their current response). The loop continues until: (a) the arbiter reports confidence >= threshold, (b) no workers are flagged for revision, or (c) `maxRefinementRounds` is reached.
5. **Final Synthesis** -- The arbiter produces the final answer from the (possibly revised) worker responses, including a `refinement_impact` assessment describing how iteration improved the outcome.
6. **Update State** -- Records arbiter rotation state, sends per-worker feedback to the learning system, and extracts learnings.

## Return Value

```javascript
{
  status: 'threshold_met' | 'max_rounds_reached',
  winner: 'opus',                    // winning worker model
  why_selected: '...',               // arbiter's explanation
  confidence: 92,                    // final arbiter confidence
  result: { ... },                   // synthesized answer (matches schema)
  refinement_impact: '...',          // how refinement improved the answer
  refinement: {
    rounds_used: 2,                  // actual rounds before stopping
    max_rounds: 3,                   // configured maximum
    confidence_threshold: 80,        // configured threshold
    threshold_met: true,             // whether threshold was met
    initial_avg_confidence: 58.3,    // average worker confidence at round 0
    final_avg_worker_confidence: 84.7,  // average after refinement
    confidence_improvement: 26.4,    // delta
    history: [                       // per-round snapshot
      { round: 0, label: 'initial', responses: [...] },
      { round: 1, label: 'revision', arbiter_confidence: 65, ... },
      { round: 2, label: 'evaluation_passed', arbiter_confidence: 92, ... },
    ],
  },
  arbiter: 'sonnet',                 // which model served as arbiter
  workers: [                         // final state of each worker
    { model: 'opus', confidence: 88, reasoning: '...', caveats: [], revisions: 2 },
    { model: 'sonnet', confidence: 85, reasoning: '...', caveats: [], revisions: 1 },
    { model: 'haiku', confidence: 81, reasoning: '...', caveats: ['...'], revisions: 2 },
  ],
  execution_id: 'refinement_1718..._abc123',
}
```

## Examples

### Basic usage

```javascript
const result = await workflow('ai-consensus-refinement', {
  task: 'Review this function for correctness bugs',
  context: functionSourceCode,
})
```

### Strict threshold with extra rounds

```javascript
const result = await workflow('ai-consensus-refinement', {
  task: 'Identify all SQL injection vectors in this codebase',
  context: codebaseSnapshot,
  confidenceThreshold: 90,
  maxRefinementRounds: 5,
  schema: {
    type: 'object',
    properties: {
      vulnerabilities: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file: { type: 'string' },
            line: { type: 'number' },
            description: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          },
        },
      },
    },
  },
  arbiter_instructions: 'Merge all confirmed vulnerabilities. Discard false positives.',
})
```

### Fixed model set with low threshold

```javascript
const result = await workflow('ai-consensus-refinement', {
  task: 'Summarize the key points of this document',
  context: documentText,
  confidenceThreshold: 60,
  maxRefinementRounds: 2,
  models: ['sonnet', 'haiku'],
})
```

## Cost Considerations

Each refinement round invokes the arbiter once (for evaluation) plus one worker call per flagged worker (for revision). In the worst case with N workers and M rounds, the total calls are:

- Initial: N worker calls
- Per round: 1 arbiter evaluation + up to N worker revisions
- Final: 1 arbiter synthesis

**Worst case total: N + M*(1+N) + 1 calls**

With defaults (3 workers, 3 rounds): up to 3 + 3*4 + 1 = 16 calls. In practice, rounds often converge early, producing 3 + 1*4 + 1 = 8 calls or fewer.

Set `maxRefinementRounds` conservatively for cost-sensitive tasks, or use `budget: 'low'` to let the task router select cheaper models.

## Differences from Other Consensus Workflows

| Feature | ai-consensus | ai-consensus-filtered | ai-consensus-weighted | ai-consensus-refinement |
|---|---|---|---|---|
| Single pass | Yes | Yes | Yes | No (iterative) |
| Confidence filtering | No | Yes (pre-filter) | Yes (weighted) | Yes (drives refinement) |
| Worker revision | No | No | No | Yes |
| Arbiter critique | No | No | No | Yes |
| Guaranteed threshold | No | No | No | Best-effort with max rounds |
| Cost per run | Low | Low | Low | Medium-High |
