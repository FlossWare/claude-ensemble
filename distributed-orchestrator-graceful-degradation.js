#!/usr/bin/env node
// Distributed Session Orchestrator - Graceful Degradation Enhancement
// Handles node failures, work redistribution, and minimum viable fleet

const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const crypto = require('crypto');
const { execSync } = require('child_process');
const { Pool } = require('pg');

const SessionRegistry = require('./session-registry');
const SessionMessenger = require('./session-messenger');

const ORCHESTRATOR_DIR = path.join(os.homedir(), '.claude', 'orchestrator');
const CONFIG_FILE = path.join(ORCHESTRATOR_DIR, 'distributed-config.json');
const STATE_DB = path.join(ORCHESTRATOR_DIR, 'distributed-state.db');

// Default configuration
const DEFAULT_CONFIG = {
  mode: 'distributed',
  nodeId: os.hostname(),

  // Fleet nodes
  fleet: [
    { id: 'aio-01', host: 'aio-01', port: 7340 },
    { id: 'server-01', host: 'server-01', port: 7340 },
    { id: 'server-02', host: 'server-02', port: 7340 },
    { id: 'server-03', host: 'server-03', port: 7340 }
  ],

  // This node's HTTP API
  api: {
    enabled: true,
    port: 7340,
    host: '127.0.0.1'
  },

  // State backend
  state: {
    backend: 'postgresql',
    postgresql: {
      host: '/var/run/postgresql',
      database: 'learning',
      user: process.env.USER || 'sfloess',
      max: 5,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000
    },
    sqlite: {
      path: STATE_DB,
      wal: true
    },
    redis: {
      host: 'localhost',
      port: 6379,
      db: 0
    }
  },

  // Graceful degradation settings
  degradation: {
    suspectedThreshold: 45000,
    sessionTimeout: 120000,
    workTimeout: 3600000,
    retryLimit: 3,
    minimumViableFleet: 1,
    redistributionInterval: 10000,
    fleetScaleUpMultiplier: 2,
    maxDeadNodesHistory: 1000,
    maxSuspectedNodesHistory: 1000,
    maxFailedBroadcasts: 1000,
    maxBroadcastRetries: 5,
    broadcastTTL: 300000,
    suspectedNodeGracePeriod: 10000
  },

  // Heartbeat and timeouts
  heartbeatInterval: 30000,
  sessionTimeout: 120000,
  workTimeout: 3600000,

  // Circuit breaker
  circuitBreaker: {
    failureThreshold: 3,
    resetTimeout: 60000
  },

  // Work distribution
  workStealing: true,
  loadBalancing: 'least-busy',

  // Conflict detection
  conflictDetection: true,
  autoResolveConflicts: false
};

class DistributedOrchestrator {
  constructor(configPath = CONFIG_FILE) {
    this.config = this.loadConfig(configPath);
    this.nodeId = this.config.nodeId;
    this.sessionId = `${this.nodeId}-${process.pid}-${Date.now()}`;
    this.pool = null;
    this.state = this.initializeState();
    this.registry = new SessionRegistry();
    this.messenger = new SessionMessenger('orchestrator');
    this.httpServer = null;
    this.circuitBreakerState = { failures: 0, open: false, openedAt: null };
    this.heartbeatTimeout = null;
    this.interval = null;
    this.heartbeatCounter = 0;
    this.degradationCheckInProgress = false;
    this.heartbeatInProgress = false;
    this.shuttingDown = false;
    this.degradedMode = false;
    this.failedBroadcasts = [];

    // Graceful degradation stats
    this.degradationStats = {
      tasksRedistributed: 0,
      nodesFailed: 0,
      tasksExhaustedRetries: 0,
      suspectedNodes: new Map(),
      deadNodes: new Map(),
      lastRedistribution: null
    };

    this.ensureDirectories();
  }

  loadConfig(configPath) {
    if (fs.existsSync(configPath)) {
      const userConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      let config = { ...DEFAULT_CONFIG, ...userConfig };

      // Fixed: Enforce minimum failureThreshold >= 2 to allow at least one retry
      if (config.circuitBreaker.failureThreshold < 2) {
        console.warn(`WARNING: circuitBreaker.failureThreshold must be >= 2 (allows one retry before opening), adjusting from ${config.circuitBreaker.failureThreshold} to 2`);
        config.circuitBreaker.failureThreshold = 2;
      }

      // Fixed: Allow localhost for development/testing with env var override
      const localhostNodes = config.fleet.filter(n =>
        n.host === 'localhost' || n.host === '127.0.0.1'
      );
      if (localhostNodes.length > 0 && !process.env.ORCHESTRATOR_ALLOW_LOCALHOST) {
        throw new Error(`Fleet contains localhost nodes: ${localhostNodes.map(n => n.id).join(', ')}. These are not reachable from other nodes. Use actual hostnames or set ORCHESTRATOR_ALLOW_LOCALHOST=1 for testing.`);
      }

      return config;
    }
    return DEFAULT_CONFIG;
  }

