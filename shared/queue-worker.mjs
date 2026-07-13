#!/usr/bin/env node
/**
 * Queue Worker with Graceful Shutdown
 *
 * Features:
 * - Atomic batch claiming from PostgreSQL queues
 * - Graceful shutdown on SIGTERM/SIGINT
 * - Task release on shutdown (claimed tasks returned to queue)
 * - Heartbeat updates during processing
 * - Automatic timeout recovery
 * - Worker affinity for efficiency
 *
 * Usage:
 *   node queue-worker.mjs --type=chunk --worker=laptop-01 --batch=10
 *
 * Environment:
 *   DB_HOST=aio-01
 *   DB_PORT=5433
 *   DB_NAME=learning
 *   DB_USER=sfloess
 *   API_URL=http://aio-01:5000
 */

import { createRequire } from 'module';
import { setTimeout as sleep } from 'timers/promises';

const require = createRequire(import.meta.url);
const { getQueueBatch } = require('./postgres-queue-batch.cjs');

// Configuration
const CONFIG = {
  workerType: process.env.WORKER_TYPE || 'chunk',
  workerId: process.env.WORKER_ID || process.env.HOSTNAME || 'worker-unknown',
  batchSize: parseInt(process.env.BATCH_SIZE || '10'),
  pollInterval: parseInt(process.env.POLL_INTERVAL || '5000'), // 5 seconds
  heartbeatInterval: parseInt(process.env.HEARTBEAT_INTERVAL || '30000'), // 30 seconds
  shutdownTimeout: parseInt(process.env.SHUTDOWN_TIMEOUT || '60000'), // 60 seconds
  apiUrl: process.env.API_URL || 'http://aio-01:5000',
  dbConfig: {
    host: process.env.DB_HOST || 'aio-01',
    port: parseInt(process.env.DB_PORT || '5433'),
    database: process.env.DB_NAME || 'learning',
    user: process.env.DB_USER || 'sfloess',
  },
};

// Parse command line arguments
process.argv.slice(2).forEach(arg => {
  const [key, value] = arg.replace(/^--/, '').split('=');
  if (key === 'type') CONFIG.workerType = value;
  if (key === 'worker') CONFIG.workerId = value;
  if (key === 'batch') CONFIG.batchSize = parseInt(value);
});

// Worker state
let isShuttingDown = false;
let activeTasks = [];
let heartbeatTimer = null;
let queue = null;

/**
 * Log with timestamp and worker ID
 */
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  const logData = JSON.stringify({
    timestamp,
    level,
    worker: CONFIG.workerId,
    type: CONFIG.workerType,
    message,
    ...data,
  });
  console.log(logData);
}

/**
 * Process a single task based on worker type
 */
async function processTask(task) {
  const startTime = Date.now();

  try {
    log('info', `Processing task ${task.id}`, { taskId: task.id, data: task.data });

    let result;

    switch (CONFIG.workerType) {
      case 'chunk':
        result = await processChunkTask(task);
        break;
      case 'embed':
        result = await processEmbedTask(task);
        break;
      case 'store':
        result = await processStoreTask(task);
        break;
      default:
        throw new Error(`Unknown worker type: ${CONFIG.workerType}`);
    }

    const duration = Date.now() - startTime;
    log('info', `Task ${task.id} completed`, { taskId: task.id, duration });

    return { success: true, result, duration };
  } catch (error) {
    const duration = Date.now() - startTime;
    log('error', `Task ${task.id} failed: ${error.message}`, {
      taskId: task.id,
      duration,
      error: error.message,
      stack: error.stack
    });

    return { success: false, error: error.message, duration };
  }
}

/**
 * Process chunking task
 */
async function processChunkTask(task) {
  const { file_path } = task.data;

  if (!file_path) {
    throw new Error('Missing file_path in task data');
  }

  // Call chunking API
  const response = await fetch(`${CONFIG.apiUrl}/documents/chunk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Chunking API error: ${response.status} ${errorText}`);
  }

  const result = await response.json();

  // Insert chunks into next queue stage
  if (result.chunks && result.chunks.length > 0) {
    await queue.pool.query(
      `INSERT INTO queue.chunk (data, priority)
       VALUES ($1, $2)`,
      [JSON.stringify({ chunks: result.chunks, source: file_path }), task.priority]
    );
  }

  return { chunks_created: result.chunks?.length || 0 };
}

