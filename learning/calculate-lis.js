/**
 * Learning Intelligence Score (LIS) Calculator
 *
 * Standalone calculator that works with the unified v2 schema (init-db.sql).
 * Computes four primary metrics from execution_log, model_performance,
 * and parameter_tuning tables:
 *
 *   1. LIS (0-100): Weighted composite of quality, cost, speed, consistency
 *   2. Quality Trend: Statistical improvement detection via Welch's t-test
 *   3. Cost Efficiency: Cost per quality point with trend analysis
 *   4. Speed Improvement: Execution time reduction over time
 *
 * This module reads directly from the database via learning/db.js and writes
 * computed metrics back to model_performance for caching/dashboarding.
 *
 * Usage (ESM):
 *   import { computeLIS, computeAllMetrics, recomputeModelPerformance } from './learning/calculate-lis.js';
 *
 *   // Single model/task LIS
 *   const lis = computeLIS('opus', 'code_review');
 *
 *   // Full metrics for a model/task
 *   const metrics = computeAllMetrics('opus', 'code_review');
 *
 *   // Recompute and persist all model_performance rows
 *   recomputeModelPerformance();
 */

import {
  getDb,
  query,
  queryOne,
  upsertModelPerformance,
  getMetadata,
  setMetadata,
} from './db.js';

// ============================================================================
// LIS WEIGHTS
// ============================================================================

const WEIGHTS = {
  quality: 0.35,
  cost: 0.25,
  speed: 0.20,
  consistency: 0.20,
};

// ============================================================================
// PRIMARY METRIC: Learning Intelligence Score (LIS)
// ============================================================================

/**
 * Compute LIS for a specific model/task combination.
 *
 * LIS = 35*qualityScore + 25*costScore + 20*speedScore + 20*consistencyScore
 *
 * Each component is normalized to [0, 100] before weighting.
 *
 * @param {string} model - Model name (e.g. 'opus')
 * @param {string} taskType - Task type (e.g. 'code_review')
 * @param {Object} [options] - Options
 * @param {number} [options.minSamples=10] - Minimum samples required
 * @param {number} [options.trendWindowDays=30] - Days for trend analysis
 * @returns {Object|null} LIS result or null if insufficient data
 */
export function computeLIS(model, taskType, options = {}) {
  const { minSamples = 10, trendWindowDays = 30 } = options;

  const db = getDb();
  if (!db) return null;

  // Get stats for this model/task
  const stats = _getStats(model, taskType);
  if (!stats || stats.sample_count < minSamples) return null;

  // Get all model stats for percentile comparison
  const allStats = _getAllStats(minSamples);
  if (allStats.length === 0) return null;

  // Get recent data for trend analysis
  const recentQuality = _getRecentValues(model, taskType, 'quality_score', 50);
  const recentCost = _getRecentValues(model, taskType, 'cost_usd', 50);
  const recentDuration = _getRecentValues(model, taskType, 'duration_ms', 50);

  // Compute each component
  const qualityScore = _computeQualityScore(stats, allStats, recentQuality);
  const costScore = _computeCostScore(stats, allStats, recentCost);
  const speedScore = _computeSpeedScore(stats, allStats, recentDuration);
  const consistencyScore = _computeConsistencyScore(recentQuality, recentCost);

  const rawLIS =
    WEIGHTS.quality * qualityScore +
    WEIGHTS.cost * costScore +
    WEIGHTS.speed * speedScore +
    WEIGHTS.consistency * consistencyScore;

  const lis = Math.min(100, Math.max(0, rawLIS));

  return {
    score: Math.round(lis * 10) / 10,
    components: {
      quality: Math.round(qualityScore * 10) / 10,
      cost: Math.round(costScore * 10) / 10,
      speed: Math.round(speedScore * 10) / 10,
      consistency: Math.round(consistencyScore * 10) / 10,
    },
    weights: { ...WEIGHTS },
    model,
    taskType,
    sampleCount: stats.sample_count,
    timestamp: new Date().toISOString(),
  };
}

// ============================================================================
// SECONDARY METRIC: Quality Trend Analysis
// ============================================================================

/**
 * Detect statistical improvement/decline in quality via Welch's t-test.
 *
 * Splits recent quality scores into older vs recent halves and tests
 * whether the difference is statistically significant.
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type
 * @param {Object} [options] - Options
 * @param {number} [options.minSamples=5] - Minimum samples required
 * @param {number} [options.windowSize=10] - Recent window for trend slope
 * @returns {Object|null} Trend analysis result or null
 */
