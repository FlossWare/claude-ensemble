# RH Learning Service

Central learning authority for autonomous task outcome recording and analysis. Runs as a systemd user service and provides a Unix socket API for sessions to record task results and retrieve learning summaries.

## Architecture

- **Single-threaded daemon**: No race conditions, owns all state
- **Unix socket IPC**: Fast local communication on `/tmp/rh-learning.sock`
- **State persistence**: JSON files in `~/.claude/projects/-home-sfloess/learning/`
- **Thompson integration**: Records outcomes to update model routing decisions
- **Graceful degradation**: Client continues if daemon unavailable

## Installation

```bash
cd learning-service
./install.sh
```

This will:
1. Copy `rh-learning.service` to `~/.config/systemd/user/`
2. Reload systemd user daemon
3. Enable the service for auto-start
4. Start the service immediately

## Usage

### From Sessions (Client Library)

```python
from learning.learning_client import LearningClient

client = LearningClient()

# Record a task outcome
success = client.process_outcome(
    task_id='task_001',
    task_type='code-review',
    model='haiku',
    rating=4,  # 0-5, user's rating of result quality
    tokens=2800,
    cost=0.01
)

# Get learning summary
report = client.get_report()
print(report)
# Output:
# {
#   'ok': True,
#   'total_outcomes': 42,
#   'date_range': '30 days',
#   'by_model': {
#     'haiku': {'count': 20, 'avg_rating': 3.8, 'total_cost': 0.15},
#     'sonnet': {'count': 15, 'avg_rating': 4.2, 'total_cost': 0.75},
#     'opus': {'count': 7, 'avg_rating': 4.6, 'total_cost': 0.42}
#   },
#   'by_task_type': {
#     'code-review': {'count': 20, 'avg_rating': 4.1},
#     'documentation': {'count': 15, 'avg_rating': 3.9},
#     'testing': {'count': 7, 'avg_rating': 4.3}
#   }
# }

# Get recent outcomes
outcomes = client.get_recent_outcomes(days=7)
for outcome in outcomes:
    print(f"{outcome['task_id']}: {outcome['model']} rating={outcome['rating']}")

# Reset learning (clear all data)
client.reset_learning()
```

### Service Management

Check status:
```bash
systemctl --user status rh-learning.service
```

View logs:
```bash
journalctl --user -u rh-learning.service -f
```

Restart:
```bash
systemctl --user restart rh-learning.service
```

Stop:
```bash
systemctl --user stop rh-learning.service
```

## API Specification

The service listens on Unix socket `/tmp/rh-learning.sock` and accepts JSON requests (one per connection).

### Request Format
All requests are JSON objects ending with newline:
```json
{"op": "operation_name", "param1": "value1", ...}
```

### Operations

#### `process_outcome`
Record a task outcome and update learning statistics.

Request:
```json
{
  "op": "process_outcome",
  "task_id": "unique_task_id",
  "task_type": "code-review",
  "model": "haiku",
  "rating": 4,
  "tokens": 2800,
  "cost": 0.01
}
```

Response:
```json
{"ok": true}
```

Side effects:
- Saves outcome to `learning/autonomous_outcomes/{task_id}_{timestamp}.json`
- Updates Thompson router with outcome (rating >= 3 counts as success)

#### `get_report`
Get learning summary across 30 days.

Request:
```json
{"op": "get_report"}
```

Response:
```json
{
  "ok": true,
  "total_outcomes": 42,
  "date_range": "30 days",
  "by_model": {
    "haiku": {"count": 20, "avg_rating": 3.8, "total_cost": 0.15},
    "sonnet": {"count": 15, "avg_rating": 4.2, "total_cost": 0.75}
  },
  "by_task_type": {
    "code-review": {"count": 20, "avg_rating": 4.1},
    "documentation": {"count": 15, "avg_rating": 3.9}
  }
}
```

#### `get_recent_outcomes`
Get recent task outcomes (default 7 days).

Request:
```json
{"op": "get_recent_outcomes", "days": 7}
```

Response:
```json
{
  "ok": true,
  "outcomes": [
    {
      "task_id": "task_001",
      "task_type": "code-review",
      "model": "haiku",
      "rating": 4,
      "tokens": 2800,
      "cost": 0.01,
      "timestamp": "2026-09-26T22:36:43.123456"
    }
  ]
}
```

#### `reset_learning`
Clear all outcomes and priors from the learning system.

Request:
```json
{"op": "reset_learning"}
```

Response:
```json
{"ok": true}
```

Side effects:
- Removes all files from `learning/autonomous_outcomes/`
- Removes all files from `learning/autonomous_priors/`

#### `ping`
Health check / connectivity test.

Request:
```json
{"op": "ping"}
```

Response:
```json
{"ok": true, "message": "pong"}
```

## State Files

### Outcomes Directory
Location: `~/.claude/projects/-home-sfloess/learning/autonomous_outcomes/`

One JSON file per outcome:
```
{
  "task_id": "task_001",
  "task_type": "code-review",
  "model": "haiku",
  "rating": 4,
  "tokens": 2800,
  "cost": 0.01,
  "timestamp": "2026-09-26T22:36:43.123456"
}
```

### Priors Directory
Location: `~/.claude/projects/-home-sfloess/learning/autonomous_priors/`

Stores Beta distribution priors for each model (optional, updated by Thompson service).

## Graceful Degradation

If the daemon is not running:
- `LearningClient._send_request()` returns `{'ok': False, 'error': '...'}`
- `process_outcome()` returns `False`
- `get_report()` returns `{'ok': False, 'error': '...'}`
- Sessions continue without blocking (learning just doesn't get recorded)

No error is raised; clients should assume local-only mode.

## Integration with Thompson Router

When `process_outcome` is called:
1. Outcome is recorded to `autonomous_outcomes/`
2. Learning service calls `ThompsonClient.record_outcome()`
3. Thompson router updates Beta priors for that model
4. Next task's model selection uses improved priors

Success threshold: rating >= 3 (0-5 scale)

## Testing

Run comprehensive test suite:
```bash
python3 learning-service/test_learning_service.py
```

Tests cover:
- Ping/connectivity
- Recording outcomes
- Report generation
- Recent outcomes retrieval
- Multi-model tracking
- Reset functionality

## Files

- `learning_service.py` - Main daemon (339 lines)
- `rh-learning.service` - Systemd unit file
- `install.sh` - Installation script
- `test_learning_service.py` - Test suite
- `../learning_client.py` - Client library

## Logs

Service logs to:
- Standard output (systemd journal)
- `~/.claude/rh-learning-service.log`

View with:
```bash
journalctl --user -u rh-learning.service -f
tail -f ~/.claude/rh-learning-service.log
```

## Resource Limits

Configured in systemd unit:
- Memory: 512 MB max
- CPU: 50% quota
- Auto-restart on failure (10-second backoff)

## Design Notes

### Single-threaded Architecture
The daemon handles clients sequentially (no threads). This provides:
- Simplicity (no locks needed)
- Correctness (no race conditions on state)
- Sufficient throughput (learning calls are infrequent)

### File Locking
Not used (single-threaded daemon owns state exclusively).
Each outcome gets a unique filename with timestamp to prevent collisions.

### Socket Cleanup
Daemon removes socket on startup if it exists (from previous crash).
Socket is removed on shutdown.

### Error Handling
All errors are caught and returned as JSON:
- Socket timeout → `{"ok": false, "error": "timeout"}`
- Invalid JSON → `{"ok": false, "error": "Invalid JSON"}`
- Missing operation → `{"ok": false, "error": "Unknown operation: ..."}`
- File I/O errors → logged, `{"ok": false}`
