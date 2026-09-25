/**
 * Workflow Storage Adapter
 *
 * Persistent storage for multi-AI workflow orchestration results.
 * Uses PostgreSQL + pgvector for relational data + embeddings.
 *
 * Architecture:
 * - PostgreSQL: Workflow metadata, execution logs, relationships
 * - pgvector: 1024-dim embeddings (all-mpnet-base-v2) for similarity search
 *
 * Created: 2026-06-19
 */

const { Pool } = require('pg');
const { spawn } = require('child_process');
const path = require('path');
const { promisify } = require('util');
const { chunkText: semanticChunkText } = require('./semantic-chunker-adapter.cjs');
const { getEmbeddingPool } = require('./embedding-pool.cjs');
const {
  validateWorkflowExecution,
  validateWorkerResult,
  sanitizeTaskDescription,
  validateNumber,
  validateMetadata,
  validateOutcome,
  ValidationError
} = require('./input-validation.cjs');

// Reuse connection pool from postgres-adapter.js
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
  console.error('PostgreSQL pool error:', err.message);
});

// Clean up connection pool on process exit to prevent connection leaks
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

/**
 * Generate embeddings for one or more texts using Python subprocess
 * Uses sentence-transformers all-mpnet-base-v2 (1024-dim)
 * Batches multiple texts in single call for efficiency
 *
 * @param {string|string[]} texts - Single text or array of texts to embed
 * @returns {Promise<Array<number>|Array<Array<number>>|null>} 1024-dim embedding vector(s) or null if unavailable
 *
 * Examples:
 *   const vec = await _generateEmbedding("firmware reverse engineering");
 *   // => [0.123, -0.456, ..., 0.789] (384 dims)
 *
 *   const vecs = await _generateEmbedding(["task 1", "task 2", "task 3"]);
 *   // => [[0.1, 0.2, ...], [0.3, 0.4, ...], [0.5, 0.6, ...]]
 */
async function _generateEmbedding(texts) {
  // Normalize to array
  const isArray = Array.isArray(texts);
  const textArray = isArray ? texts : [texts];

  // Validate input
  if (textArray.length === 0) {
    console.warn('_generateEmbedding: empty input, returning null');
    return null;
  }

  if (textArray.some(t => typeof t !== 'string' || t.trim().length === 0)) {
    console.warn('_generateEmbedding: invalid text (non-string or empty), returning null');
    return null;
  }

  // Use throttled embedding pool (max 4 concurrent)
  try {
    const pool = getEmbeddingPool({ maxConcurrent: 4, timeout: 120000 });
    const result = await pool.generate(textArray);
    return isArray ? result : result[0];
  } catch (err) {
    console.error('Embedding generation error:', err.message);
    return null;
  }

  // OLD UNTHROTTLED VERSION - KEPT FOR REFERENCE (CAUSED CPU OVERLOAD)
  /*
  return new Promise((resolve) => {
    try {
      const pythonScript = path.join(__dirname, 'generate-embeddings.py');

      // Spawn Python subprocess with timeout
      // Use -u flag for unbuffered output (prevents hanging on stdout)
      // Timeout needs to account for first-time model download (~10s) + loading (~5s) + encoding (< 1s)
      // On slower systems or first run, model loading can take 60-90s
      const proc = spawn('python3', ['-u', pythonScript], {
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 120000 // 120s timeout (generous for first-time model load on slower systems)
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code, signal) => {
        // Filter out progress bars from stderr (tqdm noise from sentence-transformers)
        const cleanStderr = stderr.split('\n')
          .filter(line => !line.includes('%|') && !line.includes('[00:00<') && !line.includes('Loading weights:'))
          .join('\n')
          .trim();

        if (cleanStderr) {
          console.warn('Embedding generation warnings:', cleanStderr);
        }

        // Handle abnormal termination
        if (signal) {
          console.error(`Embedding generation killed by signal ${signal}`);
          resolve(null);
          return;
        }

        // code is null when process was killed, non-zero on error
        if (code !== null && code !== 0) {
          console.error(`Embedding generation failed with exit code ${code}`);
          resolve(null);
          return;
        }

        try {
          const result = JSON.parse(stdout);

          if (result.error) {
            console.error('Embedding generation error:', result.error);
            resolve(null);
            return;
          }

          if (!result.embeddings || result.embeddings.length === 0) {
            console.warn('No embeddings returned');
            resolve(null);
            return;
          }

          // Return single vector or array of vectors based on input
          const embeddings = result.embeddings;
          resolve(isArray ? embeddings : embeddings[0]);

        } catch (err) {
          console.error('Failed to parse embedding result:', err);
          resolve(null);
        }
      });

      proc.on('error', (err) => {
        console.error('Failed to spawn embedding process:', err);
        resolve(null);
      });

      // Send input to Python script via stdin (JSON array)
      proc.stdin.write(JSON.stringify(textArray));
      proc.stdin.end();

    } catch (err) {
      console.error('Exception in _generateEmbedding:', err);
      resolve(null);
    }
  });
  */
}

