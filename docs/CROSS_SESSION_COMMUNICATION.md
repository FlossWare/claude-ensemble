# Cross-Session Communication System

**Status**: ✅ Implemented and Tested  
**Version**: 1.0.0  
**Last Updated**: 2026-06-14

## Overview

The Cross-Session Communication System enables all Claude sessions to communicate through a central orchestrator, creating a **collective intelligence** where sessions can:

- Share discoveries and learnings in real-time
- Coordinate task execution
- Request help from other sessions
- Avoid duplicate work through model coordination
- Build on each other's insights

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (Central Hub)                │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Session    │  │   Message    │  │   Discovery  │      │
│  │   Registry   │  │     Bus      │  │     Sync     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
         ↑                  ↑                  ↑
         │                  │                  │
    ┌────┴────┐        ┌────┴────┐       ┌────┴────┐
    │ Session │        │ Session │       │ Session │
    │    A    │        │    B    │       │    C    │
    │ (code-  │        │ (PDF    │       │ (web    │
    │ review) │        │ analysis)       │ learn)  │
    └─────────┘        └─────────┘       └─────────┘
```

## Components

### 1. Session Registry (`learning/session-registry.json`)

**Purpose**: Track all active Claude sessions

**Data Structure**:
```json
{
  "sessions": {
    "session-abc123": {
      "pid": 12345,
      "startTime": 1718362800000,
      "lastHeartbeat": 1718362830000,
      "capabilities": ["opus", "sonnet", "haiku"],
      "taskType": "code-review",
      "metadata": {}
    }
  },
  "lastCleanup": 1718362800000,
  "version": 1
}
```

**Features**:
- Auto-registration on first orchestrator call
- Heartbeat every 30s to stay alive
- Auto-cleanup of dead sessions (no heartbeat >5min)
- Hot-reloaded (<5s discovery of new sessions)

### 2. Message Bus (`learning/session-messages.json`)

**Purpose**: Pub/sub messaging between sessions

**Message Types**:
- `discovery` - New pattern/insight discovered
- `insight` - Observation or learning
- `request` - Ask for help from other sessions
- `response` - Reply to a request
- `coordination` - Coordinate task execution

**Data Structure**:
```json
{
  "messages": [
    {
      "id": "msg-xyz789",
      "from": "session-abc123",
      "to": "session-def456",  // or "broadcast"
      "type": "discovery",
      "data": { ... },
      "timestamp": 1718362800000,
      "ttl": 3600000
    }
  ],
  "lastCleanup": 1718362800000,
  "version": 1
}
```

**Features**:
- Point-to-point and broadcast messaging
- TTL-based message expiration (default 1h)
- Auto-cleanup of old messages
- Hot-reloaded (<5s message delivery)

### 3. Session Manager (`learning/session-manager.js`)

**Purpose**: Core session lifecycle management

**Key Methods**:
```javascript
import { SessionManager } from './learning/session-manager.js';

const manager = new SessionManager({
  capabilities: ['opus', 'sonnet'],
  taskType: 'code-review',
});

// Start session (heartbeat + polling)
await manager.start();

// Send message
await manager.sendMessage('session-123', {
  type: 'discovery',
  data: { insight: 'fable fails on JSON' },
});

// Broadcast to all
await manager.broadcast({
  type: 'insight',
  data: { message: 'Opus works best for complex refactoring' },
});

// Register message handler
manager.onMessage('discovery', async (msg) => {
  console.log('Discovery received:', msg.data);
});

// Stop session
await manager.stop();
```

**Features**:
- Automatic heartbeat daemon (30s interval)
- Message polling daemon (5s interval)
- Cleanup daemon (dead sessions + old messages)
- Handler-based message processing
- Graceful shutdown

### 4. Session Integration (`learning/session-integration.js`)

**Purpose**: Auto-integrate sessions with orchestrator

**Features**:
- **Lazy initialization**: Session created on first orchestrator call
- **Auto-heartbeat**: Every orchestrator call sends heartbeat
- **Auto-discovery sharing**: New discoveries broadcast to all sessions
- **Request/response**: Sessions can ask for help
- **Model coordination**: Avoid duplicate model usage

**Usage**:
```javascript
import { wrapOrchestrator, shareDiscovery, requestHelp } from './learning/session-integration.js';

// Wrap orchestrator (adds session hooks)
const orch = await wrapOrchestrator();

// Use normally - session hooks run automatically
const model = await orch.selectModel('code-review');
// => Auto-registers session, sends heartbeat, checks for messages

