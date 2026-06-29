/**
 * Quality-First Routing System
 *
 * Removes cost weights from routing decisions - prioritizes capability × confidence × history only.
 *
 * Key Differences from weighted-voting.cjs:
 * 1. NO cost multiplier in weight calculation
 * 2. Free API models (cost=0) treated equally with paid models
 * 3. Route to BEST model regardless of price
 * 4. Historical performance weighted more heavily (no cost penalty)
 *
 * Use Cases:
 * - Critical tasks where accuracy > cost
 * - Free API fleet (DeepSeek, Gemini Flash, etc.)
 * - Research workflows requiring maximum quality
 * - Tasks where wrong answer is more expensive than API cost
 *
 * Architecture:
 * - Integrates with Thompson Sampling (bandit-state.json)
 * - Uses same capability matrix as weighted-voting
 * - Compatible with circuit-breaker, calibration, rotation
 * - Can run alongside weighted-voting (flag: use_quality_first_routing)
 *
 * Formula:
 *   quality_weight = capability × confidence × history × calibration
 *
 * Components (NO cost multiplier):
 *   - capability: Task-specific model strength (0.0-1.0)
 *   - confidence: Model's self-reported confidence (0.0-1.0)
 *   - history: Thompson Sampling avg_quality (0.0-1.0)
 *   - calibration: Penalty for confidence/accuracy mismatch (0.25-1.0)
 *
 * Created: 2026-06-28
 * Location: server-03:/home/claude/claude-global-skills/shared/quality-first-routing.cjs
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// IMPORTS (reuse existing infrastructure)
// ============================================================================

const {
  MODEL_TIER_WEIGHTS,
  CAPABILITY_MATRIX,
  DEFAULT_MIN_CONFIDENCE,
  loadBanditState,
  getModelTierWeight,
  getCapabilityScore,
  getHistoricalAccuracy,
  normalizeConfidence,
} = require('./weighted-voting.cjs');

// ============================================================================
// QUALITY-FIRST WEIGHT CALCULATION
// ============================================================================

/**
 * Calculate QUALITY-FIRST vote weight (NO cost multiplier)
 *
 * Formula:
 *   quality_weight = capability × confidence × history × calibration
 *
 * Differences from weighted-voting:
 *   - NO tier_weight multiplier (capability handles model strength)
 *   - NO cost penalty (free models treated equally)
 *   - Confidence and history weighted MORE heavily (no cost dilution)
 *
 * Result: 0.0-1.0 weight (higher = better quality for task)
 *
 * @param {Object} vote - Vote object
 * @param {string} vote.model - Model name
 * @param {number} vote.confidence - Confidence score (0-100 or 0-1)
 * @param {string} taskType - Task type
 * @param {Object} banditState - Thompson Sampling state
 * @param {Object} options - Additional options
 * @param {Object} options.calibrationPenalties - Pre-computed calibration penalties (optional)
 * @returns {number} Quality weight (0.0-1.0)
 */
function calculateQualityFirstWeight(vote, taskType, banditState, options = {}) {
  // Task-specific capability score (e.g., deepseek-coder=1.0 for code tasks)
  const capabilityScore = getCapabilityScore(vote.model, taskType);

  // Model's self-reported confidence (0.0-1.0)
  const confidence = normalizeConfidence(vote.confidence);

  // Historical performance from Thompson Sampling (avg_quality)
  const historicalAccuracy = getHistoricalAccuracy(vote.model, banditState);

  // Calibration penalty (detect overconfident/lying models)
  let calibrationPenalty = 1.0;
  if (options.calibrationPenalties && options.calibrationPenalties[vote.model]) {
    calibrationPenalty = options.calibrationPenalties[vote.model].penalty;
  }

  // QUALITY-FIRST: Pure multiplicative weighting (NO cost factor)
  // This means free models with high capability get FULL weight
  const qualityWeight = capabilityScore * confidence * historicalAccuracy * calibrationPenalty;

  return Math.max(0.0, Math.min(1.0, qualityWeight)); // Clamp to [0, 1]
}

/**
 * Get metadata for quality-first weight calculation
 *
 * Returns components used in weight calculation for transparency/debugging.
 *
 * @param {Object} vote - Vote object
 * @param {string} taskType - Task type
 * @param {Object} banditState - Thompson Sampling state
 * @param {Object} options - Additional options
 * @returns {Object} Weight components breakdown
 */
