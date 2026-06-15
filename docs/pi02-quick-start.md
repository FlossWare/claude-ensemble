# pi-02 Fleet Orchestration - Quick Start Guide

## ✅ What's Deployed

**pi-02 orchestrator** is running and managing session coordination across your fleet.

## Quick Commands

```bash
# View all sessions across fleet
~/.claude/bin/claude-sessions-pi02 list

# Register current session with pi-02
~/.claude/lib/pi02-session-client.sh register

# Send heartbeat (let pi-02 know you're alive)
~/.claude/lib/pi02-session-client.sh heartbeat "Working on XYZ"

# Check if anyone is working on these files
~/.claude/bin/claude-sessions-pi02 conflicts src/auth/*.ts

# Fleet-wide status
~/.claude/bin/claude-sessions-pi02 status
```

## Typical Workflow

### 1. Start New Session

When you start working in a new Claude session:

```bash
# Register and start automatic heartbeat
~/.claude/lib/pi02-session-client.sh start-heartbeat
```

This will:
- Register your session with pi-02
- Start background heartbeat (every 60s)
- Auto-unregister when you exit

### 2. Before Editing Files

Check for conflicts:

```bash
~/.claude/bin/claude-sessions-pi02 conflicts path/to/file.ts
```

If conflicts detected:
```
⚠️  Conflicts detected!

File: path/to/file.ts
  Session abc12345... on server-01 (PID 45678)
  Working on: Refactoring authentication
```

Coordinate with that session before proceeding.

### 3. Update Your Status

Let others know what you're working on:

```bash
~/.claude/lib/pi02-session-client.sh heartbeat "Implementing OAuth login"
```

### 4. See What Others Are Doing

```bash
~/.claude/bin/claude-sessions-pi02 list
```

Output:
```
Session: 1bdb3e55... (PID 97265)
  Node: laptop-01
  CWD: /home/sfloess
  Age: 0s
  Working on: Implementing OAuth login

Session: abc12345... (PID 45678)
  Node: server-01
  CWD: /workspace/project
  Age: 120s
  Working on: Code review
```

### 5. When Done

```bash
~/.claude/lib/pi02-session-client.sh unregister
```

Or just exit - background heartbeat will auto-cleanup.

## API Endpoints (for automation)

### Register Session
```bash
curl -X POST http://pi-02:3002/sessions/register \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "your-session-id",
    "node": "laptop-01",
    "pid": 12345,
    "cwd": "/home/user/project",
    "working_on": "Feature XYZ"
  }'
```

### List Sessions
```bash
curl http://pi-02:3002/sessions/list | jq
```

### Check Conflicts
```bash
curl -X POST http://pi-02:3002/sessions/conflicts \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["src/auth/login.ts", "src/auth/oauth.ts"]
  }' | jq
```

### Fleet Status
```bash
curl http://pi-02:3002/status | jq
```

## Integration with Workflows

Use in workflow scripts:

```javascript
// Register workflow session
const axios = require('axios');

await axios.post('http://pi-02:3002/sessions/register', {
  sessionId: args.sessionId,
  node: os.hostname(),
  pid: process.pid,
  cwd: process.cwd(),
  working_on: 'Running code review workflow'
});

// Check conflicts
const conflicts = await axios.post('http://pi-02:3002/sessions/conflicts', {
  files: ['src/auth/*']
});

if (conflicts.data.has_conflicts) {
  log('⚠️  Conflicts detected, waiting...');
  // Wait or coordinate
}

// Heartbeat during long operations
setInterval(async () => {
  await axios.post('http://pi-02:3002/sessions/heartbeat', {
    sessionId: args.sessionId,
    working_on: `Progress: ${currentStep}`
  });
}, 60000);
```

## Monitoring

### Real-time Fleet View

```bash
watch -n 5 '~/.claude/bin/claude-sessions-pi02 list'
```

### pi-02 Logs

```bash
ssh pi-02 tail -f ~/fleet-coordinator/logs/job-queue.log
```

### Health Check

```bash
curl http://pi-02:3002/health
```

```json
{
  "status": "ok",
  "service": "pi-02-job-queue",
  "active_sessions": 1,
  "active_work": 0
}
```

## Troubleshooting

### Session not showing up?

```bash
# Check if registered
curl http://pi-02:3002/sessions/list | jq '.sessions[] | select(.node == "laptop-01")'

# Re-register
~/.claude/lib/pi02-session-client.sh register
```

### Can't reach pi-02?

```bash
# Test connectivity
curl http://pi-02:3002/health

# Check if service running
ssh pi-02 "ps aux | grep pi02-job-queue"
```

### Stale sessions?

Sessions auto-expire after 5 minutes of no heartbeat. Force cleanup:

```bash
curl http://pi-02:3002/health
```

This triggers cleanup of stale sessions.

## Next Steps

- [ ] Set up auto-registration hooks
- [ ] Integrate with workflows
- [ ] Add session groups for team coordination
- [ ] Build web dashboard for visualization

## Files Reference

- `pi-02:~/fleet-coordinator/services/pi02-job-queue.py` - Orchestrator API
- `~/.claude/lib/pi02-session-client.sh` - Client library  
- `~/.claude/bin/claude-sessions-pi02` - CLI tool
- `~/.claude/docs/pi02-integration-complete.md` - Full documentation
