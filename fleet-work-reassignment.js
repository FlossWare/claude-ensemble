/**
 * Fleet Work Reassignment System
 *
 * Detects node failures and reassigns failed work to alternative nodes
 * using Thompson Sampling with anti-affinity for retry routing.
 *
 * Features:
 * - Timeout-based failure detection (60s work, 30s SSH, 15s health check)
 * - PostgreSQL work queue state tracking (pending/assigned/in_progress/failed/completed)
 * - 3-retry limit with permanent failure marking
 * - Thompson Sampling with anti-affinity for retry node selection
 * - Atomic slot reservation to prevent duplicate work
 * - Grace period to avoid killing slow-but-working nodes
 *
 * Fixed Issues:
 * - Advisory locks for TOCTOU prevention in reserveSlot()
 * - SELECT FOR UPDATE before version-checked updates in handleFailure()
 * - Distributed lock around handleFailure() to prevent double-timeout
 * - Database-side timeout enforcement via statement_timeout
 * - Re-check node availability after Thompson sampling
 * - Scheduler notification via LISTEN/NOTIFY for backoff expiry
 * - Deep equality check for late completion result comparison
 * - Circuit breaker checks work status before triggering failure
 * - Extended checkAbandonedAssignments() to cover 'in_progress' status
 * - Higher Beta prior (alpha=beta=5) to reduce sampling variance
 * - Dynamic health check socket limit based on fleet size
 * - AbortSignal documentation + statement_timeout at pool level
 * - Graceful shutdown with 30s drain period
 * - Beta decay factor for transient vs permanent failures
 */

const { Pool } = require('pg');
const { execSync } = require('child_process');
const http = require('http');

// Configuration
const CONFIG = {
  workTimeout: 60000,           // 60s default work timeout
  sshTimeout: 30000,            // 30s SSH connection timeout
  healthCheckInterval: 15000,   // 15s health check polling
  maxRetries: 3,                // Max retry attempts per work item
  retryGracePeriod: 15000,      // 15s grace period after timeout
  heartbeatTimeout: 120000,     // 120s session heartbeat timeout
  permanentFailureAction: 'log', // 'log' or 'alert'
  maxWorkTimeout: 300000,       // 5 min cap on adaptive timeout
  timeoutMultiplier: 2.5,       // Adaptive timeout = avg_duration * 2.5
  maxRetryHistorySize: 10,      // Max retry history entries
  maxErrorMessageLength: 500,   // Max error message length in history
  healthCheckMaxSocketsPerNode: 2, // Max concurrent health check connections per node
  healthCheckCircuitBreakerThreshold: 3, // Consecutive failures before circuit break
  abandonedAssignmentTimeout: 300000, // 5 min before assigned work is considered abandoned
  abandonedInProgressTimeout: 600000, // 10 min before in_progress work is considered abandoned
  allNodesExhaustedBackoff: 60000, // 1 min backoff when all nodes exhausted
  awaitingSlotBackoff: 30000,   // 30s backoff when awaiting slot
  epsilonGreedy: 0.05,          // 5% random exploration in Thompson Sampling
  betaPriorAlpha: 5,            // Higher prior to reduce sampling variance
  betaPriorBeta: 5,             // Higher prior to reduce sampling variance
  betaDecayFactor: 0.5,         // Decay beta by 50% for transient failures
  shutdownDrainTimeout: 30000,  // 30s drain period before forced shutdown
  statementTimeout: 60000,      // 60s database statement timeout
};

// HTTP agent for health checks (dynamic connection pooling)
let healthCheckAgent = null;

function getHealthCheckAgent(fleetSize) {
  const maxSockets = Math.max(50, fleetSize * CONFIG.healthCheckMaxSocketsPerNode);

  if (healthCheckAgent) {
    healthCheckAgent.destroy();
  }

  healthCheckAgent = new http.Agent({
    maxSockets,
    timeout: 5000,
    keepAlive: true,
    keepAliveMsecs: 30000,
  });

  return healthCheckAgent;
}

// PostgreSQL connection pool
const pool = new Pool({
  host: 'localhost',
  database: 'learning',
  user: process.env.USER,
  max: 20,
  idleTimeoutMillis: 30000,
  statement_timeout: CONFIG.statementTimeout, // Database-side timeout enforcement
});

// Validate configuration
if (CONFIG.workTimeout <= 0) {
  throw new Error('workTimeout must be positive');
}
if (CONFIG.maxRetries < 1) {
  throw new Error('maxRetries must be at least 1');
}

/**
 * Work Reassignment Manager
 */
class WorkReassignmentManager {
  constructor(config = {}) {
    this.config = { ...CONFIG, ...config };
    this.inFlight = new Map(); // jobId -> {nodeId, startTime, slotReserved, abortController}
    this.healthChecks = new Map(); // jobId -> {intervalId, consecutiveFailures}
    this.failureLocks = new Map(); // jobId -> boolean (distributed lock simulation)
    this.shuttingDown = false;
  }

  /**
   * Get adaptive timeout for task type
   * @param {string} taskType - Task type (e.g., 'code-review', 'ai-consensus')
   * @returns {Promise<number>} Timeout in milliseconds
   */
  async getAdaptiveTimeout(taskType) {
    try {
      const result = await pool.query(
        `SELECT AVG(avg_duration_ms) as avg_ms
         FROM orchestrator.node_performance
         WHERE task_type = $1 AND avg_duration_ms > 0`,
        [taskType]
      );

      if (result.rows[0]?.avg_ms && result.rows[0].avg_ms > 0) {
        const adaptiveTimeout = Math.ceil(result.rows[0].avg_ms * this.config.timeoutMultiplier);
        return Math.max(
          this.config.workTimeout,
          Math.min(adaptiveTimeout, this.config.maxWorkTimeout)
        );
      }
    } catch (err) {
      console.warn(`Failed to get adaptive timeout for ${taskType}:`, err.message);
    }

    return this.config.workTimeout;
  }