export function computeQualityTrend(model, taskType, options = {}) {
  const { minSamples = 5, windowSize = 10 } = options;

  const values = _getRecentValues(model, taskType, 'quality_score', 100);
  if (values.length < minSamples) return null;

  const midpoint = Math.floor(values.length / 2);
  const recentHalf = values.slice(0, midpoint);
  const olderHalf = values.slice(midpoint);

  const recentMean = _mean(recentHalf);
  const olderMean = _mean(olderHalf);

  if (olderMean === 0) return null;

  const improvement = ((recentMean - olderMean) / olderMean) * 100;

  // Welch's t-test
  const recentStdDev = _stdDev(recentHalf);
  const olderStdDev = _stdDev(olderHalf);
  const pooledStdError = Math.sqrt(
    (olderStdDev ** 2) / olderHalf.length +
    (recentStdDev ** 2) / recentHalf.length
  );

  let tScore = 0;
  let pValue = 1.0;
  if (pooledStdError > 0) {
    tScore = (recentMean - olderMean) / pooledStdError;
    const df = _welchDF(recentStdDev, recentHalf.length, olderStdDev, olderHalf.length);
    pValue = _tTestPValue(tScore, df);
  }

  let trend = 'stable';
  let confidence = 0;
  if (pValue < 0.05) {
    trend = improvement > 0 ? 'improving' : 'declining';
    confidence = 1 - pValue;
  }

  // Linear regression on recent window
  const recentWindow = values.slice(0, Math.min(windowSize, values.length));
  const regression = _linearRegression(recentWindow);

  return {
    trend,
    improvementPercent: Math.round(improvement * 100) / 100,
    pValue: Math.round(pValue * 10000) / 10000,
    tScore: Math.round(tScore * 100) / 100,
    confidence: Math.min(0.99, Math.round(confidence * 1000) / 1000),
    recentTrendSlope: regression.slope,
    recentTrendR2: regression.r2,
    recentMean: Math.round(recentMean * 1000) / 1000,
    olderMean: Math.round(olderMean * 1000) / 1000,
    recentStdDev: Math.round(recentStdDev * 1000) / 1000,
    samples: values.length,
    timestamp: new Date().toISOString(),
  };
}

// ============================================================================
// TERTIARY METRIC: Cost Efficiency
// ============================================================================

/**
 * Compute cost per quality point and track efficiency trends.
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type
 * @param {Object} [options] - Options
 * @param {number} [options.minSamples=5] - Minimum samples required
 * @param {number} [options.windowSize=10] - Recent window for trend
 * @returns {Object|null} Cost efficiency result or null
 */
export function computeCostEfficiency(model, taskType, options = {}) {
  const { minSamples = 5, windowSize = 10 } = options;

  const rows = query(
    `SELECT quality_score, cost_usd FROM execution_log
     WHERE model = ? AND task_type = ?
       AND quality_score IS NOT NULL AND quality_score > 0
       AND cost_usd IS NOT NULL AND cost_usd > 0
     ORDER BY timestamp DESC
     LIMIT 100`,
    [model, taskType]
  );

  if (rows.length < minSamples) return null;

  const costPerQuality = rows.map(r => r.cost_usd / r.quality_score);
  const efficiencyMean = _mean(costPerQuality);
  const efficiencyStdDev = _stdDev(costPerQuality);

  // Trend: is efficiency improving (decreasing)?
  const recentWindow = costPerQuality.slice(0, Math.min(windowSize, costPerQuality.length));
  const trend = _linearRegression(recentWindow);

  // Rank among all model/task combos
  const allEfficiency = query(
    `SELECT model, task_type,
            AVG(cost_usd / quality_score) as cpq
     FROM execution_log
     WHERE quality_score > 0 AND cost_usd > 0
     GROUP BY model, task_type
     HAVING COUNT(*) >= ?`,
    [minSamples]
  );

  const allCPQ = allEfficiency.map(r => r.cpq).sort((a, b) => a - b);
  const percentile = _percentileRank(efficiencyMean, allCPQ);

  return {
    costPerQualityPoint: Math.round(efficiencyMean * 10000) / 10000,
    stdDev: Math.round(efficiencyStdDev * 10000) / 10000,
    trendSlope: trend.slope,
    trendR2: trend.r2,
    percentileRank: Math.round(percentile * 1000) / 1000,
    costEfficiencyScore: Math.round((1 - percentile) * 100 * 10) / 10,
    samples: rows.length,
    timestamp: new Date().toISOString(),
  };
}

