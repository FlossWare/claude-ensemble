#!/usr/bin/env node

/**
 * Intelligent Model Mesh Orchestrator
 *
 * Manages distributed multi-vendor model fleet with:
 * - Zero duplication (each model on exactly ONE node)
 * - Dynamic node registration/deregistration
 * - Smart routing based on capabilities and availability
 * - Health monitoring and failure handling
 * - Cost-aware routing (cloud vs local)
 * - Usage tracking for Thompson Sampling
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class ModelMeshOrchestrator {
  constructor(registryPath = null) {
    this.registryPath = registryPath || path.join(__dirname, 'fleet-model-registry.json');
    this.registry = this.loadRegistry();
    this.usageStats = this.loadUsageStats();
    this.heartbeatInterval = 30000; // 30 seconds
    this.heartbeatTimeout = 90000; // 90 seconds (3 missed heartbeats)
    this.heartbeatTimer = null;
  }

  /**
   * Load model registry from disk
   */
  loadRegistry() {
    try {
      const data = fs.readFileSync(this.registryPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error(`Failed to load registry from ${this.registryPath}:`, error.message);
      return this.createEmptyRegistry();
    }
  }

  /**
   * Save registry to disk
   */
  saveRegistry() {
    try {
      this.registry._last_updated = new Date().toISOString();
      fs.writeFileSync(this.registryPath, JSON.stringify(this.registry, null, 2));
      return true;
    } catch (error) {
      console.error('Failed to save registry:', error.message);
      return false;
    }
  }

  /**
   * Create empty registry structure
   */
  createEmptyRegistry() {
    return {
      _version: '1.0',
      _last_updated: new Date().toISOString(),
      models: {},
      nodes: {},
      distribution_stats: {
        total_models: 0,
        cloud_api_models: 0,
        ollama_local_models: 0,
        total_nodes: 0,
        duplication_count: 0,
        models_per_node: {}
      }
    };
  }

  /**
   * Load usage statistics
   */
  loadUsageStats() {
    const statsPath = path.join(__dirname, 'fleet-usage-stats.json');
    try {
      const data = fs.readFileSync(statsPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      return {
        models: {},
        last_reset: new Date().toISOString()
      };
    }
  }

  /**
   * Save usage statistics
   */
  saveUsageStats() {
    const statsPath = path.join(__dirname, 'fleet-usage-stats.json');
    try {
      fs.writeFileSync(statsPath, JSON.stringify(this.usageStats, null, 2));
    } catch (error) {
      console.error('Failed to save usage stats:', error.message);
    }
  }

  /**
   * Register a node with its models
   * @param {string} nodeName - Node identifier
   * @param {Object} nodeConfig - Node configuration
   * @param {Array} models - List of model configurations
   * @returns {Object} Registration result
   */
  registerNode(nodeName, nodeConfig, models) {
    console.log(`Registering node: ${nodeName} with ${models.length} models`);

    // Validate no duplication
    const duplicates = this.findDuplicates(models);
    if (duplicates.length > 0) {
      return {
        success: false,
        error: 'Duplication detected',
        duplicates: duplicates,
        message: 'Each model must be on exactly ONE node'
      };
    }

    // Register node
    this.registry.nodes[nodeName] = {
      ...nodeConfig,
      status: 'online',
      last_heartbeat: new Date().toISOString(),
      models: models.map(m => m.name),
      total_models: models.length,
      cloud_models: models.filter(m => m.type === 'cloud-api').length,
      local_models: models.filter(m => m.type === 'local').length
    };

    // Register models
    models.forEach(model => {
      this.registry.models[model.name] = {
        ...model,
        node: nodeName,
        status: 'available',
        fallback_nodes: []
      };
    });

    // Update stats
    this.updateDistributionStats();
    this.saveRegistry();

    return {
      success: true,
      node: nodeName,
      models_registered: models.length,
      message: `Node ${nodeName} registered successfully`
    };
  }

  /**
   * Unregister a node (node going offline)
   * @param {string} nodeName - Node identifier
   * @returns {Object} Unregistration result
   */
  unregisterNode(nodeName) {
    if (!this.registry.nodes[nodeName]) {
      return {
        success: false,
        error: 'Node not found',
        node: nodeName
      };
    }

    const node = this.registry.nodes[nodeName];
    const affectedModels = node.models || [];

    // Mark node offline
    node.status = 'offline';
    node.last_heartbeat = new Date().toISOString();

    // Mark all models on this node as unavailable
    affectedModels.forEach(modelName => {
      if (this.registry.models[modelName]) {
        this.registry.models[modelName].status = 'unavailable';
      }
    });

    this.updateDistributionStats();
    this.saveRegistry();

    return {
      success: true,
      node: nodeName,
      affected_models: affectedModels.length,
      models: affectedModels,
      message: `Node ${nodeName} marked offline, ${affectedModels.length} models unavailable`
    };
  }

  /**
   * Find duplicate models across nodes
   * @param {Array} newModels - Models being registered
   * @returns {Array} List of duplicates
   */
  findDuplicates(newModels) {
    const duplicates = [];
    newModels.forEach(model => {
      if (this.registry.models[model.name]) {
        duplicates.push({
          model: model.name,
          existing_node: this.registry.models[model.name].node,
          new_node: model.node
        });
      }
    });
    return duplicates;
  }

  /**
   * Route a request to the best available model
   * @param {Array|string} capabilities - Required capabilities
   * @param {Object} constraints - Routing constraints
   * @returns {Object} Routing result
   */
  routeRequest(capabilities, constraints = {}) {
    const capArray = Array.isArray(capabilities) ? capabilities : [capabilities];

    // Find matching models
    const candidates = Object.entries(this.registry.models)
      .filter(([name, model]) => {
        // Must be available
        if (model.status !== 'available') return false;

        // Must have required capabilities
        if (!capArray.every(cap => model.capabilities?.includes(cap))) return false;

        // Check constraints
        if (constraints.type && model.type !== constraints.type) return false;
        if (constraints.vendor && model.vendor !== constraints.vendor) return false;
        if (constraints.maxCost && model.cost_per_1m_tokens > constraints.maxCost) return false;

        // Check node status
        const node = this.registry.nodes[model.node];
        if (!node || node.status !== 'online') return false;

        return true;
      })
      .map(([name, model]) => ({
        name,
        ...model,
        nodeInfo: this.registry.nodes[model.node]
      }));

    if (candidates.length === 0) {
      return {
        success: false,
        error: 'No matching models available',
        capabilities: capArray,
        constraints: constraints,
        suggestion: this.suggestAlternatives(capArray)
      };
    }

    // Score candidates
    const scored = candidates.map(model => ({
      ...model,
      score: this.scoreModel(model, constraints)
    }));

    // Sort by score (higher is better)
    scored.sort((a, b) => b.score - a.score);
    const best = scored[0];

    // Track usage
    this.trackUsage(best.name);

    return {
      success: true,
      model: best.name,
      node: best.node,
      endpoint: best.endpoint,
      vendor: best.vendor,
      type: best.type,
      cost_per_1m_tokens: best.cost_per_1m_tokens,
      capabilities: best.capabilities,
      score: best.score,
      alternatives: scored.slice(1, 4).map(m => ({
        model: m.name,
        node: m.node,
        score: m.score
      }))
    };
  }

  /**
   * Score a model for routing (higher is better)
   */
  scoreModel(model, constraints = {}) {
    let score = 0;

    // Prefer localhost (zero network latency)
    if (model.node === 'localhost') score += 100;

    // Prefer local over cloud (zero cost)
    if (model.type === 'local') score += 50;

    // Cost factor (lower cost is better)
    score -= model.cost_per_1m_tokens * 2;

    // Usage frequency (prefer frequently used models - they're battle-tested)
    const usage = this.usageStats.models[model.name];
    if (usage) {
      score += Math.log(usage.count + 1) * 10;
    }

    // Node priority
    score += (10 - model.nodeInfo.priority) * 5;

    // Preference hints from constraints
    if (constraints.preferLocal && model.type === 'local') score += 30;
    if (constraints.preferCloud && model.type === 'cloud-api') score += 30;
    if (constraints.preferNode && model.node === constraints.preferNode) score += 50;

    return score;
  }

  /**
   * Suggest alternative models when no exact match found
   */
  suggestAlternatives(capabilities) {
    // Find models with at least one matching capability
    const partialMatches = Object.entries(this.registry.models)
      .filter(([name, model]) => {
        if (model.status !== 'available') return false;
        const node = this.registry.nodes[model.node];
        if (!node || node.status !== 'online') return false;
        return capabilities.some(cap => model.capabilities?.includes(cap));
      })
      .map(([name, model]) => ({
        name,
        matching_capabilities: capabilities.filter(cap => model.capabilities?.includes(cap)),
        missing_capabilities: capabilities.filter(cap => !model.capabilities?.includes(cap)),
        node: model.node,
        type: model.type
      }))
      .slice(0, 5);

    return partialMatches;
  }

  /**
   * Track model usage for Thompson Sampling
   */
  trackUsage(modelName) {
    if (!this.usageStats.models[modelName]) {
      this.usageStats.models[modelName] = {
        count: 0,
        last_used: null,
        first_used: new Date().toISOString()
      };
    }

    this.usageStats.models[modelName].count += 1;
    this.usageStats.models[modelName].last_used = new Date().toISOString();
    this.saveUsageStats();
  }

  /**
   * Health check - ping all nodes
   * @returns {Object} Health check results
   */
  async healthCheck() {
    console.log('Running fleet health check...');
    const results = {};

    for (const [nodeName, node] of Object.entries(this.registry.nodes)) {
      if (nodeName === 'localhost') {
        // localhost always online
        results[nodeName] = {
          status: 'online',
          latency_ms: 0,
          checked_at: new Date().toISOString()
        };
        node.status = 'online';
        node.last_heartbeat = new Date().toISOString();
        continue;
      }

      try {
        // Try to ping the node
        const start = Date.now();
        execSync(`ping -c 1 -W 1 ${node.hostname} > /dev/null 2>&1`);
        const latency = Date.now() - start;

        results[nodeName] = {
          status: 'online',
          latency_ms: latency,
          checked_at: new Date().toISOString()
        };

        node.status = 'online';
        node.last_heartbeat = new Date().toISOString();

        // Mark models as available
        node.models?.forEach(modelName => {
          if (this.registry.models[modelName]) {
            this.registry.models[modelName].status = 'available';
          }
        });

      } catch (error) {
        results[nodeName] = {
          status: 'offline',
          error: 'Ping failed',
          checked_at: new Date().toISOString()
        };

        node.status = 'offline';

        // Mark models as unavailable
        node.models?.forEach(modelName => {
          if (this.registry.models[modelName]) {
            this.registry.models[modelName].status = 'unavailable';
          }
        });
      }
    }

    this.updateDistributionStats();
    this.saveRegistry();

    return results;
  }

  /**
   * Start periodic health checks
   */
  startHealthMonitoring() {
    console.log(`Starting health monitoring (interval: ${this.heartbeatInterval}ms)`);
    this.healthCheck(); // Run immediately
    this.heartbeatTimer = setInterval(() => {
      this.healthCheck();
    }, this.heartbeatInterval);
  }

  /**
   * Stop health monitoring
   */
  stopHealthMonitoring() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
      console.log('Health monitoring stopped');
    }
  }

  /**
   * Get all available models
   * @returns {Array} List of available models
   */
  getAvailableModels() {
    return Object.entries(this.registry.models)
      .filter(([name, model]) => {
        if (model.status !== 'available') return false;
        const node = this.registry.nodes[model.node];
        return node && node.status === 'online';
      })
      .map(([name, model]) => ({
        name,
        vendor: model.vendor,
        type: model.type,
        node: model.node,
        capabilities: model.capabilities,
        cost_per_1m_tokens: model.cost_per_1m_tokens
      }));
  }

  /**
   * Get node status
   */
  getNodeStatus(nodeName) {
    const node = this.registry.nodes[nodeName];
    if (!node) {
      return {
        success: false,
        error: 'Node not found',
        node: nodeName
      };
    }

    const models = node.models?.map(modelName => {
      const model = this.registry.models[modelName];
      return {
        name: modelName,
        status: model?.status || 'unknown',
        type: model?.type,
        vendor: model?.vendor
      };
    }) || [];

    return {
      success: true,
      node: nodeName,
      status: node.status,
      last_heartbeat: node.last_heartbeat,
      ram_gb: node.ram_gb,
      cpu_cores: node.cpu_cores,
      roles: node.roles,
      total_models: node.total_models,
      available_models: models.filter(m => m.status === 'available').length,
      models: models
    };
  }

  /**
   * Update distribution statistics
   */
  updateDistributionStats() {
    const stats = {
      total_models: Object.keys(this.registry.models).length,
      cloud_api_models: 0,
      ollama_local_models: 0,
      total_nodes: Object.keys(this.registry.nodes).length,
      online_nodes: 0,
      duplication_count: 0,
      models_per_node: {},
      available_models: 0
    };

    // Count models by type
    Object.values(this.registry.models).forEach(model => {
      if (model.type === 'cloud-api') stats.cloud_api_models++;
      if (model.type === 'local') stats.ollama_local_models++;
      if (model.status === 'available') stats.available_models++;
    });

    // Count models per node and online nodes
    Object.entries(this.registry.nodes).forEach(([name, node]) => {
      stats.models_per_node[name] = node.total_models || 0;
      if (node.status === 'online') stats.online_nodes++;
    });

    // Check for duplications (should always be zero)
    const modelNodes = new Map();
    Object.entries(this.registry.models).forEach(([name, model]) => {
      if (modelNodes.has(name)) {
        stats.duplication_count++;
      }
      modelNodes.set(name, model.node);
    });

    this.registry.distribution_stats = stats;
  }

  /**
   * Suggest model rebalancing
   * @returns {Object} Rebalancing suggestions
   */
  rebalance() {
    const suggestions = [];
    const nodeLoads = {};

    // Calculate current load per node
    Object.entries(this.registry.nodes).forEach(([name, node]) => {
      nodeLoads[name] = {
        current: node.total_models || 0,
        capacity: this.estimateCapacity(node),
        utilization: (node.total_models || 0) / this.estimateCapacity(node)
      };
    });

    // Find overloaded and underutilized nodes
    const overloaded = Object.entries(nodeLoads)
      .filter(([name, load]) => load.utilization > 0.8)
      .map(([name]) => name);

    const underutilized = Object.entries(nodeLoads)
      .filter(([name, load]) => load.utilization < 0.3)
      .map(([name]) => name);

    if (overloaded.length > 0 && underutilized.length > 0) {
      suggestions.push({
        type: 'rebalance',
        from: overloaded,
        to: underutilized,
        reason: 'Load imbalance detected'
      });
    }

    return {
      balanced: suggestions.length === 0,
      suggestions: suggestions,
      current_loads: nodeLoads
    };
  }

  /**
   * Estimate node capacity based on RAM and CPU
   */
  estimateCapacity(node) {
    // Rough estimate: 1 model per 2GB RAM or 1 CPU core, whichever is lower
    const ramCapacity = Math.floor(node.ram_gb / 2);
    const cpuCapacity = node.cpu_cores * 3; // Can handle 3x models with good parallelism
    return Math.min(ramCapacity, cpuCapacity);
  }

  /**
   * Get comprehensive fleet status
   */
  getFleetStatus() {
    return {
      registry_version: this.registry._version,
      last_updated: this.registry._last_updated,
      stats: this.registry.distribution_stats,
      nodes: Object.entries(this.registry.nodes).map(([name, node]) => ({
        name,
        status: node.status,
        models: node.total_models,
        online: node.status === 'online'
      })),
      top_models: this.getTopModels(10),
      health: this.registry.distribution_stats.online_nodes > 0 ? 'healthy' : 'degraded'
    };
  }

  /**
   * Get most-used models
   */
  getTopModels(limit = 10) {
    return Object.entries(this.usageStats.models)
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, limit)
      .map(([name, stats]) => ({
        model: name,
        usage_count: stats.count,
        last_used: stats.last_used
      }));
  }
}

