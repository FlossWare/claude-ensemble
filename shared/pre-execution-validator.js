/**
 * Pre-Execution Validation Layer
 *
 * Validates fleet orchestration parameters before worker dispatch to prevent
 * common failure modes identified in ECC issue #193:
 *
 * 1. Parallelizability detection - warns if sequential execution detected
 * 2. Token budget validation - prevents cascading budget exhaustion
 * 3. Model diversity checks - alerts if >70/30 concentration detected
 * 4. Worker capacity planning - prevents timeout failures from overload
 *
 * Integration: Called by fleet orchestrators before task dispatch
 * Strategy: Fail-open (proceed with warnings if validation unavailable)
 * Override: options.skipPreValidation = true to bypass checks
 *
 * Created: 2026-07-01
 * Issue: ECC #193
 */

import os from 'os';
import path from 'path';

/**
 * Pre-validation result structure
 * @typedef {Object} ValidationResult
 * @property {boolean} passed - Overall validation status (false = blockers present)
 * @property {string[]} warnings - Non-blocking issues to log
 * @property {string[]} blockers - Blocking issues (execution should abort)
 * @property {string[]} recommendations - Optimization suggestions
 * @property {Object} details - Detailed validation data for debugging
 */

/**
 * Main pre-validation function
 * Runs all validators in parallel and aggregates results
 *
 * @param {Object} config - Validation configuration
 * @param {Array<{id: string, prompt: string}>} config.tasks - Tasks to validate
 * @param {number} [config.maxParallel] - Max concurrent workers
 * @param {string[]} [config.availableWorkers] - Worker hostnames
 * @param {Object} [config.tokenBudget] - Token budget tracker instance
 * @param {Object} [config.healthCache] - Worker health cache from orchestrator
 * @returns {Promise<ValidationResult>}
 */
export async function preValidate(config) {
  const {
    tasks = [],
    maxParallel = 6,
    availableWorkers = [],
    tokenBudget = null,
    healthCache = null
  } = config;

  const result = {
    passed: true,
    warnings: [],
    blockers: [],
    recommendations: [],
    details: {}
  };

  // Run all validators in parallel
  const validators = [
    validateParallelizability(tasks),
    validateTokenBudget(tasks, tokenBudget),
    validateModelDiversity(),
    validateWorkerCapacity(availableWorkers, maxParallel, healthCache)
  ];

  try {
    const [parallelCheck, budgetCheck, diversityCheck, capacityCheck] =
      await Promise.all(validators);

    // Aggregate results
    if (!parallelCheck.passed) {
      result.passed = false;
      result.blockers.push(...parallelCheck.blockers);
    }
    result.warnings.push(...parallelCheck.warnings);
    result.recommendations.push(...parallelCheck.recommendations);
    result.details.parallelizability = parallelCheck.details;

    if (!budgetCheck.passed) {
      result.passed = false;
      result.blockers.push(...budgetCheck.blockers);
    }
    result.warnings.push(...budgetCheck.warnings);
    result.details.tokenBudget = budgetCheck.details;

    if (!diversityCheck.passed) {
      result.warnings.push(...diversityCheck.warnings); // Diversity is warning-only
    }
    result.recommendations.push(...diversityCheck.recommendations);
    result.details.modelDiversity = diversityCheck.details;

    if (!capacityCheck.passed) {
      result.passed = false;
      result.blockers.push(...capacityCheck.blockers);
    }
    result.warnings.push(...capacityCheck.warnings);
    result.recommendations.push(...capacityCheck.recommendations);
    result.details.workerCapacity = capacityCheck.details;

  } catch (error) {
    // Fail-open: validation failure should not block execution
    // But we need to catch individual validator errors, not task structure errors
    const isTaskError = !tasks || !Array.isArray(tasks);

    if (isTaskError) {
      // Task structure error - provide minimal valid result
      return {
        passed: true,
        warnings: [`Validation error (fail-open): ${error.message}`],
        blockers: [],
        recommendations: [],
        details: { validationError: error.message }
      };
    }

    result.warnings.push(`Validation error (fail-open): ${error.message}`);
    result.passed = true; // Allow execution despite validation failure
    result.details.validationError = error.message;
  }

  return result;
}

/**
 * Validate task parallelizability
 * Detects when tasks could be parallelized but execution pattern is sequential
 *
 * @param {Array<{id: string, prompt: string}>} tasks
 * @returns {Promise<Object>} Validation result
 */