/**
 * Legacy single-text embedding function (for backward compatibility)
 * @deprecated Use _generateEmbedding instead
 */
async function generateEmbedding(text) {
  const result = await _generateEmbedding(text);
  if (result === null) {
    // Graceful fallback: return null instead of throwing
    console.warn(`Failed to generate embedding for: ${text.substring(0, 50)}...`);
    return null;
  }
  return result;
}

/**
 * Auto-detect task type from task description text
 * Used for confidence calibration when task_type not explicitly provided
 *
 * @param {string} taskText - Task description or assignment text
 * @returns {string} Detected task type or 'general'
 */
function _detectTaskType(taskText) {
  if (!taskText || typeof taskText !== 'string') {
    return 'general';
  }

  const lower = taskText.toLowerCase();

  // Code-related tasks
  if (lower.includes('code') || lower.includes('implement') || lower.includes('function')) {
    return 'code_generation';
  }
  if (lower.includes('review') || lower.includes('audit') || lower.includes('check')) {
    return 'code_review';
  }
  if (lower.includes('bug') || lower.includes('fix') || lower.includes('debug')) {
    return 'bug_detection';
  }
  if (lower.includes('test') || lower.includes('verify')) {
    return 'testing';
  }

  // Security tasks
  if (lower.includes('security') || lower.includes('vulnerability') || lower.includes('exploit')) {
    return 'security_audit';
  }

  // Research tasks
  if (lower.includes('research') || lower.includes('investigate') || lower.includes('analyze')) {
    return 'research';
  }

  // Documentation tasks
  if (lower.includes('document') || lower.includes('explain') || lower.includes('describe')) {
    return 'documentation';
  }

  // Refactoring tasks
  if (lower.includes('refactor') || lower.includes('optimize') || lower.includes('improve')) {
    return 'refactoring';
  }

  return 'general';
}

/**
 * Chunk large text semantically, embed each chunk, and return the mean embedding.
 * For texts <= 500 chars, embeds directly without chunking.
 *
 * @param {string} text - Text to embed (possibly large)
 * @returns {Promise<Array<number>|null>} Averaged 1024-dim embedding or null
 */
async function chunkAndEmbedText(text) {
  if (!text || text.trim().length === 0) return null;

  // Short text: embed directly, no chunking needed
  if (text.length <= 500) {
    return generateEmbedding(text);
  }

  // Chunk large text using semantic boundaries
  const chunks = semanticChunkText(text, { minChunkSize: 300, maxChunkSize: 1500, overlapSize: 100 });

  if (!chunks || chunks.length === 0) {
    return generateEmbedding(text.substring(0, 4000));
  }

  // Single chunk: embed directly
  if (chunks.length === 1) {
    return generateEmbedding(chunks[0].content || chunks[0]);
  }

  // Multiple chunks: batch embed, then average
  const chunkTexts = chunks.map(c => c.content || c);
  const embeddings = await _generateEmbedding(chunkTexts);

  if (!embeddings || !Array.isArray(embeddings) || embeddings.length === 0) {
    // Fallback: embed just the first chunk
    return generateEmbedding(chunkTexts[0]);
  }

  // Mean-pool across chunk embeddings
  const dim = embeddings[0].length;
  const mean = new Array(dim).fill(0);
  let validCount = 0;

  for (const emb of embeddings) {
    if (!emb || emb.length !== dim) continue;
    for (let i = 0; i < dim; i++) {
      mean[i] += emb[i];
    }
    validCount++;
  }

  if (validCount === 0) return null;

  // Normalize to unit length (L2 normalize after averaging)
  for (let i = 0; i < dim; i++) {
    mean[i] /= validCount;
  }
  const norm = Math.sqrt(mean.reduce((s, v) => s + v * v, 0));
  if (norm > 0) {
    for (let i = 0; i < dim; i++) {
      mean[i] /= norm;
    }
  }

  return mean;
}

