#!/usr/bin/env node
/**
 * Workflow-Node Tracker HTTP Service
 *
 * Standalone HTTP wrapper around the workflow-node-tracker logic.
 * Provides REST API for tracking workflow-to-node mappings, querying
 * execution maps, node utilization, model deployment, and metrics.
 *
 * Usage:
 *   node monitoring/workflow-node-tracker-service.js [--port 9093]
 *
 * Endpoints:
 *   POST /track           - Track a workflow execution
 *   GET  /map             - Get execution map (?workflow_id=X)
 *   GET  /utilization     - Node utilization (?node_id=X&hours=24)
 *   GET  /models          - Model deployment map (?model=X&hours=24)
 *   GET  /path/:id        - Analyze execution path for workflow
 *   GET  /metrics         - Performance metrics (?type=latency&hours=24)
 *   GET  /report          - Generate report (?type=full&hours=24)
 *   POST /reset           - Reset tracking data
 *   GET  /health          - Health check
 */

import fs from 'fs';
import path from 'path';
import http from 'http';
import os from 'os';

// ============================================================================
// CONFIGURATION
// ============================================================================

const HOME = process.env.HOME || os.homedir();
const DATA_DIR = path.join(HOME, '.claude', 'learning', 'workflow-tracking');
const DATA_FILE = path.join(DATA_DIR, 'workflow-node-tracking.json');

const DEFAULT_CONFIG = {
  max_records: 10000,
};

// ============================================================================
// TRANSCRIPT PARSING PATTERNS
// ============================================================================

const TRANSCRIPT_PATTERNS = {
  workflow_start: /\[WORKFLOW\]\s+(\w[\w-]*)\s+(?:started|initiated).*?(?:on\s+node\s+(\w[\w-]*))?\s*$/im,
  agent_execution: /\[AGENT\]\s+(\w[\w-]*)\s+(?:running|executing).*?(?:model:\s*(\w[\w-]*))?\s*$/im,
  node_assignment: /(?:assigned\s+to|executing\s+on|node[:\s]+)(\w[\w-]*)/im,
  model_spec: /(?:model|using|with)\s+(?:model\s+)?(\w[\w-]*?)(?:\s|$|,|\))/im,
  start_time: /(?:start|begin|initiated)\s+(?:at|time:\s+)(\d{2}:\d{2}:\d{2})/im,
  end_time: /(?:end|completed|finished)\s+(?:at|time:\s+)(\d{2}:\d{2}:\d{2})/im,
  duration_ms: /(?:duration|took|elapsed|time)\s+(\d+(?:\.\d+)?)\s*(?:ms|milliseconds)/im,
  status_success: /(?:success|completed|finished|done)\s+/im,
  status_error: /(?:error|failed|exception)\s+/im,
  phase_marker: /\[PHASE\]\s+(\w[\w\s]*?)(?:\s+\||$)/im,
  function_call: /(?:calling|invoking|executing)\s+([a-zA-Z_]\w*)/im,
};

// ============================================================================
// DATA STRUCTURES
// ============================================================================

function generateId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function createTrackingData() {
  return {
    version: '1.0',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    session_id: generateId('session'),
    records: [],
    node_index: {},
    workflow_index: {},
    model_index: {},
    stats: {
      total_workflows: 0,
      total_nodes: 0,
      total_models: 0,
      total_records: 0,
    },
  };
}

function createNodeRecord(args = {}) {
  return {
    id: args.id || generateId('node'),
    workflow_id: args.workflow_id || null,
    node_id: args.node_id || null,
    model: args.model || null,
    start_time: args.start_time || new Date().toISOString(),
    end_time: args.end_time || null,
    duration_ms: args.duration_ms || null,
    status: args.status || 'pending',
    error: args.error || null,
    metadata: args.metadata || {},
    phases: args.phases || [],
    operations: args.operations || [],
  };
}

// ============================================================================
// FILE I/O
// ============================================================================

function loadTrackingData() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      return JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
    }
  } catch (err) {
    console.error(`Warning: Could not load tracking data: ${err.message}`);
  }
  return createTrackingData();
}

function saveTrackingData(data) {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    data.updated_at = new Date().toISOString();
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), 'utf-8');
  } catch (err) {
    console.error(`Warning: Could not save tracking data: ${err.message}`);
  }
}

// ============================================================================
// TRANSCRIPT PARSING
// ============================================================================

