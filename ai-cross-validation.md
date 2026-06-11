# AI Cross-Validation Framework

Cross-validation and A/B testing framework for evaluating and comparing different AI consensus strategies.

## Purpose

Systematically evaluate the performance of different multi-AI consensus strategies (weighted, filtered, debate, refinement, basic) using rigorous statistical methods:

- **K-Fold Cross-Validation**: Split dataset into k folds, train on k-1, test on 1, rotate through all folds
- **Train/Test Split**: Traditional holdout validation with configurable split ratio
- **A/B Testing**: Compare multiple strategies head-to-head on the same test set
- **Bootstrap Confidence Intervals**: Compute 95% confidence intervals via resampling
- **Multiple Metrics**: Accuracy, precision, recall, F1, confidence calibration, MAE

## Installation

```bash
chmod +x ai-cross-validation.js
```

## Usage

### Basic K-Fold Cross-Validation

```bash
/ai-cross-validation --dataset my-dataset.json --k-folds 5 --report
```

### A/B Test Multiple Strategies

```bash
/ai-cross-validation \
  --dataset my-dataset.json \
  --ab-test \
  --strategies weighted,filtered,debate \
  --test-split 0.3 \
  --bootstrap 1000 \
  --report
```

### Custom Metrics and Output

```bash
/ai-cross-validation \
  --dataset tasks.json \
  --strategies refinement,basic \
  --k-folds 10 \
  --metrics accuracy,f1,confidence \
  --output results/experiment-1.json \
  --primary-metric f1
```

## Dataset Format

The dataset should be a JSON array where each item contains:

```json
[
  {
    "task": "Classify this sentiment: I love this product!",
    "label": "positive",
    "value": 0.95
  },
  {
    "task": "Determine if this is spam: Buy now!",
    "label": "spam",
    "value": 1
  }
]
```

**Fields:**
- `task` (required): The prompt/task to send to the AI consensus strategy
- `label` (required for classification): Ground truth label (e.g., "positive", "negative", "spam", "ham")
- `value` (optional for regression): Ground truth numeric value

## Options

### Dataset & Strategies

- `--dataset <path>`: Path to JSON dataset file (required)
- `--strategies <list>`: Comma-separated strategies to test
  - Available: `weighted`, `filtered`, `debate`, `refinement`, `basic`
  - Default: all strategies

### Cross-Validation

- `--k-folds <n>`: Number of folds for k-fold CV (default: 5)
- `--test-split <ratio>`: Train/test split ratio for A/B test (default: 0.2)
- `--ab-test`: Run A/B test instead of k-fold CV

### Metrics & Analysis

- `--metrics <list>`: Comma-separated metrics to compute
  - Available: `accuracy`, `precision`, `recall`, `f1`, `confidence`
  - Default: all metrics
- `--primary-metric <name>`: Primary metric for strategy comparison (default: `accuracy`)
- `--bootstrap <n>`: Bootstrap iterations for confidence intervals (default: 1000)

### Output

- `--output <path>`: Output JSON path (default: `./cv-results.json`)
- `--report`: Generate human-readable markdown report (saves as `.md`)
- `--timeout <ms>`: Timeout per agent call in milliseconds (default: 300000)

## Output Format

### JSON Results

```json
{
  "timestamp": "2026-06-10T12:00:00.000Z",
  "options": { ... },
  "crossValidation": {
    "weighted": {
      "strategy": "weighted",
      "kFolds": 5,
      "foldResults": [...],
      "aggregated": {
        "accuracy": {
          "mean": 0.8542,
          "std": 0.0234,
          "values": [0.85, 0.87, 0.84, 0.85, 0.86]
        },
        "f1": { ... }
      }
    }
  },
  "abTest": {
    "results": {
      "weighted": {
        "metrics": {
          "accuracy": 0.8542,
          "precision": 0.8234,
          "recall": 0.8891,
          "f1": 0.8549
        },
        "bootstrap": {
          "accuracy": {
            "mean": 0.8542,
            "ci95": [0.8201, 0.8883]
          }
        }
      }
    },
    "comparison": {
      "winner": "weighted",
      "maxMetric": 0.8542
    },
    "testSize": 20,
    "trainSize": 80
  }
}
```

### Markdown Report

When `--report` is specified, generates a human-readable markdown report with:

- K-fold CV results table per strategy
- A/B test comparison table
- Bootstrap confidence intervals
- Winner declaration

Example:

```markdown
# AI Consensus Strategy Cross-Validation Report

## K-Fold Cross-Validation Results

### Strategy: weighted

K-Folds: 5

| Metric | Mean | Std Dev |
|--------|------|----------|
| accuracy | 0.8542 | 0.0234 |
| f1 | 0.8549 | 0.0189 |

## A/B Test Results

Winner: **weighted**

### Strategy Comparison

| Strategy | Accuracy | Precision | Recall | F1 |
|----------|----------|-----------|--------|-----|
| weighted | 0.8542 | 0.8234 | 0.8891 | 0.8549 |
| filtered | 0.8301 | 0.8100 | 0.8502 | 0.8296 |
```

## Metrics Explained

### Classification Metrics

- **Accuracy**: (TP + TN) / Total - Overall correctness
- **Precision**: TP / (TP + FP) - Positive predictive value
- **Recall**: TP / (TP + FN) - True positive rate
- **F1 Score**: Harmonic mean of precision and recall

### Regression Metrics

- **MAE** (Mean Absolute Error): Average absolute difference between predictions and ground truth

### Confidence Metrics

- **avgConfidence**: Average confidence score reported by strategies
- **calibrationError**: Expected Calibration Error - measures if confidence matches actual correctness

