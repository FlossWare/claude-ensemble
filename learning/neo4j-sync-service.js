#!/usr/bin/env node

/**
 * Neo4jSyncService
 *
 * Syncs workflow execution data from PostgreSQL to Neo4j graph database.
 * Uses the new schema with Workflow, Phase, Worker, Learning, Model,
 * and ArbiterDecision nodes with typed relationships.
 *
 * Features:
 *   - Connection management with health checks and reconnection
 *   - syncWorkflowExecution(executionId) -- full sync of a single execution
 *   - createSimilarityLinks(threshold) -- vector-based RELATED_TO edges between Learnings
 *   - Batch operations for bulk sync
 *   - Exponential-backoff retries on transient failures
 *   - Configurable via NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars
 *
 * Integration:
 *   Called from workflow-completion-hook.js (lines 88-93) after PostgreSQL storage.
 *   Non-blocking: Neo4j failures never break the workflow pipeline.
 *
 * Usage:
 *   const { Neo4jSyncService } = require('./neo4j-sync-service.js');
 *   const svc = new Neo4jSyncService();
 *   await svc.initialize();                          // schema + indexes
 *   await svc.syncWorkflowExecution(42);             // sync one execution
 *   await svc.syncUnsynced();                        // bulk catch-up
 *   await svc.createSimilarityLinks(0.75);           // learning relationships
 *   await svc.close();
 */

const neo4j = require('neo4j-driver');
const { Pool } = require('pg');

// ---------------------------------------------------------------------------
// Cypher templates -- match the provided schema exactly
// ---------------------------------------------------------------------------