  /**
   * Acquire advisory lock for work item (prevents duplicate failure handling)
   * @param {string} workId - Work queue ID
   * @returns {Promise<boolean>} True if lock acquired
   */
  async acquireFailureLock(workId) {
    try {
      // Use PostgreSQL advisory lock (session-level, auto-released on connection close)
      // Hash workId to 32-bit integer for pg_advisory_lock
      const lockId = this.hashToInt32(workId);

      const result = await pool.query(
        `SELECT pg_try_advisory_lock($1) as locked`,
        [lockId]
      );

      const locked = result.rows[0]?.locked || false;

      if (locked) {
        this.failureLocks.set(workId, true);
      }

      return locked;
    } catch (err) {
      console.error(`Failed to acquire failure lock for ${workId}:`, err.message);
      return false;
    }
  }

  /**
   * Release advisory lock for work item
   * @param {string} workId - Work queue ID
   */
  async releaseFailureLock(workId) {
    try {
      const lockId = this.hashToInt32(workId);

      await pool.query(
        `SELECT pg_advisory_unlock($1)`,
        [lockId]
      );

      this.failureLocks.delete(workId);
    } catch (err) {
      console.error(`Failed to release failure lock for ${workId}:`, err.message);
    }
  }

  /**
   * Hash string to 32-bit integer for advisory lock
   * @param {string} str - String to hash
   * @returns {number} 32-bit integer
   */
  hashToInt32(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash;
  }

  /**
   * Reserve work slot atomically (prevents duplicate work)
   * FIXED: SELECT FOR UPDATE SKIP LOCKED before UPDATE to prevent TOCTOU race
   * @param {string} workId - Work queue ID
   * @param {string} nodeId - Node session ID
   * @returns {Promise<{reserved: boolean, version: number}>} Reservation result
   */
  async reserveSlot(workId, nodeId) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      // FIXED: Acquire row lock first to prevent concurrent reserveSlot() race
      const lockResult = await client.query(
        `SELECT id, version, status, assigned_to
         FROM orchestrator.work_queue
         WHERE id = $1 AND status = 'pending'
         FOR UPDATE SKIP LOCKED`,
        [workId]
      );

      if (lockResult.rows.length === 0) {
        // Another process already locked this row or status changed
        await client.query('ROLLBACK');
        return { reserved: false, version: null };
      }

      const { version, assigned_to } = lockResult.rows[0];

      // Verify work is still available (double-check under lock)
      if (assigned_to !== null && assigned_to !== nodeId) {
        await client.query('ROLLBACK');
        return { reserved: false, version: null };
      }

      // Atomic slot reservation with version increment
      const result = await client.query(
        `UPDATE orchestrator.work_queue
         SET status = 'assigned',
             assigned_to = $1,
             assigned_at = NOW(),
             version = version + 1
         WHERE id = $2 AND version = $3
         RETURNING id, version`,
        [nodeId, workId, version]
      );

      await client.query('COMMIT');

      if (result.rows.length > 0) {
        this.inFlight.set(workId, {
          nodeId,
          startTime: Date.now(),
          slotReserved: true,
          abortController: new AbortController(),
          version: result.rows[0].version,
        });
        return { reserved: true, version: result.rows[0].version };
      }

