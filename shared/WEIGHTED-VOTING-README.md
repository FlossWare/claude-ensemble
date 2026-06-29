# Weighted Voting - Multi-Model Consensus Arbiter

## Overview

The weighted voting system is the core consensus engine that coordinates multiple AI models to reach high-quality decisions. Instead of naive vote counting (30 weak models beat 5 strong models), it weights each vote based on model capability, confidence, task-specific strengths, and historical accuracy.

This prevents scenarios where quantity beats quality. For example: 30 haiku models voting "A" with 50% confidence lose to 5 opus models voting "B" with 90% confidence, because weighted votes are B=45, A=15.

The system integrates with Thompson Sampling (historical accuracy), confidence calibration (detect lying models), circuit breaker (filter failed models), rotation policy (traffic allocation), and disagreement detection (human review queue).

## How It Works

### Phase 1: Worker Execution
Multiple AI models (workers) independently answer the same question. Each worker provides:
- Answer (text, code, or structured data)
- Confidence score (0-100 or 0.0-1.0)
- Model identifier (opus, sonnet, haiku, gpt-4o, etc.)

### Phase 2: Weight Calculation
Each vote receives a weight based on multiplicative factors:

```
weight = tier_weight × capability_score × confidence × historical_accuracy × calibration_penalty
```

**Components:**
1. **Tier Weight** (0.5-1.0): Base model capability
   - opus = 1.0 (highest)
   - sonnet = 0.85
   - haiku = 0.60
   - fable = 0.95
   - gpt-4o = 0.95
   - gemini = 0.90
   - phi-4-mini = 0.50 (fast routing)
   - deepseek-coder = 0.70 (specialized)

2. **Capability Score** (0.0-1.0): Task-specific strength
   - deepseek-coder = 1.0 for code_generation (specialized)
   - opus = 0.95 for security_audit
   - phi-4-mini = 1.0 for routing (specialized)
   - Fallback to tier weight if no task-specific data

3. **Confidence** (0.0-1.0): Model's self-reported confidence
   - Normalized from 0-100 or 0-1 range
   - Defaults to 0.5 if missing

4. **Historical Accuracy** (0.0-1.0): Thompson Sampling avg_quality
   - Loaded from `~/.claude/learning/bandit-state.json`
   - Defaults to 0.5 if no history

5. **Calibration Penalty** (0.25-1.0): Penalty for confidence/accuracy mismatch
   - Detects "lying models" (high confidence, low accuracy)
   - Loaded from confidence calibration system
   - Defaults to 1.0 if unavailable

### Phase 3: Consensus Algorithm
Votes are grouped by answer, weights summed per group, highest total weight wins.

**Tie-breaking rules:**
1. Total weight (primary)
2. Vote count (first tie-breaker)
3. Max individual weight (second tie-breaker)
4. Alphabetical (reproducibility)

**Byzantine Fault Tolerance (BFT) strategies:**
- `weighted-average`: Standard mean (vulnerable to outliers)
- `median`: Weighted median (50th percentile, resistant to outliers)
- `trimmed-mean`: Drop top/bottom 20%, average middle 60%
- `mad`: Median Absolute Deviation outlier detection (auto-filters broken models)

### Phase 4: Result Analysis
System calculates:
- **Consensus strength**: Winner weight / total weight (0.0-1.0)
- **Consensus level**: strong (≥80%), moderate (≥60%), weak (≥40%), none (<40%)
- **Runner-up analysis**: Second-place answer and weight difference
- **Tie detection**: Flag if top 2 answers within 1% weight difference
- **Statistical significance**: Confidence intervals via bootstrap resampling (optional)
- **Disagreement score**: Coefficient of variation for human review queue

### Phase 5: Arbiter Review
Arbiter model (typically opus or fable) receives:
- Weighted voting results (winner, runner-up, all groups)
- Individual vote weights breakdown
- Edge case warnings (tie, low confidence, unanimous)
- Recommendation (approve winner or require deeper review)

Arbiter makes final decision: APPROVE winner, SELECT runner-up, or SYNTHESIZE new answer.

## Safety Features

### PRIORITY 0: Circuit Breaker Integration
Filters out models with open circuits (failed/unavailable) before voting begins.

