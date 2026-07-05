# Code Review Pattern Extractor

**Status:** ✅ Deployed (2026-07-03)  
**Location:** `tools/code_review_pattern_extractor.py`  
**Model:** `learning/code_review_pattern_extractor.pkl` (313 KB)  
**JavaScript API:** `shared/code-review-pattern-adapter.cjs`

## Overview

Machine learning system that extracts patterns from code review workflow data to:
1. Recommend optimal models for review tasks
2. Predict likelihood of finding issues
3. Suggest review strategies based on task characteristics
4. Track common issue categories and severities

## Training Data

**Source:** PostgreSQL `workflow.*` tables on `aio-01:5433`  
**Dataset:** 465 code review tasks from last 90 days  
**Performance:**
- Training accuracy: 99.73%
- Test accuracy: 94.62%
- Cross-validation: 96.50% ± 1.38%

## Features

### 1. Model Recommendations

Ranks models by success rate and confidence:

```javascript
const { getTopReviewModels } = require('./shared/code-review-pattern-adapter.cjs');

const models = await getTopReviewModels(5);
// Returns:
// [
//   { model: 'opus', success_rate: '100.0%', avg_confidence: '0.95', reviews: 1 },
//   { model: 'command-a-03-2025', success_rate: '84.6%', avg_confidence: '1.00', reviews: 136 },
//   { model: 'liquid/lfm-2.5-1.2b-instruct:free', success_rate: '62.5%', reviews: 8 }
// ]
```

**Current Top 3 Models:**
1. **opus** - 100.0% success (1 review)
2. **command-a-03-2025** - 84.6% success (136 reviews)
3. **liquid/lfm-2.5-1.2b-instruct:free** - 62.5% success (8 reviews)

### 2. Issue Prediction

Predicts probability of finding issues based on task features:

```javascript
const { predictIssues } = require('./shared/code-review-pattern-adapter.cjs');

const prediction = await predictIssues({
  duration_ms: 5000,
  input_tokens: 1000,
  output_tokens: 500,
  files: 10,
  confidence: 0.8
});

// Returns: { probability: 0.78, message: "High likelihood of finding issues" }
```

**Top Predictive Features:**
1. **duration_ms** (46.7%) - Longer reviews find more issues
2. **output_tokens** (14.9%) - Detailed outputs correlate with findings
3. **files_mentioned** (14.5%) - More files = more issues
4. **input_tokens** (10.4%) - Complexity indicator
5. **severities** (6.0%) - Severity level distribution

### 3. Strategy Recommendations

Suggests optimal review strategy based on task characteristics:

```javascript
const { getReviewStrategy } = require('./shared/code-review-pattern-adapter.cjs');

// Small style review
const strategy1 = await getReviewStrategy({ files: 5, type: 'style' });
// Returns: { strategy: 'base', workers: [...3 models], arbiter: 'opus' }

// Large security review
const strategy2 = await getReviewStrategy({ files: 50, type: 'security' });
// Returns: { strategy: 'maximum-coverage', workers: [...6 models], arbiter: 'opus' }

// High-confidence bug hunt
const strategy3 = await getReviewStrategy({ files: 20, type: 'bug' });
// Returns: { strategy: 'quintuple-verification', workers: [...5 models] }
```

**Strategy Selection Logic:**
- **base:** < 20 files, general review → 3 workers
- **maximum-coverage:** > 50 files OR security review → 6 workers
- **quintuple-verification:** High issue probability (>70%) → 5 workers + multi-stage consensus

### 4. Pattern Statistics

Get historical pattern data:

```javascript
const { getPatternStats } = require('./shared/code-review-pattern-adapter.cjs');

const stats = await getPatternStats();
// Returns:
// {
//   issue_categories: { performance: 77, documentation: 35, bug: 30, security: 15, ... },
//   severity_distribution: { low: 102, high: 85, critical: 34 },
//   task_complexity: { simple: 273, medium: 160, complex: 32 },
//   review_outcomes: { error: 298, success: 167 },
//   trained_at: "2026-07-03T00:00:00",
//   version: "1.0.0"
// }
```

## Patterns Discovered

### Issue Categories (465 tasks analyzed)

| Category        | Count | Percentage |
|-----------------|-------|------------|
| Performance     | 77    | 46.1%      |
| Documentation   | 35    | 21.0%      |
| Bug             | 30    | 18.0%      |
| Security        | 15    | 9.0%       |
| Maintainability | 11    | 6.6%       |

### Severity Distribution

| Severity | Count | Percentage |
|----------|-------|------------|
| Low      | 102   | 46.2%      |
| High     | 85    | 38.5%      |
| Critical | 34    | 15.4%      |

