# Multi-Dimensional Thompson Sampling Learning System

## Overview

This system implements Thompson Sampling across **six dimensions** to learn the best strategies for different task contexts:

1. **Capability**: What kind of work? (code_review, code_test, code_solve, pr_review, etc.)
2. **Task Type**: Which domain? (java, python, refactor, test, bug_fix, feature, etc.)
3. **Model**: Which LLM? (opus, sonnet, haiku, gpt4o, local_model, etc.)
4. **Prompt Style**: How to prompt? (direct, chain_of_thought, summarize, step_by_step, etc.)
5. **Orchestration**: How to coordinate? (single, consensus, adversarial, parallel, etc.)
6. **Verification**: How to verify? (none, adversarial_refute, external_check, human_review, etc.)

## Quick Start

### Select a Strategy

```javascript
const { selectStrategy } = require('./shared/multi-dimensional-learning.cjs');

const strategy = await selectStrategy('code_review', 'java', {
  max_cost: 0.05,
  max_latency_ms: 10000,
  allowed_models: ['opus', 'sonnet']
});

// Returns:
// {
//   capability: 'code_review',
//   task_type: 'java',
//   model: 'opus',           // Best model learned for this context
//   prompt_style: 'cot',     // Best prompt style for this context
//   orchestration: 'consensus',
//   verification: 'refute',
//   confidence: 0.92,        // Confidence based on sample size
//   alpha: 15,               // Thompson Sampling Beta(15, 2)
//   beta: 2
// }
```

### Record Learning

```javascript
const { updateStrategyBandit } = require('./shared/multi-dimensional-learning.cjs');

// After executing with the strategy
const reward = await evaluateQuality(result);  // 0.0 to 1.0
const success = reward > 0.75;

await updateStrategyBandit(
  'code_review',
  'java',
  strategy,
  reward,
  success
);

// Thompson Sampling Beta distribution updated:
// New alpha = 1 + successes
// New beta = 1 + failures
```

### Get Top Strategies

```javascript
const { getTopStrategies } = require('./shared/multi-dimensional-learning.cjs');

const topStrategies = await getTopStrategies('code_review', 'java', 10);

// Returns ranked list:
// [
//   { model: 'opus', prompt_style: 'cot', orchestration: 'consensus',
//     verification: 'refute', avg_reward: 0.94, confidence: 0.92, ... },
//   { model: 'sonnet', prompt_style: 'direct', orchestration: 'single',
//     verification: 'none', avg_reward: 0.78, confidence: 0.71, ... },
//   ...
// ]
```

## Strategy Key Format

Strategies are stored with composite keys:

```
capability:task_type:model:prompt_style:orchestration:verification
```

Example: `code_review:java:opus:cot:consensus:refute`

### Fallback Hierarchy

When an exact strategy isn't found, the system progressively searches more general patterns:

1. **Exact**: `code_review:java:opus:cot:consensus:refute`
2. **No verification**: `code_review:java:opus:cot:consensus:*`
3. **No orch/verif**: `code_review:java:opus:cot:*:*`
4. **Task-specific**: `code_review:java:*:*:*:*`
5. **Capability-specific**: `code_review:*:*:*:*:*`
6. **Global fallback**: `*:*:*:*:*:*`

This allows the system to learn from partial matches when exact strategies haven't been tried yet.

## Integration Pattern

### Typical Workflow

```javascript
export default async function({ phase, parallel, agent, log }) {
  const { selectStrategy, updateStrategyBandit } = require('./shared/multi-dimensional-learning.cjs');

  // Phase 1: Select strategy based on past learning
  const strategy = await selectStrategy('code_review', 'java', {
    max_cost: 0.05,
    max_latency_ms: 10000
  });

  log(`Selected strategy: ${strategy.model} with ${strategy.prompt_style}`);

  // Phase 2: Execute with selected strategy
  const result = await agent(`
    Review this code using ${strategy.model}.
    Use ${strategy.prompt_style} approach.
    Orchestrate via: ${strategy.orchestration}
    Verify using: ${strategy.verification}
  `);

  // Phase 3: Evaluate result
  const evaluation = await evaluateQuality(result);
  const reward = evaluation.score;  // 0.0 to 1.0
  const success = reward > 0.75;

  // Phase 4: Update learning
  await updateStrategyBandit('code_review', 'java', strategy, reward, success);

  return result;
}
```

