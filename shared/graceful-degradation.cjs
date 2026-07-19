/**
 * Graceful Degradation - Fallback logic when services are unavailable
 *
 * Provides three core functions:
 *   - executeWithFallback(serviceName, input, fallbackFn) - Try primary, fall back on failure
 *   - getServiceOrFallback(serviceName, fallbackService) - Return available service connector
 *   - requireService(serviceName) - Throw if service is unavailable
 *
 * Features:
 *   - Degradation event logging (file + console)
 *   - Prometheus metrics for service availability
 *   - Configurable health checks per service
 *   - In-memory availability cache with TTL
 *
 * Created: 2026-06-28
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// CONFIGURATION
// ============================================================================

const LOG_DIR = process.env.DEGRADATION_LOG_DIR
  || path.join(__dirname, '..', 'monitoring', 'logs');

const LOG_FILE = path.join(LOG_DIR, 'degradation-events.jsonl');

const CACHE_TTL_MS = parseInt(process.env.DEGRADATION_CACHE_TTL_MS || '30000');

// ============================================================================
// SERVICE REGISTRY
// ============================================================================

/**
 * Known services and their health-check functions.
 * Each entry maps a service name to:
 *   - check(): async boolean - returns true if reachable
 *   - description: human-readable label
 */
const serviceRegistry = {};

/**
 * Register a service with a health-check function.
 *
 * @param {string} name - Service identifier (e.g. 'orientdb', 'postgres', 'redis')
 * @param {object} opts
 * @param {Function} opts.check - Async function returning true if service is healthy
 * @param {string}  [opts.description] - Human-readable description
 */
function registerService(name, opts = {}) {
  if (!name || typeof name !== 'string') {
    throw new Error('registerService requires a non-empty string name');
  }
  serviceRegistry[name] = {
    check: opts.check || (async () => true),
    description: opts.description || name,
  };
}

// ============================================================================
// AVAILABILITY CACHE
// ============================================================================

const availabilityCache = {};

/**
 * Check whether a service is currently available.
 * Results are cached for CACHE_TTL_MS to avoid hammering health endpoints.
 *
 * @param {string} serviceName
 * @returns {Promise<boolean>}
 */
async function isServiceAvailable(serviceName) {
  const now = Date.now();
  const cached = availabilityCache[serviceName];
  if (cached && (now - cached.timestamp) < CACHE_TTL_MS) {
    return cached.available;
  }

  const entry = serviceRegistry[serviceName];
  if (!entry) {
    // Unknown service - assume unavailable
    availabilityCache[serviceName] = { available: false, timestamp: now };
    return false;
  }

  let available = false;
  try {
    available = await entry.check();
  } catch (_err) {
    available = false;
  }

  availabilityCache[serviceName] = { available, timestamp: now };
  return available;
}

/**
 * Clear the availability cache for one or all services.
 *
 * @param {string} [serviceName] - If omitted, clears entire cache
 */
function clearAvailabilityCache(serviceName) {
  if (serviceName) {
    delete availabilityCache[serviceName];
  } else {
    for (const key of Object.keys(availabilityCache)) {
      delete availabilityCache[key];
    }
  }
}

// ============================================================================
// DEGRADATION EVENT LOGGING
// ============================================================================

/**
 * Log a degradation event to both console and a JSONL file.
 *
 * @param {object} event
 */
