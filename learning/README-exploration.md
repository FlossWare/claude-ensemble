# UCB Exploration for Thompson Sampling

## Summary

Added **Upper Confidence Bound (UCB)** and **Epsilon-Greedy** exploration methods to the Thompson Sampling bandit system. This prevents getting stuck on local optima by giving exploration bonuses to underexplored strategies.

## Problem Solved

**Before:** Pure Thompson Sampling could get stuck if early bad luck biased against a good strategy.

Example:
- Gemini gets unlucky early (0/5 successes) → low alpha, never selected again
- Meanwhile Gemini API improves, but we never discover this

**After:** UCB adds exploration bonus to occasionally retry low-usage models, even when Thompson Sampling has high confidence in another strategy.

## Implementation

### Files Created

1. **`learning/postgres-adapter.js`** - Enhanced with UCB methods
   - `selectThompson()` - Bayesian sampling (original)
   - `selectUCB(C)` - Upper Confidence Bound with exploration bonus
   - `selectEpsilonGreedy(ε)` - Simple random vs best tradeoff
   - `select(method, options)` - Unified API

2. **`learning/test-exploration-strategies.js`** - Comprehensive test suite
   - Thompson Sampling behavior validation
   - UCB exploration bonus verification
   - Epsilon-Greedy random/best tradeoff
   - Edge cases (empty DB, single strategy, new strategies)
   - Method selection API testing
   - Record + Select integration

3. **`learning/example-exploration.js`** - Interactive demo
   - Simulates 4 models with different performance
   - Compares all 3 exploration methods
   - Shows when to use each method

4. **`docs/exploration-strategies.md`** - Complete documentation
   - When to use each method
   - Hyperparameter tuning guide
   - A/B testing workflow
   - API reference

### Database Schema

```sql
-- Already existed, no changes needed
CREATE TABLE workflow.strategy_performance (
  strategy VARCHAR(255) PRIMARY KEY,
  successes INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0,
  alpha NUMERIC NOT NULL DEFAULT 1.0,
  beta NUMERIC NOT NULL DEFAULT 1.0,
  total_reward NUMERIC NOT NULL DEFAULT 0.0,
  avg_reward NUMERIC NOT NULL DEFAULT 0.0,
  last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Supporting tables created in `workflow` schema:
- `workflow.execution_summary` - Model execution logs
- `workflow.cost_entries` - Cost tracking
- `workflow.experiences` - Experience memory (continual learning)

## Usage

### Quick Start

```javascript
const { getStrategyPerformance } = require('./learning/postgres-adapter');
const sp = getStrategyPerformance();

// Thompson Sampling (default, backward compatible)
const strategy = await sp.select('thompson');

// UCB (exploration bonus for underexplored strategies)
const strategy = await sp.select('ucb', { explorationConstant: 2.0 });

// Epsilon-Greedy (simple random vs best)
const strategy = await sp.select('epsilon-greedy', { epsilon: 0.1 });
```

### Environment Variable

```bash
# Set default exploration method
EXPLORATION_METHOD=ucb node your-workflow.js
```

### Example Output

```
Thompson Sampling (100 trials):
  opus: 57%
  sonnet: 25%
  gemini: 18%  ← Explores occasionally
  haiku: 0%

UCB (100 trials):
  gemini: 100%  ← Aggressive exploration bonus (only 3 trials)
  opus: 0%
  sonnet: 0%
  haiku: 0%

Epsilon-Greedy (100 trials):
  opus: 84%
  gemini: 7%
  sonnet: 6%
  haiku: 3%  ← Wastes exploration on bad strategy
```

## Testing

### Run Test Suite

```bash
node learning/test-exploration-strategies.js
```

**Expected output:**
```
✅ PASS: Thompson Sampling should favor high-success strategy >70%
✅ PASS: UCB should select underexplored high-reward strategy
✅ PASS: UCB exploration bonus should be positive
✅ PASS: Epsilon-Greedy should exploit best strategy >60%
✅ PASS: All edge cases handled correctly
✅ ALL TESTS PASSED
```

### Run Interactive Demo

```bash
node learning/example-exploration.js
```

Shows real-world comparison of all 3 methods.

## When to Use Each Method

### Thompson Sampling (Default)

**Use for:**
- Production workflows (exploits known-good strategies)
- General-purpose exploration/exploitation
- When you have moderate data (>10 trials per strategy)

**Characteristics:**
- Bayesian approach, theoretically sound
- Naturally explores uncertain strategies
- No hyperparameters to tune

**Example:**
```javascript
const strategy = await sp.select('thompson');
```

### UCB (Upper Confidence Bound)

**Use for:**
- Suspecting API improvements (e.g., Gemini got better)
- Ensuring all strategies get tried periodically
- Deterministic results (reproducibility)

**Characteristics:**
- Exploration bonus = `C × √(ln(total_trials) / trials)`
- Deterministic (same data → same selection)
- Hyperparameter `C` controls exploration strength

**Tuning C:**
- `C = 0.5` - Conservative (mostly exploit)
- `C = 2.0` - Default (strong exploration)
- `C = 5.0` - Aggressive (rarely exploit)

**Example:**
```javascript
const strategy = await sp.select('ucb', { explorationConstant: 2.0 });
```

### Epsilon-Greedy

**Use for:**
- Simple baseline for comparison
- Explicit exploration percentage
- Fast, low-overhead selection

**Characteristics:**
- `ε%` of time: random choice (explore)
- `(1-ε)%` of time: best known (exploit)

**Tuning ε:**
- `ε = 0.05` - Conservative (5% exploration)
- `ε = 0.10` - Default (10% exploration)
- `ε = 0.20` - Aggressive (20% exploration)

**Example:**
```javascript
const strategy = await sp.select('epsilon-greedy', { epsilon: 0.1 });
```

## Comparison Table

| Method | Exploration | Deterministic | Hyperparameters | Best For |
|--------|-------------|---------------|-----------------|----------|
| **Thompson** | Adaptive (uncertainty-based) | No | None | Production, general use |
| **UCB** | Deterministic bonus | Yes | `C` (default 2.0) | Avoiding local optima |
| **Epsilon-Greedy** | Random (ε% of time) | No | `ε` (default 0.1) | Simple baseline |

## A/B Testing

Compare methods empirically:

```javascript
const results = {};

