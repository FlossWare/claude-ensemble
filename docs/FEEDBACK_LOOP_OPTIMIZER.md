# Feedback Loop Optimizer

**Created:** 2026-07-03  
**Status:** Production Ready  
**Integration:** PostgreSQL + pgvector (via REST API at aio-01:5000)

## Overview

The Feedback Loop Optimizer detects and prevents self-referential feedback loops in distributed LLM orchestration systems. It implements 4 layers of analysis to identify when the system is "learning from itself" rather than improving objectively.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Model Distribution Analysis                  │
│  - Detects echo chamber effects (>70/30 rule)          │
│  - Alerts when one model dominates usage               │
│  - Recommendation: Force model rotation                │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Evaluator-Generator Coupling                 │
│  - Detects when models evaluate their own outputs      │
│  - Correlates workflow.worker_results + arbiters       │
│  - Recommendation: Enforce arbiter ≠ worker            │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Reward Hacking Detection                     │
│  - Quality increasing + diversity decreasing           │
│  - Temporal trend analysis over 7 days                 │
│  - Recommendation: Adversarial evaluation              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Concept Collapse Detection                   │
│  - Output embeddings converging (>0.90 similarity)     │
│  - Uses pgvector cosine similarity                     │
│  - Recommendation: Increase task diversity             │
└─────────────────────────────────────────────────────────┘
```

## What This Detects

### 1. Model Dominance (Echo Chamber)

**Symptom:** One model handles >70% of executions

**Risk:** System converges on single model's biases and limitations

**Example Evidence:**
```json
{
  "model": "opus",
  "percentage": 0.78,
  "distribution": {
    "opus": 0.78,
    "sonnet": 0.15,
    "haiku": 0.07
  }
}
```

**Mitigation:** Forced model rotation (temporarily boost minority models)

### 2. Evaluator-Generator Coupling

**Symptom:** Model frequently evaluates its own outputs (>40% self-evaluation)

**Risk:** Circular validation ("I checked my own work and it's perfect")

**Example Evidence:**
```json
{
  "model": "sonnet",
  "self_eval_count": 45,
  "total_evals": 100,
  "self_eval_percentage": 0.45
}
```

**Mitigation:** Enforce constraint: `arbiter.model ≠ worker.model`

### 3. Reward Hacking

**Symptom:** Quality scores increase while model diversity decreases

**Risk:** System learns to game evaluation metrics rather than improve

**Example Evidence:**
```json
{
  "quality_trend": 0.035,
  "diversity_trend": -0.15,
  "recent_quality": 0.89,
  "baseline_quality": 0.72
}
```

**Mitigation:** External adversarial evaluation (ChatGPT framework)

### 4. Concept Collapse

**Symptom:** Output embeddings highly similar (mean >0.85 cosine similarity)

**Risk:** System converges to single solution pattern, loses creativity

**Example Evidence:**
```json
{
  "mean_similarity": 0.87,
  "max_similarity": 0.96,
  "high_similarity_percentage": 0.34,
  "similarity_histogram": {
    "0.85-0.95": 67,
    "0.95-1.0": 21
  }
}
```

**Mitigation:** Increase temperature, vary prompts, inject task diversity

## Usage

### CLI

```bash
# Run full analysis (7-day window)
python3 tools/feedback_loop_optimizer.py

# Custom window
python3 tools/feedback_loop_optimizer.py --window 14

# Save JSON report
python3 tools/feedback_loop_optimizer.py --output /tmp/report.json

# Quiet mode (only output to file)
python3 tools/feedback_loop_optimizer.py --output /tmp/report.json --quiet

# Don't save risks to database
python3 tools/feedback_loop_optimizer.py --no-save
```

**Exit Codes:**
- `0` - No critical/high risks
- `1` - High risks detected (severity 0.6-0.8)
- `2` - Critical risks detected (severity >0.8)

### JavaScript/Node.js

```javascript
const { analyzeFeedbackLoops, isSystemHealthy } = require('./shared/feedback-loop-adapter.cjs');

// Run analysis
const analysis = await analyzeFeedbackLoops({ windowDays: 7 });

console.log('Total risks:', analysis.summary.total_risks);
console.log('Critical:', analysis.summary.critical);
console.log('Model distribution:', analysis.model_distribution);

// Check health
const healthy = await isSystemHealthy(7);
if (!healthy) {
  console.warn('System has critical/high feedback loop risks!');
}

// Get specific risk type
const { getRisksByType } = require('./shared/feedback-loop-adapter.cjs');
const dominanceRisks = await getRisksByType('model_dominance', 7);
```

### Workflow Integration (Before Execution)

```javascript
const { beforeWorkflow } = require('./shared/feedback-loop-adapter.cjs');

