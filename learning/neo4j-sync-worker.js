#!/usr/bin/env node

/**
 * Neo4j Sync Background Worker
 *
 * Processes queued Neo4j sync jobs from orchestrator.work_queue.
 * Runs as a background daemon, polling for pending jobs.
 *
 * Features:
 * - Configurable poll interval
 * - Graceful shutdown on SIGINT/SIGTERM
 * - Automatic retry on failure (with exponential backoff)
 * - Logging to file and console
 *
 * Usage:
 *   node neo4j-sync-worker.js [--interval=5000] [--concurrency=1] [--log=/path/to/log]
 */

const { WorkflowGraphSync } = require('./workflow-graph-sync.js');
const { writeFileSync, appendFileSync, existsSync } = require('fs');
const { join } = require('path');
const { homedir } = require('os');

class Neo4jSyncWorker {
  constructor(config = {}) {
    this.graphSync = new WorkflowGraphSync(config.graphSync);
    this.pollInterval = config.pollInterval || 5000; // 5 seconds
    this.concurrency = config.concurrency || 1; // Process 1 job at a time
    this.logFile = config.logFile || join(homedir(), '.claude', 'learning', 'neo4j-sync-worker.log');
    this.running = false;
    this.activeJobs = new Set();
  }

  /**
   * Start the worker (daemon mode)
   */
  async start() {
    this.running = true;
    this.log('Neo4j Sync Worker started');
    this.log(`Poll interval: ${this.pollInterval}ms`);
    this.log(`Concurrency: ${this.concurrency}`);

    // Setup signal handlers for graceful shutdown
    process.on('SIGINT', () => this.shutdown('SIGINT'));
    process.on('SIGTERM', () => this.shutdown('SIGTERM'));

    // Main worker loop
    while (this.running) {
      try {
        await this.processNextJobs();
      } catch (err) {
        this.log(`Worker error: ${err.message}`, 'ERROR');
      }

      // Wait before next poll
      await this.sleep(this.pollInterval);
    }

    this.log('Neo4j Sync Worker stopped');
  }

  /**
   * Process next available jobs (up to concurrency limit)
   */
  async processNextJobs() {
    // Calculate how many jobs we can take
    const availableSlots = this.concurrency - this.activeJobs.size;
    if (availableSlots <= 0) {
      return; // All slots busy
    }

    // Fetch pending jobs
    const jobs = await this.fetchPendingJobs(availableSlots);
    if (jobs.length === 0) {
      return; // No work to do
    }

    this.log(`Processing ${jobs.length} jobs`);

    // Process jobs concurrently (up to concurrency limit)
    const processPromises = jobs.map(job => this.processJob(job));
    await Promise.all(processPromises);
  }

  /**
   * Fetch pending jobs from work_queue
   */
  async fetchPendingJobs(limit) {
    await this.graphSync.connect();

    const query = `
      SELECT id, payload, created_at
      FROM orchestrator.work_queue
      WHERE task_type = 'neo4j_sync'
        AND status = 'pending'
        AND scheduled_for <= NOW()
      ORDER BY priority DESC, created_at ASC
      LIMIT $1
    `;

    const result = await this.graphSync.pgClient.query(query, [limit]);
    return result.rows;
  }

  /**
   * Process a single job
   */
  async processJob(job) {
    const jobId = job.id;
    this.activeJobs.add(jobId);

    try {
      this.log(`Processing job ${jobId}`);

      // Process the job
      const result = await this.graphSync.processQueuedJob(jobId);

      this.log(`Job ${jobId} completed: ${result.status}`);

    } catch (err) {
      this.log(`Job ${jobId} failed: ${err.message}`, 'ERROR');

      // Check if we should retry
      const retryCount = await this.getRetryCount(jobId);
      if (retryCount < 3) {
        // Schedule retry with exponential backoff
        const backoffMs = Math.pow(2, retryCount) * 1000; // 1s, 2s, 4s
        await this.scheduleRetry(jobId, backoffMs, retryCount + 1);
        this.log(`Job ${jobId} scheduled for retry ${retryCount + 1}/3 in ${backoffMs}ms`);
      } else {
        this.log(`Job ${jobId} exceeded max retries, marking as failed`);
      }

    } finally {
      this.activeJobs.delete(jobId);
    }
  }

