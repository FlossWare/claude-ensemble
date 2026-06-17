#!/usr/bin/env node

/**
 * Grafana JSON Datasource API
 *
 * Serves metrics from the AI Learning System for Grafana visualization.
 * Implements the Grafana JSON Datasource plugin interface.
 *
 * Usage:
 *   node grafana-api.js
 *   Listens on http://localhost:3000
 *
 * Grafana Configuration:
 *   Data Source Type: JSON API
 *   URL: http://localhost:3000
 *
 * Available Endpoints:
 *   GET /metrics/lis        - LIS score + trend
 *   GET /metrics/quality    - Quality metrics over time
 *   GET /metrics/cost       - Cost metrics + savings
 *   GET /metrics/discoveries - Recent learnings + tuning
 *   POST /search            - Grafana search API (returns metric names)
 *   POST /query             - Grafana query API (main data endpoint)
 */

const http = require('http');
const url = require('url');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const DB_PATH = path.resolve(__dirname, 'db', 'learning.db');
const PORT = 3000;

let db;

// Initialize database connection
function initDB() {
  return new Promise((resolve, reject) => {
    db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) {
        console.error('Database connection error:', err);
        reject(err);
      } else {
        console.log('Connected to learning.db');
        resolve(db);
      }
    });
  });
}

// Query helper
function dbQuery(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows || []);
    });
  });
}

// Get LIS Score (current + trend)
async function getLISMetrics() {
  try {
    const current = await dbQuery(`
      SELECT
        ROUND((
          COALESCE(AVG(quality_score), 0) * 40 +
          COALESCE(AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END), 0) * 20 +
          COALESCE(1.0 - MIN(1.0, AVG(cost_usd) / 0.50), 0) * 20 +
          COALESCE(1.0 - MIN(1.0, AVG(duration_ms) / 30000.0), 0) * 20
        ), 1) AS lis_score,
        COUNT(*) as samples,
        ROUND(AVG(quality_score) * 100, 1) as quality_pct,
        ROUND(AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END) * 100, 1) as success_rate_pct,
        ROUND(AVG(cost_usd), 6) as avg_cost_usd,
        ROUND(AVG(duration_ms) / 1000.0, 2) as avg_duration_sec
      FROM execution_log
      WHERE timestamp >= datetime('now', '-7 days')
        AND model NOT IN ('test-model', 'unknown', 'test')
    `);

    const trend = await dbQuery(`
      SELECT
        strftime('%Y-%m-%d', timestamp) as date,
        strftime('%s', MIN(timestamp)) * 1000 as timestamp,
        ROUND((
          COALESCE(AVG(quality_score), 0) * 40 +
          COALESCE(AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END), 0) * 20 +
          COALESCE(1.0 - MIN(1.0, AVG(cost_usd) / 0.50), 0) * 20 +
          COALESCE(1.0 - MIN(1.0, AVG(duration_ms) / 30000.0), 0) * 20
        ), 1) as lis_score
      FROM execution_log
      WHERE timestamp >= datetime('now', '-7 days')
        AND model NOT IN ('test-model', 'unknown', 'test')
      GROUP BY strftime('%Y-%m-%d', timestamp)
      ORDER BY date ASC
    `);

    return {
      current: current[0] || {},
      trend: trend
    };
  } catch (err) {
    console.error('Error fetching LIS metrics:', err);
    return { current: {}, trend: [] };
  }
}

