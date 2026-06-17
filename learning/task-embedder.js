#!/usr/bin/env node
/**
 * Task Embedder -- Task Embedding and Intelligent Routing (Phase 2)
 *
 * Creates feature vectors for each task type from execution history,
 * computes pairwise similarity, and enables transfer learning for
 * cold-start task types.
 *
 * Features:
 *   1. Task Feature Vectors: ~25-dim embedding from execution_log statistics
 *   2. Similarity Index: cosine similarity between task type pairs
 *   3. Transfer Routing: borrow bandit posteriors from similar tasks
 *   4. Affinity Matrix: correlation of model quality rankings
 *
 * Usage:
 *   const embedder = require('./task-embedder');
 *   const embedding = await embedder.getTaskEmbedding('security');
 *   const similar = await embedder.findSimilarTasks('security', 3);
 *   const transferred = await embedder.transferPriors(db, 'new_task', models);
 *
 * Tables read:  execution_log, model_tuning
 * Tables written: task_affinity
 */

const path = require('path');

const DB_PATH = path.join(__dirname, 'db', 'learning.db');
const KNOWN_MODELS = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'];
const MIN_SAMPLES_FOR_EMBEDDING = 3;
const K_NEAREST = 3;
const AFFINITY_RECOMPUTE_INTERVAL = 50; // recompute after every N executions

// ---------------------------------------------------------------------------
// Database helpers
// ---------------------------------------------------------------------------

let _sqlite3 = null;
function getSqlite3() {
  if (!_sqlite3) {
    try { _sqlite3 = require('sqlite3').verbose(); } catch (_) {
      _sqlite3 = require(path.join(__dirname, 'node_modules', 'sqlite3')).verbose();
    }
  }
  return _sqlite3;
}

function openDb() {
  const sqlite3 = getSqlite3();
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) return reject(err);
      db.run('PRAGMA journal_mode = WAL', () => {
        db.run('PRAGMA synchronous = NORMAL', () => {
          db.run('PRAGMA busy_timeout = 5000', () => resolve(db));
        });
      });
    });
  });
}

function dbAll(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => err ? reject(err) : resolve(rows || []));
  });
}

function dbGet(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => err ? reject(err) : resolve(row || null));
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

function closeDb(db) {
  return new Promise((resolve) => {
    if (db) db.close(() => resolve());
    else resolve();
  });
}

// ---------------------------------------------------------------------------
// Math helpers
// ---------------------------------------------------------------------------

function mean(arr) {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function cosineSimilarity(a, b) {
  if (a.length !== b.length || a.length === 0) return 0;
  let dotProduct = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom === 0 ? 0 : dotProduct / denom;
}

function pearsonCorrelation(x, y) {
  if (x.length !== y.length || x.length < 2) return 0;
  const n = x.length;
  const mx = mean(x), my = mean(y);
  let num = 0, dx2 = 0, dy2 = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - mx;
    const dy = y[i] - my;
    num += dx * dy;
    dx2 += dx * dx;
    dy2 += dy * dy;
  }
  const denom = Math.sqrt(dx2 * dy2);
  return denom === 0 ? 0 : num / denom;
}

// ---------------------------------------------------------------------------
// Core: Build task embedding vector
// ---------------------------------------------------------------------------

/**
 * Build a feature vector for a task type from execution history.
 *
 * Dimensions (approximately 25):
 *   - avg_quality_by_model (6 dims: one per known model)
 *   - avg_cost_by_model (6 dims)
 *   - avg_duration_by_model (6 dims)
 *   - consensus_score_mean (1 dim)
 *   - diversity_score_mean (1 dim)
 *   - model_count_mean (1 dim)
 *   - success_rate (1 dim)
 *   - sample_count_normalized (1 dim)
 *   - avg_confidence (1 dim)
 *   - selection_rate_variance (1 dim)
 *
 * @param {string} taskType - Task type to embed
 * @param {object} db - Optional database connection
 * @returns {object} { taskType, vector, dimensions, sampleCount }
 */
