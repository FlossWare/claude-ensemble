/**
 * Statistical Significance Testing for Multi-AI Consensus
 *
 * Reports confidence intervals and detects statistical ties in weighted voting.
 *
 * Features:
 * 1. Bootstrap resampling for interval estimation
 * 2. 95% confidence intervals on consensus strength
 * 3. Statistical tie detection (margin <5%)
 * 4. Sample size recommendations
 *
 * Example:
 *   const result = calculateConfidenceInterval(votes, 'winner_weight');
 *   console.log(`95% CI: [${result.ci_lower}, ${result.ci_upper}]`);
 *   console.log(`Statistical tie: ${result.is_tie}`);
 *
 * Created: 2026-06-28
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Bootstrap configuration
 */
const BOOTSTRAP_CONFIG = {
  iterations: 1000,        // Number of bootstrap samples
  sample_fraction: 1.0,    // Fraction of data to sample (1.0 = same size as original)
  confidence_level: 0.95,  // 95% confidence interval
  min_samples: 3,          // Minimum samples required for bootstrap
};

/**
 * Statistical tie thresholds
 */
const TIE_THRESHOLDS = {
  margin_percent: 5,       // <5% difference = statistical tie
  min_ci_overlap: 0.5,     // >50% CI overlap = statistical tie
};

/**
 * Sample size recommendations
 */
const SAMPLE_SIZE_CONFIG = {
  min_recommended: 5,      // Minimum recommended vote count
  high_confidence: 10,     // High confidence threshold
  very_high_confidence: 20, // Very high confidence threshold
};

// ============================================================================
// BOOTSTRAP RESAMPLING
// ============================================================================

/**
 * Bootstrap resample an array (sample with replacement)
 *
 * @param {Array} data - Original data array
 * @param {number} sampleSize - Size of bootstrap sample (default: same as original)
 * @returns {Array} Bootstrap sample
 */
function bootstrapSample(data, sampleSize = null) {
  const n = sampleSize || data.length;
  const sample = [];

  for (let i = 0; i < n; i++) {
    const randomIndex = Math.floor(Math.random() * data.length);
    sample.push(data[randomIndex]);
  }

  return sample;
}

/**
 * Bootstrap confidence interval for a statistic
 *
 * Algorithm:
 * 1. Resample data B times (with replacement)
 * 2. Calculate statistic on each bootstrap sample
 * 3. Sort bootstrap statistics
 * 4. Extract percentiles for confidence interval
 *
 * @param {Array} data - Original data array
 * @param {Function} statistic - Function to calculate statistic from data
 * @param {Object} options - Bootstrap options
 * @param {number} options.iterations - Number of bootstrap samples (default: 1000)
 * @param {number} options.confidence_level - Confidence level (default: 0.95)
 * @param {number} options.sample_fraction - Fraction of data to sample (default: 1.0)
 * @returns {Object} { estimate, ci_lower, ci_upper, std_error }
 */
function bootstrapCI(data, statistic, options = {}) {
  const iterations = options.iterations || BOOTSTRAP_CONFIG.iterations;
  const confidenceLevel = options.confidence_level || BOOTSTRAP_CONFIG.confidence_level;
  const sampleFraction = options.sample_fraction || BOOTSTRAP_CONFIG.sample_fraction;

  // Edge case: too few samples
  if (data.length < BOOTSTRAP_CONFIG.min_samples) {
    const estimate = statistic(data);
    return {
      estimate,
      ci_lower: estimate,
      ci_upper: estimate,
      std_error: 0,
      warning: 'insufficient_samples',
      message: `Only ${data.length} samples (min ${BOOTSTRAP_CONFIG.min_samples} for CI)`,
    };
  }

  // Calculate statistic on original data
  const originalEstimate = statistic(data);

  // Bootstrap resampling
  const bootstrapEstimates = [];
  const sampleSize = Math.floor(data.length * sampleFraction);

  for (let i = 0; i < iterations; i++) {
    const sample = bootstrapSample(data, sampleSize);
    const estimate = statistic(sample);
    bootstrapEstimates.push(estimate);
  }

  // Sort bootstrap estimates
  bootstrapEstimates.sort((a, b) => a - b);

  // Calculate percentiles for CI
  const alpha = 1 - confidenceLevel;
  const lowerPercentile = alpha / 2;
  const upperPercentile = 1 - (alpha / 2);

  const lowerIndex = Math.floor(iterations * lowerPercentile);
  const upperIndex = Math.floor(iterations * upperPercentile);

  const ciLower = bootstrapEstimates[lowerIndex];
  const ciUpper = bootstrapEstimates[upperIndex];

  // Calculate standard error (std dev of bootstrap estimates)
  const mean = bootstrapEstimates.reduce((sum, x) => sum + x, 0) / iterations;
  const variance = bootstrapEstimates.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / (iterations - 1);
  const stdError = Math.sqrt(variance);

  return {
    estimate: originalEstimate,
    ci_lower: ciLower,
    ci_upper: ciUpper,
    std_error: stdError,
    confidence_level: confidenceLevel,
    iterations,
  };
}

