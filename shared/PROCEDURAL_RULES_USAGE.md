# Procedural Rules Integration (Issue #253)

**Table:** `learning.procedural_rules` (PostgreSQL learning DB on aio-01:5433)  
**Purpose:** Extract and query task-specific execution patterns  
**Status:** ✅ WIRED AND TESTED

## What Are Procedural Rules?

Procedural rules capture patterns like:
- "For Java/Maven code generation → use deepseek-coder (92% confidence, 10 observations)"
- "For security reviews of large codebases → use opus (88% confidence, 24 observations)"
- "For meta-answer tasks → use sonnet (80% confidence, 6 observations)"

Rules are extracted automatically from successful executions with high quality scores.

## Integration Points

### 1. Automatic Extraction (learning-system.js)

Procedural rules are automatically extracted when using `captureDecision()`:

```javascript
import { captureDecision } from './shared/learning-system.js';

// Capture arbiter decision with outcome and quality
await captureDecision(agent, {
  workflow: 'code-generation',
  task_type: 'java_maven',
  worker_models: ['opus', 'sonnet', 'haiku'],
  worker_proposals: [...],
  arbiter_model: 'fable',
  selected_index: 1,
  why_accepted: 'Best approach',
  rejection_reasons: {...},
  consensus_score: 85,
  outcome: 'success',          // Required for rule extraction
  quality_score: 0.92          // Required (must be >= 0.75)
});

// Rule automatically extracted:
// condition: { workflow: 'code-generation', task_type: 'java_maven' }
// action: 'use_model_sonnet'
// confidence: 0.92
```

### 2. Manual Rule Recording

```javascript
import { recordProceduralRule } from './shared/procedural-rules-adapter.js';

await recordProceduralRule({
  condition: {
    task_type: 'code_generation',
    language: 'java',
    framework: 'maven'
  },
  action: 'use_deepseek_coder',
  confidence: 0.92,
  evidence_count: 5
});
```

### 3. Querying Rules

```javascript
import { queryProceduralRules, getRecommendedAction } from './shared/procedural-rules-adapter.js';

// Exact match
const rules = await queryProceduralRules(
  { workflow: 'code-generation', task_type: 'java_maven' },
  0.7  // minConfidence
);

// Partial match (JSONB containment)
const partialRules = await queryProceduralRules(
  { workflow: 'code-generation' },  // Missing task_type
  0.7
);

// Get top recommendation
const recommendation = await getRecommendedAction(
  { workflow: 'code-generation', task_type: 'java_maven' },
  0.75
);

console.log(recommendation);
// { action: 'use_model_deepseek_coder', confidence: 0.92, evidence_count: 10 }
```

### 4. Batch Extraction from Execution History

```javascript
import { extractRulesFromExecutions } from './shared/procedural-rules-adapter.js';

const result = await extractRulesFromExecutions({
  minQuality: 0.75,
  minConfidence: 0.7,
  limit: 100
});

console.log(result);
// {
//   executions_analyzed: 11,
//   patterns_found: 4,
//   rules_created: 1,
//   rules: [...]
// }
```

## Database Schema

```sql
CREATE TABLE learning.procedural_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  condition_hash text NOT NULL,           -- SHA256 hash of condition
  condition jsonb NOT NULL,               -- Task condition
  action text NOT NULL,                   -- Action to take
  confidence double precision NOT NULL,   -- 0-1 confidence
  evidence_count integer DEFAULT 1,       -- Number of observations
  last_updated timestamp with time zone DEFAULT now(),
  
  CONSTRAINT procedural_rules_condition_hash_action_key 
    UNIQUE (condition_hash, action),
  CONSTRAINT procedural_rules_confidence_check 
    CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE INDEX idx_proc_condition_hash ON learning.procedural_rules(condition_hash);
```

## Example Workflow Integration

```javascript
export default async function({ agent, parallel, phase }) {
  const workflowName = 'code-generation';
  const taskType = 'java_maven';

  // Query historical rules for guidance
  const recommendation = await getRecommendedAction(
    { workflow: workflowName, task_type: taskType },
    0.75
  );

  if (recommendation) {
    console.log(`Historical data suggests: ${recommendation.action} (${recommendation.confidence} confidence)`);
  }

  // Execute workflow with workers
  await phase('Planning');
  const workers = await parallel([...]);

  // Arbiter selects best proposal
  await phase('Selection');
  const arbiter = await agent(...);

  // Capture decision (auto-extracts rule if successful)
  await captureDecision(agent, {
    workflow: workflowName,
    task_type: taskType,
    worker_models: ['opus', 'sonnet', 'haiku'],
    worker_proposals: workers,
    arbiter_model: 'fable',
    selected_index: arbiter.selected_index,
    why_accepted: arbiter.reason,
    consensus_score: 85,
    outcome: 'success',
    quality_score: 0.92
  });
}
```

## Testing

Run the integration test:

```bash
node shared/test-procedural-rules.mjs
```

Query the database directly:

```bash
psql -h aio-01 -p 5433 -U claude -d learning -c \
  "SELECT condition, action, confidence, evidence_count 
   FROM learning.procedural_rules 
   ORDER BY confidence DESC 
   LIMIT 10;"
```

## Files Created

- `shared/procedural-rules-adapter.js` - JavaScript adapter
- `shared/postgres_table_integrations.py` - Python adapter (pre-existing, Issue #251-254)
- `shared/test-procedural-rules.mjs` - Integration test
- `shared/PROCEDURAL_RULES_USAGE.md` - This documentation

## Integration with learning-system.js

The `captureDecision()` and `updateOutcome()` functions now automatically extract procedural rules when:
1. Outcome is 'success'
2. Quality score is >= 0.75
3. Workflow and task_type are provided

No changes required to existing workflows - rule extraction is automatic and silent-fail.

## Sample Data

Current rules in database:

```json
[
  {
    "condition": {
      "language": "java",
      "framework": "maven",
      "task_type": "code_generation",
      "input_tokens_range": [1000, 5000]
    },
    "action": "use_deepseek_coder",
    "confidence": 0.92,
    "evidence_count": 10
  },
  {
    "condition": {
      "severity": "high",
      "task_type": "security_review",
      "codebase_size": "large"
    },
    "action": "use_opus",
    "confidence": 0.88,
    "evidence_count": 24
  },
  {
    "condition": {
      "workflow": "meta-answer",
      "task_type": "meta-answer"
    },
    "action": "use_model_sonnet",
    "confidence": 0.8,
    "evidence_count": 6
  }
]
```

## Next Steps

1. Add rule querying to worker feedback (show historical patterns before proposing)
2. Add rule-based model selection hints to arbiter
3. Create automated rule pruning (remove low-confidence rules with low evidence)
4. Build rule visualization dashboard
