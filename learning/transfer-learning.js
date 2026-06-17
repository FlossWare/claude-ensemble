#!/usr/bin/env node
/**
 * Transfer Learning Module
 *
 * Implements transfer learning for new models by bootstrapping from similar existing models
 * with confidence decay over time.
 *
 * Features:
 *   1. Model similarity detection (architecture, provider, family)
 *   2. Bootstrap calibration data from similar models
 *   3. Time-based confidence decay
 *   4. Weighted transfer based on similarity score
 *   5. Automatic transition from transferred to native calibration
 *   6. Transfer quality tracking and validation
 *
 * Usage:
 *   const transfer = require('./transfer-learning');
 *   await transfer.bootstrapNewModel('claude-opus-4.5', sourceModels);
 *   const calibration = await transfer.getTransferredCalibration('claude-opus-4.5', taskType);
 *   await transfer.updateWithNativeData(modelId, executionData);
 *
 * Tables:
 *   model_transfer_log   - Transfer events and similarity mappings
 *   calibration_history  - Native + transferred calibration data
 *   execution_log        - Source data for native calibration
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const os = require('os');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DB_PATH = path.join(os.homedir(), '.claude', 'learning', 'db', 'learning.db');

// Decay function: exponential decay over time
// confidence(t) = initial_confidence * exp(-decay_rate * days_elapsed)
const TRANSFER_DECAY_RATE = 0.1;  // 10% decay per day
const MIN_TRANSFER_CONFIDENCE = 0.2;  // Don't use transfers below 20% confidence
const TRANSFER_INITIAL_CONFIDENCE = 0.7;  // Start at 70% confidence for good matches

// Minimum native samples before fully trusting native calibration
const NATIVE_SAMPLES_THRESHOLD = 20;

// Similarity scoring weights
const SIMILARITY_WEIGHTS = {
  provider: 0.3,      // Same provider (anthropic, openai, google)
  family: 0.3,        // Same model family (claude-3, gpt-4, gemini)
  architecture: 0.2,  // Similar architecture (opus, sonnet, haiku)
  taskType: 0.2       // Performance on same task type
};

// ---------------------------------------------------------------------------
// Database helpers
// ---------------------------------------------------------------------------

function openDb() {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) return reject(err);
      db.run('PRAGMA journal_mode = WAL', () => {
        db.run('PRAGMA synchronous = NORMAL', () => {
          db.run('PRAGMA busy_timeout = 5000', () => {
            resolve(db);
          });
        });
      });
    });
  });
}

function dbAll(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows || []);
    });
  });
}

function dbGet(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => {
      if (err) reject(err);
      else resolve(row || null);
    });
  });
}

function dbRun(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) {
      if (err) reject(err);
      else resolve({ lastID: this.lastID, changes: this.changes });
    });
  });
}

// ---------------------------------------------------------------------------
// Model similarity calculation
// ---------------------------------------------------------------------------

/**
 * Parse model identifier into components
 * Examples:
 *   claude-opus-4 → { provider: 'anthropic', family: 'claude-4', arch: 'opus' }
 *   gpt-4-turbo → { provider: 'openai', family: 'gpt-4', arch: 'turbo' }
 *   gemini-1.5-pro → { provider: 'google', family: 'gemini-1.5', arch: 'pro' }
 */