// Get Quality metrics
async function getQualityMetrics() {
  try {
    const byModel = await dbQuery(`
      SELECT
        strftime('%s', MIN(timestamp)) * 1000 as timestamp,
        model,
        ROUND(AVG(quality_score), 4) as quality,
        COUNT(*) as executions
      FROM execution_log
      WHERE quality_score IS NOT NULL
        AND model NOT IN ('test-model', 'unknown', 'test')
        AND timestamp >= datetime('now', '-7 days')
      GROUP BY strftime('%Y-%m-%d', timestamp), model
      ORDER BY timestamp ASC
    `);

    const overall = await dbQuery(`
      SELECT
        strftime('%s', MIN(timestamp)) * 1000 as timestamp,
        ROUND(AVG(quality_score), 4) as quality,
        ROUND(MIN(quality_score), 4) as min_quality,
        ROUND(MAX(quality_score), 4) as max_quality,
        COUNT(*) as samples
      FROM execution_log
      WHERE quality_score IS NOT NULL
        AND model NOT IN ('test-model', 'unknown', 'test')
        AND timestamp >= datetime('now', '-7 days')
      GROUP BY strftime('%Y-%m-%d', timestamp)
      ORDER BY timestamp ASC
    `);

    return {
      by_model: byModel,
      overall: overall
    };
  } catch (err) {
    console.error('Error fetching quality metrics:', err);
    return { by_model: [], overall: [] };
  }
}

// Get Cost metrics
async function getCostMetrics() {
  try {
    const daily = await dbQuery(`
      SELECT
        strftime('%s', MIN(timestamp)) * 1000 as timestamp,
        strftime('%Y-%m-%d', timestamp) as date,
        ROUND(SUM(cost_usd), 4) as daily_cost,
        COUNT(*) as executions,
        ROUND(AVG(cost_usd), 6) as avg_cost_per_exec
      FROM execution_log
      WHERE model NOT IN ('test-model', 'unknown', 'test')
        AND timestamp >= datetime('now', '-30 days')
      GROUP BY strftime('%Y-%m-%d', timestamp)
      ORDER BY timestamp ASC
    `);

    const baseline = await dbQuery(`
      SELECT
        ROUND(AVG(cost_usd), 6) as baseline_cost_per_exec,
        ROUND(SUM(cost_usd), 4) as baseline_daily_cost
      FROM execution_log
      WHERE model NOT IN ('test-model', 'unknown', 'test')
        AND timestamp >= datetime('now', '-7 days')
        AND timestamp <= datetime('now', '-6 days')
    `);

    const summary = {
      total_7day: await dbQuery(`
        SELECT ROUND(SUM(cost_usd), 2) as total FROM execution_log
        WHERE model NOT IN ('test-model', 'unknown', 'test')
          AND timestamp >= datetime('now', '-7 days')
      `),
      avg_daily: await dbQuery(`
        SELECT ROUND(AVG(daily_cost), 2) as avg FROM (
          SELECT SUM(cost_usd) as daily_cost FROM execution_log
          WHERE model NOT IN ('test-model', 'unknown', 'test')
            AND timestamp >= datetime('now', '-7 days')
          GROUP BY strftime('%Y-%m-%d', timestamp)
        )
      `)
    };

    return {
      daily: daily,
      baseline: baseline[0] || {},
      summary: {
        total_7day: summary.total_7day[0]?.total || 0,
        avg_daily: summary.avg_daily[0]?.avg || 0
      }
    };
  } catch (err) {
    console.error('Error fetching cost metrics:', err);
    return { daily: [], baseline: {}, summary: {} };
  }
}

