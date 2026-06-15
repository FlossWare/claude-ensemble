# Cross-Session Orchestration

Complete system for cross-session visibility, communication, and work coordination across single-node and distributed (multi-node) Claude Code deployments.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Distributed Fleet                        │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│   aio-01    │  server-01  │  server-02  │   server-03      │
│             │             │             │                  │
│ Orch:7340   │ Orch:7340   │ Orch:7340   │  Orch:7340       │
│ Sessions:   │ Sessions:   │ Sessions:   │  Sessions:       │
│  - abc123   │  - def456   │  - ghi789   │   - jkl012       │
│  - mno345   │  - pqr678   │             │                  │
└─────────────┴─────────────┴─────────────┴──────────────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                            │
                    Shared SQLite DB
                    (or Redis cluster)
```

## Components

### 1. Session Registry (`session-registry.js`)

Tracks all active sessions across nodes:

```javascript
const SessionRegistry = require('~/.claude/lib/session-registry');
const registry = new SessionRegistry();

// Register current session
registry.register(sessionId, {
  working_on: 'Implementing auth',
  files_locked: ['src/auth/*.ts'],
  current_task: 'Writing tests'
});

// Heartbeat (keep alive)
registry.heartbeat(sessionId);

// Get all active sessions
const sessions = registry.getActiveSessions();

// Find conflicts with files
const conflicts = registry.findConflicts(['src/auth/login.ts']);
```

**State stored:**
- Session ID, PID, CWD
- What the session is working on
- Files locked
- Last heartbeat
- Node hostname

### 2. Session Messenger (`session-messenger.js`)

File-based message queue for inter-session communication:

```javascript
const SessionMessenger = require('~/.claude/lib/session-messenger');
const messenger = new SessionMessenger();

// Send to specific session
messenger.send(targetSessionId, {
  type: 'conflict_warning',
  payload: 'I\'m working on auth.ts, please coordinate'
});

// Broadcast to all sessions
messenger.broadcast({
  type: 'announcement',
  payload: 'Starting CI build, pause commits'
});

// Receive messages
const messages = messenger.receive();

// Reply to message
messenger.reply(messageId, 'Acknowledged, will wait');
```

**Message types:**
- `message` - General message
- `work_assignment` - Orchestrator assigning work
- `conflict_warning` - File conflict detected
- `status_query` - Request status
- `reply` - Reply to previous message

### 3. Session Orchestrator (`session-orchestrator.js`)

Single-node coordinator (file-based):

```bash
# Start orchestrator daemon
node ~/.claude/lib/session-orchestrator.js start

# Enqueue work
node ~/.claude/lib/session-orchestrator.js enqueue "Review PR #123"

# Check status
node ~/.claude/lib/session-orchestrator.js status

# View logs
node ~/.claude/lib/session-orchestrator.js logs

# Stop
node ~/.claude/lib/session-orchestrator.js stop
```

**Features:**
- Work queue management
- Auto-assignment to least-busy session
- Conflict detection
- Message routing

### 4. Distributed Orchestrator (`distributed-orchestrator.js`)

Multi-node coordinator with HTTP API and shared state:

```bash
# Start on each node
node ~/.claude/lib/distributed-orchestrator.js start

