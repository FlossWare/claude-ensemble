# User Intent Predictor

**Status:** Production Ready  
**Training Date:** 2026-07-03  
**Training Samples:** 2,209 user messages  
**Accuracy:** 81% exact match, 90% weighted F1-score  

## Overview

The User Intent Predictor is a multi-label text classifier that predicts user intent from natural language queries. It's trained on your actual conversation history with Claude and can detect 10 different intent categories.

## Intent Categories

| Intent | Description | Example Queries |
|--------|-------------|----------------|
| **code_generation** | Write/create new code | "Write a Python script to...", "Create a function that..." |
| **code_review** | Review/analyze existing code | "Review this code", "Check for bugs", "Audit this implementation" |
| **research** | Deep research, PDF analysis | "Research Kubernetes", "Analyze this PDF", "What is X?" |
| **system_ops** | DevOps, infrastructure, config | "Deploy to production", "Install Docker", "Configure SSH" |
| **debugging** | Fix bugs, troubleshoot | "Debug this error", "Why isn't this working?", "Fix this bug" |
| **data_analysis** | Analyze data, metrics, logs | "Analyze PostgreSQL metrics", "Parse these logs", "Generate dashboard" |
| **documentation** | Write docs, explain concepts | "Document this API", "Write a README", "Explain how this works" |
| **workflow_automation** | Create workflows, orchestration | "Create a workflow", "Automate this process", "Run in parallel" |
| **learning** | Train models, ML tasks | "Train a classifier", "Fine-tune a model", "Create embeddings" |
| **other** | Fallback category | General queries, multi-intent, unclear |

## Model Performance

**Per-Intent Metrics (Test Set):**

| Intent | Precision | Recall | F1-Score | Support |
|--------|-----------|--------|----------|---------|
| code_generation | 60% | 94% | 73% | 31 |
| code_review | 89% | 92% | 90% | 95 |
| data_analysis | 86% | 93% | 89% | 95 |
| debugging | 85% | 89% | 87% | 62 |
| documentation | 31% | 80% | 44% | 10 |
| learning | 77% | 94% | 84% | 49 |
| other | 92% | 100% | 96% | 261 |
| research | 37% | 79% | 50% | 14 |
| system_ops | 92% | 89% | 90% | 112 |
| workflow_automation | 97% | 94% | 95% | 77 |

**Overall:**
- Hamming Loss: 4.3%
- Exact Match Accuracy: 81%
- Weighted F1-Score: 90%

## Usage

### Python

```python
#!/usr/bin/env python3
from tools.predict_intent import load_model, predict_intent

# Load model
model = load_model()

# Predict intent
text = "Write a Python script to parse JSON logs"
intents = predict_intent(model, text, threshold=0.3)

print(f"Predicted intents: {intents}")
# Output: [('workflow_automation', 0.20), ('code_generation', 0.19), ...]
```

### Command Line

```bash
# Basic usage
python3 tools/predict_intent.py "Debug this error"

# JSON output
python3 tools/predict_intent.py "Train a classifier" --json

# Custom threshold
python3 tools/predict_intent.py "Review this code" --threshold 0.5
```

### JavaScript/Node.js

```javascript
import { predictIntent, predictAndRoute } from './shared/intent-predictor.js';

// Simple prediction
const result = predictIntent("Deploy to production");
console.log(result.primary_intent); // "system_ops"

// Prediction + routing configuration
const routed = predictAndRoute("Write a Python script");
console.log(routed.routing);
// {
//   suggested_models: ['deepseek-coder-java:finetuned', 'sonnet', 'haiku'],
//   worker_count: 2,
//   quality_threshold: 0.7,
//   verification_required: true
// }
```

## Intent-Based Routing

The predictor integrates with workflow orchestration to automatically configure:

- **Model selection**: Which models are best for this intent
- **Worker count**: Optimal parallelism for the task
- **Quality threshold**: Minimum acceptable quality score
- **Verification**: Whether to require human/multi-AI review

### Routing Configuration by Intent

```javascript
{
  code_review: {
    suggested_models: ['opus', 'sonnet', 'fable'],
    worker_count: 3,
    quality_threshold: 0.8,
    verification_required: true
  },
  research: {
    suggested_models: ['opus', 'gemini', 'sonnet'],
    worker_count: 4,
    quality_threshold: 0.75,
    verification_required: false
  },
  debugging: {
    suggested_models: ['sonnet', 'opus', 'haiku'],
    worker_count: 3,
    quality_threshold: 0.75,
    verification_required: true
  },
  // ... see shared/intent-predictor.js for full config
}
```

