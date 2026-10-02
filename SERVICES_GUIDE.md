# Claude Ensemble AI Toolkit — Services Guide

Six systemd user services for orchestration, learning, routing, alerts, inter-session messaging, and the local Graph HTTP boundary.

---

## Services Overview

| Service | Purpose | Socket | Docs |
|---------|---------|--------|------|
| **Memory** | Concurrent-safe shared state across sessions | `$XDG_RUNTIME_DIR/claude-ensemble/memory.sock` | `memory-service/README.md` |
| **Thompson** | Model selection via Bayesian sampling | `$XDG_RUNTIME_DIR/claude-ensemble/thompson.sock` | `thompson-service/README.md` |
| **Learning** | Task outcome recording and learning | `$XDG_RUNTIME_DIR/claude-ensemble/learning.sock` | `learning-service/README.md` |
| **Alert** | Anomaly detection and email alerts | `$XDG_RUNTIME_DIR/claude-ensemble/alert.sock` | `alert_service/README.md` |
| **Messenger** | Topic-based pub/sub for inter-session commands | `$XDG_RUNTIME_DIR/claude-messenger/claude-messenger.sock` | `session-messaging/README.md` |
| **Graph** | Local durable graph HTTP service | `127.0.0.1:8766` | `graph-service/README.md` |

---

## Universal Commands

### Start All Services

```bash
systemctl --user start claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service claude-graph.service
```

### Stop All Services

```bash
systemctl --user stop claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

### Restart All Services

```bash
systemctl --user restart claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

### Check Status

```bash
systemctl --user status claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

### Enable Auto-Start (on login)

```bash
systemctl --user enable claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

### Disable Auto-Start

```bash
systemctl --user disable claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

### Watch Logs (all services)

```bash
journalctl --user -f
```

### Watch Logs (single service)

```bash
journalctl --user-unit claude-thompson.service -f
journalctl --user-unit claude-learning.service -f
journalctl --user-unit claude-alert.service -f
```

---

## Data Flow

```
Task Execution
    ↓
  rh-api-wrapper.py
    ↓
  Thompson (select best model)
    ↓
  Execute task with selected model
    ↓
  Task complete
    ↓
  Learning service (record outcome)
    ↓
  Compare: user rating vs consensus rating
    ↓
  Thompson (update model performance)
    ↓
  Alert service (check for anomalies)
    ↓
  Email alert if cost spike or quality drop
    ↓
  Next task (Thompson has learned)
```

---

## Quick Diagnostics

### Check All Sockets Listening

```bash
ls -la $XDG_RUNTIME_DIR/claude-ensemble/ 2>/dev/null || ls -la ~/.cache/claude-ensemble/
# Should show: memory, thompson, learning, alert sockets
# Messenger socket will be under: $XDG_RUNTIME_DIR/claude-messenger/
```

### Test Thompson

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from shared.thompson_client import ThompsonClient
tc = ThompsonClient()
model = tc.select_model("code_review")
print(f"Thompson responds: {model}")
EOF
```

### Test Learning

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from learning.learning_client import LearningClient
lc = LearningClient()
report = lc.get_report()
print(f"Learning responds: {report.get('total_outcomes')} outcomes")
EOF
```

### Test Alert

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from tools.alert_client import AlertClient
ac = AlertClient()
result = ac.trigger_check()
print(f"Alert responds: {result}")
EOF
```

---

## Troubleshooting

### Service fails to start

```bash
# Check why
journalctl --user-unit claude-SERVICENAME.service -n 20

# Restart
systemctl --user restart claude-SERVICENAME.service
```

### Services won't communicate

```bash
# Are all sockets present?
ls /tmp/rh-*.sock

# Are all services running?
systemctl --user status claude-*.service

# Try restarting all
systemctl --user restart claude-thompson.service claude-learning.service claude-alert.service
```

### Stale socket files

```bash
# Remove stale sockets (memory, thompson, learning, alert)
rm -f ~/.cache/claude-ensemble/*.sock

# Remove messenger socket if stale
rm -rf ~/.cache/claude-messenger/

# Restart services
systemctl --user restart claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

---

## Performance Monitoring

### Thompson Model Distribution

```bash
cat learning/thompson-sampling-state.json | jq '.models | to_entries[] | "\(.key): \(.value.calls) calls, \(.value.successes) successes"'
```

### Learning Outcomes

```bash
# Count outcomes
ls learning/post_task_outcomes/ | wc -l

# Recent outcomes
ls -lt learning/post_task_outcomes/ | head -5

# Summary
python3 << 'EOF'
import json
from pathlib import Path
outcomes_dir = Path("learning/post_task_outcomes")
outcomes = [json.loads(f.read_text()) for f in outcomes_dir.glob("*.json")]
print(f"Total: {len(outcomes)}")
print(f"Models: {set(o['outcome']['model_used'] for o in outcomes)}")
print(f"Avg rating: {sum(o['comparison'].get('final_rating', 3) for o in outcomes) / len(outcomes):.1f}")
EOF
```

### Alert Activity

```bash
# Recent alerts
ls -lt alerts/ | head -10

# Alert summary
ls alerts/*.json | wc -l

# Delivery status
tail -20 alerts/delivery_log.jsonl | jq '.success'
```

---

## Resource Usage

Monitor with:

```bash
# System resource usage
systemctl --user status claude-*.service

# Disk usage
du -sh learning/ alerts/

# Socket connections
lsof | grep rh-
```

---

## Installation and Setup

The installers in this repository target Linux systemd user services. Native Windows service installation is not provided; see [`PLATFORM_SUPPORT.md`](PLATFORM_SUPPORT.md) for the platform boundary.

All services are installed via individual `install.sh` scripts in each service directory:

```bash
# Install a specific service
cd <service-directory>
./install.sh

# Or install all at once
for svc in memory-service thompson-service learning-service alert_service session-messaging graph-service; do
  (cd $svc && ./install.sh)
done
```

Each installer:
- Creates the systemd user service file
- Reloads systemd configuration
- Enables the service (auto-start on login)
- Starts the service immediately

---

## Lifecycle Ownership

The baseline lifecycle contract and service ownership model are documented in [`SERVICE_LIFECYCLE.md`](SERVICE_LIFECYCLE.md).

## Documentation

For detailed docs on each service, see:

- `memory-service/README.md` — Memory service and concurrent access
- `thompson-service/README.md` — Model selection details
- `learning-service/README.md` — Outcome recording details
- `alert_service/README.md` — Alert configuration details
- `session-messaging/README.md` — Inter-session messaging (pub/sub)
- `graph-service/README.md` — Local Graph HTTP service and persistence

---

## Advanced: Manual Service Management

### Reload systemd configuration

```bash
systemctl --user daemon-reload
```

### List all user services

```bash
systemctl --user list-units --type=service
```

### Show service file

```bash
systemctl --user show claude-thompson.service
```

### Edit service file (advanced)

```bash
systemctl --user edit claude-thompson.service
```

---

## Integration with Your Workflow

### After task completion:

```bash
# Learning service automatically captures outcome
# Just rate the task (1-5) when prompted

# Thompson learns and improves model selection
# Next task gets better model choice
```

### Monitor learning:

```bash
# Watch as system learns
watch -n 5 'cat learning/thompson-sampling-state.json | jq ".models | map(.calls) | add"'
```

### Check for alerts:

```bash
# See recent alerts
tail -5 alerts/delivery_log.jsonl

# Or check email for sfloess@example.com alerts
```

---

## Questions?

See the individual service README files:
- `thompson-service/README.md`
- `learning-service/README.md`
- `alert_service/README.md`
