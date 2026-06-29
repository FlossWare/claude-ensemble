# Quality-First Routing

**Location:** `shared/quality-first-routing.cjs`  
**Created:** 2026-06-28  
**Purpose:** Remove cost weights from routing - prioritize capability × confidence × history only

---

## Overview

Quality-first routing is an alternative to cost-weighted routing that **completely ignores model costs** when selecting the best model for a task.

### Key Differences from Weighted-Voting

| Feature | Weighted-Voting | Quality-First Routing |
|---------|----------------|---------------------|
| **Formula** | tier × capability × confidence × history × calibration | capability × confidence × history × calibration |
| **Tier Weight** | Included (opus=1.0, haiku=0.6) | **Removed** (no tier penalty) |
| **Cost Factor** | Implicit via tier weights | **None** (cost=0 treated equally) |
| **Free API Models** | Lower weight (tier < 1.0) | **Full weight** (no penalty) |
| **Use Case** | Cost-sensitive workflows | Critical tasks, free API fleets |

### When to Use Quality-First Routing

✅ **Use quality-first routing when:**
- Using **free API fleet** (DeepSeek, Gemini Flash, Llama, Mistral, etc.)
- Cost of being **wrong > API cost** (security audits, medical, legal, financial)
- Research workflows requiring **maximum accuracy**
- Evaluation/benchmark tasks where quality is the only metric
- Exploring **new model capabilities** without cost bias

❌ **Use cost-weighted routing when:**
- Budget constraints exist
- Task is low-stakes (documentation, simple queries)
- Volume is high (thousands of calls per day)
- Cost-quality tradeoff is acceptable

---

## API Reference

### Main Entry Point

```javascript
const { runQualityFirstVoting } = require('./shared/quality-first-routing.cjs');

const result = await runQualityFirstVoting(votes, taskType, options);
```

**Parameters:**
- `votes` (Array): Worker votes (same format as weighted-voting)
- `taskType` (string): Task type for capability scoring
- `options` (Object): Same options as weighted-voting

**Returns:**
```javascript
{
  voting_result: {
    status: 'success',
    algorithm: 'quality_first_voting',
    routing_mode: 'QUALITY_FIRST (cost ignored)',
    winner: { answer, total_weight, vote_count, consensus_level, votes },
    runner_up: { ... },
    metadata: { total_votes, filtered_votes, ... }
  },
  quality_first_enabled: true,
  cost_ignored: true,
  summary: { winner_answer, consensus_level, routing_mode }
}
```

### Weight Calculation

```javascript
const { calculateQualityFirstWeight } = require('./shared/quality-first-routing.cjs');

const weight = calculateQualityFirstWeight(vote, taskType, banditState, options);
```

**Formula:**
```
quality_weight = capability × confidence × history × calibration
```

**Components:**
- `capability`: Task-specific model strength (0.0-1.0) from CAPABILITY_MATRIX
- `confidence`: Model's self-reported confidence (0.0-1.0)
- `history`: Thompson Sampling avg_quality (0.0-1.0) from bandit-state.json
- `calibration`: Penalty for overconfidence (0.25-1.0) from confidence-calibration

**NO tier weight (removes implicit cost penalty)**

### Model Selection Helper

```javascript
const { selectBestModel } = require('./shared/quality-first-routing.cjs');

const result = selectBestModel(availableModels, taskType);
```

**Returns:**
```javascript
{
  best_model: 'opus',
  quality_score: 0.855,
  capability_score: 0.95,
  historical_accuracy: 0.90,
  alternatives: [
    { model: 'sonnet', quality_score: 0.782, score_difference: 0.073 },
    { model: 'deepseek-coder', quality_score: 0.720, ... }
  ]
}
```

### Comparison Tool

```javascript
const { compareQualityVsCost } = require('./shared/quality-first-routing.cjs');

const comparison = await compareQualityVsCost(votes, taskType, options);
```

**Returns:**
```javascript
{
  comparison: {
    same_winner: false,
    weight_difference: 0.123,
    quality_consensus_level: 'strong',
    cost_consensus_level: 'moderate'
  },
  quality_first: { ... },
  cost_weighted: { ... },
  recommendation: 'Algorithms DISAGREE - quality-first may select more expensive but better model'
}
```

### Weak Model Detection

```javascript
const { detectWeakModels } = require('./shared/quality-first-routing.cjs');

const analysis = detectWeakModels(votes, weakThreshold = 0.3);
```