function parseModelId(modelId) {
  const normalized = modelId.toLowerCase();

  let provider = 'unknown';
  if (normalized.includes('claude') || normalized.includes('anthropic')) {
    provider = 'anthropic';
  } else if (normalized.includes('gpt') || normalized.includes('openai')) {
    provider = 'openai';
  } else if (normalized.includes('gemini') || normalized.includes('google')) {
    provider = 'google';
  } else if (normalized.includes('llama')) {
    provider = 'meta';
  } else if (normalized.includes('mistral')) {
    provider = 'mistral';
  }

  let family = 'unknown';
  let arch = 'unknown';

  if (provider === 'anthropic') {
    const match = normalized.match(/claude-(\d+(?:\.\d+)?)/);
    family = match ? `claude-${match[1]}` : 'claude';

    if (normalized.includes('opus')) arch = 'opus';
    else if (normalized.includes('sonnet')) arch = 'sonnet';
    else if (normalized.includes('haiku')) arch = 'haiku';
  } else if (provider === 'openai') {
    if (normalized.includes('gpt-4')) {
      family = 'gpt-4';
      if (normalized.includes('turbo')) arch = 'turbo';
      else if (normalized.includes('o')) arch = 'o';
    } else if (normalized.includes('gpt-3.5')) {
      family = 'gpt-3.5';
    }
  } else if (provider === 'google') {
    const match = normalized.match(/gemini-(\d+(?:\.\d+)?)/);
    family = match ? `gemini-${match[1]}` : 'gemini';

    if (normalized.includes('pro')) arch = 'pro';
    else if (normalized.includes('flash')) arch = 'flash';
    else if (normalized.includes('ultra')) arch = 'ultra';
  }

  return { provider, family, arch, original: modelId };
}

/**
 * Calculate similarity score between two models
 * Returns 0.0 (completely different) to 1.0 (identical)
 */
function calculateSimilarity(model1, model2, taskType = null, model1Stats = null, model2Stats = null) {
  const parsed1 = parseModelId(model1);
  const parsed2 = parseModelId(model2);

  let score = 0;

  // Provider similarity
  if (parsed1.provider === parsed2.provider) {
    score += SIMILARITY_WEIGHTS.provider;
  }

  // Family similarity
  if (parsed1.family === parsed2.family) {
    score += SIMILARITY_WEIGHTS.family;
  }

  // Architecture similarity
  if (parsed1.arch === parsed2.arch) {
    score += SIMILARITY_WEIGHTS.architecture;
  }

  // Task type performance correlation (if stats available)
  if (taskType && model1Stats && model2Stats) {
    // Compare quality scores for same task type
    const qualityDiff = Math.abs(model1Stats.avgQuality - model2Stats.avgQuality);
    const taskSimilarity = Math.max(0, 1 - qualityDiff);
    score += SIMILARITY_WEIGHTS.taskType * taskSimilarity;
  }

  return Math.min(1.0, score);
}

/**
 * Find most similar models for transfer learning
 * Returns array of { model, similarity, stats } sorted by similarity
 */
async function findSimilarModels(db, targetModel, taskType = null, limit = 5) {
  // Get all existing models with calibration data
  const existingModels = await dbAll(db, `
    SELECT DISTINCT el.model,
      COUNT(*) as execution_count,
      AVG(el.quality_score) as avg_quality,
      AVG(el.confidence) as avg_confidence
    FROM execution_log el
    WHERE el.model != ?
    GROUP BY el.model
    HAVING execution_count >= 5
    ORDER BY execution_count DESC
  `, [targetModel]);

  if (existingModels.length === 0) {
    return [];
  }

  // Calculate similarity scores
  const similarities = [];
  for (const existing of existingModels) {
    const similarity = calculateSimilarity(
      targetModel,
      existing.model,
      taskType,
      null,
      { avgQuality: existing.avg_quality, avgConfidence: existing.avg_confidence }
    );

    if (similarity > 0.1) {  // Only include if at least 10% similar
      similarities.push({
        model: existing.model,
        similarity,
        executionCount: existing.execution_count,
        avgQuality: existing.avg_quality,
        avgConfidence: existing.avg_confidence
      });
    }
  }

  // Sort by similarity and return top matches
  similarities.sort((a, b) => b.similarity - a.similarity);
  return similarities.slice(0, limit);
}

// ---------------------------------------------------------------------------
// Transfer learning initialization
// ---------------------------------------------------------------------------

