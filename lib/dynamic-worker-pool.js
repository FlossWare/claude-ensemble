#!/usr/bin/env node
// Dynamic Worker Pool Discovery
// Re-queries fleet nodes before each batch to detect nodes joining mid-workflow
// Integrates with existing health monitoring and circuit breaker

const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const EventEmitter = require('events');

const FLEET_CONFIG = path.join(os.homedir(), '.claude', 'fleet.json');
const CACHE_TTL_MS = 10000; // 10 seconds cache
const CONFIG_RETRY_MAX_AGE_MS = 300000; // 5 minutes max stale cache on config errors
const MAX_HEALTH_RESPONSE_SIZE = 10240; // 10KB max response body
const CONFIG_RETRY_DELAYS = [100, 500, 1000, 2000]; // Exponential backoff

/**
 * Worker Pool Discovery with proper cache management and error handling
 * Can be used as singleton (default) or instantiated per workflow
 */
class WorkerPool extends EventEmitter {
  constructor(options = {}) {
    super();
    this.cachedWorkers = null;
    this.cacheTimestamp = 0;
    this.inflightDiscovery = null;
    this.configErrorCount = 0;
    this.lastConfigError = null;
    this.options = {
      cacheTTL: options.cacheTTL || CACHE_TTL_MS,
      configRetryMaxAge: options.configRetryMaxAge || CONFIG_RETRY_MAX_AGE_MS,
      onError: options.onError || ((err) => console.error('WorkerPool error:', err))
    };
  }

  /**
   * Health check a single node with proper resource limits and race condition handling
   * @param {string} host - Node hostname
   * @param {number} port - Health check port (default 7340)
   * @param {number} timeout - Timeout in ms (default 2000)
   * @returns {Promise<Object|null>} Health status or null if unreachable
   */
  async checkNodeHealth(host, port = 7340, timeout = 2000) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      let resolved = false;

      // Guard against multiple resolve() calls
      const safeResolve = (val) => {
        if (!resolved) {
          resolved = true;
          resolve(val);
        }
      };

      const req = http.request({
        host,
        port,
        path: '/health',
        method: 'GET',
        timeout
      }, (res) => {
        let body = '';
        let bodySize = 0;

        res.on('data', chunk => {
          bodySize += chunk.length;

          // Enforce body size limit to prevent OOM
          if (bodySize > MAX_HEALTH_RESPONSE_SIZE) {
            req.destroy();
            safeResolve({
              alive: false,
              error: `Response too large (>${MAX_HEALTH_RESPONSE_SIZE} bytes)`,
              responseTime: Date.now() - startTime
            });
            return;
          }

          body += chunk;
        });

        res.on('end', () => {
          const duration = Date.now() - startTime;

          try {
            const data = JSON.parse(body);
            if (res.statusCode === 200 && data.status === 'ok') {
              safeResolve({
                alive: true,
                node: data.node,
                session: data.session,
                models: data.models || [], // Actual model list from endpoint
                responseTime: duration
              });
            } else {
              safeResolve({
                alive: false,
                error: `HTTP ${res.statusCode}`,
                responseTime: duration
              });
            }
          } catch (err) {
            safeResolve({
              alive: false,
              error: 'Invalid JSON',
              responseTime: duration
            });
          }
        });
      });

      req.on('error', (err) => {
        safeResolve({
          alive: false,
          error: err.message,
          responseTime: Date.now() - startTime
        });
      });

      req.on('timeout', () => {
        req.destroy();
        safeResolve({
          alive: false,
          error: 'Timeout',
          responseTime: timeout
        });
      });

      // Add socket-level timeout for faster failure detection
      req.on('socket', (socket) => {
        socket.setTimeout(timeout);
        socket.on('timeout', () => {
          req.destroy();
          safeResolve({
            alive: false,
            error: 'Socket timeout',
            responseTime: Date.now() - startTime
          });
        });
      });

