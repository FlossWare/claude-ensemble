#!/usr/bin/env node
/**
 * Prometheus Exporter for Consensus Monitoring
 * 
 * Exposes metrics for:
 * - consensus_decisions_total (counter)
 * - consensus_cost_usd (gauge by model)
 * - consensus_disagreement_score (histogram)
 * - consensus_quality_score (gauge by model)
 * - consensus_drift_alerts_total (counter by type)
 * 
 * Port: 9101 (to avoid conflict with node_exporter on 9100)
 */

const http = require('http');
const { Client } = require('pg');

const PORT = process.env.PROMETHEUS_PORT || 9101;
const PG_HOST = process.env.PG_HOST || 'laptop-01';
const PG_DATABASE = process.env.PG_DATABASE || 'learning';
const PG_USER = process.env.PG_USER || 'sfloess';

// Metrics cache with 30s TTL
let metricsCache = null;
let lastUpdate = 0;
const CACHE_TTL_MS = 30000;

// PostgreSQL connection
function getDB() {
  return new Client({
    host: PG_HOST,
    database: PG_DATABASE,
    user: PG_USER,
    port: 5432
  });
}

// Fetch metrics from PostgreSQL
async function fetchMetrics() {
  const now = Date.now();
  if (metricsCache && (now - lastUpdate) < CACHE_TTL_MS) {
    return metricsCache;
  }

  const db = getDB();
  await db.connect();

  try {
    const metrics = {
      decisions_total: 0,
      cost_by_model: {},
      disagreement_histogram: { le_01: 0, le_02: 0, le_03: 0, inf: 0 },
      quality_by_model: {},
      drift_alerts_total: 0
    };

    // 1. Total consensus decisions (last 24h)
    const decisionsResult = await db.query(
      `SELECT COUNT(*) as count FROM workflow.arbiter_decisions WHERE created_at >= NOW() - INTERVAL '24 hours'`
    );
    metrics.decisions_total = parseInt(decisionsResult.rows[0]?.count || 0);

    // 2. Cost by model (last 1h)
    const costResult = await db.query(
      `SELECT model, SUM(cost_usd) as total_cost 
       FROM workflow.worker_results 
       WHERE created_at >= NOW() - INTERVAL '1 hour'
       GROUP BY model`
    );
    for (const row of costResult.rows) {
      metrics.cost_by_model[row.model] = parseFloat(row.total_cost || 0);
    }

    // 3. Disagreement score histogram (last 7 days)
    const disagreementResult = await db.query(
      `SELECT disagreement_score FROM workflow.arbiter_decisions WHERE created_at >= NOW() - INTERVAL '7 days'`
    );
    for (const row of disagreementResult.rows) {
      const score = parseFloat(row.disagreement_score);
      if (score < 0.1) metrics.disagreement_histogram.le_01++;
      else if (score < 0.2) metrics.disagreement_histogram.le_02++;
      else if (score < 0.3) metrics.disagreement_histogram.le_03++;
      else metrics.disagreement_histogram.inf++;
    }

    // 4. Quality by model (last 7 days avg)
    const qualityResult = await db.query(
      `SELECT model, AVG(quality_score) as avg_quality 
       FROM workflow.worker_results 
       WHERE created_at >= NOW() - INTERVAL '7 days' AND quality_score IS NOT NULL
       GROUP BY model`
    );
    for (const row of qualityResult.rows) {
      metrics.quality_by_model[row.model] = parseFloat(row.avg_quality || 0);
    }

    // 5. Drift alerts (last 24h)
    const driftResult = await db.query(
      `SELECT COUNT(*) as count FROM monitoring.model_drift WHERE detected_at >= NOW() - INTERVAL '24 hours'`
    );
    metrics.drift_alerts_total = parseInt(driftResult.rows[0]?.count || 0);

    metricsCache = metrics;
    lastUpdate = now;

    return metrics;
  } finally {
    await db.end();
  }
}

// Format metrics in Prometheus exposition format
function formatPrometheusMetrics(metrics) {
  const lines = [];

  // consensus_decisions_total
  lines.push('# HELP consensus_decisions_total Total consensus decisions (24h window)');
  lines.push('# TYPE consensus_decisions_total counter');
  lines.push(`consensus_decisions_total ${metrics.decisions_total}`);
  lines.push('');

  // consensus_cost_usd
  lines.push('# HELP consensus_cost_usd Cost per model (1h window)');
  lines.push('# TYPE consensus_cost_usd gauge');
  for (const [model, cost] of Object.entries(metrics.cost_by_model)) {
    lines.push(`consensus_cost_usd{model="${model}"} ${cost}`);
  }
  lines.push('');

  // consensus_disagreement_score_bucket
  lines.push('# HELP consensus_disagreement_score Disagreement score distribution (7 days)');
  lines.push('# TYPE consensus_disagreement_score histogram');
  lines.push(`consensus_disagreement_score_bucket{le="0.1"} ${metrics.disagreement_histogram.le_01}`);
  lines.push(`consensus_disagreement_score_bucket{le="0.2"} ${metrics.disagreement_histogram.le_01 + metrics.disagreement_histogram.le_02}`);
  lines.push(`consensus_disagreement_score_bucket{le="0.3"} ${metrics.disagreement_histogram.le_01 + metrics.disagreement_histogram.le_02 + metrics.disagreement_histogram.le_03}`);
  lines.push(`consensus_disagreement_score_bucket{le="+Inf"} ${metrics.disagreement_histogram.le_01 + metrics.disagreement_histogram.le_02 + metrics.disagreement_histogram.le_03 + metrics.disagreement_histogram.inf}`);
  lines.push('');

  // consensus_quality_score
  lines.push('# HELP consensus_quality_score Quality score per model (7 day avg)');
  lines.push('# TYPE consensus_quality_score gauge');
  for (const [model, quality] of Object.entries(metrics.quality_by_model)) {
    lines.push(`consensus_quality_score{model="${model}"} ${quality}`);
  }
  lines.push('');

  // consensus_drift_alerts_total
  lines.push('# HELP consensus_drift_alerts_total Drift alerts detected (24h window)');
  lines.push('# TYPE consensus_drift_alerts_total counter');
  lines.push(`consensus_drift_alerts_total ${metrics.drift_alerts_total}`);
  lines.push('');

  return lines.join('\n');
}

// HTTP server
const server = http.createServer(async (req, res) => {
  if (req.url === '/metrics') {
    try {
      const metrics = await fetchMetrics();
      const output = formatPrometheusMetrics(metrics);
      
      res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4' });
      res.end(output);
    } catch (error) {
      console.error('Error fetching metrics:', error);
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('Error fetching metrics\n');
    }
  } else if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('OK\n');
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not found\n');
  }
});

server.listen(PORT, () => {
  console.log(`Prometheus Consensus Exporter listening on port ${PORT}`);
  console.log(`Metrics endpoint: http://localhost:${PORT}/metrics`);
  console.log(`Health endpoint: http://localhost:${PORT}/health`);
  console.log('');
  console.log('NOTE: Port 9100 is used by node_exporter, this exporter uses 9101');
});
