# PostgreSQL Table Integration Guide

**Created:** 2026-07-01  
**Issues:** #251-254  
**Purpose:** Wire in four previously-unused PostgreSQL tables

---

## Summary

Four tables in PostgreSQL database `learning` on `aio-01:5433` have been wired into the orchestration system:

| Table | Purpose | Integration Point |
|-------|---------|-------------------|
| `learning.diversity_violations` | Model selection diversity enforcement | Model routing/selection |
| `learning.procedural_rules` | Pattern/rule extraction | Post-execution learning |
| `monitoring.execution_log` | Detailed task execution tracking | Task execution (complements summary) |
| `monitoring.model_tuning` | Model parameter tuning history | Parameter optimization |

---

## Files Created

### Integration Wrappers

1. **`shared/postgres-table-integrations.cjs`** - JavaScript/Node.js integration
   - CommonJS module (for workflows using require())
   - Full CRUD operations for all four tables
   - Connection pooling with PostgreSQL

2. **`shared/postgres_table_integrations.py`** - Python integration
   - Python wrapper with same API
   - For use in Python-based routers and monitoring

3. **`shared/postgres-integration-examples.cjs`** - Usage examples
   - Demonstrates all four table types
   - Sample queries and integration patterns
   - Runnable test script

---

## Integration Points

### 1. Diversity Violations (`learning.diversity_violations`)

**Where to integrate:** Model selection/routing code

**Locations:**
- `~/.claude/self/multi-model-router.py`
- `~/.claude/self/contextual-bandits-production.py`
- `shared/model-performance.js` (ModelPerformanceTracker)
- `shared/smart-consensus.js`

**How to use:**

```javascript
const { recordDiversityViolation, calculateDiversityEntropy } = require('./shared/postgres-table-integrations.cjs');

// In model selection:
const modelUsage = { opus: 72, sonnet: 18, haiku: 8, 'gpt-4o': 2 };
const entropy = calculateDiversityEntropy(modelUsage);

if (modelUsage['opus'] / total > 0.70) {
  await recordDiversityViolation({
    violation_type: 'ceiling_breach',
    model: 'opus',
    current_usage_pct: 72,
    quota_limit_pct: 70,
    diversity_entropy: entropy,
    action_taken: 'forced_rotation'
  });
}
```

**Python:**

```python
from postgres_table_integrations import record_diversity_violation, calculate_diversity_entropy

model_usage = {'opus': 72, 'sonnet': 18, 'haiku': 8}
entropy = calculate_diversity_entropy(model_usage)

if model_usage['opus'] / sum(model_usage.values()) > 0.70:
    record_diversity_violation({
        'violation_type': 'ceiling_breach',
        'model': 'opus',
        'current_usage_pct': 72,
        'quota_limit_pct': 70,
        'diversity_entropy': entropy,
        'action_taken': 'forced_rotation'
    })
```

**Sample queries:**

```sql
-- Models with most violations (last 30 days)
SELECT model, violation_type, COUNT(*) as count, AVG(current_usage_pct) as avg_usage
FROM learning.diversity_violations
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY model, violation_type
ORDER BY count DESC;

-- Diversity entropy trends
SELECT DATE(timestamp) as date, AVG(diversity_entropy) as avg_entropy
FROM learning.diversity_violations
WHERE diversity_entropy IS NOT NULL
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

---

### 2. Procedural Rules (`learning.procedural_rules`)

**Where to integrate:** Post-execution learning, pattern extraction

**Locations:**
- After successful task completion in workflows
- `shared/learning-system.js` (captureDecision)
- `shared/learning.js`
- Custom workflow files (code-test.js, code-solve.js, etc.)

**How to use:**

```javascript
const { recordProceduralRule, queryProceduralRules } = require('./shared/postgres-table-integrations.cjs');

// After successful execution:
await recordProceduralRule({
  condition: {
    task_type: 'code_generation',
    language: 'java',
    framework: 'maven',
    input_tokens_range: [1000, 5000]
  },
  action: 'use_deepseek_coder',
  confidence: 0.92,
  evidence_count: 5
});

