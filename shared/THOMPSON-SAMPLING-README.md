# Thompson Sampling - Adaptive Strategy Selection

## Overview

Thompson Sampling is a Bayesian bandit algorithm that learns which consensus strategies perform best over time. It balances **exploration** (trying new strategies) with **exploitation** (using proven strategies) using probabilistic sampling from Beta distributions.

Unlike naive approaches (always pick the best, or random selection), Thompson Sampling:
- Automatically explores underutilized strategies to discover hidden value
- Gradually converges on high-performing strategies as evidence accumulates
- Maintains uncertainty estimates via Bayesian updates (Beta distributions)
- Handles cold-start gracefully (uniform prior = no bias toward any strategy)

**Key Insight:** Instead of deterministically picking the strategy with highest observed success rate, we sample from each strategy's performance distribution and pick the highest sample. This naturally balances exploration and exploitation.

---

## How It Works

### 1. Beta Distribution Modeling

Each strategy tracks two parameters:
- **α (alpha)**: Successes + 1 (uniform prior)
- **β (beta)**: Failures + 1 (uniform prior)

The Beta(α, β) distribution represents our belief about the strategy's true success rate:
- Mean: α / (α + β)
- Variance: High when few trials, low when many trials
- Shape: Peaked at mean, wider for uncertainty

**Example:**
- New strategy: Beta(1, 1) = uniform (no knowledge)
- After 10 successes, 2 failures: Beta(11, 3) = ~80% success rate, moderate confidence
- After 100 successes, 20 failures: Beta(101, 21) = ~83% success rate, high confidence

### 2. Thompson Sampling Selection Process

**Algorithm:**
```javascript
// For each strategy:
for (const strategy of strategies) {
  // Sample a value from Beta(α, β)
  const sample = sampleBeta(strategy.alpha, strategy.beta);
  
  // Track best sample
  if (sample > bestSample) {
    bestStrategy = strategy;
    bestSample = sample;
  }
}

return bestStrategy;
```

**Why this works:**
- Strategies with high α/β ratios (high success rate) tend to sample higher values
- Strategies with high uncertainty (few trials) have wide distributions → occasionally sample very high → get explored
- Strategies with low success rate + high certainty (many failures) rarely sample high → rarely selected
- No hyperparameters to tune (unlike epsilon-greedy or UCB)

### 3. Bayesian Update Rule

After each trial:
```javascript
if (success) {
  α = α + 1  // Increment successes
} else {
  β = β + 1  // Increment failures
}
```

This is the conjugate prior update for Beta distributions - mathematically optimal for binary outcomes.

---

## When To Use

### ✅ **Perfect For:**

1. **Adaptive Model Routing**
   - Which LLM (opus/sonnet/haiku) for which task type?
   - Route code tasks to model with best code performance
   - Route research tasks to model with best research performance

2. **Consensus Strategy Selection**
   - Weighted average vs median vs Upper Confidence Bound?
   - Confidence filtering vs no filtering?
   - Adversarial verification vs simple majority?

3. **A/B Testing with Continuous Learning**
   - Compare new implementation vs old
   - Automatically shift traffic to better variant
   - No need to manually stop the test

4. **Exploration Strategies (Meta-Level)**
   - Thompson Sampling vs UCB vs Epsilon-Greedy?
   - Let Thompson Sampling pick which exploration method to use!

### ❌ **Not Suitable For:**

1. **Multi-Armed Contextual Bandits** (use LinUCB instead)
   - When features/context affect strategy performance
   - Example: Strategy A works for short prompts, Strategy B for long prompts

2. **Non-Stationary Environments** (use Discounted Thompson Sampling instead)
   - When strategy performance changes over time
   - Example: Model quality degrades after API update

3. **Safety-Critical Decisions** (use conservative exploration instead)
   - When failures have high cost (data loss, security breaches)
   - Thompson Sampling explores failures - unacceptable in high-stakes scenarios

4. **Known Optimal Strategy** (just use it)
   - If you already know Strategy X is best, no need for exploration

---

## Integration

### Database Schema

**Table:** `workflow.strategy_performance`