for (const method of ['thompson', 'ucb', 'epsilon-greedy']) {
  process.env.EXPLORATION_METHOD = method;
  results[method] = { successes: 0, total: 0 };

  for (let i = 0; i < 100; i++) {
    const strategy = await sp.select();
    const result = await runTask(strategy.strategy);
    await sp.record(strategy.strategy, result.success, result.reward);

    if (result.success) results[method].successes++;
    results[method].total++;
  }
}

console.table(results);
```

## Edge Cases Handled

1. **Empty database** → Returns `null`
2. **Single strategy** → Returns only available strategy
3. **New strategy (no trials)** → UCB skips, Thompson samples from uniform prior
4. **Division by zero** → SQL uses `NULLIF()` and `GREATEST()` guards
5. **Invalid parameters** → Throws validation errors

## API Reference

### `select(method, options)`

Select strategy using specified method.

**Parameters:**
- `method` (string, optional) - 'thompson' | 'ucb' | 'epsilon-greedy' (default: env var or 'thompson')
- `options` (object, optional)
  - `explorationConstant` (number) - UCB C (default: 2.0)
  - `epsilon` (number) - Epsilon-Greedy ε (default: 0.1)

**Returns:** `Promise<Object>` - Selected strategy with metadata

### `selectThompson()`

Select using Thompson Sampling.

**Returns:** `Promise<Object>`

### `selectUCB(explorationConstant = 2.0)`

Select using UCB.

**Returns:** `Promise<Object>` - Includes `ucb_score`, `exploitation_score`, `exploration_bonus`

### `selectEpsilonGreedy(epsilon = 0.1)`

Select using Epsilon-Greedy.

**Returns:** `Promise<Object>`

### `record(strategy, success, reward)`

Record outcome and update Thompson Sampling parameters.

**Parameters:**
- `strategy` (string) - Strategy name
- `success` (boolean) - Whether task succeeded
- `reward` (number) - Reward value 0.0-1.0

## Migration Guide

### Old Code (Manual Thompson Sampling)

```javascript
const strategies = await sp.getAllStrategies();
// ... manual Beta sampling logic ...
```

### New Code (Drop-in Replacement)

```javascript
// Backward compatible - default behavior unchanged
const strategy = await sp.select('thompson');
```

## Performance

- **Thompson Sampling:** O(n) where n = number of strategies
- **UCB:** O(n log n) due to SQL ORDER BY (negligible for <1000 strategies)
- **Epsilon-Greedy:** O(n log n) due to SQL ORDER BY (negligible)

All methods use database indexes for fast lookups.

## References

- **Thompson Sampling:** Chapelle & Li (2011)
- **UCB:** Auer et al. (2002) - "Finite-time Analysis of the Multiarmed Bandit Problem"
- **Epsilon-Greedy:** Sutton & Barto (2018) - "Reinforcement Learning"

## Troubleshooting

### UCB always selects same strategy

Increase exploration constant: `selectUCB(5.0)`

### Thompson Sampling stuck on suboptimal strategy

Switch to UCB temporarily to force exploration, then return to Thompson

### Epsilon-Greedy wastes too much on bad strategies

Decrease epsilon: `selectEpsilonGreedy(0.05)`

### Getting "Unknown exploration method" error

Use valid method name: 'thompson', 'ucb', or 'epsilon-greedy' (case-insensitive)

## Future Enhancements

Potential additions (not implemented):

1. **UCB1-Tuned** - Variance-aware exploration bonus
2. **Thompson Sampling variants** - Non-uniform priors
3. **Contextual bandits** - Strategy selection based on task features
4. **Sliding window** - Forget old data to adapt to changing APIs
5. **Multi-objective** - Optimize for both quality and cost

## License

Part of the Claude Global Skills project.
