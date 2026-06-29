/**
 * Service Interface Contracts
 *
 * Base Service class with lifecycle management (initialize, execute,
 * healthCheck, shutdown) and a singleton ServiceRegistry for dependency
 * injection and service discovery.
 *
 * Usage:
 *   const { Service, ServiceRegistry } = require('./service-interface.cjs');
 *
 *   class MyService extends Service {
 *     constructor() { super('my-service', '1.0.0'); }
 *     async _doInitialize(config) { ... }
 *     async _doExecute(input) { return result; }
 *     async _doHealthCheck() { return { healthy: true }; }
 *     async _doShutdown() { ... }
 *   }
 *
 *   const registry = ServiceRegistry.getInstance();
 *   registry.register(new MyService());
 *   const svc = registry.get('my-service');
 *   await svc.initialize({ port: 8080 });
 *   const result = await svc.execute({ task: 'work' });
 */

'use strict';

// ---------------------------------------------------------------------------
// Service States
// ---------------------------------------------------------------------------

const ServiceState = Object.freeze({
  CREATED:      'created',
  INITIALIZING: 'initializing',
  READY:        'ready',
  EXECUTING:    'executing',
  DEGRADED:     'degraded',
  SHUTTING_DOWN: 'shutting_down',
  STOPPED:      'stopped',
  ERROR:        'error',
});

// ---------------------------------------------------------------------------
// ServiceError
// ---------------------------------------------------------------------------

class ServiceError extends Error {
  /**
   * @param {string} message
   * @param {string} serviceName
   * @param {string} code - Machine-readable error code
   * @param {Error} [cause] - Underlying error
   */
  constructor(message, serviceName, code, cause) {
    super(message);
    this.name = 'ServiceError';
    this.serviceName = serviceName;
    this.code = code;
    this.cause = cause || null;
    this.timestamp = new Date().toISOString();
  }
}

// ---------------------------------------------------------------------------
// Base Service
// ---------------------------------------------------------------------------

class Service {
  /**
   * @param {string} name    - Unique service identifier
   * @param {string} version - Semantic version string
   */
  constructor(name, version) {
    if (new.target === Service) {
      throw new ServiceError(
        'Service is abstract and cannot be instantiated directly',
        name || 'unknown',
        'ABSTRACT_INSTANTIATION'
      );
    }

    if (!name || typeof name !== 'string') {
      throw new ServiceError(
        'Service name is required and must be a non-empty string',
        'unknown',
        'INVALID_NAME'
      );
    }

    if (!version || typeof version !== 'string') {
      throw new ServiceError(
        'Service version is required and must be a non-empty string',
        name,
        'INVALID_VERSION'
      );
    }

    /** @type {string} */
    this.name = name;

    /** @type {string} */
    this.version = version;

    /** @type {string} */
    this.state = ServiceState.CREATED;

    /** @type {Object|null} */
    this._config = null;

    /** @type {Object} */
    this._metrics = {
      initializeCount: 0,
      executeCount: 0,
      executeErrorCount: 0,
      healthCheckCount: 0,
      lastExecuteMs: 0,
      totalExecuteMs: 0,
      lastHealthCheck: null,
      startedAt: null,
    };

    /** @type {string[]} */
    this._dependencies = [];
  }

  // ---- Lifecycle methods (public API) ----

