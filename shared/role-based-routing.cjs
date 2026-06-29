/**
 * Role-Based Routing - Vendor-neutral capability selection
 * Integrates with Thompson Sampling for quality/cost/latency optimization
 *
 * NOTE: Model capabilities are dynamically loaded from capability-registry.cjs
 * This file no longer contains hardcoded vendor models. To add/update models,
 * use the capability registry API or configuration files.
 */

const { getCapableModels: getRegistryCapableModels } = require('./capability-registry.cjs');

const ROLE_CAPABILITIES = {
  // Map roles to capability registry queries
  // Each role defines required capabilities and performance thresholds

  // Code generation and analysis
  code_generation: {
    capability: 'code_generation',
    minQuality: 0.7,
    maxLatency: 5000,
    maxCost: 0.20
  },
  code_review: {
    capability: 'code_review',
    minQuality: 0.75,
    maxLatency: 10000,
    maxCost: 0.15
  },

  // Research and analysis
  research: {
    capability: 'research',
    minQuality: 0.8,
    maxLatency: 15000,
    maxCost: 0.30
  },
  analysis: {
    capability: 'analysis',
    minQuality: 0.75,
    maxLatency: 10000,
    maxCost: 0.20
  },

  // Consensus and arbitration
  arbiter: {
    capability: 'verifier',
    minQuality: 0.85,
    maxLatency: 8000,
    maxCost: 0.20
  },
  consensus: {
    capability: 'reasoner',
    minQuality: 0.7,
    maxLatency: 10000,
    maxCost: 0.15
  },

  // Vision and multimodal
  vision: {
    capability: 'vision',
    minQuality: 0.7,
    maxLatency: 10000,
    maxCost: 0.25
  },

  // Fast routing and classification
  routing: {
    capability: 'planner',
    minQuality: 0.6,
    maxLatency: 2000,
    maxCost: 0.05
  },
  classification: {
    capability: 'planner',
    minQuality: 0.65,
    maxLatency: 3000,
    maxCost: 0.05
  },

  // Additional role mappings
  reasoning: {
    capability: 'reasoner',
    minQuality: 0.75,
    maxLatency: 15000,
    maxCost: 0.20
  },
  summarization: {
    capability: 'summarizer',
    minQuality: 0.75,
    maxLatency: 10000,
    maxCost: 0.10
  }
};

/**
 * Calculate model score for a given role from capability-registry data
 */
function scoreModelForRole(model, capabilityData, roleConfig, options = {}) {
  const { prioritize = 'balanced' } = options;

  // Validate performance thresholds
  if (capabilityData.quality_score < roleConfig.minQuality) return 0;
  if (capabilityData.avg_latency_ms > roleConfig.maxLatency) return 0;
  if (capabilityData.avg_cost > roleConfig.maxCost) return 0;

  // Base score from quality
  let score = capabilityData.quality_score * 100;

  // Confidence bonus (models with more history are more reliable)
  const confidence = capabilityData.confidence || 0;
  score += confidence * 20;

  // Adjust based on priority
  switch (prioritize) {
    case 'quality':
      score += capabilityData.quality_score * 20;
      break;
    case 'speed':
      score += (1 - capabilityData.avg_latency_ms / 30000) * 20;
      break;
    case 'cost':
      score += (1 - Math.min(capabilityData.avg_cost / 0.20, 1)) * 20;
      break;
    case 'balanced':
      // Balance quality, speed, cost
      score += capabilityData.quality_score * 10;
      score += (1 - capabilityData.avg_latency_ms / 30000) * 10;
      score += (1 - Math.min(capabilityData.avg_cost / 0.20, 1)) * 10;
      break;
  }

  return score;
}

/**
 * Get Thompson Sampling statistics for a model
 */
function getThompsonStats(modelId, thompsonData = {}) {
  const stats = thompsonData[modelId] || { alpha: 1, beta: 1 };
  // Beta distribution mean
  return stats.alpha / (stats.alpha + stats.beta);
}

/**
 * Select best model for a capability/role
 * Dynamically queries capability-registry for available models
 */
