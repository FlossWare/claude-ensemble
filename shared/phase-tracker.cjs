/**
 * Workflow Phase Tracker
 *
 * Lightweight wrapper to track workflow phase timing and store to PostgreSQL.
 * Works with existing workflow pattern where phase() is called as a marker.
 *
 * Usage in workflows:
 *
 *   const { PhaseTracker } = require('../shared/phase-tracker.cjs');
 *   const tracker = new PhaseTracker('workflow-name', 'task description');
 *
 *   // Start tracking
 *   await tracker.init();
 *
 *   // Track a phase
 *   tracker.startPhase('Read PDFs');
 *   // ... do work ...
 *   tracker.endPhase('Read PDFs', 'success');
 *
 *   // Or use wrapper (auto-timing)
 *   await tracker.phase('Extract Claims', async () => {
 *     // ... do work ...
 *   });
 *
 *   // Complete workflow
 *   await tracker.complete('success');
 *
 * Created: 2026-07-01
 */

const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');

class PhaseTracker {
  constructor(workflowName, taskDescription, options = {}) {
    this.workflowName = workflowName;
    this.taskDescription = taskDescription;
    this.options = {
      enableStorage: options.enableStorage !== false,
      autoComplete: options.autoComplete !== false,
      ...options
    };

    this.db = this.options.enableStorage ? getWorkflowStorage() : null;
    this.workflowExecutionId = null;
    this.workflowId = `wf-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.startTime = Date.now();

    // Phase tracking
    this.phases = [];
    this.currentPhase = null;
    this.phaseOrder = 0;
  }

  /**
   * Initialize tracker and create workflow execution record
   *
   * @returns {Promise<number>} Workflow execution ID
   */
  async init() {
    if (!this.options.enableStorage || !this.db) {
      console.log(`⏱️  Phase tracking disabled (storage=${this.options.enableStorage})`);
      return null;
    }

    try {
      this.workflowExecutionId = await this.db.storeExecution({
        workflow_id: this.workflowId,
        workflow_name: this.workflowName,
        task_description: this.taskDescription,
        total_workers: 0, // Will update on complete
        total_duration_ms: 0, // Will update on complete
        outcome: 'running',
        metadata: {
          started_at: new Date().toISOString(),
          hostname: require('os').hostname()
        }
      });

      console.log(`✅ Phase tracking initialized: workflow execution ID ${this.workflowExecutionId}`);
      return this.workflowExecutionId;

    } catch (error) {
      console.error(`❌ Failed to initialize phase tracking: ${error.message}`);
      this.options.enableStorage = false; // Disable to prevent further errors
      return null;
    }
  }

  /**
   * Start tracking a phase
   *
   * @param {string} phaseName - Phase name
   * @returns {Object} Phase metadata
   */
  startPhase(phaseName) {
    const phase = {
      name: phaseName,
      order: this.phaseOrder++,
      startTime: Date.now(),
      endTime: null,
      durationMs: null,
      outcome: null
    };

    this.currentPhase = phase;
    this.phases.push(phase);

    console.log(`\n📋 PHASE ${phase.order + 1}: ${phaseName.toUpperCase()}`);

    return phase;
  }

  /**
   * End tracking a phase and store to PostgreSQL
   *
   * @param {string} phaseName - Phase name (must match startPhase call)
   * @param {string} outcome - 'success' | 'failed' | 'error'
   * @param {Object} metadata - Additional phase metadata
   * @returns {Promise<void>}
   */
  async endPhase(phaseName, outcome = 'success', metadata = {}) {
    const phase = this.phases.find(p => p.name === phaseName && p.endTime === null);

    if (!phase) {
      console.warn(`⚠️  No active phase found: ${phaseName}`);
      return;
    }

    phase.endTime = Date.now();
    phase.durationMs = phase.endTime - phase.startTime;
    phase.outcome = outcome;
    phase.metadata = metadata;

    console.log(`✅ Phase ${phase.order + 1} complete: ${phaseName} (${phase.durationMs}ms, ${outcome})`);

    // Store to PostgreSQL
    if (this.options.enableStorage && this.db && this.workflowExecutionId) {
      try {
        await this.db.storePhase({
          workflow_execution_id: this.workflowExecutionId,
          phase_name: phaseName,
          phase_order: phase.order,
          duration_ms: phase.durationMs,
          outcome: outcome,
          metadata: metadata
        });
      } catch (error) {
        console.error(`❌ Failed to store phase: ${error.message}`);
      }
    }

    this.currentPhase = null;
  }

  /**
   * Track a phase with automatic timing (wrapper pattern)
   *
   * @param {string} phaseName - Phase name
   * @param {Function} fn - Async function to execute
   * @returns {Promise<any>} Result from fn
   */
  async phase(phaseName, fn) {
    this.startPhase(phaseName);

    try {
      const result = await fn();
      await this.endPhase(phaseName, 'success');
      return result;

    } catch (error) {
      await this.endPhase(phaseName, 'error', { error: error.message });
      throw error;
    }
  }

  /**
   * Complete workflow and update execution record
   *
   * @param {string} outcome - 'success' | 'failed' | 'error'
   * @param {Object} metadata - Additional workflow metadata
   * @returns {Promise<void>}
   */
  async complete(outcome = 'success', metadata = {}) {
    const totalDuration = Date.now() - this.startTime;

    console.log(`\n🎯 WORKFLOW COMPLETE: ${this.workflowName}`);
    console.log(`   Phases: ${this.phases.length}`);
    console.log(`   Duration: ${totalDuration}ms`);
    console.log(`   Outcome: ${outcome}`);

    // Update workflow execution record
    if (this.options.enableStorage && this.db && this.workflowExecutionId) {
      try {
        await this.db.pool.query(
          `UPDATE workflow.executions
           SET total_duration_ms = $1, outcome = $2, metadata = metadata || $3
           WHERE id = $4`,
          [
            totalDuration,
            outcome,
            JSON.stringify({
              ...metadata,
              completed_at: new Date().toISOString(),
              phases_count: this.phases.length
            }),
            this.workflowExecutionId
          ]
        );

        console.log(`✅ Workflow execution updated: ID ${this.workflowExecutionId}`);

      } catch (error) {
        console.error(`❌ Failed to update workflow execution: ${error.message}`);
      }
    }
  }

  /**
   * Get phase statistics
   *
   * @returns {Object} Phase stats
   */
  getStats() {
    const completed = this.phases.filter(p => p.outcome !== null);
    const successful = completed.filter(p => p.outcome === 'success');
    const totalDuration = completed.reduce((sum, p) => sum + p.durationMs, 0);

    return {
      total: this.phases.length,
      completed: completed.length,
      successful: successful.length,
      failed: completed.length - successful.length,
      totalDuration,
      avgDuration: completed.length > 0 ? totalDuration / completed.length : 0,
      phases: this.phases.map(p => ({
        name: p.name,
        order: p.order,
        durationMs: p.durationMs,
        outcome: p.outcome
      }))
    };
  }
}

/**
 * Create a simple phase marker function (for backward compatibility)
 *
 * This wraps the workflow's phase() parameter to track timing automatically.
 *
 * @param {PhaseTracker} tracker - Phase tracker instance
 * @returns {Function} Phase marker function
 */
function createPhaseMarker(tracker) {
  let lastPhaseName = null;

  return function(phaseName) {
    // End previous phase if exists
    if (lastPhaseName !== null) {
      tracker.endPhase(lastPhaseName, 'success').catch(err => {
        console.error(`Failed to end phase ${lastPhaseName}: ${err.message}`);
      });
    }

    // Start new phase
    tracker.startPhase(phaseName);
    lastPhaseName = phaseName;
  };
}

module.exports = {
  PhaseTracker,
  createPhaseMarker
};
