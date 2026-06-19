/**
 * Fleet Auto-Recovery Module
 *
 * Provides automatic node recovery detection and work redistribution
 * Integrates with DistributedOrchestrator for fleet resilience
 *
 * Key Features:
 * - HTTP health probe with exponential backoff
 * - Database heartbeat verification
 * - Optimistic concurrency via work_version
 * - Race condition prevention (FOR UPDATE SKIP LOCKED)
 * - Session resurrection (dead → active)
 * - Automatic work reassignment
 */

import { Pool } from 'pg';
import http from 'http';
import { readFileSync } from 'fs';
import path from 'path';
import os from 'os';

// Configuration
const CONFIG_PATH = path.join(os.homedir(), '.claude', 'orchestrator', 'fleet-resilience-config.json');

const DEFAULT_CONFIG = {
  autoRecovery: {
    probeInterval: 30000,        // 30s between probes
    exponentialBackoff: true,
    backoffMultiplier: 2,
    maxBackoff: 120000,          // 2 min max
    verifyHeartbeatAge: 60000,   // Heartbeat must be <60s old
    httpTimeout: 5000,           // 5s HTTP timeout
    maxRetries: 3,
    sessionTimeout: 120000,      // 2 min before marking dead
    httpBodyLimit: 10240,        // 10KB max response body
    probeLockTimeout: 60000      // 1 min probe lock expiry
  },
  circuitBreaker: {
    failureThreshold: 3,
    resetTimeout: 60000,         // 1 min cooldown
    halfOpenRequests: 1
  },
  fleet: [
    { id: 'laptop-01', host: 'laptop-01', port: 7340 },
    { id: 'aio-01', host: 'aio-01', port: 7340 },
    { id: 'server-01', host: 'server-01', port: 7340 },
    { id: 'server-02', host: 'server-02', port: 7340 },
    { id: 'server-03', host: 'server-03', port: 7340 }
  ],
  database: {
    host: '/var/run/postgresql',
    database: 'learning',
    user: process.env.USER || 'sfloess',
    max: 5,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 5000
  }
};

/**
 * Auto-Recovery Engine
 */
export class AutoRecovery {
  constructor(config = {}) {
    this.config = this.loadConfig(config);
    this.pool = null;
    this.nodeStates = new Map(); // nodeId -> NodeRecoveryState
    this.probeTimers = new Map(); // nodeId -> setTimeout handle
    this.probeLocks = new Map(); // nodeId -> { locked: boolean, timestamp: number }
    this.isRunning = false;
    this.isStopping = false;
    this.isShuttingDown = false; // FIXED: Add shutdown flag for abort signaling
    this.dbHealthy = true;
    this.globalErrorHandler = null;
    this.stopCalled = false; // Prevent multiple stop() calls
    this.maxFailureRetries = 3; // Limit onNodeFailed retry attempts
  }

  /**
   * Load configuration from file or use defaults
   *
   * Fixed: Always validate merged config before returning
   */
  loadConfig(overrides) {
    let mergedConfig;

    try {
      const fileConfig = JSON.parse(readFileSync(CONFIG_PATH, 'utf8'));
      mergedConfig = { ...DEFAULT_CONFIG, ...fileConfig, ...overrides };
    } catch (err) {
      if (err.code !== 'ENOENT') {
        console.warn(`[AutoRecovery] Failed to load config from ${CONFIG_PATH}: ${err.message}. Using defaults.`);
      }
      mergedConfig = { ...DEFAULT_CONFIG, ...overrides };
    }

    // FIXED: Always validate merged config (including overrides)
    try {
      this.validateFleetConfigInternal(mergedConfig);
    } catch (validationErr) {
      throw new Error(`Configuration validation failed: ${validationErr.message}`);
    }

    return mergedConfig;
  }

  /**
   * Validate fleet configuration (internal helper)
   */
  validateFleetConfigInternal(config) {
    if (!Array.isArray(config.fleet) || config.fleet.length === 0) {
      throw new Error('Fleet configuration must be a non-empty array');
    }

    for (const node of config.fleet) {
      if (!node.id || typeof node.id !== 'string') {
        throw new Error(`Invalid fleet node: missing or invalid 'id' field`);
      }
      if (!node.host || typeof node.host !== 'string') {
        throw new Error(`Invalid fleet node ${node.id}: missing or invalid 'host' field`);
      }
      if (!node.port || typeof node.port !== 'number') {
        throw new Error(`Invalid fleet node ${node.id}: missing or invalid 'port' field`);
      }
    }
  }

