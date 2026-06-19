#!/usr/bin/env node

/**
 * Workflow Completion Hook
 *
 * Called when a workflow completes. Handles:
 * 1. Store execution in PostgreSQL
 * 2. Generate embeddings for similarity search
 * 3. Enqueue Neo4j sync job (async, non-blocking)
 * 4. Update strategy performance (Thompson Sampling)
 * 5. Refresh materialized views
 *
 * Integration:
 * - Import this in workflows (deep-research.mjs, etc.)
 * - Call onWorkflowComplete() at the end of execution
 * - Non-blocking: Neo4j sync happens in background
 */

const { WorkflowStorageAdapter } = require('./workflow-storage-adapter.js');
const { WorkflowGraphSync } = require('./workflow-graph-sync.js');
const { createHash } = require('crypto');

class WorkflowCompletionHook {
  constructor(config = {}) {
    this.storage = new WorkflowStorageAdapter(config.storage);
    this.graphSync = new WorkflowGraphSync(config.graphSync);
    this.enableEmbeddings = config.enableEmbeddings !== false;
    this.enableNeo4j = config.enableNeo4j !== false;
  }

  /**
   * Main hook: called when workflow completes
   *
   * @param {Object} workflow - Workflow execution data
   * @param {string} workflow.name - Workflow name
   * @param {string} workflow.query - Original query/task
   * @param {Object} workflow.result - Final result
   * @param {Array} workflow.phases - Execution phases
   * @param {number} workflow.durationMs - Total duration
   * @param {string} workflow.outcome - 'success' | 'failure'
   * @param {Object} workflow.metadata - Additional metadata
   * @returns {Promise<Object>} Stored execution with ID
   */
  async onWorkflowComplete(workflow) {
    const {
      name,
      query,
      result,
      phases = [],
      durationMs,
      outcome,
      metadata = {}
    } = workflow;

    try {
      // 1. Calculate quality score
      const qualityScore = this.calculateQualityScore(workflow);

      // 2. Store execution in PostgreSQL monitoring.execution_summary
      const execution = await this.storage.storeExecution({
        workflow: name,
        model: metadata.primaryModel || 'claude-sonnet-4',
        task_type: metadata.taskType || 'general',
        quality_score: qualityScore,
        input_tokens: metadata.inputTokens || 0,
        output_tokens: metadata.outputTokens || 0,
        cost_usd: metadata.costUsd || 0,
        duration_ms: durationMs,
        outcome,
        metadata: {
          query,
          phases: phases.map(p => ({ name: p.name, status: p.status })),
          ...metadata
        }
      });

      console.log(`Stored execution ${execution.id} in PostgreSQL`);

      // 3. Store in workflows.executions table for graph sync
      const workflowExecution = await this.storeWorkflowExecution({
        workflowName: name,
        startedAt: metadata.startedAt,
        completedAt: new Date().toISOString(),
        status: outcome === 'success' ? 'completed' : 'failed',
        metadata: {
          query,
          qualityScore,
          durationMs,
          phases: phases.length
        }
      });

      console.log(`Created workflow execution ${workflowExecution.id}`);

      // 4. Store worker results (if multi-model)
      if (metadata.workers && Array.isArray(metadata.workers)) {
        await this.storeWorkerResults(workflowExecution.id, metadata.workers);
      }

      // 5. Store arbiter decision (if applicable)
      if (metadata.arbiter) {
        await this.storeArbiterDecision(workflowExecution.id, metadata.arbiter);
      }

      // 6. Generate and store embedding (async, non-blocking)
      if (this.enableEmbeddings && outcome === 'success') {
        this.generateAndStoreEmbedding(workflow, execution.id, qualityScore)
          .catch(err => console.warn(`Embedding generation failed: ${err.message}`));
      }

      // 7. Enqueue Neo4j sync job (async, non-blocking)
      if (this.enableNeo4j) {
        this.graphSync.enqueueSync(workflowExecution.id)
          .catch(err => console.warn(`Neo4j sync enqueue failed: ${err.message}`));
      }

      // 8. Update strategy performance (if strategy specified)
      if (metadata.strategy) {
        await this.storage.updateStrategyPerformance(
          metadata.strategy,
          outcome === 'success',
          qualityScore
        );
      }

      return {
        executionId: execution.id,
        workflowExecutionId: workflowExecution.id,
        qualityScore,
        outcome
      };

    } catch (err) {
      console.error(`Workflow completion hook failed: ${err.message}`);
      throw err;
    } finally {
      await this.storage.disconnect();
    }
  }