  /**
   * Initialize the service with configuration.
   * Transitions: CREATED | STOPPED | ERROR -> READY
   *
   * @param {Object} [config={}] - Service configuration
   * @returns {Promise<void>}
   * @throws {ServiceError} If already initialized or initialization fails
   */
  async initialize(config = {}) {
    const allowed = [ServiceState.CREATED, ServiceState.STOPPED, ServiceState.ERROR];
    if (!allowed.includes(this.state)) {
      throw new ServiceError(
        `Cannot initialize service in state "${this.state}"; ` +
          `allowed states: ${allowed.join(', ')}`,
        this.name,
        'INVALID_STATE_TRANSITION'
      );
    }

    this.state = ServiceState.INITIALIZING;

    try {
      this._config = Object.freeze({ ...config });
      await this._doInitialize(this._config);
      this.state = ServiceState.READY;
      this._metrics.initializeCount++;
      this._metrics.startedAt = new Date().toISOString();
    } catch (err) {
      this.state = ServiceState.ERROR;
      throw new ServiceError(
        `Initialization failed for service "${this.name}": ${err.message}`,
        this.name,
        'INIT_FAILED',
        err
      );
    }
  }

  /**
   * Execute a task on the service.
   *
   * @param {*} input - Task input (shape determined by subclass)
   * @returns {Promise<*>} Task result
   * @throws {ServiceError} If service is not ready
   */
  async execute(input) {
    if (this.state !== ServiceState.READY && this.state !== ServiceState.DEGRADED) {
      throw new ServiceError(
        `Cannot execute on service "${this.name}" in state "${this.state}"; ` +
          'service must be in "ready" or "degraded" state',
        this.name,
        'NOT_READY'
      );
    }

    const prevState = this.state;
    this.state = ServiceState.EXECUTING;

    const start = Date.now();
    try {
      const result = await this._doExecute(input);
      const elapsed = Date.now() - start;

      this._metrics.executeCount++;
      this._metrics.lastExecuteMs = elapsed;
      this._metrics.totalExecuteMs += elapsed;

      this.state = ServiceState.READY;
      return result;
    } catch (err) {
      this._metrics.executeErrorCount++;
      const elapsed = Date.now() - start;
      this._metrics.lastExecuteMs = elapsed;
      this._metrics.totalExecuteMs += elapsed;

      // Revert to previous state (READY or DEGRADED) rather than ERROR
      // so transient failures don't kill the service permanently.
      this.state = prevState;

      throw new ServiceError(
        `Execution failed on service "${this.name}": ${err.message}`,
        this.name,
        'EXEC_FAILED',
        err
      );
    }
  }