  /**
   * Validate fleet configuration (public API)
   */
  validateFleetConfig() {
    if (!this.isRunning) {
      throw new Error('AutoRecovery not started');
    }
    this.validateFleetConfigInternal(this.config);
  }

  /**
   * Initialize database connection
   *
   * Fixed: Idempotent error handler registration
   */
  async connect() {
    if (this.pool) return;

    let dbConfig = { ...this.config.database };

    this.pool = new Pool(dbConfig);

    // Single global error handler
    if (!this.globalErrorHandler) {
      this.globalErrorHandler = (err) => {
        this.log(`PostgreSQL connection error: ${err.message}`);
        this.dbHealthy = false;

        if (this.isRunning && !this.stopCalled) {
          this.log('Database connection lost - stopping auto-recovery');
          this.stop().catch(e => this.log(`Error during emergency stop: ${e.message}`));
        }
      };
    }

    // FIXED: Idempotent registration - remove first, then add
    this.pool.removeListener('error', this.globalErrorHandler);
    this.pool.on('error', this.globalErrorHandler);

    // Verify connection
    try {
      await this.pool.query('SELECT 1');
      this.dbHealthy = true;
      this.log('Connected to PostgreSQL');
    } catch (err) {
      if (dbConfig.host === '/var/run/postgresql') {
        this.log('Unix socket connection failed, trying TCP localhost:5432');

        this.pool.removeAllListeners('error');
        await this.pool.end();

        dbConfig = { ...this.config.database, host: 'localhost', port: 5432 };
        this.pool = new Pool(dbConfig);

        // FIXED: Idempotent re-registration
        this.pool.removeListener('error', this.globalErrorHandler);
        this.pool.on('error', this.globalErrorHandler);

        await this.pool.query('SELECT 1');
        this.dbHealthy = true;
        this.log('Connected to PostgreSQL via TCP');
      } else {
        throw new Error(`Failed to connect to PostgreSQL: ${err.message}`);
      }
    }
  }

  /**
   * Disconnect from database
   */
  async disconnect() {
    if (this.pool) {
      this.pool.removeAllListeners('error');
      await this.pool.end();
      this.pool = null;
    }
  }

  /**
   * Start auto-recovery monitoring
   */
  async start() {
    if (this.isRunning) {
      this.log('Auto-recovery already running');
      return;
    }

    await this.connect();
    this.isRunning = true;
    this.stopCalled = false;
    this.isStopping = false;
    this.isShuttingDown = false; // FIXED: Reset shutdown flag

    // Initialize node states
    for (const node of this.config.fleet) {
      this.nodeStates.set(node.id, {
        nodeId: node.id,
        host: node.host,
        port: node.port,
        status: 'unknown', // unknown | healthy | degraded | failed | recovering
        lastProbe: null,
        lastSuccess: null,
        consecutiveFailures: 0,
        backoffDelay: this.config.autoRecovery.probeInterval,
        circuitState: 'closed', // closed | open | half_open
        transitionInProgress: false, // Atomic state transition guard
        failureRetries: 0 // Track onNodeFailed retry attempts
      });
      this.probeLocks.set(node.id, { locked: false, timestamp: 0 });
    }

    // Start probing all nodes
    for (const node of this.config.fleet) {
      this.scheduleProbe(node.id);
    }

    this.log('Auto-recovery started');
  }

  /**
   * Stop auto-recovery monitoring
   *
   * Fixed: Set shutdown flag early and check in all async operations
   */
  async stop() {
    if (!this.isRunning || this.stopCalled) return;

    this.stopCalled = true;
    this.isStopping = true;
    this.isShuttingDown = true; // FIXED: Signal shutdown to in-flight operations
    this.isRunning = false;

    // Wait for in-flight probes (max 5 seconds)
    const maxWait = 5000;
    const startWait = Date.now();

    while (Date.now() - startWait < maxWait) {
      let anyLocked = false;
      for (const [nodeId, lock] of this.probeLocks) {
        if (lock.locked) {
          anyLocked = true;
          break;
        }
      }

      if (!anyLocked) break;
      await new Promise(r => setTimeout(r, 100));
    }

    // Clear all probe timers
    for (const timer of this.probeTimers.values()) {
      clearTimeout(timer);
    }
    this.probeTimers.clear();
    this.probeLocks.clear();

    await this.disconnect();
    this.log('Auto-recovery stopped');
  }

  /**
   * Remove a node permanently (cleanup timers and state)
   */
  removeNode(nodeId) {
    const timer = this.probeTimers.get(nodeId);
    if (timer) {
      clearTimeout(timer);
      this.probeTimers.delete(nodeId);
    }

    this.probeLocks.delete(nodeId);
    this.nodeStates.delete(nodeId);

    this.log(`Removed node ${nodeId} from monitoring`);
  }

