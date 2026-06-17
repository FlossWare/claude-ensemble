# Cross-Session Communication Quickstart

Get up and running with cross-session communication in 5 minutes.

## Quick Start

### 1. Run Tests (Verify Installation)

```bash
chmod +x ./learning/test-session-communication.js
./learning/test-session-communication.js
```

Expected output:
```
✓ Session ID matches
✓ One session registered
✓ Heartbeat updated timestamp
✓ Message sent
...
✓ All tests passed!
```

### 2. Interactive Demo (Single Session)

```bash
chmod +x ./learning/demo-session-communication.js
./learning/demo-session-communication.js
```

Try these commands:
1. Show active sessions
2. Send broadcast message
3. Share test discovery
5. Show session statistics

### 3. Multi-Session Demo (Two Terminals)

**Terminal 1** (Session A):
```bash
SESSION_NAME="SessionA" ./learning/demo-session-communication.js
```

**Terminal 2** (Session B):
```bash
SESSION_NAME="SessionB" ./learning/demo-session-communication.js
```

Now try:
- In Session A: Send broadcast → See it in Session B
- In Session B: Share discovery → See it in Session A
- In Session A: Request help → Session B responds

### 4. Use in Your Code

**Basic Usage** (Auto-integration):
```javascript
import { wrapOrchestrator } from './learning/session-integration.js';

// Wrap orchestrator - session hooks added automatically
const orch = await wrapOrchestrator();

// Use normally - session registered, heartbeat sent automatically
const model = await orch.selectModel('code-review');
```

**Manual Control**:
```javascript
import { SessionManager } from './learning/session-manager.js';

// Create session
const manager = new SessionManager({
  capabilities: ['opus', 'sonnet'],
  taskType: 'code-review',
});

// Start (heartbeat + polling)
await manager.start();

// Register handler
manager.onMessage('discovery', async (msg) => {
  console.log('Discovery:', msg.data);
});

// Send message
await manager.sendMessage('other-session-id', {
  type: 'insight',
  data: { message: 'Hello!' },
});

// Broadcast to all
await manager.broadcast({
  type: 'discovery',
  data: { insight: 'Important finding' },
});

// Stop
await manager.stop();
```

## Common Patterns

### Share Discoveries Automatically

Discoveries are shared automatically when using `wrapOrchestrator()`:

```javascript
import { wrapOrchestrator } from './learning/session-integration.js';

const orch = await wrapOrchestrator();

// Discoveries.json changes are auto-detected and broadcast
// Other sessions receive and apply automatically
// No code needed!
```

### Coordinate Model Selection

```javascript
import { coordinateModels } from './learning/session-integration.js';

// Tell other sessions which models you're using
await coordinateModels(['opus', 'sonnet']);

// Other sessions can avoid duplication
```

### Request Help

```javascript
import { requestHelp } from './learning/session-integration.js';

const responses = await requestHelp({
  task: 'pdf-analysis',
  capabilities: ['opus'],
});

if (responses.length > 0) {
  console.log(`Found ${responses.length} helpers`);
}
```

### Monitor Sessions

```javascript
import { getActiveSessions } from './orchestrator.js';

const sessions = await getActiveSessions();
console.log(`Active: ${sessions.length} sessions`);

for (const session of sessions) {
  console.log(`  ${session.sessionId}: ${session.taskType}`);
}
```

## Debugging

Enable debug logging:

```bash
export SESSION_DEBUG=true
export HOT_RELOAD_DEBUG=true
./your-script.js
```

Check session registry:

```bash
cat learning/session-registry.json | jq '.sessions'
```

Check pending messages:

```bash
cat learning/session-messages.json | jq '.messages'
```

## Troubleshooting

**Sessions not showing up?**
- Wait 5s for heartbeat
- Check that session called `start()` or used wrapped orchestrator

**Messages not delivered?**
- Wait 5-10s for polling interval
- Check session IDs match
- Verify message TTL hasn't expired

**Discoveries not shared?**
- Check `learning/discoveries.json` exists
- Wait 5s for auto-check
- Enable `SESSION_DEBUG=true` to see sharing

## Next Steps

- [Full Documentation](CROSS_SESSION_COMMUNICATION.md)
- [Architecture Details](CROSS_SESSION_COMMUNICATION.md#architecture)
- [Use Cases](CROSS_SESSION_COMMUNICATION.md#use-cases)
- [API Reference](CROSS_SESSION_COMMUNICATION.md#orchestrator-extensions)

## Examples

### Example 1: Collective Learning

```javascript
// Session A discovers pattern
// (happens automatically via auto-discovery)

// Session B receives and applies
// (happens automatically via session-integration)

// All sessions benefit immediately
```

### Example 2: Task Coordination

```javascript
// Session A - working on code review
import { wrapOrchestrator, coordinateModels } from './learning/session-integration.js';

const orch = await wrapOrchestrator();
const model = await orch.selectModel('code-review');
await coordinateModels([model]);

// Session B - working on same codebase
// Automatically avoids model Session A is using
```

### Example 3: Expert Finder

```javascript
// Session A - needs help
import { requestHelp } from './learning/session-integration.js';

const experts = await requestHelp({
  task: 'pdf-analysis',
  capabilities: ['opus'],
});

console.log(`Found ${experts.length} experts`);
```

## Performance Tips

1. **Use wrapped orchestrator** - Automatic session management
2. **Don't poll manually** - Session manager handles it
3. **Set reasonable TTLs** - Default 1h is usually fine
4. **Cleanup old messages** - Automatic every 1min
5. **Rate limit checks** - Discovery checks limited to 5s

## Architecture Summary

```
Session A    Session B    Session C
    │            │            │
    └────────────┴────────────┘
                 │
           Orchestrator
                 │
         ┌───────┴───────┐
         │               │
    Registry         Messages
    (sessions)       (pub/sub)
```

- **Registry**: Track active sessions (heartbeat every 30s)
- **Messages**: Pub/sub with TTL (polling every 5s)
- **Hot-reload**: Live updates (<5s)
- **Auto-cleanup**: Dead sessions + old messages (every 1min)

## What's Included

✅ Session registry (`learning/session-registry.json`)  
✅ Message bus (`learning/session-messages.json`)  
✅ Session manager (`learning/session-manager.js`)  
✅ Session integration (`learning/session-integration.js`)  
✅ Orchestrator extensions (`orchestrator.js`)  
✅ Comprehensive tests (`learning/test-session-communication.js`)  
✅ Interactive demo (`learning/demo-session-communication.js`)  
✅ Full documentation (`docs/CROSS_SESSION_COMMUNICATION.md`)

## Getting Help

**Questions?** Check the [full documentation](CROSS_SESSION_COMMUNICATION.md)

**Issues?** Run tests to verify installation:
```bash
./learning/test-session-communication.js
```

**Still stuck?** Enable debug logging:
```bash
SESSION_DEBUG=true ./your-script.js
```