```sql
CREATE TABLE workflow.strategy_performance (
  strategy VARCHAR(255) PRIMARY KEY,
  successes INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0,
  alpha NUMERIC NOT NULL DEFAULT 1.0,  -- Beta distribution parameter
  beta NUMERIC NOT NULL DEFAULT 1.0,   -- Beta distribution parameter
  total_reward NUMERIC NOT NULL DEFAULT 0.0,
  avg_reward NUMERIC NOT NULL DEFAULT 0.0,
  last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_strategy_avg_reward ON workflow.strategy_performance(avg_reward DESC);
CREATE INDEX idx_strategy_last_updated ON workflow.strategy_performance(last_updated DESC);
```

**Real Data Example (2026-06-28):**
```sql
 strategy | successes | failures | alpha | beta |   avg_reward
----------+-----------+----------+-------+------+---------------
 haiku    |        25 |        6 |    26 |    7 | 0.806  (80.6%)
 opus     |        19 |       12 |    20 |   13 | 0.613  (61.3%)
 sonnet   |        13 |       18 |    14 |   19 | 0.419  (41.9%)
 gpt4o    |         0 |        6 |     1 |    7 | 0.000  (0.0%)
```

**Interpretation:**
- Haiku: 25 successes / 31 trials = 80.6% observed success rate (high confidence)
- Opus: 19 successes / 31 trials = 61.3% observed success rate (moderate confidence)
- GPT-4o: 0 successes / 6 trials = 0% observed success rate (still exploring, uniform prior)

### Code API

**Location:** `learning/postgres-adapter.js`

#### Initialize Database Connection
```javascript
const { getStrategyPerformance } = require('./learning/postgres-adapter');
const strategyDB = getStrategyPerformance();
```

#### Record an Outcome
```javascript
// After task completes
await strategyDB.record(
  'haiku',           // strategy name
  true,              // success (boolean)
  0.85               // reward (0.0-1.0 quality score)
);

// Automatically updates:
// - successes/failures counters
// - alpha/beta parameters (Bayesian update)
// - avg_reward (running average)
```

#### Select Best Strategy (Thompson Sampling)
```javascript
const selected = await strategyDB.select('thompson');

console.log(selected);
// {
//   strategy: 'haiku',
//   alpha: 26,
//   beta: 7,
//   successes: 25,
//   failures: 6,
//   avg_reward: 0.806
// }
```

#### Alternative Exploration Methods
```javascript
// Upper Confidence Bound (UCB)
const selected = await strategyDB.select('ucb', { 
  explorationConstant: 2.0  // Higher = more exploration
});

// Epsilon-Greedy
const selected = await strategyDB.select('epsilon-greedy', {
  epsilon: 0.1,      // 10% exploration
  minTrials: 3       // Ignore strategies with <3 trials
});
```

#### Get All Strategies (Ranked)
```javascript
const strategies = await strategyDB.getAllStrategies();
// Returns array sorted by avg_reward DESC
```

#### Get Strategy Stats
```javascript
const stats = await strategyDB.getStats('haiku');
console.log(stats);
// {
//   strategy: 'haiku',
//   alpha: 26,
//   beta: 7,
//   successes: 25,
//   failures: 6,
//   total_reward: 20.16,
//   avg_reward: 0.806,
//   last_updated: '2026-06-28T18:45:00Z'
// }
```

---

## Configuration

### Uniform Prior (Default)

**Initial Values:**
- α = 1 (uniform prior = no bias)
- β = 1 (uniform prior = no bias)

**Why uniform prior:**
- Beta(1, 1) = uniform distribution over [0, 1]
- No assumptions about strategy performance
- Let data drive the learning

**Alternative Priors (Advanced):**
- **Optimistic Prior:** α=10, β=1 (assume high success until proven otherwise)
  - Use for: Safe-to-explore strategies
  - Effect: Encourages early exploration
- **Pessimistic Prior:** α=1, β=10 (assume low success until proven otherwise)
  - Use for: Risky strategies with potential downside
  - Effect: Requires strong evidence before selection
- **Informative Prior:** α=5, β=5 (assume 50% success with moderate confidence)
  - Use for: When you have domain knowledge
  - Effect: Regularizes estimates (prevents overfitting to early data)

### Reward Function

**Current Implementation:**
```javascript
reward = quality_score  // 0.0-1.0 from arbiter evaluation
```

