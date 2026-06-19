#!/usr/bin/env node
// Dynamic Worker Pool Discovery
// Re-queries fleet nodes before each batch to detect nodes joining mid-workflow
// Integrates with existing health monitoring

const fs = require('fs').promises;
const fssync = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const EventEmitter = require('events');

const FLEET_CONFIG = path.join(os.homedir(), '.claude', 'fleet.json');
const CACHE_TTL_MS = 10000; // 10 seconds cache
const CONFIG_RETRY_MAX_AGE_MS = 300000; // 5 minutes max stale cache on config errors
const MAX_HEALTH_RESPONSE_SIZE = 10240; // 10KB max response body
const CONFIG_RETRY_DELAYS = [100, 500, 1000, 2000]; // Exponential backoff
const DISCOVERY_TIMEOUT_MS = 10000; // 10 second max for entire discovery
const STALE_CACHE_MAX_AGE_MS = 300000; // 5 minutes max stale cache age
const CIRCUIT_BREAKER_THRESHOLD = 3; // Failures before opening circuit
const CIRCUIT_BREAKER_RESET_MS = 60000; // 1 minute before retry
const MAX_BACKGROUND_REFRESH_RETRIES = 10; // Prevent unbounded recursion
const BACKGROUND_REFRESH_WINDOW_MS = 3600000; // 1 hour window for retry counter

/**
 * Proper mutex implementation using promise queue
 * @private
 */
class Mutex {
  constructor() {
    this._queue = Promise.resolve();
  }

  async acquire() {
    let release;
    const nextPromise = new Promise(resolve => {
      release = resolve;
    });

    const currentPromise = this._queue;
    this._queue = this._queue.then(() => nextPromise);

    await currentPromise;
    return release;
  }
}

/**
 * Worker Pool Discovery with proper cache management and error handling
 * Can be used as singleton (default) or instantiated per workflow
 */
class WorkerPool extends EventEmitter {
  constructor(options = {}) {
    super();
    this.setMaxListeners(0); // Unlimited listeners (events are transient)
    this.cachedWorkers = null;
    this.cacheTimestamp = 0;
    this.inflightDiscovery = null;
    this.configErrorCount = 0;
    this.lastConfigError = null;
    this.cacheLock = new Mutex(); // Proper mutex for cache operations
    this.ignoreInflightResult = false; // Flag to ignore stale inflight results
    this.circuitBreakers = options.sharedCircuitBreakers || new Map(); // Per-instance by default
    this.backgroundRefreshTimer = null; // Track background refresh to prevent leaks
    this.backgroundRefreshCount = 0; // Track refresh attempts to prevent unbounded recursion
    this.backgroundRefreshWindowStart = null; // Track retry window for time-based reset
    this.options = {
      cacheTTL: options.cacheTTL || CACHE_TTL_MS,
      configRetryMaxAge: options.configRetryMaxAge || CONFIG_RETRY_MAX_AGE_MS,
      onError: options.onError || ((err) => console.error('WorkerPool error:', err))
    };
  }

  /**
   * Check circuit breaker state for a node
   * @private
   */
  _checkCircuitBreaker(host) {
    const state = this.circuitBreakers.get(host);
    if (!state) {
      return { open: false };
    }

    // Check if circuit should reset
    if (state.open && Date.now() - state.openedAt > CIRCUIT_BREAKER_RESET_MS) {
      state.open = false;
      state.failures = 0;
      this.emit('circuit-breaker-closed', { host, resetAfterMs: CIRCUIT_BREAKER_RESET_MS });
      return { open: false };
    }

    return state;
  }

  /**
   * Record circuit breaker result
   * @private
   */
  _recordCircuitBreakerResult(host, success) {
    let state = this.circuitBreakers.get(host);
    if (!state) {
      state = { failures: 0, open: false, openedAt: null };
      this.circuitBreakers.set(host, state);
    }

    if (success) {
      state.failures = 0;
      state.open = false;
      state.openedAt = null;
    } else {
      state.failures++;
      if (state.failures >= CIRCUIT_BREAKER_THRESHOLD) {
        state.open = true;
        state.openedAt = Date.now();
        this.emit('circuit-breaker-opened', { host, failures: state.failures });
      }
    }
  }