// Get Recent Discoveries (learnings)
async function getDiscoveries() {
  try {
    const tuning = await dbQuery(`
      SELECT
        model,
        task_type,
        ROUND(avg_quality, 3) as quality,
        ROUND(avg_cost_usd, 6) as cost_usd,
        sample_count,
        ROUND(success_rate * 100, 1) as success_rate_pct,
        ROUND(selection_rate * 100, 1) as selection_rate_pct,
        json_extract(optimal_params, '$.temperature') as temperature,
        json_extract(optimal_params, '$.top_p') as top_p,
        json_extract(optimal_params, '$.max_tokens') as max_tokens,
        updated_at
      FROM model_tuning
      ORDER BY updated_at DESC
      LIMIT 20
    `);

    const combinations = await dbQuery(`
      SELECT
        task_type,
        worker_models,
        arbiter_model,
        ROUND(avg_quality, 3) as quality,
        ROUND(avg_consensus, 3) as consensus,
        ROUND(synergy_score, 3) as synergy,
        ROUND(diversity_score, 3) as diversity,
        usage_count,
        ROUND(avg_cost_usd, 6) as cost_usd,
        updated_at
      FROM model_combinations
      ORDER BY updated_at DESC
      LIMIT 15
    `);

    const stats = {
      total_tuned: await dbQuery('SELECT COUNT(*) as count FROM model_tuning'),
      total_combos: await dbQuery('SELECT COUNT(*) as count FROM model_combinations'),
      best_quality: await dbQuery(`
        SELECT model, task_type, ROUND(avg_quality, 3) as quality
        FROM model_tuning ORDER BY avg_quality DESC LIMIT 1
      `),
      best_combo: await dbQuery(`
        SELECT worker_models, arbiter_model, ROUND(synergy_score, 3) as synergy
        FROM model_combinations ORDER BY synergy_score DESC LIMIT 1
      `)
    };

    return {
      tuning: tuning,
      combinations: combinations,
      stats: {
        total_tuned: stats.total_tuned[0]?.count || 0,
        total_combos: stats.total_combos[0]?.count || 0,
        best_quality: stats.best_quality[0] || {},
        best_combo: stats.best_combo[0] || {}
      }
    };
  } catch (err) {
    console.error('Error fetching discoveries:', err);
    return { tuning: [], combinations: [], stats: {} };
  }
}

// Grafana Search API
async function handleSearch(req, res) {
  const metrics = [
    { text: 'LIS Score', value: 'lis_score' },
    { text: 'LIS Trend', value: 'lis_trend' },
    { text: 'Quality Score', value: 'quality_score' },
    { text: 'Quality by Model', value: 'quality_by_model' },
    { text: 'Cost Daily', value: 'cost_daily' },
    { text: 'Cost Savings', value: 'cost_savings' },
    { text: 'Discoveries', value: 'discoveries' },
    { text: 'Model Tuning', value: 'model_tuning' },
    { text: 'Model Combinations', value: 'model_combinations' }
  ];

  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(metrics));
}

// Grafana Query API (main data endpoint)
async function handleQuery(req, res) {
  let body = '';

  req.on('data', chunk => body += chunk);
  req.on('end', async () => {
    try {
      const query = JSON.parse(body);
      const results = [];

      for (const target of query.targets || []) {
        const { target: targetName } = target;
        let data = null;

        switch (targetName) {
          case 'lis_score':
          case 'lis_trend': {
            const metrics = await getLISMetrics();
            data = {
              target: targetName === 'lis_score' ? 'LIS Score' : 'LIS Trend',
              datapoints: targetName === 'lis_score'
                ? [[metrics.current.lis_score || 0, Date.now()]]
                : metrics.trend.map(row => [row.lis_score, row.timestamp])
            };
            break;
          }

          case 'quality_score': {
            const metrics = await getQualityMetrics();
            data = {
              target: 'Quality Score (Overall)',
              datapoints: metrics.overall.map(row => [row.quality, row.timestamp])
            };
            break;
          }

          case 'quality_by_model': {
            const metrics = await getQualityMetrics();
            data = metrics.by_model.map(row => ({
              target: `Quality - ${row.model}`,
              datapoints: [[row.quality, row.timestamp]]
            }));
            results.push(...data);
            continue;
          }

          case 'cost_daily': {
            const metrics = await getCostMetrics();
            data = {
              target: 'Daily Cost ($)',
              datapoints: metrics.daily.map(row => [row.daily_cost, row.timestamp])
            };
            break;
          }

          case 'cost_savings': {
            const metrics = await getCostMetrics();
            data = {
              target: 'Cost Savings',
              datapoints: metrics.daily.map((row, idx, arr) => {
                const baseline = metrics.baseline.baseline_daily_cost || 0;
                const savings = baseline - row.daily_cost;
                return [savings, row.timestamp];
              })
            };
            break;
          }

          case 'discoveries': {
            const discoveries = await getDiscoveries();
            data = {
              target: 'Recent Learnings',
              type: 'table',
              rows: [
                ['Model', 'Task', 'Quality', 'Cost', 'Samples', 'Success %', 'Temp', 'Updated'],
                ...discoveries.tuning.map(d => [
                  d.model,
                  d.task_type,
                  d.quality,
                  d.cost_usd,
                  d.sample_count,
                  d.success_rate_pct,
                  d.temperature,
                  d.updated_at
                ])
              ]
            };
            break;
          }

          case 'model_tuning': {
            const discoveries = await getDiscoveries();
            data = discoveries.tuning;
            break;
          }

          case 'model_combinations': {
            const discoveries = await getDiscoveries();
            data = discoveries.combinations;
            break;
          }

          default:
            data = { target: 'unknown', datapoints: [] };
        }

        if (data && !Array.isArray(data)) {
          results.push(data);
        } else if (Array.isArray(data)) {
          results.push(...data);
        }
      }

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(results));
    } catch (err) {
      console.error('Query error:', err);
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  });
}

