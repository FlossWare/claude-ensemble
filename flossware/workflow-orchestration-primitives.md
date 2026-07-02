# Workflow Orchestration Primitives

**Package:** FlossWare/skills-ai  
**Purpose:** Battle-tested workflow orchestration patterns from claude-global-skills  
**Production Evidence:** 63 workflow executions, 182 total workflows logged

## Core Primitives

### 1. `parallel()`
**Purpose:** Run agents concurrently (barrier pattern)

```javascript
const results = await parallel([
  () => agent('Task 1'),
  () => agent('Task 2'),
  () => agent('Task 3')
]);
// ALL tasks complete before continuing
```

**When to Use:**
- Need ALL results before next step
- Cross-item analysis required
- Early-exit if count is zero

**When NOT to Use:**
- Independent stages (use pipeline instead)
- No cross-item dependencies

### 2. `pipeline()`
**Purpose:** Multi-stage processing WITHOUT barriers

```javascript
const results = await pipeline(
  items,
  stage1,  // Item A can be in stage 3
  stage2,  // while Item B is in stage 1
  stage3
);
// Wall-clock = slowest single-item chain, not sum-of-slowest-per-stage
```

**When to Use:**
- DEFAULT for multi-stage work
- Independent items flowing through stages
- Maximum parallelism desired

**Production Pattern:**
```javascript
// Canonical: pipeline for review → verify
const results = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, {schema: FINDINGS_SCHEMA, phase: 'Review'}),
  review => parallel(review.findings.map(f => () =>
    agent(`Verify: ${f.title}`, {schema: VERDICT_SCHEMA, phase: 'Verify'})
      .then(v => ({...f, verdict: v}))
  ))
);
```

### 3. `agent()`
**Purpose:** Spawn subagent with structured output

```javascript
const result = await agent('Your prompt', {
  label: 'custom-label',      // Override display
  phase: 'Analysis',          // Progress group
  schema: RESULT_SCHEMA,      // Force structured output
  model: 'opus',              // Model override (rare)
  effort: 'high',             // Reasoning effort
  isolation: 'worktree',      // Git worktree isolation
  agentType: 'code-reviewer'  // Custom agent type
});
```

**Schema-Based Structured Output:**
```javascript
const BUGS_SCHEMA = {
  type: 'object',
  properties: {
    bugs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          severity: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'number' }
        }
      }
    }
  }
};

const result = await agent('Find bugs', {schema: BUGS_SCHEMA});
// result is validated object, not string - no parsing needed
```

### 4. `phase()`
**Purpose:** Progress tracking and grouping

```javascript
await phase('Research');
// Subsequent agent() calls grouped under "Research"

await phase('Synthesis');
// New group starts
```

**Production Evidence:**
- workflow.phases table: 227 phases logged
- Phases tracked with duration_ms, outcome
- Used for performance analysis

## Advanced Patterns

### Loop-Until-Dry
```javascript
const bugs = [];
let dry = 0;
while (dry < 2) {
  const found = await parallel(FINDERS.map(f => () => agent(f.prompt)));
  const fresh = found.filter(b => !seen.has(key(b)));
  if (!fresh.length) { dry++; continue; }
  dry = 0;
  bugs.push(...fresh);
}
```

### Adversarial Verify
```javascript
const votes = await parallel(Array.from({length: 3}, () => () =>
  agent(`Try to refute: ${claim}`, {schema: VERDICT})
));
const survives = votes.filter(v => !v.refuted).length >= 2;
```

### Judge Panel
```javascript
const attempts = await parallel(APPROACHES.map(a => () =>
  agent(a.prompt, {schema: SOLUTION})
));
const scores = await parallel(attempts.map(s => () =>
  agent(`Score this solution: ${s}`, {schema: SCORE})
));
const winner = attempts[scores.indexOf(Math.max(...scores))];
```

## Production Metrics

**From PostgreSQL monitoring.execution_summary:**
- Total workflows: 182
- Total agents: 914 worker tasks
- Models used: command-a-03-2025, command-r7b-12-2024, gpt-4o, nvidia/nemotron
- Success rate: ~80% (varies by model)
- Avg duration: 5-11 seconds per agent

**Worker Distribution:**
- 8 workers: laptop-01, server-01/02/03, pi-01/02, desktop-ap, server-ap
- Max parallelism: 8 concurrent agents
- Fleet utilization: 68% (up from 16% before orchestration)

## FlossWare Integration

**Package Structure:**
```
flossware/skills-ai/
├── primitives/
│   ├── parallel.js
│   ├── pipeline.js
│   ├── agent.js
│   └── phase.js
├── patterns/
│   ├── loop-until-dry.js
│   ├── adversarial-verify.js
│   └── judge-panel.js
└── examples/
    ├── deep-research.js
    └── code-review.js
```

**Dependencies:**
- Node.js 18+
- PostgreSQL 14+ with pgvector (for workflow storage)
- sentence-transformers (for embeddings)

**Production Ready:**
- ✅ 182 workflows executed
- ✅ PostgreSQL storage integration
- ✅ Multi-model support
- ✅ Fleet distribution proven