export default async function myWorkflow({ parallel, agent }) {
  // Check for critical risks before running
  await beforeWorkflow({ criticalOnly: true });

  // ... workflow execution ...
}
```

### Workflow Integration (After Execution)

```javascript
const { afterWorkflow } = require('./shared/feedback-loop-adapter.cjs');
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.cjs');

export default async function myWorkflow({ parallel, agent }) {
  const db = getWorkflowStorage();
  const execId = await db.storeExecution({ ... });

  // ... workflow execution ...

  // Analyze feedback loops after workflow
  const analysis = await afterWorkflow({ workflowId: execId, warnOnly: true });

  if (analysis.summary.critical > 0) {
    console.warn('Workflow may have introduced feedback loop risks!');
  }
}
```

### Background Monitoring

```javascript
const { startMonitoring } = require('./shared/feedback-loop-adapter.cjs');

// Check every 6 hours
const monitor = startMonitoring({
  intervalHours: 6,
  windowDays: 7,
  onRisk: (analysis) => {
    console.error('[ALERT] Feedback loop risks detected:', analysis.summary);

    // Send notification, trigger mitigation, etc.
    if (analysis.summary.critical > 0) {
      // Immediate action required
      process.exit(1);
    }
  }
});

// To stop monitoring
// monitor.stop();
```

## Python API

```python
from tools.feedback_loop_optimizer import FeedbackLoopOptimizer

optimizer = FeedbackLoopOptimizer()

# Run full analysis
analysis = optimizer.run_full_analysis(window_days=7, save_to_db=True)

# Print report
optimizer.print_report(analysis)

# Get specific analysis
distribution, risks = optimizer.analyze_model_distribution(window_days=7)
coupling_risks = optimizer.analyze_eval_generator_coupling(window_days=7)
reward_risks = optimizer.analyze_reward_hacking(window_days=7)
collapse_risks = optimizer.analyze_concept_collapse(limit=100)

# Get mitigation actions
actions = optimizer.get_mitigation_actions('model_dominance')
for action in actions:
    print(action)
```

## Database Schema

### Risks Stored In: `monitoring.diversity_alerts`

```sql
CREATE TABLE monitoring.diversity_alerts (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    alert_type VARCHAR(50) NOT NULL,  -- risk_type
    severity FLOAT NOT NULL,          -- 0.0 - 1.0
    description TEXT NOT NULL,
    evidence JSONB,
    mitigation TEXT
);
```

**Query Recent Alerts:**
```sql
SELECT alert_type, severity, description, timestamp
FROM monitoring.diversity_alerts
WHERE timestamp > NOW() - INTERVAL '7 days'
ORDER BY severity DESC, timestamp DESC;
```

## Integration with Existing Systems

### 1. Multi-Model Router

Update `~/.claude/self/multi-model-router.py` to boost minority models:

```python
from tools.feedback_loop_optimizer import FeedbackLoopOptimizer

optimizer = FeedbackLoopOptimizer()
distribution, risks = optimizer.analyze_model_distribution(window_days=1)

# Boost underused models
for model, percentage in distribution.items():
    if percentage < 0.15:  # Less than 15% usage
        model_weights[model] *= 2.0  # Double selection probability
```

### 2. Consensus Workflows

Enforce arbiter ≠ worker constraint:

```javascript
const { getCriticalRisks } = require('./shared/feedback-loop-adapter.cjs');

// Before selecting arbiter
const couplingRisks = await getCriticalRisks(1);
const problematicModels = couplingRisks
  .filter(r => r.risk_type === 'eval_gen_coupling')
  .map(r => r.evidence.model);

// Filter out workers that match arbiter model
const eligibleWorkers = workers.filter(w =>
  !problematicModels.includes(w.model)
);
```

### 3. Evaluation Harness

Enable adversarial evaluation when reward hacking detected:

```javascript
const { getRisksByType } = require('./shared/feedback-loop-adapter.cjs');
const { evaluateWithHarness } = require('~/.claude/self/evaluation-harness.mjs');

const rewardRisks = await getRisksByType('reward_hacking', 7);

if (rewardRisks.length > 0) {
  // Enable Layer 2: External validation
  const result = await evaluateWithHarness({
    output: candidateOutput,
    task: originalTask,
    models: ['gpt4o', 'gemini'],  // External validators
    adversarial: true
  });
}
```

## Grafana Dashboard

Add to existing dashboard at `http://aio-01:3000`:

**Panel 1: Feedback Loop Risk Summary**
```sql
SELECT
  alert_type,
  MAX(severity) as max_severity,
  COUNT(*) as count
FROM monitoring.diversity_alerts
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY alert_type
ORDER BY max_severity DESC
```