function parseTranscript(transcript) {
  if (!transcript || typeof transcript !== 'string') {
    return [];
  }

  const lines = transcript.split('\n');
  const events = [];

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    const phaseMatch = line.match(TRANSCRIPT_PATTERNS.phase_marker);
    if (phaseMatch) {
      events.push({ type: 'phase', name: phaseMatch[1], timestamp: new Date().toISOString() });
      continue;
    }

    const workflowMatch = line.match(TRANSCRIPT_PATTERNS.workflow_start);
    if (workflowMatch) {
      events.push({ type: 'workflow_start', workflow_id: workflowMatch[1], node_id: workflowMatch[2] || null, timestamp: new Date().toISOString() });
      continue;
    }

    const agentMatch = line.match(TRANSCRIPT_PATTERNS.agent_execution);
    if (agentMatch) {
      events.push({ type: 'agent_execution', agent: agentMatch[1], model: agentMatch[2] || null, timestamp: new Date().toISOString() });
      continue;
    }

    const nodeMatch = line.match(TRANSCRIPT_PATTERNS.node_assignment);
    if (nodeMatch) {
      events.push({ type: 'node_assignment', node_id: nodeMatch[1], timestamp: new Date().toISOString() });
    }

    const modelMatch = line.match(TRANSCRIPT_PATTERNS.model_spec);
    if (modelMatch && !agentMatch) {
      events.push({ type: 'model_spec', model: modelMatch[1], timestamp: new Date().toISOString() });
    }

    const durationMatch = line.match(TRANSCRIPT_PATTERNS.duration_ms);
    if (durationMatch) {
      events.push({ type: 'timing', subtype: 'duration', duration_ms: parseFloat(durationMatch[1]), timestamp: new Date().toISOString() });
    }

    if (line.match(TRANSCRIPT_PATTERNS.status_success)) {
      events.push({ type: 'status', status: 'success', timestamp: new Date().toISOString() });
    }
    if (line.match(TRANSCRIPT_PATTERNS.status_error)) {
      events.push({ type: 'status', status: 'error', timestamp: new Date().toISOString() });
    }

    const funcMatch = line.match(TRANSCRIPT_PATTERNS.function_call);
    if (funcMatch) {
      events.push({ type: 'function_call', function: funcMatch[1], timestamp: new Date().toISOString() });
    }
  }

  return events;
}

function synthesizeRecord(workflowId, events, nodeId, model) {
  const record = createNodeRecord({ workflow_id: workflowId, node_id: nodeId, model: model });
  const phases = [];
  let totalDuration = 0;

  for (const event of events) {
    switch (event.type) {
      case 'phase':
        phases.push({ name: event.name, start_time: event.timestamp, end_time: null, duration_ms: null, status: 'running' });
        break;
      case 'agent_execution':
        if (!record.model && event.model) record.model = event.model;
        break;
      case 'node_assignment':
        if (!record.node_id) record.node_id = event.node_id;
        break;
      case 'model_spec':
        if (!record.model) record.model = event.model;
        break;
      case 'timing':
        if (event.subtype === 'duration') totalDuration += event.duration_ms || 0;
        break;
      case 'status':
        record.status = event.status;
        break;
      case 'function_call':
        record.operations.push({ name: event.function, start_time: event.timestamp, status: 'pending' });
        break;
    }
  }

  record.phases = phases;
  if (totalDuration > 0) record.duration_ms = totalDuration;

  return record;
}

// ============================================================================
// ACTIONS
// ============================================================================

function trackExecution(data, workflowId, transcript, nodeId, model) {
  const events = parseTranscript(transcript);
  const record = synthesizeRecord(workflowId, events, nodeId, model);

  data.records.push(record);
  if (data.records.length > DEFAULT_CONFIG.max_records) {
    data.records.shift();
  }

  if (!data.workflow_index[record.workflow_id]) {
    data.workflow_index[record.workflow_id] = [];
    data.stats.total_workflows += 1;
  }
  data.workflow_index[record.workflow_id].push(record.id);

  if (record.node_id) {
    if (!data.node_index[record.node_id]) {
      data.node_index[record.node_id] = [];
      data.stats.total_nodes += 1;
    }
    data.node_index[record.node_id].push(record.id);
  }

  if (record.model) {
    if (!data.model_index[record.model]) {
      data.model_index[record.model] = [];
      data.stats.total_models += 1;
    }
    data.model_index[record.model].push(record.id);
  }

  data.stats.total_records = data.records.length;
  saveTrackingData(data);

  return {
    status: 'tracked',
    record_id: record.id,
    workflow_id: record.workflow_id,
    node_id: record.node_id,
    model: record.model,
    duration_ms: record.duration_ms,
    phases_count: record.phases.length,
    operations_count: record.operations.length,
  };
}

