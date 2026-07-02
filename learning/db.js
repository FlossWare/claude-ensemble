/**
 * Database Helper - PostgreSQL Connection Wrapper
 *
 * MIGRATED: This module now delegates to postgres-adapter.js
 * Legacy SQLite code removed in favor of PostgreSQL (aio-01:5433)
 *
 * Provides unified interface for learning system database access.
 * All data now stored in PostgreSQL with ACID guarantees, WAL, and automated backups.
 *
 * Usage (ESM):
 *   import { getDb, query, logOrchestration } from './learning/db.js';
 *
 *   const db = getDb();
 *   const rows = await db.query('SELECT * FROM workflow.execution_summary WHERE model = $1', ['opus']);
 *
 *   await logOrchestration({ execution_id: uuid, workflow: 'code-review', ... });
 */

import {
  getDB,
  getStrategyPerformance,
  getExecutionMonitor,
  getCostTracker,
  getExperienceMemory,
  getWorkflowsLearning,
  OUTCOMES,
} from './postgres-adapter.js';

// ============================================================================
// RE-EXPORT POSTGRES ADAPTER
// ============================================================================

/**
 * Get database instance (PostgreSQL)
 */
export function getDb() {
  return getDB();
}

/**
 * Execute a query (async)
 */
export async function query(sql, params = []) {
  const db = getDB();
  return await db.query(sql, params);
}

/**
 * Execute a query returning single row (async)
 */
export async function queryOne(sql, params = []) {
  const db = getDB();
  return await db.get(sql, params);
}

/**
 * Execute a write statement (async)
 */
export async function exec(sql, params = []) {
  const db = getDB();
  return await db.run(sql, params);
}

/**
 * Run transaction (async)
 */
export async function transaction(fn) {
  const db = getDB();
  return await db.transaction(fn);
}

/**
 * Log orchestration execution
 */
export async function logOrchestration(data) {
  const monitor = getExecutionMonitor();
  return await monitor.logExecution(data);
}

/**
 * Get best model for task type
 */
export async function getBestModel(taskType, timeWindow = 'week') {
  const sp = getStrategyPerformance();
  const allStrategies = await sp.getAllStrategies();

  // Filter and sort by avg_reward
  return allStrategies
    .map(s => ({
      model: s.strategy,
      avg_quality: parseFloat(s.avg_reward),
      sample_count: parseInt(s.successes) + parseInt(s.failures),
      success_rate: parseFloat(s.alpha) / (parseFloat(s.alpha) + parseFloat(s.beta)),
    }))
    .sort((a, b) => b.avg_quality - a.avg_quality);
}

/**
 * Get recent executions
 */
export async function getRecentExecutions(limit = 100) {
  const monitor = getExecutionMonitor();
  return await monitor.getRecentExecutions(limit);
}

/**
 * Get execution by ID
 */
export async function getExecution(executionId) {
  const db = getDB();
  return await db.get(
    'SELECT * FROM workflow.execution_summary WHERE execution_id = $1',
    [executionId]
  );
}

/**
 * Check if database is available
 */
export function isAvailable() {
  try {
    const db = getDB();
    return db !== null;
  } catch (err) {
    return false;
  }
}

/**
 * Get database connection info
 */
export function getDbPath() {
  return `postgresql://${process.env.PGHOST || 'aio-01'}:${process.env.PGPORT || 5433}/${process.env.PGDATABASE || 'learning'}`;
}

/**
 * Close database connection
 */
export async function close() {
  const db = getDB();
  if (db) {
    await db.close();
  }
}

// ============================================================================
// LEGACY API COMPATIBILITY
// ============================================================================

/**
 * @deprecated Use getExecutionMonitor().logExecution() directly
 */
export async function upsertModelPerformance(data) {
  console.warn('[db.js] upsertModelPerformance is deprecated, use getExecutionMonitor().logExecution()');
  return await logOrchestration(data);
}

/**
 * @deprecated Use getStrategyPerformance() directly
 */
export async function upsertParameterTuning(data) {
  console.warn('[db.js] upsertParameterTuning is deprecated, use getStrategyPerformance()');
  return null;
}

/**
 * @deprecated Use getExecutionMonitor() directly
 */
export async function insertRating(data) {
  console.warn('[db.js] insertRating is deprecated, use getExecutionMonitor()');
  return null;
}

/**
 * @deprecated Use getExecutionMonitor() directly
 */
export async function getModelPerformance(model, taskType, timeWindow = 'week') {
  const sp = getStrategyPerformance();
  return await sp.getStrategy(model);
}

/**
 * @deprecated Use getStrategyPerformance() directly
 */
export async function getAllModelPerformance(timeWindow = 'all_time') {
  const sp = getStrategyPerformance();
  return await sp.getAllStrategies();
}

/**
 * @deprecated Use getStrategyPerformance() directly
 */
export async function getOptimalParams(model, taskType) {
  const sp = getStrategyPerformance();
  return await sp.getStrategy(model);
}

/**
 * @deprecated Not implemented in PostgreSQL version
 */
export async function getQualityRatings(executionId) {
  console.warn('[db.js] getQualityRatings not implemented in PostgreSQL version');
  return [];
}

/**
 * @deprecated Not implemented in PostgreSQL version
 */
export async function getQualityTrend(model, taskType, limit = 30) {
  console.warn('[db.js] getQualityTrend not implemented in PostgreSQL version');
  return [];
}

/**
 * @deprecated Not implemented in PostgreSQL version
 */
export async function detectDrift(limit = 20) {
  console.warn('[db.js] detectDrift not implemented in PostgreSQL version');
  return [];
}

/**
 * @deprecated Use getExecutionMonitor() directly
 */
export async function getExecutionsByWorkflow(workflow, limit = 50) {
  const db = getDB();
  return await db.query(
    'SELECT * FROM workflow.execution_summary WHERE workflow = $1 ORDER BY timestamp DESC LIMIT $2',
    [workflow, limit]
  );
}

/**
 * @deprecated Not implemented in PostgreSQL version
 */
export async function getDistinctModels() {
  const db = getDB();
  const rows = await db.query('SELECT DISTINCT model FROM workflow.execution_summary');
  return rows.map(r => r.model);
}

/**
 * @deprecated Not implemented in PostgreSQL version
 */
export async function getDistinctTaskTypes() {
  const db = getDB();
  const rows = await db.query('SELECT DISTINCT task_type FROM workflow.execution_summary');
  return rows.map(r => r.task_type);
}

/**
 * @deprecated Not implemented in PostgreSQL version
 */
export function getMetadata(key) {
  console.warn('[db.js] getMetadata not implemented in PostgreSQL version');
  return null;
}

/**
 * @deprecated Not implemented in PostgreSQL version
 */
export function setMetadata(key, value) {
  console.warn('[db.js] setMetadata not implemented in PostgreSQL version');
  return false;
}

/**
 * @deprecated Schema version always current in PostgreSQL
 */
export function getSchemaVersion() {
  return 3; // PostgreSQL version
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  getDb,
  query,
  queryOne,
  exec,
  transaction,
  logOrchestration,
  getBestModel,
  getRecentExecutions,
  getExecution,
  close,
  isAvailable,
  getDbPath,
  getSchemaVersion,
  // Re-export adapters
  getStrategyPerformance,
  getExecutionMonitor,
  getCostTracker,
  getExperienceMemory,
  getWorkflowsLearning,
  OUTCOMES,
};