  /**
   * Schedule next probe for a node (with exponential backoff)
   *
   * Fixed: Clear timer FIRST to prevent race condition
   * Fixed: Always recalculate delay from consecutiveFailures
   */
  scheduleProbe(nodeId, delay = null) {
    if (!this.isRunning || this.isStopping) return;

    const state = this.nodeStates.get(nodeId);
    if (!state) return;

    // FIXED: Clear existing timer FIRST (before ANY other logic)
    const existingTimer = this.probeTimers.get(nodeId);
    if (existingTimer) {
      clearTimeout(existingTimer);
      this.probeTimers.delete(nodeId);
    }

    // FIXED: Always recalculate delay from consecutiveFailures (ignore stale state.backoffDelay)
    let probeDelay = delay;
    if (probeDelay === null) {
      if (this.config.autoRecovery.exponentialBackoff && state.consecutiveFailures > 0) {
        probeDelay = Math.min(
          this.config.autoRecovery.probeInterval * Math.pow(this.config.autoRecovery.backoffMultiplier, state.consecutiveFailures),
          this.config.autoRecovery.maxBackoff
        );
      } else {
        probeDelay = this.config.autoRecovery.probeInterval;
      }
    }

    // Schedule next probe with error boundary
    const timer = setTimeout(() => {
      if (!this.isRunning || !this.pool || this.isStopping || this.isShuttingDown) {
        return;
      }

      setImmediate(async () => {
        try {
          await this.probeNode(nodeId);
          this.scheduleProbe(nodeId);
        } catch (err) {
          this.log(`Unhandled error in probe for ${nodeId}: ${err.message}`);
          this.scheduleProbe(nodeId);
        }
      });
    }, probeDelay);

    this.probeTimers.set(nodeId, timer);
  }

  /**
   * Check if probe lock is valid (not expired)
   *
   * Fixed: Explicitly reset lock after expiry check
   */
  isProbeLocked(nodeId) {
    const lock = this.probeLocks.get(nodeId);
    if (!lock || !lock.locked) return false;

    const lockAge = Date.now() - lock.timestamp;
    if (lockAge > this.config.autoRecovery.probeLockTimeout) {
      this.log(`Probe lock expired for ${nodeId} (age=${Math.round(lockAge / 1000)}s)`);
      // FIXED: Explicitly reset lock
      this.probeLocks.set(nodeId, { locked: false, timestamp: 0 });
      return false;
    }

    return true;
  }

  /**
   * Probe a single node for health
   * @param {string} nodeId - Node identifier
   * @returns {Promise<boolean>} - True if healthy
   */
  async probeNode(nodeId) {
    // Check shutdown flag at entry
    if (!this.isRunning || !this.pool || this.isStopping || this.isShuttingDown) {
      return false;
    }

    // FIXED: Check and reset expired lock before returning
    if (this.isProbeLocked(nodeId)) {
      return false;
    }

    const state = this.nodeStates.get(nodeId);
    if (!state) return false;

    this.probeLocks.set(nodeId, { locked: true, timestamp: Date.now() });

    try {
      state.lastProbe = new Date();

      // Step 1: HTTP health check
      const httpHealthy = await this.httpHealthProbe(state.host, state.port);

      if (!httpHealthy) {
        return await this.handleProbeFailure(nodeId, 'HTTP health check failed');
      }

      // FIXED: Check shutdown flag before database operations
      if (this.isShuttingDown || !this.pool) {
        return false;
      }

      // Step 2: Database heartbeat verification
      const dbHealthy = await this.verifyDatabaseHeartbeat(nodeId);

      if (!dbHealthy) {
        return await this.handleProbeFailure(nodeId, 'Database heartbeat stale');
      }

      // Success - node is healthy
      return await this.handleProbeSuccess(nodeId);

    } catch (err) {
      return await this.handleProbeFailure(nodeId, err.message);
    } finally {
      this.probeLocks.set(nodeId, { locked: false, timestamp: 0 });
    }
  }