**Customization Options:**
```javascript
// Binary reward (0 or 1)
reward = success ? 1.0 : 0.0;

// Latency-adjusted reward
reward = quality_score * (1.0 - duration_penalty);

// Cost-adjusted reward
reward = quality_score / (cost_usd * 100);

// Multi-objective reward
reward = 0.6 * quality + 0.3 * speed + 0.1 * cost;
```

**Important:** Reward should be comparable across strategies (same scale/meaning).

### Exploration Control (Environment Variable)

```bash
# Select exploration method globally
export EXPLORATION_METHOD=thompson  # Default
export EXPLORATION_METHOD=ucb       # More exploration
export EXPLORATION_METHOD=epsilon   # Hybrid approach
```

**When to override:**
- `thompson`: Best for most cases (default)
- `ucb`: When you need provable regret bounds (academic settings)
- `epsilon`: When you want simple, tunable exploration (easier to explain)

---

## Implementation Details

### Beta Distribution Sampling

**Algorithm:** Marsaglia & Tsang's method via Gamma distributions

```javascript
// Beta(α, β) = Gamma(α, 1) / (Gamma(α, 1) + Gamma(β, 1))
_sampleBeta(alpha, beta) {
  const x = this._sampleGamma(alpha, 1);
  const y = this._sampleGamma(beta, 1);
  return x / (x + y);
}

_sampleGamma(alpha, beta) {
  // Marsaglia & Tsang's method
  // (see lines 419-449 in postgres-adapter.js)
}
```

**Why this method:**
- Numerically stable for all α, β > 0
- Fast (O(1) rejection sampling)
- Widely used in scientific computing

**Alternative (naive, DO NOT USE):**
```javascript
// BROKEN: Numerical instability for α,β >> 1
return Math.pow(Math.random(), alpha) * Math.pow(1 - Math.random(), beta);
```

### Transaction Safety

**Race Condition Protection:**
```javascript
// Prevent concurrent updates from corrupting state
async record(strategy, success, reward) {
  // Atomic read-modify-write
  await this.db.transaction(async (client) => {
    const existing = await client.query('SELECT * FROM ... FOR UPDATE');
    const updated = { successes: existing.successes + 1, ... };
    await client.query('UPDATE ... SET successes = $1', [updated.successes]);
  });
}
```

**Why transactions matter:**
- Two workers finish simultaneously → both read successes=10
- Without transaction: Both write successes=11 (lost update!)
- With transaction: Serializable execution → successes=12 (correct)

### Numeric Type Handling (PostgreSQL)

**Issue:** PostgreSQL returns NUMERIC as strings
```javascript
// BROKEN
const alpha = result.alpha;  // "26" (string!)
const sample = this._sampleBeta(alpha, beta);  // NaN

// FIXED
const alpha = parseFloat(result.alpha);  // 26 (number)
const sample = this._sampleBeta(alpha, beta);  // 0.78
```

**Normalization helper:**
```javascript
_normalizeStrategy(row) {
  return {
    strategy: row.strategy,
    alpha: parseFloat(row.alpha),        // Force numeric
    beta: parseFloat(row.beta),          // Force numeric
    successes: parseInt(row.successes),  // Force integer
    failures: parseInt(row.failures),    // Force integer
    total_reward: parseFloat(row.total_reward),
    avg_reward: parseFloat(row.avg_reward)
  };
}
```

---

## Usage Patterns

### Pattern 1: Model Selection for Task Type

**Scenario:** Route task to best LLM for the job

```javascript
const { getStrategyPerformance } = require('./learning/postgres-adapter');
const strategyDB = getStrategyPerformance();

// Task arrives
const task = { type: 'code_review', prompt: '...' };

// Select best model using Thompson Sampling
const selected = await strategyDB.select('thompson');
const model = selected.strategy;  // 'haiku', 'opus', 'sonnet'

// Execute task
const result = await runTask(task, model);

// Record outcome
await strategyDB.record(
  model,
  result.success,
  result.quality_score
);
```

### Pattern 2: Consensus Strategy Selection

**Scenario:** Pick best consensus algorithm (weighted-average vs median vs UCB)

