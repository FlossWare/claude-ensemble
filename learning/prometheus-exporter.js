#!/usr/bin/env node
/**
 * Prometheus Exporter for Autonomous AI Learning System
 *
 * Exposes ai_learning_* metrics from learning.db for Grafana dashboards.
 * Runs on port 9090 by default (configurable via PORT env var).
 *
 * Metrics exposed:
 * - ai_learning_execution_total: Total executions by model/workflow/task/outcome
 * - ai_learning_quality_score: Quality score by model/task
 * - ai_learning_cost_usd: Cost in USD by model/workflow
 * - ai_learning_duration_seconds: Duration by model/task
 * - ai_learning_success_rate: Success rate by model/task
 * - ai_learning_consensus_score: Consensus score by model/task
 * - ai_learning_token_usage: Token usage by model/type
 * - ai_learning_model_selection_rate: Arbiter selection rate by model/task
 * - ai_learning_tuning_temperature: Optimal temperature by model/task
 * - ai_learning_tuning_quality: Tuned quality by model/task
 * - ai_learning_combo_quality: Combination quality by task/workers/arbiter
 * - ai_learning_combo_synergy: Synergy score by task/workers/arbiter
 * - ai_learning_lis_score: Learning Intelligence Score (composite 0-100)
 *
 * Usage:
 *   node prometheus-exporter.js
 *   PORT=9091 node prometheus-exporter.js
 */

const http = require('http');
const sqlite3 = require('sqlite3');
const { promisify } = require('util');
const path = require('path');

const PORT = process.env.PORT || 9090;
const DB_PATH = path.join(__dirname, 'db', 'learning.db');