**Panel 2: Model Distribution Over Time**
```sql
SELECT
  DATE(timestamp) as day,
  model,
  COUNT(*) as executions
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY day, model
ORDER BY day, executions DESC
```

**Panel 3: Quality vs Diversity Trend**
```sql
SELECT
  DATE(timestamp) as day,
  AVG(quality_score) as avg_quality,
  COUNT(DISTINCT model) as model_diversity
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '30 days'
  AND quality_score IS NOT NULL
GROUP BY day
ORDER BY day
```

## Threshold Tuning

Default thresholds (adjustable in `FeedbackLoopOptimizer.__init__`):

```python
self.dominance_threshold = 0.70   # Alert if one model >70% usage
self.coupling_threshold = 0.40    # Alert if self-eval >40%
self.reward_hack_threshold = 0.85 # Alert if quality >0.85 without diversity
self.collapse_threshold = 0.90    # Alert if embedding similarity >0.90
```

**Conservative (fewer false positives):**
```python
optimizer = FeedbackLoopOptimizer()
optimizer.dominance_threshold = 0.80
optimizer.coupling_threshold = 0.50
optimizer.reward_hack_threshold = 0.90
optimizer.collapse_threshold = 0.95
```

**Aggressive (catch early warning signs):**
```python
optimizer = FeedbackLoopOptimizer()
optimizer.dominance_threshold = 0.60
optimizer.coupling_threshold = 0.30
optimizer.reward_hack_threshold = 0.80
optimizer.collapse_threshold = 0.85
```

## Example Output

```
================================================================================
FEEDBACK LOOP ANALYSIS REPORT
================================================================================
Timestamp: 2026-07-03T18:30:00
Analysis Window: 7 days

SUMMARY:
  Total Risks: 2
    Critical (>0.8): 0
    High (0.6-0.8): 1
    Medium (0.4-0.6): 1
    Low (<0.4): 0

MODEL DISTRIBUTION:
  opus                : 68.5%
  sonnet              : 22.1%
  haiku               :  6.2%
  gemini              :  3.2%

DETECTED RISKS:

  [1] MODEL_DOMINANCE - HIGH (severity=0.68)
      Model 'opus' dominates with 68.5% usage
      Mitigation: Force rotate models: temporarily boost selection probability for underused models

  [2] CONCEPT_COLLAPSE - MEDIUM (severity=0.56)
      Output embeddings show high similarity (mean=0.856, max=0.942)
      Mitigation: Increase task diversity: use temperature sampling, vary prompts

RECOMMENDATIONS:
  1. Implement forced model rotation to restore diversity
  2. Increase task diversity: vary prompts, use temperature sampling

================================================================================
```

## Automated Remediation

Future enhancement: Auto-apply mitigations when safe to do so.

**Example:**
```python
# In multi-model-router.py
from tools.feedback_loop_optimizer import FeedbackLoopOptimizer

optimizer = FeedbackLoopOptimizer()
analysis = optimizer.run_full_analysis(window_days=1, save_to_db=False)

for risk in analysis['risks']:
    if risk['risk_type'] == 'model_dominance' and risk['severity'] > 0.7:
        dominant_model = risk['evidence']['model']

        # Auto-mitigation: boost minority models
        for model in AVAILABLE_MODELS:
            if model != dominant_model:
                MODEL_WEIGHTS[model] *= 1.5  # Temporary boost

        print(f"[AUTO-MITIGATION] Boosted minority models to counter {dominant_model} dominance")
```

## Testing

```bash
# Simulate model dominance (via REST API)
for i in $(seq 1 100); do
  curl -s -X POST http://aio-01:5000/monitoring/execution \
    -H "Content-Type: application/json" \
    -d '{"model":"opus","workflow":"test","outcome":"success","quality_score":0.85}'
done

# Run analysis (should detect dominance)
python3 tools/feedback_loop_optimizer.py --window 1

# Clean up test data (via REST API)
curl -s -X DELETE "http://aio-01:5000/monitoring/executions?workflow=test"
```

## Files Created

- `tools/feedback_loop_optimizer.py` - Core Python implementation
- `shared/feedback-loop-adapter.cjs` - JavaScript/Node.js adapter
- `docs/FEEDBACK_LOOP_OPTIMIZER.md` - This documentation

## Related Systems

- **PostgreSQL Adapter:** `~/.claude/learning/postgres_adapter.py`
- **Workflow Storage:** `shared/workflow-storage-adapter.cjs`
- **Evaluation Harness:** `~/.claude/self/evaluation-harness.mjs`
- **Multi-Model Router:** `~/.claude/self/multi-model-router.py`
- **Thompson Sampling Bandit:** `learning.strategy_performance` table

## License

Same as parent project (see root LICENSE file)
