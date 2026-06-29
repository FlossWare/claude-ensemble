# Streaming Consensus - Real-Time Consensus Building

**Building Block #8** - Progressive consensus updates with event streaming

## Overview

Stream consensus building in real-time as workers complete their tasks. Emit events for each phase: worker started, worker completed, partial consensus updates, and final consensus. Ideal for long-running workflows where users want progress updates.

## Quick Start

### Basic Usage (Async Iterator)

```javascript
import { streamConsensus, EventTypes } from './shared/streaming-consensus.js';

// Define workers
const workers = [
  { id: 'w1', model: 'opus', task: 'Analyze firmware security' },
  { id: 'w2', model: 'sonnet', task: 'Analyze firmware security' },
  { id: 'w3', model: 'haiku', task: 'Analyze firmware security' },
  { id: 'w4', model: 'gemini', task: 'Analyze firmware security' }
];

// Execute workers and stream events
const stream = streamConsensus(workers, {
  executor: async (worker) => {
    // Your worker execution logic
    const result = await runModel(worker.model, worker.task);
    return {
      result: result.output,
      confidence: result.confidence,
      inputTokens: result.usage.input,
      outputTokens: result.usage.output,
      cost: result.cost
    };
  },
  emitPartialAfterEach: true,
  minWorkersForPartial: 2
});

// Consume events
for await (const event of stream) {
  switch (event.type) {
    case EventTypes.WORKER_STARTED:
      console.log(`🚀 ${event.data.model} started`);
      break;
    
    case EventTypes.WORKER_COMPLETED:
      console.log(`✅ ${event.data.model} completed (${event.data.duration}ms)`);
      break;
    
    case EventTypes.PARTIAL_CONSENSUS:
      console.log(`📊 Partial consensus: ${event.data.completedWorkers}/${workers.length} workers`);
      console.log(`   Score: ${event.data.consensusScore.toFixed(3)}`);
      console.log(`   Agreement: ${(event.data.agreementRatio * 100).toFixed(1)}%`);
      break;
    
    case EventTypes.FINAL_CONSENSUS:
      console.log(`🎯 Final consensus reached`);
      console.log(`   Result: ${JSON.stringify(event.data.result)}`);
      console.log(`   Score: ${event.data.consensusScore.toFixed(3)}`);
      console.log(`   Agreement: ${event.data.agreeingWorkers}/${event.data.totalWorkers} workers`);
      break;
    
    case EventTypes.ERROR:
      console.error(`❌ Error: ${event.data.error}`);
      break;
  }
}
```

### EventEmitter Pattern

```javascript
import { streamConsensusEvents, EventTypes } from './shared/streaming-consensus.js';

const emitter = streamConsensusEvents(workers, {
  executor: async (worker) => { /* ... */ }
});

emitter.on(EventTypes.WORKER_COMPLETED, (data) => {
  console.log(`Worker ${data.workerId} completed`);
});

emitter.on(EventTypes.PARTIAL_CONSENSUS, (data) => {
  updateProgressBar(data.completedWorkers, workers.length);
});

emitter.on(EventTypes.FINAL_CONSENSUS, (data) => {
  showFinalResult(data.result);
});

emitter.on('error', (error) => {
  console.error('Stream error:', error);
});

emitter.on('done', () => {
  console.log('Stream complete');
});
```

### WebSocket Integration

```javascript
import { streamConsensusToWebSocket } from './shared/streaming-consensus.js';
import WebSocket from 'ws';

const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', (ws) => {
  ws.on('message', async (message) => {
    const { workers, options } = JSON.parse(message);
    
    // Stream consensus events to WebSocket client
    await streamConsensusToWebSocket(ws, workers, {
      ...options,
      executor: async (worker) => { /* ... */ }
    });
  });
});
```

## Event Types

### WORKER_STARTED

Emitted when a worker begins execution.

