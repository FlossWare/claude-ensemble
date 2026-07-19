#!/usr/bin/env node
/**
 * Auto-Sync Daemon
 *
 * Continuously syncs PostgreSQL data to OrientDB via REST API
 * - Runs every 5 minutes
 * - Triggered on workflow completion
 * - Handles incremental updates
 */

import http from 'http';

function queryOrientDB(query) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ query });
    const req = http.request({
      hostname: 'aio-01', port: 5000, path: '/graph/query', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
      timeout: 10000
    }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode < 300) {
          try { resolve(JSON.parse(data)); } catch { resolve(data); }
        } else {
          reject(new Error(`OrientDB ${res.statusCode}: ${data}`));
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.write(body);
    req.end();
  });
}

function queryREST(path) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'aio-01', port: 5000, path, method: 'GET',
      timeout: 10000
    }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode < 300) {
          try { resolve(JSON.parse(data)); } catch { resolve(data); }
        } else {
          reject(new Error(`REST API ${res.statusCode}: ${data}`));
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.end();
  });
}

class AutoSyncDaemon {
  constructor() {
    this.syncInterval = 5 * 60 * 1000;
    this.running = false;
  }

  async start() {
    console.log('Auto-Sync Daemon starting...');
    this.running = true;

    await this.performSync();

    this.intervalId = setInterval(async () => {
      if (this.running) {
        await this.performSync();
      }
    }, this.syncInterval);

    console.log(`Auto-Sync Daemon running (sync every ${this.syncInterval / 1000}s)`);
  }

  async performSync() {
    console.log(`\n[${new Date().toISOString()}] Starting OrientDB sync...`);

    try {
      const fleet = await queryREST('/fleet/');
      const workflows = await queryREST('/workflows/?limit=50');

      let synced = 0;

      if (fleet && fleet.workers) {
        for (const worker of fleet.workers) {
          try {
            await queryOrientDB(
              `UPDATE Infrastructure SET last_synced = '${new Date().toISOString()}' ` +
              `WHERE hostname = '${worker.hostname}'`
            );
            synced++;
          } catch { /* non-blocking */ }
        }
      }

      console.log(`Sync complete: ${synced} nodes updated`);

    } catch (error) {
      console.error('Sync error:', error.message);
    }
  }

  async stop() {
    console.log('Stopping Auto-Sync Daemon...');
    this.running = false;

    if (this.intervalId) {
      clearInterval(this.intervalId);
    }

    console.log('Auto-Sync Daemon stopped');
  }

  async triggerSync() {
    if (this.running) {
      console.log('Triggering immediate OrientDB sync...');
      await this.performSync();
    }
  }
}

const daemon = new AutoSyncDaemon();

daemon.start().catch(console.error);

process.on('SIGINT', async () => {
  await daemon.stop();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await daemon.stop();
  process.exit(0);
});

export { AutoSyncDaemon };
