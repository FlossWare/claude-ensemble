#!/usr/bin/env node

/**
 * Fleet Orchestrator Client Library
 *
 * Lightweight HTTP client for connecting to pi-02 fleet brain.
 * Used by other nodes to:
 * - Register on startup
 * - Send heartbeats
 * - Route requests
 */

const http = require('http');
const { execSync } = require('child_process');

class FleetOrchestratorClient {
  constructor(brainHost = 'pi-02', brainPort = 8080) {
    this.brainHost = brainHost;
    this.brainPort = brainPort;
    this.nodeName = this.detectNodeName();
    this.heartbeatTimer = null;
    this.heartbeatInterval = 30000; // 30 seconds
  }

  /**
   * Detect current node name
   */
  detectNodeName() {
    try {
      return execSync('hostname -s').toString().trim();
    } catch (error) {
      return 'unknown';
    }
  }

  /**
   * Make HTTP request to brain
   */
  request(method, path, body = null) {
    return new Promise((resolve, reject) => {
      const options = {
        hostname: this.brainHost,
        port: this.brainPort,
        path: path,
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': `fleet-client/${this.nodeName}`
        },
        timeout: 10000
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            resolve({
              statusCode: res.statusCode,
              headers: res.headers,
              data: parsed
            });
          } catch (error) {
            resolve({
              statusCode: res.statusCode,
              headers: res.headers,
              data: data
            });
          }
        });
      });

      req.on('error', (error) => {
        reject(new Error(`Fleet brain unreachable at ${this.brainHost}:${this.brainPort}: ${error.message}`));
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timeout to ${this.brainHost}:${this.brainPort}`));
      });

      if (body) {
        req.write(JSON.stringify(body));
      }

      req.end();
    });
  }

  /**
   * Register this node with the brain
   */
  async registerNode(nodeConfig) {
    const { hostname, ram_gb, cpu_cores, roles, models } = nodeConfig;

    const body = {
      node: this.nodeName,
      hostname: hostname || this.nodeName,
      ram_gb: ram_gb || 0,
      cpu_cores: cpu_cores || 1,
      roles: roles || ['worker'],
      models: models || []
    };

    try {
      const response = await this.request('POST', '/register-node', body);

      if (response.statusCode === 200) {
        console.log(`✅ Registered with fleet brain: ${this.nodeName}`);
        console.log(`   Models: ${models.length}`);
        return { success: true, ...response.data };
      } else {
        console.error(`❌ Registration failed: ${response.data.error}`);
        return { success: false, error: response.data.error };
      }
    } catch (error) {
      console.error(`❌ Cannot reach fleet brain: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  /**
   * Send heartbeat to brain
   */
  async sendHeartbeat() {
    try {
      const response = await this.request('POST', '/heartbeat', {
        node: this.nodeName
      });

      if (response.statusCode === 200) {
        return { success: true, ...response.data };
      } else {
        console.warn(`⚠️  Heartbeat failed: ${response.data.error}`);
        return { success: false, error: response.data.error };
      }
    } catch (error) {
      console.error(`❌ Heartbeat failed: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  /**
   * Start automatic heartbeats
   */
  startHeartbeat() {
    console.log(`💓 Starting heartbeat (interval: ${this.heartbeatInterval}ms)`);

    // Send initial heartbeat
    this.sendHeartbeat();

    // Schedule periodic heartbeats
    this.heartbeatTimer = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatInterval);
  }

  /**
   * Stop automatic heartbeats
   */
  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
      console.log('💤 Heartbeat stopped');
    }
  }

  /**
   * Route request to best model
   */
  async routeRequest(capabilities, constraints = {}) {
    try {
      const response = await this.request('POST', '/route', {
        capabilities: Array.isArray(capabilities) ? capabilities : [capabilities],
        constraints: constraints
      });

      if (response.statusCode === 200) {
        return { success: true, ...response.data };
      } else {
        return { success: false, ...response.data };
      }
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Get available models
   */
  async getModels() {
    try {
      const response = await this.request('GET', '/models');
      return response.data;
    } catch (error) {
      return { error: error.message };
    }
  }

  /**
   * Get fleet nodes
   */
  async getNodes() {
    try {
      const response = await this.request('GET', '/nodes');
      return response.data;
    } catch (error) {
      return { error: error.message };
    }
  }

  /**
   * Get fleet status
   */
  async getStatus() {
    try {
      const response = await this.request('GET', '/status');
      return response.data;
    } catch (error) {
      return { error: error.message };
    }
  }

  /**
   * Health check
   */
  async healthCheck() {
    try {
      const response = await this.request('GET', '/health');
      return response.data;
    } catch (error) {
      return { error: error.message };
    }
  }

  /**
   * Detect Ollama models on this node
   */
  detectOllamaModels() {
    try {
      const output = execSync('ollama list', { encoding: 'utf8', timeout: 5000 });
      const lines = output.split('\n').slice(1); // Skip header

      const models = [];
      lines.forEach(line => {
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 1 && parts[0]) {
          const name = parts[0];
          const size = parts[1] || 'unknown';

          // Parse model name to extract capabilities
          const capabilities = this.guessCapabilities(name);

          models.push({
            name: name,
            vendor: 'ollama',
            type: 'local',
            capabilities: capabilities,
            cost_per_1m_tokens: 0.0,
            model_size: size,
            endpoint: `http://${this.nodeName}:11434`
          });
        }
      });

      return models;
    } catch (error) {
      console.error('Failed to detect Ollama models:', error.message);
      return [];
    }
  }

  /**
   * Guess model capabilities from name
   */
  guessCapabilities(modelName) {
    const name = modelName.toLowerCase();
    const capabilities = [];

    if (name.includes('code') || name.includes('coder')) capabilities.push('coding');
    if (name.includes('deepseek')) capabilities.push('reasoning', 'coding');
    if (name.includes('llama')) capabilities.push('reasoning', 'chat');
    if (name.includes('gemma')) capabilities.push('reasoning', 'chat');
    if (name.includes('phi')) capabilities.push('reasoning', 'fast');
    if (name.includes('qwen')) capabilities.push('coding');
    if (name.includes('starcoder')) capabilities.push('coding', 'completion');
    if (name.includes('vicuna')) capabilities.push('chat', 'reasoning');
    if (name.includes('wizardlm')) capabilities.push('reasoning', 'chat');
    if (name.includes('openchat')) capabilities.push('chat', 'fast');
    if (name.includes('zephyr')) capabilities.push('chat', 'helpful');
    if (name.includes('mathstral') || name.includes('math')) capabilities.push('math', 'reasoning');
    if (name.includes('sql')) capabilities.push('sql', 'coding');
    if (name.includes('llava')) capabilities.push('multimodal', 'vision');
    if (name.includes('embed')) capabilities.push('embedding');
    if (name.includes('hermes')) capabilities.push('chat', 'reasoning');
    if (name.includes('aya')) capabilities.push('multilingual', 'chat');
    if (name.includes('granite')) capabilities.push('coding', 'reasoning');
    if (name.includes('falcon')) capabilities.push('reasoning', 'chat');
    if (name.includes('solar')) capabilities.push('reasoning', 'coding');
    if (name.includes('yi')) capabilities.push('coding');
    if (name.includes('stable')) capabilities.push('chat', 'lightweight');

    // Default if nothing matched
    if (capabilities.length === 0) {
      capabilities.push('chat', 'reasoning');
    }

    return capabilities;
  }

  /**
   * Auto-register this node with auto-detected models
   */
  async autoRegister(additionalModels = []) {
    console.log('🔍 Auto-detecting node configuration...');

    // Detect hardware
    let ram_gb = 0;
    let cpu_cores = 0;

    try {
      const memInfo = execSync('grep MemTotal /proc/meminfo', { encoding: 'utf8' });
      const memKB = parseInt(memInfo.split(/\s+/)[1]);
      ram_gb = Math.floor(memKB / 1024 / 1024);
    } catch (error) {
      console.warn('Could not detect RAM');
    }

    try {
      cpu_cores = parseInt(execSync('nproc', { encoding: 'utf8' }).trim());
    } catch (error) {
      console.warn('Could not detect CPU cores');
    }

    console.log(`   Node: ${this.nodeName}`);
    console.log(`   RAM: ${ram_gb}GB`);
    console.log(`   CPU: ${cpu_cores} cores`);

    // Detect Ollama models
    const ollamaModels = this.detectOllamaModels();
    console.log(`   Ollama models: ${ollamaModels.length}`);

    // Combine with additional models
    const allModels = [...ollamaModels, ...additionalModels];

    // Determine roles
    const roles = ['worker'];
    if (ollamaModels.length > 0) roles.push('local-ollama');
    if (additionalModels.length > 0) roles.push('cloud-api');

    // Register
    return this.registerNode({
      hostname: this.nodeName,
      ram_gb: ram_gb,
      cpu_cores: cpu_cores,
      roles: roles,
      models: allModels
    });
  }
}

