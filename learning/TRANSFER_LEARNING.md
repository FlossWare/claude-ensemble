# Transfer Learning Implementation

Comprehensive transfer learning system for AI model calibration with confidence decay.

## Overview

When a new AI model is introduced, we don't have calibration data yet. Transfer learning allows us to bootstrap the new model using data from similar existing models, with confidence that decays over time as we accumulate native data.

## Key Features

### 1. **Model Similarity Detection**
Automatically identifies similar models based on:
- **Provider** (Anthropic, OpenAI, Google, Meta, etc.) - 30% weight
- **Family** (Claude-4, GPT-4, Gemini-1.5) - 30% weight
- **Architecture** (Opus, Sonnet, Haiku, Turbo, Pro, Flash) - 20% weight
- **Task Performance** (quality scores on same task type) - 20% weight

### 2. **Bootstrap from Similar Models**
Automatically transfers calibration data from top 5 most similar models with weighted blending.

### 3. **Time-Based Confidence Decay**
Transferred calibration confidence decays exponentially:
```
confidence(t) = initial_confidence × e^(-decay_rate × days_elapsed)
```
- **Initial confidence**: 70% × similarity_score
- **Decay rate**: 10% per day
- **Minimum confidence**: 20% (below this, transfer expires)

### 4. **Automatic Transition to Native**
As native data accumulates:
- **< 20 samples**: Use transferred calibration (with decay)
- **20-50 samples**: Blend transferred + native calibration
- **50+ samples**: Use pure native calibration, mark transfers as superseded

