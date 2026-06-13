# Remote Result Streaming Design

## Executive Summary

Design for streaming incremental results from remote fleet execution to provide real-time visibility into long-running agent tasks. This enables progress tracking, early error detection, and improved user experience without waiting for complete task execution.

**Current State**: RemoteExecutor uses SSH + `claude -p` with blocking execution that returns only final results.

**Target State**: Stream partial results, logs, and progress updates as they occur on remote servers.

---

## Architecture Overview

### Current Flow (Blocking)
```
Workflow → RemoteExecutor.execute()
          ↓
       SSH + claude -p (waits)
          ↓
       Parse full JSON output
          ↓
       Return {result, cost, duration}
```

### Proposed Flow (Streaming)
```
Workflow → RemoteExecutor.executeStreaming()
          ↓
       SSH + claude -p --output-format json-stream
          ↓
       Stream handler (EventEmitter/AsyncIterator)
          ├─ emit('log', {message, timestamp})
          ├─ emit('progress', {phase, percent})
          ├─ emit('partial', {data})
          └─ emit('complete', {result, cost, duration})
          ↓
       Caller consumes events
```

---

## Design Approaches

### Approach 1: Progressive JSON Line Protocol (RECOMMENDED)

**Description**: Claude outputs newline-delimited JSON (NDJSON) to stdout, each line representing a discrete event.

**Event Format**:
```json
{"type":"log","timestamp":"2026-06-13T12:00:00Z","message":"Starting analysis..."}
{"type":"progress","phase":"parse","percent":25,"detail":"Analyzing 50 files"}
{"type":"partial","data":{"files_processed":10,"issues_found":2}}
{"type":"result","subtype":"success","cost_usd":0.05,"duration_ms":5000,"result":"..."}
```

**RemoteExecutor Integration**:
```javascript
async executeStreaming(server, model, prompt, opts = {}) {
  const { onLog, onProgress, onPartial, jobId = ... } = opts;
  
  // Build SSH command with --output-format json-stream
  const command = await this.buildStreamingCommand(server, prompt, model, jobId);
  
  return new Promise((resolve, reject) => {
    const proc = spawn('ssh', [
      ...SSH_OPTS.split(' '),
      `-o ConnectTimeout=${this.sshTimeoutSec}`,
      server,
      command
    ], { stdio: ['ignore', 'pipe', 'pipe'] });
    
    let buffer = '';
    let finalResult = null;
    
    proc.stdout.on('data', (chunk) => {
      buffer += chunk.toString();
      
      // Process complete lines
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (!line.trim()) continue;
        
        try {
          const event = JSON.parse(line);
          
          switch (event.type) {
            case 'log':
              onLog?.(event);
              break;
            case 'progress':
              onProgress?.(event);
              break;
            case 'partial':
              onPartial?.(event.data);
              break;
            case 'result':
              finalResult = this.parseClaudeOutput(JSON.stringify(event), opts.schema);
              break;
          }
        } catch (e) {
          // Skip malformed lines (bash completion messages, etc.)
          continue;
        }
      }
    });
    
    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Remote execution failed with code ${code}`));
      } else if (finalResult) {
        resolve(finalResult);
      } else {
        reject(new Error('No result received from remote execution'));
      }
    });
    
    // Timeout handling (AbortController)
    const timeout = setTimeout(() => {
      proc.kill('SIGTERM');
      reject(new Error(`Execution timeout after ${opts.timeoutMs}ms`));
    }, opts.timeoutMs || 180000);
    
    proc.on('close', () => clearTimeout(timeout));
  });
}
```

**Advantages**:
- Simple protocol: newline-delimited JSON
- Backward compatible: falls back to buffering if `--output-format json-stream` not supported
- No additional infrastructure needed
- Works over SSH stdout naturally
- Easy to parse incrementally

**Disadvantages**:
- Requires Claude CLI support for `--output-format json-stream` flag
- Limited to stdout bandwidth (not a real issue for text)
- No backpressure mechanism

---

### Approach 2: Server-Sent Events (SSE) via HTTP Proxy

**Description**: Fleet dispatcher acts as HTTP proxy to remote execution, streaming SSE events.

**Flow**:
```
Workflow → HTTP GET /agent/execute-stream?job_id=...
          ↓
       Fleet Dispatcher (pi-02:3004)
          ↓
       SSH to selected server, spawn claude -p
          ↓
       Parse stdout, emit SSE events
          ↓
       Client receives text/event-stream
