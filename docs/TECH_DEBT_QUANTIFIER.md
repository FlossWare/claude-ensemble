# Tech Debt Quantifier

**ML-based technical debt scoring system for proactive code quality management**

## Overview

The Tech Debt Quantifier uses machine learning to automatically assess technical debt across your codebase, providing actionable metrics and prioritized recommendations for improvement.

### Key Features

- **Automated Debt Scoring** - 0-100 scale with severity categorization
- **Priority Ranking** - Identifies which files need immediate attention
- **Cost Estimation** - Predicts hours needed to fix debt
- **Multi-dimensional Analysis** - Complexity, maintainability, code smells, quality metrics
- **Integration Ready** - Works with workflow storage and CI/CD pipelines

## Model Architecture

### Algorithm

- **Debt Scorer:** Gradient Boosting Regressor (150 estimators)
- **Priority Scorer:** Random Forest Regressor (100 estimators)
- **Feature Scaler:** StandardScaler (31 features)

### Performance (Test Set)

| Metric | Debt Score | Priority Score |
|--------|-----------|----------------|
| R² | 0.889 | 0.880 |
| MAE | 4.5 points | 5.0 points |
| RMSE | 5.9 points | 6.3 points |
| CV R² | 0.853 ± 0.037 | 0.856 ± 0.014 |

**Training Data:** 400 samples (synthetic + historical execution data)  
**Test Data:** 100 samples  
**Features:** 31 (static analysis + quality metrics + historical performance)

## Feature Categories

### Static Code Analysis (21 features)

- **Complexity Metrics:** Cyclomatic, cognitive complexity, nesting depth
- **Size Metrics:** LOC, function count, class count, function length
- **Code Smells:** Long methods, long parameter lists, deeply nested blocks, magic numbers
- **Documentation:** Comment ratio, TODOs, FIXMEs, HACKs
- **Quality Indicators:** Duplication, global variables

### Quality Metrics (6 features)

- Mean quality score (from quality_thresholds.json)
- Success rate
- Failure count
- Average duration
- Retry count
- Verification trigger status

### Derived Features (4 features)

- **Maintainability Index** (0-100, Microsoft formula)
- **Complexity Category** (1-4 scale)
- **Debt Indicators** (count of TODOs/FIXMEs/HACKs)
- **Smell Score** (weighted sum of code smells)

## Feature Importance

### Top 8 Features (Debt Score)

| Feature | Importance |
|---------|------------|
| smell_score | 43.7% |
| num_failures | 18.7% |
| debt_indicators | 16.6% |
| has_tests | 9.3% |
| num_todos | 2.8% |
| mean_quality_score | 2.6% |
| avg_function_length | 1.0% |
| maintainability_index | 0.6% |

### Top 8 Features (Priority Score)

| Feature | Importance |
|---------|------------|
| num_failures | 42.3% |
| verification_triggered | 15.5% |
| cyclomatic_complexity | 9.1% |
| cognitive_complexity | 8.3% |
| complexity_category | 4.5% |
| smell_score | 4.3% |
| success_rate | 3.8% |
| maintainability_index | 2.6% |

## Debt Score Interpretation

| Score | Level | Meaning | Action |
|-------|-------|---------|--------|
| 0-19 | EXCELLENT | Minimal debt | No action needed |
| 20-39 | GOOD | Low debt | Minor cleanup recommended |
| 40-59 | MODERATE | Medium debt | Refactoring should be prioritized |
| 60-79 | HIGH | Significant debt | Urgent refactoring needed |
| 80-100 | CRITICAL | Severe debt | Immediate attention required |

## Usage

### Train the Model

```bash
python3 tools/tech_debt_quantifier.py
```

**Output:**
- Model: `~/.claude/learning/tech_debt_quantifier.pkl` (2.5MB)
- Stats: `~/.claude/learning/tech_debt_quantifier_stats.json`

### Analyze a Directory

```bash
python3 tools/analyze_tech_debt.py <directory> [options]

Options:
  --threshold <score>  Flag files above this score (default: 60)
  --top <n>            Show top N files by priority (default: 10)
  --json               Output as JSON
```

**Example:**

```bash
python3 tools/analyze_tech_debt.py ./tools --threshold 70 --top 20
```

**Output:**