## Strategies

### weighted
Uses confidence-weighted voting/averaging across multiple AI models.

### filtered
Only synthesizes responses above a confidence threshold.

### debate
Adversarial debate with workers proposing, exchanging critiques, and arbiter judging.

### refinement
Iterative refinement via arbiter critique until confidence threshold is met.

### basic
Simple multi-AI consensus with arbiter synthesis.

## Example Workflow

1. **Collect labeled dataset**: Gather tasks with ground truth labels/values
2. **Run k-fold CV**: Test all strategies to get unbiased performance estimates
3. **Analyze results**: Compare mean metrics and standard deviations
4. **Run A/B test**: Head-to-head comparison on holdout test set
5. **Bootstrap CI**: Get confidence intervals for winner selection
6. **Deploy winner**: Use the best-performing strategy in production

## Sample Dataset Creation

```javascript
// classification-tasks.json
[
  {
    "task": "Is this code vulnerable to SQL injection? SELECT * FROM users WHERE id = '" + userId + "'",
    "label": "vulnerable"
  },
  {
    "task": "Is this code vulnerable to SQL injection? db.query('SELECT * FROM users WHERE id = ?', [userId])",
    "label": "safe"
  },
  {
    "task": "Classify sentiment: This is the worst experience ever!",
    "label": "negative"
  },
  {
    "task": "Classify sentiment: Absolutely amazing, highly recommend!",
    "label": "positive"
  }
]
```

## Advanced Usage

### Custom Metric Comparison

```bash
# Compare strategies on F1 instead of accuracy
/ai-cross-validation \
  --dataset sentiment-tasks.json \
  --ab-test \
  --primary-metric f1 \
  --bootstrap 2000
```

### High-Confidence Testing

```bash
# Test only high-confidence strategies
/ai-cross-validation \
  --dataset security-audit.json \
  --strategies filtered,refinement \
  --k-folds 10
```

### Quick Validation

```bash
# Fast validation with fewer folds
/ai-cross-validation \
  --dataset quick-test.json \
  --k-folds 3 \
  --bootstrap 500
```

## Integration with Other Skills

### With ai-cost-tracker

Track costs during cross-validation:

```bash
# Enable cost tracking in AI consensus strategies
# Then run cross-validation
/ai-cross-validation --dataset tasks.json --ab-test
```

### With ai-confidence-calibration

Use calibration data to improve confidence scoring:

```bash
# First calibrate models
/ai-confidence-calibration --record <model> <confidence> <outcome>

# Then run CV with calibrated confidence
/ai-cross-validation --dataset tasks.json --metrics calibrationError
```

## Statistical Methods

### K-Fold Cross-Validation

- Divides dataset into k equal-sized folds
- Trains on k-1 folds, tests on 1 fold
- Rotates through all k folds
- Aggregates metrics: mean and standard deviation
- Reduces variance compared to single train/test split

### Bootstrap Resampling

- Randomly samples with replacement from test set
- Repeats n times (default 1000)
- Computes metric for each sample
- Calculates 95% confidence interval from distribution
- Provides uncertainty quantification

### A/B Testing

- Single train/test split
- All strategies tested on same test set
- Fair head-to-head comparison
- Winner selected by primary metric
- Bootstrap CI quantifies statistical significance

## Best Practices

1. **Dataset Size**: Use at least 100 samples for reliable CV, 500+ for bootstrap CI
2. **Stratification**: Ensure balanced class distribution across folds
3. **Multiple Metrics**: Don't rely on accuracy alone - check precision, recall, F1
4. **Confidence Calibration**: Monitor calibration error to ensure confidence scores are meaningful
5. **Statistical Significance**: Use bootstrap CI to confirm winner is statistically better
6. **Reproducibility**: Set random seed for reproducible fold splits (future enhancement)

## Limitations

- Requires labeled ground truth dataset
- Computational cost scales with dataset size × strategies × folds
- Agent timeouts may affect results for complex tasks
- No stratified k-fold (random shuffle only)
- No multi-class confusion matrix (binary only currently)

## Future Enhancements

- Stratified k-fold for imbalanced datasets
- Multi-class confusion matrices
- ROC/AUC curves for binary classification
- Learning curves (performance vs dataset size)
- Hyperparameter tuning integration
- Parallel fold execution
- Random seed control
- Cross-project validation (train on A, test on B)

## Module API

Can be imported and used programmatically:

```javascript
const cv = require('./ai-cross-validation.js');

// Run k-fold CV
const results = await cv.kFoldCrossValidation(dataset, 'weighted', 5, options);

// Run A/B test
const abResults = await cv.abTest(dataset, ['weighted', 'filtered'], options);

// Compute metrics
const metrics = cv.computeMetrics(predictions, groundTruth, { classification: true });

// Bootstrap confidence intervals
const ci = cv.bootstrap(data, metricFunction, 1000);
```

## Related Skills

- `/ai-consensus` - Basic multi-AI consensus
- `/ai-consensus-weighted` - Confidence-weighted consensus
- `/ai-consensus-filtered` - Filtered consensus
- `/ai-consensus-debate` - Adversarial debate consensus
- `/ai-consensus-refinement` - Refinement-based consensus
- `/ai-confidence-calibration` - Confidence calibration tracking
- `/ai-cost-tracker` - Cost tracking for AI calls

## References

- Cross-Validation: Kohavi, R. (1995). "A study of cross-validation and bootstrap for accuracy estimation and model selection"
- Bootstrap: Efron, B., & Tibshirani, R. J. (1994). "An introduction to the bootstrap"
- Calibration: Guo, C., et al. (2017). "On Calibration of Modern Neural Networks"
