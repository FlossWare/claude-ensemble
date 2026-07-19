#!/usr/bin/env node

/**
 * Knowledge Sync Daemon
 *
 * Background service that:
 *   1. Polls PostgreSQL knowledge.discoveries for new verified discoveries
 *   2. Syncs verified discoveries to OrientDB knowledge graph via REST API
 *   3. Triggers fleet-wide distribution of high-value knowledge
 *   4. Monitors verification backlog and alerts on stale discoveries
 *
 * Architecture:
 *   knowledge.discoveries (PostgreSQL)
 *        ↓ (poll every 5 minutes)
 *   Filter: status='verified', not yet synced to OrientDB
 *        ↓
 *   OrientDB sync via REST API (POST http://aio-01:5000/graph/query)
 *        ↓
 *   Update: mark as synced in metadata
 *
 * Deployment:
 *   - Run on aio-01 (orchestrator)
 *   - Auto-restart on failure (systemd or PM2)
 *   - Log to ~/.claude/learning/logs/knowledge-sync-daemon.log
 *
 * Usage:
 *   node knowledge-sync-daemon.js           # Start daemon
 *   node knowledge-sync-daemon.js --once    # Run once and exit
 *   node knowledge-sync-daemon.js --status  # Show status
 */

const { Client } = require('pg');
const fs = require('fs');
const path = require('path');
const http = require('http');

const LEARNING_DIR = path.join(process.env.HOME, '.claude', 'learning');
const LOG_DIR = path.join(LEARNING_DIR, 'logs');
const LOG_FILE = path.join(LOG_DIR, 'knowledge-sync-daemon.log');
const STATE_FILE = path.join(LEARNING_DIR, 'knowledge-sync-daemon-state.json');

// Config
const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
const PG_CONFIG = {
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: 'claude'
};
const ORIENTDB_API_URL = 'http://aio-01:5000/graph/query';