      req.end();
    });
  }

  /**
   * Read fleet config with retry and exponential backoff
   * @returns {Promise<Object|null>} Fleet config or null if permanently failed
   */
  async readFleetConfig() {
    for (let attempt = 0; attempt < CONFIG_RETRY_DELAYS.length; attempt++) {
      try {
        const configData = fs.readFileSync(FLEET_CONFIG, 'utf8');
        const config = JSON.parse(configData);

        // Validate config structure
        if (!config.nodes || !Array.isArray(config.nodes)) {
          throw new Error('Invalid fleet config: missing nodes array');
        }

        // Reset error tracking on success
        this.configErrorCount = 0;
        this.lastConfigError = null;

        return config;
      } catch (err) {
        this.configErrorCount++;
        this.lastConfigError = err;
        this.options.onError(new Error(`Fleet config read failed (attempt ${attempt + 1}): ${err.message}`));

        // Last attempt - don't delay
        if (attempt === CONFIG_RETRY_DELAYS.length - 1) {
          break;
        }

        // Exponential backoff
        await new Promise(r => setTimeout(r, CONFIG_RETRY_DELAYS[attempt]));
      }
    }

    return null; // All retries exhausted
  }

  /**
   * Discover available workers from fleet.json with health checks
   * @param {Object} options - Configuration options
   * @param {boolean} options.forceRefresh - Bypass cache and force fresh discovery
   * @param {number} options.timeout - Health check timeout in ms (default 2000)
   * @param {number} options.port - Health check port (default 7340)
   * @param {boolean} options.includeModels - Include model capabilities in response (default false)
   * @returns {Promise<Array>} List of available worker nodes
   */
  async getAvailableWorkers(options = {}) {
    const {
      forceRefresh = false,
      timeout = 2000,
      port = 7340,
      includeModels = false
    } = options;

    const now = Date.now();

    // Check cache (TTL-based)
    if (!forceRefresh && this.cachedWorkers && (now - this.cacheTimestamp) < this.options.cacheTTL) {
      return this.cachedWorkers;
    }

    // Deduplicate concurrent discovery requests
    if (this.inflightDiscovery) {
      return this.inflightDiscovery;
    }

    // Start discovery
    this.inflightDiscovery = this._doDiscovery(port, timeout, includeModels);

    try {
      const result = await this.inflightDiscovery;
      return result;
    } finally {
      this.inflightDiscovery = null;
    }
  }

  /**
   * Internal discovery implementation
   * @private
   */
  async _doDiscovery(port, timeout, includeModels) {
    const now = Date.now();
    const cacheAge = this.cachedWorkers ? now - this.cacheTimestamp : null;

    // Try to read fleet configuration with retry
    const fleetConfig = await this.readFleetConfig();

    if (!fleetConfig) {
      // Config read failed after all retries
      const staleCacheAge = cacheAge || Infinity;

      // If we have stale cache and it's not too old, use it
      if (this.cachedWorkers && staleCacheAge < this.options.configRetryMaxAge) {
        this.options.onError(new Error(
          `Fleet config unavailable, using stale cache (age: ${Math.round(staleCacheAge / 1000)}s)`
        ));
        this.emit('stale-cache-used', { age: staleCacheAge, reason: 'config-unavailable' });
        return this.cachedWorkers;
      }

      // No valid cache - this is a critical error
      const error = new Error(
        `Fleet config permanently unavailable and no valid cache (last error: ${this.lastConfigError?.message})`
      );
      this.options.onError(error);
      this.emit('discovery-failed', { error: error.message, attempts: this.configErrorCount });
      throw error;
    }

    // Filter for worker nodes (explicit role check)
    const workerNodes = fleetConfig.nodes.filter(node => {
      // Must have role='worker' AND not explicitly disabled
      return node.role === 'worker' && node.worker_disabled !== true;
    });

    // If no workers defined in config, this is legitimate empty state
    if (workerNodes.length === 0) {
      console.log('No worker nodes defined in fleet config');
      this.cachedWorkers = [];
      this.cacheTimestamp = now;
      return [];
    }

    // Health check all worker nodes in parallel with error isolation
    const healthChecks = workerNodes.map(async (node) => {
      try {
        const health = await this.checkNodeHealth(node.host, port, timeout);

        return {
          name: node.name,
          host: node.host,
          cpu: node.cpu,
          memory: node.memory,
          capabilities: node.capabilities || [],
          role: node.role,
          health: health.alive,
          responseTime: health.responseTime,
          error: health.error || null,
          session: health.alive ? health.session : null,
          models: health.alive ? health.models : []
        };
      } catch (err) {
        // Isolate errors - don't let one bad node crash entire discovery
        this.options.onError(new Error(`Health check failed for ${node.name}: ${err.message}`));
        return {
          name: node.name,
          host: node.host,
          cpu: node.cpu,
          memory: node.memory,
          capabilities: node.capabilities || [],
          role: node.role,
          health: false,
          responseTime: timeout,
          error: err.message,
          session: null,
          models: []
        };
      }
    });

    const results = await Promise.all(healthChecks);

    // Filter for healthy nodes only
    const availableWorkers = results.filter(node => node.health);

    // Cache results
    this.cachedWorkers = availableWorkers;
    this.cacheTimestamp = now;

    // Log discovery results
    const healthyCount = availableWorkers.length;
    const totalCount = workerNodes.length;
    const unhealthyNodes = results.filter(n => !n.health).map(n => `${n.name} (${n.error})`);

    console.log(`Worker discovery: ${healthyCount}/${totalCount} healthy`);
    if (unhealthyNodes.length > 0) {
      console.log(`Unavailable nodes: ${unhealthyNodes.join(', ')}`);
    }

    this.emit('discovery-complete', {
      healthy: healthyCount,
      total: totalCount,
      unavailable: unhealthyNodes
    });

    // Return based on includeModels flag
    if (includeModels) {
      return availableWorkers;
    } else {
      // Extract actual models from health endpoint responses
      const models = new Set();

      availableWorkers.forEach(node => {
        if (node.models && Array.isArray(node.models)) {
          node.models.forEach(model => models.add(model));
        }
      });

      // If no models reported by health endpoints, warn and return empty
      if (models.size === 0) {
        console.warn('WARNING: No models reported by health endpoints. Health endpoint may not implement model discovery.');
        console.warn('Consider using getWorkerDetails() for full node information.');
      }

      return Array.from(models);
    }
  }

  /**
   * Get detailed worker information for task routing
   * Returns full node details including capabilities and performance metrics
   * @param {Object} options - Same as getAvailableWorkers
   * @returns {Promise<Array>} Detailed worker information
   */
  async getWorkerDetails(options = {}) {
    return this.getAvailableWorkers({ ...options, includeModels: true });
  }

  /**
   * Invalidate specific node from cache without full refresh
   * Use this when task routing fails to a specific node
   * @param {string} hostname - Hostname or name of node to invalidate
   */
  invalidateNode(hostname) {
    if (!this.cachedWorkers) {
      return;
    }

    const beforeCount = this.cachedWorkers.length;
    this.cachedWorkers = this.cachedWorkers.filter(
      node => node.host !== hostname && node.name !== hostname
    );
    const afterCount = this.cachedWorkers.length;

    if (beforeCount !== afterCount) {
      console.log(`Invalidated node ${hostname} from cache (${beforeCount} → ${afterCount} workers)`);
      this.emit('node-invalidated', { hostname, remaining: afterCount });
    }
  }

  /**
   * Clear the entire worker cache
   * Useful for forcing immediate refresh on next call
   */
  clearCache() {
    this.cachedWorkers = null;
    this.cacheTimestamp = 0;
    this.emit('cache-cleared');
  }

  /**
   * Get cache status
   * @returns {Object} Cache information
   */
  getCacheStatus() {
    const now = Date.now();
    const age = this.cachedWorkers ? now - this.cacheTimestamp : null;
    const ttlRemaining = this.cachedWorkers ? Math.max(0, this.options.cacheTTL - age) : 0;

    return {
      cached: this.cachedWorkers !== null,
      count: this.cachedWorkers ? this.cachedWorkers.length : 0,
      ageMs: age,
      ttlRemainingMs: ttlRemaining,
      stale: age !== null && age > this.options.cacheTTL,
      configErrors: this.configErrorCount,
      lastError: this.lastConfigError?.message || null
    };
  }
}