**⚠️ 34 critical issues detected** - High-priority risk area

### Task Complexity

| Level   | Count | Percentage |
|---------|-------|------------|
| Simple  | 273   | 58.7%      |
| Medium  | 160   | 34.4%      |
| Complex | 32    | 6.9%       |

**Most reviews (58.7%) are simple** - Opportunity for automation

### Review Outcomes

| Outcome | Count | Percentage |
|---------|-------|------------|
| Error   | 298   | 64.1%      |
| Success | 167   | 35.9%      |

**⚠️ 35.9% success rate** - Indicates task definition clarity issues

## Workflow Integration

### Example 1: Automatic Model Selection

```javascript
// Before (manual model selection)
const workers = ['opus', 'sonnet', 'haiku'];

// After (learned recommendations)
const { getTopReviewModels } = require('./shared/code-review-pattern-adapter.cjs');
const models = await getTopReviewModels(3);
const workers = models.map(m => m.model);
```

### Example 2: Adaptive Strategy

```javascript
const { getReviewStrategy } = require('./shared/code-review-pattern-adapter.cjs');

export default async function codeReview({ files, type }) {
  // Get learned strategy
  const strategy = await getReviewStrategy({ files: files.length, type });

  console.log(`Strategy: ${strategy.strategy}`);
  console.log(`Workers: ${strategy.workers.length}`);
  console.log(`Issue probability: ${(strategy.prediction.probability * 100).toFixed(1)}%`);

  // Execute review with recommended workers
  const reviews = await parallel(strategy.workers.map(model => () =>
    agent(`Review code for ${type} issues...`, { model })
  ));

  // Arbiter consensus
  const consensus = await agent('Resolve findings...', { model: strategy.arbiter });

  return consensus;
}
```

### Example 3: Pre-flight Prediction

```javascript
const { predictIssues } = require('./shared/code-review-pattern-adapter.cjs');

// Before expensive review, predict likelihood
const prediction = await predictIssues({
  files: 50,
  duration_ms: 30000,
  confidence: 0.9
});

if (prediction.probability < 0.3) {
  console.log('Low issue probability - skipping expensive multi-model review');
  // Use single fast model instead
} else {
  console.log(`High issue probability (${prediction.probability:.1%}) - running full review`);
  // Use full consensus strategy
}
```

## Retraining

### Automatic Retraining (Recommended)

Add to cron (every Sunday at 2 AM):

```bash
0 2 * * 0 cd /home/sfloess/Development/.../claude-global-skills && python3 tools/code_review_pattern_extractor.py --window 90 >> /var/log/code-review-training.log 2>&1
```

### Manual Retraining

```bash
# Train on last 90 days
python3 tools/code_review_pattern_extractor.py --window 90

# Train on last 30 days (faster, recent data only)
python3 tools/code_review_pattern_extractor.py --window 30

# Custom output location
python3 tools/code_review_pattern_extractor.py --window 90 --output /tmp/model.pkl
```

### Load Existing Model

```bash
# View statistics without retraining
python3 tools/code_review_pattern_extractor.py --load learning/code_review_pattern_extractor.pkl

# Run predictions on sample data
python3 tools/code_review_pattern_extractor.py --load learning/code_review_pattern_extractor.pkl --predict
```

## JavaScript API Reference

### `getTopReviewModels(n: number): Promise<Array>`

Returns top N performing models ranked by success rate and confidence.

**Parameters:**
- `n` - Number of models to return (default: 5)

**Returns:**
```typescript
Array<{
  model: string,
  success_rate: string,  // e.g., "84.6%"
  avg_confidence: string, // e.g., "0.95"
  reviews: number
}>
```

**Caching:** Results cached for 5 minutes

---

### `predictIssues(taskFeatures: Object): Promise<Object>`

Predicts likelihood of finding issues in a review task.

**Parameters:**
```typescript
{
  duration_ms?: number,
  input_tokens?: number,
  output_tokens?: number,
  files?: number,
  confidence?: number,
  categories?: number,
  severities?: number,
  outcome?: string,
  cost_usd?: number
}
```

**Returns:**
```typescript
{
  probability: number,  // 0.0 - 1.0
  message: string       // "High/Moderate/Low likelihood of finding issues"
}
```

---

### `getPatternStats(): Promise<Object>`

Returns historical pattern statistics.

**Returns:**
```typescript
{
  issue_categories: Object,
  severity_distribution: Object,
  task_complexity: Object,
  review_outcomes: Object,
  trained_at: string,
  version: string
}
```

**Caching:** Results cached for 5 minutes

---

### `getReviewStrategy(task: Object): Promise<Object>`

Recommends optimal review strategy based on task characteristics.

