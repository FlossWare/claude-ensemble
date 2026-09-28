# RH AI Toolkit — Services Guide

Three systemd user services for autonomous learning and model selection.

---

## Services Overview

| Service | Purpose | Socket | Docs |
|---------|---------|--------|------|
| **Thompson** | Model selection via Bayesian sampling | `/tmp/rh-thompson.sock` | `thompson-service/README.md` |
| **Learning** | Task outcome recording and learning | `/tmp/rh-learning.sock` | `learning-service/README.md` |
| **Alert** | Anomaly detection and email alerts | `/tmp/rh-alert.sock` | `alert_service/README.md` |

---

## Universal Commands

### Start All Services

```bash
systemctl --user start rh-thompson.service rh-learning.service rh-alert.service
```

### Stop All Services

```bash
systemctl --user stop rh-thompson.service rh-learning.service rh-alert.service
```

### Restart All Services

```bash
systemctl --user restart rh-thompson.service rh-learning.service rh-alert.service
```

### Check Status

```bash
systemctl --user status rh-thompson.service rh-learning.service rh-alert.service
```

### Enable Auto-Start (on login)

```bash
systemctl --user enable rh-thompson.service rh-learning.service rh-alert.service
```

### Disable Auto-Start

```bash
systemctl --user disable rh-thompson.service rh-learning.service rh-alert.service
```

### Watch Logs (all services)

```bash
journalctl --user -f
```

### Watch Logs (single service)

```bash
journalctl --user-unit rh-thompson.service -f
journalctl --user-unit rh-learning.service -f
journalctl --user-unit rh-alert.service -f
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
ls -la /tmp/rh-*.sock
# Should show: thompson, learning, alert sockets
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
journalctl --user-unit rh-SERVICENAME.service -n 20

# Restart
systemctl --user restart rh-SERVICENAME.service
```

### Services won't communicate

```bash
# Are all sockets present?
ls /tmp/rh-*.sock

# Are all services running?
systemctl --user status rh-*.service

# Try restarting all
systemctl --user restart rh-thompson.service rh-learning.service rh-alert.service
```

### Stale socket files

```bash
# Remove stale sockets
rm /tmp/rh-thompson.sock /tmp/rh-learning.sock /tmp/rh-alert.sock

# Restart services
systemctl --user restart rh-thompson.service rh-learning.service rh-alert.service
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
systemctl --user status rh-*.service

# Disk usage
du -sh learning/ alerts/

# Socket connections
lsof | grep rh-
```

---

## Documentation

For detailed docs on each service, see:

- `thompson-service/README.md` — Model selection details
- `learning-service/README.md` — Outcome recording details
- `alert_service/README.md` — Alert configuration details

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
systemctl --user show rh-thompson.service
```

### Edit service file (advanced)

```bash
systemctl --user edit rh-thompson.service
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

# Or check email for sfloess@redhat.com alerts
```

---

## Questions?

See the individual service README files:
- `thompson-service/README.md`
- `learning-service/README.md`
- `alert_service/README.md`
