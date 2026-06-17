#!/usr/bin/env node
/**
 * Quality Tracker Module
 *
 * Implements post-execution quality measurement and tracking.
 *
 * Features:
 *   1. Automated quality scoring based on multiple metrics
 *   2. Optional user feedback collection
 *   3. Storage in quality_ratings table
 *   4. LIS (Learning Impact Score) updates
 *   5. Quality trend analysis
 *   6. Performance correlation tracking
 *
 * Usage:
 *   const tracker = require('./track-quality');
 *   await tracker.recordQuality(executionId, automatedScores, userRating);
 *   const trends = await tracker.getQualityTrends(workflow, taskType);
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// Database path
const DB_PATH = path.join(os.homedir(), '.claude', 'learning', 'db', 'learning.db');

/**
 * Initialize database connection with optimizations
 */
function getDb() {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) reject(err);
      else {
        // Apply pragmas for concurrent access
        db.run('PRAGMA journal_mode = WAL', (err) => {
          if (err) reject(err);
          else {
            db.run('PRAGMA synchronous = NORMAL', (err) => {
              if (err) reject(err);
              else {
                db.run('PRAGMA busy_timeout = 5000', (err) => {
                  if (err) reject(err);
                  else resolve(db);
                });
              }
            });
          }
        });
      }
    });
  });
}

/**
 * Run database query
 */
function dbRun(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function(err) {
      if (err) reject(err);
      else resolve({ lastID: this.lastID, changes: this.changes });
    });
  });
}

/**
 * Get a single row from database
 */
function dbGet(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => {
      if (err) reject(err);
      else resolve(row);
    });
  });
}

/**
 * Get all rows from database
 */
function dbAll(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows || []);
    });
  });
}

/**
 * Calculate automated quality score based on multiple metrics
 *
 * @param {object} executionData - Data from execution_log
 * @param {object} outcomes - Outcomes and metrics
 * @returns {object} Quality scores breakdown
 */
function calculateAutomatedQuality(executionData, outcomes = {}) {
  const scores = {
    accuracy: 1.0,      // 0-1: correctness
    completeness: 1.0,  // 0-1: coverage
    clarity: 1.0,       // 0-1: readability
    actionability: 1.0, // 0-1: usability
    relevance: 1.0,     // 0-1: relevance
    efficiency: 1.0,    // 0-1: cost-quality ratio
    consistency: 1.0    // 0-1: alignment with expectations
  };

  // Accuracy: based on outcome success
  if (outcomes.outcome === 'success') {
    scores.accuracy = 0.95;
  } else if (outcomes.outcome === 'partial') {
    scores.accuracy = 0.60;
  } else if (outcomes.outcome === 'failed') {
    scores.accuracy = 0.10;
  }

  // Completeness: based on whether execution met requirements
  if (outcomes.completeness !== undefined) {
    scores.completeness = Math.max(0, Math.min(1, outcomes.completeness));
  }

  // Clarity: based on task type and output length
  if (outcomes.clarity !== undefined) {
    scores.clarity = Math.max(0, Math.min(1, outcomes.clarity));
  }

  // Actionability: based on presence of next steps or output usability
  if (outcomes.actionability !== undefined) {
    scores.actionability = Math.max(0, Math.min(1, outcomes.actionability));
  }

  // Relevance: based on output matching task requirements
  if (outcomes.relevance !== undefined) {
    scores.relevance = Math.max(0, Math.min(1, outcomes.relevance));
  }

  // Efficiency: cost-quality tradeoff
  // Quality matters more, but cost is a factor
  const qualityBase = executionData.quality_score || 0.5;
  const costFactor = executionData.total_cost_usd || 0.01;
  const durationFactor = (executionData.duration_ms || 1000) / 1000;

  // Lower cost and duration is better
  // Normalize to 0-1 range (assume max cost of $1, max duration of 1 hour)
  const costScore = Math.max(0, 1 - (costFactor / 1.0));
  const durationScore = Math.max(0, 1 - (durationFactor / 3600));

  // Efficiency = 70% quality, 20% cost, 10% speed
  scores.efficiency = (qualityBase * 0.7) + (costScore * 0.2) + (durationScore * 0.1);

  // Consistency: measure confidence and consensus alignment
  const confidence = executionData.confidence || 0.5;
  const consensus = executionData.consensus_score || 0.5;
  scores.consistency = (confidence * 0.6) + (consensus * 0.4);

  // Overall score: weighted average
  const weights = {
    accuracy: 0.25,
    completeness: 0.20,
    clarity: 0.15,
    actionability: 0.15,
    relevance: 0.10,
    efficiency: 0.10,
    consistency: 0.05
  };

  let overallScore = 0;
  for (const [key, weight] of Object.entries(weights)) {
    overallScore += scores[key] * weight;
  }

  scores.overall = Math.max(0, Math.min(1, overallScore));

  return scores;
}

