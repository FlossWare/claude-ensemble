/**
 * Real-time PostgreSQL → Neo4j Sync
 *
 * Syncs workflow execution data to Neo4j immediately upon completion.
 * Best-effort: logs errors but doesn't fail workflows.
 *
 * Usage:
 *   const { syncWorkflowToNeo4j } = require('./neo4j-realtime-sync');
 *   await syncWorkflowToNeo4j(executionId);  // Fire and forget
 */

const neo4j = require('neo4j-driver');
const { Pool } = require('pg');

// Neo4j connection (reused across calls)
let driver = null;

function getDriver() {
  if (!driver) {
    const uri = process.env.NEO4J_URI || 'bolt://aio-01:7687';
    const user = process.env.NEO4J_USER || 'neo4j';
    const password = process.env.NEO4J_PASSWORD || 'neo4j';

    driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
  }
  return driver;
}

// PostgreSQL connection pool
const pgPool = new Pool({
  host: process.env.POSTGRES_HOST || 'aio-01',
  port: parseInt(process.env.POSTGRES_PORT || '5433'),
  database: process.env.POSTGRES_DB || 'learning',
  user: process.env.POSTGRES_USER || 'claude',
  max: 5
});

/**
 * Sync a single workflow execution to Neo4j
 *
 * @param {number} executionId - Workflow execution ID from PostgreSQL
 * @returns {Promise<boolean>} True if synced successfully, false if failed (logged)
 */
async function syncWorkflowToNeo4j(executionId) {
  const session = getDriver().session();

  try {
    // 1. Fetch workflow execution from PostgreSQL
    const execResult = await pgPool.query(
      'SELECT * FROM workflow.executions WHERE id = $1',
      [executionId]
    );

    if (execResult.rows.length === 0) {
      console.warn(`⚠️  Workflow execution ${executionId} not found in PostgreSQL`);
      return false;
    }

    const execution = execResult.rows[0];

    // 2. Create/update Workflow node in Neo4j
    await session.run(`
      MERGE (w:Workflow {execution_id: $execution_id})
      SET w.workflow_name = $workflow_name,
          w.task_description = $task_description,
          w.quality_score = $quality_score,
          w.duration_ms = $duration_ms,
          w.outcome = $outcome,
          w.total_workers = $total_workers,
          w.created_at = datetime($created_at),
          w.synced_at = datetime()
    `, {
      execution_id: neo4j.int(execution.id),
      workflow_name: execution.workflow_name || 'unknown',
      task_description: execution.task_description || '',
      quality_score: execution.quality_score || 0.0,
      duration_ms: neo4j.int(execution.total_duration_ms || 0),
      outcome: execution.outcome || 'unknown',
      total_workers: neo4j.int(execution.total_workers || 0),
      created_at: execution.created_at ? execution.created_at.toISOString() : new Date().toISOString()
    });

    // 3. Link to Topic if exists in metadata
    const metadata = execution.metadata || {};
    if (metadata.topic) {
      await session.run(`
        MATCH (w:Workflow {execution_id: $execution_id})
        MERGE (t:Topic {name: $topic})
        MERGE (w)-[:HAS_TOPIC]->(t)
      `, {
        execution_id: neo4j.int(execution.id),
        topic: metadata.topic
      });

      console.log(`  ✓ Linked workflow ${executionId} to topic "${metadata.topic}"`);
    }

    // 4. Link to Model if we have worker results
    const workerResult = await pgPool.query(
      'SELECT model FROM workflow.worker_results WHERE workflow_execution_id = $1 LIMIT 1',
      [executionId]
    );

    if (workerResult.rows.length > 0) {
      const model = workerResult.rows[0].model;

      await session.run(`
        MATCH (w:Workflow {execution_id: $execution_id})
        MERGE (m:Model {name: $model})
        MERGE (w)-[:USES_MODEL]->(m)
      `, {
        execution_id: neo4j.int(execution.id),
        model: model
      });

      console.log(`  ✓ Linked workflow ${executionId} to model "${model}"`);
    }

    console.log(`✅ Synced workflow ${executionId} to Neo4j (${execution.workflow_name})`);
    return true;

  } catch (error) {
    // Best effort - log but don't fail
    console.error(`⚠️  Neo4j sync failed for workflow ${executionId}:`, error.message);
    return false;
  } finally {
    await session.close();
  }
}

/**
 * Sync multiple workflows in batch (for backfill/catch-up)
 *
 * @param {number[]} executionIds - Array of execution IDs
 * @returns {Promise<{synced: number, failed: number}>}
 */
async function syncBatch(executionIds) {
  const results = { synced: 0, failed: 0 };

  for (const id of executionIds) {
    const success = await syncWorkflowToNeo4j(id);
    if (success) {
      results.synced++;
    } else {
      results.failed++;
    }
  }

  return results;
}

/**
 * Close connections (call on shutdown)
 */
async function closeConnections() {
  if (driver) {
    await driver.close();
    driver = null;
  }
  await pgPool.end();
}

module.exports = {
  syncWorkflowToNeo4j,
  syncBatch,
  closeConnections
};