```javascript
{
  type: 'worker_started',
  data: {
    workerId: 'w1',
    model: 'opus',
    task: 'Analyze firmware security',
    timestamp: '2026-06-28T10:30:00.000Z'
  }
}
```

### WORKER_COMPLETED

Emitted when a worker finishes successfully.

```javascript
{
  type: 'worker_completed',
  data: {
    workerId: 'w1',
    model: 'opus',
    task: 'Analyze firmware security',
    result: { /* worker output */ },
    confidence: 0.92,
    duration: 5420,
    inputTokens: 1500,
    outputTokens: 800,
    cost: 0.05,
    timestamp: '2026-06-28T10:30:05.420Z'
  }
}
```

### PARTIAL_CONSENSUS

Emitted after each worker completes (if `emitPartialAfterEach: true`).

```javascript
{
  type: 'partial_consensus',
  data: {
    result: { /* current consensus result */ },
    consensusScore: 0.78,
    agreementRatio: 0.75,        // 3/4 workers agree
    diversity: 0.25,              // 1 dissenting opinion
    avgConfidence: 0.85,
    completedWorkers: 3,
    agreeingWorkers: 3,
    models: ['opus', 'sonnet', 'haiku'],
    isPartial: true
  }
}
```

### FINAL_CONSENSUS

Emitted after all workers complete.

```javascript
{
  type: 'final_consensus',
  data: {
    result: { /* final consensus result */ },
    consensusScore: 0.82,
    agreementRatio: 0.75,
    diversity: 0.25,
    avgConfidence: 0.87,
    completedWorkers: 4,
    agreeingWorkers: 3,
    totalWorkers: 4,
    models: ['opus', 'sonnet', 'haiku'],
    isPartial: false,
    timestamp: '2026-06-28T10:30:15.000Z',
    errors: [ /* optional: any worker errors */ ]
  }
}
```

### ERROR

Emitted when a worker fails.

```javascript
{
  type: 'error',
  data: {
    workerId: 'w4',
    model: 'gemini',
    error: 'API rate limit exceeded',
    timestamp: '2026-06-28T10:30:10.000Z'
  }
}
```

## API Reference

### `streamConsensus(workers, options)`

Main streaming function (async iterator).

**Parameters:**

- `workers` (Array): Worker configurations
  ```javascript
  [
    {
      id: 'worker-1',          // Optional: defaults to worker-${index}
      model: 'opus',
      task: 'Task description',
      // ... any other worker-specific data
    }
  ]
  ```

- `options` (Object):
  - `executor` (Function, **required**): Async function to execute each worker
    ```javascript
    async (worker) => {
      // Execute worker task
      return {
        result: /* worker output */,
        confidence: 0.85,
        inputTokens: 1000,
        outputTokens: 500,
        cost: 0.03
      };
    }
    ```
  
  - `emitPartialAfterEach` (Boolean, default: `true`): Emit partial consensus after each worker completes
  
  - `minWorkersForPartial` (Number, default: `2`): Minimum completed workers before emitting partial consensus
  
  - `storeInDatabase` (Boolean, default: `true`): Store results in PostgreSQL workflow storage
  
  - `workflowExecutionId` (Number, optional): Workflow execution ID for database storage
  
  - `consensusThreshold` (Number, default: `0.6`): Minimum score to accept consensus
  
  - `diversityWeight` (Number, default: `0.3`): Weight for diversity in consensus scoring
  
  - `confidenceWeight` (Number, default: `0.7`): Weight for confidence in consensus scoring

**Returns:** AsyncIterator yielding events

### `streamConsensusEvents(workers, options)`

EventEmitter-based streaming (same options as `streamConsensus`).

**Returns:** EventEmitter

**Events:**
- `worker_started` - Worker begins
- `worker_completed` - Worker finishes
- `partial_consensus` - Intermediate consensus
- `final_consensus` - Complete consensus
- `error` - Worker or stream error
- `event` - Generic event (all types)
- `done` - Stream complete

### `streamConsensusToWebSocket(ws, workers, options)`

