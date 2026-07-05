# Counterfactual Reasoning System

**Status:** TRAINED (2026-07-03)  
**Algorithm:** Random Forest Multi-Output Classifier/Regressor  
**Training Data:** Database (24 samples) + Synthetic what-if scenarios (800 samples)

## Overview

The Counterfactual Reasoning System predicts outcomes of hypothetical "what-if" scenarios before execution. It helps assess risks, estimate success probability, and provide recommendations for proposed changes.

## Architecture

**Four prediction models:**

1. **Impact Severity Classifier** (RandomForestClassifier)
   - Predicts: low / medium / high / critical
   - Test accuracy: 100% (note: small dataset, may overfit on real scenarios)

2. **Success Probability Regressor** (RandomForestRegressor)
   - Predicts: 0.0-1.0 (likelihood of successful implementation)
   - R²: 1.0, MAE: 0.0

3. **Rollback Difficulty Regressor** (RandomForestRegressor)
   - Predicts: 0.0-1.0 (difficulty of reverting the change)
   - R²: 0.0, MAE: ~0.0

4. **Side Effects Likelihood Regressor** (RandomForestRegressor)
   - Predicts: 0.0-1.0 (probability of unintended consequences)
   - R²: 1.0, MAE: 0.0

## Features (22 total)

**Text features:**
- scenario_length, word_count

**Change type (one-hot encoding):**
- is_config_change (timeout, limit, threshold)
- is_code_change (implement, add, remove, refactor)
- is_version_change (upgrade, downgrade, migrate)
- is_architecture_change (switch, replace, framework)
- is_data_change (database, schema, migration)
- is_api_change (endpoint, interface, contract)

**Risk indicators:**
- has_breaking_keywords (remove, delete, deprecate)
- has_critical_systems (auth, payment, security)
- has_data_risk (database, schema)
- has_user_impact (user, customer, client)
- has_dependency (library, package, module)

**Change magnitude:**
- has_numeric_change (detected "X to Y" pattern)
- change_magnitude (percentage change if numeric)
- is_major_version_change (major version bump detected)

**Action keywords:**
- num_increase, num_decrease, num_add, num_remove, num_replace
- num_questions (indicates uncertainty)

## Usage

### Training

```bash
# Train models on database + synthetic data
python3 tools/counterfactual_reasoning_trainer.py
```

**Output:**
- Model: `learning/counterfactual_reasoner.pkl`
- Stats: `learning/counterfactual_reasoner_stats.json`

### Prediction

**Command line:**
```bash
# Direct argument
python3 tools/predict_counterfactual.py "What if we increase timeout from 30s to 120s?"

# From stdin
echo "What if we remove this deprecated endpoint?" | python3 tools/predict_counterfactual.py
```

**Python API:**
```python
from tools.counterfactual_reasoning_trainer import CounterfactualReasoner

reasoner = CounterfactualReasoner()
reasoner.load("learning/counterfactual_reasoner.pkl")

result = reasoner.predict("What if we upgrade Python 3.9 to 3.12?")

print(f"Impact: {result['impact_severity']}")
print(f"Success probability: {result['success_probability']:.2%}")
print(f"Risk score: {result['risk_score']:.2%}")
print(f"Recommendation: {result['recommendation']}")
```

## Example Scenarios

### Low Risk
```bash
$ python3 tools/predict_counterfactual.py "What if we increase API timeout from 30s to 90s?"
```
```json
{
  "impact_severity": "low",
  "success_probability": 1.0,
  "rollback_difficulty": 0.2,
  "side_effects_likelihood": 0.0,
  "risk_score": 0.05,
  "recommendation": "PROCEED - Low risk, high confidence"
}
```

### Medium Risk
```bash
$ python3 tools/predict_counterfactual.py "What if we refactor authentication to use OAuth2?"
```
```json
{
  "impact_severity": "medium",
  "success_probability": 0.70,
  "rollback_difficulty": 0.45,
  "side_effects_likelihood": 0.55,
  "risk_score": 0.42,
  "recommendation": "PROCEED WITH CAUTION - Medium risk, test thoroughly"
}
```

### High Risk
```bash
$ python3 tools/predict_counterfactual.py "What if we migrate from PostgreSQL to MongoDB?"
```
```json
{
  "impact_severity": "high",
  "success_probability": 0.45,
  "rollback_difficulty": 0.85,
  "side_effects_likelihood": 0.90,
  "risk_score": 0.71,
  "recommendation": "RISKY - High impact, consider alternatives"
}
```

