#!/usr/bin/env node

/**
 * Neo4j Workflow Graph Sync
 *
 * Reads from PostgreSQL (workflow.executions, worker_results, arbiter_decisions)
 * and creates Neo4j nodes/relationships for graph analysis.
 *
 * Features:
 * - MERGE operations to avoid duplicates
 * - Non-blocking: Neo4j unavailability doesn't fail workflow
 * - Background job via orchestrator.work_queue
 * - Fallback to PostgreSQL recursive CTEs if Neo4j not deployed
 */

const { Pool } = require('pg');
const neo4j = require('neo4j-driver');

class WorkflowGraphSync {
  constructor(config = {}) {
    this.pgConfig = {
      host: config.pgHost || 'laptop-01',
      port: config.pgPort || 5432,
      database: config.pgDatabase || 'learning',
      user: config.pgUser || 'sfloess',
      ...config.pg
    };

    this.neo4jConfig = {
      uri: config.neo4jUri || 'bolt://laptop-01:7687',
      user: config.neo4jUser || 'neo4j',
      password: config.neo4jPassword || process.env.NEO4J_PASSWORD || '',
      ...config.neo4j
    };

    this.pgPool = null;
    this.neo4jDriver = null;
    this.neo4jAvailable = false;
    this.skipNeo4j = config.skipNeo4j || false;
  }

  async connect() {
    // Always connect to PostgreSQL
    if (!this.pgPool) {
      this.pgPool = new Pool(this.pgConfig);
    }

    // Attempt Neo4j connection (non-blocking)
    if (!this.skipNeo4j && !this.neo4jDriver) {
      try {
        this.neo4jDriver = neo4j.driver(
          this.neo4jConfig.uri,
          neo4j.auth.basic(this.neo4jConfig.user, this.neo4jConfig.password),
          {
            maxConnectionPoolSize: 10,
            connectionAcquisitionTimeout: 5000,
            connectionTimeout: 5000
          }
        );

        // Test connection
        const session = this.neo4jDriver.session();
        await session.run('RETURN 1');
        await session.close();

        this.neo4jAvailable = true;
        console.log('Neo4j connection established');
      } catch (err) {
        console.warn(`Neo4j unavailable: ${err.message}. Using PostgreSQL only.`);
        this.neo4jAvailable = false;
        this.neo4jDriver = null;
      }
    }
  }

  async disconnect() {
    if (this.pgPool) {
      await this.pgPool.end();
      this.pgPool = null;
    }

    if (this.neo4jDriver) {
      await this.neo4jDriver.close();
      this.neo4jDriver = null;
    }
  }