```javascript
// Automatic - enabled by default
const result = await runWeightedVoting(votes, taskType);
// Models with open circuits auto-filtered

// Manual override (skip circuit breaker)
const result = await runWeightedVoting(votes, taskType, {
  skipCircuitBreaker: true,
});
```

If all votes filtered: returns error `all_models_circuit_open`.

### PRIORITY 1: Confidence Calibration
Detects "lying models" (high confidence, low accuracy) and applies penalties.

**Example:**
- Model A: 90% confidence, 50% accuracy → calibration_penalty = 0.60
- Model B: 70% confidence, 85% accuracy → calibration_penalty = 1.0

Model B's vote weighted higher despite lower confidence (calibrated honesty).

### PRIORITY 2: Sybil Attack Protection
Prevents vote flooding from single model family (30 haiku votes overwhelming 5 opus votes).

**Detection:**
- Triggers when >50% votes from same family (configurable via `familyFloodThreshold`)
- Family defined by model name prefix (opus, gpt, deepseek, etc.)

**Mitigation:**
- Caps votes per family to 5 (configurable via `familyCap`)
- Keeps highest-weight votes from each family
- Logs warning and audit trail

**Example:**
```
Input: 30 haiku votes, 5 opus votes
Detection: 30/35 (85.7%) from 'haiku' family (>50% threshold)
Action: Cap haiku to 5 votes (keep highest weights)
Result: 5 haiku votes, 5 opus votes (balanced)
```

### PRIORITY 2.5: Rotation Policy
Applies traffic allocation multipliers to prevent model dominance (>70% usage).

**Integration:**
- Loads rotation state from `model-rotation.cjs`
- Applies multiplier to vote weights (0.5-1.0 range)
- Ensures diversity via forced exploration

**Example:**
- opus used 75% recently → rotation_multiplier = 0.7
- haiku used 20% recently → rotation_multiplier = 1.0

This encourages trying underused models to prevent feedback loop collapse.

### PRIORITY 3: MAD Minority Opinion Protection
Median Absolute Deviation (MAD) detects faulty/broken models but protects legitimate minority opinions.

**Algorithm:**
1. Calculate weighted median of confidence scores
2. Calculate deviation of each vote from median
3. Calculate median of deviations (MAD)
4. Mark votes > 3×MAD as outliers

**CRITICAL SAFEGUARD:**
- Never mark >30% of votes as outliers
- If >30% would be marked, return NO outliers (legitimate disagreement)
- This protects expert minority opinions from being suppressed

**Example:**
```
Scenario 1 (broken model):
- 9 models: 0.75 confidence
- 1 model: 0.01 confidence (broken)
Action: Mark 1 outlier (10%), filter it out

Scenario 2 (legitimate disagreement):
- 6 models: 0.75 confidence (approve)
- 4 models: 0.25 confidence (reject)
Action: Would mark 4 outliers (40%), exceeds 30% threshold
Result: Return NO outliers, protect minority expert opinion
```

### Disagreement Detection and Human Review Queue
Automatically detects high disagreement and flags for human review before arbiter synthesis.

**Metrics:**
- **Coefficient of Variation (CV)**: std_dev / mean of vote weights
- **Threshold**: CV > 0.20 (default, configurable)

**Action:**
- Queue entry created in PostgreSQL `human_review.queue` table
- Priority: high (CV > 0.50), medium (0.30-0.50), low (0.20-0.30)
- Workflow proceeds with weighted voting result (non-blocking)
- Human review happens asynchronously

**Example:**
```javascript
const result = await runWeightedVotingWithDisagreementDetection(votes, taskType, {
  reviewThreshold: 0.20,
  context: {
    workflow_execution_id: 'wf-123',
    workflow_name: 'deep-research',
    task_description: 'Analyze firmware security',
  },
});

if (result.needs_human_review) {
  console.warn(`High disagreement (CV: ${result.disagreement.cv})`);
  console.warn(`Queue ID: ${result.human_review_queue.queue_id}`);
}
```

### Statistical Significance Testing
Bootstrap resampling to calculate confidence intervals and detect statistical ties.

**Metrics:**
- **95% Confidence Interval**: Weight range containing 95% of bootstrap samples
- **Tie Detection**: CIs overlap + margin <5% → statistical tie
- **Sample Size Recommendation**: Recommend more votes if CI too wide

