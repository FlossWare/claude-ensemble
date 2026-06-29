/**
 * Service Health Monitoring System
 *
 * Monitors health of all services (PostgreSQL, Prometheus, API providers, etc.)
 * Auto-disables unhealthy services and exposes Prometheus metrics.
 *
 * Architecture:
 * - PostgreSQL: monitoring.service_health table (with in-memory fallback)
 * - Configurable health check intervals (default 60s)
 * - Integrates with prometheus-exporter.cjs
 * - Auto-disable threshold: health < 0.50 (50%)
 * - Custom health check registration for extensibility
 *
 * Created: 2026-06-28
 */

'use strict';

const http = require('http');
const path = require('path');
const fs = require('fs');

// ============================================================================
// CONFIGURATION
// ============================================================================

const DEFAULT_CONFIG = {
  check_interval_ms: 60000,            // 60 seconds
  health_check_timeout_ms: 5000,       // 5s timeout per check
  auto_disable_threshold: 0.50,        // 50% health threshold
  degraded_threshold: 0.75,            // 75% for degraded status
  history_window: 20,                  // Track last 20 checks
  pg_host: process.env.PGHOST || 'aio-01',
  pg_port: parseInt(process.env.PGPORT || '5433', 10),
  pg_database: process.env.PGDATABASE || 'learning',
  pg_user: process.env.PGUSER || process.env.USER || 'sfloess',
  pg_password: process.env.PGPASSWORD || undefined,
  prometheus_port: 9101,
  prometheus_health_path: '/health',
};

let config = { ...DEFAULT_CONFIG };

// Load optional config file
const CONFIG_PATH = path.join(__dirname, 'webhook-config.json');
try {
  if (fs.existsSync(CONFIG_PATH)) {
    const fileConfig = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    if (fileConfig.thresholds?.service_health) {
      config = { ...DEFAULT_CONFIG, ...fileConfig.thresholds.service_health };
    }
  }
} catch (_err) {
  // Config file not available, use defaults
}

// ============================================================================
// IN-MEMORY STORE (fallback when PostgreSQL unavailable)
// ============================================================================

/**
 * In-memory store that mirrors PostgreSQL schema.
 * Used when database is unavailable or for unit testing.
 */
class InMemoryStore {
  constructor() {
    this.services = new Map();      // service_name -> health record
    this.healthChecks = [];         // historical check records
    this._nextId = 1;
  }

  getServiceRecord(serviceName) {
    if (!this.services.has(serviceName)) {
      this.services.set(serviceName, {
        service_name: serviceName,
        healthy: true,
        health_score: 1.0,
        total_checks: 0,
        successful_checks: 0,
        failed_checks: 0,
        status: 'healthy',
        last_check: null,
        last_success: null,
        last_failure: null,
        last_latency_ms: null,
        error_message: null,
        created_at: new Date(),
        updated_at: new Date(),
        metadata: {},
      });
    }
    return this.services.get(serviceName);
  }

  recordCheck(serviceName, result) {
    const now = new Date();
    const record = this.getServiceRecord(serviceName);

    // Add to historical checks
    this.healthChecks.push({
      id: this._nextId++,
      service_name: serviceName,
      healthy: result.healthy,
      latency_ms: result.latency_ms,
      error_message: result.error || null,
      created_at: now,
    });

    // Calculate health score from recent checks
    const recentChecks = this.healthChecks
      .filter(c => c.service_name === serviceName)
      .slice(-config.history_window);

    const successCount = recentChecks.filter(c => c.healthy).length;
    const totalCount = recentChecks.length;
    const healthScore = totalCount > 0 ? successCount / totalCount : 1.0;

    // Determine status
    let status;
    if (healthScore < config.auto_disable_threshold) {
      status = 'disabled';
    } else if (healthScore < config.degraded_threshold) {
      status = 'degraded';
    } else {
      status = 'healthy';
    }

    // Update record
    record.healthy = result.healthy;
    record.health_score = healthScore;
    record.total_checks += 1;
    record.successful_checks += result.healthy ? 1 : 0;
    record.failed_checks += result.healthy ? 0 : 1;
    record.status = status;
    record.last_check = now;
    record.last_latency_ms = result.latency_ms;
    record.error_message = result.error || null;
    record.updated_at = now;

    if (result.healthy) {
      record.last_success = now;
    } else {
      record.last_failure = now;
    }

    return { healthScore, status };
  }