Stream events to WebSocket connection.

**Parameters:**
- `ws` (WebSocket): WebSocket connection
- `workers` (Array): Worker configurations
- `options` (Object): Same as `streamConsensus`

**Returns:** Promise (resolves when stream completes)

### `collectStreamEvents(workers, options)`

Collect all events into array (for testing/debugging).

**Parameters:** Same as `streamConsensus`

**Returns:** Promise<Array> of all events

## Consensus Scoring

The consensus score is calculated using a weighted formula:

```
consensusScore = (
  (agreementRatio × (1 - diversityWeight)) +
  (avgConfidence × confidenceWeight) +
  (diversity × diversityWeight)
) / (1 + confidenceWeight)
```

**Components:**

- **Agreement Ratio**: Percentage of workers agreeing on the consensus result (0-1)
- **Average Confidence**: Mean confidence score from agreeing workers (0-1)
- **Diversity**: Ratio of unique opinions to total workers (0-1)

**Weights:**

- `diversityWeight` (default: 0.3): Higher values favor diverse opinions
- `confidenceWeight` (default: 0.7): Higher values favor high-confidence results

**Tuning Tips:**

- **High-stakes decisions**: Increase `consensusThreshold` to 0.8+
- **Exploratory research**: Increase `diversityWeight` to 0.5+
- **Fast decisions**: Lower `minWorkersForPartial` to 1 or 2
- **Quality over speed**: Disable `emitPartialAfterEach` and wait for final consensus

## Database Integration

When `storeInDatabase: true` and `workflowExecutionId` is provided, streaming consensus automatically stores:

1. **Worker Results** → `workflow.worker_results` table
2. **Arbiter Decision** → `workflow.arbiter_decisions` table (final consensus)
3. **Error Metadata** → `workflow.worker_results.metadata` (on failure)

**Schema:**

```sql
-- Worker results stored automatically
SELECT worker_id, model, result, confidence, duration_ms, cost_usd
FROM workflow.worker_results
WHERE workflow_execution_id = 123
ORDER BY created_at;

-- Final consensus stored as arbiter decision
SELECT decision, reasoning, confidence
FROM workflow.arbiter_decisions
WHERE workflow_execution_id = 123;
```

**Usage:**

```javascript
// Create workflow execution
const db = getWorkflowStorage();
const execId = await db.storeExecution({
  workflow_id: 'wf-' + Date.now(),
  workflow_name: 'streaming-consensus-demo',
  task_description: 'Analyze firmware security',
  total_workers: 4
});

// Stream with database storage
for await (const event of streamConsensus(workers, {
  executor: async (worker) => { /* ... */ },
  storeInDatabase: true,
  workflowExecutionId: execId
})) {
  // Events are automatically stored in database
}
```

## Error Handling

Streaming consensus uses `Promise.allSettled()` to handle worker failures gracefully:

- **Failed workers** emit `ERROR` events but don't stop the stream
- **Partial consensus** calculated from successful workers only
- **Final consensus** includes `errors` array if any workers failed

**Example:**

```javascript
for await (const event of stream) {
  if (event.type === EventTypes.FINAL_CONSENSUS) {
    if (event.data.errors && event.data.errors.length > 0) {
      console.warn(`${event.data.errors.length} workers failed:`);
      event.data.errors.forEach(err => {
        console.warn(`  - ${err.model}: ${err.error}`);
      });
    }
    
    // Check if consensus is still valid
    if (event.data.consensusScore >= 0.6) {
      console.log('Consensus valid despite failures');
    } else {
      console.error('Insufficient consensus due to failures');
    }
  }
}
```

## Performance Considerations

### Parallelism

Workers execute in parallel using `Promise.allSettled()`. All workers start immediately, events stream as they complete.

**Execution Timeline:**

