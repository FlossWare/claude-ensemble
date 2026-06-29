/**
 * Disagreement Detection for Multi-AI Consensus
 *
 * Detects high-variance voting patterns and flags for human review.
 * Integrates with weighted voting system to prevent blindly picking
 * winners when models fundamentally disagree.
 *
 * Key Concept:
 *   When 3 models say "A" (60% confidence) and 3 models say "B" (55% confidence),
 *   weighted voting picks one, but disagreement is HIGH and should be flagged.
 *
 * Disagreement Metric: Coefficient of Variation (CV)
 *   CV = std_dev(confidences) / mean(confidences)
 *   - CV < 0.10: Low disagreement (10% variation)
 *   - CV 0.10-0.20: Moderate disagreement
 *   - CV 0.20-0.40: High disagreement → FLAG FOR REVIEW
 *   - CV > 0.40: Critical disagreement → URGENT REVIEW
 *
 * Created: 2026-06-28
 */

const { Pool } = require('pg');

// PostgreSQL connection (reuse environment variables)
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('[disagreement-detector] PostgreSQL pool error:', err.message);
});

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Disagreement thresholds (coefficient of variation)
 */
const DISAGREEMENT_THRESHOLDS = {
  LOW: 0.10,       // 10% variation or less
  MODERATE: 0.20,  // 10-20% variation
  HIGH: 0.40,      // 20-40% variation → flag for human review
  CRITICAL: 0.40,  // >40% variation → urgent human review
};

/**
 * Default threshold to trigger human review queue
 * Override via options.review_threshold
 */
const DEFAULT_REVIEW_THRESHOLD = DISAGREEMENT_THRESHOLDS.MODERATE; // 0.20

/**
 * Task-specific thresholds for human review
 *
 * Different tasks have different tolerance for disagreement:
 * - High-stakes tasks (security, architecture): Stricter thresholds (lower CV triggers review)
 * - Research/routing tasks: More lenient thresholds (higher CV acceptable)
 *
 * Usage: Pass task_type in options to analyzeDisagreement()
 */
const TASK_THRESHOLDS = {
  'security_audit': 0.15,      // Stricter (high stakes, need agreement)
  'code_review': 0.20,         // Moderate strictness
  'bug_detection': 0.20,       // Moderate strictness
  'architecture_review': 0.18, // Strict (major decisions)
  'research': 0.30,            // More lenient (exploration acceptable)
  'fact_checking': 0.25,       // Moderate lenient
  'consensus': 0.22,           // Slightly lenient
  'routing': 0.40,             // Most lenient (quick decisions, low cost)
  'general': 0.20,             // Default (same as MODERATE)
};

/**
 * Get task-specific review threshold
 *
 * @param {string} taskType - Task type key (from TASK_THRESHOLDS)
 * @returns {number} CV threshold for this task type
 */
function getReviewThreshold(taskType) {
  return TASK_THRESHOLDS[taskType] || TASK_THRESHOLDS.general;
}

// ============================================================================
// STATISTICS HELPERS
// ============================================================================

/**
 * Convert string to int32 for PostgreSQL advisory lock
 *
 * Uses Java-style hashCode algorithm for consistency
 * Returns absolute value to ensure positive lock ID
 *
 * @param {string} str - String to hash
 * @returns {number} 32-bit integer hash
 */
function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}

/**
 * Calculate mean of an array of numbers
 */