// Export for use in other modules
module.exports = ModelMeshOrchestrator;

// CLI interface
if (require.main === module) {
  const orchestrator = new ModelMeshOrchestrator();
  const command = process.argv[2];

  switch (command) {
    case 'status':
      console.log(JSON.stringify(orchestrator.getFleetStatus(), null, 2));
      break;

    case 'health':
      orchestrator.healthCheck().then(results => {
        console.log(JSON.stringify(results, null, 2));
      });
      break;

    case 'monitor':
      console.log('Starting health monitoring... (Ctrl+C to stop)');
      orchestrator.startHealthMonitoring();
      // Keep process alive
      process.on('SIGINT', () => {
        orchestrator.stopHealthMonitoring();
        process.exit(0);
      });
      break;

    case 'models':
      const available = orchestrator.getAvailableModels();
      console.log(`Available models: ${available.length}`);
      console.log(JSON.stringify(available, null, 2));
      break;

    case 'node':
      const nodeName = process.argv[3];
      if (!nodeName) {
        console.error('Usage: orchestrator-model-mesh.js node <node-name>');
        process.exit(1);
      }
      const status = orchestrator.getNodeStatus(nodeName);
      console.log(JSON.stringify(status, null, 2));
      break;

    case 'route':
      const capability = process.argv[3];
      if (!capability) {
        console.error('Usage: orchestrator-model-mesh.js route <capability>');
        process.exit(1);
      }
      const route = orchestrator.routeRequest(capability);
      console.log(JSON.stringify(route, null, 2));
      break;

    case 'rebalance':
      const suggestions = orchestrator.rebalance();
      console.log(JSON.stringify(suggestions, null, 2));
      break;

    default:
      console.log(`
Model Mesh Orchestrator - Distributed Multi-Vendor Fleet Manager

Usage:
  orchestrator-model-mesh.js <command> [options]

Commands:
  status              Show fleet status
  health              Run health check on all nodes
  monitor             Start continuous health monitoring
  models              List all available models
  node <name>         Show node status
  route <capability>  Route request to best model
  rebalance           Suggest load rebalancing

Examples:
  orchestrator-model-mesh.js status
  orchestrator-model-mesh.js health
  orchestrator-model-mesh.js monitor
  orchestrator-model-mesh.js models
  orchestrator-model-mesh.js node localhost
  orchestrator-model-mesh.js route coding
  orchestrator-model-mesh.js rebalance
      `);
  }
}