const CYPHER = {
  // Node creation
  createWorkflow: `
    CREATE (w:Workflow {
      workflow_id: $workflow_id,
      workflow_name: $workflow_name,
      task_description: $task_description,
      total_workers: $total_workers,
      total_duration_ms: $total_duration_ms,
      outcome: $outcome,
      metadata: $metadata,
      created_at: datetime(),
      pg_execution_id: $pg_execution_id
    })
    RETURN w
  `,

  mergeWorkflow: `
    MERGE (w:Workflow {workflow_id: $workflow_id})
    ON CREATE SET
      w.workflow_name = $workflow_name,
      w.task_description = $task_description,
      w.total_workers = $total_workers,
      w.total_duration_ms = $total_duration_ms,
      w.outcome = $outcome,
      w.metadata = $metadata,
      w.created_at = datetime(),
      w.pg_execution_id = $pg_execution_id
    ON MATCH SET
      w.workflow_name = $workflow_name,
      w.task_description = $task_description,
      w.total_workers = $total_workers,
      w.total_duration_ms = $total_duration_ms,
      w.outcome = $outcome,
      w.metadata = $metadata,
      w.pg_execution_id = $pg_execution_id
    RETURN w
  `,

  createPhase: `
    MATCH (w:Workflow {workflow_id: $workflow_id})
    MERGE (p:Phase {pg_phase_id: $pg_phase_id})
    ON CREATE SET
      p.phase_name = $phase_name,
      p.phase_order = $phase_order,
      p.duration_ms = $duration_ms,
      p.outcome = $outcome,
      p.metadata = $metadata,
      p.created_at = datetime()
    ON MATCH SET
      p.phase_name = $phase_name,
      p.phase_order = $phase_order,
      p.duration_ms = $duration_ms,
      p.outcome = $outcome,
      p.metadata = $metadata
    MERGE (w)-[:CONTAINS {phase_order: $phase_order}]->(p)
    WITH w, p
    OPTIONAL MATCH (prev:Phase)<-[:CONTAINS]-(w)
    WHERE prev.phase_order = $phase_order - 1
    FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
      MERGE (prev)-[:NEXT_PHASE]->(p)
    )
    RETURN p
  `,

  createWorker: `
    MATCH (w:Workflow {workflow_id: $workflow_id})
    MERGE (wr:Worker {pg_worker_result_id: $pg_worker_result_id})
    ON CREATE SET
      wr.worker_id = $worker_id,
      wr.model = $model,
      wr.task_assigned = $task_assigned,
      wr.confidence = $confidence,
      wr.duration_ms = $duration_ms,
      wr.input_tokens = $input_tokens,
      wr.output_tokens = $output_tokens,
      wr.cost_usd = $cost_usd,
      wr.outcome = $outcome,
      wr.metadata = $metadata,
      wr.created_at = datetime()
    ON MATCH SET
      wr.worker_id = $worker_id,
      wr.model = $model,
      wr.task_assigned = $task_assigned,
      wr.confidence = $confidence,
      wr.duration_ms = $duration_ms,
      wr.input_tokens = $input_tokens,
      wr.output_tokens = $output_tokens,
      wr.cost_usd = $cost_usd,
      wr.outcome = $outcome,
      wr.metadata = $metadata
    MERGE (wr)-[:EXECUTES]->(w)
    WITH wr
    MERGE (m:Model {name: $model})
    ON CREATE SET m.first_seen = datetime(), m.total_executions = 1
    ON MATCH SET m.total_executions = m.total_executions + 1
    MERGE (wr)-[:USES_MODEL]->(m)
    RETURN wr
  `,

  createArbiterDecision: `
    MATCH (w:Workflow {workflow_id: $workflow_id})
    MERGE (a:ArbiterDecision {pg_arbiter_decision_id: $pg_arbiter_decision_id})
    ON CREATE SET
      a.arbiter_model = $arbiter_model,
      a.decision = $decision,
      a.reasoning = $reasoning,
      a.confidence = $confidence,
      a.duration_ms = $duration_ms,
      a.input_tokens = $input_tokens,
      a.output_tokens = $output_tokens,
      a.cost_usd = $cost_usd,
      a.metadata = $metadata,
      a.created_at = datetime()
    ON MATCH SET
      a.arbiter_model = $arbiter_model,
      a.decision = $decision,
      a.reasoning = $reasoning,
      a.confidence = $confidence,
      a.duration_ms = $duration_ms,
      a.input_tokens = $input_tokens,
      a.output_tokens = $output_tokens,
      a.cost_usd = $cost_usd,
      a.metadata = $metadata
    MERGE (w)-[:ARBITRATED_BY]->(a)
    WITH a
    MERGE (m:Model {name: $arbiter_model})
    ON CREATE SET m.first_seen = datetime(), m.total_executions = 1
    ON MATCH SET m.total_executions = m.total_executions + 1
    MERGE (a)-[:ARBITER_USES_MODEL]->(m)
    RETURN a
  `,

  createEvaluatedRelationship: `
    MATCH (a:ArbiterDecision {pg_arbiter_decision_id: $pg_arbiter_decision_id})
    MATCH (wr:Worker {pg_worker_result_id: $pg_worker_result_id})
    MERGE (a)-[r:EVALUATED]->(wr)
    ON CREATE SET r.was_selected = $was_selected
    ON MATCH SET r.was_selected = $was_selected
  `,

  createLearning: `
    MATCH (w:Workflow {workflow_id: $workflow_id})
    MERGE (l:Learning {pg_learning_id: $pg_learning_id})
    ON CREATE SET
      l.learning_type = $learning_type,
      l.description = $description,
      l.actionable_insight = $actionable_insight,
      l.importance = $importance,
      l.embedding = $embedding,
      l.metadata = $metadata,
      l.created_at = datetime()
    ON MATCH SET
      l.learning_type = $learning_type,
      l.description = $description,
      l.actionable_insight = $actionable_insight,
      l.importance = $importance,
      l.embedding = $embedding,
      l.metadata = $metadata
    MERGE (w)-[:PRODUCED]->(l)
    RETURN l
  `,

  // Similarity link creation via vector index
  createRelatedTo: `
    CALL db.index.vector.queryNodes('learning_embedding_index', $top_k, $query_embedding)
    YIELD node AS candidate, score
    WITH candidate, score
    WHERE score >= $similarity_threshold
    MATCH (source:Learning {pg_learning_id: $source_learning_id})
    WHERE source <> candidate
    MERGE (source)-[r:RELATED_TO]->(candidate)
    ON CREATE SET r.similarity_score = score, r.method = 'cosine', r.created_at = datetime()
    ON MATCH SET r.similarity_score = score
    RETURN source.pg_learning_id AS source_id, candidate.pg_learning_id AS target_id, score
  `,

  // Utility queries
  workflowExists: `
    MATCH (w:Workflow {pg_execution_id: $pg_execution_id})
    RETURN w.workflow_id AS workflow_id
  `,

  deleteWorkflowGraph: `
    MATCH (w:Workflow {workflow_id: $workflow_id})
    OPTIONAL MATCH (w)-[:CONTAINS]->(p:Phase)
    OPTIONAL MATCH (w)<-[:EXECUTES]-(wr:Worker)
    OPTIONAL MATCH (w)-[:ARBITRATED_BY]->(a:ArbiterDecision)
    OPTIONAL MATCH (w)-[:PRODUCED]->(l:Learning)
    DETACH DELETE p, wr, a, l, w
  `,
};

// ---------------------------------------------------------------------------
// Schema DDL -- constraints and indexes to run on initialize()
// ---------------------------------------------------------------------------