  /**
   * HTTP health probe with timeout
   *
   * Fixed: Add resolved check to ALL handlers at START
   * Fixed: Prevent res.on('end') double-resolution after destroy
   */
  async httpHealthProbe(host, port, timeout = null) {
    timeout = timeout || this.config.autoRecovery.httpTimeout;
    const bodyLimit = this.config.autoRecovery.httpBodyLimit;

    return new Promise((resolve) => {
      const startTime = Date.now();
      let resolved = false;
      let bodySize = 0;

      const safeResolve = (value) => {
        if (!resolved) {
          resolved = true;
          resolve(value);
        }
      };

      const req = http.get({
        hostname: host,
        port: port,
        path: '/health',
        timeout: timeout
      }, (res) => {
        let body = '';

        res.on('data', chunk => {
          // FIXED: Check resolved at START to prevent memory leak
          if (resolved) return;

          bodySize += chunk.length;

          if (bodySize > bodyLimit) {
            req.destroy();
            this.log(`HTTP probe ${host}:${port} FAILED: response too large (>${bodyLimit} bytes)`);
            safeResolve(false);
            return;
          }

          body += chunk;
        });

        res.on('end', () => {
          // FIXED: Check resolved at START to prevent double-resolution after destroy
          if (resolved) return;

          const latency = Date.now() - startTime;

          if (res.statusCode === 200) {
            try {
              const data = JSON.parse(body);
              if (data.status === 'ok') {
                this.log(`HTTP probe ${host}:${port} OK (${latency}ms)`);
                safeResolve(true);
                return;
              }
            } catch (err) {
              // Invalid JSON
            }
          }

          this.log(`HTTP probe ${host}:${port} FAILED (status=${res.statusCode})`);
          safeResolve(false);
        });
      });

      req.on('error', (err) => {
        if (resolved) return;
        this.log(`HTTP probe ${host}:${port} ERROR: ${err.message}`);
        safeResolve(false);
      });

      req.on('timeout', () => {
        if (resolved) return;
        req.destroy();
        this.log(`HTTP probe ${host}:${port} TIMEOUT (>${timeout}ms)`);
        safeResolve(false);
      });
    });
  }

  /**
   * Verify database heartbeat is recent
   *
   * Fixed: Check node state BEFORE query to reject failed/degraded idle nodes
   */
  async verifyDatabaseHeartbeat(nodeId) {
    // FIXED: Check shutdown flag
    if (this.isShuttingDown || !this.pool) {
      return false;
    }

    try {
      const maxAge = this.config.autoRecovery.verifyHeartbeatAge;
      const state = this.nodeStates.get(nodeId);

      // FIXED: Reject failed/degraded nodes BEFORE query
      if (state && (state.status === 'failed' || state.status === 'degraded')) {
        // For failed/degraded nodes, require active session to recover
        const { rows } = await this.pool.query(`
          SELECT session_id, last_heartbeat, status,
                 EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) * 1000 AS age_ms
          FROM orchestrator.sessions
          WHERE node_id = $1 AND status = 'active'
          ORDER BY last_heartbeat DESC
          LIMIT 1
        `, [nodeId]);

        if (rows.length === 0) {
          this.log(`No active sessions for node ${nodeId} (marked ${state.status}) - NOT healthy`);
          return false;
        }

        const heartbeatAge = rows[0].age_ms;
        if (heartbeatAge > maxAge) {
          this.log(`Node ${nodeId} heartbeat stale (${Math.round(heartbeatAge / 1000)}s old)`);
          return false;
        }

        this.log(`Node ${nodeId} heartbeat OK (${Math.round(heartbeatAge / 1000)}s ago)`);
        return true;
      }

      // For unknown/healthy nodes, idle is acceptable
      const { rows } = await this.pool.query(`
        SELECT session_id, last_heartbeat, status,
               EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) * 1000 AS age_ms
        FROM orchestrator.sessions
        WHERE node_id = $1 AND status = 'active'
        ORDER BY last_heartbeat DESC
        LIMIT 1
      `, [nodeId]);

      if (rows.length === 0) {
        this.log(`No active sessions for node ${nodeId} (idle)`);
        return true;
      }

      const session = rows[0];
      const heartbeatAge = session.age_ms;

      if (heartbeatAge > maxAge) {
        this.log(`Node ${nodeId} heartbeat stale (${Math.round(heartbeatAge / 1000)}s old)`);
        return false;
      }

      this.log(`Node ${nodeId} heartbeat OK (${Math.round(heartbeatAge / 1000)}s ago)`);
      return true;

    } catch (err) {
      this.log(`Database heartbeat check failed for ${nodeId}: ${err.message}`);
      return false;
    }
  }

