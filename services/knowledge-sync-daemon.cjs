#!/usr/bin/env node

/**
 * Knowledge Sync Daemon
 *
 * Background service that:
 *   1. Polls PostgreSQL knowledge.discoveries for new verified discoveries
 *   2. Syncs verified discoveries to Neo4j knowledge graph
 *   3. Triggers fleet-wide distribution of high-value knowledge
 *   4. Monitors verification backlog and alerts on stale discoveries
 *
 * Architecture:
 *   knowledge.discoveries (PostgreSQL)
 *        ↓ (poll every 5 minutes)
 *   Filter: status='verified', not yet synced to Neo4j
 *        ↓
 *   Neo4j sync via workflow-graph-sync.js
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

// Neo4j is optional - only load if available
let neo4j = null;
try {
  neo4j = require('neo4j-driver');
} catch (err) {
  // Neo4j not installed - will run in PostgreSQL-only mode
  console.log('[knowledge-sync-daemon] Neo4j driver not installed - running in PostgreSQL-only mode');
}

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
const NEO4J_CONFIG = {
  uri: 'bolt://aio-01:7687',
  user: 'neo4j',
  password: process.env.NEO4J_PASSWORD || ''
};

class KnowledgeSyncDaemon {
  constructor() {
    this.pgClient = null;
    this.neo4jDriver = null;
    this.neo4jAvailable = false;
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

  async connect() {
    // Connect to PostgreSQL
    if (!this.pgClient) {
      this.pgClient = new Client(PG_CONFIG);
      await this.pgClient.connect();
      this.log('Connected to PostgreSQL');
    }

    // Connect to Neo4j (optional)
    if (!this.neo4jDriver) {
      try {
        this.neo4jDriver = neo4j.driver(
          NEO4J_CONFIG.uri,
          neo4j.auth.basic(NEO4J_CONFIG.user, NEO4J_CONFIG.password)
        );

        // Test connection
        const session = this.neo4jDriver.session();
        await session.run('RETURN 1');
        await session.close();

        this.neo4jAvailable = true;
        this.log('Connected to Neo4j');
      } catch (err) {
        this.log(`Neo4j unavailable: ${err.message}. PostgreSQL-only mode.`);
        this.neo4jAvailable = false;
      }
    }
  }

  async disconnect() {
    if (this.pgClient) {
      await this.pgClient.end();
      this.pgClient = null;
      this.log('Disconnected from PostgreSQL');
    }

    if (this.neo4jDriver) {
      await this.neo4jDriver.close();
      this.neo4jDriver = null;
      this.log('Disconnected from Neo4j');
    }
  }

  /**
   * Fetch verified discoveries not yet synced to Neo4j
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
        AND (metadata->>'synced_to_neo4j')::boolean IS NOT TRUE
      ORDER BY verified_at DESC
      LIMIT 100
    `);

    return result.rows;
  }

  /**
   * Sync discovery to Neo4j knowledge graph
   */
  async syncToNeo4j(discovery) {
    if (!this.neo4jAvailable) {
      this.log(`Neo4j unavailable, skipping sync for discovery ${discovery.id}`);
      return { status: 'skipped', reason: 'neo4j_unavailable' };
    }

    const session = this.neo4jDriver.session();

    try {
      await session.executeWrite(async (tx) => {
        // Create Discovery node
        await tx.run(`
          MERGE (d:Discovery {id: $id})
          SET d.type = $type,
              d.content = $content,
              d.confidence = $confidence,
              d.verifications = $verifications,
              d.createdAt = datetime($createdAt),
              d.verifiedAt = datetime($verifiedAt)
          RETURN d
        `, {
          id: discovery.id.toString(),
          type: discovery.discovery_type,
          content: discovery.content,
          confidence: discovery.confidence,
          verifications: discovery.verification_count,
          createdAt: discovery.created_at.toISOString(),
          verifiedAt: discovery.verified_at.toISOString()
        });

        // Create Worker node and relationship
        await tx.run(`
          MERGE (w:Worker {worker_id: $worker_id})
          WITH w
          MATCH (d:Discovery {id: $discovery_id})
          MERGE (w)-[r:DISCOVERED]->(d)
          SET r.createdAt = datetime($createdAt)
          RETURN r
        `, {
          worker_id: discovery.worker_id,
          discovery_id: discovery.id.toString(),
          createdAt: discovery.created_at.toISOString()
        });

        // Create verifier relationships
        for (const verifier of discovery.verified_by || []) {
          await tx.run(`
            MERGE (v:Worker {worker_id: $verifier_id})
            WITH v
            MATCH (d:Discovery {id: $discovery_id})
            MERGE (v)-[r:VERIFIED]->(d)
            SET r.createdAt = datetime()
            RETURN r
          `, {
            verifier_id: verifier,
            discovery_id: discovery.id.toString()
          });
        }
      });

      // Mark as synced in PostgreSQL
      await this.pgClient.query(`
        UPDATE knowledge.discoveries
        SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"synced_to_neo4j": true, "synced_at": "${new Date().toISOString()}"}'::jsonb
        WHERE id = $1
      `, [discovery.id]);

      this.log(`Synced discovery ${discovery.id} to Neo4j`);
      return { status: 'synced', discoveryId: discovery.id };

    } catch (err) {
      this.log(`Failed to sync discovery ${discovery.id}: ${err.message}`);
      return { status: 'failed', discoveryId: discovery.id, error: err.message };

    } finally {
      await session.close();
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
        const result = await this.syncToNeo4j(discovery);

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
        COUNT(*) FILTER (WHERE status = 'verified' AND (metadata->>'synced_to_neo4j')::boolean IS TRUE) as synced,
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
      neo4j: {
        available: this.neo4jAvailable
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
