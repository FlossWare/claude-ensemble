#!/usr/bin/env node

/**
 * Fleet Node Monitor
 *
 * Provides health monitoring, heartbeat tracking, and node lifecycle management
 * for the distributed model fleet.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const http = require('http');

class FleetNodeMonitor {
  constructor(registryPath = null) {
    this.registryPath = registryPath || path.join(__dirname, 'fleet-model-registry.json');
    this.heartbeatInterval = 30000; // 30 seconds
    this.heartbeatTimeout = 90000; // 90 seconds (3 missed heartbeats)
    this.monitors = new Map();
    this.eventLog = [];
  }

  /**
   * Load registry
   */
  loadRegistry() {
    try {
      const data = fs.readFileSync(this.registryPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load registry:', error.message);
      return null;
    }
  }

  /**
   * Save registry
   */
  saveRegistry(registry) {
    try {
      registry._last_updated = new Date().toISOString();
      fs.writeFileSync(this.registryPath, JSON.stringify(registry, null, 2));
      return true;
    } catch (error) {
      console.error('Failed to save registry:', error.message);
      return false;
    }
  }

  /**
   * Log an event
   */
  logEvent(eventType, nodeName, details = {}) {
    const event = {
      timestamp: new Date().toISOString(),
      type: eventType,
      node: nodeName,
      ...details
    };
    this.eventLog.push(event);
    console.log(`[${event.timestamp}] ${eventType}: ${nodeName}`, details);

    // Keep only last 1000 events
    if (this.eventLog.length > 1000) {
      this.eventLog = this.eventLog.slice(-1000);
    }
  }

  /**
   * Check if a node is reachable via ping
   */
  async pingNode(hostname) {
    return new Promise((resolve) => {
      try {
        const start = Date.now();
        execSync(`ping -c 1 -W 2 ${hostname} > /dev/null 2>&1`);
        const latency = Date.now() - start;
        resolve({ reachable: true, latency });
      } catch (error) {
        resolve({ reachable: false, latency: null });
      }
    });
  }

  /**
   * Check Ollama service on a node
   */
  async checkOllamaService(hostname, port = 11434) {
    return new Promise((resolve) => {
      const options = {
        hostname: hostname,
        port: port,
        path: '/api/tags',
        method: 'GET',
        timeout: 5000
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            const models = JSON.parse(data);
            resolve({
              available: true,
              models: models.models || [],
              model_count: models.models?.length || 0
            });
          } catch (error) {
            resolve({ available: false, error: 'Invalid response' });
          }
        });
      });

      req.on('error', (error) => {
        resolve({ available: false, error: error.message });
      });

      req.on('timeout', () => {
        req.destroy();
        resolve({ available: false, error: 'Timeout' });
      });

      req.end();
    });
  }

  /**
   * Perform comprehensive node health check
   */
  async healthCheckNode(nodeName, nodeConfig) {
    const result = {
      node: nodeName,
      timestamp: new Date().toISOString(),
      checks: {}
    };

    // Skip localhost (always online)
    if (nodeName === 'localhost') {
      result.status = 'online';
      result.checks.ping = { reachable: true, latency: 0 };
      return result;
    }

    // Ping check
    const pingResult = await this.pingNode(nodeConfig.hostname);
    result.checks.ping = pingResult;

    if (!pingResult.reachable) {
      result.status = 'offline';
      result.reason = 'Ping failed';
      return result;
    }

    // Ollama service check (if node has local models)
    if (nodeConfig.local_models > 0) {
      const ollamaResult = await this.checkOllamaService(nodeConfig.hostname);
      result.checks.ollama = ollamaResult;

      if (!ollamaResult.available) {
        result.status = 'degraded';
        result.reason = 'Ollama service unavailable';
        return result;
      }
    }

    result.status = 'online';
    return result;
  }

  /**
   * Monitor all nodes in the fleet
   */
  async monitorFleet() {
    const registry = this.loadRegistry();
    if (!registry) return null;

    const results = {
      timestamp: new Date().toISOString(),
      nodes: {},
      summary: {
        total: 0,
        online: 0,
        offline: 0,
        degraded: 0
      }
    };

    for (const [nodeName, nodeConfig] of Object.entries(registry.nodes)) {
      const healthCheck = await this.healthCheckNode(nodeName, nodeConfig);
      results.nodes[nodeName] = healthCheck;
      results.summary.total++;

      // Update registry
      const previousStatus = nodeConfig.status;
      nodeConfig.status = healthCheck.status;
      nodeConfig.last_heartbeat = healthCheck.timestamp;

      // Log status changes
      if (previousStatus !== healthCheck.status) {
        this.logEvent('status_change', nodeName, {
          from: previousStatus,
          to: healthCheck.status,
          reason: healthCheck.reason
        });

        // Update model availability
        if (healthCheck.status === 'offline' || healthCheck.status === 'degraded') {
          nodeConfig.models?.forEach(modelName => {
            if (registry.models[modelName]) {
              registry.models[modelName].status = 'unavailable';
            }
          });
        } else if (healthCheck.status === 'online') {
          nodeConfig.models?.forEach(modelName => {
            if (registry.models[modelName]) {
              registry.models[modelName].status = 'available';
            }
          });
        }
      }

      // Count by status
      if (healthCheck.status === 'online') results.summary.online++;
      else if (healthCheck.status === 'offline') results.summary.offline++;
      else if (healthCheck.status === 'degraded') results.summary.degraded++;
    }

    // Save updated registry
    this.saveRegistry(registry);

    return results;
  }

  /**
   * Start continuous monitoring
   */
  async startMonitoring() {
    console.log('Starting fleet monitoring...');
    console.log(`Heartbeat interval: ${this.heartbeatInterval}ms`);
    console.log(`Timeout threshold: ${this.heartbeatTimeout}ms`);

    // Initial check
    const initial = await this.monitorFleet();
    console.log('Initial health check complete:');
    console.log(`  Total nodes: ${initial.summary.total}`);
    console.log(`  Online: ${initial.summary.online}`);
    console.log(`  Offline: ${initial.summary.offline}`);
    console.log(`  Degraded: ${initial.summary.degraded}`);

    // Schedule periodic checks
    const timer = setInterval(async () => {
      await this.monitorFleet();
    }, this.heartbeatInterval);

    // Cleanup on exit
    process.on('SIGINT', () => {
      console.log('\nStopping fleet monitoring...');
      clearInterval(timer);
      this.saveEventLog();
      process.exit(0);
    });

    process.on('SIGTERM', () => {
      clearInterval(timer);
      this.saveEventLog();
      process.exit(0);
    });
  }

  /**
   * Save event log to disk
   */
  saveEventLog() {
    const logPath = path.join(__dirname, 'fleet-monitor-events.json');
    try {
      fs.writeFileSync(logPath, JSON.stringify({
        events: this.eventLog,
        last_updated: new Date().toISOString()
      }, null, 2));
      console.log(`Event log saved to ${logPath}`);
    } catch (error) {
      console.error('Failed to save event log:', error.message);
    }
  }

  /**
   * Get monitoring statistics
   */
  getStatistics() {
    const stats = {
      total_events: this.eventLog.length,
      events_by_type: {},
      events_by_node: {},
      recent_events: this.eventLog.slice(-10)
    };

    this.eventLog.forEach(event => {
      // Count by type
      stats.events_by_type[event.type] = (stats.events_by_type[event.type] || 0) + 1;

      // Count by node
      stats.events_by_node[event.node] = (stats.events_by_node[event.node] || 0) + 1;
    });

    return stats;
  }

  /**
   * Node discovery - scan network for Ollama instances
   */
  async discoverNodes(ipRange = '192.168.1') {
    console.log(`Discovering Ollama nodes in ${ipRange}.0/24...`);
    const discovered = [];

    for (let i = 1; i <= 254; i++) {
      const ip = `${ipRange}.${i}`;
      const result = await this.checkOllamaService(ip);

      if (result.available) {
        console.log(`Found Ollama at ${ip} with ${result.model_count} models`);
        discovered.push({
          ip: ip,
          models: result.models,
          model_count: result.model_count,
          discovered_at: new Date().toISOString()
        });
      }
    }

    console.log(`Discovery complete. Found ${discovered.length} nodes.`);
    return discovered;
  }

  /**
   * Get current fleet health summary
   */
  async getHealthSummary() {
    const registry = this.loadRegistry();
    if (!registry) return null;

    const summary = {
      timestamp: new Date().toISOString(),
      nodes: {},
      totals: {
        nodes: 0,
        online: 0,
        offline: 0,
        models: 0,
        available_models: 0
      }
    };

    for (const [nodeName, node] of Object.entries(registry.nodes)) {
      summary.nodes[nodeName] = {
        status: node.status,
        last_heartbeat: node.last_heartbeat,
        models: node.total_models,
        uptime: this.calculateUptime(node.last_heartbeat)
      };

      summary.totals.nodes++;
      if (node.status === 'online') summary.totals.online++;
      else if (node.status === 'offline') summary.totals.offline++;
      summary.totals.models += node.total_models || 0;
    }

    // Count available models
    Object.values(registry.models).forEach(model => {
      if (model.status === 'available') {
        summary.totals.available_models++;
      }
    });

    return summary;
  }

  /**
   * Calculate uptime from last heartbeat
   */
  calculateUptime(lastHeartbeat) {
    if (!lastHeartbeat) return 'unknown';
    const now = new Date();
    const last = new Date(lastHeartbeat);
    const diffMs = now - last;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  }
}