  /**
   * Handle probe failure
   *
   * Fixed: Extract error message explicitly to prevent [object Object]
   */
  async handleProbeFailure(nodeId, reason) {
    const state = this.nodeStates.get(nodeId);
    if (!state) return false;

    // FIXED: Extract error message explicitly
    const sanitizedReason = (reason instanceof Error ? reason.message : String(reason)).substring(0, 500);

    const previousStatus = state.status;
    state.consecutiveFailures++;

    // Atomic state transitions with guard
    if (state.consecutiveFailures >= this.config.circuitBreaker.failureThreshold) {
      if (state.circuitState !== 'open' && !state.transitionInProgress) {
        state.transitionInProgress = true;
        state.circuitState = 'open';
        state.status = 'failed';

        try {
          await this.onNodeFailed(nodeId, sanitizedReason);
        } catch (err) {
          this.log(`Error in onNodeFailed handler: ${err.message}`);
        } finally {
          state.transitionInProgress = false;
        }

        this.log(`❌ Node ${nodeId} FAILED (${state.consecutiveFailures} failures) - ${sanitizedReason}`);
      }
    } else if (state.consecutiveFailures >= 2) {
      if (state.status !== 'degraded' && !state.transitionInProgress) {
        state.transitionInProgress = true;
        state.status = 'degraded';

        try {
          await this.onNodeDegraded(nodeId, sanitizedReason);
        } catch (err) {
          this.log(`Error in onNodeDegraded handler: ${err.message}`);
        } finally {
          state.transitionInProgress = false;
        }

        this.log(`⚠️ Node ${nodeId} DEGRADED (${state.consecutiveFailures} failures) - ${sanitizedReason}`);
      }
    }

    return false;
  }

  /**
   * Handle probe success
   */
  async handleProbeSuccess(nodeId) {
    const state = this.nodeStates.get(nodeId);
    if (!state) return true;

    const wasUnhealthy = state.status !== 'healthy';

    state.consecutiveFailures = 0;
    state.backoffDelay = this.config.autoRecovery.probeInterval;
    state.lastSuccess = new Date();
    state.failureRetries = 0;

    // Detect recovery
    if (wasUnhealthy) {
      const recovered = await this.detectRecovery(nodeId);
      if (recovered && state.status !== 'healthy' && !state.transitionInProgress) {
        state.transitionInProgress = true;
        state.status = 'healthy';
        state.circuitState = 'closed';

        try {
          await this.onNodeRecovered(nodeId);
        } catch (err) {
          this.log(`Error in onNodeRecovered handler: ${err.message}`);
        } finally {
          state.transitionInProgress = false;
        }

        this.log(`✅ Node ${nodeId} RECOVERED`);
      }
    } else {
      state.status = 'healthy';
      state.circuitState = 'closed';
    }

    return true;
  }

  /**
   * Detect if a node has recovered (Layer 5)
   *
   * Fixed: Catch commit failure explicitly
   *
   * Recovery criteria:
   * 1. HTTP health probe succeeds
   * 2. Database heartbeat is recent (<60s)
   * 3. Session exists and is active
   *
   * @param {string} nodeId - Node identifier
   * @returns {Promise<boolean>} - True if recovered
   */
  async detectRecovery(nodeId) {
    // FIXED: Check shutdown flag
    if (this.isShuttingDown || !this.pool) {
      return false;
    }

    const client = await this.pool.connect();

    try {
      const maxAge = this.config.autoRecovery.verifyHeartbeatAge;

      await client.query('BEGIN');

      const { rows } = await client.query(`
        SELECT session_id, status, last_heartbeat,
               EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) * 1000 AS age_ms
        FROM orchestrator.sessions
        WHERE node_id = $1
          AND EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) * 1000 < $2
        ORDER BY last_heartbeat DESC
        LIMIT 1
        FOR UPDATE
      `, [nodeId, maxAge]);

      if (rows.length === 0) {
        await this.safeRollback(client);
        this.log(`No recent sessions for ${nodeId} - not recovered yet`);
        return false;
      }

      const session = rows[0];

      if (session.status === 'dead') {
        this.log(`Node ${nodeId} sending heartbeats but marked dead - resurrecting session ${session.session_id}`);

        await client.query(`
          UPDATE orchestrator.sessions
          SET status = 'active', last_heartbeat = NOW()
          WHERE session_id = $1
        `, [session.session_id]);

        // FIXED: Catch commit failure explicitly
        try {
          await client.query('COMMIT');
        } catch (commitErr) {
          this.log(`COMMIT failed for resurrection of ${session.session_id}: ${commitErr.message}`);
          return false;
        }

        this.log(`✅ Resurrected session ${session.session_id} on node ${nodeId}`);
        return true;
      }

      await client.query('COMMIT');
      return true;

    } catch (err) {
      await this.safeRollback(client);
      this.log(`Recovery detection failed for ${nodeId}: ${err.message}`);
      return false;
    } finally {
      client.release();
    }
  }