```

**Event Format**:
```
event: log
data: {"message":"Starting analysis...","timestamp":"2026-06-13T12:00:00Z"}

event: progress
data: {"phase":"parse","percent":25}

event: partial
data: {"files_processed":10,"issues_found":2}

event: result
data: {"result":"...","cost_usd":0.05,"duration_ms":5000}
```

**Dispatcher Implementation**:
```javascript
// In fleet dispatcher (pi-02:3004)
app.get('/agent/execute-stream', async (req, res) => {
  const { job_id, server, model, prompt } = req.query;
  
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  
  const executor = new RemoteExecutor();
  
  await executor.executeStreaming(server, model, prompt, {
    jobId: job_id,
    onLog: (event) => {
      res.write(`event: log\ndata: ${JSON.stringify(event)}\n\n`);
    },
    onProgress: (event) => {
      res.write(`event: progress\ndata: ${JSON.stringify(event)}\n\n`);
    },
    onPartial: (data) => {
      res.write(`event: partial\ndata: ${JSON.stringify(data)}\n\n`);
    }
  }).then(result => {
    res.write(`event: result\ndata: ${JSON.stringify(result)}\n\n`);
    res.end();
  }).catch(error => {
    res.write(`event: error\ndata: ${JSON.stringify({message: error.message})}\n\n`);
    res.end();
  });
});
```

**Client Consumption**:
```javascript
// In fleet-utils.js or workflow
async function streamRemoteAgent(server, model, prompt, callbacks) {
  const response = await fetch(
    `${FLEET_DISPATCHER}/agent/execute-stream?` + 
    new URLSearchParams({ server, model, prompt: prompt.slice(0, 200), job_id: ... })
  );
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    
    // Parse SSE events
    const events = buffer.split('\n\n');
    buffer = events.pop(); // Keep incomplete event
    
    for (const eventText of events) {
      const [eventLine, dataLine] = eventText.split('\n');
      if (!eventLine?.startsWith('event:') || !dataLine?.startsWith('data:')) continue;
      
      const eventType = eventLine.slice(7).trim();
      const data = JSON.parse(dataLine.slice(6));
      
      switch (eventType) {
        case 'log':
          callbacks.onLog?.(data);
          break;
        case 'progress':
          callbacks.onProgress?.(data);
          break;
        case 'partial':
          callbacks.onPartial?.(data);
          break;
        case 'result':
          return data;
        case 'error':
          throw new Error(data.message);
      }
    }
  }
}
```

**Advantages**:
- Standard HTTP protocol (SSE)
- Centralizes streaming logic in dispatcher
- Client-side EventSource API support (browser)
- Automatic reconnection support
- Works through firewalls/proxies

**Disadvantages**:
- Requires dispatcher infrastructure
- Additional network hop (client → dispatcher → remote)
- More complex error handling
- Dispatcher becomes single point of failure for streaming

---

### Approach 3: WebSocket Bidirectional Channel

**Description**: Establish WebSocket connection for full-duplex communication between workflow and remote execution.

**Use Cases**:
- Interactive agents that need user input during execution
- Real-time steering/cancellation of long-running tasks
- Multi-stage workflows with intermediate checkpoints

**Flow**:
```
Workflow → WebSocket /agent/ws?job_id=...
          ↓
       Fleet Dispatcher maintains WS connection
          ↓
       Bidirectional message exchange:
          client → server: {"type":"start","model":"opus","prompt":"..."}
          server → client: {"type":"log","message":"..."}
          server → client: {"type":"progress","percent":25}
          client → server: {"type":"cancel"}
          server → client: {"type":"result","data":"..."}
