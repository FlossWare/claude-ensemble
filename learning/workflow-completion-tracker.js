/**
 * Workflow Completion Tracker
 * Hooks into workflow orchestrator to log completions with embeddings
 *
 * Integration:
 * - Call trackWorkflowStart() at workflow start
 * - Call trackWorkflowCompletion() at workflow end
 * - Embeddings are automatically generated from query + result summary
 * - Retention policy clears embeddings after 90 days (daily at 3 AM)
 */

const { getDB } = require('./postgres-adapter');
const { spawn } = require('child_process');

class WorkflowCompletionTracker {
  constructor() {
    this.db = getDB();
  }

  /**
   * Track workflow start
   * @param {Object} params
   * @param {string} params.workflowName - Workflow name (e.g., 'deep-research')
   * @param {string} params.sessionId - Unique session ID
   * @param {string} params.query - User query
   * @param {Object} params.metadata - Optional metadata
   * @returns {Promise<number>} Workflow ID
   */
  async trackWorkflowStart({ workflowName, sessionId, query, metadata = {} }) {
    const result = await this.db.run(
      `INSERT INTO learning.workflow_completions
       (workflow_name, session_id, query, started_at, status, metadata)
       VALUES ($1, $2, $3, NOW(), 'running', $4)
       RETURNING id`,
      [workflowName, sessionId, query, JSON.stringify(metadata)]
    );

    return result.lastID;
  }

  /**
   * Track workflow completion and generate embedding
   * @param {Object} params
   * @param {string} params.sessionId - Session ID from trackWorkflowStart
   * @param {string} params.status - 'completed' or 'failed'
   * @param {Object} params.phases - Phase execution data
   * @param {string} params.resultSummary - Summary of results (for embedding)
   * @param {number} params.durationMs - Execution duration
   */
  async trackWorkflowCompletion({ sessionId, status, phases, resultSummary, durationMs }) {
    // Generate embedding from query + result summary
    const row = await this.db.get(
      'SELECT query FROM learning.workflow_completions WHERE session_id = $1',
      [sessionId]
    );

    if (!row) {
      throw new Error(`Session not found: ${sessionId}`);
    }

    const embedding = await this.generateEmbedding(`${row.query}\n\n${resultSummary}`);

    await this.db.run(
      `UPDATE learning.workflow_completions
       SET completed_at = NOW(),
           duration_ms = $1,
           status = $2,
           phases = $3,
           result_summary = $4,
           embedding = $5::vector
       WHERE session_id = $6`,
      [durationMs, status, JSON.stringify(phases), resultSummary, embedding, sessionId]
    );
  }

  /**
   * Generate embedding using sentence-transformers
   * Uses Python script for embedding generation (768-dim all-mpnet-base-v2)
   * @param {string} text - Text to embed
   * @returns {Promise<string>} Embedding as PostgreSQL vector string
   */
  async generateEmbedding(text) {
    return new Promise((resolve, reject) => {
      const python = spawn('python3', [
        '-c',
        `
import sys
from sentence_transformers import SentenceTransformer
import json

model = SentenceTransformer('all-mpnet-base-v2')
text = sys.stdin.read()
embedding = model.encode(text).tolist()
print(json.dumps(embedding))
        `
      ]);

      let stdout = '';
      let stderr = '';

      python.stdin.write(text);
      python.stdin.end();

      python.stdout.on('data', (data) => { stdout += data.toString(); });
      python.stderr.on('data', (data) => { stderr += data.toString(); });

      python.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Embedding generation failed: ${stderr}`));
        } else {
          try {
            const embedding = JSON.parse(stdout);
            // Convert to PostgreSQL vector format: '[0.1, 0.2, ...]'
            resolve(`[${embedding.join(',')}]`);
          } catch (err) {
            reject(new Error(`Failed to parse embedding: ${err.message}`));
          }
        }
      });
    });
  }

  /**
   * Search similar workflows by semantic similarity
   * @param {string} query - Search query
   * @param {number} limit - Max results (default 10)
   * @returns {Promise<Array>} Similar workflows
   */
  async searchSimilar(query, limit = 10) {
    const queryEmbedding = await this.generateEmbedding(query);

    return await this.db.all(
      `SELECT
         workflow_name,
         session_id,
         query,
         result_summary,
         completed_at,
         duration_ms,
         status,
         embedding <=> $1::vector as similarity
       FROM learning.workflow_completions
       WHERE embedding IS NOT NULL
         AND status = 'completed'
       ORDER BY embedding <=> $1::vector
       LIMIT $2`,
      [queryEmbedding, limit]
    );
  }

  /**
   * Get workflow statistics
   * @param {string} workflowName - Workflow name filter (optional)
   * @returns {Promise<Object>} Statistics
   */
  async getStats(workflowName = null) {
    const sql = workflowName
      ? `SELECT
           COUNT(*) as total_workflows,
           COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
           COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
           AVG(duration_ms) as avg_duration_ms,
           COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings,
           COUNT(CASE WHEN embedding_cleared_at IS NOT NULL THEN 1 END) as embeddings_cleared
         FROM learning.workflow_completions
         WHERE workflow_name = $1`
      : `SELECT
           COUNT(*) as total_workflows,
           COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
           COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
           AVG(duration_ms) as avg_duration_ms,
           COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings,
           COUNT(CASE WHEN embedding_cleared_at IS NOT NULL THEN 1 END) as embeddings_cleared
         FROM learning.workflow_completions`;

    const params = workflowName ? [workflowName] : [];
    const row = await this.db.get(sql, params);

    return {
      total_workflows: parseInt(row.total_workflows, 10),
      completed: parseInt(row.completed, 10),
      failed: parseInt(row.failed, 10),
      avg_duration_ms: row.avg_duration_ms ? parseFloat(row.avg_duration_ms) : 0,
      with_embeddings: parseInt(row.with_embeddings, 10),
      embeddings_cleared: parseInt(row.embeddings_cleared, 10)
    };
  }
}

// Singleton instance
let _tracker = null;

function getWorkflowTracker() {
  if (!_tracker) _tracker = new WorkflowCompletionTracker();
  return _tracker;
}

module.exports = {
  WorkflowCompletionTracker,
  getWorkflowTracker
};