function getExecutionMap(data, workflowId) {
  let records = workflowId
    ? data.records.filter(r => (data.workflow_index[workflowId] || []).includes(r.id))
    : data.records;

  const map = { total_records: records.length, workflows: {} };

  for (const record of records) {
    if (!map.workflows[record.workflow_id]) {
      map.workflows[record.workflow_id] = {
        executions: [],
        total_duration_ms: 0,
        status: 'unknown',
        nodes_used: [],
        models_used: [],
      };
    }
    const wf = map.workflows[record.workflow_id];
    wf.executions.push({
      record_id: record.id,
      node_id: record.node_id,
      model: record.model,
      start_time: record.start_time,
      duration_ms: record.duration_ms,
      status: record.status,
    });
    if (record.duration_ms) wf.total_duration_ms += record.duration_ms;
    wf.status = record.status;
    if (record.node_id && !wf.nodes_used.includes(record.node_id)) wf.nodes_used.push(record.node_id);
    if (record.model && !wf.models_used.includes(record.model)) wf.models_used.push(record.model);
  }

  return map;
}

function getNodeUtilization(data, nodeId, timeWindowHours) {
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000);
  let records = data.records.filter(r => new Date(r.start_time) >= cutoffTime);

  if (nodeId) {
    const ids = data.node_index[nodeId] || [];
    records = records.filter(r => ids.includes(r.id));
  }

  const utilization = { time_window_hours: timeWindowHours, nodes: {} };
  const nodeRecords = {};
  for (const record of records) {
    if (!record.node_id) continue;
    if (!nodeRecords[record.node_id]) nodeRecords[record.node_id] = [];
    nodeRecords[record.node_id].push(record);
  }

  for (const [nid, nodeRecs] of Object.entries(nodeRecords)) {
    const totalDuration = nodeRecs.reduce((sum, r) => sum + (r.duration_ms || 0), 0);
    const successCount = nodeRecs.filter(r => r.status === 'success').length;
    const errorCount = nodeRecs.filter(r => r.status === 'error').length;

    utilization.nodes[nid] = {
      total_executions: nodeRecs.length,
      successful: successCount,
      failed: errorCount,
      error_rate: nodeRecs.length > 0 ? errorCount / nodeRecs.length : 0,
      total_duration_ms: totalDuration,
      avg_duration_ms: nodeRecs.length > 0 ? totalDuration / nodeRecs.length : 0,
      models_deployed: [...new Set(nodeRecs.map(r => r.model).filter(Boolean))],
      workflows_executed: [...new Set(nodeRecs.map(r => r.workflow_id).filter(Boolean))],
    };
  }

  return utilization;
}

function getModelDeployment(data, model, timeWindowHours) {
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000);
  let records = data.records.filter(r => new Date(r.start_time) >= cutoffTime);

  if (model) {
    const ids = data.model_index[model] || [];
    records = records.filter(r => ids.includes(r.id));
  }

  const deployment = { time_window_hours: timeWindowHours, models: {} };
  const modelRecords = {};
  for (const record of records) {
    if (!record.model) continue;
    if (!modelRecords[record.model]) modelRecords[record.model] = [];
    modelRecords[record.model].push(record);
  }

  for (const [modelId, modelRecs] of Object.entries(modelRecords)) {
    const totalDuration = modelRecs.reduce((sum, r) => sum + (r.duration_ms || 0), 0);
    deployment.models[modelId] = {
      total_executions: modelRecs.length,
      successful: modelRecs.filter(r => r.status === 'success').length,
      failed: modelRecs.filter(r => r.status === 'error').length,
      total_duration_ms: totalDuration,
      avg_duration_ms: modelRecs.length > 0 ? totalDuration / modelRecs.length : 0,
      nodes_deployed_on: [...new Set(modelRecs.map(r => r.node_id).filter(Boolean))],
    };
  }

  return deployment;
}

function getMetrics(data, nodeId, model, metricType, timeWindowHours) {
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000);
  let records = data.records.filter(r => new Date(r.start_time) >= cutoffTime);

  if (nodeId) records = records.filter(r => (data.node_index[nodeId] || []).includes(r.id));
  if (model) records = records.filter(r => (data.model_index[model] || []).includes(r.id));

  const metrics = { filter: { nodeId, model, metricType, timeWindowHours }, total_records: records.length, results: {} };
  if (records.length === 0) return metrics;

  switch (metricType) {
    case 'latency': {
      const durations = records.map(r => r.duration_ms || 0).filter(d => d > 0).sort((a, b) => a - b);
      if (durations.length > 0) {
        const sum = durations.reduce((a, b) => a + b, 0);
        const mean = sum / durations.length;
        metrics.results = {
          count: durations.length, min_ms: durations[0], max_ms: durations[durations.length - 1],
          mean_ms: mean, median_ms: durations[Math.floor(durations.length / 2)],
          p95_ms: durations[Math.floor(durations.length * 0.95)],
          p99_ms: durations[Math.floor(durations.length * 0.99)],
        };
      }
      break;
    }
    case 'throughput': {
      const timestamps = records.map(r => new Date(r.start_time).getTime());
      const timeSpan = (Math.max(...timestamps) - Math.min(...timestamps)) / 3600000;
      metrics.results = { total_executions: records.length, time_span_hours: timeSpan, executions_per_hour: timeSpan > 0 ? records.length / timeSpan : 0 };
      break;
    }
    case 'error_rate': {
      const errorCount = records.filter(r => r.status === 'error').length;
      metrics.results = { total: records.length, successful: records.length - errorCount, failed: errorCount, error_rate: errorCount / records.length };
      break;
    }
    default:
      metrics.results = { error: `Unknown metric type: ${metricType}` };
  }

  return metrics;
}

