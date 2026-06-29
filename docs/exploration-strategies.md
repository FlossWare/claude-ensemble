# Exploration Strategies for Thompson Sampling

## Overview

The learning system supports three exploration strategies for balancing exploration (trying new strategies) vs exploitation (using known-good strategies):

1. **Thompson Sampling** (default) - Bayesian approach, samples from posterior distribution
2. **UCB (Upper Confidence Bound)** - Deterministic exploration bonus for underexplored strategies
3. **Epsilon-Greedy** - Simple random vs best tradeoff

## Quick Start

### Via Environment Variable

```bash
# Thompson Sampling (default)
EXPLORATION_METHOD=thompson node your-workflow.js

# UCB with default C=2.0
EXPLORATION_METHOD=ucb node your-workflow.js

# Epsilon-Greedy with default ε=0.1
EXPLORATION_METHOD=epsilon-greedy node your-workflow.js
```

### Via Code

```javascript
const { getStrategyPerformance } = require('./learning/postgres-adapter');
const sp = getStrategyPerformance();

// Thompson Sampling (default)
const strategy = await sp.select('thompson');

// UCB with custom exploration constant
const strategy = await sp.select('ucb', { explorationConstant: 2.0 });

// Epsilon-Greedy with custom epsilon
const strategy = await sp.select('epsilon-greedy', { epsilon: 0.1 });

// Use environment variable
const strategy = await sp.select(); // Uses EXPLORATION_METHOD env var
```

## Thompson Sampling (Default)

**When to use:**
- General-purpose exploration/exploitation
- Want probabilistic exploration based on uncertainty
- Have moderate amounts of data (>10 trials per strategy)

**How it works:**
1. Maintains Beta distribution for each strategy: `Beta(α, β)`
   - `α = 1 + successes`
   - `β = 1 + failures`
2. Samples from each distribution
3. Selects strategy with highest sample

**Characteristics:**
- **Exploration:** Naturally explores uncertain strategies (wide distributions)
- **Exploitation:** Converges to best strategy as data accumulates
- **Adaptive:** Exploration decreases as confidence increases

**Example:**
```javascript
// Record outcomes
await sp.record('model-a', true, 0.9);  // Success
await sp.record('model-a', true, 0.85); // Success
await sp.record('model-b', false, 0.3); // Failure

// Select next strategy
const selected = await sp.selectThompson();
// likely selects 'model-a' but occasionally tries 'model-b'
```

**Pros:**
- Bayesian approach, theoretically sound
- Good balance of exploration/exploitation
- No hyperparameters to tune

**Cons:**
- Can get stuck if early bad luck biases against good strategy
- Slower to explore than UCB in some cases

---

## UCB (Upper Confidence Bound)

**When to use:**
- Need deterministic exploration (reproducible results)
- Worried about getting stuck on local optima
- Want to ensure all strategies get tried periodically

**How it works:**

Formula: `UCB = exploitation_score + C × √(ln(total_trials) / trials)`