# HTTP API (port 7340)
curl http://aio-01:7340/health
curl http://aio-01:7340/sessions
curl http://aio-01:7340/work
```

**Features:**
- Shared SQLite database (or Redis)
- HTTP API for cross-node communication
- Work stealing across nodes
- Fleet-wide session visibility
- Message routing between nodes

**API Endpoints:**
- `GET /health` - Health check
- `GET /sessions` - All active sessions
- `POST /sessions` - Register session
- `GET /work` - Get queued work
- `POST /work` - Enqueue work
- `POST /messages` - Send message

## CLI Tool: `claude-sessions`

Unified command-line interface:

```bash
# Session visibility
claude-sessions list                    # All active sessions
claude-sessions conflicts src/auth/*.ts  # Check file conflicts

# Messaging
claude-sessions send abc123 "Please pause, I'm refactoring auth"
claude-sessions broadcast "CI starting, hold commits"
claude-sessions inbox                   # Show my messages
claude-sessions read <messageId>        # Mark as read
claude-sessions reply <id> "Got it!"    # Reply

# Orchestration
claude-sessions orchestrator start      # Start daemon
claude-sessions orchestrator stop       # Stop daemon
claude-sessions orchestrator status     # Show status
claude-sessions orchestrator enqueue "Review PR #456"
claude-sessions orchestrator logs       # View logs
```

## Deployment

### Single Node (Local)

```bash
# Already installed, just start orchestrator
claude-sessions orchestrator start
```

### Distributed Fleet

```bash
# Deploy to all nodes
~/.claude/bin/deploy-orchestrator-fleet

# Verify deployment
for node in aio-01 server-01 server-02 server-03; do
  ssh $node "claude-sessions list"
done
```

## State Storage Options

### SQLite (Default)

- **Location:** `~/.claude/orchestrator/distributed-state.db`
- **Mode:** WAL (Write-Ahead Logging)
- **Shared:** NFS or synced across nodes
- **Best for:** Small-medium fleets (< 10 nodes)

### Redis (Future)

- **Best for:** Large fleets (10+ nodes)
- **Features:** Pub/sub, automatic expiry, clustering
- **Config:** Set `state.backend: "redis"` in config

## Configuration

Edit `~/.claude/orchestrator/distributed-config.json`:

```json
{
  "mode": "distributed",
  "nodeId": "aio-01",

  "fleet": [
    { "id": "aio-01", "host": "aio-01", "port": 7340 },
    { "id": "server-01", "host": "server-01", "port": 7340 },
    { "id": "server-02", "host": "server-02", "port": 7340 },
    { "id": "server-03", "host": "server-03", "port": 7340 }
  ],

  "api": {
    "enabled": true,
    "port": 7340,
    "host": "0.0.0.0"
  },

  "state": {
    "backend": "sqlite",
    "sqlite": {
      "path": "~/.claude/orchestrator/distributed-state.db",
      "wal": true
    }
  },

  "workStealing": true,
  "loadBalancing": "least-busy",
  "conflictDetection": true
}
```

## Use Cases

### 1. Conflict Prevention

**Scenario:** Two sessions editing the same file

```bash
# Session 1
claude-sessions conflicts src/auth/login.ts

# Output: Session abc123 (PID 12345) is working on auth/login.ts
```

### 2. Work Coordination

**Scenario:** Distribute PR reviews across sessions

```bash
# Enqueue work
for pr in 123 124 125 126; do
  claude-sessions orchestrator enqueue "Review PR #$pr"
done

# Sessions automatically receive assignments
```

### 3. Fleet-Wide Announcements

**Scenario:** Notify all sessions of CI build

```bash
claude-sessions broadcast "CI build starting on main, pause commits for 5 minutes"
```

### 4. Cross-Session Queries

**Scenario:** Ask another session for information

```bash
claude-sessions send def456 "What's the status of the auth refactor?"
```

## Integration with Workflows

Workflows can now coordinate across sessions:

```javascript
// In a workflow script
const SessionRegistry = require('~/.claude/lib/session-registry');
const registry = new SessionRegistry();

// Check for conflicts before starting work
const conflicts = registry.findConflicts(['src/auth/*']);
if (conflicts.length > 0) {
  log(`Conflicts detected: ${conflicts.length} sessions working on auth`);
  // Wait or coordinate
}

// Register our work
registry.heartbeat(args.sessionId, {
  working_on: 'Auth refactoring workflow',
  files_locked: ['src/auth/*']
});
```

## Monitoring

### View Active Sessions

```bash
claude-sessions list
```

```
3 active session(s):

→ Session: ff4c1dc9...
  PID: 97265 | Age: 2m 30s | Host: aio-01
  CWD: /home/sfloess
  Working on: Cross-session orchestration

  Session: abc12345...
  PID: 12345 | Age: 15m 10s | Host: server-01
  CWD: /workspace/project
  Working on: Implementing auth
  Files locked: src/auth/*.ts
```

### Check Orchestrator Status

```bash
claude-sessions orchestrator status
```

```json
{
  "running": true,
  "workQueue": 3,
  "queued": 2,
  "assigned": 1,
  "completed": 15,
  "activeSessions": 4,
  "conflicts": 0
}
```

### View Messages

```bash
claude-sessions inbox
```

```
2 message(s):

[a1b2c3d4] work_assignment from orchestr...
  Time: 2026-06-13T19:00:00.000Z
  Priority: high
  Payload: {
    "id": "work-1234",
    "description": "Review PR #123"
  }

[e5f6g7h8] message from abc12345...
  Time: 2026-06-13T19:05:00.000Z
  Priority: normal
  Message: Working on auth.ts, any conflicts?
```

## Security Considerations

1. **Authentication:** HTTP API has no auth (internal fleet only)
2. **Encryption:** No TLS (use VPN or internal network)
3. **File Permissions:** Registry files are world-readable
4. **Message Privacy:** Messages stored in plaintext

**Recommendation:** Deploy behind firewall or VPN for multi-node setup.

## Troubleshooting

### Sessions not showing up

```bash
# Check if registry file exists
ls -la ~/.claude/sessions/registry.json

# Manually register current session
node ~/.claude/lib/session-registry.js register
```

### Orchestrator not starting

```bash
# Check if already running
cat ~/.claude/orchestrator/orchestrator.pid

# View logs
tail -f ~/.claude/orchestrator/orchestrator.log

# Kill stale process
kill $(cat ~/.claude/orchestrator/orchestrator.pid)
rm ~/.claude/orchestrator/orchestrator.pid
```

### Messages not delivered

```bash
# Check message directory
ls -la ~/.claude/sessions/messages/inbox/

# Cleanup expired messages
node ~/.claude/lib/session-messenger.js cleanup
```

### Cross-node communication failing

```bash
# Test HTTP API
curl http://aio-01:7340/health

# Check firewall
sudo firewall-cmd --list-ports

# Open port 7340
sudo firewall-cmd --add-port=7340/tcp --permanent
sudo firewall-cmd --reload
```

## Future Enhancements

- [ ] Redis backend for large fleets
- [ ] TLS/authentication for HTTP API
- [ ] Web UI dashboard for fleet monitoring
- [ ] Load balancing strategies (priority, capability-based)
- [ ] Session migration (move work between nodes)
- [ ] Automatic conflict resolution
- [ ] Integration with git hooks
- [ ] Session replay/debugging
- [ ] Metrics and analytics (Prometheus/Grafana)

## Related Files

- `~/.claude/lib/session-registry.js` - Session tracking
- `~/.claude/lib/session-messenger.js` - Inter-session messaging
- `~/.claude/lib/session-orchestrator.js` - Single-node orchestrator
- `~/.claude/lib/distributed-orchestrator.js` - Multi-node orchestrator
- `~/.claude/bin/claude-sessions` - CLI tool
- `~/.claude/bin/deploy-orchestrator-fleet` - Fleet deployment
- `~/.claude/sessions/` - Session state directory
- `~/.claude/orchestrator/` - Orchestrator state directory
