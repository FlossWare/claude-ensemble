# ai-consensus-debate

Adversarial debate consensus workflow where workers propose answers, see competing proposals, write rebuttals, and an arbiter judges the strongest position.

## Overview

`ai-consensus-debate` implements a structured adversarial debate protocol that surfaces better reasoning through intellectual conflict. Unlike standard consensus workflows that synthesize answers in parallel, this workflow creates an adversarial environment where worker models must defend their positions against critique and actively challenge competing proposals.

The protocol follows: **propose → exchange → rebut → judge**

## When to Use

- **Critical decisions** where you need multiple perspectives stress-tested against each other (architecture choices, security trade-offs, strategic decisions)
- **Controversial topics** where different valid positions exist and you want the strongest argument to emerge
- **Complex analysis** where adversarial review surfaces blind spots better than independent analysis
- **Quality validation** where you want ideas battle-tested before implementation
- **Red team/blue team** scenarios where you need opposing viewpoints to challenge assumptions

## When NOT to Use

- Simple factual questions with clear right answers (use `ai-consensus` instead)
- Tasks requiring collaborative synthesis rather than competitive selection (use `ai-consensus-weighted`)
- Time-sensitive queries (debate rounds add latency)
- Low-stakes questions where the overhead isn't justified

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `task` | string | *required* | The question, decision, or analysis task for debate |
| `context` | string | `''` | Additional context provided to all participants |
| `schema` | object | `{ position, reasoning, confidence }` | JSON Schema for worker proposals |
| `arbiter_instructions` | string | `'Judge strongest reasoning...'` | Instructions for arbiter judgment criteria |
| `debate_rounds` | number | `1` | Number of exchange-rebuttal cycles to run |
| `models` | string[] | task-router selection | Worker model names (e.g., `['opus', 'sonnet', 'haiku']`) |
| `budget` | string | `'medium'` | Budget tier passed to task router when `models` not specified |

Both camelCase (`debateRounds`, `arbiterInstructions`) and snake_case (`debate_rounds`, `arbiter_instructions`) parameter names are accepted.

## How It Works

```
Phase 1: PROPOSAL ROUND
         Workers independently propose answers
         Each presents position + reasoning
         |
         v
Phase 2: EXCHANGE PHASE
         All proposals shared with all workers
         Workers see competing positions
         |
         v
Phase 3: REBUTTAL ROUND
         Workers critique other proposals
         Workers defend their own position
         Workers may revise if convinced
         |
         +-- Multiple rounds? Loop back to exchange
         |
         v
Phase 4: ARBITER JUDGMENT
         Arbiter evaluates all proposals + rebuttals
         Judges based on reasoning, defense, critiques
         Selects winning position
```

### Phase Details

1. **Get Arbiter** — Selects the arbiter model via rotation (same system as other consensus workflows).