/**
 * Workflow Storage Database Adapter
 */
class WorkflowStorageDB {
  constructor() {
    this.pool = pool;
  }

  /**
   * Execute a transaction (ensures atomicity)
   * @param {Function} callback - async function that receives a client
   * @returns {Promise<any>} Result from callback
   */
  async transaction(callback) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  /**
   * Store workflow execution metadata
   *
   * @param {Object} workflowData - Workflow execution data
   * @param {string} workflowData.workflow_id - Unique workflow identifier
   * @param {string} workflowData.workflow_name - Workflow name (e.g., 'deep-research')
   * @param {string} workflowData.task_description - Original task/prompt
   * @param {number} workflowData.total_workers - Number of workers spawned
   * @param {number} workflowData.total_duration_ms - Total execution time
   * @param {string} workflowData.outcome - 'success' | 'failed' | 'error'
   * @param {Object} workflowData.metadata - Additional workflow metadata
   *   - Optional: metadata.context_used - Boolean indicating if context was injected
   *   - Optional: metadata.context_source - Array of workflow IDs used as context
   *   - Optional: metadata.context_count - Number of similar workflows loaded
   *   - Optional: metadata.similarity_scores - Array of similarity scores
   * @returns {Promise<number>} Workflow record ID
   */
  async storeExecution(workflowData) {
    // Validate all inputs
    const validated = validateWorkflowExecution(workflowData);

    const {
      workflow_id,
      workflow_name,
      task_description,
      total_workers,
      total_duration_ms,
      outcome,
      metadata
    } = validated;

    // Generate embedding for task description (for similarity search)
    // Uses semantic chunking for large descriptions (>500 chars)
    // Graceful fallback: store NULL if embedding unavailable
    const embedding = await chunkAndEmbedText(task_description);

    return await this.transaction(async (client) => {
      const result = await client.query(
        `INSERT INTO workflow.executions
         (workflow_id, workflow_name, task_description, task_embedding,
          total_workers, total_duration_ms, outcome, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
         RETURNING id`,
        [
          workflow_id,
          workflow_name,
          task_description,
          embedding ? JSON.stringify(embedding) : null, // pgvector stores as JSON array, NULL if unavailable
          total_workers,
          total_duration_ms,
          outcome,
          JSON.stringify(metadata)
        ]
      );

      return result.rows[0].id;
    });
  }

