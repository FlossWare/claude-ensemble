'use strict';

/**
 * Strategy Taxonomy - Phase 2
 * Defines 4 strategy dimensions for AI task orchestration
 *
 * Dimensions:
 * 1. prompts: Input framing techniques
 * 2. orchestration: Multi-model coordination patterns
 * 3. verification: Output validation strategies
 * 4. sequences: Task execution patterns
 */

// DIMENSION 1: PROMPT STRATEGIES
const PROMPT_STRATEGIES = {
  zero_shot: {
    id: 'zero_shot',
    name: 'Zero-Shot',
    description: 'Direct task request without examples',
    use_cases: ['Simple tasks', 'Well-defined problems', 'Rapid prototyping'],
    pros: ['Fast', 'Minimal context'],
    cons: ['May require clarification', 'Lower accuracy on complex tasks'],
    cost_profile: 'low',
    latency_profile: 'low',
    example: 'Implement a function to calculate factorial'
  },

  few_shot: {
    id: 'few_shot',
    name: 'Few-Shot',
    description: 'Task request with 2-5 example inputs/outputs',
    use_cases: ['Pattern recognition', 'Code generation', 'Specific formats'],
    pros: ['Better accuracy', 'Guides model behavior'],
    cons: ['More context tokens', 'Requires good examples'],
    cost_profile: 'medium',
    latency_profile: 'low',
    example: 'Given examples: [input1->output1, input2->output2], solve input3'
  },

  chain_of_thought: {
    id: 'chain_of_thought',
    name: 'Chain-of-Thought',
    description: 'Request step-by-step reasoning with intermediate steps',
    use_cases: ['Complex logic', 'Math problems', 'Multi-step analysis'],
    pros: ['Improves reasoning', 'Debuggable steps', 'Higher accuracy'],
    cons: ['More tokens', 'Slower inference'],
    cost_profile: 'medium',
    latency_profile: 'medium',
    example: 'Think through the problem step by step, showing your work'
  },

  tree_of_thought: {
    id: 'tree_of_thought',
    name: 'Tree-of-Thought',
    description: 'Explore multiple reasoning branches and select best path',
    use_cases: ['Optimization', 'Complex problem solving', 'Strategic decisions'],
    pros: ['Explores alternatives', 'Better optimization', 'Handles ambiguity'],
    cons: ['Very expensive', 'Requires synthesis', 'High latency'],
    cost_profile: 'high',
    latency_profile: 'high',
    example: 'Explore 3 different approaches, evaluate each, recommend best'
  }
};

// DIMENSION 2: ORCHESTRATION STRATEGIES
const ORCHESTRATION_STRATEGIES = {
  single_model: {
    id: 'single_model',
    name: 'Single Model',
    description: 'Use one model for the entire task',
    use_cases: ['Simple tasks', 'Fast execution', 'Cost optimization'],
    pros: ['Minimal overhead', 'Deterministic', 'Fast'],
    cons: ['Single point of failure', 'Biased perspective', 'Limited robustness'],
    cost_profile: 'low',
    latency_profile: 'low',
    cost_relative: 1.0,
    latency_relative: 1.0,
    quality_relative: 0.7
  },

  consensus: {
    id: 'consensus',
    name: 'Consensus',
    description: 'Run task on multiple models, combine via voting/averaging',
    use_cases: ['Critical decisions', 'Quality assurance', 'Risk mitigation'],
    pros: ['Robust', 'Diverse perspectives', 'Self-checking'],
    cons: ['Higher cost', 'Slower', 'Complexity in synthesis'],
    cost_profile: 'high',
    latency_profile: 'medium',
    cost_relative: 3.0,
    latency_relative: 2.5,
    quality_relative: 0.88
  },

  adversarial: {
    id: 'adversarial',
    name: 'Adversarial',
    description: 'Workers propose, others refute, arbiter judges',
    use_cases: ['Verification', 'Bug hunting', 'Bias detection'],
    pros: ['Catches errors', 'Finds edge cases', 'Critical analysis'],
    cons: ['Very expensive', 'Requires arbiter', 'Slower'],
    cost_profile: 'high',
    latency_profile: 'high',
    cost_relative: 4.0,
    latency_relative: 3.5,
    quality_relative: 0.92
  },

  cascading: {
    id: 'cascading',
    name: 'Cascading',
    description: 'Chain models: fast first, escalate to expensive on failure',
    use_cases: ['Cost optimization', 'Tiered execution', 'Progressive enhancement'],
    pros: ['Cost efficient', 'Fast common case', 'Graceful degradation'],
    cons: ['Complex routing', 'Multiple models needed', 'Latency variability'],
    cost_profile: 'medium',
    latency_profile: 'medium',
    cost_relative: 1.5,
    latency_relative: 1.2,
    quality_relative: 0.82
  }
};