  getAllServices() {
    return Array.from(this.services.values())
      .sort((a, b) => b.health_score - a.health_score);
  }

  getHistory(serviceName, limit = 20) {
    return this.healthChecks
      .filter(c => c.service_name === serviceName)
      .sort((a, b) => b.created_at - a.created_at)
      .slice(0, limit);
  }

  disableUnhealthy(threshold) {
    const disabled = [];
    for (const [name, record] of this.services) {
      if (record.health_score < threshold && record.status !== 'disabled') {
        record.status = 'disabled';
        record.updated_at = new Date();
        disabled.push(name);
      }
    }
    return disabled;
  }

  clear() {
    this.services.clear();
    this.healthChecks = [];
    this._nextId = 1;
  }
}

// ============================================================================
// DATABASE BACKEND
// ============================================================================

/**
 * PostgreSQL-backed storage.
 * Wraps pg Pool and provides the same interface as InMemoryStore.
 */
class PostgresStore {
  constructor(poolInstance) {
    this.pool = poolInstance;
    this._schemaInitialized = false;
  }

  async initSchema() {
    if (this._schemaInitialized) return;
    const client = await this.pool.connect();
    try {
      await client.query('CREATE SCHEMA IF NOT EXISTS monitoring');

      await client.query(`
        CREATE TABLE IF NOT EXISTS monitoring.service_health (
          service_name VARCHAR(100) PRIMARY KEY,
          healthy BOOLEAN NOT NULL DEFAULT true,
          health_score NUMERIC(5,4) DEFAULT 1.0,
          total_checks INTEGER DEFAULT 0,
          successful_checks INTEGER DEFAULT 0,
          failed_checks INTEGER DEFAULT 0,
          status VARCHAR(20) DEFAULT 'healthy',
          last_check TIMESTAMPTZ,
          last_success TIMESTAMPTZ,
          last_failure TIMESTAMPTZ,
          last_latency_ms INTEGER,
          error_message TEXT,
          created_at TIMESTAMPTZ DEFAULT NOW(),
          updated_at TIMESTAMPTZ DEFAULT NOW(),
          metadata JSONB DEFAULT '{}'::jsonb
        )
      `);

      await client.query(`
        CREATE TABLE IF NOT EXISTS monitoring.service_health_checks (
          id SERIAL PRIMARY KEY,
          service_name VARCHAR(100) NOT NULL,
          healthy BOOLEAN NOT NULL,
          latency_ms INTEGER,
          error_message TEXT,
          created_at TIMESTAMPTZ DEFAULT NOW()
        )
      `);

      await client.query(`
        CREATE INDEX IF NOT EXISTS idx_service_health_checks_service_created
        ON monitoring.service_health_checks(service_name, created_at DESC)
      `);

      this._schemaInitialized = true;
    } finally {
      client.release();
    }
  }