```

**Advantages**:
- Full bidirectional communication
- Can send control messages (cancel, pause, resume)
- Lower latency than HTTP polling
- Efficient for high-frequency updates

**Disadvantages**:
- More complex protocol
- Requires WebSocket infrastructure
- Connection state management
- Harder to debug than HTTP

---

## Recommended Implementation Plan

### Phase 1: Progressive JSON Line Protocol (Approach 1)
**Timeline**: 1-2 weeks

1. **Extend Claude CLI Support** (if needed)
   - Add `--output-format json-stream` flag
   - Emit NDJSON events during execution
   - Ensure backward compatibility

2. **Update RemoteExecutor**
   - Add `executeStreaming()` method
   - Implement spawn-based SSH execution (replace exec)
   - Add event callbacks: `onLog`, `onProgress`, `onPartial`
   - Maintain backward compatibility with `execute()` (non-streaming)

3. **Update fleet-agent-wrapper.js**
   - Add streaming option to `createFleetAgent()`
   - Pass callbacks through to RemoteExecutor
   - Emit workflow log() calls from stream events

4. **Workflow Integration**
   - Modify workflows to use streaming agent calls
   - Example: `agent(prompt, { streaming: true, onProgress: (p) => log(`Progress: ${p.percent}%`) })`

### Phase 2: SSE HTTP Proxy (Approach 2)
**Timeline**: 2-3 weeks

1. **Fleet Dispatcher Enhancement**
   - Add `/agent/execute-stream` endpoint
   - Implement SSE event streaming
   - Handle remote execution lifecycle

2. **Client Library Update**
   - Add `streamRemoteAgent()` to fleet-utils.js
   - Implement SSE parsing
   - Handle reconnection logic

3. **Monitoring & Telemetry**
   - Track streaming connection metrics
   - Monitor event delivery latency
   - Alert on stream interruptions

### Phase 3: WebSocket (Optional)
**Timeline**: 3-4 weeks

Only if bidirectional control is required for advanced use cases.

---

## Implementation Details

### Event Schema

#### Log Event
```typescript
interface LogEvent {
  type: 'log';
  timestamp: string;  // ISO 8601
  level: 'debug' | 'info' | 'warn' | 'error';
  message: string;
  source?: 'agent' | 'workflow' | 'remote-executor';
}
```

#### Progress Event
```typescript
interface ProgressEvent {
  type: 'progress';
  phase: string;           // e.g., 'analyze', 'execute', 'synthesize'
  percent: number;         // 0-100
  detail?: string;         // Human-readable description
  eta_seconds?: number;    // Estimated time remaining
}
```

#### Partial Result Event
```typescript
interface PartialEvent {
  type: 'partial';
  data: any;              // Schema-dependent partial result
  sequence?: number;      // Order of partial results
  merge_strategy?: 'append' | 'replace' | 'merge';
}
```

#### Final Result Event
```typescript
interface ResultEvent {
  type: 'result';
  subtype: 'success' | 'error';
  result: any;
  cost_usd: number;
  duration_ms: number;
  num_turns?: number;
  session_id?: string;
  is_error: boolean;
}
```

### Backward Compatibility

**Non-streaming execution** (current behavior):
```javascript
// Works as today
const result = await executor.execute(server, model, prompt, { jobId, timeoutMs, schema });
```

**Streaming execution** (new):
```javascript
// New streaming API
const result = await executor.executeStreaming(server, model, prompt, {
  jobId,
  timeoutMs,
  schema,
  onLog: (event) => console.log(event.message),
  onProgress: (event) => console.log(`${event.phase}: ${event.percent}%`),
  onPartial: (data) => console.log('Partial:', data)
});
```

**Auto-detection**:
```javascript
// Wrapper automatically uses streaming if callbacks provided
const agent = createFleetAgent(originalAgent, {
  enableStreaming: true,
  onProgress: (p) => log(`Progress: ${p.percent}%`)
});
```

### Error Handling

**Stream Interruption**:
- Network failure mid-stream → retry logic (reconnect SSE, re-establish SSH)
- Timeout during stream → partial results saved, timeout error thrown
- Malformed event → skip event, log warning, continue processing

**Graceful Degradation**:
```javascript
try {
  const result = await executor.executeStreaming(server, model, prompt, {
    onLog, onProgress, onPartial
  });
} catch (error) {
  if (error.code === 'STREAMING_NOT_SUPPORTED') {
    // Fall back to non-streaming execution
    console.warn('Streaming not supported, falling back to blocking execution');
    const result = await executor.execute(server, model, prompt, opts);
  } else {
    throw error;
  }
}
```

---

## Performance Considerations

### Bandwidth
- Average event size: ~200 bytes (JSON)
- Event frequency: 1-10 events/second (log + progress)
- Total overhead: ~2KB/second per stream
- Acceptable for SSH (typically 1+ Mbps)

### Latency
- SSH baseline: 5-20ms (LAN)
- Event propagation: +2-5ms (parsing + emission)
- End-to-end: 10-30ms per event (acceptable for human perception)

### Buffering
- Client buffer: max 100 events or 1MB (whichever first)
- Server buffer: line-buffered (NDJSON)
- SSH buffer: default (~64KB)

### Scalability
- Concurrent streams: 100+ per dispatcher (SSE approach)
- Memory per stream: ~100KB (buffers + state)
- Total: 10MB for 100 concurrent streams (acceptable)

---

## Testing Strategy

### Unit Tests
```javascript
describe('RemoteExecutor.executeStreaming', () => {
  it('emits log events', async () => {
    const logs = [];
    await executor.executeStreaming(server, model, prompt, {
      onLog: (e) => logs.push(e)
    });
    expect(logs.length).toBeGreaterThan(0);
    expect(logs[0]).toMatchObject({ type: 'log', message: expect.any(String) });
  });
  
  it('emits progress events in order', async () => {
    const progress = [];
    await executor.executeStreaming(server, model, prompt, {
      onProgress: (e) => progress.push(e.percent)
    });
    expect(progress).toEqual([...progress].sort((a, b) => a - b));
  });
  
  it('handles stream interruption gracefully', async () => {
    // Mock SSH process killed mid-stream
    await expect(executor.executeStreaming(server, model, prompt, {
      simulateKill: true
    })).rejects.toThrow('Stream interrupted');
  });
});
```

### Integration Tests
```javascript
describe('Fleet Streaming E2E', () => {
  it('streams remote agent execution end-to-end', async () => {
    const events = { logs: [], progress: [], partials: [] };
    
    const result = await fleetUtils.streamRemoteAgent('server-01', 'sonnet', 
      'Analyze this file and report progress', {
        onLog: (e) => events.logs.push(e),
        onProgress: (e) => events.progress.push(e),
        onPartial: (d) => events.partials.push(d)
      }
    );
    
    expect(events.logs.length).toBeGreaterThan(0);
    expect(events.progress.length).toBeGreaterThan(0);
    expect(result).toBeDefined();
  });
});
```

---

## Workflow Usage Examples

### Example 1: Progress Logging
```javascript
export const meta = {
  name: 'code-review-auto',
  description: 'Automated code review with progress tracking'
};

