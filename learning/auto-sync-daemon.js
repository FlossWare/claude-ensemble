#!/usr/bin/env node
/**
 * Auto-Sync Daemon
 *
 * Continuously syncs PostgreSQL data to Neo4j
 * - Runs every 5 minutes
 * - Triggered on workflow completion
 * - Handles incremental updates
 */

import { getNeo4jAutoSync } from './neo4j-auto-sync.js';
import pg from 'pg';

const { Pool } = pg;

class AutoSyncDaemon {
  constructor() {
    this.neo4j = getNeo4jAutoSync();
    this.pool = new Pool({
      host: 'laptop-01',
      user: 'sfloess',
      database: 'learning',
    });
    this.syncInterval = 5 * 60 * 1000; // 5 minutes
    this.running = false;
  }

  async start() {
    console.log('🚀 Auto-Sync Daemon starting...');
    this.running = true;

    // Initial sync
    await this.performSync();

    // Periodic sync
    this.intervalId = setInterval(async () => {
      if (this.running) {
        await this.performSync();
      }
    }, this.syncInterval);

    console.log(`✅ Auto-Sync Daemon running (sync every ${this.syncInterval / 1000}s)`);
  }

  async performSync() {
    console.log(`\n[${new Date().toISOString()}] Starting Neo4j sync...`);

    try {
      const results = await this.neo4j.syncAll();

      console.log('✅ Sync complete:');
      console.log(`   - Tasks: ${results.tasks} nodes`);
      console.log(`   - Code entities: ${results.code} nodes`);
      console.log(`   - Research docs: ${results.research} nodes`);
      console.log(`   - Workers: ${results.workers} nodes`);
      console.log(`   - Workflows: ${results.workflows} nodes`);

      // Update integration status in orchestration queue
      await this.pool.query(`
        UPDATE orchestration.task_queue
        SET metadata = jsonb_set(
          metadata,
          '{integrations,neo4j}',
          jsonb_build_object(
            'sync_completed', true,
            'last_sync_at', NOW()::text,
            'nodes_synced', $1
          )
        )
        WHERE status = 'running'
      `, [results.tasks + results.code + results.research]);

    } catch (error) {
      console.error('❌ Sync error:', error.message);
    }
  }

  async stop() {
    console.log('Stopping Auto-Sync Daemon...');
    this.running = false;

    if (this.intervalId) {
      clearInterval(this.intervalId);
    }

    await this.neo4j.close();
    await this.pool.end();

    console.log('✅ Auto-Sync Daemon stopped');
  }

  /**
   * Trigger immediate sync (called on workflow completion)
   */
  async triggerSync() {
    if (this.running) {
      console.log('🔄 Triggering immediate Neo4j sync...');
      await this.performSync();
    }
  }
}

// Main
const daemon = new AutoSyncDaemon();

daemon.start().catch(console.error);

// Graceful shutdown
process.on('SIGINT', async () => {
  await daemon.stop();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await daemon.stop();
  process.exit(0);
});

export { AutoSyncDaemon };