**Example:**
```javascript
const result = await runWeightedVoting(votes, taskType, {
  skipStatisticalSignificance: false,
  bootstrapIterations: 10000,
  confidenceLevel: 0.95,
});

if (result.statistical_significance.tie_analysis.is_tie) {
  console.warn('Statistical tie detected - recommend more samples');
}
```

## When To Use

### ALWAYS Use For:
- Multi-model consensus for critical decisions
- Security audits, code reviews, architecture reviews
- Research fact-checking, adversarial verification
- Any task where single model might be wrong

### CONSIDER Using For:
- Tasks requiring high confidence (medical, legal, safety)
- Tasks with high disagreement (multiple valid approaches)
- Tasks where model specialization matters (code vs research vs routing)

### SKIP For:
- Single-model tasks (no consensus needed)
- Trivial tasks where speed > accuracy
- Tasks where unanimous agreement expected

## Integration

### Used By:
- All consensus workflows (ai-consensus, ai-consensus-debate, etc.)
- Deep research workflows (adversarial verification)
- Code review workflows (multi-AI review)
- Any workflow using `parallel()` + arbiter pattern

### Integrates With:
- **Thompson Sampling** (`bandit-state.json`): Historical accuracy weights
- **Circuit Breaker** (`circuit-breaker.cjs`): Filters failed models
- **Confidence Calibration** (`confidence-calibration.cjs`): Detects lying models
- **Model Rotation** (`model-rotation.cjs`): Traffic allocation
- **Disagreement Detection** (`disagreement-detector.cjs`): Human review queue
- **Statistical Significance** (`statistical-significance.cjs`): Confidence intervals
- **Workflow Storage** (`workflow-storage-adapter.js`): Audit trail

## Configuration

### Model Tier Weights
Defined in `MODEL_TIER_WEIGHTS` object:

```javascript
const MODEL_TIER_WEIGHTS = {
  'opus': 1.0,
  'sonnet': 0.85,
  'haiku': 0.60,
  'fable': 0.95,
  'gpt-4o': 0.95,
  'gemini': 0.90,
  'deepseek-coder': 0.70,
  'phi-4-mini': 0.50,
  'mistral-7b': 0.65,
  'default': 0.60,
};
```

### Task Type Capability Matrix
Defined in `CAPABILITY_MATRIX` object:

```javascript
const CAPABILITY_MATRIX = {
  'code_generation': {
    'deepseek-coder': 1.0,  // Specialized
    'opus': 0.95,
    'sonnet': 0.90,
  },
  'security_audit': {
    'opus': 0.95,
    'sonnet': 0.90,
    'haiku': 0.65,
  },
  'routing': {
    'phi-4-mini': 1.0,  // Specialized
    'opus': 0.80,
  },
  // ... more task types
};
```

### Confidence Threshold
Minimum confidence to include vote (default: 20%):

```javascript
const DEFAULT_MIN_CONFIDENCE = 20;
```

### Sybil Attack Protection
Family flood detection and capping:

```javascript
const familyCap = 5;                    // Max votes per family
const familyFloodThreshold = 0.50;      // Trigger at 50% votes from one family
```

### MAD Outlier Detection
Median Absolute Deviation threshold:

```javascript
const madThreshold = 3;                 // 3× MAD = outlier
```

### Disagreement Detection
Coefficient of Variation threshold for human review:

```javascript
const reviewThreshold = 0.20;           // CV > 0.20 = high disagreement
```

## API Reference

### `runWeightedVoting(votes, taskType, options)`
Main entry point for weighted voting with all safety features.

**Parameters:**
- `votes`: Array of vote objects `[{model, answer, confidence}, ...]`
- `taskType`: Task type string (code_review, security_audit, research, etc.)
- `options`: Optional configuration object

**Options:**
```javascript
{
  minConfidence: 20,                    // Min confidence threshold (0-100)
  strategy: 'weighted-average',         // BFT strategy: weighted-average, median, trimmed-mean, mad
  trimPercent: 20,                      // Trim % for trimmed-mean
  madThreshold: 3,                      // MAD outlier threshold
  familyCap: 5,                         // Max votes per model family
  familyFloodThreshold: 0.50,           // Vote flooding threshold
  skipCircuitBreaker: false,            // Skip circuit breaker integration
  skipRotationPolicy: false,            // Skip rotation policy integration
  skipStatisticalSignificance: false,   // Skip CI calculation
  bootstrapIterations: 10000,           // Bootstrap iterations
  confidenceLevel: 0.95,                // CI confidence level
}
```

