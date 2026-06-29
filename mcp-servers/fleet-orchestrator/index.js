#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { fleetExecute } from './tools/fleet-execute.js';
import { fleetStatus } from './tools/fleet-status.js';
import { fleetConsensus } from './tools/fleet-consensus.js';
import http from 'http';

// Prometheus metrics
const metrics = {
  mcp_requests_total: {},
  mcp_request_duration_ms: {},
  mcp_errors_total: {}
};

function recordRequest(toolName, durationMs, isError) {
  metrics.mcp_requests_total[toolName] = (metrics.mcp_requests_total[toolName] || 0) + 1;

  if (!metrics.mcp_request_duration_ms[toolName]) {
    metrics.mcp_request_duration_ms[toolName] = { sum: 0, count: 0, min: Infinity, max: 0 };
  }
  const durMetric = metrics.mcp_request_duration_ms[toolName];
  durMetric.sum += durationMs;
  durMetric.count++;
  durMetric.min = Math.min(durMetric.min, durationMs);
  durMetric.max = Math.max(durMetric.max, durationMs);

  if (isError) {
    metrics.mcp_errors_total[toolName] = (metrics.mcp_errors_total[toolName] || 0) + 1;
  }
}

function formatPrometheusMetrics() {
  let output = '';

  // mcp_requests_total
  output += '# HELP mcp_requests_total Total number of MCP requests\n';
  output += '# TYPE mcp_requests_total counter\n';
  for (const [tool, count] of Object.entries(metrics.mcp_requests_total)) {
    output += `mcp_requests_total{tool="${tool}"} ${count}\n`;
  }

  // mcp_request_duration_ms
  output += '# HELP mcp_request_duration_ms MCP request duration in milliseconds\n';
  output += '# TYPE mcp_request_duration_ms summary\n';
  for (const [tool, stats] of Object.entries(metrics.mcp_request_duration_ms)) {
    const avg = stats.count > 0 ? stats.sum / stats.count : 0;
    output += `mcp_request_duration_ms{tool="${tool}",quantile="avg"} ${avg.toFixed(2)}\n`;
    output += `mcp_request_duration_ms{tool="${tool}",quantile="min"} ${stats.min}\n`;
    output += `mcp_request_duration_ms{tool="${tool}",quantile="max"} ${stats.max}\n`;
    output += `mcp_request_duration_ms_sum{tool="${tool}"} ${stats.sum}\n`;
    output += `mcp_request_duration_ms_count{tool="${tool}"} ${stats.count}\n`;
  }

  // mcp_errors_total
  output += '# HELP mcp_errors_total Total number of MCP errors\n';
  output += '# TYPE mcp_errors_total counter\n';
  for (const [tool, count] of Object.entries(metrics.mcp_errors_total)) {
    output += `mcp_errors_total{tool="${tool}"} ${count}\n`;
  }

  return output;
}

// Start Prometheus metrics HTTP server
const metricsServer = http.createServer((req, res) => {
  if (req.url === '/metrics') {
    res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4' });
    res.end(formatPrometheusMetrics());
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

metricsServer.listen(9090, () => {
  console.error('Prometheus metrics endpoint available at http://localhost:9090/metrics');
});

const server = new Server(
  { name: 'fleet-orchestrator', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

const TOOLS = [
  {
    name: 'fleet-execute',
    description: 'Execute task on distributed fleet (8 workers, 9 API providers)',
    inputSchema: {
      type: 'object',
      properties: {
        task: { type: 'string', description: 'Task to execute' },
        model: { type: 'string', description: 'Model to use (opus/sonnet/haiku/gpt-4o/gemini)', default: 'auto' },
        worker: { type: 'string', description: 'Worker hostname or "auto"', default: 'auto' },
        timeout_ms: { type: 'number', description: 'Timeout in milliseconds', default: 120000 }
      },
      required: ['task']
    }
  },
  {
    name: 'fleet-status',
    description: 'Get health status of all fleet workers',
    inputSchema: {
      type: 'object',
      properties: {
        detailed: { type: 'boolean', description: 'Include detailed metrics', default: false }
      }
    }
  },
  {
    name: 'fleet-consensus',
    description: 'Execute question on multiple models in parallel, return majority-vote consensus with cost tracking and workflow storage',
    inputSchema: {
      type: 'object',
      properties: {
        question: { type: 'string', description: 'Question or task to get consensus on' },
        models: {
          type: 'array',
          items: { type: 'string' },
          description: 'Models to query (default: opus, sonnet, haiku)',
          default: ['opus', 'sonnet', 'haiku']
        },
        min_confidence: { type: 'number', description: 'Minimum confidence threshold for ACCEPT verdict', default: 0.7 },
        timeout_ms: { type: 'number', description: 'Per-model timeout in milliseconds', default: 120000 },
        track_costs: { type: 'boolean', description: 'Track costs in PostgreSQL', default: true },
        track_execution: { type: 'boolean', description: 'Track execution in workflow storage', default: true }
      },
      required: ['question']
    }
  }
];

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const startTime = Date.now();
  let isError = false;

  try {
    let result;
    if (name === 'fleet-execute') {
      result = await fleetExecute(args);
    } else if (name === 'fleet-status') {
      result = await fleetStatus(args);
    } else if (name === 'fleet-consensus') {
      result = await fleetConsensus(args);
    } else {
      throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
    };
  } catch (error) {
    isError = true;
    return {
      content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }],
      isError: true
    };
  } finally {
    const durationMs = Date.now() - startTime;
    recordRequest(name, durationMs, isError);
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Fleet Orchestrator MCP server running on stdio');
}

// Graceful shutdown handler
process.on('SIGTERM', async () => {
  console.error('SIGTERM received, shutting down gracefully...');
  metricsServer.close(() => {
    console.error('Metrics server closed');
  });
  // Close database connections
  // Close circuit breaker intervals
  process.exit(0);
});

main().catch(console.error);
