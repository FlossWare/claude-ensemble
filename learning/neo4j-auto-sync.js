/**
 * Neo4j Auto-Sync Integration
 *
 * Automatically syncs to Neo4j graph database:
 * - Task dependencies → Graph edges
 * - Code relationships → Import/dependency graph
 * - Research citations → Knowledge graph
 * - Concept networks → Semantic relationships
 * - Worker assignments → Execution graph
 */

import neo4j from 'neo4j-driver';
import pg from 'pg';

const { Pool } = pg;

class Neo4jAutoSync {
  constructor() {
    // Neo4j connection
    this.driver = neo4j.driver(
      'bolt://laptop-01:7687',
      neo4j.auth.basic('neo4j', process.env.NEO4J_PASSWORD || 'neo4j')
    );

    // PostgreSQL connection
    this.pool = new Pool({
      host: 'laptop-01',
      user: 'sfloess',
      database: 'learning',
    });
  }

  /**
   * Sync task dependencies to Neo4j
   */
  async syncTaskDependencies() {
    const session = this.driver.session();

    try {
      // Get all tasks from orchestration queue
      const tasks = await this.pool.query(`
        SELECT
          task_id,
          task_type,
          description,
          status,
          depends_on,
          blocks,
          metadata
        FROM orchestration.task_queue
      `);

      for (const task of tasks.rows) {
        // Create task node
        await session.run(`
          MERGE (t:Task {task_id: $task_id})
          SET t.task_type = $task_type,
              t.description = $description,
              t.status = $status,
              t.session_id = $session_id,
              t.orchestrator = $orchestrator,
              t.updated_at = datetime()
        `, {
          task_id: task.task_id,
          task_type: task.task_type,
          description: task.description,
          status: task.status,
          session_id: task.metadata?.session?.session_id || 'unknown',
          orchestrator: task.metadata?.session?.orchestrator || 'laptop-01'
        });

        // Create dependency edges (DEPENDS_ON)
        if (task.depends_on && task.depends_on.length > 0) {
          for (const dep_id of task.depends_on) {
            const depTask = await this.pool.query(
              'SELECT task_id FROM orchestration.task_queue WHERE id = $1',
              [dep_id]
            );

            if (depTask.rows[0]) {
              await session.run(`
                MATCH (t:Task {task_id: $task_id})
                MATCH (d:Task {task_id: $dep_task_id})
                MERGE (t)-[r:DEPENDS_ON]->(d)
                SET r.created_at = datetime()
              `, {
                task_id: task.task_id,
                dep_task_id: depTask.rows[0].task_id
              });
            }
          }
        }

        // Create blocking edges (BLOCKS)
        if (task.blocks && task.blocks.length > 0) {
          for (const block_id of task.blocks) {
            const blockTask = await this.pool.query(
              'SELECT task_id FROM orchestration.task_queue WHERE id = $1',
              [block_id]
            );

            if (blockTask.rows[0]) {
              await session.run(`
                MATCH (t:Task {task_id: $task_id})
                MATCH (b:Task {task_id: $block_task_id})
                MERGE (t)-[r:BLOCKS]->(b)
                SET r.created_at = datetime()
              `, {
                task_id: task.task_id,
                block_task_id: blockTask.rows[0].task_id
              });
            }
          }
        }
      }

      console.log(`✅ Synced ${tasks.rows.length} task nodes to Neo4j`);
      return tasks.rows.length;

    } finally {
      await session.close();
    }
  }