**Returns:**
```javascript
{
  voting_result: {
    status: 'success',
    algorithm: 'weighted_voting',
    task_type: 'code_review',
    winner: {
      answer: "...",
      total_weight: 4.523,
      vote_count: 6,
      consensus_strength: 0.82,
      consensus_level: 'strong',
      votes: [...],
    },
    runner_up: { ... },
    all_groups: [...],
    metadata: { ... },
    circuit_breaker_analysis: { ... },    // If models filtered
    sybil_analysis: { ... },              // If vote flooding detected
    rotation_analysis: { ... },           // If rotation applied
    bft_analysis: { ... },                // If BFT strategy used
  },
  edge_case: { type: 'tie', action: 'require_arbiter_review' },
  statistical_significance: { ... },      // CI analysis
  buildArbiterPrompt: (task) => "...",    // Helper function
  summary: { ... },
}
```

### `runWeightedVotingWithDisagreementDetection(votes, taskType, options)`
Enhanced version with human review queue integration.

**Additional Options:**
```javascript
{
  reviewThreshold: 0.20,                // Disagreement CV threshold
  context: {
    workflow_execution_id: 'wf-123',    // Workflow ID
    workflow_name: 'deep-research',     // Workflow name
    task_description: '...',            // Task description
  },
}
```

**Additional Returns:**
```javascript
{
  ...runWeightedVoting_results,
  disagreement: {
    cv: 0.35,                           // Coefficient of variation
    needs_review: true,
    reason: 'high_variation',
  },
  human_review_queue: {
    queue_id: 123,
    priority: 'high',
  },
  needs_human_review: true,
}
```

### `buildArbiterPrompt(votingResult, originalTask)`
Builds arbiter prompt with voting results.

**Returns:** Formatted string with:
- Winner and runner-up details
- Vote weights breakdown
- Edge case warnings
- Recommendation for arbiter

### `storeAuditTrail(votingResult, workflowExecutionId)`
Stores voting results in PostgreSQL `workflow.weighted_votes` table.

**Schema:**
```sql
CREATE TABLE workflow.weighted_votes (
  id SERIAL PRIMARY KEY,
  workflow_execution_id TEXT NOT NULL,
  task_type TEXT,
  winning_answer JSONB,
  total_weight NUMERIC,
  consensus_level TEXT,
  consensus_strength NUMERIC,
  vote_count INTEGER,
  vote_details JSONB,
  edge_case TEXT,
  edge_case_action TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Example Usage

### Basic Weighted Voting

```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');

const votes = [
  { model: 'opus', answer: 'B', confidence: 0.90 },
  { model: 'opus', answer: 'B', confidence: 0.85 },
  { model: 'sonnet', answer: 'B', confidence: 0.80 },
  { model: 'haiku', answer: 'A', confidence: 0.50 },
  { model: 'haiku', answer: 'A', confidence: 0.55 },
];

const result = await runWeightedVoting(votes, 'code_review');

console.log(`Winner: ${result.voting_result.winner.answer}`);
console.log(`Consensus: ${result.voting_result.winner.consensus_level}`);
console.log(`Weight: ${result.voting_result.winner.total_weight.toFixed(3)}`);

// Output:
// Winner: B
// Consensus: strong
// Weight: 3.421
```

### With Arbiter Integration

```javascript
const { runWeightedVoting } = require('./shared/weighted-voting.cjs');

// Worker phase
const workerResults = await parallel([
  agent({ model: 'opus' }, 'Review this code for bugs'),
  agent({ model: 'sonnet' }, 'Review this code for bugs'),
  agent({ model: 'haiku' }, 'Review this code for bugs'),
]);

const votes = workerResults.map(r => ({
  model: r.model,
  answer: r.output,
  confidence: r.confidence || 0.5,
}));

// Weighted voting
const votingResult = await runWeightedVoting(votes, 'code_review');

// Build arbiter prompt
const arbiterPrompt = votingResult.buildArbiterPrompt(
  'Review this code for bugs: function foo() { ... }'
);

