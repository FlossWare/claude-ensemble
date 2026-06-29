/**
 * Streaming Consensus - Real-time consensus building with progressive updates
 *
 * Emit events as workers complete:
 * - worker_started: Worker begins execution
 * - worker_completed: Worker finishes with result
 * - partial_consensus: Intermediate consensus (after each worker)
 * - final_consensus: Complete consensus result
 *
 * Usage:
 *   const stream = streamConsensus(workers, options);
 *   for await (const event of stream) {
 *     console.log(event.type, event.data);
 *   }
 */

import { EventEmitter } from 'events';

// Optional database integration (gracefully handle missing module)
let getWorkflowStorage = null;
try {
  const module = await import('./workflow-storage-adapter.js');
  getWorkflowStorage = module.getWorkflowStorage;
} catch (error) {
  // Database adapter not available - continue without storage
  getWorkflowStorage = () => null;
}

/**
 * Event types emitted during streaming consensus
 */
export const EventTypes = {
  WORKER_STARTED: 'worker_started',
  WORKER_COMPLETED: 'worker_completed',
  PARTIAL_CONSENSUS: 'partial_consensus',
  FINAL_CONSENSUS: 'final_consensus',
  ERROR: 'error'
};

/**
 * Calculate partial consensus from completed workers
 * @param {Array} completedResults - Results from workers that have finished
 * @param {Object} options - Consensus options
 * @returns {Object} Partial consensus data
 */
function calculatePartialConsensus(completedResults, options = {}) {
  if (completedResults.length === 0) {
    return null;
  }

  const {
    consensusThreshold = 0.6,
    diversityWeight = 0.3,
    confidenceWeight = 0.7
  } = options;

  // Group by similar results using normalized comparison
  const groups = {};

  completedResults.forEach(result => {
    // Extract key fields for comparison (handle nested result structures)
    const resultData = result.result?.result || result.result;

    // Create a normalized key for grouping
    let key;
    if (typeof resultData === 'object' && resultData !== null) {
      // For objects, use verdict/decision field if present
      const verdict = resultData.verdict || resultData.decision || resultData.answer ||
                      JSON.stringify(resultData);
      key = String(verdict).toLowerCase().trim();
    } else {
      key = String(resultData).toLowerCase().trim();
    }

    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(result);
  });

  // Find largest group
  let largestGroup = [];
  let largestKey = null;
  for (const [key, group] of Object.entries(groups)) {
    if (group.length > largestGroup.length) {
      largestGroup = group;
      largestKey = key;
    }
  }

  // Calculate weighted consensus score
  const agreementRatio = largestGroup.length / completedResults.length;
  const avgConfidence = largestGroup.reduce((sum, r) => sum + (r.confidence || 0.5), 0) / largestGroup.length;
  const diversity = Object.keys(groups).length / completedResults.length;

  const consensusScore = (
    (agreementRatio * (1 - diversityWeight)) +
    (avgConfidence * confidenceWeight) +
    (diversity * diversityWeight)
  ) / (1 + confidenceWeight);

  return {
    result: largestGroup[0].result,
    consensusScore,
    agreementRatio,
    diversity,
    avgConfidence,
    completedWorkers: completedResults.length,
    agreeingWorkers: largestGroup.length,
    models: largestGroup.map(r => r.model),
    isPartial: true
  };
}

/**
 * Calculate final consensus from all workers
 * @param {Array} allResults - All worker results
 * @param {Object} options - Consensus options
 * @returns {Object} Final consensus data
 */
function calculateFinalConsensus(allResults, options = {}) {
  const partial = calculatePartialConsensus(allResults, options);
  if (!partial) {
    return null;
  }

  return {
    ...partial,
    isPartial: false,
    totalWorkers: allResults.length,
    timestamp: new Date().toISOString()
  };
}

/**
 * Stream consensus building in real-time
 * @param {Array} workers - Worker configurations [{model, task, ...}]
 * @param {Object} options - Streaming options
 * @returns {AsyncIterator} Event stream
 */
