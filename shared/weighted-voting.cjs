/**
 * Weighted Voting System for Multi-AI Consensus
 *
 * Prevents naive vote counting by weighting votes based on:
 * 1. Model capability score for task type (from capability matrix)
 * 2. Model confidence score (from response metadata)
 * 3. Historical accuracy on similar tasks (Thompson Sampling)
 * 4. Model size/tier (opus > sonnet > haiku)
 *
 * Architecture:
 * - Integrates with existing arbiter pattern
 * - Uses Thompson Sampling from bandit-state.json
 * - Stores vote weights in PostgreSQL for audit trail
 * - Handles edge cases gracefully
 *
 * Example:
 *   30 weak models (haiku) vote "A" with 50% confidence
 *   5 strong models (opus) vote "B" with 90% confidence
 *   Result: "B" wins (weighted votes: B=45, A=15)
 *
 * Created: 2026-06-28
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Model tier weights (base multiplier for model capability)
 * Based on parameter count and training quality
 */
const MODEL_TIER_WEIGHTS = {
  // Claude models (Anthropic)
  'opus': 1.0,        // Highest capability, 175B+ params
  'sonnet': 0.85,     // High capability, balanced
  'haiku': 0.60,      // Fast but lower capability
  'fable': 0.95,      // Near-opus quality

  // OpenAI models
  'gpt-4o': 0.95,     // GPT-4 level
  'gpt-4': 0.95,
  'gpt-3.5-turbo': 0.70,

  // Google models
  'gemini': 0.90,     // Gemini 1.5 Pro level
  'gemini-pro': 0.90,
  'gemini-flash': 0.75,

  // Local models (Ollama)
  'deepseek-coder': 0.70,     // Specialized code model
  'phi-4-mini': 0.50,         // Fast routing
  'mistral-7b': 0.65,         // Local arbiter
  'llama3': 0.70,
  'codellama': 0.70,

  // Fallback for unknown models
  'default': 0.60,
};

/**
 * Task type capability matrix
 * Maps task types to model strengths (0.0-1.0 multiplier)
 */
const CAPABILITY_MATRIX = {
  // Code tasks
  'code_generation': {
    'opus': 0.95, 'sonnet': 0.90, 'haiku': 0.70, 'fable': 0.92,
    'gpt-4o': 0.90, 'gemini': 0.85,
    'deepseek-coder': 1.0,  // Specialized
    'codellama': 0.85,
  },
  'code_review': {
    'opus': 0.95, 'sonnet': 0.92, 'haiku': 0.75, 'fable': 0.93,
    'gpt-4o': 0.90, 'gemini': 0.85,
    'deepseek-coder': 0.90,
  },
  'bug_detection': {
    'opus': 0.90, 'sonnet': 0.88, 'haiku': 0.70, 'fable': 0.92,
    'gpt-4o': 0.85, 'gemini': 0.80,
  },

  // Analysis tasks
  'security_audit': {
    'opus': 0.95, 'sonnet': 0.90, 'haiku': 0.65, 'fable': 0.93,
    'gpt-4o': 0.90, 'gemini': 0.85,
  },
  'architecture_review': {
    'opus': 0.95, 'sonnet': 0.85, 'haiku': 0.60, 'fable': 0.92,
    'gpt-4o': 0.90, 'gemini': 0.85,
  },

  // Research tasks
  'research': {
    'opus': 0.90, 'sonnet': 0.85, 'haiku': 0.70, 'fable': 0.88,
    'gpt-4o': 0.90, 'gemini': 0.88,
  },
  'fact_checking': {
    'opus': 0.90, 'sonnet': 0.88, 'haiku': 0.75, 'fable': 0.90,
    'gpt-4o': 0.92, 'gemini': 0.90,
  },

  // Consensus/arbiter tasks
  'consensus': {
    'opus': 0.95, 'sonnet': 0.92, 'haiku': 0.70, 'fable': 0.95,
    'gpt-4o': 0.90, 'gemini': 0.88,
    'mistral-7b': 0.75,  // Local arbiter
  },
  'routing': {
    'phi-4-mini': 1.0,  // Specialized for fast routing
    'opus': 0.80, 'sonnet': 0.78, 'haiku': 0.70, 'fable': 0.82,
  },

  // General tasks (fallback)
  'general': {
    'opus': 0.90, 'sonnet': 0.85, 'haiku': 0.70, 'fable': 0.88,
    'gpt-4o': 0.88, 'gemini': 0.85,
  },
};

/**
 * Minimum confidence threshold
 * Votes below this confidence are discarded (configurable)
 */
const DEFAULT_MIN_CONFIDENCE = 20; // 0-100 scale

/**
 * Thompson Sampling state path
 */
const BANDIT_STATE_PATH = path.join(
  process.env.HOME,
  '.claude',
  'learning',
  'bandit-state.json'
);

// ============================================================================
// THOMPSON SAMPLING INTEGRATION
// ============================================================================

/**
 * Load Thompson Sampling state from bandit-state.json
 * @returns {Object} Bandit state with model performance data
 */
function loadBanditState() {
  try {
    if (fs.existsSync(BANDIT_STATE_PATH)) {
      const data = fs.readFileSync(BANDIT_STATE_PATH, 'utf8');
      return JSON.parse(data);
    }
  } catch (err) {
    console.warn(`Could not load bandit state: ${err.message}`);
  }

  // Return default state if file missing
  return {
    version: 1,
    models: {},
    updated: new Date().toISOString(),
  };
}

/**
 * Get historical accuracy for a model from Thompson Sampling
 * Uses avg_quality as proxy for accuracy
 * @param {string} model - Model name
 * @param {Object} banditState - Loaded bandit state
 * @returns {number} Accuracy score (0.0-1.0)
 */
function getHistoricalAccuracy(model, banditState) {
  const modelData = banditState.models?.[model];

  if (!modelData || modelData.total === 0) {
    // No historical data - return neutral 0.5
    return 0.5;
  }

  // avg_quality from Thompson Sampling (0.0-1.0)
  return modelData.avg_quality || 0.5;
}