## Retraining

The model should be retrained periodically as you have more conversations:

```bash
# Retrain on latest conversation history
python3 tools/train_intent_predictor.py

# Model saved to: ~/.claude/learning/intent_predictor.pkl
# Stats saved to: ~/.claude/learning/intent_predictor_stats.json
```

**Recommended retraining schedule:**
- Every 500 new conversations
- When adding new intent categories
- When accuracy drops below 75%

## Training Data

The model is trained on conversation logs from:
- `~/.claude/projects/-home-sfloess/*.jsonl`
- `~/.claude/projects/-home-sflooss-Development-*/*.jsonl`

**Current training set:**
- 2,209 user messages
- 474 conversation files
- Date range: June-July 2026

## Model Architecture

- **Vectorizer**: TF-IDF with 5,000 features, unigrams to trigrams
- **Classifier**: OneVsRest Logistic Regression
- **Class Balancing**: Balanced class weights to handle imbalance
- **Multi-label**: Can predict multiple intents per query

## Files

**Training & Prediction:**
- `tools/train_intent_predictor.py` - Training script
- `tools/predict_intent.py` - CLI prediction tool
- `shared/intent-predictor.js` - JavaScript integration

**Model Artifacts:**
- `~/.claude/learning/intent_predictor.pkl` - Trained model (595 KB)
- `~/.claude/learning/intent_predictor_stats.json` - Model metadata

## Integration Examples

### Workflow Orchestration

```javascript
import { predictAndRoute } from './shared/intent-predictor.js';

export default async function({ parallel, agent, log }) {
  const userQuery = "Review this code for security issues";

  // Get intent-based routing
  const { intent, routing } = predictAndRoute(userQuery);

  log(`Detected intent: ${intent}`);
  log(`Using ${routing.worker_count} workers`);

  // Run workers with intent-specific configuration
  const results = await parallel(
    routing.suggested_models.slice(0, routing.worker_count).map(model => ({
      model,
      task: userQuery,
      quality_threshold: routing.quality_threshold,
    }))
  );

  // Verify if required
  if (routing.verification_required) {
    await agent({
      model: 'opus',
      task: 'Verify results...',
    });
  }

  return results;
}
```

### Smart Router

```python
from tools.predict_intent import load_model, predict_intent

class SmartRouter:
    def __init__(self):
        self.model = load_model()

    def route_task(self, user_query: str):
        intents = predict_intent(self.model, user_query)
        primary = intents[0][0]

        routing_map = {
            'code_generation': 'code_specialist',
            'code_review': 'review_specialist',
            'research': 'research_specialist',
            'debugging': 'debug_specialist',
        }

        specialist = routing_map.get(primary, 'general_agent')
        return specialist

router = SmartRouter()
specialist = router.route_task("Debug this memory leak")
print(f"Routing to: {specialist}")  # "debug_specialist"
```

## Monitoring

Track intent prediction accuracy:

```javascript
const predictions = [];

for (const query of userQueries) {
  const result = predictIntent(query);
  predictions.push({
    query,
    predicted_intent: result.primary_intent,
    confidence: result.intents[0].confidence,
    timestamp: new Date().toISOString(),
  });
}

// Log for analysis
await db.storePredictions(predictions);
```

## Known Limitations

1. **Documentation intent**: Low precision (31%) due to limited training examples (44 samples). More training data needed.

2. **Research intent**: Low precision (37%) because research queries often overlap with other intents. Consider refining patterns.

3. **Multi-intent queries**: Model can predict multiple intents, but primary intent selection uses highest confidence. May not always match user's implicit priority.

4. **Domain drift**: Trained on June-July 2026 conversations. Performance may degrade on significantly different query patterns.

## Future Improvements

1. **Active learning**: Flag low-confidence predictions for manual labeling
2. **Intent hierarchy**: Parent/child relationships (e.g., code_review → security_audit)
3. **Context awareness**: Use conversation history for better predictions
4. **Custom intents**: Allow user-defined intent categories
5. **Fine-tuned embeddings**: Use domain-specific embeddings instead of TF-IDF

## Support

For issues or questions:
- Check model stats: `cat ~/.claude/learning/intent_predictor_stats.json`
- Retrain if accuracy drops: `python3 tools/train_intent_predictor.py`
- Test predictions: `python3 tools/predict_intent.py "<query>"`
