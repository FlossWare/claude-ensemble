/**
 * Workflow Resource Monitor
 *
 * Tracks memory and CPU usage during workflow execution.
 * Samples resource usage every 1 second and logs aggregated stats to PostgreSQL.
 *
 * Features:
 * - startMonitoring(workflowId) - begins tracking
 * - stopMonitoring(workflowId) - stops and returns stats
 * - Auto-samples every 1 second during execution
 * - Tracks: peak_memory_mb, avg_cpu_percent, duration_ms
 * - Logs to PostgreSQL monitoring.resource_usage table
 *
 * Usage:
 *   const { startMonitoring, stopMonitoring } = require('./shared/workflow-resource-monitor.js');
 *
 *   await startMonitoring('wf-12345');
 *   // ... workflow execution ...
 *   const stats = await stopMonitoring('wf-12345');
 *   // => { peak_memory_mb: 245.3, avg_cpu_percent: 32.5, duration_ms: 45000 }
 *
 * Created: 2026-07-04
 */

const { Pool } = require('pg');
const os = require('os');

// PostgreSQL connection pool
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
  console.error('PostgreSQL pool error (workflow-resource-monitor):', err.message);
});

// Clean up connection pool on process exit
process.on('exit', () => {
  pool.end();
});

process.on('SIGINT', () => {
  pool.end();
  process.exit(0);
});

process.on('SIGTERM', () => {
  pool.end();
  process.exit(0);
});

// Active monitoring sessions
// Map: workflowId -> { startTime, samples: [{timestamp, memory_mb, cpu_percent}], intervalId }
const activeSessions = new Map();

/**
 * Initialize database schema (idempotent)
 * Creates monitoring.resource_usage table if it doesn't exist
 */
async function _initSchema() {
  const createTableSQL = `
    CREATE TABLE IF NOT EXISTS monitoring.resource_usage (
      id SERIAL PRIMARY KEY,
      workflow_id TEXT NOT NULL,
      workflow_execution_id INTEGER,
      start_time TIMESTAMPTZ NOT NULL,
      end_time TIMESTAMPTZ NOT NULL,
      duration_ms INTEGER NOT NULL,
      peak_memory_mb NUMERIC(10, 2) NOT NULL,
      avg_memory_mb NUMERIC(10, 2) NOT NULL,
      min_memory_mb NUMERIC(10, 2) NOT NULL,
      avg_cpu_percent NUMERIC(5, 2) NOT NULL,
      max_cpu_percent NUMERIC(5, 2) NOT NULL,
      min_cpu_percent NUMERIC(5, 2) NOT NULL,
      sample_count INTEGER NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_resource_usage_workflow_id
      ON monitoring.resource_usage(workflow_id);

    CREATE INDEX IF NOT EXISTS idx_resource_usage_workflow_execution_id
      ON monitoring.resource_usage(workflow_execution_id);

    CREATE INDEX IF NOT EXISTS idx_resource_usage_created_at
      ON monitoring.resource_usage(created_at);
  `;

  try {
    await pool.query(createTableSQL);
  } catch (err) {
    console.error('Failed to initialize resource_usage schema:', err.message);
    throw err;
  }
}

// Initialize schema on module load
_initSchema().catch(err => {
  console.error('Schema initialization failed:', err.message);
});

/**
 * Get current memory usage in MB
 * @returns {number} Memory usage in MB
 */
function _getMemoryUsageMB() {
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;
  return usedMem / (1024 * 1024); // Convert to MB
}

/**
 * Get current CPU load percentage (approximate)
 * Uses 1-minute load average normalized by CPU count
 *
 * @returns {number} CPU load percentage (0-100)
 */
function _getCPULoadPercent() {
  const loadAvg = os.loadavg(); // [1min, 5min, 15min]
  const cpuCount = os.cpus().length;

  // Use 1-minute load average
  // Normalize by CPU count (load of 4.0 on 4 cores = 100%)
  const loadPercent = (loadAvg[0] / cpuCount) * 100;

  // Clamp to 0-100 range (load can exceed 100% under heavy load)
  return Math.max(0, Math.min(100, loadPercent));
}

/**
 * Take a resource usage sample
 * @param {string} workflowId - Workflow identifier
 */
function _takeSample(workflowId) {
  const session = activeSessions.get(workflowId);
  if (!session) {
    return; // Session was stopped
  }

  const sample = {
    timestamp: Date.now(),
    memory_mb: _getMemoryUsageMB(),
    cpu_percent: _getCPULoadPercent(),
  };

  session.samples.push(sample);
}