const SCHEMA_STATEMENTS = [
  // Constraints
  'CREATE CONSTRAINT workflow_id_unique IF NOT EXISTS FOR (w:Workflow) REQUIRE w.workflow_id IS UNIQUE',
  'CREATE CONSTRAINT model_name_unique IF NOT EXISTS FOR (m:Model) REQUIRE m.name IS UNIQUE',

  // Workflow indexes
  'CREATE INDEX workflow_name_index IF NOT EXISTS FOR (w:Workflow) ON (w.workflow_name)',
  'CREATE INDEX workflow_outcome_index IF NOT EXISTS FOR (w:Workflow) ON (w.outcome)',
  'CREATE INDEX workflow_created_at_index IF NOT EXISTS FOR (w:Workflow) ON (w.created_at)',
  'CREATE INDEX workflow_pg_id_index IF NOT EXISTS FOR (w:Workflow) ON (w.pg_execution_id)',

  // Phase indexes
  'CREATE INDEX phase_name_index IF NOT EXISTS FOR (p:Phase) ON (p.phase_name)',
  'CREATE INDEX phase_outcome_index IF NOT EXISTS FOR (p:Phase) ON (p.outcome)',
  'CREATE INDEX phase_pg_id_index IF NOT EXISTS FOR (p:Phase) ON (p.pg_phase_id)',

  // Worker indexes
  'CREATE INDEX worker_model_index IF NOT EXISTS FOR (wr:Worker) ON (wr.model)',
  'CREATE INDEX worker_outcome_index IF NOT EXISTS FOR (wr:Worker) ON (wr.outcome)',
  'CREATE INDEX worker_confidence_index IF NOT EXISTS FOR (wr:Worker) ON (wr.confidence)',
  'CREATE INDEX worker_pg_id_index IF NOT EXISTS FOR (wr:Worker) ON (wr.pg_worker_result_id)',

  // Learning indexes
  'CREATE INDEX learning_type_index IF NOT EXISTS FOR (l:Learning) ON (l.learning_type)',
  'CREATE INDEX learning_importance_index IF NOT EXISTS FOR (l:Learning) ON (l.importance)',
  'CREATE INDEX learning_pg_id_index IF NOT EXISTS FOR (l:Learning) ON (l.pg_learning_id)',

  // ArbiterDecision indexes
  'CREATE INDEX arbiter_model_index IF NOT EXISTS FOR (a:ArbiterDecision) ON (a.arbiter_model)',
  'CREATE INDEX arbiter_confidence_index IF NOT EXISTS FOR (a:ArbiterDecision) ON (a.confidence)',
  'CREATE INDEX arbiter_decision_index IF NOT EXISTS FOR (a:ArbiterDecision) ON (a.decision)',
  'CREATE INDEX arbiter_pg_id_index IF NOT EXISTS FOR (a:ArbiterDecision) ON (a.pg_arbiter_decision_id)',
];

// Vector index must be created separately (different syntax in some Neo4j versions)
const VECTOR_INDEX_STATEMENT =
  "CREATE VECTOR INDEX learning_embedding_index IF NOT EXISTS FOR (l:Learning) ON (l.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}";

// ---------------------------------------------------------------------------
// Neo4jSyncService
// ---------------------------------------------------------------------------

class Neo4jSyncService {
  /**
   * @param {Object} config
   * @param {string} config.neo4jUri        - bolt:// URI (default: NEO4J_URI env or bolt://laptop-01:7687)
   * @param {string} config.neo4jUser       - Neo4j username (default: NEO4J_USER env or 'neo4j')
   * @param {string} config.neo4jPassword   - Neo4j password (default: NEO4J_PASSWORD env)
   * @param {Object} config.pg              - pg.Pool overrides (host, database, user, ...)
   * @param {number} config.maxRetries      - Max retries on transient failure (default: 3)
   * @param {number} config.retryBaseMs     - Base backoff in ms (default: 1000)
   * @param {number} config.batchSize       - Batch size for bulk operations (default: 50)
   */
  constructor(config = {}) {
    // Neo4j
    this.neo4jUri = config.neo4jUri || process.env.NEO4J_URI || 'bolt://laptop-01:7687';
    this.neo4jUser = config.neo4jUser || process.env.NEO4J_USER || 'neo4j';
    this.neo4jPassword = config.neo4jPassword || process.env.NEO4J_PASSWORD || '';
    if (!this.neo4jPassword) {
      console.warn('[Neo4jSyncService] WARNING: No Neo4j password configured (NEO4J_PASSWORD not set)');
    }

    this.driver = null;
    this.neo4jAvailable = false;

    // PostgreSQL
    this.pgPool = new Pool({
      host: config.pg?.host || '/var/run/postgresql',
      database: config.pg?.database || 'learning',
      user: config.pg?.user || process.env.USER,
      max: config.pg?.max || 5,
      idleTimeoutMillis: config.pg?.idleTimeoutMillis || 30000,
      ...config.pg,
    });

    // Retry / batch config
    this.maxRetries = config.maxRetries ?? 3;
    this.retryBaseMs = config.retryBaseMs ?? 1000;
    this.batchSize = config.batchSize ?? 50;
  }