/**
 * Bootstrap a new model with transferred calibration data
 *
 * @param {string} newModel - Model identifier to bootstrap
 * @param {string[]} sourceModels - Optional: specific source models (auto-detected if null)
 * @param {string} taskType - Optional: specific task type
 * @returns {object} Transfer summary
 */
async function bootstrapNewModel(newModel, sourceModels = null, taskType = null) {
  const db = await openDb();

  try {
    // Check if model already has calibration data
    const existing = await dbGet(db, `
      SELECT COUNT(*) as count FROM execution_log WHERE model = ?
    `, [newModel]);

    if (existing && existing.count >= NATIVE_SAMPLES_THRESHOLD) {
      return {
        success: false,
        reason: 'model_already_calibrated',
        nativeSamples: existing.count,
        message: `Model ${newModel} already has ${existing.count} native samples`
      };
    }

    // Find similar models
    const similarModels = sourceModels
      ? sourceModels.map(m => ({ model: m, similarity: 1.0 }))
      : await findSimilarModels(db, newModel, taskType, 5);

    if (similarModels.length === 0) {
      return {
        success: false,
        reason: 'no_similar_models',
        message: `No similar models found for ${newModel}`
      };
    }

    // Create transfer records
    const timestamp = new Date().toISOString();
    const transfers = [];

    for (const similar of similarModels) {
      // Record transfer event
      await dbRun(db, `
        INSERT INTO model_transfer_log (
          timestamp, target_model, source_model, similarity_score,
          task_type, transfer_method, initial_confidence, decay_rate,
          status, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `, [
        timestamp,
        newModel,
        similar.model,
        similar.similarity,
        taskType,
        'similarity_weighted',
        TRANSFER_INITIAL_CONFIDENCE * similar.similarity,
        TRANSFER_DECAY_RATE,
        'active',
        JSON.stringify({
          executionCount: similar.executionCount,
          avgQuality: similar.avgQuality,
          avgConfidence: similar.avgConfidence
        })
      ]);

      transfers.push({
        sourceModel: similar.model,
        similarity: similar.similarity,
        initialConfidence: TRANSFER_INITIAL_CONFIDENCE * similar.similarity
      });
    }

    return {
      success: true,
      targetModel: newModel,
      sourceModels: transfers,
      timestamp,
      taskType,
      message: `Bootstrapped ${newModel} from ${transfers.length} similar models`
    };

  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Transferred calibration retrieval with decay
// ---------------------------------------------------------------------------

/**
 * Get calibration data for a model, using transfers if native data insufficient
 * Applies time-based confidence decay to transferred data
 *
 * @param {string} modelId - Target model
 * @param {string} taskType - Task type
 * @returns {object} Calibration data with confidence
 */
async function getTransferredCalibration(modelId, taskType) {
  const db = await openDb();

  try {
    // Check native calibration data
    const nativeData = await dbAll(db, `
      SELECT
        quality_score,
        confidence,
        outcome,
        timestamp
      FROM execution_log
      WHERE model = ? AND task_type = ?
      ORDER BY timestamp DESC
      LIMIT 50
    `, [modelId, taskType]);

    const nativeCount = nativeData.length;

    // If sufficient native data, use it with full confidence
    if (nativeCount >= NATIVE_SAMPLES_THRESHOLD) {
      const avgQuality = nativeData.reduce((sum, d) => sum + d.quality_score, 0) / nativeCount;
      const avgConfidence = nativeData.reduce((sum, d) => sum + d.confidence, 0) / nativeCount;
      const successRate = nativeData.filter(d => d.outcome === 'success').length / nativeCount;

      return {
        source: 'native',
        modelId,
        taskType,
        sampleCount: nativeCount,
        avgQuality,
        avgConfidence,
        successRate,
        calibrationConfidence: 1.0,
        timestamp: new Date().toISOString()
      };
    }

    // Get active transfers
    const transfers = await dbAll(db, `
      SELECT
        source_model,
        similarity_score,
        initial_confidence,
        decay_rate,
        timestamp,
        metadata
      FROM model_transfer_log
      WHERE target_model = ?
        AND (task_type = ? OR task_type IS NULL)
        AND status = 'active'
      ORDER BY similarity_score DESC
    `, [modelId, taskType]);

    if (transfers.length === 0 && nativeCount > 0) {
      // Use native data with reduced confidence
      const avgQuality = nativeData.reduce((sum, d) => sum + d.quality_score, 0) / nativeCount;
      const avgConfidence = nativeData.reduce((sum, d) => sum + d.confidence, 0) / nativeCount;
      const successRate = nativeData.filter(d => d.outcome === 'success').length / nativeCount;

      return {
        source: 'native_partial',
        modelId,
        taskType,
        sampleCount: nativeCount,
        avgQuality,
        avgConfidence,
        successRate,
        calibrationConfidence: nativeCount / NATIVE_SAMPLES_THRESHOLD,
        timestamp: new Date().toISOString()
      };
    }

    if (transfers.length === 0) {
      return {
        source: 'none',
        modelId,
        taskType,
        sampleCount: 0,
        calibrationConfidence: 0.0,
        message: 'No calibration data available'
      };
    }

    // Combine transferred data with confidence decay
    const now = Date.now();
    let totalWeight = 0;
    let weightedQuality = 0;
    let weightedConfidence = 0;
    let weightedSuccess = 0;
    const sources = [];

    for (const transfer of transfers) {
      // Calculate time decay
      const transferTime = new Date(transfer.timestamp).getTime();
      const daysElapsed = (now - transferTime) / (1000 * 60 * 60 * 24);
      const decayedConfidence = transfer.initial_confidence * Math.exp(-transfer.decay_rate * daysElapsed);

      if (decayedConfidence < MIN_TRANSFER_CONFIDENCE) {
        // Mark transfer as expired
        await dbRun(db, `
          UPDATE model_transfer_log
          SET status = 'expired', metadata = json_set(metadata, '$.expired_at', ?)
          WHERE target_model = ? AND source_model = ?
        `, [new Date().toISOString(), modelId, transfer.source_model]);
        continue;
      }

      // Get source model calibration data
      const sourceData = await dbAll(db, `
        SELECT quality_score, confidence, outcome
        FROM execution_log
        WHERE model = ? AND task_type = ?
        ORDER BY timestamp DESC
        LIMIT 50
      `, [transfer.source_model, taskType]);

      if (sourceData.length === 0) continue;

      const sourceQuality = sourceData.reduce((sum, d) => sum + d.quality_score, 0) / sourceData.length;
      const sourceConfidence = sourceData.reduce((sum, d) => sum + d.confidence, 0) / sourceData.length;
      const sourceSuccess = sourceData.filter(d => d.outcome === 'success').length / sourceData.length;

      // Weight by similarity and decayed confidence
      const weight = transfer.similarity_score * decayedConfidence;
      totalWeight += weight;
      weightedQuality += sourceQuality * weight;
      weightedConfidence += sourceConfidence * weight;
      weightedSuccess += sourceSuccess * weight;

      sources.push({
        sourceModel: transfer.source_model,
        similarity: transfer.similarity_score,
        decayedConfidence,
        daysElapsed,
        sampleCount: sourceData.length,
        weight
      });
    }

    // Blend with native data if available
    if (nativeCount > 0) {
      const nativeWeight = nativeCount / NATIVE_SAMPLES_THRESHOLD;
      const nativeQuality = nativeData.reduce((sum, d) => sum + d.quality_score, 0) / nativeCount;
      const nativeConfidence = nativeData.reduce((sum, d) => sum + d.confidence, 0) / nativeCount;
      const nativeSuccess = nativeData.filter(d => d.outcome === 'success').length / nativeCount;

      totalWeight += nativeWeight;
      weightedQuality += nativeQuality * nativeWeight;
      weightedConfidence += nativeConfidence * nativeWeight;
      weightedSuccess += nativeSuccess * nativeWeight;

      sources.push({
        sourceModel: 'native',
        similarity: 1.0,
        confidence: 1.0,
        sampleCount: nativeCount,
        weight: nativeWeight
      });
    }

    if (totalWeight === 0) {
      return {
        source: 'none',
        modelId,
        taskType,
        sampleCount: 0,
        calibrationConfidence: 0.0
      };
    }

    return {
      source: nativeCount > 0 ? 'hybrid' : 'transferred',
      modelId,
      taskType,
      nativeSamples: nativeCount,
      transferSources: sources.filter(s => s.sourceModel !== 'native'),
      avgQuality: weightedQuality / totalWeight,
      avgConfidence: weightedConfidence / totalWeight,
      successRate: weightedSuccess / totalWeight,
      calibrationConfidence: Math.min(1.0, totalWeight),
      timestamp: new Date().toISOString()
    };

  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Native data updates
// ---------------------------------------------------------------------------

/**
 * Update model with new native execution data
 * Automatically transitions from transferred to native calibration
 *
 * @param {string} modelId - Model identifier
 * @param {object} executionData - New execution data
 * @returns {object} Update status
 */
async function updateWithNativeData(modelId, executionData) {
  const db = await openDb();

  try {
    // Check current native sample count
    const current = await dbGet(db, `
      SELECT COUNT(*) as count FROM execution_log WHERE model = ?
    `, [modelId]);

    const newCount = (current?.count || 0) + 1;

    // If crossing threshold, mark transfers as superseded
    if (current?.count < NATIVE_SAMPLES_THRESHOLD && newCount >= NATIVE_SAMPLES_THRESHOLD) {
      await dbRun(db, `
        UPDATE model_transfer_log
        SET status = 'superseded',
            metadata = json_set(metadata, '$.superseded_at', ?, '$.native_samples', ?)
        WHERE target_model = ? AND status = 'active'
      `, [new Date().toISOString(), newCount, modelId]);

      return {
        success: true,
        modelId,
        nativeSamples: newCount,
        transition: 'transferred_to_native',
        message: `Model ${modelId} now has sufficient native calibration data`
      };
    }

    return {
      success: true,
      modelId,
      nativeSamples: newCount,
      transition: newCount < NATIVE_SAMPLES_THRESHOLD ? 'building_native' : 'native_established'
    };

  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Transfer quality validation
// ---------------------------------------------------------------------------

/**
 * Validate transfer quality by comparing transferred vs native performance
 *
 * @param {string} modelId - Model to validate
 * @param {string} taskType - Task type
 * @returns {object} Validation results
 */
async function validateTransfer(modelId, taskType) {
  const db = await openDb();

  try {
    // Get native data
    const nativeData = await dbAll(db, `
      SELECT quality_score, confidence, outcome
      FROM execution_log
      WHERE model = ? AND task_type = ?
      ORDER BY timestamp DESC
      LIMIT 50
    `, [modelId, taskType]);

    if (nativeData.length < 10) {
      return {
        success: false,
        reason: 'insufficient_native_data',
        nativeSamples: nativeData.length
      };
    }

    // Get transferred prediction
    const transferred = await getTransferredCalibration(modelId, taskType);

    if (transferred.source === 'none' || transferred.source === 'native') {
      return {
        success: false,
        reason: 'no_transfer_to_validate'
      };
    }

    // Calculate native statistics
    const nativeQuality = nativeData.reduce((sum, d) => sum + d.quality_score, 0) / nativeData.length;
    const nativeConfidence = nativeData.reduce((sum, d) => sum + d.confidence, 0) / nativeData.length;
    const nativeSuccess = nativeData.filter(d => d.outcome === 'success').length / nativeData.length;

    // Calculate prediction errors
    const qualityError = Math.abs(nativeQuality - transferred.avgQuality);
    const confidenceError = Math.abs(nativeConfidence - transferred.avgConfidence);
    const successError = Math.abs(nativeSuccess - transferred.successRate);

    // Overall transfer quality (lower error = better)
    const transferQuality = 1 - ((qualityError + confidenceError + successError) / 3);

    return {
      success: true,
      modelId,
      taskType,
      nativeSamples: nativeData.length,
      transferSources: transferred.transferSources,
      native: {
        avgQuality: nativeQuality,
        avgConfidence: nativeConfidence,
        successRate: nativeSuccess
      },
      transferred: {
        avgQuality: transferred.avgQuality,
        avgConfidence: transferred.avgConfidence,
        successRate: transferred.successRate
      },
      errors: {
        quality: qualityError,
        confidence: confidenceError,
        success: successError
      },
      transferQuality,
      assessment: transferQuality > 0.8 ? 'excellent' :
                  transferQuality > 0.6 ? 'good' :
                  transferQuality > 0.4 ? 'fair' : 'poor'
    };

  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  bootstrapNewModel,
  getTransferredCalibration,
  updateWithNativeData,
  validateTransfer,
  findSimilarModels,
  calculateSimilarity,
  parseModelId,

  // Constants
  TRANSFER_DECAY_RATE,
  MIN_TRANSFER_CONFIDENCE,
  TRANSFER_INITIAL_CONFIDENCE,
  NATIVE_SAMPLES_THRESHOLD
};

// ---------------------------------------------------------------------------
// CLI interface
// ---------------------------------------------------------------------------

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  (async () => {
    try {
      switch (command) {
        case 'bootstrap': {
          // Usage: transfer-learning.js bootstrap <new-model> [source-model1,source-model2,...] [task-type]
          const newModel = args[1];
          const sourceModels = args[2] ? args[2].split(',') : null;
          const taskType = args[3] || null;

          const result = await bootstrapNewModel(newModel, sourceModels, taskType);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'calibration': {
          // Usage: transfer-learning.js calibration <model> <task-type>
          const model = args[1];
          const taskType = args[2];

          const result = await getTransferredCalibration(model, taskType);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'validate': {
          // Usage: transfer-learning.js validate <model> <task-type>
          const model = args[1];
          const taskType = args[2];

          const result = await validateTransfer(model, taskType);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'similar': {
          // Usage: transfer-learning.js similar <model> [task-type] [limit]
          const model = args[1];
          const taskType = args[2] || null;
          const limit = parseInt(args[3]) || 5;

          const db = await openDb();
          try {
            const result = await findSimilarModels(db, model, taskType, limit);
            console.log(JSON.stringify(result, null, 2));
          } finally {
            db.close();
          }
          break;
        }

        case 'parse': {
          // Usage: transfer-learning.js parse <model-id>
          const model = args[1];
          const result = parseModelId(model);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        default:
          console.log(`
Transfer Learning CLI

Usage:
  transfer-learning.js bootstrap <new-model> [source1,source2,...] [task-type]
    Bootstrap a new model with transferred calibration data

  transfer-learning.js calibration <model> <task-type>
    Get calibration data (native or transferred with decay)

  transfer-learning.js validate <model> <task-type>
    Validate transfer quality against native data

  transfer-learning.js similar <model> [task-type] [limit]
    Find similar models for transfer learning

  transfer-learning.js parse <model-id>
    Parse model identifier into components

Examples:
  transfer-learning.js bootstrap claude-opus-4.5
  transfer-learning.js calibration claude-opus-4.5 code-review
  transfer-learning.js validate claude-opus-4.5 code-review
  transfer-learning.js similar claude-sonnet-4 code-review 10
  transfer-learning.js parse claude-opus-4.5
          `);
      }
    } catch (error) {
      console.error('Error:', error.message);
      console.error(error.stack);
      process.exit(1);
    }
  })();
}
