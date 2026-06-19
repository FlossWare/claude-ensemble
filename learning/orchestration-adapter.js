/**
 * Persistent Orchestration Queue Adapter
 *
 * Tracks all fleet work across reboots with:
 * - Task queue with vector embeddings
 * - Worker heartbeats and assignment
 * - Progress tracking with chunking
 * - Dependency graph for Neo4j sync
 * - Auto-recovery after restart
 */

const { Pool } = require('pg');
const { execSync } = require('child_process');

class OrchestrationQueue {
  constructor() {
    this.pool = new Pool({
      host: 'laptop-01',
      user: 'sfloess',
      database: 'learning',
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });
  }

  /**
   * Generate 384-dim embedding for task description
   */
  async generateEmbedding(text) {
    try {
      const result = execSync(
        `python3 -c "from sentence_transformers import SentenceTransformer; import sys; m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print(m.encode(sys.stdin.read()).tolist())"`,
        { input: text, encoding: 'utf-8', timeout: 10000 }
      );
      return JSON.parse(result);
    } catch (error) {
      console.warn('Embedding generation failed:', error.message);
      return null;
    }
  }

  /**
   * Enqueue a new task
   */
  async enqueue(task) {
    const {
      task_id,
      task_type,
      description,
      priority = 50,
      depends_on = [],
      metadata = {},
      estimated_duration_ms = null
    } = task;

    const embedding = await this.generateEmbedding(description);

    const result = await this.pool.query(`
      INSERT INTO orchestration.task_queue
      (task_id, task_type, description, embedding, priority, depends_on, metadata, estimated_duration_ms)
      VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8)
      ON CONFLICT (task_id) DO UPDATE SET
        description = EXCLUDED.description,
        embedding = EXCLUDED.embedding,
        priority = EXCLUDED.priority,
        metadata = EXCLUDED.metadata
      RETURNING id, task_id, status
    `, [task_id, task_type, description, embedding, priority, depends_on, JSON.stringify(metadata), estimated_duration_ms]);

    return result.rows[0];
  }

  /**
   * Claim next available task for a worker
   */
  async claimTask(worker_id) {
    const result = await this.pool.query(`
      UPDATE orchestration.task_queue
      SET status = 'running',
          assigned_worker = $1,
          started_at = NOW()
      WHERE id = (
        SELECT id FROM orchestration.task_queue
        WHERE status = 'queued'
          AND (depends_on IS NULL OR depends_on = '{}' OR NOT EXISTS (
            SELECT 1 FROM orchestration.task_queue dep
            WHERE dep.id = ANY(task_queue.depends_on)
              AND dep.status != 'completed'
          ))
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
      )
      RETURNING id, task_id, task_type, description, metadata
    `, [worker_id]);

    return result.rows[0] || null;
  }

  /**
   * Update task progress
   */
  async updateProgress(task_id, progress) {
    const {
      progress_percent,
      current_phase,
      phases_completed,
      input_tokens,
      output_tokens,
      cost_usd,
      message
    } = progress;

    await this.pool.query(`
      UPDATE orchestration.task_queue
      SET progress_percent = COALESCE($2, progress_percent),
          current_phase = COALESCE($3, current_phase),
          phases_completed = COALESCE($4, phases_completed),
          input_tokens = COALESCE($5, input_tokens),
          output_tokens = COALESCE($6, output_tokens),
          cost_usd = COALESCE($7, cost_usd)
      WHERE task_id = $1
    `, [task_id, progress_percent, current_phase, phases_completed, input_tokens, output_tokens, cost_usd]);

    if (message) {
      await this.pool.query(`
        INSERT INTO orchestration.task_progress_log
        (task_id, phase, message, progress_percent)
        VALUES ($1, $2, $3, $4)
      `, [task_id, current_phase, message, progress_percent]);
    }
  }

  /**
   * Complete a task
   */
  async completeTask(task_id, result) {
    const {
      outcome = 'success',
      result_path,
      result_summary,
      error_message,
      actual_duration_ms,
      input_tokens,
      output_tokens,
      cost_usd
    } = result;

    await this.pool.query(`
      UPDATE orchestration.task_queue
      SET status = 'completed',
          completed_at = NOW(),
          progress_percent = 100,
          outcome = $2,
          result_path = $3,
          result_summary = $4,
          error_message = $5,
          actual_duration_ms = COALESCE($6, EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000),
          input_tokens = COALESCE($7, input_tokens),
          output_tokens = COALESCE($8, output_tokens),
          cost_usd = COALESCE($9, cost_usd)
      WHERE task_id = $1
    `, [task_id, outcome, result_path, result_summary, error_message, actual_duration_ms, input_tokens, output_tokens, cost_usd]);
  }