export async function* streamConsensus(workers, options = {}) {
  const {
    executor = null, // Function to execute worker: async (worker) => result
    emitPartialAfterEach = true,
    minWorkersForPartial = 2,
    storeInDatabase = true,
    workflowExecutionId = null,
    ...consensusOptions
  } = options;

  if (!executor) {
    throw new Error('executor function required (async function to run each worker)');
  }

  const completedResults = [];
  const errors = [];
  const db = storeInDatabase ? getWorkflowStorage() : null;

  // Execute workers in parallel using Promise.race pattern
  const pendingWorkers = workers.map((worker, index) => ({
    worker,
    index,
    promise: null,
    completed: false
  }));

  // Start all workers
  for (const item of pendingWorkers) {
    const { worker, index } = item;

    item.promise = (async () => {
      try {
        const startTime = Date.now();
        const result = await executor(worker);
        const duration = Date.now() - startTime;

        return {
          success: true,
          workerId: worker.id || `worker-${index}`,
          model: worker.model,
          task: worker.task,
          result,
          duration,
          timestamp: new Date().toISOString()
        };
      } catch (error) {
        return {
          success: false,
          workerId: worker.id || `worker-${index}`,
          model: worker.model,
          error: error.message,
          timestamp: new Date().toISOString()
        };
      }
    })();

    // Emit worker started immediately
    yield {
      type: EventTypes.WORKER_STARTED,
      data: {
        workerId: worker.id || `worker-${index}`,
        model: worker.model,
        task: worker.task,
        timestamp: new Date().toISOString()
      }
    };
  }

  // Wait for workers to complete and yield events as they finish
  while (pendingWorkers.some(w => !w.completed)) {
    // Race to find the next worker to complete
    const raceResults = await Promise.race(
      pendingWorkers
        .filter(w => !w.completed)
        .map(async (item) => {
          const outcome = await item.promise;
          return { item, outcome };
        })
    );

    const { item, outcome } = raceResults;
    item.completed = true;

    if (outcome.success) {
      const workerResult = {
        ...outcome.result,
        workerId: outcome.workerId,
        model: outcome.model,
        task: outcome.task,
        duration: outcome.duration,
        timestamp: outcome.timestamp,
        confidence: outcome.result.confidence || null,
        inputTokens: outcome.result.inputTokens || null,
        outputTokens: outcome.result.outputTokens || null,
        cost: outcome.result.cost || null
      };

      completedResults.push(workerResult);

      // Store in database
      if (db && workflowExecutionId) {
        await db.storeWorkerResult({
          workflow_execution_id: workflowExecutionId,
          worker_id: workerResult.workerId,
          model: workerResult.model,
          task_assigned: workerResult.task,
          result: JSON.stringify(workerResult.result),
          confidence: workerResult.confidence,
          duration_ms: workerResult.duration,
          input_tokens: workerResult.inputTokens,
          output_tokens: workerResult.outputTokens,
          cost_usd: workerResult.cost,
          outcome: 'success'
        });
      }

      // Emit worker completed
      yield {
        type: EventTypes.WORKER_COMPLETED,
        data: workerResult
      };

      // Emit partial consensus if enabled
      if (emitPartialAfterEach && completedResults.length >= minWorkersForPartial) {
        const partial = calculatePartialConsensus(completedResults, consensusOptions);
        if (partial) {
          yield {
            type: EventTypes.PARTIAL_CONSENSUS,
            data: partial
          };
        }
      }
    } else {
      // Handle error
      errors.push({
        workerId: outcome.workerId,
        model: outcome.model,
        error: outcome.error,
        timestamp: outcome.timestamp
      });

      // Store error in database
      if (db && workflowExecutionId) {
        await db.storeWorkerResult({
          workflow_execution_id: workflowExecutionId,
          worker_id: outcome.workerId,
          model: outcome.model,
          task_assigned: item.worker.task,
          result: null,
          confidence: null,
          duration_ms: null,
          input_tokens: null,
          output_tokens: null,
          cost_usd: null,
          outcome: 'error',
          metadata: { error: outcome.error }
        });
      }

      yield {
        type: EventTypes.ERROR,
        data: {
          workerId: outcome.workerId,
          model: outcome.model,
          error: outcome.error,
          timestamp: outcome.timestamp
        }
      };
    }
  }

  // Emit final consensus
  const final = calculateFinalConsensus(completedResults, consensusOptions);
  if (final) {
    // Store arbiter decision in database
    if (db && workflowExecutionId) {
      await db.storeArbiterDecision({
        workflow_execution_id: workflowExecutionId,
        arbiter_model: 'streaming-consensus',
        decision: JSON.stringify(final.result),
        reasoning: `Consensus from ${final.agreeingWorkers}/${final.totalWorkers} workers (score: ${final.consensusScore.toFixed(3)})`,
        confidence: final.consensusScore,
        input_tokens: null,
        output_tokens: null,
        cost_usd: null
      });
    }

    yield {
      type: EventTypes.FINAL_CONSENSUS,
      data: {
        ...final,
        errors: errors.length > 0 ? errors : undefined
      }
    };
  } else {
    yield {
      type: EventTypes.ERROR,
      data: {
        error: 'No workers completed successfully',
        errors
      }
    };
  }
}

/**
 * EventEmitter-based streaming (for non-async iterator consumers)
 * @param {Array} workers - Worker configurations
 * @param {Object} options - Streaming options
 * @returns {EventEmitter} Event emitter
 */
export function streamConsensusEvents(workers, options = {}) {
  const emitter = new EventEmitter();

  (async () => {
    try {
      for await (const event of streamConsensus(workers, options)) {
        emitter.emit(event.type, event.data);
        emitter.emit('event', event); // Generic event for all types
      }
      emitter.emit('done');
    } catch (error) {
      emitter.emit('error', error);
    }
  })();

  return emitter;
}

/**
 * Convert stream to WebSocket messages
 * @param {WebSocket} ws - WebSocket connection
 * @param {Array} workers - Worker configurations
 * @param {Object} options - Streaming options
 */
export async function streamConsensusToWebSocket(ws, workers, options = {}) {
  try {
    for await (const event of streamConsensus(workers, options)) {
      if (ws.readyState === 1) { // WebSocket.OPEN
        ws.send(JSON.stringify(event));
      }
    }
  } catch (error) {
    if (ws.readyState === 1) {
      ws.send(JSON.stringify({
        type: EventTypes.ERROR,
        data: { error: error.message }
      }));
    }
  }
}

/**
 * Collect all events into array (for testing/debugging)
 * @param {Array} workers - Worker configurations
 * @param {Object} options - Streaming options
 * @returns {Promise<Array>} All events
 */
export async function collectStreamEvents(workers, options = {}) {
  const events = [];
  for await (const event of streamConsensus(workers, options)) {
    events.push(event);
  }
  return events;
}

export default {
  streamConsensus,
  streamConsensusEvents,
  streamConsensusToWebSocket,
  collectStreamEvents,
  EventTypes
};