// ============================================================================
// WEIGHT CALCULATION
// ============================================================================

/**
 * Get model tier weight (base capability)
 * @param {string} model - Model name
 * @returns {number} Tier weight (0.0-1.0)
 */
function getModelTierWeight(model) {
  // Normalize model name (remove version suffixes)
  const baseModel = model.toLowerCase().split(':')[0].split('-')[0];

  // Check exact match first
  if (MODEL_TIER_WEIGHTS[model]) {
    return MODEL_TIER_WEIGHTS[model];
  }

  // Check base model
  if (MODEL_TIER_WEIGHTS[baseModel]) {
    return MODEL_TIER_WEIGHTS[baseModel];
  }

  // Fallback to default
  return MODEL_TIER_WEIGHTS.default;
}

/**
 * Get capability score for task type
 * @param {string} model - Model name
 * @param {string} taskType - Task type (code_review, security_audit, etc.)
 * @returns {number} Capability score (0.0-1.0)
 */
function getCapabilityScore(model, taskType) {
  const taskMatrix = CAPABILITY_MATRIX[taskType] || CAPABILITY_MATRIX.general;

  // Check exact match
  if (taskMatrix[model]) {
    return taskMatrix[model];
  }

  // Check base model name
  const baseModel = model.toLowerCase().split(':')[0].split('-')[0];
  if (taskMatrix[baseModel]) {
    return taskMatrix[baseModel];
  }

  // Fallback to tier weight
  return getModelTierWeight(model);
}

/**
 * Normalize confidence score to 0.0-1.0 range
 * Handles various input formats (0-1, 0-100, null, undefined)
 * @param {number|null|undefined} confidence - Raw confidence value
 * @returns {number} Normalized confidence (0.0-1.0)
 */
function normalizeConfidence(confidence) {
  if (confidence === null || confidence === undefined || isNaN(confidence)) {
    return 0.5; // Neutral default
  }

  const conf = parseFloat(confidence);

  // If already in 0-1 range, return as-is
  if (conf >= 0 && conf <= 1.0) {
    return conf;
  }

  // If in 0-100 range, normalize
  if (conf >= 0 && conf <= 100) {
    return conf / 100.0;
  }

  // Invalid range - return neutral
  return 0.5;
}

/**
 * Calculate vote weight for a model's response
 *
 * Weight Formula:
 *   weight = tier_weight × capability_score × confidence × historical_accuracy × calibration_penalty
 *
 * Components:
 *   - tier_weight: Base model capability (opus=1.0, haiku=0.6)
 *   - capability_score: Task-specific strength (deepseek-coder=1.0 for code)
 *   - confidence: Model's self-reported confidence (0.0-1.0)
 *   - historical_accuracy: Thompson Sampling avg_quality (0.0-1.0)
 *   - calibration_penalty: Penalty for confidence/accuracy mismatch (0.25-1.0)
 *
 * Result: 0.0-1.0 weight (higher = more influence)
 *
 * @param {Object} vote - Vote object
 * @param {string} vote.model - Model name
 * @param {number} vote.confidence - Confidence score (0-100 or 0-1)
 * @param {string} taskType - Task type
 * @param {Object} banditState - Thompson Sampling state
 * @param {Object} options - Additional options
 * @param {Object} options.calibrationPenalties - Pre-computed calibration penalties (optional)
 * @returns {number} Vote weight (0.0-1.0)
 */
function calculateVoteWeight(vote, taskType, banditState, options = {}) {
  const tierWeight = getModelTierWeight(vote.model);
  const capabilityScore = getCapabilityScore(vote.model, taskType);
  const confidence = normalizeConfidence(vote.confidence);
  const historicalAccuracy = getHistoricalAccuracy(vote.model, banditState);

  // PRIORITY 1: Apply calibration penalty (detect lying models)
  let calibrationPenalty = 1.0;
  if (options.calibrationPenalties && options.calibrationPenalties[vote.model]) {
    calibrationPenalty = options.calibrationPenalties[vote.model].penalty;
  }

  // Multiplicative weighting with calibration penalty
  const weight = tierWeight * capabilityScore * confidence * historicalAccuracy * calibrationPenalty;

  return Math.max(0.0, Math.min(1.0, weight)); // Clamp to [0, 1]
}

// ============================================================================
// VOTING ALGORITHMS
// ============================================================================

/**
 * Calculate weighted median of confidence scores
 *
 * Byzantine Fault Tolerance (BFT) - resistant to outliers.
 * Returns the value where cumulative weight crosses 50% of total weight.
 *
 * @param {Array<Object>} votes - Votes with weight property
 * @param {string} field - Field to calculate median for (default: 'normalized_confidence')
 * @returns {number} Weighted median value
 */
function weightedMedian(votes, field = 'normalized_confidence') {
  if (!votes || votes.length === 0) {
    return 0.5; // Neutral default
  }

  if (votes.length === 1) {
    return votes[0][field];
  }

  // Sort by field value (ascending)
  const sorted = [...votes].sort((a, b) => a[field] - b[field]);

  // Calculate total weight
  const totalWeight = sorted.reduce((sum, v) => sum + v.weight, 0);

  if (totalWeight === 0) {
    return 0.5; // All zero weights - return neutral
  }

  // Find value where cumulative weight crosses 50%
  let cumWeight = 0;
  const halfWeight = totalWeight / 2;

  for (let i = 0; i < sorted.length; i++) {
    const prevCumWeight = cumWeight;
    cumWeight += sorted[i].weight;

    // Check if we crossed the median point
    if (cumWeight >= halfWeight) {
      // If we exactly hit 50%, interpolate between current and next
      if (cumWeight === halfWeight && i + 1 < sorted.length) {
        return (sorted[i][field] + sorted[i + 1][field]) / 2;
      }
      return sorted[i][field];
    }
  }

  // Fallback (shouldn't reach here)
  return sorted[Math.floor(sorted.length / 2)][field];
}