      return { reserved: false, version: null };
    } catch (err) {
      await client.query('ROLLBACK');
      console.error(`Slot reservation failed for work ${workId}:`, err.message);
      return { reserved: false, version: null };
    } finally {
      client.release();
    }
  }

  /**
   * Release work slot (called on completion or timeout)
   * FIXED: Update database state to prevent zombie work
   * @param {string} workId - Work queue ID
   */
  async releaseSlot(workId) {
    const flight = this.inFlight.get(workId);
    if (flight?.abortController) {
      flight.abortController.abort();
    }

    this.inFlight.delete(workId);

    // Stop health check if running
    if (this.healthChecks.has(workId)) {
      const { intervalId } = this.healthChecks.get(workId);
      clearInterval(intervalId);
      this.healthChecks.delete(workId);
    }

    // FIXED: Mark slot as released in database to enable abandoned work detection
    try {
      await pool.query(
        `UPDATE orchestrator.work_queue
         SET result = COALESCE(result, '{}'::jsonb) || '{"slot_released": true, "released_at": $1}'::jsonb
         WHERE id = $2 AND status = 'in_progress'`,
        [new Date().toISOString(), workId]
      );
    } catch (err) {
      console.error(`Failed to mark slot as released for ${workId}:`, err.message);
    }
  }

  /**
   * Check node health via HTTP /health endpoint
   * @param {string} nodeId - Node session ID (format: server-03:9100)
   * @returns {Promise<boolean>} True if healthy
   */
  async checkNodeHealth(nodeId) {
    return new Promise((resolve) => {
      const [host, port] = nodeId.includes(':')
        ? nodeId.split(':')
        : [nodeId, '9100'];

      // Get dynamic agent based on current fleet size
      const fleetSize = this.inFlight.size || 10;
      const agent = getHealthCheckAgent(fleetSize);

      const req = http.get(
        `http://${host}:${port}/health`,
        { timeout: 5000, agent },
        (res) => {
          let body = '';
          res.on('data', chunk => body += chunk);
          res.on('end', () => {
            // Validate health endpoint response schema
            try {
              if (res.statusCode === 200) {
                const data = JSON.parse(body);
                resolve(data.status === 'ok' || data.healthy === true);
              } else {
                resolve(false);
              }
            } catch {
              // Fallback: accept 200 without JSON validation
              resolve(res.statusCode === 200);
            }
          });
        }
      );

      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  /**
   * Check session heartbeat in PostgreSQL
   * @param {string} nodeId - Node session ID
   * @returns {Promise<boolean>} True if heartbeat fresh
   */
  async checkHeartbeat(nodeId) {
    try {
      const result = await pool.query(
        `SELECT session_id
         FROM orchestrator.sessions
         WHERE session_id = $1
           AND last_heartbeat > NOW() - INTERVAL '${this.config.heartbeatTimeout / 1000} seconds'`,
        [nodeId]
      );

      return result.rows.length > 0;
    } catch (err) {
      console.error(`Heartbeat check failed for ${nodeId}:`, err.message);
      return false;
    }
  }

  /**
   * Detect SSH failure via exit code and error patterns
   * @param {Error} error - SSH execution error
   * @returns {boolean} True if SSH failure (vs work failure)
   */
  isSshFailure(error) {
    // SSH connection errors: 255, ECONNREFUSED, ETIMEDOUT, etc.
    if (error.status === 255) return true;
    if (error.code === 'ECONNREFUSED') return true;
    if (error.code === 'ETIMEDOUT') return true;
    if (error.code === 'ENOTFOUND') return true;
    if (error.code === 'EHOSTUNREACH') return true;

    const msg = error.message || '';
    if (msg.includes('Connection refused')) return true;
    if (msg.includes('Connection timed out')) return true;
    if (msg.includes('Host key verification failed')) return true;
    if (msg.includes('Permission denied')) return true;
    if (msg.includes('Protocol error')) return true;
    if (msg.includes('Name or service not known')) return true;
    if (msg.includes('No route to host')) return true;

    return false;
  }

  /**
   * Start health check monitoring for work item with circuit breaker
   * FIXED: Check work status before triggering failure
   * @param {string} workId - Work queue ID
   * @param {string} nodeId - Node session ID
   */
  startHealthCheck(workId, nodeId) {
    // Clear existing interval if present (prevent leak)
    if (this.healthChecks.has(workId)) {
      const { intervalId } = this.healthChecks.get(workId);
      clearInterval(intervalId);
    }

    let consecutiveFailures = 0;

    const intervalId = setInterval(async () => {
      // Circuit breaker: stop checking if node consistently fails
      if (consecutiveFailures >= this.config.healthCheckCircuitBreakerThreshold) {
        console.error(`Circuit breaker triggered for node ${nodeId} (work ${workId})`);
        clearInterval(intervalId);
        this.healthChecks.delete(workId);

        // FIXED: Check work status before triggering failure
        const statusResult = await pool.query(
          `SELECT status FROM orchestrator.work_queue WHERE id = $1`,
          [workId]
        );

        if (statusResult.rows.length === 0 || statusResult.rows[0].status !== 'in_progress') {
          console.log(`Work ${workId} already completed/failed, skipping circuit breaker failure`);
          return;
        }

        // Trigger immediate failure handling
        const flight = this.inFlight.get(workId);
        if (flight && Date.now() - flight.startTime > this.config.workTimeout) {
          await this.handleFailure(workId, nodeId, new Error('Circuit breaker: consecutive health check failures'));
        }
        return;
      }

      const healthy = await this.checkNodeHealth(nodeId);

      if (!healthy) {
        consecutiveFailures++;
        console.warn(`Health check failed for node ${nodeId} (work ${workId}), consecutive failures: ${consecutiveFailures}`);

        // If health check fails + timeout exceeded, trigger reassignment
        const flight = this.inFlight.get(workId);
        if (flight && Date.now() - flight.startTime > this.config.workTimeout) {
          // FIXED: Check work status before triggering failure
          const statusResult = await pool.query(
            `SELECT status FROM orchestrator.work_queue WHERE id = $1`,
            [workId]
          );

          if (statusResult.rows.length > 0 && statusResult.rows[0].status === 'in_progress') {
            console.error(`Work ${workId} timed out on unhealthy node ${nodeId}`);
            await this.handleFailure(workId, nodeId, new Error('Health check timeout'));
          }
        }
      } else {
        // Reset on success
        consecutiveFailures = 0;
      }

      // Update consecutive failures in map
      if (this.healthChecks.has(workId)) {
        this.healthChecks.get(workId).consecutiveFailures = consecutiveFailures;
      }
    }, this.config.healthCheckInterval);

    this.healthChecks.set(workId, { intervalId, consecutiveFailures });
  }

  /**
   * Get retry history from work result JSONB (with size limit)
   * @param {string} workId - Work queue ID
   * @returns {Promise<Array>} Array of previous attempts
   */
  async getRetryHistory(workId) {
    try {
      const result = await pool.query(
        `SELECT result FROM orchestrator.work_queue WHERE id = $1`,
        [workId]
      );

      const resultData = result.rows[0]?.result;
      if (resultData?.retry_history) {
        return resultData.retry_history;
      }
    } catch (err) {
      console.error(`Failed to get retry history for ${workId}:`, err.message);
    }

    return [];
  }

  /**
   * Truncate error message to prevent JSONB bloat
   * @param {string} message - Error message
   * @returns {string} Truncated message
   */
  truncateErrorMessage(message) {
    if (!message) return 'Unknown error';
    if (message.length <= this.config.maxErrorMessageLength) return message;
    return message.substring(0, this.config.maxErrorMessageLength) + '... (truncated)';
  }

  /**
   * Select alternative node for retry using Thompson Sampling with anti-affinity
   * FIXED: Re-check node availability after Thompson sampling
   * @param {string} taskType - Task type
   * @param {string} failedNodeId - Node that failed
   * @param {Array} previousAttempts - Previous retry attempts [{node, error, timestamp}]
   * @returns {Promise<{nodeId: string|null, allNodesExhausted: boolean}>} Selection result
   */
  async selectRetryNode(taskType, failedNodeId, previousAttempts = []) {
    try {
      // Get all nodes with performance data for this task type
      const result = await pool.query(
        `SELECT node_id, alpha, beta
         FROM orchestrator.node_performance
         WHERE task_type = $1 AND node_id != $2`,
        [taskType, failedNodeId]
      );

      if (result.rows.length === 0) {
        console.warn(`No alternative nodes available for task type ${taskType}`);
        return { nodeId: null, allNodesExhausted: true };
      }

      const previousNodes = new Set(previousAttempts.map(a => a.node));
      const allNodesExhausted = result.rows.every(row => previousNodes.has(row.node_id));

      // If all nodes exhausted, reset anti-affinity and select least-recently-failed
      if (allNodesExhausted) {
        console.warn(`All nodes exhausted for work retry, selecting least-recently-failed`);

        // Sort previous attempts by timestamp (oldest first)
        const sortedAttempts = [...previousAttempts].sort(
          (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
        );

        // Find oldest failed node that still exists in node_performance
        for (const attempt of sortedAttempts) {
          if (result.rows.some(row => row.node_id === attempt.node)) {
            return { nodeId: attempt.node, allNodesExhausted: true };
          }
        }
      }

      // Epsilon-greedy: 5% random exploration
      if (Math.random() < this.config.epsilonGreedy) {
        const availableNodes = result.rows.filter(row => !previousNodes.has(row.node_id));
        if (availableNodes.length > 0) {
          const randomNode = availableNodes[Math.floor(Math.random() * availableNodes.length)];
          console.log(`Epsilon-greedy exploration: selected random node ${randomNode.node_id}`);
          return { nodeId: randomNode.node_id, allNodesExhausted: false };
        }
      }

      // Apply temporary penalty to previously-attempted nodes
      const candidates = result.rows
        .filter(row => !previousNodes.has(row.node_id))
        .map(row => {
          let { alpha, beta } = row;

          // 50% alpha penalty for previously-failed nodes (shouldn't apply here due to filter)
          if (previousNodes.has(row.node_id)) {
            alpha = alpha * 0.5;
          }

          return {
            nodeId: row.node_id,
            alpha,
            beta,
          };
        });

      if (candidates.length === 0) {
        console.warn(`No untried alternative nodes for task type ${taskType}`);
        return { nodeId: null, allNodesExhausted: true };
      }

      // Thompson Sampling: proper Beta distribution sampling
      const sampled = this.thompsonSample(candidates);

      // FIXED: Re-check node availability after sampling
      if (sampled?.nodeId) {
        const availabilityCheck = await pool.query(
          `SELECT node_id FROM orchestrator.node_performance
           WHERE node_id = $1 AND task_type = $2`,
          [sampled.nodeId, taskType]
        );

        if (availabilityCheck.rows.length === 0) {
          console.warn(`Selected node ${sampled.nodeId} no longer available, retrying selection`);
          // Recursively retry selection (with depth limit implicit via candidates shrinking)
          const remainingCandidates = candidates.filter(c => c.nodeId !== sampled.nodeId);
          if (remainingCandidates.length > 0) {
            const resampled = this.thompsonSample(remainingCandidates);
            return {
              nodeId: resampled?.nodeId || null,
              allNodesExhausted: false
            };
          }
          return { nodeId: null, allNodesExhausted: true };
        }
      }

      return {
        nodeId: sampled?.nodeId || null,
        allNodesExhausted: false
      };
    } catch (err) {
      console.error(`Failed to select retry node for ${taskType}:`, err.message);
      return { nodeId: null, allNodesExhausted: false };
    }
  }

  /**
   * Thompson Sampling selection with proper Beta distribution
   * @param {Array} candidates - [{nodeId, alpha, beta}]
   * @returns {object|null} Selected candidate
   */
  thompsonSample(candidates) {
    if (candidates.length === 0) return null;

    // Sample from each candidate's Beta distribution
    const samples = candidates.map(c => ({
      ...c,
      sample: this.betaSample(c.alpha, c.beta),
    }));

    // Select candidate with highest sample
    samples.sort((a, b) => b.sample - a.sample);
    return samples[0];
  }

  /**
   * Proper Beta distribution sampling using Gamma distribution
   * FIXED: Higher prior (alpha=beta=5) to reduce sampling variance
   * @param {number} alpha - Alpha parameter
   * @param {number} beta - Beta parameter
   * @returns {number} Sample value in [0, 1]
   */
  betaSample(alpha, beta) {
    // Add prior to reduce variance for new nodes
    const priorAlpha = alpha + this.config.betaPriorAlpha;
    const priorBeta = beta + this.config.betaPriorBeta;

    // Beta(alpha, beta) = Gamma(alpha, 1) / (Gamma(alpha, 1) + Gamma(beta, 1))
    const x = this.gammaSample(priorAlpha, 1);
    const y = this.gammaSample(priorBeta, 1);

    // Add epsilon to prevent division by ~0
    const epsilon = 1e-10;
    return x / (x + y + epsilon);
  }

  /**
   * Gamma distribution sampling (Marsaglia and Tsang method)
   * @param {number} shape - Shape parameter (alpha)
   * @param {number} scale - Scale parameter (theta)
   * @returns {number} Sample value
   */
  gammaSample(shape, scale) {
    // Simplified Gamma sampling for shape >= 1
    if (shape < 1) {
      // Use shape + 1 and scale down
      return this.gammaSample(shape + 1, scale) * Math.pow(Math.random(), 1 / shape);
    }

    const d = shape - 1/3;
    const c = 1 / Math.sqrt(9 * d);

    let iterations = 0;
    const maxIterations = 1000; // Prevent infinite loop

    while (iterations < maxIterations) {
      iterations++;

      let x, v;
      do {
        x = this.normalSample(0, 1);
        v = 1 + c * x;
      } while (v <= 0);

      v = v * v * v;
      const u = Math.random();
      const x2 = x * x;

      if (u < 1 - 0.0331 * x2 * x2) {
        return d * v * scale;
      }

      if (Math.log(u) < 0.5 * x2 + d * (1 - v + Math.log(v))) {
        return d * v * scale;
      }
    }

    // Fallback if max iterations exceeded
    return d * scale;
  }

  /**
   * Normal distribution sampling (Box-Muller transform)
   * @param {number} mean - Mean
   * @param {number} stddev - Standard deviation
   * @returns {number} Sample value
   */
  normalSample(mean, stddev) {
    const u1 = Math.random();
    const u2 = Math.random();
    const z0 = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    return z0 * stddev + mean;
  }

  /**
   * Handle work failure and trigger retry/permanent failure
   * FIXED: SELECT FOR UPDATE before version-checked updates + distributed lock
   * @param {string} workId - Work queue ID
   * @param {string} nodeId - Failed node ID
   * @param {Error} error - Failure error
   * @param {boolean} isTransient - True if failure is transient (network/SSH)
   * @returns {Promise<void>}
   */
  async handleFailure(workId, nodeId, error, isTransient = false) {
    // FIXED: Acquire distributed lock to prevent double-timeout race
    const lockAcquired = await this.acquireFailureLock(workId);
    if (!lockAcquired) {
      console.warn(`Failure lock already held for work ${workId}, skipping duplicate failure handling`);
      return;
    }

    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      // FIXED: SELECT FOR UPDATE first to get current state atomically
      const workResult = await client.query(
        `SELECT retry_count, task_type, result, version, status
         FROM orchestrator.work_queue
         WHERE id = $1
         FOR UPDATE`,
        [workId]
      );

      if (workResult.rows.length === 0) {
        console.warn(`Work ${workId} not found in queue`);
        await client.query('ROLLBACK');
        return;
      }

      const { retry_count, task_type, result, version, status } = workResult.rows[0];

      // Check if work already completed/failed (late timeout)
      if (status !== 'in_progress' && status !== 'assigned') {
        console.warn(`Work ${workId} already in status ${status}, skipping failure handling`);
        await client.query('ROLLBACK');
        return;
      }

      let retryHistory = result?.retry_history || [];

      // Add this failure to retry history (with size limit)
      retryHistory.push({
        node: nodeId,
        error: this.truncateErrorMessage(error.message),
        timestamp: new Date().toISOString(),
        duration: Date.now() - (this.inFlight.get(workId)?.startTime || Date.now()),
        transient: isTransient,
      });

      // Limit retry history size
      if (retryHistory.length > this.config.maxRetryHistorySize) {
        retryHistory = retryHistory.slice(-this.config.maxRetryHistorySize);
      }

      // FIXED: Increment retry_count atomically with version check
      const newRetryCount = retry_count + 1;

      // Check if max retries exceeded
      if (newRetryCount > this.config.maxRetries) {
        // Mark as permanently failed
        await client.query(
          `UPDATE orchestrator.work_queue
           SET status = 'failed',
               result = $1,
               retry_count = $2,
               version = version + 1
           WHERE id = $3 AND version = $4`,
          [JSON.stringify({ retry_history: retryHistory, permanent_failure: true }), newRetryCount, workId, version]
        );

        // FIXED: Only update beta on permanent failure, not on every retry
        // Update node performance: increment beta (failure) for all attempted nodes
        for (const attempt of retryHistory) {
          await client.query(
            `UPDATE orchestrator.node_performance
             SET beta = beta + 1,
                 total_failures = total_failures + 1
             WHERE node_id = $1 AND task_type = $2`,
            [attempt.node, task_type]
          );
        }

        // Log permanent failure
        await client.query(
          `INSERT INTO monitoring.execution_summary
           (timestamp, model, workflow, task_type, quality_score, outcome)
           VALUES (NOW(), 'unknown', 'work-reassignment', $1, 0.0, 'permanent_failure')`,
          [task_type]
        );

        console.error(`Work ${workId} permanently failed after ${newRetryCount} retries`);

        if (this.config.permanentFailureAction === 'alert') {
          // TODO: Trigger alert system
          console.error(`ALERT: Permanent failure for work ${workId}`);
        }

        await client.query('COMMIT');
        this.releaseSlot(workId);
        return;
      }

      // Select alternative node for retry
      const { nodeId: retryNode, allNodesExhausted } = await this.selectRetryNode(
        task_type,
        nodeId,
        retryHistory
      );

      if (!retryNode) {
        if (allNodesExhausted) {
          console.warn(`All nodes exhausted for work ${workId}, applying backoff`);

          // Store backoff expiry time
          await client.query(
            `UPDATE orchestrator.work_queue
             SET status = 'pending',
                 assigned_to = NULL,
                 result = $1,
                 retry_count = $2,
                 version = version + 1
             WHERE id = $3 AND version = $4`,
            [JSON.stringify({
              retry_history: retryHistory,
              all_nodes_exhausted: true,
              backoff_until: new Date(Date.now() + this.config.allNodesExhaustedBackoff).toISOString(),
            }), newRetryCount, workId, version]
          );
        } else {
          console.warn(`No alternative node available for retry of work ${workId}`);

          // FIXED: Set backoff_until even when awaiting_slot to prevent infinite pending
          await client.query(
            `UPDATE orchestrator.work_queue
             SET status = 'pending',
                 assigned_to = NULL,
                 result = $1,
                 retry_count = $2,
                 version = version + 1
             WHERE id = $3 AND version = $4`,
            [JSON.stringify({
              retry_history: retryHistory,
              awaiting_slot: true,
              backoff_until: new Date(Date.now() + this.config.awaitingSlotBackoff).toISOString(),
            }), newRetryCount, workId, version]
          );
        }

        await client.query('COMMIT');
        this.releaseSlot(workId);
        return;
      }

      // Mark for retry on alternative node
      await client.query(
        `UPDATE orchestrator.work_queue
         SET status = 'pending',
             assigned_to = NULL,
             result = $1,
             retry_count = $2,
             version = version + 1
         WHERE id = $3 AND version = $4`,
        [JSON.stringify({
          retry_history: retryHistory,
          retry_node: retryNode,
          all_nodes_exhausted: allNodesExhausted,
        }), newRetryCount, workId, version]
      );

      // FIXED: Apply beta decay factor for transient failures (network/SSH)
      // Only penalize heavily for non-transient (work) failures
      const betaIncrement = isTransient ? this.config.betaDecayFactor : 1.0;

      await client.query(
        `UPDATE orchestrator.node_performance
         SET beta = beta + $1,
             total_failures = total_failures + 1
         WHERE node_id = $2 AND task_type = $3`,
        [betaIncrement, nodeId, task_type]
      );

      await client.query('COMMIT');

      // FIXED: Notify scheduler via LISTEN/NOTIFY
      await pool.query(`NOTIFY work_queue_updated, '{"action": "retry_available", "work_id": "${workId}"}'`);

      this.releaseSlot(workId);

      console.log(`Work ${workId} reassigned from ${nodeId} to ${retryNode} (retry ${newRetryCount}/${this.config.maxRetries})`);

    } catch (err) {
      await client.query('ROLLBACK');
      console.error(`Failed to handle work failure for ${workId}:`, err.message);
      this.releaseSlot(workId);
    } finally {
      client.release();
      await this.releaseFailureLock(workId);
    }
  }

  /**
   * Execute work with failure detection and reassignment
   * FIXED: Update node_performance stats even on late completion
   * @param {string} workId - Work queue ID
   * @param {string} nodeId - Target node session ID
   * @param {Function} executor - Execution function (async, accepts AbortSignal)
   * @returns {Promise<any>} Execution result
   */
  async executeWithFailureDetection(workId, nodeId, executor) {
    // Reserve slot atomically
    const { reserved, version } = await this.reserveSlot(workId, nodeId);
    if (!reserved) {
      throw new Error(`Failed to reserve slot for work ${workId} on node ${nodeId}`);
    }

    const client = await pool.connect();
    try {
      // Update status to in_progress with version check
      const updateResult = await client.query(
        `UPDATE orchestrator.work_queue
         SET status = 'in_progress',
             version = version + 1
         WHERE id = $1 AND version = $2 AND status = 'assigned'
         RETURNING version`,
        [workId, version]
      );

      if (updateResult.rows.length === 0) {
        throw new Error(`Failed to transition work ${workId} to in_progress (version conflict or status changed)`);
      }

      const inProgressVersion = updateResult.rows[0].version;

      // Start health check monitoring
      this.startHealthCheck(workId, nodeId);

      // Get adaptive timeout
      const taskType = await this.getTaskType(workId);
      const timeout = await this.getAdaptiveTimeout(taskType);

      const flight = this.inFlight.get(workId);
      if (!flight) {
        throw new Error(`Flight info lost for work ${workId}`);
      }

      // Execute with timeout and abort support
      // NOTE: executor MUST respect AbortSignal - see documentation below
      const result = await this.executeWithTimeout(
        () => executor(flight.abortController.signal),
        timeout
      );

      // Mark as completed with optimistic locking
      const completionResult = await client.query(
        `UPDATE orchestrator.work_queue
         SET status = 'completed',
             result = $1,
             completed_at = NOW(),
             version = version + 1
         WHERE id = $2 AND version = $3 AND status = 'in_progress'
         RETURNING id`,
        [JSON.stringify({ success: true, result }), workId, inProgressVersion]
      );

      const duration = Date.now() - flight.startTime;

      if (completionResult.rows.length === 0) {
        // Version conflict or status changed (likely timeout already fired)
        console.warn(`Late completion detected for work ${workId}, storing as duplicate`);

        // FIXED: Still update node_performance stats for late completion
        await this.handleLateCompletion(workId, result, nodeId, taskType, duration);
        return result;
      }

      // Update node performance: increment alpha (success)
      await client.query(
        `UPDATE orchestrator.node_performance
         SET alpha = alpha + 1,
             total_successes = total_successes + 1,
             avg_duration_ms = (avg_duration_ms * total_successes + $1) / (total_successes + 1)
         WHERE node_id = $2 AND task_type = $3`,
        [duration, nodeId, taskType]
      );

      this.releaseSlot(workId);
      return result;

    } catch (error) {
      // Determine failure type
      const isSshError = this.isSshFailure(error);
      const isTimeout = error.message?.includes('timeout') || error.name === 'AbortError';
      const isTransient = isSshError || isTimeout;

      console.error(`Work ${workId} failed on ${nodeId}: ${error.message} (SSH=${isSshError}, Timeout=${isTimeout})`);

      // Trigger reassignment
      await this.handleFailure(workId, nodeId, error, isTransient);

      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Execute function with timeout and proper cleanup
   *
   * IMPORTANT: Executors MUST respect AbortSignal to enable proper cancellation.
   *
   * Example for PostgreSQL queries:
   * ```javascript
   * async function executor(signal) {
   *   const client = await pool.connect();
   *   try {
   *     // Wire abort signal to query cancel
   *     signal.addEventListener('abort', () => {
   *       client.query('SELECT pg_cancel_backend($1)', [client.processID]);
   *     });
   *
   *     return await client.query('SELECT expensive_operation()');
   *   } finally {
   *     client.release();
   *   }
   * }
   * ```
   *
   * Note: Database-side timeout is enforced via statement_timeout (pool config).
   *
   * @param {Function} executor - Async function to execute
   * @param {number} timeoutMs - Timeout in milliseconds
   * @returns {Promise<any>} Execution result
   */
  async executeWithTimeout(executor, timeoutMs) {
    let timeoutId;

    const timeoutPromise = new Promise((_, reject) => {
      timeoutId = setTimeout(() => {
        const err = new Error('Execution timeout');
        err.name = 'AbortError';
        reject(err);
      }, timeoutMs);
    });

    try {
      const result = await Promise.race([
        executor(),
        timeoutPromise,
      ]);

      // Executor won the race, clear timeout
      clearTimeout(timeoutId);
      return result;
    } catch (error) {
      // Either executor threw or timeout fired
      clearTimeout(timeoutId);
      throw error;
    }
  }

  /**
   * Get task type for work item
   * @param {string} workId - Work queue ID
   * @returns {Promise<string>} Task type
   */
  async getTaskType(workId) {
    const result = await pool.query(
      `SELECT task_type FROM orchestrator.work_queue WHERE id = $1`,
      [workId]
    );
    return result.rows[0]?.task_type || 'unknown';
  }

  /**
   * Deep equality check for objects (order-insensitive)
   * @param {any} obj1 - First object
   * @param {any} obj2 - Second object
   * @returns {boolean} True if semantically equal
   */
  deepEqual(obj1, obj2) {
    if (obj1 === obj2) return true;
    if (obj1 == null || obj2 == null) return false;
    if (typeof obj1 !== typeof obj2) return false;

    if (typeof obj1 !== 'object') {
      // Handle floating point comparison
      if (typeof obj1 === 'number' && typeof obj2 === 'number') {
        return Math.abs(obj1 - obj2) < 1e-9;
      }
      return obj1 === obj2;
    }

    if (Array.isArray(obj1) !== Array.isArray(obj2)) return false;

    if (Array.isArray(obj1)) {
      if (obj1.length !== obj2.length) return false;
      for (let i = 0; i < obj1.length; i++) {
        if (!this.deepEqual(obj1[i], obj2[i])) return false;
      }
      return true;
    }

    const keys1 = Object.keys(obj1).sort();
    const keys2 = Object.keys(obj2).sort();

    if (keys1.length !== keys2.length) return false;
    if (!this.deepEqual(keys1, keys2)) return false;

    for (const key of keys1) {
      if (!this.deepEqual(obj1[key], obj2[key])) return false;
    }

    return true;
  }

  /**
   * Handle late completion (work completed after timeout) with idempotency check
   * FIXED: Deep equality check + update node_performance stats
   * @param {string} workId - Work queue ID
   * @param {any} result - Work result
   * @param {string} nodeId - Node session ID
   * @param {string} taskType - Task type
   * @param {number} duration - Execution duration in milliseconds
   */
  async handleLateCompletion(workId, result, nodeId, taskType, duration) {
    try {
      const workResult = await pool.query(
        `SELECT status, result FROM orchestrator.work_queue WHERE id = $1`,
        [workId]
      );

      if (workResult.rows.length === 0) return;

      const { status, result: existingResult } = workResult.rows[0];

      if (status === 'completed') {
        // FIXED: Use deep equality check instead of JSON.stringify
        const resultsDiffer = !this.deepEqual(result, existingResult?.result);

        if (resultsDiffer) {
          console.error(`CRITICAL: Late completion for work ${workId} has DIFFERENT result (non-idempotent work detected)`);
          console.error(`Task type: ${taskType}`);
          console.error(`Existing result:`, JSON.stringify(existingResult?.result).substring(0, 200));
          console.error(`Late result:`, JSON.stringify(result).substring(0, 200));
        }

        // Store as duplicate
        const updated = {
          ...existingResult,
          duplicate_completion: {
            result,
            timestamp: new Date().toISOString(),
            result_differs: resultsDiffer,
          },
        };

        await pool.query(
          `UPDATE orchestrator.work_queue
           SET result = $1
           WHERE id = $2`,
          [JSON.stringify(updated), workId]
        );

        console.warn(`Late completion for work ${workId} stored as duplicate`);

        // FIXED: Update node_performance stats even for late completion (proportionally)
        if (!resultsDiffer) {
          // If results match, credit the late completion (idempotent work)
          await pool.query(
            `UPDATE orchestrator.node_performance
             SET alpha = alpha + 0.5,
                 total_successes = total_successes + 0.5,
                 avg_duration_ms = (avg_duration_ms * total_successes + $1) / (total_successes + 0.5)
             WHERE node_id = $2 AND task_type = $3`,
            [duration, nodeId, taskType]
          );
          console.log(`Late completion stats updated for node ${nodeId} (0.5× credit for idempotent result)`);
        }
      } else {
        // First completion - store normally
        await pool.query(
          `UPDATE orchestrator.work_queue
           SET status = 'completed',
               result = $1,
               completed_at = NOW(),
               version = version + 1
           WHERE id = $2 AND status = 'in_progress'`,
          [JSON.stringify({ late_completion: true, result }), workId]
        );

        // Update node_performance stats
        await pool.query(
          `UPDATE orchestrator.node_performance
           SET alpha = alpha + 1,
               total_successes = total_successes + 1,
               avg_duration_ms = (avg_duration_ms * total_successes + $1) / (total_successes + 1)
           WHERE node_id = $2 AND task_type = $3`,
          [duration, nodeId, taskType]
        );

        console.log(`Late completion for work ${workId} accepted`);
      }
    } catch (err) {
      console.error(`Failed to handle late completion for ${workId}:`, err.message);
    }
  }

  /**
   * Cleanup: Stop all health checks and release slots
   */
  cleanup() {
    for (const [workId, { intervalId }] of this.healthChecks.entries()) {
      clearInterval(intervalId);
    }
    this.healthChecks.clear();

    for (const [workId, flight] of this.inFlight.entries()) {
      if (flight.abortController) {
        flight.abortController.abort();
      }
    }
    this.inFlight.clear();
  }

  /**
   * Graceful shutdown with drain period
   * FIXED: Wait up to 30s for in-flight work to complete
   * @returns {Promise<void>}
   */
  async gracefulShutdown() {
    this.shuttingDown = true;
    console.log('Starting graceful shutdown...');

    const drainStart = Date.now();
    const drainDeadline = drainStart + this.config.shutdownDrainTimeout;

    // Wait for in-flight work to complete
    while (this.inFlight.size > 0 && Date.now() < drainDeadline) {
      const remaining = this.inFlight.size;
      const timeLeft = Math.ceil((drainDeadline - Date.now()) / 1000);
      console.log(`Waiting for ${remaining} in-flight work items to complete (${timeLeft}s remaining)...`);
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    if (this.inFlight.size > 0) {
      console.warn(`Forcefully aborting ${this.inFlight.size} remaining work items after drain timeout`);

      // Mark remaining work as interrupted
      for (const [workId, flight] of this.inFlight.entries()) {
        try {
          await pool.query(
            `UPDATE orchestrator.work_queue
             SET status = 'pending',
                 assigned_to = NULL,
                 result = COALESCE(result, '{}'::jsonb) || '{"interrupted": true, "shutdown_abort": true}'::jsonb
             WHERE id = $1 AND status = 'in_progress'`,
            [workId]
          );

          console.log(`Work ${workId} marked as interrupted due to forced shutdown`);
        } catch (err) {
          console.error(`Failed to mark work ${workId} as interrupted:`, err.message);
        }
      }
    }

    this.cleanup();

    console.log(`Graceful shutdown complete (${this.inFlight.size === 0 ? 'clean' : 'forced'})`);
  }
}

/**
 * Standalone timeout monitor (runs periodically to detect hung work)
 */
class TimeoutMonitor {
  constructor(reassignmentManager, intervalMs = 30000) {
    this.manager = reassignmentManager;
    this.intervalMs = intervalMs;
    this.intervalId = null;
  }

  /**
   * Start monitoring for timeouts
   */
  start() {
    this.intervalId = setInterval(async () => {
      await this.checkTimeouts();
      await this.checkAbandonedAssignments();
      await this.checkBackoffExpiry();
    }, this.intervalMs);

    // Listen for work queue updates (backoff expiry notifications)
    this.listenForNotifications();
  }

  /**
   * Stop monitoring
   */
  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Listen for PostgreSQL NOTIFY events
   */
  async listenForNotifications() {
    try {
      const client = await pool.connect();

      await client.query('LISTEN work_queue_updated');

      client.on('notification', async (msg) => {
        if (msg.channel === 'work_queue_updated') {
          try {
            const payload = JSON.parse(msg.payload);
            console.log(`Received work queue notification:`, payload);

            if (payload.action === 'retry_available') {
              // Trigger immediate scheduler poll (external integration point)
              console.log(`Retry available for work ${payload.work_id}, notifying scheduler`);
            }
          } catch (err) {
            console.error('Failed to parse notification payload:', err.message);
          }
        }
      });

      console.log('Listening for work queue notifications');
    } catch (err) {
      console.error('Failed to set up NOTIFY listener:', err.message);
    }
  }

  /**
   * Check for timed-out work items (using database timestamps)
   */
  async checkTimeouts() {
    try {
      // Find work items that are in_progress but assigned_at is old (use database time)
      const result = await pool.query(
        `SELECT id, assigned_to, task_type, assigned_at
         FROM orchestrator.work_queue
         WHERE status = 'in_progress'
           AND assigned_at < NOW() - INTERVAL '${this.manager.config.workTimeout / 1000} seconds'`
      );

      for (const row of result.rows) {
        const { id, assigned_to, task_type } = row;

        // Check heartbeat before marking as failed
        const heartbeatOk = await this.manager.checkHeartbeat(assigned_to);

        if (!heartbeatOk) {
          // Grace period: use database time for consistency
          const gracePeriodResult = await pool.query(
            `SELECT id FROM orchestrator.work_queue
             WHERE id = $1
               AND assigned_at < NOW() - INTERVAL '${(this.manager.config.workTimeout + this.manager.config.retryGracePeriod) / 1000} seconds'`,
            [id]
          );

          if (gracePeriodResult.rows.length > 0) {
            console.error(`Work ${id} timed out on node ${assigned_to} (no heartbeat + grace period expired)`);
            await this.manager.handleFailure(id, assigned_to, new Error('Heartbeat timeout + grace period expired'), false);
          } else {
            // Calculate remaining grace period
            const remainingResult = await pool.query(
              `SELECT EXTRACT(EPOCH FROM (
                NOW() - INTERVAL '${(this.manager.config.workTimeout + this.manager.config.retryGracePeriod) / 1000} seconds' - assigned_at
              )) as remaining_seconds
              FROM orchestrator.work_queue
              WHERE id = $1`,
              [id]
            );

            const remainingSeconds = Math.abs(Math.ceil(remainingResult.rows[0]?.remaining_seconds || 0));
            console.warn(`Work ${id} timeout detected but within grace period (${remainingSeconds}s remaining)`);
          }
        }
      }
    } catch (err) {
      console.error('Timeout monitor check failed:', err.message);
    }
  }

  /**
   * Check for abandoned assignments (stuck in 'assigned' or 'in_progress' status)
   * FIXED: Extended to cover 'in_progress' status with stale assigned_at
   */
  async checkAbandonedAssignments() {
    try {
      // Check assigned status (5 min timeout)
      const assignedResult = await pool.query(
        `SELECT id, assigned_to, task_type
         FROM orchestrator.work_queue
         WHERE status = 'assigned'
           AND assigned_at < NOW() - INTERVAL '${this.manager.config.abandonedAssignmentTimeout / 1000} seconds'`
      );

      for (const row of assignedResult.rows) {
        const { id, assigned_to, task_type } = row;

        console.warn(`Abandoned assignment detected: work ${id} stuck in 'assigned' for ${this.manager.config.abandonedAssignmentTimeout / 1000}s`);

        // Reset to pending
        await pool.query(
          `UPDATE orchestrator.work_queue
           SET status = 'pending',
               assigned_to = NULL,
               result = COALESCE(result, '{}'::jsonb) || '{"abandoned_assignment": true, "previous_node": $1}'::jsonb
           WHERE id = $2 AND status = 'assigned'`,
          [assigned_to, id]
        );

        console.log(`Work ${id} reset to pending after abandoned assignment on ${assigned_to}`);
      }

      // FIXED: Check in_progress status (10 min timeout)
      const inProgressResult = await pool.query(
        `SELECT id, assigned_to, task_type, result
         FROM orchestrator.work_queue
         WHERE status = 'in_progress'
           AND assigned_at < NOW() - INTERVAL '${this.manager.config.abandonedInProgressTimeout / 1000} seconds'
           AND (result->>'slot_released' = 'true' OR result IS NULL)`
      );

      for (const row of inProgressResult.rows) {
        const { id, assigned_to, task_type } = row;

        console.warn(`Abandoned in_progress work detected: work ${id} stuck for ${this.manager.config.abandonedInProgressTimeout / 1000}s with slot released`);

        // Reset to pending
        await pool.query(
          `UPDATE orchestrator.work_queue
           SET status = 'pending',
               assigned_to = NULL,
               result = COALESCE(result, '{}'::jsonb) || '{"abandoned_in_progress": true, "previous_node": $1}'::jsonb
           WHERE id = $2 AND status = 'in_progress'`,
          [assigned_to, id]
        );

        console.log(`Work ${id} reset to pending after abandoned in_progress on ${assigned_to}`);
      }
    } catch (err) {
      console.error('Abandoned assignment check failed:', err.message);
    }
  }

  /**
   * Check for work items with expired backoff period (all nodes exhausted recovery)
   * FIXED: Notify scheduler via LISTEN/NOTIFY when backoff expires
   */
  async checkBackoffExpiry() {
    try {
      const result = await pool.query(
        `SELECT id, result
         FROM orchestrator.work_queue
         WHERE status = 'pending'
           AND (result->>'all_nodes_exhausted' = 'true' OR result->>'awaiting_slot' = 'true')
           AND result->>'backoff_until' IS NOT NULL`
      );

      for (const row of result.rows) {
        const { id, result } = row;
        const backoffUntil = new Date(result.backoff_until);

        if (backoffUntil <= new Date()) {
          console.log(`Backoff expired for work ${id}, clearing flags and notifying scheduler`);

          // Clear backoff flag to allow retry
          const updatedResult = { ...result };
          delete updatedResult.all_nodes_exhausted;
          delete updatedResult.awaiting_slot;
          delete updatedResult.backoff_until;

          await pool.query(
            `UPDATE orchestrator.work_queue
             SET result = $1
             WHERE id = $2`,
            [JSON.stringify(updatedResult), id]
          );

          // FIXED: Notify scheduler via LISTEN/NOTIFY
          await pool.query(`NOTIFY work_queue_updated, '{"action": "backoff_expired", "work_id": "${id}"}'`);
        }
      }
    } catch (err) {
      console.error('Backoff expiry check failed:', err.message);
    }
  }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully...');

  if (global.timeoutMonitor) {
    global.timeoutMonitor.stop();
  }

  if (global.workReassignmentManager) {
    await global.workReassignmentManager.gracefulShutdown();
  }

  await pool.end();

  if (healthCheckAgent) {
    healthCheckAgent.destroy();
  }

  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, shutting down gracefully...');

  if (global.timeoutMonitor) {
    global.timeoutMonitor.stop();
  }

  if (global.workReassignmentManager) {
    await global.workReassignmentManager.gracefulShutdown();
  }

  await pool.end();

  if (healthCheckAgent) {
    healthCheckAgent.destroy();
  }

  process.exit(0);
});

// Export
module.exports = {
  WorkReassignmentManager,
  TimeoutMonitor,
  CONFIG,
};