## Thompson Sampling Mechanics

### Beta Distribution

Each strategy tracks a Beta distribution with parameters:
- **Alpha** = 1 + (number of successes)
- **Beta** = 1 + (number of failures)

This represents the probability distribution of the strategy's true success rate.

### Selection Algorithm

1. Sample from each strategy's Beta(alpha, beta)
2. Select the strategy with the highest sample
3. Execute and evaluate
4. Update the Beta distribution based on outcome

This balances:
- **Exploitation**: Strategies with high average reward are sampled higher
- **Exploration**: Strategies with few trials get higher variance samples

### Confidence Calculation

Confidence = success_rate adjusted for sample size using Wilson score interval

More trials → higher confidence (narrower distribution)
Fewer trials → lower confidence (wider distribution, more exploration)

## API Reference

### selectStrategy(capability, taskType, constraints)

**Parameters:**
- `capability` (string): Work category (code_review, code_test, etc.)
- `taskType` (string): Domain (java, python, refactor, etc.)
- `constraints` (object, optional):
  - `max_cost`: Maximum cost in dollars
  - `max_latency_ms`: Maximum latency
  - `allowed_models`: Array of allowed models
  - `min_confidence`: Minimum confidence threshold (0.0-1.0)

**Returns:** Promise<Strategy>
- `model`: Selected model
- `prompt_style`: Selected prompt style
- `orchestration`: Selected orchestration pattern
- `verification`: Selected verification method
- `confidence`: Confidence score (0.0-1.0)
- `alpha`, `beta`: Thompson Sampling parameters
- `is_default`: true if using default (no learning data)

### updateStrategyBandit(capability, taskType, strategy, reward, success)

**Parameters:**
- `capability` (string): Work category
- `taskType` (string): Domain
- `strategy` (object): Selected strategy from selectStrategy()
- `reward` (number): Quality score (0.0-1.0)
- `success` (boolean): Did it succeed?

**Returns:** Promise<UpdatedStats>

### getTopStrategies(capability, taskType, limit)

**Parameters:**
- `capability` (string): Work category
- `taskType` (string): Domain
- `limit` (number): Max results (default 10)

**Returns:** Promise<Array<Strategy>>

### getAnalytics(filters)

**Parameters:**
- `filters` (object, optional):
  - `capability`: Filter by capability
  - `task_type`: Filter by task type
  - `model`: Filter by model

**Returns:** Promise<Analytics>
- `total_strategies`: Number of strategies found
- `avg_reward_overall`: Average reward across strategies
- `best_reward`: Highest average reward
- `worst_reward`: Lowest average reward
- `avg_success_rate`: Average success rate

### exportStrategies(filters)

**Parameters:**
- `filters` (object, optional): Same as getAnalytics

**Returns:** Promise<Array<StrategyRecord>>

## Database Integration

The system integrates with PostgreSQL via the existing `postgres-adapter.js`:

```javascript
const { getDB, getStrategyPerformance } = require('./learning/postgres-adapter');

// Strategies are stored in:
// workflow.strategy_performance

// Key columns:
// - strategy: varchar (composite key)
// - successes: integer
// - failures: integer
// - alpha: numeric
// - beta: numeric
// - total_reward: numeric
// - avg_reward: numeric
// - last_updated: timestamp
```

## Testing

Run tests:

```bash
node shared/multi-dimensional-learning.test.cjs
```

Output:
```
MultiDimensionalStrategy Tests
  ✓ should create strategy with dimensions
  ✓ should generate composite key
  ✓ should handle wildcard dimensions
  ✓ should generate fallback keys in specificity order

MultiDimensionalLearning Tests
  ✓ should select default strategy when none exist
  ✓ should update strategy with Thompson Sampling
  ✓ should track multiple strategies independently
  ✓ should update multiple success rates correctly
  ✓ should learn from code review tasks
  ✓ should support multi-task learning

Results: 10 passed, 0 failed
```