function mean(values) {
  if (values.length === 0) return 0;
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

/**
 * Calculate standard deviation of an array of numbers
 */
function stdDev(values) {
  if (values.length === 0) return 0;
  const avg = mean(values);
  const variance = values.reduce((sum, v) => sum + Math.pow(v - avg, 2), 0) / values.length;
  return Math.sqrt(variance);
}

/**
 * Calculate median of an array of numbers
 */
function median(values) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

/**
 * Calculate coefficient of variation (CV)
 * CV = std_dev / mean
 * Robust to scale (unitless measure of relative variability)
 *
 * PRIORITY 1 FIX: Guard against NaN, Infinity, division by zero
 */
function coefficientOfVariation(values) {
  const avg = mean(values);
  const sd = stdDev(values);

  // Guard against NaN, Infinity, division by zero
  if (!isFinite(avg) || !isFinite(sd) || avg === 0) {
    return 0;
  }

  return sd / avg;
}

// ============================================================================
// DISAGREEMENT DETECTION
// ============================================================================

/**
 * Analyze disagreement in a set of votes
 *
 * @param {Array<Object>} votes - Array of vote objects
 * @param {string} votes[].model - Model name
 * @param {*} votes[].answer - Model's answer
 * @param {number} votes[].confidence - Confidence score (0-100 or 0.0-1.0)
 * @param {Object} options - Detection options
 * @param {number} options.review_threshold - CV threshold to trigger review (default: 0.20, or task-specific)
 * @param {string} options.task_type - Task type for task-specific thresholds (e.g., 'security_audit', 'research')
 * @returns {Object} Disagreement analysis
 */
function analyzeDisagreement(votes, options = {}) {
  // PRIORITY 3: Task-specific thresholds
  const taskType = options.task_type || 'general';
  const reviewThreshold = options.review_threshold || getReviewThreshold(taskType);

  if (!votes || votes.length === 0) {
    return {
      status: 'error',
      error: 'empty_votes',
      message: 'No votes to analyze',
    };
  }

  // PRIORITY 2: Filter out invalid confidence scores before processing
  const validVotes = votes.filter(v => {
    const conf = v.confidence;
    return conf !== null && conf !== undefined &&
           !isNaN(conf) && isFinite(conf);
  });

  if (validVotes.length === 0) {
    return {
      status: 'error',
      error: 'all_invalid_confidence',
      message: 'All votes have invalid confidence scores',
      original_vote_count: votes.length,
    };
  }

  // Warn if we filtered out some votes
  if (validVotes.length < votes.length) {
    console.warn(`[disagreement-detector] Filtered out ${votes.length - validVotes.length} votes with invalid confidence scores`);
  }

  // Normalize confidence scores to 0-100 range
  const normalizeConfidence = (conf) => {
    if (conf === null || conf === undefined || isNaN(conf)) return 50;
    const c = parseFloat(conf);
    if (c >= 0 && c <= 1.0) return c * 100; // Convert 0-1 to 0-100
    if (c >= 0 && c <= 100) return c;
    return 50; // Fallback
  };

  // Use validVotes for the rest of the analysis
  const confidences = validVotes.map(v => normalizeConfidence(v.confidence));

  // Calculate statistics
  const stats = {
    mean: mean(confidences),
    median: median(confidences),
    std_dev: stdDev(confidences),
    min: Math.min(...confidences),
    max: Math.max(...confidences),
    range: Math.max(...confidences) - Math.min(...confidences),
  };

  // Coefficient of variation (key disagreement metric)
  const cv = coefficientOfVariation(confidences);

  // Determine disagreement level
  let disagreementLevel;
  if (cv < DISAGREEMENT_THRESHOLDS.LOW) {
    disagreementLevel = 'low';
  } else if (cv < DISAGREEMENT_THRESHOLDS.MODERATE) {
    disagreementLevel = 'moderate';
  } else if (cv < DISAGREEMENT_THRESHOLDS.HIGH) {
    disagreementLevel = 'high';
  } else {
    disagreementLevel = 'critical';
  }

  // Count unique answers (use validVotes, not original votes)
  const uniqueAnswers = new Set(validVotes.map(v => JSON.stringify(v.answer))).size;

  // Flag for human review if CV exceeds threshold
  const needsHumanReview = cv >= reviewThreshold;

  // Calculate priority (1-10 scale)
  // Higher disagreement = higher priority
  let priority = 5; // Default
  if (cv >= 0.50) priority = 10; // Critical
  else if (cv >= 0.40) priority = 9;
  else if (cv >= 0.30) priority = 8;
  else if (cv >= 0.25) priority = 7;
  else if (cv >= 0.20) priority = 6;
  else if (cv >= 0.15) priority = 5;
  else if (cv >= 0.10) priority = 4;
  else priority = 3;

  return {
    status: 'success',

    // Disagreement metrics
    disagreement_score: cv,
    disagreement_level: disagreementLevel,
    needs_human_review: needsHumanReview,
    priority: priority,

    // Vote statistics
    num_votes: validVotes.length,
    original_vote_count: votes.length,
    filtered_invalid_votes: votes.length - validVotes.length,
    unique_answers: uniqueAnswers,
    confidence_stats: stats,

    // Recommendation
    recommendation: needsHumanReview
      ? `HIGH DISAGREEMENT (CV=${cv.toFixed(3)}): Flag for human review`
      : `Low disagreement (CV=${cv.toFixed(3)}): Proceed with weighted voting`,

    // Threshold used
    review_threshold: reviewThreshold,
    task_type: taskType,
  };
}

// ============================================================================
// HUMAN REVIEW QUEUE INTEGRATION
// ============================================================================

/**
 * Store disagreement analysis in human review queue
 *
 * Only stores if needs_human_review is true.
 *
 * CRITICAL FIX (2026-06-28): Added advisory lock to prevent race condition
 * when multiple workers analyze same workflow concurrently. Lock is acquired
 * before INSERT and automatically released on COMMIT/ROLLBACK.
 *
 * @param {Object} analysis - Result from analyzeDisagreement()
 * @param {Object} context - Task context
 * @param {string} context.workflow_execution_id - Workflow execution ID
 * @param {string} context.workflow_name - Workflow name
 * @param {string} context.task_description - Task description
 * @param {Array<Object>} context.votes - Original votes
 * @param {Object} context.weighted_winner - Winner from weighted voting
 * @param {number} context.winner_confidence - Winner's total confidence
 * @param {Object} context.runner_up - Runner-up from weighted voting
 * @returns {Promise<Object>} Queue entry result
 */
async function storeInReviewQueue(analysis, context) {
  if (!analysis.needs_human_review) {
    return {
      status: 'skipped',
      message: 'Disagreement below review threshold, not queued',
      disagreement_score: analysis.disagreement_score,
    };
  }

  const {
    workflow_execution_id,
    workflow_name,
    task_description,
    votes,
    weighted_winner,
    winner_confidence,
    runner_up,
  } = context;

  if (!workflow_execution_id || !task_description) {
    return {
      status: 'error',
      error: 'missing_context',
      message: 'workflow_execution_id and task_description are required',
    };
  }

  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    // CRITICAL FIX: Acquire advisory lock using workflow_execution_id hash
    // This prevents race condition when multiple workers analyze same workflow
    // Lock is automatically released on COMMIT or ROLLBACK
    const lockId = hashCode(workflow_execution_id);
    await client.query('SELECT pg_advisory_xact_lock($1)', [lockId]);

    // Now safe to INSERT ON CONFLICT
    const result = await client.query(`
      INSERT INTO workflow.human_review_queue
        (workflow_execution_id, workflow_name, task_description,
         votes_json, disagreement_score, disagreement_level,
         num_votes, unique_answers, confidence_range,
         status, priority, weighted_winner, winner_confidence, runner_up,
         metadata, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW())
      ON CONFLICT (workflow_execution_id, task_description)
      DO UPDATE SET
        disagreement_score = GREATEST(human_review_queue.disagreement_score, EXCLUDED.disagreement_score),
        disagreement_level = EXCLUDED.disagreement_level,
        priority = GREATEST(human_review_queue.priority, EXCLUDED.priority),
        updated_at = NOW()
      RETURNING id
    `, [
      workflow_execution_id,
      workflow_name || null,
      task_description,
      JSON.stringify(votes),
      analysis.disagreement_score,
      analysis.disagreement_level,
      analysis.num_votes,
      analysis.unique_answers,
      JSON.stringify(analysis.confidence_stats),
      'pending',
      analysis.priority,
      JSON.stringify(weighted_winner),
      winner_confidence,
      JSON.stringify(runner_up),
      JSON.stringify({ review_threshold: analysis.review_threshold }),
    ]);

    await client.query('COMMIT');

    const queueId = result.rows[0].id;

    console.log(`[disagreement-detector] Queued for human review (ID: ${queueId}, CV: ${analysis.disagreement_score.toFixed(3)}, priority: ${analysis.priority})`);

    return {
      status: 'queued',
      queue_id: queueId,
      disagreement_score: analysis.disagreement_score,
      disagreement_level: analysis.disagreement_level,
      priority: analysis.priority,
      message: `Flagged for human review (disagreement CV: ${analysis.disagreement_score.toFixed(3)})`,
    };

  } catch (err) {
    await client.query('ROLLBACK');
    console.error('[disagreement-detector] Failed to store in review queue:', err.message);
    return {
      status: 'error',
      error: 'database_error',
      message: err.message,
    };
  } finally {
    client.release();
  }
}