// ============================================================================
// QUATERNARY METRIC: Speed Improvement
// ============================================================================

/**
 * Compute execution time reduction over time.
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type
 * @param {Object} [options] - Options
 * @param {number} [options.minSamples=5] - Minimum samples required
 * @param {number} [options.windowSize=10] - Recent window for trend
 * @returns {Object|null} Speed improvement result or null
 */
export function computeSpeedImprovement(model, taskType, options = {}) {
  const { minSamples = 5, windowSize = 10 } = options;

  const durations = _getRecentValues(model, taskType, 'duration_ms', 100);
  if (durations.length < minSamples) return null;

  const midpoint = Math.floor(durations.length / 2);
  const recentHalf = durations.slice(0, midpoint);
  const olderHalf = durations.slice(midpoint);

  const recentMean = _mean(recentHalf);
  const olderMean = _mean(olderHalf);

  const speedImprovement = olderMean > 0
    ? ((olderMean - recentMean) / olderMean) * 100
    : 0;

  // Trend
  const recentWindow = durations.slice(0, Math.min(windowSize, durations.length));
  const trend = _linearRegression(recentWindow);

  // Percentage of recent runs faster than old mean
  const fasterCount = recentHalf.filter(d => d < olderMean).length;
  const fasterPercent = recentHalf.length > 0
    ? (fasterCount / recentHalf.length) * 100
    : 0;

  return {
    speedImprovement: Math.round(speedImprovement * 100) / 100,
    oldMeanMs: Math.round(olderMean),
    recentMeanMs: Math.round(recentMean),
    reductionMs: Math.round(olderMean - recentMean),
    trendSlope: trend.slope,
    trendR2: trend.r2,
    percentFasterThanBaseline: Math.round(fasterPercent * 10) / 10,
    samples: durations.length,
    timestamp: new Date().toISOString(),
  };
}

// ============================================================================
// COMPOSITE FUNCTIONS
// ============================================================================

/**
 * Compute all four metrics for a model/task combination.
 */