  // =========================================================================
  // Connection management
  // =========================================================================

  /**
   * Connect to Neo4j, verify connectivity, optionally initialize schema.
   * Safe to call multiple times -- idempotent.
   */
  async connect() {
    if (this.driver && this.neo4jAvailable) {
      return true;
    }

    try {
      this.driver = neo4j.driver(
        this.neo4jUri,
        neo4j.auth.basic(this.neo4jUser, this.neo4jPassword),
        {
          maxConnectionPoolSize: 10,
          connectionAcquisitionTimeout: 5000,
          connectionTimeout: 5000,
        }
      );

      // Verify connectivity
      await this.driver.verifyConnectivity();
      this.neo4jAvailable = true;
      console.log(`[Neo4jSyncService] Connected to ${this.neo4jUri}`);
      return true;

    } catch (err) {
      console.warn(`[Neo4jSyncService] Neo4j unavailable (${this.neo4jUri}): ${err.message}`);
      this.neo4jAvailable = false;
      if (this.driver) {
        try { await this.driver.close(); } catch (_) { /* ignore */ }
        this.driver = null;
      }
      return false;
    }
  }

  /**
   * Close Neo4j driver and PostgreSQL pool.
   */
  async close() {
    if (this.driver) {
      try { await this.driver.close(); } catch (_) { /* ignore */ }
      this.driver = null;
    }
    this.neo4jAvailable = false;

    if (this.pgPool) {
      await this.pgPool.end();
    }
  }

  /**
   * Health check -- returns { neo4j: bool, postgres: bool }.
   */
  async healthCheck() {
    const result = { neo4j: false, postgres: false };

    // PostgreSQL
    try {
      const client = await this.pgPool.connect();
      try {
        await client.query('SELECT 1');
        result.postgres = true;
      } finally {
        client.release();
      }
    } catch (_) { /* leave false */ }

    // Neo4j
    try {
      if (!this.driver) await this.connect();
      if (this.driver) {
        const session = this.driver.session();
        try {
          await session.run('RETURN 1');
          result.neo4j = true;
        } finally {
          await session.close();
        }
      }
    } catch (_) {
      this.neo4jAvailable = false;
    }

    return result;
  }

  // =========================================================================
  // Schema initialization
  // =========================================================================

  /**
   * Create all constraints, indexes, and the vector index in Neo4j.
   * Idempotent (IF NOT EXISTS).
   */
  async initialize() {
    const connected = await this.connect();
    if (!connected) {
      console.warn('[Neo4jSyncService] Cannot initialize schema -- Neo4j unavailable');
      return false;
    }

    const session = this.driver.session();
    try {
      // Standard indexes and constraints
      for (const stmt of SCHEMA_STATEMENTS) {
        try {
          await session.run(stmt);
        } catch (err) {
          // Some Neo4j versions throw on IF NOT EXISTS when it already exists -- safe to ignore
          if (!err.message.includes('already exists') && !err.message.includes('equivalent')) {
            console.warn(`[Neo4jSyncService] Schema warning: ${err.message}`);
          }
        }
      }

      // Vector index (separate because syntax varies by version)
      try {
        await session.run(VECTOR_INDEX_STATEMENT);
      } catch (err) {
        if (!err.message.includes('already exists') && !err.message.includes('equivalent')) {
          console.warn(`[Neo4jSyncService] Vector index warning: ${err.message}`);
        }
      }

      console.log('[Neo4jSyncService] Schema initialized');
      return true;

    } finally {
      await session.close();
    }
  }

  // =========================================================================
  // Core sync: single workflow execution
  // =========================================================================

