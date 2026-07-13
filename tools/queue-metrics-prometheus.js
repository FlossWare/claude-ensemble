#!/usr/bin/env node

/**
 * Prometheus Exporter for Redis Queue Metrics
 *
 * Exposes metrics at :9091/metrics for Prometheus scraping
 */

const http = require('http');
const QueueMetrics = require('./queue-metrics');

const PORT = process.env.METRICS_PORT || 9091;

class PrometheusExporter {
  constructor() {
    this.metrics = new QueueMetrics();
  }

  /**
   * Convert snapshot to Prometheus format
   */
  async formatPrometheus() {
    const snapshot = await this.metrics.getSnapshot();
    const lines = [];

    // Queue depths
    lines.push('# HELP queue_depth Number of items in queue');
    lines.push('# TYPE queue_depth gauge');
    for (const [queue, depth] of Object.entries(snapshot.depths)) {
      lines.push(`queue_depth{queue="${queue}"} ${depth}`);
    }

    // Throughput - items per second (1min window)
    lines.push('# HELP queue_throughput_items_per_second Items processed per second');
    lines.push('# TYPE queue_throughput_items_per_second gauge');
    for (const [queue, tp] of Object.entries(snapshot.throughputs)) {
      lines.push(`queue_throughput_items_per_second{queue="${queue}",window="1min"} ${tp['1min'].itemsPerSec.toFixed(4)}`);
      lines.push(`queue_throughput_items_per_second{queue="${queue}",window="5min"} ${tp['5min'].itemsPerSec.toFixed(4)}`);
    }

    // Processing time - average
    lines.push('# HELP queue_processing_time_ms Average processing time in milliseconds');
    lines.push('# TYPE queue_processing_time_ms gauge');
    for (const [queue, tp] of Object.entries(snapshot.throughputs)) {
      lines.push(`queue_processing_time_ms{queue="${queue}",window="1min",stat="avg"} ${tp['1min'].avgProcessingMs.toFixed(2)}`);
      lines.push(`queue_processing_time_ms{queue="${queue}",window="1min",stat="min"} ${tp['1min'].minProcessingMs.toFixed(2)}`);
      lines.push(`queue_processing_time_ms{queue="${queue}",window="1min",stat="max"} ${tp['1min'].maxProcessingMs.toFixed(2)}`);
    }

    // Error rates
    lines.push('# HELP queue_error_total Total errors in time window');
    lines.push('# TYPE queue_error_total counter');
    for (const [queue, errors] of Object.entries(snapshot.errorRates)) {
      lines.push(`queue_error_total{queue="${queue}",window="5min"} ${errors.errorCount}`);
    }

    lines.push('# HELP queue_processed_total Total items processed in time window');
    lines.push('# TYPE queue_processed_total counter');
    for (const [queue, errors] of Object.entries(snapshot.errorRates)) {
      lines.push(`queue_processed_total{queue="${queue}",window="5min"} ${errors.totalProcessed}`);
    }

    lines.push('# HELP queue_error_rate Error rate percentage');
    lines.push('# TYPE queue_error_rate gauge');
    for (const [queue, errors] of Object.entries(snapshot.errorRates)) {
      const rate = parseFloat(errors.errorRate.replace('%', ''));
      lines.push(`queue_error_rate{queue="${queue}",window="5min"} ${rate.toFixed(2)}`);
    }

    // Worker counts
    lines.push('# HELP queue_workers_active Number of active workers');
    lines.push('# TYPE queue_workers_active gauge');
    lines.push(`queue_workers_active{queue="all"} ${snapshot.workers.total}`);
    for (const [queue, count] of Object.entries(snapshot.workers.byQueue)) {
      lines.push(`queue_workers_active{queue="${queue}"} ${count}`);
    }

    // Worker age (time since last heartbeat)
    lines.push('# HELP queue_worker_age_ms Time since last worker heartbeat');
    lines.push('# TYPE queue_worker_age_ms gauge');
    for (const worker of snapshot.workers.details) {
      lines.push(`queue_worker_age_ms{worker="${worker.id}",queue="${worker.queue}"} ${worker.age}`);
    }

    return lines.join('\n') + '\n';
  }

  /**
   * Start HTTP server
   */
  start() {
    const server = http.createServer(async (req, res) => {
      if (req.url === '/metrics') {
        try {
          const metrics = await this.formatPrometheus();
          res.writeHead(200, { 'Content-Type': 'text/plain' });
          res.end(metrics);
        } catch (error) {
          console.error('Error generating metrics:', error);
          res.writeHead(500, { 'Content-Type': 'text/plain' });
          res.end('Error generating metrics\n');
        }
      } else if (req.url === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok' }));
      } else {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not found. Try /metrics or /health\n');
      }
    });

    server.listen(PORT, () => {
      console.log(`Prometheus exporter listening on :${PORT}/metrics`);
      console.log(`Health check available at :${PORT}/health`);
    });

    // Graceful shutdown
    process.on('SIGTERM', async () => {
      console.log('SIGTERM received, shutting down...');
      server.close();
      await this.metrics.close();
      process.exit(0);
    });

    process.on('SIGINT', async () => {
      console.log('SIGINT received, shutting down...');
      server.close();
      await this.metrics.close();
      process.exit(0);
    });
  }
}

// CLI usage
if (require.main === module) {
  const exporter = new PrometheusExporter();
  exporter.start();
}

module.exports = PrometheusExporter;