// Share discovery with other sessions
await shareDiscovery({
  id: 'disc-123',
  insight: 'fable fails on JSON',
  confidence: 0.92,
});

// Request help from other sessions
const responses = await requestHelp({
  task: 'pdf-analysis',
  capabilities: ['opus'],
});
```

### 5. Orchestrator Extensions (`orchestrator.js`)

**New Exported Functions**:

```javascript
import {
  registerSession,
  sendMessage,
  broadcast,
  getMessages,
  heartbeat,
  getActiveSessions,
  onMessage,
  initSession,
  getSessionStats,
} from './orchestrator.js';

// Register this session
const sessionId = await registerSession({
  capabilities: ['opus', 'sonnet'],
  taskType: 'code-review',
});

// Send message
await sendMessage('session-123', {
  type: 'discovery',
  data: { ... },
});

// Broadcast
await broadcast({
  type: 'insight',
  data: { ... },
});

// Get messages
const messages = await getMessages();

// Heartbeat
await heartbeat();

// Get all sessions
const sessions = await getActiveSessions();

// Register handler
await onMessage('discovery', async (msg) => {
  console.log('Discovery:', msg.data);
});

// Initialize session
await initSession({
  capabilities: ['opus'],
  taskType: 'pdf-analysis',
});

// Get stats
const stats = await getSessionStats();
```

## Use Cases

### 1. Collective Learning

**Scenario**: Session A discovers "fable fails on JSON schema tasks"

**Flow**:
1. Session A discovers pattern through auto-discovery
2. Discovery written to `learning/discoveries.json`
3. Session integration detects new discovery
4. Broadcast to all active sessions
5. Sessions B, C, D receive and apply discovery
6. All sessions immediately avoid fable for JSON tasks

**Code**:
```javascript
// Session A - discovery happens automatically
// No code needed - auto-discovery detects pattern

// Sessions B, C, D - automatically receive and apply
// No code needed - session integration handles it
```

### 2. Coordinated Task Execution

**Scenario**: Multiple sessions working on same codebase

**Flow**:
1. Session A selects "opus" for code review
2. Broadcasts: "I'm using opus"
3. Session B sees message
4. Session B selects "sonnet" instead (avoids duplication)
5. Parallel exploration with different models

**Code**:
```javascript
// Session A
await coordinateModels(['opus']);

// Session B - listens for coordination messages
// Automatically avoids already-used models
```

### 3. Request/Response Help

**Scenario**: Session needs specific expertise

**Flow**:
1. Session A needs help with PDF analysis
2. Broadcasts request: "Who can help with PDF analysis?"
3. Session C (running PDF workflow) responds
4. Session A gets response with capabilities
5. Sessions coordinate on task

**Code**:
```javascript
// Session A - request help
const responses = await requestHelp({
  task: 'pdf-analysis',
  capabilities: ['opus'],
});

if (responses.length > 0) {
  console.log(`Found ${responses.length} helper sessions`);
}
```

### 4. Shared Insights

**Scenario**: Session observes interesting behavior

**Flow**:
1. Session B notices "opus excels at complex refactoring"
2. Shares insight with all sessions
3. Other sessions receive and log insight
4. Future sessions benefit from observation

**Code**:
```javascript
// Session B - share insight
await broadcast({
  type: 'insight',
  data: {
    observation: 'opus excels at complex refactoring',
    context: 'large codebase, >1000 lines changed',
    confidence: 0.88,
  },
});
```

## Message Flow

### Discovery Propagation

```
Session A                  Orchestrator               Session B
   │                            │                         │
   │  1. New discovery          │                         │
   │─────────────────────────>  │                         │
   │                            │                         │
   │  2. Broadcast discovery    │                         │
   │                            │──────────────────────>  │
   │                            │                         │
   │                            │  3. Receive & apply     │
   │                            │  <──────────────────── │
   │                            │                         │
```

### Request/Response

```
Session A                  Orchestrator               Session C
   │                            │                         │
   │  1. Request help           │                         │
   │─────────────────────────>  │                         │
   │                            │                         │
   │                            │  2. Forward request     │
   │                            │──────────────────────>  │
   │                            │                         │
   │                            │  3. Send response       │
   │                            │  <──────────────────── │
   │                            │                         │
   │  4. Receive response       │                         │
   │  <─────────────────────── │                         │
   │                            │                         │