  /**
   * Sync a single workflow execution (and all related entities) from
   * PostgreSQL to Neo4j.
   *
   * Creates nodes:  Workflow, Phase(s), Worker(s), ArbiterDecision(s),
   *                 Learning(s), Model(s)
   * Creates edges:  CONTAINS, NEXT_PHASE, EXECUTES, USES_MODEL,
   *                 ARBITRATED_BY, ARBITER_USES_MODEL, EVALUATED,
   *                 PRODUCED
   *
   * @param {number} executionId - workflow.executions.id in PostgreSQL
   * @returns {Promise<Object>} { status, executionId, nodesCreated }
   */
  async syncWorkflowExecution(executionId) {
    // Fetch everything from PostgreSQL first
    const data = await this._fetchFullExecution(executionId);
    if (!data.execution) {
      throw new Error(`Execution ${executionId} not found in PostgreSQL`);
    }

    // Ensure Neo4j is reachable
    const connected = await this.connect();
    if (!connected) {
      console.log(`[Neo4jSyncService] Neo4j unavailable, execution ${executionId} not synced`);
      return { status: 'skipped', executionId, reason: 'neo4j_unavailable' };
    }

    return await this._withRetry(async () => {
      const session = this.driver.session();
      try {
        const counters = { workflows: 0, phases: 0, workers: 0, arbiters: 0, learnings: 0 };

        await session.executeWrite(async (tx) => {
          const exec = data.execution;

          // 1. Workflow node (MERGE to be idempotent on re-sync)
          await tx.run(CYPHER.mergeWorkflow, {
            workflow_id: exec.workflow_id,
            workflow_name: exec.workflow_name,
            task_description: exec.task_description || '',
            total_workers: neo4j.int(exec.total_workers || 0),
            total_duration_ms: neo4j.int(exec.total_duration_ms || 0),
            outcome: exec.outcome || 'success',
            metadata: JSON.stringify(exec.metadata || {}),
            pg_execution_id: neo4j.int(exec.id),
          });
          counters.workflows = 1;

          // 2. Phases (ordered, with NEXT_PHASE chain)
          //    Sort by phase_order to ensure NEXT_PHASE links are correct.
          const phases = (data.phases || []).sort(
            (a, b) => (a.phase_order || 0) - (b.phase_order || 0)
          );
          for (const phase of phases) {
            await tx.run(CYPHER.createPhase, {
              workflow_id: exec.workflow_id,
              phase_name: phase.phase_name || '',
              phase_order: neo4j.int(phase.phase_order ?? 0),
              duration_ms: neo4j.int(phase.duration_ms || 0),
              outcome: phase.outcome || 'success',
              metadata: JSON.stringify(phase.metadata || {}),
              pg_phase_id: neo4j.int(phase.id),
            });
            counters.phases++;
          }

          // 3. Workers
          for (const worker of data.workers || []) {
            await tx.run(CYPHER.createWorker, {
              workflow_id: exec.workflow_id,
              worker_id: worker.worker_id || `worker-${worker.id}`,
              model: worker.model || 'unknown',
              task_assigned: worker.task_assigned || '',
              confidence: worker.confidence ?? 0.0,
              duration_ms: neo4j.int(worker.duration_ms || 0),
              input_tokens: neo4j.int(worker.input_tokens || 0),
              output_tokens: neo4j.int(worker.output_tokens || 0),
              cost_usd: worker.cost_usd ?? 0.0,
              outcome: worker.outcome || 'success',
              metadata: JSON.stringify(worker.metadata || {}),
              pg_worker_result_id: neo4j.int(worker.id),
            });
            counters.workers++;
          }

          // 4. Arbiter decisions
          for (const arbiter of data.arbiters || []) {
            await tx.run(CYPHER.createArbiterDecision, {
              workflow_id: exec.workflow_id,
              arbiter_model: arbiter.arbiter_model || arbiter.model || 'unknown',
              decision: arbiter.decision || '',
              reasoning: arbiter.reasoning || '',
              confidence: arbiter.confidence ?? 0.0,
              duration_ms: neo4j.int(arbiter.duration_ms || 0),
              input_tokens: neo4j.int(arbiter.input_tokens || 0),
              output_tokens: neo4j.int(arbiter.output_tokens || 0),
              cost_usd: arbiter.cost_usd ?? 0.0,
              metadata: JSON.stringify(arbiter.metadata || {}),
              pg_arbiter_decision_id: neo4j.int(arbiter.id),
            });
            counters.arbiters++;

            // EVALUATED relationships (arbiter -> workers it evaluated)
            // If selected_worker_id exists, that worker gets was_selected: true
            for (const worker of data.workers || []) {
              const wasSelected = arbiter.selected_worker_id === worker.id;
              await tx.run(CYPHER.createEvaluatedRelationship, {
                pg_arbiter_decision_id: neo4j.int(arbiter.id),
                pg_worker_result_id: neo4j.int(worker.id),
                was_selected: wasSelected,
              });
            }
          }

          // 5. Learnings
          for (const learning of data.learnings || []) {
            // Parse embedding from PG vector string if present
            let embedding = null;
            if (learning.learning_embedding) {
              embedding = this._parseEmbedding(learning.learning_embedding);
            }

            await tx.run(CYPHER.createLearning, {
              workflow_id: exec.workflow_id,
              learning_type: learning.learning_type || 'pattern',
              description: learning.description || '',
              actionable_insight: learning.actionable_insight || '',
              importance: learning.importance ?? 0.5,
              embedding: embedding,
              metadata: JSON.stringify(learning.metadata || {}),
              pg_learning_id: neo4j.int(learning.id),
            });
            counters.learnings++;
          }
        });

        console.log(
          `[Neo4jSyncService] Synced execution ${executionId}: ` +
          `${counters.workflows}W ${counters.phases}P ${counters.workers}Wr ` +
          `${counters.arbiters}A ${counters.learnings}L`
        );

        return { status: 'synced', executionId, nodesCreated: counters };

      } finally {
        await session.close();
      }
    }, `syncWorkflowExecution(${executionId})`);
  }