// ============================================================================
// STATISTICAL TIE DETECTION
// ============================================================================

/**
 * Check if two values are statistically tied
 *
 * A tie is detected if:
 * 1. Difference <5% of winner value (margin threshold), AND
 * 2. Confidence intervals overlap >50%
 *
 * @param {Object} winner - Winner CI result
 * @param {Object} runnerUp - Runner-up CI result
 * @returns {Object} Tie analysis
 */
function detectStatisticalTie(winner, runnerUp) {
  if (!winner || !runnerUp) {
    return {
      is_tie: false,
      reason: 'missing_runner_up',
    };
  }

  // Check margin threshold
  const difference = winner.estimate - runnerUp.estimate;
  const marginPercent = (difference / winner.estimate) * 100;
  const marginBelowThreshold = marginPercent < TIE_THRESHOLDS.margin_percent;

  // Check CI overlap
  const overlapLower = Math.max(winner.ci_lower, runnerUp.ci_lower);
  const overlapUpper = Math.min(winner.ci_upper, runnerUp.ci_upper);
  const overlapSize = Math.max(0, overlapUpper - overlapLower);

  const winnerCISize = winner.ci_upper - winner.ci_lower;
  const runnerUpCISize = runnerUp.ci_upper - runnerUp.ci_lower;
  const avgCISize = (winnerCISize + runnerUpCISize) / 2;

  const overlapPercent = avgCISize > 0 ? (overlapSize / avgCISize) : 0;
  const ciOverlap = overlapPercent > TIE_THRESHOLDS.min_ci_overlap;

  // Both conditions must be true for a tie
  const isTie = marginBelowThreshold && ciOverlap;

  return {
    is_tie: isTie,
    margin_percent: marginPercent,
    margin_below_threshold: marginBelowThreshold,
    ci_overlap_percent: overlapPercent * 100,
    ci_overlap: ciOverlap,
    reason: isTie
      ? `Margin ${marginPercent.toFixed(1)}% < ${TIE_THRESHOLDS.margin_percent}% AND CI overlap ${(overlapPercent * 100).toFixed(1)}% > ${TIE_THRESHOLDS.min_ci_overlap * 100}%`
      : (marginBelowThreshold
          ? `Margin below threshold but CI overlap insufficient (${(overlapPercent * 100).toFixed(1)}%)`
          : `Margin ${marginPercent.toFixed(1)}% exceeds threshold ${TIE_THRESHOLDS.margin_percent}%`),
  };
}

// ============================================================================
// SAMPLE SIZE RECOMMENDATIONS
// ============================================================================

/**
 * Recommend additional samples based on uncertainty
 *
 * Heuristic:
 * - Narrow CI (std_error <0.05): High confidence, no additional samples
 * - Medium CI (0.05-0.10): Recommend 5-10 more samples
 * - Wide CI (>0.10): Recommend 10-20 more samples
 * - Statistical tie: Always recommend more samples
 *
 * @param {Object} ciResult - Confidence interval result
 * @param {number} currentSamples - Current sample count
 * @returns {Object} Sample size recommendation
 */
function recommendSampleSize(ciResult, currentSamples) {
  if (!ciResult || ciResult.warning === 'insufficient_samples') {
    return {
      needs_more_samples: true,
      recommended_additional: SAMPLE_SIZE_CONFIG.min_recommended - currentSamples,
      confidence_level: 'very_low',
      reason: 'Insufficient samples for confidence interval estimation',
    };
  }

  const { std_error } = ciResult;

  // Determine confidence level based on standard error
  let confidenceLevel;
  let recommendedAdditional = 0;
  let needsMoreSamples = false;

  if (std_error < 0.05) {
    confidenceLevel = 'high';
    // No additional samples needed
  } else if (std_error < 0.10) {
    confidenceLevel = 'medium';
    recommendedAdditional = Math.max(5, SAMPLE_SIZE_CONFIG.high_confidence - currentSamples);
    needsMoreSamples = recommendedAdditional > 0;
  } else {
    confidenceLevel = 'low';
    recommendedAdditional = Math.max(10, SAMPLE_SIZE_CONFIG.very_high_confidence - currentSamples);
    needsMoreSamples = true;
  }

  return {
    needs_more_samples: needsMoreSamples,
    recommended_additional: Math.max(0, recommendedAdditional),
    confidence_level: confidenceLevel,
    std_error,
    reason: needsMoreSamples
      ? `Standard error ${std_error.toFixed(3)} indicates ${confidenceLevel} confidence. Recommend ${recommendedAdditional} more samples.`
      : `Standard error ${std_error.toFixed(3)} indicates ${confidenceLevel} confidence. No additional samples needed.`,
  };
}