**Parameters:**
```typescript
{
  files: number,
  type: 'bug' | 'security' | 'style' | 'performance' | ...
}
```

**Returns:**
```typescript
{
  strategy: 'base' | 'maximum-coverage' | 'quintuple-verification',
  workers: Array<string>,
  arbiter: string,
  prediction: { probability: number, message: string },
  top_models: Array<Object>
}
```

---

### `retrainModel(windowDays: number): Promise<Object>`

Retrain model with latest workflow data.

**Parameters:**
- `windowDays` - Analysis window in days (default: 90)

**Returns:**
```typescript
{
  success: boolean,
  message: string
}
```

---

### `healthCheck(): Promise<Object>`

Check system health and model status.

**Returns:**
```typescript
{
  healthy: boolean,
  model_exists: boolean,
  trained_at: string,
  version: string,
  message: string
}
```

## Performance Optimization

### Caching

Both `getTopReviewModels()` and `getPatternStats()` use 5-minute TTL cache to avoid expensive Python subprocess calls.

**Cache hit:** < 1ms  
**Cache miss:** ~500ms (Python model loading)

### Timeouts

All Python subprocess calls have 30-second timeout with graceful fallback to defaults.

### Fallback Defaults

When model unavailable or Python fails:
- **Top models:** `[opus, command-a-03-2025, sonnet]`
- **Prediction probability:** `0.5` (50%)
- **Strategy:** `base` (3 workers)

## Testing

```bash
# Run full integration test suite
node tests/test-code-review-pattern-extractor.mjs

# Tests:
# ✅ Model file exists
# ✅ Health check
# ✅ Get top review models
# ✅ Predict issue likelihood
# ✅ Get pattern statistics
# ✅ Get review strategy recommendation
# ✅ Workflow integration example
# ✅ Model persistence check
```

**Test Results (2026-07-03):**
- Passed: 8/8 (100%)
- Failed: 0/8 (0%)

## Recommendations

### Immediate Actions

1. **Review task definitions** - 35.9% success rate is low
   - Clarify expected outputs
   - Add concrete examples
   - Validate inputs before execution

2. **Address critical issues** - 34 critical severity issues detected
   - Prioritize security reviews
   - Implement automated checks
   - Track resolution time

3. **Optimize simple tasks** - 58.7% are simple complexity
   - Automate with scripts
   - Create templates
   - Reduce model overhead

### Long-term Improvements

1. **Increase arbiter data** - 0 arbiter decisions in dataset
   - Track consensus outcomes
   - Measure validation accuracy
   - Tune rejection thresholds

2. **Expand training window** - Currently 90 days
   - Consider 180-day window for stability
   - Balance recency vs. data volume
   - Monitor distribution shifts

3. **Add new features** - Current 9 features
   - Code churn metrics
   - Test coverage
   - Developer experience level
   - Historical defect density

## Files Created

```
tools/code_review_pattern_extractor.py           (600 lines) - Core ML implementation
shared/code-review-pattern-adapter.cjs           (330 lines) - JavaScript API
tests/test-code-review-pattern-extractor.mjs     (200 lines) - Integration tests
learning/code_review_pattern_extractor.pkl       (313 KB)   - Trained model
learning/code_review_pattern_extractor_stats.json (1.5 KB)  - Model statistics
docs/CODE_REVIEW_PATTERN_EXTRACTOR.md            (this file) - Documentation
```

## Dependencies

**Python:**
- `psycopg2` - PostgreSQL adapter
- `scikit-learn` - ML models (RandomForestClassifier, StandardScaler, TfidfVectorizer)
- `numpy` - Numerical operations

**JavaScript:**
- `child_process` (Node.js built-in) - Python subprocess execution
- `fs`, `path` (Node.js built-in) - File operations

**Database:**
- PostgreSQL on `aio-01:5433`
- Database: `learning`
- Tables: `workflow.worker_results`, `workflow.arbiter_decisions`, `workflow.executions`

## Version History

- **1.0.0** (2026-07-03) - Initial release
  - Random Forest classifier (100 estimators, max_depth=10)
  - 9 features (duration, tokens, files, confidence, categories, severities, outcome, cost)
  - 94.62% test accuracy
  - JavaScript adapter with caching
  - Complete integration test suite

## Future Enhancements

1. **Multi-model ensemble** - Combine Random Forest + Gradient Boosting
2. **Deep learning features** - Extract semantic patterns from code
3. **Time series forecasting** - Predict future issue trends
4. **Active learning** - Request labels for uncertain predictions
5. **Explainability** - SHAP values for feature importance
6. **Real-time updates** - Incremental learning on new data

## Contact

**System:** Distributed LLM Orchestration Framework  
**Owner:** sfloess  
**Last Updated:** 2026-07-03