/**
 * Fetch pending human reviews
 *
 * @param {Object} options - Query options
 * @param {number} options.limit - Max results (default: 10)
 * @param {string} options.order_by - Order by field (disagreement_score, priority, created_at)
 * @param {string} options.status - Filter by status (default: 'pending')
 * @returns {Promise<Array<Object>>} Pending reviews
 */
async function fetchPendingReviews(options = {}) {
  const limit = options.limit || 10;
  const orderBy = options.order_by || 'disagreement_score';
  const status = options.status || 'pending';

  const validOrderFields = ['disagreement_score', 'priority', 'created_at'];
  const orderField = validOrderFields.includes(orderBy) ? orderBy : 'disagreement_score';

  // Build safe ORDER BY clause (no string interpolation)
  let orderByClause;
  switch (orderField) {
    case 'disagreement_score':
      orderByClause = 'disagreement_score DESC, created_at ASC';
      break;
    case 'priority':
      orderByClause = 'priority DESC, created_at ASC';
      break;
    case 'created_at':
    default:
      orderByClause = 'created_at ASC';
      break;
  }

  try {
    const client = await pool.connect();

    try {
      const result = await client.query(`
        SELECT
          id, workflow_execution_id, workflow_name, task_description,
          votes_json, disagreement_score, disagreement_level,
          num_votes, unique_answers, confidence_range,
          status, priority, weighted_winner, winner_confidence, runner_up,
          created_at, updated_at
        FROM workflow.human_review_queue
        WHERE status = $1
        ORDER BY ${orderByClause}
        LIMIT $2
      `, [status, limit]);

      return result.rows.map(row => ({
        ...row,
        votes_json: row.votes_json,  // Already parsed by node-postgres
        confidence_range: row.confidence_range,
        weighted_winner: row.weighted_winner,
        runner_up: row.runner_up,
      }));

    } finally {
      client.release();
    }

  } catch (err) {
    console.error('[disagreement-detector] Failed to fetch pending reviews:', err.message);
    return [];
  }
}