/**
 * Process embedding task
 */
async function processEmbedTask(task) {
  const { chunks } = task.data;

  if (!chunks || !Array.isArray(chunks)) {
    throw new Error('Missing or invalid chunks in task data');
  }

  // Call embedding API
  const response = await fetch(`${CONFIG.apiUrl}/documents/embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chunks }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Embedding API error: ${response.status} ${errorText}`);
  }

  const result = await response.json();

  // Insert embeddings into next queue stage
  if (result.embeddings && result.embeddings.length > 0) {
    await queue.pool.query(
      `INSERT INTO queue.store (data, priority)
       VALUES ($1, $2)`,
      [JSON.stringify({ embeddings: result.embeddings, source: task.data.source }), task.priority]
    );
  }

  return { embeddings_created: result.embeddings?.length || 0 };
}

/**
 * Process storage task
 */
async function processStoreTask(task) {
  const { embeddings, source } = task.data;

  if (!embeddings || !Array.isArray(embeddings)) {
    throw new Error('Missing or invalid embeddings in task data');
  }

  let stored = 0;

  // Store each embedding
  for (const embedding of embeddings) {
    await queue.pool.query(
      `INSERT INTO knowledge.scraped_data
       (file_path, chunk_id, chunk_text, embedding, source, created_at)
       VALUES ($1, $2, $3, $4, $5, NOW())
       ON CONFLICT (file_path, chunk_id) DO UPDATE
       SET chunk_text = EXCLUDED.chunk_text,
           embedding = EXCLUDED.embedding,
           updated_at = NOW()`,
      [
        source,
        embedding.chunk_id,
        embedding.text,
        JSON.stringify(embedding.vector),
        embedding.source || source,
      ]
    );
    stored++;
  }

  return { embeddings_stored: stored };
}

/**
 * Start heartbeat updates for active tasks
 */
function startHeartbeat() {
  heartbeatTimer = setInterval(async () => {
    if (activeTasks.length > 0 && !isShuttingDown) {
      try {
        const taskIds = activeTasks.map(t => t.id);
        const queueName = getQueueName(CONFIG.workerType);
        const updated = await queue.heartbeatBatch(queueName, taskIds);
        log('debug', `Heartbeat updated ${updated} tasks`, { taskIds });
      } catch (error) {
        log('error', `Heartbeat failed: ${error.message}`, { error: error.message });
      }
    }
  }, CONFIG.heartbeatInterval);
}

/**
 * Stop heartbeat updates
 */
function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

/**
 * Get queue name based on worker type
 */
function getQueueName(workerType) {
  switch (workerType) {
    case 'chunk':
      return 'tasks';
    case 'embed':
      return 'chunk';
    case 'store':
      return 'store';
    default:
      throw new Error(`Unknown worker type: ${workerType}`);
  }
}

/**
 * Release claimed tasks back to queue
 */
async function releaseTasks(tasks) {
  if (!tasks || tasks.length === 0) {
    return 0;
  }

  const queueName = getQueueName(CONFIG.workerType);
  const taskIds = tasks.map(t => t.id);

  try {
    log('info', `Releasing ${taskIds.length} tasks back to queue`, { taskIds });

    const result = await queue.pool.query(
      `UPDATE queue.${queueName}
       SET status = 'pending',
           claimed_by = NULL,
           claimed_at = NULL,
           last_heartbeat = NULL,
           timeout_at = NULL
       WHERE id = ANY($1)
         AND status = 'processing'
       RETURNING id`,
      [taskIds]
    );

    log('info', `Released ${result.rowCount} tasks`, { released: result.rowCount });
    return result.rowCount;
  } catch (error) {
    log('error', `Failed to release tasks: ${error.message}`, {
      error: error.message,
      taskIds
    });
    throw error;
  }
}

/**
 * Graceful shutdown handler
 */