Where:
- `exploitation_score = α / (α + β)` (empirical success rate)
- `C` = exploration constant (default 2.0)
- `total_trials` = sum of all strategy trials
- `trials = α + β - 2` (this strategy's trial count)

**Characteristics:**
- **Exploration bonus:** Grows with uncertainty (fewer trials)
- **Deterministic:** Same data → same selection
- **Hyperparameter:** `C` controls exploration vs exploitation

**Example:**
```javascript
// High-reward but underexplored strategy gets bonus
await sp.record('model-a', true, 0.9);  // 1 success, 0 failures
await sp.record('model-b', true, 0.6);  // 50 successes, 50 failures

const selected = await sp.selectUCB(2.0);
// Likely selects 'model-a' due to exploration bonus
// despite 'model-b' having more data
```

**Tuning exploration constant C:**
- `C = 0.5` - Conservative exploration (mostly exploit)
- `C = 1.0` - Balanced (moderate exploration)
- `C = 2.0` - Default (strong exploration)
- `C = 5.0` - Aggressive exploration (rarely exploit)

**Pros:**
- Prevents getting stuck on local optima
- Deterministic (reproducible)
- Guarantees all strategies get tried

**Cons:**
- Requires tuning `C` hyperparameter
- Can over-explore if `C` too high
- Less theoretically grounded than Thompson Sampling

---

## Epsilon-Greedy

**When to use:**
- Simple baseline for comparison
- Want explicit exploration percentage
- Need fast, low-overhead selection

**How it works:**

With probability `ε`:
- **Explore:** Select random strategy (from strategies with ≥minTrials)

With probability `1 - ε`:
- **Exploit:** Select best average reward

**Example:**
```javascript
// ε = 0.1 (10% exploration, 90% exploitation)
// minTrials = 3 (only explore strategies with ≥3 trials)
const selected = await sp.selectEpsilonGreedy(0.1, 3);
// 90% chance: selects best avg_reward
// 10% chance: selects random strategy (with ≥3 trials)
```

**Tuning epsilon ε:**
- `ε = 0.01` - Mostly exploit (1% exploration)
- `ε = 0.05` - Conservative exploration (5%)
- `ε = 0.10` - Default (10% exploration)
- `ε = 0.20` - Aggressive exploration (20%)

**Tuning minTrials:**
- `minTrials = 0` - No filter (explore all strategies, even untested)
- `minTrials = 3` - Default (skip strategies with <3 trials)
- `minTrials = 10` - Conservative (only explore well-tested strategies)

**Why minTrials matters:**
Without a minimum trials filter, epsilon-greedy wastes exploration on untested strategies. Example:
- 100 strategies, 99 untested (0 trials), 1 good strategy (100 trials)
- ε=0.1: 10% exploration → likely picks an untested strategy (wasted)
- With minTrials=3: 10% exploration → only picks from tested strategies (useful)

**Pros:**
- Simple, easy to understand
- Explicit control over exploration rate
- Fast execution
- minTrials filter prevents wasted exploration

**Cons:**
- Doesn't consider uncertainty (unlike Thompson Sampling)
- Fixed exploration rate (not adaptive)
- May explore too much/too little

---

## Comparison Table

| Method | Exploration | Deterministic | Hyperparameters | Best For |
|--------|-------------|---------------|-----------------|----------|
| **Thompson** | Adaptive (uncertainty-based) | No | None | General use, moderate data |
| **UCB** | Deterministic bonus | Yes | `C` (default 2.0) | Avoiding local optima, reproducibility |
| **Epsilon-Greedy** | Random (ε% of time) | No | `ε` (default 0.1) | Simple baseline, explicit control |

---

## A/B Testing Workflow

To compare exploration methods empirically:

**IMPORTANT:** A/B tests MUST use controlled conditions to prevent bias. Sequential testing (method A then method B on live data) is invalid because:
- Earlier methods affect database state (bandit parameters)
- Time-based confounds (system load, external factors)
- Non-stationary environments (strategies improve over time)

**CORRECT A/B Test Design (Snapshot + Restore):**

```javascript
const { getDB, getStrategyPerformance } = require('./learning/postgres-adapter');
const db = getDB();
const sp = getStrategyPerformance();

async function runABTest() {
  const results = {};
  
  // Test each method starting from same initial state
  for (const method of ['thompson', 'ucb', 'epsilon-greedy']) {
    // Snapshot current database state (before testing this method)
    const snapshot = await db.query('SELECT * FROM workflow.strategy_performance');
    
    // Run 100 trials with this method
    process.env.EXPLORATION_METHOD = method;
    const methodResults = [];
    
    for (let i = 0; i < 100; i++) {
      const strategy = await sp.select();
      const result = await runTask(strategy.strategy);
      
      // Record outcome
      await sp.record(strategy.strategy, result.success, result.reward);
      
      // Track for this method
      methodResults.push({
        quality_score: result.reward,
        success: result.success
      });
    }
    
    // Aggregate results
    results[method] = {
      trials: methodResults.length,
      avg_quality: methodResults.reduce((sum, r) => sum + r.quality_score, 0) / methodResults.length,
      success_rate: methodResults.filter(r => r.success).length / methodResults.length
    };
    
    // Restore original state (undo this method's changes)
    await db.query('DELETE FROM workflow.strategy_performance');
    for (const row of snapshot) {
      await db.query(`
        INSERT INTO workflow.strategy_performance 
        (strategy, successes, failures, alpha, beta, total_reward, avg_reward, last_updated, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
      `, [row.strategy, row.successes, row.failures, row.alpha, row.beta, row.total_reward, row.avg_reward, row.last_updated, row.created_at]);
    }
  }
  
  console.table(results);
  return results;
}
```

**Alternative: Interleaved Testing (Production-Safe)**

For live production testing, interleave methods randomly:

```javascript
async function runInterleavedABTest(totalTrials = 300) {
  const methods = ['thompson', 'ucb', 'epsilon-greedy'];
  const results = { thompson: [], ucb: [], 'epsilon-greedy': [] };
  
  for (let i = 0; i < totalTrials; i++) {
    // Randomly select method for this trial
    const method = methods[Math.floor(Math.random() * methods.length)];
    
    const strategy = await sp.select(method);
    const result = await runTask(strategy.strategy);
    
    // Record outcome (affects bandit state for ALL methods)
    await sp.record(strategy.strategy, result.success, result.reward);
    
    // Track per-method performance
    results[method].push({
      quality_score: result.reward,
      success: result.success
    });
  }
  
  // Aggregate results
  const summary = {};
  for (const method of methods) {
    const trials = results[method];
    summary[method] = {
      trials: trials.length,
      avg_quality: trials.reduce((sum, r) => sum + r.quality_score, 0) / trials.length,
      success_rate: trials.filter(r => r.success).length / trials.length
    };
  }
  
  console.table(summary);
}
```

**Statistical Significance Testing:**

```javascript
// After collecting results, test for statistical significance
function calculateConfidenceInterval(samples, confidence = 0.95) {
  const n = samples.length;
  const mean = samples.reduce((sum, x) => sum + x, 0) / n;
  const stddev = Math.sqrt(samples.reduce((sum, x) => sum + (x - mean) ** 2, 0) / n);
  const z = 1.96; // 95% confidence
  const margin = z * (stddev / Math.sqrt(n));
  
  return {
    mean,
    lower: mean - margin,
    upper: mean + margin,
    stddev
  };
}

// Compare methods
const thompsonCI = calculateConfidenceInterval(results.thompson.map(r => r.quality_score));
const ucbCI = calculateConfidenceInterval(results.ucb.map(r => r.quality_score));

console.log('Thompson:', thompsonCI);
console.log('UCB:', ucbCI);

// Check for overlap (non-overlapping = statistically significant difference)
if (thompsonCI.upper < ucbCI.lower) {
  console.log('UCB is statistically significantly better (95% confidence)');
} else if (ucbCI.upper < thompsonCI.lower) {
  console.log('Thompson is statistically significantly better (95% confidence)');
} else {
  console.log('No statistically significant difference detected');
}
```

---

## Edge Cases

### 1. Empty Database (No Strategies)

All methods return `null`:

```javascript
const result = await sp.select('thompson');
// => null
```

### 2. Single Strategy

All methods select the only available strategy:

```javascript
await sp.record('only-strategy', true, 0.8);
const result = await sp.select('ucb');
// => { strategy: 'only-strategy', ... }
```

### 3. New Strategy (No Trials)

- **Thompson:** Samples from `Beta(1, 1)` (uniform prior)
- **UCB:** Skipped (requires >0 trials)
- **Epsilon-Greedy:** Can be selected during exploration

### 4. Division by Zero

UCB handles gracefully using `NULLIF()` and `GREATEST()`:

```sql
SQRT(LN(GREATEST(NULLIF(total_trials, 0), 1)) / GREATEST(trials, 1))
```

---

## Database Schema

```sql
CREATE TABLE workflow.strategy_performance (
  strategy VARCHAR(255) PRIMARY KEY,
  successes INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0,
  alpha NUMERIC NOT NULL DEFAULT 1.0,  -- Beta(α, β) parameter
  beta NUMERIC NOT NULL DEFAULT 1.0,   -- Beta(α, β) parameter
  total_reward NUMERIC NOT NULL DEFAULT 0.0,
  avg_reward NUMERIC NOT NULL DEFAULT 0.0,
  last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## API Reference

### `StrategyPerformance.select(method, options)`

Select next strategy using specified method.

**Parameters:**
- `method` (string, optional) - 'thompson' | 'ucb' | 'epsilon-greedy' (default: `EXPLORATION_METHOD` env var or 'thompson')
- `options` (object, optional)
  - `explorationConstant` (number) - UCB exploration constant (default: 2.0)
  - `epsilon` (number) - Epsilon-Greedy exploration probability (default: 0.1)

**Returns:** `Promise<Object>` - Selected strategy with metadata

**Example:**
```javascript
const strategy = await sp.select('ucb', { explorationConstant: 1.5 });
```

### `StrategyPerformance.selectThompson()`

Select using Thompson Sampling.

**Returns:** `Promise<Object>` - Selected strategy

### `StrategyPerformance.selectUCB(explorationConstant = 2.0)`

Select using UCB.

**Parameters:**
- `explorationConstant` (number) - Exploration constant C (default: 2.0)

**Returns:** `Promise<Object>` - Selected strategy with UCB score

### `StrategyPerformance.selectEpsilonGreedy(epsilon = 0.1, minTrials = 3)`

Select using Epsilon-Greedy.

**Parameters:**
- `epsilon` (number) - Exploration probability 0-1 (default: 0.1)
- `minTrials` (number) - Minimum trials before exploring (default: 3, prevents wasting exploration on untested strategies)

**Returns:** `Promise<Object>` - Selected strategy

### `StrategyPerformance.record(strategy, success, reward)`

Record outcome and update Thompson Sampling parameters.

**Parameters:**
- `strategy` (string) - Strategy name
- `success` (boolean) - Whether task succeeded
- `reward` (number) - Reward value 0.0-1.0

---

## Testing

Run comprehensive test suite:

```bash
node learning/test-exploration-strategies.js
```

Tests cover:
- Thompson Sampling behavior
- UCB exploration bonus
- Epsilon-Greedy random/best tradeoff
- Edge cases (empty DB, single strategy, new strategies)
- Method selection API
- Record + Select integration

---

## References

- **Thompson Sampling:** Chapelle & Li (2011) - "An Empirical Evaluation of Thompson Sampling"
- **UCB:** Auer et al. (2002) - "Finite-time Analysis of the Multiarmed Bandit Problem"
- **Epsilon-Greedy:** Sutton & Barto (2018) - "Reinforcement Learning: An Introduction"

---

## Migration from Pure Thompson Sampling

Old code:
```javascript
const strategies = await sp.getAllStrategies();
// ... manual Thompson Sampling logic ...
```

New code:
```javascript
// Drop-in replacement
const strategy = await sp.select('thompson');
```

**Backward compatible:** Default behavior unchanged (Thompson Sampling).
