#!/usr/bin/env node

/**
 * Fleet Brain API Server - REST API for pi-02
 *
 * Runs on pi-02 as the centralized orchestration hub.
 * All fleet nodes and clients connect to this API.
 *
 * Endpoints:
 * - POST /route          - Route request to best model
 * - GET  /models         - List available models
 * - GET  /nodes          - List fleet status
 * - GET  /health         - Health check
 * - POST /register-node  - Node registers itself
 * - POST /heartbeat      - Node heartbeat
 * - GET  /status         - Full fleet status
 */

const http = require('http');
const url = require('url');
const ModelMeshOrchestrator = require('./orchestrator-model-mesh.cjs');

class FleetBrainAPI {
  constructor(port = 8080, registryPath = null) {
    this.port = port;
    this.orchestrator = new ModelMeshOrchestrator(registryPath);
    this.server = null;
    this.requestLog = [];
  }

  /**
   * Parse JSON body from request
   */
  parseBody(req) {
    return new Promise((resolve, reject) => {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', () => {
        try {
          resolve(body ? JSON.parse(body) : {});
        } catch (error) {
          reject(new Error('Invalid JSON'));
        }
      });
      req.on('error', reject);
    });
  }

  /**
   * Send JSON response
   */
  sendJSON(res, statusCode, data) {
    res.writeHead(statusCode, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    });
    res.end(JSON.stringify(data, null, 2));
  }

  /**
   * Log request
   */
  logRequest(req, statusCode, responseTime) {
    const entry = {
      timestamp: new Date().toISOString(),
      method: req.method,
      path: req.url,
      statusCode: statusCode,
      responseTime: responseTime,
      userAgent: req.headers['user-agent']
    };
    this.requestLog.push(entry);

    // Keep only last 1000 requests
    if (this.requestLog.length > 1000) {
      this.requestLog = this.requestLog.slice(-1000);
    }

    console.log(`[${entry.timestamp}] ${req.method} ${req.url} ${statusCode} ${responseTime}ms`);
  }

  /**
   * Handle routing requests
   */
  async handleRoute(req, res) {
    try {
      const body = await this.parseBody(req);
      const { capabilities, constraints } = body;

      if (!capabilities) {
        this.sendJSON(res, 400, {
          error: 'Missing required field: capabilities',
          usage: 'POST /route with JSON body: { capabilities: ["coding"], constraints: {...} }'
        });
        return;
      }

      const result = this.orchestrator.routeRequest(capabilities, constraints || {});
      this.sendJSON(res, result.success ? 200 : 404, result);
    } catch (error) {
      this.sendJSON(res, 400, { error: error.message });
    }
  }

  /**
   * Handle model listing
   */
  handleModels(req, res) {
    const models = this.orchestrator.getAvailableModels();
    this.sendJSON(res, 200, {
      count: models.length,
      models: models
    });
  }

  /**
   * Handle node listing
   */
  handleNodes(req, res) {
    const registry = this.orchestrator.registry;
    const nodes = Object.entries(registry.nodes).map(([name, node]) => ({
      name,
      status: node.status,
      last_heartbeat: node.last_heartbeat,
      ram_gb: node.ram_gb,
      cpu_cores: node.cpu_cores,
      roles: node.roles,
      total_models: node.total_models,
      cloud_models: node.cloud_models,
      local_models: node.local_models
    }));

    this.sendJSON(res, 200, {
      count: nodes.length,
      nodes: nodes
    });
  }

  /**
   * Handle health check
   */
  async handleHealth(req, res) {
    const results = await this.orchestrator.healthCheck();
    this.sendJSON(res, 200, {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      nodes: results
    });
  }

  /**
   * Handle node registration
   */
  async handleRegisterNode(req, res) {
    try {
      const body = await this.parseBody(req);
      const { node, hostname, ram_gb, cpu_cores, roles, models } = body;

      if (!node || !hostname || !models) {
        this.sendJSON(res, 400, {
          error: 'Missing required fields',
          required: ['node', 'hostname', 'models'],
          usage: 'POST /register-node with JSON body'
        });
        return;
      }

      const nodeConfig = {
        hostname,
        ram_gb: ram_gb || 0,
        cpu_cores: cpu_cores || 1,
        roles: roles || ['worker']
      };

      const result = this.orchestrator.registerNode(node, nodeConfig, models);
      this.sendJSON(res, result.success ? 200 : 409, result);
    } catch (error) {
      this.sendJSON(res, 400, { error: error.message });
    }
  }

  /**
   * Handle heartbeat
   */
  async handleHeartbeat(req, res) {
    try {
      const body = await this.parseBody(req);
      const { node } = body;

      if (!node) {
        this.sendJSON(res, 400, {
          error: 'Missing required field: node',
          usage: 'POST /heartbeat with JSON body: { node: "server-01" }'
        });
        return;
      }

      const registry = this.orchestrator.registry;
      const nodeConfig = registry.nodes[node];

      if (!nodeConfig) {
        this.sendJSON(res, 404, {
          error: 'Node not found',
          node: node,
          suggestion: 'Register the node first with POST /register-node'
        });
        return;
      }

      // Update heartbeat
      nodeConfig.last_heartbeat = new Date().toISOString();
      nodeConfig.status = 'online';

      // Mark models as available
      nodeConfig.models?.forEach(modelName => {
        if (registry.models[modelName]) {
          registry.models[modelName].status = 'available';
        }
      });

      this.orchestrator.saveRegistry();

      this.sendJSON(res, 200, {
        success: true,
        node: node,
        heartbeat_received: nodeConfig.last_heartbeat,
        next_heartbeat_in: 30000 // 30 seconds
      });
    } catch (error) {
      this.sendJSON(res, 400, { error: error.message });
    }
  }

  /**
   * Handle full status
   */
  handleStatus(req, res) {
    const status = this.orchestrator.getFleetStatus();
    this.sendJSON(res, 200, status);
  }

  /**
   * Handle request logs
   */
  handleLogs(req, res) {
    const limit = parseInt(url.parse(req.url, true).query.limit) || 100;
    const logs = this.requestLog.slice(-limit);
    this.sendJSON(res, 200, {
      count: logs.length,
      logs: logs
    });
  }

  /**
   * Handle GET node by name
   */
  handleGetNode(req, res) {
    const parsedUrl = url.parse(req.url, true);
    const nodeName = parsedUrl.pathname.split('/')[2];

    if (!nodeName) {
      this.sendJSON(res, 400, {
        error: 'Node name required',
        usage: 'GET /nodes/<node-name>'
      });
      return;
    }

    const status = this.orchestrator.getNodeStatus(nodeName);
    this.sendJSON(res, status.success ? 200 : 404, status);
  }

  /**
   * Main request handler
   */
  async handleRequest(req, res) {
    const startTime = Date.now();
    const parsedUrl = url.parse(req.url, true);
    const path = parsedUrl.pathname;
    const method = req.method;

    try {
      // CORS preflight
      if (method === 'OPTIONS') {
        res.writeHead(200, {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type'
        });
        res.end();
        return;
      }

      // Route handling
      if (method === 'POST' && path === '/route') {
        await this.handleRoute(req, res);
      } else if (method === 'GET' && path === '/models') {
        this.handleModels(req, res);
      } else if (method === 'GET' && path === '/nodes') {
        this.handleNodes(req, res);
      } else if (method === 'GET' && path.startsWith('/nodes/')) {
        this.handleGetNode(req, res);
      } else if (method === 'GET' && path === '/health') {
        await this.handleHealth(req, res);
      } else if (method === 'POST' && path === '/register-node') {
        await this.handleRegisterNode(req, res);
      } else if (method === 'POST' && path === '/heartbeat') {
        await this.handleHeartbeat(req, res);
      } else if (method === 'GET' && path === '/status') {
        this.handleStatus(req, res);
      } else if (method === 'GET' && path === '/logs') {
        this.handleLogs(req, res);
      } else if (method === 'GET' && path === '/') {
        // Root - show API documentation
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end(`Fleet Brain API - pi-02 Orchestration Hub

Available Endpoints:

POST /route
  Route request to best model
  Body: { capabilities: ["coding"], constraints: {...} }

GET /models
  List all available models

GET /nodes
  List all nodes

GET /nodes/<name>
  Get node details

GET /health
  Run health check on all nodes

POST /register-node
  Register a new node
  Body: { node: "server-01", hostname: "server-01", ram_gb: 31, cpu_cores: 8, roles: ["worker"], models: [...] }

POST /heartbeat
  Send heartbeat from node
  Body: { node: "server-01" }

GET /status
  Get full fleet status

GET /logs?limit=100
  Get recent request logs

Examples:

curl -X POST http://pi-02:8080/route \\
  -H "Content-Type: application/json" \\
  -d '{"capabilities": ["coding"]}'

curl http://pi-02:8080/models

curl http://pi-02:8080/nodes

curl -X POST http://pi-02:8080/heartbeat \\
  -H "Content-Type: application/json" \\
  -d '{"node": "server-01"}'
`);
      } else {
        this.sendJSON(res, 404, {
          error: 'Not found',
          path: path,
          method: method,
          available_endpoints: [
            'POST /route',
            'GET  /models',
            'GET  /nodes',
            'GET  /nodes/<name>',
            'GET  /health',
            'POST /register-node',
            'POST /heartbeat',
            'GET  /status',
            'GET  /logs'
          ]
        });
      }
    } catch (error) {
      console.error('Request handler error:', error);
      this.sendJSON(res, 500, { error: 'Internal server error', message: error.message });
    } finally {
      const responseTime = Date.now() - startTime;
      this.logRequest(req, res.statusCode || 500, responseTime);
    }
  }

  /**
   * Start API server
   */
  start() {
    this.server = http.createServer((req, res) => {
      this.handleRequest(req, res).catch(error => {
        console.error('Unhandled error:', error);
        this.sendJSON(res, 500, { error: 'Internal server error' });
      });
    });

    this.server.listen(this.port, '0.0.0.0', () => {
      console.log('╔════════════════════════════════════════════════════════════╗');
      console.log('║         Fleet Brain API Server - pi-02                    ║');
      console.log('╚════════════════════════════════════════════════════════════╝');
      console.log('');
      console.log(`🚀 Server running on http://0.0.0.0:${this.port}`);
      console.log(`📡 Accessible from fleet at http://pi-02:${this.port}`);
      console.log('');
      console.log('Available endpoints:');
      console.log('  POST /route          - Route request to best model');
      console.log('  GET  /models         - List available models');
      console.log('  GET  /nodes          - List fleet status');
      console.log('  GET  /health         - Health check');
      console.log('  POST /register-node  - Node registration');
      console.log('  POST /heartbeat      - Node heartbeat');
      console.log('  GET  /status         - Full fleet status');
      console.log('  GET  /logs           - Request logs');
      console.log('');
      console.log('Press Ctrl+C to stop');
      console.log('');
    });

    // Start health monitoring
    this.orchestrator.startHealthMonitoring();

    // Graceful shutdown
    process.on('SIGINT', () => {
      console.log('\n\nShutting down gracefully...');
      this.orchestrator.stopHealthMonitoring();
      this.server.close(() => {
        console.log('Server stopped');
        process.exit(0);
      });
    });

    process.on('SIGTERM', () => {
      this.orchestrator.stopHealthMonitoring();
      this.server.close(() => {
        process.exit(0);
      });
    });
  }

  /**
   * Stop API server
   */
  stop() {
    if (this.server) {
      this.orchestrator.stopHealthMonitoring();
      this.server.close();
    }
  }
}

// Export for use as library
module.exports = FleetBrainAPI;

// CLI entry point
if (require.main === module) {
  const port = parseInt(process.env.PORT || '8080');
  const registryPath = process.env.REGISTRY_PATH || null;

  const api = new FleetBrainAPI(port, registryPath);
  api.start();
}