```
============================================================
TECH DEBT SUMMARY
============================================================

📊 Total Files:          64
💳 Average Debt Score:   61.3/100
⏱️  Total Fix Estimate:   196.0 hours
🚨 Critical Files:       27

🔝 TOP 5 PRIORITY FILES:
────────────────────────────────────────────────────────────

1. tech_debt_quantifier.py
   Debt:     88.6/100 (CRITICAL)
   Priority: 60.7/100
   Fix Time: 4.4h
   → Immediate attention required
...
```

### Analyze a Single File

```bash
python3 tools/analyze_tech_debt.py <file_path>
```

**Example:**

```bash
python3 tools/analyze_tech_debt.py tools/complexity_estimator.py
```

**Output:**

```
============================================================
TECH DEBT ANALYSIS: complexity_estimator.py
============================================================

📊 Debt Score:      86.2/100
🎯 Priority Score:  55.5/100
📈 Debt Level:      CRITICAL
⏱️  Fix Estimate:    4.3 hours

💡 Recommendation: Immediate attention required

📋 Metrics:
  Maintainability Index: 72.3
  Code Smell Score:      18.0
  Debt Indicators:       0
```

### Integration Script (Node.js)

```bash
node tools/integrate_tech_debt.cjs <directory> [options]

Options:
  --threshold <score>  Debt score threshold (default: 60)
  --top <n>            Show top N files (default: 10)
  --report <path>      Generate markdown report
  --store              Store results in workflow database
  --file <path>        Analyze single file
```

**Example:**

```bash
# Generate report
node tools/integrate_tech_debt.cjs ./tools --report report.md

# Store in workflow database
node tools/integrate_tech_debt.cjs ./tools --store

# Analyze single file
node tools/integrate_tech_debt.cjs --file ./tools/complexity_estimator.py
```

### Programmatic Usage (JavaScript)

```javascript
const { analyzeTechDebt, generateReport } = require('./tools/integrate_tech_debt.cjs');

// Analyze directory
const results = analyzeTechDebt('./src', {
  threshold: 70,
  topN: 20
});

// Generate report
generateReport(results, 'tech_debt_report.md');

// Access results
console.log(`Critical files: ${results.critical_files}`);
console.log(`Fix estimate: ${results.total_estimated_fix_hours}h`);
```

### Programmatic Usage (Python)

```python
from tech_debt_quantifier import TechDebtQuantifier

# Load trained model
quantifier = TechDebtQuantifier()
quantifier.load('~/.claude/learning/tech_debt_quantifier.pkl')

# Analyze single file
result = quantifier.predict('path/to/file.py')
print(f"Debt: {result['debt_score']:.1f}/100")
print(f"Level: {result['debt_level']}")
print(f"Fix: {result['estimated_fix_hours']:.1f}h")

# Analyze directory
summary = quantifier.analyze_directory('./src')
print(f"Total files: {summary['total_files']}")
print(f"Avg debt: {summary['avg_debt_score']:.1f}/100")
print(f"Critical: {summary['critical_files']}")

# Top priority files
for file in summary['top_priority_files'][:5]:
    print(f"{file['file_path']}: {file['debt_score']:.1f}")
```

## CI/CD Integration

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Analyze changed files
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|js|mjs|java)$')

if [ -n "$CHANGED_FILES" ]; then
  for FILE in $CHANGED_FILES; do
    RESULT=$(python3 tools/analyze_tech_debt.py "$FILE" --json 2>/dev/null)
    DEBT=$(echo "$RESULT" | jq -r '.debt_score // 0')
    
    if (( $(echo "$DEBT > 80" | bc -l) )); then
      echo "❌ CRITICAL tech debt in $FILE (score: $DEBT/100)"
      exit 1
    fi
  done
fi
```

### GitHub Actions

```yaml
name: Tech Debt Monitor

