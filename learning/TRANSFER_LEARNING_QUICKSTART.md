# Transfer Learning Quick Start

## Installation

```bash
cd ~/.claude/learning
node init-transfer-learning-db.js
```

## Basic Usage

### 1. Bootstrap a New Model

```bash
# Auto-detect similar models
node transfer-learning.js bootstrap claude-opus-4.5

# Specify source models manually
node transfer-learning.js bootstrap claude-opus-4.5 claude-opus-4,claude-sonnet-4
```

### 2. Get Calibration Data

```bash
node transfer-learning.js calibration claude-opus-4.5 code-review
```

**Output:**
```json
{
  "source": "transferred",
  "modelId": "claude-opus-4.5",
  "taskType": "code-review",
  "nativeSamples": 0,
  "transferSources": [
    {
      "sourceModel": "claude-opus-4",
      "similarity": 0.85,
      "decayedConfidence": 0.595,
      "daysElapsed": 0,
      "weight": 0.506
    }
  ],
  "avgQuality": 0.82,
  "avgConfidence": 0.76,
  "successRate": 0.88,
  "calibrationConfidence": 0.68
}
```

### 3. Validate Transfer Quality

```bash
# Requires at least 10 native samples
node transfer-learning.js validate claude-opus-4.5 code-review
```

### 4. Find Similar Models

```bash
node transfer-learning.js similar claude-opus-4.5 code-review 10
```

## In Your Code

```javascript
const transfer = require('./transfer-learning');

// Bootstrap new model
const bootstrap = await transfer.bootstrapNewModel('claude-opus-4.5');

// Get calibration
const calibration = await transfer.getTransferredCalibration(
  'claude-opus-4.5',
  'code-review'
);

// Use calibration
console.log(`Predicted quality: ${calibration.avgQuality}`);
console.log(`Confidence: ${calibration.calibrationConfidence}`);

// Update with native data
await transfer.updateWithNativeData('claude-opus-4.5', {
  quality_score: 0.85,
  confidence: 0.80,
  outcome: 'success'
});
```

## Testing

```bash
# Run all tests
node test-transfer-learning.js

# Run examples
node example-transfer-learning.js

# Run specific example
node example-transfer-learning.js 6  # Parse model IDs
node example-transfer-learning.js 7  # Similarity matrix
node example-transfer-learning.js 8  # Decay timeline
```

## How It Works

1. **New model appears** → Automatically find similar models
2. **Bootstrap** → Transfer calibration from similar models
3. **Confidence decay** → Transfer confidence decreases 10% per day
4. **Native data** → Blend transferred + native calibration
5. **Transition** → Switch to pure native at 50 samples

## Configuration

Edit `/home/sfloess/.claude/learning/transfer-learning.js`:

```javascript
// Decay rate: 0.1 = 10% per day
const TRANSFER_DECAY_RATE = 0.1;

// Minimum confidence before expiring: 0.2 = 20%
const MIN_TRANSFER_CONFIDENCE = 0.2;

// Initial confidence: 0.7 = 70%
const TRANSFER_INITIAL_CONFIDENCE = 0.7;

// Native samples needed for transition: 20
const NATIVE_SAMPLES_THRESHOLD = 20;
```

## Common Patterns

### Pattern 1: New Model Detection
```javascript
async function handleNewModel(modelId) {
  // Check if calibration exists
  const calibration = await transfer.getTransferredCalibration(modelId, taskType);
  
  if (calibration.source === 'none') {
    // Bootstrap from similar models
    await transfer.bootstrapNewModel(modelId);
  }
  
  return calibration;
}
```

### Pattern 2: Execution Recording
```javascript
async function recordExecution(modelId, result) {
  // Update native data
  const update = await transfer.updateWithNativeData(modelId, {
    quality_score: result.quality,
    confidence: result.confidence,
    outcome: result.success ? 'success' : 'failed'
  });
  
  if (update.transition === 'transferred_to_native') {
    console.log(`${modelId} now has native calibration!`);
  }
}
```

### Pattern 3: Model Selection with Transfer Learning
```javascript
async function selectModel(taskType, candidates) {
  const evaluations = [];
  
  for (const modelId of candidates) {
    const calibration = await transfer.getTransferredCalibration(modelId, taskType);
    
    evaluations.push({
      modelId,
      expectedQuality: calibration.avgQuality,
      confidence: calibration.calibrationConfidence,
      source: calibration.source
    });
  }
  
  // Sort by quality × confidence
  evaluations.sort((a, b) => 
    (b.expectedQuality * b.confidence) - (a.expectedQuality * a.confidence)
  );
  
  return evaluations[0].modelId;
}
```

## Troubleshooting

### "No similar models found"
- Database is empty (no existing models)
- New model is too different from existing models
- Solution: Add source models manually

### "Database tables not initialized"
```bash
node init-transfer-learning-db.js
```

### "Insufficient native data"
- Need at least 10 native samples for validation
- Keep accumulating native data

### Transfer quality is "poor"
- Source models may not be similar enough
- Task characteristics may differ significantly
- Solution: Accumulate more native data faster

## Files

| File | Purpose |
|------|---------|
| `transfer-learning.js` | Core implementation |
| `schema/transfer-learning-schema.sql` | Database schema |
| `init-transfer-learning-db.js` | DB initialization |
| `test-transfer-learning.js` | Test suite |
| `example-transfer-learning.js` | Usage examples |
| `TRANSFER_LEARNING.md` | Full documentation |

## Next Steps

1. ✓ Initialize database
2. ✓ Run tests
3. ✓ Run examples
4. Bootstrap your models
5. Integrate into your workflow
6. Monitor transfer quality

## Support

See full documentation: `TRANSFER_LEARNING.md`