```javascript
// Consensus strategies tracked in database
// strategy = 'weighted-average', 'median', 'ucb', 'bft-median'

// Select consensus method using Thompson Sampling
const selected = await strategyDB.select('thompson');
const consensusMethod = selected.strategy;

// Run consensus
let finalAnswer;
if (consensusMethod === 'weighted-average') {
  finalAnswer = weightedAverage(votes);
} else if (consensusMethod === 'median') {
  finalAnswer = median(votes);
} else if (consensusMethod === 'ucb') {
  finalAnswer = upperConfidenceBound(votes);
}

// Evaluate quality (adversarial verification)
const quality = await adversarialVerify(finalAnswer);

// Update Thompson Sampling
await strategyDB.record(
  consensusMethod,
  quality > 0.75,  // Success if quality > threshold
  quality
);
```

### Pattern 3: A/B Testing New Implementation

**Scenario:** Compare new algorithm vs old, automatically shift to winner

```javascript
// Register both variants as strategies
// 'grep_parallel' (new) vs 'grep_serial' (old)

// Select implementation using Thompson Sampling
const selected = await strategyDB.select('thompson');
const implementation = selected.strategy;

// Execute
const startTime = Date.now();
const result = await (implementation === 'grep_parallel' 
  ? grepParallel(query) 
  : grepSerial(query));
const duration = Date.now() - startTime;

// Measure quality
const quality = evaluateResults(result);

// Record (automatically shifts traffic to winner over time)
await strategyDB.record(
  implementation,
  quality > 0.8,
  quality
);

// After 100 trials:
// - If grep_parallel is 20% better → gets 80% of traffic
// - If grep_serial is slightly better → gets 60% of traffic
// - If tied → both get ~50% of traffic (continued exploration)
```

### Pattern 4: Monitoring and Alerts

**Scenario:** Detect when a strategy is underperforming

```javascript
const strategies = await strategyDB.getAllStrategies();

for (const strategy of strategies) {
  const trials = strategy.alpha + strategy.beta - 2;
  
  // Alert if avg_reward drops below threshold (with minimum trials)
  if (trials >= 10 && strategy.avg_reward < 0.3) {
    console.warn(`Strategy '${strategy.strategy}' performing poorly:`);
    console.warn(`  Avg reward: ${strategy.avg_reward.toFixed(3)}`);
    console.warn(`  Trials: ${trials}`);
    console.warn(`  Consider removing or debugging this strategy.`);
  }
  
  // Alert if strategy hasn't been used recently
  const daysSinceUpdate = (Date.now() - new Date(strategy.last_updated)) / 86400000;
  if (daysSinceUpdate > 7) {
    console.warn(`Strategy '${strategy.strategy}' not used in ${daysSinceUpdate.toFixed(1)} days`);
    console.warn(`  May need manual exploration or removal.`);
  }
}
```

---

## Comparison with Other Exploration Methods

### Thompson Sampling vs Epsilon-Greedy

| Aspect | Thompson Sampling | Epsilon-Greedy |
|--------|------------------|----------------|
| **Exploration** | Probabilistic (Beta sampling) | Fixed probability ε |
| **Tuning** | None (prior only) | ε parameter (0.05-0.20) |
| **Regret Bound** | O(√(KT log T)) | O(K log T / ε + εT) |
| **Convergence** | Faster (adaptive) | Slower (fixed ε) |
| **Interpretability** | Moderate (Bayesian) | High (simple) |
| **Cold-Start** | Good (uniform prior) | Poor (ε too low) or wasteful (ε too high) |

**When to use Epsilon-Greedy:**
- Need simple explanation to non-technical stakeholders
- Want direct control over exploration rate
- Environment is non-stationary (ε prevents over-exploitation)

### Thompson Sampling vs UCB (Upper Confidence Bound)

| Aspect | Thompson Sampling | UCB |
|--------|------------------|-----|
| **Exploration** | Sample from belief | Add confidence bonus |
| **Tuning** | None | C parameter (1.0-3.0) |
| **Regret Bound** | O(√(KT log T)) | O(√(KT log T)) (provable) |
| **Computation** | O(K) sampling | O(K) arithmetic |
| **Theory** | Bayesian | Frequentist |
| **Cold-Start** | Good | Good |
| **Interpretability** | Moderate | High ("optimism under uncertainty") |