## Example Scenarios

### Scenario 1: Code Review Learning

Task: Review Java code

Initial state: No learning data
- Uses defaults: Sonnet, direct, single, no verification

After 5 reviews:
- Sonnet + chain_of_thought: 4/5 success (avg: 0.88)
- Opus + chain_of_thought: 1/1 success (avg: 0.95, low confidence)
- Haiku + direct: 0/1 success (avg: 0.25)

Next strategy selection:
- Selects Opus (highest sample from Beta(2,1))
- Falls back to Sonnet if cost constraint violated
- Gradually learns Opus is better for Java reviews

### Scenario 2: Multi-Task Learning

Same model/prompt but different tasks:

```
code_review:java:opus:cot:consensus:* → avg_reward: 0.94
code_review:python:opus:cot:consensus:* → avg_reward: 0.71
code_test:java:opus:cot:consensus:* → avg_reward: 0.65
```

System learns:
- Opus + CoT excellent for Java code review
- Opus + CoT okay for Python code review
- Opus + CoT mediocre for Java testing

Future selections adapt per task!

### Scenario 3: Constraint-Based Selection

Query: `selectStrategy('code_solve', 'complex', { max_cost: 0.02 })`

Options learned:
- Opus (best): $0.05 cost → excluded
- Sonnet (good): $0.02 cost → included
- Haiku (acceptable): $0.005 cost → preferred

Returns: Haiku (meets constraints, acceptable quality)

## Implementation Details

### MultiDimensionalStrategy Class

Represents a single strategy as a composition of 6 dimensions.

```javascript
const strategy = new MultiDimensionalStrategy({
  capability: 'code_review',
  task_type: 'java',
  model: 'opus',
  prompt_style: 'cot',
  orchestration: 'consensus',
  verification: 'refute'
});

strategy.getKey()           // → 'code_review:java:opus:cot:consensus:refute'
strategy.getFallbackKeys()  // → [exact, no-verif, no-orch, ...]
```

### MultiDimensionalLearning Class

Main learning engine managing Thompson Sampling across all dimensions.

```javascript
const learning = new MultiDimensionalLearning();

// All methods are async
await learning.selectStrategy(...)
await learning.updateStrategyBandit(...)
await learning.getTopStrategies(...)
await learning.getAnalytics(...)
await learning.exportStrategies(...)
```

## Performance Characteristics

- **Select strategy**: ~1ms (database query)
- **Update learning**: ~5ms (insert + beta recalculation)
- **Get top strategies**: ~10ms (pattern matching + sort)
- **Analytics**: ~20ms (aggregation query)

All operations are non-blocking async.

## Future Enhancements

1. **Cost tracking**: Integrate with cost tracker to penalize expensive models
2. **Latency tracking**: Consider actual execution time in selection
3. **Per-user learning**: Separate strategies for different team members
4. **Temporal decay**: Down-weight old experiences (concept drift)
5. **Regret minimization**: Track cumulative regret across decisions
6. **Transfer learning**: Reuse strategies across similar capabilities

## Troubleshooting

### Strategy not improving

Check that:
1. Rewards are being provided (not all 1.0 or 0.0)
2. Success flags match reward levels
3. Database is updating (`SELECT * FROM workflow.strategy_performance`)
4. Sufficient samples exist (min 5 per dimension)

### Exploration vs exploitation imbalance

Thompson Sampling automatically handles this:
- High variance early (few samples) → exploration
- Low variance late (many samples) → exploitation

If stuck on suboptimal strategy:
- Add more trials (action: execute more)
- Increase reward variance (evaluation: more sensitive scoring)

### Constraint violations

If a strategy violates constraints:
- Check constraint definition
- Verify model costs in database
- Use more specific task_type for finer control

## References

- Thompson Sampling: https://en.wikipedia.org/wiki/Thompson_sampling
- Multi-armed bandit: https://en.wikipedia.org/wiki/Multi-armed_bandit
- Beta distribution: https://en.wikipedia.org/wiki/Beta_distribution
