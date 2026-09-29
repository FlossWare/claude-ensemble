# RH Thompson Router Service

**Purpose:** Model selection authority using Thompson Sampling (Bayesian multi-armed bandit)

Tracks performance of all available models (Haiku, Sonnet, Opus, Cursor, Gemini) and selects the best one for each task type using probabilistic sampling.

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

## What It Does

1. **Tracks model performance** — Maintains global and task-scoped success/failure counts
2. **Learns task types** — Outcomes are scoped by `task_type` so unrelated workloads do not share task evidence
3. **Bayesian sampling** — Uses Beta distributions to balance exploration vs exploitation
4. **Selects models** — Applies capability and hard cost constraints before Thompson sampling

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
systemctl --user stop claude-thompson.service

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
journalctl --user-unit claude-thompson.service -f

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
journalctl --user-unit claude-thompson.service -n 20
```

**"Address already in use" (socket file stale):**
```bash
rm /tmp/claude-thompson.sock
systemctl --user restart claude-thompson.service
```

**"Connection refused":**
```bash
# Service not running
systemctl --user start claude-thompson.service
```

**Always selecting same model:**
- Check state: `cat learning/thompson-sampling-state.json | jq '.models'`
- Need ~10+ outcomes per model for Thompson to learn

---

## Architecture

- **Listen:** Unix socket `/tmp/claude-thompson.sock`
- **Protocol:** newline-delimited JSON
- **State:** `learning/thompson-sampling-state.json`
- **Thread model:** Single-threaded
- **Memory:** 256M max, 25% CPU quota

---

## Integration

**Used by:**
- `rh-api-wrapper.py` — Model selection
- `learning-service` — Outcome recording
- Client library: `shared/thompson_client.py`

**Outputs:**
- `/tmp/claude-thompson.sock` — newline-delimited JSON socket
- `learning/thompson-sampling-state.json` — Persistent state
- `journalctl` — Structured logs


## Current routing constraints

- `task_type` selects task-scoped performance statistics when available.
- `required_capability` is a hard minimum from 0 to 1. Model capabilities are registered explicitly; unregistered models use a neutral 0.5 capability.
- `max_cost` is a hard average-cost ceiling. With a finite limit, untested models are not considered budget-safe.
- If no model satisfies the constraints, selection fails instead of returning an over-budget or under-capability model.
- State persistence is atomic, but this daemon does not use an inter-process lock.