**When to use UCB:**
- Need provable regret guarantees (academic/research setting)
- Want deterministic behavior (no randomness)
- Need to explain exploration bonus to stakeholders

### Summary Recommendation

**Use Thompson Sampling for:**
- Most real-world applications (default choice)
- When you want optimal exploration/exploitation tradeoff
- When hyperparameter tuning is too expensive

**Use Epsilon-Greedy for:**
- Simplicity is paramount
- Non-stationary environments
- Quick prototyping

**Use UCB for:**
- Academic/research contexts requiring proofs
- Deterministic behavior required
- Safety-critical with formal guarantees

---

## Advanced Topics

### Contextual Bandits (Future Extension)

**Limitation of Current Implementation:**
- Assumes strategy performance is **context-independent**
- Example: Strategy A always better than Strategy B

**Reality:**
- Strategy A better for **short prompts**
- Strategy B better for **long prompts**

**Solution: LinUCB (Linear Upper Confidence Bound)**
```sql
-- Extended schema
CREATE TABLE workflow.strategy_performance_contextual (
  strategy VARCHAR(255),
  context_features JSONB,  -- {prompt_length: 1500, task_type: 'code_review'}
  coefficients NUMERIC[],  -- Linear weights for features
  covariance_matrix NUMERIC[][],  -- Uncertainty estimates
  ...
);
```

**Use Cases:**
- Model selection based on prompt length
- Consensus method based on vote diversity
- Routing based on task complexity

### Discounted Thompson Sampling (Non-Stationary)

**Problem:** Model quality changes after API update

**Solution:** Exponential decay of old observations
```javascript
// Decay old observations
const decay_rate = 0.99;  // Per-day decay
const days_since_update = ...;
const effective_alpha = alpha * Math.pow(decay_rate, days_since_update);
const effective_beta = beta * Math.pow(decay_rate, days_since_update);
```

**Effect:**
- Recent observations weighted more heavily
- Old observations gradually forgotten
- Adapts to changing environment

### Multi-Objective Optimization

**Problem:** Maximize quality AND minimize cost

**Solution 1: Scalarization**
```javascript
reward = 0.7 * quality + 0.3 * (1 - cost_normalized);
```

**Solution 2: Pareto Thompson Sampling**
- Maintain separate α, β for each objective
- Sample from joint distribution
- Select Pareto-optimal strategy

---

## Testing and Validation

### Unit Tests

**Location:** `shared/weighted-voting.test.cjs`

**Coverage:**
- Beta sampling correctness (statistical tests)
- Numeric type handling (PostgreSQL NUMERIC → JS number)
- Transaction isolation (concurrent updates)
- Edge cases (zero trials, extreme α/β values)

### Integration Tests

**Location:** `workflows/deep-research.mjs`

**Tests:**
- Model selection with Thompson Sampling
- Outcome recording after task completion
- Strategy convergence over 100+ trials
- Diversity monitoring (prevent >70% dominance)

### Statistical Validation

**Verify Thompson Sampling is working:**
```javascript
// Run 1000 trials
const trials = 1000;
const selections = { haiku: 0, opus: 0, sonnet: 0 };

for (let i = 0; i < trials; i++) {
  const selected = await strategyDB.select('thompson');
  selections[selected.strategy]++;
}

// Expected distribution (based on current data):
// haiku: ~60% (α=26, β=7, avg_reward=0.806)
// opus:  ~30% (α=20, β=13, avg_reward=0.613)
// sonnet: ~10% (α=14, β=19, avg_reward=0.419)

console.log(selections);
// Verify within ±5% of expected
```

---

## Troubleshooting

### Issue: Same strategy always selected

**Symptoms:**
```javascript
const selected = await strategyDB.select('thompson');
console.log(selected.strategy);  // Always 'haiku'
```

**Diagnosis:**
```sql
SELECT strategy, alpha, beta, avg_reward 
FROM workflow.strategy_performance 
ORDER BY avg_reward DESC;
```

**Possible Causes:**
1. **Extreme performance difference:** If haiku has 95% success and others have 10%, it dominates
   - **Fix:** This is correct behavior! Thompson Sampling should exploit the best strategy.