  /**
   * Store worker result
   *
   * @param {Object} workerData - Worker execution data
   * @param {number} workerData.workflow_execution_id - Parent workflow ID
   * @param {string} workerData.worker_id - Worker identifier
   * @param {string} workerData.model - Model used (e.g., 'opus', 'sonnet')
   * @param {string} workerData.task_assigned - Task assigned to worker
   * @param {string} workerData.result - Worker output/result
   * @param {number} workerData.confidence - Confidence score (0.0 - 1.0)
   * @param {number} workerData.duration_ms - Execution duration
   * @param {number} workerData.input_tokens - Input tokens consumed
   * @param {number} workerData.output_tokens - Output tokens generated
   * @param {number} workerData.cost_usd - Cost in USD
   * @param {string} workerData.outcome - 'success' | 'failed' | 'error'
   * @param {Object} workerData.metadata - Additional worker metadata
   * @returns {Promise<number>} Worker result record ID
   */
  async storeWorkerResult(workerData) {
    // Validate all inputs
    const validated = validateWorkerResult(workerData);

    const {
      workflow_execution_id,
      worker_id,
      model,
      task_assigned,
      result,
      confidence,
      duration_ms,
      input_tokens,
      output_tokens,
      cost_usd,
      outcome,
      metadata
    } = validated;

    // Generate embedding for result (for similarity search)
    // Uses semantic chunking for large results (>500 chars)
    // Graceful fallback: store NULL if embedding unavailable
    const embedding = await chunkAndEmbedText(result);

    const workerId = await this.transaction(async (client) => {
      const queryResult = await client.query(
        `INSERT INTO workflow.worker_results
         (workflow_execution_id, worker_id, model, task_assigned, result,
          result_embedding, confidence, duration_ms, input_tokens, output_tokens,
          cost_usd, outcome, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
         RETURNING id`,
        [
          workflow_execution_id,
          worker_id,
          model,
          task_assigned,
          result,
          embedding ? JSON.stringify(embedding) : null, // NULL if unavailable
          confidence,
          duration_ms,
          input_tokens,
          output_tokens,
          cost_usd,
          outcome,
          JSON.stringify(metadata)
        ]
      );

      return queryResult.rows[0].id;
    });

    // Auto-record confidence calibration observation if confidence and outcome are available
    if (confidence != null && outcome != null && model != null) {
      try {
        const { recordObservation } = require('./confidence-calibration-integration.cjs');

        // Convert outcome to binary (success = 1.0, failure/error = 0.0)
        const actualOutcome = outcome === 'success' ? 1.0 : 0.0;

        // Auto-detect task type from task_assigned or metadata
        const taskType = metadata.task_type || _detectTaskType(task_assigned) || 'general';

        await recordObservation(
          model,
          confidence,
          actualOutcome,
          taskType,
          workflow_execution_id
        );
      } catch (err) {
        // Non-fatal - continue even if calibration recording fails
        console.warn(`[workflow-storage] Confidence calibration recording failed: ${err.message}`);
      }
    }

    return workerId;
  }

  /**
   * Store arbiter decision
   *
   * @param {Object} arbiterData - Arbiter decision data
   * @param {number} arbiterData.workflow_execution_id - Parent workflow ID
   * @param {string} arbiterData.arbiter_model - Arbiter model used
   * @param {Array<number>} arbiterData.worker_result_ids - Worker results evaluated
   * @param {string} arbiterData.decision - Final decision/synthesis
   * @param {string} arbiterData.reasoning - Decision reasoning
   * @param {number} arbiterData.confidence - Confidence score (0.0 - 1.0)
   * @param {number} arbiterData.duration_ms - Decision duration
   * @param {number} arbiterData.input_tokens - Input tokens consumed
   * @param {number} arbiterData.output_tokens - Output tokens generated
   * @param {number} arbiterData.cost_usd - Cost in USD
   * @param {Object} arbiterData.metadata - Additional arbiter metadata
   * @returns {Promise<number>} Arbiter decision record ID
   */
  async storeArbiterDecision(arbiterData) {
    // Validate inputs
    const workflow_execution_id = validateNumber(arbiterData.workflow_execution_id, {
      min: 1,
      integer: true,
      field: 'workflow_execution_id'
    });
    const arbiter_model = arbiterData.arbiter_model; // Validated in model-loader
    const worker_result_ids = arbiterData.worker_result_ids; // Array of IDs
    const decision = sanitizeTaskDescription(arbiterData.decision, { maxLength: 50000 });
    const reasoning = sanitizeTaskDescription(arbiterData.reasoning || '', { maxLength: 10000 });
    const confidence = arbiterData.confidence; // Validated in API
    const duration_ms = validateNumber(arbiterData.duration_ms, {
      min: 0,
      max: 3600000,
      integer: true,
      field: 'duration_ms'
    });
    const input_tokens = validateNumber(arbiterData.input_tokens, {
      min: 0,
      max: 1000000,
      integer: true,
      field: 'input_tokens'
    });
    const output_tokens = validateNumber(arbiterData.output_tokens, {
      min: 0,
      max: 1000000,
      integer: true,
      field: 'output_tokens'
    });
    const cost_usd = validateNumber(arbiterData.cost_usd, {
      min: 0,
      max: 100,
      field: 'cost_usd'
    });
    const metadata = validateMetadata(arbiterData.metadata || {});

    // Generate embedding for decision (for similarity search)
    // Uses semantic chunking for large decisions (>500 chars)
    // Graceful fallback: store NULL if embedding unavailable
    const embedding = await chunkAndEmbedText(decision);

    return await this.transaction(async (client) => {
      const result = await client.query(
        `INSERT INTO workflow.arbiter_decisions
         (workflow_execution_id, arbiter_model, worker_result_ids, decision,
          decision_embedding, reasoning, confidence, duration_ms, input_tokens,
          output_tokens, cost_usd, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
         RETURNING id`,
        [
          workflow_execution_id,
          arbiter_model,
          worker_result_ids,
          decision,
          embedding ? JSON.stringify(embedding) : null, // NULL if unavailable
          reasoning,
          confidence,
          duration_ms,
          input_tokens,
          output_tokens,
          cost_usd,
          JSON.stringify(metadata)
        ]
      );

      return result.rows[0].id;
    });
  }