/**
 * Calculate trimmed mean (drop top/bottom percentiles)
 *
 * BFT strategy - removes extreme outliers before averaging.
 * Default: drop top 20% and bottom 20%, average middle 60%.
 *
 * @param {Array<Object>} votes - Votes with weight property
 * @param {string} field - Field to calculate trimmed mean for
 * @param {number} trimPercent - Percentage to trim from each end (0-50)
 * @returns {number} Trimmed mean value
 */
function trimmedMean(votes, field = 'normalized_confidence', trimPercent = 20) {
  if (!votes || votes.length === 0) {
    return 0.5; // Neutral default
  }

  if (votes.length === 1) {
    return votes[0][field];
  }

  if (votes.length <= 2) {
    // Too few votes to trim - use weighted average
    return weightedAverage(votes, field);
  }

  // Sort by field value
  const sorted = [...votes].sort((a, b) => a[field] - b[field]);

  // Calculate number of votes to drop from each end
  const trimCount = Math.floor(sorted.length * (trimPercent / 100));

  if (trimCount === 0) {
    // No trimming needed - use weighted average
    return weightedAverage(sorted, field);
  }

  // Keep middle votes only
  const trimmed = sorted.slice(trimCount, sorted.length - trimCount);

  if (trimmed.length === 0) {
    // Edge case: trimmed all votes - use median instead
    return weightedMedian(votes, field);
  }

  // Weighted average of trimmed votes
  return weightedAverage(trimmed, field);
}

/**
 * Calculate weighted average
 *
 * Standard mean-based approach (vulnerable to outliers).
 *
 * @param {Array<Object>} votes - Votes with weight property
 * @param {string} field - Field to average
 * @returns {number} Weighted average value
 */
function weightedAverage(votes, field = 'normalized_confidence') {
  if (!votes || votes.length === 0) {
    return 0.5; // Neutral default
  }

  const totalWeight = votes.reduce((sum, v) => sum + v.weight, 0);

  if (totalWeight === 0) {
    // All zero weights - simple average
    return votes.reduce((sum, v) => sum + v[field], 0) / votes.length;
  }

  return votes.reduce((sum, v) => sum + v.weight * v[field], 0) / totalWeight;
}

/**
 * Detect outliers using Median Absolute Deviation (MAD)
 *
 * BFT strategy - identifies faulty/broken models returning garbage.
 *
 * IMPORTANT: MAD detects faulty models (broken outputs), NOT wrong answers.
 * Legitimate disagreement (30%+ of votes) is NOT a failure - it's minority opinion.
 *
 * Algorithm:
 * 1. Calculate weighted median
 * 2. Calculate deviation of each vote from median
 * 3. Calculate median of deviations (MAD)
 * 4. Mark votes > threshold * MAD as outliers
 *
 * PRIORITY 3 SAFEGUARD: Never mark >30% of votes as outliers.
 * If >30% would be marked, return NO outliers (legitimate disagreement, not failures).
 *
 * Special cases:
 *   - MAD = 0 (all votes clustered): Use minimum absolute threshold (0.1)
 *   - MAD < 0.1: Ensure minimum threshold to avoid triggering on tiny variance
 *   - >30% outliers: Return empty outlier list (protect minority opinions)
 *
 * @param {Array<Object>} votes - Votes with weight property
 * @param {string} field - Field to detect outliers in
 * @param {number} threshold - MAD threshold multiplier (default: 3)
 * @returns {Object} { inliers: Array, outliers: Array, mad: number, median: number }
 */
function detectOutliersMAD(votes, field = 'normalized_confidence', threshold = 3) {
  if (!votes || votes.length === 0) {
    return { inliers: [], outliers: [], mad: 0, median: 0.5 };
  }

  if (votes.length === 1) {
    // Single vote - cannot be outlier
    return { inliers: votes, outliers: [], mad: 0, median: votes[0][field] };
  }

  // Calculate weighted median
  const median = weightedMedian(votes, field);

  // Calculate absolute deviations
  const deviations = votes.map(v => ({
    ...v,
    deviation: Math.abs(v[field] - median),
  }));

  // Calculate MAD (median of deviations)
  const mad = weightedMedian(deviations, 'deviation');

  // PRIORITY 3: Minimum MAD threshold (0.1) before outlier detection activates
  // This prevents MAD from triggering on tiny natural variance
  let madThreshold;

  if (mad === 0 || mad < 0.001) {
    // All votes clustered - use absolute threshold
    // Any vote >0.1 away from median is an outlier
    madThreshold = 0.1;
  } else if (mad < 0.1) {
    // MAD exists but very small - set minimum threshold to 0.1
    // This prevents overly aggressive outlier detection
    madThreshold = Math.max(0.1, threshold * mad);
  } else {
    // Standard MAD threshold
    madThreshold = threshold * mad;
  }

  // Classify as outlier if deviation > threshold
  const inliers = [];
  const outliers = [];

  deviations.forEach(v => {
    if (v.deviation <= madThreshold) {
      inliers.push(v);
    } else {
      outliers.push(v);
    }
  });

  // PRIORITY 3 SAFEGUARD: Never mark >30% as outliers
  // This protects legitimate minority expert opinions from being suppressed
  const outlierPercentage = outliers.length / votes.length;

  if (outlierPercentage > 0.3) {
    console.warn(
      `[MAD] Would mark ${outliers.length}/${votes.length} (${(outlierPercentage * 100).toFixed(1)}%) as outliers. ` +
      `This indicates legitimate disagreement, not failures. Returning NO outliers to protect minority opinions.`
    );

    return {
      inliers: votes,  // All votes are inliers
      outliers: [],    // No outliers
      mad,
      median,
      warning: 'high_disagreement',
      disagreement_percentage: outlierPercentage,
    };
  }

  return { inliers, outliers, mad, median };
}

