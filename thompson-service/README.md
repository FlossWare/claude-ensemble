# RH Thompson Router Service

Central Thompson Sampling authority for model selection across Claude Code sessions.

## Overview

The Thompson Router Service runs as a systemd user daemon and provides model selection via Thompson Sampling (multi-armed bandit algorithm). Sessions and hooks can query the service to select the best model for a task and record outcomes to improve future selections.

**Architecture:**
- Single-threaded daemon with Unix socket communication
- Maintains Beta priors for each model based on historical success/failure
- Persists state to JSON file with atomic updates
- Graceful degradation: clients fall back to 'haiku' if service is unavailable

## Installation

```bash
./thompson-service/install.sh
```

This will:
1. Create `~/.config/systemd/user/rh-thompson.service` symlink
2. Reload systemd and enable the service
3. Start the Thompson Router daemon
4. Display service status

## Service Management

```bash
# Check status
systemctl --user status rh-thompson.service

# View logs
journalctl --user -u rh-thompson.service -f

# Restart service
systemctl --user restart rh-thompson.service

# Stop service
systemctl --user stop rh-thompson.service

# Start service
systemctl --user start rh-thompson.service
```

## Client Usage

### Python Client

```python
from shared.thompson_client import ThompsonClient

# Initialize client
client = ThompsonClient()

# Select model for a task
model = client.select_model(
    task_type="code-review",
    required_capability=0.7,
    max_cost=0.05
)

# Record outcome
success = client.record_outcome(
    model=model,
    task_type="code-review",
    success=True,
    cost=0.024,
    tokens=1250
)

# Get current state
state = client.get_state()
print(f"Model stats: {state['models']}")

# Reset model history
client.reset('haiku')
```

### Request/Response Protocol

The service listens on `/tmp/rh-thompson.sock` and processes JSON requests:

#### select_model
```json
{
  "action": "select_model",
  "task_type": "code-review",
  "required_capability": 0.7,
  "max_cost": 0.05
}
```

Response:
```json
{
  "ok": true,
  "model": "claude-sonnet-5"
}
```

#### record_outcome
```json
{
  "action": "record_outcome",
  "model": "haiku",
  "task_type": "code-review",
  "success": true,
  "cost": 0.024,
  "tokens": 1250
}
```

Response:
```json
{
  "ok": true
}
```

#### get_state
```json
{
  "action": "get_state"
}
```

Response:
```json
{
  "ok": true,
  "state": {
    "last_updated": "2026-09-26T22:30:00.000000",
    "models": {
      "haiku": {
        "model_name": "haiku",
        "successes": 36,
        "failures": 6,
        "total_cost": 0.61,
        "total_tokens": 45000,
        "calls": 42,
        "last_updated": "2026-09-26T22:31:55.706494"
      },
      ...
    }
  }
}
```

#### reset
```json
{
  "action": "reset",
  "model": "haiku"
}
```

Response:
```json
{
  "ok": true
}
```

#### ping
```json
{
  "action": "ping"
}
```

Response:
```json
{
  "ok": true,
  "message": "pong"
}
```

## State File

Persistent state is stored in:
```
~/.claude/projects/-home-sfloess/learning/thompson-sampling-state.json
```

Format:
```json
{
  "last_updated": "2026-09-26T22:30:00.000000",
  "models": {
    "haiku": {
      "model_name": "haiku",
      "successes": 36,
      "failures": 6,
      "total_cost": 0.61,
      "total_tokens": 45000,
      "calls": 42,
      "last_updated": "2026-09-26T22:31:55.706494"
    },
    ...
  }
}
```

## Thompson Sampling Algorithm

The service uses Thompson Sampling (Bayesian bandits) to select models:

1. **Track outcomes:** successes and failures for each model
2. **Beta prior:** For each model, maintain Beta(alpha=successes+1, beta=failures+1)
3. **Sample:** Draw sample from posterior Beta distribution for each model
4. **Select:** Choose model with highest sample value
5. **Explore/Exploit:** Exploration naturally occurs through uncertainty in untested models

### Example Posterior Samples

Given:
- Haiku: 36 successes, 6 failures → Beta(37, 7)
- Sonnet: 20 successes, 3 failures → Beta(21, 4)
- Opus: 14 successes, 2 failures → Beta(15, 3)

Thompson Sampling draws from each posterior, allowing occasional exploration of less-tested models while favoring proven performers.

## Cost Constraints

Models are filtered by cost before selection:
- Only models with `avg_cost <= max_cost` are considered
- Untested models (cost=0) are always eligible
- If all models exceed the cost limit, the cheapest is selected

## Logging

Service logs to:
```
~/.claude/rh-thompson-service.log
```

Also logs to systemd journal:
```bash
journalctl --user -u rh-thompson.service
```

## Troubleshooting

### Service won't start
```bash
journalctl --user -n 50 -u rh-thompson.service
```

### Socket connection refused
- Check socket directory: `ls -la /tmp/rh-thompson.sock`
- Check service status: `systemctl --user status rh-thompson.service`
- Restart service: `systemctl --user restart rh-thompson.service`

### State file corruption
- Backup current state: `cp ~/.claude/projects/-home-sfloess/learning/thompson-sampling-state.json ~/.claude/projects/-home-sfloess/learning/thompson-sampling-state.json.bak`
- Remove lock file: `rm ~/.claude/projects/-home-sfloess/learning/thompson-sampling-state.json.lock`
- Restart service: `systemctl --user restart rh-thompson.service`

## Files

- `thompson_service.py` - Daemon implementation
- `rh-thompson.service` - Systemd unit file
- `install.sh` - Installation script
- `../shared/thompson_client.py` - Python client library
- `~/.claude/projects/-home-sfloess/learning/thompson-sampling-state.json` - State file