  /**
   * Store workflow execution in workflows.executions table
   */
  async storeWorkflowExecution(data) {
    await this.storage.connect();

    const query = `
      INSERT INTO workflows.executions (
        workflow_name, started_at, completed_at, status, metadata
      )
      VALUES ($1, $2, $3, $4, $5)
      RETURNING id, started_at, completed_at, status
    `;

    const result = await this.storage.client.query(query, [
      data.workflowName,
      data.startedAt,
      data.completedAt,
      data.status,
      JSON.stringify(data.metadata)
    ]);

    return result.rows[0];
  }

  /**
   * Store worker results in workflows.worker_results table
   */
  async storeWorkerResults(executionId, workers) {
    await this.storage.connect();

    const query = `
      INSERT INTO workflows.worker_results (
        execution_id, model, task_type, result, quality_score,
        confidence, duration_ms, execution_order, parallel_group
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
      RETURNING id
    `;

    const workerIds = [];

    for (const worker of workers) {
      const result = await this.storage.client.query(query, [
        executionId,
        worker.model,
        worker.taskType || 'general',
        JSON.stringify(worker.result || {}),
        worker.qualityScore || 0.5,
        worker.confidence || 0.5,
        worker.durationMs || 0,
        worker.executionOrder || 0,
        worker.parallelGroup || null
      ]);

      workerIds.push(result.rows[0].id);
    }

    console.log(`Stored ${workers.length} worker results`);
    return workerIds;
  }

  /**
   * Store arbiter decision in workflows.arbiter_decisions table
   */
  async storeArbiterDecision(executionId, arbiter) {
    await this.storage.connect();

    const query = `
      INSERT INTO workflows.arbiter_decisions (
        execution_id, model, decision, reasoning, confidence,
        selected_worker_id, final_quality_score
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      RETURNING id
    `;

    const result = await this.storage.client.query(query, [
      executionId,
      arbiter.model,
      arbiter.decision,
      arbiter.reasoning || '',
      arbiter.confidence || 0.5,
      arbiter.selectedWorkerId || null,
      arbiter.finalQualityScore || 0.5
    ]);

    console.log(`Stored arbiter decision ${result.rows[0].id}`);
    return result.rows[0].id;
  }

  /**
   * Calculate quality score from workflow phases
   */
  calculateQualityScore(workflow) {
    const { phases = [], outcome, metadata = {} } = workflow;

    // If quality score provided in metadata, use it
    if (metadata.qualityScore !== undefined) {
      return metadata.qualityScore;
    }

    // If workflow failed, score is 0
    if (outcome === 'failure') {
      return 0.0;
    }

    // Calculate based on phase completion
    const totalPhases = phases.length;
    if (totalPhases === 0) {
      return 0.5; // Default for workflows without phases
    }

    const completedPhases = phases.filter(p => p.status === 'completed').length;
    const failedPhases = phases.filter(p => p.status === 'failed').length;

    // Score = (completed - failed) / total
    const score = Math.max(0, Math.min(1, (completedPhases - failedPhases) / totalPhases));

    return score;
  }

  /**
   * Generate embedding for workflow and store in learning.experiences
   *
   * Embedding is generated from:
   * - Query/task description
   * - Workflow name
   * - Phase names
   * - Result summary (first 500 chars)
   */
  async generateAndStoreEmbedding(workflow, executionId, qualityScore) {
    try {
      // Create text representation for embedding
      const text = this.createEmbeddingText(workflow);

      // Generate embedding (using OpenAI API or local model)
      const embedding = await this.generateEmbedding(text);

      // Create problem hash for deduplication
      const problemHash = createHash('sha256')
        .update(workflow.query || workflow.name)
        .digest('hex')
        .substring(0, 16);

      // Store in learning.experiences
      await this.storage.storeExperience({
        problem_type: workflow.name,
        problem_hash: problemHash,
        context: {
          query: workflow.query,
          phases: workflow.phases?.map(p => p.name),
          executionId
        },
        embedding,
        strategy: workflow.metadata?.strategy || 'default',
        success: workflow.outcome === 'success',
        reward: qualityScore,
        novelty_score: 0.5, // TODO: Calculate based on similarity to existing experiences
        importance: qualityScore
      });

      console.log(`Generated and stored embedding for execution ${executionId}`);

    } catch (err) {
      console.warn(`Embedding generation failed: ${err.message}`);
      // Non-blocking: continue without embedding
    }
  }