phase('Review');

const result = await agent(
  'Review all files in src/ and report issues',
  {
    model: 'opus',
    streaming: true,
    onProgress: (p) => log(`Reviewing: ${p.phase} - ${p.percent}% complete`),
    onLog: (e) => {
      if (e.level === 'error') log(`ERROR: ${e.message}`);
    }
  }
);

return result;
```

### Example 2: Partial Result Collection
```javascript
phase('Extract');

const findings = [];

await agent(
  'Extract security vulnerabilities from codebase',
  {
    model: 'sonnet',
    streaming: true,
    onPartial: (data) => {
      if (data.vulnerability) {
        findings.push(data.vulnerability);
        log(`Found vulnerability: ${data.vulnerability.type} in ${data.vulnerability.file}`);
      }
    }
  }
);

return { findings, count: findings.length };
```

### Example 3: Multi-Stage Workflow with Streaming
```javascript
phase('Analyze');

let analysisProgress = 0;

const analysis = await agent(
  'Analyze architecture of 100 files',
  {
    model: 'opus',
    streaming: true,
    onProgress: (p) => {
      analysisProgress = p.percent;
      log(`Analysis: ${p.percent}%`);
    }
  }
);

phase('Synthesize');

await agent(
  `Synthesize findings from analysis: ${JSON.stringify(analysis)}`,
  {
    model: 'sonnet',
    streaming: true,
    onLog: (e) => log(`Synthesis: ${e.message}`)
  }
);
```

---

## Monitoring & Observability

### Metrics to Track
- `remote_stream_duration_ms` (histogram): time from start to completion
- `remote_stream_events_total` (counter): total events emitted per type
- `remote_stream_errors_total` (counter): stream failures by error type
- `remote_stream_active_connections` (gauge): concurrent streaming sessions
- `remote_stream_event_latency_ms` (histogram): time from event emission to client receipt

### Logging
```javascript
// Structured logging for stream lifecycle
logger.info('stream_started', { job_id, server, model });
logger.debug('stream_event', { job_id, event_type, sequence });
logger.warn('stream_interrupted', { job_id, reason, partial_results_saved });
logger.info('stream_completed', { job_id, duration_ms, total_events });
```

### Alerting
- Alert if stream error rate > 5% over 5 minutes
- Alert if stream latency p99 > 500ms
- Alert if no events received for > 60 seconds on active stream

---

## Security Considerations

### SSH Command Injection Prevention
Already handled by existing `escapeForSsh()` and `escapeForDoubleQuotes()` functions in RemoteExecutor.

### Event Data Sanitization
```javascript
function sanitizeEvent(event) {
  // Prevent XSS if events displayed in web UI
  if (event.type === 'log' && event.message) {
    event.message = event.message.replace(/[<>]/g, '');
  }
  return event;
}
```

### Rate Limiting
- Max 1000 events per stream (prevent DoS)
- Max 10 concurrent streams per client (resource protection)

---

## Migration Path

### Week 1-2: Foundation
- Implement `executeStreaming()` in RemoteExecutor
- Add NDJSON parsing logic
- Create unit tests
- Document API

### Week 3: Integration
- Update fleet-agent-wrapper to support streaming
- Add streaming option to fleet-utils
- Backward compatibility tests

### Week 4: Pilot
- Migrate 2-3 workflows to use streaming (code-review-auto, ai-consensus)
- Collect feedback
- Performance profiling

### Week 5-6: Rollout
- Migrate all autonomous workflows
- Add monitoring dashboards
- Write user documentation

### Week 7+: Advanced Features
- SSE dispatcher endpoint (if needed)
- WebSocket support (if needed)
- Advanced partial result merging strategies

---

## Open Questions

1. **Claude CLI Support**: Does `claude -p` support `--output-format json-stream`?
   - If NO → need to instrument workflow code to emit events manually
   - If YES → straightforward implementation

2. **Event Granularity**: How frequently should progress events emit?
   - Too frequent → network overhead
   - Too sparse → poor user experience
   - Recommendation: 1-5 second intervals, or 5% progress deltas

3. **Partial Result Schema**: Should partial results follow the same schema as final results?
   - YES → easier to merge, but may be incomplete
   - NO → separate schema for partials, more flexible but complex

4. **Stream Persistence**: Should interrupted streams be resumable?
   - If YES → need to persist stream state (sequence numbers, checkpoint data)
   - If NO → simpler implementation, but poor UX for long tasks

---

## Conclusion

**Recommended Approach**: Progressive JSON Line Protocol (Approach 1)

**Rationale**:
- Simplest to implement
- No additional infrastructure required
- Works naturally with SSH stdout
- Backward compatible
- Sufficient for 90% of use cases

**Next Steps**:
1. Verify Claude CLI streaming support
2. Implement `RemoteExecutor.executeStreaming()`
3. Update fleet-agent-wrapper
4. Pilot with code-review-auto workflow
5. Measure performance and user feedback
6. Iterate based on learnings

**Success Criteria**:
- 100% backward compatibility (non-streaming still works)
- < 50ms event propagation latency (p95)
- > 95% stream completion rate (no interruptions)
- Positive user feedback on visibility and progress tracking
