/**
 * Workflow Storage Adapter
 * Stores multi-AI consensus workflow executions with embeddings
 */

const { getDB } = require('./postgres-adapter');
const { spawn } = require('child_process');
const crypto = require('crypto');

class WorkflowStorage {
  constructor(db) {
    this.db = db || getDB();
  }

  /**
   * Generate embedding for text using sentence-transformers
   * Falls back to simple hash-based embedding if Python unavailable
   */
  async generateEmbedding(text) {
    return new Promise((resolve, reject) => {
      // Try to use sentence-transformers
      const python = spawn('python3', ['-c', `
import sys
import json
try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-mpnet-base-v2')
    text = sys.stdin.read()
    embedding = model.encode(text).tolist()
    print(json.dumps(embedding))
except ImportError:
    # Fallback: simple hash-based embedding
    import hashlib
    text = sys.stdin.read()
    # Generate 768-dim embedding from text hash
    hash_obj = hashlib.sha256(text.encode())
    # Use hash to seed deterministic random values
    import random
    random.seed(int(hash_obj.hexdigest(), 16))
    embedding = [random.random() * 2 - 1 for _ in range(768)]
    print(json.dumps(embedding))
`]);

      let stdout = '';
      let stderr = '';

      python.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      python.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      python.on('close', (code) => {
        if (code !== 0) {
          // Fallback: zero vector
          resolve(Array(768).fill(0));
        } else {
          try {
            const embedding = JSON.parse(stdout.trim());
            resolve(embedding);
          } catch (err) {
            resolve(Array(768).fill(0));
          }
        }
      });

      python.stdin.write(text);
      python.stdin.end();
    });
  }

  /**
   * Log a workflow execution start
   * Returns execution_id for tracking worker results
   */
  async logExecutionStart(data) {
    const { workflow_type, prompt, metadata } = data;
    const embedding = await this.generateEmbedding(prompt);

    const result = await this.db.query(
      `INSERT INTO workflows.executions
       (workflow_type, prompt, metadata, embedding, timestamp)
       VALUES ($1, $2, $3, $4::vector, NOW())
       RETURNING execution_id`,
      [workflow_type, prompt, JSON.stringify(metadata || {}), JSON.stringify(embedding)]
    );

    return result[0].execution_id;
  }

  /**
   * Update execution with final outcome and metrics
   */
  async logExecutionEnd(execution_id, data) {
    const { duration_ms, total_cost_usd, outcome } = data;

    await this.db.query(
      `UPDATE workflows.executions
       SET duration_ms = $1, total_cost_usd = $2, outcome = $3
       WHERE execution_id = $4`,
      [duration_ms, total_cost_usd, outcome, execution_id]
    );
  }

  /**
   * Log a worker result (individual model response)
   */
  async logWorkerResult(data) {
    const {
      execution_id, model, response, confidence, quality_score,
      input_tokens, output_tokens, cost_usd, duration_ms, metadata
    } = data;

    const embedding = await this.generateEmbedding(response || '');

    await this.db.query(
      `INSERT INTO workflows.worker_results
       (execution_id, model, response, confidence, quality_score,
        input_tokens, output_tokens, cost_usd, duration_ms, metadata, embedding, timestamp)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::vector, NOW())`,
      [
        execution_id, model, response, confidence, quality_score,
        input_tokens, output_tokens, cost_usd, duration_ms,
        JSON.stringify(metadata || {}), JSON.stringify(embedding)
      ]
    );
  }

  /**
   * Log an arbiter decision (final consensus)
   */
  async logArbiterDecision(data) {
    const {
      execution_id, arbiter_model, final_response, confidence,
      worker_votes, reasoning, input_tokens, output_tokens, cost_usd, duration_ms
    } = data;

    const embedding = await this.generateEmbedding(final_response || '');

    await this.db.query(
      `INSERT INTO workflows.arbiter_decisions
       (execution_id, arbiter_model, final_response, confidence, worker_votes,
        reasoning, input_tokens, output_tokens, cost_usd, duration_ms, embedding, timestamp)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::vector, NOW())`,
      [
        execution_id, arbiter_model, final_response, confidence,
        JSON.stringify(worker_votes || {}), reasoning,
        input_tokens, output_tokens, cost_usd, duration_ms,
        JSON.stringify(embedding)
      ]
    );
  }

  /**
   * Find similar workflow executions by prompt embedding
   */
  async findSimilarExecutions(prompt, limit = 10) {
    const embedding = await this.generateEmbedding(prompt);

    return await this.db.query(
      `SELECT
         execution_id, workflow_type, prompt, outcome,
         duration_ms, total_cost_usd, timestamp,
         embedding <=> $1::vector as distance
       FROM workflows.executions
       ORDER BY embedding <=> $1::vector
       LIMIT $2`,
      [JSON.stringify(embedding), limit]
    );
  }

  /**
   * Get execution details with all worker results and arbiter decision
   */
  async getExecutionDetails(execution_id) {
    const execution = await this.db.get(
      'SELECT * FROM workflows.executions WHERE execution_id = $1',
      [execution_id]
    );

    const workers = await this.db.all(
      'SELECT * FROM workflows.worker_results WHERE execution_id = $1 ORDER BY timestamp',
      [execution_id]
    );

    const arbiter = await this.db.get(
      'SELECT * FROM workflows.arbiter_decisions WHERE execution_id = $1',
      [execution_id]
    );

    return { execution, workers, arbiter };
  }

  /**
   * Refresh materialized views
   */
  async refreshViews() {
    await this.db.query('SELECT workflows.refresh_views()');
  }

  /**
   * Get summary statistics
   */
  async getSummary() {
    return await this.db.all('SELECT * FROM workflows.summary ORDER BY total_executions DESC');
  }

  /**
   * Get model performance statistics
   */
  async getModelPerformance() {
    return await this.db.all('SELECT * FROM workflows.model_performance ORDER BY avg_quality_score DESC');
  }
}

// Singleton instance
let _workflowStorage = null;

function getWorkflowStorage() {
  if (!_workflowStorage) _workflowStorage = new WorkflowStorage();
  return _workflowStorage;
}

module.exports = {
  WorkflowStorage,
  getWorkflowStorage,
};