  /**
   * Resurrect a dead session (race condition safe)
   *
   * NOTE: This is now deprecated in favor of inline resurrection in detectRecovery()
   * Kept for backwards compatibility
   *
   * @param {string} sessionId - Session to resurrect
   * @param {string} nodeId - Node identifier
   * @returns {Promise<{resurrected: boolean, reason: string}>}
   */
  async resurrectSession(sessionId, nodeId) {
    if (this.isShuttingDown || !this.pool) {
      return { resurrected: false, reason: 'Shutting down' };
    }

    const client = await this.pool.connect();

    try {
      await client.query('BEGIN');

      const { rows } = await client.query(`
        SELECT status, last_heartbeat
        FROM orchestrator.sessions
        WHERE session_id = $1
        FOR UPDATE
      `, [sessionId]);

      if (rows.length === 0) {
        await this.safeRollback(client);
        this.log(`Session ${sessionId} does not exist - cannot resurrect`);
        return { resurrected: false, reason: 'Session not found' };
      }

      const session = rows[0];

      if (session.status !== 'dead') {
        await this.safeRollback(client);
        this.log(`Session ${sessionId} already resurrected (status=${session.status})`);
        return { resurrected: false, reason: `Already ${session.status}` };
      }

      await client.query(`
        UPDATE orchestrator.sessions
        SET status = 'active', last_heartbeat = NOW()
        WHERE session_id = $1
      `, [sessionId]);

      await client.query('COMMIT');
      this.log(`✅ Resurrected session ${sessionId} on node ${nodeId}`);
      return { resurrected: true, reason: 'Success' };

    } catch (err) {
      await this.safeRollback(client);
      this.log(`Failed to resurrect session ${sessionId}: ${err.message}`);
      return { resurrected: false, reason: err.message };
    } finally {
      client.release();
    }
  }

  /**
   * Safe ROLLBACK helper (catch errors on ROLLBACK itself)
   */
  async safeRollback(client) {
    try {
      await client.query('ROLLBACK');
    } catch (rollbackErr) {
      this.log(`ROLLBACK error (non-fatal): ${rollbackErr.message}`);
    }
  }

  /**
   * Verify node is healthy for re-adding to pool
   *
   * @param {string} nodeId - Node to verify
   * @returns {Promise<boolean>} - True if ready to re-add
   */
  async verifyNodeHealthy(nodeId) {
    if (!this.isRunning) {
      throw new Error('AutoRecovery not started');
    }

    if (this.isShuttingDown || !this.pool) {
      return false;
    }

    try {
      const { rows } = await this.pool.query(`
        SELECT COUNT(*) as count
        FROM orchestrator.sessions
        WHERE node_id = $1 AND status = 'active'
      `, [nodeId]);

      const activeSessionCount = parseInt(rows[0].count, 10);

      if (activeSessionCount === 0) {
        this.log(`Node ${nodeId} has no active sessions - cannot re-add`);
        return false;
      }

      const state = this.nodeStates.get(nodeId);
      if (!state) {
        this.log(`Unknown node ${nodeId} - cannot re-add`);
        return false;
      }

      if (state.status !== 'healthy') {
        this.log(`Node ${nodeId} not healthy (status=${state.status}) - cannot re-add`);
        return false;
      }

      this.log(`✅ Node ${nodeId} verified healthy - ready to re-add (${activeSessionCount} sessions)`);
      return true;

    } catch (err) {
      this.log(`Failed to verify node ${nodeId} for re-add: ${err.message}`);
      return false;
    }
  }

