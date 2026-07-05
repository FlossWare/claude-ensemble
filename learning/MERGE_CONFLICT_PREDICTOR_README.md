# Merge Conflict Predictor

**Status:** TRAINED (2026-07-03)  
**Model:** Random Forest Classifier  
**Location:** `~/.claude/learning/merge_conflict_predictor.pkl`  
**Integration:** PostgreSQL continual learning system

---

## Overview

Predicts merge conflicts **before** they happen by analyzing:
- File co-modification patterns (files changed together)
- Author conflict history (certain author pairs = higher risk)
- Time-based patterns (recently changed files = higher risk)
- Structural factors (file type, directory, LOC changes)

**Prevents:**
- Merge conflicts disrupting workflow
- Broken builds from unexpected interactions
- Time wasted resolving conflicts

**Use cases:**
- Pre-merge risk assessment (before creating PR)
- CI/CD integration (fail early on high-risk merges)
- Code review prioritization (review high-risk files first)
- Branch planning (identify risky parallel development)

---

## Quick Start

### 1. Train Model (one-time setup)

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 tools/merge_conflict_predictor.py --train
```

**Output:**
- Model saved to `~/.claude/learning/merge_conflict_predictor.pkl`
- Statistics saved to `~/.claude/learning/merge_conflict_stats.json`
- Metadata stored in PostgreSQL `learning.experiences`

### 2. Predict Conflicts

```bash
# Predict conflicts when merging feature-branch into main
python3 tools/merge_conflict_predictor.py --predict main feature-branch

# Predict conflicts when merging PR branch
python3 tools/merge_conflict_predictor.py --predict main fix/issue-273-fleet-executor
```

**Output:**
```
============================================================
Conflict Predictions: fix/issue-273-fleet-executor → main
============================================================

Total predictions: 12
  HIGH risk:   3
  MEDIUM risk: 5
  LOW risk:    4

------------------------------------------------------------
HIGH RISK Conflicts:
------------------------------------------------------------

  File 1: workflows/code-review.js
  File 2: workflows/code-solve.js
  Type:   cross_branch
  Probability: 87.23%

  File 1: shared/fleet-executor.js
  File 2: shared/fleet-executor.js
  Type:   direct_overlap
  Probability: 92.45%
```

Predictions saved to `~/.claude/learning/merge_conflict_predictions.json`

---

## How It Works

### Feature Extraction (7 features per file pair)

1. **Co-modification Count**
   - How many times files were modified in same commit
   - Higher count = higher coupling = higher conflict risk

2. **Extension Similarity**
   - Same file type = more likely to conflict
   - Example: `.js` files conflict with `.js`, not `.md`

3. **Directory Proximity**
   - Files in same directory = higher conflict risk
   - Shared parent directories = related functionality

4. **Recency (days since last change)**
   - Recently modified files = more active = higher risk
   - Stale files rarely conflict

5. **Max LOC (lines of code)**
   - Larger files = more complexity = higher conflict risk
   - Small files rarely conflict

6. **Modification Frequency (last 90 days)**
   - Frequently changed files = hotspots = higher risk
   - Stable files rarely conflict

7. **Author Overlap**
   - Same authors on both files = understand codebase = lower risk
   - Different authors = different styles = higher risk

### Machine Learning Model

**Algorithm:** Random Forest Classifier
- 100 decision trees
- Max depth: 10 (prevents overfitting)
- Balanced class weights (handles imbalanced data)
- Stratified train/test split (80/20)

**Training Data Sources:**
1. Historical merge commits (detects actual conflicts)
2. Co-modification patterns (last 90 days)
3. Author conflict history
4. File change statistics

**Prediction:**
- Probability score: 0.0 (no conflict) → 1.0 (certain conflict)
- Risk levels:
  - HIGH: >70% probability
  - MEDIUM: 40-70% probability
  - LOW: <40% probability

---

## Integration Examples

### CI/CD Pipeline (GitLab CI)

```yaml
merge_conflict_check:
  stage: test
  script:
    - python3 tools/merge_conflict_predictor.py --predict main $CI_COMMIT_REF_NAME
    - python3 -c "
