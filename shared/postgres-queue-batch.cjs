/**
 * PostgreSQL Queue Batch Operations
 *
 * Supports atomic claiming of multiple tasks from PostgreSQL queues.
 *
 * Features:
 * - Atomic batch claiming using SELECT FOR UPDATE SKIP LOCKED
 * - Configurable batch sizes
 * - Worker affinity (prefer tasks for same worker)
 * - Priority-aware batching
 * - Heartbeat updates for batch items
 * - Batch completion/failure handling
 *
 * Usage:
 * ```javascript
 * const { getQueueBatch } = require('./postgres-queue-batch');
 * const queue = getQueueBatch();
 *
 * // Claim batch of tasks
 * const tasks = await queue.claimBatch('store', 'worker-01', 10);
 *
 * // Process tasks...
 *
 * // Complete batch
 * await queue.completeBatch('store', taskIds);
 * ```
 */

const { Pool } = require('pg');

class PostgresQueueBatch {
  constructor(config = {}) {
    this.pool = new Pool({
      host: config.host || 'aio-01',
      port: config.port || 5433,
      database: config.database || 'learning',
      user: config.user || 'sfloess',
      password: config.password || '',
      max: config.maxConnections || 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });
  }

  /**
   * Atomically claim a batch of tasks from the queue
   *
   * @param {string} queueName - Queue name (store, chunk, embed, graph)
   * @param {string} workerId - Worker identifier
   * @param {number} batchSize - Number of tasks to claim (default: 10)
   * @param {object} options - Additional options
   * @returns {Promise<Array>} Array of claimed tasks
   */
  async claimBatch(queueName, workerId, batchSize = 10, options = {}) {
    const client = await this.pool.connect();

    try {
      await client.query('BEGIN');

      const {
        priorityMin = 0,
        priorityMax = 100,
        timeout = 300, // 5 minutes default
        affinityWeight = 0.3, // 30% preference for same worker tasks
      } = options;

      // Build query to select tasks atomically
      // Uses SELECT FOR UPDATE SKIP LOCKED for atomic claiming
      // Prioritizes by:
      // 1. Worker affinity (prefer tasks from same worker)
      // 2. Priority (higher priority first)
      // 3. Age (older tasks first)
      const query = `
        WITH available_tasks AS (
          SELECT
            id,
            payload,
            priority,
            created_at,
            retry_count,
            (CASE WHEN worker_id = $2 THEN 1 ELSE 0 END) as affinity_boost
          FROM queue.${queueName}
          WHERE status = 'pending'
            AND priority BETWEEN $3 AND $4
            AND retry_count < 3
          ORDER BY affinity_boost DESC, priority DESC, created_at ASC
          LIMIT $1
          FOR UPDATE SKIP LOCKED
        )
        UPDATE queue.${queueName} q
        SET
          status = 'processing',
          worker_id = $2,
          claimed_at = NOW()
        FROM available_tasks at
        WHERE q.id = at.id
        RETURNING q.id, q.payload, q.priority, q.created_at, q.retry_count, q.claimed_at
      `;

      const result = await client.query(query, [
        batchSize,
        workerId,
        priorityMin,
        priorityMax,
      ]);

      await client.query('COMMIT');

      return result.rows.map(row => ({
        id: row.id,
        data: row.payload,
        priority: row.priority,
        createdAt: row.created_at,
        retryCount: row.retry_count,
        claimedAt: row.claimed_at,
        queueName,
        workerId,
      }));
    } catch (error) {
      await client.query('ROLLBACK');
      throw new Error(`Failed to claim batch from ${queueName}: ${error.message}`);
    } finally {
      client.release();
    }
  }

  /**
   * Complete a batch of tasks atomically
   *
   * @param {string} queueName - Queue name
   * @param {Array<number>} taskIds - Array of task IDs to complete
   * @param {object} results - Optional results to store
   * @returns {Promise<number>} Number of tasks completed
   */
  async completeBatch(queueName, taskIds, results = {}) {
    if (!taskIds || taskIds.length === 0) {
      return 0;
    }

    const client = await this.pool.connect();

    try {
      await client.query('BEGIN');

      const query = `
        UPDATE queue.${queueName}
        SET
          status = 'completed',
          completed_at = NOW(),
          result = $2::jsonb
        WHERE id = ANY($1)
          AND status = 'processing'
        RETURNING id
      `;

      const result = await client.query(query, [taskIds, JSON.stringify(results)]);

      await client.query('COMMIT');

      return result.rowCount;
    } catch (error) {
      await client.query('ROLLBACK');
      throw new Error(`Failed to complete batch in ${queueName}: ${error.message}`);
    } finally {
      client.release();
    }
  }