// Arbiter synthesis
const arbiterResult = await agent({ model: 'fable' }, arbiterPrompt);

console.log(`Arbiter decision: ${arbiterResult.output}`);
```

### With BFT Median Strategy

```javascript
const result = await runWeightedVoting(votes, 'security_audit', {
  strategy: 'median',  // Resistant to outliers
});

console.log(`Median confidence: ${result.voting_result.bft_metrics.median_confidence}`);
```

### With MAD Outlier Detection

```javascript
const result = await runWeightedVoting(votes, 'architecture_review', {
  strategy: 'mad',
  madThreshold: 3,  // 3× MAD = outlier
});

if (result.voting_result.bft_analysis.outliers_detected > 0) {
  console.warn('Outliers detected:');
  result.voting_result.bft_analysis.outliers.forEach(o => {
    console.warn(`  - ${o.model}: confidence=${o.confidence}, deviation=${o.deviation}`);
  });
}
```

### With Disagreement Detection

```javascript
const result = await runWeightedVotingWithDisagreementDetection(votes, 'research', {
  reviewThreshold: 0.20,
  context: {
    workflow_execution_id: execId,
    workflow_name: 'deep-research',
    task_description: 'Analyze firmware security vulnerabilities',
  },
});

if (result.needs_human_review) {
  console.warn(`High disagreement detected (CV: ${result.disagreement.cv.toFixed(3)})`);
  console.warn(`Queue ID: ${result.human_review_queue.queue_id}`);
  console.warn(`Priority: ${result.human_review_queue.priority}`);
}
```

### With Statistical Significance

```javascript
const result = await runWeightedVoting(votes, 'fact_checking', {
  skipStatisticalSignificance: false,
  bootstrapIterations: 10000,
  confidenceLevel: 0.95,
});

const stats = result.statistical_significance;

console.log(`Winner CI: [${stats.winner_ci.lower.toFixed(3)}, ${stats.winner_ci.upper.toFixed(3)}]`);

if (stats.tie_analysis.is_tie) {
  console.warn('Statistical tie detected - recommend more samples');
  console.warn(`Reason: ${stats.tie_analysis.reason}`);
}

if (stats.sample_size_recommendation.needs_more_samples) {
  console.warn(`Recommend ${stats.sample_size_recommendation.recommended_additional} more samples`);
}
```

### With Audit Trail

```javascript
const { runWeightedVoting, storeAuditTrail } = require('./shared/weighted-voting.cjs');

const result = await runWeightedVoting(votes, 'code_generation');

// Store in PostgreSQL
await storeAuditTrail(result, execId);

// Query later
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.js');
const db = getWorkflowStorage();

const auditRecords = await db.pool.query(`
  SELECT * FROM workflow.weighted_votes
  WHERE workflow_execution_id = $1
`, [execId]);
```

## Edge Cases

### All Votes Below Threshold
If all votes below `minConfidence`, threshold lowered to 50% and retried.

**Example:**
```javascript
const result = await runWeightedVoting([
  { model: 'opus', answer: 'A', confidence: 0.15 },
  { model: 'sonnet', answer: 'B', confidence: 0.18 },
], 'general', { minConfidence: 20 });

// All votes below 20% threshold
// Action: Lower threshold to 10% and retry
// Warning: result.voting_result.edge_case_warning
```

### Unanimous Vote
If all votes same answer, fast-path (skip weight calculation).

**Example:**
```javascript
const result = await runWeightedVoting([
  { model: 'opus', answer: 'A', confidence: 0.90 },
  { model: 'sonnet', answer: 'A', confidence: 0.85 },
], 'general');

// Unanimous vote detected
// Fast-path: result.voting_result.algorithm === 'unanimous_vote'
```

### Tie (Top 2 Within 1%)
If winner and runner-up within 1% weight difference, tie flagged.

**Example:**
```javascript
const result = await runWeightedVoting(votes, 'research');

if (result.voting_result.tie_detected) {
  console.warn(`Tie margin: ${result.voting_result.tie_margin}`);
  console.warn('Recommendation: REQUIRE_ARBITER_REVIEW');
}
```

### No Capable Models
If all models have <0.3 capability for task, fallback to 'general' task type.

**Example:**
```javascript
const result = await runWeightedVoting([
  { model: 'phi-4-mini', answer: 'A', confidence: 0.80 },  // Not designed for security
], 'security_audit');