**Returns:**
```javascript
{
  weak_models: [
    { model: 'haiku', weight: 0.28, confidence: 0.80, ... },
    { model: 'gemini-flash', weight: 0.25, ... }
  ],
  strong_models: [ { model: 'opus', weight: 0.72 }, ... ],
  summary: {
    total_votes: 5,
    weak_count: 2,
    strong_count: 3,
    weak_percentage: '40.0',
    threshold: 0.3
  },
  recommendation: 'OK: Majority of models have sufficient quality weights'
}
```

---

## Integration Examples

### Drop-in Replacement for Weighted-Voting

```javascript
// Before (cost-weighted)
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');
const result = await runWeightedVoting(votes, taskType, options);

// After (quality-first)
const { runQualityFirstVoting } = require('./shared/quality-first-routing.cjs');
const result = await runQualityFirstVoting(votes, taskType, options);
```

### Workflow Integration

```javascript
// In deep-research.mjs
const { runQualityFirstVoting } = require('./shared/quality-first-routing.cjs');

export default async function({ phase, parallel, agent, log }) {
  await phase('Workers', async () => {
    const workers = await parallel([
      agent({ model: 'deepseek-chat', task: 'Research topic A' }),
      agent({ model: 'gemini-flash', task: 'Research topic B' }),
      agent({ model: 'llama3.3', task: 'Research topic C' }),
    ]);

    // Use quality-first routing (free APIs)
    const result = await runQualityFirstVoting(
      workers.map(w => ({ model: w.model, answer: w.result, confidence: w.confidence })),
      'research',
      { minConfidence: 50 }
    );

    log(`Winner: ${result.voting_result.winner.answer}`);
    log(`Routing mode: ${result.voting_result.routing_mode}`);
  });
}
```

### Conditional Quality-First

```javascript
// Use quality-first for critical tasks, cost-weighted for others
const isCriticalTask = taskType === 'security_audit' || taskType === 'medical_diagnosis';

const votingFunction = isCriticalTask
  ? runQualityFirstVoting
  : runWeightedVoting;

const result = await votingFunction(votes, taskType, options);
```

### Database Configuration

```sql
-- Enable quality-first routing for specific workflows
INSERT INTO workflow.quality_first_config
  (workflow_name, task_type, use_quality_first_routing, reason)
VALUES
  ('deep-research', 'research', TRUE, 'Free API fleet - cost not a factor'),
  ('code-security', 'security_audit', TRUE, 'Critical security - accuracy > cost')
ON CONFLICT (workflow_name, task_type) DO UPDATE SET
  use_quality_first_routing = EXCLUDED.use_quality_first_routing,
  reason = EXCLUDED.reason,
  last_updated = NOW();
```

```javascript
// Read config from database
const { Pool } = require('pg');
const pool = new Pool({ connectionString: 'postgresql://aio-01:5433/learning' });

async function getRoutingMode(workflowName, taskType) {
  const result = await pool.query(
    `SELECT use_quality_first_routing FROM workflow.quality_first_config
     WHERE workflow_name = $1 AND task_type = $2`,
    [workflowName, taskType]
  );

  return result.rows.length > 0 && result.rows[0].use_quality_first_routing
    ? runQualityFirstVoting
    : runWeightedVoting;
}
```

---

## Performance Impact

### Weight Calculation Comparison

| Model | Tier | Capability | Confidence | History | Quality-First Weight | Cost-Weighted Weight | Difference |
|-------|------|-----------|-----------|---------|---------------------|---------------------|------------|
| **opus** | 1.0 | 0.95 | 0.90 | 0.90 | **0.769** | **0.769** | 0.000 (same) |
| **sonnet** | 0.85 | 0.92 | 0.85 | 0.85 | **0.665** | **0.565** | +0.100 (+17.7%) |
| **haiku** | 0.6 | 0.75 | 0.80 | 0.70 | **0.420** | **0.252** | +0.168 (+66.7%) |
| **gemini-flash** | 0.75 | 0.75 | 0.85 | 0.75 | **0.478** | **0.359** | +0.119 (+33.2%) |
| **deepseek-coder** | 0.7 | 1.0 | 0.80 | 0.80 | **0.640** | **0.448** | +0.192 (+42.9%) |

**Key Insight:** Quality-first routing gives **lower-tier models** (haiku, gemini-flash, deepseek) significantly higher weights compared to cost-weighted routing.

### Real-World Example: Free API Fleet

**Scenario:** 5 haiku votes vs 2 opus votes

```javascript
const votes = [
  { model: 'haiku', answer: 'X', confidence: 80 },  // 5 votes
  { model: 'opus', answer: 'Y', confidence: 90 },   // 2 votes
];
```

