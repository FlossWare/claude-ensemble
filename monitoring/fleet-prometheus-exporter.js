#!/usr/bin/env node
/**
 * Fleet Prometheus Exporter
 *
 * Unified Prometheus exporter that aggregates metrics from all three fleet
 * monitoring subsystems:
 *   - FleetActivityCollector (fleet-activity-collector.js)
 *   - FleetResourceMonitor  (fleet-resource-monitor.js)
 *   - WorkflowNodeTracker   (workflow-node-tracker.js)
 *
 * Exposed metrics (Prometheus format):
 *   fleet_node_cpu_usage{node}           - CPU usage % per node
 *   fleet_node_ram_usage{node}           - RAM usage % per node
 *   fleet_active_workflows               - Number of active workflows
 *   fleet_workflow_duration{workflow,phase} - Workflow duration in seconds
 *   fleet_cost_per_node{node,model}      - Estimated cost in USD per node
 *   fleet_ai_model_assignments{model,node,status} - Model-to-node assignment state
 *
 * Additional metrics derived from collectors:
 *   fleet_node_load_1m{node}             - 1-minute load average per node
 *   fleet_node_load_5m{node}             - 5-minute load average per node
 *   fleet_node_load_15m{node}            - 15-minute load average per node
 *   fleet_node_ram_total_bytes{node}     - Total RAM in bytes per node
 *   fleet_node_ram_used_bytes{node}      - Used RAM in bytes per node
 *   fleet_node_ram_available_bytes{node} - Available RAM in bytes per node
 *   fleet_node_cpu_cores{node}           - CPU core count per node
 *   fleet_node_reachable{node}           - Whether the node is reachable (0/1)
 *   fleet_node_claude_processes{node}    - Number of claude/agent processes
 *   fleet_node_ssh_sessions{node}        - Number of SSH sessions
 *   fleet_dispatcher_up                  - Whether the fleet dispatcher is available
 *   fleet_pending_jobs                   - Jobs pending in dispatcher queue
 *   fleet_total_workflows                - Total tracked workflows
 *   fleet_workflow_status{workflow,status} - Status of each tracked workflow
 *   fleet_workflow_agents{workflow}       - Number of agents per workflow
 *   fleet_workflow_nodes{workflow}        - Number of nodes per workflow
 *   fleet_model_executions_total{model}  - Executions per model
 *   fleet_model_error_rate{model}        - Error rate per model
 *   fleet_nfs_inflight_jobs              - NFS in-flight jobs
 *   fleet_nfs_recent_completions         - Recently completed NFS jobs
 *   fleet_exporter_collection_duration_seconds - Scrape duration
 *   fleet_exporter_last_collection_timestamp   - Last successful collection
 *
 * Usage:
 *   node monitoring/fleet-prometheus-exporter.js [--port 9091] [--interval 60]
 *   node monitoring/fleet-prometheus-exporter.js --once
 *
 * Endpoints:
 *   /metrics  - Prometheus-compatible metrics
 *   /health   - Health check (200 OK)
 *   /status   - JSON summary of latest collection
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import http from 'http';
import { FleetActivityCollector } from './fleet-activity-collector.js';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const HOME = process.env.HOME || '/home/sfloess';
const DEFAULT_PORT = 9091;
const DEFAULT_INTERVAL_SEC = 60;

// Cost estimation per model (USD per 1K tokens, averaged input+output)
const MODEL_COST_PER_1K = {
  fable:           0.045,   // high-end
  opus:            0.045,
  sonnet:          0.009,
  haiku:           0.001,
  gemini:          0.001,
  'gpt-4o':        0.010,
  'llama-70b-fast': 0.001,
  'qwen-coder-32b': 0.001,
  'cerebras-120b':  0.002,
};

// Estimated tokens per minute of claude process runtime
const EST_TOKENS_PER_MINUTE = 2000;

// Fleet topology (duplicated from fleet-activity-collector.js for cost calculation)
const FLEET_NODES = [
  { hostname: 'laptop-01', role: 'heavy',      arch: 'amd64', models: ['fable', 'opus'] },
  { hostname: 'server-01', role: 'fast',        arch: 'amd64', models: ['sonnet', 'haiku', 'llama-70b-fast'] },
  { hostname: 'server-02', role: 'code',        arch: 'amd64', models: ['gpt-4o', 'qwen-coder-32b'] },
  { hostname: 'server-03', role: 'heavy',       arch: 'amd64', models: ['gemini', 'cerebras-120b'] },
  { hostname: 'aio-01',    role: 'passive',     arch: 'amd64', models: [] },
  { hostname: 'pi-02',     role: 'coordinator', arch: 'arm64', models: [] },
];

// Workflow-node-tracker data file
const TRACKER_DATA_PATH = path.join(
  HOME, '.claude', 'repos', 'claude-global-skills', 'memory',
  'workflow-node-tracking.json'
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Safely load JSON from a file path, returning null on any error.
 */
