# Cross-Session Communication System

## Overview

Claude Code now has **full cross-session visibility and communication**. You can:

1. ✅ **See what other sessions are working on**
2. ✅ **Send messages between sessions**
3. ✅ **Detect file conflicts** before they happen
4. ✅ **Distribute work** via the orchestrator
5. ✅ **Coordinate multi-session workflows**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Session Registry                          │
│  ~/.claude/sessions/registry.json                           │
│  Tracks: PID, CWD, working_on, files_locked, heartbeat      │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐   ┌────────▼────────┐   ┌─────▼──────┐
│  Session 1  │   │   Session 2     │   │  Session 3 │
│  PID 43112  │   │   PID 95328     │   │  PID 97265 │
└─────────────┘   └─────────────────┘   └────────────┘
       │                   │                   │
       └───────────────────▼───────────────────┘
                           │
┌─────────────────────────▼────────────────────────────────────┐
│              Session Messenger                                │
│  ~/.claude/sessions/messages/inbox/                          │
│  File-based message queue for inter-session communication    │
└───────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────▼────────────────────────────────────┐
│           Session Orchestrator (Optional Daemon)             │
│  Coordinates work distribution, conflict detection           │
│  Auto-assigns tasks to least-busy sessions                   │
└───────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. View All Active Sessions

```bash
claude-sessions list
```

Output:
```
3 active session(s):

→ Session: ddc76ad6...
  PID: 43112 | Age: 5m 30s | Host: laptop-01
  CWD: /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
  Working on: Implementing multi-AI consensus

  Session: 1bdb3e55...
  PID: 95328 | Age: 12m 15s | Host: laptop-01
  CWD: /home/sfloess
  Working on: Building cross-session communication

  Session: ff4c1dc9...
  PID: 97265 | Age: 2m 45s | Host: laptop-01
  CWD: /home/sfloess/Development/virtos
  Working on: Testing kernel modules
```

The `→` marker indicates YOUR current session.

### 2. Check for File Conflicts

Before editing files, check if another session is working on them:

```bash
claude-sessions conflicts src/auth/*.ts
```

If conflicts exist:
```
Potential conflicts detected:

Session: ddc76ad6... (PID 43112)
  Working on: Implementing auth refactor
  Conflicting files: src/auth/login.ts, src/auth/session.ts
  CWD: /home/sfloess/myproject
```

### 3. Send a Message to Another Session

```bash
# Get the session ID from claude-sessions list, then:
claude-sessions send ddc76ad6 "I'm working on auth.ts, can you hold off?"
```

The other session will see this message in their inbox.

### 4. Broadcast to All Sessions

```bash
claude-sessions broadcast "CI build starting in 5 minutes, please pause commits"
```

### 5. Check Your Inbox

```bash
claude-sessions inbox
```

Output:
```
2 message(s):

[a1b2c3d4] message from ddc76ad6...
  Time: 2026-06-13T19:00:00.000Z
  Priority: normal
  Message: Got it, I'll wait until you're done with auth.ts

[e5f6g7h8] broadcast from 1bdb3e55...
  Time: 2026-06-13T19:05:00.000Z
  Priority: high
  Message: CI build starting in 5 minutes, please pause commits
```

### 6. Reply to a Message

```bash
claude-sessions reply a1b2c3d4 "Thanks! I'll be done in 10 minutes"
```

## Use Cases

### 1. Avoid Merge Conflicts

**Scenario**: Two sessions editing the same file

```bash
# Session A
claude-sessions conflicts src/components/Header.tsx

# Output: Session ddc76ad6 is editing Header.tsx
# Session A can wait or coordinate with Session B
```

### 2. Coordinate Deployments

**Scenario**: One session is deploying, others should pause

```bash
# Deploying session
claude-sessions broadcast "Deploying to production, hold all git pushes for 5 minutes"

# Other sessions receive the message and know to wait
```

### 3. Distribute Work Across Sessions

**Scenario**: You have 50 files to refactor, 3 sessions available

```bash
# Start the orchestrator
claude-sessions orchestrator start

# Enqueue work
claude-sessions orchestrator enqueue "Refactor file src/components/Button.tsx"
claude-sessions orchestrator enqueue "Refactor file src/components/Modal.tsx"
# ... (enqueue all 50 files)

# Orchestrator automatically distributes work to available sessions
# Sessions can request work:
node -e "
const SessionMessenger = require('~/.claude/lib/session-messenger.js');
const messenger = new SessionMessenger();
messenger.send('orchestrator', { type: 'work_request' });
"
```

### 4. Session Health Monitoring

**Scenario**: Track which sessions are active/stuck/crashed

```bash
# Check orchestrator status
claude-sessions orchestrator status

# View logs
claude-sessions orchestrator logs
```

## API Reference

### SessionRegistry

```javascript
const SessionRegistry = require('~/.claude/lib/session-registry.js');
const registry = new SessionRegistry();

// Register current session
registry.register(sessionId, {
  working_on: 'Description of work',
  files_locked: ['path/to/file1.ts', 'path/to/file2.ts'],
  status: 'active'
});

// Update heartbeat (keeps session alive)
registry.heartbeat(sessionId);

// Get all active sessions
const sessions = registry.getActiveSessions();

// Find conflicts
const conflicts = registry.findConflicts(['path/to/file.ts']);

// Unregister when done
registry.unregister(sessionId);
```

### SessionMessenger