// Before task execution (query for learned patterns):
const rules = await queryProceduralRules({
  task_type: 'code_generation',
  language: 'java'
}, 0.8); // min confidence 0.8

if (rules.length > 0) {
  console.log(`Recommended: ${rules[0].action} (confidence: ${rules[0].confidence})`);
}
```

**Python:**

```python
from postgres_table_integrations import record_procedural_rule, query_procedural_rules

# Record pattern
record_procedural_rule({
    'condition': {
        'task_type': 'security_review',
        'severity': 'high',
        'codebase_size': 'large'
    },
    'action': 'use_opus',
    'confidence': 0.88,
    'evidence_count': 12
})

# Query patterns
rules = query_procedural_rules({'task_type': 'security_review'}, min_confidence=0.8)
```

**Sample queries:**

```sql
-- Most reliable rules (high confidence, strong evidence)
SELECT action, confidence, evidence_count, condition, last_updated
FROM learning.procedural_rules
WHERE confidence > 0.8 AND evidence_count > 10
ORDER BY confidence DESC, evidence_count DESC
LIMIT 10;

-- Rules by task type
SELECT 
  condition->>'task_type' as task_type,
  action,
  COUNT(*) as rule_count,
  AVG(confidence) as avg_confidence
FROM learning.procedural_rules
WHERE condition ? 'task_type'
GROUP BY condition->>'task_type', action
ORDER BY rule_count DESC;
```

---

### 3. Execution Log (`monitoring.execution_log`)

**Where to integrate:** Task execution (worker/arbiter/verifier)

**Locations:**
- Workflow execution wrappers
- `shared/workflow-storage-adapter.cjs` (storeWorkerResult)
- Multi-model orchestration code
- Individual workflow files

**How to use:**

```javascript
const { logExecution } = require('./shared/postgres-table-integrations.cjs');

// During/after task execution:
const startTime = Date.now();
const result = await executeTask(...);

await logExecution({
  model: 'opus',
  model_role: 'worker',
  workflow: 'code-review',
  task_type: 'security',
  phase: 'analysis',
  label: 'SQL injection check',
  parameters: {
    file_pattern: '**/*.java',
    severity_threshold: 'high'
  },
  quality_score: 0.92,
  confidence: 0.88,
  consensus_score: 0.85,
  was_selected: true,
  input_tokens: 1500,
  output_tokens: 800,
  cost_usd: 0.015,
  duration_ms: Date.now() - startTime,
  outcome: 'SUCCESS',
  run_id: 'review-2026-07-01-001',
  execution_id: 'exec-001-worker-opus',
  selection_method: 'contextual_bandit'
});
```

**Python:**

```python
from postgres_table_integrations import log_execution
import time

start_time = time.time()
# ... execute task ...

log_execution({
    'model': 'sonnet',
    'model_role': 'arbiter',
    'workflow': 'code-review',
    'task_type': 'security',
    'worker_models': ['opus', 'gpt-4o', 'gemini-2.0-flash-exp'],
    'selected_model': 'opus',
    'quality_score': 0.90,
    'input_tokens': 5000,
    'output_tokens': 1200,
    'cost_usd': 0.018,
    'duration_ms': int((time.time() - start_time) * 1000),
    'outcome': 'SUCCESS'
})
```

**Sample queries:**

```sql
-- Model selection rates by workflow
SELECT model, workflow,
       COUNT(*) as total,
       SUM(CASE WHEN was_selected THEN 1 ELSE 0 END) as selected,
       (SUM(CASE WHEN was_selected THEN 1 ELSE 0 END)::float / COUNT(*) * 100) as selection_pct
FROM monitoring.execution_log
WHERE workflow IS NOT NULL
GROUP BY model, workflow
HAVING COUNT(*) > 5
ORDER BY selection_pct DESC;

