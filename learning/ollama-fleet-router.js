#!/usr/bin/env node

/**
 * Ollama Fleet Router - Smart routing to distributed Ollama instances
 *
 * Features:
 * - Auto-discovery of model locations via registry
 * - Health checks with fallback routing
 * - Load balancing for duplicated models
 * - Network latency optimization (localhost first when available)
 * - Metrics tracking (requests/model, latency, failures)
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

const REGISTRY_PATH = join(homedir(), '.claude/learning/ollama-fleet-distribution.json');
const HEALTH_CHECK_INTERVAL = 30000; // 30s
const REQUEST_TIMEOUT = 120000; // 2min for large models

class OllamaFleetRouter {
  constructor() {
    this.registry = this.loadRegistry();
    this.healthStatus = new Map(); // hostname -> {healthy: bool, lastCheck: timestamp, latency: ms}
    this.metrics = new Map(); // model -> {requests: count, failures: count, avgLatency: ms}
    this.startHealthChecks();
  }

  loadRegistry() {
    try {
      const data = JSON.parse(readFileSync(REGISTRY_PATH, 'utf8'));
      return data.model_registry;
    } catch (err) {
      throw new Error(`Failed to load Ollama registry: ${err.message}`);
    }
  }

  /**
   * Route a model request to the best available host
   * @param {string} modelName - Ollama model name (e.g., "qwen2.5-coder:7b")
   * @param {object} options - Request options
   * @returns {Promise<object>} - {host, port, url, latency}
   */
  async route(modelName, options = {}) {
    const modelInfo = this.registry[modelName];
    if (!modelInfo) {
      throw new Error(`Model "${modelName}" not found in fleet registry`);
    }

    // Sort hosts by priority and health status
    const sortedHosts = this.sortHostsByPreference(modelInfo.hosts);

    // Try each host in order until success
    for (const hostConfig of sortedHosts) {
      const { hostname, port, priority } = hostConfig;
      const health = this.healthStatus.get(hostname);

      // Skip unhealthy hosts unless it's the last option
      if (health && !health.healthy && sortedHosts.indexOf(hostConfig) < sortedHosts.length - 1) {
        console.warn(`Skipping unhealthy host ${hostname} for ${modelName}`);
        continue;
      }

      try {
        const url = `http://${hostname}:${port}`;
        const startTime = Date.now();

        // Test connectivity (lightweight check before routing)
        await this.checkModelAvailable(url, modelName);

        const latency = Date.now() - startTime;
        this.updateMetrics(modelName, true, latency);

        return {
          host: hostname,
          port,
          url,
          latency,
          modelInfo: {
            size_gb: modelInfo.size_gb,
            category: modelInfo.category,
            min_ram_gb: modelInfo.min_ram_gb
          }
        };
      } catch (err) {
        console.error(`Failed to route to ${hostname}:${port} for ${modelName}: ${err.message}`);
        this.updateMetrics(modelName, false, 0);
        this.markUnhealthy(hostname);
        // Continue to next host
      }
    }

    throw new Error(`All hosts failed for model "${modelName}"`);
  }

  /**
   * Sort hosts by preference: localhost > healthy > priority > latency
   */
  sortHostsByPreference(hosts) {
    return hosts.slice().sort((a, b) => {
      // Localhost always first
      if (a.hostname === 'localhost') return -1;
      if (b.hostname === 'localhost') return 1;

      const healthA = this.healthStatus.get(a.hostname);
      const healthB = this.healthStatus.get(b.hostname);

      // Healthy hosts before unhealthy
      if (healthA?.healthy && !healthB?.healthy) return -1;
      if (!healthA?.healthy && healthB?.healthy) return 1;

      // Priority (lower number = higher priority)
      if (a.priority !== b.priority) return a.priority - b.priority;

      // Latency (lower is better)
      const latencyA = healthA?.latency || Infinity;
      const latencyB = healthB?.latency || Infinity;
      return latencyA - latencyB;
    });
  }

  /**
   * Check if model is available on the given Ollama instance
   */
  async checkModelAvailable(baseUrl, modelName) {
    const response = await fetch(`${baseUrl}/api/tags`, {
      signal: AbortSignal.timeout(5000)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const modelExists = data.models?.some(m => m.name === modelName);

    if (!modelExists) {
      throw new Error(`Model ${modelName} not found on ${baseUrl}`);
    }

    return true;
  }

  /**
   * Perform health check on a specific host
   */
  async healthCheck(hostname, port = 11434) {
    const url = `http://${hostname}:${port}`;
    const startTime = Date.now();

    try {
      const response = await fetch(`${url}/api/tags`, {
        signal: AbortSignal.timeout(5000)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const latency = Date.now() - startTime;
      this.healthStatus.set(hostname, {
        healthy: true,
        lastCheck: Date.now(),
        latency,
        url
      });

      return true;
    } catch (err) {
      this.healthStatus.set(hostname, {
        healthy: false,
        lastCheck: Date.now(),
        error: err.message
      });

      return false;
    }
  }

  /**
   * Start periodic health checks for all fleet nodes
   */
  startHealthChecks() {
    const allHosts = new Set();

    // Extract all unique hostnames from registry
    Object.values(this.registry).forEach(model => {
      model.hosts.forEach(host => allHosts.add(host.hostname));
    });

    // Initial health check
    allHosts.forEach(hostname => {
      this.healthCheck(hostname);
    });

    // Periodic health checks
    setInterval(() => {
      allHosts.forEach(hostname => {
        this.healthCheck(hostname);
      });
    }, HEALTH_CHECK_INTERVAL);
  }

  markUnhealthy(hostname) {
    const current = this.healthStatus.get(hostname) || {};
    this.healthStatus.set(hostname, {
      ...current,
      healthy: false,
      lastCheck: Date.now()
    });
  }

  updateMetrics(modelName, success, latency) {
    const current = this.metrics.get(modelName) || {
      requests: 0,
      failures: 0,
      totalLatency: 0,
      avgLatency: 0
    };

    current.requests++;
    if (!success) {
      current.failures++;
    } else {
      current.totalLatency += latency;
      current.avgLatency = current.totalLatency / (current.requests - current.failures);
    }

    this.metrics.set(modelName, current);
  }

  /**
   * Get fleet status report
   */
  getStatus() {
    const hostStatus = {};
    this.healthStatus.forEach((status, hostname) => {
      hostStatus[hostname] = status;
    });

    const modelMetrics = {};
    this.metrics.forEach((metrics, modelName) => {
      modelMetrics[modelName] = {
        ...metrics,
        successRate: ((metrics.requests - metrics.failures) / metrics.requests * 100).toFixed(2) + '%'
      };
    });

    return {
      hosts: hostStatus,
      models: modelMetrics,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Find all models matching a category
   */
  getModelsByCategory(category) {
    return Object.entries(this.registry)
      .filter(([_, info]) => info.category === category)
      .map(([name, info]) => ({ name, ...info }));
  }

  /**
   * Get best model recommendation for a task
   */
  recommendModel(task) {
    const recommendations = {
      'coding': ['qwen2.5-coder:7b', 'yi-coder:9b', 'granite-code:8b', 'codestral:22b'],
      'reasoning': ['deepseek-r1:14b', 'deepseek-r1:32b', 'mathstral:7b'],
      'general': ['gemma4:12b', 'vicuna:13b', 'solar:10.7b'],
      'sql': ['sqlcoder:7b'],
      'vision': ['llava:13b'],
      'embedding': ['granite-embedding', 'nomic-embed-text']
    };

    const models = recommendations[task] || recommendations.general;

    // Return first available model based on health
    for (const modelName of models) {
      const modelInfo = this.registry[modelName];
      if (!modelInfo) continue;

      const healthyHost = modelInfo.hosts.find(host => {
        const health = this.healthStatus.get(host.hostname);
        return !health || health.healthy;
      });

      if (healthyHost) {
        return { modelName, ...modelInfo };
      }
    }

    return null;
  }
}

// CLI interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const router = new OllamaFleetRouter();

  const command = process.argv[2];

  switch (command) {
    case 'route': {
      const modelName = process.argv[3];
      if (!modelName) {
        console.error('Usage: ollama-fleet-router.js route <model-name>');
        process.exit(1);
      }

      router.route(modelName)
        .then(result => {
          console.log(JSON.stringify(result, null, 2));
        })
        .catch(err => {
          console.error('Routing failed:', err.message);
          process.exit(1);
        });
      break;
    }

    case 'status': {
      setTimeout(() => {
        const status = router.getStatus();
        console.log(JSON.stringify(status, null, 2));
        process.exit(0);
      }, 2000); // Wait for initial health checks
      break;
    }

    case 'recommend': {
      const task = process.argv[3];
      if (!task) {
        console.error('Usage: ollama-fleet-router.js recommend <task>');
        console.error('Tasks: coding, reasoning, general, sql, vision, embedding');
        process.exit(1);
      }

      setTimeout(() => {
        const recommendation = router.recommendModel(task);
        if (recommendation) {
          console.log(JSON.stringify(recommendation, null, 2));
        } else {
          console.error('No healthy model found for task:', task);
          process.exit(1);
        }
        process.exit(0);
      }, 2000);
      break;
    }

    case 'list': {
      const category = process.argv[3];
      const models = category
        ? router.getModelsByCategory(category)
        : Object.entries(router.registry).map(([name, info]) => ({ name, ...info }));

      console.log(JSON.stringify(models, null, 2));
      process.exit(0);
      break;
    }

    default: {
      console.log(`Ollama Fleet Router

Usage:
  ollama-fleet-router.js route <model-name>     Route to best host for model
  ollama-fleet-router.js status                 Show fleet health status
  ollama-fleet-router.js recommend <task>       Recommend best model for task
  ollama-fleet-router.js list [category]        List all models (optionally filtered)

Examples:
  ollama-fleet-router.js route "qwen2.5-coder:7b"
  ollama-fleet-router.js recommend coding
  ollama-fleet-router.js list coding
`);
      process.exit(0);
    }
  }
}

export default OllamaFleetRouter;