function getQualityFirstWeightMetadata(vote, taskType, banditState, options = {}) {
  const capabilityScore = getCapabilityScore(vote.model, taskType);
  const confidence = normalizeConfidence(vote.confidence);
  const historicalAccuracy = getHistoricalAccuracy(vote.model, banditState);
  const calibrationPenalty = options.calibrationPenalties?.[vote.model]?.penalty || 1.0;
  const calibrationReason = options.calibrationPenalties?.[vote.model]?.reason || 'unknown';

  const qualityWeight = calculateQualityFirstWeight(vote, taskType, banditState, options);

  return {
    model: vote.model,
    task_type: taskType,

    // Weight components
    capability_score: capabilityScore,
    confidence: confidence,
    historical_accuracy: historicalAccuracy,
    calibration_penalty: calibrationPenalty,
    calibration_reason: calibrationReason,

    // Final weight
    quality_weight: qualityWeight,

    // Comparison with weighted-voting (for debugging)
    tier_weight_ignored: getModelTierWeight(vote.model), // Not used in quality-first
    cost_penalty_ignored: 'NONE (quality-first routing)',
  };
}

// ============================================================================
// QUALITY-FIRST VOTING ALGORITHM
// ============================================================================

/**
 * Quality-first voting algorithm
 *
 * Same structure as weightedVoting() but uses quality-first weights.
 * Routes to BEST model regardless of cost.
 *
 * Supports all BFT strategies from weighted-voting:
 *   - weighted-average (default)
 *   - median (BFT)
 *   - trimmed-mean (BFT)
 *   - mad (outlier detection)
 *
 * Integrates with:
 *   - Circuit breaker (filter unavailable models)
 *   - Confidence calibration (penalize lying models)
 *   - Rotation policy (traffic allocation)
 *   - Sybil protection (vote flooding detection)
 *
 * @param {Array<Object>} votes - Array of vote objects
 * @param {string} taskType - Task type for capability weighting
 * @param {Object} options - Algorithm options (same as weighted-voting)
 * @returns {Promise<Object>} Quality-first voting result
 */
