/**
 * Orchestrator Brain - Intelligent Coordination Engine
 *
 * Transforms the orchestrator from a passive message passer into an intelligent
 * coordinator that learns from experience and makes smart decisions about:
 * - Which agents to spawn
 * - Which models to use for each role
 * - Which servers to distribute work to
 * - How to combine results
 * - What worked and what didn't
 *
 * Uses Thompson Sampling, learning database, and meta-learnings to get smarter
 * over time.
 *
 * State tracking:
 * - orchestrator-decisions.jsonl - Every coordination decision
 * - orchestrator-learnings.jsonl - What orchestrator learned
 * - learning.db - Metrics and performance data
 *
 * Usage:
 *   import { coordinateTask, analyzeTaskComplexity, selectAgentStrategy,
 *            learnFromCoordination } from './orchestrator-brain.js';
 *
 *   // Analyze task and decide strategy
 *   const analysis = await analyzeTaskComplexity(task);
 *   const strategy = await selectAgentStrategy(task, analysis);
 *
 *   // Coordinate execution
 *   const result = await coordinateTask(task, strategy);
 *
 *   // Learn from outcome
 *   await learnFromCoordination(result);
 */

import { readFileSync, existsSync, appendFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';
import * as db from './learning/db.js';
import * as thompson from './learning/thompson-sampling.js';
import * as orchestrator from './orchestrator.js';
import * as integration from './claude-learning-integration.js';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const LEARNING_DIR = join(HOME, '.claude', 'learning');
const DECISIONS_LOG = join(LEARNING_DIR, 'orchestrator-decisions.jsonl');
const LEARNINGS_LOG = join(LEARNING_DIR, 'orchestrator-learnings.jsonl');

// Agent strategies
const STRATEGIES = {
  SINGLE_AGENT: 'single-agent',           // Simple task, one agent
  PARALLEL_WORKERS: 'parallel-workers',   // Independent subtasks
  PIPELINE: 'pipeline',                   // Sequential stages
  CONSENSUS: 'consensus',                 // Multi-AI agreement needed
  HIERARCHICAL: 'hierarchical',           // Specialized sub-teams
  DEBATE: 'debate',                       // Adversarial validation
};

// Complexity scoring weights
const COMPLEXITY_WEIGHTS = {
  SUBTASK_COUNT: 0.25,      // More subtasks → higher complexity
  DOMAIN_COUNT: 0.20,       // Multi-domain → higher complexity
  UNCERTAINTY: 0.20,        // Unknown/new task → higher complexity
  DEPENDENCIES: 0.15,       // Task dependencies → higher complexity
  QUALITY_REQUIREMENT: 0.10, // High quality needed → higher complexity
  TIME_PRESSURE: 0.10,      // Time constraints → affects strategy
};

// ============================================================================
// TASK COMPLEXITY ANALYSIS
// ============================================================================

/**
 * Analyze task complexity to guide coordination strategy.
 *
 * @param {Object} task - Task description
 * @param {string} task.type - Task type
 * @param {string} task.description - Task description
 * @param {string[]} task.subtasks - Subtasks
 * @param {string[]} task.domains - Domains involved
 * @param {number} task.quality_requirement - Required quality (0-1)
 * @returns {Promise<Object>} Complexity analysis
 */
export async function analyzeTaskComplexity(task) {
  const {
    type,
    description,
    subtasks = [],
    domains = [],
    quality_requirement = 0.7,
    time_pressure = 0.5,
  } = task;

  try {
    // 1. Consult historical learnings
    const guidance = await integration.consultLearnings(type);

    // 2. Calculate complexity score
    const scores = {
      subtask_count: Math.min(1.0, subtasks.length / 10),
      domain_count: Math.min(1.0, domains.length / 5),
      uncertainty: guidance.available ? (1 - guidance.confidence) : 0.8,
      dependencies: _analyzeDependencies(subtasks),
      quality_requirement,
      time_pressure,
    };

    const complexity = Object.entries(scores).reduce((sum, [key, score]) => {
      const weight = COMPLEXITY_WEIGHTS[key.toUpperCase()] || 0;
      return sum + (score * weight);
    }, 0);

    // 3. Estimate resource requirements
    const estimatedModels = _estimateModelCount(complexity, subtasks.length);
    const estimatedDuration = _estimateDuration(complexity, guidance);
    const estimatedCost = _estimateCost(estimatedModels, estimatedDuration, guidance);

    return {
      complexity_score: complexity,
      complexity_level: _complexityLevel(complexity),
      scores,
      estimated_models: estimatedModels,
      estimated_duration_ms: estimatedDuration,
      estimated_cost_usd: estimatedCost,
      guidance,
      recommendation: _recommendStrategy(complexity, subtasks, domains),
    };
  } catch (err) {
    console.error(`[analyzeTaskComplexity] Error: ${err.message}`);
    return {
      complexity_score: 0.5,
      complexity_level: 'medium',
      error: err.message,
    };
  }
}

/**
 * Analyze task dependencies
 */
function _analyzeDependencies(subtasks) {
  if (subtasks.length === 0) return 0;

  // Simple heuristic: if subtasks mention each other, they're dependent
  let dependencyCount = 0;
  for (let i = 0; i < subtasks.length; i++) {
    for (let j = i + 1; j < subtasks.length; j++) {
      const task1 = subtasks[i].toLowerCase();
      const task2 = subtasks[j].toLowerCase();

      // Keywords suggesting dependency
      if (task1.includes('then') || task1.includes('after') ||
          task2.includes('before') || task2.includes('requires')) {
        dependencyCount++;
      }
    }
  }

  return Math.min(1.0, dependencyCount / (subtasks.length * 0.5));
}

/**
 * Estimate model count needed
 */
function _estimateModelCount(complexity, subtaskCount) {
  if (complexity < 0.3) return 1;           // Simple → single model
  if (complexity < 0.5) return 2;           // Medium → 2 models
  if (complexity < 0.7) return 3;           // Complex → 3 models
  if (subtaskCount > 5) return 6;           // Many subtasks → max models
  return 4;                                 // Very complex → 4 models
}

/**
 * Estimate duration
 */
function _estimateDuration(complexity, guidance) {
  const baselineDuration = guidance.avg_duration || 30000; // 30s default
  const complexityMultiplier = 1 + complexity;
  return Math.round(baselineDuration * complexityMultiplier);
}

/**
 * Estimate cost
 */
function _estimateCost(modelCount, duration, guidance) {
  const baselineCost = guidance.avg_cost || 0.01;
  return baselineCost * modelCount * (duration / 30000);
}

/**
 * Get complexity level label
 */
function _complexityLevel(score) {
  if (score < 0.3) return 'low';
  if (score < 0.5) return 'medium';
  if (score < 0.7) return 'high';
  return 'very-high';
}

/**
 * Recommend strategy based on analysis
 */
function _recommendStrategy(complexity, subtasks, domains) {
  if (complexity < 0.3) {
    return STRATEGIES.SINGLE_AGENT;
  }

  if (domains.length > 2) {
    return STRATEGIES.HIERARCHICAL;
  }

  if (subtasks.length > 5 && _analyzeDependencies(subtasks) < 0.3) {
    return STRATEGIES.PARALLEL_WORKERS;
  }

  if (complexity >= 0.7) {
    return STRATEGIES.CONSENSUS;
  }

  if (subtasks.length > 2) {
    return STRATEGIES.PIPELINE;
  }

  return STRATEGIES.CONSENSUS;
}

// ============================================================================
// AGENT STRATEGY SELECTION
// ============================================================================

/**
 * Select the best agent strategy based on task analysis.
 *
 * @param {Object} task - Task description
 * @param {Object} analysis - Complexity analysis from analyzeTaskComplexity
 * @returns {Promise<Object>} Strategy selection
 */
export async function selectAgentStrategy(task, analysis) {
  const { type } = task;
  const { complexity_score, recommendation } = analysis;

  try {
    // 1. Get historical performance by strategy
    const strategyPerformance = await _getStrategyPerformance(type);

    // 2. Thompson Sampling for strategy selection
    let selectedStrategy = recommendation;

    if (strategyPerformance.length > 0) {
      // Use Thompson Sampling across strategies
      // Find best strategy via single-pass max tracking (no intermediate arrays)
      let maxSample = -Infinity;

      for (const perf of strategyPerformance) {
        const alpha = (perf.success_count || 0) + 1;
        const beta = (perf.failure_count || 0) + 1;
        const sample = _sampleBeta(alpha, beta);

        if (sample > maxSample) {
          maxSample = sample;
          selectedStrategy = perf.strategy;
        }
      }
    }

    // 3. Select models for each role
    const workerModels = await _selectWorkerModels(type, selectedStrategy, analysis);
    const arbiterModel = await _selectArbiterModel(type, selectedStrategy, workerModels);

    return {
      strategy: selectedStrategy,
      worker_models: workerModels,
      arbiter_model: arbiterModel,
      confidence: _calculateStrategyConfidence(strategyPerformance, selectedStrategy),
      reasoning: _explainStrategy(selectedStrategy, analysis),
    };
  } catch (err) {
    console.error(`[selectAgentStrategy] Error: ${err.message}`);
    return {
      strategy: STRATEGIES.SINGLE_AGENT,
      worker_models: ['sonnet'],
      arbiter_model: 'opus',
      confidence: 0.5,
      error: err.message,
    };
  }
}

/**
 * Get historical strategy performance
 */
async function _getStrategyPerformance(taskType) {
  try {
    const rows = db.query(`
      SELECT strategy,
             COUNT(*) as total,
             SUM(CASE WHEN quality_score >= 0.7 THEN 1 ELSE 0 END) as success_count,
             SUM(CASE WHEN quality_score < 0.5 THEN 1 ELSE 0 END) as failure_count,
             AVG(quality_score) as avg_quality
      FROM execution_log
      WHERE task_type = ?
        AND strategy IS NOT NULL
        AND quality_score IS NOT NULL
      GROUP BY strategy
      ORDER BY avg_quality DESC
    `, [taskType]);

    return rows;
  } catch (_err) {
    return [];
  }
}

/**
 * Beta distribution sampling using Johnk's algorithm
 * (Proper Thompson Sampling requires random draws, not deterministic mean)
 */
function _sampleBeta(alpha, beta) {
  // Johnk's algorithm for Beta sampling
  let u, v, x, y;
  do {
    u = Math.random();
    v = Math.random();
    x = Math.pow(u, 1 / alpha);
    y = Math.pow(v, 1 / beta);
  } while (x + y > 1);

  // Guard against division by zero (both random() = 0 edge case)
  const sum = x + y;
  return sum === 0 ? 0.5 : x / sum;
}

/**
 * Select worker models for strategy
 */
async function _selectWorkerModels(taskType, strategy, analysis) {
  const { estimated_models } = analysis;

  const count = {
    [STRATEGIES.SINGLE_AGENT]: 1,
    [STRATEGIES.PARALLEL_WORKERS]: Math.min(estimated_models, 4),
    [STRATEGIES.PIPELINE]: Math.min(estimated_models, 3),
    [STRATEGIES.CONSENSUS]: Math.min(estimated_models, 6),
    [STRATEGIES.HIERARCHICAL]: 6,
    [STRATEGIES.DEBATE]: 4,
  }[strategy] || 3;

  const selected = await integration.selectModelIntelligently(taskType, {
    useThompson: true,
    count,
  });

  // Ensure we always return an array
  return Array.isArray(selected) ? selected : [selected];
}

/**
 * Select arbiter model
 */
async function _selectArbiterModel(taskType, strategy, workerModels) {
  // Arbiter should be different from workers
  const candidates = ['opus', 'fable', 'sonnet', 'gemini']
    .filter(m => !workerModels.includes(m));

  if (candidates.length === 0) {
    return 'fable'; // Fallback
  }

  const selected = await integration.selectModelIntelligently(taskType, {
    useThompson: true,
    count: 1,
    candidates,
  });

  return Array.isArray(selected) ? selected[0] : selected;
}

/**
 * Calculate confidence in strategy selection
 */
function _calculateStrategyConfidence(performance, strategy) {
  if (performance.length === 0) return 0.5;

  const strategyPerf = performance.find(p => p.strategy === strategy);
  if (!strategyPerf) return 0.5;

  const sampleSize = strategyPerf.total || 0;
  const avgQuality = strategyPerf.avg_quality || 0.5;

  // Confidence increases with sample size and quality
  return Math.min(0.95, 0.5 + (sampleSize / 100) * 0.3 + avgQuality * 0.2);
}

/**
 * Explain strategy selection
 */
function _explainStrategy(strategy, analysis) {
  const { complexity_score, scores } = analysis;

  const reasons = [];

  if (strategy === STRATEGIES.SINGLE_AGENT) {
    reasons.push(`Low complexity (${complexity_score.toFixed(2)}) → single agent sufficient`);
  } else if (strategy === STRATEGIES.CONSENSUS) {
    reasons.push(`High complexity (${complexity_score.toFixed(2)}) → multi-AI consensus needed`);
  } else if (strategy === STRATEGIES.HIERARCHICAL) {
    reasons.push(`Multi-domain task → specialized sub-teams`);
  } else if (strategy === STRATEGIES.PARALLEL_WORKERS) {
    reasons.push(`Low dependencies (${scores.dependencies.toFixed(2)}) → parallel execution`);
  } else if (strategy === STRATEGIES.PIPELINE) {
    reasons.push(`Sequential subtasks → pipeline approach`);
  } else if (strategy === STRATEGIES.DEBATE) {
    reasons.push(`Adversarial validation needed → debate strategy`);
  }

  return reasons.join('; ');
}

// ============================================================================
// TASK COORDINATION
// ============================================================================

/**
 * Coordinate task execution using selected strategy.
 *
 * @param {Object} task - Task description
 * @param {Object} strategy - Strategy from selectAgentStrategy
 * @returns {Promise<Object>} Coordination result
 */
export async function coordinateTask(task, strategy) {
  const coordinationId = randomUUID();
  const startTime = Date.now();

  const coordination = {
    id: coordinationId,
    timestamp: new Date().toISOString(),
    task_type: task.type,
    task_description: task.description,
    strategy: strategy.strategy,
    worker_models: strategy.worker_models,
    arbiter_model: strategy.arbiter_model,
    status: 'running',
  };

  try {
    // Log coordination decision
    _logDecision(coordination);

    // Execute based on strategy
    let result;
    switch (strategy.strategy) {
      case STRATEGIES.SINGLE_AGENT:
        result = await _executeSingleAgent(task, strategy);
        break;
      case STRATEGIES.PARALLEL_WORKERS:
        result = await _executeParallelWorkers(task, strategy);
        break;
      case STRATEGIES.PIPELINE:
        result = await _executePipeline(task, strategy);
        break;
      case STRATEGIES.CONSENSUS:
        result = await _executeConsensus(task, strategy);
        break;
      case STRATEGIES.HIERARCHICAL:
        result = await _executeHierarchical(task, strategy);
        break;
      case STRATEGIES.DEBATE:
        result = await _executeDebate(task, strategy);
        break;
      default:
        throw new Error(`Unknown strategy: ${strategy.strategy}`);
    }

    const duration = Date.now() - startTime;

    coordination.status = 'completed';
    coordination.duration_ms = duration;
    coordination.result = result;
    coordination.quality_score = result.quality_score || 0.5;

    // Log completion
    _logDecision(coordination);

    return {
      success: true,
      coordination_id: coordinationId,
      result,
      duration_ms: duration,
    };
  } catch (err) {
    const duration = Date.now() - startTime;

    coordination.status = 'failed';
    coordination.duration_ms = duration;
    coordination.error = err.message;

    _logDecision(coordination);

    return {
      success: false,
      coordination_id: coordinationId,
      error: err.message,
      duration_ms: duration,
    };
  }
}

/**
 * Execute single agent strategy
 */
async function _executeSingleAgent(task, strategy) {
  // Single model execution (placeholder - integrate with actual agent spawning)
  return {
    strategy: STRATEGIES.SINGLE_AGENT,
    model: strategy.worker_models[0],
    quality_score: 0.75,
    output: 'Single agent execution result',
  };
}

/**
 * Execute parallel workers strategy
 */
async function _executeParallelWorkers(task, strategy) {
  // Parallel execution (placeholder)
  return {
    strategy: STRATEGIES.PARALLEL_WORKERS,
    workers: strategy.worker_models,
    quality_score: 0.80,
    output: 'Parallel workers execution result',
  };
}

/**
 * Execute pipeline strategy
 */
async function _executePipeline(task, strategy) {
  // Sequential pipeline (placeholder)
  return {
    strategy: STRATEGIES.PIPELINE,
    stages: strategy.worker_models,
    quality_score: 0.78,
    output: 'Pipeline execution result',
  };
}

/**
 * Execute consensus strategy
 */
async function _executeConsensus(task, strategy) {
  // Multi-AI consensus (placeholder)
  return {
    strategy: STRATEGIES.CONSENSUS,
    workers: strategy.worker_models,
    arbiter: strategy.arbiter_model,
    quality_score: 0.85,
    consensus_score: 0.82,
    output: 'Consensus execution result',
  };
}

/**
 * Execute hierarchical strategy
 */
async function _executeHierarchical(task, strategy) {
  // Hierarchical coordination (placeholder)
  return {
    strategy: STRATEGIES.HIERARCHICAL,
    teams: strategy.worker_models,
    meta_arbiter: strategy.arbiter_model,
    quality_score: 0.88,
    output: 'Hierarchical execution result',
  };
}

/**
 * Execute debate strategy
 */
async function _executeDebate(task, strategy) {
  // Adversarial debate (placeholder)
  return {
    strategy: STRATEGIES.DEBATE,
    debaters: strategy.worker_models,
    judge: strategy.arbiter_model,
    quality_score: 0.83,
    output: 'Debate execution result',
  };
}

/**
 * Log coordination decision
 */
function _logDecision(coordination) {
  try {
    appendFileSync(DECISIONS_LOG, JSON.stringify(coordination) + '\n', 'utf-8');
  } catch (err) {
    console.error(`[_logDecision] Error: ${err.message}`);
  }
}

// ============================================================================
// LEARNING FROM COORDINATION
// ============================================================================

/**
 * Learn from coordination outcome.
 * Updates Thompson Sampling, logs learnings, records to DB.
 *
 * @param {Object} result - Result from coordinateTask
 * @returns {Promise<Object>} Learning result
 */
export async function learnFromCoordination(result) {
  const { coordination_id, result: executionResult, duration_ms } = result;

  try {
    const qualityScore = executionResult.quality_score || 0.5;

    // 1. Update Thompson Sampling for each model used
    if (executionResult.workers) {
      for (const model of executionResult.workers) {
        thompson.updateModel(model, qualityScore);
      }
    }
    if (executionResult.arbiter) {
      thompson.updateModel(executionResult.arbiter, qualityScore);
    }

    // 2. Extract learning
    const learning = {
      id: randomUUID(),
      timestamp: new Date().toISOString(),
      coordination_id,
      strategy: executionResult.strategy,
      quality_score: qualityScore,
      duration_ms,
      learning_type: qualityScore >= 0.7 ? 'success_pattern' : 'failure_pattern',
      insight: _extractInsight(executionResult, qualityScore),
    };

    // 3. Log learning
    appendFileSync(LEARNINGS_LOG, JSON.stringify(learning) + '\n', 'utf-8');

    // 4. Record to database
    await integration.recordDecision({
      task_type: executionResult.strategy || 'unknown',
      model_used: executionResult.arbiter || executionResult.model || 'unknown',
      decision: `Strategy: ${executionResult.strategy}`,
      outcome: qualityScore >= 0.7 ? 'success' : 'failure',
      quality_score: qualityScore,
      metadata: {
        coordination_id,
        workers: executionResult.workers,
        consensus_score: executionResult.consensus_score,
      },
    });

    return {
      success: true,
      learning_id: learning.id,
      insight: learning.insight,
    };
  } catch (err) {
    console.error(`[learnFromCoordination] Error: ${err.message}`);
    return {
      success: false,
      error: err.message,
    };
  }
}

/**
 * Extract insight from execution result
 */
function _extractInsight(result, qualityScore) {
  const insights = [];

  if (qualityScore >= 0.9) {
    insights.push(`Excellent result with ${result.strategy}`);
  } else if (qualityScore >= 0.7) {
    insights.push(`Good result with ${result.strategy}`);
  } else if (qualityScore >= 0.5) {
    insights.push(`Mediocre result with ${result.strategy} - consider alternative`);
  } else {
    insights.push(`Poor result with ${result.strategy} - avoid this approach`);
  }

  if (result.consensus_score && result.consensus_score < 0.6) {
    insights.push('Low consensus - models disagreed significantly');
  }

  if (result.workers && result.workers.length > 4) {
    insights.push('High model count may have diminishing returns');
  }

  return insights.join('; ');
}

// ============================================================================
// ORCHESTRATOR INTELLIGENCE SUMMARY
// ============================================================================

/**
 * Get summary of orchestrator's intelligence and learnings.
 *
 * @returns {Promise<Object>} Intelligence summary
 */
export async function getIntelligenceSummary() {
  try {
    const thompsonStats = thompson.getAllModelStats();
    const decisionSummary = await integration.getDecisionSummary({ limit: 100 });

    // Load orchestrator learnings
    let learnings = [];
    if (existsSync(LEARNINGS_LOG)) {
      const lines = readFileSync(LEARNINGS_LOG, 'utf-8').trim().split('\n').filter(Boolean);
      learnings = lines.slice(-20).map(line => {
        try {
          return JSON.parse(line);
        } catch (_err) {
          return null;
        }
      }).filter(Boolean);
    }

    const successLearnings = learnings.filter(l => l.learning_type === 'success_pattern');
    const failureLearnings = learnings.filter(l => l.learning_type === 'failure_pattern');

    return {
      thompson_sampling: {
        models_tracked: thompsonStats.length,
        stats: thompsonStats,
      },
      decisions: {
        total: decisionSummary.total,
        success_rate: decisionSummary.success_rate,
        avg_quality: decisionSummary.avg_quality,
      },
      learnings: {
        total: learnings.length,
        success_patterns: successLearnings.length,
        failure_patterns: failureLearnings.length,
        recent: learnings.slice(-5),
      },
    };
  } catch (err) {
    console.error(`[getIntelligenceSummary] Error: ${err.message}`);
    return { error: err.message };
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

export { STRATEGIES };

export default {
  analyzeTaskComplexity,
  selectAgentStrategy,
  coordinateTask,
  learnFromCoordination,
  getIntelligenceSummary,
  STRATEGIES,
};