-- Cost efficiency by model
SELECT model,
       COUNT(*) as executions,
       AVG(quality_score) as avg_quality,
       AVG(cost_usd) as avg_cost,
       (AVG(quality_score) / NULLIF(AVG(cost_usd), 0)) as quality_per_dollar
FROM monitoring.execution_log
WHERE outcome = 'SUCCESS' AND cost_usd > 0
GROUP BY model
ORDER BY quality_per_dollar DESC;

-- Recent failures by model
SELECT model, workflow, task_type, error, timestamp
FROM monitoring.execution_log
WHERE outcome = 'FAILURE' OR outcome = 'PARTIAL'
ORDER BY timestamp DESC
LIMIT 20;
```

---

### 4. Model Tuning (`monitoring.model_tuning`)

**Where to integrate:** Parameter optimization, A/B testing

**Locations:**
- Parameter sweep scripts
- Model configuration updates
- Performance tuning workflows
- Adaptive parameter selection

**How to use:**

```javascript
const { recordModelTuning, queryModelTuning } = require('./shared/postgres-table-integrations.cjs');

// After parameter sweep:
await recordModelTuning({
  model: 'opus',
  task_type: 'security_review',
  optimal_params: {
    temperature: 0.3,
    top_p: 0.9,
    max_tokens: 2000,
    presence_penalty: 0.1
  },
  avg_quality: 0.92,
  avg_confidence: 0.88,
  avg_cost_usd: 0.015,
  avg_duration_ms: 4200,
  sample_count: 50,
  success_rate: 0.94,
  selection_rate: 0.68,
  quality_trend: [0.85, 0.87, 0.90, 0.92],
  cost_trend: [0.018, 0.017, 0.016, 0.015]
});

// Query optimal params before execution:
const tuning = await queryModelTuning({ 
  model: 'opus', 
  task_type: 'security_review' 
});

if (tuning.length > 0) {
  const params = tuning[0].optimal_params;
  console.log('Using tuned params:', params);
}
```

**Python:**

```python
from postgres_table_integrations import record_model_tuning, query_model_tuning

# Record tuning
record_model_tuning({
    'model': 'sonnet',
    'task_type': 'code_generation',
    'optimal_params': {'temperature': 0.5, 'top_p': 0.95},
    'avg_quality': 0.85,
    'sample_count': 75,
    'success_rate': 0.88,
    'quality_trend': [0.80, 0.82, 0.84, 0.85]
})

# Query tuning
tuning = query_model_tuning({'task_type': 'code_generation'})
```

**Sample queries:**

```sql
-- Quality improvements over time
SELECT model, task_type,
       quality_trend->0 as initial_quality,
       quality_trend->-1 as final_quality,
       (quality_trend->-1)::float - (quality_trend->0)::float as improvement
FROM monitoring.model_tuning
WHERE jsonb_array_length(quality_trend) >= 2
ORDER BY improvement DESC;

-- Best models by task type
SELECT task_type, model, avg_quality, success_rate, sample_count
FROM monitoring.model_tuning
WHERE sample_count >= 10
ORDER BY task_type, avg_quality DESC;

-- Cost trends
SELECT model, task_type,
       cost_trend->0 as initial_cost,
       cost_trend->-1 as current_cost,
       ((cost_trend->-1)::float - (cost_trend->0)::float) / (cost_trend->0)::float * 100 as cost_change_pct
FROM monitoring.model_tuning
WHERE jsonb_array_length(cost_trend) >= 2
ORDER BY cost_change_pct;
```

---

## Testing

Run the examples to verify integration:

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared
node postgres-integration-examples.cjs
```

Expected output:
- Diversity violation recorded and queried
- Procedural rules stored and retrieved
- Execution logs captured with full metadata
- Model tuning parameters stored and queried
- Sample SQL queries demonstrating analytics

---

## Database Schema Reference

### `learning.diversity_violations`