/**
 * Update review status with human verdict
 *
 * @param {number} queueId - Review queue entry ID
 * @param {Object} verdict - Human verdict
 * @param {*} verdict.answer - Human's selected answer
 * @param {number} verdict.confidence - Human's confidence (0-100)
 * @param {string} verdict.reviewer - Reviewer identifier (email, username, etc.)
 * @param {string} verdict.notes - Optional resolution notes
 * @returns {Promise<Object>} Update result
 */
async function updateReviewWithVerdict(queueId, verdict) {
  const { answer, confidence, reviewer, notes } = verdict;

  if (!answer || confidence === null || confidence === undefined || !reviewer) {
    return {
      status: 'error',
      error: 'invalid_verdict',
      message: 'Verdict must include: answer, confidence, reviewer',
    };
  }

  try {
    const client = await pool.connect();

    try {
      const result = await client.query(`
        UPDATE workflow.human_review_queue
        SET
          status = 'reviewed',
          human_verdict = $1,
          human_reviewer = $2,
          reviewed_at = NOW(),
          resolution_notes = $3,
          updated_at = NOW()
        WHERE id = $4
        RETURNING id, workflow_execution_id, disagreement_score
      `, [
        JSON.stringify({ answer, confidence }),
        reviewer,
        notes || null,
        queueId,
      ]);

      if (result.rows.length === 0) {
        return {
          status: 'error',
          error: 'not_found',
          message: `Review queue entry ${queueId} not found`,
        };
      }

      const updated = result.rows[0];

      console.log(`[disagreement-detector] Review ${queueId} marked as reviewed by ${reviewer}`);

      return {
        status: 'success',
        queue_id: updated.id,
        workflow_execution_id: updated.workflow_execution_id,
        message: 'Review updated with human verdict',
      };

    } finally {
      client.release();
    }

  } catch (err) {
    console.error('[disagreement-detector] Failed to update review:', err.message);
    return {
      status: 'error',
      error: 'database_error',
      message: err.message,
    };
  }
}

// ============================================================================
// HUMAN FEEDBACK LOOP CLOSURE
// ============================================================================