/**
 * Start monitoring resource usage for a workflow
 *
 * @param {string} workflowId - Workflow identifier
 * @param {Object} options - Optional configuration
 * @param {number} options.sampleIntervalMs - Sampling interval in milliseconds (default: 1000)
 * @returns {void}
 *
 * @example
 *   startMonitoring('wf-12345');
 *   startMonitoring('wf-67890', { sampleIntervalMs: 500 }); // Sample every 500ms
 */
function startMonitoring(workflowId, options = {}) {
  if (activeSessions.has(workflowId)) {
    console.warn(`Resource monitoring already active for workflow ${workflowId}`);
    return;
  }

  const sampleIntervalMs = options.sampleIntervalMs || 1000;

  const session = {
    startTime: Date.now(),
    samples: [],
    intervalId: null,
  };

  // Take initial sample
  _takeSample(workflowId);

  // Start periodic sampling
  session.intervalId = setInterval(() => {
    _takeSample(workflowId);
  }, sampleIntervalMs);

  activeSessions.set(workflowId, session);
}

/**
 * Stop monitoring and return aggregated statistics
 *
 * @param {string} workflowId - Workflow identifier
 * @param {Object} options - Optional configuration
 * @param {number} options.workflowExecutionId - Optional workflow execution ID to link in database
 * @returns {Promise<Object>} Aggregated resource usage statistics
 *
 * @example
 *   const stats = await stopMonitoring('wf-12345');
 *   // => {
 *   //   workflow_id: 'wf-12345',
 *   //   duration_ms: 45000,
 *   //   peak_memory_mb: 245.3,
 *   //   avg_memory_mb: 210.5,
 *   //   min_memory_mb: 195.2,
 *   //   avg_cpu_percent: 32.5,
 *   //   max_cpu_percent: 85.3,
 *   //   min_cpu_percent: 5.2,
 *   //   sample_count: 45,
 *   //   start_time: '2026-07-04T10:15:30.000Z',
 *   //   end_time: '2026-07-04T10:16:15.000Z'
 *   // }
 */