  /**
   * Reassign abandoned work from dead/failed nodes
   *
   * Fixed: Add status check to UPDATE WHERE clause to prevent reassigning completed work
   * Fixed: Move connect() inside try block to prevent connection leak
   *
   * @param {string} nodeId - Failed node (optional - if omitted, reassigns all abandoned work)
   * @returns {Promise<number>} - Number of tasks reassigned
   */
  async reassignAbandonedWork(nodeId = null) {
    if (this.isShuttingDown || !this.pool) {
      return 0;
    }

    let client;

    try {
      // FIXED: Move connect inside try block
      client = await this.pool.connect();

      await client.query('BEGIN');

      const sessionTimeout = new Date(Date.now() - this.config.autoRecovery.sessionTimeout);
      const batchSize = 1000;

      let query, params;

      if (nodeId) {
        // FIXED: Add status='assigned' to UPDATE WHERE clause
        query = `
          WITH target_work AS (
            SELECT work_id, work_version
            FROM orchestrator.work_queue
            WHERE status = 'assigned'
              AND (assigned_at < $1 OR assigned_to IN (
                SELECT session_id FROM orchestrator.sessions
                WHERE node_id = $2 AND status = 'dead'
              ))
            LIMIT $3
            FOR UPDATE SKIP LOCKED
          )
          UPDATE orchestrator.work_queue wq
          SET status = 'pending',
              assigned_to = NULL,
              work_version = wq.work_version + 1,
              assigned_at = NULL
          FROM target_work tw
          WHERE wq.work_id = tw.work_id
            AND wq.work_version = tw.work_version
            AND wq.status = 'assigned'
          RETURNING wq.work_id, wq.task_type
        `;
        params = [sessionTimeout, nodeId, batchSize];
      } else {
        // FIXED: Add status='assigned' to UPDATE WHERE clause
        query = `
          WITH target_work AS (
            SELECT work_id, work_version
            FROM orchestrator.work_queue
            WHERE status = 'assigned'
              AND (assigned_at < $1 OR assigned_to IN (
                SELECT session_id FROM orchestrator.sessions WHERE status = 'dead'
              ))
            LIMIT $2
            FOR UPDATE SKIP LOCKED
          )
          UPDATE orchestrator.work_queue wq
          SET status = 'pending',
              assigned_to = NULL,
              work_version = wq.work_version + 1,
              assigned_at = NULL
          FROM target_work tw
          WHERE wq.work_id = tw.work_id
            AND wq.work_version = tw.work_version
            AND wq.status = 'assigned'
          RETURNING wq.work_id, wq.task_type
        `;
        params = [sessionTimeout, batchSize];
      }

      const { rows } = await client.query(query, params);

      await client.query('COMMIT');

      const reassignedCount = rows.length;

      if (reassignedCount > 0) {
        const taskSummary = rows.slice(0, 10).map(r => `${r.work_id}(${r.task_type})`).join(', ');
        const remaining = reassignedCount > 10 ? ` ... and ${reassignedCount - 10} more` : '';

        this.log(`♻️ Reassigned ${reassignedCount} tasks from ${nodeId || 'failed nodes'}: ${taskSummary}${remaining}`);
      }

      return reassignedCount;

    } catch (err) {
      if (client) {
        await this.safeRollback(client);
      }
      this.log(`Failed to reassign abandoned work: ${err.message}`);
      throw err;
    } finally {
      if (client) {
        client.release();
      }
    }
  }

  /**
   * Get current recovery state for all nodes
   *
   * Fixed: Snapshot nodeStates to prevent concurrent modification during iteration
   */
  getRecoveryState() {
    if (!this.isRunning) {
      throw new Error('AutoRecovery not started');
    }

    // FIXED: Clone state snapshot
    const snapshot = new Map(this.nodeStates);
    const state = {};

    for (const [nodeId, nodeState] of snapshot.entries()) {
      state[nodeId] = {
        status: nodeState.status,
        circuitState: nodeState.circuitState,
        consecutiveFailures: nodeState.consecutiveFailures,
        lastProbe: nodeState.lastProbe,
        lastSuccess: nodeState.lastSuccess,
        backoffDelay: nodeState.backoffDelay
      };
    }
    return state;
  }

  /**
   * Get healthy nodes
   *
   * Fixed: Snapshot nodeStates to prevent concurrent modification during iteration
   */
  getHealthyNodes() {
    if (!this.isRunning) {
      throw new Error('AutoRecovery not started');
    }

    // FIXED: Clone state snapshot
    const snapshot = new Map(this.nodeStates);
    const healthy = [];

    for (const [nodeId, state] of snapshot.entries()) {
      if (state.status === 'healthy') {
        healthy.push({
          nodeId,
          host: state.host,
          port: state.port,
          lastSuccess: state.lastSuccess
        });
      }
    }
    return healthy;
  }

  /**
   * Get failed/degraded nodes
   *
   * Fixed: Snapshot nodeStates to prevent concurrent modification during iteration
   */
  getUnhealthyNodes() {
    if (!this.isRunning) {
      throw new Error('AutoRecovery not started');
    }

    // FIXED: Clone state snapshot
    const snapshot = new Map(this.nodeStates);
    const unhealthy = [];

    for (const [nodeId, state] of snapshot.entries()) {
      if (state.status === 'failed' || state.status === 'degraded') {
        unhealthy.push({
          nodeId,
          status: state.status,
          circuitState: state.circuitState,
          consecutiveFailures: state.consecutiveFailures,
          lastProbe: state.lastProbe
        });
      }
    }
    return unhealthy;
  }

  /**
   * Event handlers (override in subclass or via callbacks)
   */