async function gracefulShutdown(signal) {
  if (isShuttingDown) {
    log('warn', 'Shutdown already in progress, ignoring signal', { signal });
    return;
  }

  isShuttingDown = true;
  log('info', `Received ${signal}, initiating graceful shutdown`, {
    signal,
    activeTasks: activeTasks.length
  });

  // Stop heartbeat
  stopHeartbeat();

  // Set shutdown timeout
  const shutdownTimer = setTimeout(() => {
    log('error', 'Shutdown timeout exceeded, forcing exit', {
      timeout: CONFIG.shutdownTimeout,
      remainingTasks: activeTasks.length,
    });
    process.exit(1);
  }, CONFIG.shutdownTimeout);

  try {
    // Release active tasks back to queue
    if (activeTasks.length > 0) {
      await releaseTasks(activeTasks);
      activeTasks = [];
    }

    // Close database connection
    if (queue) {
      await queue.close();
      queue = null;
    }

    clearTimeout(shutdownTimer);
    log('info', 'Graceful shutdown complete', { signal });
    process.exit(0);
  } catch (error) {
    clearTimeout(shutdownTimer);
    log('error', `Shutdown error: ${error.message}`, {
      error: error.message,
      stack: error.stack
    });
    process.exit(1);
  }
}

/**
 * Main worker loop
 */
async function runWorker() {
  const queueName = getQueueName(CONFIG.workerType);

  log('info', 'Worker starting', {
    workerType: CONFIG.workerType,
    workerId: CONFIG.workerId,
    batchSize: CONFIG.batchSize,
    queueName,
    pollInterval: CONFIG.pollInterval,
  });

  // Initialize queue
  queue = getQueueBatch(CONFIG.dbConfig);

  // Start heartbeat
  startHeartbeat();

  // Register signal handlers
  process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
  process.on('SIGINT', () => gracefulShutdown('SIGINT'));

  let consecutiveEmptyPolls = 0;
  const maxEmptyPolls = 12; // Exit after 12 empty polls (1 minute with 5s interval)

  // Main processing loop
  while (!isShuttingDown) {
    try {
      // Claim batch of tasks
      const tasks = await queue.claimBatch(queueName, CONFIG.workerId, CONFIG.batchSize);

      if (tasks.length === 0) {
        consecutiveEmptyPolls++;
        log('debug', `No tasks available (${consecutiveEmptyPolls}/${maxEmptyPolls})`, {
          queueName,
          consecutiveEmptyPolls,
        });

        if (consecutiveEmptyPolls >= maxEmptyPolls) {
          log('info', 'Queue empty for extended period, shutting down', {
            consecutiveEmptyPolls,
          });
          break;
        }

        // Wait before next poll
        await sleep(CONFIG.pollInterval);
        continue;
      }

      consecutiveEmptyPolls = 0;
      activeTasks = tasks;

      log('info', `Claimed ${tasks.length} tasks`, {
        taskCount: tasks.length,
        taskIds: tasks.map(t => t.id),
      });

      // Process tasks in parallel
      const results = await Promise.allSettled(
        tasks.map(task => processTask(task))
      );

      // Categorize results
      const completed = [];
      const failed = [];

      results.forEach((result, index) => {
        const task = tasks[index];
        if (result.status === 'fulfilled' && result.value.success) {
          completed.push(task.id);
        } else {
          failed.push({
            id: task.id,
            error: result.status === 'rejected'
              ? result.reason.message
              : result.value.error,
          });
        }
      });

      // Complete successful tasks
      if (completed.length > 0) {
        await queue.completeBatch(queueName, completed);
        log('info', `Completed ${completed.length} tasks`, { taskIds: completed });
      }

      // Fail errored tasks
      if (failed.length > 0) {
        await queue.failBatch(
          queueName,
          failed.map(f => f.id),
          failed[0].error, // Use first error as representative
          true // Allow retry
        );
        log('warn', `Failed ${failed.length} tasks`, { failures: failed });
      }

      activeTasks = [];

      // Brief pause before next batch
      await sleep(100);

    } catch (error) {
      log('error', `Worker loop error: ${error.message}`, {
        error: error.message,
        stack: error.stack,
      });

      // Release any active tasks on error
      if (activeTasks.length > 0) {
        try {
          await releaseTasks(activeTasks);
          activeTasks = [];
        } catch (releaseError) {
          log('error', `Failed to release tasks: ${releaseError.message}`, {
            error: releaseError.message,
          });
        }
      }

      // Wait before retrying
      await sleep(CONFIG.pollInterval);
    }
  }

  // Normal shutdown
  await gracefulShutdown('NORMAL');
}

// Start worker
runWorker().catch(error => {
  log('error', `Fatal worker error: ${error.message}`, {
    error: error.message,
    stack: error.stack,
  });
  process.exit(1);
});