  // =========================================================================
  // Similarity links between Learnings
  // =========================================================================

  /**
   * For every Learning node that has an embedding, query the Neo4j vector
   * index and create RELATED_TO edges to other Learnings above the
   * similarity threshold.
   *
   * @param {number} threshold - Cosine similarity threshold (0.0 - 1.0, default 0.75)
   * @param {number} topK      - Max neighbours per learning (default 10)
   * @returns {Promise<Object>} { linksCreated, learningsProcessed }
   */
  async createSimilarityLinks(threshold = 0.75, topK = 10) {
    const connected = await this.connect();
    if (!connected) {
      console.warn('[Neo4jSyncService] Neo4j unavailable, cannot create similarity links');
      return { linksCreated: 0, learningsProcessed: 0 };
    }

    return await this._withRetry(async () => {
      const session = this.driver.session();
      try {
        // Step 1: get all learnings that have an embedding
        const allLearnings = await session.run(`
          MATCH (l:Learning)
          WHERE l.embedding IS NOT NULL AND size(l.embedding) = 768
          RETURN l.pg_learning_id AS pg_id, l.embedding AS embedding
        `);

        const records = allLearnings.records;
        let linksCreated = 0;

        // Step 2: for each learning, query vector index and create RELATED_TO
        for (const record of records) {
          const pgId = this._toJsNumber(record.get('pg_id'));
          const embedding = record.get('embedding');

          if (!embedding || !Array.isArray(embedding)) continue;

          // Convert to native floats if they are Neo4j Integer/Float wrappers
          const queryEmbedding = embedding.map(v =>
            typeof v === 'number' ? v : neo4j.isInt(v) ? v.toNumber() : parseFloat(v)
          );

          try {
            const result = await session.run(CYPHER.createRelatedTo, {
              top_k: neo4j.int(topK),
              query_embedding: queryEmbedding,
              similarity_threshold: threshold,
              source_learning_id: neo4j.int(pgId),
            });
            linksCreated += result.records.length;
          } catch (err) {
            // Vector index may not be populated yet -- warn and continue
            if (err.message.includes('index') || err.message.includes('vector')) {
              console.warn(`[Neo4jSyncService] Vector index query failed for learning ${pgId}: ${err.message}`);
            } else {
              throw err;
            }
          }
        }

        console.log(
          `[Neo4jSyncService] Similarity links: ${linksCreated} created ` +
          `across ${records.length} learnings (threshold=${threshold})`
        );

        return { linksCreated, learningsProcessed: records.length };

      } finally {
        await session.close();
      }
    }, 'createSimilarityLinks');
  }

  // =========================================================================
  // Batch operations
  // =========================================================================

  /**
   * Sync all unsynced workflow executions from PostgreSQL to Neo4j.
   * Unsynced = exists in PG but not in Neo4j (checked by pg_execution_id).
   *
   * @param {number} limit - Max executions to sync in one call (default: 100)
   * @returns {Promise<Object>} { synced, failed, skipped }
   */
  async syncUnsynced(limit = 100) {
    const connected = await this.connect();
    if (!connected) {
      return { synced: 0, failed: 0, skipped: 0, reason: 'neo4j_unavailable' };
    }

    // Get all pg execution ids already in Neo4j
    const session = this.driver.session();
    let existingIds;
    try {
      const result = await session.run(
        'MATCH (w:Workflow) RETURN w.pg_execution_id AS pg_id'
      );
      existingIds = new Set(
        result.records.map(r => this._toJsNumber(r.get('pg_id')))
      );
    } finally {
      await session.close();
    }

    // Get recent execution ids from PostgreSQL
    const pgResult = await this.pgPool.query(
      'SELECT id FROM workflow.executions ORDER BY id DESC LIMIT $1',
      [limit]
    );

    const toSync = pgResult.rows
      .map(r => r.id)
      .filter(id => !existingIds.has(id));

    if (toSync.length === 0) {
      console.log('[Neo4jSyncService] All executions already synced');
      return { synced: 0, failed: 0, skipped: existingIds.size };
    }

    console.log(`[Neo4jSyncService] Syncing ${toSync.length} unsynced executions...`);

    const stats = { synced: 0, failed: 0, skipped: existingIds.size };

    // Process in batches to avoid overwhelming Neo4j
    for (let i = 0; i < toSync.length; i += this.batchSize) {
      const batch = toSync.slice(i, i + this.batchSize);

      const results = await Promise.allSettled(
        batch.map(id => this.syncWorkflowExecution(id))
      );

      for (const r of results) {
        if (r.status === 'fulfilled' && r.value?.status === 'synced') {
          stats.synced++;
        } else {
          stats.failed++;
          if (r.status === 'rejected') {
            console.warn(`[Neo4jSyncService] Batch sync error: ${r.reason?.message}`);
          }
        }
      }
    }

    console.log(
      `[Neo4jSyncService] Batch sync complete: ` +
      `${stats.synced} synced, ${stats.failed} failed, ${stats.skipped} already existed`
    );

    return stats;
  }