async function getTaskEmbedding(taskType, db = null) {
  const ownDb = !db;
  if (!db) db = await openDb();

  try {
    // Get per-model quality averages
    const modelStats = await dbAll(db, `
      SELECT
        model,
        AVG(quality_score) AS avg_quality,
        AVG(cost_usd) AS avg_cost,
        AVG(duration_ms) AS avg_duration,
        AVG(was_selected) AS selection_rate,
        COUNT(*) AS cnt
      FROM execution_log
      WHERE task_type = ? AND quality_score IS NOT NULL
      GROUP BY model
    `, [taskType]);

    // Build per-model feature maps
    const qualityByModel = {};
    const costByModel = {};
    const durationByModel = {};
    let totalSamples = 0;

    for (const row of modelStats) {
      qualityByModel[row.model] = row.avg_quality || 0;
      costByModel[row.model] = row.avg_cost || 0;
      durationByModel[row.model] = row.avg_duration || 0;
      totalSamples += row.cnt;
    }

    if (totalSamples < MIN_SAMPLES_FOR_EMBEDDING) {
      return { taskType, vector: null, dimensions: 0, sampleCount: totalSamples };
    }

    // Get aggregate stats
    const aggRow = await dbGet(db, `
      SELECT
        AVG(consensus_score) AS avg_consensus,
        AVG(diversity_score) AS avg_diversity,
        AVG(model_count) AS avg_model_count,
        AVG(confidence) AS avg_confidence,
        SUM(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END) / COUNT(*) AS success_rate
      FROM execution_log
      WHERE task_type = ? AND quality_score IS NOT NULL
    `, [taskType]);

    // Build vector: ordered by KNOWN_MODELS for consistency
    const vector = [];

    // Quality dims (6)
    for (const model of KNOWN_MODELS) {
      vector.push(qualityByModel[model] || 0);
    }
    // Cost dims (6) -- normalize to 0-1 range (max $1)
    for (const model of KNOWN_MODELS) {
      vector.push(Math.min(1, (costByModel[model] || 0)));
    }
    // Duration dims (6) -- normalize to 0-1 range (max 60s)
    for (const model of KNOWN_MODELS) {
      vector.push(Math.min(1, (durationByModel[model] || 0) / 60000));
    }
    // Aggregate dims
    vector.push(aggRow?.avg_consensus || 0);
    vector.push(aggRow?.avg_diversity || 0);
    vector.push(Math.min(1, (aggRow?.avg_model_count || 1) / 6));
    vector.push(aggRow?.success_rate || 0);
    vector.push(Math.min(1, totalSamples / 100)); // normalized sample count
    vector.push(aggRow?.avg_confidence || 0);

    // Selection rate variance (how much do models differ in being chosen)
    const selRates = KNOWN_MODELS.map(m => {
      const s = modelStats.find(r => r.model === m);
      return s ? s.selection_rate : 0;
    });
    const selMean = mean(selRates);
    const selVar = selRates.reduce((sum, v) => sum + (v - selMean) ** 2, 0) / (selRates.length || 1);
    vector.push(selVar);

    return {
      taskType,
      vector,
      dimensions: vector.length,
      sampleCount: totalSamples,
      modelStats: qualityByModel
    };

  } finally {
    if (ownDb) await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Find similar task types
// ---------------------------------------------------------------------------

/**
 * Find the k most similar task types to the given one.
 *
 * @param {string} taskType - Target task type
 * @param {number} k - Number of similar tasks to return
 * @param {object} db - Optional database connection
 * @returns {object[]} Sorted by similarity descending
 */
async function findSimilarTasks(taskType, k = K_NEAREST, db = null) {
  const ownDb = !db;
  if (!db) db = await openDb();

  try {
    // Get target embedding
    const target = await getTaskEmbedding(taskType, db);
    if (!target.vector) {
      return [];
    }

    // Get all other task types
    const taskTypes = await dbAll(db, `
      SELECT DISTINCT task_type FROM execution_log
      WHERE task_type IS NOT NULL AND task_type != ?
        AND quality_score IS NOT NULL
      GROUP BY task_type
      HAVING COUNT(*) >= ?
    `, [taskType, MIN_SAMPLES_FOR_EMBEDDING]);

    // Compute embeddings and similarities
    const similarities = [];
    for (const row of taskTypes) {
      const other = await getTaskEmbedding(row.task_type, db);
      if (!other.vector) continue;

      const sim = cosineSimilarity(target.vector, other.vector);
      similarities.push({
        taskType: row.task_type,
        similarity: sim,
        sampleCount: other.sampleCount
      });
    }

    // Sort by similarity descending, return top k
    similarities.sort((a, b) => b.similarity - a.similarity);
    return similarities.slice(0, k);

  } finally {
    if (ownDb) await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Transfer bandit priors from similar tasks (cold-start solution)
// ---------------------------------------------------------------------------

/**
 * When a new task type has fewer than MIN_SAMPLES executions,
 * find k nearest task types and transfer their bandit posteriors
 * weighted by similarity.
 *
 * @param {object} db - Database connection
 * @param {string} taskType - New task type
 * @param {string[]} candidateModels - Models to create priors for
 * @returns {object} { transferred, states, sourceTaskTypes }
 */
async function transferPriors(db, taskType, candidateModels) {
  const similar = await findSimilarTasks(taskType, K_NEAREST, db);

  if (similar.length === 0) {
    return { transferred: false, states: null, reason: 'no similar tasks found' };
  }

  // Load bandit states from similar tasks
  const states = new Map();
  for (const model of candidateModels) {
    let weightedAlpha = 0;
    let weightedBeta = 0;
    let totalWeight = 0;

    for (const src of similar) {
      const srcState = await dbGet(db,
        'SELECT alpha, beta FROM bandit_state WHERE model = ? AND task_type = ?',
        [model, src.taskType]
      );

      if (srcState) {
        const weight = src.similarity;
        weightedAlpha += srcState.alpha * weight;
        weightedBeta += srcState.beta * weight;
        totalWeight += weight;
      }
    }

    if (totalWeight > 0) {
      states.set(model, {
        alpha: Math.max(1.0, weightedAlpha / totalWeight),
        beta: Math.max(1.0, weightedBeta / totalWeight),
        totalPulls: 0,
        cumulativeRegret: 0.0,
        windowStart: null
      });
    } else {
      states.set(model, {
        alpha: 1.0,
        beta: 1.0,
        totalPulls: 0,
        cumulativeRegret: 0.0,
        windowStart: null
      });
    }
  }

  return {
    transferred: true,
    states,
    sourceTaskTypes: similar.map(s => ({ taskType: s.taskType, similarity: s.similarity }))
  };
}

// ---------------------------------------------------------------------------
// Core: Compute and store task affinity matrix
// ---------------------------------------------------------------------------

/**
 * Recompute pairwise task affinity: cosine similarity of embeddings and
 * correlation of model quality rankings.
 *
 * Called periodically (every AFFINITY_RECOMPUTE_INTERVAL executions).
 */
async function recomputeAffinityMatrix() {
  const db = await openDb();

  try {
    // Get all task types with sufficient data
    const taskTypes = await dbAll(db, `
      SELECT DISTINCT task_type FROM execution_log
      WHERE task_type IS NOT NULL AND quality_score IS NOT NULL
      GROUP BY task_type
      HAVING COUNT(*) >= ?
    `, [MIN_SAMPLES_FOR_EMBEDDING]);

    const embeddings = new Map();
    const modelQualityRankings = new Map();

    // Build embeddings and quality rankings for each task type
    for (const { task_type } of taskTypes) {
      const emb = await getTaskEmbedding(task_type, db);
      if (emb.vector) {
        embeddings.set(task_type, emb);

        // Get quality rankings: ordered model list by avg quality
        const rankings = KNOWN_MODELS.map(m => emb.modelStats?.[m] || 0);
        modelQualityRankings.set(task_type, rankings);
      }
    }

    // Compute pairwise similarities
    const taskTypeList = Array.from(embeddings.keys());
    let updated = 0;

    for (let i = 0; i < taskTypeList.length; i++) {
      for (let j = i + 1; j < taskTypeList.length; j++) {
        const a = taskTypeList[i];
        const b = taskTypeList[j];

        const embA = embeddings.get(a);
        const embB = embeddings.get(b);

        const cosSim = cosineSimilarity(embA.vector, embB.vector);

        // Compute quality correlation: do models rank the same way?
        const rankA = modelQualityRankings.get(a);
        const rankB = modelQualityRankings.get(b);
        const qualCorr = pearsonCorrelation(rankA, rankB);

        // Transfer score: weighted combination
        const transferScore = 0.6 * cosSim + 0.4 * Math.max(0, qualCorr);
        const sampleCount = embA.sampleCount + embB.sampleCount;

        await dbRun(db, `
          INSERT INTO task_affinity (task_type_a, task_type_b, cosine_similarity,
                                     transfer_score, quality_correlation, sample_count, computed_at)
          VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
          ON CONFLICT(task_type_a, task_type_b) DO UPDATE SET
            cosine_similarity = excluded.cosine_similarity,
            transfer_score = excluded.transfer_score,
            quality_correlation = excluded.quality_correlation,
            sample_count = excluded.sample_count,
            computed_at = excluded.computed_at
        `, [a, b, cosSim, transferScore, qualCorr, sampleCount]);

        // Also store reverse direction
        await dbRun(db, `
          INSERT INTO task_affinity (task_type_a, task_type_b, cosine_similarity,
                                     transfer_score, quality_correlation, sample_count, computed_at)
          VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
          ON CONFLICT(task_type_a, task_type_b) DO UPDATE SET
            cosine_similarity = excluded.cosine_similarity,
            transfer_score = excluded.transfer_score,
            quality_correlation = excluded.quality_correlation,
            sample_count = excluded.sample_count,
            computed_at = excluded.computed_at
        `, [b, a, cosSim, transferScore, qualCorr, sampleCount]);

        updated++;
      }
    }

    return {
      taskTypes: taskTypeList.length,
      pairsUpdated: updated,
      timestamp: new Date().toISOString()
    };

  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Core: Get affinity data for visualization
// ---------------------------------------------------------------------------

/**
 * Get the full affinity matrix for a task type or all task types.
 */
async function getAffinityMatrix(taskType = null) {
  const db = await openDb();
  try {
    let sql = 'SELECT * FROM task_affinity';
    const params = [];
    if (taskType) {
      sql += ' WHERE task_type_a = ? OR task_type_b = ?';
      params.push(taskType, taskType);
    }
    sql += ' ORDER BY transfer_score DESC';

    const rows = await dbAll(db, sql, params);
    return rows;
  } finally {
    await closeDb(db);
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  getTaskEmbedding,
  findSimilarTasks,
  transferPriors,
  recomputeAffinityMatrix,
  getAffinityMatrix,
  // Helpers exposed for testing
  cosineSimilarity,
  pearsonCorrelation,
  KNOWN_MODELS
};

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  (async () => {
    try {
      switch (command) {
        case 'embed': {
          const taskType = args[1] || 'code_review';
          const emb = await getTaskEmbedding(taskType);
          console.log(JSON.stringify(emb, null, 2));
          break;
        }
        case 'similar': {
          const taskType = args[1] || 'code_review';
          const k = parseInt(args[2]) || 3;
          const similar = await findSimilarTasks(taskType, k);
          console.log(JSON.stringify(similar, null, 2));
          break;
        }
        case 'recompute': {
          const result = await recomputeAffinityMatrix();
          console.log(JSON.stringify(result, null, 2));
          break;
        }
        case 'affinity': {
          const taskType = args[1] || null;
          const matrix = await getAffinityMatrix(taskType);
          console.log(JSON.stringify(matrix, null, 2));
          break;
        }
        default:
          console.log(`
Task Embedder CLI

Usage:
  task-embedder.js embed <task_type>
    Get feature vector embedding for a task type

  task-embedder.js similar <task_type> [k]
    Find k most similar task types

  task-embedder.js recompute
    Recompute full affinity matrix

  task-embedder.js affinity [task_type]
    Get affinity matrix (optionally filtered by task type)
          `);
      }
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  })();
}