  /**
   * Get retry count for a job (stored in result JSONB)
   */
  async getRetryCount(jobId) {
    await this.graphSync.connect();

    const query = `
      SELECT COALESCE((result->>'retryCount')::int, 0) AS retry_count
      FROM orchestrator.work_queue
      WHERE id = $1
    `;

    const result = await this.graphSync.pgClient.query(query, [jobId]);
    return result.rows[0]?.retry_count || 0;
  }

  /**
   * Schedule a job for retry
   */
  async scheduleRetry(jobId, backoffMs, retryCount) {
    await this.graphSync.connect();

    const scheduledFor = new Date(Date.now() + backoffMs);

    const query = `
      UPDATE orchestrator.work_queue
      SET status = 'pending',
          scheduled_for = $2,
          result = jsonb_set(COALESCE(result, '{}'::jsonb), '{retryCount}', $3::text::jsonb)
      WHERE id = $1
    `;

    await this.graphSync.pgClient.query(query, [jobId, scheduledFor, retryCount]);
  }

  /**
   * Graceful shutdown
   */
  async shutdown(signal) {
    this.log(`Received ${signal}, shutting down gracefully...`);
    this.running = false;

    // Wait for active jobs to complete (max 30s)
    const maxWait = 30000;
    const startTime = Date.now();

    while (this.activeJobs.size > 0 && (Date.now() - startTime) < maxWait) {
      this.log(`Waiting for ${this.activeJobs.size} active jobs to complete...`);
      await this.sleep(1000);
    }

    if (this.activeJobs.size > 0) {
      this.log(`Force shutdown with ${this.activeJobs.size} jobs still running`, 'WARN');
    }

    await this.graphSync.disconnect();
    this.log('Shutdown complete');
    process.exit(0);
  }

  /**
   * Sleep helper
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Log message to file and console
   */
  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logLine = `[${timestamp}] [${level}] ${message}\n`;

    // Console
    console.log(logLine.trim());

    // File
    try {
      appendFileSync(this.logFile, logLine);
    } catch (err) {
      console.error(`Failed to write to log file: ${err.message}`);
    }
  }
}

// CLI usage
if (require.main === module) {
  // Parse command line arguments
  const args = process.argv.slice(2);
  const config = {};

  for (const arg of args) {
    if (arg.startsWith('--interval=')) {
      config.pollInterval = parseInt(arg.split('=')[1]);
    } else if (arg.startsWith('--concurrency=')) {
      config.concurrency = parseInt(arg.split('=')[1]);
    } else if (arg.startsWith('--log=')) {
      config.logFile = arg.split('=')[1];
    } else if (arg === '--skip-neo4j') {
      config.graphSync = { skipNeo4j: true };
    } else if (arg === '--help') {
      console.log('Usage: node neo4j-sync-worker.js [options]');
      console.log('');
      console.log('Options:');
      console.log('  --interval=<ms>       Poll interval in milliseconds (default: 5000)');
      console.log('  --concurrency=<n>     Max concurrent jobs (default: 1)');
      console.log('  --log=<path>          Log file path (default: ~/.claude/learning/neo4j-sync-worker.log)');
      console.log('  --skip-neo4j          Skip Neo4j sync (PostgreSQL only)');
      console.log('  --help                Show this help message');
      process.exit(0);
    }
  }

  // Start worker
  const worker = new Neo4jSyncWorker(config);

  (async () => {
    try {
      await worker.start();
    } catch (err) {
      console.error('Worker failed:', err.message);
      process.exit(1);
    }
  })();
}

module.exports = { Neo4jSyncWorker };