on: [pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install numpy scikit-learn
      
      - name: Analyze Tech Debt
        run: |
          python3 tools/tech_debt_quantifier.py
          node tools/integrate_tech_debt.cjs . --report report.md
      
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: tech-debt-report
          path: report.md
      
      - name: Check Threshold
        run: |
          CRITICAL=$(grep -c "CRITICAL" report.md || true)
          if [ $CRITICAL -gt 10 ]; then
            echo "Too many critical files: $CRITICAL"
            exit 1
          fi
```

## Workflow Storage Integration

Results can be automatically stored in the PostgreSQL workflow database:

```javascript
const { storeResults } = require('./tools/integrate_tech_debt.cjs');

const results = analyzeTechDebt('./src');
await storeResults(results, {
  description: 'Weekly tech debt scan',
  duration_ms: 15000
});
```

**Stored data:**
- Execution metadata
- Top priority files
- Actionable insights
- Importance score (based on avg debt)

**Query stored results:**

```sql
SELECT 
  description,
  actionable_insight,
  importance,
  created_at
FROM workflow.learnings
WHERE description LIKE '%Tech debt%'
ORDER BY created_at DESC;
```

## Maintenance

### Retrain with Real Data

As execution history grows, retrain with actual data:

```python
from tech_debt_quantifier import TechDebtQuantifier

quantifier = TechDebtQuantifier()

# Load from PostgreSQL workflow.worker_results
training_data = quantifier.load_database_training_data()

# Train with real data
stats = quantifier.train(training_data)

# Save updated model
quantifier.save('~/.claude/learning/tech_debt_quantifier.pkl')
```

### Update Features

To add new features:

1. Update `extract_static_features()` or `extract_quality_features()`
2. Add feature to synthetic data generation
3. Retrain model
4. Verify feature importance

### Tune Hyperparameters

Adjust in `train()` method:

```python
# Debt scorer (Gradient Boosting)
self.debt_model = GradientBoostingRegressor(
    n_estimators=150,      # Increase for better accuracy
    max_depth=7,           # Increase for complex patterns
    learning_rate=0.1,     # Decrease for stability
)

# Priority scorer (Random Forest)
self.priority_model = RandomForestRegressor(
    n_estimators=100,      # Increase for stability
    max_depth=10,          # Adjust for overfitting
    min_samples_split=5,   # Increase to prevent overfitting
)
```

## Limitations

1. **Synthetic Training Data:** Initial model trained on synthetic data; accuracy improves with real execution history
2. **Language Coverage:** Heuristics work best for Python/JavaScript/Java; may need tuning for other languages
3. **Static Analysis Only:** Does not execute code or run dynamic analysis
4. **No AST Parsing:** Uses regex/heuristics instead of proper parsing (faster but less precise)

## Future Enhancements

- [ ] AST-based analysis for precise complexity metrics
- [ ] Test coverage integration (pytest-cov, Istanbul)
- [ ] Security vulnerability scanning (Bandit, ESLint)
- [ ] Dependency staleness detection
- [ ] Git history analysis (churn, bug correlation)
- [ ] Real-time monitoring dashboard
- [ ] Automated refactoring suggestions
- [ ] Multi-language support (C++, Rust, Go)

## Files

| File | Purpose |
|------|---------|
| `tools/tech_debt_quantifier.py` | Core ML model (training + prediction) |
| `tools/analyze_tech_debt.py` | CLI tool for analysis |
| `tools/integrate_tech_debt.cjs` | Node.js integration script |
| `~/.claude/learning/tech_debt_quantifier.pkl` | Trained model (2.5MB) |
| `~/.claude/learning/tech_debt_quantifier_stats.json` | Model statistics |
| `docs/TECH_DEBT_QUANTIFIER.md` | This documentation |

## Examples

### Weekly Cron Job

```bash
#!/bin/bash
# Daily tech debt scan

cd /path/to/project
node tools/integrate_tech_debt.cjs . \
  --threshold 70 \
  --report /var/reports/tech_debt_$(date +%Y%m%d).md \
  --store

# Email if critical files increase
CRITICAL=$(grep -c "CRITICAL" /var/reports/tech_debt_$(date +%Y%m%d).md)
if [ $CRITICAL -gt 20 ]; then
  mail -s "Tech Debt Alert: $CRITICAL critical files" team@example.com < /var/reports/tech_debt_$(date +%Y%m%d).md
fi
```

### Pre-release Quality Gate

```bash
# Before tagging release
node tools/integrate_tech_debt.cjs . --threshold 60 > /tmp/debt.json
AVG_DEBT=$(jq -r '.avg_debt_score' /tmp/debt.json)

if (( $(echo "$AVG_DEBT > 50" | bc -l) )); then
  echo "❌ Cannot release: avg debt = $AVG_DEBT"
  exit 1
fi
```

## Support

For issues or questions:
- Review this documentation
- Check model stats: `cat ~/.claude/learning/tech_debt_quantifier_stats.json | jq`
- Verify model exists: `ls -lh ~/.claude/learning/tech_debt_quantifier.pkl`
- Retrain if needed: `python3 tools/tech_debt_quantifier.py`

---

**Last Updated:** 2026-07-03  
**Model Version:** 1.0.0  
**Status:** Production-ready ✅