// DIMENSION 3: VERIFICATION STRATEGIES
const VERIFICATION_STRATEGIES = {
  self_check: {
    id: 'self_check',
    name: 'Self-Check',
    description: 'Model reviews its own output for correctness',
    use_cases: ['Quick validation', 'Format checking', 'Consistency verification'],
    pros: ['Minimal overhead', 'Fast', 'Some error catching'],
    cons: ['Biased self-evaluation', 'Misses logical errors', 'Limited effectiveness'],
    cost_profile: 'low',
    latency_profile: 'low',
    effectiveness: 0.45,
    cost_multiplier: 1.2
  },

  peer_review: {
    id: 'peer_review',
    name: 'Peer Review',
    description: 'Another model reviews the output independently',
    use_cases: ['Quality gates', 'Code review', 'Fact-checking'],
    pros: ['Unbiased', 'Catches logical errors', 'Good balance'],
    cons: ['Higher cost', 'Slower', 'Reviewer bias possible'],
    cost_profile: 'medium',
    latency_profile: 'medium',
    effectiveness: 0.72,
    cost_multiplier: 1.5
  },

  adversarial_refute: {
    id: 'adversarial_refute',
    name: 'Adversarial Refute',
    description: 'Dedicated model tries to refute/break the output',
    use_cases: ['Critical systems', 'Security', 'Robustness validation'],
    pros: ['Finds weaknesses', 'Highest quality', 'Security-focused'],
    cons: ['Very expensive', 'Slower', 'Requires synthesis phase'],
    cost_profile: 'high',
    latency_profile: 'high',
    effectiveness: 0.88,
    cost_multiplier: 2.0
  }
};

// DIMENSION 4: SEQUENCE STRATEGIES
const SEQUENCE_STRATEGIES = {
  analyze_then_verify: {
    id: 'analyze_then_verify',
    name: 'Analyze Then Verify',
    description: 'Generate solution, then verify it (sequential)',
    use_cases: ['Standard workflow', 'Quality gates', 'Simple tasks'],
    pros: ['Clear causality', 'Easy to debug', 'Logical flow'],
    cons: ['Serial latency', 'Cannot parallelize', 'Slower overall'],
    cost_profile: 'medium',
    latency_profile: 'high',
    latency_factor: 2.0,
    good_for: ['single_model', 'consensus']
  },

  parallel_then_merge: {
    id: 'parallel_then_merge',
    name: 'Parallel Then Merge',
    description: 'Run analysis & verification in parallel, merge results',
    use_cases: ['Time-critical tasks', 'High concurrency', 'Load balancing'],
    pros: ['Fast', 'Leverages parallelism', 'Good resource utilization'],
    cons: ['Merge complexity', 'Potential conflicts', 'Synchronization overhead'],
    cost_profile: 'high',
    latency_profile: 'low',
    latency_factor: 1.3,
    good_for: ['consensus', 'cascading']
  },

  iterative_refine: {
    id: 'iterative_refine',
    name: 'Iterative Refine',
    description: 'Generate -> Review -> Refine in cycles until quality threshold',
    use_cases: ['Complex problems', 'Incremental improvement', 'Refinement'],
    pros: ['Highest quality', 'Handles complexity', 'Self-correcting'],
    cons: ['Unpredictable latency', 'Higher cost', 'Cycle count variability'],
    cost_profile: 'high',
    latency_profile: 'high',
    latency_factor: 3.5,
    good_for: ['adversarial', 'peer_review']
  }
};

const COST_MULTIPLIERS = { low: 1, medium: 2, high: 4 };
const LATENCY_MULTIPLIERS = { low: 1, medium: 2, high: 4 };

const STRATEGY_DIMENSIONS = {
  prompts: PROMPT_STRATEGIES,
  orchestration: ORCHESTRATION_STRATEGIES,
  verification: VERIFICATION_STRATEGIES,
  sequences: SEQUENCE_STRATEGIES,
};

