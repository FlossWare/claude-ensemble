# Session Awareness - Making Sessions Know About Each Other

## Problem

Sessions don't automatically know:
- What other sessions exist
- What they're working on
- If they're editing the same files
- When commits happen
- When conflicts arise

## Solution: Active Session Awareness

Every session now **actively monitors and broadcasts** its activity to all other sessions via pi-02.

## How It Works

```
┌─────────────────────────────────────────────────────┐
│                    pi-02:3002                        │
│  Activity Hub & Message Broker                      │
│  ├─ Tracks all session activity                     │
│  ├─ Broadcasts changes to all sessions              │
│  └─ Detects conflicts in real-time                  │
└─────────────────────────────────────────────────────┘
         ▲          ▲          ▲          ▲
         │          │          │          │
    ┌────┴──┐  ┌───┴───┐  ┌───┴───┐  ┌───┴───┐
    │Sess A │  │Sess B │  │Sess C │  │Sess D │
    │Monitor│  │Monitor│  │Monitor│  │Monitor│
    │Notify │  │Notify │  │Notify │  │Notify │
    └───────┘  └───────┘  └───────┘  └───────┘
```

## What Gets Broadcast

### 1. Session Presence

When a session starts:
```
🔔 New Session Detected
───────────────────────────────────────────────────────
Session abc12345... started on server-01
Working on: Implementing OAuth login
```

### 2. File Changes

When files are edited:
```
🔔 File Changed on server-01
───────────────────────────────────────────────────────
Session abc12345... modified: src/auth/login.ts,src/auth/oauth.ts
```

### 3. Git Commits

When commits are made:
```
🔔 Git Commit on server-01
───────────────────────────────────────────────────────
Session abc12345...: feat: add OAuth provider integration (3 files)
```

### 4. Task Changes

When work shifts:
```
🔔 Task Update on server-01
───────────────────────────────────────────────────────
Session abc12345... is now: Code review for PR #456
```

### 5. Conflict Warnings

When editing same files:
```
⚠️  FILE CONFLICT DETECTED
───────────────────────────────────────────────────────
You are editing files that another session is working on:

src/auth/login.ts: abc12345... on server-01

Coordinate before continuing!
```

## Setup

### Option 1: Manual Start

In each session:

```bash
# Announce presence and start monitoring
~/.claude/lib/session-awareness.sh start
```

This will:
1. Announce your session to the fleet
2. Show current fleet status
3. Monitor for changes every 10s
4. Notify you of activity from other sessions

### Option 2: Auto-Start (Recommended)

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "session-start": "~/.claude/hooks/session-awareness-auto.sh"
  }
}
```

Now every session automatically:
- Announces its presence
- Monitors fleet activity
- Receives notifications

## Usage

### See Fleet Status Anytime

```bash
~/.claude/lib/session-awareness.sh status
```

Output:
```
╔════════════════════════════════════════════════════════╗
║           FLEET STATUS - 18:55:36                    ║
╠════════════════════════════════════════════════════════╣
║ Total Sessions: 3                                  ║
╚════════════════════════════════════════════════════════╝

Node: laptop-01
  • Session 1bdb3e55... (PID 97265)
    Working on: Deploying pi-02 integration

Node: server-01
  • Session abc12345... (PID 45678)
    Working on: Implementing OAuth login

Node: server-02
  • Session def67890... (PID 91011)
    Working on: Code review
```

### Announce Your Presence

```bash
~/.claude/lib/session-awareness.sh announce
```

### Check for Conflicts Now

```bash
~/.claude/lib/session-awareness.sh check-conflicts
```

### Set Your Current Task

```bash
~/.claude/lib/session-activity-tracker.sh task "Implementing feature X"
```

This broadcasts to all sessions:
```
🔔 Task Update on laptop-01
───────────────────────────────────────────────────────
Session 1bdb3e55... is now: Implementing feature X
```

## What Sessions See

### Session A (laptop-01)

```bash
$ # Working on auth implementation
$ vim src/auth/login.ts

# Sees notification:
🔔 File Changed on server-01
───────────────────────────────────────────────────────
Session abc12345... modified: src/auth/login.ts
```

**Now Session A knows:** Someone else is also working on `login.ts`!

### Session B (server-01)

```bash
$ git commit -m "feat: add OAuth provider"

# All other sessions see:
🔔 Git Commit on server-01
───────────────────────────────────────────────────────
Session abc12345...: feat: add OAuth provider (3 files)
```

**Everyone knows:** OAuth work was just committed on server-01.

### Session C (server-02)

```bash
$ # About to edit login.ts
$ vim src/auth/login.ts

# Immediately sees:
⚠️  FILE CONFLICT DETECTED
───────────────────────────────────────────────────────
You are editing files that another session is working on:

src/auth/login.ts: abc12345... on server-01, 1bdb3e55... on laptop-01