  /**
   * Store workflow phase data
   *
   * @param {Object} phaseData - Phase execution data
   * @param {number} phaseData.workflow_execution_id - Parent workflow ID
   * @param {string} phaseData.phase_name - Phase name (e.g., 'search', 'verify', 'synthesize')
   * @param {number} phaseData.phase_order - Phase sequence number
   * @param {number} phaseData.duration_ms - Phase duration
   * @param {string} phaseData.outcome - 'success' | 'failed' | 'error'
   * @param {Object} phaseData.metadata - Additional phase metadata
   * @returns {Promise<number>} Phase record ID
   */
  async storePhase(phaseData) {
    const {
      workflow_execution_id,
      phase_name,
      phase_order,
      duration_ms,
      outcome,
      metadata = {}
    } = phaseData;

    return await this.transaction(async (client) => {
      const result = await client.query(
        `INSERT INTO workflow.phases
         (workflow_execution_id, phase_name, phase_order, duration_ms, outcome, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, NOW())
         RETURNING id`,
        [
          workflow_execution_id,
          phase_name,
          phase_order,
          duration_ms,
          outcome,
          JSON.stringify(metadata)
        ]
      );

      return result.rows[0].id;
    });
  }

  /**
   * Store feedback on workflow execution
   *
   * @param {Object} feedbackData - Feedback data
   * @param {number} feedbackData.workflow_execution_id - Parent workflow ID
   * @param {string} feedbackData.feedback_type - 'user' | 'automated' | 'adversarial'
   * @param {number} feedbackData.quality_score - Quality score (0.0 - 1.0)
   * @param {string} feedbackData.feedback_text - Feedback comments
   * @param {Object} feedbackData.metadata - Additional feedback metadata
   * @returns {Promise<number>} Feedback record ID
   */
  async storeFeedback(feedbackData) {
    const {
      workflow_execution_id,
      feedback_type,
      quality_score,
      feedback_text,
      metadata = {}
    } = feedbackData;

    return await this.transaction(async (client) => {
      const result = await client.query(
        `INSERT INTO workflow.feedback
         (workflow_execution_id, feedback_type, quality_score, feedback_text, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, NOW())
         RETURNING id`,
        [
          workflow_execution_id,
          feedback_type,
          quality_score,
          feedback_text,
          JSON.stringify(metadata)
        ]
      );

      return result.rows[0].id;
    });
  }