// HTTP Request Handler
async function handleRequest(req, res) {
  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;

  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  try {
    // Grafana API endpoints
    if (pathname === '/search' && req.method === 'POST') {
      await handleSearch(req, res);
    } else if (pathname === '/query' && req.method === 'POST') {
      await handleQuery(req, res);
    }
    // REST API endpoints
    else if (pathname === '/metrics/lis' && req.method === 'GET') {
      const data = await getLISMetrics();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } else if (pathname === '/metrics/quality' && req.method === 'GET') {
      const data = await getQualityMetrics();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } else if (pathname === '/metrics/cost' && req.method === 'GET') {
      const data = await getCostMetrics();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } else if (pathname === '/metrics/discoveries' && req.method === 'GET') {
      const data = await getDiscoveries();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    }
    // Health check
    else if (pathname === '/health' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', db: 'connected' }));
    }
    // Default
    else {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        error: 'Not Found',
        endpoints: [
          'GET /metrics/lis',
          'GET /metrics/quality',
          'GET /metrics/cost',
          'GET /metrics/discoveries',
          'POST /search (Grafana)',
          'POST /query (Grafana)',
          'GET /health'
        ]
      }));
    }
  } catch (err) {
    console.error('Request error:', err);
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: err.message }));
  }
}

// Start server
async function startServer() {
  try {
    await initDB();

    const server = http.createServer(handleRequest);
    server.listen(PORT, '0.0.0.0', () => {
      console.log(`Grafana API server running on http://0.0.0.0:${PORT}`);
      console.log(`Database: ${DB_PATH}`);
      console.log(`\nEndpoints:`);
      console.log(`  REST API:`);
      console.log(`    GET http://localhost:${PORT}/metrics/lis`);
      console.log(`    GET http://localhost:${PORT}/metrics/quality`);
      console.log(`    GET http://localhost:${PORT}/metrics/cost`);
      console.log(`    GET http://localhost:${PORT}/metrics/discoveries`);
      console.log(`  Grafana Plugin:`);
      console.log(`    POST http://localhost:${PORT}/search`);
      console.log(`    POST http://localhost:${PORT}/query`);
      console.log(`  Health:`);
      console.log(`    GET http://localhost:${PORT}/health`);
    });

    // Graceful shutdown
    process.on('SIGINT', () => {
      console.log('\nShutting down...');
      server.close();
      db.close();
      process.exit(0);
    });
  } catch (err) {
    console.error('Failed to start server:', err);
    process.exit(1);
  }
}

// Run server if called directly
if (require.main === module) {
  startServer();
}

module.exports = { getLISMetrics, getQualityMetrics, getCostMetrics, getDiscoveries };