2. **Insufficient exploration:** Early lucky streak biases selection
   - **Fix:** Increase prior uncertainty (α=5, β=5 instead of α=1, β=1)
3. **Broken sampling:** `_sampleBeta` returning NaN or constant
   - **Fix:** Check numeric type handling (parseFloat everywhere)

### Issue: All strategies selected equally

**Symptoms:**
```javascript
// After 100 trials, all strategies have equal selection rate
```

**Diagnosis:**
```sql
SELECT strategy, alpha, beta, avg_reward 
FROM workflow.strategy_performance;

-- If all α, β are equal → outcomes not recorded
```

**Possible Causes:**
1. **Recording failure:** `strategyDB.record()` throwing errors silently
   - **Fix:** Add logging, check database permissions
2. **Transaction rollback:** Errors causing rollback
   - **Fix:** Wrap in try/catch, log errors
3. **Wrong strategy name:** Recording 'haiku-v3' but selecting 'haiku'
   - **Fix:** Normalize strategy names before recording

### Issue: PostgreSQL connection errors

**Symptoms:**
```
Error: Connection terminated unexpectedly
```

**Diagnosis:**
```bash
# Check PostgreSQL is running
psql -h aio-01 -p 5433 -U sfloess -d learning -c '\dt workflow.*'

# Check connection pool
node -e "const {getDB} = require('./learning/postgres-adapter'); getDB().query('SELECT 1');"
```

**Possible Causes:**
1. **Wrong host/port:** Check environment variables
   - **Fix:** `export PGHOST=aio-01 PGPORT=5433`
2. **Authentication failure:** Missing .pgpass or wrong password
   - **Fix:** Create ~/.pgpass with `aio-01:5433:learning:sfloess:password`
3. **Pool exhaustion:** All 10 connections in use
   - **Fix:** Increase pool size or call `client.release()` in all code paths

---

## References

### Academic Papers

1. **Thompson Sampling (Original):**
   - Thompson, W. R. (1933). "On the likelihood that one unknown probability exceeds another in view of the evidence of two samples." *Biometrika*, 25(3-4), 285-294.

2. **Tutorial on Thompson Sampling:**
   - Russo, D., Van Roy, B., Kazerouni, A., Osband, I., & Wen, Z. (2017). "A tutorial on Thompson sampling." *arXiv preprint arXiv:1707.02038*.

3. **Regret Bounds:**
   - Agrawal, S., & Goyal, N. (2012). "Analysis of Thompson sampling for the multi-armed bandit problem." *COLT*, 39(1), 39.

### Implementation References

- **Database Schema:** `db/schema.sql` (workflow.strategy_performance table)
- **Core Algorithm:** `learning/postgres-adapter.js` (StrategyPerformance class)
- **Integration:** `shared/weighted-voting.cjs` (Thompson Sampling for consensus)
- **Tests:** `shared/weighted-voting.test.cjs`

### Related Documentation

- **Weighted Voting Integration:** `shared/weighted-voting-integration.md`
- **Workflow Storage:** Project README section "Workflow Storage and Analytics"
- **BFT Median Voting:** `docs/bft-median-voting.md`
- **Exploration Strategies:** `docs/exploration-strategies.md`

---

## Quick Start Checklist

- [ ] PostgreSQL connection configured (`PGHOST=aio-01 PGPORT=5433`)
- [ ] Strategy names standardized (lowercase, no version suffixes)
- [ ] Reward function defined (0.0-1.0 scale)
- [ ] Initial prior selected (default: α=1, β=1 uniform)
- [ ] Recording integrated after task completion
- [ ] Selection integrated before task execution
- [ ] Monitoring dashboard set up (Grafana recommended)
- [ ] Statistical validation run (1000 trials, verify distribution)
- [ ] Documentation updated with strategy semantics

**Next Steps:**
1. Read `shared/weighted-voting-integration.md` for full consensus integration
2. Review `docs/exploration-strategies.md` for UCB and epsilon-greedy alternatives
3. Check Grafana dashboard at `http://aio-01:3000` for real-time Thompson Sampling metrics

---

**Last Updated:** 2026-06-28  
**Version:** 1.0  
**Maintainer:** Claude Code (via postgres-adapter.js)