// ============================================================================
// WEIGHTED VOTING INTEGRATION
// ============================================================================

/**
 * Calculate confidence intervals for weighted voting result
 *
 * Calculates bootstrap CI for:
 * 1. Winner total weight
 * 2. Runner-up total weight
 * 3. Consensus strength (winner weight / total weight)
 * 4. Detects statistical ties
 * 5. Recommends sample size
 *
 * @param {Array<Object>} votes - Votes with weight property (from weighted-voting.cjs)
 * @param {Object} votingResult - Result from weightedVoting() (from weighted-voting.cjs)
 * @param {Object} options - Bootstrap options
 * @returns {Object} Statistical significance analysis
 */
function analyzeStatisticalSignificance(votes, votingResult, options = {}) {
  if (!votingResult || votingResult.status !== 'success') {
    return {
      status: 'error',
      error: 'invalid_voting_result',
      message: 'Voting result is missing or has error status',
    };
  }

  const { winner, runner_up } = votingResult;

  // Group votes by answer for bootstrap sampling
  const winnerVotes = votes.filter(v => JSON.stringify(v.answer) === JSON.stringify(winner.answer));
  const runnerUpVotes = runner_up ? votes.filter(v => JSON.stringify(v.answer) === JSON.stringify(runner_up.answer)) : [];

  // Statistic: sum of weights
  const sumWeights = (voteArray) => voteArray.reduce((sum, v) => sum + v.weight, 0);

  // Bootstrap CI for winner weight
  const winnerCI = bootstrapCI(winnerVotes, sumWeights, options);

  // Bootstrap CI for runner-up weight (if exists)
  const runnerUpCI = runnerUpVotes.length > 0
    ? bootstrapCI(runnerUpVotes, sumWeights, options)
    : null;

  // Bootstrap CI for consensus strength (winner weight / total weight)
  const totalWeight = votes.reduce((sum, v) => sum + v.weight, 0);
  const consensusStrengthStatistic = (voteArray) => {
    const winnerWeight = sumWeights(voteArray.filter(v => JSON.stringify(v.answer) === JSON.stringify(winner.answer)));
    return winnerWeight / totalWeight;
  };

  const consensusStrengthCI = bootstrapCI(votes, consensusStrengthStatistic, options);

  // Detect statistical tie
  const tieAnalysis = detectStatisticalTie(winnerCI, runnerUpCI);

  // Recommend sample size
  const sampleSizeRecommendation = recommendSampleSize(winnerCI, votes.length);

  return {
    status: 'success',

    // Winner confidence interval
    winner_ci: {
      estimate: winnerCI.estimate,
      ci_lower: winnerCI.ci_lower,
      ci_upper: winnerCI.ci_upper,
      std_error: winnerCI.std_error,
      confidence_level: winnerCI.confidence_level,
      iterations: winnerCI.iterations,
      warning: winnerCI.warning,
      message: winnerCI.message,
    },

    // Runner-up confidence interval (if exists)
    runner_up_ci: runnerUpCI ? {
      estimate: runnerUpCI.estimate,
      ci_lower: runnerUpCI.ci_lower,
      ci_upper: runnerUpCI.ci_upper,
      std_error: runnerUpCI.std_error,
      confidence_level: runnerUpCI.confidence_level,
      iterations: runnerUpCI.iterations,
      warning: runnerUpCI.warning,
      message: runnerUpCI.message,
    } : null,

    // Consensus strength CI
    consensus_strength_ci: {
      estimate: consensusStrengthCI.estimate,
      ci_lower: consensusStrengthCI.ci_lower,
      ci_upper: consensusStrengthCI.ci_upper,
      std_error: consensusStrengthCI.std_error,
      confidence_level: consensusStrengthCI.confidence_level,
      iterations: consensusStrengthCI.iterations,
      warning: consensusStrengthCI.warning,
      message: consensusStrengthCI.message,
    },

    // Statistical tie detection
    tie_analysis: tieAnalysis,

    // Sample size recommendation
    sample_size_recommendation: sampleSizeRecommendation,

    // Metadata
    metadata: {
      total_votes: votes.length,
      winner_votes: winnerVotes.length,
      runner_up_votes: runnerUpVotes.length,
      bootstrap_config: {
        iterations: options.iterations || BOOTSTRAP_CONFIG.iterations,
        confidence_level: options.confidence_level || BOOTSTRAP_CONFIG.confidence_level,
        sample_fraction: options.sample_fraction || BOOTSTRAP_CONFIG.sample_fraction,
      },
    },
  };
}