// No capable models for security_audit
// Fallback to 'general' task type
// Warning: result.voting_result.edge_case_warning
```

### All Models Circuit Open
If circuit breaker filters all votes, error returned.

**Example:**
```javascript
const result = await runWeightedVoting(votes, 'code_review');

if (result.voting_result.status === 'error' && 
    result.voting_result.error === 'all_models_circuit_open') {
  console.error('All models unavailable (circuit breaker)');
  // Fallback to single model or retry later
}
```

## Performance

### Typical Runtime
- 6 votes, basic strategy: ~5ms
- 20 votes, MAD outlier detection: ~15ms
- 50 votes, bootstrap CI (10k iterations): ~200ms

### Database Impact
- Audit trail: 1 INSERT per vote (non-blocking)
- PostgreSQL `workflow.weighted_votes` table
- Minimal overhead (~2ms per insert)

### Memory Usage
- Votes held in memory during calculation
- No persistence until `storeAuditTrail()` called
- Safe for 100+ votes per workflow

## Best Practices

### DO:
- Use task-specific types (code_review, security_audit, research)
- Enable disagreement detection for critical decisions
- Store audit trail for transparency
- Use BFT strategies (median, mad) for high-stakes tasks
- Configure family caps to prevent Sybil attacks

### DON'T:
- Use 'general' task type if specific type exists
- Skip circuit breaker (safety feature)
- Skip rotation policy (prevents model dominance)
- Ignore tie warnings (require arbiter review)
- Ignore high disagreement warnings (consider human review)

### CONSIDER:
- Statistical significance for close races
- MAD outlier detection for noisy environments
- Trimmed-mean for moderate outlier resistance
- Median for maximum outlier resistance

## Troubleshooting

### Low Consensus Strength
**Problem:** Winner has <60% consensus strength.

**Causes:**
- High disagreement (multiple valid answers)
- No dominant answer (votes spread evenly)
- Low model confidence across board

**Solutions:**
- Review disagreement analysis (CV threshold)
- Consider human review queue
- Add more diverse models
- Check if task well-defined

### Vote Flooding Detected
**Problem:** Sybil analysis shows >50% votes from one family.

**Causes:**
- Workflow using too many similar models
- Same model called multiple times with different configs

**Solutions:**
- Diversify model selection (mix opus, gpt, gemini, etc.)
- Apply family cap (default: 5 votes per family)
- Review rotation policy settings

### Statistical Tie
**Problem:** Winner and runner-up CIs overlap significantly.

**Causes:**
- Close vote (weight difference <5%)
- High variance in vote weights
- Insufficient samples

**Solutions:**
- Add more models to vote
- Use MAD to filter noisy votes
- Require arbiter review (don't auto-approve)
- Consider human review

### All Outliers (MAD)
**Problem:** MAD marks all votes as outliers.

**Causes:**
- MAD threshold too strict
- All votes have high variance (legitimate disagreement)

**Solutions:**
- MAD auto-falls back to all votes (safe)
- Review disagreement analysis
- Consider human review queue
- Lower MAD threshold (default: 3)

## File Locations

- **Main implementation:** `shared/weighted-voting.cjs` (1,450 lines)
- **Thompson Sampling state:** `~/.claude/learning/bandit-state.json`
- **Confidence calibration:** `shared/confidence-calibration.cjs`
- **Circuit breaker:** `shared/circuit-breaker.cjs`
- **Model rotation:** `shared/model-rotation.cjs`
- **Disagreement detection:** `shared/disagreement-detector.cjs`
- **Statistical significance:** `shared/statistical-significance.cjs`
- **Workflow storage:** `shared/workflow-storage-adapter.js`
- **Audit trail DB:** PostgreSQL `learning.workflow.weighted_votes`

## See Also

- **Multi-AI Consensus Pattern:** See workflow examples in `workflows/ai-consensus*.mjs`
- **Byzantine Fault Tolerance:** See `docs/bft-median-voting.md`
- **Disagreement Detection:** See `DISAGREEMENT-DETECTION-README.md`
- **Confidence Calibration:** See `shared/confidence-calibration.cjs` comments
- **Model Rotation:** See `shared/model-rotation.cjs` comments