async function selectCapability(role, options = {}) {
  const {
    prioritize = 'balanced',
    thompsonSampling = null,
    excludeModels = []
  } = options;

  const roleConfig = ROLE_CAPABILITIES[role];
  if (!roleConfig) {
    throw new Error(`Unknown role: ${role}`);
  }

  try {
    // Query capability registry for models capable of this role
    const registryModels = await getRegistryCapableModels(roleConfig.capability, {
      min_quality: roleConfig.minQuality,
      max_cost: roleConfig.maxCost,
      max_latency_ms: roleConfig.maxLatency
    });

    if (registryModels.length === 0) {
      throw new Error(
        `No models available for role: ${role} (capability: ${roleConfig.capability})`
      );
    }

    // Score and rank candidates
    const candidates = registryModels
      .filter(m => !excludeModels.includes(m.model))
      .map(model => {
        const baseScore = scoreModelForRole(model.model, model, roleConfig, {
          prioritize
        });

        // Apply Thompson Sampling if available
        let finalScore = baseScore;
        if (thompsonSampling) {
          const thompsonScore = getThompsonStats(model.model, thompsonSampling);
          finalScore = baseScore * 0.7 + thompsonScore * 100 * 0.3;
        }

        return {
          modelId: model.model,
          data: model,
          baseScore,
          finalScore,
          thompsonScore: thompsonSampling
            ? getThompsonStats(model.model, thompsonSampling)
            : null
        };
      });

    if (candidates.length === 0) {
      throw new Error(
        `No suitable models found for role: ${role} after filtering`
      );
    }

    // Sort by final score
    candidates.sort((a, b) => b.finalScore - a.finalScore);

    const winner = candidates[0];
    return {
      modelId: winner.modelId,
      data: winner.data,
      score: winner.finalScore,
      baseScore: winner.baseScore,
      thompsonScore: winner.thompsonScore,
      alternatives: candidates.slice(1, 4).map(c => ({
        modelId: c.modelId,
        score: c.finalScore
      })),
      fallback: false
    };
  } catch (error) {
    throw new Error(
      `selectCapability error for role '${role}': ${error.message}`
    );
  }
}

/**
 * Get all models capable of a role (async)
 */
async function getCapableModels(role, options = {}) {
  const { prioritize = 'balanced', minScore = 0 } = options;

  const roleConfig = ROLE_CAPABILITIES[role];
  if (!roleConfig) {
    throw new Error(`Unknown role: ${role}`);
  }

  try {
    const registryModels = await getRegistryCapableModels(roleConfig.capability, {
      min_quality: roleConfig.minQuality,
      max_cost: roleConfig.maxCost,
      max_latency_ms: roleConfig.maxLatency
    });

    const capable = registryModels.map(model => ({
      modelId: model.model,
      data: model,
      score: scoreModelForRole(model.model, model, roleConfig, { prioritize })
    }));

    return capable
      .filter(c => c.score > minScore)
      .sort((a, b) => b.score - a.score);
  } catch (error) {
    throw new Error(
      `getCapableModels error for role '${role}': ${error.message}`
    );
  }
}

/**
 * Update Thompson Sampling statistics
 */
function updateThompsonStats(modelId, success, currentStats = {}) {
  const stats = currentStats[modelId] || { alpha: 1, beta: 1 };

  if (success) {
    stats.alpha += 1;
  } else {
    stats.beta += 1;
  }

  return {
    ...currentStats,
    [modelId]: stats
  };
}

/**
 * Get role requirements (for debugging/introspection)
 */
function getRoleRequirements(role) {
  return ROLE_CAPABILITIES[role] || null;
}

/**
 * Get model capabilities from registry (async)
 * Returns metadata about a specific model's capabilities
 */
async function getModelCapabilities(modelId) {
  try {
    const { getModelCapabilities: getRegistryCapabilities } = require('./capability-registry.cjs');
    return await getRegistryCapabilities(modelId);
  } catch (error) {
    console.error(
      `getModelCapabilities error for model '${modelId}':`,
      error.message
    );
    return null;
  }
}

module.exports = {
  selectCapability,
  getCapableModels,
  updateThompsonStats,
  getRoleRequirements,
  getModelCapabilities,
  ROLE_CAPABILITIES
  // NOTE: MODEL_CAPABILITIES no longer exported. Use capability-registry.cjs directly.
};
