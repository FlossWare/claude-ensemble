# Model Caching Implementation

**Issue**: #322 Part 3
**Implementation Date**: 2026-07-04
**Status**: ✅ Complete

## Overview

Implemented in-memory model caching to eliminate the ~40s model reload overhead on every prediction. Models are now cached in a persistent Python daemon process.

## Architecture

### Two-Layer Caching Strategy

1. **Python Layer (Model Cache)**
   - Caches loaded sklearn model objects in memory
   - TTL: 30 minutes (configurable via `CACHE_TTL_MS`)
   - Benefit: Eliminates ~7s disk I/O for pickle loading
   - Result: Subsequent predictions on same model ~227ms

2. **JavaScript Layer (Prediction Cache)**
   - Caches prediction results for identical feature inputs
   - TTL: 5 minutes
   - Benefit: Eliminates all computation for duplicate predictions
   - Result: <1ms for cached predictions

### Persistent Daemon Mode

Instead of spawning a new Python process for each prediction:

**Before (CLI mode)**:
```
JS → spawn python → load model → predict → exit
     [~7000ms per prediction]
```

**After (Daemon mode)**:
```
JS → daemon (persistent) → predict (model cached)
     [~227ms first time, <1ms cached]
```

## Performance Results

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| Cold start (first load) | ~7000ms | ~7000ms | 0% (unavoidable disk I/O) |
| Same model, different features | ~7000ms | ~227ms | **96.8% faster** |
| Same features (exact duplicate) | ~7000ms | <1ms | **99.99% faster** |

### Actual Test Results

```
First prediction (cold model):        7050ms
Second prediction (cached model):     227ms  (different features)
Third prediction (JS cached):         0ms    (same features as #1)
Fourth prediction (JS cached):        0ms    (same features as #2)
```

## Usage

### Basic Usage (Automatic)

No code changes required! The daemon starts automatically on first prediction:

```javascript
const { predict } = require('./shared/model-loader.cjs');

// First call - cold start (~7s)
const result1 = await predict('complexity_estimator', features);

// Second call - model cached (~227ms)
const result2 = await predict('complexity_estimator', differentFeatures);

// Third call - prediction cached (<1ms)
const result3 = await predict('complexity_estimator', features);
```

### Manual Daemon Management

```javascript
const {
  startDaemon,
  stopDaemon,
  restartDaemon,
  getCacheStats,
  clearPythonCache
} = require('./shared/model-loader.cjs');

// Start daemon (optional - auto-starts on first prediction)
startDaemon();

// Get cache statistics
const stats = await getCacheStats();
console.log(stats);
// {
//   javascript: { predictions: 2, modelInfo: 0 },
//   python: { cached_models: 1, models: [...] },
//   daemon: { running: true, ready: true, queueLength: 0 }
// }

// Clear Python model cache (keeps daemon running)
await clearPythonCache();

// Restart daemon (useful after model retraining)
await restartDaemon();

// Stop daemon (cleanup)
stopDaemon();
```

### Python CLI (Direct)

You can also use the Python helper directly:

```bash
# One-shot mode (no caching)
python3 shared/model-loader-helper.py predict complexity_estimator '{"prompt_length": 100, ...}'

# Cache statistics
python3 shared/model-loader-helper.py cache-stats

# Clear cache
python3 shared/model-loader-helper.py clear-cache

# Daemon mode (persistent)
python3 shared/model-loader-helper.py daemon
```

## Implementation Details

### Python Model Cache

**Location**: `shared/model-loader-helper.py`

```python
# Cache structure
MODEL_CACHE = {
  'model_name': {
    'model': <loaded_sklearn_model>,
    'expires_at': <timestamp>,
    'loaded_at': <timestamp>,
    'load_time_ms': <ms>
  }
}

CACHE_TTL_MS = 30 * 60 * 1000  # 30 minutes
```

**Key functions**:
- `load_model(model_name, use_cache=True)` - Loads with caching
- `cache_stats()` - Returns cache statistics
- `clear_cache()` - Clears all cached models
- `run_daemon()` - Persistent mode (stdin/stdout communication)

### JavaScript Daemon Manager

**Location**: `shared/model-loader.cjs`

**Key components**:
- `pythonDaemon` - Spawned Python process
- `requestQueue` - Queued prediction requests
- `daemonReady` - Daemon initialization status

**Request flow**:
1. `predict()` called
2. Check JS prediction cache (5min TTL)
3. If cache miss → queue request to daemon
4. Daemon processes request (checks Python model cache)
5. Result returned and cached in JS

## Cache Expiration

| Cache Layer | TTL | Reason |
|-------------|-----|--------|
| Python models | 30 minutes | Balance memory vs reload overhead |
| JS predictions | 5 minutes | Fast invalidation for changing data |

Models are automatically expired and reloaded when TTL expires. No manual management needed.

## Testing

Three test suites verify caching behavior:

### 1. Basic Caching Test
```bash
node tests/test-model-caching.cjs
```
Tests cold start → cached → cached flow with multiple models.

### 2. Daemon Warmup Test
```bash
node tests/test-model-caching-warmup.cjs
```
Tests with pre-warmed daemon (realistic production scenario).

### 3. Python Model Cache Test
```bash
node tests/test-python-model-cache.cjs
```
Tests that model stays cached even with different features (verifies Python caching).

## Benefits

1. **Development Speed**: No more 40s waits during development
2. **Production Performance**: 96.8% faster for repeated model usage
3. **Resource Efficiency**: Models loaded once, shared across predictions
4. **Transparent**: No code changes needed for existing callers

## Configuration

### Change Cache TTL

**Python models** (`shared/model-loader-helper.py`):
```python
CACHE_TTL_MS = 60 * 60 * 1000  # 1 hour
```

**JS predictions** (`shared/model-loader.cjs`):
```javascript
if (Date.now() - cached.timestamp < 10 * 60 * 1000) {  // 10 minutes
```

### Disable Caching

```javascript
// Disable Python caching (CLI mode)
const result = await predict(model, features, { useDaemon: false });

// Disable JS caching
const result = await predict(model, features, { cache: false });
```

## Troubleshooting

### Daemon Won't Start

Check Python dependencies:
```bash
python3 -c "import sklearn, numpy, pickle; print('OK')"
```

### Stale Predictions

Clear caches after model retraining:
```javascript
await restartDaemon();
```

Or manually:
```bash
python3 shared/model-loader-helper.py clear-cache
```

### Memory Usage

Monitor Python cache:
```javascript
const stats = await getCacheStats();
console.log(stats.python.cached_models); // Number of models in memory
```

Each model is typically 5-50MB. With 30min TTL and 60 models, worst case ~3GB.

## Future Improvements

- [ ] LRU eviction (currently only time-based)
- [ ] Persistent cache (Redis/memcached)
- [ ] Cache warming (preload common models)
- [ ] Metrics (cache hit rate, latency percentiles)
- [ ] Multi-daemon support (worker pool)

## Files Modified

- `shared/model-loader-helper.py` - Added caching and daemon mode
- `shared/model-loader.cjs` - Added daemon management
- `tests/test-model-caching.cjs` - Basic test suite
- `tests/test-model-caching-warmup.cjs` - Warmup test
- `tests/test-python-model-cache.cjs` - Python cache test
- `docs/MODEL_CACHING.md` - This documentation

## See Also

- Issue #322: Production blockers
- `shared/model-loader.cjs` - Main API
- `shared/model-loader-helper.py` - Python implementation