export function computeAllMetrics(model, taskType, options = {}) {
  return {
    lis: computeLIS(model, taskType, options),
    qualityTrend: computeQualityTrend(model, taskType, options),
    costEfficiency: computeCostEfficiency(model, taskType, options),
    speedImprovement: computeSpeedImprovement(model, taskType, options),
    model,
    taskType,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Compute LIS for all model/task combinations and return a leaderboard.
 */
export function computeLeaderboard(options = {}) {
  const { minSamples = 10 } = options;

  const modelTasks = query(
    `SELECT DISTINCT model, task_type
     FROM execution_log
     WHERE quality_score IS NOT NULL AND task_type IS NOT NULL
     GROUP BY model, task_type
     HAVING COUNT(*) >= ?`,
    [minSamples]
  );

  const leaderboard = [];
  for (const { model, task_type } of modelTasks) {
    const metrics = computeAllMetrics(model, task_type, { minSamples });
    if (metrics.lis) {
      leaderboard.push(metrics);
    }
  }

  leaderboard.sort((a, b) => (b.lis?.score || 0) - (a.lis?.score || 0));
  return leaderboard;
}

// ============================================================================
// BACKGROUND RECOMPUTATION
// ============================================================================

/**
 * Recompute all model_performance rows from execution_log data.
 * Called periodically by the background learner.
 *
 * Computes metrics for time windows: day, week, month, all_time.
 * Writes results to the model_performance table.
 *
 * @param {Object} [options] - Options
 * @param {number} [options.minSamples=3] - Min samples per window
 * @returns {Object} { modelsUpdated, windowsComputed }
 */
export function recomputeModelPerformance(options = {}) {
  const { minSamples = 3 } = options;
  const db = getDb();
  if (!db) return { modelsUpdated: 0, windowsComputed: 0 };

  const windows = [
    { name: 'day',      days: 1 },
    { name: 'week',     days: 7 },
    { name: 'month',    days: 30 },
    { name: 'all_time', days: 36500 },
  ];

  let modelsUpdated = 0;
  let windowsComputed = 0;

  // Get all model/task pairs
  const modelTasks = query(
    `SELECT DISTINCT model, task_type, model_role
     FROM execution_log
     WHERE quality_score IS NOT NULL AND task_type IS NOT NULL`
  );

  for (const window of windows) {
    const now = new Date();
    const windowStart = new Date(now.getTime() - window.days * 24 * 60 * 60 * 1000);
    const windowStartStr = windowStart.toISOString();
    const windowEndStr = now.toISOString();

    for (const { model, task_type, model_role } of modelTasks) {
      const role = model_role || 'worker';

      const stats = queryOne(
        `SELECT
           COUNT(*) as sample_count,
           AVG(quality_score) as avg_quality,
           MIN(quality_score) as min_quality,
           MAX(quality_score) as max_quality,
           AVG(confidence) as avg_confidence,
           AVG(cost_usd) as avg_cost_usd,
           SUM(cost_usd) as total_cost_usd,
           AVG(duration_ms) as avg_duration_ms,
           SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as success_count,
           SUM(CASE WHEN outcome = 'failed' THEN 1 ELSE 0 END) as failure_count,
           AVG(consensus_score) as avg_consensus,
           AVG(was_selected) as selection_rate
         FROM execution_log
         WHERE model = ? AND task_type = ? AND model_role = ?
           AND quality_score IS NOT NULL
           AND timestamp >= ?`,
        [model, task_type, role, windowStartStr]
      );

      if (!stats || stats.sample_count < minSamples) continue;

      // Compute stddev and median
      const qualityValues = _getRecentValues(model, task_type, 'quality_score', 1000);
      const durationValues = _getRecentValues(model, task_type, 'duration_ms', 1000);
      const stddevQuality = _stdDev(qualityValues);
      const medianQuality = _median(qualityValues);

      // Duration percentiles
      const sortedDurations = [...durationValues].sort((a, b) => a - b);
      const p50 = _percentileValue(sortedDurations, 0.50);
      const p95 = _percentileValue(sortedDurations, 0.95);
      const p99 = _percentileValue(sortedDurations, 0.99);

      // Cost per quality
      const costPerQuality = stats.avg_quality > 0
        ? stats.avg_cost_usd / stats.avg_quality
        : null;

      // Calibration error
      const calibrationError = stats.avg_confidence !== null && stats.sample_count > 0
        ? Math.abs(stats.avg_confidence - (stats.success_count / stats.sample_count))
        : null;

      // Trend arrays (last 50 values)
      const qualityTrend = qualityValues.slice(0, 50);
      const costTrend = _getRecentValues(model, task_type, 'cost_usd', 50);
      const durationTrend = durationValues.slice(0, 50);

      const successRate = stats.sample_count > 0
        ? stats.success_count / stats.sample_count
        : 0;

      upsertModelPerformance({
        model,
        role,
        task_type,
        time_window: window.name,
        window_start: windowStartStr,
        window_end: windowEndStr,
        avg_quality: stats.avg_quality || 0,
        min_quality: stats.min_quality,
        max_quality: stats.max_quality,
        stddev_quality: stddevQuality,
        median_quality: medianQuality,
        avg_confidence: stats.avg_confidence || 0,
        calibration_error: calibrationError,
        selection_rate: stats.selection_rate || 0,
        avg_consensus: stats.avg_consensus || 0,
        win_rate: stats.selection_rate || 0,
        avg_cost_usd: stats.avg_cost_usd || 0,
        total_cost_usd: stats.total_cost_usd || 0,
        cost_per_quality: costPerQuality,
        avg_duration_ms: stats.avg_duration_ms || 0,
        p50_duration_ms: p50,
        p95_duration_ms: p95,
        p99_duration_ms: p99,
        sample_count: stats.sample_count,
        success_count: stats.success_count,
        failure_count: stats.failure_count,
        success_rate: successRate,
        quality_trend: qualityTrend,
        cost_trend: costTrend,
        duration_trend: durationTrend,
        selection_trend: [],
      });

      modelsUpdated++;
      windowsComputed++;
    }

    // Compute rankings within each task_type for this window
    _computeRankings(window.name);
  }

  setMetadata('last_model_performance_recompute', new Date().toISOString());

  return { modelsUpdated, windowsComputed };
}

// ============================================================================
// LIS COMPONENT CALCULATIONS
// ============================================================================

function _computeQualityScore(stats, allStats, recentQuality) {
  if (!stats.avg_quality) return 0;

  const allQualities = allStats.map(s => s.avg_quality).filter(q => q > 0);
  if (allQualities.length === 0) return stats.avg_quality * 100;

  const sortedQualities = allQualities.sort((a, b) => a - b);
  const percentileRank = _percentileRank(stats.avg_quality, sortedQualities) * 100;

  const trendBonus = _computeTrendBonus(recentQuality, 10);
  const score = (percentileRank + trendBonus) / 1.1;

  return Math.min(100, score);
}

function _computeCostScore(stats, allStats, recentCost) {
  if (stats.avg_cost === undefined || stats.avg_cost === 0) return 50;

  const allCosts = allStats.map(s => s.avg_cost).filter(c => c > 0);
  if (allCosts.length === 0) return 50;

  const sortedCosts = allCosts.sort((a, b) => a - b);
  const costPercentile = _percentileRank(stats.avg_cost, sortedCosts);
  const costScore = (1 - costPercentile) * 100;

  // Trend bonus: reducing cost adds up to 15 points
  const invertedCost = recentCost.map(c => -c);
  const trendBonus = _computeTrendBonus(invertedCost, 15);

  const score = (costScore + trendBonus) / 1.15;
  return Math.min(100, score);
}

function _computeSpeedScore(stats, allStats, recentDuration) {
  if (!stats.avg_duration || stats.avg_duration === 0) return 50;

  const allDurations = allStats.map(s => s.avg_duration).filter(d => d > 0);
  if (allDurations.length === 0) return 50;

  const sortedDurations = allDurations.sort((a, b) => a - b);
  const speedPercentile = _percentileRank(stats.avg_duration, sortedDurations);
  const speedScore = (1 - speedPercentile) * 100;

  const invertedDuration = recentDuration.map(d => -d);
  const trendBonus = _computeTrendBonus(invertedDuration, 10);

  const score = (speedScore + trendBonus) / 1.1;
  return Math.min(100, score);
}

function _computeConsistencyScore(recentQuality, recentCost) {
  if (recentQuality.length < 2) return 50;

  const qualityCV = _coefficientOfVariation(recentQuality);
  const costCV = _coefficientOfVariation(recentCost);

  const qualityCVScore = Math.max(0, 100 - qualityCV * 200);
  const costCVScore = recentCost.length >= 2
    ? Math.max(0, 100 - costCV * 200)
    : 50;

  return (qualityCVScore + costCVScore) / 2;
}

function _computeTrendBonus(values, maxBonus) {
  if (values.length < 2) return 0;
  const trend = _linearRegression(values);
  const trendStrength = Math.min(1, Math.abs(trend.slope) * 10);
  return trend.slope > 0 ? maxBonus * trendStrength : 0;
}

// ============================================================================
// RANKING
// ============================================================================

function _computeRankings(timeWindow) {
  const db = getDb();
  if (!db) return;

  // Get all models for each task_type in this window
  const rows = query(
    `SELECT id, model, task_type, avg_quality, cost_per_quality, avg_duration_ms
     FROM model_performance
     WHERE time_window = ?`,
    [timeWindow]
  );

  // Group by task_type
  const byTask = {};
  for (const row of rows) {
    if (!byTask[row.task_type]) byTask[row.task_type] = [];
    byTask[row.task_type].push(row);
  }

  // Rank within each task_type
  for (const [_taskType, models] of Object.entries(byTask)) {
    // Quality rank (highest quality = rank 1)
    const byQuality = [...models].sort((a, b) => (b.avg_quality || 0) - (a.avg_quality || 0));
    // Efficiency rank (lowest cost_per_quality = rank 1)
    const byEfficiency = [...models].sort((a, b) => (a.cost_per_quality || Infinity) - (b.cost_per_quality || Infinity));
    // Speed rank (lowest duration = rank 1)
    const bySpeed = [...models].sort((a, b) => (a.avg_duration_ms || Infinity) - (b.avg_duration_ms || Infinity));

    for (let i = 0; i < models.length; i++) {
      const qualityRank = byQuality.findIndex(m => m.id === models[i].id) + 1;
      const efficiencyRank = byEfficiency.findIndex(m => m.id === models[i].id) + 1;
      const speedRank = bySpeed.findIndex(m => m.id === models[i].id) + 1;

      try {
        db.prepare(
          `UPDATE model_performance
           SET quality_rank = ?, efficiency_rank = ?, speed_rank = ?
           WHERE id = ?`
        ).run(qualityRank, efficiencyRank, speedRank, models[i].id);
      } catch (_err) {
        // Ignore ranking update failures
      }
    }
  }
}

// ============================================================================
// DATABASE HELPERS
// ============================================================================

function _getStats(model, taskType) {
  return queryOne(
    `SELECT
       COUNT(*) as sample_count,
       AVG(quality_score) as avg_quality,
       AVG(cost_usd) as avg_cost,
       AVG(duration_ms) as avg_duration,
       AVG(confidence) as avg_confidence,
       SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as success_rate,
       AVG(was_selected) as selection_rate
     FROM execution_log
     WHERE model = ? AND task_type = ?
       AND quality_score IS NOT NULL`,
    [model, taskType]
  );
}

function _getAllStats(minSamples) {
  return query(
    `SELECT
       model,
       task_type,
       COUNT(*) as sample_count,
       AVG(quality_score) as avg_quality,
       AVG(cost_usd) as avg_cost,
       AVG(duration_ms) as avg_duration
     FROM execution_log
     WHERE quality_score IS NOT NULL
     GROUP BY model, task_type
     HAVING COUNT(*) >= ?`,
    [minSamples]
  );
}

function _getRecentValues(model, taskType, column, limit) {
  const rows = query(
    `SELECT ${column} as val FROM execution_log
     WHERE model = ? AND task_type = ?
       AND ${column} IS NOT NULL
     ORDER BY timestamp DESC
     LIMIT ?`,
    [model, taskType, limit]
  );
  return rows.map(r => r.val);
}

// ============================================================================
// STATISTICAL HELPERS
// ============================================================================

function _mean(values) {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function _stdDev(values) {
  if (values.length < 2) return 0;
  const mean = _mean(values);
  const variance = values.reduce((sum, val) => sum + (val - mean) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function _median(values) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

function _coefficientOfVariation(values) {
  if (values.length < 2) return 0;
  const mean = _mean(values);
  if (mean === 0) return 0;
  return _stdDev(values) / Math.abs(mean);
}

function _percentileRank(value, sortedValues) {
  if (sortedValues.length === 0) return 0.5;
  const count = sortedValues.filter(v => v < value).length;
  return count / sortedValues.length;
}

function _percentileValue(sortedValues, percentile) {
  if (sortedValues.length === 0) return null;
  const idx = Math.ceil(percentile * sortedValues.length) - 1;
  return sortedValues[Math.max(0, idx)];
}

function _linearRegression(values) {
  if (values.length < 2) {
    return { slope: 0, intercept: 0, r2: 0 };
  }

  const n = values.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;

  for (let i = 0; i < n; i++) {
    sumX += i;
    sumY += values[i];
    sumXY += i * values[i];
    sumX2 += i * i;
  }

  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return { slope: 0, intercept: sumY / n, r2: 0 };

  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;

  // R-squared
  const yMean = sumY / n;
  let totalSS = 0, residualSS = 0;
  for (let i = 0; i < n; i++) {
    totalSS += (values[i] - yMean) ** 2;
    residualSS += (values[i] - (slope * i + intercept)) ** 2;
  }

  const r2 = totalSS > 0 ? Math.max(0, 1 - residualSS / totalSS) : 0;

  return {
    slope: Math.round(slope * 100000) / 100000,
    intercept: Math.round(intercept * 100000) / 100000,
    r2: Math.round(r2 * 10000) / 10000,
  };
}

/**
 * Welch's degrees of freedom for unequal-variance t-test.
 */
function _welchDF(s1, n1, s2, n2) {
  const v1 = (s1 ** 2) / n1;
  const v2 = (s2 ** 2) / n2;
  const num = (v1 + v2) ** 2;
  const denom = (v1 ** 2) / (n1 - 1) + (v2 ** 2) / (n2 - 1);
  return denom > 0 ? num / denom : 1;
}

/**
 * Approximate two-tailed p-value from t-score and degrees of freedom.
 * Uses the normal approximation for large df, lookup table for small df.
 */
function _tTestPValue(tScore, df) {
  const absT = Math.abs(tScore);

  if (df < 1) return 1.0;

  // For large df, use normal approximation
  if (df > 30) {
    if (absT > 3.29) return 0.001;
    if (absT > 2.58) return 0.01;
    if (absT > 1.96) return 0.05;
    if (absT > 1.65) return 0.10;
    if (absT > 1.28) return 0.20;
    return 1.0;
  }

  // For small df, more conservative thresholds
  if (absT > 4.0) return 0.001;
  if (absT > 3.0) return 0.01;
  if (absT > 2.5) return 0.02;
  if (absT > 2.0) return 0.05;
  if (absT > 1.5) return 0.15;
  if (absT > 1.0) return 0.30;
  return 1.0;
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  computeLIS,
  computeQualityTrend,
  computeCostEfficiency,
  computeSpeedImprovement,
  computeAllMetrics,
  computeLeaderboard,
  recomputeModelPerformance,
  WEIGHTS,
};
