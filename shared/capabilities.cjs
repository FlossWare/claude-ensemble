/**
 * Capability Interfaces
 *
 * Defines 6 capability types: reasoner, verifier, critic, planner, summarizer, code_reviewer.
 * Each with quality thresholds, cost limits, latency limits.
 */

/**
 * @typedef {Object} CapabilityDefinition
 * @property {string} name - Capability name
 * @property {string} description - What this capability does
 * @property {number} minQualityScore - Minimum quality score (0-1)
 * @property {number} maxCostUsd - Maximum cost per request (USD)
 * @property {number} maxLatencyMs - Maximum acceptable latency (ms)
 * @property {string[]} requiredSkills - Skills required for this capability
 */

/**
 * Capability type definitions
 * @type {Object.<string, CapabilityDefinition>}
 */
const CAPABILITIES = {
  reasoner: {
    name: 'reasoner',
    description: 'Complex reasoning and problem-solving tasks',
    minQualityScore: 0.80,
    maxCostUsd: 0.10,
    maxLatencyMs: 30000,
    requiredSkills: ['logic', 'analysis', 'multi-step-reasoning']
  },

  verifier: {
    name: 'verifier',
    description: 'Verify correctness of outputs, fact-checking',
    minQualityScore: 0.85,
    maxCostUsd: 0.05,
    maxLatencyMs: 20000,
    requiredSkills: ['verification', 'fact-checking', 'adversarial-testing']
  },

  critic: {
    name: 'critic',
    description: 'Critical analysis and improvement suggestions',
    minQualityScore: 0.75,
    maxCostUsd: 0.05,
    maxLatencyMs: 15000,
    requiredSkills: ['critical-thinking', 'pattern-recognition', 'edge-case-detection']
  },

  planner: {
    name: 'planner',
    description: 'Strategic planning and task decomposition',
    minQualityScore: 0.70,
    maxCostUsd: 0.03,
    maxLatencyMs: 10000,
    requiredSkills: ['planning', 'decomposition', 'prioritization']
  },

  summarizer: {
    name: 'summarizer',
    description: 'Content summarization and synthesis',
    minQualityScore: 0.75,
    maxCostUsd: 0.02,
    maxLatencyMs: 10000,
    requiredSkills: ['summarization', 'extraction', 'conciseness']
  },

  code_reviewer: {
    name: 'code_reviewer',
    description: 'Code review, bug detection, security analysis',
    minQualityScore: 0.80,
    maxCostUsd: 0.08,
    maxLatencyMs: 25000,
    requiredSkills: ['code-analysis', 'security', 'best-practices', 'bug-detection']
  }
};

/**
 * Get capability definition
 * @param {string} capabilityName - Name of the capability
 * @returns {CapabilityDefinition|null} Capability definition or null if not found
 */
function getCapability(capabilityName) {
  return CAPABILITIES[capabilityName] || null;
}

/**
 * Get all capability names
 * @returns {string[]} Array of capability names
 */
function getAllCapabilities() {
  return Object.keys(CAPABILITIES);
}

/**
 * Check if a capability exists
 * @param {string} capabilityName - Name to check
 * @returns {boolean} True if capability exists
 */
function hasCapability(capabilityName) {
  return capabilityName in CAPABILITIES;
}

/**
 * Validate if model performance meets capability requirements
 * @param {string} capabilityName - Capability to check
 * @param {Object} performance - Model performance metrics
 * @param {number} performance.qualityScore - Quality score (0-1)
 * @param {number} performance.avgCostUsd - Average cost per request (USD)
 * @param {number} performance.avgLatencyMs - Average latency (ms)
 * @returns {Object} { meets: boolean, reasons: string[] }
 */
function meetsCapabilityRequirements(capabilityName, performance) {
  const capability = getCapability(capabilityName);

  if (!capability) {
    return {
      meets: false,
      reasons: [`Unknown capability: ${capabilityName}`]
    };
  }

  const reasons = [];
  let meets = true;

  if (performance.qualityScore < capability.minQualityScore) {
    meets = false;
    reasons.push(
      `Quality score ${performance.qualityScore.toFixed(3)} below minimum ${capability.minQualityScore.toFixed(3)}`
    );
  }

  if (performance.avgCostUsd > capability.maxCostUsd) {
    meets = false;
    reasons.push(
      `Cost $${performance.avgCostUsd.toFixed(4)} exceeds maximum $${capability.maxCostUsd.toFixed(4)}`
    );
  }

  if (performance.avgLatencyMs > capability.maxLatencyMs) {
    meets = false;
    reasons.push(
      `Latency ${performance.avgLatencyMs}ms exceeds maximum ${capability.maxLatencyMs}ms`
    );
  }

  return { meets, reasons };
}

module.exports = {
  CAPABILITIES,
  getCapability,
  getAllCapabilities,
  hasCapability,
  meetsCapabilityRequirements
};