  /**
   * Fail a batch of tasks atomically
   *
   * @param {string} queueName - Queue name
   * @param {Array<number>} taskIds - Array of task IDs to fail
   * @param {string} error - Error message
   * @param {boolean} retry - Whether to retry (default: true)
   * @returns {Promise<number>} Number of tasks failed
   */
  async failBatch(queueName, taskIds, error, retry = true) {
    if (!taskIds || taskIds.length === 0) {
      return 0;
    }

    const client = await this.pool.connect();

    try {
      await client.query('BEGIN');

      const query = `
        UPDATE queue.${queueName}
        SET
          status = CASE
            WHEN retry_count >= 2 OR $3 = false THEN 'failed'
            ELSE 'pending'
          END,
          error_message = $2,
          retry_count = retry_count + 1,
          worker_id = NULL,
          claimed_at = NULL
        WHERE id = ANY($1)
          AND status = 'processing'
        RETURNING id, status, retry_count
      `;

      const result = await client.query(query, [taskIds, error, retry]);

      await client.query('COMMIT');

      return result.rowCount;
    } catch (err) {
      await client.query('ROLLBACK');
      throw new Error(`Failed to fail batch in ${queueName}: ${err.message}`);
    } finally {
      client.release();
    }
  }

  /**
   * Update heartbeat for a batch of tasks
   * Note: Current schema doesn't have last_heartbeat column
   * This is a no-op placeholder for API compatibility
   *
   * @param {string} queueName - Queue name
   * @param {Array<number>} taskIds - Array of task IDs
   * @returns {Promise<number>} Number of tasks updated
   */
  async heartbeatBatch(queueName, taskIds) {
    if (!taskIds || taskIds.length === 0) {
      return 0;
    }

    // No-op: schema doesn't have heartbeat column
    // Tasks are monitored via claimed_at timestamp instead
    return taskIds.length;
  }

  /**
   * Get batch statistics
   *
   * @param {string} queueName - Queue name
   * @returns {Promise<object>} Statistics object
   */
  async getBatchStats(queueName) {
    const query = `
      SELECT
        COUNT(*) FILTER (WHERE status = 'pending') as pending,
        COUNT(*) FILTER (WHERE status = 'processing') as processing,
        COUNT(*) FILTER (WHERE status = 'completed') as completed,
        COUNT(*) FILTER (WHERE status = 'failed') as failed,
        COUNT(DISTINCT worker_id) FILTER (WHERE status = 'processing') as active_workers,
        AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) FILTER (WHERE status = 'completed') as avg_completion_time,
        AVG(retry_count) FILTER (WHERE status = 'completed' OR status = 'failed') as avg_retries
      FROM queue.${queueName}
    `;

    const result = await this.pool.query(query);
    return result.rows[0];
  }

  /**
   * Reclaim timed-out tasks
   *
   * @param {string} queueName - Queue name
   * @returns {Promise<number>} Number of tasks reclaimed
   */
  async reclaimTimedOut(queueName, timeoutMinutes = 5) {
    const query = `
      UPDATE queue.${queueName}
      SET
        status = 'pending',
        worker_id = NULL,
        claimed_at = NULL,
        retry_count = retry_count + 1
      WHERE status = 'processing'
        AND claimed_at < NOW() - INTERVAL '${timeoutMinutes} minutes'
        AND retry_count < 3
      RETURNING id
    `;

    const result = await this.pool.query(query);
    return result.rowCount;
  }

  /**
   * Close database connection pool
   */
  async close() {
    await this.pool.end();
  }
}

// Singleton instance
let instance = null;

/**
 * Get the queue batch instance
 *
 * @param {object} config - Optional configuration
 * @returns {PostgresQueueBatch} Queue batch instance
 */
function getQueueBatch(config = {}) {
  if (!instance) {
    instance = new PostgresQueueBatch(config);
  }
  return instance;
}

module.exports = {
  PostgresQueueBatch,
  getQueueBatch,
};
