# Thompson Router Service

**Purpose:** Central model-selection authority using Thompson Sampling (Bayesian multi-armed bandit).

Maintains success/failure statistics for named models and selects a model by sampling its Beta posterior.

---

## Quick Start

**Start service (no sudo needed):**
```bash
systemctl --user start claude-thompson.service
```

**Check status:**
```bash
systemctl --user status claude-thompson.service
```

**Watch logs:**
```bash
journalctl --user-unit claude-thompson.service -f
```

**Stop:**
```bash
systemctl --user stop claude-thompson.service
```

---

## Current Scope

- `max_cost` currently affects selection.
- `task_type` and `required_capability` are accepted but are not yet used to partition or filter model performance.
- Outcomes are stored as aggregate per-model statistics.
- State is persisted atomically after each recorded outcome.
- The daemon is single-threaded and does not use an inter-process file lock.
- The client falls back to `haiku` when the daemon is unavailable.

## What It Does

1. **Tracks model performance** — Maintains success/failure counts per model
2. **Accepts task types** — The API carries task type for future task-specific routing
3. **Bayesian sampling** — Uses Beta distributions to balance exploration vs exploitation
4. **Selects models** — Returns the best-performing model for a given task

**Example flow:**
```
Task: "code_review"
  → Thompson samples from Beta distribution for each model
  → Returns model with highest expected reward (e.g., "sonnet")
  
Later: Learning service records outcome (rating 4/5)
  → Thompson updates success count for sonnet on code_review
  → Next time, sonnet will have higher probability
```

---

## Command Reference

### Start/Stop/Status

```bash
# Start (user service, no sudo)
systemctl --user start claude-thompson.service

# Stop
systemctl --user stop rh-thompson.service

# Restart
systemctl --user restart claude-thompson.service

# Status
systemctl --user status claude-thompson.service

# Enable auto-start on login
systemctl --user enable claude-thompson.service
```

### Logs

```bash
# Last 50 lines
journalctl --user-unit claude-thompson.service -n 50

# Follow live
journalctl --user-unit rh-thompson.service -f

# Last hour
journalctl --user-unit claude-thompson.service --since "1 hour ago"
```

### Check State

```bash
# All models
cat learning/thompson-sampling-state.json | jq '.models'

# Just Haiku
cat learning/thompson-sampling-state.json | jq '.models.haiku'

# Pretty print
cat learning/thompson-sampling-state.json | jq '.'
```

---

## Troubleshooting

**Service won't start:**
```bash
journalctl --user-unit rh-thompson.service -n 20
```

**"Address already in use" (socket file stale):**
```bash
rm /tmp/claude-thompson.sock
systemctl --user restart rh-thompson.service
```

**"Connection refused":**
```bash
# Service not running
systemctl --user start rh-thompson.service
```

**Always selecting same model:**
- Check state: `cat learning/thompson-sampling-state.json | jq '.models'`
- Need ~10+ outcomes per model for Thompson to learn

---

## Architecture

- **Listen:** Unix-domain socket `/tmp/claude-thompson.sock`
- **Protocol:** newline-delimited JSON
- **State:** `learning/thompson-sampling-state.json`
- **Thread model:** Single-threaded; state writes use atomic replacement, not inter-process locking
- **Memory:** 256M max, 25% CPU quota

---

## Integration

**Used by:**
- `rh-api-wrapper.py` — Model selection
- `learning-service` — Outcome recording
- Client library: `shared/thompson_client.py`

**Outputs:**
- `/tmp/rh-thompson.sock` — JSON-RPC socket
- `learning/thompson-sampling-state.json` — Persistent state
- `journalctl` — Structured logs


## Windows

Native Windows SCM can host the Thompson service process, but the Thompson application
protocol currently uses Unix-domain sockets. The Windows service host therefore does not
make Thompson client IPC Windows-native. See `windows/README.md` for the current Windows
service scope.