export async function validateParallelizability(tasks) {
  const result = {
    passed: true,
    warnings: [],
    blockers: [],
    recommendations: [],
    details: {}
  };

  if (!tasks || tasks.length === 0) {
    result.details.tasksCount = 0;
    return result;
  }

  result.details.tasksCount = tasks.length;

  // Heuristic: Check if tasks appear independent (no cross-references)
  const taskIds = new Set(tasks.map(t => t.id));
  let dependenciesDetected = 0;

  for (const task of tasks) {
    const prompt = task.prompt || '';

    // Check if prompt references other task IDs
    for (const otherId of taskIds) {
      if (otherId !== task.id && prompt.includes(otherId)) {
        dependenciesDetected++;
        break;
      }
    }
  }

  const parallelizableCount = tasks.length - dependenciesDetected;
  result.details.parallelizableCount = parallelizableCount;
  result.details.dependentCount = dependenciesDetected;

  if (parallelizableCount >= 3) {
    // Significant parallelization opportunity
    result.recommendations.push(
      `${parallelizableCount}/${tasks.length} tasks appear parallelizable - ` +
      `expect ~${Math.min(parallelizableCount, 6)}× speedup with fleet execution`
    );
  }

  if (tasks.length >= 3 && parallelizableCount < 2) {
    result.warnings.push(
      `Only ${parallelizableCount}/${tasks.length} tasks are parallelizable - ` +
      `consider task decomposition for better fleet utilization`
    );
  }

  return result;
}

/**
 * Validate token budget constraints
 * Prevents execution if estimated token usage exceeds available budget
 *
 * @param {Array<{id: string, prompt: string}>} tasks
 * @param {Object|null} tokenBudget - Token budget tracker instance
 * @returns {Promise<Object>} Validation result
 */
export async function validateTokenBudget(tasks, tokenBudget) {
  const result = {
    passed: true,
    warnings: [],
    blockers: [],
    recommendations: [],
    details: {}
  };

  if (!tokenBudget || !tasks || tasks.length === 0) {
    result.details.budgetAvailable = false;
    return result;
  }

  try {
    // Estimate token usage: ~4 chars/token average
    const estimatedInputTokens = tasks.reduce((sum, task) => {
      const promptLength = (task.prompt || '').length;
      return sum + Math.ceil(promptLength / 4);
    }, 0);

    // Estimate output tokens (conservative: 2× input)
    const estimatedOutputTokens = estimatedInputTokens * 2;
    const totalEstimated = estimatedInputTokens + estimatedOutputTokens;

    result.details.estimatedInputTokens = estimatedInputTokens;
    result.details.estimatedOutputTokens = estimatedOutputTokens;
    result.details.totalEstimated = totalEstimated;

    // Check if tokenBudget has getRemainingBudget method
    if (typeof tokenBudget.getRemainingBudget === 'function') {
      const remaining = tokenBudget.getRemainingBudget();
      result.details.budgetRemaining = remaining;

      if (totalEstimated > remaining) {
        result.passed = false;
        result.blockers.push(
          `Estimated token usage (${totalEstimated}) exceeds remaining budget (${remaining}). ` +
          `Reduce task count or prompt length.`
        );
      } else if (totalEstimated > remaining * 0.8) {
        result.warnings.push(
          `Estimated token usage (${totalEstimated}) is ${Math.round(totalEstimated/remaining*100)}% ` +
          `of remaining budget (${remaining})`
        );
      }
    } else {
      result.details.budgetTrackerType = 'incompatible';
      result.warnings.push('Token budget tracker does not support getRemainingBudget()');
    }

  } catch (error) {
    result.details.budgetCheckError = error.message;
    result.warnings.push(`Token budget validation failed: ${error.message}`);
  }

  return result;
}

/**
 * Validate model diversity requirements
 * Alerts if recent execution history shows >70/30 model concentration
 *
 * @returns {Promise<Object>} Validation result
 */
export async function validateModelDiversity() {
  const result = {
    passed: true,
    warnings: [],
    blockers: [],
    recommendations: [],
    details: {}
  };

  try {
    // Load PostgreSQL adapter
    const adapterPath = path.join(os.homedir(), '.claude', 'learning', 'postgres-adapter.js');
    const adapter = await import(adapterPath);
    const pool = adapter.default?.pool || adapter.pool;

    if (!pool) {
      result.details.dbAvailable = false;
      return result;
    }

    // Query recent model usage (last 100 executions)
    const queryResult = await pool.query(`
      SELECT
        model,
        COUNT(*) as execution_count,
        AVG(quality_score) as avg_quality
      FROM monitoring.execution_summary
      WHERE timestamp > NOW() - INTERVAL '24 hours'
      GROUP BY model
      ORDER BY execution_count DESC
      LIMIT 10
    `);

    if (queryResult.rows.length === 0) {
      result.details.recentExecutions = 0;
      return result;
    }

    const totalExecutions = queryResult.rows.reduce((sum, r) => sum + parseInt(r.execution_count), 0);
    result.details.totalExecutions = totalExecutions;
    result.details.modelDistribution = queryResult.rows.map(r => ({
      model: r.model,
      count: parseInt(r.execution_count),
      percentage: (parseInt(r.execution_count) / totalExecutions * 100).toFixed(1),
      avgQuality: parseFloat(r.avg_quality)
    }));

    // Check for >70/30 skew
    const topModel = queryResult.rows[0];
    const topModelPercentage = parseInt(topModel.execution_count) / totalExecutions;

    if (topModelPercentage > 0.70) {
      result.passed = true; // Warning-only, not blocking
      result.warnings.push(
        `Model diversity alert: ${topModel.model} used in ${(topModelPercentage * 100).toFixed(1)}% ` +
        `of recent executions (>70% threshold). Risk of feedback loop bias.`
      );
      result.recommendations.push(
        `Consider forced rotation to prevent model concentration. ` +
        `Review orchestrator-learning-adapter.js routing logic.`
      );
    }

    // Check for quality-based stagnation
    if (queryResult.rows.length >= 2) {
      const topQuality = parseFloat(topModel.avg_quality);
      const secondModel = queryResult.rows[1];
      const secondQuality = parseFloat(secondModel.avg_quality);

      if (topQuality > 0 && secondQuality > 0 && Math.abs(topQuality - secondQuality) < 0.05) {
        result.recommendations.push(
          `${topModel.model} (${topQuality.toFixed(3)}) and ${secondModel.model} (${secondQuality.toFixed(3)}) ` +
          `have similar quality - consider exploration to find better models`
        );
      }
    }

  } catch (error) {
    result.details.diversityCheckError = error.message;
    result.warnings.push(`Model diversity validation failed (non-blocking): ${error.message}`);
  }

  return result;
}