import json
from pathlib import Path
with open(Path.home() / '.claude/learning/merge_conflict_predictions.json') as f:
    preds = json.load(f)
high_risk = [p for p in preds['predictions'] if p['risk'] == 'HIGH']
if len(high_risk) > 5:
    print(f'ERROR: {len(high_risk)} HIGH-risk conflicts predicted!')
    exit(1)
"
  only:
    - merge_requests
```

### Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-push

# Check if pushing to main/master
if [[ "$2" == *"main"* ]] || [[ "$2" == *"master"* ]]; then
    echo "Checking for merge conflicts..."
    python3 tools/merge_conflict_predictor.py --predict main HEAD
    
    # Warn if high-risk conflicts
    HIGH_RISK=$(python3 -c "
import json
from pathlib import Path
try:
    with open(Path.home() / '.claude/learning/merge_conflict_predictions.json') as f:
        preds = json.load(f)
    print(len([p for p in preds['predictions'] if p['risk'] == 'HIGH']))
except:
    print(0)
")
    
    if [ "$HIGH_RISK" -gt 0 ]; then
        echo "⚠ WARNING: $HIGH_RISK high-risk conflicts predicted!"
        echo "Consider reviewing merge strategy before pushing."
    fi
fi
```

### Code Review Bot

```javascript
const { execSync } = require('child_process');
const fs = require('fs');

// Run predictor
execSync(`python3 tools/merge_conflict_predictor.py --predict main ${prBranch}`);

// Parse results
const predictions = JSON.parse(
  fs.readFileSync(`${process.env.HOME}/.claude/learning/merge_conflict_predictions.json`)
);

const highRisk = predictions.predictions.filter(p => p.risk === 'HIGH');

if (highRisk.length > 0) {
  // Post comment to PR
  await github.issues.createComment({
    owner, repo, issue_number: prNumber,
    body: `⚠️ **Merge Conflict Risk Analysis**\n\n` +
          `Found ${highRisk.length} HIGH-risk conflicts:\n\n` +
          highRisk.map(p => 
            `- \`${p.file1}\` ↔ \`${p.file2}\` (${(p.conflict_probability * 100).toFixed(1)}%)`
          ).join('\n')
  });
}
```

---

## Maintenance

### Retrain Model (periodic updates)

Retrain monthly or after major refactoring:

```bash
python3 tools/merge_conflict_predictor.py --train
```

**When to retrain:**
- New merge conflicts resolved (model learns from mistakes)
- Codebase structure changes (new directories, file types)
- Team changes (new author pairs)
- Every 30 days (catch drift in development patterns)

### Monitor Model Performance

Check PostgreSQL for model metadata:

```python
from postgres_adapter import get_db

db = get_db()
result = db.query("""
    SELECT problem_type, strategy, success, reward, 
           novelty_score, importance, timestamp
    FROM learning.experiences
    WHERE problem_type = 'merge_conflict_prediction'
    ORDER BY timestamp DESC
    LIMIT 5
""")

for row in result:
    print(f"{row['timestamp']}: reward={row['reward']}, novelty={row['novelty_score']}")
```

### Adjust Risk Thresholds

Edit `merge_conflict_predictor.py` if thresholds need tuning:

```python
# Current thresholds
'risk': 'HIGH' if prob > 0.7 else 'MEDIUM' if prob > 0.4 else 'LOW'

# More conservative (fewer false alarms)
'risk': 'HIGH' if prob > 0.85 else 'MEDIUM' if prob > 0.6 else 'LOW'