async function stopMonitoring(workflowId, options = {}) {
  const session = activeSessions.get(workflowId);
  if (!session) {
    console.warn(`No active resource monitoring session for workflow ${workflowId}`);
    return null;
  }

  // Stop periodic sampling
  if (session.intervalId) {
    clearInterval(session.intervalId);
  }

  // Take final sample
  _takeSample(workflowId);

  // Remove from active sessions
  activeSessions.delete(workflowId);

  const endTime = Date.now();
  const durationMs = endTime - session.startTime;

  // Calculate aggregated statistics
  if (session.samples.length === 0) {
    console.warn(`No samples collected for workflow ${workflowId}`);
    return null;
  }

  const memoryValues = session.samples.map(s => s.memory_mb);
  const cpuValues = session.samples.map(s => s.cpu_percent);

  const peakMemoryMB = Math.max(...memoryValues);
  const avgMemoryMB = memoryValues.reduce((a, b) => a + b, 0) / memoryValues.length;
  const minMemoryMB = Math.min(...memoryValues);

  const avgCPUPercent = cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length;
  const maxCPUPercent = Math.max(...cpuValues);
  const minCPUPercent = Math.min(...cpuValues);

  const stats = {
    workflow_id: workflowId,
    workflow_execution_id: options.workflowExecutionId || null,
    start_time: new Date(session.startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    duration_ms: durationMs,
    peak_memory_mb: parseFloat(peakMemoryMB.toFixed(2)),
    avg_memory_mb: parseFloat(avgMemoryMB.toFixed(2)),
    min_memory_mb: parseFloat(minMemoryMB.toFixed(2)),
    avg_cpu_percent: parseFloat(avgCPUPercent.toFixed(2)),
    max_cpu_percent: parseFloat(maxCPUPercent.toFixed(2)),
    min_cpu_percent: parseFloat(minCPUPercent.toFixed(2)),
    sample_count: session.samples.length,
  };

  // Store to PostgreSQL
  try {
    await _storeStats(stats);
  } catch (err) {
    console.error('Failed to store resource usage stats:', err.message);
    // Return stats even if storage fails
  }

  return stats;
}

/**
 * Store resource usage statistics to PostgreSQL
 * @private
 */
async function _storeStats(stats) {
  const insertSQL = `
    INSERT INTO monitoring.resource_usage (
      workflow_id,
      workflow_execution_id,
      start_time,
      end_time,
      duration_ms,
      peak_memory_mb,
      avg_memory_mb,
      min_memory_mb,
      avg_cpu_percent,
      max_cpu_percent,
      min_cpu_percent,
      sample_count
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
    RETURNING id
  `;

  const values = [
    stats.workflow_id,
    stats.workflow_execution_id,
    stats.start_time,
    stats.end_time,
    stats.duration_ms,
    stats.peak_memory_mb,
    stats.avg_memory_mb,
    stats.min_memory_mb,
    stats.avg_cpu_percent,
    stats.max_cpu_percent,
    stats.min_cpu_percent,
    stats.sample_count,
  ];

  await pool.query(insertSQL, values);
}

/**
 * Get resource usage history for a workflow
 *
 * @param {string} workflowId - Workflow identifier
 * @param {Object} options - Optional filters
 * @param {number} options.limit - Maximum number of records to return (default: 100)
 * @returns {Promise<Array>} Resource usage records
 *
 * @example
 *   const history = await getResourceHistory('wf-12345');
 *   const recent = await getResourceHistory('wf-12345', { limit: 10 });
 */
async function getResourceHistory(workflowId, options = {}) {
  const limit = options.limit || 100;

  const querySQL = `
    SELECT
      id,
      workflow_id,
      workflow_execution_id,
      start_time,
      end_time,
      duration_ms,
      peak_memory_mb,
      avg_memory_mb,
      min_memory_mb,
      avg_cpu_percent,
      max_cpu_percent,
      min_cpu_percent,
      sample_count,
      created_at
    FROM monitoring.resource_usage
    WHERE workflow_id = $1
    ORDER BY created_at DESC
    LIMIT $2
  `;

  const result = await pool.query(querySQL, [workflowId, limit]);
  return result.rows;
}

/**
 * Get resource usage statistics by workflow execution ID
 *
 * @param {number} workflowExecutionId - Workflow execution ID
 * @returns {Promise<Object|null>} Resource usage record or null if not found
 */
async function getResourceByExecutionId(workflowExecutionId) {
  const querySQL = `
    SELECT
      id,
      workflow_id,
      workflow_execution_id,
      start_time,
      end_time,
      duration_ms,
      peak_memory_mb,
      avg_memory_mb,
      min_memory_mb,
      avg_cpu_percent,
      max_cpu_percent,
      min_cpu_percent,
      sample_count,
      created_at
    FROM monitoring.resource_usage
    WHERE workflow_execution_id = $1
    ORDER BY created_at DESC
    LIMIT 1
  `;

  const result = await pool.query(querySQL, [workflowExecutionId]);
  return result.rows.length > 0 ? result.rows[0] : null;
}

/**
 * Get aggregated resource usage statistics across all workflows
 *
 * @param {Object} options - Optional filters
 * @param {string} options.since - ISO timestamp to filter records after (e.g., '2026-07-01T00:00:00Z')
 * @param {number} options.limit - Maximum number of records to return (default: 1000)
 * @returns {Promise<Object>} Aggregated statistics
 *
 * @example
 *   const stats = await getAggregatedStats();
 *   const recentStats = await getAggregatedStats({ since: '2026-07-01T00:00:00Z' });
 */
async function getAggregatedStats(options = {}) {
  const limit = options.limit || 1000;
  let whereClause = '';
  const queryParams = [];

  if (options.since) {
    whereClause = 'WHERE created_at >= $1';
    queryParams.push(options.since);
  }

  const querySQL = `
    SELECT
      COUNT(*) as total_workflows,
      AVG(duration_ms) as avg_duration_ms,
      MAX(duration_ms) as max_duration_ms,
      MIN(duration_ms) as min_duration_ms,
      AVG(peak_memory_mb) as avg_peak_memory_mb,
      MAX(peak_memory_mb) as max_peak_memory_mb,
      AVG(avg_cpu_percent) as avg_cpu_percent,
      MAX(max_cpu_percent) as max_cpu_percent
    FROM (
      SELECT * FROM monitoring.resource_usage
      ${whereClause}
      ORDER BY created_at DESC
      LIMIT ${limit}
    ) sub
  `;

  const result = await pool.query(querySQL, queryParams);
  return result.rows[0];
}

module.exports = {
  startMonitoring,
  stopMonitoring,
  getResourceHistory,
  getResourceByExecutionId,
  getAggregatedStats,
  pool, // Export for testing
};