  /**
   * Create text representation for embedding generation
   */
  createEmbeddingText(workflow) {
    const parts = [
      `Workflow: ${workflow.name}`,
      `Query: ${workflow.query || 'N/A'}`,
      `Phases: ${workflow.phases?.map(p => p.name).join(', ') || 'N/A'}`,
      `Outcome: ${workflow.outcome}`
    ];

    // Add result summary (first 500 chars)
    if (workflow.result && typeof workflow.result === 'string') {
      parts.push(`Result: ${workflow.result.substring(0, 500)}`);
    } else if (workflow.result && typeof workflow.result === 'object') {
      parts.push(`Result: ${JSON.stringify(workflow.result).substring(0, 500)}`);
    }

    return parts.join('\n');
  }

  /**
   * Generate embedding vector using OpenAI API or local model
   *
   * This is a placeholder - replace with actual embedding generation
   */
  async generateEmbedding(text) {
    // TODO: Integrate with OpenAI embeddings API or local model
    // For now, generate a dummy 128-dim embedding
    const dim = 128;
    const embedding = new Array(dim).fill(0).map(() => Math.random());

    // Normalize to unit vector
    const magnitude = Math.sqrt(embedding.reduce((sum, x) => sum + x * x, 0));
    return embedding.map(x => x / magnitude);
  }

  /**
   * Find similar past executions using vector similarity
   */
  async findSimilarExecutions(query, limit = 5) {
    const text = `Query: ${query}`;
    const embedding = await this.generateEmbedding(text);

    return await this.storage.findSimilarExperiences(embedding, limit);
  }

  /**
   * Cleanup: disconnect all clients
   */
  async disconnect() {
    await this.storage.disconnect();
    await this.graphSync.disconnect();
  }
}

module.exports = { WorkflowCompletionHook };

// CLI usage
if (require.main === module) {
  const hook = new WorkflowCompletionHook();

  // Example workflow completion
  const exampleWorkflow = {
    name: 'deep-research',
    query: 'What are the latest advances in quantum computing?',
    result: 'Research report with 15 verified sources...',
    phases: [
      { name: 'scope', status: 'completed' },
      { name: 'search', status: 'completed' },
      { name: 'fetch', status: 'completed' },
      { name: 'verify', status: 'completed' },
      { name: 'synthesize', status: 'completed' }
    ],
    durationMs: 45000,
    outcome: 'success',
    metadata: {
      primaryModel: 'claude-opus-4',
      taskType: 'research_synthesis',
      inputTokens: 12000,
      outputTokens: 3000,
      costUsd: 0.15,
      strategy: 'adversarial_verification',
      startedAt: new Date(Date.now() - 45000).toISOString(),
      workers: [
        {
          model: 'claude-opus-4',
          taskType: 'scope',
          result: { angles: ['angle1', 'angle2'] },
          qualityScore: 0.85,
          confidence: 0.9,
          durationMs: 5000,
          executionOrder: 0,
          parallelGroup: null
        },
        {
          model: 'claude-sonnet-4',
          taskType: 'search',
          result: { urls: ['url1', 'url2'] },
          qualityScore: 0.78,
          confidence: 0.85,
          durationMs: 8000,
          executionOrder: 1,
          parallelGroup: 1
        }
      ],
      arbiter: {
        model: 'claude-opus-4',
        decision: 'ACCEPT',
        reasoning: 'All phases completed successfully with high quality',
        confidence: 0.92,
        selectedWorkerId: null,
        finalQualityScore: 0.82
      }
    }
  };

  (async () => {
    try {
      console.log('Testing workflow completion hook...');
      const result = await hook.onWorkflowComplete(exampleWorkflow);
      console.log('Result:', JSON.stringify(result, null, 2));
      await hook.disconnect();
    } catch (err) {
      console.error('Error:', err.message);
      await hook.disconnect();
      process.exit(1);
    }
  })();
}