function loadJson(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * Escape a Prometheus label value (backslash, double-quote, newline).
 */
function escapeLabelValue(val) {
  if (val == null) return '';
  return String(val)
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n');
}

// ---------------------------------------------------------------------------
// MetricRegistry -- accumulates HELP/TYPE/samples and serializes to text
// ---------------------------------------------------------------------------
class MetricRegistry {
  constructor() {
    this._declared = new Set();
    this._lines = [];
  }

  /**
   * Declare and emit a metric sample.
   * @param {string} name     Metric name
   * @param {string} help     HELP string (only emitted on first occurrence)
   * @param {string} type     gauge | counter | histogram | summary
   * @param {number} value    Numeric value
   * @param {Object} [labels] Label key-value pairs
   */
  add(name, help, type, value, labels = {}) {
    if (!this._declared.has(name)) {
      this._lines.push(`# HELP ${name} ${help}`);
      this._lines.push(`# TYPE ${name} ${type}`);
      this._declared.add(name);
    }

    const labelStr = Object.keys(labels).length > 0
      ? '{' + Object.entries(labels)
          .map(([k, v]) => `${k}="${escapeLabelValue(v)}"`)
          .join(',') + '}'
      : '';

    this._lines.push(`${name}${labelStr} ${value}`);
  }

  serialize() {
    return this._lines.join('\n') + '\n';
  }
}

// ---------------------------------------------------------------------------
// FleetPrometheusExporter
// ---------------------------------------------------------------------------
export class FleetPrometheusExporter {
  /**
   * @param {Object} config
   * @param {number} config.port          - HTTP port (default 9091)
   * @param {number} config.intervalSec   - Collection interval (default 60)
   * @param {Object} config.collector     - Optional pre-constructed FleetActivityCollector
   */
  constructor(config = {}) {
    this.port = config.port || DEFAULT_PORT;
    this.intervalSec = config.intervalSec || DEFAULT_INTERVAL_SEC;
    this.collector = config.collector || new FleetActivityCollector();

    this._lastCollectionTime = null;
    this._lastCollectionDuration = 0;
    this._collectCount = 0;
    this._errorCount = 0;
    this._server = null;
    this._intervalId = null;
  }

  // -------------------------------------------------------------------------
  // Collect from all sources
  // -------------------------------------------------------------------------

  /**
   * Run a full collection cycle: activity collector + tracker data.
   * Returns the activity snapshot for immediate use.
   */
  async collect() {
    const start = Date.now();
    try {
      const snapshot = await this.collector.collect();
      this._lastCollectionTime = Date.now();
      this._lastCollectionDuration = (Date.now() - start) / 1000;
      this._collectCount++;
      return snapshot;
    } catch (err) {
      this._errorCount++;
      console.error(`[fleet-prometheus-exporter] Collection error: ${err.message}`);
      return null;
    }
  }

  // -------------------------------------------------------------------------
  // Generate Prometheus text
  // -------------------------------------------------------------------------

  /**
   * Build the full /metrics payload.
   */
  generateMetrics() {
    const reg = new MetricRegistry();
    const snapshot = this.collector.getLatestSnapshot();
    const trackerData = loadJson(TRACKER_DATA_PATH);

    // -- Exporter meta metrics --
    reg.add(
      'fleet_exporter_collection_duration_seconds',
      'Duration of the last data collection cycle in seconds',
      'gauge',
      this._lastCollectionDuration
    );
    reg.add(
      'fleet_exporter_last_collection_timestamp',
      'Unix timestamp of the last successful collection',
      'gauge',
      this._lastCollectionTime ? this._lastCollectionTime / 1000 : 0
    );
    reg.add(
      'fleet_exporter_collections_total',
      'Total number of collection cycles performed',
      'counter',
      this._collectCount
    );
    reg.add(
      'fleet_exporter_errors_total',
      'Total number of collection errors',
      'counter',
      this._errorCount
    );

    if (!snapshot) {
      // No data yet -- return meta metrics only
      return reg.serialize();
    }

    // =====================================================================
    // 1. Per-node resource metrics (from activity collector node data)
    // =====================================================================
    for (const [hostname, activity] of Object.entries(snapshot.nodes || {})) {
      const nodeLabels = { node: hostname };

      reg.add(
        'fleet_node_reachable',
        'Whether the fleet node is reachable via SSH (1=yes, 0=no)',
        'gauge',
        activity.reachable ? 1 : 0,
        nodeLabels
      );

      if (!activity.reachable || !activity.resources) continue;

      const res = activity.resources;

      // -- fleet_node_cpu_usage --
      // CPU usage approximated from load average / cores
      const cpuCores = res.cpuCores || 1;
      const cpuUsagePct = Math.min(100, (res.loadAvg[0] / cpuCores) * 100);
      reg.add(
        'fleet_node_cpu_usage',
        'Estimated CPU usage percentage per node',
        'gauge',
        parseFloat(cpuUsagePct.toFixed(2)),
        nodeLabels
      );

      // Load averages
      reg.add(
        'fleet_node_load_1m',
        'One-minute load average per node',
        'gauge',
        res.loadAvg[0],
        nodeLabels
      );
      reg.add(
        'fleet_node_load_5m',
        'Five-minute load average per node',
        'gauge',
        res.loadAvg[1],
        nodeLabels
      );
      reg.add(
        'fleet_node_load_15m',
        'Fifteen-minute load average per node',
        'gauge',
        res.loadAvg[2],
        nodeLabels
      );

      // CPU cores
      reg.add(
        'fleet_node_cpu_cores',
        'Number of CPU cores per node',
        'gauge',
        cpuCores,
        nodeLabels
      );

      // -- fleet_node_ram_usage --
      const memUsedPct = res.memTotalMb > 0
        ? (res.memUsedMb / res.memTotalMb) * 100
        : 0;
      reg.add(
        'fleet_node_ram_usage',
        'RAM usage percentage per node',
        'gauge',
        parseFloat(memUsedPct.toFixed(2)),
        nodeLabels
      );

      // RAM in bytes for Grafana byte-format panels
      reg.add(
        'fleet_node_ram_total_bytes',
        'Total RAM in bytes per node',
        'gauge',
        res.memTotalMb * 1024 * 1024,
        nodeLabels
      );
      reg.add(
        'fleet_node_ram_used_bytes',
        'Used RAM in bytes per node',
        'gauge',
        res.memUsedMb * 1024 * 1024,
        nodeLabels
      );
      reg.add(
        'fleet_node_ram_available_bytes',
        'Available RAM in bytes per node',
        'gauge',
        res.memAvailMb * 1024 * 1024,
        nodeLabels
      );

      // Process and session counts
      reg.add(
        'fleet_node_claude_processes',
        'Number of claude/agent/workflow processes on the node',
        'gauge',
        activity.claudeProcesses?.length || 0,
        nodeLabels
      );
      reg.add(
        'fleet_node_ssh_sessions',
        'Number of SSH sessions on the node',
        'gauge',
        activity.sshSessions?.length || 0,
        nodeLabels
      );
    }

    // =====================================================================
    // 2. Dispatcher metrics
    // =====================================================================
    reg.add(
      'fleet_dispatcher_up',
      'Whether the fleet dispatcher is available (1=yes, 0=no)',
      'gauge',
      snapshot.dispatcher?.available ? 1 : 0
    );

    reg.add(
      'fleet_pending_jobs',
      'Number of jobs pending in the dispatcher queue',
      'gauge',
      snapshot.summary?.pendingJobs || 0
    );

    // Per-server dispatcher view
    if (snapshot.dispatcher?.available && snapshot.dispatcher.servers) {
      for (const srv of snapshot.dispatcher.servers) {
        const srvLabels = { node: srv.hostname || srv.instance };
        reg.add(
          'fleet_dispatcher_node_cpu_pct',
          'CPU usage reported by dispatcher per node',
          'gauge',
          srv.cpuPct || 0,
          srvLabels
        );
        reg.add(
          'fleet_dispatcher_node_avail_ram_gb',
          'Available RAM in GB reported by dispatcher per node',
          'gauge',
          srv.availRamGb || 0,
          srvLabels
        );
        reg.add(
          'fleet_dispatcher_node_overloaded',
          'Whether the dispatcher considers this node overloaded (1=yes)',
          'gauge',
          srv.isOverloaded ? 1 : 0,
          srvLabels
        );
        reg.add(
          'fleet_dispatcher_node_active_jobs',
          'Active jobs on this node as seen by dispatcher',
          'gauge',
          srv.activeJobs || 0,
          srvLabels
        );
      }
    }

    // =====================================================================
    // 3. Workflow metrics
    // =====================================================================

    // -- fleet_active_workflows --
    const activeWorkflows = snapshot.summary?.activeWorkflows || 0;
    reg.add(
      'fleet_active_workflows',
      'Number of currently running workflows across the fleet',
      'gauge',
      activeWorkflows
    );

    reg.add(
      'fleet_total_workflows',
      'Total number of tracked workflows in current snapshot',
      'gauge',
      snapshot.summary?.totalWorkflows || 0
    );

    // Per-workflow details from workflowNodeMap
    for (const [wfId, wf] of Object.entries(snapshot.workflowNodeMap || {})) {
      const wfLabels = { workflow: wfId };

      // -- fleet_workflow_duration --
      // Duration from startTime to lastActivity (or now if running)
      if (wf.startTime) {
        const startMs = new Date(wf.startTime).getTime();
        const endMs = wf.isRunning
          ? Date.now()
          : (wf.lastActivity ? new Date(wf.lastActivity).getTime() : Date.now());
        const durationSec = Math.max(0, (endMs - startMs) / 1000);

        reg.add(
          'fleet_workflow_duration',
          'Workflow duration in seconds (running or completed)',
          'gauge',
          parseFloat(durationSec.toFixed(2)),
          { workflow: wfId, phase: wf.phase || 'unknown' }
        );
      }

      // Workflow status
      reg.add(
        'fleet_workflow_status',
        'Workflow running status (1=running, 0=completed)',
        'gauge',
        wf.isRunning ? 1 : 0,
        { workflow: wfId, status: wf.isRunning ? 'running' : 'completed' }
      );

      // Agents per workflow
      reg.add(
        'fleet_workflow_agents',
        'Number of agents spawned for this workflow',
        'gauge',
        wf.agentCount || 0,
        wfLabels
      );

      // Nodes per workflow
      reg.add(
        'fleet_workflow_nodes',
        'Number of fleet nodes participating in this workflow',
        'gauge',
        wf.nodes?.length || 0,
        wfLabels
      );
    }

    // =====================================================================
    // 4. Model assignment metrics
    // =====================================================================

    // -- fleet_ai_model_assignments --
    for (const [model, assignment] of Object.entries(snapshot.modelAssignments || {})) {
      const server = assignment.activeOnServer || assignment.configuredServer || 'none';
      const isActive = assignment.activeOnServer ? 1 : 0;
      const status = isActive ? 'active' : 'configured';

      reg.add(
        'fleet_ai_model_assignments',
        'AI model assignment to fleet nodes (1=active, 0=configured only)',
        'gauge',
        isActive,
        { model, node: server, status }
      );
    }

    // =====================================================================
    // 5. Cost-per-node estimation
    // =====================================================================

    // -- fleet_cost_per_node --
    // Estimate cost based on running claude processes and their models
    for (const [hostname, activity] of Object.entries(snapshot.nodes || {})) {
      if (!activity.reachable) continue;

      // Find models running on this node
      const modelsOnNode = new Set();
      for (const proc of (activity.claudeProcesses || [])) {
        const modelMatch = proc.command.match(
          /--model\s+(\S+)|model[=:]\s*["']?(\w+)/i
        );
        if (modelMatch) {
          modelsOnNode.add(modelMatch[1] || modelMatch[2]);
        }
      }

      // Also include models from static config
      const nodeConfig = FLEET_NODES.find(n => n.hostname === hostname);
      if (nodeConfig) {
        for (const m of nodeConfig.models) {
          // Only add configured models if there are active processes
          if ((activity.claudeProcesses || []).length > 0) {
            modelsOnNode.add(m);
          }
        }
      }

      // If no models detected but processes exist, use 'unknown'
      if (modelsOnNode.size === 0 && (activity.claudeProcesses || []).length > 0) {
        modelsOnNode.add('unknown');
      }

      for (const model of modelsOnNode) {
        // Estimate cost: processes * estimated_tokens_per_minute * cost_per_1k
        const numProcesses = (activity.claudeProcesses || []).length;
        const costPer1k = MODEL_COST_PER_1K[model] || 0.005;
        // Estimate cost since last collection interval
        const intervalMinutes = this.intervalSec / 60;
        const estimatedTokens = numProcesses * EST_TOKENS_PER_MINUTE * intervalMinutes;
        const estimatedCost = (estimatedTokens / 1000) * costPer1k;

        reg.add(
          'fleet_cost_per_node',
          'Estimated cost in USD per collection interval per node and model',
          'gauge',
          parseFloat(estimatedCost.toFixed(6)),
          { node: hostname, model }
        );
      }
    }

    // =====================================================================
    // 6. Workflow-Node Tracker metrics (from persisted tracking data)
    // =====================================================================
    if (trackerData && trackerData.records) {
      const records = trackerData.records;

      // Per-model execution counts and error rates
      for (const [model, recordIds] of Object.entries(trackerData.model_index || {})) {
        const modelRecords = records.filter(r => recordIds.includes(r.id));
        const errorCount = modelRecords.filter(r => r.status === 'error').length;
        const errorRate = modelRecords.length > 0 ? errorCount / modelRecords.length : 0;

        reg.add(
          'fleet_model_executions_total',
          'Total workflow executions tracked per model',
          'counter',
          modelRecords.length,
          { model }
        );
        reg.add(
          'fleet_model_error_rate',
          'Error rate for workflow executions per model (0-1)',
          'gauge',
          parseFloat(errorRate.toFixed(4)),
          { model }
        );
      }

      // Per-node execution counts from tracker
      for (const [nodeId, recordIds] of Object.entries(trackerData.node_index || {})) {
        const nodeRecords = records.filter(r => recordIds.includes(r.id));
        const totalDuration = nodeRecords.reduce(
          (sum, r) => sum + (r.duration_ms || 0), 0
        );

        reg.add(
          'fleet_tracker_node_executions_total',
          'Total tracked workflow executions per node',
          'counter',
          nodeRecords.length,
          { node: nodeId }
        );
        reg.add(
          'fleet_tracker_node_total_duration_seconds',
          'Total tracked execution duration per node in seconds',
          'counter',
          parseFloat((totalDuration / 1000).toFixed(3)),
          { node: nodeId }
        );
      }
    }

    // =====================================================================
    // 7. NFS activity metrics
    // =====================================================================
    if (snapshot.nfsActivity?.available) {
      reg.add(
        'fleet_nfs_inflight_jobs',
        'Number of in-flight jobs (active prompt files on NFS)',
        'gauge',
        snapshot.nfsActivity.inFlightCount || 0
      );
      reg.add(
        'fleet_nfs_recent_completions',
        'Number of recently completed NFS jobs (last 30 minutes)',
        'gauge',
        snapshot.nfsActivity.recentCompletionCount || 0
      );
    }

    return reg.serialize();
  }

  // -------------------------------------------------------------------------
  // HTTP server
  // -------------------------------------------------------------------------

  /**
   * Start the HTTP server and periodic collection loop.
   */
  async start() {
    // Initial collection
    console.log('[fleet-prometheus-exporter] Running initial collection...');
    await this.collect();
    console.log('[fleet-prometheus-exporter] Initial collection complete.');

    // Periodic collection
    this._intervalId = setInterval(async () => {
      try {
        const snapshot = await this.collect();
        if (snapshot) {
          const s = snapshot.summary;
          console.log(
            `[${new Date().toISOString()}] ` +
            `nodes=${s.nodesReachable}/${s.nodesTotal} ` +
            `workflows=${s.activeWorkflows}/${s.totalWorkflows} ` +
            `models=${s.activeModels.join(',') || 'none'} ` +
            `collected_in=${(this._lastCollectionDuration * 1000).toFixed(0)}ms`
          );
        }
      } catch (err) {
        console.error(`[fleet-prometheus-exporter] Periodic collection error: ${err.message}`);
      }
    }, this.intervalSec * 1000);

    // HTTP server
    this._server = http.createServer(async (req, res) => {
      const url = new URL(req.url, `http://localhost:${this.port}`);

      switch (url.pathname) {
        case '/metrics': {
          try {
            const metrics = this.generateMetrics();
            res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4; charset=utf-8' });
            res.end(metrics);
          } catch (err) {
            console.error(`[fleet-prometheus-exporter] /metrics error: ${err.message}`);
            res.writeHead(500, { 'Content-Type': 'text/plain' });
            res.end(`# Error generating metrics: ${err.message}\n`);
          }
          break;
        }

        case '/health': {
          const hasData = this.collector.getLatestSnapshot() !== null;
          res.writeHead(hasData ? 200 : 503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            status: hasData ? 'healthy' : 'initializing',
            collections: this._collectCount,
            errors: this._errorCount,
            lastCollection: this._lastCollectionTime
              ? new Date(this._lastCollectionTime).toISOString()
              : null,
            lastDurationSec: this._lastCollectionDuration,
            uptimeSec: process.uptime(),
          }));
          break;
        }

        case '/status': {
          const snapshot = this.collector.getLatestSnapshot();
          if (!snapshot) {
            res.writeHead(503, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'No data collected yet' }));
            break;
          }
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            summary: snapshot.summary,
            modelAssignments: snapshot.modelAssignments,
            workflowNodeMap: snapshot.workflowNodeMap,
            collectionDurationMs: snapshot.collectionDurationMs,
            timestamp: snapshot.timestamp,
          }, null, 2));
          break;
        }

        default: {
          res.writeHead(200, { 'Content-Type': 'text/plain' });
          res.end([
            'Fleet Prometheus Exporter',
            '',
            'Endpoints:',
            '  /metrics  - Prometheus-format metrics (text/plain)',
            '  /health   - Health check (JSON)',
            '  /status   - Latest collection summary (JSON)',
            '',
            `Port: ${this.port}`,
            `Collection interval: ${this.intervalSec}s`,
            `Collections: ${this._collectCount}`,
            `Errors: ${this._errorCount}`,
            '',
            'Add to prometheus.yml:',
            '',
            '  - job_name: "fleet-metrics"',
            '    scrape_interval: 60s',
            '    static_configs:',
            `      - targets: ["localhost:${this.port}"]`,
          ].join('\n'));
        }
      }
    });

    this._server.listen(this.port, () => {
      console.log(`[fleet-prometheus-exporter] HTTP server on http://localhost:${this.port}`);
      console.log(`[fleet-prometheus-exporter] Metrics at http://localhost:${this.port}/metrics`);
      console.log(`[fleet-prometheus-exporter] Collection interval: ${this.intervalSec}s`);
    });

    // Graceful shutdown
    const shutdown = () => {
      console.log('[fleet-prometheus-exporter] Shutting down...');
      if (this._intervalId) clearInterval(this._intervalId);
      if (this._server) {
        this._server.close(() => {
          console.log('[fleet-prometheus-exporter] Server closed.');
          process.exit(0);
        });
      } else {
        process.exit(0);
      }
    };

    process.on('SIGTERM', shutdown);
    process.on('SIGINT', shutdown);

    return this;
  }

  /**
   * Stop the exporter gracefully.
   */
  stop() {
    if (this._intervalId) {
      clearInterval(this._intervalId);
      this._intervalId = null;
    }
    if (this._server) {
      this._server.close();
      this._server = null;
    }
  }
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------
const isMainModule = process.argv[1] &&
  (process.argv[1].endsWith('fleet-prometheus-exporter.js') ||
   process.argv[1].includes('fleet-prometheus-exporter'));