  /**
   * Sanitize error message to prevent sensitive data leaks
   * @private
   */
  _sanitizeError(message) {
    // Truncate to 200 chars to prevent stack traces or internal paths
    return String(message).substring(0, 200);
  }

  /**
   * Health check a single node with proper resource limits and race condition handling
   * @param {string} host - Node hostname
   * @param {number} port - Health check port (default 7340)
   * @param {number} timeout - Timeout in ms (default 2000)
   * @param {AbortSignal} signal - Optional abort signal for cancellation
   * @returns {Promise<Object|null>} Health status or null if unreachable
   */
  async checkNodeHealth(host, port = 7340, timeout = 2000, signal = null) {
    // Check circuit breaker
    const circuitState = this._checkCircuitBreaker(host);
    if (circuitState.open) {
      return {
        alive: false,
        error: 'Circuit breaker open',
        responseTime: 0
      };
    }

    return new Promise((resolve) => {
      const startTime = Date.now();
      let resolved = false;
      let dataAborted = false; // Flag to stop data accumulation
      let responseDestroyed = false; // Track if response was destroyed
      let socketTimeoutCleared = false; // Track if socket timeout was cleared

      // Guard against multiple resolve() calls
      const safeResolve = (val) => {
        if (!resolved) {
          resolved = true;
          this._recordCircuitBreakerResult(host, val.alive === true);
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
          // CRITICAL FIX: Check dataAborted FIRST, set it BEFORE size check
          if (dataAborted) {
            return;
          }

          bodySize += chunk.length;

          // Enforce body size limit to prevent OOM
          if (bodySize > MAX_HEALTH_RESPONSE_SIZE) {
            dataAborted = true; // Set flag BEFORE any async operations
            responseDestroyed = true;

            // Use destroy() immediately instead of pause() to prevent buffered chunks
            res.destroy();
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
          // Skip if response was destroyed due to size limit
          if (responseDestroyed) {
            return;
          }

          const duration = Date.now() - startTime;

          // CRITICAL FIX: Remove timeout listener BEFORE JSON parsing to prevent race
          req.removeAllListeners('timeout');
          req.removeAllListeners('socket');

          try {
            const data = JSON.parse(body);

            // CRITICAL FIX: Validate health endpoint response schema
            if (res.statusCode === 200 && data.status === 'ok') {
              if (!data.node || !data.session) {
                safeResolve({
                  alive: false,
                  error: 'Invalid health response: missing required fields',
                  responseTime: duration
                });
                return;
              }

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
        // CRITICAL FIX: Ignore AbortError from cancelled requests
        if (signal?.aborted && err.name === 'AbortError') {
          return;
        }

        safeResolve({
          alive: false,
          error: this._sanitizeError(err.message),
          responseTime: Date.now() - startTime
        });
      });

      // Add socket-level timeout for faster failure detection
      req.on('socket', (socket) => {
        socket.setTimeout(timeout);

        const socketTimeoutHandler = () => {
          // CRITICAL FIX: Guard to prevent double-destroy race
          if (req.destroyed || responseDestroyed || socketTimeoutCleared) {
            return;
          }

          req.destroy();
          safeResolve({
            alive: false,
            error: 'Socket timeout',
            responseTime: Date.now() - startTime
          });
        };

        socket.on('timeout', socketTimeoutHandler);

        // CRITICAL FIX: Store cleanup function to prevent double-destroy
        req.once('response', () => {
          socketTimeoutCleared = true;
          socket.removeListener('timeout', socketTimeoutHandler);
        });
      });

      // Handle abort signal
      if (signal) {
        signal.addEventListener('abort', () => {
          if (!req.destroyed) {
            req.destroy();
          }
          safeResolve({
            alive: false,
            error: 'Aborted',
            responseTime: Date.now() - startTime
          });
        });
      }

      req.end();
    });
  }

  /**
   * Read fleet config with retry and exponential backoff
   * @returns {Promise<Object|null>} Fleet config or null if permanently failed
   */
  async readFleetConfig() {
    const retryStartTime = Date.now();

    for (let attempt = 0; attempt < CONFIG_RETRY_DELAYS.length; attempt++) {
      // CRITICAL FIX: Recalculate cache age on each iteration to prevent TOCTOU races
      const cacheAge = this.cachedWorkers ? Date.now() - this.cacheTimestamp : 0;
      const elapsed = Date.now() - retryStartTime;

      if (cacheAge > 0 && cacheAge + elapsed > this.options.configRetryMaxAge) {
        this.options.onError(new Error(
          `Config retry timeout - using stale cache (age: ${Math.round(cacheAge / 1000)}s)`
        ));
        break;
      }

      try {
        const configData = await fs.readFile(FLEET_CONFIG, 'utf8');
        const config = JSON.parse(configData);

        // Validate config structure
        if (!config.nodes || !Array.isArray(config.nodes)) {
          this.configErrorCount++;
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

    // CRITICAL FIX: Re-check if cache was invalidated during retry window
    if (this.cachedWorkers && Date.now() - this.cacheTimestamp < this.options.cacheTTL) {
      return null; // Signal to use cache
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

    // Check cache (TTL-based) - recalculate 'now' to avoid stale timestamp issues
    let now = Date.now();
    if (!forceRefresh && this.cachedWorkers && (now - this.cacheTimestamp) < this.options.cacheTTL) {
      return this.cachedWorkers;
    }

    // CRITICAL FIX: Double-check pattern for ignoreInflightResult (before AND after await)
    // This prevents race condition where clearCache() is called during inflight discovery
    // Don't optimize away either check - both are needed for correctness
    if (this.inflightDiscovery && !this.ignoreInflightResult) {
      const result = await this.inflightDiscovery;

      // CRITICAL FIX: Snapshot cachedWorkers BEFORE checking ignoreInflightResult
      // to prevent TOCTOU race with clearCache()
      const snapshot = this.cachedWorkers;

      // Check if result should be ignored (clearCache called during discovery)
      if (this.ignoreInflightResult) {
        return snapshot || [];
      }

      return result;
    }

    // Start discovery
    this.ignoreInflightResult = false; // Reset flag
    this.inflightDiscovery = this._doDiscovery(port, timeout, includeModels);

    try {
      const result = await this.inflightDiscovery;

      // Check if result should be ignored (clearCache called during discovery)
      if (this.ignoreInflightResult) {
        throw new Error('Discovery invalidated during flight');
      }

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

      // Snapshot to prevent TOCTOU race with clearCache
      const cacheSnapshot = this.cachedWorkers;

      // If we have stale cache and it's not too old, use it
      if (cacheSnapshot && staleCacheAge < STALE_CACHE_MAX_AGE_MS) {
        this.options.onError(new Error(
          `Fleet config unavailable, using stale cache (age: ${Math.round(staleCacheAge / 1000)}s)`
        ));
        this.emit('stale-cache-used', { age: staleCacheAge, reason: 'config-unavailable' });

        // CRITICAL FIX: Reset retry counter only if >1 hour has passed
        const resetWindow = !this.backgroundRefreshWindowStart ||
                           (Date.now() - this.backgroundRefreshWindowStart) > BACKGROUND_REFRESH_WINDOW_MS;

        if (resetWindow) {
          this.backgroundRefreshCount = 0;
          this.backgroundRefreshWindowStart = Date.now();
        }

        // CRITICAL FIX: Prevent unbounded recursion with retry limit
        if (this.backgroundRefreshCount >= MAX_BACKGROUND_REFRESH_RETRIES) {
          this.emit('fleet-permanently-unavailable', {
            reason: 'max-background-retries-exceeded',
            attempts: this.backgroundRefreshCount
          });
          this.options.onError(new Error(
            `Fleet permanently unavailable after ${this.backgroundRefreshCount} background refresh attempts`
          ));
          // Stop retrying but continue using stale cache
          return cacheSnapshot;
        }

        // Cancel previous background refresh timer to prevent multiple timers
        if (this.backgroundRefreshTimer) {
          clearTimeout(this.backgroundRefreshTimer);
          this.backgroundRefreshTimer = null;
        }

        // Schedule background refresh attempt
        this.backgroundRefreshCount++;
        this.backgroundRefreshTimer = setTimeout(() => {
          this.backgroundRefreshTimer = null; // Clear reference
          this.getAvailableWorkers({ forceRefresh: true })
            .then(() => {
              // Success - don't reset counter (time-based reset only)
            })
            .catch(err => {
              this.options.onError(new Error(`Background refresh failed: ${err.message}`));
              // Counter already incremented, will be checked on next attempt
            });
        }, 5000);

        return cacheSnapshot;
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

      // Use proper mutex pattern for cache update
      const unlock = await this.cacheLock.acquire();
      try {
        this.cachedWorkers = [];
        this.cacheTimestamp = now;
      } finally {
        unlock();
      }

      return [];
    }

    // Create AbortController for cancellable health checks
    const abortController = new AbortController();

    // Health check all worker nodes in parallel with error isolation
    const healthChecks = workerNodes.map(async (node) => {
      try {
        const health = await this.checkNodeHealth(node.host, port, timeout, abortController.signal);

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
        // CRITICAL FIX: Record circuit breaker failure on caught exceptions
        this._recordCircuitBreakerResult(node.host, false);

        // CRITICAL FIX: Ignore AbortError from cancelled requests
        if (abortController.signal.aborted && err.name === 'AbortError') {
          return {
            name: node.name,
            host: node.host,
            cpu: node.cpu,
            memory: node.memory,
            capabilities: node.capabilities || [],
            role: node.role,
            health: false,
            responseTime: timeout,
            error: 'Aborted',
            session: null,
            models: []
          };
        }

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
          error: this._sanitizeError(err.message),
          session: null,
          models: []
        };
      }
    });

    // CRITICAL FIX: Wrap Promise.all with overall timeout and abort inflight requests
    const discoveryTimeout = Math.max(timeout * 1.5, DISCOVERY_TIMEOUT_MS);
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => {
        abortController.abort(); // Cancel all inflight health checks
        reject(new Error(`Discovery timeout after ${discoveryTimeout}ms`));
      }, discoveryTimeout);
    });

    let results;
    try {
      results = await Promise.race([Promise.all(healthChecks), timeoutPromise]);
    } catch (err) {
      this.options.onError(new Error(`Discovery timed out: ${err.message}`));

      // Snapshot to prevent TOCTOU race
      const cacheSnapshot = this.cachedWorkers;

      // If we have stale cache, use it
      if (cacheSnapshot && cacheAge < STALE_CACHE_MAX_AGE_MS) {
        this.emit('stale-cache-used', { age: cacheAge, reason: 'discovery-timeout' });
        return cacheSnapshot;
      }

      throw err;
    }

    // Filter for healthy nodes only
    const availableWorkers = results.filter(node => node.health);

    // Distinguish between "no workers configured" and "all workers failed health check"
    const allWorkersFailed = workerNodes.length > 0 && availableWorkers.length === 0;

    if (allWorkersFailed) {
      // Don't cache empty result from health failures - use shorter TTL or stale cache
      console.log('WARNING: All workers failed health checks - not caching empty result');

      // Snapshot to prevent TOCTOU race
      const cacheSnapshot = this.cachedWorkers;

      if (cacheSnapshot && cacheAge < STALE_CACHE_MAX_AGE_MS) {
        this.emit('stale-cache-used', { age: cacheAge, reason: 'all-workers-failed' });
        return cacheSnapshot;
      }

      // CRITICAL FIX: Use consistent Error constructor pattern
      const error = new Error('All workers failed health checks and no valid cache available');
      throw error;
    }

    // CRITICAL FIX: Use proper mutex pattern for cache update with timestamp check
    const unlock = await this.cacheLock.acquire();
    try {
      // Compare timestamps before update to prevent slower discovery overwriting newer cache
      if (now > this.cacheTimestamp) {
        this.cachedWorkers = availableWorkers;
        this.cacheTimestamp = now;
      }
    } finally {
      unlock();
    }

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
        if (Array.isArray(node.models)) {
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
  async invalidateNode(hostname) {
    const normalizedHostname = hostname.toLowerCase();

    // Use proper mutex pattern for cache update
    const unlock = await this.cacheLock.acquire();
    try {
      if (!this.cachedWorkers) {
        return;
      }

      const beforeCount = this.cachedWorkers.length;
      this.cachedWorkers = this.cachedWorkers.filter(
        node => node.host.toLowerCase() !== normalizedHostname && node.name.toLowerCase() !== normalizedHostname
      );
      const afterCount = this.cachedWorkers.length;

      if (beforeCount !== afterCount) {
        console.log(`Invalidated node ${hostname} from cache (${beforeCount} → ${afterCount} workers)`);
        this.emit('node-invalidated', { hostname, remaining: afterCount });
      }
    } finally {
      unlock();
    }
  }

  /**
   * Clear the entire worker cache
   * Useful for forcing immediate refresh on next call
   */
  async clearCache() {
    // CRITICAL FIX: Clear background refresh timer before setting ignoreInflightResult
    if (this.backgroundRefreshTimer) {
      clearTimeout(this.backgroundRefreshTimer);
      this.backgroundRefreshTimer = null;
    }

    // Set flag to ignore inflight discovery result
    if (this.inflightDiscovery) {
      this.ignoreInflightResult = true;
    }

    // Use proper mutex pattern for cache clear
    const unlock = await this.cacheLock.acquire();
    try {
      this.cachedWorkers = null;
      this.cacheTimestamp = 0;
      this.emit('cache-cleared');

      // CRITICAL FIX: Reset ignoreInflightResult after cache clear completes
      // This prevents surprise errors when getAvailableWorkers() is called immediately after
      this.ignoreInflightResult = false;
    } finally {
      unlock();
    }
  }

  /**
   * Cleanup method to prevent resource leaks
   * Call this before destroying the WorkerPool instance
   */
  destroy() {
    // Clear background refresh timer
    if (this.backgroundRefreshTimer) {
      clearTimeout(this.backgroundRefreshTimer);
      this.backgroundRefreshTimer = null;
    }

    // Clear all event listeners
    this.removeAllListeners();

    // Clear inflight discovery
    this.inflightDiscovery = null;
    this.ignoreInflightResult = true;
  }

  /**
   * Get cache status
   * @returns {Object} Cache information
   */
  getCacheStatus() {
    // Snapshot to avoid TOCTOU race
    const cachedWorkersSnapshot = this.cachedWorkers;
    const cacheTimestampSnapshot = this.cacheTimestamp;

    const now = Date.now();
    const age = cachedWorkersSnapshot ? now - cacheTimestampSnapshot : null;
    const ttlRemaining = cachedWorkersSnapshot ? Math.max(0, this.options.cacheTTL - age) : 0;

    return {
      cached: cachedWorkersSnapshot !== null,
      count: cachedWorkersSnapshot ? cachedWorkersSnapshot.length : 0,
      ageMs: age,
      ttlRemainingMs: ttlRemaining,
      stale: age !== null && age > this.options.cacheTTL,
      configErrors: this.configErrorCount,
      lastError: this.lastConfigError?.message || null,
      backgroundRefreshCount: this.backgroundRefreshCount,
      circuitBreakers: Array.from(this.circuitBreakers.entries()).map(([host, state]) => ({
        host,
        open: state.open,
        failures: state.failures
      }))
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
  CONFIG_RETRY_MAX_AGE_MS,
  CIRCUIT_BREAKER_THRESHOLD,
  CIRCUIT_BREAKER_RESET_MS,
  MAX_BACKGROUND_REFRESH_RETRIES
};

// CLI usage for testing
if (require.main === module) {
  (async () => {
    // CRITICAL FIX: Use unref() to prevent timeout from blocking process exit
    const testTimeout = setTimeout(() => {
      // CRITICAL FIX: Check if process is exiting before logging error
      if (!process.exitCode) {
        console.error('Test timeout after 30s');
        process.exit(1);
      }
    }, 30000).unref();

    try {
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
        await defaultPool.invalidateNode(testNode);
        console.log(defaultPool.getCacheStatus());
      }

      clearTimeout(testTimeout);
      process.exit(0);
    } catch (err) {
      console.error('Test failed:', err);
      clearTimeout(testTimeout);
      process.exit(1);
    }
  })();
}