```sql
\d+ learning.diversity_violations
```

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| timestamp | timestamp | When violation occurred |
| violation_type | text | 'floor_breach', 'ceiling_breach', 'entropy_collapse' |
| model | text | Model that violated quota |
| current_usage_pct | real | Current usage percentage |
| quota_limit_pct | real | Quota limit breached |
| diversity_entropy | real | Shannon entropy of distribution |
| action_taken | text | Action: 'forced_rotation', 'banned_temporarily', 'warning_only' |

**Indexes:**
- `idx_diversity_violations_model` (model)
- `idx_diversity_violations_timestamp` (timestamp DESC)
- `idx_diversity_violations_type` (violation_type)

---

### `learning.procedural_rules`

```sql
\d+ learning.procedural_rules
```

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| condition_hash | text | Hash of condition for deduplication |
| condition | jsonb | Condition that triggers rule |
| action | text | Action to take |
| confidence | double precision | Confidence score (0-1) |
| evidence_count | integer | Number of observations |
| last_updated | timestamp | Last update time |

**Indexes:**
- `idx_proc_condition_hash` (condition_hash)
- Unique constraint: (condition_hash, action)

**Constraints:**
- confidence BETWEEN 0.0 AND 1.0

---

### `monitoring.execution_log`

```sql
\d+ monitoring.execution_log
```

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| timestamp | timestamp | Execution timestamp |
| model | text | Model used |
| model_role | text | 'worker', 'arbiter', 'verifier' |
| workflow | text | Workflow name |
| task_type | text | Task category |
| phase | text | Execution phase |
| label | text | Task label |
| parameters | jsonb | Task parameters |
| quality_score | real | Quality score (0-1) |
| confidence | real | Model confidence (0-1) |
| consensus_score | real | Consensus with others (0-1) |
| was_selected | boolean | Was output selected? |
| input_tokens | integer | Input token count |
| output_tokens | integer | Output token count |
| cost_usd | real | Cost in USD |
| duration_ms | integer | Duration in milliseconds |
| outcome | text | 'SUCCESS', 'FAILURE', 'PARTIAL', 'unknown' |
| outcome_notes | text | Notes about outcome |
| ... | ... | (38 total columns) |

**Indexes:**
- `idx_exec_model` (model)
- `idx_exec_timestamp` (timestamp DESC)
- `idx_exec_workflow` (workflow)

---

### `monitoring.model_tuning`

```sql
\d+ monitoring.model_tuning
```

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| updated_at | timestamp | Last update time |
| model | text | Model name |
| task_type | text | Task type |
| optimal_params | jsonb | Optimal parameters |
| avg_quality | real | Average quality score |
| avg_confidence | real | Average confidence |
| avg_cost_usd | real | Average cost |
| avg_duration_ms | real | Average duration |
| sample_count | integer | Sample count |
| success_rate | real | Success rate (0-1) |
| selection_rate | real | Selection rate (0-1) |
| quality_trend | jsonb | Quality trend array |
| cost_trend | jsonb | Cost trend array |

**Indexes:**
- Unique constraint: (model, task_type)

---

## Next Steps

1. **Integrate into model routers:**
   - Add diversity violation checks to `multi-model-router.py`
   - Add to contextual bandits router
   - Add to smart consensus

2. **Integrate into workflows:**
   - Add execution logging to all workflow files
   - Add procedural rule extraction after successful executions
   - Query rules before task execution for learned patterns

3. **Create monitoring dashboards:**
   - Grafana dashboard for diversity violations
   - Cost efficiency dashboard from execution_log
   - Model tuning trends

4. **Automated responses:**
   - Alert when diversity entropy drops below threshold
   - Auto-rotate models on ceiling breach
   - Auto-apply learned procedural rules

---

## API Reference

See inline documentation in:
- `shared/postgres-table-integrations.cjs` (JavaScript)
- `shared/postgres_table_integrations.py` (Python)
- `shared/postgres-integration-examples.cjs` (Usage examples)

---

**Status:** Ready for integration (tested 2026-07-01)