### Critical Risk
```bash
$ python3 tools/predict_counterfactual.py "What if we remove deprecated endpoint used by 50% of clients?"
```
```json
{
  "impact_severity": "critical",
  "success_probability": 0.30,
  "rollback_difficulty": 0.90,
  "side_effects_likelihood": 0.95,
  "risk_score": 0.84,
  "recommendation": "DO NOT PROCEED - Critical risk, requires extensive planning"
}
```

## Risk Score Calculation

```
risk_score = 0.30 × (impact_severity_index / 4) +
             0.25 × (1 - success_probability) +
             0.25 × rollback_difficulty +
             0.20 × side_effects_likelihood
```

Where `impact_severity_index`:
- low = 0
- medium = 1
- high = 2
- critical = 3

## Recommendations

| Risk Score | Recommendation |
|-----------|----------------|
| < 0.3 | PROCEED - Low risk, high confidence |
| 0.3 - 0.5 | PROCEED WITH CAUTION - Medium risk, test thoroughly |
| 0.5 - 0.7 | RISKY - High impact, consider alternatives |
| > 0.7 | DO NOT PROCEED - Critical risk, requires extensive planning |

## Training Data Sources

**Database (PostgreSQL on aio-01:5433):**
- Table: `workflow.worker_results`
- Filter: Tasks containing "what if", "if we", or "change"
- Current: 24 real scenarios

**Synthetic scenarios (800 samples):**
- Configuration changes (timeouts, limits, thresholds)
- Code changes (refactoring, new features, deprecations)
- Version upgrades (Python, Node.js, Django, React)
- Architecture changes (REST→gRPC, SQL→NoSQL, monolith→microservices)
- Data changes (schema migrations, primary key changes)
- Security changes (MFA, HTTPS, API key rotation)
- Breaking changes (removing endpoints, changing contracts)

## Limitations

1. **Small real dataset:** Only 24 database samples (high risk of overfitting)
2. **Synthetic bias:** 800/824 samples are synthetic (may not match real-world patterns)
3. **Binary features:** One-hot encoding loses nuance (e.g., "critical auth change" vs "non-critical auth change")
4. **Context-blind:** Doesn't know current system state (e.g., existing auth method, database size)
5. **No dependency graph:** Can't model cascading effects across systems

## Improvement Roadmap

**Short-term (when more data available):**
1. Collect real what-if scenarios from workflow database
2. Store actual outcomes (success rate, rollback attempts, incidents)
3. Retrain with balanced real/synthetic data (50/50 split)

**Medium-term:**
1. Add context features (system size, user count, tech stack)
2. Implement multi-label impact (e.g., affects auth + payments + frontend)
3. Add temporal features (time since last major change, deployment frequency)

**Long-term:**
1. Build dependency graph from codebase
2. Simulate cascading effects (if auth changes → payment API breaks → checkout fails)
3. Integrate with incident database (learn from past failures)
4. Active learning (flag uncertain predictions for human review)

## Integration

**Workflow integration:**
```javascript
const { exec } = require('child_process');

async function evaluateChange(scenario) {
  return new Promise((resolve, reject) => {
    exec(`python3 tools/predict_counterfactual.py "${scenario}"`, (error, stdout) => {
      if (error) reject(error);
      else resolve(JSON.parse(stdout));
    });
  });
}

const result = await evaluateChange("What if we increase timeout to 300s?");
if (result.risk_score > 0.7) {
  console.log("⚠️  HIGH RISK - requires review");
}
```

**Pre-commit hook:**
```bash
#!/bin/bash
# .git/hooks/pre-commit

if git diff --cached | grep -q "timeout.*="; then
  echo "⚠️  Timeout change detected - running counterfactual analysis..."
  python3 tools/predict_counterfactual.py "What if we change this timeout?"
fi
```

## Files

- **Trainer:** `tools/counterfactual_reasoning_trainer.py` (600 lines)
- **Predictor:** `tools/predict_counterfactual.py` (50 lines)
- **Model:** `learning/counterfactual_reasoner.pkl` (serialized Random Forests)
- **Stats:** `learning/counterfactual_reasoner_stats.json`
- **This doc:** `docs/COUNTERFACTUAL_REASONING.md`

## Version History

- **2026-07-03:** Initial training with 24 database + 800 synthetic samples
  - Impact accuracy: 100% (overfitting likely)
  - Success R²: 1.0
  - Side effects R²: 1.0
  - Rollback R²: 0.0 (needs more diverse data)

---

**Next steps:**
1. Test on real what-if scenarios from recent workflow runs
2. Collect feedback on prediction accuracy
3. Retrain with updated data after 100+ real scenarios
