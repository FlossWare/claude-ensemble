#!/usr/bin/env node

/**
 * Redis Queue Monitoring Metrics
 *
 * Tracks:
 * - Queue depth (pending items)
 * - Throughput (items/sec, items/min)
 * - Error rates
 * - Processing times
 * - Worker health
 */

const Redis = require('ioredis');

const REDIS_SENTINEL = [
  { host: '192.168.1.25', port: 26379 },
  { host: '192.168.1.20', port: 26379 },
  { host: '192.168.1.23', port: 26379 }
];

const QUEUE_NAMES = {
  scrape: 'queue:scrape',
  storage: 'queue:storage',
  embedding: 'queue:embedding'
};

const METRICS_KEY_PREFIX = 'metrics:queue:';
const WORKER_KEY_PREFIX = 'worker:';

class QueueMetrics {
  constructor() {
    this.redis = new Redis({
      sentinels: REDIS_SENTINEL,
      name: 'mymaster',
      sentinelRetryStrategy: (times) => Math.min(times * 50, 2000)
    });
  }

  /**
   * Get queue depth for all queues
   */
  async getQueueDepths() {
    const depths = {};

    for (const [name, key] of Object.entries(QUEUE_NAMES)) {
      depths[name] = await this.redis.llen(key);
    }

    return depths;
  }

  /**
   * Record item processed (for throughput calculation)
   */
  async recordProcessed(queueName, processingTimeMs) {
    const now = Date.now();
    const metricsKey = `${METRICS_KEY_PREFIX}${queueName}`;

    // Store in sorted set with timestamp as score
    await this.redis.zadd(metricsKey, now, JSON.stringify({
      timestamp: now,
      processingTime: processingTimeMs
    }));

    // Keep only last hour of metrics
    const oneHourAgo = now - (60 * 60 * 1000);
    await this.redis.zremrangebyscore(metricsKey, '-inf', oneHourAgo);
  }

  /**
   * Record error
   */
  async recordError(queueName, error) {
    const now = Date.now();
    const errorKey = `${METRICS_KEY_PREFIX}${queueName}:errors`;

    await this.redis.zadd(errorKey, now, JSON.stringify({
      timestamp: now,
      error: error.message || String(error),
      stack: error.stack
    }));

    // Keep only last hour
    const oneHourAgo = now - (60 * 60 * 1000);
    await this.redis.zremrangebyscore(errorKey, '-inf', oneHourAgo);
  }

  /**
   * Get throughput metrics
   */
  async getThroughput(queueName, windowMs = 60000) {
    const now = Date.now();
    const windowStart = now - windowMs;
    const metricsKey = `${METRICS_KEY_PREFIX}${queueName}`;

    // Get all items processed in window
    const items = await this.redis.zrangebyscore(metricsKey, windowStart, now);

    const count = items.length;
    const windowSec = windowMs / 1000;

    // Calculate processing times
    const times = items.map(item => JSON.parse(item).processingTime);
    const avgTime = times.length > 0
      ? times.reduce((a, b) => a + b, 0) / times.length
      : 0;
    const minTime = times.length > 0 ? Math.min(...times) : 0;
    const maxTime = times.length > 0 ? Math.max(...times) : 0;

    return {
      count,
      itemsPerSec: count / windowSec,
      itemsPerMin: (count / windowSec) * 60,
      avgProcessingMs: avgTime,
      minProcessingMs: minTime,
      maxProcessingMs: maxTime
    };
  }

  /**
   * Get error rate
   */
  async getErrorRate(queueName, windowMs = 60000) {
    const now = Date.now();
    const windowStart = now - windowMs;
    const errorKey = `${METRICS_KEY_PREFIX}${queueName}:errors`;

    const errors = await this.redis.zrangebyscore(errorKey, windowStart, now);
    const errorCount = errors.length;

    // Get total processed in same window
    const throughput = await this.getThroughput(queueName, windowMs);
    const totalProcessed = throughput.count;

    const errorRate = totalProcessed > 0
      ? (errorCount / (totalProcessed + errorCount)) * 100
      : 0;

    return {
      errorCount,
      totalProcessed,
      errorRate: errorRate.toFixed(2) + '%',
      recentErrors: errors.slice(-5).map(e => JSON.parse(e))
    };
  }

  /**
   * Update worker heartbeat
   */
  async workerHeartbeat(workerId, queueName, status = 'active') {
    const workerKey = `${WORKER_KEY_PREFIX}${workerId}`;

    await this.redis.hmset(workerKey, {
      lastSeen: Date.now(),
      queue: queueName,
      status,
      pid: process.pid
    });

    // Expire after 60 seconds of no heartbeat
    await this.redis.expire(workerKey, 60);
  }