2. **Proposal Round** — Workers execute in parallel. Each model independently proposes an answer to the task, providing their position, reasoning, and initial confidence. Proposals are blind (workers don't see each other yet).

3. **Exchange Phase** — All proposals are shared with all workers. Each model sees what the others proposed, setting up the adversarial dynamic.

4. **Rebuttal Round** — Each worker must:
   - **Defend** their original position against anticipated critiques
   - **Critique** weaknesses in other proposals, providing specific counterarguments
   - **Revise** their position if they found compelling evidence in other proposals (or strengthen it if they remain convinced)
   
   The workflow encourages intellectual honesty: workers should acknowledge merit in other positions and correct their own reasoning if flawed.

5. **Multi-Round Debates** (optional) — If `debate_rounds > 1`, steps 3-4 repeat. Each round uses the revised positions from the previous round, allowing iterative refinement through adversarial pressure.

6. **Arbiter Judgment** — The arbiter reviews all initial proposals and all rebuttals, then judges which worker presented the strongest overall case. Evaluation criteria:
   - Strength of original reasoning
   - Quality of defense against critiques
   - Validity of critiques against others
   - Intellectual honesty (willingness to revise when wrong)
   - Evidence and logical soundness
   
   The arbiter also assesses the debate quality itself, rating how productive the adversarial process was.

7. **Update State & Learning** — Records arbiter rotation state, sends per-worker feedback to the learning system (marking winner vs. non-winners), and extracts learnings from the debate for future improvement.

## Return Value

```javascript
{
  status: 'success',
  winner: 'opus',                      // which worker won the debate
  confidence: 87,                      // arbiter's confidence in judgment
  result: { ... },                     // synthesized answer (matches schema)
  debate_quality: {
    quality_score: 82,                 // 0-100 rating of debate quality
    key_insights: '...',               // insights that emerged from debate
    strongest_arguments: [...],        // best arguments presented
    weakest_arguments: [...],          // weakest arguments presented
  },
  debate_history: {
    proposals: [...],                  // initial proposals from all workers
    rounds: [                          // per-round rebuttal data
      { round: 1, rebuttals: [...] },
    ],
  },
  all_workers: [...],                  // all worker proposals
  arbiter: 'sonnet',                   // which model served as arbiter
  rounds_completed: 1,                 // how many debate rounds ran
  execution_id: 'debate_1718..._abc123',
}
```

## Examples

### Basic Usage (Architecture Decision)

```javascript
const result = await workflow('ai-consensus-debate', {
  task: 'Should we use microservices or a monolith for this e-commerce platform?',
  context: `
    - Expected load: 10k requests/min peak
    - Team size: 8 engineers
    - Launch timeline: 3 months
    - Future scaling: 5x growth expected in 2 years
  `,
})
```

### Multi-Round Debate (Complex Analysis)

```javascript
const result = await workflow('ai-consensus-debate', {
  task: 'Analyze the security implications of this authentication flow',
  context: authFlowCode,
  debate_rounds: 2,  // Two rounds of exchange-rebuttal
  schema: {
    type: 'object',
    properties: {
      position: { type: 'string', enum: ['secure', 'vulnerable', 'needs-changes'] },
      vulnerabilities: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            type: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
            description: { type: 'string' },
            remediation: { type: 'string' },
          },
        },
      },
      overall_risk: { type: 'string' },
    },
  },
  arbiter_instructions: 'Judge which security analysis is most thorough and identifies the most critical real vulnerabilities with valid remediation.',
})
```

### Custom Models + Budget Control

```javascript
const result = await workflow('ai-consensus-debate', {
  task: 'What is the best pricing strategy for this SaaS product?',
  context: productDetails,
  models: ['opus', 'sonnet'],  // Use only two models for faster debate
  budget: 'high',              // Allow expensive models if router needed
  arbiter_instructions: 'Select the pricing strategy with strongest market evidence and clearest competitive positioning.',
})
```

## Debate Quality Metrics

The arbiter assesses debate quality on these dimensions:

- **Quality Score (0-100)** — Overall productivity of the adversarial process
- **Key Insights** — Novel insights that emerged through debate (vs. independent analysis)
- **Strongest Arguments** — Which arguments withstood adversarial scrutiny
- **Weakest Arguments** — Which arguments collapsed under critique

Low quality scores may indicate:
- Task not suited for adversarial debate (too simple, or workers all converged immediately)
- Workers not engaging meaningfully with critiques
- Proposals too vague for specific rebuttal

## Cost Considerations

Each debate round invokes:
- **Proposal**: N worker calls (parallel)
- **Rebuttal**: N worker calls per round (parallel)
- **Judgment**: 1 arbiter call

**Total calls with N workers and R rounds: N + (N * R) + 1**

With defaults (3 workers, 1 round): 3 + 3 + 1 = 7 calls

With multi-round (3 workers, 2 rounds): 3 + 6 + 1 = 10 calls

Debate rounds are more expensive than standard consensus but surface higher-quality reasoning through adversarial pressure. Use `debate_rounds: 1` for most cases, reserving multi-round debates for critical decisions.

## Differences from Other Consensus Workflows

| Feature | ai-consensus | ai-consensus-refinement | ai-consensus-debate |
|---|---|---|---|
| Interaction model | Independent → synthesize | Critique → revise (arbiter-driven) | Propose → rebut (peer-driven) |
| Workers see others | No | No (only critiques) | Yes (full proposals) |
| Adversarial dynamic | No | No | Yes |
| Intellectual honesty | N/A | N/A | Explicit requirement |
| Defense of position | N/A | No | Yes |
| Critique of peers | No | No | Yes |
| Best for | Parallel diversity | Iterative improvement | Competitive selection |

## Tips

- **Phrase task as debate-worthy**: "Should we..." or "What is the best approach..." works better than "Calculate..." or "List..."
- **Provide rich context**: More context gives workers more to debate about
- **Use custom schema**: Structure the position schema to match your decision type (recommendation, risk assessment, design choice, etc.)
- **Start with 1 round**: Only add rounds if first-round rebuttals felt superficial
- **Check debate_quality**: Low scores suggest task isn't benefiting from adversarial structure

## Integration with Learning System

Each debate run records:
- Winner vs. non-winner outcomes per model
- Arbiter confidence in judgment
- Debate quality score
- Final worker confidence after seeing rebuttals

This feeds the learning system to improve future model selection and arbiter rotation.