  /**
   * Sync code analysis chunks to Neo4j
   */
  async syncCodeAnalysis() {
    const session = this.driver.session();

    try {
      // Get code chunks with relationships
      const chunks = await this.pool.query(`
        SELECT
          id,
          source_type,
          repository,
          file_path,
          chunk_type,
          name,
          signature,
          dependencies,
          metadata
        FROM code_analysis.chunks
        WHERE chunk_type IN ('function', 'class', 'method')
        LIMIT 1000
      `);

      for (const chunk of chunks.rows) {
        // Create code entity node
        await session.run(`
          MERGE (c:CodeEntity {id: $id})
          SET c.source_type = $source_type,
              c.repository = $repository,
              c.file_path = $file_path,
              c.chunk_type = $chunk_type,
              c.name = $name,
              c.signature = $signature,
              c.updated_at = datetime()
        `, {
          id: chunk.id.toString(),
          source_type: chunk.source_type,
          repository: chunk.repository,
          file_path: chunk.file_path,
          chunk_type: chunk.chunk_type,
          name: chunk.name,
          signature: chunk.signature
        });

        // Create dependency edges
        if (chunk.dependencies && chunk.dependencies.length > 0) {
          for (const dep of chunk.dependencies) {
            // Find dependency by name in same repository
            const depChunk = await this.pool.query(`
              SELECT id FROM code_analysis.chunks
              WHERE repository = $1 AND name = $2
              LIMIT 1
            `, [chunk.repository, dep]);

            if (depChunk.rows[0]) {
              await session.run(`
                MATCH (c1:CodeEntity {id: $id1})
                MATCH (c2:CodeEntity {id: $id2})
                MERGE (c1)-[r:IMPORTS]->(c2)
                SET r.type = 'code_dependency'
              `, {
                id1: chunk.id.toString(),
                id2: depChunk.rows[0].id.toString()
              });
            }
          }
        }

        // Create file containment relationship
        await session.run(`
          MERGE (f:File {path: $file_path, repository: $repository})
          SET f.updated_at = datetime()
          WITH f
          MATCH (c:CodeEntity {id: $id})
          MERGE (f)-[r:CONTAINS]->(c)
          SET r.created_at = datetime()
        `, {
          file_path: chunk.file_path,
          repository: chunk.repository,
          id: chunk.id.toString()
        });
      }

      console.log(`✅ Synced ${chunks.rows.length} code entities to Neo4j`);
      return chunks.rows.length;

    } finally {
      await session.close();
    }
  }

  /**
   * Sync research citations to Neo4j
   */
  async syncResearchCitations() {
    const session = this.driver.session();

    try {
      // Get research chunks with citations from auto_storage
      const research = await this.pool.query(`
        SELECT
          source_id,
          text,
          metadata
        FROM orchestration.auto_storage
        WHERE source_type = 'workflow_result'
          AND metadata->>'workflow_name' LIKE '%research%'
        LIMIT 500
      `);

      for (const item of research.rows) {
        const metadata = item.metadata || {};

        // Create research document node
        await session.run(`
          MERGE (r:ResearchDocument {id: $id})
          SET r.workflow_name = $workflow_name,
              r.topic = $topic,
              r.updated_at = datetime()
        `, {
          id: item.source_id,
          workflow_name: metadata.workflow_name || 'unknown',
          topic: metadata.description || ''
        });

        // Extract and create citation relationships
        // Simple citation extraction (look for URLs, DOIs, etc.)
        const citations = this.extractCitations(item.text);

        for (const citation of citations) {
          await session.run(`
            MERGE (c:Citation {url: $url})
            SET c.type = $type,
                c.updated_at = datetime()
            WITH c
            MATCH (r:ResearchDocument {id: $id})
            MERGE (r)-[rel:CITES]->(c)
            SET rel.created_at = datetime()
          `, {
            url: citation.url,
            type: citation.type,
            id: item.source_id
          });
        }
      }

      console.log(`✅ Synced ${research.rows.length} research documents to Neo4j`);
      return research.rows.length;

    } finally {
      await session.close();
    }
  }

  /**
   * Sync worker assignments to Neo4j (execution graph)
   */
  async syncWorkerAssignments() {
    const session = this.driver.session();

    try {
      // Get worker heartbeats
      const workers = await this.pool.query(`
        SELECT worker_id, hostname, status, current_task_id, capabilities
        FROM orchestration.worker_heartbeats
      `);

      for (const worker of workers.rows) {
        // Create worker node
        await session.run(`
          MERGE (w:Worker {worker_id: $worker_id})
          SET w.hostname = $hostname,
              w.status = $status,
              w.capabilities = $capabilities,
              w.updated_at = datetime()
        `, {
          worker_id: worker.worker_id,
          hostname: worker.hostname,
          status: worker.status,
          capabilities: JSON.stringify(worker.capabilities || {})
        });

        // Create assignment edge if worker has current task
        if (worker.current_task_id) {
          await session.run(`
            MATCH (w:Worker {worker_id: $worker_id})
            MATCH (t:Task {task_id: $task_id})
            MERGE (w)-[r:ASSIGNED_TO]->(t)
            SET r.assigned_at = datetime()
          `, {
            worker_id: worker.worker_id,
            task_id: worker.current_task_id
          });
        }
      }

      console.log(`✅ Synced ${workers.rows.length} workers to Neo4j`);
      return workers.rows.length;

    } finally {
      await session.close();
    }
  }

