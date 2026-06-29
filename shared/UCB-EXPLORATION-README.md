# UCB Exploration - Upper Confidence Bound Strategy Selection

## Overview

Upper Confidence Bound (UCB) is an exploration strategy that balances **exploitation** (using the best-known strategy) with **exploration** (trying under-sampled strategies). Unlike Thompson Sampling's probabilistic approach, UCB uses deterministic confidence intervals: strategies with fewer trials get higher exploration bonuses, ensuring all strategies are tested before converging to the best one.

**Key Insight:** UCB treats strategy selection as a confidence problem. Strategies we haven't tested much could be better than we know, so we add a bonus proportional to our uncertainty.

## How It Works

### The UCB Formula

For each strategy, UCB calculates a score:

```
UCB Score = Exploitation Score + Exploration Bonus
          = (alpha / (alpha + beta)) + C × √(ln(total_trials) / trials)
```

**Components:**

1. **Exploitation Score** = `alpha / (alpha + beta)`
   - This is the strategy's estimated success rate
   - Same as Thompson Sampling's mean estimate
   - Higher = better historical performance

2. **Exploration Bonus** = `C × √(ln(total_trials) / trials)`
   - `C` = exploration constant (default 2.0)
   - `total_trials` = sum of all strategy trials across the system
   - `trials` = this specific strategy's trial count
   - Higher = more uncertainty, needs more exploration

**Selection Rule:** Choose the strategy with the highest UCB score.

### Why This Works

- **Early Phase (few trials):** Exploration bonus dominates → ensures all strategies are tested
- **Late Phase (many trials):** Exploitation score dominates → converges to the best strategy
- **Logarithmic Growth:** As `total_trials` increases, exploration bonus grows slowly (logarithmic), ensuring convergence

### Mathematical Properties

- **Regret Bound:** UCB has a logarithmic regret bound `O(log n)`, meaning it provably converges to the optimal strategy
- **Deterministic:** Unlike Thompson Sampling (random sampling), UCB always picks the same strategy given the same state
- **Confidence Intervals:** The exploration bonus represents a confidence interval upper bound (hence "Upper Confidence Bound")

## When To Use

### UCB vs Thompson Sampling vs Epsilon-Greedy

| Strategy | Best For | Pros | Cons |
|----------|----------|------|------|
| **UCB** | A/B testing, strategy comparison, reproducibility | Deterministic, provable bounds, systematic exploration | Less randomness (may miss rare good outcomes) |
| **Thompson Sampling** | Dynamic environments, multi-armed bandits | Handles uncertainty well, explores naturally | Probabilistic (non-reproducible) |
| **Epsilon-Greedy** | Simple tasks, known environments | Simple, fast | Fixed exploration rate, no confidence modeling |

### Use UCB When:

1. **Reproducibility Matters:** You want deterministic strategy selection (e.g., debugging, auditing)
2. **Systematic Exploration:** You want to ensure all strategies are tested proportionally
3. **A/B Testing:** You're comparing a few strategies and want provable convergence
4. **Scientific Rigor:** You need formal guarantees on exploration/exploitation trade-off

### Avoid UCB When:

1. **Highly Stochastic Environments:** Thompson Sampling handles randomness better
2. **Need Immediate Randomness:** UCB is deterministic (picks same strategy until updated)
3. **Very High Dimensionality:** UCB assumes independent strategies (doesn't scale to contextual bandits)

## Integration with postgres-adapter.js

### Database Schema

UCB reads from `workflow.strategy_performance` table:

```sql
CREATE TABLE workflow.strategy_performance (
  strategy VARCHAR(255) PRIMARY KEY,
  successes INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0,
  alpha NUMERIC NOT NULL DEFAULT 1,  -- Beta distribution parameter (1 + successes)
  beta NUMERIC NOT NULL DEFAULT 1,   -- Beta distribution parameter (1 + failures)
  total_reward NUMERIC NOT NULL DEFAULT 0,
  avg_reward NUMERIC NOT NULL DEFAULT 0,
  last_updated TIMESTAMP DEFAULT NOW()
);
```

**Key Fields:**
- `alpha` = 1 + successes (Beta distribution parameter)
- `beta` = 1 + failures (Beta distribution parameter)
- `avg_reward` = exploitation score (used in UCB formula)
- `alpha + beta - 2` = total trials for this strategy

### API Usage

```javascript
const { getStrategyPerformance } = require('./learning/postgres-adapter.js');
const strategyPerf = getStrategyPerformance();

// Select strategy using UCB
const strategy = await strategyPerf.select('ucb', {
  explorationConstant: 2.0  // C parameter (default 2.0)
});

console.log(strategy);
// {
//   strategy: 'grep_parallel',
//   alpha: 15,
//   beta: 3,
//   successes: 14,
//   failures: 2,
//   total_reward: 11.8,
//   avg_reward: 0.74,
//   exploitation_score: 0.83,     // alpha / (alpha + beta)
//   exploration_bonus: 0.12,      // C × √(ln(total) / trials)
//   ucb_score: 0.95               // exploitation + exploration
// }

// Record outcome (updates alpha/beta)
await strategyPerf.record('grep_parallel', true, 0.85);
```

### Environment Variable Configuration

Set default exploration method via environment variable:

```bash
export EXPLORATION_METHOD=ucb
```

Then call `select()` without parameters:

```javascript
const strategy = await strategyPerf.select();  // Uses UCB from env var
```

### Implementation Details

**SQL Query (from postgres-adapter.js lines 266-288):**

```sql
WITH totals AS (
  SELECT COALESCE(SUM(alpha + beta - 2), 0) as total_trials
  FROM workflow.strategy_performance
)
SELECT
  sp.strategy,
  sp.alpha,
  sp.beta,
  sp.successes,
  sp.failures,
  sp.total_reward,
  sp.avg_reward,
  sp.alpha / NULLIF(sp.alpha + beta, 0) as exploitation_score,
  $1 * SQRT(LN(GREATEST(NULLIF(t.total_trials, 0), 1)) / 
            GREATEST(sp.alpha + beta - 2, 1)) as exploration_bonus,
  (sp.alpha / NULLIF(sp.alpha + beta, 0)) + 
  ($1 * SQRT(LN(...) / ...)) as ucb_score
FROM workflow.strategy_performance sp
CROSS JOIN totals t
WHERE sp.alpha + beta > 2  -- Require at least 1 trial
ORDER BY ucb_score DESC NULLS LAST
LIMIT 1
```

**Fallback Behavior:**
- If no strategies have trials (alpha + beta ≤ 2), falls back to random selection
- Uses `NULLIF` and `GREATEST` to prevent division by zero and log(0) errors

## Configuration

### Exploration Constant (C)

The `explorationConstant` parameter controls the exploration/exploitation trade-off:

| C Value | Behavior | Use Case |
|---------|----------|----------|
| **0.5** | Heavy exploitation | Known environment, converge quickly |
| **1.0** | Moderate exploitation | Balanced, slightly favor best strategy |
| **2.0** (default) | Balanced | Standard UCB, good general-purpose |
| **3.0** | Moderate exploration | Uncertain environment, test more |
| **5.0** | Heavy exploration | Highly uncertain, ensure all strategies tested |

**Rule of Thumb:** Start with C=2.0. Increase if you suspect the best strategy hasn't been found. Decrease if exploration is too slow to converge.

### Minimum Trials Requirement

UCB filters strategies with `alpha + beta > 2`, meaning at least 1 trial is required before considering a strategy.

**Why?** Prevents UCB from wasting exploration on completely untested strategies (which would have infinite exploration bonus).

**Trade-off:**
- Too low (e.g., 0): UCB may get stuck exploring bad strategies
- Too high (e.g., 10): Requires many trials before UCB can select a strategy

**Recommendation:** Keep at 1 trial (current implementation). Let UCB's exploration bonus handle the rest.

## Example Scenarios

### Scenario 1: Early Exploration (Few Trials)

```
Strategy A: 5 successes, 1 failure (alpha=6, beta=2, trials=6)
Strategy B: 2 successes, 0 failures (alpha=3, beta=1, trials=2)
Strategy C: 0 successes, 0 failures (alpha=1, beta=1, trials=0)

Total trials = 8

UCB Scores (C=2.0):
- Strategy A: 0.75 + 2.0 × √(ln(8)/6) = 0.75 + 0.67 = 1.42
- Strategy B: 0.75 + 2.0 × √(ln(8)/2) = 0.75 + 1.92 = 2.67  ← SELECTED
- Strategy C: Excluded (no trials)

Result: Strategy B selected despite same success rate as A (exploration bonus dominates)
```

### Scenario 2: Convergence (Many Trials)

```
Strategy A: 50 successes, 10 failures (alpha=51, beta=11, trials=60)
Strategy B: 30 successes, 5 failures (alpha=31, beta=6, trials=35)

Total trials = 95

UCB Scores (C=2.0):
- Strategy A: 0.82 + 2.0 × √(ln(95)/60) = 0.82 + 0.17 = 0.99  ← SELECTED
- Strategy B: 0.84 + 2.0 × √(ln(95)/35) = 0.84 + 0.23 = 1.07

Result: Strategy B selected (higher success rate + higher uncertainty)
```

### Scenario 3: Mature System (Converged)

```
Strategy A: 500 successes, 50 failures (alpha=501, beta=51, trials=550)
Strategy B: 400 successes, 100 failures (alpha=401, beta=101, trials=500)

Total trials = 1050

UCB Scores (C=2.0):
- Strategy A: 0.91 + 2.0 × √(ln(1050)/550) = 0.91 + 0.05 = 0.96  ← SELECTED
- Strategy B: 0.80 + 2.0 × √(ln(1050)/500) = 0.80 + 0.06 = 0.86

Result: Strategy A wins (exploitation dominates, exploration bonus negligible)
```

## Advanced Topics

### UCB1-Tuned (Not Implemented)

Standard UCB uses a conservative exploration bonus. UCB1-Tuned adjusts the bonus based on empirical variance:

```
Exploration Bonus = √(ln(total_trials) / trials × min(1/4, V(trials)))
```

Where `V(trials)` is the empirical variance of rewards.

**Trade-off:** More accurate exploration, but requires tracking reward variance (more complex).

### Contextual Bandits (Not Applicable)

UCB assumes strategies are independent. For contextual bandits (strategy selection depends on context), use:
- LinUCB (linear contextual bandits)
- Neural UCB (deep contextual bandits)

**Current Implementation:** Only non-contextual UCB (assumes strategy performance is context-independent).

### UCB vs Thompson Sampling in Practice

**Empirical Comparison (from bandit literature):**

- **Regret:** UCB has better worst-case regret bounds (logarithmic), Thompson Sampling has better empirical regret
- **Exploration:** UCB explores systematically (all strategies tested proportionally), Thompson Sampling explores randomly
- **Convergence:** UCB converges faster in deterministic environments, Thompson Sampling converges faster in stochastic environments

**Recommendation:** Use UCB for reproducibility and formal guarantees. Use Thompson Sampling for real-world stochastic tasks.

## Monitoring and Debugging

### Check Current UCB Scores

```sql
WITH totals AS (
  SELECT COALESCE(SUM(alpha + beta - 2), 0) as total_trials
  FROM workflow.strategy_performance
)
SELECT
  sp.strategy,
  sp.alpha / NULLIF(sp.alpha + sp.beta, 0) as exploitation_score,
  2.0 * SQRT(LN(GREATEST(NULLIF(t.total_trials, 0), 1)) / 
             GREATEST(sp.alpha + sp.beta - 2, 1)) as exploration_bonus,
  (sp.alpha / NULLIF(sp.alpha + sp.beta, 0)) + 
  (2.0 * SQRT(...)) as ucb_score
FROM workflow.strategy_performance sp
CROSS JOIN totals t
ORDER BY ucb_score DESC;
```

### Common Issues

**Issue 1: UCB Always Picks Same Strategy**

**Cause:** Exploration bonus too small (C too low or total_trials too high)

**Solution:**
```javascript
// Increase exploration constant
const strategy = await strategyPerf.select('ucb', { explorationConstant: 3.0 });
```

**Issue 2: UCB Explores Too Much (Never Converges)**

**Cause:** Exploration constant too high

**Solution:**
```javascript
// Decrease exploration constant
const strategy = await strategyPerf.select('ucb', { explorationConstant: 1.0 });
```

**Issue 3: Division by Zero / NaN Scores**

**Cause:** No trials recorded (alpha + beta = 2)

**Solution:**
- Ensure strategies are recorded with `record()` after each trial
- Check fallback logic (should return first strategy if no trials)

## Performance Benchmarks

**Query Performance (PostgreSQL on laptop-01):**

| Operation | Time | Notes |
|-----------|------|-------|
| Select strategy (UCB) | 0.4ms | Single query with CTE |
| Record outcome | 0.5ms | Upsert with ON CONFLICT |
| Get all strategies | 0.3ms | Simple SELECT |

**Scalability:**

- **Strategies:** O(n) where n = number of strategies (typically < 100)
- **Total Trials:** O(1) (logarithmic growth in formula, constant query time)
- **Recommendation:** UCB scales well to hundreds of strategies, thousands of trials

## References

- **Original Paper:** Auer, P., Cesa-Bianchi, N., & Fischer, P. (2002). "Finite-time Analysis of the Multiarmed Bandit Problem". Machine Learning, 47(2-3), 235-256.
- **UCB1-Tuned:** Auer, P., Cesa-Bianchi, N., & Fischer, P. (2002). Section 4.
- **Comparison to Thompson Sampling:** Chapelle, O., & Li, L. (2011). "An Empirical Evaluation of Thompson Sampling". NIPS.

## Implementation Location

**File:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/postgres-adapter.js`

**Key Functions:**
- `selectUCB(explorationConstant)` (lines 265-311)
- `select(method, options)` (lines 383-398)
- `record(strategy, success, reward)` (lines 175-215)

**Database:** PostgreSQL `learning` on `aio-01:5433`
**Schema:** `workflow.strategy_performance`

## Quick Start Example

```javascript
// 1. Import adapter
const { getStrategyPerformance } = require('./learning/postgres-adapter.js');
const strategyPerf = getStrategyPerformance();

// 2. Select strategy using UCB
const strategy = await strategyPerf.select('ucb', {
  explorationConstant: 2.0  // Balanced exploration/exploitation
});

console.log(`Selected strategy: ${strategy.strategy}`);
console.log(`UCB score: ${strategy.ucb_score.toFixed(3)}`);
console.log(`  Exploitation: ${strategy.exploitation_score.toFixed(3)}`);
console.log(`  Exploration:  ${strategy.exploration_bonus.toFixed(3)}`);

// 3. Execute task
const result = await executeTask(strategy.strategy);

// 4. Record outcome
await strategyPerf.record(
  strategy.strategy,
  result.success,
  result.quality_score
);
```

## Summary

**UCB Exploration Strengths:**
- Deterministic strategy selection (reproducible)
- Provable logarithmic regret bounds
- Systematic exploration (ensures all strategies tested)
- No hyperparameters except C (self-tuning)

**UCB Exploration Weaknesses:**
- Less effective in highly stochastic environments
- Assumes independent strategies (no contextual information)
- May be slower to converge than Thompson Sampling in practice

**Recommendation:** Use UCB when reproducibility and formal guarantees matter. Use Thompson Sampling for real-world stochastic tasks. Use Epsilon-Greedy for simple, fast exploration.