  async recordCheck(serviceName, result) {
    await this.initSchema();
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      // Ensure service exists
      await client.query(`
        INSERT INTO monitoring.service_health (service_name)
        VALUES ($1)
        ON CONFLICT (service_name) DO NOTHING
      `, [serviceName]);

      // Insert historical check
      await client.query(`
        INSERT INTO monitoring.service_health_checks
        (service_name, healthy, latency_ms, error_message)
        VALUES ($1, $2, $3, $4)
      `, [serviceName, result.healthy, result.latency_ms, result.error || null]);

      // Get rolling window
      const historyResult = await client.query(`
        SELECT healthy
        FROM monitoring.service_health_checks
        WHERE service_name = $1
        ORDER BY created_at DESC
        LIMIT $2
      `, [serviceName, config.history_window]);

      const history = historyResult.rows;
      const successCount = history.filter(h => h.healthy).length;
      const totalCount = history.length;
      const healthScore = totalCount > 0 ? successCount / totalCount : 1.0;

      let status;
      if (healthScore < config.auto_disable_threshold) {
        status = 'disabled';
      } else if (healthScore < config.degraded_threshold) {
        status = 'degraded';
      } else {
        status = 'healthy';
      }

      // Upsert status row
      await client.query(`
        INSERT INTO monitoring.service_health
        (service_name, healthy, health_score, total_checks, successful_checks, failed_checks,
         status, last_check, last_success, last_failure, last_latency_ms, error_message, updated_at)
        VALUES ($1, $2, $3, 1, $4, $5, $6, NOW(),
                CASE WHEN $2 THEN NOW() ELSE NULL END,
                CASE WHEN NOT $2 THEN NOW() ELSE NULL END,
                $7, $8, NOW())
        ON CONFLICT (service_name) DO UPDATE SET
          healthy = $2,
          health_score = $3,
          total_checks = monitoring.service_health.total_checks + 1,
          successful_checks = monitoring.service_health.successful_checks + CASE WHEN $2 THEN 1 ELSE 0 END,
          failed_checks = monitoring.service_health.failed_checks + CASE WHEN NOT $2 THEN 1 ELSE 0 END,
          status = $6,
          last_check = NOW(),
          last_success = CASE WHEN $2 THEN NOW() ELSE monitoring.service_health.last_success END,
          last_failure = CASE WHEN NOT $2 THEN NOW() ELSE monitoring.service_health.last_failure END,
          last_latency_ms = $7,
          error_message = $8,
          updated_at = NOW()
      `, [
        serviceName,
        result.healthy,
        healthScore,
        result.healthy ? 1 : 0,
        result.healthy ? 0 : 1,
        status,
        result.latency_ms,
        result.error || null,
      ]);

      await client.query('COMMIT');
      return { healthScore, status };

    } catch (err) {
      await client.query('ROLLBACK').catch(() => {});
      throw err;
    } finally {
      client.release();
    }
  }

  async getAllServices() {
    await this.initSchema();
    const result = await this.pool.query(`
      SELECT
        service_name, healthy, health_score, total_checks,
        successful_checks, failed_checks, status,
        last_check, last_success, last_failure,
        last_latency_ms, error_message, updated_at
      FROM monitoring.service_health
      ORDER BY health_score DESC
    `);
    return result.rows.map(r => ({
      ...r,
      health_score: parseFloat(r.health_score || 0),
    }));
  }

  async getHistory(serviceName, limit = 20) {
    await this.initSchema();
    const result = await this.pool.query(`
      SELECT id, healthy, latency_ms, error_message, created_at
      FROM monitoring.service_health_checks
      WHERE service_name = $1
      ORDER BY created_at DESC
      LIMIT $2
    `, [serviceName, limit]);
    return result.rows;
  }

  async disableUnhealthy(threshold) {
    await this.initSchema();
    const result = await this.pool.query(`
      UPDATE monitoring.service_health
      SET status = 'disabled', updated_at = NOW()
      WHERE health_score < $1 AND status != 'disabled'
      RETURNING service_name, health_score
    `, [threshold]);
    return result.rows.map(r => r.service_name);
  }
}

// ============================================================================
// SERVICE HEALTH MONITOR
// ============================================================================

/**
 * Service Health Monitor
 *
 * Central class that manages health checks, recording, and metrics.
 * Supports both PostgreSQL and in-memory backends.
 */
class ServiceHealthMonitor {
  /**
   * @param {Object} options
   * @param {Object} options.config - Override default configuration
   * @param {Object} options.pool - pg Pool instance (optional, creates one if omitted)
   * @param {Object} options.store - Custom store backend (InMemoryStore or PostgresStore)
   * @param {Object} options.customChecks - Map of service_name -> async check function
   */
  constructor(options = {}) {
    if (options.config) {
      config = { ...config, ...options.config };
    }

    this._pool = options.pool || null;
    this._store = options.store || null;
    this._customChecks = new Map(Object.entries(options.customChecks || {}));
    this._schedulerInterval = null;
    this._initialized = false;

    // Default service list
    this._defaultServices = [
      'postgresql',
      'prometheus',
      'anthropic',
      'openai',
      'google',
      'openrouter',
    ];
  }

  /**
   * Lazy-initialize storage backend.
   * Tries PostgreSQL first, falls back to in-memory.
   */
  async _getStore() {
    if (this._store) return this._store;

    // Try PostgreSQL
    if (!this._pool) {
      try {
        const { Pool } = require('pg');
        this._pool = new Pool({
          host: config.pg_host,
          port: config.pg_port,
          database: config.pg_database,
          user: config.pg_user,
          password: config.pg_password,
          max: 10,
          idleTimeoutMillis: 30000,
          connectionTimeoutMillis: 5000,
        });
        this._pool.on('error', (err) => {
          console.error('[ServiceHealth] PostgreSQL pool error:', err.message);
        });
      } catch (_err) {
        // pg module not available
        this._store = new InMemoryStore();
        return this._store;
      }
    }

    // Test connection
    try {
      const client = await this._pool.connect();
      client.release();
      this._store = new PostgresStore(this._pool);
    } catch (_err) {
      console.warn('[ServiceHealth] PostgreSQL unavailable, using in-memory store');
      this._store = new InMemoryStore();
    }

    return this._store;
  }