/**
 * Validate worker capacity planning
 * Prevents timeout failures from overloaded or unhealthy workers
 *
 * @param {string[]} availableWorkers - Worker hostnames
 * @param {number} maxParallel - Max concurrent tasks
 * @param {Map|null} healthCache - Worker health cache from orchestrator
 * @returns {Promise<Object>} Validation result
 */
export async function validateWorkerCapacity(availableWorkers, maxParallel, healthCache) {
  const result = {
    passed: true,
    warnings: [],
    blockers: [],
    recommendations: [],
    details: {}
  };

  if (!availableWorkers || availableWorkers.length === 0) {
    result.passed = false;
    result.blockers.push('No workers available for execution');
    result.details.workersAvailable = 0;
    return result;
  }

  result.details.workersAvailable = availableWorkers.length;
  result.details.maxParallel = maxParallel;

  // Check health cache if provided
  if (healthCache && healthCache instanceof Map) {
    const now = Date.now();
    const HEALTH_CACHE_TTL_MS = 60000; // 60s TTL from orchestrator

    let healthyCount = 0;
    let unhealthyCount = 0;
    let staleCount = 0;

    for (const worker of availableWorkers) {
      const cached = healthCache.get(worker);

      if (!cached) {
        staleCount++;
      } else if ((now - cached.lastCheck) > HEALTH_CACHE_TTL_MS) {
        staleCount++;
      } else if (cached.healthy) {
        healthyCount++;
      } else {
        unhealthyCount++;
      }
    }

    result.details.healthyWorkers = healthyCount;
    result.details.unhealthyWorkers = unhealthyCount;
    result.details.staleHealthChecks = staleCount;

    if (healthyCount === 0) {
      result.passed = false;
      result.blockers.push(
        unhealthyCount > 0
          ? `All ${unhealthyCount} workers are unhealthy - execution will fail`
          : 'No healthy workers available - execution will fail'
      );
    } else if (healthyCount < maxParallel / 2) {
      result.warnings.push(
        `Only ${healthyCount}/${availableWorkers.length} workers are healthy - ` +
        `may not achieve desired parallelism (maxParallel=${maxParallel})`
      );
      result.recommendations.push(
        `Consider reducing maxParallel to ${healthyCount} or investigate worker health issues`
      );
    }

    if (staleCount > 0) {
      result.warnings.push(
        `${staleCount}/${availableWorkers.length} workers have stale health checks (>60s old)`
      );
    }
  } else {
    result.details.healthCacheAvailable = false;
    result.warnings.push('Worker health cache not available - cannot validate capacity');
  }

  // Check if maxParallel exceeds available workers
  if (maxParallel > availableWorkers.length) {
    result.recommendations.push(
      `maxParallel (${maxParallel}) exceeds available workers (${availableWorkers.length}) - ` +
      `effective parallelism will be limited to ${availableWorkers.length}`
    );
  }

  return result;
}

/**
 * Store validation metrics to PostgreSQL monitoring.validation_stats
 *
 * @param {string} validationType - Type of validation performed
 * @param {boolean} passed - Validation result
 * @param {boolean} blocked - Execution was blocked
 * @param {boolean} overrideUsed - skipPreValidation flag was used
 * @returns {Promise<void>}
 */
export async function recordValidationMetrics(validationType, passed, blocked, overrideUsed) {
  try {
    const adapterPath = path.join(os.homedir(), '.claude', 'learning', 'postgres-adapter.js');
    const adapter = await import(adapterPath);
    const pool = adapter.default?.pool || adapter.pool;

    if (!pool) return;

    await pool.query(`
      INSERT INTO monitoring.validation_stats
      (validation_type, passed, blocked, override_used, timestamp)
      VALUES ($1, $2, $3, $4, NOW())
    `, [validationType, passed, blocked, overrideUsed]);

  } catch (error) {
    // Non-fatal: metrics recording should not break execution
    console.warn('[pre-execution-validator] Failed to record metrics:', error.message);
  }
}

export default {
  preValidate,
  validateParallelizability,
  validateTokenBudget,
  validateModelDiversity,
  validateWorkerCapacity,
  recordValidationMetrics
};