  /**
   * Store learnings extracted from workflow
   *
   * @param {Object} learningsData - Learning data
   * @param {number} learningsData.workflow_execution_id - Parent workflow ID
   * @param {string} learningsData.learning_type - 'pattern' | 'failure' | 'optimization'
   * @param {string} learningsData.description - Learning description
   * @param {string} learningsData.actionable_insight - What to do differently
   * @param {number} learningsData.importance - Importance score (0.0 - 1.0)
   * @param {Object} learningsData.metadata - Additional learning metadata
   * @returns {Promise<number>} Learning record ID
   */
  async storeLearnings(learningsData) {
    const {
      workflow_execution_id,
      learning_type,
      description,
      actionable_insight,
      importance,
      metadata = {}
    } = learningsData;

    const combinedText = description + ' ' + actionable_insight;

    // Check if semantic chunking needed (>500 chars)
    if (combinedText.length > 500) {
      const chunks = semanticChunkText(combinedText, { minChunkSize: 300, maxChunkSize: 1500, overlapSize: 100 });

      // Single chunk or fallback: embed and store directly
      if (!chunks || chunks.length <= 1) {
        const embedding = await generateEmbedding(combinedText.substring(0, 4000));
        return await this.transaction(async (client) => {
          const result = await client.query(
            `INSERT INTO workflow.learnings
             (workflow_execution_id, learning_type, description, learning_embedding,
              actionable_insight, importance, metadata, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
             RETURNING id`,
            [
              workflow_execution_id,
              learning_type,
              description,
              embedding ? JSON.stringify(embedding) : null,
              actionable_insight,
              importance,
              JSON.stringify(metadata)
            ]
          );
          return result.rows[0].id;
        });
      }

      // Multiple chunks: create parent + individual chunk rows
      console.log(`Large learning (${combinedText.length} chars), semantic chunking into ${chunks.length} pieces...`);
      const chunkIds = [];

      // Create parent learning first (without embedding)
      const parentResult = await this.transaction(async (client) => {
        return await client.query(
          `INSERT INTO workflow.learnings
           (workflow_execution_id, learning_type, description, learning_embedding,
            actionable_insight, importance, metadata, created_at)
           VALUES ($1, $2, $3, NULL, $4, $5, $6, NOW())
           RETURNING id`,
          [
            workflow_execution_id,
            learning_type,
            `[CHUNKED ${chunks.length} parts] ${description.substring(0, 200)}...`,
            actionable_insight.substring(0, 200),
            importance,
            JSON.stringify({ ...metadata, is_parent: true, total_chunks: chunks.length })
          ]
        );
      });

      const parentId = parentResult.rows[0].id;

      // Batch embed all chunks at once for efficiency
      const chunkTexts = chunks.map(c => c.content || c);
      const allEmbeddings = await _generateEmbedding(chunkTexts);

      // Store each chunk with its embedding
      for (let i = 0; i < chunks.length; i++) {
        const chunkContent = chunkTexts[i];
        const chunkEmbedding = (Array.isArray(allEmbeddings) && allEmbeddings[i]) ? allEmbeddings[i] : null;

        const chunkResult = await this.transaction(async (client) => {
          return await client.query(
            `INSERT INTO workflow.learnings
             (workflow_execution_id, learning_type, description, learning_embedding,
              actionable_insight, importance, metadata, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
             RETURNING id`,
            [
              workflow_execution_id,
              learning_type,
              chunkContent,
              chunkEmbedding ? JSON.stringify(chunkEmbedding) : null,
              '',
              importance,
              JSON.stringify({
                ...metadata,
                chunk_index: i,
                total_chunks: chunks.length,
                parent_learning_id: parentId,
                chunk_type: chunks[i].chunk_type || 'text',
                char_count: chunks[i].char_count || chunkContent.length
              })
            ]
          );
        });

        chunkIds.push(chunkResult.rows[0].id);
        console.log(`  Stored chunk ${i + 1}/${chunks.length} (ID: ${chunkResult.rows[0].id})`);
      }

      console.log(`Chunked learning stored: parent ID ${parentId}, ${chunkIds.length} chunks`);
      return parentId;

    } else {
      // Short text: embed directly, no chunking needed
      const embedding = await generateEmbedding(combinedText);

      return await this.transaction(async (client) => {
        const result = await client.query(
          `INSERT INTO workflow.learnings
           (workflow_execution_id, learning_type, description, learning_embedding,
            actionable_insight, importance, metadata, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
           RETURNING id`,
          [
            workflow_execution_id,
            learning_type,
            description,
            embedding ? JSON.stringify(embedding) : null,
            actionable_insight,
            importance,
            JSON.stringify(metadata)
          ]
        );

        return result.rows[0].id;
      });
    }
  }