// Export for use as library
module.exports = FleetOrchestratorClient;

// CLI interface
if (require.main === module) {
  const client = new FleetOrchestratorClient();
  const command = process.argv[2];

  (async () => {
    switch (command) {
      case 'auto-register':
        const result = await client.autoRegister();
        if (result.success) {
          console.log('✅ Auto-registration successful!');
          console.log('   Starting heartbeat...');
          client.startHeartbeat();

          // Keep process alive
          process.on('SIGINT', () => {
            client.stopHeartbeat();
            process.exit(0);
          });
        } else {
          console.error('❌ Auto-registration failed');
          process.exit(1);
        }
        break;

      case 'heartbeat':
        const hb = await client.sendHeartbeat();
        console.log(JSON.stringify(hb, null, 2));
        break;

      case 'route':
        const capability = process.argv[3];
        if (!capability) {
          console.error('Usage: fleet-orchestrator-client.js route <capability>');
          process.exit(1);
        }
        const route = await client.routeRequest(capability);
        console.log(JSON.stringify(route, null, 2));
        break;

      case 'models':
        const models = await client.getModels();
        console.log(JSON.stringify(models, null, 2));
        break;

      case 'nodes':
        const nodes = await client.getNodes();
        console.log(JSON.stringify(nodes, null, 2));
        break;

      case 'status':
        const status = await client.getStatus();
        console.log(JSON.stringify(status, null, 2));
        break;

      case 'health':
        const health = await client.healthCheck();
        console.log(JSON.stringify(health, null, 2));
        break;

      default:
        console.log(`
Fleet Orchestrator Client - Connect to pi-02 Fleet Brain

Usage:
  fleet-orchestrator-client.js <command>

Commands:
  auto-register    Auto-detect and register this node
  heartbeat        Send single heartbeat
  route <cap>      Route request to best model
  models           List available models
  nodes            List fleet nodes
  status           Get fleet status
  health           Run health check

Examples:
  # Auto-register this node with detected models
  fleet-orchestrator-client.js auto-register

  # Send heartbeat
  fleet-orchestrator-client.js heartbeat

  # Find best model for coding
  fleet-orchestrator-client.js route coding

  # List all models
  fleet-orchestrator-client.js models

  # Get fleet status
  fleet-orchestrator-client.js status

Library Usage:
  const FleetOrchestratorClient = require('./fleet-orchestrator-client.cjs');
  const client = new FleetOrchestratorClient('pi-02', 8080);

  // Register node
  await client.autoRegister();

  // Start heartbeat
  client.startHeartbeat();

  // Route request
  const route = await client.routeRequest('coding');
  console.log('Use model:', route.model, 'on', route.node);
        `);
    }
  })();
}