// ============================================================================
// HTTP SERVER
// ============================================================================

function startServer(port = 9093) {
  let data = loadTrackingData();

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${port}`);
    const respond = (code, body) => {
      res.writeHead(code, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(body, null, 2));
    };

    try {
      // Reload data from disk on each request to stay current
      data = loadTrackingData();

      if (req.method === 'GET' && url.pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end('OK');
        return;
      }

      if (req.method === 'POST' && url.pathname === '/track') {
        let body = '';
        for await (const chunk of req) body += chunk;
        const payload = JSON.parse(body);
        const result = trackExecution(data, payload.workflow_id, payload.transcript, payload.node_id, payload.model);
        respond(200, result);
        return;
      }

      if (req.method === 'GET' && url.pathname === '/map') {
        respond(200, getExecutionMap(data, url.searchParams.get('workflow_id')));
        return;
      }

      if (req.method === 'GET' && url.pathname === '/utilization') {
        const hours = parseInt(url.searchParams.get('hours') || '24', 10);
        respond(200, getNodeUtilization(data, url.searchParams.get('node_id'), hours));
        return;
      }

      if (req.method === 'GET' && url.pathname === '/models') {
        const hours = parseInt(url.searchParams.get('hours') || '24', 10);
        respond(200, getModelDeployment(data, url.searchParams.get('model'), hours));
        return;
      }

      if (req.method === 'GET' && url.pathname === '/metrics') {
        const metricType = url.searchParams.get('type') || 'latency';
        const hours = parseInt(url.searchParams.get('hours') || '24', 10);
        respond(200, getMetrics(data, url.searchParams.get('node_id'), url.searchParams.get('model'), metricType, hours));
        return;
      }

      if (req.method === 'GET' && url.pathname === '/report') {
        const reportType = url.searchParams.get('type') || 'full';
        const hours = parseInt(url.searchParams.get('hours') || '24', 10);
        respond(200, { stats: data.stats, records_in_window: data.records.filter(r => new Date(r.start_time) >= new Date(Date.now() - hours * 3600000)).length, report_type: reportType });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/reset') {
        data = createTrackingData();
        saveTrackingData(data);
        respond(200, { status: 'reset', session_id: data.session_id });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/stats') {
        respond(200, data.stats);
        return;
      }

      // Default
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end([
        'Workflow-Node Tracker Service',
        '',
        'Endpoints:',
        '  POST /track           - Track execution (JSON body: workflow_id, transcript, node_id?, model?)',
        '  GET  /map             - Execution map (?workflow_id=X)',
        '  GET  /utilization     - Node utilization (?node_id=X&hours=24)',
        '  GET  /models          - Model deployment (?model=X&hours=24)',
        '  GET  /metrics         - Metrics (?type=latency|throughput|error_rate&hours=24)',
        '  GET  /report          - Report (?type=full|summary&hours=24)',
        '  GET  /stats           - Current stats',
        '  POST /reset           - Reset tracking data',
        '  GET  /health          - Health check',
      ].join('\n'));
    } catch (err) {
      respond(500, { error: err.message });
    }
  });

  server.listen(port, () => {
    console.log(`[workflow-node-tracker] HTTP service on http://localhost:${port}`);
    console.log(`[workflow-node-tracker] Health: http://localhost:${port}/health`);
    console.log(`[workflow-node-tracker] Data: ${DATA_FILE}`);
    console.log(`[workflow-node-tracker] Stats: ${JSON.stringify(data.stats)}`);
  });

  const shutdown = () => {
    console.log('[workflow-node-tracker] Shutting down...');
    server.close(() => process.exit(0));
  };
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  return server;
}

// ============================================================================
// CLI
// ============================================================================

const args = process.argv.slice(2);
let port = 9093;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--port' && args[i + 1]) {
    port = parseInt(args[i + 1], 10);
    i++;
  }
}

startServer(port);