  /**
   * Query similar workflows by task embedding
   *
   * @param {string} taskDescription - Task description to match
   * @param {number} limit - Max results to return
   * @returns {Promise<Array>} Similar workflow executions
   */
  async findSimilarWorkflows(taskDescription, limit = 10) {
    const embedding = await generateEmbedding(taskDescription);

    // Graceful fallback: if embedding unavailable, return empty array
    if (!embedding) {
      console.warn('Cannot search similar workflows: embedding generation failed');
      return [];
    }

    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT *, task_embedding <=> $1::vector as distance
         FROM workflow.executions
         WHERE outcome = 'success' AND task_embedding IS NOT NULL
         ORDER BY task_embedding <=> $1::vector
         LIMIT $2`,
        [JSON.stringify(embedding), limit]
      );

      return result.rows;
    } finally {
      client.release();
    }
  }

  /**
   * Get models used in a workflow execution
   *
   * @param {number} workflowExecutionId - Workflow execution ID
   * @returns {Promise<Array<string>>} Array of model names used
   */
  async getModelsUsed(workflowExecutionId) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT DISTINCT model
         FROM workflow.worker_results
         WHERE workflow_execution_id = $1
         ORDER BY model`,
        [workflowExecutionId]
      );

      return result.rows.map(row => row.model);
    } finally {
      client.release();
    }
  }

  /**
   * Get workflow execution with all related data
   *
   * @param {string} workflowId - Workflow ID
   * @returns {Promise<Object>} Complete workflow data
   */
  async getWorkflowComplete(workflowId) {
    return await this.transaction(async (client) => {
      // Get main execution record
      const execResult = await client.query(
        `SELECT * FROM workflow.executions WHERE workflow_id = $1`,
        [workflowId]
      );

      if (execResult.rows.length === 0) {
        return null;
      }

      const execution = execResult.rows[0];
      const executionId = execution.id;

      // Get worker results
      const workersResult = await client.query(
        `SELECT * FROM workflow.worker_results WHERE workflow_execution_id = $1 ORDER BY created_at`,
        [executionId]
      );

      // Get arbiter decisions
      const arbitersResult = await client.query(
        `SELECT * FROM workflow.arbiter_decisions WHERE workflow_execution_id = $1 ORDER BY created_at`,
        [executionId]
      );

      // Get phases
      const phasesResult = await client.query(
        `SELECT * FROM workflow.phases WHERE workflow_execution_id = $1 ORDER BY phase_order`,
        [executionId]
      );

      // Get feedback
      const feedbackResult = await client.query(
        `SELECT * FROM workflow.feedback WHERE workflow_execution_id = $1 ORDER BY created_at`,
        [executionId]
      );

      // Get learnings
      const learningsResult = await client.query(
        `SELECT * FROM workflow.learnings WHERE workflow_execution_id = $1 ORDER BY importance DESC`,
        [executionId]
      );

      return {
        execution,
        workers: workersResult.rows,
        arbiters: arbitersResult.rows,
        phases: phasesResult.rows,
        feedback: feedbackResult.rows,
        learnings: learningsResult.rows
      };
    });
  }

  /**
   * Get model distribution from worker results for given workflow execution IDs
   * Used for diversity checks to detect echo chamber effects
   *
   * @param {Array<number>} workflowExecutionIds - Array of workflow execution IDs
   * @returns {Promise<Object>} Model distribution { opus: 12, sonnet: 8, haiku: 4, ... }
   */
  async getModelDistribution(workflowExecutionIds) {
    if (!workflowExecutionIds || workflowExecutionIds.length === 0) {
      return {};
    }

    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT model, COUNT(*) as count
         FROM workflow.worker_results
         WHERE workflow_execution_id = ANY($1::int[])
         GROUP BY model
         ORDER BY count DESC`,
        [workflowExecutionIds]
      );

      const distribution = {};
      for (const row of result.rows) {
        distribution[row.model] = parseInt(row.count);
      }

      return distribution;
    } finally {
      client.release();
    }
  }

  /**
   * Get learning summary for given workflow execution IDs
   * Returns top learnings by importance for context injection
   *
   * @param {Array<number>} workflowExecutionIds - Array of workflow execution IDs
   * @param {number} limit - Max learnings to return (default: 10)
   * @returns {Promise<Array>} Learning objects with description, importance, actionable_insight
   */
  async getLearningSummary(workflowExecutionIds, limit = 10) {
    if (!workflowExecutionIds || workflowExecutionIds.length === 0) {
      return [];
    }

    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT description, actionable_insight, importance, learning_type, metadata
         FROM workflow.learnings
         WHERE workflow_execution_id = ANY($1::int[])
           AND metadata->>'is_parent' IS NULL
         ORDER BY importance DESC
         LIMIT $2`,
        [workflowExecutionIds, limit]
      );

      return result.rows;
    } finally {
      client.release();
    }
  }

  /**
   * Store tool validation result
   *
   * @param {Object} validationData - Validation data
   * @param {number} validationData.workflow_execution_id - Parent workflow ID (optional)
   * @param {string} validationData.tool_name - Tool name (Bash, Read, Write, Edit)
   * @param {Object} validationData.parameters - Tool parameters (JSON)
   * @param {boolean} validationData.valid - True if validation passed
   * @param {Array<string>} validationData.errors - Validation errors
   * @param {Array<string>} validationData.warnings - Validation warnings
   * @param {boolean} validationData.dry_run - True if dry-run validation
   * @param {boolean} validationData.permission_check - True if permission checks performed
   * @returns {Promise<number>} Validation record ID
   */
  async storeToolValidation(validationData) {
    const {
      workflow_execution_id = null,
      tool_name,
      parameters,
      valid,
      errors = [],
      warnings = [],
      dry_run = false,
      permission_check = true
    } = validationData;

    return await this.transaction(async (client) => {
      const result = await client.query(
        `INSERT INTO workflow.tool_validations
         (workflow_execution_id, tool_name, parameters, valid, errors, warnings, dry_run, permission_check, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
         RETURNING id`,
        [
          workflow_execution_id,
          tool_name,
          JSON.stringify(parameters),
          valid,
          errors,
          warnings,
          dry_run,
          permission_check
        ]
      );

      return result.rows[0].id;
    });
  }

  /**
   * Get validation statistics for a workflow
   *
   * @param {number} workflowExecutionId - Workflow execution ID
   * @returns {Promise<Object>} Validation statistics
   */
  async getValidationStats(workflowExecutionId) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(
        `SELECT
           tool_name,
           COUNT(*) as total,
           SUM(CASE WHEN valid THEN 1 ELSE 0 END) as passed,
           SUM(CASE WHEN NOT valid THEN 1 ELSE 0 END) as failed,
           ARRAY_AGG(unnested_error) FILTER (WHERE unnested_error IS NOT NULL) as errors
         FROM workflow.tool_validations
         CROSS JOIN LATERAL unnest(errors) AS unnested_error
         WHERE workflow_execution_id = $1
         GROUP BY tool_name`,
        [workflowExecutionId]
      );

      return result.rows;
    } finally {
      client.release();
    }
  }

  /**
   * Close connection pool
   */
  async close() {
    await this.pool.end();
  }
}

// Singleton instance
let _workflowDB = null;

/**
 * Get singleton workflow storage instance
 */
function getWorkflowStorage() {
  if (!_workflowDB) _workflowDB = new WorkflowStorageDB();
  return _workflowDB;
}

/**
 * Batch generate embeddings for multiple texts
 * More efficient than calling generateEmbedding multiple times
 *
 * @param {string[]} texts - Array of texts to embed
 * @returns {Promise<Array<Array<number>>|null>} Array of 1024-dim vectors or null
 *
 * Example:
 *   const embeddings = await generateEmbeddingsBatch([
 *     "task 1 description",
 *     "task 2 description",
 *     "task 3 description"
 *   ]);
 *   // => [[0.1, ...], [0.2, ...], [0.3, ...]]
 */
async function generateEmbeddingsBatch(texts) {
  if (!Array.isArray(texts) || texts.length === 0) {
    console.warn('generateEmbeddingsBatch: invalid input, must be non-empty array');
    return null;
  }

  return await _generateEmbedding(texts);
}

module.exports = {
  WorkflowStorageDB,
  getWorkflowStorage,
  generateEmbedding,
  generateEmbeddingsBatch,
  chunkAndEmbedText,
  _generateEmbedding,
  pool
};