/**
 * Get all dimension names.
 */
function getDimensions() {
  return Object.keys(STRATEGY_DIMENSIONS);
}

/**
 * Get strategies within a dimension.
 */
function getStrategies(dimension) {
  const dim = STRATEGY_DIMENSIONS[dimension];
  if (!dim) throw new Error(`Unknown dimension: ${dimension}`);
  return Object.keys(dim);
}

/**
 * Get metadata for a specific strategy.
 */
function getStrategyMeta(dimension, strategy) {
  const dim = STRATEGY_DIMENSIONS[dimension];
  if (!dim) throw new Error(`Unknown dimension: ${dimension}`);
  const meta = dim[strategy];
  if (!meta) throw new Error(`Unknown strategy: ${strategy} in ${dimension}`);
  return { ...meta, dimension, strategy };
}

/**
 * Get total count of strategies across all dimensions.
 */
function getTotalStrategies() {
  return getDimensions().reduce((sum, d) => sum + getStrategies(d).length, 0);
}

/**
 * Estimate relative cost for a combination of strategies (one per dimension).
 */
function estimateCost(combo) {
  let total = 0;
  for (const [dim, strat] of Object.entries(combo)) {
    // Normalize dimension names (prompt -> prompts, sequence -> sequences)
    const normalizedDim = dim === 'prompt' ? 'prompts' : (dim === 'sequence' ? 'sequences' : dim);
    const meta = getStrategyMeta(normalizedDim, strat);
    total += COST_MULTIPLIERS[meta.cost_profile] || 1;
  }
  return total;
}

/**
 * Estimate relative latency for a combination of strategies.
 */
function estimateLatency(combo) {
  let max = 0;
  for (const [dim, strat] of Object.entries(combo)) {
    // Normalize dimension names (prompt -> prompts, sequence -> sequences)
    const normalizedDim = dim === 'prompt' ? 'prompts' : (dim === 'sequence' ? 'sequences' : dim);
    const meta = getStrategyMeta(normalizedDim, strat);
    const val = LATENCY_MULTIPLIERS[meta.latency_profile] || 1;
    if (val > max) max = val;
  }
  return max;
}

/**
 * Find strategies matching a cost/latency constraint.
 */
function filterStrategies(dimension, { maxCost, maxLatency } = {}) {
  return getStrategies(dimension).filter(s => {
    const meta = getStrategyMeta(dimension, s);
    if (maxCost && COST_MULTIPLIERS[meta.cost_profile] > COST_MULTIPLIERS[maxCost]) return false;
    if (maxLatency && LATENCY_MULTIPLIERS[meta.latency_profile] > LATENCY_MULTIPLIERS[maxLatency]) return false;
    return true;
  });
}

/**
 * StrategyTaxonomy class for comprehensive strategy management
 */
class StrategyTaxonomy {
  constructor() {
    this.prompts = PROMPT_STRATEGIES;
    this.orchestration = ORCHESTRATION_STRATEGIES;
    this.verification = VERIFICATION_STRATEGIES;
    this.sequences = SEQUENCE_STRATEGIES;
    this._buildIndex();
  }

  /**
   * Build internal indices for fast lookup
   */
  _buildIndex() {
    this.allStrategies = {};

    Object.values(this.prompts).forEach(s => {
      this.allStrategies[s.id] = { type: 'prompt', ...s };
    });
    Object.values(this.orchestration).forEach(s => {
      this.allStrategies[s.id] = { type: 'orchestration', ...s };
    });
    Object.values(this.verification).forEach(s => {
      this.allStrategies[s.id] = { type: 'verification', ...s };
    });
    Object.values(this.sequences).forEach(s => {
      this.allStrategies[s.id] = { type: 'sequence', ...s };
    });
  }

  /**
   * Get strategy by ID
   */
  getStrategy(strategyId) {
    return this.allStrategies[strategyId] || null;
  }

  /**
   * Get all strategies of a dimension
   */
  getDimension(dimensionName) {
    const dims = {
      'prompt': this.prompts,
      'prompts': this.prompts,
      'orchestration': this.orchestration,
      'verification': this.verification,
      'sequence': this.sequences,
      'sequences': this.sequences
    };
    return dims[dimensionName] || null;
  }

  /**
   * List all strategy IDs in a dimension
   */
  listStrategyIds(dimensionName) {
    const dim = this.getDimension(dimensionName);
    return dim ? Object.values(dim).map(s => s.id) : [];
  }

