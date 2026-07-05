/**
 * Circuit Breaker for Model Failure Protection
 */

const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('[CircuitBreaker] PostgreSQL pool error:', err.message);
});

const DEFAULT_CONFIG = {
  failure_threshold: 5,
  timeout_ms: 30000,
  half_open_max_calls: 3,
  half_open_success_threshold: 2,
};

let config = { ...DEFAULT_CONFIG };
const CONFIG_PATH = path.join(__dirname, '../monitoring/webhook-config.json');

try {
  if (fs.existsSync(CONFIG_PATH)) {
    const fileConfig = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    if (fileConfig.thresholds?.circuit_breaker) {
      config = { ...DEFAULT_CONFIG, ...fileConfig.thresholds.circuit_breaker };
    }
  }
} catch (err) {
  console.warn('[CircuitBreaker] Failed to load config:', err.message);
}

const circuitState = {};

function getCircuitState(model) {
  if (!circuitState[model]) {
    circuitState[model] = {
      state: 'closed',
      consecutive_failures: 0,
      last_failure_time: null,
      last_success_time: null,
      half_open_calls: 0,
      half_open_successes: 0,
      total_failures: 0,
      total_successes: 0,
      call_history: [],
    };
  }

  // Add test-compatible aliases as getters
  const state = circuitState[model];
  if (!Object.prototype.hasOwnProperty.call(state, 'success_count')) {
    Object.defineProperty(state, 'success_count', {
      get() { return this.total_successes; },
      enumerable: true,
    });
    Object.defineProperty(state, 'failure_count', {
      get() { return this.total_failures; },
      enumerable: true,
    });
  }

  return state;
}

function isOpen(model) {
  const state = getCircuitState(model);
  if (state.state === 'open') {
    const now = Date.now();
    const timeSinceFailure = now - state.last_failure_time;
    if (timeSinceFailure >= config.timeout_ms) {
      state.state = 'half_open';
      state.half_open_calls = 0;
      state.half_open_successes = 0;
      console.log(`[CircuitBreaker] ${model}: OPEN → HALF_OPEN (testing recovery)`);
      return false;
    }
    return true;
  }
  if (state.state === 'half_open') {
    if (state.half_open_calls >= config.half_open_max_calls) {
      state.state = 'open';
      state.last_failure_time = Date.now();
      console.log(`[CircuitBreaker] ${model}: HALF_OPEN → OPEN (failed recovery test)`);
      return true;
    }
    return false;
  }
  return false;
}

function recordSuccess(model, metadata = null) {
  const state = getCircuitState(model);
  state.last_success_time = Date.now();
  state.total_successes += 1;

  // Initialize call_history if not exists
  if (!state.call_history) {
    state.call_history = [];
  }

  // Add to call history (keep last 10)
  state.call_history.push({ success: true, timestamp: Date.now(), metadata });
  if (state.call_history.length > 10) {
    state.call_history.shift();
  }

  if (state.state === 'half_open') {
    state.half_open_calls += 1;
    state.half_open_successes += 1;
    if (state.half_open_successes >= config.half_open_success_threshold) {
      state.state = 'closed';
      state.consecutive_failures = 0;
      console.log(`[CircuitBreaker] ${model}: HALF_OPEN → CLOSED (recovered)`);
    }
  } else if (state.state === 'closed') {
    state.consecutive_failures = 0;
  }

  // Return updated state for compatibility
  return state;
}

async function recordFailure(model, reason = 'Unknown error', metadata = null) {
  const state = getCircuitState(model);
  state.last_failure_time = Date.now();
  state.total_failures += 1;
  state.consecutive_failures += 1;

  // Initialize call_history if not exists
  if (!state.call_history) {
    state.call_history = [];
  }

  // Add to call history (keep last 10)
  state.call_history.push({
    success: false,
    timestamp: Date.now(),
    failure_type: reason, // Store reason as failure_type for test compatibility
    reason,
    metadata
  });
  if (state.call_history.length > 10) {
    state.call_history.shift();
  }

  if (state.state === 'half_open') {
    state.half_open_calls += 1;
    state.state = 'open';
    console.log(`[CircuitBreaker] ${model}: HALF_OPEN → OPEN (failure during recovery)`);
    await sendCircuitBreakerNotification(model, state, reason);
  } else if (state.state === 'closed') {
    if (state.consecutive_failures >= config.failure_threshold) {
      state.state = 'open';
      console.log(`[CircuitBreaker] ${model}: CLOSED → OPEN (${state.consecutive_failures} consecutive failures)`);
      await sendCircuitBreakerNotification(model, state, reason);
      await logCircuitBreakerEvent(model, 'open', reason, state);
    }
  }

  // Return updated state for compatibility
  return state;
}

