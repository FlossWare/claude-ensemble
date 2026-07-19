#!/usr/bin/env node

/**
 * Workflow Tracker Middleware
 *
 * Provides automatic tracking and storage for workflow executions.
 * Use this in any .mjs workflow to automatically populate:
 * - workflow.executions
 * - workflow.worker_results
 * - workflow.arbiter_decisions
 * - workflow.phases
 * - workflow.learnings
 *
 * Usage:
 *   import { WorkflowTracker } from './shared/workflow-tracker.js';
 *   const tracker = new WorkflowTracker('workflow-name', 'task description');
 *   await tracker.trackPhase('phase-name', async () => { ... });
 *   tracker.trackWorker({ model, taskType, result, ... });
 *   await tracker.complete(finalResult, qualityScore);
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const path = require('path');
const { WorkflowCompletionHook } = require(path.join(process.env.HOME, '.claude/learning/workflow-completion-hook.js'));

export class WorkflowTracker {
  constructor(workflowName, query) {
    this.workflowName = workflowName;
    this.query = query;
    this.workers = [];
    this.phases = [];
    this.arbiter = null;
    this.learnings = [];
    this.startTime = Date.now();
    this.inputTokens = 0;
    this.outputTokens = 0;
    this.costUsd = 0;
  }

  /**
   * Track a workflow phase
   * @param {string} phaseName - Phase identifier
   * @param {Function} fn - Async function to execute
   * @returns {Promise<any>} Result from fn
   */
  async trackPhase(phaseName, fn) {
    const phaseStart = Date.now();
    console.log(`\n📋 PHASE: ${phaseName.toUpperCase()}`);

    try {
      const result = await fn();

      this.phases.push({
        name: phaseName,
        status: 'completed',
        durationMs: Date.now() - phaseStart,
        order: this.phases.length
      });

      console.log(`✅ Phase ${phaseName} completed in ${Date.now() - phaseStart}ms`);
      return result;

    } catch (error) {
      this.phases.push({
        name: phaseName,
        status: 'failed',
        error: error.message,
        durationMs: Date.now() - phaseStart,
        order: this.phases.length
      });

      console.error(`❌ Phase ${phaseName} failed: ${error.message}`);
      throw error;
    }
  }

  /**
   * Track a worker execution
   * @param {Object} workerData - Worker metadata
   * @param {string} workerData.model - Model used
   * @param {string} workerData.taskType - Type of task
   * @param {any} workerData.result - Worker result
   * @param {number} workerData.qualityScore - Quality score 0-1
   * @param {number} workerData.confidence - Confidence 0-1
   * @param {number} workerData.durationMs - Execution duration
   * @param {string} workerData.parallelGroup - Optional parallel group ID
   */
  trackWorker(workerData) {
    this.workers.push({
      executionOrder: this.workers.length,
      parallelGroup: null,
      ...workerData
    });

    console.log(`  ↳ Worker ${this.workers.length}: ${workerData.model} (${workerData.taskType})`);
  }

  /**
   * Track an arbiter decision
   * @param {Object} arbiterData - Arbiter metadata
   */
  trackArbiter(arbiterData) {
    this.arbiter = arbiterData;
    console.log(`  ↳ Arbiter: ${arbiterData.model} → ${arbiterData.decision}`);
  }

  /**
   * Add a learning
   * @param {string} description - Learning description
   * @param {string} insight - Actionable insight
   * @param {number} importance - Importance 0-1
   * @param {Object} evidence - Supporting evidence
   */
  addLearning(description, insight, importance, evidence) {
    this.learnings.push({
      description,
      insight,
      importance,
      evidence
    });
  }

  /**
   * Track token usage
   * @param {number} inputTokens - Input tokens consumed
   * @param {number} outputTokens - Output tokens generated
   */
  trackTokens(inputTokens, outputTokens) {
    this.inputTokens += inputTokens;
    this.outputTokens += outputTokens;

    // Rough cost estimation (Claude Sonnet 4.5 pricing)
    const inputCost = (inputTokens / 1000000) * 3.00;
    const outputCost = (outputTokens / 1000000) * 15.00;
    this.costUsd += inputCost + outputCost;
  }

  /**
   * Complete workflow and store all data
   * @param {any} finalResult - Final workflow result
   * @param {number} qualityScore - Overall quality score 0-1
   * @param {string} outcome - 'success' | 'failed' | 'error'
   * @returns {Promise<Object>} Stored execution data
   */
  async complete(finalResult, qualityScore, outcome = 'success') {
    console.log(`\n🎯 COMPLETING WORKFLOW: ${this.workflowName}`);
    console.log(`   Workers: ${this.workers.length}`);
    console.log(`   Phases: ${this.phases.length}`);
    console.log(`   Learnings: ${this.learnings.length}`);
    console.log(`   Duration: ${Date.now() - this.startTime}ms`);

    try {
      const hook = new WorkflowCompletionHook({
        enableEmbeddings: true,
        enableGraphSync: true
      });

      const result = await hook.onWorkflowComplete({
        name: this.workflowName,
        query: this.query,
        result: finalResult,
        phases: this.phases,
        durationMs: Date.now() - this.startTime,
        outcome,
        metadata: {
          primaryModel: this.workers[0]?.model || 'claude-sonnet-4',
          taskType: 'research_synthesis',
          inputTokens: this.inputTokens,
          outputTokens: this.outputTokens,
          costUsd: this.costUsd,
          strategy: 'multi-agent-consensus',
          startedAt: new Date(this.startTime).toISOString(),
          workers: this.workers,
          arbiter: this.arbiter,
          learnings: this.learnings,
          qualityScore
        }
      });

      console.log(`✅ Auto-storage complete: execution ID ${result.id}`);
      return result;

    } catch (error) {
      console.error(`❌ Auto-storage failed: ${error.message}`);
      throw error;
    }
  }
}

// Export is at class declaration above