  /**
   * Get recommended strategies for a task
   */
  getRecommendation(taskType) {
    const recommendations = {
      'simple_task': {
        prompt: 'zero_shot',
        orchestration: 'single_model',
        verification: 'self_check',
        sequence: 'analyze_then_verify'
      },
      'complex_problem': {
        prompt: 'chain_of_thought',
        orchestration: 'consensus',
        verification: 'peer_review',
        sequence: 'iterative_refine'
      },
      'critical_decision': {
        prompt: 'tree_of_thought',
        orchestration: 'adversarial',
        verification: 'adversarial_refute',
        sequence: 'iterative_refine'
      },
      'fast_execution': {
        prompt: 'zero_shot',
        orchestration: 'cascading',
        verification: 'self_check',
        sequence: 'parallel_then_merge'
      },
      'cost_optimized': {
        prompt: 'few_shot',
        orchestration: 'cascading',
        verification: 'self_check',
        sequence: 'analyze_then_verify'
      }
    };

    return recommendations[taskType] || recommendations.simple_task;
  }

  /**
   * Calculate cost of a strategy combination
   */
  calculateCost(strategies) {
    const { prompt, orchestration, verification, sequence } = strategies;

    let baseCost = 1.0;

    if (orchestration && this.orchestration[orchestration]) {
      baseCost = this.orchestration[orchestration].cost_relative;
    }

    if (verification && this.verification[verification]) {
      baseCost *= this.verification[verification].cost_multiplier;
    }

    return {
      base: baseCost,
      estimated_tokens: Math.round(baseCost * 2000),
      estimated_cost_usd: parseFloat((baseCost * 0.01).toFixed(4))
    };
  }

  /**
   * Calculate latency of a strategy combination
   */
  calculateLatency(strategies) {
    const { orchestration, sequence } = strategies;

    let latency = 1.0;

    if (orchestration && this.orchestration[orchestration]) {
      latency = this.orchestration[orchestration].latency_relative;
    }

    if (sequence && this.sequences[sequence]) {
      latency *= this.sequences[sequence].latency_factor;
    }

    return {
      relative: latency,
      estimated_ms: Math.round(latency * 2000)
    };
  }

  /**
   * Get compatibility warnings
   */
  validateCombination(strategies) {
    const warnings = [];
    const { prompt, orchestration, verification, sequence } = strategies;

    // Check prompt/orchestration compatibility
    if (prompt === 'zero_shot' && orchestration === 'adversarial') {
      warnings.push('Zero-shot prompts may not provide enough context for adversarial evaluation');
    }

    // Check sequence/orchestration compatibility
    if (sequence === 'parallel_then_merge' && orchestration === 'single_model') {
      warnings.push('Parallel execution unnecessary with single model');
    }

    // Check sequence/orchestration match
    const seqGoodFor = this.sequences[sequence]?.good_for || [];
    if (seqGoodFor.length > 0 && !seqGoodFor.includes(orchestration)) {
      warnings.push(`Sequence '${sequence}' works best with: ${seqGoodFor.join(', ')}`);
    }

    return {
      valid: true,
      warnings: warnings
    };
  }

  /**
   * Export all strategies as JSON
   */
  toJSON() {
    return {
      prompts: this.prompts,
      orchestration: this.orchestration,
      verification: this.verification,
      sequences: this.sequences,
      all_strategies: this.allStrategies
    };
  }

  /**
   * Get summary stats
   */
  getStats() {
    return {
      total_strategies: Object.keys(this.allStrategies).length,
      prompt_strategies: Object.keys(this.prompts).length,
      orchestration_strategies: Object.keys(this.orchestration).length,
      verification_strategies: Object.keys(this.verification).length,
      sequence_strategies: Object.keys(this.sequences).length
    };
  }
}

module.exports = {
  StrategyTaxonomy,
  PROMPT_STRATEGIES,
  ORCHESTRATION_STRATEGIES,
  VERIFICATION_STRATEGIES,
  SEQUENCE_STRATEGIES,
  STRATEGY_DIMENSIONS,
  COST_MULTIPLIERS,
  LATENCY_MULTIPLIERS,
  getDimensions,
  getStrategies,
  getStrategyMeta,
  getTotalStrategies,
  estimateCost,
  estimateLatency,
  filterStrategies,
};