# More aggressive (catch more potential conflicts)
'risk': 'HIGH' if prob > 0.5 else 'MEDIUM' if prob > 0.25 else 'LOW'
```

---

## Current Training Stats

**Last trained:** 2026-07-03 18:38:02

**Dataset:**
- Total merges analyzed: 5
- Conflict merges: 1 (20% conflict rate)
- Unique files tracked: 2,864
- Author pairs analyzed: 1
- Training samples: 20 (with synthetic augmentation)

**Top Co-Modified File Pairs:**
1. `workflows/code-review.js` ↔ `workflows/code-solve.js` (17× together)
2. `workflows/ai-web-learn-fleet.js` ↔ `workflows/code-review.js` (16×)
3. Learning research files (web-synthesis-*.json) (16× each)

**Feature Importances** (higher = more predictive):
- Co-modification count: Most important predictor
- Directory proximity: Second most important
- Recency/Frequency: Moderate importance
- Author overlap: Helps distinguish false positives

---

## Troubleshooting

### "Model not trained" error

```bash
# Train model first
python3 tools/merge_conflict_predictor.py --train
```

### "No common ancestor found" warning

```bash
# Branches diverged too far - update local branches
git fetch origin
git checkout main && git pull
git checkout feature-branch && git rebase main

# Try prediction again
python3 tools/merge_conflict_predictor.py --predict main feature-branch
```

### Prediction too slow

```bash
# Reduce lookback window in code (default: 90 days)
# Edit merge_conflict_predictor.py line 251:
extract_file_comodification_patterns(lookback_days=30)  # Was 90
```

### Model predicts no conflicts but merge fails

This means:
- New conflict pattern not in training data (retrain model)
- Non-file conflict (branch divergence, deleted files)
- Model needs more training samples

**Fix:** Retrain after resolving conflict so model learns.

---

## Files Created

**Model & Stats:**
- `~/.claude/learning/merge_conflict_predictor.pkl` (36KB)
- `~/.claude/learning/merge_conflict_stats.json` (13MB - co-modification matrix)
- `~/.claude/learning/merge_conflict_predictions.json` (latest prediction results)

**Code:**
- `tools/merge_conflict_predictor.py` (main implementation)
- `learning/MERGE_CONFLICT_PREDICTOR_README.md` (this file)

**Database:**
- PostgreSQL `learning.experiences` (model metadata)
- Adapter: `~/.claude/learning/postgres_adapter.py`

---

## API Reference

### Command Line

```bash
# Train model
python3 tools/merge_conflict_predictor.py --train [--repo /path/to/repo]

# Predict conflicts
python3 tools/merge_conflict_predictor.py --predict BRANCH1 BRANCH2 [--repo /path/to/repo]
```

### Python API

```python
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from merge_conflict_predictor import MergeConflictPredictor

# Initialize
predictor = MergeConflictPredictor(repo_path='/path/to/repo')

# Train
predictor.train()

# Predict
predictions = predictor.predict('main', 'feature-branch')

for p in predictions:
    if p['risk'] == 'HIGH':
        print(f"HIGH RISK: {p['file1']} ↔ {p['file2']}")
        print(f"  Probability: {p['conflict_probability']:.2%}")
```

---

## Future Enhancements

**Planned:**
1. Semantic conflict detection (function signature changes)
2. Test coverage correlation (low coverage = higher risk)
3. Continuous learning (auto-retrain on new merges)
4. Multi-repository support (learn across projects)
5. Conflict resolution suggestions (based on past resolutions)

**Integration targets:**
- GitHub Actions workflow
- GitLab CI/CD pipeline
- Slack/Discord notifications
- Grafana dashboard metrics

---

## License & Attribution

Part of Claude Global Skills orchestration framework.

**Dependencies:**
- scikit-learn (Random Forest)
- numpy (feature vectors)
- psycopg2 (PostgreSQL integration)
- Git (conflict history extraction)

**References:**
- PostgreSQL pgvector for embedding similarity
- Thompson Sampling bandit (strategy selection)
- Continual learning infrastructure (experience memory)