  /**
   * Re-sync a workflow execution by deleting existing Neo4j nodes and
   * re-creating them from PostgreSQL.
   *
   * @param {number} executionId - workflow.executions.id
   * @returns {Promise<Object>} sync result
   */
  async resyncWorkflowExecution(executionId) {
    const connected = await this.connect();
    if (!connected) {
      return { status: 'skipped', executionId, reason: 'neo4j_unavailable' };
    }

    // Find the workflow_id for this execution
    const pgResult = await this.pgPool.query(
      'SELECT workflow_id FROM workflow.executions WHERE id = $1',
      [executionId]
    );

    if (pgResult.rows.length === 0) {
      throw new Error(`Execution ${executionId} not found in PostgreSQL`);
    }

    const workflowId = pgResult.rows[0].workflow_id;

    // Delete existing graph for this workflow
    const session = this.driver.session();
    try {
      await session.executeWrite(async (tx) => {
        await tx.run(CYPHER.deleteWorkflowGraph, { workflow_id: workflowId });
      });
    } finally {
      await session.close();
    }

    // Re-create from PostgreSQL
    return await this.syncWorkflowExecution(executionId);
  }

  // =========================================================================
  // PostgreSQL data fetching
  // =========================================================================

  /**
   * Fetch a complete workflow execution with all related entities from
   * PostgreSQL in a single round-trip where possible.
   *
   * @param {number} executionId
   * @returns {Promise<Object>} { execution, phases, workers, arbiters, learnings }
   */
  async _fetchFullExecution(executionId) {
    const client = await this.pgPool.connect();
    try {
      const [execResult, phasesResult, workersResult, arbitersResult, learningsResult] =
        await Promise.all([
          client.query(
            `SELECT id, workflow_id, workflow_name, task_description,
                    total_workers, total_duration_ms, outcome,
                    task_embedding, metadata, created_at
             FROM workflow.executions WHERE id = $1`,
            [executionId]
          ),
          client.query(
            `SELECT id, workflow_execution_id, phase_name, phase_order,
                    duration_ms, outcome, metadata, created_at
             FROM workflow.phases WHERE workflow_execution_id = $1
             ORDER BY phase_order`,
            [executionId]
          ),
          client.query(
            `SELECT id, workflow_execution_id, worker_id, model,
                    task_assigned, result, confidence, duration_ms,
                    input_tokens, output_tokens, cost_usd, outcome,
                    metadata, created_at
             FROM workflow.worker_results WHERE workflow_execution_id = $1`,
            [executionId]
          ),
          client.query(
            `SELECT id, workflow_execution_id, arbiter_model, model,
                    decision, reasoning, confidence, duration_ms,
                    input_tokens, output_tokens, cost_usd,
                    selected_worker_id, metadata, created_at
             FROM workflow.arbiter_decisions WHERE workflow_execution_id = $1`,
            [executionId]
          ),
          client.query(
            `SELECT id, workflow_execution_id, learning_type,
                    description, actionable_insight, importance,
                    learning_embedding, metadata, created_at
             FROM workflow.learnings WHERE workflow_execution_id = $1`,
            [executionId]
          ),
        ]);

      return {
        execution: execResult.rows[0] || null,
        phases: phasesResult.rows,
        workers: workersResult.rows,
        arbiters: arbitersResult.rows,
        learnings: learningsResult.rows,
      };

    } finally {
      client.release();
    }
  }

  // =========================================================================
  // Retry logic
  // =========================================================================