class PrometheusExporter {
  constructor(dbPath) {
    this.dbPath = dbPath;
    this.db = null;
    this.lastUpdate = 0;
    this.cache = '';
    this.CACHE_TTL = 10000; // 10 seconds
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.db = new sqlite3.Database(this.dbPath, sqlite3.OPEN_READONLY, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  async query(sql, params = []) {
    return new Promise((resolve, reject) => {
      this.db.all(sql, params, (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });
  }

  escapeLabel(value) {
    if (value === null || value === undefined) return 'unknown';
    return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n');
  }

  formatMetric(name, labels, value, help = '', type = 'gauge') {
    let output = '';
    if (help) output += `# HELP ${name} ${help}\n`;
    if (type) output += `# TYPE ${name} ${type}\n`;

    const labelStr = Object.keys(labels).length > 0
      ? `{${Object.entries(labels).map(([k, v]) => `${k}="${this.escapeLabel(v)}"`).join(',')}}`
      : '';

    output += `${name}${labelStr} ${value}\n`;
    return output;
  }

  async generateMetrics() {
    const now = Date.now();
    if (now - this.lastUpdate < this.CACHE_TTL && this.cache) {
      return this.cache;
    }

    let metrics = '';

    try {
      // 1. Total executions by model/workflow/task/outcome
      const executions = await this.query(`
        SELECT model, workflow, task_type, outcome, COUNT(*) as count
        FROM execution_log
        GROUP BY model, workflow, task_type, outcome
      `);

      metrics += '# HELP ai_learning_execution_total Total executions by model, workflow, task_type, and outcome\n';
      metrics += '# TYPE ai_learning_execution_total counter\n';
      for (const row of executions) {
        metrics += this.formatMetric('ai_learning_execution_total', {
          model: row.model,
          workflow: row.workflow || 'unknown',
          task_type: row.task_type || 'unknown',
          outcome: row.outcome
        }, row.count, '', null);
      }

      // 2. Quality score by model/task
      const quality = await this.query(`
        SELECT model, task_type, AVG(quality_score) as avg_quality, COUNT(*) as sample_count
        FROM execution_log
        WHERE quality_score IS NOT NULL
        GROUP BY model, task_type
      `);

      metrics += '# HELP ai_learning_quality_score Average quality score by model and task_type\n';
      metrics += '# TYPE ai_learning_quality_score gauge\n';
      for (const row of quality) {
        metrics += this.formatMetric('ai_learning_quality_score', {
          model: row.model,
          task_type: row.task_type || 'unknown'
        }, row.avg_quality || 0, '', null);
      }

      // 3. Cost by model/workflow
      const cost = await this.query(`
        SELECT model, workflow, SUM(cost_usd) as total_cost, AVG(cost_usd) as avg_cost
        FROM execution_log
        GROUP BY model, workflow
      `);

      metrics += '# HELP ai_learning_cost_usd Total and average cost in USD by model and workflow\n';
      metrics += '# TYPE ai_learning_cost_usd gauge\n';
      for (const row of cost) {
        metrics += this.formatMetric('ai_learning_cost_usd', {
          model: row.model,
          workflow: row.workflow || 'unknown',
          aggregation: 'total'
        }, row.total_cost || 0, '', null);
        metrics += this.formatMetric('ai_learning_cost_usd', {
          model: row.model,
          workflow: row.workflow || 'unknown',
          aggregation: 'avg'
        }, row.avg_cost || 0, '', null);
      }

      // 4. Duration by model/task
      const duration = await this.query(`
        SELECT model, task_type, AVG(duration_ms) as avg_duration_ms
        FROM execution_log
        WHERE duration_ms > 0
        GROUP BY model, task_type
      `);

      metrics += '# HELP ai_learning_duration_seconds Average duration in seconds by model and task_type\n';
      metrics += '# TYPE ai_learning_duration_seconds gauge\n';
      for (const row of duration) {
        metrics += this.formatMetric('ai_learning_duration_seconds', {
          model: row.model,
          task_type: row.task_type || 'unknown'
        }, (row.avg_duration_ms || 0) / 1000, '', null);
      }

      // 5. Success rate by model/task
      const successRate = await this.query(`
        SELECT model, task_type,
               COUNT(*) as total,
               SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as success_count
        FROM execution_log
        GROUP BY model, task_type
      `);

      metrics += '# HELP ai_learning_success_rate Success rate by model and task_type\n';
      metrics += '# TYPE ai_learning_success_rate gauge\n';
      for (const row of successRate) {
        const rate = row.total > 0 ? row.success_count / row.total : 0;
        metrics += this.formatMetric('ai_learning_success_rate', {
          model: row.model,
          task_type: row.task_type || 'unknown'
        }, rate, '', null);
      }

      // 6. Consensus score by model/task
      const consensus = await this.query(`
        SELECT model, task_type, AVG(consensus_score) as avg_consensus
        FROM execution_log
        WHERE consensus_score IS NOT NULL
        GROUP BY model, task_type
      `);

      metrics += '# HELP ai_learning_consensus_score Average consensus score by model and task_type\n';
      metrics += '# TYPE ai_learning_consensus_score gauge\n';
      for (const row of consensus) {
        metrics += this.formatMetric('ai_learning_consensus_score', {
          model: row.model,
          task_type: row.task_type || 'unknown'
        }, row.avg_consensus || 0, '', null);
      }

      // 7. Token usage by model/type
      const tokens = await this.query(`
        SELECT model,
               SUM(input_tokens) as total_input,
               SUM(output_tokens) as total_output
        FROM execution_log
        GROUP BY model
      `);

      metrics += '# HELP ai_learning_token_usage Total token usage by model and token_type\n';
      metrics += '# TYPE ai_learning_token_usage counter\n';
      for (const row of tokens) {
        metrics += this.formatMetric('ai_learning_token_usage', {
          model: row.model,
          token_type: 'input'
        }, row.total_input || 0, '', null);
        metrics += this.formatMetric('ai_learning_token_usage', {
          model: row.model,
          token_type: 'output'
        }, row.total_output || 0, '', null);
      }

      // 8. Model selection rate (arbiter picks)
      const selectionRate = await this.query(`
        SELECT model, task_type,
               COUNT(*) as total,
               SUM(was_selected) as selected_count
        FROM execution_log
        WHERE model_role = 'worker'
        GROUP BY model, task_type
      `);

      metrics += '# HELP ai_learning_model_selection_rate Rate at which arbiter selects this model by task_type\n';
      metrics += '# TYPE ai_learning_model_selection_rate gauge\n';
      for (const row of selectionRate) {
        const rate = row.total > 0 ? row.selected_count / row.total : 0;
        metrics += this.formatMetric('ai_learning_model_selection_rate', {
          model: row.model,
          task_type: row.task_type || 'unknown'
        }, rate, '', null);
      }

      // 9. Tuning parameters from model_tuning table
      const tuning = await this.query(`
        SELECT model, task_type, optimal_params, avg_quality, avg_cost_usd,
               avg_duration_ms, sample_count, success_rate, selection_rate
        FROM model_tuning
      `);

      metrics += '# HELP ai_learning_tuning_temperature Optimal temperature by model and task_type\n';
      metrics += '# TYPE ai_learning_tuning_temperature gauge\n';
      metrics += '# HELP ai_learning_tuning_top_p Optimal top_p by model and task_type\n';
      metrics += '# TYPE ai_learning_tuning_top_p gauge\n';
      metrics += '# HELP ai_learning_tuning_max_tokens Optimal max_tokens by model and task_type\n';
      metrics += '# TYPE ai_learning_tuning_max_tokens gauge\n';
      metrics += '# HELP ai_learning_tuning_quality Average quality for tuned parameters\n';
      metrics += '# TYPE ai_learning_tuning_quality gauge\n';
      metrics += '# HELP ai_learning_tuning_sample_count Number of samples for tuning\n';
      metrics += '# TYPE ai_learning_tuning_sample_count gauge\n';

      for (const row of tuning) {
        const params = JSON.parse(row.optimal_params || '{}');
        const labels = {
          model: row.model,
          task_type: row.task_type || 'unknown'
        };

        if (params.temperature !== undefined) {
          metrics += this.formatMetric('ai_learning_tuning_temperature', labels, params.temperature, '', null);
        }
        if (params.top_p !== undefined) {
          metrics += this.formatMetric('ai_learning_tuning_top_p', labels, params.top_p, '', null);
        }
        if (params.max_tokens !== undefined) {
          metrics += this.formatMetric('ai_learning_tuning_max_tokens', labels, params.max_tokens, '', null);
        }

        metrics += this.formatMetric('ai_learning_tuning_quality', labels, row.avg_quality || 0, '', null);
        metrics += this.formatMetric('ai_learning_tuning_sample_count', labels, row.sample_count || 0, '', null);
      }

      // 10. Model combinations from model_combinations table
      const combos = await this.query(`
        SELECT task_type, worker_models, arbiter_model, avg_consensus, avg_quality,
               avg_cost_usd, avg_duration_ms, usage_count, synergy_score, diversity_score
        FROM model_combinations
      `);

      metrics += '# HELP ai_learning_combo_quality Average quality for model combination\n';
      metrics += '# TYPE ai_learning_combo_quality gauge\n';
      metrics += '# HELP ai_learning_combo_synergy Synergy score for model combination\n';
      metrics += '# TYPE ai_learning_combo_synergy gauge\n';
      metrics += '# HELP ai_learning_combo_consensus Average consensus for model combination\n';
      metrics += '# TYPE ai_learning_combo_consensus gauge\n';
      metrics += '# HELP ai_learning_combo_diversity Diversity score for model combination\n';
      metrics += '# TYPE ai_learning_combo_diversity gauge\n';
      metrics += '# HELP ai_learning_combo_usage_count Usage count for model combination\n';
      metrics += '# TYPE ai_learning_combo_usage_count counter\n';

      for (const row of combos) {
        const labels = {
          task_type: row.task_type || 'unknown',
          workers: row.worker_models || '[]',
          arbiter: row.arbiter_model || 'unknown'
        };

        metrics += this.formatMetric('ai_learning_combo_quality', labels, row.avg_quality || 0, '', null);
        metrics += this.formatMetric('ai_learning_combo_synergy', labels, row.synergy_score || 0, '', null);
        metrics += this.formatMetric('ai_learning_combo_consensus', labels, row.avg_consensus || 0, '', null);
        metrics += this.formatMetric('ai_learning_combo_diversity', labels, row.diversity_score || 0, '', null);
        metrics += this.formatMetric('ai_learning_combo_usage_count', labels, row.usage_count || 0, '', null);
      }

      // 11. LIS Score (Learning Intelligence Score) - Composite metric
      // Formula: 40% quality + 20% success rate + 20% cost efficiency + 20% speed efficiency
      const lisData = await this.query(`
        SELECT
          AVG(quality_score) as avg_quality,
          COUNT(CASE WHEN outcome = 'success' THEN 1 END) * 1.0 / COUNT(*) as success_rate,
          AVG(cost_usd) as avg_cost,
          AVG(duration_ms) as avg_duration
        FROM execution_log
        WHERE quality_score IS NOT NULL
      `);

      if (lisData.length > 0) {
        const d = lisData[0];
        const qualityComponent = (d.avg_quality || 0) * 40;
        const successComponent = (d.success_rate || 0) * 20;
        // Cost efficiency: inverse normalized (lower is better)
        const costEfficiency = d.avg_cost > 0 ? Math.max(0, 20 - (d.avg_cost * 100)) : 20;
        // Speed efficiency: inverse normalized (lower is better)
        const speedEfficiency = d.avg_duration > 0 ? Math.max(0, 20 - (d.avg_duration / 1000)) : 20;

        const lisScore = qualityComponent + successComponent + costEfficiency + speedEfficiency;

        metrics += '# HELP ai_learning_lis_score Learning Intelligence Score (0-100 composite metric)\n';
        metrics += '# TYPE ai_learning_lis_score gauge\n';
        metrics += this.formatMetric('ai_learning_lis_score', {}, Math.min(100, Math.max(0, lisScore)), '', null);
      }

      // 12. Error count by model
      const errors = await this.query(`
        SELECT model, COUNT(*) as error_count
        FROM execution_log
        WHERE error IS NOT NULL AND error != ''
        GROUP BY model
      `);

      metrics += '# HELP ai_learning_error_total Total errors by model\n';
      metrics += '# TYPE ai_learning_error_total counter\n';
      for (const row of errors) {
        metrics += this.formatMetric('ai_learning_error_total', {
          model: row.model
        }, row.error_count, '', null);
      }

      // 13. Active models count
      const activeModels = await this.query(`
        SELECT COUNT(DISTINCT model) as count
        FROM execution_log
        WHERE timestamp > datetime('now', '-7 days')
      `);

      metrics += '# HELP ai_learning_active_models_count Number of distinct models used in last 7 days\n';
      metrics += '# TYPE ai_learning_active_models_count gauge\n';
      if (activeModels.length > 0) {
        metrics += this.formatMetric('ai_learning_active_models_count', {}, activeModels[0].count, '', null);
      }

      this.cache = metrics;
      this.lastUpdate = now;
      return metrics;

    } catch (error) {
      console.error('Error generating metrics:', error);
      return `# Error generating metrics: ${error.message}\n`;
    }
  }

  async handleRequest(req, res) {
    if (req.url === '/metrics') {
      try {
        const metrics = await this.generateMetrics();
        res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4' });
        res.end(metrics);
      } catch (error) {
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end(`Error: ${error.message}\n`);
      }
    } else if (req.url === '/health' || req.url === '/') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'healthy',
        port: PORT,
        database: this.dbPath,
        uptime: process.uptime(),
        cache_age_ms: Date.now() - this.lastUpdate
      }));
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found\n');
    }
  }

  async start() {
    await this.connect();
    console.log(`✓ Connected to database: ${this.dbPath}`);

    const server = http.createServer((req, res) => this.handleRequest(req, res));

    server.listen(PORT, () => {
      console.log(`✓ Prometheus exporter listening on http://localhost:${PORT}/metrics`);
      console.log(`  Health check: http://localhost:${PORT}/health`);
      console.log(`  Cache TTL: ${this.CACHE_TTL}ms`);
    });

    // Graceful shutdown
    process.on('SIGTERM', () => {
      console.log('\nReceived SIGTERM, shutting down gracefully...');
      server.close(() => {
        if (this.db) this.db.close();
        process.exit(0);
      });
    });

    process.on('SIGINT', () => {
      console.log('\nReceived SIGINT, shutting down gracefully...');
      server.close(() => {
        if (this.db) this.db.close();
        process.exit(0);
      });
    });
  }
}

// Main
if (require.main === module) {
  const exporter = new PrometheusExporter(DB_PATH);
  exporter.start().catch(error => {
    console.error('Failed to start exporter:', error);
    process.exit(1);
  });
}

module.exports = PrometheusExporter;