```
t=0s:   All workers start
t=2s:   Worker 3 completes → WORKER_COMPLETED, PARTIAL_CONSENSUS
t=4s:   Worker 1 completes → WORKER_COMPLETED, PARTIAL_CONSENSUS
t=5s:   Worker 2 completes → WORKER_COMPLETED, PARTIAL_CONSENSUS
t=7s:   Worker 4 completes → WORKER_COMPLETED, FINAL_CONSENSUS
```

### Memory Usage

Streaming consensus holds completed results in memory until final consensus. For large result sets:

- Use `emitPartialAfterEach: false` to reduce event overhead
- Process partial consensus events immediately (don't accumulate)
- Consider pagination for 100+ workers

### Network Efficiency

**WebSocket Mode:**
- Events sent as JSON-serialized messages
- Client receives real-time updates (no polling)
- Automatic reconnection logic recommended

**Long-Polling Alternative:**
```javascript
// Collect events server-side, poll periodically
let lastEventIndex = 0;
const allEvents = await collectStreamEvents(workers, options);

// Client polls: GET /events?since=5
app.get('/events', (req, res) => {
  const since = parseInt(req.query.since) || 0;
  res.json(allEvents.slice(since));
});
```

## Testing

See `shared/streaming-consensus.test.cjs` for comprehensive test suite.

**Run tests:**

```bash
node shared/streaming-consensus.test.cjs
```

**Coverage:**
- Basic event streaming
- Partial consensus updates
- Final consensus calculation
- Error handling (worker failures)
- EventEmitter pattern
- Database integration
- WebSocket simulation

## Use Cases

### 1. Real-Time Dashboard

```javascript
// Server: Stream to WebSocket
wss.on('connection', (ws) => {
  streamConsensusToWebSocket(ws, workers, { executor });
});

// Client: Update UI in real-time
ws.onmessage = (msg) => {
  const event = JSON.parse(msg.data);
  switch (event.type) {
    case 'worker_completed':
      updateWorkerStatus(event.data.workerId, 'complete');
      break;
    case 'partial_consensus':
      updateConsensusScore(event.data.consensusScore);
      updateProgressBar(event.data.completedWorkers);
      break;
  }
};
```

### 2. Early Termination

```javascript
for await (const event of stream) {
  if (event.type === EventTypes.PARTIAL_CONSENSUS) {
    // Stop early if strong consensus reached
    if (event.data.consensusScore > 0.9 && 
        event.data.agreementRatio > 0.8) {
      console.log('Strong consensus reached early, stopping');
      break;
    }
  }
}
```

### 3. Adaptive Worker Spawning

```javascript
const initialWorkers = [/* 3 workers */];
let additionalWorkers = [];

for await (const event of streamConsensus(initialWorkers, options)) {
  if (event.type === EventTypes.PARTIAL_CONSENSUS) {
    // Spawn more workers if consensus is weak
    if (event.data.consensusScore < 0.5 && 
        event.data.completedWorkers === initialWorkers.length) {
      console.log('Weak consensus, spawning additional workers');
      additionalWorkers = [/* 2 more workers */];
      // Start new stream with additional workers
    }
  }
}
```

### 4. Progress Notifications

```javascript
import { EventEmitter } from 'events';

async function runWithProgress(workers, executor) {
  const progress = new EventEmitter();
  
  // Background streaming
  (async () => {
    for await (const event of streamConsensus(workers, { executor })) {
      if (event.type === EventTypes.WORKER_COMPLETED) {
        progress.emit('progress', {
          completed: event.data.workerId,
          total: workers.length
        });
      } else if (event.type === EventTypes.FINAL_CONSENSUS) {
        progress.emit('complete', event.data);
      }
    }
  })();
  
  return progress;
}

// Usage
const progress = await runWithProgress(workers, executor);
progress.on('progress', ({ completed, total }) => {
  console.log(`Progress: ${completed}/${total}`);
});
progress.on('complete', (result) => {
  console.log('Done:', result);
});
```

## Integration with Other Building Blocks

### With Adaptive Routing (#1)

```javascript
import { AdaptiveRouter } from './shared/adaptive-routing.js';
import { streamConsensus } from './shared/streaming-consensus.js';

const router = new AdaptiveRouter();

const stream = streamConsensus(workers, {
  executor: async (worker) => {
    // Use adaptive routing to select best model
    const model = await router.selectModel({
      taskType: worker.task,
      constraints: { maxLatency: 5000 }
    });
    return await executeWithModel(model, worker);
  }
});
```

### With Democratic Consensus (#7)

```javascript
import { democraticConsensus } from './shared/democratic-consensus.js';
import { streamConsensus } from './shared/streaming-consensus.js';

// Stream worker execution, then run democratic vote
const workerResults = [];

for await (const event of streamConsensus(workers, { executor })) {
  if (event.type === EventTypes.WORKER_COMPLETED) {
    workerResults.push(event.data);
  } else if (event.type === EventTypes.FINAL_CONSENSUS) {
    // Run democratic vote on collected results
    const democraticResult = await democraticConsensus(workerResults, {
      votingMethod: 'borda',
      modelWeights: { opus: 1.2, sonnet: 1.0, haiku: 0.8 }
    });
    console.log('Democratic consensus:', democraticResult);
  }
}
```

### With Cost Optimization (#2)

```javascript
import { CostOptimizer } from './shared/cost-optimizer.js';
import { streamConsensus } from './shared/streaming-consensus.js';

const costOpt = new CostOptimizer({ dailyBudget: 50 });

const stream = streamConsensus(workers, {
  executor: async (worker) => {
    // Check budget before executing
    const canExecute = await costOpt.canExecute(worker.model, estimatedTokens);
    if (!canExecute) {
      throw new Error('Budget exceeded');
    }
    
    const result = await executeWorker(worker);
    
    // Track cost in real-time
    await costOpt.trackExecution({
      model: worker.model,
      cost: result.cost
    });
    
    return result;
  }
});
```

## Troubleshooting

### Partial consensus not emitting

**Symptom:** Only `WORKER_STARTED`, `WORKER_COMPLETED`, and `FINAL_CONSENSUS` events.

**Fix:** Check `minWorkersForPartial` - need at least this many workers completed before partial consensus emits.

```javascript
streamConsensus(workers, {
  minWorkersForPartial: 1,  // Emit after first worker
  emitPartialAfterEach: true
});
```

### Events not streaming in real-time

**Symptom:** All events arrive at once after all workers complete.

**Fix:** Ensure you're using async iteration (`for await`) correctly:

```javascript
// ✅ Correct: streams in real-time
for await (const event of stream) {
  console.log(event);
}

// ❌ Wrong: waits for all events
const events = await Promise.all([...stream]);
```

### Database storage not working

**Symptom:** Events stream correctly but nothing in database.

**Fix:** Ensure `workflowExecutionId` is provided:

```javascript
const db = getWorkflowStorage();
const execId = await db.storeExecution({ /* ... */ });

streamConsensus(workers, {
  storeInDatabase: true,
  workflowExecutionId: execId  // Required!
});
```

### WebSocket disconnects during stream

**Symptom:** WebSocket closes before final consensus.

**Fix:** Add connection keepalive and error handling:

```javascript
ws.on('error', (error) => {
  console.error('WebSocket error:', error);
});

ws.on('close', () => {
  console.log('WebSocket closed, client may have disconnected');
});

// Send periodic pings
const pingInterval = setInterval(() => {
  if (ws.readyState === 1) {
    ws.ping();
  } else {
    clearInterval(pingInterval);
  }
}, 30000);
```

## License

MIT

## Related Documentation

- [Workflow Storage and Analytics](../README.md#workflow-storage-and-analytics)
- [Building Block #1: Adaptive Routing](./ADAPTIVE-ROUTING-README.md)
- [Building Block #2: Cost Optimization](./COST-OPTIMIZATION-README.md)
- [Building Block #7: Democratic Consensus](./DEMOCRATIC-CONSENSUS-README.md)