  async onNodeDegraded(nodeId, reason) {
    if (this.isShuttingDown || !this.pool) {
      return;
    }

    try {
      const limitedReason = String(reason).substring(0, 500);

      await this.pool.query(`
        INSERT INTO monitoring.node_events (node_id, event_type, metadata)
        VALUES ($1, 'degraded', $2)
      `, [nodeId, JSON.stringify({ reason: limitedReason, timestamp: new Date().toISOString() })]);

      await this.pool.query(`
        UPDATE monitoring.node_health
        SET status = 'degraded', consecutive_failures = consecutive_failures + 1
        WHERE node_id = $1
      `, [nodeId]);
    } catch (err) {
      this.log(`Failed to record degraded event for ${nodeId}: ${err.message}`);
    }
  }

  /**
   * Fixed: Increment failureRetries BEFORE operations (off-by-one fix)
   */
  async onNodeFailed(nodeId, reason) {
    if (this.isShuttingDown || !this.pool) {
      return;
    }

    const state = this.nodeStates.get(nodeId);
    if (!state) return;

    // FIXED: Increment BEFORE operations to prevent off-by-one
    state.failureRetries++;

    if (state.failureRetries > this.maxFailureRetries) {
      this.log(`CRITICAL: onNodeFailed max retries (${this.maxFailureRetries}) reached for ${nodeId} - giving up`);
      return;
    }

    try {
      const limitedReason = String(reason).substring(0, 500);

      await this.pool.query(`
        INSERT INTO monitoring.node_events (node_id, event_type, metadata)
        VALUES ($1, 'node_down', $2)
      `, [nodeId, JSON.stringify({ reason: limitedReason, timestamp: new Date().toISOString() })]);

      await this.pool.query(`
        UPDATE monitoring.node_health
        SET status = 'failed',
            circuit_state = 'open',
            failure_count = failure_count + 1,
            consecutive_failures = consecutive_failures + 1,
            last_failure = NOW()
        WHERE node_id = $1
      `, [nodeId]);

      await this.pool.query(`
        UPDATE orchestrator.sessions
        SET status = 'dead'
        WHERE node_id = $1 AND status = 'active'
      `, [nodeId]);

      await this.reassignAbandonedWork(nodeId);

    } catch (err) {
      this.log(`CRITICAL: Failed to handle node failure for ${nodeId} (attempt ${state.failureRetries}/${this.maxFailureRetries}): ${err.message}`);
    }
  }

  async onNodeRecovered(nodeId) {
    if (this.isShuttingDown || !this.pool) {
      return;
    }

    try {
      await this.pool.query(`
        INSERT INTO monitoring.node_events (node_id, event_type, metadata)
        VALUES ($1, 'recovered', $2)
      `, [nodeId, JSON.stringify({ timestamp: new Date().toISOString() })]);

      await this.pool.query(`
        UPDATE monitoring.node_health
        SET status = 'healthy',
            circuit_state = 'closed',
            consecutive_failures = 0,
            last_recovery = NOW()
        WHERE node_id = $1
      `, [nodeId]);

    } catch (err) {
      this.log(`Failed to record recovery event for ${nodeId}: ${err.message}`);
    }
  }

  /**
   * Logging
   */
  log(message) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [AutoRecovery] ${message}`);
  }
}

/**
 * Standalone CLI for testing
 *
 * Fixed: Await recovery.stop() before exit
 */
if (import.meta.url === `file://${process.argv[1]}`) {
  const recovery = new AutoRecovery();

  process.on('SIGINT', async () => {
    console.log('\nStopping auto-recovery...');
    await recovery.stop();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    await recovery.stop();
    process.exit(0);
  });

  // FIXED: Await stop() before exit
  process.on('uncaughtException', async (err) => {
    console.error(`[AutoRecovery] Uncaught exception: ${err.message}`);
    console.error(err.stack);
    await recovery.stop().catch(e => console.error('Stop failed:', e.message));
    process.exit(1);
  });

  process.on('unhandledRejection', async (reason, promise) => {
    console.error(`[AutoRecovery] Unhandled rejection at:`, promise, 'reason:', reason);
    await recovery.stop().catch(e => console.error('Stop failed:', e.message));
    process.exit(1);
  });

  (async () => {
    try {
      await recovery.start();

      setInterval(() => {
        const state = recovery.getRecoveryState();
        console.log('\n=== Recovery State ===');
        for (const [nodeId, nodeState] of Object.entries(state)) {
          console.log(`${nodeId}: ${nodeState.status} (failures=${nodeState.consecutiveFailures}, circuit=${nodeState.circuitState})`);
        }
        console.log('=====================\n');
      }, 30000);

    } catch (err) {
      console.error(`Failed to start auto-recovery: ${err.message}`);
      process.exit(1);
    }
  })();
}

export default AutoRecovery;