Coordinate before continuing!
```

**Session C knows to coordinate first!**

## Activity Log

All notifications are logged to `~/.claude/.session-awareness.log`:

```bash
tail -f ~/.claude/.session-awareness.log
```

```
[2026-06-13T18:55:00Z] New Session Detected: Session abc12345... started on server-01
[2026-06-13T18:56:15Z] Task Update on server-01: Session abc12345... is now: Implementing OAuth login
[2026-06-13T18:57:30Z] File Changed on server-01: Session abc12345... modified: src/auth/login.ts
[2026-06-13T18:58:45Z] Git Commit on server-01: Session abc12345...: feat: add OAuth provider (3 files)
```

## Desktop Notifications

If `notify-send` is available (Linux desktop):

```bash
sudo apt-get install libnotify-bin  # Ubuntu/Debian
```

You'll get desktop popup notifications for critical events (conflicts, commits).

## Broadcast Types

| Event | Urgency | When |
|-------|---------|------|
| Session Joined | Normal | New session detected |
| File Changed | Low | Files edited in last 10s |
| Git Commit | Normal | Commit detected |
| Task Update | Low | Task description changed |
| Conflict Warning | **Critical** | Editing same files |

## Integration with Workflows

Workflows can broadcast activity:

```javascript
// In workflow script
const { execSync } = require('child_process');

// Broadcast workflow start
execSync(`~/.claude/lib/session-activity-tracker.sh broadcast workflow_start "Running code review workflow"`);

// During workflow
for (const file of files) {
  execSync(`~/.claude/lib/session-activity-tracker.sh broadcast file_processing "${file}"`);
  // ... process file
}

// Broadcast completion
execSync(`~/.claude/lib/session-activity-tracker.sh broadcast workflow_complete "Code review complete: ${findings.length} issues"`);
```

All sessions see:
```
🔔 Workflow Started on laptop-01
───────────────────────────────────────────────────────
Running code review workflow

🔔 Workflow Complete on laptop-01
───────────────────────────────────────────────────────
Code review complete: 5 issues
```

## Monitoring Fleet Activity

### Real-Time View

```bash
# Terminal 1: Fleet status
watch -n 5 '~/.claude/lib/session-awareness.sh status'

# Terminal 2: Activity log
tail -f ~/.claude/.session-awareness.log

# Terminal 3: pi-02 logs
ssh pi-02 tail -f ~/fleet-coordinator/logs/job-queue.log
```

### Check Who's Working on What

```bash
~/.claude/bin/claude-sessions-pi02 list
```

```
Session: 1bdb3e55... (PID 97265)
  Node: laptop-01
  CWD: /home/sfloess
  Working on: Implementing feature X
  Files locked: src/auth/login.ts, src/auth/oauth.ts

Session: abc12345... (PID 45678)
  Node: server-01
  CWD: /workspace/project
  Working on: Code review
```

## Best Practices

### 1. Always Set Your Task

```bash
~/.claude/lib/session-activity-tracker.sh task "Your current task"
```

This helps others understand what you're doing.

### 2. Check Status Before Big Changes

```bash
~/.claude/lib/session-awareness.sh status
~/.claude/lib/session-awareness.sh check-conflicts
```

### 3. Coordinate on Conflicts

When you get a conflict warning:
- Check who's working on it: `claude-sessions-pi02 list`
- Send a message: `claude-sessions-pi02 send <sessionId> "Let's coordinate on auth.ts"`
- Wait for them to finish or work on different area

### 4. Announce Major Work

```bash
~/.claude/lib/session-activity-tracker.sh broadcast major_refactor "Starting auth module refactor, will take 30min"
```

## Troubleshooting

### Not seeing notifications?

```bash
# Check if awareness is running
ps aux | grep session-awareness

# Restart it
~/.claude/lib/session-awareness.sh start
```

### Missing other sessions?

```bash
# Check pi-02 connection
curl http://pi-02:3002/sessions/list

# Re-announce presence
~/.claude/lib/session-awareness.sh announce
```

### Too many notifications?

Edit `~/.claude/lib/session-awareness.sh` and increase `CHECK_INTERVAL`:

```bash
CHECK_INTERVAL=30  # Check every 30s instead of 10s
```

## Files

- `~/.claude/lib/session-awareness.sh` - Main awareness system
- `~/.claude/lib/session-activity-tracker.sh` - Activity monitoring
- `~/.claude/hooks/session-awareness-auto.sh` - Auto-start hook
- `~/.claude/.session-awareness.log` - Activity log
- `~/.claude/.known-sessions` - Tracked sessions

## Summary

✅ **Sessions now actively know about each other**

Every session:
- Announces its presence
- Broadcasts activity (file edits, commits, task changes)
- Receives notifications from other sessions
- Detects conflicts in real-time
- Shows fleet status on demand

No more surprise conflicts or wondering "did someone else change this?"