  /**
   * Check service health.
   *
   * @returns {Promise<Object>} Health report
   *   { healthy: boolean, state: string, metrics: Object, details?: Object }
   */
  async healthCheck() {
    this._metrics.healthCheckCount++;
    this._metrics.lastHealthCheck = new Date().toISOString();

    try {
      const details = await this._doHealthCheck();
      const healthy = details && details.healthy !== false;

      if (!healthy && this.state === ServiceState.READY) {
        this.state = ServiceState.DEGRADED;
      } else if (healthy && this.state === ServiceState.DEGRADED) {
        this.state = ServiceState.READY;
      }

      return {
        service: this.name,
        version: this.version,
        state: this.state,
        healthy,
        metrics: this.getMetrics(),
        details: details || {},
        timestamp: new Date().toISOString(),
      };
    } catch (err) {
      if (this.state === ServiceState.READY) {
        this.state = ServiceState.DEGRADED;
      }
      return {
        service: this.name,
        version: this.version,
        state: this.state,
        healthy: false,
        metrics: this.getMetrics(),
        error: err.message,
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Gracefully shut down the service.
   *
   * @returns {Promise<void>}
   */
  async shutdown() {
    if (this.state === ServiceState.STOPPED) {
      return; // idempotent
    }

    if (this.state === ServiceState.SHUTTING_DOWN) {
      throw new ServiceError(
        `Service "${this.name}" is already shutting down`,
        this.name,
        'ALREADY_SHUTTING_DOWN'
      );
    }

    const prevState = this.state;
    this.state = ServiceState.SHUTTING_DOWN;

    try {
      await this._doShutdown();
      this.state = ServiceState.STOPPED;
    } catch (err) {
      this.state = prevState;
      throw new ServiceError(
        `Shutdown failed for service "${this.name}": ${err.message}`,
        this.name,
        'SHUTDOWN_FAILED',
        err
      );
    }
  }

  // ---- Metrics ----

  /**
   * Get a snapshot of service metrics.
   * @returns {Object}
   */
  getMetrics() {
    const avgMs =
      this._metrics.executeCount > 0
        ? Math.round(this._metrics.totalExecuteMs / this._metrics.executeCount)
        : 0;

    return {
      ...this._metrics,
      avgExecuteMs: avgMs,
      errorRate:
        this._metrics.executeCount > 0
          ? +(
              this._metrics.executeErrorCount / this._metrics.executeCount
            ).toFixed(4)
          : 0,
    };
  }

  // ---- Dependency declaration ----

  /**
   * Declare services that this service depends on.
   * @param {string[]} serviceNames
   */
  declareDependencies(serviceNames) {
    if (!Array.isArray(serviceNames)) {
      throw new ServiceError(
        'Dependencies must be an array of service names',
        this.name,
        'INVALID_DEPENDENCIES'
      );
    }
    this._dependencies = [...serviceNames];
  }

  /**
   * Get declared dependency names.
   * @returns {string[]}
   */
  getDependencies() {
    return [...this._dependencies];
  }

  // ---- Abstract hooks (subclass must override) ----

  /**
   * Subclass initialization logic.
   * @param {Object} config - Frozen configuration object
   * @returns {Promise<void>}
   */
  async _doInitialize(_config) {
    throw new ServiceError(
      `Service "${this.name}" must implement _doInitialize()`,
      this.name,
      'NOT_IMPLEMENTED'
    );
  }

  /**
   * Subclass execution logic.
   * @param {*} input
   * @returns {Promise<*>}
   */
  async _doExecute(_input) {
    throw new ServiceError(
      `Service "${this.name}" must implement _doExecute()`,
      this.name,
      'NOT_IMPLEMENTED'
    );
  }

  /**
   * Subclass health-check logic.
   * @returns {Promise<Object>} Should include at least { healthy: boolean }
   */
  async _doHealthCheck() {
    // Default: report healthy if state is READY
    return { healthy: this.state === ServiceState.READY || this.state === ServiceState.EXECUTING };
  }

  /**
   * Subclass shutdown logic.
   * @returns {Promise<void>}
   */
  async _doShutdown() {
    // Default: no-op (subclass overrides if cleanup needed)
  }
}

// ---------------------------------------------------------------------------
// ServiceRegistry (Singleton)
// ---------------------------------------------------------------------------

let _registryInstance = null;

class ServiceRegistry {
  constructor() {
    if (_registryInstance) {
      throw new ServiceError(
        'ServiceRegistry is a singleton - use ServiceRegistry.getInstance()',
        'ServiceRegistry',
        'SINGLETON_VIOLATION'
      );
    }
    /** @type {Map<string, Service>} */
    this._services = new Map();
  }

  /**
   * Get the singleton registry instance.
   * @returns {ServiceRegistry}
   */
  static getInstance() {
    if (!_registryInstance) {
      _registryInstance = new ServiceRegistry();
    }
    return _registryInstance;
  }

  /**
   * Reset the singleton (useful for testing).
   * Shuts down all registered services.
   * @returns {Promise<void>}
   */
  static async reset() {
    if (_registryInstance) {
      await _registryInstance.shutdownAll();
      _registryInstance._services.clear();
    }
    _registryInstance = null;
  }

  /**
   * Register a service.
   *
   * @param {Service} service - Service instance to register
   * @param {Object} [options]
   * @param {boolean} [options.replace=false] - If true, replace existing
   * @returns {ServiceRegistry} this (for chaining)
   * @throws {ServiceError} If already registered and not replacing
   */
  register(service, options = {}) {
    if (!(service instanceof Service)) {
      throw new ServiceError(
        'Only Service instances can be registered',
        'ServiceRegistry',
        'INVALID_SERVICE'
      );
    }

    if (this._services.has(service.name) && !options.replace) {
      throw new ServiceError(
        `Service "${service.name}" is already registered; ` +
          'pass { replace: true } to overwrite',
        service.name,
        'DUPLICATE_SERVICE'
      );
    }

    this._services.set(service.name, service);
    return this;
  }

  /**
   * Retrieve a service by name.
   *
   * @param {string} name - Service name
   * @returns {Service}
   * @throws {ServiceError} If not found
   */
  get(name) {
    const service = this._services.get(name);
    if (!service) {
      throw new ServiceError(
        `Service "${name}" is not registered`,
        name,
        'SERVICE_NOT_FOUND'
      );
    }
    return service;
  }

  /**
   * Retrieve a service by name, returning null if not found.
   *
   * @param {string} name - Service name
   * @returns {Service|null}
   */
  getOptional(name) {
    return this._services.get(name) || null;
  }

  /**
   * Check whether a service is registered.
   *
   * @param {string} name - Service name
   * @returns {boolean}
   */
  has(name) {
    return this._services.has(name);
  }

  /**
   * Unregister a service by name.
   *
   * @param {string} name - Service name
   * @returns {boolean} True if the service was removed
   */
  unregister(name) {
    return this._services.delete(name);
  }

  /**
   * List all registered service names.
   *
   * @returns {string[]}
   */
  list() {
    return [...this._services.keys()];
  }

  /**
   * List all registered services with their current state.
   *
   * @returns {Array<{name: string, version: string, state: string}>}
   */
  listDetailed() {
    return [...this._services.values()].map((svc) => ({
      name: svc.name,
      version: svc.version,
      state: svc.state,
    }));
  }

  /**
   * Initialize all registered services, respecting dependency order.
   * Services with unsatisfied dependencies are skipped and reported.
   *
   * @param {Object} [globalConfig={}] - Config passed to every service
   * @returns {Promise<{initialized: string[], failed: {name: string, error: string}[]}>}
   */
  async initializeAll(globalConfig = {}) {
    const initialized = [];
    const failed = [];
    const visited = new Set();

    const initService = async (name) => {
      if (visited.has(name)) return;
      visited.add(name);

      const svc = this._services.get(name);
      if (!svc) {
        failed.push({ name, error: 'Not registered' });
        return;
      }

      // Initialize dependencies first
      for (const dep of svc.getDependencies()) {
        if (!initialized.includes(dep) && !visited.has(dep)) {
          await initService(dep);
        }
        if (!this._services.has(dep)) {
          failed.push({
            name,
            error: `Missing dependency: ${dep}`,
          });
          return;
        }
      }

      try {
        await svc.initialize(globalConfig);
        initialized.push(name);
      } catch (err) {
        failed.push({ name, error: err.message });
      }
    };

    for (const name of this._services.keys()) {
      await initService(name);
    }

    return { initialized, failed };
  }

  /**
   * Run health checks on all services.
   *
   * @returns {Promise<Object[]>} Array of health reports
   */
  async healthCheckAll() {
    const reports = [];
    for (const svc of this._services.values()) {
      const report = await svc.healthCheck();
      reports.push(report);
    }
    return reports;
  }

  /**
   * Shut down all registered services (reverse registration order).
   *
   * @returns {Promise<{stopped: string[], failed: {name: string, error: string}[]}>}
   */
  async shutdownAll() {
    const names = [...this._services.keys()].reverse();
    const stopped = [];
    const failed = [];

    for (const name of names) {
      const svc = this._services.get(name);
      try {
        await svc.shutdown();
        stopped.push(name);
      } catch (err) {
        failed.push({ name, error: err.message });
      }
    }

    return { stopped, failed };
  }

  /**
   * Get the number of registered services.
   * @returns {number}
   */
  get size() {
    return this._services.size;
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = {
  Service,
  ServiceState,
  ServiceError,
  ServiceRegistry,
};
