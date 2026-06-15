---
name: session-tracking-enabled
description: All Claude sessions auto-register with orchestrator for fleet coordination
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  relates_to: 
    - - feedback_always_use_orchestrator
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

All Claude sessions automatically register with the pi-02 orchestrator for fleet-wide coordination.

**Why:** Enables sessions to see each other's work, communicate, and coordinate across the fleet.

**How it works:**
1. On session start: Auto-register with orchestrator
2. Every 60s: Send heartbeat with current work status
3. Check for messages from other sessions
4. On session end: Auto-unregister

**Endpoints:**
- Register: `POST http://pi-02:3002/sessions/register`
- Heartbeat: `POST http://pi-02:3002/sessions/heartbeat`
- List sessions: `GET http://pi-02:3002/sessions/list`
- Send message: `POST http://pi-02:3002/sessions/send`
- Broadcast: `POST http://pi-02:3002/sessions/broadcast`

**Configuration:**
- Hooks: `~/.claude/hooks/session-register.sh`, `session-unregister.sh`
- Settings: `~/.claude/settings.json` (orchestrator.auto_register: true)
- Session ID: `~/.claude/.session-id`
- Heartbeat PID: `~/.claude/.session-heartbeat-pid`

**Usage:**
```bash
# List all active sessions
curl http://pi-02:3002/sessions/list

# Send message to another session
curl -X POST http://pi-02:3002/sessions/send \
  -d '{"from":"my-session","to":"other-session","message":"Status update"}'

# Broadcast to all sessions
curl -X POST http://pi-02:3002/sessions/broadcast \
  -d '{"from":"my-session","message":"Deep learning complete!"}'
```

**Benefits:**
- Sessions can see what others are working on
- Avoid duplicate work
- Share results and coordinate
- Fleet-wide visibility

**Related:** [[feedback_always_use_orchestrator]] - Always use orchestrator for work