/**
 * Weighted voting algorithm
 *
 * Groups votes by answer, sums weights per answer, picks highest total weight.
 * Ties broken by: 1) vote count, 2) max individual weight, 3) alphabetical
 *
 * NEW: Supports BFT strategies for outlier resistance.
 *
 * PRIORITY 1: Confidence calibration (detect lying models)
 * PRIORITY 2: Sybil attack protection (prevent vote flooding)
 * PRIORITY 3: MAD minority opinion protection (don't suppress dissent)
 *
 * @param {Array<Object>} votes - Array of vote objects
 * @param {string} taskType - Task type for capability weighting
 * @param {Object} options - Algorithm options
 * @param {number} options.minConfidence - Minimum confidence threshold (0-100)
 * @param {string} options.strategy - Voting strategy: 'weighted-average' (default), 'median', 'trimmed-mean', 'mad'
 * @param {number} options.trimPercent - Trim percentage for trimmed-mean (default: 20)
 * @param {number} options.madThreshold - MAD threshold multiplier for outlier detection (default: 3)
 * @param {number} options.familyCap - Max votes per model family (default: 5)
 * @param {number} options.familyFloodThreshold - Vote flooding threshold (default: 0.50 = 50%)
 * @returns {Object} Weighted voting result
 */
async function weightedVoting(votes, taskType, options = {}) {
  const minConfidence = options.minConfidence || DEFAULT_MIN_CONFIDENCE;
  const strategy = options.strategy || 'weighted-average';
  const trimPercent = options.trimPercent || 20;
  const madThreshold = options.madThreshold || 3;
  const familyCap = options.familyCap || 5;
  const familyFloodThreshold = options.familyFloodThreshold || 0.50;
  const banditState = loadBanditState();

  // PRIORITY 0: Filter out open-circuit models (circuit breaker integration)
  let circuitBreakerAnalysis = null;
  const votesBeforeCircuit = votes.length;

  if (!options.skipCircuitBreaker) {
    try {
      const { getCircuitBreaker } = require('./circuit-breaker.cjs');
      const circuitBreaker = getCircuitBreaker();

      // Get unique models from votes
      const modelSet = new Set(votes.map(v => v.model));
      const models = Array.from(modelSet);

      // Filter available models
      const availableModels = await circuitBreaker.filterAvailableModels(models);
      const unavailableModels = models.filter(m => !availableModels.includes(m));

      if (unavailableModels.length > 0) {
        // Filter votes to only include available models
        votes = votes.filter(v => availableModels.includes(v.model));

        circuitBreakerAnalysis = {
          detected: true,
          unavailable_models: unavailableModels,
          votes_filtered: votesBeforeCircuit - votes.length,
          votes_remaining: votes.length,
          warning: `Circuit breaker filtered ${unavailableModels.length} unavailable models: ${unavailableModels.join(', ')}`,
        };

        console.warn(`[weighted-voting] ${circuitBreakerAnalysis.warning}`);
        console.warn(`[weighted-voting] Votes filtered: ${votesBeforeCircuit} → ${votes.length}`);

        // If all votes filtered out, return error
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
      console.warn(`[weighted-voting] Circuit breaker integration failed: ${err.message}`);
      // Continue without circuit breaker (graceful degradation)
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

  // PRIORITY 1: Load calibration penalties for all models
  const { getCalibrationPenalty } = require('./confidence-calibration.cjs');
  const calibrationPenalties = {};
  const uniqueModels = [...new Set(filteredVotes.map(v => v.model))];

  for (const model of uniqueModels) {
    try {
      calibrationPenalties[model] = await getCalibrationPenalty(model, taskType);
    } catch (err) {
      console.warn(`[weighted-voting] Could not load calibration for ${model}: ${err.message}`);
      calibrationPenalties[model] = { penalty: 1.0, reason: 'calibration_unavailable' };
    }
  }

  // PRIORITY 2: Detect Sybil attack (vote flooding)
  const modelFamilies = {};
  filteredVotes.forEach(v => {
    // Extract model family (first part before '-' or ':')
    // Examples: 'opus-4' -> 'opus', 'gpt-4o' -> 'gpt', 'deepseek-coder:finetuned' -> 'deepseek'
    const family = v.model.toLowerCase().split(/[-:]/)[0];
    modelFamilies[family] = (modelFamilies[family] || 0) + 1;
  });

  // Check for vote flooding (>50% votes from same family)
  const maxFamilyCount = Math.max(...Object.values(modelFamilies));
  const maxFamilyName = Object.keys(modelFamilies).find(f => modelFamilies[f] === maxFamilyCount);
  const voteFloodingDetected = maxFamilyCount > filteredVotes.length * familyFloodThreshold;

  let sybilAnalysis = null;

  if (voteFloodingDetected) {
    sybilAnalysis = {
      detected: true,
      family: maxFamilyName,
      count: maxFamilyCount,
      total: filteredVotes.length,
      percentage: (maxFamilyCount / filteredVotes.length * 100).toFixed(1),
      threshold: (familyFloodThreshold * 100).toFixed(0),
      warning: `Vote flooding detected: ${maxFamilyCount}/${filteredVotes.length} votes from '${maxFamilyName}' family (>${familyFloodThreshold * 100}% threshold)`,
    };

    console.warn(`[weighted-voting] ${sybilAnalysis.warning}`);
    console.warn(`[weighted-voting] Applying family diversity normalization to prevent Sybil attack`);
  }

  // Calculate base weights for each vote
  const baseWeightedVotes = filteredVotes.map(vote => ({
    ...vote,
    weight: calculateVoteWeight(vote, taskType, banditState, { calibrationPenalties }),
    tier_weight: getModelTierWeight(vote.model),
    capability_score: getCapabilityScore(vote.model, taskType),
    historical_accuracy: getHistoricalAccuracy(vote.model, banditState),
    normalized_confidence: normalizeConfidence(vote.confidence),
    calibration_penalty: calibrationPenalties[vote.model]?.penalty || 1.0,
    calibration_reason: calibrationPenalties[vote.model]?.reason || 'unknown',
  }));

  // PRIORITY 2.5: Apply rotation policy (traffic allocation + exploration)
  let weightedVotes = baseWeightedVotes;
  let rotationAnalysis = null;

  if (!options.skipRotationPolicy) {
    try {
      const { applyRotationPolicy } = require('./model-rotation.cjs');
      const rotatedVotes = await applyRotationPolicy(baseWeightedVotes);

      // Update weights with rotation multipliers
      weightedVotes = rotatedVotes.map(v => ({
        ...v,
        base_weight: v.weight, // Store original weight
        weight: v.rotation_adjusted_weight, // Use rotation-adjusted weight
      }));

      // Track which models had rotation applied
      const modelsWithRotation = rotatedVotes.filter(v => v.rotation_multiplier < 1.0);

      if (modelsWithRotation.length > 0) {
        rotationAnalysis = {
          detected: true,
          models_affected: modelsWithRotation.length,
          models: modelsWithRotation.map(v => ({
            model: v.model,
            multiplier: v.rotation_multiplier,
            base_weight: v.base_weight,
            adjusted_weight: v.rotation_adjusted_weight,
          })),
        };

        console.log(
          `[weighted-voting] Rotation policy applied to ${modelsWithRotation.length} models`
        );
      }

    } catch (err) {
      console.warn(`[weighted-voting] Rotation policy integration failed: ${err.message}`);
      // Continue without rotation policy (graceful degradation)
    }
  }

  // PRIORITY 2: Apply family cap (cap votes per family to prevent flooding)
  let votesToUse = weightedVotes;

  if (voteFloodingDetected) {
    // Group votes by family
    const votesByFamily = {};
    weightedVotes.forEach(v => {
      const family = v.model.toLowerCase().split(/[-:]/)[0];
      if (!votesByFamily[family]) {
        votesByFamily[family] = [];
      }
      votesByFamily[family].push(v);
    });

    // Cap each family to familyCap votes (keep highest weights)
    votesToUse = [];
    Object.keys(votesByFamily).forEach(family => {
      const familyVotes = votesByFamily[family];

      if (familyVotes.length > familyCap) {
        // Sort by weight descending, keep top familyCap
        const capped = familyVotes.sort((a, b) => b.weight - a.weight).slice(0, familyCap);
        votesToUse.push(...capped);

        console.warn(
          `[weighted-voting] Family '${family}': ${familyVotes.length} votes capped to ${familyCap} (kept highest weights)`
        );
      } else {
        votesToUse.push(...familyVotes);
      }
    });

    sybilAnalysis.action_taken = `family_cap_applied`;
    sybilAnalysis.votes_before = weightedVotes.length;
    sybilAnalysis.votes_after = votesToUse.length;
    sybilAnalysis.votes_dropped = weightedVotes.length - votesToUse.length;
  }

  // BFT: Detect and filter outliers if MAD strategy enabled
  let bftOutliers = [];
  let bftAnalysis = null;

  if (strategy === 'mad') {
    const madResult = detectOutliersMAD(votesToUse, 'normalized_confidence', madThreshold);
    bftOutliers = madResult.outliers;
    votesToUse = madResult.inliers;

    bftAnalysis = {
      strategy: 'mad',
      median: madResult.median,
      mad: madResult.mad,
      threshold: madThreshold,
      outliers_detected: bftOutliers.length,
      outliers: bftOutliers.map(v => ({
        model: v.model,
        confidence: v.normalized_confidence,
        deviation: v.deviation,
        answer: v.answer,
      })),
    };

    // Check for MAD minority protection warning
    if (madResult.warning === 'high_disagreement') {
      bftAnalysis.warning = 'high_disagreement';
      bftAnalysis.disagreement_percentage = (madResult.disagreement_percentage * 100).toFixed(1);
      bftAnalysis.action_taken = 'minority_opinion_protected';
      console.warn(
        `[BFT-MAD] High disagreement (${bftAnalysis.disagreement_percentage}%) - ` +
        `Protected minority opinions from being suppressed as outliers`
      );
    }

    // Edge case: All votes marked as outliers
    if (votesToUse.length === 0) {
      console.warn(`BFT: All ${weightedVotes.length} votes marked as outliers (MAD threshold too strict). Using all votes.`);
      votesToUse = weightedVotes;
      bftAnalysis.warning = 'all_votes_outliers';
      bftAnalysis.action_taken = 'used_all_votes';
    }
  }

  // Group by answer
  const answerGroups = {};

  votesToUse.forEach(vote => {
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
    // Primary: total weight
    if (Math.abs(a.total_weight - b.total_weight) > 0.001) {
      return b.total_weight - a.total_weight;
    }

    // Tie-breaker 1: vote count
    if (a.vote_count !== b.vote_count) {
      return b.vote_count - a.vote_count;
    }

    // Tie-breaker 2: max individual weight
    if (Math.abs(a.max_individual_weight - b.max_individual_weight) > 0.001) {
      return b.max_individual_weight - a.max_individual_weight;
    }

    // Tie-breaker 3: alphabetical (for reproducibility)
    return JSON.stringify(a.answer).localeCompare(JSON.stringify(b.answer));
  });

  const winner = sortedGroups[0];
  const runnerUp = sortedGroups[1] || null;

  // Calculate consensus strength
  const totalWeight = sortedGroups.reduce((sum, g) => sum + g.total_weight, 0);
  const consensusStrength = totalWeight > 0 ? (winner.total_weight / totalWeight) : 0;

  // BFT: Calculate consensus metrics using chosen strategy
  let bftMetrics = null;
  if (strategy !== 'weighted-average') {
    const allVotes = votesToUse;

    if (strategy === 'median') {
      bftMetrics = {
        strategy: 'median',
        median_confidence: weightedMedian(allVotes, 'normalized_confidence'),
        median_weight: weightedMedian(allVotes, 'weight'),
      };
    } else if (strategy === 'trimmed-mean') {
      bftMetrics = {
        strategy: 'trimmed-mean',
        trim_percent: trimPercent,
        trimmed_confidence: trimmedMean(allVotes, 'normalized_confidence', trimPercent),
        trimmed_weight: trimmedMean(allVotes, 'weight', trimPercent),
      };
    }
    // MAD metrics already in bftAnalysis
  }

  // Determine consensus level
  let consensusLevel;
  if (consensusStrength >= 0.80) consensusLevel = 'strong';
  else if (consensusStrength >= 0.60) consensusLevel = 'moderate';
  else if (consensusStrength >= 0.40) consensusLevel = 'weak';
  else consensusLevel = 'no_consensus';

  const result = {
    status: 'success',
    algorithm: strategy === 'weighted-average' ? 'weighted_voting' : `weighted_voting_bft_${strategy}`,
    task_type: taskType,
    bft_enabled: strategy !== 'weighted-average',

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
        tier_weight: v.tier_weight,
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
      total_votes: votesBeforeCircuit, // Original vote count before circuit breaker
      filtered_votes: filteredVotes.length,
      discarded_votes: votesBeforeCircuit - filteredVotes.length,
      min_confidence_threshold: minConfidence,
      total_weight: totalWeight,
      num_unique_answers: sortedGroups.length,
    },
  };

  // Add circuit breaker analysis if models were filtered (PRIORITY 0)
  if (circuitBreakerAnalysis) {
    result.circuit_breaker_analysis = circuitBreakerAnalysis;
  }

  // Add Sybil attack analysis if detected (PRIORITY 2)
  if (sybilAnalysis) {
    result.sybil_analysis = sybilAnalysis;
  }

  // Add rotation policy analysis if applied (PRIORITY 2.5)
  if (rotationAnalysis) {
    result.rotation_analysis = rotationAnalysis;
  }

  // Add BFT analysis if enabled
  if (bftAnalysis) {
    result.bft_analysis = bftAnalysis;
  }

  if (bftMetrics) {
    result.bft_metrics = bftMetrics;
  }

  return result;
}

// ============================================================================
// EDGE CASE HANDLING
// ============================================================================

/**
 * Handle edge cases in weighted voting
 *
 * Edge cases:
 * 1. All votes below confidence threshold
 * 2. Top 2 answers tied (within 1% weight difference)
 * 3. No model capable for this task type
 * 4. All votes have same answer (unanimous)
 * 5. Empty vote array
 *
 * @param {Array<Object>} votes - Vote array
 * @param {string} taskType - Task type
 * @param {Object} options - Voting options
 * @returns {Promise<Object>} Edge case handling result
 */
async function handleEdgeCases(votes, taskType, options = {}) {
  const result = {
    has_edge_case: false,
    edge_case_type: null,
    action_taken: null,
    result: null,
  };

  // Edge case 1: Empty vote array
  if (!votes || votes.length === 0) {
    result.has_edge_case = true;
    result.edge_case_type = 'empty_votes';
    result.action_taken = 'return_error';
    result.result = {
      status: 'error',
      error: 'empty_votes',
      message: 'No votes provided',
    };
    return result;
  }

  // Edge case 2: All votes below confidence threshold
  const minConfidence = options.minConfidence || DEFAULT_MIN_CONFIDENCE;
  const aboveThreshold = votes.filter(v =>
    normalizeConfidence(v.confidence) * 100 >= minConfidence
  );

  if (aboveThreshold.length === 0) {
    result.has_edge_case = true;
    result.edge_case_type = 'all_votes_below_threshold';
    result.action_taken = 'lower_threshold_and_retry';

    // Retry with lowered threshold (50% of original)
    const loweredThreshold = Math.max(0, minConfidence * 0.5);
    result.result = await weightedVoting(votes, taskType, {
      ...options,
      minConfidence: loweredThreshold,
    });

    result.result.edge_case_warning = `All votes below ${minConfidence}% threshold. Lowered to ${loweredThreshold}% and retried.`;
    return result;
  }

  // Edge case 3: Unanimous vote (all same answer)
  const uniqueAnswers = new Set(votes.map(v => JSON.stringify(v.answer)));
  if (uniqueAnswers.size === 1) {
    result.has_edge_case = true;
    result.edge_case_type = 'unanimous';
    result.action_taken = 'fast_path';

    // Fast-path: no need for weighted voting
    const banditState = loadBanditState();
    const avgWeight = votes.reduce((sum, v) =>
      sum + calculateVoteWeight(v, taskType, banditState), 0
    ) / votes.length;

    result.result = {
      status: 'success',
      algorithm: 'unanimous_vote',
      winner: {
        answer: votes[0].answer,
        total_weight: avgWeight * votes.length,
        vote_count: votes.length,
        consensus_strength: 1.0,
        consensus_level: 'unanimous',
        votes: votes.map(v => ({
          model: v.model,
          confidence: normalizeConfidence(v.confidence),
        })),
      },
      metadata: {
        total_votes: votes.length,
        edge_case: 'unanimous',
      },
    };
    return result;
  }

  // Edge case 4: No model capable for this task
  const banditState = loadBanditState();
  const maxCapability = Math.max(...votes.map(v =>
    getCapabilityScore(v.model, taskType)
  ));

  if (maxCapability < 0.3) {
    result.has_edge_case = true;
    result.edge_case_type = 'no_capable_models';
    result.action_taken = 'fallback_to_general_task';

    // Fallback to 'general' task type
    result.result = await weightedVoting(votes, 'general', options);
    result.result.edge_case_warning = `No models capable for task '${taskType}'. Using 'general' task weights.`;
    return result;
  }

  // Edge case 5: Tie (top 2 answers within 1% weight difference)
  const votingResult = await weightedVoting(votes, taskType, options);

  if (votingResult.status === 'success' && votingResult.runner_up) {
    const weightDiff = votingResult.runner_up.weight_difference;
    const winnerWeight = votingResult.winner.total_weight;

    if (weightDiff / winnerWeight < 0.01) {
      result.has_edge_case = true;
      result.edge_case_type = 'tie';
      result.action_taken = 'require_arbiter_review';

      votingResult.tie_detected = true;
      votingResult.tie_margin = (weightDiff / winnerWeight * 100).toFixed(2) + '%';
      votingResult.recommendation = 'REQUIRE_ARBITER_REVIEW';
      result.result = votingResult;
      return result;
    }
  }

  // No edge case detected
  result.result = votingResult;
  return result;
}

// ============================================================================
// INTEGRATION WITH ARBITER PATTERN
// ============================================================================

/**
 * Arbiter prompt builder with weighted voting results
 *
 * Provides arbiter with:
 * - Weighted voting results
 * - Individual vote weights breakdown
 * - Edge case warnings (if any)
 * - Recommendation (approve winner or require deeper review)
 *
 * @param {Object} votingResult - Result from weightedVoting() or handleEdgeCases()
 * @param {string} originalTask - Original task description
 * @returns {string} Arbiter prompt
 */
function buildArbiterPrompt(votingResult, originalTask) {
  if (votingResult.status === 'error') {
    return `ERROR: Weighted voting failed.
Reason: ${votingResult.error}
Message: ${votingResult.message}

Please make a decision based on your own analysis of the task:
${originalTask}`;
  }

  const { winner, runner_up, metadata, all_groups } = votingResult;

  let prompt = `[WEIGHTED VOTING RESULTS]

Original Task: ${originalTask}

WINNER (${winner.consensus_level.toUpperCase()} consensus):
- Answer: ${JSON.stringify(winner.answer, null, 2)}
- Total Weight: ${winner.total_weight.toFixed(3)}
- Vote Count: ${winner.vote_count}
- Consensus Strength: ${(winner.consensus_strength * 100).toFixed(1)}%

Supporting Votes:
${winner.votes.map(v => `  - ${v.model}: weight=${v.weight.toFixed(3)}, confidence=${(v.confidence * 100).toFixed(0)}%, tier=${v.tier_weight}, capability=${v.capability_score.toFixed(2)}, history=${v.historical_accuracy.toFixed(2)}`).join('\n')}
`;

  if (runner_up) {
    prompt += `
RUNNER-UP:
- Answer: ${JSON.stringify(runner_up.answer, null, 2)}
- Total Weight: ${runner_up.total_weight.toFixed(3)}
- Vote Count: ${runner_up.vote_count}
- Weight Difference: ${runner_up.weight_difference.toFixed(3)} (${((runner_up.weight_difference / winner.total_weight) * 100).toFixed(1)}%)
`;
  }

  if (all_groups.length > 2) {
    prompt += `
OTHER ANSWERS (${all_groups.length - 2} total):
${all_groups.slice(2).map(g => `  - ${g.percentage}% weight: ${JSON.stringify(g.answer)}`).join('\n')}
`;
  }

  prompt += `
METADATA:
- Total votes: ${metadata.total_votes}
- Filtered votes: ${metadata.filtered_votes}
- Discarded (low confidence): ${metadata.discarded_votes}
- Min confidence threshold: ${metadata.min_confidence_threshold}%
- Unique answers: ${metadata.num_unique_answers}
`;

  if (votingResult.tie_detected) {
    prompt += `
⚠️ TIE DETECTED: Top 2 answers within ${votingResult.tie_margin} weight difference.
Requires careful arbiter review.
`;
  }

  if (votingResult.edge_case_warning) {
    prompt += `
⚠️ EDGE CASE: ${votingResult.edge_case_warning}
`;
  }

  prompt += `
YOUR TASK:
1. Review the weighted voting results above
2. Validate the winner's answer for correctness
3. Consider if runner-up raises valid concerns
4. Make final decision: APPROVE winner, SELECT runner-up, or SYNTHESIZE new answer

${winner.consensus_level === 'strong' ? 'Strong consensus detected - likely correct unless you find critical flaw.' : ''}
${votingResult.tie_detected ? 'TIE DETECTED - examine both answers carefully before deciding.' : ''}
`;

  return prompt;
}

/**
 * Run weighted voting and return arbiter-ready result
 *
 * This is the main entry point for integration with existing workflows.
 * Replaces naive vote counting with weighted algorithm.
 *
 * NEW: Includes disagreement detection and human review queue integration.
 * NEW: Statistical significance testing (confidence intervals, tie detection).
 *
 * @param {Array<Object>} votes - Worker votes
 * @param {string} taskType - Task type
 * @param {Object} options - Options
 * @param {number} options.minConfidence - Min confidence threshold (0-100)
 * @param {number} options.reviewThreshold - Disagreement CV threshold for human review (default: 0.20)
 * @param {boolean} options.skipStatisticalSignificance - Skip CI calculation (default: false)
 * @param {Object} options.context - Task context for human review queue
 * @param {string} options.context.workflow_execution_id - Workflow execution ID
 * @param {string} options.context.workflow_name - Workflow name
 * @param {string} options.context.task_description - Task description
 * @returns {Promise<Object>} Result with arbiter prompt and statistical significance
 */
async function runWeightedVoting(votes, taskType, options = {}) {
  // Handle edge cases
  const edgeResult = await handleEdgeCases(votes, taskType, options);

  const votingResult = edgeResult.result;

  // Calculate statistical significance (if enabled)
  let statisticalSignificance = null;

  if (!options.skipStatisticalSignificance && votingResult.status === 'success') {
    try {
      const { analyzeStatisticalSignificance } = require('./statistical-significance.cjs');

      // Extract votes with weights from voting result
      const votesWithWeights = votingResult.winner.votes.concat(
        votingResult.runner_up?.votes || [],
        ...votingResult.all_groups.slice(2).flatMap(g => g.votes || [])
      );

      statisticalSignificance = analyzeStatisticalSignificance(
        votesWithWeights,
        votingResult,
        {
          iterations: options.bootstrapIterations,
          confidence_level: options.confidenceLevel,
          sample_fraction: options.sampleFraction,
        }
      );

      // Log warnings if statistical tie detected
      if (statisticalSignificance.tie_analysis?.is_tie) {
        console.warn(`[weighted-voting] STATISTICAL TIE DETECTED: ${statisticalSignificance.tie_analysis.reason}`);
        console.warn(`[weighted-voting] Margin: ${statisticalSignificance.tie_analysis.margin_percent.toFixed(1)}%, CI overlap: ${statisticalSignificance.tie_analysis.ci_overlap_percent.toFixed(1)}%`);
      }

      // Log warnings if more samples recommended
      if (statisticalSignificance.sample_size_recommendation?.needs_more_samples) {
        console.warn(`[weighted-voting] LOW CONFIDENCE: ${statisticalSignificance.sample_size_recommendation.reason}`);
        console.warn(`[weighted-voting] Recommend ${statisticalSignificance.sample_size_recommendation.recommended_additional} more samples for higher confidence`);
      }
    } catch (err) {
      console.warn(`[weighted-voting] Could not calculate statistical significance: ${err.message}`);
      // Non-fatal - continue without CI
    }
  }

  return {
    voting_result: votingResult,
    edge_case: edgeResult.has_edge_case ? {
      type: edgeResult.edge_case_type,
      action: edgeResult.action_taken,
    } : null,

    // Statistical significance analysis
    statistical_significance: statisticalSignificance,

    // Helper for arbiter integration
    buildArbiterPrompt: (originalTask) => buildArbiterPrompt(votingResult, originalTask),

    // Helper for logging
    summary: votingResult.status === 'success' ? {
      winner_answer: votingResult.winner.answer,
      consensus_level: votingResult.winner.consensus_level,
      total_weight: votingResult.winner.total_weight,
      vote_count: votingResult.winner.vote_count,
      statistical_tie: statisticalSignificance?.tie_analysis?.is_tie || false,
      needs_more_samples: statisticalSignificance?.sample_size_recommendation?.needs_more_samples || false,
    } : null,
  };
}

/**
 * Run weighted voting WITH disagreement detection and human review queue
 *
 * This is the recommended entry point for production workflows.
 * Integrates disagreement detection BEFORE arbiter synthesis.
 *
 * @param {Array<Object>} votes - Worker votes
 * @param {string} taskType - Task type
 * @param {Object} options - Options (see runWeightedVoting + context fields)
 * @returns {Promise<Object>} Result with disagreement analysis
 */
async function runWeightedVotingWithDisagreementDetection(votes, taskType, options = {}) {
  // Import disagreement detector (lazy load to avoid circular deps)
  const { detectAndQueue } = require('./disagreement-detector.cjs');

  // Run standard weighted voting first
  const votingResult = await runWeightedVoting(votes, taskType, options);

  // Detect disagreement and queue if needed
  const disagreementResult = await detectAndQueue(
    votes,
    votingResult.voting_result,
    options.context || {},
    {
      review_threshold: options.reviewThreshold,
      task_type: options.task_type || taskType,  // Use task_type from options or infer from taskType
    }
  );

  // Log warning if high disagreement detected
  if (disagreementResult.needs_human_review) {
    console.warn(`[weighted-voting] HIGH DISAGREEMENT DETECTED (CV: ${disagreementResult.disagreement_score.toFixed(3)})`);
    console.warn(`[weighted-voting] Flagged for human review (queue ID: ${disagreementResult.queue_result?.queue_id})`);
    console.warn(`[weighted-voting] Proceeding with weighted voting, but human review recommended`);
  }

  return {
    ...votingResult,
    disagreement: disagreementResult.analysis,
    human_review_queue: disagreementResult.queue_result,
    needs_human_review: disagreementResult.needs_human_review,
  };
}

// ============================================================================
// POSTGRESQL AUDIT TRAIL
// ============================================================================

/**
 * Store weighted voting audit trail in PostgreSQL
 *
 * Creates a record in workflow.weighted_votes table for transparency.
 * Schema (suggested):
 *   - id SERIAL PRIMARY KEY
 *   - workflow_execution_id TEXT
 *   - task_type TEXT
 *   - winning_answer JSONB
 *   - total_weight NUMERIC
 *   - consensus_level TEXT
 *   - vote_details JSONB (all votes with weights)
 *   - edge_case TEXT
 *   - created_at TIMESTAMP DEFAULT NOW()
 *
 * @param {Object} votingResult - Result from runWeightedVoting()
 * @param {string} workflowExecutionId - Workflow execution ID
 * @returns {Promise<void>}
 */
async function storeAuditTrail(votingResult, workflowExecutionId) {
  try {
    // Import workflow storage adapter
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Create table if not exists (idempotent)
    await db.pool.query(`
      CREATE TABLE IF NOT EXISTS workflow.weighted_votes (
        id SERIAL PRIMARY KEY,
        workflow_execution_id TEXT NOT NULL,
        task_type TEXT,
        winning_answer JSONB,
        total_weight NUMERIC,
        consensus_level TEXT,
        consensus_strength NUMERIC,
        vote_count INTEGER,
        vote_details JSONB,
        edge_case TEXT,
        edge_case_action TEXT,
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    const { voting_result, edge_case } = votingResult;

    if (voting_result.status === 'success') {
      await db.pool.query(`
        INSERT INTO workflow.weighted_votes
        (workflow_execution_id, task_type, winning_answer, total_weight,
         consensus_level, consensus_strength, vote_count, vote_details,
         edge_case, edge_case_action)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
      `, [
        workflowExecutionId,
        voting_result.task_type,
        JSON.stringify(voting_result.winner.answer),
        voting_result.winner.total_weight,
        voting_result.winner.consensus_level,
        voting_result.winner.consensus_strength,
        voting_result.winner.vote_count,
        JSON.stringify(voting_result.winner.votes),
        edge_case?.type || null,
        edge_case?.action || null,
      ]);

      console.log(`✓ Weighted voting audit trail stored (execution: ${workflowExecutionId})`);
    }
  } catch (err) {
    console.warn(`WARNING: Could not store weighted voting audit trail: ${err.message}`);
    // Non-fatal - continue workflow
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  runWeightedVoting,
  runWeightedVotingWithDisagreementDetection,  // NEW: With human review queue
  weightedVoting,
  handleEdgeCases,
  buildArbiterPrompt,
  storeAuditTrail,

  // BFT (Byzantine Fault Tolerance) functions
  weightedMedian,
  trimmedMean,
  weightedAverage,
  detectOutliersMAD,

  // Weight calculation (for testing/debugging)
  calculateVoteWeight,
  getModelTierWeight,
  getCapabilityScore,
  getHistoricalAccuracy,
  normalizeConfidence,

  // Configuration (export for customization)
  MODEL_TIER_WEIGHTS,
  CAPABILITY_MATRIX,
  DEFAULT_MIN_CONFIDENCE,

  // Thompson Sampling integration
  loadBanditState,
};