```javascript
const SessionMessenger = require('~/.claude/lib/session-messenger.js');
const messenger = new SessionMessenger();

// Send message
messenger.send(toSessionId, {
  type: 'notification',
  priority: 'high',
  payload: 'Your message here',
  requires_response: false
});

// Broadcast
messenger.broadcast({
  payload: 'Message to all sessions'
});

// Receive messages
const messages = messenger.receive({
  unread_only: true,
  type: 'notification'
});

// Reply
messenger.reply(originalMessageId, 'Reply text');

// Mark as read
messenger.markRead(messageId);
```

### SessionOrchestrator

```javascript
const SessionOrchestrator = require('~/.claude/lib/session-orchestrator.js');
const orchestrator = new SessionOrchestrator();

// Enqueue work
orchestrator.enqueueWork({
  description: 'Refactor component',
  files: ['src/Component.tsx'],
  priority: 'high',
  estimatedCost: 'medium'
});

// Assign work to specific session
orchestrator.assignWork(workId, sessionId);

// Mark work complete
orchestrator.completeWork(workId, { success: true });

// Get status
const status = orchestrator.getStatus();
```

## Configuration

### Auto-Register Sessions

Add to `~/.claude/hooks/post-session-start.sh`:

```bash
#!/bin/bash
node ~/.claude/hooks/session-auto-register.js "Automated session registration"
```

### Heartbeat Interval

Edit `~/.claude/lib/session-registry.js`:

```javascript
const HEARTBEAT_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes (default)
```

### Message Expiration

Set expiration when sending:

```javascript
messenger.send(sessionId, {
  payload: 'Urgent message',
  expires_at: new Date(Date.now() + 60000).toISOString() // 1 minute
});
```

## Troubleshooting

### Sessions Not Appearing

**Problem**: `claude-sessions list` shows "No active sessions"

**Solution**:
1. Sessions must register themselves:
   ```bash
   node ~/.claude/hooks/session-auto-register.js "My work description"
   ```

2. Check session files exist:
   ```bash
   ls -la ~/.claude/sessions/*.json
   ```

3. Verify heartbeat timeout hasn't expired (default: 5 minutes)

### Messages Not Received

**Problem**: Sent message but recipient doesn't see it

**Solution**:
1. Check inbox directory:
   ```bash
   ls -la ~/.claude/sessions/messages/inbox/
   ```

2. Verify recipient session ID is correct:
   ```bash
   claude-sessions list  # Copy exact session ID
   ```

3. Check message hasn't expired

### Orchestrator Won't Start

**Problem**: `claude-sessions orchestrator start` fails

**Solution**:
1. Check if already running:
   ```bash
   cat ~/.claude/orchestrator/orchestrator.pid
   ps aux | grep session-orchestrator
   ```

2. Kill stale process:
   ```bash
   claude-sessions orchestrator stop
   ```

3. Check logs:
   ```bash
   claude-sessions orchestrator logs
   ```

## Advanced Patterns

### Distributed Workflow

```javascript
// Main session orchestrates, worker sessions execute
// main-session.js
const orchestrator = new SessionOrchestrator();

const tasks = [
  { description: 'Run tests', files: ['test/**/*.spec.ts'] },
  { description: 'Lint code', files: ['src/**/*.ts'] },
  { description: 'Build docs', files: ['docs/**/*.md'] }
];

for (const task of tasks) {
  orchestrator.enqueueWork(task);
}

// worker-session.js
const messenger = new SessionMessenger();
messenger.send('orchestrator', { type: 'work_request' });

// Listen for work assignment
setInterval(() => {
  const messages = messenger.receive({ type: 'work_assignment' });
  for (const msg of messages) {
    const work = msg.payload;
    // Execute work...
    messenger.send('orchestrator', {
      type: 'work_complete',
      payload: { workId: work.id, result: { success: true } }
    });
    messenger.markRead(msg.id);
  }
}, 5000);
```

### Conflict-Free Parallel Editing

```javascript
// Before editing files
const registry = new SessionRegistry();
const files = ['src/auth/login.ts', 'src/auth/session.ts'];

const conflicts = registry.findConflicts(files);
if (conflicts.length > 0) {
  console.log('WARNING: Other sessions editing these files:');
  for (const conflict of conflicts) {
    console.log(`  - Session ${conflict.sessionId}: ${conflict.working_on}`);
  }
  
  // Wait or coordinate
  const messenger = new SessionMessenger();
  messenger.send(conflicts[0].sessionId, {
    payload: 'Can I edit auth files? I need them for my task.',
    requires_response: true
  });
} else {
  // Safe to edit
  registry.register(sessionId, { files_locked: files });
  // ... do work ...
  registry.register(sessionId, { files_locked: [] }); // Release lock
}
```

## Future Enhancements

- [ ] Web UI for session dashboard
- [ ] Session recording/replay
- [ ] Automatic conflict resolution suggestions
- [ ] Session clustering (group sessions by project)
- [ ] Remote session support (coordinate across machines)
- [ ] Integration with git hooks (auto-detect conflicts on commit)

## Related Files

- `~/.claude/lib/session-registry.js` - Session tracking
- `~/.claude/lib/session-messenger.js` - Inter-session messaging
- `~/.claude/lib/session-orchestrator.js` - Work distribution
- `~/.claude/bin/claude-sessions` - CLI tool
- `~/.claude/hooks/session-auto-register.js` - Auto-registration hook
- `~/.claude/sessions/registry.json` - Active session registry
- `~/.claude/sessions/messages/` - Message queue
- `~/.claude/orchestrator/` - Orchestrator state and logs