  /**
   * Sync a single workflow execution to Neo4j
   *
   * Creates:
   * - (:Workflow) node
   * - (:Worker) nodes for each worker result
   * - (:Arbiter) node for final decision
   * - (Workflow)-[:EXECUTED_BY]->(Worker)
   * - (Worker)-[:JUDGED_BY]->(Arbiter)
   * - (Workflow)-[:COMPLETED_WITH]->(Arbiter)
   */
  async syncWorkflowExecution(executionId) {
    await this.connect();

    // Fetch workflow execution from PostgreSQL
    const execution = await this.fetchExecution(executionId);
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`);
    }

    // If Neo4j is unavailable, log and continue
    if (!this.neo4jAvailable) {
      console.log(`Neo4j unavailable, execution ${executionId} logged to PostgreSQL only`);
      return { status: 'postgres_only', executionId };
    }

    // Sync to Neo4j
    try {
      const session = this.neo4jDriver.session();

      try {
        await session.executeWrite(async (tx) => {
          // Create Workflow node
          await tx.run(`
            MERGE (w:Workflow {id: $id})
            SET w.name = $name,
                w.startedAt = datetime($startedAt),
                w.completedAt = datetime($completedAt),
                w.status = $status,
                w.metadata = $metadata
            RETURN w
          `, {
            id: execution.id,
            name: execution.workflow_name,
            startedAt: execution.started_at,
            completedAt: execution.completed_at,
            status: execution.status,
            metadata: JSON.stringify(execution.metadata || {})
          });

          // Create Worker nodes and relationships
          for (const worker of execution.workers) {
            await tx.run(`
              MERGE (worker:Worker {id: $workerId})
              SET worker.model = $model,
                  worker.taskType = $taskType,
                  worker.result = $result,
                  worker.qualityScore = $qualityScore,
                  worker.confidence = $confidence,
                  worker.durationMs = $durationMs,
                  worker.timestamp = datetime($timestamp)

              WITH worker
              MATCH (w:Workflow {id: $workflowId})
              MERGE (w)-[r:EXECUTED_BY]->(worker)
              SET r.order = $order,
                  r.parallel = $parallel

              RETURN worker
            `, {
              workerId: worker.id,
              model: worker.model,
              taskType: worker.task_type,
              result: JSON.stringify(worker.result || {}),
              qualityScore: worker.quality_score,
              confidence: worker.confidence || 0.5,
              durationMs: worker.duration_ms,
              timestamp: worker.timestamp,
              workflowId: execution.id,
              order: worker.execution_order || 0,
              parallel: worker.parallel_group !== null
            });
          }

          // Create Arbiter node and relationships
          if (execution.arbiter) {
            await tx.run(`
              MERGE (arbiter:Arbiter {id: $arbiterId})
              SET arbiter.model = $model,
                  arbiter.decision = $decision,
                  arbiter.reasoning = $reasoning,
                  arbiter.confidence = $confidence,
                  arbiter.selectedWorker = $selectedWorker,
                  arbiter.timestamp = datetime($timestamp)

              WITH arbiter
              MATCH (w:Workflow {id: $workflowId})
              MERGE (w)-[r:COMPLETED_WITH]->(arbiter)
              SET r.finalQuality = $finalQuality

              RETURN arbiter
            `, {
              arbiterId: execution.arbiter.id,
              model: execution.arbiter.model,
              decision: execution.arbiter.decision,
              reasoning: execution.arbiter.reasoning,
              confidence: execution.arbiter.confidence,
              selectedWorker: execution.arbiter.selected_worker_id,
              timestamp: execution.arbiter.timestamp,
              workflowId: execution.id,
              finalQuality: execution.arbiter.final_quality_score
            });

            // Link workers to arbiter
            for (const worker of execution.workers) {
              await tx.run(`
                MATCH (worker:Worker {id: $workerId})
                MATCH (arbiter:Arbiter {id: $arbiterId})
                MERGE (worker)-[r:JUDGED_BY]->(arbiter)
                RETURN r
              `, {
                workerId: worker.id,
                arbiterId: execution.arbiter.id
              });
            }
          }
        });

        console.log(`Synced execution ${executionId} to Neo4j`);
        return { status: 'synced', executionId };

      } finally {
        await session.close();
      }

    } catch (err) {
      console.error(`Neo4j sync failed for execution ${executionId}: ${err.message}`);
      // Non-blocking: log error but don't throw
      return { status: 'failed', executionId, error: err.message };
    }
  }

  /**
   * Fetch workflow execution with workers and arbiter from PostgreSQL
   */
  async fetchExecution(executionId) {
    const executionQuery = `
      SELECT
        id,
        workflow_name,
        started_at,
        completed_at,
        status,
        metadata
      FROM workflow.executions
      WHERE id = $1
    `;

    const workersQuery = `
      SELECT
        id,
        model,
        task_type,
        result,
        quality_score,
        confidence,
        duration_ms,
        timestamp,
        execution_order,
        parallel_group
      FROM workflow.worker_results
      WHERE execution_id = $1
      ORDER BY execution_order
    `;

    const arbiterQuery = `
      SELECT
        id,
        model,
        decision,
        reasoning,
        confidence,
        selected_worker_id,
        final_quality_score,
        timestamp
      FROM workflow.arbiter_decisions
      WHERE execution_id = $1
      LIMIT 1
    `;

    const executionResult = await this.pgPool.query(executionQuery, [executionId]);
    if (executionResult.rows.length === 0) {
      return null;
    }

    const workersResult = await this.pgPool.query(workersQuery, [executionId]);
    const arbiterResult = await this.pgPool.query(arbiterQuery, [executionId]);

    return {
      ...executionResult.rows[0],
      workers: workersResult.rows,
      arbiter: arbiterResult.rows[0] || null
    };
  }

  /**
   * Enqueue sync job as background task in orchestrator.work_queue
   */
  async enqueueSync(executionId, priority = 5) {
    await this.connect();

    const query = `
      INSERT INTO orchestrator.work_queue (
        task_type,
        payload,
        priority,
        status,
        created_at,
        scheduled_for
      )
      VALUES ($1, $2, $3, 'pending', NOW(), NOW())
      RETURNING id
    `;

    const result = await this.pgPool.query(query, [
      'neo4j_sync',
      JSON.stringify({ executionId }),
      priority
    ]);

    console.log(`Enqueued Neo4j sync job ${result.rows[0].id} for execution ${executionId}`);
    return result.rows[0].id;
  }

  /**
   * Process background sync job from work_queue
   */
  async processQueuedJob(jobId) {
    await this.connect();

    // Fetch job
    const jobQuery = `
      SELECT id, payload, created_at
      FROM orchestrator.work_queue
      WHERE id = $1 AND task_type = 'neo4j_sync' AND status = 'pending'
    `;

    const jobResult = await this.pgPool.query(jobQuery, [jobId]);
    if (jobResult.rows.length === 0) {
      throw new Error(`Job ${jobId} not found or already processed`);
    }

    const job = jobResult.rows[0];
    const { executionId } = JSON.parse(job.payload);

    try {
      // Mark as running
      await this.pgPool.query(`
        UPDATE orchestrator.work_queue
        SET status = 'running', started_at = NOW()
        WHERE id = $1
      `, [jobId]);

      // Sync to Neo4j
      const result = await this.syncWorkflowExecution(executionId);

      // Mark as completed
      await this.pgPool.query(`
        UPDATE orchestrator.work_queue
        SET status = 'completed', completed_at = NOW(), result = $2
        WHERE id = $1
      `, [jobId, JSON.stringify(result)]);

      console.log(`Completed Neo4j sync job ${jobId}`);
      return result;

    } catch (err) {
      // Mark as failed (non-blocking for workflow)
      await this.pgPool.query(`
        UPDATE orchestrator.work_queue
        SET status = 'failed', completed_at = NOW(), error = $2
        WHERE id = $1
      `, [jobId, err.message]);

      console.error(`Neo4j sync job ${jobId} failed: ${err.message}`);
      throw err;
    }
  }

  /**
   * Query workflow graph using Neo4j (if available) or PostgreSQL recursive CTEs
   */
  async queryWorkflowGraph(queryType, params = {}) {
    await this.connect();

    if (this.neo4jAvailable) {
      return await this.queryNeo4j(queryType, params);
    } else {
      return await this.queryPostgreSQL(queryType, params);
    }
  }

  /**
   * Neo4j graph queries
   */
  async queryNeo4j(queryType, params) {
    const queries = {
      // Find workflows using a specific model
      workflowsByModel: `
        MATCH (w:Workflow)-[:EXECUTED_BY]->(worker:Worker {model: $model})
        RETURN DISTINCT w.id AS workflowId, w.name AS workflowName, w.status
        ORDER BY w.completedAt DESC
        LIMIT $limit
      `,

      // Find best performing model for a task type
      bestModelForTask: `
        MATCH (w:Workflow)-[:EXECUTED_BY]->(worker:Worker {taskType: $taskType})
        WITH worker.model AS model, AVG(worker.qualityScore) AS avgQuality, COUNT(*) AS executions
        WHERE executions > $minExecutions
        RETURN model, avgQuality, executions
        ORDER BY avgQuality DESC
        LIMIT 10
      `,

      // Workflow execution path (workers -> arbiter)
      executionPath: `
        MATCH path = (w:Workflow {id: $workflowId})-[:EXECUTED_BY]->(worker:Worker)-[:JUDGED_BY]->(arbiter:Arbiter)
        RETURN worker.model AS workerModel,
               worker.qualityScore AS workerQuality,
               arbiter.decision AS arbiterDecision,
               arbiter.selectedWorker AS selectedWorker
        ORDER BY worker.timestamp
      `,

      // Model collaboration patterns
      modelCollaboration: `
        MATCH (w:Workflow)-[:EXECUTED_BY]->(worker:Worker)
        WITH w, COLLECT(DISTINCT worker.model) AS models
        WHERE SIZE(models) > 1
        UNWIND models AS model1
        UNWIND models AS model2
        WHERE model1 < model2
        RETURN model1, model2, COUNT(*) AS cooccurrences
        ORDER BY cooccurrences DESC
        LIMIT 20
      `
    };

    const query = queries[queryType];
    if (!query) {
      throw new Error(`Unknown query type: ${queryType}`);
    }

    const session = this.neo4jDriver.session();
    try {
      const result = await session.run(query, {
        limit: params.limit || 10,
        minExecutions: params.minExecutions || 5,
        ...params
      });

      return result.records.map(record => record.toObject());
    } finally {
      await session.close();
    }
  }

  /**
   * PostgreSQL recursive CTE fallback queries
   */
  async queryPostgreSQL(queryType, params) {
    const queries = {
      workflowsByModel: `
        SELECT DISTINCT
          e.id AS "workflowId",
          e.workflow_name AS "workflowName",
          e.status
        FROM workflow.executions e
        JOIN workflow.worker_results wr ON e.id = wr.execution_id
        WHERE wr.model = $1
        ORDER BY e.completed_at DESC
        LIMIT $2
      `,

      bestModelForTask: `
        SELECT
          model,
          AVG(quality_score) AS "avgQuality",
          COUNT(*) AS executions
        FROM workflow.worker_results
        WHERE task_type = $1
        GROUP BY model
        HAVING COUNT(*) > $2
        ORDER BY AVG(quality_score) DESC
        LIMIT 10
      `,

      executionPath: `
        SELECT
          wr.model AS "workerModel",
          wr.quality_score AS "workerQuality",
          ad.decision AS "arbiterDecision",
          ad.selected_worker_id AS "selectedWorker"
        FROM workflow.worker_results wr
        LEFT JOIN workflow.arbiter_decisions ad ON wr.execution_id = ad.execution_id
        WHERE wr.execution_id = $1
        ORDER BY wr.timestamp
      `,

      modelCollaboration: `
        WITH workflow_models AS (
          SELECT
            execution_id,
            ARRAY_AGG(DISTINCT model ORDER BY model) AS models
          FROM workflow.worker_results
          GROUP BY execution_id
          HAVING COUNT(DISTINCT model) > 1
        )
        SELECT
          m1.model AS model1,
          m2.model AS model2,
          COUNT(*) AS cooccurrences
        FROM workflow_models wm
        CROSS JOIN LATERAL UNNEST(wm.models) AS m1(model)
        CROSS JOIN LATERAL UNNEST(wm.models) AS m2(model)
        WHERE m1.model < m2.model
        GROUP BY m1.model, m2.model
        ORDER BY cooccurrences DESC
        LIMIT 20
      `
    };

    const query = queries[queryType];
    if (!query) {
      throw new Error(`Unknown query type: ${queryType}`);
    }

    const queryParams = {
      workflowsByModel: [params.model, params.limit || 10],
      bestModelForTask: [params.taskType, params.minExecutions || 5],
      executionPath: [params.workflowId],
      modelCollaboration: []
    };

    const result = await this.pgPool.query(query, queryParams[queryType]);
    return result.rows;
  }

  /**
   * Initialize Neo4j schema (indexes and constraints)
   */
  async initializeNeo4jSchema() {
    if (!this.neo4jAvailable) {
      console.log('Neo4j not available, skipping schema initialization');
      return;
    }

    const session = this.neo4jDriver.session();

    try {
      const constraints = [
        'CREATE CONSTRAINT workflow_id IF NOT EXISTS FOR (w:Workflow) REQUIRE w.id IS UNIQUE',
        'CREATE CONSTRAINT worker_id IF NOT EXISTS FOR (w:Worker) REQUIRE w.id IS UNIQUE',
        'CREATE CONSTRAINT arbiter_id IF NOT EXISTS FOR (a:Arbiter) REQUIRE a.id IS UNIQUE'
      ];

      const indexes = [
        'CREATE INDEX workflow_name IF NOT EXISTS FOR (w:Workflow) ON (w.name)',
        'CREATE INDEX worker_model IF NOT EXISTS FOR (w:Worker) ON (w.model)',
        'CREATE INDEX worker_task_type IF NOT EXISTS FOR (w:Worker) ON (w.taskType)',
        'CREATE INDEX arbiter_decision IF NOT EXISTS FOR (a:Arbiter) ON (a.decision)'
      ];

      for (const constraint of constraints) {
        await session.run(constraint);
        console.log(`Created constraint: ${constraint.split(' ')[2]}`);
      }

      for (const index of indexes) {
        await session.run(index);
        console.log(`Created index: ${index.split(' ')[2]}`);
      }

      console.log('Neo4j schema initialization complete');

    } catch (err) {
      console.error(`Neo4j schema initialization failed: ${err.message}`);
    } finally {
      await session.close();
    }
  }

  /**
   * Initialize PostgreSQL orchestrator schema
   */
  async initializePostgreSQLSchema() {
    await this.connect();

    const schemas = [
      `
        CREATE SCHEMA IF NOT EXISTS orchestrator;
      `,
      `
        CREATE SCHEMA IF NOT EXISTS workflow;
      `,
      `
        CREATE TABLE IF NOT EXISTS orchestrator.work_queue (
          id SERIAL PRIMARY KEY,
          task_type VARCHAR(100) NOT NULL,
          payload JSONB NOT NULL,
          priority INTEGER DEFAULT 5,
          status VARCHAR(20) DEFAULT 'pending',
          created_at TIMESTAMP DEFAULT NOW(),
          scheduled_for TIMESTAMP DEFAULT NOW(),
          started_at TIMESTAMP,
          completed_at TIMESTAMP,
          result JSONB,
          error TEXT
        );
      `,
      `
        CREATE INDEX IF NOT EXISTS idx_work_queue_status
        ON orchestrator.work_queue(status, priority DESC, scheduled_for);
      `,
      `
        CREATE TABLE IF NOT EXISTS workflow.executions (
          id SERIAL PRIMARY KEY,
          workflow_name VARCHAR(100) NOT NULL,
          started_at TIMESTAMP NOT NULL,
          completed_at TIMESTAMP,
          status VARCHAR(20) DEFAULT 'running',
          metadata JSONB
        );
      `,
      `
        CREATE TABLE IF NOT EXISTS workflow.worker_results (
          id SERIAL PRIMARY KEY,
          execution_id INTEGER REFERENCES workflow.executions(id),
          model VARCHAR(100) NOT NULL,
          task_type VARCHAR(100),
          result JSONB,
          quality_score FLOAT,
          confidence FLOAT,
          duration_ms INTEGER,
          timestamp TIMESTAMP DEFAULT NOW(),
          execution_order INTEGER,
          parallel_group INTEGER
        );
      `,
      `
        CREATE TABLE IF NOT EXISTS workflow.arbiter_decisions (
          id SERIAL PRIMARY KEY,
          execution_id INTEGER REFERENCES workflow.executions(id),
          model VARCHAR(100) NOT NULL,
          decision TEXT,
          reasoning TEXT,
          confidence FLOAT,
          selected_worker_id INTEGER REFERENCES workflow.worker_results(id),
          final_quality_score FLOAT,
          timestamp TIMESTAMP DEFAULT NOW()
        );
      `,
      `
        CREATE INDEX IF NOT EXISTS idx_worker_results_execution
        ON workflow.worker_results(execution_id);
      `,
      `
        CREATE INDEX IF NOT EXISTS idx_arbiter_decisions_execution
        ON workflow.arbiter_decisions(execution_id);
      `
    ];

    for (const schema of schemas) {
      try {
        await this.pgPool.query(schema);
      } catch (err) {
        console.warn(`Schema already exists: ${err.message}`);
      }
    }

    console.log('PostgreSQL orchestrator schema initialized');
  }
}

module.exports = { WorkflowGraphSync };

// CLI usage
if (require.main === module) {
  const sync = new WorkflowGraphSync();

  const command = process.argv[2];
  const args = process.argv.slice(3);

  (async () => {
    try {
      switch (command) {
        case 'init':
          await sync.initializePostgreSQLSchema();
          await sync.initializeNeo4jSchema();
          break;

        case 'sync':
          if (!args[0]) {
            console.error('Usage: node workflow-graph-sync.js sync <executionId>');
            process.exit(1);
          }
          await sync.syncWorkflowExecution(parseInt(args[0]));
          break;

        case 'enqueue':
          if (!args[0]) {
            console.error('Usage: node workflow-graph-sync.js enqueue <executionId>');
            process.exit(1);
          }
          await sync.enqueueSync(parseInt(args[0]));
          break;

        case 'process':
          if (!args[0]) {
            console.error('Usage: node workflow-graph-sync.js process <jobId>');
            process.exit(1);
          }
          await sync.processQueuedJob(parseInt(args[0]));
          break;

        case 'query':
          if (!args[0]) {
            console.error('Usage: node workflow-graph-sync.js query <queryType> [params...]');
            console.error('Available queries: workflowsByModel, bestModelForTask, executionPath, modelCollaboration');
            process.exit(1);
          }
          const queryType = args[0];
          const params = JSON.parse(args[1] || '{}');
          const results = await sync.queryWorkflowGraph(queryType, params);
          console.log(JSON.stringify(results, null, 2));
          break;

        default:
          console.error('Usage: node workflow-graph-sync.js <command> [args]');
          console.error('Commands:');
          console.error('  init              - Initialize database schemas');
          console.error('  sync <execId>     - Sync execution to Neo4j immediately');
          console.error('  enqueue <execId>  - Enqueue background sync job');
          console.error('  process <jobId>   - Process queued sync job');
          console.error('  query <type> <params> - Query workflow graph');
          process.exit(1);
      }

      await sync.disconnect();
      console.log('Done');

    } catch (err) {
      console.error('Error:', err.message);
      await sync.disconnect();
      process.exit(1);
    }
  })();
}