  /**
   * Execute an async function with exponential-backoff retries on transient
   * Neo4j errors (connection resets, timeouts, leader switches).
   *
   * @param {Function} fn        - async function to execute
   * @param {string}   label     - label for log messages
   * @returns {Promise<*>}       - result of fn()
   */
  async _withRetry(fn, label = 'operation') {
    let lastError;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;

        // Only retry on transient / connection errors
        if (!this._isRetryable(err)) {
          throw err;
        }

        if (attempt < this.maxRetries) {
          const delayMs = this.retryBaseMs * Math.pow(2, attempt);
          const jitter = Math.floor(Math.random() * delayMs * 0.3);
          const totalDelay = delayMs + jitter;

          console.warn(
            `[Neo4jSyncService] ${label} failed (attempt ${attempt + 1}/${this.maxRetries + 1}), ` +
            `retrying in ${totalDelay}ms: ${err.message}`
          );

          await this._sleep(totalDelay);

          // Attempt reconnect before retry
          this.neo4jAvailable = false;
          if (this.driver) {
            try { await this.driver.close(); } catch (_) { /* ignore */ }
            this.driver = null;
          }
          await this.connect();
        }
      }
    }

    throw lastError;
  }

  /**
   * Determine if an error is transient and worth retrying.
   */
  _isRetryable(err) {
    if (!err) return false;
    const msg = (err.message || '').toLowerCase();
    const code = err.code || '';

    // Neo4j transient error codes
    if (code.startsWith('Neo.TransientError')) return true;

    // Connection-level errors
    const retryablePatterns = [
      'connection refused',
      'connection reset',
      'econnrefused',
      'econnreset',
      'socket hang up',
      'timeout',
      'pool is closed',
      'session expired',
      'no longer accepting',
      'leader switch',
      'not a leader',
      'database unavailable',
      'failed to connect',
      'connection acquisition',
    ];

    return retryablePatterns.some(pattern => msg.includes(pattern));
  }

  // =========================================================================
  // Helpers
  // =========================================================================

  /**
   * Parse a PostgreSQL vector string (e.g. "[0.1,0.2,0.3]") into a
   * float array suitable for Neo4j vector parameters.
   */
  _parseEmbedding(pgVector) {
    if (!pgVector) return null;

    if (Array.isArray(pgVector)) {
      return pgVector.map(Number);
    }

    if (typeof pgVector === 'string') {
      try {
        // Remove surrounding brackets/braces and parse
        const cleaned = pgVector.replace(/^[\[{]|[\]}]$/g, '');
        return cleaned.split(',').map(v => parseFloat(v.trim()));
      } catch (_) {
        return null;
      }
    }

    return null;
  }

  /**
   * Convert a Neo4j Integer value to a native JS number.
   */
  _toJsNumber(val) {
    if (val === null || val === undefined) return null;
    if (typeof val === 'number') return val;
    if (neo4j.isInt(val)) return val.toNumber();
    return Number(val);
  }

  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

let _instance = null;

/**
 * Get singleton Neo4jSyncService instance.
 * @param {Object} config - Optional config (only used on first call)
 * @returns {Neo4jSyncService}
 */
function getNeo4jSyncService(config = {}) {
  if (!_instance) {
    _instance = new Neo4jSyncService(config);
  }
  return _instance;
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = { Neo4jSyncService, getNeo4jSyncService, CYPHER, SCHEMA_STATEMENTS };

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  const svc = new Neo4jSyncService();

  (async () => {
    try {
      switch (command) {
        case 'init':
          await svc.initialize();
          break;

        case 'sync': {
          const execId = parseInt(args[1], 10);
          if (isNaN(execId)) {
            console.error('Usage: node neo4j-sync-service.js sync <executionId>');
            process.exit(1);
          }
          const result = await svc.syncWorkflowExecution(execId);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'resync': {
          const execId = parseInt(args[1], 10);
          if (isNaN(execId)) {
            console.error('Usage: node neo4j-sync-service.js resync <executionId>');
            process.exit(1);
          }
          const result = await svc.resyncWorkflowExecution(execId);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'sync-all':
        case 'catch-up': {
          const limit = parseInt(args[1], 10) || 100;
          const result = await svc.syncUnsynced(limit);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'similarity': {
          const threshold = parseFloat(args[1]) || 0.75;
          const topK = parseInt(args[2], 10) || 10;
          const result = await svc.createSimilarityLinks(threshold, topK);
          console.log(JSON.stringify(result, null, 2));
          break;
        }

        case 'health': {
          const health = await svc.healthCheck();
          console.log(JSON.stringify(health, null, 2));
          break;
        }

        default:
          console.error('Usage: node neo4j-sync-service.js <command> [args]');
          console.error('');
          console.error('Commands:');
          console.error('  init                          Initialize Neo4j schema (constraints + indexes)');
          console.error('  sync <executionId>            Sync single execution from PG to Neo4j');
          console.error('  resync <executionId>          Delete + re-sync a single execution');
          console.error('  sync-all [limit]              Sync all unsynced executions (default limit: 100)');
          console.error('  similarity [threshold] [topK] Create RELATED_TO edges between Learnings');
          console.error('  health                        Check Neo4j + PostgreSQL connectivity');
          console.error('');
          console.error('Environment:');
          console.error('  NEO4J_URI        bolt:// URI          (default: bolt://laptop-01:7687)');
          console.error('  NEO4J_USER       Neo4j username       (default: neo4j)');
          console.error('  NEO4J_PASSWORD   Neo4j password       (required)');
          process.exit(1);
      }

      await svc.close();

    } catch (err) {
      console.error(`Error: ${err.message}`);
      await svc.close();
      process.exit(1);
    }
  })();
}
