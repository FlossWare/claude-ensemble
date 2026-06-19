#!/usr/bin/env node
// Distributed Session Orchestrator v2 - Multi-node coordination with work stealing
// Adds health monitoring, slow node detection, and dynamic work reallocation

const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const { execSync } = require('child_process');
const { Pool } = require('pg');

const SessionRegistry = require('./session-registry');
const SessionMessenger = require('./session-messenger');
const FleetAPIEnforcer = require('./fleet-api-enforcer');

// Learning adapter (lazy-loaded to handle ESM import)
let learningAdapter = null;
let adapterLoadingPromise = null;

/**
 * Get learning adapter instance
 * P0-1 fix: Pass orchestrator's pool to avoid dual connection pools
 * @param {Pool} pool - PostgreSQL pool from orchestrator
 */
async function getLearningAdapter(pool = null) {
  // P2-2 fix: Prevent race condition on concurrent first-time loads
  if (adapterLoadingPromise) {
    return await adapterLoadingPromise;
  }

  if (learningAdapter) {
    return learningAdapter;
  }

  // Start loading
  adapterLoadingPromise = (async () => {
    try {
      // P0-3 fix: Use deployment-agnostic path
      const adapterPath = path.join(__dirname, 'orchestrator-learning-adapter.js');
      const module = await import(adapterPath);
      // P0-1 fix: Pass pool to avoid creating second connection pool
      learningAdapter = new module.OrchestratorLearningAdapter(pool);
      await learningAdapter.connect();
      return learningAdapter;
    } catch (err) {
      // P0-2 fix: Reset on connection failure so next call retries
      learningAdapter = null;
      adapterLoadingPromise = null;
      throw err;
    }
  })();

  return await adapterLoadingPromise;
}

const ORCHESTRATOR_DIR = path.join(os.homedir(), '.claude', 'orchestrator');
const CONFIG_FILE = path.join(ORCHESTRATOR_DIR, 'distributed-config.json');
const STATE_DB = path.join(ORCHESTRATOR_DIR, 'distributed-state.db');