// Singleton instance for backward compatibility
const defaultPool = new WorkerPool();

/**
 * Factory function for creating isolated worker pools
 * @param {Object} options - Pool configuration
 * @returns {WorkerPool} New worker pool instance
 */
function createWorkerPool(options = {}) {
  return new WorkerPool(options);
}

// Export singleton methods for backward compatibility
module.exports = {
  // Singleton API (uses default pool)
  getAvailableWorkers: (opts) => defaultPool.getAvailableWorkers(opts),
  getWorkerDetails: (opts) => defaultPool.getWorkerDetails(opts),
  checkNodeHealth: (host, port, timeout) => defaultPool.checkNodeHealth(host, port, timeout),
  clearCache: () => defaultPool.clearCache(),
  getCacheStatus: () => defaultPool.getCacheStatus(),
  invalidateNode: (hostname) => defaultPool.invalidateNode(hostname),

  // Class-based API (for multi-workflow isolation)
  WorkerPool,
  createWorkerPool,

  // Constants
  CACHE_TTL_MS,
  MAX_HEALTH_RESPONSE_SIZE,
  CONFIG_RETRY_MAX_AGE_MS
};

// CLI usage for testing
if (require.main === module) {
  (async () => {
    console.log('Dynamic Worker Pool Discovery - Test Mode\n');

    // Test 1: Basic discovery
    console.log('Test 1: Basic model discovery');
    const models = await defaultPool.getAvailableWorkers();
    console.log('Available models:', models);
    console.log('');

    // Test 2: Detailed worker info
    console.log('Test 2: Detailed worker information');
    const workers = await defaultPool.getWorkerDetails();
    workers.forEach(worker => {
      console.log(`  ${worker.name}: ${worker.capabilities.join(', ')} (${worker.responseTime}ms)`);
      if (worker.models && worker.models.length > 0) {
        console.log(`    Models: ${worker.models.join(', ')}`);
      }
    });
    console.log('');

    // Test 3: Cache status
    console.log('Test 3: Cache status');
    console.log(defaultPool.getCacheStatus());
    console.log('');

    // Test 4: Force refresh
    console.log('Test 4: Force refresh (bypassing cache)');
    const refreshed = await defaultPool.getAvailableWorkers({ forceRefresh: true });
    console.log('Refreshed models:', refreshed);
    console.log('');

    // Test 5: Cache hit (with delay to show measurable age)
    console.log('Test 5: Cache hit after delay (should be instant)');
    await new Promise(r => setTimeout(r, 500)); // Add delay to show cache age
    const cached = await defaultPool.getAvailableWorkers();
    console.log('Cached models:', cached);
    console.log(defaultPool.getCacheStatus());
    console.log('');

    // Test 6: Node invalidation
    if (workers.length > 0) {
      console.log('Test 6: Node invalidation');
      const testNode = workers[0].host;
      console.log(`Invalidating node: ${testNode}`);
      defaultPool.invalidateNode(testNode);
      console.log(defaultPool.getCacheStatus());
    }
  })();
}