  /**
   * Initialize schema (PostgreSQL only).
   */
  async initSchema() {
    const store = await this._getStore();
    if (store instanceof PostgresStore) {
      await store.initSchema();
    }
  }

  // --------------------------------------------------------------------------
  // HEALTH CHECK IMPLEMENTATIONS
  // --------------------------------------------------------------------------

  /**
   * Check PostgreSQL health
   * @returns {Promise<Object>} { healthy, latency_ms, error }
   */
  async _checkPostgresHealth() {
    const startTime = Date.now();
    try {
      if (!this._pool) {
        return {
          healthy: false,
          latency_ms: Date.now() - startTime,
          error: 'No PostgreSQL pool configured',
        };
      }
      const client = await this._pool.connect();
      try {
        await client.query('SELECT 1');
        return {
          healthy: true,
          latency_ms: Date.now() - startTime,
          error: null,
        };
      } finally {
        client.release();
      }
    } catch (err) {
      return {
        healthy: false,
        latency_ms: Date.now() - startTime,
        error: err.message,
      };
    }
  }

  /**
   * Check Prometheus exporter health
   * @returns {Promise<Object>} { healthy, latency_ms, error }
   */
  async _checkPrometheusHealth() {
    const startTime = Date.now();
    return new Promise((resolve) => {
      try {
        const options = {
          hostname: 'localhost',
          port: config.prometheus_port,
          path: config.prometheus_health_path,
          timeout: config.health_check_timeout_ms,
        };

        const req = http.get(options, (res) => {
          // Drain the response to prevent memory leaks
          res.resume();
          if (res.statusCode === 200) {
            resolve({
              healthy: true,
              latency_ms: Date.now() - startTime,
              error: null,
            });
          } else {
            resolve({
              healthy: false,
              latency_ms: Date.now() - startTime,
              error: `HTTP ${res.statusCode}`,
            });
          }
        });

        req.on('error', (err) => {
          resolve({
            healthy: false,
            latency_ms: Date.now() - startTime,
            error: err.message,
          });
        });

        req.on('timeout', () => {
          req.destroy();
          resolve({
            healthy: false,
            latency_ms: Date.now() - startTime,
            error: 'Timeout',
          });
        });
      } catch (err) {
        resolve({
          healthy: false,
          latency_ms: Date.now() - startTime,
          error: err.message,
        });
      }
    });
  }

  /**
   * Check API provider health (generic)
   * @param {string} provider - Provider name
   * @returns {Promise<Object>} { healthy, latency_ms, error }
   */
  async _checkAPIProviderHealth(provider) {
    const startTime = Date.now();
    try {
      // Check if API key exists
      const envKey = `${provider.toUpperCase()}_API_KEY`;
      if (!process.env[envKey]) {
        return {
          healthy: false,
          latency_ms: Date.now() - startTime,
          error: `${envKey} not set`,
        };
      }

      // If we have a PostgreSQL pool, try to query api_health_status
      if (this._pool) {
        try {
          const client = await this._pool.connect();
          try {
            const result = await client.query(`
              SELECT status, success_rate, last_check
              FROM monitoring.api_health_status
              WHERE provider = $1
            `, [provider]);

            if (result.rows.length === 0) {
              return {
                healthy: true,
                latency_ms: Date.now() - startTime,
                error: null,
              };
            }

            const row = result.rows[0];
            const successRate = parseFloat(row.success_rate);

            return {
              healthy: row.status !== 'disabled',
              latency_ms: Date.now() - startTime,
              error: row.status === 'disabled'
                ? `Disabled (success rate: ${(successRate * 100).toFixed(1)}%)`
                : null,
            };
          } finally {
            client.release();
          }
        } catch (_err) {
          // DB query failed, fall through to env-key-only check
        }
      }

      // Fallback: API key exists, assume healthy
      return {
        healthy: true,
        latency_ms: Date.now() - startTime,
        error: null,
      };
    } catch (err) {
      return {
        healthy: false,
        latency_ms: Date.now() - startTime,
        error: err.message,
      };
    }
  }