// Default configuration
const DEFAULT_CONFIG = {
  mode: 'distributed',
  nodeId: os.hostname(),

  // Fleet nodes
  fleet: [
    { id: 'laptop-01', host: 'laptop-01', port: 7340, role: 'coordinator' },
    { id: 'aio-01', host: 'aio-01', port: 7340, role: 'worker' },
    { id: 'server-01', host: 'server-01', port: 7340, role: 'worker' },
    { id: 'server-02', host: 'server-02', port: 7340, role: 'worker' },
    { id: 'server-03', host: 'server-03', port: 7340, role: 'worker' }
  ],

  // This node's HTTP API
  api: {
    enabled: true,
    port: 7340,
    host: '0.0.0.0'
  },

  // State backend
  state: {
    backend: 'postgresql', // 'postgresql' | 'sqlite' | 'redis' | 'file'
    postgresql: {
      host: '/var/run/postgresql',  // Unix socket directory (uses peer auth)
      database: 'learning',
      user: process.env.USER || 'sfloess',
      max: 5,  // Connection pool size (reduced from 10)
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000  // Fail fast
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

  // Heartbeat and timeouts
  heartbeatInterval: 30000,  // 30s
  sessionTimeout: 120000,    // 2 minutes (mark dead if no heartbeat)
  workTimeout: 3600000,      // 1 hour

  // Circuit breaker
  circuitBreaker: {
    failureThreshold: 3,
    resetTimeout: 60000  // 1 min cooldown
  },

  // Work distribution
  workStealing: true,
  loadBalancing: 'health-aware', // 'health-aware' | 'least-busy' | 'round-robin' | 'random'

  // Work stealing configuration
  healthCheckInterval: 5000,      // 5s health check polling
  slowNodeThreshold: 1.5,         // 150% of average duration = slow
  reallocationTimeout: 500,       // Max 500ms to reallocate work
  proactiveRecovery: true,        // Enable proactive failure recovery

  // Health-aware work assignment
  thermalThreshold: 75,           // °C - skip node if hotter
  loadThreshold: 8.0,             // Skip node if load > this
  ramThreshold: 1,                // GB - skip node if less available
  minHealthScore: 30,             // Skip nodes with health score < 30
  laptopComputeLast: false,       // laptop-01 is a full worker (no special treatment)
  healthMonitorScript: path.join(os.homedir(), '.claude', 'fleet', 'node-health-monitor.sh')

  // Conflict detection
  conflictDetection: true,
  autoResolveConflicts: false
};

class DistributedOrchestrator {
  constructor(configPath = CONFIG_FILE) {
    this.config = this.loadConfig(configPath);
    this.nodeId = this.config.nodeId;
    this.sessionId = `${this.nodeId}-${process.pid}-${Date.now()}`;
    this.pool = null;  // Initialize pool before initializeState()
    this.state = this.initializeState();
    // After initializeState(), this.pool should be set (if PostgreSQL backend)
    this.registry = new SessionRegistry();
    this.messenger = new SessionMessenger('orchestrator');
    this.httpServer = null;
    this.circuitBreakerState = { failures: 0, open: false, openedAt: null };
    this.heartbeatInterval = null;
    this.interval = null;
    this.apiEnforcer = new FleetAPIEnforcer();  // API policy enforcer

    // Work stealing state
    this.nodeHealth = new Map();  // nodeId -> { responsive: boolean, latency_ms: number, avg_duration_ms: number }
    this.workReallocationMetrics = {
      totalReallocations: 0,
      successfulReallocations: 0,
      failedReallocations: 0,
      avgReallocationTimeMs: 0,
      recoveryOverheadPct: 0
    };
    this.healthCheckIntervalHandle = null;

    this.ensureDirectories();
  }

  loadConfig(configPath) {
    if (fs.existsSync(configPath)) {
      const userConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      return { ...DEFAULT_CONFIG, ...userConfig };
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

    // Connection error handler
    this.pool.on('error', (err) => {
      this.log(`PostgreSQL connection error: ${err.message}`);
      this.circuitBreakerState.failures++;
      if (this.circuitBreakerState.failures >= this.config.circuitBreaker.failureThreshold) {
        this.openCircuitBreaker();
      }
    });

    return {
      type: 'postgresql',
      pool: this.pool
    };
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
    if (!this.pool) {
      throw new Error('PostgreSQL pool not initialized - backend may be SQLite or file-based');
    }

    if (this.circuitBreakerState.open) {
      throw new Error('Circuit breaker open - PostgreSQL unavailable');
    }

    try {
      const result = await this.pool.query(sql, params);
      this.circuitBreakerState.failures = 0;  // Reset on success
      return result.rows;
    } catch (err) {
      this.circuitBreakerState.failures++;
      if (this.circuitBreakerState.failures >= this.config.circuitBreaker.failureThreshold) {
        this.openCircuitBreaker();
      }
      this.log(`Query failed: ${err.message}`);
      throw err;
    }
  }

  async registerSession() {
    await this.executeQuery(`
      INSERT INTO orchestrator.sessions (session_id, node_id, status)
      VALUES ($1, $2, 'active')
      ON CONFLICT (session_id) DO UPDATE SET last_heartbeat = NOW(), status = 'active'
    `, [this.sessionId, this.nodeId]);
  }

  async heartbeat() {
    try {
      await this.executeQuery(`
        UPDATE orchestrator.sessions
        SET last_heartbeat = NOW(), status = 'active'
        WHERE session_id = $1
      `, [this.sessionId]);
    } catch (err) {
      this.log(`Heartbeat failed: ${err.message}`);
    }
  }

  async assignWork() {
    // Use FOR UPDATE SKIP LOCKED to prevent race conditions
    const rows = await this.executeQuery(`
      WITH next_work AS (
        SELECT work_id FROM orchestrator.work_queue
        WHERE status = 'pending'
        ORDER BY priority DESC, enqueued_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
      )
      UPDATE orchestrator.work_queue
      SET status = 'assigned', assigned_to = $1, assigned_at = NOW()
      FROM next_work
      WHERE orchestrator.work_queue.work_id = next_work.work_id
      RETURNING orchestrator.work_queue.*;
    `, [this.sessionId]);

    return rows[0] || null;
  }

  async selectNode(taskType, requestedModel = null) {
    // If model specified, enforce API policy
    if (requestedModel) {
      const routing = this.apiEnforcer.routeTask(requestedModel, this.config.fleet.map(n => n.id));
      console.log(`[API Policy] ${requestedModel} → ${routing.node} (${routing.reason})`);
      return routing.node;
    }

    // Thompson Sampling node selection
    const nodes = await this.executeQuery(`
      SELECT node_id, alpha, beta, total_assigned
      FROM orchestrator.node_performance
      WHERE task_type = $1
    `, [taskType]);

    if (nodes.length === 0) {
      // Cold start: random selection
      const allNodes = this.config.fleet.map(n => n.id);
      return allNodes[Math.floor(Math.random() * allNodes.length)];
    }

    // Sample from Beta distribution
    let bestNode = null;
    let bestSample = -1;

    for (const node of nodes) {
      // Simple Beta sampling approximation: sample = alpha / (alpha + beta)
      const sample = node.alpha / (node.alpha + node.beta) + (Math.random() * 0.1);
      if (sample > bestSample) {
        bestSample = sample;
        bestNode = node.node_id;
      }
    }

    return bestNode;
  }

  async updateNodePerformance(nodeId, taskType, success, durationMs) {
    const reward = success ? (1.0 - Math.min(durationMs / 60000, 1.0)) : 0.0;

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
        avg_duration_ms = (orchestrator.node_performance.avg_duration_ms * orchestrator.node_performance.total_assigned + $7) / (orchestrator.node_performance.total_assigned + 1),
        avg_reward = (orchestrator.node_performance.avg_reward * orchestrator.node_performance.total_assigned + $8) / (orchestrator.node_performance.total_assigned + 1),
        last_assigned = NOW()
    `, [
      nodeId, taskType,
      success ? 1 : 0,  // alpha increment
      success ? 0 : 1,  // beta increment
      success ? 1 : 0,  // completed count
      success ? 0 : 1,  // failed count
      durationMs,
      reward
    ]);

    // Update local node health cache
    const healthEntry = this.nodeHealth.get(nodeId) || { responsive: true, latency_ms: 0, avg_duration_ms: 0 };
    healthEntry.avg_duration_ms = durationMs;
    this.nodeHealth.set(nodeId, healthEntry);
  }

  initializeSQLite() {
    const Database = require('better-sqlite3');
    const db = new Database(this.config.state.sqlite.path);

    if (this.config.state.sqlite.wal) {
      db.pragma('journal_mode = WAL');
    }

    // Create tables
    db.exec(`
      CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL,
        pid INTEGER NOT NULL,
        cwd TEXT,
        working_on TEXT,
        files_locked TEXT, -- JSON array
        status TEXT DEFAULT 'active',
        started_at TEXT NOT NULL,
        last_heartbeat TEXT NOT NULL,
        metadata TEXT -- JSON blob
      );

      CREATE TABLE IF NOT EXISTS work_queue (
        work_id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        files TEXT, -- JSON array
        priority TEXT DEFAULT 'normal',
        status TEXT DEFAULT 'queued',
        assigned_to_session TEXT,
        assigned_to_node TEXT,
        enqueued_at TEXT NOT NULL,
        assigned_at TEXT,
        completed_at TEXT,
        result TEXT, -- JSON blob
        metadata TEXT -- JSON blob
      );

      CREATE TABLE IF NOT EXISTS messages (
        message_id TEXT PRIMARY KEY,
        from_session TEXT NOT NULL,
        from_node TEXT NOT NULL,
        to_session TEXT NOT NULL,
        to_node TEXT,
        type TEXT NOT NULL,
        priority TEXT DEFAULT 'normal',
        payload TEXT NOT NULL, -- JSON blob
        created_at TEXT NOT NULL,
        delivered_at TEXT,
        read_at TEXT,
        expires_at TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_sessions_node ON sessions(node_id);
      CREATE INDEX IF NOT EXISTS idx_sessions_heartbeat ON sessions(last_heartbeat);
      CREATE INDEX IF NOT EXISTS idx_work_status ON work_queue(status);
      CREATE INDEX IF NOT EXISTS idx_work_assigned ON work_queue(assigned_to_node, assigned_to_session);
      CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_session, to_node);
      CREATE INDEX IF NOT EXISTS idx_messages_delivered ON messages(delivered_at);
    `);

    return {
      type: 'sqlite',
      db,

      // Session operations
      registerSession(sessionId, nodeId, data) {
        const stmt = db.prepare(`
          INSERT OR REPLACE INTO sessions
          (session_id, node_id, pid, cwd, working_on, files_locked, status, started_at, last_heartbeat, metadata)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        stmt.run(
          sessionId,
          nodeId,
          data.pid,
          data.cwd,
          data.working_on,
          JSON.stringify(data.files_locked || []),
          data.status || 'active',
          data.started || new Date().toISOString(),
          new Date().toISOString(),
          JSON.stringify(data.metadata || {})
        );
      },

      getActiveSessions(nodeId = null) {
        const timeoutThreshold = new Date(Date.now() - 300000).toISOString();
        let stmt;

        if (nodeId) {
          stmt = db.prepare('SELECT * FROM sessions WHERE node_id = ? AND last_heartbeat > ?');
          return stmt.all(nodeId, timeoutThreshold);
        } else {
          stmt = db.prepare('SELECT * FROM sessions WHERE last_heartbeat > ?');
          return stmt.all(timeoutThreshold);
        }
      },

      // Work queue operations
      enqueueWork(work) {
        const workId = work.id || `work-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const stmt = db.prepare(`
          INSERT INTO work_queue
          (work_id, description, files, priority, status, enqueued_at, metadata)
          VALUES (?, ?, ?, ?, 'queued', ?, ?)
        `);
        stmt.run(
          workId,
          work.description,
          JSON.stringify(work.files || []),
          work.priority || 'normal',
          new Date().toISOString(),
          JSON.stringify(work.metadata || {})
        );
        return workId;
      },

      assignWork(workId, sessionId, nodeId) {
        const stmt = db.prepare(`
          UPDATE work_queue
          SET status = 'assigned', assigned_to_session = ?, assigned_to_node = ?, assigned_at = ?
          WHERE work_id = ? AND status = 'queued'
        `);
        const result = stmt.run(sessionId, nodeId, new Date().toISOString(), workId);
        return result.changes > 0;
      },

      getQueuedWork() {
        const stmt = db.prepare('SELECT * FROM work_queue WHERE status = "queued" ORDER BY priority DESC, enqueued_at ASC');
        return stmt.all();
      },

      completeWork(workId, result) {
        const stmt = db.prepare(`
          UPDATE work_queue
          SET status = 'completed', completed_at = ?, result = ?
          WHERE work_id = ?
        `);
        stmt.run(new Date().toISOString(), JSON.stringify(result), workId);
      },

      // Message operations
      sendMessage(msg) {
        const stmt = db.prepare(`
          INSERT INTO messages
          (message_id, from_session, from_node, to_session, to_node, type, priority, payload, created_at, expires_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        stmt.run(
          msg.id,
          msg.from_session,
          msg.from_node,
          msg.to_session,
          msg.to_node || null,
          msg.type,
          msg.priority || 'normal',
          JSON.stringify(msg.payload),
          new Date().toISOString(),
          msg.expires_at || null
        );
      },

      getMessages(sessionId) {
        const stmt = db.prepare('SELECT * FROM messages WHERE to_session = ? AND delivered_at IS NULL ORDER BY created_at ASC');
        return stmt.all(sessionId);
      },

      markDelivered(messageId) {
        const stmt = db.prepare('UPDATE messages SET delivered_at = ? WHERE message_id = ?');
        stmt.run(new Date().toISOString(), messageId);
      }
    };
  }

  initializeRedis() {
    // TODO: Implement Redis backend
    throw new Error('Redis backend not implemented yet');
  }

  initializeFileState() {
    // Fallback to file-based state (single node only)
    return {
      type: 'file',
      // ... file-based implementation
    };
  }

  /**
   * Thermal/Load-Aware Health Check: Call node-health-monitor.sh for comprehensive metrics
   * Returns { responsive: boolean, latency_ms: number, health_score: number, metrics: {...}, thresholds: {...} }
   */
  async checkNodeHealth(nodeId) {
    const start = Date.now();
    try {
      const healthScript = this.config.healthMonitorScript;
      const result = execSync(`${healthScript} ${nodeId}`, {
        timeout: 3000,
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore']  // Suppress stderr noise
      });
      const latency = Date.now() - start;
      const healthData = JSON.parse(result);

      return {
        responsive: true,
        latency_ms: latency,
        health_score: healthData.health_score,
        metrics: healthData.metrics,
        thresholds: healthData.thresholds,
        avg_duration_ms: this.nodeHealth.get(nodeId)?.avg_duration_ms || 0
      };
    } catch (err) {
      this.log(`Node ${nodeId} health check failed: ${err.message}`);
      return {
        responsive: false,
        latency_ms: null,
        health_score: 0,
        metrics: null,
        thresholds: null,
        avg_duration_ms: 0
      };
    }
  }

  /**
   * Work Stealing: Get work assigned to a specific node
   * Returns array of work items
   */
  async getNodeWork(nodeId) {
    if (!this.pool) return [];

    try {
      const rows = await this.executeQuery(`
        SELECT * FROM orchestrator.work_queue
        WHERE assigned_to = $1 AND status = 'assigned'
        ORDER BY priority DESC, enqueued_at ASC
      `, [nodeId]);
      return rows;
    } catch (err) {
      this.log(`Failed to get work for node ${nodeId}: ${err.message}`);
      return [];
    }
  }

  /**
   * Health-Aware Node Selection: Get best node by health score (thermal + load + RAM)
   * Returns node ID or null
   */
  getBestHealthyNode() {
    const minScore = this.config.minHealthScore;
    const candidates = [];

    // Filter nodes by health score threshold
    for (const [nodeId, health] of this.nodeHealth.entries()) {
      if (health.responsive && health.health_score >= minScore) {
        candidates.push({ nodeId, health });
      }
    }

    if (candidates.length === 0) {
      this.log(`No nodes meet health threshold (min: ${minScore})`);
      return null;
    }

    // Sort by health score (descending), then by avg_duration_ms (ascending)
    candidates.sort((a, b) => {
      if (b.health.health_score !== a.health.health_score) {
        return b.health.health_score - a.health.health_score;
      }
      return a.health.avg_duration_ms - b.health.avg_duration_ms;
    });

    const selected = candidates[0];
    this.log(`Selected node ${selected.nodeId} (score: ${selected.health.health_score}, load: ${selected.health.metrics?.load_avg_1m || 'N/A'}, temp: ${selected.health.metrics?.temp_c || 'N/A'}°C)`);

    return selected.nodeId;
  }

  /**
   * Backward compatibility: Alias for health-aware selection
   * @deprecated Use getBestHealthyNode() for clarity
   */
  getFastestAvailableNode() {
    return this.getBestHealthyNode();
  }

  /**
   * Work Stealing: Reassign work from slow/dead node to fast node
   * Returns number of work items reallocated
   */
  async reassignWork(workItems, targetNodeId) {
    if (!this.pool || workItems.length === 0) return 0;

    let reallocatedCount = 0;
    const startTime = Date.now();

    try {
      for (const work of workItems) {
        await this.executeQuery(`
          UPDATE orchestrator.work_queue
          SET assigned_to = $1, assigned_at = NOW(), status = 'pending'
          WHERE work_id = $2
        `, [targetNodeId, work.work_id]);
        reallocatedCount++;
      }

      const reallocationTime = Date.now() - startTime;
      this.workReallocationMetrics.totalReallocations += reallocatedCount;
      this.workReallocationMetrics.successfulReallocations += reallocatedCount;
      this.workReallocationMetrics.avgReallocationTimeMs =
        (this.workReallocationMetrics.avgReallocationTimeMs + reallocationTime) / 2;

      this.log(`Reallocated ${reallocatedCount} work items to ${targetNodeId} in ${reallocationTime}ms`);
    } catch (err) {
      this.workReallocationMetrics.failedReallocations++;
      this.log(`Failed to reallocate work: ${err.message}`);
    }

    return reallocatedCount;
  }

  /**
   * Work Stealing: Detect slow nodes and reallocate their work
   * Triggered by health check polling
   */
  async reallocateWork(slowNodeId) {
    if (!this.config.workStealing || !this.config.proactiveRecovery) {
      return;
    }

    const startTime = Date.now();

    try {
      const pendingWork = await this.getNodeWork(slowNodeId);
      if (pendingWork.length === 0) {
        return;  // No work to reallocate
      }

      const fastestNode = this.getFastestAvailableNode();
      if (!fastestNode) {
        this.log(`No available nodes to reallocate work from ${slowNodeId}`);
        return;
      }

      const reallocatedCount = await this.reassignWork(pendingWork, fastestNode);
      const reallocationTime = Date.now() - startTime;

      if (reallocationTime > this.config.reallocationTimeout) {
        this.log(`WARNING: Reallocation took ${reallocationTime}ms (threshold: ${this.config.reallocationTimeout}ms)`);
      }

      // Calculate recovery overhead percentage
      const totalWorkDuration = pendingWork.reduce((sum, w) => sum + (w.duration_ms || 0), 0);
      this.workReallocationMetrics.recoveryOverheadPct =
        totalWorkDuration > 0 ? (reallocationTime / totalWorkDuration) * 100 : 0;

    } catch (err) {
      this.log(`Error reallocating work from ${slowNodeId}: ${err.message}`);
    }
  }

  /**
   * Work Stealing: Monitor node health and trigger reallocation
   * Runs every healthCheckInterval
   */
  async monitorNodeHealth() {
    for (const node of this.config.fleet) {
      if (node.id === this.nodeId) continue;  // Skip self

      const health = await this.checkNodeHealth(node.id);
      this.nodeHealth.set(node.id, health);

      // Detect unresponsive nodes
      if (!health.responsive) {
        this.log(`Node ${node.id} is unresponsive - triggering work reallocation`);
        await this.reallocateWork(node.id);
        continue;
      }

      // Detect slow nodes (>150% of fleet average)
      const avgDuration = await this.getFleetAverageDuration();
      if (health.avg_duration_ms > avgDuration * this.config.slowNodeThreshold) {
        this.log(`Node ${node.id} is slow (${health.avg_duration_ms}ms vs avg ${avgDuration}ms) - triggering work reallocation`);
        await this.reallocateWork(node.id);
      }
    }
  }

  /**
   * Work Stealing: Calculate fleet-wide average task duration
   * Returns average duration in milliseconds
   */
  async getFleetAverageDuration() {
    if (!this.pool) return 0;

    try {
      const rows = await this.executeQuery(`
        SELECT AVG(avg_duration_ms) as fleet_avg
        FROM orchestrator.node_performance
      `);
      return rows[0]?.fleet_avg || 0;
    } catch (err) {
      this.log(`Failed to calculate fleet average duration: ${err.message}`);
      return 0;
    }
  }

  /**
   * Start health check polling for work stealing
   */
  startHealthCheckMonitoring() {
    if (!this.config.workStealing) {
      this.log('Work stealing disabled - skipping health monitoring');
      return;
    }

    this.log(`Starting health check monitoring (interval: ${this.config.healthCheckInterval}ms)`);
    this.healthCheckIntervalHandle = setInterval(
      () => this.monitorNodeHealth(),
      this.config.healthCheckInterval
    );
  }

  /**
   * Stop health check polling
   */
  stopHealthCheckMonitoring() {
    if (this.healthCheckIntervalHandle) {
      clearInterval(this.healthCheckIntervalHandle);
      this.healthCheckIntervalHandle = null;
      this.log('Stopped health check monitoring');
    }
  }

  // HTTP API for health checks + metrics
  startHTTPAPI() {
    if (!this.config.api.enabled) {
      return;
    }

    this.httpServer = http.createServer(async (req, res) => {
      const url = new URL(req.url, `http://${req.headers.host}`);

      if (url.pathname === '/health') {
        try {
          await this.executeQuery('SELECT 1');
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ok', node: this.nodeId, session: this.sessionId }));
        } catch (err) {
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'error', error: err.message }));
        }
      } else if (url.pathname === '/metrics') {
        try {
          const sessions = await this.executeQuery('SELECT COUNT(*) as count FROM orchestrator.sessions WHERE status = \'active\'');
          const pending = await this.executeQuery('SELECT COUNT(*) as count FROM orchestrator.work_queue WHERE status = \'pending\'');
          const assigned = await this.executeQuery('SELECT COUNT(*) as count FROM orchestrator.work_queue WHERE status = \'assigned\'');

          res.writeHead(200, { 'Content-Type': 'text/plain' });
          res.end(`# HELP orchestrator_sessions_active Active orchestrator sessions
# TYPE orchestrator_sessions_active gauge
orchestrator_sessions_active{node="${this.nodeId}"} ${sessions[0].count}

# HELP orchestrator_work_queue_depth Work queue depth by status
# TYPE orchestrator_work_queue_depth gauge
orchestrator_work_queue_depth{status="pending"} ${pending[0].count}
orchestrator_work_queue_depth{status="assigned"} ${assigned[0].count}

# HELP orchestrator_circuit_breaker_open Circuit breaker state
# TYPE orchestrator_circuit_breaker_open gauge
orchestrator_circuit_breaker_open ${this.circuitBreakerState.open ? 1 : 0}

# HELP orchestrator_work_reallocations Total work reallocations
# TYPE orchestrator_work_reallocations counter
orchestrator_work_reallocations{status="total"} ${this.workReallocationMetrics.totalReallocations}
orchestrator_work_reallocations{status="successful"} ${this.workReallocationMetrics.successfulReallocations}
orchestrator_work_reallocations{status="failed"} ${this.workReallocationMetrics.failedReallocations}

# HELP orchestrator_reallocation_time_ms Average work reallocation time
# TYPE orchestrator_reallocation_time_ms gauge
orchestrator_reallocation_time_ms ${this.workReallocationMetrics.avgReallocationTimeMs}

# HELP orchestrator_recovery_overhead_pct Recovery overhead percentage
# TYPE orchestrator_recovery_overhead_pct gauge
orchestrator_recovery_overhead_pct ${this.workReallocationMetrics.recoveryOverheadPct}
`);
        } catch (err) {
          res.writeHead(500, { 'Content-Type': 'text/plain' });
          res.end(`# Error generating metrics: ${err.message}\n`);
        }
      } else {
        // Delegate to old handler for backward compatibility
        this.handleHTTPRequest(req, res);
      }
    });

    // P1-4 fix: Use configured host (not hardcoded 127.0.0.1)
    this.httpServer.listen(this.config.api.port, this.config.api.host, () => {
      this.log(`HTTP API listening on ${this.config.api.host}:${this.config.api.port}`);
    });
  }

  handleHTTPRequest(req, res) {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const path = url.pathname;

    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
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
            await this.handleThompsonRoutingAPI(req.method, data, res);
            break;

          case '/feedback':
            await this.handleFeedbackAPI(req.method, data, res);
            break;

          case '/rankings':
            await this.handleRankingsAPI(req.method, data, res);
            break;

          case '/work-stealing-metrics':
            await this.handleWorkStealingMetricsAPI(req.method, data, res);
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
    });
  }

  async handleSessionsAPI(method, data, res) {
    try {
      if (method === 'GET') {
        const sessions = await this.executeQuery(
          `SELECT * FROM orchestrator.sessions WHERE status = 'active'`
        );
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(sessions));
      } else if (method === 'POST') {
        await this.executeQuery(
          `INSERT INTO orchestrator.sessions (session_id, node_id, status)
           VALUES ($1, $2, 'active')
           ON CONFLICT (session_id) DO UPDATE SET last_heartbeat = NOW(), status = 'active'`,
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
           WHERE status = 'pending'
           ORDER BY priority DESC, enqueued_at ASC
           LIMIT 1`
        );
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(work[0] || null));
      } else if (method === 'POST') {
        const rows = await this.executeQuery(
          `INSERT INTO orchestrator.work_queue (task_type, task_payload, priority, assigned_to)
           VALUES ($1, $2, $3, $4)
           RETURNING work_id`,
          [data.task_type, JSON.stringify(data.task_data || {}), Math.max(1, Math.min(10, data.priority || 5)), data.session_id || this.sessionId]
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

  async handleThompsonRoutingAPI(method, data, res) {
    if (method !== 'POST') {
      res.writeHead(405, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Method not allowed' }));
      return;
    }

    try {
      const { taskType, availableModels, count = 3 } = data;

      if (!taskType || !availableModels || !Array.isArray(availableModels)) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          error: 'Missing required fields: taskType, availableModels (array)'
        }));
        return;
      }

      // P1-2 fix: Validate count parameter
      const validatedCount = Math.max(1, Math.min(availableModels.length, parseInt(count, 10) || 3));

      const adapter = await getLearningAdapter(this.pool);
      const selectedModels = await adapter.selectModelsThompson(taskType, availableModels, validatedCount);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        taskType,
        selectedModels,
        count: selectedModels.length,
        timestamp: new Date().toISOString()
      }));
    } catch (err) {
      this.log(`Thompson Routing API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  async handleFeedbackAPI(method, data, res) {
    if (method !== 'POST') {
      res.writeHead(405, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Method not allowed' }));
      return;
    }

    try {
      const { model, feedback } = data;

      if (!model || !feedback) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          error: 'Missing required fields: model, feedback (object)'
        }));
        return;
      }

      const adapter = await getLearningAdapter(this.pool);
      await adapter.recordFeedback(model, feedback);

      res.writeHead(201, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'recorded',
        model,
        timestamp: new Date().toISOString()
      }));
    } catch (err) {
      this.log(`Feedback API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  async handleRankingsAPI(method, data, res) {
    if (method !== 'GET') {
      res.writeHead(405, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Method not allowed' }));
      return;
    }

    try {
      const adapter = await getLearningAdapter(this.pool);
      const rankings = await adapter.getModelRankings();

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        rankings,
        count: rankings.length,
        timestamp: new Date().toISOString()
      }));
    } catch (err) {
      this.log(`Rankings API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  async handleWorkStealingMetricsAPI(method, data, res) {
    if (method !== 'GET') {
      res.writeHead(405, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Method not allowed' }));
      return;
    }

    try {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        workStealingEnabled: this.config.workStealing,
        healthCheckIntervalMs: this.config.healthCheckInterval,
        slowNodeThreshold: this.config.slowNodeThreshold,
        reallocationTimeoutMs: this.config.reallocationTimeout,
        proactiveRecovery: this.config.proactiveRecovery,
        metrics: this.workReallocationMetrics,
        nodeHealth: Array.from(this.nodeHealth.entries()).map(([nodeId, health]) => ({
          nodeId,
          ...health
        })),
        timestamp: new Date().toISOString()
      }));
    } catch (err) {
      this.log(`Work Stealing Metrics API error: ${err.message}`);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  // Broadcast session registration to all nodes
  broadcastSession(sessionId, data) {
    for (const node of this.config.fleet) {
      if (node.id === this.nodeId) continue;

      try {
        this.httpPost(node.host, node.port, '/sessions', {
          sessionId,
          ...data
        });
      } catch (err) {
        this.log(`Failed to broadcast session to ${node.id}: ${err.message}`);
      }
    }
  }

  // HTTP POST helper
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
        }
      };

      const req = http.request(options, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve(JSON.parse(body)));
      });

      req.on('error', reject);
      req.write(postData);
      req.end();
    });
  }

  log(message) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${this.nodeId}] ${message}`);
  }

  async run() {
    this.log('Distributed orchestrator v2 starting (work stealing enabled)...');

    // Register this session
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

    // Start HTTP API
    this.startHTTPAPI();

    // Start health check monitoring (work stealing)
    this.startHealthCheckMonitoring();

    // Heartbeat loop
    if (this.pool) {
      this.heartbeatInterval = setInterval(() => this.heartbeat(), this.config.heartbeatInterval);
    }

    // Main orchestration loop
    const tick = async () => {
      try {
        if (this.pool && !this.circuitBreakerState.open) {
          // Auto-assign work
          const work = await this.assignWork();
          if (work) {
            this.log(`Assigned work ${work.work_id}: ${work.task_type}`);
          }

          // Cleanup expired data (every 10th iteration = ~50s)
          if (Math.random() < 0.1) {
            await this.executeQuery('SELECT orchestrator.cleanup_expired()');
          }
        } else {
          // Fallback to SQLite/file-based for local sessions
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
      } catch (err) {
        this.log(`Error in orchestration loop: ${err.message}`);
      }
    };

    // Initial tick
    await tick();

    // Schedule recurring ticks
    this.interval = setInterval(tick, 5000);

    this.log(`Orchestrator v2 running on node ${this.nodeId}`);
  }

  async stop() {
    this.log('Stopping orchestrator v2...');

    if (this.interval) {
      clearInterval(this.interval);
    }

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    // Stop health check monitoring
    this.stopHealthCheckMonitoring();

    // Mark session as dead
    if (this.pool && !this.circuitBreakerState.open) {
      try {
        await this.executeQuery('UPDATE orchestrator.sessions SET status = \'dead\' WHERE session_id = $1', [this.sessionId]);
      } catch (err) {
        this.log(`Failed to mark session dead: ${err.message}`);
      }
    }

    if (this.httpServer) {
      this.httpServer.close();
    }

    if (this.pool) {
      await this.pool.end();
    }

    if (this.state.db) {
      this.state.db.close();
    }

    process.exit(0);
  }
}

// CLI
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
      console.log('Stopping distributed orchestrator v2...');
      // TODO: Send stop signal
      break;

    default:
      console.log('Usage: distributed-orchestrator-v2.js <start|stop>');
  }
}

module.exports = DistributedOrchestrator;
