# pi-02 Fleet Orchestrator - Session Integration

## Current pi-02 Services

pi-02 is your existing fleet orchestrator running:

```
~/fleet-coordinator/services/
├── pi02-health-monitor.py       # Monitors fleet node health
├── pi02-job-queue.py            # Job dispatch API (Flask)
├── pi02-workflow-dispatcher.py  # Workflow distribution
├── pi02-log-collector.py        # Centralized logging
└── status-api.py                # Fleet status API
```

## Integration Strategy

Instead of building a parallel system, **extend pi-02's existing infrastructure**:

### 1. Add Session Tracking to Existing Services

**Option A: Extend job-queue.py**

Add session registration endpoint to the existing Flask API:

```python
# In pi02-job-queue.py

@app.route('/sessions/register', methods=['POST'])
def register_session():
    """Register a Claude Code session"""
    data = request.json
    session_id = data.get('sessionId')
    node = data.get('node')
    pid = data.get('pid')
    cwd = data.get('cwd')
    
    # Store in sessions dict or database
    sessions[session_id] = {
        'node': node,
        'pid': pid,
        'cwd': cwd,
        'registered_at': datetime.now().isoformat(),
        'last_heartbeat': datetime.now().isoformat()
    }
    
    return jsonify({'status': 'registered'})

@app.route('/sessions/list', methods=['GET'])
def list_sessions():
    """List all active sessions"""
    return jsonify(sessions)

@app.route('/sessions/heartbeat', methods=['POST'])
def heartbeat():
    """Update session heartbeat"""
    data = request.json
    session_id = data.get('sessionId')
    
    if session_id in sessions:
        sessions[session_id]['last_heartbeat'] = datetime.now().isoformat()
        return jsonify({'status': 'updated'})
    else:
        return jsonify({'error': 'session not found'}), 404
```

**Option B: Standalone session tracker (deployed separately)**

Deploy `pi02-session-tracker.py` that integrates with existing services.

### 2. Client-Side Integration

Each Claude session registers with pi-02 on startup:

```bash
# In Claude session init hook (~/.claude/hooks/session-start.sh)

SESSION_ID=$(jq -r .sessionId ~/.claude/sessions/$(ls -t ~/.claude/sessions/*.json | head -1))
NODE=$(hostname)
PID=$$
CWD=$(pwd)

# Register with pi-02
curl -X POST http://pi-02:5000/sessions/register \
  -H "Content-Type: application/json" \
  -d "{
    \"sessionId\": \"$SESSION_ID\",
    \"node\": \"$NODE\",
    \"pid\": $PID,
    \"cwd\": \"$CWD\"
  }"

# Heartbeat every 60s
(
  while true; do
    sleep 60
    curl -X POST http://pi-02:5000/sessions/heartbeat \
      -H "Content-Type: application/json" \
      -d "{\"sessionId\": \"$SESSION_ID\"}"
  done
) &
```

### 3. CLI Tool Integration

Update `claude-sessions` to query pi-02 instead of local files:

```bash
# List all sessions across fleet
claude-sessions list

# Internally calls:
curl http://pi-02:5000/sessions/list | jq
```

### 4. Work Distribution via pi-02

Use existing job queue for session work assignment:

```bash
# Submit work to pi-02
curl -X POST http://pi-02:5000/jobs/submit \
  -d '{
    "type": "claude-task",
    "description": "Review PR #123",
    "target_session": "auto"  # pi-02 selects best session
  }'
```

pi-02 job queue already has:
- Worker selection logic
- Load balancing
- Job status tracking

## Recommended Architecture

```
┌─────────────────────────────────────────────────┐
│                    pi-02                         │
│  ┌─────────────────────────────────────────┐    │
│  │  Flask API (port 5000)                   │    │
│  │  ├─ /jobs/*          (existing)          │    │
│  │  ├─ /health/*        (existing)          │    │
│  │  └─ /sessions/*      (NEW)               │    │
│  │      ├─ /register                        │    │
│  │      ├─ /list                            │    │
│  │      ├─ /heartbeat                       │    │
│  │      └─ /conflicts                       │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
         ▲          ▲          ▲          ▲
         │          │          │          │
    ┌────┴──┐  ┌───┴───┐  ┌───┴───┐  ┌───┴───┐
    │aio-01 │  │srv-01 │  │srv-02 │  │srv-03 │
    │Session│  │Session│  │Session│  │Session│
    │  A    │  │  B    │  │  C    │  │  D    │
    └───────┘  └───────┘  └───────┘  └───────┘
```

## Implementation Steps

### Step 1: Extend pi-02 Job Queue API

```bash
# SSH to pi-02
ssh pi-02

# Edit job queue to add session endpoints
nano ~/fleet-coordinator/services/pi02-job-queue.py
```

Add the session endpoints shown above.

### Step 2: Restart pi-02 Services

```bash
ssh pi-02 "cd ~/fleet-coordinator/services && \
  pkill -f pi02-job-queue && \
  nohup python3 pi02-job-queue.py > ../logs/job-queue.log 2>&1 &"
```

### Step 3: Deploy Client Hooks

Create `~/.claude/hooks/session-start.sh` on each node:

```bash
for node in aio-01 server-01 server-02 server-03; do
  scp ~/.claude/hooks/session-start.sh $node:~/.claude/hooks/
  ssh $node "chmod +x ~/.claude/hooks/session-start.sh"
done
```

### Step 4: Update claude-sessions CLI

Modify `~/.claude/bin/claude-sessions` to call pi-02 API instead of local files.

## Benefits of pi-02 Integration

✅ **Centralized orchestration** - Single source of truth  
✅ **Reuse existing infrastructure** - Job queue, health monitoring  
✅ **Single API** - All fleet management through one endpoint  
✅ **Proven reliability** - pi-02 already stable and running  
✅ **No parallel systems** - Avoid maintenance duplication  

## Quick Start (Manual Testing)

```bash
# Test pi-02 API connectivity
curl http://pi-02:5000/health

# Register a test session
curl -X POST http://pi-02:5000/sessions/register \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-123",
    "node": "aio-01",
    "pid": 12345,
    "cwd": "/home/sfloess"
  }'

# List sessions
curl http://pi-02:5000/sessions/list | jq
```

## Next Steps

1. [ ] Add `/sessions/*` endpoints to `pi02-job-queue.py`
2. [ ] Deploy session registration hooks to fleet nodes
3. [ ] Update `claude-sessions` CLI to use pi-02 API
4. [ ] Test cross-session visibility
5. [ ] Integrate with workflows

## Comparison: Local Files vs pi-02 API

| Feature | Local Files | pi-02 API |
|---------|-------------|-----------|
| Visibility | Single node only | Fleet-wide |
| State | Distributed | Centralized |
| Reliability | File locks | Proven Flask API |
| Work queue | Separate daemon | Existing job queue |
| Monitoring | New code | Existing health checks |
| Maintenance | New system | Extend existing |

**Recommendation:** Use pi-02 API approach for production fleet coordination.