// Export for use in other modules
module.exports = FleetNodeMonitor;

// CLI interface
if (require.main === module) {
  const monitor = new FleetNodeMonitor();
  const command = process.argv[2];

  switch (command) {
    case 'check':
      monitor.monitorFleet().then(results => {
        console.log(JSON.stringify(results, null, 2));
      });
      break;

    case 'monitor':
      monitor.startMonitoring();
      break;

    case 'stats':
      const stats = monitor.getStatistics();
      console.log(JSON.stringify(stats, null, 2));
      break;

    case 'summary':
      monitor.getHealthSummary().then(summary => {
        console.log(JSON.stringify(summary, null, 2));
      });
      break;

    case 'discover':
      const ipRange = process.argv[3] || '192.168.1';
      monitor.discoverNodes(ipRange).then(nodes => {
        console.log(JSON.stringify(nodes, null, 2));
      });
      break;

    default:
      console.log(`
Fleet Node Monitor - Health monitoring and lifecycle management

Usage:
  fleet-node-monitor.js <command> [options]

Commands:
  check               Run one-time health check on all nodes
  monitor             Start continuous monitoring (Ctrl+C to stop)
  stats               Show monitoring statistics
  summary             Show current fleet health summary
  discover [range]    Discover Ollama nodes on network (default: 192.168.1)

Examples:
  fleet-node-monitor.js check
  fleet-node-monitor.js monitor
  fleet-node-monitor.js stats
  fleet-node-monitor.js summary
  fleet-node-monitor.js discover 192.168.1
      `);
  }
}
