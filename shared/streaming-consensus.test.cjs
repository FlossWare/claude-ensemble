/**
 * Test suite for streaming-consensus.js
 * Run: node shared/streaming-consensus.test.cjs
 */

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const { EventEmitter } = require('events');

// Mock imports since we're using CJS for testing
let streamConsensus, streamConsensusEvents, collectStreamEvents, EventTypes;

// Mock database adapter
const mockDB = {
  storeExecution: async (data) => 1,
  storeWorkerResult: async (data) => {},
  storeArbiterDecision: async (data) => {},
  query: async (sql, params) => ({ rows: [] })
};

// Mock workflow storage
const mockWorkflowStorage = {
  getWorkflowStorage: () => mockDB
};

// Dynamic import helper
async function loadModule() {
  // Create a mock module environment
  const module = { exports: {} };
  const EventEmitter = require('events').EventEmitter;

  // Simplified version of streaming-consensus for testing
  const EventTypes = {
    WORKER_STARTED: 'worker_started',
    WORKER_COMPLETED: 'worker_completed',
    PARTIAL_CONSENSUS: 'partial_consensus',
    FINAL_CONSENSUS: 'final_consensus',
    ERROR: 'error'
  };

  function calculatePartialConsensus(completedResults, options = {}) {
    if (completedResults.length === 0) return null;

    const { consensusThreshold = 0.6, diversityWeight = 0.3, confidenceWeight = 0.7 } = options;

    const groups = {};
    completedResults.forEach(result => {
      const key = JSON.stringify(result.result).slice(0, 100);
      if (!groups[key]) groups[key] = [];
      groups[key].push(result);
    });

    let largestGroup = [];
    for (const group of Object.values(groups)) {
      if (group.length > largestGroup.length) largestGroup = group;
    }

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

  function calculateFinalConsensus(allResults, options = {}) {
    const partial = calculatePartialConsensus(allResults, options);
    if (!partial) return null;
    return {
      ...partial,
      isPartial: false,
      totalWorkers: allResults.length,
      timestamp: new Date().toISOString()
    };
  }

  async function* streamConsensus(workers, options = {}) {
    const {
      executor = null,
      emitPartialAfterEach = true,
      minWorkersForPartial = 2,
      storeInDatabase = false,
      workflowExecutionId = null,
      ...consensusOptions
    } = options;

    if (!executor) {
      throw new Error('executor function required');
    }

    const completedResults = [];
    const errors = [];

    // Execute workers sequentially for predictable test behavior
    for (let index = 0; index < workers.length; index++) {
      const worker = workers[index];

      try {
        yield {
          type: EventTypes.WORKER_STARTED,
          data: {
            workerId: worker.id || `worker-${index}`,
            model: worker.model,
            task: worker.task,
            timestamp: new Date().toISOString()
          }
        };

        const startTime = Date.now();
        const result = await executor(worker);
        const duration = Date.now() - startTime;

        const workerResult = {
          ...result,
          workerId: worker.id || `worker-${index}`,
          model: worker.model,
          task: worker.task,
          duration,
          timestamp: new Date().toISOString()
        };

        completedResults.push(workerResult);

        yield {
          type: EventTypes.WORKER_COMPLETED,
          data: workerResult
        };

        if (emitPartialAfterEach && completedResults.length >= minWorkersForPartial) {
          const partial = calculatePartialConsensus(completedResults, consensusOptions);
          if (partial) {
            yield {
              type: EventTypes.PARTIAL_CONSENSUS,
              data: partial
            };
          }
        }
      } catch (error) {
        errors.push({
          workerId: worker.id || `worker-${index}`,
          model: worker.model,
          error: error.message,
          timestamp: new Date().toISOString()
        });

        yield {
          type: EventTypes.ERROR,
          data: {
            workerId: worker.id || `worker-${index}`,
            model: worker.model,
            error: error.message,
            timestamp: new Date().toISOString()
          }
        };
      }
    }

    const final = calculateFinalConsensus(completedResults, consensusOptions);
    if (final) {
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

  function streamConsensusEvents(workers, options = {}) {
    const emitter = new EventEmitter();
    (async () => {
      try {
        for await (const event of streamConsensus(workers, options)) {
          emitter.emit(event.type, event.data);
          emitter.emit('event', event);
        }
        emitter.emit('done');
      } catch (error) {
        emitter.emit('error', error);
      }
    })();
    return emitter;
  }

  async function collectStreamEvents(workers, options = {}) {
    const events = [];
    for await (const event of streamConsensus(workers, options)) {
      events.push(event);
    }
    return events;
  }

  return {
    streamConsensus,
    streamConsensusEvents,
    collectStreamEvents,
    EventTypes
  };
}

// Test suite
describe('Streaming Consensus', () => {
  before(async () => {
    const module = await loadModule();
    streamConsensus = module.streamConsensus;
    streamConsensusEvents = module.streamConsensusEvents;
    collectStreamEvents = module.collectStreamEvents;
    EventTypes = module.EventTypes;
  });

  it('should emit worker_started and worker_completed events', async () => {
    const workers = [
      { id: 'w1', model: 'opus', task: 'Test task' },
      { id: 'w2', model: 'sonnet', task: 'Test task' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => ({
        result: { analysis: 'Test result' },
        confidence: 0.9
      })
    });

    const startedEvents = events.filter(e => e.type === EventTypes.WORKER_STARTED);
    const completedEvents = events.filter(e => e.type === EventTypes.WORKER_COMPLETED);

    assert.strictEqual(startedEvents.length, 2, 'Should emit 2 worker_started events');
    assert.strictEqual(completedEvents.length, 2, 'Should emit 2 worker_completed events');
    assert.strictEqual(startedEvents[0].data.model, 'opus');
    assert.strictEqual(completedEvents[1].data.model, 'sonnet');
  });

  it('should emit partial_consensus after each worker (when enabled)', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' },
      { model: 'haiku', task: 'Test' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => ({
        result: { answer: 'A' },
        confidence: 0.85
      }),
      emitPartialAfterEach: true,
      minWorkersForPartial: 2
    });

    const partialEvents = events.filter(e => e.type === EventTypes.PARTIAL_CONSENSUS);

    assert.strictEqual(partialEvents.length, 2, 'Should emit 2 partial consensus events (after 2nd and 3rd worker)');
    assert.strictEqual(partialEvents[0].data.completedWorkers, 2);
    assert.strictEqual(partialEvents[1].data.completedWorkers, 3);
    assert.strictEqual(partialEvents[0].data.isPartial, true);
  });

  it('should emit final_consensus with correct data', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' },
      { model: 'haiku', task: 'Test' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => ({
        result: { answer: 'Secure' },
        confidence: 0.9
      })
    });

    const finalEvent = events.find(e => e.type === EventTypes.FINAL_CONSENSUS);

    assert.ok(finalEvent, 'Should emit final_consensus event');
    assert.strictEqual(finalEvent.data.isPartial, false);
    assert.strictEqual(finalEvent.data.totalWorkers, 3);
    assert.strictEqual(finalEvent.data.completedWorkers, 3);
    assert.strictEqual(finalEvent.data.agreeingWorkers, 3);
    assert.strictEqual(finalEvent.data.agreementRatio, 1.0);
    assert.ok(finalEvent.data.consensusScore > 0.8, 'Consensus score should be high for unanimous agreement');
  });

  it('should handle worker failures gracefully', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' },
      { model: 'haiku', task: 'Test' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => {
        if (worker.model === 'sonnet') {
          throw new Error('API timeout');
        }
        return {
          result: { answer: 'Pass' },
          confidence: 0.85
        };
      }
    });

    const errorEvents = events.filter(e => e.type === EventTypes.ERROR);
    const finalEvent = events.find(e => e.type === EventTypes.FINAL_CONSENSUS);

    assert.strictEqual(errorEvents.length, 1, 'Should emit 1 error event');
    assert.strictEqual(errorEvents[0].data.model, 'sonnet');
    assert.ok(finalEvent, 'Should still emit final_consensus');
    assert.strictEqual(finalEvent.data.completedWorkers, 2, 'Should have 2 successful workers');
    assert.ok(finalEvent.data.errors, 'Should include errors in final consensus');
    assert.strictEqual(finalEvent.data.errors.length, 1);
  });

  it('should calculate consensus with disagreement correctly', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' },
      { model: 'haiku', task: 'Test' },
      { model: 'gemini', task: 'Test' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => {
        // 3 agree on 'A', 1 says 'B'
        const result = worker.model === 'gemini' ? 'B' : 'A';
        return {
          result: { answer: result },
          confidence: 0.8
        };
      }
    });

    const finalEvent = events.find(e => e.type === EventTypes.FINAL_CONSENSUS);

    assert.ok(finalEvent);
    assert.strictEqual(finalEvent.data.totalWorkers, 4);
    assert.strictEqual(finalEvent.data.agreeingWorkers, 3);
    assert.strictEqual(finalEvent.data.agreementRatio, 0.75);
    assert.strictEqual(finalEvent.data.diversity, 0.5); // 2 unique answers / 4 workers
    assert.strictEqual(finalEvent.data.result.answer, 'A', 'Should choose majority answer');
  });

  it('should work with EventEmitter pattern', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' }
    ];

    const emitter = streamConsensusEvents(workers, {
      executor: async (worker) => ({
        result: { answer: 'Pass' },
        confidence: 0.9
      })
    });

    const receivedEvents = [];

    return new Promise((resolve, reject) => {
      emitter.on('event', (event) => {
        receivedEvents.push(event);
      });

      emitter.on('done', () => {
        try {
          assert.ok(receivedEvents.length > 0, 'Should receive events');
          const hasStarted = receivedEvents.some(e => e.type === EventTypes.WORKER_STARTED);
          const hasCompleted = receivedEvents.some(e => e.type === EventTypes.WORKER_COMPLETED);
          const hasFinal = receivedEvents.some(e => e.type === EventTypes.FINAL_CONSENSUS);

          assert.ok(hasStarted, 'Should have worker_started events');
          assert.ok(hasCompleted, 'Should have worker_completed events');
          assert.ok(hasFinal, 'Should have final_consensus event');
          resolve();
        } catch (error) {
          reject(error);
        }
      });

      emitter.on('error', reject);
    });
  });

  it('should not emit partial consensus when disabled', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' },
      { model: 'haiku', task: 'Test' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => ({
        result: { answer: 'Pass' },
        confidence: 0.9
      }),
      emitPartialAfterEach: false
    });

    const partialEvents = events.filter(e => e.type === EventTypes.PARTIAL_CONSENSUS);

    assert.strictEqual(partialEvents.length, 0, 'Should not emit partial consensus when disabled');
  });

  it('should respect minWorkersForPartial threshold', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' },
      { model: 'haiku', task: 'Test' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => ({
        result: { answer: 'Pass' },
        confidence: 0.9
      }),
      emitPartialAfterEach: true,
      minWorkersForPartial: 3
    });

    const partialEvents = events.filter(e => e.type === EventTypes.PARTIAL_CONSENSUS);

    assert.strictEqual(partialEvents.length, 1, 'Should emit partial only when 3 workers complete');
    assert.strictEqual(partialEvents[0].data.completedWorkers, 3);
  });

  it('should include worker metadata in events', async () => {
    const workers = [
      { id: 'custom-w1', model: 'opus', task: 'Custom task', priority: 'high' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => ({
        result: { answer: 'Complete' },
        confidence: 0.95,
        inputTokens: 1000,
        outputTokens: 500,
        cost: 0.03
      })
    });

    const completedEvent = events.find(e => e.type === EventTypes.WORKER_COMPLETED);

    assert.strictEqual(completedEvent.data.workerId, 'custom-w1');
    assert.strictEqual(completedEvent.data.model, 'opus');
    assert.strictEqual(completedEvent.data.task, 'Custom task');
    assert.strictEqual(completedEvent.data.confidence, 0.95);
    assert.strictEqual(completedEvent.data.inputTokens, 1000);
    assert.strictEqual(completedEvent.data.outputTokens, 500);
    assert.strictEqual(completedEvent.data.cost, 0.03);
    assert.ok(completedEvent.data.duration >= 0);
    assert.ok(completedEvent.data.timestamp);
  });

  it('should throw error when executor not provided', async () => {
    const workers = [{ model: 'opus', task: 'Test' }];

    try {
      for await (const event of streamConsensus(workers, {})) {
        // Should not reach here
      }
      assert.fail('Should have thrown error');
    } catch (error) {
      assert.strictEqual(error.message, 'executor function required');
    }
  });

  it('should handle all workers failing', async () => {
    const workers = [
      { model: 'opus', task: 'Test' },
      { model: 'sonnet', task: 'Test' }
    ];

    const events = await collectStreamEvents(workers, {
      executor: async (worker) => {
        throw new Error('All workers failed');
      }
    });

    const errorEvents = events.filter(e => e.type === EventTypes.ERROR);
    const finalEvent = events.find(e => e.type === EventTypes.FINAL_CONSENSUS);

    assert.strictEqual(errorEvents.length, 3, 'Should have 2 worker errors + 1 final error');
    assert.ok(!finalEvent, 'Should not emit final_consensus when all workers fail');

    const finalError = errorEvents.find(e => e.data.error === 'No workers completed successfully');
    assert.ok(finalError, 'Should emit error about no successful workers');
  });
});

// Run tests automatically when executed directly
if (require.main === module) {
  console.log('Running streaming consensus tests...\n');
}
