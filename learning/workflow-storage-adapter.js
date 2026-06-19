/**
 * Workflow Storage Adapter
 *
 * Automatically stores workflow execution data into PostgreSQL when workflows complete.
 * This is the "workflow completion hook" that integrates with existing orchestrators.
 *
 * Usage in workflows:
 *   import { WorkflowStorageAdapter } from '~/.claude/learning/workflow-storage-adapter.js';
 *   const storage = new WorkflowStorageAdapter();
 *   await storage.storeExecution({ workflow, model, task_type, quality_score, ... });
 *   await storage.disconnect();
 */

import { getWorkflowsLearning, getStrategyPerformance, getDB, OUTCOMES } from './postgres-adapter.js';

export class WorkflowStorageAdapter {
  constructor() {
    this.db = getDB();
    this.workflowsLearning = getWorkflowsLearning();
    this.strategyPerf = getStrategyPerformance();
  }

  /**
   * Generate simple embedding from text (placeholder)
   * TODO: Replace with proper embedding model
   */
  generateEmbedding(text, dim = 128) {
    const normalized = text.toLowerCase();
    const vector = new Array(dim).fill(0);

    // Character frequency distribution
    for (let i = 0; i < normalized.length; i++) {
      const charCode = normalized.charCodeAt(i);
      const idx = charCode % dim;
      vector[idx] += 1.0;
    }

    // Normalize to unit length
    const magnitude = Math.sqrt(vector.reduce((sum, val) => sum + val * val, 0));
    if (magnitude > 0) {
      for (let i = 0; i < dim; i++) {
        vector[i] /= magnitude;
      }
    }

    return vector;
  }

  /**
   * Assess task difficulty from quality score and outcome
   */
  assessTaskDifficulty(qualityScore, outcome) {
    if (outcome === OUTCOMES.ERROR) {
      return 'hard';
    }

    if (qualityScore >= 0.8) {
      return 'easy';
    } else if (qualityScore >= 0.5) {
      return 'moderate';
    } else {
      return 'hard';
    }
  }

  /**
   * Generate a unique run ID
   */
  generateRunId(workflowName) {
    const timestamp = new Date().toISOString().split('.')[0].replace(/:/g, '-');
    const random = Math.random().toString(36).slice(2, 8);
    return `${workflowName}_${timestamp}_${random}`;
  }

  /**
   * Store workflow execution data
   */
  async storeExecution(data) {
    const {
      workflow,
      model,
      task_type = 'unknown',
      quality_score = 0,
      input_tokens = 0,
      output_tokens = 0,
      cost_usd = 0,
      duration_ms = 0,
      outcome = OUTCOMES.SUCCESS,
      metadata = {},
      run_id = this.generateRunId(workflow),
      task_summary = metadata.query || '',
      model_count = 1,
      task_difficulty = null
    } = data;

    if (!workflow) {
      throw new Error('workflow is required');
    }

    const difficulty = task_difficulty || this.assessTaskDifficulty(quality_score, outcome);
    const embedding = task_summary ? this.generateEmbedding(task_summary, 128) : null;

    await this.workflowsLearning.recordRun({
      run_id,
      workflow_name: workflow,
      status: outcome === OUTCOMES.SUCCESS ? 'completed' : outcome === OUTCOMES.ERROR ? 'failed' : 'running',
      input_args: metadata.input_args || null,
      output_result: metadata.output_result || null,
      error_message: metadata.error || null,
      duration_ms
    });

    await this.workflowsLearning.recordLearning({
      run_id,
      workflow_name: workflow,
      learning_type: 'task_difficulty',
      task_difficulty: difficulty,
      task_type,
      task_summary: task_summary.substring(0, 500),
      quality_score,
      outcome,
      model_count,
      duration_ms,
      cost_usd,
      metadata,
      embedding: embedding ? `[${embedding.join(',')}]` : null
    });

    const strategy = `${workflow}-workflow`;
    const success = outcome === OUTCOMES.SUCCESS;
    const reward = quality_score;

    await this.strategyPerf.record(strategy, success, reward);

    return { run_id, workflow, quality_score, outcome, difficulty, strategy };
  }

  async disconnect() {
    await this.db.close();
  }
}

export async function storeWorkflowExecution(data) {
  const adapter = new WorkflowStorageAdapter();
  try {
    return await adapter.storeExecution(data);
  } finally {
    await adapter.disconnect();
  }
}