  /**
   * Sync workflow execution lineage
   */
  async syncWorkflowLineage() {
    const session = this.driver.session();

    try {
      const workflows = await this.pool.query(`
        SELECT
          id,
          workflow_id,
          workflow_name,
          task_description,
          outcome,
          metadata
        FROM workflow.executions
        ORDER BY created_at DESC
        LIMIT 500
      `);

      for (const wf of workflows.rows) {
        const metadata = wf.metadata || {};

        // Create workflow execution node
        await session.run(`
          MERGE (w:WorkflowExecution {workflow_id: $workflow_id})
          SET w.workflow_name = $workflow_name,
              w.task_description = $task_description,
              w.outcome = $outcome,
              w.updated_at = datetime()
        `, {
          workflow_id: wf.workflow_id,
          workflow_name: wf.workflow_name,
          task_description: wf.task_description,
          outcome: wf.outcome
        });

        // Link to parent workflow if exists
        if (metadata.parent_workflow_id) {
          await session.run(`
            MATCH (child:WorkflowExecution {workflow_id: $child_id})
            MATCH (parent:WorkflowExecution {workflow_id: $parent_id})
            MERGE (child)-[r:DERIVED_FROM]->(parent)
            SET r.created_at = datetime()
          `, {
            child_id: wf.workflow_id,
            parent_id: metadata.parent_workflow_id
          });
        }

        // Link workflow to task
        const task = await this.pool.query(`
          SELECT task_id FROM orchestration.task_queue
          WHERE workflow_run_id = $1
          LIMIT 1
        `, [wf.workflow_id]);

        if (task.rows[0]) {
          await session.run(`
            MATCH (w:WorkflowExecution {workflow_id: $workflow_id})
            MATCH (t:Task {task_id: $task_id})
            MERGE (w)-[r:EXECUTES]->(t)
            SET r.created_at = datetime()
          `, {
            workflow_id: wf.workflow_id,
            task_id: task.rows[0].task_id
          });
        }
      }

      console.log(`✅ Synced ${workflows.rows.length} workflow executions to Neo4j`);
      return workflows.rows.length;

    } finally {
      await session.close();
    }
  }

  /**
   * Full sync - all data types
   */
  async syncAll() {
    console.log('Starting full Neo4j sync...');

    const results = {
      tasks: await this.syncTaskDependencies(),
      code: await this.syncCodeAnalysis(),
      research: await this.syncResearchCitations(),
      workers: await this.syncWorkerAssignments(),
      workflows: await this.syncWorkflowLineage()
    };

    console.log('✅ Full Neo4j sync complete:', results);
    return results;
  }

  /**
   * Helper: Extract citations from text
   */
  extractCitations(text) {
    const citations = [];

    // Extract URLs
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const urls = text.match(urlRegex) || [];
    for (const url of urls) {
      citations.push({ url, type: 'url' });
    }

    // Extract DOIs
    const doiRegex = /10\.\d{4,}\/[^\s]+/g;
    const dois = text.match(doiRegex) || [];
    for (const doi of dois) {
      citations.push({ url: `https://doi.org/${doi}`, type: 'doi' });
    }

    return citations;
  }

  async close() {
    await this.driver.close();
    await this.pool.end();
  }
}

// Singleton
let instance = null;

function getNeo4jAutoSync() {
  if (!instance) {
    instance = new Neo4jAutoSync();
  }
  return instance;
}

export {
  Neo4jAutoSync,
  getNeo4jAutoSync
};