function logDegradationEvent(event) {
  const record = {
    timestamp: new Date().toISOString(),
    ...event,
  };

  console.warn(`[GracefulDegradation] ${event.type}: ${event.service} - ${event.message}`);

  try {
    const dir = path.dirname(LOG_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.appendFileSync(LOG_FILE, JSON.stringify(record) + '\n');
  } catch (err) {
    console.error('[GracefulDegradation] Failed to write log:', err.message);
  }
}

// ============================================================================
// PROMETHEUS METRICS
// ============================================================================

const metrics = {
  fallback_invocations_total: {},   // { serviceName: count }
  fallback_successes_total: {},
  fallback_failures_total: {},
  service_available: {},            // { serviceName: 0|1 }
  require_failures_total: {},
};

/**
 * Increment a counter metric for a service.
 */
function incMetric(metricName, serviceName) {
  if (!metrics[metricName]) {
    metrics[metricName] = {};
  }
  metrics[metricName][serviceName] = (metrics[metricName][serviceName] || 0) + 1;
}

/**
 * Set a gauge metric for a service.
 */
function setMetric(metricName, serviceName, value) {
  if (!metrics[metricName]) {
    metrics[metricName] = {};
  }
  metrics[metricName][serviceName] = value;
}

/**
 * Return Prometheus-formatted metrics string.
 *
 * @returns {string}
 */
function getPrometheusMetrics() {
  const lines = [];

  lines.push('# HELP graceful_degradation_fallback_invocations_total Total fallback invocations per service');
  lines.push('# TYPE graceful_degradation_fallback_invocations_total counter');
  for (const [svc, val] of Object.entries(metrics.fallback_invocations_total)) {
    lines.push(`graceful_degradation_fallback_invocations_total{service="${svc}"} ${val}`);
  }

  lines.push('# HELP graceful_degradation_fallback_successes_total Successful fallback executions');
  lines.push('# TYPE graceful_degradation_fallback_successes_total counter');
  for (const [svc, val] of Object.entries(metrics.fallback_successes_total)) {
    lines.push(`graceful_degradation_fallback_successes_total{service="${svc}"} ${val}`);
  }

  lines.push('# HELP graceful_degradation_fallback_failures_total Failed fallback executions');
  lines.push('# TYPE graceful_degradation_fallback_failures_total counter');
  for (const [svc, val] of Object.entries(metrics.fallback_failures_total)) {
    lines.push(`graceful_degradation_fallback_failures_total{service="${svc}"} ${val}`);
  }

  lines.push('# HELP graceful_degradation_service_available Whether a service is available (1=yes, 0=no)');
  lines.push('# TYPE graceful_degradation_service_available gauge');
  for (const [svc, val] of Object.entries(metrics.service_available)) {
    lines.push(`graceful_degradation_service_available{service="${svc}"} ${val}`);
  }

  lines.push('# HELP graceful_degradation_require_failures_total Times requireService threw');
  lines.push('# TYPE graceful_degradation_require_failures_total counter');
  for (const [svc, val] of Object.entries(metrics.require_failures_total)) {
    lines.push(`graceful_degradation_require_failures_total{service="${svc}"} ${val}`);
  }

  return lines.join('\n') + '\n';
}

// ============================================================================
// CORE API
// ============================================================================

/**
 * Execute an operation against a service, falling back to fallbackFn on failure.
 *
 * If the service is known-unavailable (cached), the fallback is invoked immediately
 * without attempting the primary path. If the service check passes, the caller's
 * primary logic is expected to be embedded in the fallbackFn's counterpart -- but
 * since the caller controls the primary path externally, this function focuses on
 * detecting unavailability and routing to the fallback.
 *
 * Usage pattern:
 *   const result = await executeWithFallback('orientdb', query, async (q) => {
 *     log('OrientDB unavailable, using PostgreSQL CTEs');
 *     return await postgresRecursiveCTE(q);
 *   });
 *
 * @param {string} serviceName - The service to check
 * @param {*} input - Input to pass to the primary or fallback function
 * @param {Function} fallbackFn - async (input) => result, invoked when service unavailable
 * @param {object} [opts]
 * @param {Function} [opts.primaryFn] - async (input) => result, the primary service call
 * @returns {Promise<{result: *, degraded: boolean, service: string}>}
 */
async function executeWithFallback(serviceName, input, fallbackFn, opts = {}) {
  if (!serviceName || typeof serviceName !== 'string') {
    throw new Error('executeWithFallback requires a non-empty serviceName');
  }
  if (typeof fallbackFn !== 'function') {
    throw new Error('executeWithFallback requires a fallbackFn function');
  }

  const available = await isServiceAvailable(serviceName);
  setMetric('service_available', serviceName, available ? 1 : 0);

  // If primary is available and a primaryFn was provided, try it first
  if (available && opts.primaryFn) {
    try {
      const result = await opts.primaryFn(input);
      return { result, degraded: false, service: serviceName };
    } catch (primaryErr) {
      // Primary failed at runtime -- mark unavailable, fall through
      clearAvailabilityCache(serviceName);
      availabilityCache[serviceName] = { available: false, timestamp: Date.now() };
      setMetric('service_available', serviceName, 0);

      logDegradationEvent({
        type: 'primary_failure',
        service: serviceName,
        message: `Primary call failed: ${primaryErr.message}`,
        error: primaryErr.message,
      });
    }
  } else if (available && !opts.primaryFn) {
    // Service is available but no primaryFn -- caller handles primary externally
    // Return a signal that the service is up; no fallback needed
    return { result: null, degraded: false, service: serviceName, available: true };
  }

  // Service is unavailable (or primary failed) -- invoke fallback
  incMetric('fallback_invocations_total', serviceName);

  logDegradationEvent({
    type: 'fallback_invoked',
    service: serviceName,
    message: `Service unavailable, invoking fallback`,
  });

  try {
    const result = await fallbackFn(input);
    incMetric('fallback_successes_total', serviceName);

    logDegradationEvent({
      type: 'fallback_success',
      service: serviceName,
      message: 'Fallback completed successfully',
    });

    return { result, degraded: true, service: serviceName };
  } catch (fallbackErr) {
    incMetric('fallback_failures_total', serviceName);

    logDegradationEvent({
      type: 'fallback_failure',
      service: serviceName,
      message: `Fallback also failed: ${fallbackErr.message}`,
      error: fallbackErr.message,
    });

    throw new Error(
      `[GracefulDegradation] Both ${serviceName} and fallback failed: ${fallbackErr.message}`
    );
  }
}

/**
 * Return the preferred service name based on availability.
 * If the primary service is unavailable, returns the fallback service name.
 *
 * @param {string} serviceName - Primary service
 * @param {string} fallbackService - Fallback service
 * @returns {Promise<{service: string, degraded: boolean}>}
 */
async function getServiceOrFallback(serviceName, fallbackService) {
  if (!serviceName || typeof serviceName !== 'string') {
    throw new Error('getServiceOrFallback requires a non-empty serviceName');
  }
  if (!fallbackService || typeof fallbackService !== 'string') {
    throw new Error('getServiceOrFallback requires a non-empty fallbackService');
  }

  const primaryAvailable = await isServiceAvailable(serviceName);
  setMetric('service_available', serviceName, primaryAvailable ? 1 : 0);

  if (primaryAvailable) {
    return { service: serviceName, degraded: false };
  }

  const fallbackAvailable = await isServiceAvailable(fallbackService);
  setMetric('service_available', fallbackService, fallbackAvailable ? 1 : 0);

  if (fallbackAvailable) {
    logDegradationEvent({
      type: 'service_fallback',
      service: serviceName,
      message: `Falling back from ${serviceName} to ${fallbackService}`,
      fallback: fallbackService,
    });

    return { service: fallbackService, degraded: true };
  }

  logDegradationEvent({
    type: 'no_service_available',
    service: serviceName,
    message: `Neither ${serviceName} nor ${fallbackService} is available`,
    fallback: fallbackService,
  });

  throw new Error(
    `[GracefulDegradation] Neither ${serviceName} nor ${fallbackService} is available`
  );
}

/**
 * Assert that a service is available. Throws if not.
 *
 * @param {string} serviceName
 * @returns {Promise<void>}
 * @throws {Error} if the service is unavailable
 */
async function requireService(serviceName) {
  if (!serviceName || typeof serviceName !== 'string') {
    throw new Error('requireService requires a non-empty serviceName');
  }

  const available = await isServiceAvailable(serviceName);
  setMetric('service_available', serviceName, available ? 1 : 0);

  if (!available) {
    incMetric('require_failures_total', serviceName);

    logDegradationEvent({
      type: 'require_failed',
      service: serviceName,
      message: `Required service ${serviceName} is unavailable`,
    });

    const err = new Error(
      `[GracefulDegradation] Required service '${serviceName}' is unavailable`
    );
    err.code = 'SERVICE_UNAVAILABLE';
    err.service = serviceName;
    throw err;
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Core API
  executeWithFallback,
  getServiceOrFallback,
  requireService,

  // Service registry
  registerService,
  isServiceAvailable,
  clearAvailabilityCache,

  // Metrics
  getPrometheusMetrics,
  getMetrics: () => ({ ...metrics }),

  // Logging
  logDegradationEvent,

  // For testing
  _internals: {
    availabilityCache,
    serviceRegistry,
    metrics,
    LOG_FILE,
    CACHE_TTL_MS,
  },
};