### 5. **Transfer Validation**
Compare transferred predictions against actual native performance to measure transfer quality.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     New Model Appears                        │
│                  (e.g., claude-opus-4.5)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Find Similar Models                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Parse model ID → { provider, family, architecture } │   │
│  │ Query execution_log for existing models             │   │
│  │ Calculate similarity scores                          │   │
│  │ Return top 5 matches sorted by similarity           │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            Bootstrap Calibration Transfer                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ For each similar model:                             │   │
│  │   - Record transfer event in model_transfer_log     │   │
│  │   - Set initial_confidence = 0.7 × similarity       │   │
│  │   - Set decay_rate = 0.1 (10% per day)              │   │
│  │   - Status = 'active'                                │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           Runtime: Get Calibration Data                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Check native sample count:                          │   │
│  │                                                       │   │
│  │ IF native_count >= 50:                              │   │
│  │   → Use native calibration (100% confidence)        │   │
│  │   → Mark transfers as 'superseded'                   │   │
│  │                                                       │   │
│  │ ELSE IF native_count > 0:                           │   │
│  │   → Get active transfers                             │   │
│  │   → Apply time decay to each transfer                │   │
│  │   → Blend transferred + native (weighted average)    │   │
│  │                                                       │   │
│  │ ELSE:                                                │   │
│  │   → Use transferred only (with decay)                │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Confidence Decay Formula                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ days_elapsed = (now - transfer_timestamp) / 86400000│   │
│  │ decayed = initial × exp(-0.1 × days_elapsed)        │   │
│  │                                                       │   │
│  │ IF decayed < 0.2:                                   │   │
│  │   → Mark transfer as 'expired'                       │   │
│  │   → Exclude from calibration                         │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Weighted Blending                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ For each active transfer:                           │   │
│  │   weight = similarity × decayed_confidence           │   │
│  │   weighted_quality += source_quality × weight        │   │
│  │                                                       │   │
│  │ If native data exists:                               │   │
│  │   native_weight = native_count / 50                  │   │
│  │   weighted_quality += native_quality × native_weight │   │
│  │                                                       │   │
│  │ Final = weighted_sum / total_weight                  │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Return Calibration                              │
│  {                                                           │
│    source: 'transferred' | 'hybrid' | 'native',             │
│    avgQuality: 0.85,                                         │
│    avgConfidence: 0.75,                                      │
│    calibrationConfidence: 0.65,                              │
│    transferSources: [...],                                   │
│    nativeSamples: 12                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### `model_transfer_log`
Records each transfer learning event:
- `target_model` - New model being bootstrapped
- `source_model` - Model providing calibration data
- `similarity_score` - 0.0 to 1.0
- `initial_confidence` - Starting confidence before decay
- `decay_rate` - Exponential decay rate per day
- `status` - 'active', 'expired', 'superseded'
- `metadata` - JSON with execution stats

### `calibration_history`
Snapshots of calibration data over time:
- `model`, `task_type` - What this calibration is for
- `calibration_source` - 'native', 'transferred', 'hybrid'
- `sample_count` - Native samples
- `transfer_count` - Transfer sources
- `calibration_confidence` - Overall confidence score
- `transfer_sources` - JSON array of source details

### `model_similarity_cache`
Precomputed similarity scores (performance optimization):
- `model1`, `model2` - Pair of models
- `similarity_score` - Cached score
- `task_type` - NULL for general similarity
- `computed_at` - Timestamp

### `transfer_validation`
Transfer quality tracking:
- `native_avg_quality` vs `transferred_avg_quality`
- `quality_error`, `confidence_error`, `success_error`
- `transfer_quality` - Overall score
- `assessment` - 'excellent', 'good', 'fair', 'poor'

### `model_taxonomy`
Explicit model relationships:
- `provider`, `family`, `architecture`, `version`
- `capabilities` - JSON metadata
- Used to improve similarity detection

## API Reference

### Core Functions

#### `bootstrapNewModel(newModel, sourceModels, taskType)`
Initialize transfer learning for a new model.

**Parameters:**
- `newModel` (string) - Model identifier (e.g., 'claude-opus-4.5')
- `sourceModels` (string[], optional) - Specific sources (auto-detected if null)
- `taskType` (string, optional) - Task type filter

**Returns:**
```javascript
{
  success: true,
  targetModel: 'claude-opus-4.5',
  sourceModels: [
    { sourceModel: 'claude-opus-4', similarity: 0.85, initialConfidence: 0.595 },
    { sourceModel: 'claude-sonnet-4', similarity: 0.65, initialConfidence: 0.455 }
  ],
  timestamp: '2026-06-13T...',
  message: 'Bootstrapped claude-opus-4.5 from 2 similar models'
}
```

#### `getTransferredCalibration(modelId, taskType)`
Get calibration data with automatic decay and blending.

**Parameters:**
- `modelId` (string) - Model identifier
- `taskType` (string) - Task type

**Returns:**
```javascript
{
  source: 'hybrid',  // 'native' | 'transferred' | 'hybrid' | 'none'
  modelId: 'claude-opus-4.5',
  taskType: 'code-review',
  nativeSamples: 12,
  transferSources: [
    {
      sourceModel: 'claude-opus-4',
      similarity: 0.85,
      decayedConfidence: 0.54,  // Decayed from 0.595 over time
      daysElapsed: 3.2,
      sampleCount: 150,
      weight: 0.459  // similarity × decayed_confidence
    }
  ],
  avgQuality: 0.82,
  avgConfidence: 0.76,
  successRate: 0.88,
  calibrationConfidence: 0.68,  // Overall confidence in this calibration
  timestamp: '2026-06-13T...'
}
```

#### `updateWithNativeData(modelId, executionData)`
Update model with new native execution data. Automatically transitions when threshold reached.

**Parameters:**
- `modelId` (string) - Model identifier
- `executionData` (object) - New execution data

**Returns:**
```javascript
{
  success: true,
  modelId: 'claude-opus-4.5',
  nativeSamples: 50,
  transition: 'transferred_to_native',  // or 'building_native', 'native_established'
  message: 'Model claude-opus-4.5 now has sufficient native calibration data'
}
```

#### `validateTransfer(modelId, taskType)`
Compare transferred predictions against actual native performance.

**Parameters:**
- `modelId` (string) - Model identifier
- `taskType` (string) - Task type

**Returns:**
```javascript
{
  success: true,
  modelId: 'claude-opus-4.5',
  taskType: 'code-review',
  nativeSamples: 45,
  transferSources: [...],
  native: { avgQuality: 0.84, avgConfidence: 0.78, successRate: 0.91 },
  transferred: { avgQuality: 0.82, avgConfidence: 0.76, successRate: 0.88 },
  errors: { quality: 0.02, confidence: 0.02, success: 0.03 },
  transferQuality: 0.93,  // 1 - average error
  assessment: 'excellent'  // 'excellent' | 'good' | 'fair' | 'poor'
}
```

#### `findSimilarModels(db, targetModel, taskType, limit)`
Find most similar models for transfer learning.

**Parameters:**
- `db` (Database) - Database connection
- `targetModel` (string) - Target model
- `taskType` (string, optional) - Task type filter
- `limit` (number) - Max results (default 5)

**Returns:**
```javascript
[
  {
    model: 'claude-opus-4',
    similarity: 0.85,
    executionCount: 450,
    avgQuality: 0.83,
    avgConfidence: 0.77
  },
  // ... more similar models
]
```

### Utility Functions

#### `parseModelId(modelId)`
Parse model identifier into components.

```javascript
parseModelId('claude-opus-4.5')
// → { provider: 'anthropic', family: 'claude-4.5', arch: 'opus', original: 'claude-opus-4.5' }

parseModelId('gpt-4-turbo')
// → { provider: 'openai', family: 'gpt-4', arch: 'turbo', original: 'gpt-4-turbo' }
```

#### `calculateSimilarity(model1, model2, taskType, model1Stats, model2Stats)`
Calculate similarity score between two models (0.0 to 1.0).

## CLI Usage

### Bootstrap a new model
```bash
# Auto-detect similar models
node transfer-learning.js bootstrap claude-opus-4.5

# Specify source models
node transfer-learning.js bootstrap claude-opus-4.5 claude-opus-4,claude-sonnet-4

# Task-specific
node transfer-learning.js bootstrap claude-opus-4.5 '' code-review
```

### Get calibration data
```bash
node transfer-learning.js calibration claude-opus-4.5 code-review
```

### Validate transfer quality
```bash
node transfer-learning.js validate claude-opus-4.5 code-review
```

### Find similar models
```bash
node transfer-learning.js similar claude-opus-4.5 code-review 10
```

### Parse model identifier
```bash
node transfer-learning.js parse claude-opus-4.5
```

## Confidence Decay Timeline

With default settings (initial=0.7, decay=0.1/day):

| Days | Confidence | Status |
|------|-----------|--------|
| 0 | 0.700 | ✓ Active (100%) |
| 1 | 0.634 | ✓ Active (90.6%) |
| 3 | 0.518 | ✓ Active (74.0%) |
| 7 | 0.348 | ✓ Active (49.7%) |
| 10 | 0.258 | ✓ Active (36.8%) |
| 15 | 0.157 | ✗ **Expired** (< 20%) |

After 15 days, transferred calibration expires and is no longer used.

## Integration Example

```javascript
const transfer = require('./transfer-learning');

// When new model is detected
async function onNewModel(modelId) {
  // Bootstrap from similar models
  const bootstrap = await transfer.bootstrapNewModel(modelId);
  console.log(`Bootstrapped ${modelId} from ${bootstrap.sourceModels.length} sources`);
  
  return bootstrap;
}

// When requesting model calibration
async function getModelCalibration(modelId, taskType) {
  // Get calibration with automatic decay and blending
  const calibration = await transfer.getTransferredCalibration(modelId, taskType);
  
  console.log(`Calibration source: ${calibration.source}`);
  console.log(`Native samples: ${calibration.nativeSamples}`);
  console.log(`Calibration confidence: ${calibration.calibrationConfidence}`);
  
  return calibration;
}

// After each execution
async function recordExecution(modelId, executionData) {
  // Update native data, check for transition
  const update = await transfer.updateWithNativeData(modelId, executionData);
  
  if (update.transition === 'transferred_to_native') {
    console.log(`${modelId} transitioned to native calibration!`);
  }
  
  return update;
}

// Periodic validation
async function validateTransfers() {
  const models = await getAllModelsWithTransfers();
  
  for (const model of models) {
    const validation = await transfer.validateTransfer(model.id, model.taskType);
    
    if (validation.assessment === 'poor') {
      console.warn(`Poor transfer quality for ${model.id}: ${validation.transferQuality}`);
    }
  }
}
```

## Testing

```bash
# Run all tests
node test-transfer-learning.js

# Individual test suites
node -e "require('./test-transfer-learning').testModelParsing()"
node -e "require('./test-transfer-learning').testSimilarityCalculation()"
node -e "require('./test-transfer-learning').testConfidenceDecay()"
node -e "require('./test-transfer-learning').testIntegration()"
```

## Setup

1. **Initialize database:**
```bash
node init-transfer-learning-db.js
```

2. **Verify tables created:**
```bash
# Should show: model_transfer_log, calibration_history, model_similarity_cache, etc.
```

3. **Run tests:**
```bash
node test-transfer-learning.js
```

4. **Bootstrap your first model:**
```bash
node transfer-learning.js bootstrap claude-opus-4.5
```

## Configuration

### Constants (in `transfer-learning.js`)

```javascript
// Decay settings
const TRANSFER_DECAY_RATE = 0.1;  // 10% decay per day
const MIN_TRANSFER_CONFIDENCE = 0.2;  // Expire below 20%
const TRANSFER_INITIAL_CONFIDENCE = 0.7;  // Start at 70%

// Native data threshold
const NATIVE_SAMPLES_THRESHOLD = 20;  // Transition at 20 samples

// Similarity weights
const SIMILARITY_WEIGHTS = {
  provider: 0.3,      // Same provider
  family: 0.3,        // Same family
  architecture: 0.2,  // Same arch
  taskType: 0.2       // Task performance
};
```

Adjust these based on your needs:
- **Faster decay**: Increase `TRANSFER_DECAY_RATE`
- **Longer transfer lifetime**: Decrease `MIN_TRANSFER_CONFIDENCE`
- **Earlier native transition**: Decrease `NATIVE_SAMPLES_THRESHOLD`
- **Provider-first similarity**: Increase `SIMILARITY_WEIGHTS.provider`

## Performance Considerations

1. **Similarity caching**: Precompute and cache similarity scores in `model_similarity_cache` table
2. **Decay schedule**: Precompute decay values in `transfer_decay_schedule` table
3. **Batch updates**: Update multiple transfers in single transaction
4. **Index optimization**: Ensure indexes on `(target_model, status)`, `(model, task_type)`

## Future Enhancements

1. **Task-specific similarity**: Weight task performance more heavily for task-specific transfers
2. **Adaptive decay**: Adjust decay rate based on transfer quality validation
3. **Multi-hop transfer**: Transfer from models that were themselves bootstrapped
4. **Confidence intervals**: Provide uncertainty bounds on transferred calibration
5. **Auto-bootstrapping**: Automatically bootstrap new models on first detection

## References

- **Exponential decay**: Standard time-decay model for information freshness
- **Weighted blending**: Combines multiple sources with confidence weighting
- **Model taxonomy**: Hierarchical model classification for similarity
- **Calibration confidence**: Meta-confidence in calibration estimates
