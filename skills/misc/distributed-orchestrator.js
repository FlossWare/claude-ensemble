#!/usr/bin/env node
// Distributed Session Orchestrator - Multi-node coordination
// Uses shared state (Redis/SQLite) and network messaging

const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
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
  loadBalancing: 'least-busy', // 'least-busy' | 'round-robin' | 'random'

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

  async selectNode(taskType) {
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

    this.httpServer.listen(this.config.api.port, '127.0.0.1', () => {
      this.log(`HTTP API listening on 127.0.0.1:${this.config.api.port}`);
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
    this.log('Distributed orchestrator starting...');

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

    this.log(`Orchestrator running on node ${this.nodeId}`);
  }

  async stop() {
    this.log('Stopping orchestrator...');

    if (this.interval) {
      clearInterval(this.interval);
    }

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

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
      console.log('Stopping distributed orchestrator...');
      // TODO: Send stop signal
      break;

    default:
      console.log('Usage: distributed-orchestrator.js <start|stop>');
  }
}

module.exports = DistributedOrchestrator;