class KnowledgeSyncDaemon {
  constructor() {
    this.pgClient = null;
    this.orientdbAvailable = false;
    this.running = false;
    this.stats = {
      discoveries_synced: 0,
      sync_failures: 0,
      last_sync: null,
      uptime_started: new Date()
    };

    // Ensure log directory exists
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true });
    }
  }

  log(message) {
    const timestamp = new Date().toISOString();
    const logLine = `[${timestamp}] ${message}\n`;
    console.log(logLine.trim());
    fs.appendFileSync(LOG_FILE, logLine);
  }

  /**
   * Send a query to OrientDB via REST API (best-effort, non-blocking)
   */
  async orientdbQuery(query) {
    return new Promise((resolve, reject) => {
      const postData = JSON.stringify({ query });
      const url = new URL(ORIENTDB_API_URL);
      const options = {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        },
        timeout: 10000
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            resolve({ result: data });
          }
        });
      });

      req.on('error', (err) => reject(err));
      req.on('timeout', () => { req.destroy(); reject(new Error('OrientDB request timed out')); });
      req.write(postData);
      req.end();
    });
  }

  async connect() {
    // Connect to PostgreSQL
    if (!this.pgClient) {
      this.pgClient = new Client(PG_CONFIG);
      await this.pgClient.connect();
      this.log('Connected to PostgreSQL');
    }

    // Check OrientDB availability via REST API (optional)
    if (!this.orientdbAvailable) {
      try {
        await this.orientdbQuery('SELECT 1');
        this.orientdbAvailable = true;
        this.log('Connected to OrientDB via REST API');
      } catch (err) {
        this.log(`OrientDB unavailable: ${err.message}. PostgreSQL-only mode.`);
        this.orientdbAvailable = false;
      }
    }
  }

  async disconnect() {
    if (this.pgClient) {
      await this.pgClient.end();
      this.pgClient = null;
      this.log('Disconnected from PostgreSQL');
    }

    this.orientdbAvailable = false;
    this.log('OrientDB REST API session ended');
  }

  /**
   * Fetch verified discoveries not yet synced to OrientDB
   */
  async fetchUnsynced() {
    const result = await this.pgClient.query(`
      SELECT
        id,
        worker_id,
        discovery_type,
        content,
        confidence,
        verified_by,
        verification_count,
        created_at,
        verified_at
      FROM knowledge.discoveries
      WHERE status = 'verified'
        AND (metadata->>'synced_to_graph')::boolean IS NOT TRUE
      ORDER BY verified_at DESC
      LIMIT 100
    `);

    return result.rows;
  }

  /**
   * Sync discovery to OrientDB knowledge graph via REST API
   */
  async syncToOrientDB(discovery) {
    if (!this.orientdbAvailable) {
      this.log(`OrientDB unavailable, skipping sync for discovery ${discovery.id}`);
      return { status: 'skipped', reason: 'orientdb_unavailable' };
    }

    try {
      // Create or update Discovery vertex
      const escContent = (discovery.content || '').replace(/'/g, "\\'");
      await this.orientdbQuery(
        `UPDATE Discovery SET id = '${discovery.id}', type = '${discovery.discovery_type}', ` +
        `content = '${escContent}', confidence = ${discovery.confidence}, ` +
        `verifications = ${discovery.verification_count}, ` +
        `createdAt = '${discovery.created_at.toISOString()}', ` +
        `verifiedAt = '${discovery.verified_at.toISOString()}' ` +
        `UPSERT WHERE id = '${discovery.id}'`
      );

      // Create Worker vertex and DISCOVERED edge
      await this.orientdbQuery(
        `UPDATE Worker SET worker_id = '${discovery.worker_id}' ` +
        `UPSERT WHERE worker_id = '${discovery.worker_id}'`
      );

      await this.orientdbQuery(
        `CREATE EDGE Discovered FROM ` +
        `(SELECT FROM Worker WHERE worker_id = '${discovery.worker_id}') TO ` +
        `(SELECT FROM Discovery WHERE id = '${discovery.id}') ` +
        `SET createdAt = '${discovery.created_at.toISOString()}'`
      );

      // Create verifier relationships
      for (const verifier of discovery.verified_by || []) {
        await this.orientdbQuery(
          `UPDATE Worker SET worker_id = '${verifier}' ` +
          `UPSERT WHERE worker_id = '${verifier}'`
        );

        await this.orientdbQuery(
          `CREATE EDGE Verified FROM ` +
          `(SELECT FROM Worker WHERE worker_id = '${verifier}') TO ` +
          `(SELECT FROM Discovery WHERE id = '${discovery.id}') ` +
          `SET createdAt = '${new Date().toISOString()}'`
        );
      }

      // Mark as synced in PostgreSQL
      await this.pgClient.query(`
        UPDATE knowledge.discoveries
        SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
        WHERE id = $1
      `, [discovery.id, JSON.stringify({ synced_to_graph: true, synced_at: new Date().toISOString() })]);

      this.log(`Synced discovery ${discovery.id} to OrientDB`);
      return { status: 'synced', discoveryId: discovery.id };

    } catch (err) {
      this.log(`Failed to sync discovery ${discovery.id}: ${err.message}`);
      return { status: 'failed', discoveryId: discovery.id, error: err.message };
    }
  }

  /**
   * Run one sync cycle
   */
  async runSyncCycle() {
    try {
      await this.connect();

      // Fetch unsynced discoveries
      const discoveries = await this.fetchUnsynced();
      this.log(`Found ${discoveries.length} verified discoveries to sync`);

      if (discoveries.length === 0) {
        this.stats.last_sync = new Date();
        return;
      }

      // Sync each discovery
      let synced = 0;
      let failed = 0;

      for (const discovery of discoveries) {
        const result = await this.syncToOrientDB(discovery);

        if (result.status === 'synced') {
          synced++;
        } else if (result.status === 'failed') {
          failed++;
        }
      }

      this.stats.discoveries_synced += synced;
      this.stats.sync_failures += failed;
      this.stats.last_sync = new Date();

      this.log(`Sync cycle complete: ${synced} synced, ${failed} failed`);

      // Save state
      this.saveState();

    } catch (err) {
      this.log(`Sync cycle error: ${err.message}`);
      this.stats.sync_failures++;
    }
  }

  /**
   * Start daemon (continuous polling)
   */
  async start() {
    this.log('Knowledge Sync Daemon starting...');
    this.running = true;

    while (this.running) {
      await this.runSyncCycle();

      // Wait for next cycle
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
    }

    await this.disconnect();
    this.log('Knowledge Sync Daemon stopped');
  }

  /**
   * Stop daemon
   */
  async stop() {
    this.log('Knowledge Sync Daemon stopping...');
    this.running = false;
  }

  /**
   * Save daemon state
   */
  saveState() {
    const state = {
      ...this.stats,
      last_updated: new Date().toISOString()
    };

    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
  }

  /**
   * Load daemon state
   */
  loadState() {
    if (fs.existsSync(STATE_FILE)) {
      const state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
      this.stats = {
        ...state,
        uptime_started: new Date() // Reset uptime on load
      };
      this.log('Loaded previous state');
    }
  }

  /**
   * Get current status
   */
  async getStatus() {
    await this.connect();

    // Get PostgreSQL stats
    const pgStats = await this.pgClient.query(`
      SELECT
        COUNT(*) FILTER (WHERE status = 'pending') as pending,
        COUNT(*) FILTER (WHERE status = 'verified') as verified,
        COUNT(*) FILTER (WHERE status = 'verified' AND (metadata->>'synced_to_graph')::boolean IS TRUE) as synced,
        COUNT(*) as total
      FROM knowledge.discoveries
    `);

    const dbStats = pgStats.rows[0];

    return {
      daemon: {
        running: this.running,
        uptime_ms: Date.now() - this.stats.uptime_started.getTime(),
        discoveries_synced: this.stats.discoveries_synced,
        sync_failures: this.stats.sync_failures,
        last_sync: this.stats.last_sync
      },
      database: {
        pending: parseInt(dbStats.pending),
        verified: parseInt(dbStats.verified),
        synced: parseInt(dbStats.synced),
        total: parseInt(dbStats.total),
        unsynced: parseInt(dbStats.verified) - parseInt(dbStats.synced)
      },
      orientdb: {
        available: this.orientdbAvailable
      }
    };
  }
}

// CLI
if (require.main === module) {
  const daemon = new KnowledgeSyncDaemon();

  const command = process.argv[2];

  (async () => {
    try {
      if (command === '--once') {
        // Run once and exit
        await daemon.runSyncCycle();
        await daemon.disconnect();
        process.exit(0);

      } else if (command === '--status') {
        // Show status
        const status = await daemon.getStatus();
        console.log(JSON.stringify(status, null, 2));
        await daemon.disconnect();
        process.exit(0);

      } else {
        // Start daemon
        daemon.loadState();

        // Graceful shutdown
        process.on('SIGINT', async () => {
          await daemon.stop();
          process.exit(0);
        });

        process.on('SIGTERM', async () => {
          await daemon.stop();
          process.exit(0);
        });

        await daemon.start();
      }

    } catch (err) {
      console.error('Fatal error:', err.message);
      await daemon.disconnect();
      process.exit(1);
    }
  })();
}

module.exports = { KnowledgeSyncDaemon };