  saveConfig() {
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(this.config, null, 2), 'utf8');
  }

  ensureDirectories() {
    if (!fs.existsSync(ORCHESTRATOR_DIR)) {
      fs.mkdirSync(ORCHESTRATOR_DIR, { recursive: true });
    }
  }

  initializeState() {
    const backend = this.config.state.backend;

    switch (backend) {
      case 'postgresql':
        return this.initializePostgreSQL();
      case 'sqlite':
        return this.initializeSQLite();
      case 'redis':
        return this.initializeRedis();
      default:
        return this.initializeFileState();
    }
  }

  initializePostgreSQL() {
    this.pool = new Pool(this.config.state.postgresql);

    this.pool.on('error', (err) => {
      // Fixed: Ignore pool errors when circuit is already open to prevent counter inflation
      if (this.circuitBreakerState.open) {
        this.log(`PostgreSQL connection error (circuit open, ignoring): ${err.message}`);
        return;
      }

      this.log(`PostgreSQL connection error: ${err.message}`);
      this.circuitBreakerState.failures = Math.min(
        this.circuitBreakerState.failures + 1,
        this.config.circuitBreaker.failureThreshold + 1
      );
      if (this.circuitBreakerState.failures >= this.config.circuitBreaker.failureThreshold) {
        this.openCircuitBreaker();
      }
    });

    this.ensureGracefulDegradationSchema();

    return {
      type: 'postgresql',
      pool: this.pool
    };
  }

  async ensureGracefulDegradationSchema() {
    if (!this.pool) return;

    // Fixed: Wrap advisory lock acquisition in try/finally with unconditional unlock
    let lockAcquired = false;
    try {
      const lockResult = await this.pool.query(`SELECT pg_try_advisory_lock(hashtext('schema_init')) as acquired`);
      lockAcquired = lockResult.rows[0]?.acquired;

      if (!lockAcquired) {
        this.log('Another orchestrator is initializing schema, waiting...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        return;
      }

      await this.pool.query('BEGIN');

      try {
        await this.pool.query(`
          CREATE TABLE IF NOT EXISTS orchestrator.schema_version (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            applied_at TIMESTAMPTZ DEFAULT NOW()
          );
        `);

        const versionResult = await this.pool.query(`
          SELECT version FROM orchestrator.schema_version
          WHERE component = 'graceful_degradation'
          FOR UPDATE
        `);

        const currentVersion = versionResult.rows.length > 0 ? versionResult.rows[0].version : 0;
        const targetVersion = 2;

        if (currentVersion < targetVersion) {
          await this.pool.query(`
            DO $$ BEGIN
              CREATE TYPE orchestrator.session_health_state AS ENUM ('active', 'suspected', 'dead');
            EXCEPTION
              WHEN duplicate_object THEN null;
            END $$;

            ALTER TABLE orchestrator.sessions
              ADD COLUMN IF NOT EXISTS health_state orchestrator.session_health_state DEFAULT 'active',
              ADD COLUMN IF NOT EXISTS suspected_at TIMESTAMPTZ;

            ALTER TABLE orchestrator.work_queue
              ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
              ADD COLUMN IF NOT EXISTS retry_limit INTEGER DEFAULT 3,
              ADD COLUMN IF NOT EXISTS last_failure_reason TEXT;

            CREATE TABLE IF NOT EXISTS orchestrator.dead_letter_queue (
              work_id TEXT PRIMARY KEY,
              task_type TEXT,
              failure_reason TEXT,
              failed_at TIMESTAMPTZ DEFAULT NOW(),
              original_payload JSONB
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_health_state
              ON orchestrator.sessions(health_state, last_heartbeat);

            CREATE INDEX IF NOT EXISTS idx_work_retry
              ON orchestrator.work_queue(retry_count, retry_limit, status);
          `);

          await this.pool.query(`
            INSERT INTO orchestrator.schema_version (component, version)
            VALUES ('graceful_degradation', $1)
            ON CONFLICT (component) DO UPDATE SET
              version = $1,
              applied_at = NOW()
          `, [targetVersion]);

          this.log('Graceful degradation schema initialized');
        }

        await this.pool.query('COMMIT');
      } catch (err) {
        await this.pool.query('ROLLBACK');
        throw err;
      }
    } catch (err) {
      this.log(`Schema initialization warning: ${err.message}`);
    } finally {
      // Fixed: Unconditionally release lock in finally block
      if (lockAcquired) {
        try {
          await this.pool.query(`SELECT pg_advisory_unlock(hashtext('schema_init'))`);
        } catch (err) {
          this.log(`Failed to release schema_init lock: ${err.message}`);
        }
      }
    }
  }

  openCircuitBreaker() {
    this.circuitBreakerState.open = true;
    this.circuitBreakerState.openedAt = Date.now();
    this.log(`Circuit breaker OPEN - PostgreSQL unreachable, entering local-only mode`);

    setTimeout(() => {
      this.log(`Circuit breaker half-open - retrying PostgreSQL`);
      this.circuitBreakerState.open = false;
      this.circuitBreakerState.failures = 0;
    }, this.config.circuitBreaker.resetTimeout);
  }

  async executeQuery(sql, params = []) {
    if (this.shuttingDown) {
      this.log('Query skipped - orchestrator shutting down');
      return [];
    }

    if (!this.pool) {
      throw new Error('PostgreSQL pool not initialized - backend may be SQLite or file-based');
    }

    if (this.circuitBreakerState.open) {
      throw new Error('Circuit breaker open - PostgreSQL unavailable');
    }

    try {
      const result = await this.pool.query(sql, params);
      this.circuitBreakerState.failures = 0;
      if (this.circuitBreakerState.open) {
        this.log('Circuit breaker closed - PostgreSQL recovered');
        this.circuitBreakerState.open = false;
      }
      return result.rows;
    } catch (err) {
      this.circuitBreakerState.failures = Math.min(
        this.circuitBreakerState.failures + 1,
        this.config.circuitBreaker.failureThreshold + 1
      );
      if (this.circuitBreakerState.failures >= this.config.circuitBreaker.failureThreshold) {
        this.openCircuitBreaker();
      }
      this.log(`Query failed: ${err.message}`);
      throw err;
    }
  }

  async registerSession() {
    await this.executeQuery(`
      INSERT INTO orchestrator.sessions (session_id, node_id, status, health_state)
      VALUES ($1, $2, 'active', 'active')
      ON CONFLICT (session_id) DO UPDATE SET
        last_heartbeat = NOW(),
        status = 'active',
        health_state = 'active',
        suspected_at = NULL
    `, [this.sessionId, this.nodeId]);
  }

  async heartbeat() {
    if (this.shuttingDown) return;

    // Fixed: Prevent concurrent heartbeats with flag
    if (this.heartbeatInProgress) {
      this.log('WARNING: Previous heartbeat still running, skipping');
      return;
    }

    this.heartbeatInProgress = true;

    try {
      await this.executeQuery(`
        UPDATE orchestrator.sessions
        SET last_heartbeat = NOW(), status = 'active', health_state = 'active', suspected_at = NULL
        WHERE session_id = $1
      `, [this.sessionId]);

      this.heartbeatCounter++;

      if (this.failedBroadcasts.length > 0) {
        await this.retryFailedBroadcasts();
      }

      // Fixed: Wrap degradation check in try/finally inside runDegradationChecks
      if (this.heartbeatCounter % 10 === 0 && !this.degradationCheckInProgress) {
        this.runDegradationChecks()
          .catch(err => this.log(`Degradation check error: ${err.message}`));
      }
    } catch (err) {
      this.log(`Heartbeat failed: ${err.message}`);
    } finally {
      this.heartbeatInProgress = false;
    }
  }

  async retryFailedBroadcasts() {
    const now = Date.now();
    const toRetry = this.failedBroadcasts.splice(0, 10);
    if (toRetry.length === 0) return;

    this.log(`Retrying ${toRetry.length} failed broadcasts`);

    const results = await Promise.allSettled(
      toRetry.map(broadcast =>
        this.httpPost(broadcast.node.host, broadcast.node.port, '/sessions', broadcast.data)
      )
    );

    // Fixed: Track retry attempts and TTL, discard exhausted broadcasts
    const stillFailed = results
      .map((r, i) => {
        if (r.status === 'rejected') {
          const broadcast = toRetry[i];
          broadcast.retryCount = (broadcast.retryCount || 0) + 1;
          broadcast.firstFailedAt = broadcast.firstFailedAt || now;

          if (broadcast.retryCount >= this.config.degradation.maxBroadcastRetries) {
            this.log(`Broadcast to ${broadcast.node?.id} exhausted retries (${broadcast.retryCount}), discarding`);
            return null;
          }

          if (now - broadcast.firstFailedAt > this.config.degradation.broadcastTTL) {
            this.log(`Broadcast to ${broadcast.node?.id} expired (TTL ${this.config.degradation.broadcastTTL}ms), discarding`);
            return null;
          }

          return broadcast;
        }
        return null;
      })
      .filter(b => b !== null);

    if (stillFailed.length > 0) {
      // Fixed: Cap failedBroadcasts array size
      if (this.failedBroadcasts.length + stillFailed.length > this.config.degradation.maxFailedBroadcasts) {
        const excess = (this.failedBroadcasts.length + stillFailed.length) - this.config.degradation.maxFailedBroadcasts;
        this.log(`Dropping ${excess} oldest failed broadcasts to prevent memory leak`);
        this.failedBroadcasts.splice(0, excess);
      }
      this.failedBroadcasts.push(...stillFailed);
      this.log(`${stillFailed.length} broadcasts still failing`);
    }
  }

  pruneNodeHistory() {
    // Fixed: Prune by age if over limit, else prune oldest entries regardless of age
    if (this.degradationStats.deadNodes.size > this.config.degradation.maxDeadNodesHistory) {
      const entries = Array.from(this.degradationStats.deadNodes.entries());
      const excessCount = this.degradationStats.deadNodes.size - this.config.degradation.maxDeadNodesHistory;
      const sorted = entries.sort((a, b) => a[1] - b[1]);
      const toRemove = sorted.slice(0, excessCount);

      toRemove.forEach(([nodeId]) => this.degradationStats.deadNodes.delete(nodeId));
      if (toRemove.length > 0) {
        this.log(`Pruned ${toRemove.length} old entries from deadNodes history`);
      }
    }

    if (this.degradationStats.suspectedNodes.size > this.config.degradation.maxSuspectedNodesHistory) {
      const entries = Array.from(this.degradationStats.suspectedNodes.entries());
      const excessCount = this.degradationStats.suspectedNodes.size - this.config.degradation.maxSuspectedNodesHistory;
      const sorted = entries.sort((a, b) => a[1] - b[1]);
      const toRemove = sorted.slice(0, excessCount);

      toRemove.forEach(([nodeId]) => this.degradationStats.suspectedNodes.delete(nodeId));
      if (toRemove.length > 0) {
        this.log(`Pruned ${toRemove.length} old entries from suspectedNodes history`);
      }
    }
  }

  async detectFailedNodes() {
    const deadThreshold = this.config.degradation.sessionTimeout;

    try {
      // Fixed: Exclude self from dead node detection
      const rows = await this.executeQuery(`
        WITH newly_dead AS (
          SELECT session_id, node_id
          FROM orchestrator.sessions
          WHERE last_heartbeat < NOW() - INTERVAL '${deadThreshold} milliseconds'
            AND status != 'dead'
            AND session_id != $1
          FOR UPDATE SKIP LOCKED
        )
        UPDATE orchestrator.sessions s
        SET status = 'dead', health_state = 'dead'
        FROM newly_dead
        WHERE s.session_id = newly_dead.session_id
        RETURNING s.session_id, s.node_id
      `, [this.sessionId]);

      for (const row of rows) {
        this.log(`Node ${row.node_id} (session ${row.session_id}) marked as DEAD`);
        this.degradationStats.nodesFailed++;
        this.degradationStats.deadNodes.set(row.node_id, Date.now());
        this.degradationStats.suspectedNodes.delete(row.node_id);
      }

      this.pruneNodeHistory();

      return rows;
    } catch (err) {
      this.log(`detectFailedNodes error: ${err.message}`);
      return [];
    }
  }

  async markSuspectedNodes() {
    const suspectedThreshold = this.config.degradation.suspectedThreshold;

    try {
      const rows = await this.executeQuery(`
        WITH newly_suspected AS (
          SELECT session_id, node_id
          FROM orchestrator.sessions
          WHERE last_heartbeat < NOW() - INTERVAL '${suspectedThreshold} milliseconds'
            AND last_heartbeat >= NOW() - INTERVAL '${this.config.degradation.sessionTimeout} milliseconds'
            AND health_state = 'active'
          FOR UPDATE SKIP LOCKED
        )
        UPDATE orchestrator.sessions s
        SET health_state = 'suspected', suspected_at = COALESCE(s.suspected_at, NOW())
        FROM newly_suspected
        WHERE s.session_id = newly_suspected.session_id
        RETURNING s.session_id, s.node_id
      `);

      for (const row of rows) {
        this.log(`Node ${row.node_id} (session ${row.session_id}) marked as SUSPECTED`);
        this.degradationStats.suspectedNodes.set(row.node_id, Date.now());
      }

      return rows;
    } catch (err) {
      this.log(`markSuspectedNodes error: ${err.message}`);
      return [];
    }
  }

  async redistributeWork() {
    try {
      // Fixed: Add assigned_to IS NOT NULL check for mutual exclusion with timeoutStuckWork
      const rows = await this.executeQuery(`
        WITH dead_sessions AS (
          SELECT session_id FROM orchestrator.sessions WHERE status = 'dead'
        ),
        tasks_to_redistribute AS (
          SELECT work_id FROM orchestrator.work_queue
          WHERE assigned_to IN (SELECT session_id FROM dead_sessions)
            AND status = 'assigned'
            AND assigned_to IS NOT NULL
            AND retry_count < retry_limit
          FOR UPDATE SKIP LOCKED
        )
        UPDATE orchestrator.work_queue
        SET
          status = 'pending',
          assigned_to = NULL,
          retry_count = retry_count + 1,
          last_failure_reason = 'Node failure - session dead'
        FROM tasks_to_redistribute
        WHERE orchestrator.work_queue.work_id = tasks_to_redistribute.work_id
        RETURNING orchestrator.work_queue.work_id, orchestrator.work_queue.task_type, orchestrator.work_queue.retry_count
      `);

      if (rows.length > 0) {
        this.log(`Redistributed ${rows.length} tasks from dead nodes`);
        this.degradationStats.tasksRedistributed += rows.length;
        this.degradationStats.lastRedistribution = new Date();

        for (const row of rows) {
          this.log(`  - Task ${row.work_id} (${row.task_type}) retry ${row.retry_count}/${this.config.degradation.retryLimit}`);
        }
      }

      return rows;
    } catch (err) {
      this.log(`redistributeWork error: ${err.message}`);
      return [];
    }
  }

  async timeoutStuckWork() {
    const workTimeout = this.config.degradation.workTimeout;

    try {
      // Fixed: Add assigned_to IS NOT NULL check for mutual exclusion
      const rows = await this.executeQuery(`
        WITH stuck_tasks AS (
          SELECT work_id, assigned_at
          FROM orchestrator.work_queue
          WHERE status = 'assigned'
            AND assigned_to IS NOT NULL
            AND assigned_at < NOW() - INTERVAL '${workTimeout} milliseconds'
            AND retry_count < retry_limit
          FOR UPDATE SKIP LOCKED
        )
        UPDATE orchestrator.work_queue
        SET
          status = 'pending',
          assigned_to = NULL,
          retry_count = retry_count + 1,
          last_failure_reason = 'Work timeout - task stuck'
        FROM stuck_tasks
        WHERE orchestrator.work_queue.work_id = stuck_tasks.work_id
        RETURNING orchestrator.work_queue.work_id, orchestrator.work_queue.task_type,
                  orchestrator.work_queue.retry_count, stuck_tasks.assigned_at
      `);

      if (rows.length > 0) {
        this.log(`Timed out ${rows.length} stuck tasks`);
        for (const row of rows) {
          const age = Date.now() - new Date(row.assigned_at).getTime();
          this.log(`  - Task ${row.work_id} stuck for ${Math.round(age / 1000)}s, retry ${row.retry_count}/${this.config.degradation.retryLimit}`);
        }
      }

      return rows;
    } catch (err) {
      this.log(`timeoutStuckWork error: ${err.message}`);
      return [];
    }
  }

  async failExhaustedRetries() {
    try {
      // Fixed: Add status check in UPDATE for idempotency
      const rows = await this.executeQuery(`
        WITH exhausted_tasks AS (
          SELECT work_id, task_type, task_payload, last_failure_reason
          FROM orchestrator.work_queue
          WHERE retry_count >= retry_limit
            AND status != 'failed'
          FOR UPDATE SKIP LOCKED
        )
        INSERT INTO orchestrator.dead_letter_queue (work_id, task_type, failure_reason, original_payload)
        SELECT work_id, task_type,
               COALESCE(last_failure_reason, 'Retry limit exhausted'),
               task_payload::jsonb
        FROM exhausted_tasks
        ON CONFLICT (work_id) DO NOTHING
        RETURNING work_id, task_type, failure_reason
      `);

      if (rows.length > 0) {
        await this.executeQuery(`
          UPDATE orchestrator.work_queue
          SET
            status = 'failed',
            last_failure_reason = COALESCE(last_failure_reason, 'Retry limit exhausted')
          WHERE work_id = ANY($1)
            AND status != 'failed'
        `, [rows.map(r => r.work_id)]);

        this.log(`Failed ${rows.length} tasks due to retry exhaustion`);
        this.degradationStats.tasksExhaustedRetries += rows.length;

        for (const row of rows) {
          this.log(`  - Task ${row.work_id} (${row.task_type}) moved to dead letter queue: ${row.failure_reason}`);
        }
      }

      return rows;
    } catch (err) {
      this.log(`failExhaustedRetries error: ${err.message}`);
      return [];
    }
  }

  async runDegradationChecks() {
    if (this.shuttingDown) return;

    // Fixed: Move degradationCheckInProgress flag inside this method with try/finally
    if (this.degradationCheckInProgress) {
      this.log('Degradation check already in progress, skipping');
      return;
    }

    this.degradationCheckInProgress = true;

    let lockAcquired = false;
    try {
      const lockResult = await this.executeQuery(`
        SELECT pg_try_advisory_lock(hashtext('degradation_check')) as acquired
      `);

      lockAcquired = lockResult[0]?.acquired;

      if (!lockAcquired) {
        this.log('Another orchestrator is running degradation checks, skipping');
        return;
      }

      this.log('Running graceful degradation checks...');

      const failedNodes = await this.detectFailedNodes();
      await this.markSuspectedNodes();

      if (failedNodes.length > 0) {
        await this.redistributeWork();
      }

      await this.timeoutStuckWork();
      await this.failExhaustedRetries();
      await this.checkMinimumViableFleet();

      const deadThreshold = this.config.degradation.sessionTimeout;
      await this.executeQuery(`
        UPDATE orchestrator.sessions
        SET health_state = 'dead', status = 'dead'
        WHERE health_state = 'suspected'
          AND last_heartbeat < NOW() - INTERVAL '${deadThreshold} milliseconds'
      `);
    } catch (err) {
      this.log(`runDegradationChecks error: ${err.message}`);
    } finally {
      if (lockAcquired) {
        try {
          await this.executeQuery(`SELECT pg_advisory_unlock(hashtext('degradation_check'))`);
        } catch (err) {
          this.log(`Failed to release degradation_check lock: ${err.message}`);
        }
      }
      this.degradationCheckInProgress = false;
    }
  }

  async checkMinimumViableFleet() {
    try {
      const activeNodes = await this.executeQuery(`
        SELECT COUNT(DISTINCT node_id) as count
        FROM orchestrator.sessions
        WHERE health_state = 'active'
      `);

      const activeCount = parseInt(activeNodes[0]?.count || 0);
      const totalFleet = this.config.fleet.length;

      if (activeCount < this.config.degradation.minimumViableFleet) {
        this.log(`CRITICAL: Fleet below minimum viable (${activeCount}/${this.config.degradation.minimumViableFleet})`);
        this.log('MANUAL INTERVENTION REQUIRED: Scale up fleet capacity or increase worker concurrency');
      } else if (activeCount < totalFleet / 2) {
        this.log(`WARNING: Fleet capacity reduced (${activeCount}/${totalFleet} nodes active)`);
        this.log('MANUAL INTERVENTION REQUIRED: Consider scaling up fleet or increasing worker concurrency');
      } else {
        this.log(`Fleet healthy: ${activeCount}/${totalFleet} nodes active`);
      }

      return activeCount;
    } catch (err) {
      this.log(`checkMinimumViableFleet error: ${err.message}`);
      return 0;
    }
  }

  async assignWork() {
    const rows = await this.executeQuery(`
      WITH next_work AS (
        SELECT work_id, retry_count, retry_limit FROM orchestrator.work_queue
        WHERE status = 'pending'
          AND retry_count < retry_limit
        ORDER BY priority DESC, enqueued_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
      )
      UPDATE orchestrator.work_queue wq
      SET status = 'assigned', assigned_to = $1, assigned_at = NOW()
      FROM next_work
      WHERE wq.work_id = next_work.work_id
        AND wq.retry_count = next_work.retry_count
        AND next_work.retry_count < next_work.retry_limit
      RETURNING wq.*;
    `, [this.sessionId]);

    return rows[0] || null;
  }

  async selectNode(taskType) {
    // Fixed: Filter suspected nodes near sessionTimeout threshold
    const gracePeriod = this.config.degradation.suspectedNodeGracePeriod;

    let nodes = await this.executeQuery(`
      SELECT np.node_id, np.alpha, np.beta, np.total_assigned, s.health_state
      FROM orchestrator.node_performance np
      JOIN orchestrator.sessions s ON np.node_id = s.node_id
      WHERE np.task_type = $1
        AND s.health_state = 'active'
    `, [taskType]);

    if (nodes.length === 0) {
      this.log('WARNING: No active nodes, falling back to suspected nodes');
      nodes = await this.executeQuery(`
        SELECT np.node_id, np.alpha, np.beta, np.total_assigned, s.health_state, s.suspected_at
        FROM orchestrator.node_performance np
        JOIN orchestrator.sessions s ON np.node_id = s.node_id
        WHERE np.task_type = $1
          AND s.health_state = 'suspected'
          AND s.suspected_at < NOW() - INTERVAL '${gracePeriod} milliseconds'
      `, [taskType]);
    }

    if (nodes.length === 0) {
      const availableNodes = await this.executeQuery(`
        SELECT DISTINCT node_id, health_state, suspected_at
        FROM orchestrator.sessions
        WHERE health_state = 'active'
           OR (health_state = 'suspected' AND suspected_at < NOW() - INTERVAL '${gracePeriod} milliseconds')
      `);

      if (availableNodes.length === 0) {
        this.log('CRITICAL: No viable nodes available (all dead)');
        throw new Error('No viable nodes available for task assignment');
      }

      const randomIndex = Math.floor(Math.random() * availableNodes.length);
      const selected = availableNodes[randomIndex];
      return { nodeId: selected.node_id, healthState: selected.health_state };
    }

    // Fixed: Handle division by zero in Thompson Sampling with Bayesian prior
    let bestNode = null;
    let bestSample = -1;

    for (const node of nodes) {
      const alpha = Math.max(1, (node.alpha || 0) + 1);
      const beta = Math.max(1, (node.beta || 0) + 1);
      const sample = alpha / (alpha + beta) + (Math.random() * 0.1);
      if (sample > bestSample) {
        bestSample = sample;
        bestNode = node;
      }
    }

    return { nodeId: bestNode.node_id, healthState: bestNode.health_state };
  }

  async updateNodePerformance(nodeId, taskType, success, durationMs) {
    const reward = success ? (1.0 - Math.min(durationMs / 60000, 1.0)) : 0.0;

    // Fixed: Change condition to <= 0 for division by zero check
    await this.executeQuery(`
      INSERT INTO orchestrator.node_performance
      (node_id, task_type, alpha, beta, total_assigned, total_completed, total_failed, avg_duration_ms, avg_reward)
      VALUES ($1, $2, $3, $4, 1, $5, $6, $7, $8)
      ON CONFLICT (node_id, task_type) DO UPDATE SET
        alpha = orchestrator.node_performance.alpha + $3,
        beta = orchestrator.node_performance.beta + $4,
        total_assigned = orchestrator.node_performance.total_assigned + 1,
        total_completed = orchestrator.node_performance.total_completed + $5,
        total_failed = orchestrator.node_performance.total_failed + $6,
        avg_duration_ms = CASE
          WHEN COALESCE(orchestrator.node_performance.total_assigned, 0) <= 0 THEN $7
          ELSE (orchestrator.node_performance.avg_duration_ms * orchestrator.node_performance.total_assigned + $7) / (orchestrator.node_performance.total_assigned + 1)
        END,
        avg_reward = CASE
          WHEN COALESCE(orchestrator.node_performance.total_assigned, 0) <= 0 THEN $8
          ELSE (orchestrator.node_performance.avg_reward * orchestrator.node_performance.total_assigned + $8) / (orchestrator.node_performance.total_assigned + 1)
        END,
        last_assigned = NOW()
    `, [
      nodeId, taskType,
      success ? 1 : 0,
      success ? 0 : 1,
      success ? 1 : 0,
      success ? 0 : 1,
      durationMs,
      reward
    ]);
  }

  async getStats() {
    try {
      const sessions = await this.executeQuery(`
        SELECT
          COUNT(*) FILTER (WHERE health_state = 'active') as active,
          COUNT(*) FILTER (WHERE health_state = 'suspected') as suspected,
          COUNT(*) FILTER (WHERE health_state = 'dead') as dead
        FROM orchestrator.sessions
      `);

      const work = await this.executeQuery(`
        SELECT
          COUNT(*) FILTER (WHERE status = 'pending') as pending,
          COUNT(*) FILTER (WHERE status = 'assigned') as assigned,
          COUNT(*) FILTER (WHERE status = 'completed') as completed,
          COUNT(*) FILTER (WHERE status = 'failed') as failed,
          COUNT(*) FILTER (WHERE retry_count >= retry_limit) as exhausted
        FROM orchestrator.work_queue
      `);

      // Fixed: Return timestamps with node IDs for debugging
      return {
        sessions: sessions[0],
        work: work[0],
        degradation: {
          tasksRedistributed: this.degradationStats.tasksRedistributed,
          nodesFailed: this.degradationStats.nodesFailed,
          tasksExhaustedRetries: this.degradationStats.tasksExhaustedRetries,
          suspectedNodes: Array.from(this.degradationStats.suspectedNodes.entries()).map(([id, ts]) => ({ nodeId: id, timestamp: ts })),
          deadNodes: Array.from(this.degradationStats.deadNodes.entries()).map(([id, ts]) => ({ nodeId: id, timestamp: ts })),
          lastRedistribution: this.degradationStats.lastRedistribution
        }
      };
    } catch (err) {
      this.log(`getStats error: ${err.message}`);
      return { error: err.message };
    }
  }

  initializeSQLite() {
    const Database = require('better-sqlite3');
    const db = new Database(this.config.state.sqlite.path);

    if (this.config.state.sqlite.wal) {
      db.pragma('journal_mode = WAL');
    }

    db.exec(`
      CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL,
        pid INTEGER NOT NULL,
        cwd TEXT,
        working_on TEXT,
        files_locked TEXT,
        status TEXT DEFAULT 'active',
        health_state TEXT DEFAULT 'active',
        suspected_at TEXT,
        started_at TEXT NOT NULL,
        last_heartbeat TEXT NOT NULL,
        metadata TEXT
      );

      CREATE TABLE IF NOT EXISTS work_queue (
        work_id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        files TEXT,
        priority TEXT DEFAULT 'normal',
        status TEXT DEFAULT 'queued',
        assigned_to_session TEXT,
        assigned_to_node TEXT,
        retry_count INTEGER DEFAULT 0,
        retry_limit INTEGER DEFAULT 3,
        last_failure_reason TEXT,
        enqueued_at TEXT NOT NULL,
        assigned_at TEXT,
        completed_at TEXT,
        result TEXT,
        metadata TEXT
      );

      CREATE TABLE IF NOT EXISTS messages (
        message_id TEXT PRIMARY KEY,
        from_session TEXT NOT NULL,
        from_node TEXT NOT NULL,
        to_session TEXT NOT NULL,
        to_node TEXT,
        type TEXT NOT NULL,
        priority TEXT DEFAULT 'normal',
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        delivered_at TEXT,
        read_at TEXT,
        expires_at TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_sessions_node ON sessions(node_id);
      CREATE INDEX IF NOT EXISTS idx_sessions_heartbeat ON sessions(last_heartbeat);
      CREATE INDEX IF NOT EXISTS idx_sessions_health ON sessions(health_state, last_heartbeat);
      CREATE INDEX IF NOT EXISTS idx_work_status ON work_queue(status);
      CREATE INDEX IF NOT EXISTS idx_work_assigned ON work_queue(assigned_to_node, assigned_to_session);
      CREATE INDEX IF NOT EXISTS idx_work_retry ON work_queue(retry_count, retry_limit, status);
      CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_session, to_node);
      CREATE INDEX IF NOT EXISTS idx_messages_delivered ON messages(delivered_at);
    `);

    return { type: 'sqlite', db };
  }

  initializeRedis() {
    throw new Error('Redis backend not implemented yet');
  }

  initializeFileState() {
    return { type: 'file' };
  }

  startHTTPAPI() {
    if (!this.config.api.enabled) {
      return;
    }

    const API_KEY = process.env.ORCHESTRATOR_API_KEY || crypto.randomBytes(32).toString('hex');
    if (!process.env.ORCHESTRATOR_API_KEY) {
      // Fixed: Log only hash of generated API key
      const keyHash = crypto.createHash('sha256').update(API_KEY).digest('hex').slice(0, 16);
      this.log(`WARNING: ORCHESTRATOR_API_KEY not set. Generated random API key (hash: ${keyHash}...)`);
      this.log('Set ORCHESTRATOR_API_KEY environment variable for persistent authentication');
    }

    this.httpServer = http.createServer(async (req, res) => {
      const url = new URL(req.url, `http://${req.headers.host}`);

      if (!req.headers['x-api-key'] || req.headers['x-api-key'] !== API_KEY) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Unauthorized' }));
        return;
      }

      if (url.pathname === '/health') {
        try {
          await this.executeQuery('SELECT 1');
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            status: 'ok',
            node: this.nodeId,
            session: this.sessionId
          }));
        } catch (err) {
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'error', error: err.message }));
        }
      } else if (url.pathname === '/metrics') {
        try {
          const stats = await this.getStats();
          const nodeHash = crypto.createHash('sha256').update(this.nodeId).digest('hex').slice(0, 8);

          res.writeHead(200, { 'Content-Type': 'text/plain' });
          res.end(`# HELP orchestrator_sessions_active Active orchestrator sessions
# TYPE orchestrator_sessions_active gauge
orchestrator_sessions_active{node="${nodeHash}"} ${stats.sessions?.active || 0}

# HELP orchestrator_sessions_suspected Suspected orchestrator sessions
# TYPE orchestrator_sessions_suspected gauge
orchestrator_sessions_suspected{node="${nodeHash}"} ${stats.sessions?.suspected || 0}

# HELP orchestrator_sessions_dead Dead orchestrator sessions
# TYPE orchestrator_sessions_dead gauge
orchestrator_sessions_dead{node="${nodeHash}"} ${stats.sessions?.dead || 0}

# HELP orchestrator_work_queue_depth Work queue depth by status
# TYPE orchestrator_work_queue_depth gauge
orchestrator_work_queue_depth{status="pending"} ${stats.work?.pending || 0}
orchestrator_work_queue_depth{status="assigned"} ${stats.work?.assigned || 0}
orchestrator_work_queue_depth{status="completed"} ${stats.work?.completed || 0}
orchestrator_work_queue_depth{status="failed"} ${stats.work?.failed || 0}

# HELP orchestrator_tasks_redistributed Total tasks redistributed from failed nodes
# TYPE orchestrator_tasks_redistributed counter
orchestrator_tasks_redistributed ${stats.degradation?.tasksRedistributed || 0}

# HELP orchestrator_nodes_failed Total nodes failed
# TYPE orchestrator_nodes_failed counter
orchestrator_nodes_failed ${stats.degradation?.nodesFailed || 0}

# HELP orchestrator_tasks_exhausted_retries Tasks failed due to retry exhaustion
# TYPE orchestrator_tasks_exhausted_retries counter
orchestrator_tasks_exhausted_retries ${stats.degradation?.tasksExhaustedRetries || 0}

# HELP orchestrator_circuit_breaker_open Circuit breaker state
# TYPE orchestrator_circuit_breaker_open gauge
orchestrator_circuit_breaker_open ${this.circuitBreakerState.open ? 1 : 0}
`);
        } catch (err) {
          res.writeHead(500, { 'Content-Type': 'text/plain' });
          res.end(`# Error generating metrics: ${err.message}\n`);
        }
      } else if (url.pathname === '/stats') {
        try {
          const stats = await this.getStats();
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(stats, null, 2));
        } catch (err) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: err.message }));
        }
      } else {
        this.handleHTTPRequest(req, res);
      }
    });

    this.httpServer.listen(this.config.api.port, this.config.api.host, () => {
      this.log(`HTTP API listening on ${this.config.api.host}:${this.config.api.port}`);
    });
  }

  handleHTTPRequest(req, res) {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const path = url.pathname;

    const MAX_BODY_SIZE = 1024 * 1024;
    let body = '';
    let bodySize = 0;
    let limitExceeded = false;

    const onData = (chunk) => {
      // Fixed: Check size before concatenating
      if (bodySize + chunk.length > MAX_BODY_SIZE) {
        limitExceeded = true;
        req.removeAllListeners('data');
        req.removeAllListeners('end');
        res.writeHead(413, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Payload too large' }));
        req.connection.destroy();
        return;
      }
      bodySize += chunk.length;
      body += chunk;
    };

    const onEnd = async () => {
      if (limitExceeded) return;

      try {
        const data = body ? JSON.parse(body) : {};

        switch (path) {
          case '/sessions':
            await this.handleSessionsAPI(req.method, data, res);
            break;

          case '/work':
            await this.handleWorkAPI(req.method, data, res);
            break;

          case '/messages':
            await this.handleMessagesAPI(req.method, data, res);
            break;

          case '/route-thompson':
            await this.handleThompsonSamplingAPI(req.method, data, res);
            break;

          case '/health':
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok', node: this.nodeId }));
            break;

          default:
            res.writeHead(404, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Not found' }));
        }
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    };

    req.on('data', onData);
    req.on('end', onEnd);
  }

  async handleSessionsAPI(method, data, res) {
    try {
      if (method === 'GET') {
        const sessions = await this.executeQuery(
          `SELECT * FROM orchestrator.sessions WHERE health_state = 'active'`
        );
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(sessions));
      } else if (method === 'POST') {
        await this.executeQuery(
          `INSERT INTO orchestrator.sessions (session_id, node_id, status, health_state)
           VALUES ($1, $2, 'active', 'active')
           ON CONFLICT (session_id) DO UPDATE SET
             last_heartbeat = NOW(),
             status = 'active',
             health_state = 'active'`,
          [data.sessionId, data.nodeId || this.nodeId]
        );
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'registered' }));
      } else {
        res.writeHead(405);
        res.end();
      }
    } catch (err) {
      this.log(`Sessions API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  async handleWorkAPI(method, data, res) {
    try {
      if (method === 'GET') {
        const work = await this.executeQuery(
          `SELECT * FROM orchestrator.work_queue
           WHERE status = 'pending' AND retry_count < retry_limit
           ORDER BY priority DESC, enqueued_at ASC
           LIMIT 1`
        );
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(work[0] || null));
      } else if (method === 'POST') {
        const rows = await this.executeQuery(
          `INSERT INTO orchestrator.work_queue (task_type, task_payload, priority, assigned_to, retry_limit)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING work_id`,
          [
            data.task_type,
            JSON.stringify(data.task_data || {}),
            Math.max(1, Math.min(10, data.priority || 5)),
            data.session_id || this.sessionId,
            data.retry_limit || this.config.degradation.retryLimit
          ]
        );
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ workId: rows[0].work_id }));
      } else {
        res.writeHead(405);
        res.end();
      }
    } catch (err) {
      this.log(`Work API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  async handleMessagesAPI(method, data, res) {
    try {
      if (method === 'POST') {
        const rows = await this.executeQuery(
          `INSERT INTO orchestrator.messages (from_session, to_session, message_type, payload)
           VALUES ($1, $2, $3, $4)
           RETURNING message_id`,
          [data.from_session, data.to_session, data.message_type || 'generic', JSON.stringify(data.payload || {})]
        );
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ messageId: rows[0].message_id, status: 'sent' }));
      } else {
        res.writeHead(405);
        res.end();
      }
    } catch (err) {
      this.log(`Messages API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  async handleThompsonSamplingAPI(method, data, res) {
    try {
      const result = await this.selectNode(data.task_type);

      if (result.healthState === 'suspected') {
        this.log(`WARNING: Assigned task ${data.task_type} to suspected node ${result.nodeId}`);
      }

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        nodeId: result.nodeId,
        taskType: data.task_type,
        healthState: result.healthState
      }));
    } catch (err) {
      this.log(`Thompson Sampling API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  async broadcastSession(sessionId, data) {
    const results = await Promise.allSettled(
      this.config.fleet
        .filter(node => node.id !== this.nodeId)
        .map(node =>
          this.httpPost(node.host, node.port, '/sessions', { sessionId, ...data })
            .then(result => ({ node, result }))
            .catch(err => ({ node, error: err }))
        )
    );

    const failures = results
      .filter(r => r.status === 'rejected' || r.value?.error)
      .map(r => ({
        node: r.status === 'rejected' ? null : r.value.node,
        data: { sessionId, ...data },
        error: r.reason || r.value?.error,
        retryCount: 0,
        firstFailedAt: Date.now()
      }));

    if (failures.length > 0) {
      // Fixed: Cap failedBroadcasts before pushing new failures
      const capacityRemaining = this.config.degradation.maxFailedBroadcasts - this.failedBroadcasts.length;
      if (capacityRemaining < failures.length) {
        const excess = failures.length - capacityRemaining;
        this.log(`Failed broadcasts queue at capacity, dropping ${excess} oldest entries`);
        this.failedBroadcasts.splice(0, excess);
      }

      this.log(`Broadcast failed to ${failures.length} nodes - queued for retry`);
      this.failedBroadcasts.push(...failures);
    }

    return results;
  }

  httpPost(host, port, path, data) {
    return new Promise((resolve, reject) => {
      const postData = JSON.stringify(data);
      const options = {
        hostname: host,
        port,
        path,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        },
        timeout: 5000
      };

      const req = http.request(options, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => {
          // Fixed: Validate response before JSON.parse
          if (res.statusCode >= 200 && res.statusCode < 300) {
            try {
              resolve(JSON.parse(body));
            } catch (err) {
              reject(new Error(`Invalid JSON response: ${err.message}`));
            }
          } else {
            reject(new Error(`HTTP ${res.statusCode}: ${body}`));
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Request timeout'));
      });

      req.write(postData);
      req.end();
    });
  }

  log(message) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${this.nodeId}] ${message}`);
  }

  async run() {
    this.log('Distributed orchestrator starting...');

    if (this.pool) {
      try {
        await this.registerSession();
        this.log(`Session registered: ${this.sessionId}`);
      } catch (err) {
        this.log(`Failed to register session: ${err.message}`);
      }
    } else {
      this.log('WARNING: PostgreSQL pool not initialized, session NOT registered');
    }

    this.startHTTPAPI();

    if (this.pool) {
      const scheduleNextHeartbeat = () => {
        if (this.shuttingDown) return;

        this.heartbeatTimeout = setTimeout(async () => {
          if (this.shuttingDown) return;

          try {
            await this.heartbeat();
          } catch (err) {
            this.log(`Heartbeat error: ${err.message}`);
          } finally {
            scheduleNextHeartbeat();
          }
        }, this.config.heartbeatInterval);
      };
      scheduleNextHeartbeat();
    }

    // Fixed: Cap consecutiveErrors to prevent overflow
    let consecutiveErrors = 0;
    const tick = async () => {
      try {
        if (this.pool && !this.circuitBreakerState.open && !this.degradedMode) {
          const work = await this.assignWork();
          if (work) {
            this.log(`Assigned work ${work.work_id}: ${work.task_type}`);
          }

          if (Math.random() < 0.1) {
            await this.executeQuery('SELECT orchestrator.cleanup_expired()');
          }
        } else {
          const localSessions = this.registry.getActiveSessions();
          for (const [sessionId, data] of Object.entries(localSessions)) {
            if (this.state.registerSession) {
              this.state.registerSession(sessionId, this.nodeId, data);
            }
          }

          if (this.state.getQueuedWork && this.state.assignWork) {
            const work = this.state.getQueuedWork();
            const sessions = this.state.getActiveSessions(this.nodeId);

            for (const w of work) {
              if (sessions.length > 0) {
                const assigned = this.state.assignWork(w.work_id, sessions[0].session_id, this.nodeId);
                if (assigned) {
                  this.log(`Assigned work ${w.work_id} to session ${sessions[0].session_id}`);
                }
              }
            }
          }
        }
        consecutiveErrors = 0;
      } catch (err) {
        consecutiveErrors = Math.min(consecutiveErrors + 1, 1000);
        this.log(`Error in orchestration loop (${consecutiveErrors} consecutive): ${err.message}`);

        if (consecutiveErrors >= 5) {
          this.log('Too many consecutive errors - entering degraded mode for 30s');
          this.degradedMode = true;
          setTimeout(() => {
            this.degradedMode = false;
            consecutiveErrors = 0;
            this.log('Exiting degraded mode');
          }, 30000);
        }
      }
    };

    await tick();
    this.interval = setInterval(tick, 5000);

    this.log(`Orchestrator running on node ${this.nodeId}`);
  }

  async stop() {
    this.log('Stopping orchestrator...');
    this.shuttingDown = true;

    let lastProgress = Date.now();
    const progressCheck = setInterval(() => {
      if (Date.now() - lastProgress > 10000) {
        this.log('Shutdown timeout - forcing exit');
        process.exit(1);
      }
    }, 1000);

    if (this.interval) {
      clearInterval(this.interval);
      lastProgress = Date.now();
    }

    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      lastProgress = Date.now();
    }

    if (this.pool && !this.circuitBreakerState.open) {
      try {
        await this.executeQuery(
          'UPDATE orchestrator.sessions SET status = \'dead\', health_state = \'dead\' WHERE session_id = $1',
          [this.sessionId]
        );
        lastProgress = Date.now();
      } catch (err) {
        this.log(`Failed to mark session dead: ${err.message}`);
      }
    }

    if (this.httpServer) {
      this.httpServer.close();
      lastProgress = Date.now();
    }

    if (this.pool) {
      try {
        await Promise.race([
          this.pool.end().then(() => { lastProgress = Date.now(); }),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Pool shutdown timeout')), 5000)
          )
        ]);

        // Fixed: Grace period after pool.end() timeout
        await new Promise(resolve => setTimeout(resolve, 100));
      } catch (err) {
        this.log(`Pool shutdown error: ${err.message}`);
      }
    }

    if (this.state.db) {
      this.state.db.close();
      lastProgress = Date.now();
    }

    clearInterval(progressCheck);
    process.exit(0);
  }
}

if (require.main === module) {
  const command = process.argv[2];
  const orchestrator = new DistributedOrchestrator();

  switch (command) {
    case 'start':
      orchestrator.run();
      process.on('SIGINT', () => orchestrator.stop());
      process.on('SIGTERM', () => orchestrator.stop());
      break;

    case 'stop':
      console.log('Stopping distributed orchestrator...');
      break;

    default:
      console.log('Usage: distributed-orchestrator-graceful-degradation.js <start|stop>');
  }
}

module.exports = DistributedOrchestrator;