if (isMainModule) {
  const args = process.argv.slice(2);

  let port = DEFAULT_PORT;
  let interval = DEFAULT_INTERVAL_SEC;
  let once = false;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--port':
        port = parseInt(args[++i], 10);
        break;
      case '--interval':
        interval = parseInt(args[++i], 10);
        break;
      case '--once':
        once = true;
        break;
      case '--help':
        console.log(`
Fleet Prometheus Exporter

Usage:
  node monitoring/fleet-prometheus-exporter.js [OPTIONS]

Options:
  --port <num>       HTTP port (default: ${DEFAULT_PORT})
  --interval <sec>   Collection interval in seconds (default: ${DEFAULT_INTERVAL_SEC})
  --once             Collect once, print metrics to stdout, then exit
  --help             Show this help

Endpoints (server mode):
  /metrics           Prometheus-format metrics
  /health            Health check (JSON)
  /status            Latest collection summary (JSON)

Metrics exposed:
  fleet_node_cpu_usage{node}                CPU usage % per node
  fleet_node_ram_usage{node}                RAM usage % per node
  fleet_active_workflows                    Active workflow count
  fleet_workflow_duration{workflow,phase}    Duration in seconds
  fleet_cost_per_node{node,model}           Estimated USD cost per interval
  fleet_ai_model_assignments{model,node,status}  Model-to-node assignments

  Plus: load averages, RAM bytes, CPU cores, reachable state, claude
  processes, SSH sessions, dispatcher status, NFS activity, tracker
  execution counts, and exporter meta metrics.

Examples:
  node monitoring/fleet-prometheus-exporter.js
  node monitoring/fleet-prometheus-exporter.js --port 9092 --interval 30
  node monitoring/fleet-prometheus-exporter.js --once
        `);
        process.exit(0);
    }
  }

  if (once) {
    // One-shot mode: collect, print metrics, exit
    const exporter = new FleetPrometheusExporter({ port, intervalSec: interval });
    await exporter.collect();
    console.log(exporter.generateMetrics());
    process.exit(0);
  }

  // Server mode
  const exporter = new FleetPrometheusExporter({ port, intervalSec: interval });
  exporter.start().catch(err => {
    console.error(`[fleet-prometheus-exporter] Failed to start: ${err.message}`);
    process.exit(1);
  });
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
export default FleetPrometheusExporter;
