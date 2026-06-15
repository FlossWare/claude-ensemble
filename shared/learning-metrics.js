/**
 * Learning Metrics Calculation System
 *
 * Computes four primary metrics to measure AI learning and improvement:
 * 1. Learning Intelligence Score (LIS): 0-100 aggregate improvement metric
 * 2. Quality Trend: Statistical improvement in output quality over time
 * 3. Cost Efficiency: Improvement in cost per unit quality
 * 4. Speed Improvement: Reduction in execution time
 *
 * All metrics include:
 * - Raw calculation (for detailed analysis)
 * - Trend detection (improving/stable/declining)
 * - Confidence interval (statistical significance)
 * - Peer comparison (vs other models/combinations)
 */

import {
  getModelTaskStats,
  getRecentQuality,
  getRecentCost,
  getRecentExecutions,
  getTuning,
  getAllTuning,
  getAllCombinations,
  getDistinctModelTasks,
  getDb,
} from './learning-logger.js';

/**
 * ============================================================================
 * PRIMARY METRIC: Learning Intelligence Score (LIS)
 * ============================================================================
 *
 * LIS aggregates four dimensions of improvement into a single 0-100 score:
 * - Quality improvement: 35% weight
 * - Cost efficiency: 25% weight
 * - Speed improvement: 20% weight
 * - Consistency (low variance): 20% weight
 *
 * Formula:
 *   LIS = 35*qualityScore + 25*costScore + 20*speedScore + 20*consistencyScore
 *
 * Each component is normalized to [0, 100] before weighting.
 */

