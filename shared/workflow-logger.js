/**
 * Workflow Execution Logger - Automatic learning capture
 *
 * Phase 1: Supervised learning - automatic logging wrapper for workflows
 *
 * This module provides a lightweight wrapper that automatically logs
 * workflow executions to the learning database without requiring changes
 * to existing workflow code.
 *
 * Usage in workflows:
 *
 * ```javascript
 * import { logWorkflowExecution } from './shared/workflow-logger.js';
 *
 * // At the start of your workflow
 * const logger = logWorkflowExecution({
 *   workflow: 'code-review',
 *   taskType: 'security',
 *   model: 'opus',
 *   runId: process.env.LEARNING_RUN_ID // Optional: ties multiple executions together
 * });
 *
 * try {
 *   // ... your workflow code ...
 *   const result = await someOperation();
 *
 *   // Log success
 *   logger.success({
 *     qualityScore: 0.92,
 *     inputTokens: 1500,
 *     outputTokens: 800,
 *     costUsd: 0.024,
 *     durationMs: 3200
 *   });
 * } catch (error) {
 *   // Log failure
 *   logger.error(error);
 * }
 * ```
 *
 * For multi-AI consensus workflows:
 *
 * ```javascript
 * import { logConsensusExecution } from './shared/workflow-logger.js';
 *
 * const consensusLogger = logConsensusExecution({
 *   workflow: 'ai-consensus-debate',
 *   taskType: 'architecture',
 *   workers: ['opus', 'sonnet', 'gpt4o'],
 *   arbiter: 'gemini',
 *   runId: process.env.LEARNING_RUN_ID
 * });
 *
 * // Log each worker result
 * for (const workerResult of workerResults) {
 *   consensusLogger.logWorker({
 *     model: workerResult.model,
 *     phase: 'Proposal',
 *     qualityScore: workerResult.quality,
 *     confidence: workerResult.confidence,
 *     wasSelected: workerResult.model === selectedModel,
 *     inputTokens: workerResult.inputTokens,
 *     outputTokens: workerResult.outputTokens,
 *     costUsd: workerResult.cost,
 *     durationMs: workerResult.duration
 *   });
 * }
 *
 * // Log arbiter decision
 * consensusLogger.logArbiter({
 *   model: 'gemini',
 *   consensusScore: 0.91,
 *   inputTokens: 3000,
 *   outputTokens: 500,
 *   costUsd: 0.035,
 *   durationMs: 2100
 * });
 *
 * // Log combination (synergy tracking)
 * consensusLogger.logCombination({
 *   consensusScore: 0.91,
 *   qualityScore: 0.94,
 *   totalCostUsd: 0.15,
 *   totalDurationMs: 12000
 * });
 * ```
 */

import {
  logExecution,
  logWorkerResult,
  logCombination,
  isAvailable
} from './learning-logger.js';

import { randomUUID } from 'crypto';

/**
 * Create a logger for a single workflow execution
 */
export function logWorkflowExecution(config) {
  const {
    workflow,
    taskType,
    model = 'unknown',
    modelRole = 'worker',
    phase = null,
    label = null,
    runId = null,
    parameters = {}
  } = config;

  const startTime = Date.now();
  const actualRunId = runId || randomUUID();
  let executionId = -1;

  // Check if logging is available
  if (!isAvailable()) {
    // Return no-op logger if database unavailable
    return {
      success: () => {},
      error: () => {},
      update: () => {},
      getRunId: () => actualRunId,
      getId: () => -1
    };
  }

  return {
    /**
     * Log successful completion
     */
    success(metrics = {}) {
      const durationMs = metrics.durationMs || (Date.now() - startTime);

      executionId = logExecution({
        run_id: actualRunId,
        model,
        model_role: modelRole,
        workflow,
        task_type: taskType,
        phase,
        label,
        parameters,
        quality_score: metrics.qualityScore,
        confidence: metrics.confidence,
        consensus_score: metrics.consensusScore,
        was_selected: metrics.wasSelected || false,
        input_tokens: metrics.inputTokens || 0,
        output_tokens: metrics.outputTokens || 0,
        cost_usd: metrics.costUsd || 0.0,
        duration_ms: durationMs,
        outcome: 'success',
        outcome_notes: metrics.notes
      });

      return executionId;
    },

    /**
     * Log error/failure
     */
    error(error, metrics = {}) {
      const durationMs = metrics.durationMs || (Date.now() - startTime);

      executionId = logExecution({
        run_id: actualRunId,
        model,
        model_role: modelRole,
        workflow,
        task_type: taskType,
        phase,
        label,
        parameters,
        quality_score: metrics.qualityScore || 0,
        confidence: metrics.confidence || 0,
        input_tokens: metrics.inputTokens || 0,
        output_tokens: metrics.outputTokens || 0,
        cost_usd: metrics.costUsd || 0.0,
        duration_ms: durationMs,
        outcome: 'error',
        outcome_notes: error.message || String(error),
        error: error.stack || String(error)
      });

      return executionId;
    },

    /**
     * Update existing execution (rarely needed)
     */
    update(metrics = {}) {
      if (executionId === -1) {
        // No execution logged yet, log it now
        return this.success(metrics);
      }

      // For updates, we'd need to extend learning-logger.js
      // For Phase 1, just log a new execution
      return this.success(metrics);
    },

    /**
     * Get the run ID (useful for passing to child workflows)
     */
    getRunId() {
      return actualRunId;
    },

    /**
     * Get the execution ID
     */
    getId() {
      return executionId;
    }
  };
}