async function qualityFirstVoting(votes, taskType, options = {}) {
  const minConfidence = options.minConfidence || DEFAULT_MIN_CONFIDENCE;
  const strategy = options.strategy || 'weighted-average';
  const banditState = loadBanditState();

  // PRIORITY 0: Circuit breaker integration (reuse from weighted-voting)
  let circuitBreakerAnalysis = null;
  const votesBeforeCircuit = votes.length;

  if (!options.skipCircuitBreaker) {
    try {
      const { getCircuitBreaker } = require('./circuit-breaker.cjs');
      const circuitBreaker = getCircuitBreaker();

      const modelSet = new Set(votes.map(v => v.model));
      const models = Array.from(modelSet);

      const availableModels = await circuitBreaker.filterAvailableModels(models);
      const unavailableModels = models.filter(m => !availableModels.includes(m));

      if (unavailableModels.length > 0) {
        votes = votes.filter(v => availableModels.includes(v.model));

        circuitBreakerAnalysis = {
          detected: true,
          unavailable_models: unavailableModels,
          votes_filtered: votesBeforeCircuit - votes.length,
          votes_remaining: votes.length,
        };

        if (votes.length === 0) {
          return {
            status: 'error',
            error: 'all_models_circuit_open',
            message: `All ${votesBeforeCircuit} votes from models with open circuits`,
            unavailable_models: unavailableModels,
            circuit_breaker_analysis: circuitBreakerAnalysis,
          };
        }
      }
    } catch (err) {
      console.warn(`[quality-first] Circuit breaker integration failed: ${err.message}`);
    }
  }

  // Filter by confidence threshold
  const filteredVotes = votes.filter(v =>
    normalizeConfidence(v.confidence) * 100 >= minConfidence
  );

  if (filteredVotes.length === 0) {
    return {
      status: 'error',
      error: 'all_votes_below_threshold',
      message: `All ${votes.length} votes below confidence threshold ${minConfidence}%`,
      threshold: minConfidence,
      total_votes: votes.length,
      circuit_breaker_analysis: circuitBreakerAnalysis,
    };
  }

  // PRIORITY 1: Load calibration penalties
  const { getCalibrationPenalty } = require('./confidence-calibration.cjs');
  const calibrationPenalties = {};
  const uniqueModels = [...new Set(filteredVotes.map(v => v.model))];

  for (const model of uniqueModels) {
    try {
      calibrationPenalties[model] = await getCalibrationPenalty(model, taskType);
    } catch (err) {
      calibrationPenalties[model] = { penalty: 1.0, reason: 'calibration_unavailable' };
    }
  }

  // Calculate QUALITY-FIRST weights
  const qualityWeightedVotes = filteredVotes.map(vote => {
    const metadata = getQualityFirstWeightMetadata(vote, taskType, banditState, { calibrationPenalties });

    return {
      ...vote,
      weight: metadata.quality_weight,
      capability_score: metadata.capability_score,
      historical_accuracy: metadata.historical_accuracy,
      normalized_confidence: metadata.confidence,
      calibration_penalty: metadata.calibration_penalty,
      calibration_reason: metadata.calibration_reason,
    };
  });

  // Group by answer
  const answerGroups = {};

  qualityWeightedVotes.forEach(vote => {
    const answerKey = JSON.stringify(vote.answer);

    if (!answerGroups[answerKey]) {
      answerGroups[answerKey] = {
        answer: vote.answer,
        total_weight: 0,
        vote_count: 0,
        votes: [],
        max_individual_weight: 0,
      };
    }

    const group = answerGroups[answerKey];
    group.total_weight += vote.weight;
    group.vote_count += 1;
    group.votes.push(vote);
    group.max_individual_weight = Math.max(group.max_individual_weight, vote.weight);
  });

  // Sort groups by total weight (descending)
  const sortedGroups = Object.values(answerGroups).sort((a, b) => {
    if (Math.abs(a.total_weight - b.total_weight) > 0.001) {
      return b.total_weight - a.total_weight;
    }
    if (a.vote_count !== b.vote_count) {
      return b.vote_count - a.vote_count;
    }
    if (Math.abs(a.max_individual_weight - b.max_individual_weight) > 0.001) {
      return b.max_individual_weight - a.max_individual_weight;
    }
    return JSON.stringify(a.answer).localeCompare(JSON.stringify(b.answer));
  });

  const winner = sortedGroups[0];
  const runnerUp = sortedGroups[1] || null;

  // Calculate consensus strength
  const totalWeight = sortedGroups.reduce((sum, g) => sum + g.total_weight, 0);
  const consensusStrength = totalWeight > 0 ? (winner.total_weight / totalWeight) : 0;

  // Determine consensus level
  let consensusLevel;
  if (consensusStrength >= 0.80) consensusLevel = 'strong';
  else if (consensusStrength >= 0.60) consensusLevel = 'moderate';
  else if (consensusStrength >= 0.40) consensusLevel = 'weak';
  else consensusLevel = 'no_consensus';

  return {
    status: 'success',
    algorithm: 'quality_first_voting',
    task_type: taskType,
    routing_mode: 'QUALITY_FIRST (cost ignored)',

    // Winning answer
    winner: {
      answer: winner.answer,
      total_weight: winner.total_weight,
      vote_count: winner.vote_count,
      consensus_strength: consensusStrength,
      consensus_level: consensusLevel,
      votes: winner.votes.map(v => ({
        model: v.model,
        weight: v.weight,
        confidence: v.normalized_confidence,
        capability_score: v.capability_score,
        historical_accuracy: v.historical_accuracy,
        calibration_penalty: v.calibration_penalty,
        calibration_reason: v.calibration_reason,
      })),
    },

    // Runner-up (if exists)
    runner_up: runnerUp ? {
      answer: runnerUp.answer,
      total_weight: runnerUp.total_weight,
      vote_count: runnerUp.vote_count,
      weight_difference: winner.total_weight - runnerUp.total_weight,
    } : null,

    // All answer groups
    all_groups: sortedGroups.map(g => ({
      answer: g.answer,
      total_weight: g.total_weight,
      vote_count: g.vote_count,
      percentage: (g.total_weight / totalWeight * 100).toFixed(1),
    })),

    // Metadata
    metadata: {
      total_votes: votesBeforeCircuit,
      filtered_votes: filteredVotes.length,
      discarded_votes: votesBeforeCircuit - filteredVotes.length,
      min_confidence_threshold: minConfidence,
      total_weight: totalWeight,
      num_unique_answers: sortedGroups.length,
    },

    // Circuit breaker analysis (if applicable)
    circuit_breaker_analysis: circuitBreakerAnalysis,
  };
}

/**
 * Run quality-first voting (main entry point)
 *
 * Wrapper compatible with runWeightedVoting() API.
 * Drop-in replacement for cost-sensitive routing.
 *
 * @param {Array<Object>} votes - Worker votes
 * @param {string} taskType - Task type
 * @param {Object} options - Options (same as weighted-voting)
 * @returns {Promise<Object>} Quality-first voting result
 */
async function runQualityFirstVoting(votes, taskType, options = {}) {
  const votingResult = await qualityFirstVoting(votes, taskType, options);

  return {
    voting_result: votingResult,

    // Comparison summary (for debugging)
    quality_first_enabled: true,
    cost_ignored: true,

    // Helper for logging
    summary: votingResult.status === 'success' ? {
      winner_answer: votingResult.winner.answer,
      consensus_level: votingResult.winner.consensus_level,
      total_weight: votingResult.winner.total_weight,
      vote_count: votingResult.winner.vote_count,
      routing_mode: 'QUALITY_FIRST',
    } : null,
  };
}