  /**
   * Fail a task
   */
  async failTask(task_id, error_message) {
    await this.completeTask(task_id, {
      outcome: 'error',
      error_message
    });
  }

  /**
   * Worker heartbeat
   */
  async heartbeat(worker_id, data = {}) {
    const { hostname, current_task_id, status = 'idle', capabilities = {} } = data;

    await this.pool.query(`
      INSERT INTO orchestration.worker_heartbeats
      (worker_id, hostname, current_task_id, status, capabilities, last_seen)
      VALUES ($1, $2, $3, $4, $5, NOW())
      ON CONFLICT (worker_id) DO UPDATE SET
        hostname = EXCLUDED.hostname,
        current_task_id = EXCLUDED.current_task_id,
        status = EXCLUDED.status,
        capabilities = EXCLUDED.capabilities,
        last_seen = NOW()
    `, [worker_id, hostname, current_task_id, status, JSON.stringify(capabilities)]);
  }

  /**
   * Find similar tasks (semantic search)
   */
  async findSimilarTasks(description, limit = 10) {
    const embedding = await this.generateEmbedding(description);
    if (!embedding) return [];

    const result = await this.pool.query(`
      SELECT
        task_id,
        task_type,
        description,
        status,
        outcome,
        result_summary,
        1 - (embedding <=> $1::vector) as similarity
      FROM orchestration.task_queue
      WHERE embedding IS NOT NULL
      ORDER BY embedding <=> $1::vector
      LIMIT $2
    `, [embedding, limit]);

    return result.rows;
  }

  /**
   * Get queue status summary
   */
  async getQueueStatus() {
    const result = await this.pool.query(`
      SELECT * FROM orchestration.queue_summary
      ORDER BY status, task_type
    `);
    return result.rows;
  }

  /**
   * Get worker utilization
   */
  async getWorkerUtilization() {
    const result = await this.pool.query(`
      SELECT * FROM orchestration.worker_utilization
      ORDER BY worker_id
    `);
    return result.rows;
  }

  /**
   * Recover stalled tasks (workers offline > 5 min)
   */
  async recoverStalledTasks() {
    const result = await this.pool.query(`
      UPDATE orchestration.task_queue t
      SET status = 'queued',
          assigned_worker = NULL,
          started_at = NULL
      WHERE status = 'running'
        AND assigned_worker IS NOT NULL
        AND NOT EXISTS (
          SELECT 1 FROM orchestration.worker_heartbeats w
          WHERE w.worker_id = t.assigned_worker
            AND w.last_seen > NOW() - INTERVAL '5 minutes'
        )
      RETURNING task_id, task_type, description
    `);

    return result.rows;
  }

  /**
   * Get tasks ready to run (no unmet dependencies)
   */
  async getReadyTasks(limit = 50) {
    const result = await this.pool.query(`
      SELECT
        id, task_id, task_type, description, priority, metadata, estimated_duration_ms
      FROM orchestration.task_queue
      WHERE status = 'queued'
        AND (depends_on IS NULL OR depends_on = '{}' OR NOT EXISTS (
          SELECT 1 FROM orchestration.task_queue dep
          WHERE dep.id = ANY(task_queue.depends_on)
            AND dep.status != 'completed'
        ))
      ORDER BY priority DESC, created_at ASC
      LIMIT $1
    `, [limit]);

    return result.rows;
  }

  /**
   * Export state for recovery
   */
  async exportState() {
    const tasks = await this.pool.query('SELECT * FROM orchestration.task_queue ORDER BY id');
    const workers = await this.pool.query('SELECT * FROM orchestration.worker_heartbeats');
    const progress = await this.pool.query('SELECT * FROM orchestration.task_progress_log ORDER BY timestamp DESC LIMIT 1000');

    return {
      tasks: tasks.rows,
      workers: workers.rows,
      progress: progress.rows,
      exported_at: new Date().toISOString()
    };
  }

  /**
   * Close connection pool
   */
  async close() {
    await this.pool.end();
  }
}

// Singleton instance
let instance = null;

function getOrchestrationQueue() {
  if (!instance) {
    instance = new OrchestrationQueue();
  }
  return instance;
}

module.exports = {
  OrchestrationQueue,
  getOrchestrationQueue
};
