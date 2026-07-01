#!/usr/bin/env node

/**
 * Fleet-Aware Workflow Wrapper
 *
 * Transparently distributes workflow agent() and parallel() calls across
 * 8-worker API-only fleet with automatic PostgreSQL storage tracking.
 *
 * Architecture:
 * - 8 workers: server-01/02/03, laptop-01, pi-01/02, desktop-ap, server-ap
 * - SSH user: 'claude' (all nodes)
 * - Distribution: Round-robin with health checks
 * - Storage: PostgreSQL workflow.* tables via workflow-storage-adapter.cjs
 * - Fallback: Local execution if all workers fail
 *
 * Usage (Opt-In Pattern):
 *
 *   import { createFleetWorkflow } from './shared/fleet-workflow-wrapper.mjs';
 *
 *   export default async function({ args }) {
 *     const { agent, parallel, phase, complete } = createFleetWorkflow(
 *       'workflow-name',
 *       'task description',
 *       { enableFleet: true, enableStorage: true }
 *     );
 *
 *     // Same API as before, but now fleet-aware
 *     const result = await agent('Analyze this code', { model: 'claude-opus-4' });
 *     const results = await parallel([...tasks]);
 *     return complete(result, 0.85);
 *   }
 *
 * Integration with Issue #11:
 * - Tracks hostname for each agent execution
 * - Records distribution in PostgreSQL workflow.worker_results
 * - Provides execution stats via getExecutionStats()
 *
 * Created: 2026-06-28
 */

import { createRequire } from 'module';
import { execSync, spawn } from 'child_process';
import crypto from 'crypto';
import path from 'path';
import { fileURLToPath } from 'url';
import os from 'os';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Import fleet utilities using dynamic imports (handles both ESM and CJS)
const fleetUtilsModule = await import('./fleet-utils.js');
const remoteExec = fleetUtilsModule.remoteExec;

const fleetTopologyModule = await import('./fleet-topology.js');
const FLEET_NODES = fleetTopologyModule.FLEET_NODES;

// Storage adapter disabled - requires conversion to ESM
// TODO: Convert workflow-storage-adapter.cjs from CommonJS to ESM
let getWorkflowStorage = () => null;

// Feedback capture system (Issue #249)
const feedbackCaptureModule = await import('./workflow-feedback-capture.js');
const { captureWorkflowFeedback } = feedbackCaptureModule;

// Module-level state for round-robin distribution
let nextWorkerIndex = 0;
const executionHistory = [];

// Worker nodes (exclude orchestrator aio-01)
const WORKERS = FLEET_NODES.filter(n => n.roles.includes('worker'));

/**
 * Create a fleet-aware workflow execution context
 *
 * @param {string} workflowName - Workflow identifier (e.g., 'deep-research')
 * @param {string} taskDescription - Original task/prompt
 * @param {Object} options - Configuration options
 * @param {boolean} [options.enableFleet=true] - Enable fleet distribution
 * @param {boolean} [options.enableStorage=true] - Enable PostgreSQL storage
 * @param {string} [options.fleetStrategy='round-robin'] - Distribution strategy
 * @param {string} [options.sshUser='claude'] - SSH username for fleet
 * @param {number} [options.timeout=300000] - Agent timeout in ms (5 min)
 * @param {number} [options.maxRetries=2] - Max retry attempts per agent
 * @param {boolean} [options.fallbackToLocal=true] - Fallback to local on failure
 * @returns {Object} Workflow execution context { agent, parallel, phase, complete, getStats }
 *
 * @example
 *   const { agent, parallel, complete } = createFleetWorkflow('my-workflow', 'task desc');
 *   const result = await agent('Do something', { model: 'claude-sonnet-4' });
 *   await complete(result, 0.9);
 */