async function sendCircuitBreakerNotification(model, state, reason) {
  try {
    const { notifyCircuitBreaker } = require('../monitoring/webhook-notifier.cjs');
    const nextRetryAt = new Date(state.last_failure_time + config.timeout_ms);
    await notifyCircuitBreaker(model, {
      state: state.state,
      reason,
      consecutive_failures: state.consecutive_failures,
      next_retry_at: nextRetryAt.toISOString(),
    });
  } catch (err) {
    console.error('[CircuitBreaker] Failed to send webhook:', err.message);
  }
}

async function logCircuitBreakerEvent(model, event, reason, state) {
  const client = await pool.connect();
  try {
    const tableExists = await client.query(`SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'monitoring' AND table_name = 'circuit_breaker_events')`);
    if (!tableExists.rows[0].exists) {
      await client.query(`CREATE TABLE monitoring.circuit_breaker_events (id SERIAL PRIMARY KEY, model VARCHAR(100), event VARCHAR(20), reason TEXT, consecutive_failures INT, total_failures INT, total_successes INT, metadata JSONB, created_at TIMESTAMPTZ DEFAULT NOW())`);
      await client.query(`CREATE INDEX idx_cbe_model ON monitoring.circuit_breaker_events(model)`);
      await client.query(`CREATE INDEX idx_cbe_event ON monitoring.circuit_breaker_events(event, created_at)`);
    }
    await client.query(`INSERT INTO monitoring.circuit_breaker_events (model, event, reason, consecutive_failures, total_failures, total_successes, metadata) VALUES ($1, $2, $3, $4, $5, $6, $7)`, [model, event, reason, state.consecutive_failures, state.total_failures, state.total_successes, JSON.stringify({ last_failure_time: state.last_failure_time, last_success_time: state.last_success_time, config })]);
  } catch (err) {
    console.error('[CircuitBreaker] Failed to log event:', err.message);
  } finally {
    client.release();
  }
}

function reset(model) {
  if (circuitState[model]) {
    circuitState[model] = { state: 'closed', consecutive_failures: 0, last_failure_time: null, last_success_time: null, half_open_calls: 0, half_open_successes: 0, total_failures: circuitState[model].total_failures, total_successes: circuitState[model].total_successes };
    console.log(`[CircuitBreaker] Manually reset: ${model}`);
  }
}

function getAllStates() {
  const states = {};
  for (const [model, state] of Object.entries(circuitState)) {
    states[model] = { ...state, is_open: state.state === 'open', next_retry_at: state.state === 'open' ? new Date(state.last_failure_time + config.timeout_ms).toISOString() : null };
  }
  return states;
}

async function execute(model, fn) {
  if (isOpen(model)) {
    const state = getCircuitState(model);
    const nextRetryAt = new Date(state.last_failure_time + config.timeout_ms);
    throw new Error(`Circuit breaker OPEN for ${model}. Retry at ${nextRetryAt.toISOString()} (${state.consecutive_failures} consecutive failures)`);
  }
  try {
    const result = await fn();
    recordSuccess(model);
    return result;
  } catch (err) {
    await recordFailure(model, err.message);
    throw err;
  }
}

async function close() {
  await pool.end();
}

/**
 * Get circuit breaker instance with provider-level filtering
 * Integrates with api-health-monitor.cjs for provider availability
 *
 * @returns {Object} Circuit breaker with filterAvailableModels()
 */