  /**
   * Get all active workers
   */
  async getActiveWorkers() {
    const pattern = `${WORKER_KEY_PREFIX}*`;
    const keys = await this.redis.keys(pattern);

    const workers = [];
    for (const key of keys) {
      const data = await this.redis.hgetall(key);
      if (data && Object.keys(data).length > 0) {
        workers.push({
          id: key.replace(WORKER_KEY_PREFIX, ''),
          ...data,
          lastSeen: parseInt(data.lastSeen),
          age: Date.now() - parseInt(data.lastSeen)
        });
      }
    }

    return workers;
  }

  /**
   * Get complete metrics snapshot
   */
  async getSnapshot() {
    const [depths, workers] = await Promise.all([
      this.getQueueDepths(),
      this.getActiveWorkers()
    ]);

    const throughputs = {};
    const errorRates = {};

    for (const queueName of Object.keys(QUEUE_NAMES)) {
      const [tp1min, tp5min, errors] = await Promise.all([
        this.getThroughput(queueName, 60000),
        this.getThroughput(queueName, 300000),
        this.getErrorRate(queueName, 300000)
      ]);

      throughputs[queueName] = { '1min': tp1min, '5min': tp5min };
      errorRates[queueName] = errors;
    }

    return {
      timestamp: new Date().toISOString(),
      depths,
      throughputs,
      errorRates,
      workers: {
        total: workers.length,
        byQueue: workers.reduce((acc, w) => {
          acc[w.queue] = (acc[w.queue] || 0) + 1;
          return acc;
        }, {}),
        details: workers
      }
    };
  }

  /**
   * Print metrics to console
   */
  async printMetrics() {
    const snapshot = await this.getSnapshot();

    console.log('\n=== Queue Metrics ===');
    console.log(`Timestamp: ${snapshot.timestamp}\n`);

    console.log('Queue Depths:');
    for (const [queue, depth] of Object.entries(snapshot.depths)) {
      console.log(`  ${queue}: ${depth} items`);
    }

    console.log('\nThroughput (1min / 5min):');
    for (const [queue, tp] of Object.entries(snapshot.throughputs)) {
      console.log(`  ${queue}:`);
      console.log(`    1min: ${tp['1min'].itemsPerMin.toFixed(2)} items/min (avg ${tp['1min'].avgProcessingMs.toFixed(0)}ms)`);
      console.log(`    5min: ${tp['5min'].itemsPerMin.toFixed(2)} items/min (avg ${tp['5min'].avgProcessingMs.toFixed(0)}ms)`);
    }

    console.log('\nError Rates (5min):');
    for (const [queue, errors] of Object.entries(snapshot.errorRates)) {
      console.log(`  ${queue}: ${errors.errorRate} (${errors.errorCount} errors / ${errors.totalProcessed} processed)`);
      if (errors.recentErrors.length > 0) {
        console.log(`    Recent: ${errors.recentErrors[0].error}`);
      }
    }

    console.log(`\nWorkers: ${snapshot.workers.total} active`);
    for (const [queue, count] of Object.entries(snapshot.workers.byQueue)) {
      console.log(`  ${queue}: ${count} workers`);
    }

    console.log('');
  }

  async close() {
    await this.redis.quit();
  }
}

// CLI usage
if (require.main === module) {
  const metrics = new QueueMetrics();

  const command = process.argv[2] || 'snapshot';

  (async () => {
    try {
      switch (command) {
        case 'snapshot':
          await metrics.printMetrics();
          break;

        case 'watch':
          const interval = parseInt(process.argv[3]) || 5000;
          console.log(`Watching metrics every ${interval}ms (Ctrl+C to stop)...`);
          setInterval(async () => {
            console.clear();
            await metrics.printMetrics();
          }, interval);
          break;

        case 'json':
          const snapshot = await metrics.getSnapshot();
          console.log(JSON.stringify(snapshot, null, 2));
          await metrics.close();
          break;

        default:
          console.log('Usage: queue-metrics.js [snapshot|watch|json] [interval_ms]');
          console.log('  snapshot - Print metrics once (default)');
          console.log('  watch [ms] - Continuously watch metrics (default 5000ms)');
          console.log('  json - Output JSON snapshot');
          await metrics.close();
      }
    } catch (error) {
      console.error('Error:', error);
      await metrics.close();
      process.exit(1);
    }
  })();
}

module.exports = QueueMetrics;