/**
 * Format statistical significance result for logging/display
 *
 * @param {Object} sigResult - Result from analyzeStatisticalSignificance()
 * @returns {string} Formatted string
 */
function formatStatisticalSignificance(sigResult) {
  if (sigResult.status !== 'success') {
    return `Statistical Significance: ERROR - ${sigResult.message}`;
  }

  const { winner_ci, runner_up_ci, consensus_strength_ci, tie_analysis, sample_size_recommendation } = sigResult;

  let output = `STATISTICAL SIGNIFICANCE ANALYSIS\n`;
  output += `${'='.repeat(70)}\n\n`;

  // Winner CI
  output += `Winner Weight:\n`;
  output += `  Estimate: ${winner_ci.estimate.toFixed(3)}\n`;
  output += `  95% CI: [${winner_ci.ci_lower.toFixed(3)}, ${winner_ci.ci_upper.toFixed(3)}]\n`;
  output += `  Std Error: ${winner_ci.std_error.toFixed(3)}\n`;
  if (winner_ci.warning) {
    output += `  ⚠️ Warning: ${winner_ci.message}\n`;
  }
  output += `\n`;

  // Runner-up CI (if exists)
  if (runner_up_ci) {
    output += `Runner-up Weight:\n`;
    output += `  Estimate: ${runner_up_ci.estimate.toFixed(3)}\n`;
    output += `  95% CI: [${runner_up_ci.ci_lower.toFixed(3)}, ${runner_up_ci.ci_upper.toFixed(3)}]\n`;
    output += `  Std Error: ${runner_up_ci.std_error.toFixed(3)}\n`;
    if (runner_up_ci.warning) {
      output += `  ⚠️ Warning: ${runner_up_ci.message}\n`;
    }
    output += `\n`;
  }

  // Consensus strength CI
  output += `Consensus Strength:\n`;
  output += `  Estimate: ${(consensus_strength_ci.estimate * 100).toFixed(1)}%\n`;
  output += `  95% CI: [${(consensus_strength_ci.ci_lower * 100).toFixed(1)}%, ${(consensus_strength_ci.ci_upper * 100).toFixed(1)}%]\n`;
  output += `  Std Error: ${(consensus_strength_ci.std_error * 100).toFixed(1)}%\n`;
  if (consensus_strength_ci.warning) {
    output += `  ⚠️ Warning: ${consensus_strength_ci.message}\n`;
  }
  output += `\n`;

  // Statistical tie detection
  output += `Statistical Tie Detection:\n`;
  output += `  Is Tie: ${tie_analysis.is_tie ? '⚠️ YES' : 'NO'}\n`;

  // Only show margin/overlap if they exist (runner-up present)
  if (tie_analysis.margin_percent !== undefined) {
    output += `  Margin: ${tie_analysis.margin_percent.toFixed(1)}% (threshold: ${TIE_THRESHOLDS.margin_percent}%)\n`;
  }
  if (tie_analysis.ci_overlap_percent !== undefined) {
    output += `  CI Overlap: ${tie_analysis.ci_overlap_percent.toFixed(1)}% (threshold: ${TIE_THRESHOLDS.min_ci_overlap * 100}%)\n`;
  }

  output += `  Reason: ${tie_analysis.reason}\n`;
  output += `\n`;

  // Sample size recommendation
  output += `Sample Size Recommendation:\n`;
  output += `  Current Samples: ${sigResult.metadata.total_votes}\n`;
  output += `  Confidence Level: ${sample_size_recommendation.confidence_level.toUpperCase()}\n`;
  output += `  Needs More Samples: ${sample_size_recommendation.needs_more_samples ? 'YES' : 'NO'}\n`;
  if (sample_size_recommendation.needs_more_samples) {
    output += `  Recommended Additional: ${sample_size_recommendation.recommended_additional}\n`;
  }
  output += `  Reason: ${sample_size_recommendation.reason}\n`;
  output += `\n`;

  output += `${'='.repeat(70)}\n`;

  return output;
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  analyzeStatisticalSignificance,
  formatStatisticalSignificance,

  // Bootstrap functions
  bootstrapSample,
  bootstrapCI,

  // Statistical tie detection
  detectStatisticalTie,

  // Sample size recommendations
  recommendSampleSize,

  // Configuration (export for customization)
  BOOTSTRAP_CONFIG,
  TIE_THRESHOLDS,
  SAMPLE_SIZE_CONFIG,
};