  // --------------------------------------------------------------------------
  // PUBLIC API
  // --------------------------------------------------------------------------

  /**
   * Register a custom health check function.
   *
   * @param {string} serviceName - Service identifier
   * @param {Function} checkFn - Async function returning { healthy, latency_ms, error }
   */
  registerCheck(serviceName, checkFn) {
    if (typeof checkFn !== 'function') {
      throw new Error(`checkFn for "${serviceName}" must be a function`);
    }
    this._customChecks.set(serviceName, checkFn);
    if (!this._defaultServices.includes(serviceName)) {
      this._defaultServices.push(serviceName);
    }
  }

  /**
   * Unregister a custom health check.
   * @param {string} serviceName
   */
  unregisterCheck(serviceName) {
    this._customChecks.delete(serviceName);
    const idx = this._defaultServices.indexOf(serviceName);
    if (idx >= 0) this._defaultServices.splice(idx, 1);
  }

  /**
   * Check health of a specific service.
   *
   * @param {string} serviceName - Service name
   * @returns {Promise<Object>} { healthy, latency_ms, error }
   */
  async checkServiceHealth(serviceName) {
    // Check custom checks first
    if (this._customChecks.has(serviceName)) {
      const startTime = Date.now();
      try {
        const result = await this._customChecks.get(serviceName)();
        // Normalize result
        return {
          healthy: Boolean(result.healthy),
          latency_ms: result.latency_ms != null ? result.latency_ms : Date.now() - startTime,
          error: result.error || null,
        };
      } catch (err) {
        return {
          healthy: false,
          latency_ms: Date.now() - startTime,
          error: err.message,
        };
      }
    }

    // Built-in checks
    switch (serviceName) {
      case 'postgresql':
        return this._checkPostgresHealth();
      case 'prometheus':
        return this._checkPrometheusHealth();
      case 'anthropic':
      case 'openai':
      case 'google':
      case 'openrouter':
        return this._checkAPIProviderHealth(serviceName);
      default:
        return {
          healthy: false,
          latency_ms: 0,
          error: `Unknown service: ${serviceName}`,
        };
    }
  }

  /**
   * Check health of all registered services.
   * @returns {Promise<Object>} Map of service_name -> { healthy, latency_ms, error }
   */
  async checkAllServices() {
    const results = {};

    await Promise.allSettled(
      this._defaultServices.map(async (service) => {
        try {
          results[service] = await this.checkServiceHealth(service);
        } catch (err) {
          results[service] = {
            healthy: false,
            latency_ms: 0,
            error: err.message,
          };
        }
      })
    );

    return results;
  }

  /**
   * Record a health check result to the backend store.
   *
   * @param {string} serviceName
   * @param {Object} result - { healthy, latency_ms, error }
   * @returns {Promise<Object>} { healthScore, status }
   */
  async recordHealthCheck(serviceName, result) {
    const store = await this._getStore();
    const { healthScore, status } = store instanceof PostgresStore
      ? await store.recordCheck(serviceName, result)
      : store.recordCheck(serviceName, result);

    // Log status changes
    if (status === 'disabled') {
      console.warn(`[ServiceHealth] Service ${serviceName} DISABLED (health score: ${(healthScore * 100).toFixed(1)}%)`);
    } else if (status === 'degraded') {
      console.warn(`[ServiceHealth] Service ${serviceName} degraded (health score: ${(healthScore * 100).toFixed(1)}%)`);
    }

    return { healthScore, status };
  }

  /**
   * Auto-disable services below health threshold.
   *
   * @param {number} threshold - Health threshold (0.0-1.0), defaults to config
   * @returns {Promise<Array<string>>} List of newly disabled service names
   */
  async autoDisableUnhealthy(threshold = config.auto_disable_threshold) {
    const store = await this._getStore();
    const disabled = store instanceof PostgresStore
      ? await store.disableUnhealthy(threshold)
      : store.disableUnhealthy(threshold);

    if (disabled.length > 0) {
      console.warn(`[ServiceHealth] Auto-disabled ${disabled.length} services: ${disabled.join(', ')}`);
    }

    return disabled;
  }

  /**
   * Run a complete health check cycle: check all services, record results, auto-disable.
   * @returns {Promise<Object>} { results, healthy, total }
   */
  async runHealthChecks() {
    const results = await this.checkAllServices();

    for (const [serviceName, result] of Object.entries(results)) {
      try {
        await this.recordHealthCheck(serviceName, result);
      } catch (err) {
        console.error(`[ServiceHealth] Failed to record check for ${serviceName}:`, err.message);
      }
    }

    await this.autoDisableUnhealthy();

    const healthy = Object.values(results).filter(r => r.healthy).length;
    const total = Object.keys(results).length;

    return { results, healthy, total };
  }