export function calculateLIS(model, taskType, options = {}) {
  const {
    minSamples = 10,
    timeWindowDays = 30,
    percentileBasis = 'all',  // 'all' or 'recent'
  } = options;

  const stats = getModelTaskStats(model, taskType);
  if (!stats || stats.sample_count < minSamples) {
    return null; // Insufficient data
  }

  // Get recent data for trend analysis
  const recentQuality = getRecentQuality(model, taskType);
  const recentCost = getRecentCost(model, taskType);
  const recentExecutions = getRecentExecutions(100).filter(
    (e) => e.model === model && e.task_type === taskType
  );

  const qualityScore = _calculateQualityScore(stats, recentQuality, percentileBasis);
  const costScore = _calculateCostScore(stats, recentCost, percentileBasis);
  const speedScore = _calculateSpeedScore(stats, recentExecutions, percentileBasis);
  const consistencyScore = _calculateConsistencyScore(recentQuality, recentCost);

  const lis = 35 * qualityScore + 25 * costScore + 20 * speedScore + 20 * consistencyScore;

  return {
    score: Math.min(100, Math.max(0, lis)),
    components: {
      quality: qualityScore,
      cost: costScore,
      speed: speedScore,
      consistency: consistencyScore,
    },
    sampleCount: stats.sample_count,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Quality Score Component: 0-100
 * Based on average quality with percentile comparison
 */
function _calculateQualityScore(stats, recentQuality, percentileBasis) {
  if (!stats.avg_quality) return 0;

  // Get all models' average quality for comparison
  const allStats = getAllTuning().filter(t => t.sample_count >= 5);
  const allQualities = allStats.map(s => s.avg_quality).filter(q => q);

  if (allQualities.length === 0) {
    return stats.avg_quality * 100; // No comparison baseline
  }

  // Percentile rank among all models (0-100)
  const sortedQualities = allQualities.sort((a, b) => a - b);
  const modelQuality = stats.avg_quality;
  const percentileRank = _percentileRank(modelQuality, sortedQualities) * 100;

  // Apply trend bonus: recent improvement adds up to 10 points
  const trendBonus = _calculateTrendBonus(recentQuality, 10);

  const score = (percentileRank + trendBonus) / 1.1; // Normalize to 100
  return Math.min(100, score);
}

/**
 * Cost Score Component: 0-100
 * Higher scores for lower cost (efficiency)
 * Penalizes high variance in costs
 */
function _calculateCostScore(stats, recentCost, percentileBasis) {
  if (stats.avg_cost_usd === undefined || stats.avg_cost_usd === 0) {
    return 50; // Neutral: no cost data or free
  }

  // Get all models' average cost for comparison
  const allStats = getAllTuning().filter(t => t.sample_count >= 5 && t.avg_cost_usd > 0);
  const allCosts = allStats.map(s => s.avg_cost_usd);

  if (allCosts.length === 0) {
    return 50; // No comparison baseline
  }

  // Lower cost = higher score (inverted percentile)
  const sortedCosts = allCosts.sort((a, b) => a - b);
  const costPercentile = _percentileRank(stats.avg_cost_usd, sortedCosts);
  const costScore = (1 - costPercentile) * 100; // Invert so lower cost is better

  // Trend bonus: reducing cost adds up to 15 points
  const trendBonus = _calculateTrendBonus(recentCost.map(c => -c), 15);

  const score = (costScore + trendBonus) / 1.15;
  return Math.min(100, score);
}

/**
 * Speed Score Component: 0-100
 * Higher scores for faster execution (lower duration)
 */
function _calculateSpeedScore(stats, recentExecutions, percentileBasis) {
  if (!stats.avg_duration_ms || stats.avg_duration_ms === 0) {
    return 50; // Neutral
  }

  // Get all models' average duration for comparison
  const allStats = getAllTuning().filter(t => t.sample_count >= 5);
  const allDurations = allStats.map(s => s.avg_duration_ms).filter(d => d > 0);

  if (allDurations.length === 0) {
    return 50;
  }

  // Lower duration = higher score (inverted)
  const sortedDurations = allDurations.sort((a, b) => a - b);
  const speedPercentile = _percentileRank(stats.avg_duration_ms, sortedDurations);
  const speedScore = (1 - speedPercentile) * 100;

  // Trend bonus: faster execution adds up to 10 points
  const recentDurations = recentExecutions.map(e => e.duration_ms);
  const trendBonus = _calculateTrendBonus(recentDurations.map(d => -d), 10);

  const score = (speedScore + trendBonus) / 1.1;
  return Math.min(100, score);
}

/**
 * Consistency Score Component: 0-100
 * Higher scores for low variance (predictable performance)
 * Uses coefficient of variation
 */
function _calculateConsistencyScore(recentQuality, recentCost) {
  const qualityCV = _coefficientOfVariation(recentQuality);
  const costCV = _coefficientOfVariation(recentCost);

  // Lower CV = higher score (inverted)
  // CV > 0.5 gets penalized, CV < 0.2 is excellent
  const qualityCVScore = Math.max(0, 100 - qualityCV * 200);
  const costCVScore = Math.max(0, 100 - costCV * 200);

  return (qualityCVScore + costCVScore) / 2;
}

/**
 * ============================================================================
 * SECONDARY METRIC: Quality Trend Analysis
 * ============================================================================
 *
 * Detects statistical improvement, decline, or stability in quality over time
 * Returns confidence interval and trend direction
 */

export function calculateQualityTrend(model, taskType, options = {}) {
  const {
    minSamples = 5,
    windowSize = 10,  // Last N samples for recent trend
  } = options;

  const recentQuality = getRecentQuality(model, taskType);
  if (recentQuality.length < minSamples) {
    return null;
  }

  // Split into two halves for comparison
  const midpoint = Math.floor(recentQuality.length / 2);
  const olderHalf = recentQuality.slice(midpoint);
  const recentHalf = recentQuality.slice(0, midpoint);

  const olderMean = _mean(olderHalf);
  const recentMean = _mean(recentHalf);
  const improvement = ((recentMean - olderMean) / olderMean) * 100;

  // Calculate statistical significance (t-test style)
  const olderStdDev = _stdDev(olderHalf);
  const recentStdDev = _stdDev(recentHalf);
  const pooledStdError = Math.sqrt(
    (olderStdDev ** 2) / olderHalf.length + (recentStdDev ** 2) / recentHalf.length
  );
  const tScore = (recentMean - olderMean) / pooledStdError;
  const pValue = _tTestPValue(tScore, olderHalf.length + recentHalf.length - 2);

  // Trend classification
  let trend = 'stable';
  let confidence = 0;
  if (pValue < 0.05) {
    trend = improvement > 0 ? 'improving' : 'declining';
    confidence = 1 - pValue;
  }

  // Recent window trend (last N samples)
  const recentWindow = recentQuality.slice(0, Math.min(windowSize, recentQuality.length));
  const recentWindowTrend = _linearRegression(recentWindow);

  return {
    trend,
    improvementPercent: improvement,
    pValue,
    confidence: Math.min(0.99, confidence),
    recentTrendSlope: recentWindowTrend.slope,
    recentTrendR2: recentWindowTrend.r2,
    samples: recentQuality.length,
    mean: recentMean,
    stdDev: recentStdDev,
    timestamp: new Date().toISOString(),
  };
}

/**
 * ============================================================================
 * TERTIARY METRIC: Cost Efficiency Trend
 * ============================================================================
 *
 * Tracks cost per unit of quality (lower is better)
 * Identifies cost optimization opportunities
 */

export function calculateCostEfficiency(model, taskType, options = {}) {
  const {
    minSamples = 5,
    windowSize = 10,
  } = options;

  const stats = getModelTaskStats(model, taskType);
  if (!stats || stats.sample_count < minSamples) {
    return null;
  }

  const recentQuality = getRecentQuality(model, taskType);
  const recentCost = getRecentCost(model, taskType);

  if (recentQuality.length < minSamples || recentCost.length < minSamples) {
    return null;
  }

  // Cost per quality point
  const costPerQuality = recentCost.map((cost, idx) => {
    const quality = recentQuality[idx];
    return quality > 0 ? cost / quality : cost;
  });

  const efficiencyMean = _mean(costPerQuality);
  const efficiencyStdDev = _stdDev(costPerQuality);

  // Trend: is cost per quality improving (decreasing)?
  const efficiencyTrend = _linearRegression(costPerQuality.slice(0, windowSize));

  // Rank among all model/task combos
  const allTuning = getAllTuning();
  const allEfficiencies = allTuning
    .filter(t => t.avg_quality > 0 && t.sample_count >= 5)
    .map(t => ({ model: t.model, costPerQuality: t.avg_cost_usd / t.avg_quality }));
  const efficiencyPercentile = _percentileRank(
    efficiencyMean,
    allEfficiencies.map(e => e.costPerQuality)
  );

  return {
    costPerQualityPoint: efficiencyMean,
    stdDev: efficiencyStdDev,
    trendSlope: efficiencyTrend.slope, // negative = improving
    trendR2: efficiencyTrend.r2,
    percentileRank: efficiencyPercentile, // 0 = most expensive, 1 = most efficient
    costEfficiencyScore: (1 - efficiencyPercentile) * 100, // Higher is better
    samples: recentCost.length,
    timestamp: new Date().toISOString(),
  };
}

/**
 * ============================================================================
 * QUATERNARY METRIC: Speed Improvement Trend
 * ============================================================================
 *
 * Tracks execution time reduction over time
 */

export function calculateSpeedImprovement(model, taskType, options = {}) {
  const {
    minSamples = 5,
    windowSize = 10,
  } = options;

  const recentExecutions = getRecentExecutions(100).filter(
    (e) => e.model === model && e.task_type === taskType
  );

  if (recentExecutions.length < minSamples) {
    return null;
  }

  const durations = recentExecutions.map(e => e.duration_ms);

  // Split into halves
  const midpoint = Math.floor(durations.length / 2);
  const olderHalf = durations.slice(midpoint);
  const recentHalf = durations.slice(0, midpoint);

  const olderMean = _mean(olderHalf);
  const recentMean = _mean(recentHalf);
  const speedImprovement = ((olderMean - recentMean) / olderMean) * 100;

  // Trend
  const recentWindow = durations.slice(0, Math.min(windowSize, durations.length));
  const speedTrend = _linearRegression(recentWindow);

  return {
    speedImprovement: speedImprovement, // positive = faster
    oldMean: olderMean,
    recentMean: recentMean,
    recentTrendSlope: speedTrend.slope, // negative = getting faster
    recentTrendR2: speedTrend.r2,
    percentImprovement: speedImprovement,
    percentageImprovedRuns: _percentageAboveBaseline(recentHalf, olderMean) * 100,
    samples: durations.length,
    timestamp: new Date().toISOString(),
  };
}

/**
 * ============================================================================
 * COMPOSITE METRICS
 * ============================================================================
 */

/**
 * Get all metrics for a model/task combination
 */
export function getComprehensiveMetrics(model, taskType, options = {}) {
  return {
    lis: calculateLIS(model, taskType, options),
    qualityTrend: calculateQualityTrend(model, taskType, options),
    costEfficiency: calculateCostEfficiency(model, taskType, options),
    speedImprovement: calculateSpeedImprovement(model, taskType, options),
    timestamp: new Date().toISOString(),
  };
}

/**
 * Compare metrics across all model/task combinations
 * Useful for identifying best performers
 */
export function getAllMetricsLeaderboard(options = {}) {
  const { minSamples = 10 } = options;

  const modelTasks = getDistinctModelTasks();
  const leaderboard = [];

  for (const { model, task_type } of modelTasks) {
    const metrics = getComprehensiveMetrics(model, task_type, { minSamples });
    if (metrics.lis) {
      leaderboard.push({
        model,
        taskType: task_type,
        ...metrics,
      });
    }
  }

  // Sort by LIS score
  leaderboard.sort((a, b) => b.lis.score - a.lis.score);
  return leaderboard;
}

/**
 * Get model combination synergy metrics
 */
export function getModelCombinationMetrics(options = {}) {
  const { minSamples = 3 } = options;

  const combinations = getAllCombinations().filter(c => c.usage_count >= minSamples);

  return combinations.map(combo => ({
    taskType: combo.task_type,
    workers: JSON.parse(combo.worker_models),
    arbiter: combo.arbiter_model,
    avgQuality: combo.avg_quality,
    avgCost: combo.avg_cost_usd,
    avgDuration: combo.avg_duration_ms,
    synergy: combo.synergy_score,
    diversity: combo.diversity_score,
    usageCount: combo.usage_count,
    synergyStar: combo.synergy_score > 0.05 ? '★' : '',
  }));
}

/**
 * ============================================================================
 * DATABASE QUERIES FOR METRICS
 * ============================================================================
 *
 * Raw SQL queries for custom metric calculations
 */

export const METRICS_QUERIES = {
  // Quality trend: compare recent vs older quality
  qualityTrendSQL: `
    SELECT
      'older' as period,
      AVG(quality_score) as avg_quality,
      STDDEV(quality_score) as stddev_quality,
      COUNT(*) as sample_count
    FROM execution_log
    WHERE model = ? AND task_type = ?
      AND quality_score IS NOT NULL
      AND timestamp <= datetime('now', '-${30 / 2} days')
    UNION ALL
    SELECT
      'recent' as period,
      AVG(quality_score) as avg_quality,
      STDDEV(quality_score) as stddev_quality,
      COUNT(*) as sample_count
    FROM execution_log
    WHERE model = ? AND task_type = ?
      AND quality_score IS NOT NULL
      AND timestamp > datetime('now', '-${30 / 2} days')
  `,

  // Cost efficiency: cost per quality point over time
  costEfficiencySQL: `
    SELECT
      DATE(timestamp) as date,
      AVG(cost_usd / NULLIF(quality_score, 0)) as cost_per_quality,
      COUNT(*) as run_count
    FROM execution_log
    WHERE model = ? AND task_type = ?
      AND quality_score > 0 AND cost_usd IS NOT NULL
    GROUP BY DATE(timestamp)
    ORDER BY DATE(timestamp) DESC
    LIMIT 30
  `,

  // Speed: execution time percentiles
  speedPercentilesSQL: `
    SELECT
      model,
      task_type,
      PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY duration_ms) as p25,
      PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
      PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY duration_ms) as p75,
      PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_ms) as p90,
      AVG(duration_ms) as mean,
      STDDEV(duration_ms) as stddev
    FROM execution_log
    WHERE model = ? AND task_type = ?
      AND duration_ms > 0
    GROUP BY model, task_type
  `,

  // Consistency: coefficient of variation by model
  consistencySQL: `
    SELECT
      model,
      task_type,
      STDDEV(quality_score) / AVG(quality_score) as quality_cv,
      STDDEV(cost_usd) / AVG(NULLIF(cost_usd, 0)) as cost_cv,
      COUNT(*) as sample_count
    FROM execution_log
    WHERE quality_score IS NOT NULL
    GROUP BY model, task_type
    ORDER BY quality_cv ASC
  `,

  // Model synergy: combination performance vs individual models
  synergySQL: `
    SELECT
      mc.task_type,
      mc.worker_models,
      mc.arbiter_model,
      mc.avg_quality as combo_quality,
      mc.synergy_score,
      mc.diversity_score,
      mc.usage_count,
      GROUP_CONCAT(mt.model || ':' || mt.avg_quality, ',') as individual_qualities
    FROM model_combinations mc
    LEFT JOIN model_tuning mt ON mc.task_type = mt.task_type
    GROUP BY mc.task_type, mc.worker_models, mc.arbiter_model
    ORDER BY mc.synergy_score DESC
  `,

  // Improvement rate: quality trend slope
  improvementRateSQL: `
    WITH ranked AS (
      SELECT
        model,
        task_type,
        quality_score,
        ROW_NUMBER() OVER (ORDER BY timestamp ASC) as rn
      FROM execution_log
      WHERE model = ? AND task_type = ?
        AND quality_score IS NOT NULL
    )
    SELECT
      (COUNT(*) - 1.0) * SUM(rn * quality_score) - SUM(rn) * SUM(quality_score) as numerator,
      (COUNT(*) - 1.0) * SUM(rn * rn) - SUM(rn) * SUM(rn) as denominator
    FROM ranked
  `,
};

/**
 * ============================================================================
 * HELPER FUNCTIONS
 * ============================================================================
 */

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

function _coefficientOfVariation(values) {
  const mean = _mean(values);
  if (mean === 0) return 0;
  const stdDev = _stdDev(values);
  return stdDev / mean;
}

function _percentileRank(value, sortedValues) {
  if (sortedValues.length === 0) return 0.5;
  const count = sortedValues.filter(v => v < value).length;
  return count / sortedValues.length;
}

function _linearRegression(values) {
  if (values.length < 2) {
    return { slope: 0, intercept: 0, r2: 0 };
  }

  const n = values.length;
  const x = Array.from({ length: n }, (_, i) => i);
  const sumX = _sum(x);
  const sumY = _sum(values);
  const sumXY = _sum(x.map((xi, i) => xi * values[i]));
  const sumX2 = _sum(x.map(xi => xi * xi));

  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  // R-squared
  const yMean = sumY / n;
  const totalSumSquares = _sum(values.map(y => (y - yMean) ** 2));
  const residualSumSquares = _sum(
    values.map((y, i) => (y - (slope * x[i] + intercept)) ** 2)
  );
  const r2 = 1 - residualSumSquares / totalSumSquares;

  return { slope, intercept, r2: Math.max(0, r2) };
}

function _sum(values) {
  return values.reduce((a, b) => a + b, 0);
}

function _calculateTrendBonus(values, maxBonus) {
  if (values.length < 2) return 0;
  const trend = _linearRegression(values);
  const trendStrength = Math.min(1, Math.abs(trend.slope) * 10);
  return trend.slope > 0 ? maxBonus * trendStrength : 0;
}

function _tTestPValue(tScore, df) {
  // Simplified t-test p-value approximation
  // For exact values, use external statistical library
  const absT = Math.abs(tScore);
  if (absT > 3) return 0.001;
  if (absT > 2) return 0.05;
  if (absT > 1) return 0.2;
  return 1.0;
}

function _percentageAboveBaseline(recentValues, baseline) {
  const aboveBaseline = recentValues.filter(v => v < baseline).length;
  return aboveBaseline / recentValues.length;
}

export default {
  calculateLIS,
  calculateQualityTrend,
  calculateCostEfficiency,
  calculateSpeedImprovement,
  getComprehensiveMetrics,
  getAllMetricsLeaderboard,
  getModelCombinationMetrics,
  METRICS_QUERIES,
};