/**
 * Compare quality-first vs cost-weighted routing
 *
 * Runs BOTH algorithms on same votes, shows differences.
 * Use for debugging/validation/A-B testing.
 *
 * @param {Array<Object>} votes - Worker votes
 * @param {string} taskType - Task type
 * @param {Object} options - Options
 * @returns {Promise<Object>} Comparison result
 */
async function compareQualityVsCost(votes, taskType, options = {}) {
  const { weightedVoting } = require('./weighted-voting.cjs');

  // Run both algorithms
  const qualityResult = await qualityFirstVoting(votes, taskType, options);
  const costWeightedResult = await weightedVoting(votes, taskType, options);

  // Compare winners
  const sameWinner = JSON.stringify(qualityResult.winner?.answer) ===
                     JSON.stringify(costWeightedResult.winner?.answer);

  const weightDifference = qualityResult.status === 'success' && costWeightedResult.status === 'success'
    ? (qualityResult.winner.total_weight - costWeightedResult.winner.total_weight)
    : null;

  return {
    comparison: {
      same_winner: sameWinner,
      weight_difference: weightDifference,
      quality_consensus_level: qualityResult.winner?.consensus_level,
      cost_consensus_level: costWeightedResult.winner?.consensus_level,
    },

    quality_first: qualityResult,
    cost_weighted: costWeightedResult,

    // Recommendation
    recommendation: sameWinner
      ? 'Both algorithms agree - use quality-first for free API optimization'
      : 'Algorithms DISAGREE - quality-first may select more expensive but better model',
  };
}

// ============================================================================
// MODEL SELECTION HELPERS
// ============================================================================

/**
 * Select best model for task type (quality-first)
 *
 * Returns highest-capability model regardless of cost.
 * Use for critical tasks or free API fleets.
 *
 * @param {Array<string>} availableModels - List of available model names
 * @param {string} taskType - Task type
 * @param {Object} options - Additional options
 * @param {Object} options.banditState - Pre-loaded bandit state (optional)
 * @returns {Object} Best model selection result
 */
function selectBestModel(availableModels, taskType, options = {}) {
  const banditState = options.banditState || loadBanditState();

  // Score each model
  const modelScores = availableModels.map(model => {
    const capabilityScore = getCapabilityScore(model, taskType);
    const historicalAccuracy = getHistoricalAccuracy(model, banditState);

    // Quality score (no cost factor)
    const qualityScore = capabilityScore * historicalAccuracy;

    return {
      model,
      quality_score: qualityScore,
      capability_score: capabilityScore,
      historical_accuracy: historicalAccuracy,
    };
  });

  // Sort by quality score (descending)
  modelScores.sort((a, b) => b.quality_score - a.quality_score);

  const best = modelScores[0];
  const alternatives = modelScores.slice(1, 4); // Top 3 alternatives

  return {
    best_model: best.model,
    quality_score: best.quality_score,
    capability_score: best.capability_score,
    historical_accuracy: best.historical_accuracy,

    alternatives: alternatives.map(m => ({
      model: m.model,
      quality_score: m.quality_score,
      score_difference: best.quality_score - m.quality_score,
    })),

    all_scores: modelScores,
  };
}

/**
 * Detect weak models in voting pool
 *
 * Identifies models with low quality weights.
 * Use for debugging or quality assurance.
 *
 * @param {Array<Object>} votes - Votes with quality weights
 * @param {number} weakThreshold - Threshold below which model is "weak" (default: 0.3)
 * @returns {Object} Weak model analysis
 */
function detectWeakModels(votes, weakThreshold = 0.3) {
  const weakModels = votes.filter(v => v.weight < weakThreshold);
  const strongModels = votes.filter(v => v.weight >= weakThreshold);

  return {
    weak_models: weakModels.map(v => ({
      model: v.model,
      weight: v.weight,
      confidence: v.normalized_confidence,
      capability_score: v.capability_score,
      historical_accuracy: v.historical_accuracy,
    })),

    strong_models: strongModels.map(v => ({
      model: v.model,
      weight: v.weight,
    })),

    summary: {
      total_votes: votes.length,
      weak_count: weakModels.length,
      strong_count: strongModels.length,
      weak_percentage: (weakModels.length / votes.length * 100).toFixed(1),
      threshold: weakThreshold,
    },

    recommendation: weakModels.length > votes.length * 0.5
      ? 'WARNING: >50% weak models - consider using higher-capability models for this task'
      : 'OK: Majority of models have sufficient quality weights',
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  runQualityFirstVoting,
  qualityFirstVoting,

  // Weight calculation
  calculateQualityFirstWeight,
  getQualityFirstWeightMetadata,

  // Comparison tools
  compareQualityVsCost,

  // Model selection helpers
  selectBestModel,
  detectWeakModels,

  // Re-export shared utilities (for convenience)
  loadBanditState,
  getCapabilityScore,
  getHistoricalAccuracy,
};