  // --------------------------------------------------------------------------
  // QUERY API
  // --------------------------------------------------------------------------

  /**
   * Get health status for all services.
   * @returns {Promise<Array<Object>>}
   */
  async getHealthStatus() {
    const store = await this._getStore();
    const rows = store instanceof PostgresStore
      ? await store.getAllServices()
      : store.getAllServices();

    return rows.map(r => ({
      service_name: r.service_name,
      healthy: r.healthy,
      health_score: typeof r.health_score === 'number' ? r.health_score : parseFloat(r.health_score || 0),
      health_percent: ((typeof r.health_score === 'number' ? r.health_score : parseFloat(r.health_score || 0)) * 100).toFixed(1),
      total_checks: r.total_checks,
      successful_checks: r.successful_checks,
      failed_checks: r.failed_checks,
      status: r.status,
      last_check: r.last_check,
      last_success: r.last_success,
      last_failure: r.last_failure,
      last_latency_ms: r.last_latency_ms,
      error_message: r.error_message,
      updated_at: r.updated_at,
    }));
  }

  /**
   * Get health check history for a specific service.
   *
   * @param {string} serviceName
   * @param {number} limit - Number of recent checks
   * @returns {Promise<Array<Object>>}
   */
  async getHealthHistory(serviceName, limit = 20) {
    const store = await this._getStore();
    return store instanceof PostgresStore
      ? await store.getHistory(serviceName, limit)
      : store.getHistory(serviceName, limit);
  }

  // --------------------------------------------------------------------------
  // PROMETHEUS METRICS
  // --------------------------------------------------------------------------

  /**
   * Generate health metrics in Prometheus exposition format.
   * @returns {Promise<string>}
   */
  async getHealthMetrics() {
    const services = await this.getHealthStatus();
    const lines = [];

    // service_health_score
    lines.push('# HELP service_health_score Health score per service (rolling window)');
    lines.push('# TYPE service_health_score gauge');
    for (const svc of services) {
      lines.push(`service_health_score{service="${svc.service_name}",status="${svc.status}"} ${svc.health_score.toFixed(4)}`);
    }
    lines.push('');

    // service_health_checks_total
    lines.push('# HELP service_health_checks_total Total health checks per service');
    lines.push('# TYPE service_health_checks_total counter');
    for (const svc of services) {
      lines.push(`service_health_checks_total{service="${svc.service_name}"} ${svc.total_checks}`);
    }
    lines.push('');

    // service_health_checks_successful
    lines.push('# HELP service_health_checks_successful Successful health checks');
    lines.push('# TYPE service_health_checks_successful counter');
    for (const svc of services) {
      lines.push(`service_health_checks_successful{service="${svc.service_name}"} ${svc.successful_checks}`);
    }
    lines.push('');

    // service_health_checks_failed
    lines.push('# HELP service_health_checks_failed Failed health checks');
    lines.push('# TYPE service_health_checks_failed counter');
    for (const svc of services) {
      lines.push(`service_health_checks_failed{service="${svc.service_name}"} ${svc.failed_checks}`);
    }
    lines.push('');

    // service_health_latency_ms
    lines.push('# HELP service_health_latency_ms Last health check latency (ms)');
    lines.push('# TYPE service_health_latency_ms gauge');
    for (const svc of services) {
      const latency = svc.last_latency_ms || 0;
      lines.push(`service_health_latency_ms{service="${svc.service_name}"} ${latency}`);
    }
    lines.push('');

    // service_health_status (0=healthy, 1=degraded, 2=disabled)
    lines.push('# HELP service_health_status Service status (0=healthy, 1=degraded, 2=disabled)');
    lines.push('# TYPE service_health_status gauge');
    for (const svc of services) {
      let statusCode;
      if (svc.status === 'healthy') statusCode = 0;
      else if (svc.status === 'degraded') statusCode = 1;
      else statusCode = 2;
      lines.push(`service_health_status{service="${svc.service_name}"} ${statusCode}`);
    }
    lines.push('');

    return lines.join('\n');
  }

  // --------------------------------------------------------------------------
  // SCHEDULER
  // --------------------------------------------------------------------------

