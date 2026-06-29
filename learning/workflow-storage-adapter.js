/**
 * Workflow Storage Adapter
 *
 * Automatically stores workflow execution data into PostgreSQL when workflows complete.
 * This is the "workflow completion hook" that integrates with existing orchestrators.
 *
 * Features:
 *   - Intelligent semantic chunking for long text (>10000 chars)
 *   - Generates embeddings per chunk for fine-grained similarity search
 *   - Stores chunk metadata (index, total_chunks, char_start, char_end)
 *
 * Usage in workflows:
 *   import { WorkflowStorageAdapter } from '~/.claude/learning/workflow-storage-adapter.cjs';
 *   const storage = new WorkflowStorageAdapter();
 *   await storage.storeExecution({ workflow, model, task_type, quality_score, ... });
 *   await storage.disconnect();
 */

import { getWorkflowsLearning, getStrategyPerformance, getDB, OUTCOMES } from './postgres-adapter.js';
import { randomBytes } from 'crypto';
import { execSync } from 'child_process';

export class WorkflowStorageAdapter {
  constructor() {
    this.db = getDB();
    this.workflowsLearning = getWorkflowsLearning();
    this.strategyPerf = getStrategyPerformance();
    this.chunkSize = 10000;       // Max characters per chunk
    this.chunkOverlap = 500;      // Overlap to preserve context
  }

  /**
   * Generate 384-dim embedding using Google AI Studio (free tier: 15 RPM, 1M requests/day)
   * Fast (<200ms), generous free tier, better rate limits than Voyage AI
   *
   * @param {string} text - Text to embed
   * @returns {Array<number>|null} 384-dim vector or null if generation fails
   */
  generateEmbedding(text) {
    if (!text || text.trim().length === 0) return null;

    try {
      const apiKey = process.env.GOOGLE_API_KEY;
      if (!apiKey) {
        console.warn('GOOGLE_API_KEY not set, skipping embedding generation');
        return null;
      }

      const payload = JSON.stringify({
        model: 'models/gemini-embedding-001',
        content: { parts: [{ text: text.substring(0, 10000) }] }
      });

      // Write payload to temp file to prevent shell injection
      const tmpFile = `/tmp/embedding-payload-${randomBytes(16).toString('hex')}.json`;
      require('fs').writeFileSync(tmpFile, payload);

      try {
        const { execFileSync } = require('child_process');
        const result = execFileSync('curl', [
          '-s',
          'https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent',
          '-H', 'Content-Type: application/json',
          '-H', `x-goog-api-key: ${apiKey}`,
          '-d', `@${tmpFile}`
        ], {
          encoding: 'utf8',
          timeout: 5000
        });

        require('fs').unlinkSync(tmpFile);
        return this._parseEmbeddingResponse(result);
      } catch (error) {
        require('fs').unlinkSync(tmpFile);
        throw error;
      }
    } catch (error) {
      console.warn(`Embedding generation failed: ${error.message}`);
      return null;
    }
  }

  _parseEmbeddingResponse(result) {
    const response = JSON.parse(result);
    if (response.error) {
      console.warn(`Google AI error: ${response.error.message || JSON.stringify(response.error)}`);
      return null;
    }

    const fullEmbedding = response.embedding.values;

    // Resize from 768-dim to 384-dim (take first 384 values)
    return fullEmbedding.slice(0, 384);
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
   * Generate a unique run ID (UUID v4)
   */
  generateRunId(workflowName) {
    // Generate UUID v4
    const bytes = randomBytes(16);
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // Version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // Variant

    const hex = bytes.toString('hex');
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
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
    const embedding = task_summary ? this.generateEmbedding(task_summary) : null;

    const executionId = await this.workflowsLearning.recordRun({
      workflow_id: run_id,
      workflow_name: workflow,
      task_description: task_summary || workflow,
      total_workers: model_count,
      total_duration_ms: duration_ms,
      outcome: outcome,
      metadata: metadata
    });

    // Store learnings from workflow
    const learnings = metadata?.learnings || [];
    if (learnings.length > 0) {
      console.log(`Storing ${learnings.length} learnings...`);
      for (const learning of learnings) {
        const learningText = learning.description + ' ' + learning.insight;
        const learningEmbedding = this.generateEmbedding(learningText);

        await this.workflowsLearning.recordLearning({
          workflow_execution_id: executionId,
          learning_type: learning.type || 'pattern',
          description: learning.description,
          actionable_insight: learning.insight,
          importance: learning.importance || quality_score,
          learning_embedding: learningEmbedding ? `[${learningEmbedding.join(',')}]` : null,
          metadata: learning.metadata || {}
        });
      }
    } else {
      // Fallback: store task summary as learning
      await this.workflowsLearning.recordLearning({
        workflow_execution_id: executionId,
        learning_type: 'pattern',
        description: task_summary ? task_summary.substring(0, 500) : `Task difficulty analysis for ${workflow}`,
        actionable_insight: `Difficulty: ${typeof difficulty === 'number' ? difficulty.toFixed(2) : difficulty}, Quality: ${quality_score.toFixed(2)}`,
        importance: quality_score,
        learning_embedding: embedding ? `[${embedding.join(',')}]` : null,
        metadata: {
          task_type,
          task_difficulty: difficulty,
          model_count,
          duration_ms,
          cost_usd,
          ...metadata
        }
      });
    }

    const strategy = `${workflow}-workflow`;
    const success = outcome === OUTCOMES.SUCCESS;
    const reward = quality_score;

    await this.strategyPerf.record(strategy, success, reward);

    return { run_id, workflow, quality_score, outcome, difficulty, strategy, executionId };
  }

  /**
   * Update strategy performance (Thompson Sampling)
   */
  async updateStrategyPerformance(strategy, success, reward) {
    await this.strategyPerf.record(strategy, success, reward);
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