function getCircuitBreaker() {
  return {
    execute,
    isOpen,
    recordSuccess,
    recordFailure,
    reset,
    resetCircuit: reset, // Alias for compatibility
    getAllStates,
    getCircuitState,
    getState: getCircuitState, // Alias for test compatibility
    config,
    close,

    /**
     * Check if a model is available (circuit not open)
     */
    async isAvailable(model) {
      const state = getCircuitState(model);
      const available = state.state !== 'open';
      return {
        available,
        state: state.state,
        reason: state.total_failures === 0 && state.total_successes === 0 ? 'no_history' : (available ? 'healthy' : 'circuit_open')
      };
    },

    /**
     * Get list of models with open circuits
     */
    async getOpenCircuits() {
      const states = getAllStates();
      return Object.entries(states)
        .filter(([_, state]) => state.is_open)
        .map(([model, state]) => ({ model, ...state }));
    },

    /**
     * Get circuit breaker statistics
     */
    async getStatistics() {
      const states = getAllStates();
      const models = Object.keys(states);
      const openCount = Object.values(states).filter(s => s.is_open).length;
      const halfOpenCount = Object.values(states).filter(s => s.state === 'half-open').length;
      const closedCount = models.length - openCount - halfOpenCount;

      return {
        total_models: models.length,
        open: openCount,
        half_open: halfOpenCount,
        closed: closedCount,
        states
      };
    },

    /**
     * Filter models by provider availability
     * Removes models from disabled providers (via api-health-monitor.cjs)
     *
     * @param {Array<string>} models - List of model names
     * @returns {Promise<Array<string>>} Filtered model list
     */
    async filterAvailableModels(models) {
      try {
        const { getProviderAvailability } = require('../monitoring/api-health-monitor.cjs');
        const { available, disabled } = await getProviderAvailability();

        if (disabled.length === 0) {
          return models; // All providers available
        }

        // Extract provider from model name (e.g., "anthropic/opus" -> "anthropic")
        const disabledProviders = new Set(disabled.map(d => d.provider));

        const filtered = models.filter(model => {
          const provider = model.split('/')[0].toLowerCase();
          return !disabledProviders.has(provider);
        });

        if (filtered.length < models.length) {
          console.warn(`[CircuitBreaker] Filtered ${models.length - filtered.length} models from disabled providers: ${Array.from(disabledProviders).join(', ')}`);
        }

        return filtered;
      } catch (err) {
        console.warn(`[CircuitBreaker] Provider filtering failed: ${err.message}`);
        return models; // Graceful degradation - return all models
      }
    }
  };
}

/**
 * Get database instance for testing
 */
function getCircuitBreakerDB() {
  return {
    pool,
    async initialize() {
      // Create the circuit_breaker_state table if it doesn't exist
      try {
        await pool.query(`
          CREATE TABLE IF NOT EXISTS workflow.circuit_breaker_state (
            model TEXT PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'closed',
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            last_failure_time TIMESTAMPTZ,
            last_success_time TIMESTAMPTZ,
            call_history JSONB DEFAULT '[]'::jsonb,
            half_open_calls INTEGER NOT NULL DEFAULT 0,
            half_open_successes INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
          )
        `);
      } catch (err) {
        // Table might already exist or schema might not exist
        console.warn(`[CircuitBreaker] DB initialization warning: ${err.message}`);
      }
      return Promise.resolve();
    },
    async updateState(model, updates) {
      // Stub for test compatibility - not implemented in current in-memory version
      return Promise.resolve();
    },
    async close() {
      // Pool is shared, don't close it here
      // This is a no-op for compatibility with tests
      return Promise.resolve();
    }
  };
}

// Enums for test compatibility
const CircuitState = {
  CLOSED: 'closed',
  OPEN: 'open',
  HALF_OPEN: 'half-open'
};

const FailureType = {
  API_ERROR: 'api_error',
  TIMEOUT: 'timeout',
  RATE_LIMIT: 'rate_limit',
  UNKNOWN: 'unknown'
};

// Helper function for wrapping async operations
async function withCircuitBreaker(model, fn) {
  return execute(model, fn);
}

// Class-based interface for compatibility
class CircuitBreaker {
  constructor(model) {
    this.model = model;
  }

  async execute(fn) {
    return execute(this.model, fn);
  }

  isOpen() {
    return isOpen(this.model);
  }

  async recordSuccess() {
    return recordSuccess(this.model);
  }

  async recordFailure(error) {
    return recordFailure(this.model, error);
  }

  reset() {
    return reset(this.model);
  }

  getState() {
    return getCircuitState(this.model);
  }
}

module.exports = {
  execute,
  isOpen,
  recordSuccess,
  recordFailure,
  reset,
  getAllStates,
  getCircuitState,
  config,
  close,
  getCircuitBreaker,
  getCircuitBreakerDB,
  withCircuitBreaker,
  CircuitBreaker,
  CircuitState,
  FailureType
};