  /**
   * Start periodic health check scheduler.
   * @returns {Object} { stop: Function }
   */
  startScheduler() {
    if (this._schedulerInterval) {
      console.warn('[ServiceHealth] Scheduler already running');
      return { stop: () => this.stopScheduler() };
    }

    console.log(`[ServiceHealth] Starting scheduler (interval: ${config.check_interval_ms}ms)`);

    // Run immediately
    this.runHealthChecks().catch(err => {
      console.error('[ServiceHealth] Initial health check failed:', err.message);
    });

    // Schedule periodic
    this._schedulerInterval = setInterval(() => {
      this.runHealthChecks().catch(err => {
        console.error('[ServiceHealth] Periodic health check failed:', err.message);
      });
    }, config.check_interval_ms);

    return { stop: () => this.stopScheduler() };
  }

  /**
   * Stop the scheduler.
   */
  stopScheduler() {
    if (this._schedulerInterval) {
      clearInterval(this._schedulerInterval);
      this._schedulerInterval = null;
      console.log('[ServiceHealth] Scheduler stopped');
    }
  }

  // --------------------------------------------------------------------------
  // LIFECYCLE
  // --------------------------------------------------------------------------

  /**
   * Close connections and clean up.
   */
  async close() {
    this.stopScheduler();
    if (this._pool) {
      try {
        await this._pool.end();
      } catch (_err) {
        // Pool already ended or not connected
      }
      this._pool = null;
    }
    this._store = null;
    console.log('[ServiceHealth] Closed');
  }

  /**
   * Get current configuration (read-only copy).
   */
  getConfig() {
    return { ...config };
  }
}

// ============================================================================
// FACTORY + CONVENIENCE EXPORTS
// ============================================================================

// Default singleton instance (lazy)
let _defaultInstance = null;

/**
 * Get or create the default ServiceHealthMonitor instance.
 * @param {Object} options - Options for ServiceHealthMonitor constructor
 * @returns {ServiceHealthMonitor}
 */
function getServiceHealthMonitor(options = {}) {
  if (!_defaultInstance) {
    _defaultInstance = new ServiceHealthMonitor(options);
  }
  return _defaultInstance;
}

/**
 * Create a fresh ServiceHealthMonitor (does not affect singleton).
 * Useful for testing.
 * @param {Object} options
 * @returns {ServiceHealthMonitor}
 */
function createServiceHealthMonitor(options = {}) {
  return new ServiceHealthMonitor(options);
}

// Convenience wrapper functions that delegate to the singleton
async function initSchema() {
  return getServiceHealthMonitor().initSchema();
}

async function checkServiceHealth(serviceName) {
  return getServiceHealthMonitor().checkServiceHealth(serviceName);
}

async function checkAllServices() {
  return getServiceHealthMonitor().checkAllServices();
}

async function recordHealthCheck(serviceName, result) {
  return getServiceHealthMonitor().recordHealthCheck(serviceName, result);
}

async function runHealthChecks() {
  return getServiceHealthMonitor().runHealthChecks();
}

async function autoDisableUnhealthy(threshold) {
  return getServiceHealthMonitor().autoDisableUnhealthy(threshold);
}

async function getHealthMetrics() {
  return getServiceHealthMonitor().getHealthMetrics();
}

function startScheduler() {
  return getServiceHealthMonitor().startScheduler();
}

async function getHealthStatus() {
  return getServiceHealthMonitor().getHealthStatus();
}

async function getHealthHistory(serviceName, limit) {
  return getServiceHealthMonitor().getHealthHistory(serviceName, limit);
}

async function close() {
  if (_defaultInstance) {
    await _defaultInstance.close();
    _defaultInstance = null;
  }
}

// ============================================================================
// MODULE EXPORTS
// ============================================================================

module.exports = {
  // Classes (for advanced usage and testing)
  ServiceHealthMonitor,
  InMemoryStore,
  PostgresStore,

  // Factory
  getServiceHealthMonitor,
  createServiceHealthMonitor,

  // Convenience (singleton-based)
  initSchema,
  checkServiceHealth,
  checkAllServices,
  recordHealthCheck,
  runHealthChecks,
  autoDisableUnhealthy,
  getHealthMetrics,
  startScheduler,
  getHealthStatus,
  getHealthHistory,
  close,

  // Config
  config,
  DEFAULT_CONFIG,
};