/**
 * Record quality rating for an execution
 *
 * @param {string} executionId - UUID from execution_log
 * @param {string} ratingSource - 'user', 'automated', 'arbiter', 'consensus', 'ci_outcome'
 * @param {object} automatedScores - Scores from calculateAutomatedQuality
 * @param {object} userFeedback - User ratings and comments
 * @returns {object} Recorded rating details
 */
async function recordQuality(executionId, ratingSource = 'automated', automatedScores = {}, userFeedback = {}) {
  const db = await getDb();

  try {
    // Get execution details
    const execution = await dbGet(
      db,
      `SELECT id, workflow, task_type, quality_score, confidence,
              consensus_score, total_cost_usd, duration_ms, outcome
       FROM execution_log WHERE execution_id = ?`,
      [executionId]
    );

    if (!execution) {
      throw new Error(`Execution not found: ${executionId}`);
    }

    // Calculate automated scores if not provided
    let scores = automatedScores;
    if (!scores || Object.keys(scores).length === 0) {
      scores = calculateAutomatedQuality(execution, userFeedback);
    }

    // Prepare rating record
    const rating = {
      timestamp: new Date().toISOString(),
      execution_id: executionId,
      workflow: execution.workflow,
      task_type: execution.task_type,
      rating_source: ratingSource,
      rater_model: userFeedback.raterModel || null,
      overall_score: scores.overall || userFeedback.overall_score || 0.5,
      accuracy_score: scores.accuracy || userFeedback.accuracy_score,
      completeness_score: scores.completeness || userFeedback.completeness_score,
      clarity_score: scores.clarity || userFeedback.clarity_score,
      actionability_score: scores.actionability || userFeedback.actionability_score,
      relevance_score: scores.relevance || userFeedback.relevance_score,
      thumbs_up: userFeedback.thumbs_up,
      user_comment: userFeedback.comment,
      user_correction: userFeedback.correction,
      tests_passed: userFeedback.tests_passed,
      tests_total: userFeedback.tests_total,
      lint_errors: userFeedback.lint_errors,
      build_success: userFeedback.build_success,
      ci_pipeline_url: userFeedback.ci_pipeline_url,
      compared_to: userFeedback.compared_to,
      relative_score: userFeedback.relative_score,
      rating_context: JSON.stringify(userFeedback.context || {})
    };

    // Insert into quality_ratings table
    const result = await dbRun(
      db,
      `INSERT INTO quality_ratings (
        timestamp, execution_id, workflow, task_type, rating_source,
        rater_model, overall_score, accuracy_score, completeness_score,
        clarity_score, actionability_score, relevance_score,
        thumbs_up, user_comment, user_correction,
        tests_passed, tests_total, lint_errors, build_success, ci_pipeline_url,
        compared_to, relative_score, rating_context
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        rating.timestamp, rating.execution_id, rating.workflow, rating.task_type,
        rating.rating_source, rating.rater_model, rating.overall_score,
        rating.accuracy_score, rating.completeness_score, rating.clarity_score,
        rating.actionability_score, rating.relevance_score, rating.thumbs_up,
        rating.user_comment, rating.user_correction, rating.tests_passed,
        rating.tests_total, rating.lint_errors, rating.build_success,
        rating.ci_pipeline_url, rating.compared_to, rating.relative_score,
        rating.rating_context
      ]
    );

    // Update LIS (Learning Impact Score) for the execution
    await updateLIS(db, executionId, rating);

    // Phase 3: Active learning -- schedule Ebbinghaus replay if this rating
    // suggests a significant quality change
    try {
      const feedbackSelector = require('./feedback-selector');
      if (scores.overall && execution.workflow) {
        // Schedule replay for the model/task combo to verify quality persists
        await feedbackSelector.scheduleReplay(
          executionId,
          execution.task_type || 'general',
          execution.model || 'unknown',
          scores.overall,
          `quality_rating_${ratingSource}`
        );
      }
    } catch (_) {
      // feedback-selector not available; skip
    }

    // Phase 3d: If this is a CI outcome rating, check if it should trigger
    // human review for executions with high prediction error
    if (ratingSource === 'ci_outcome') {
      try {
        const feedbackSelector = require('./feedback-selector');
        const reviewCandidates = await feedbackSelector.selectForHumanReview(5);
        if (reviewCandidates.length > 0) {
          // Publish to message bus for human review
          let messageBus = null;
          try { messageBus = require('./shared/message-bus'); } catch (_) {}
          if (messageBus) {
            messageBus.postMessage('active-learning', {
              type: 'human_review_needed',
              candidates: reviewCandidates.slice(0, 3).map(c => ({
                executionId: c.executionId,
                model: c.model,
                taskType: c.taskType,
                predictionError: c.predictionError
              }))
            });
          }
        }
      } catch (_) {}
    }

    return {
      success: true,
      ratingId: result.lastID,
      executionId,
      scores,
      timestamp: rating.timestamp
    };

  } finally {
    db.close();
  }
}

/**
 * Update LIS (Learning Impact Score) based on quality rating
 *
 * LIS measures:
 *   - How well did this execution perform
 *   - How much did user feedback improve estimates
 *   - Impact on future model selection
 *
 * @param {object} db - Database connection
 * @param {string} executionId - Execution UUID
 * @param {object} rating - Quality rating record
 */
async function updateLIS(db, executionId, rating) {
  // Get all ratings for this execution
  const ratings = await dbAll(
    db,
    `SELECT overall_score, thumbs_up, tests_passed, tests_total
     FROM quality_ratings WHERE execution_id = ?`,
    [executionId]
  );

  if (!ratings || ratings.length === 0) return;

  // Calculate LIS components
  let lisScore = 0;

  // 1. Quality consensus: agreement between different rating sources
  if (ratings.length > 1) {
    const scores = ratings.map(r => r.overall_score);
    const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
    const stdDev = Math.sqrt(
      scores.reduce((sum, score) => sum + Math.pow(score - avgScore, 2), 0) / scores.length
    );
    // Lower stddev = higher consensus = higher LIS component
    const consensusLIS = 1 - Math.min(1, stdDev);
    lisScore += consensusLIS * 0.3;
  } else {
    lisScore += rating.overall_score * 0.3;
  }

  // 2. User feedback impact
  if (rating.thumbs_up !== null) {
    // User took time to provide feedback
    const userImpact = rating.thumbs_up ? 0.9 : 0.1;
    lisScore += userImpact * 0.25;
  }

  // 3. CI/automated outcome impact
  if (rating.tests_passed !== null && rating.tests_total !== null) {
    const testPassRate = rating.tests_passed / Math.max(1, rating.tests_total);
    lisScore += testPassRate * 0.25;
  }

  // 4. Correction/improvement impact
  if (rating.user_correction) {
    // User had to correct output - negative impact
    lisScore *= 0.8;
  }

  // 5. Test impact
  if (rating.lint_errors && rating.lint_errors > 0) {
    lisScore *= Math.max(0.5, 1 - (rating.lint_errors * 0.1));
  }

  // Normalize to 0-1 range
  lisScore = Math.max(0, Math.min(1, lisScore));

  // Update execution_log with LIS (stored in outcome_notes as JSON metadata)
  const existingNotes = await dbGet(
    db,
    `SELECT outcome_notes FROM execution_log WHERE execution_id = ?`,
    [executionId]
  );

  let metadata = {};
  if (existingNotes && existingNotes.outcome_notes) {
    try {
      metadata = JSON.parse(existingNotes.outcome_notes);
    } catch (e) {
      // If not valid JSON, start fresh
    }
  }

  metadata.lis_score = lisScore;
  metadata.lis_updated_at = new Date().toISOString();
  metadata.lis_components = {
    quality: rating.overall_score,
    consensus: ratings.length > 1 ? 0.3 : 0.0,
    user_feedback: rating.thumbs_up !== null ? 0.25 : 0.0,
    ci_outcome: rating.tests_passed !== null ? 0.25 : 0.0,
    correction_penalty: rating.user_correction ? 0.8 : 1.0
  };

  await dbRun(
    db,
    `UPDATE execution_log SET outcome_notes = ? WHERE execution_id = ?`,
    [JSON.stringify(metadata), executionId]
  );
}

/**
 * Get quality trends for a workflow/task type combination
 *
 * @param {string} workflow - Workflow name
 * @param {string} taskType - Task type
 * @param {number} limit - Number of recent ratings to include (default 50)
 * @returns {object} Trend analysis
 */
async function getQualityTrends(workflow, taskType, limit = 50) {
  const db = await getDb();

  try {
    // Get recent ratings
    const ratings = await dbAll(
      db,
      `SELECT timestamp, overall_score, accuracy_score, completeness_score,
              clarity_score, actionability_score, relevance_score,
              rating_source, thumbs_up
       FROM quality_ratings
       WHERE workflow = ? AND task_type = ?
       ORDER BY timestamp DESC
       LIMIT ?`,
      [workflow, taskType, limit]
    );

    if (!ratings || ratings.length === 0) {
      return {
        workflow,
        taskType,
        sampleCount: 0,
        trend: 'insufficient_data'
      };
    }

    // Reverse to get chronological order
    ratings.reverse();

    // Calculate trend statistics
    const scores = ratings.map(r => r.overall_score);
    const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);

    // Calculate trend direction (simple linear regression)
    const n = scores.length;
    const sumX = (n * (n + 1)) / 2;
    const sumY = scores.reduce((a, b) => a + b, 0);
    const sumXY = scores.reduce((sum, y, i) => sum + (i + 1) * y, 0);
    const sumX2 = (n * (n + 1) * (2 * n + 1)) / 6;

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const trend = slope > 0.01 ? 'improving' : slope < -0.01 ? 'declining' : 'stable';

    // Breakdown by rating source
    const bySource = {};
    for (const rating of ratings) {
      if (!bySource[rating.rating_source]) {
        bySource[rating.rating_source] = [];
      }
      bySource[rating.rating_source].push(rating.overall_score);
    }

    const sourceStats = {};
    for (const [source, sourceScores] of Object.entries(bySource)) {
      sourceStats[source] = {
        count: sourceScores.length,
        avg: sourceScores.reduce((a, b) => a + b, 0) / sourceScores.length,
        min: Math.min(...sourceScores),
        max: Math.max(...sourceScores)
      };
    }

    // User satisfaction (thumbs up/down ratio)
    const userRatings = ratings.filter(r => r.thumbs_up !== null);
    let userSatisfaction = 0;
    if (userRatings.length > 0) {
      const thumbsUp = userRatings.filter(r => r.thumbs_up === 1).length;
      userSatisfaction = thumbsUp / userRatings.length;
    }

    return {
      workflow,
      taskType,
      sampleCount: ratings.length,
      averageScore: avgScore,
      minScore,
      maxScore,
      trend,
      trendSlope: slope,
      bySource: sourceStats,
      userSatisfaction,
      scores: scores.slice(-20) // Last 20 for sparkline
    };

  } finally {
    db.close();
  }
}

/**
 * Get quality comparison across models for same task
 *
 * @param {string} workflow - Workflow name
 * @param {string} taskType - Task type
 * @returns {object} Model quality comparison
 */
async function compareModelQuality(workflow, taskType) {
  const db = await getDb();

  try {
    // Get execution and rating data
    const comparisons = await dbAll(
      db,
      `SELECT
        el.model,
        el.model_role,
        AVG(qr.overall_score) as avg_quality,
        AVG(qr.accuracy_score) as avg_accuracy,
        AVG(el.confidence) as avg_confidence,
        COUNT(*) as usage_count,
        SUM(CASE WHEN qr.thumbs_up = 1 THEN 1 ELSE 0 END) as thumbs_up_count,
        SUM(CASE WHEN el.outcome = 'success' THEN 1 ELSE 0 END) as success_count,
        AVG(el.total_cost_usd) as avg_cost
       FROM execution_log el
       LEFT JOIN quality_ratings qr ON el.execution_id = qr.execution_id
       WHERE el.workflow = ? AND el.task_type = ?
       GROUP BY el.model, el.model_role
       ORDER BY avg_quality DESC`,
      [workflow, taskType]
    );

    const result = {};
    for (const comp of comparisons) {
      const key = `${comp.model}(${comp.model_role})`;
      result[key] = {
        model: comp.model,
        role: comp.model_role,
        avgQuality: comp.avg_quality || 0,
        avgAccuracy: comp.avg_accuracy || 0,
        avgConfidence: comp.avg_confidence || 0,
        usageCount: comp.usage_count,
        userSatisfaction: comp.thumbs_up_count / Math.max(1, comp.usage_count),
        successRate: comp.success_count / comp.usage_count,
        avgCost: comp.avg_cost || 0
      };
    }

    return result;

  } finally {
    db.close();
  }
}

/**
 * Get LIS distribution and statistics
 *
 * @param {string} workflow - Optional: filter by workflow
 * @param {string} taskType - Optional: filter by task type
 * @returns {object} LIS statistics
 */
async function getLISStats(workflow = null, taskType = null) {
  const db = await getDb();

  try {
    let sql = `SELECT
      json_extract(outcome_notes, '$.lis_score') as lis_score,
      workflow,
      task_type,
      COUNT(*) as execution_count
     FROM execution_log
     WHERE outcome_notes IS NOT NULL`;

    const params = [];

    if (workflow) {
      sql += ' AND workflow = ?';
      params.push(workflow);
    }

    if (taskType) {
      sql += ' AND task_type = ?';
      params.push(taskType);
    }

    sql += ' GROUP BY workflow, task_type';

    const results = await dbAll(db, sql, params);

    // Calculate statistics
    const lisScores = results
      .filter(r => r.lis_score !== null)
      .map(r => parseFloat(r.lis_score));

    if (lisScores.length === 0) {
      return {
        sampleCount: 0,
        message: 'No LIS scores found'
      };
    }

    const avg = lisScores.reduce((a, b) => a + b, 0) / lisScores.length;
    const sorted = lisScores.sort((a, b) => a - b);
    const median = sorted.length % 2 === 0
      ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
      : sorted[Math.floor(sorted.length / 2)];

    const stdDev = Math.sqrt(
      lisScores.reduce((sum, score) => sum + Math.pow(score - avg, 2), 0) / lisScores.length
    );

    return {
      sampleCount: lisScores.length,
      averageLIS: avg,
      medianLIS: median,
      minLIS: Math.min(...lisScores),
      maxLIS: Math.max(...lisScores),
      stdDev,
      byWorkflowTask: results.map(r => ({
        workflow: r.workflow,
        taskType: r.task_type,
        executionCount: r.execution_count,
        avgLIS: r.lis_score
      }))
    };

  } finally {
    db.close();
  }
}

/**
 * Get active learning batch: which unrated executions would benefit most
 * from quality annotation. Delegates to feedback-selector.js.
 *
 * @param {number} poolSize - Number of recent unrated executions to consider
 * @param {number} batchSize - Number to select
 * @returns {object[]} Selected executions with annotation scores
 */
async function getActiveLearningBatch(poolSize = 100, batchSize = 20) {
  try {
    const feedbackSelector = require('./feedback-selector');
    return await feedbackSelector.selectBatch(poolSize, batchSize);
  } catch (e) {
    return { error: 'feedback-selector not available', message: e.message };
  }
}

/**
 * Export for use as module
 */
module.exports = {
  recordQuality,
  calculateAutomatedQuality,
  getQualityTrends,
  compareModelQuality,
  getLISStats,
  updateLIS,
  getActiveLearningBatch
};

/**
 * CLI interface for testing
 */
if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  (async () => {
    try {
      switch (command) {
        case 'record': {
          // Usage: track-quality.js record <execution-id> <rating-source> [json-scores]
          const executionId = args[1];
          const ratingSource = args[2] || 'automated';
          const scores = args[3] ? JSON.parse(args[3]) : {};

          const result = await recordQuality(executionId, ratingSource, scores);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'trends': {
          // Usage: track-quality.js trends <workflow> <task-type>
          const workflow = args[1];
          const taskType = args[2];

          const trends = await getQualityTrends(workflow, taskType);
          console.log(JSON.stringify(trends, null, 2));
          break;
        }

        case 'compare': {
          // Usage: track-quality.js compare <workflow> <task-type>
          const workflow = args[1];
          const taskType = args[2];

          const comparison = await compareModelQuality(workflow, taskType);
          console.log(JSON.stringify(comparison, null, 2));
          break;
        }

        case 'lis': {
          // Usage: track-quality.js lis [workflow] [task-type]
          const workflow = args[1] || null;
          const taskType = args[2] || null;

          const stats = await getLISStats(workflow, taskType);
          console.log(JSON.stringify(stats, null, 2));
          break;
        }

        default:
          console.log(`
Quality Tracker CLI

Usage:
  track-quality.js record <execution-id> [rating-source] [json-scores]
    Record quality rating for an execution

  track-quality.js trends <workflow> <task-type>
    Get quality trends for a workflow/task combination

  track-quality.js compare <workflow> <task-type>
    Compare model quality for same task

  track-quality.js lis [workflow] [task-type]
    Get LIS statistics (Learning Impact Score)
          `);
      }
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  })();
}