/**
 * Create a logger for multi-AI consensus workflows
 */
export function logConsensusExecution(config) {
  const {
    workflow,
    taskType,
    workers = [],
    arbiter = null,
    runId = null,
    parameters = {}
  } = config;

  const actualRunId = runId || randomUUID();
  const workerIds = [];
  const arbiterIds = [];

  if (!isAvailable()) {
    return {
      logWorker: () => {},
      logArbiter: () => {},
      logCombination: () => {},
      getRunId: () => actualRunId
    };
  }

  return {
    /**
     * Log a worker's result
     */
    logWorker(workerData) {
      const id = logWorkerResult({
        run_id: actualRunId,
        model: workerData.model,
        model_role: 'worker',
        workflow,
        task_type: taskType,
        phase: workerData.phase || null,
        label: workerData.label || `worker:${workerData.model}`,
        parameters,
        quality_score: workerData.qualityScore,
        confidence: workerData.confidence,
        consensus_score: workerData.consensusScore,
        was_selected: workerData.wasSelected || false,
        input_tokens: workerData.inputTokens || 0,
        output_tokens: workerData.outputTokens || 0,
        cost_usd: workerData.costUsd || 0.0,
        duration_ms: workerData.durationMs || 0,
        outcome: workerData.outcome || 'success',
        error: workerData.error || null
      });

      workerIds.push(id);
      return id;
    },

    /**
     * Log the arbiter's decision
     */
    logArbiter(arbiterData) {
      const id = logExecution({
        run_id: actualRunId,
        model: arbiterData.model,
        model_role: 'arbiter',
        workflow,
        task_type: taskType,
        phase: arbiterData.phase || 'Decision',
        label: arbiterData.label || `arbiter:${arbiterData.model}`,
        parameters,
        quality_score: arbiterData.qualityScore,
        confidence: arbiterData.confidence,
        consensus_score: arbiterData.consensusScore,
        was_selected: true, // Arbiter is always "selected"
        input_tokens: arbiterData.inputTokens || 0,
        output_tokens: arbiterData.outputTokens || 0,
        cost_usd: arbiterData.costUsd || 0.0,
        duration_ms: arbiterData.durationMs || 0,
        outcome: arbiterData.outcome || 'success',
        error: arbiterData.error || null
      });

      arbiterIds.push(id);
      return id;
    },

    /**
     * Log the model combination (for synergy tracking)
     */
    logCombination(combinationData) {
      const id = logCombination({
        task_type: taskType,
        worker_models: workers,
        arbiter_model: arbiter,
        consensus_score: combinationData.consensusScore,
        quality_score: combinationData.qualityScore,
        total_cost_usd: combinationData.totalCostUsd || 0.0,
        total_duration_ms: combinationData.totalDurationMs || 0,
        synergy_score: combinationData.synergyScore || 0,
        diversity_score: combinationData.diversityScore || 0
      });

      return id;
    },

    /**
     * Get the run ID
     */
    getRunId() {
      return actualRunId;
    },

    /**
     * Get all logged IDs
     */
    getIds() {
      return {
        runId: actualRunId,
        workers: workerIds,
        arbiters: arbiterIds
      };
    }
  };
}

/**
 * Convenience: wrap an async function with automatic success/error logging
 *
 * Usage:
 *   const result = await withLogging({
 *     workflow: 'code-review',
 *     taskType: 'security',
 *     model: 'opus'
 *   }, async () => {
 *     // ... your workflow code ...
 *     return { findings: [...] };
 *   });
 */
export async function withLogging(config, fn) {
  const logger = logWorkflowExecution(config);

  try {
    const result = await fn();

    // Try to extract metrics from result if available
    const metrics = {
      qualityScore: result?.metrics?.quality || result?.quality_score,
      confidence: result?.metrics?.confidence || result?.confidence,
      inputTokens: result?.metrics?.inputTokens || result?.input_tokens,
      outputTokens: result?.metrics?.outputTokens || result?.output_tokens,
      costUsd: result?.metrics?.cost || result?.cost_usd,
      durationMs: result?.metrics?.duration || result?.duration_ms
    };

    logger.success(metrics);
    return result;
  } catch (error) {
    logger.error(error);
    throw error;
  }
}

/**
 * Environment variable helpers for passing run IDs between workflows
 */
export function getCurrentRunId() {
  return process.env.LEARNING_RUN_ID || null;
}

export function setRunIdEnv(runId) {
  process.env.LEARNING_RUN_ID = runId;
}

export function clearRunIdEnv() {
  delete process.env.LEARNING_RUN_ID;
}

export default {
  logWorkflowExecution,
  logConsensusExecution,
  withLogging,
  getCurrentRunId,
  setRunIdEnv,
  clearRunIdEnv
};