| Algorithm | Winner | Total Weight | Reasoning |
|-----------|--------|-------------|-----------|
| **Quality-First** | X (haiku) | 5 × 0.42 = **2.10** | No tier penalty - haiku votes count more |
| **Cost-Weighted** | Y (opus) | 2 × 0.77 = **1.54** | Tier weight (0.6) reduces haiku influence |

**Result:** Quality-first routing trusts the **majority vote** even from weaker models. Cost-weighted routing favors **expert minority** (opus).

---

## Testing

```bash
# Run test suite
node shared/quality-first-routing.test.cjs
```

**Test Coverage:**
1. ✅ Weight calculation removes tier factor
2. ✅ Free API models get full weight (no penalty)
3. ✅ Weak models get lower weights (capability-based)
4. ✅ Quality-first vs cost-weighted comparison
5. ✅ Best model selection for task types
6. ✅ Weak model detection
7. ✅ Voting algorithm integration
8. ✅ Metadata transparency

**Test Results:**
```
Total tests: 28
✓ Passed: 28
✗ Failed: 0

🎉 All tests passed!
```

---

## Database Schema

### Configuration Table

```sql
workflow.quality_first_config
  - workflow_name TEXT
  - task_type TEXT
  - use_quality_first_routing BOOLEAN
  - reason TEXT
  - max_cost_per_call NUMERIC
  - enabled_at TIMESTAMP
  - last_updated TIMESTAMP
```

### Audit Trail

```sql
workflow.quality_first_decisions
  - workflow_execution_id TEXT
  - task_type TEXT
  - models_evaluated JSONB
  - winner_model TEXT
  - winner_quality_weight NUMERIC
  - cost_weighted_winner TEXT (for comparison)
  - same_winner BOOLEAN
  - quality_advantage NUMERIC
  - cost_incurred NUMERIC
  - created_at TIMESTAMP
```

### Views

```sql
-- Active quality-first workflows
SELECT * FROM workflow.active_quality_first_workflows;

-- Quality vs cost comparison by task type
SELECT * FROM workflow.quality_vs_cost_comparison;
```

---

## Migration

```bash
# Apply database migration
psql -h aio-01 -p 5433 -U sfloess -d learning -f db/migrations/008_quality_first_routing.sql
```

---

## FAQ

**Q: When should I use quality-first routing?**  
A: When using free API fleets (DeepSeek, Gemini Flash, Llama) OR when task accuracy is more valuable than API cost (security, medical, legal).

**Q: Does quality-first routing cost more?**  
A: Not necessarily. With free APIs (cost=$0), quality-first routing costs the SAME but routes to better models. With paid APIs, it MAY select more expensive models if they're significantly better.

**Q: Can I use both algorithms?**  
A: Yes! Use `compareQualityVsCost()` to run both and see the difference. Configure per-workflow in the database.

**Q: What if quality-first and cost-weighted disagree?**  
A: This indicates a quality-cost tradeoff. Review the `comparison.recommendation` field - it explains which to trust based on your priorities.

**Q: Does this work with circuit-breaker, calibration, rotation?**  
A: Yes! Quality-first routing integrates with all existing infrastructure (circuit-breaker, confidence-calibration, model-rotation, Sybil protection, BFT strategies).

---

## Files Created

| File | Purpose | Lines of Code |
|------|---------|---------------|
| `shared/quality-first-routing.cjs` | Core implementation | 480 |
| `shared/quality-first-routing.test.cjs` | Test suite (28 tests) | 410 |
| `db/migrations/008_quality_first_routing.sql` | Database schema | 150 |
| `docs/quality-first-routing.md` | Documentation (this file) | 600 |

**Total:** 1,640 lines of code

---

## Next Steps

1. **Apply Migration:**
   ```bash
   psql -h aio-01 -p 5433 -U sfloess -d learning -f db/migrations/008_quality_first_routing.sql
   ```

2. **Enable for Workflows:**
   ```sql
   UPDATE workflow.quality_first_config
   SET use_quality_first_routing = TRUE
   WHERE workflow_name = 'deep-research' AND task_type = 'research';
   ```

3. **Update Workflows:**
   Replace `runWeightedVoting()` with `runQualityFirstVoting()` in workflows using free API fleets.

4. **Monitor Performance:**
   ```sql
   SELECT * FROM workflow.quality_vs_cost_comparison ORDER BY total_decisions DESC;
   ```

---

## References

- **Weighted Voting:** `shared/weighted-voting.cjs`
- **Capability Matrix:** `shared/weighted-voting.cjs` (CAPABILITY_MATRIX)
- **Thompson Sampling:** `~/.claude/learning/bandit-state.json`
- **Confidence Calibration:** `shared/confidence-calibration.cjs`
- **Circuit Breaker:** `shared/circuit-breaker.cjs`