```

## Performance

### Latency

- **Session registration**: <50ms
- **Heartbeat**: <10ms (best-effort)
- **Message send**: <50ms
- **Message delivery**: <5s (polling interval)
- **Discovery propagation**: <5s (polling + checking)

### Scalability

- **Max sessions**: ~100 (limited by file I/O contention)
- **Max messages/session**: ~1000 (limited by JSON parsing)
- **Message throughput**: ~20 msg/s (limited by file writes)

### Optimization

- **Hot-reload caching**: 1s TTL for code, 5s for JSON
- **Atomic writes**: Temp file + rename (most filesystems)
- **Lazy cleanup**: Only when needed (1min interval)
- **Rate limiting**: Discovery checks at most every 5s

## Configuration

### Environment Variables

```bash
# Enable debug logging
export SESSION_DEBUG=true

# Enable hot-reload debug
export HOT_RELOAD_DEBUG=true

# Enable learning debug
export LEARNING_DEBUG=true
```

### Tuning

Edit constants in `learning/session-manager.js`:

```javascript
const HEARTBEAT_INTERVAL = 30000;  // 30s (lower = more responsive)
const POLL_INTERVAL = 5000;        // 5s (lower = faster delivery)
const SESSION_TIMEOUT = 300000;    // 5min (higher = more tolerant)
const MESSAGE_TTL = 3600000;       // 1h (lower = less clutter)
```

## Testing

### Run Test Suite

```bash
chmod +x ./learning/test-session-communication.js
./learning/test-session-communication.js
```

### Test Coverage

- ✅ Session registration and lifecycle
- ✅ Heartbeat mechanism
- ✅ Point-to-point messaging
- ✅ Broadcast messaging
- ✅ Message handlers
- ✅ Session cleanup (dead sessions)
- ✅ Message cleanup (expired messages)
- ✅ Orchestrator integration
- ✅ Discovery sharing
- ✅ Request/response pattern
- ✅ Model coordination
- ✅ Hot-reload integration
- ✅ Session statistics

### Manual Testing

**Terminal 1** (Session A):
```bash
node -e "
import('./learning/session-integration.js').then(async (m) => {
  const orch = await m.wrapOrchestrator();
  const model = await orch.selectModel('code-review');
  console.log('Selected model:', model);
  
  // Share discovery
  await m.shareDiscovery({
    id: 'test-disc-' + Date.now(),
    insight: 'Test from Session A',
    confidence: 0.95,
  });
  
  // Wait to keep session alive
  await new Promise(r => setTimeout(r, 60000));
});
"
```

**Terminal 2** (Session B):
```bash
node -e "
import('./learning/session-integration.js').then(async (m) => {
  const orch = await m.wrapOrchestrator();
  
  // Wait for Session A's discovery
  await new Promise(r => setTimeout(r, 10000));
  
  const messages = await orch.getMessages();
  console.log('Messages:', messages);
});
"
```

## Troubleshooting

### Sessions not appearing in registry

**Cause**: Session not initialized or heartbeat stopped  
**Fix**: Check that session called `initSession()` or used wrapped orchestrator

### Messages not delivered

**Cause**: Polling interval not elapsed or session ID mismatch  
**Fix**: Wait 5-10s for polling, verify session IDs match

### Discovery not shared

**Cause**: Discovery file not modified or rate limit hit  
**Fix**: Check `discoveries.json` modification time, wait 5s between checks

### Dead sessions not cleaned up

**Cause**: Cleanup daemon not running  
**Fix**: Ensure at least one session has started (cleanup runs every 1min)

## Future Enhancements

### Phase 2: Distributed Lock

- Add distributed locking for critical sections
- Prevent race conditions on shared resources
- Enable atomic multi-session operations

### Phase 3: Session Metrics

- Track message throughput per session
- Monitor discovery propagation latency
- Generate session activity dashboards

### Phase 4: Priority Messaging

- Add message priority levels (low, normal, high, urgent)
- Priority queue for high-priority messages
- Fast-path for urgent coordination

### Phase 5: Session Clusters

- Group sessions by task type or capability
- Cluster-specific message routing
- Load balancing across clusters

### Phase 6: Persistent Sessions

- Session state persistence across restarts
- Resume message handlers after crash
- Durable message queues

## References

- [Learning System](../learning/README.md)
- [Hot-Reload System](HOT_RELOAD_SYSTEM.md)
- [Auto-Discovery](../learning/AUTO_DISCOVERY_SYSTEM.md)
- [Thompson Sampling](../learning/THOMPSON_SAMPLING.md)

## Changelog

### v1.0.0 (2026-06-14)
- Initial implementation
- Session registry and heartbeat
- Message bus and pub/sub
- Discovery propagation
- Request/response pattern
- Model coordination
- Hot-reload integration
- Comprehensive test suite