export function createFleetWorkflow(workflowName, taskDescription, options = {}) {
  const config = {
    enableFleet: options.enableFleet !== false,
    enableStorage: options.enableStorage !== false,
    fleetStrategy: options.fleetStrategy || 'round-robin',
    sshUser: options.sshUser || 'claude',
    timeout: options.timeout || 300000,
    maxRetries: options.maxRetries || 2,
    fallbackToLocal: options.fallbackToLocal !== false,
    ...options
  };

  // Initialize storage
  const db = config.enableStorage ? getWorkflowStorage() : null;

  // Workflow metadata
  const workflowId = `wf-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
  const startTime = Date.now();
  let workflowExecutionId = null;

  // Execution tracking
  const workers = [];
  const phases = [];
  const learnings = [];
  let arbiter = null;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalCostUsd = 0;

  /**
   * Select next worker using configured strategy
   *
   * @param {Object} task - Task metadata for strategy selection
   * @param {number} taskIndex - Task index for distribution
   * @returns {Object} Selected worker node
   * @throws {Error} If no healthy workers available
   */
  function selectWorker(task, taskIndex) {
    switch (config.fleetStrategy) {
      case 'round-robin':
        // Simple round-robin with health awareness
        const startIndex = nextWorkerIndex;
        let attempts = 0;

        while (attempts < WORKERS.length) {
          const worker = WORKERS[nextWorkerIndex % WORKERS.length];
          nextWorkerIndex++;

          // Skip if known to be unhealthy (from executionHistory)
          const recentFailures = executionHistory
            .filter(e => e.hostname === worker.hostname && !e.success)
            .slice(-3);

          if (recentFailures.length < 3) {
            return worker;
          }

          attempts++;
        }

        // All workers have recent failures, just return next one anyway
        console.warn('All workers have recent failures, attempting next worker anyway');
        return WORKERS[nextWorkerIndex++ % WORKERS.length];

      case 'cost-optimized':
        // Prefer Pi nodes for lightweight tasks
        if (task.estimated_tokens && task.estimated_tokens < 1000) {
          const piWorkers = WORKERS.filter(w => w.architecture === 'aarch64');
          if (piWorkers.length > 0) {
            return piWorkers[taskIndex % piWorkers.length];
          }
        }
        return WORKERS[taskIndex % WORKERS.length];

      case 'load-aware':
        // TODO: Query PostgreSQL for least-loaded worker
        // For now, fallback to round-robin
        return WORKERS[taskIndex % WORKERS.length];

      default:
        return WORKERS[taskIndex % WORKERS.length];
    }
  }

  /**
   * Execute agent task on remote fleet worker
   *
   * @param {Object} worker - Worker node from FLEET_NODES
   * @param {string} prompt - Agent prompt
   * @param {Object} taskOptions - Task execution options
   * @returns {Promise<Object>} { output, hostname, model, cost, duration, success }
   * @throws {Error} If execution fails after retries
   */
  async function executeOnFleet(worker, prompt, taskOptions = {}) {
    const model = taskOptions.model || 'claude-sonnet-4';
    const cwd = taskOptions.cwd || process.cwd();
    const start = Date.now();

    // Build remote command
    // Note: Assumes 'claude' CLI is available on worker
    // Do NOT escape prompt here - remoteExec() handles all escaping automatically
    const command = `echo ${JSON.stringify(prompt)} | claude --model ${model} 2>&1`;

    try {
      const result = remoteExec(worker.hostname, command, {
        timeout: config.timeout,
        throwOnError: false,
        cwd
      });

      const duration = Date.now() - start;

      if (!result.success) {
        throw new Error(
          `Remote execution failed on ${worker.hostname}: ${result.stderr || result.stdout}`
        );
      }

      // Parse output (may be plain text or JSON)
      let output = result.stdout;
      let parsedResult = null;

      try {
        parsedResult = JSON.parse(result.stdout);
        output = parsedResult.text || parsedResult.response || result.stdout;
      } catch (parseError) {
        // Not JSON, use raw output
      }

      // Extract cost/tokens if available
      const inputTokens = parsedResult?.usage?.input_tokens || 0;
      const outputTokens = parsedResult?.usage?.output_tokens || 0;
      const cost = parsedResult?.usage?.cost_usd || 0;

      return {
        output,
        hostname: worker.hostname,
        model,
        inputTokens,
        outputTokens,
        cost,
        duration,
        success: true
      };

    } catch (error) {
      return {
        output: '',
        hostname: worker.hostname,
        model,
        inputTokens: 0,
        outputTokens: 0,
        cost: 0,
        duration: Date.now() - start,
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Execute agent task locally (fallback)
   *
   * @param {string} prompt - Agent prompt
   * @param {Object} taskOptions - Task execution options
   * @returns {Promise<Object>} { output, hostname, model, cost, duration, success }
   */
  async function executeLocal(prompt, taskOptions = {}) {
    const model = taskOptions.model || 'claude-sonnet-4';
    const start = Date.now();

    return new Promise((resolve, reject) => {
      const agent = spawn('claude', [
        '--model', model,
        '--message', prompt
      ], {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      agent.stdout.on('data', (data) => { stdout += data.toString(); });
      agent.stderr.on('data', (data) => { stderr += data.toString(); });

      const timeout = setTimeout(() => {
        agent.kill();
        reject(new Error(`Local agent timeout after ${config.timeout}ms`));
      }, config.timeout);

      agent.on('close', (code) => {
        clearTimeout(timeout);
        const duration = Date.now() - start;

        if (code !== 0) {
          resolve({
            output: '',
            hostname: 'localhost',
            model,
            inputTokens: 0,
            outputTokens: 0,
            cost: 0,
            duration,
            success: false,
            error: stderr || stdout
          });
          return;
        }

        // Parse output
        let output = stdout;
        let parsedResult = null;

        try {
          parsedResult = JSON.parse(stdout);
          output = parsedResult.text || parsedResult.response || stdout;
        } catch (parseError) {
          // Not JSON, use raw
        }

        const inputTokens = parsedResult?.usage?.input_tokens || 0;
        const outputTokens = parsedResult?.usage?.output_tokens || 0;
        const cost = parsedResult?.usage?.cost_usd || 0;

        resolve({
          output,
          hostname: 'localhost',
          model,
          inputTokens,
          outputTokens,
          cost,
          duration,
          success: true
        });
      });

      agent.on('error', (error) => {
        clearTimeout(timeout);
        resolve({
          output: '',
          hostname: 'localhost',
          model,
          inputTokens: 0,
          outputTokens: 0,
          cost: 0,
          duration: Date.now() - start,
          success: false,
          error: error.message
        });
      });
    });
  }

  /**
   * Track execution in history (for Issue #11 debugging)
   *
   * @param {string} hostname - Worker hostname
   * @param {string} prompt - Agent prompt
   * @param {Object} result - Execution result
   */
  function trackExecution(hostname, prompt, result) {
    executionHistory.push({
      timestamp: new Date().toISOString(),
      workflowName,
      hostname,
      promptHash: crypto.createHash('md5').update(prompt).digest('hex').slice(0, 8),
      success: result.success,
      duration: result.duration,
      model: result.model
    });

    // Keep last 1000 entries
    if (executionHistory.length > 1000) {
      executionHistory.shift();
    }
  }

  /**
   * Fleet-aware agent execution
   *
   * @param {string} prompt - Agent prompt
   * @param {Object} taskOptions - Task execution options
   * @param {string} [taskOptions.model='claude-sonnet-4'] - Model to use
   * @param {string} [taskOptions.type='agent'] - Task type for tracking
   * @param {boolean} [taskOptions.useFleet=true] - Use fleet distribution
   * @param {string} [taskOptions.cwd] - Working directory
   * @returns {Promise<string>} Agent output
   */
  async function agent(prompt, taskOptions = {}) {
    const shouldUseFleet = config.enableFleet &&
                          (taskOptions.useFleet !== false) &&
                          WORKERS.length > 0;

    if (!shouldUseFleet) {
      // Local execution
      const result = await executeLocal(prompt, taskOptions);
      trackExecution('localhost', prompt, result);

      if (config.enableStorage && workflowExecutionId) {
        await recordWorkerResult({
          prompt,
          result: result.output,
          ...result,
          taskType: taskOptions.type || 'agent'
        });
      }

      if (!result.success) {
        throw new Error(`Local agent failed: ${result.error}`);
      }

      return result.output;
    }

    // Fleet execution with retry
    let lastError = null;

    for (let attempt = 0; attempt < config.maxRetries; attempt++) {
      try {
        const worker = selectWorker(taskOptions, workers.length);
        const result = await executeOnFleet(worker, prompt, taskOptions);

        trackExecution(worker.hostname, prompt, result);

        if (config.enableStorage && workflowExecutionId) {
          await recordWorkerResult({
            prompt,
            result: result.output,
            ...result,
            taskType: taskOptions.type || 'agent'
          });
        }

        if (result.success) {
          return result.output;
        }

        lastError = result.error;
        console.warn(`Fleet agent attempt ${attempt + 1} failed on ${worker.hostname}: ${result.error}`);

      } catch (error) {
        lastError = error.message;
        console.warn(`Fleet agent attempt ${attempt + 1} exception: ${error.message}`);
      }
    }

    // All retries failed - fallback to local if enabled
    if (config.fallbackToLocal) {
      console.warn('All fleet workers failed, falling back to local execution');
      const result = await executeLocal(prompt, taskOptions);
      trackExecution('localhost', prompt, result);

      if (config.enableStorage && workflowExecutionId) {
        await recordWorkerResult({
          prompt,
          result: result.output,
          ...result,
          taskType: taskOptions.type || 'agent',
          metadata: { fallback_to_local: true }
        });
      }

      if (!result.success) {
        throw new Error(`Local agent failed after fleet exhaustion: ${result.error}`);
      }

      return result.output;
    }

    throw new Error(`Fleet execution failed after all retries: ${lastError}`);
  }

  /**
   * Fleet-aware parallel execution
   *
   * Distributes tasks across all 8 workers with intelligent batching.
   *
   * @param {Array<Object>} tasks - Array of task objects
   * @param {string} tasks[].prompt - Agent prompt
   * @param {string} [tasks[].model] - Model to use
   * @param {string} [tasks[].type] - Task type for tracking
   * @param {Object} parallelOptions - Parallel execution options
   * @param {number} [parallelOptions.maxConcurrency=8] - Max concurrent tasks
   * @returns {Promise<Array<string>>} Array of agent outputs
   *
   * @example
   *   const results = await parallel([
   *     { prompt: 'Task 1', model: 'claude-sonnet-4', type: 'search' },
   *     { prompt: 'Task 2', model: 'claude-opus-4', type: 'analysis' }
   *   ]);
   */
  async function parallel(tasks, parallelOptions = {}) {
    const maxConcurrency = parallelOptions.maxConcurrency || 8;

    if (!config.enableFleet || tasks.length === 1) {
      // Fallback to local sequential execution
      const results = [];
      for (const task of tasks) {
        const result = await agent(task.prompt, task);
        results.push(result);
      }
      return results;
    }

    console.log(`\n🚀 FLEET PARALLEL: ${tasks.length} tasks across ${WORKERS.length} workers`);

    const results = [];
    const executing = [];

    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];

      const promise = agent(task.prompt, { ...task, useFleet: true })
        .then(result => {
          results[i] = result;
          executing.splice(executing.indexOf(promise), 1);
        })
        .catch(error => {
          console.error(`Task ${i} failed: ${error.message}`);
          results[i] = null;
          executing.splice(executing.indexOf(promise), 1);
        });

      executing.push(promise);

      // Throttle concurrency
      if (executing.length >= maxConcurrency) {
        await Promise.race(executing);
      }
    }

    // Wait for remaining tasks
    await Promise.all(executing);

    console.log(`✅ Fleet parallel complete: ${results.filter(r => r !== null).length}/${tasks.length} succeeded`);

    return results;
  }

  /**
   * Track a workflow phase
   *
   * @param {string} phaseName - Phase identifier
   * @param {Function} fn - Async function to execute
   * @returns {Promise<any>} Result from fn
   */
  async function phase(phaseName, fn) {
    const phaseStart = Date.now();
    console.log(`\n📋 PHASE: ${phaseName.toUpperCase()}`);

    try {
      const result = await fn();

      phases.push({
        name: phaseName,
        status: 'completed',
        durationMs: Date.now() - phaseStart,
        order: phases.length
      });

      if (config.enableStorage && workflowExecutionId) {
        await db.storePhase({
          workflow_execution_id: workflowExecutionId,
          phase_name: phaseName,
          phase_order: phases.length - 1,
          duration_ms: Date.now() - phaseStart,
          outcome: 'success'
        });
      }

      console.log(`✅ Phase ${phaseName} completed in ${Date.now() - phaseStart}ms`);
      return result;

    } catch (error) {
      phases.push({
        name: phaseName,
        status: 'failed',
        error: error.message,
        durationMs: Date.now() - phaseStart,
        order: phases.length
      });

      if (config.enableStorage && workflowExecutionId) {
        await db.storePhase({
          workflow_execution_id: workflowExecutionId,
          phase_name: phaseName,
          phase_order: phases.length - 1,
          duration_ms: Date.now() - phaseStart,
          outcome: 'error',
          metadata: { error: error.message }
        });
      }

      console.error(`❌ Phase ${phaseName} failed: ${error.message}`);
      throw error;
    }
  }

  /**
   * Record worker result in PostgreSQL
   *
   * @param {Object} data - Worker execution data
   */
  async function recordWorkerResult(data) {
    if (!config.enableStorage || !db || !workflowExecutionId) {
      return;
    }

    try {
      await db.storeWorkerResult({
        workflow_execution_id: workflowExecutionId,
        worker_id: `agent-${Date.now()}-${crypto.randomBytes(2).toString('hex')}`,
        model: data.model || 'claude-sonnet-4',
        task_assigned: data.prompt.substring(0, 200),
        result: data.result.substring(0, 4000),
        confidence: null,
        duration_ms: data.duration,
        input_tokens: data.inputTokens || null,
        output_tokens: data.outputTokens || null,
        cost_usd: data.cost || 0,
        outcome: data.success ? 'success' : 'error',
        metadata: {
          hostname: data.hostname,
          task_type: data.taskType,
          fleet_distribution: config.fleetStrategy,
          ...data.metadata
        }
      });

      // Update totals
      totalInputTokens += data.inputTokens || 0;
      totalOutputTokens += data.outputTokens || 0;
      totalCostUsd += data.cost || 0;

    } catch (error) {
      console.warn(`Failed to record worker result: ${error.message}`);
    }
  }

  /**
   * Add a learning
   *
   * @param {string} description - Learning description
   * @param {string} insight - Actionable insight
   * @param {number} importance - Importance score 0-1
   * @param {Object} evidence - Supporting evidence
   */
  function addLearning(description, insight, importance, evidence) {
    learnings.push({
      description,
      insight,
      importance,
      evidence
    });
  }

  /**
   * Track arbiter decision
   *
   * @param {Object} arbiterData - Arbiter metadata
   */
  function trackArbiter(arbiterData) {
    arbiter = arbiterData;
    console.log(`  ↳ Arbiter: ${arbiterData.model} → ${arbiterData.decision}`);
  }

  /**
   * Complete workflow and store all data
   *
   * @param {any} finalResult - Final workflow result
   * @param {number} qualityScore - Overall quality score 0-1
   * @param {string} outcome - 'success' | 'failed' | 'error'
   * @returns {Promise<Object>} Stored execution data
   */
  async function complete(finalResult, qualityScore, outcome = 'success') {
    const totalDuration = Date.now() - startTime;

    console.log(`\n🎯 COMPLETING WORKFLOW: ${workflowName}`);
    console.log(`   Workers: ${workers.length}`);
    console.log(`   Phases: ${phases.length}`);
    console.log(`   Learnings: ${learnings.length}`);
    console.log(`   Duration: ${totalDuration}ms`);
    console.log(`   Cost: $${totalCostUsd.toFixed(4)}`);

    if (!config.enableStorage) {
      return { result: finalResult, stored: false };
    }

    try {
      // Store main execution record
      workflowExecutionId = await db.storeExecution({
        workflow_id: workflowId,
        workflow_name: workflowName,
        task_description: taskDescription,
        total_workers: workers.length,
        total_duration_ms: totalDuration,
        outcome,
        metadata: {
          quality_score: qualityScore,
          input_tokens: totalInputTokens,
          output_tokens: totalOutputTokens,
          cost_usd: totalCostUsd,
          fleet_strategy: config.fleetStrategy,
          fleet_enabled: config.enableFleet,
          workers_used: workers.length,
          phases_count: phases.length,
          learnings_count: learnings.length
        }
      });

      // Store learnings
      for (const learning of learnings) {
        await db.storeLearnings({
          workflow_execution_id: workflowExecutionId,
          learning_type: 'pattern',
          description: learning.description,
          actionable_insight: learning.insight,
          importance: learning.importance,
          metadata: learning.evidence
        });
      }

      console.log(`✅ Auto-storage complete: execution ID ${workflowExecutionId}`);

      // Capture automated feedback (Issue #249)
      try {
        await captureWorkflowFeedback({
          workflow_execution_id: workflowExecutionId,
          quality_score: qualityScore,
          metrics: {
            workers_count: workers.length,
            phases_count: phases.length,
            learnings_count: learnings.length
          },
          outcome,
          metadata: {
            fleet_strategy: config.fleetStrategy,
            fleet_enabled: config.enableFleet,
            total_duration_ms: totalDuration,
            total_cost_usd: totalCostUsd
          }
        });
      } catch (feedbackError) {
        console.warn(`⚠️  Feedback capture failed (non-fatal): ${feedbackError.message}`);
      }

      return {
        result: finalResult,
        stored: true,
        executionId: workflowExecutionId,
        workflowId,
        durationMs: totalDuration,
        costUsd: totalCostUsd
      };

    } catch (error) {
      console.error(`❌ Auto-storage failed: ${error.message}`);
      throw error;
    }
  }

  /**
   * Get execution statistics (for Issue #11 debugging)
   *
   * @returns {Object} Per-host execution statistics
   */
  function getExecutionStats() {
    const stats = {};

    for (const entry of executionHistory.filter(e => e.workflowName === workflowName)) {
      if (!stats[entry.hostname]) {
        stats[entry.hostname] = {
          total: 0,
          success: 0,
          totalDuration: 0,
          avgDuration: 0
        };
      }

      stats[entry.hostname].total++;
      if (entry.success) {
        stats[entry.hostname].success++;
      }
      stats[entry.hostname].totalDuration += entry.duration;
    }

    // Calculate averages and success rates
    for (const host of Object.keys(stats)) {
      stats[host].avgDuration = stats[host].totalDuration / stats[host].total;
      stats[host].successRate = stats[host].success / stats[host].total;
    }

    return stats;
  }

  // Public API
  return {
    agent,
    parallel,
    phase,
    complete,
    addLearning,
    trackArbiter,
    getExecutionStats,
    config // Expose config for introspection
  };
}

/**
 * Get global execution statistics across all workflows
 *
 * @returns {Object} Per-host statistics for all workflows
 */
export function getGlobalExecutionStats() {
  const stats = {};

  for (const entry of executionHistory) {
    if (!stats[entry.hostname]) {
      stats[entry.hostname] = {
        total: 0,
        success: 0,
        totalDuration: 0,
        avgDuration: 0,
        byWorkflow: {}
      };
    }

    stats[entry.hostname].total++;
    if (entry.success) {
      stats[entry.hostname].success++;
    }
    stats[entry.hostname].totalDuration += entry.duration;

    // Track per-workflow stats
    if (!stats[entry.hostname].byWorkflow[entry.workflowName]) {
      stats[entry.hostname].byWorkflow[entry.workflowName] = { total: 0, success: 0 };
    }
    stats[entry.hostname].byWorkflow[entry.workflowName].total++;
    if (entry.success) {
      stats[entry.hostname].byWorkflow[entry.workflowName].success++;
    }
  }

  // Calculate aggregates
  for (const host of Object.keys(stats)) {
    stats[host].avgDuration = stats[host].totalDuration / stats[host].total;
    stats[host].successRate = stats[host].success / stats[host].total;
  }

  return stats;
}

/**
 * Clear execution history (useful for testing)
 */
export function clearExecutionHistory() {
  executionHistory.length = 0;
  nextWorkerIndex = 0;
}

/**
 * Get current execution history (for debugging)
 *
 * @param {number} limit - Max entries to return (default: 100)
 * @returns {Array} Recent execution history
 */
export function getExecutionHistory(limit = 100) {
  return executionHistory.slice(-limit);
}