/**
 * Close the human feedback loop after review
 *
 * Updates Thompson Sampling bandit state and confidence calibration
 * based on human verdict compared to weighted voting winner.
 *
 * Process:
 * 1. Fetch review entry and votes
 * 2. Compare human verdict to each model's vote
 * 3. Update strategy_performance (Thompson Sampling alpha/beta)
 * 4. Calculate confidence calibration error
 * 5. Store learning feedback
 * 6. Track human agreement rate per model
 *
 * @param {number} reviewId - Review queue entry ID
 * @returns {Promise<Object>} Feedback loop closure result
 */
async function closeHumanFeedbackLoop(reviewId) {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    // 1. Fetch review entry
    const reviewResult = await client.query(`
      SELECT
        id, workflow_execution_id, votes_json,
        weighted_winner, winner_confidence,
        human_verdict, human_reviewer, reviewed_at
      FROM workflow.human_review_queue
      WHERE id = $1 AND status = 'reviewed'
    `, [reviewId]);

    if (reviewResult.rows.length === 0) {
      await client.query('ROLLBACK');
      return {
        status: 'error',
        error: 'not_found_or_not_reviewed',
        message: `Review ${reviewId} not found or not yet reviewed`,
      };
    }

    const review = reviewResult.rows[0];
    const votes = review.votes_json;
    const humanVerdict = review.human_verdict;
    const weightedWinner = review.weighted_winner;

    if (!humanVerdict || !humanVerdict.answer) {
      await client.query('ROLLBACK');
      return {
        status: 'error',
        error: 'missing_human_verdict',
        message: 'Human verdict not found in review entry',
      };
    }

    // 2. Determine if weighted voting was correct
    const humanAnswer = JSON.stringify(humanVerdict.answer);
    const weightedAnswer = JSON.stringify(weightedWinner?.answer || weightedWinner);
    const weightedWasCorrect = humanAnswer === weightedAnswer;

    // 3. Calculate confidence calibration error
    // If weighted voting predicted 90% confidence but was wrong, error is high
    const weightedConfidence = parseFloat(review.winner_confidence) || 0.5;
    const humanConfidence = parseFloat(humanVerdict.confidence) || 0.5;

    // Calibration error: How wrong was the weighted confidence?
    // If correct: error = |weighted_conf - 1.0|
    // If incorrect: error = weighted_conf (should have been low)
    const calibrationError = weightedWasCorrect
      ? Math.abs(weightedConfidence - 1.0)
      : weightedConfidence;

    // 4. Update Thompson Sampling for each model's vote
    const strategyUpdates = [];

    for (const vote of votes) {
      const model = vote.model;
      const modelAnswer = JSON.stringify(vote.answer);
      const modelWasCorrect = modelAnswer === humanAnswer;

      // Determine strategy (use model name as strategy if not explicitly set)
      const strategy = vote.strategy || model;

      // Thompson Sampling update: alpha (successes), beta (failures)
      const reward = modelWasCorrect ? 1.0 : 0.0;

      // Update or insert strategy performance
      const updateResult = await client.query(`
        INSERT INTO workflow.strategy_performance
          (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (strategy) DO UPDATE SET
          successes = strategy_performance.successes + $2,
          failures = strategy_performance.failures + $3,
          alpha = strategy_performance.alpha + $4,
          beta = strategy_performance.beta + $5,
          total_reward = strategy_performance.total_reward + $6,
          avg_reward = (strategy_performance.total_reward + $6) /
                       NULLIF((strategy_performance.successes + strategy_performance.failures + 1), 0),
          last_updated = NOW()
        RETURNING strategy, successes, failures, alpha, beta, avg_reward
      `, [
        strategy,
        modelWasCorrect ? 1 : 0,  // successes
        modelWasCorrect ? 0 : 1,  // failures
        modelWasCorrect ? 1 : 0,  // alpha increment
        modelWasCorrect ? 0 : 1,  // beta increment
        reward,                    // total_reward increment
        reward,                    // avg_reward (will be recalculated in query)
      ]);

      strategyUpdates.push({
        strategy,
        model,
        was_correct: modelWasCorrect,
        reward,
        updated: updateResult.rows[0],
      });
    }

    // 5. Store feedback learning entry
    await client.query(`
      INSERT INTO workflow.human_feedback_learning
        (review_queue_id, weighted_winner, weighted_confidence,
         human_winner, human_confidence, weighted_was_correct,
         confidence_calibration_error, strategy_updates)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, [
      reviewId,
      JSON.stringify(weightedWinner),
      weightedConfidence,
      humanAnswer,
      humanConfidence,
      weightedWasCorrect,
      calibrationError,
      JSON.stringify(strategyUpdates),
    ]);

    // 6. Mark review as resolved
    await client.query(`
      UPDATE workflow.human_review_queue
      SET status = 'resolved', updated_at = NOW()
      WHERE id = $1
    `, [reviewId]);

    await client.query('COMMIT');

    console.log(`[disagreement-detector] Closed feedback loop for review ${reviewId}: weighted_correct=${weightedWasCorrect}, calibration_error=${calibrationError.toFixed(3)}, ${strategyUpdates.length} strategies updated`);

    return {
      status: 'success',
      review_id: reviewId,
      weighted_was_correct: weightedWasCorrect,
      calibration_error: calibrationError,
      strategy_updates: strategyUpdates,
      human_verdict: humanVerdict,
      message: `Feedback loop closed: ${strategyUpdates.length} strategies updated`,
    };

  } catch (err) {
    await client.query('ROLLBACK');
    console.error('[disagreement-detector] Failed to close feedback loop:', err.message);
    return {
      status: 'error',
      error: 'database_error',
      message: err.message,
    };
  } finally {
    client.release();
  }
}

/**
 * Get human agreement rate per model
 *
 * Returns statistics on how often each model agrees with human reviewers.
 *
 * @param {Object} options - Query options
 * @param {number} options.limit - Max models to return (default: 20)
 * @param {string} options.min_reviews - Minimum reviews required (default: 3)
 * @returns {Promise<Array<Object>>} Model agreement statistics
 */
async function getHumanAgreementRates(options = {}) {
  const limit = options.limit || 20;
  const minReviews = options.min_reviews || 3;

  try {
    const client = await pool.connect();

    try {
      // Parse strategy_updates JSONB to extract per-model statistics
      const result = await client.query(`
        WITH model_stats AS (
          SELECT
            update_item->>'model' AS model,
            update_item->>'strategy' AS strategy,
            (update_item->>'was_correct')::boolean AS was_correct,
            hfl.created_at
          FROM workflow.human_feedback_learning hfl,
               jsonb_array_elements(hfl.strategy_updates) AS update_item
          WHERE update_item->>'model' IS NOT NULL
        )
        SELECT
          model,
          COUNT(*) AS total_reviews,
          SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) AS correct_count,
          AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) AS agreement_rate,
          MAX(created_at) AS last_review
        FROM model_stats
        GROUP BY model
        HAVING COUNT(*) >= $1
        ORDER BY agreement_rate DESC, total_reviews DESC
        LIMIT $2
      `, [minReviews, limit]);

      return result.rows.map(row => ({
        model: row.model,
        total_reviews: parseInt(row.total_reviews),
        correct_count: parseInt(row.correct_count),
        agreement_rate: parseFloat(row.agreement_rate),
        last_review: row.last_review,
      }));

    } finally {
      client.release();
    }

  } catch (err) {
    console.error('[disagreement-detector] Failed to get human agreement rates:', err.message);
    return [];
  }
}

/**
 * Get confidence calibration metrics per model
 *
 * Returns how well each model's confidence scores match human confidence.
 * Lower error = better calibrated.
 *
 * @param {Object} options - Query options
 * @param {number} options.limit - Max models to return (default: 20)
 * @param {number} options.min_reviews - Minimum reviews required (default: 3)
 * @returns {Promise<Array<Object>>} Calibration metrics
 */
async function getCalibrationMetrics(options = {}) {
  const limit = options.limit || 20;
  const minReviews = options.min_reviews || 3;

  try {
    const client = await pool.connect();

    try {
      const result = await client.query(`
        SELECT
          COUNT(*) AS total_reviews,
          AVG(confidence_calibration_error) AS avg_calibration_error,
          STDDEV(confidence_calibration_error) AS calibration_std_dev,
          SUM(CASE WHEN weighted_was_correct THEN 1 ELSE 0 END) AS correct_predictions,
          AVG(CASE WHEN weighted_was_correct THEN weighted_confidence ELSE NULL END) AS avg_conf_when_correct,
          AVG(CASE WHEN NOT weighted_was_correct THEN weighted_confidence ELSE NULL END) AS avg_conf_when_wrong
        FROM workflow.human_feedback_learning
        WHERE confidence_calibration_error IS NOT NULL
        HAVING COUNT(*) >= $1
      `, [minReviews]);

      if (result.rows.length === 0) {
        return null;
      }

      const row = result.rows[0];
      return {
        total_reviews: parseInt(row.total_reviews),
        avg_calibration_error: parseFloat(row.avg_calibration_error) || 0,
        calibration_std_dev: parseFloat(row.calibration_std_dev) || 0,
        correct_predictions: parseInt(row.correct_predictions),
        accuracy: row.total_reviews > 0
          ? parseInt(row.correct_predictions) / parseInt(row.total_reviews)
          : 0,
        avg_confidence_when_correct: parseFloat(row.avg_conf_when_correct) || 0,
        avg_confidence_when_wrong: parseFloat(row.avg_conf_when_wrong) || 0,
      };

    } finally {
      client.release();
    }

  } catch (err) {
    console.error('[disagreement-detector] Failed to get calibration metrics:', err.message);
    return null;
  }
}

// ============================================================================
// INTEGRATION HELPER
// ============================================================================

/**
 * Main integration point for weighted voting
 *
 * Call this BEFORE arbiter synthesis to detect and flag disagreements.
 *
 * @param {Array<Object>} votes - Worker votes
 * @param {Object} votingResult - Result from weighted voting
 * @param {Object} context - Task context (workflow_execution_id, task_description, etc.)
 * @param {Object} options - Detection options
 * @returns {Promise<Object>} Combined result
 */
async function detectAndQueue(votes, votingResult, context, options = {}) {
  const sendWebhooks = options.sendWebhooks !== false;

  // Analyze disagreement
  const analysis = analyzeDisagreement(votes, options);

  if (analysis.status === 'error') {
    console.warn('[disagreement-detector] Analysis failed:', analysis.message);
    return {
      analysis,
      queue_result: null,
      warning: analysis.message,
    };
  }

  // Store in queue if needed
  const queueContext = {
    ...context,
    votes: votes,
    weighted_winner: votingResult?.winner?.answer || null,
    winner_confidence: votingResult?.winner?.total_weight || null,
    runner_up: votingResult?.runner_up?.answer || null,
  };

  const queueResult = await storeInReviewQueue(analysis, queueContext);

  // Send webhook notification (if enabled and queued)
  if (sendWebhooks && queueResult.status === 'queued') {
    await sendDisagreementNotification(analysis, queueContext, queueResult);
  }

  return {
    analysis,
    queue_result: queueResult,
    needs_human_review: analysis.needs_human_review,
    disagreement_score: analysis.disagreement_score,
    disagreement_level: analysis.disagreement_level,
  };
}

/**
 * Send webhook notification for high disagreement
 *
 * @param {Object} analysis - Disagreement analysis result
 * @param {Object} context - Task context
 * @param {Object} queueResult - Queue storage result
 * @returns {Promise<void>}
 */
async function sendDisagreementNotification(analysis, context, queueResult) {
  try {
    const { notifyDisagreement } = require('../monitoring/webhook-notifier.cjs');

    const notificationData = {
      workflow_name: context.workflow_name || 'unknown',
      task_description: context.task_description || 'N/A',
      disagreement_score: analysis.disagreement_score,
      disagreement_level: analysis.disagreement_level,
      votes: context.votes || [],
      queue_id: queueResult.queue_id,
      priority: analysis.priority,
    };

    await notifyDisagreement(notificationData);
  } catch (err) {
    console.error('[disagreement-detector] Failed to send webhook notification:', err.message);
    // Non-blocking - continue even if webhook fails
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  analyzeDisagreement,
  detectAndQueue,
  storeInReviewQueue,
  fetchPendingReviews,
  updateReviewWithVerdict,

  // Human feedback loop closure
  closeHumanFeedbackLoop,
  getHumanAgreementRates,
  getCalibrationMetrics,

  // Statistics helpers (for testing)
  mean,
  stdDev,
  median,
  coefficientOfVariation,
  hashCode,

  // Configuration
  DISAGREEMENT_THRESHOLDS,
  DEFAULT_REVIEW_THRESHOLD,
  TASK_THRESHOLDS,
  getReviewThreshold,

  // Pool (for cleanup)
  pool,
};
