# RH Alert Service

Centralized alert service daemon for monitoring costs, quality, and errors in the RH Claude Global Skills toolkit.

Follows the same pattern as [memory-service](../memory-service/) — single systemd user service listening on a Unix socket.

## Architecture

```
+------------------+
| Session/Script   |
|  (alert_client)  |
+-------+----------+
        | JSON over Unix socket
        | /tmp/rh-alert.sock
        v
+------------------+
| Alert Service    |
|  (daemon)        |
|                  |
| - AlertManager   |<-- Checks (cost spike, quality drop)
| - AlertStore     |<-- File I/O (alerts, config, logs)
+------------------+
        |
        v
+------------------+
| ~/.claude/alerts/|
| - config.json    |
| - *.json         |
| - delivery_log   |
| - acknowledged   |
+------------------+
```

## Installation

```bash
# Install as systemd user service
./alert_service/install.sh

# Verify service is running
systemctl --user status rh-alert.service

# View logs
journalctl --user -u rh-alert.service -f
```

## Usage

### From Python Code

```python
from tools.alert_client import AlertClient

client = AlertClient()

# Trigger all checks (cost spike, quality drop)
alerts = client.trigger_check()
for alert in alerts:
    print(f"{alert['alert_type']}: {alert['message']}")

# Get recent alerts
recent = client.get_recent_alerts(days=7)

# Acknowledge an alert
client.acknowledge('alert-id-123')

# Get config
config = client.get_config()
print(f"Cost threshold multiplier: {config['cost_spike_threshold_multiplier']}")
```

### From Cron (Optional)

```bash
# Run check every 30 minutes
*/30 * * * * /path/to/alert_service/check_alerts.sh
```

## API

### `trigger_check()`
Run all checks and return alerts triggered.

**Response:**
```json
{
  "ok": true,
  "alerts": [
    {
      "alert_type": "cost_spike",
      "severity": "warning",
      "timestamp": "2026-09-26T22:37:00",
      "message": "Daily cost spike detected: $45.23 (baseline: $20.00)",
      "metrics": {...},
      "action_recommended": "Review model selection"
    }
  ],
  "count": 1
}
```

### `get_recent_alerts(days=7)`
List recent alerts from the last N days.

**Response:**
```json
{
  "ok": true,
  "alerts": [...],
  "count": 5
}
```

### `acknowledge(alert_id)`
Mark alert as reviewed/acknowledged.

**Response:**
```json
{
  "ok": true
}
```

### `get_config()`
Get current alert configuration and thresholds.

**Response:**
```json
{
  "ok": true,
  "config": {
    "cost_spike_threshold_multiplier": 2.0,
    "quality_drop_threshold": 3.0,
    "quality_window_days": 7,
    "enabled": true,
    "email_recipient": "sfloess@redhat.com"
  }
}
```

## Configuration

Alert thresholds are stored in `~/.claude/alerts/config.json`:

```json
{
  "cost_spike_threshold_multiplier": 2.0,
  "quality_drop_threshold": 3.0,
  "quality_window_days": 7,
  "enabled": true,
  "email_recipient": "sfloess@redhat.com"
}
```

Edit this file to change thresholds. The daemon reads config on each request.

## Checks

### Cost Spike
Alerts if daily cost > baseline × threshold_multiplier.

- **Default threshold:** 2.0× baseline
- **Data source:** `cost_tracking.logger.CostLogger`
- **Severity:** warning

### Quality Drop
Alerts if average outcome rating < threshold in recent window.

- **Default threshold:** 3.0 rating
- **Window:** Last 7 days
- **Data source:** `learning/post_task_outcomes/*.json`
- **Severity:** critical

### Model Errors
Placeholder for future error/fallback detection.

## Files

### Daemon
- `alert_service/alert_service.py` — Main daemon (socket listener, request processor)
- `alert_service/__init__.py` — Package marker
- `alert_service/rh-alert.service` — Systemd unit file

### Client
- `tools/alert_client.py` — Session-side client library

### State (in `~/.claude/alerts/`)
- `config.json` — Thresholds and settings
- `*.json` — Individual alerts (saved by daemon)
- `delivery_log.jsonl` — Email delivery attempts (JSONL)
- `acknowledged.jsonl` — User acknowledgements (JSONL)

### Tools
- `alert_service/install.sh` — Install service
- `alert_service/check_alerts.sh` — Cron wrapper script

## Service Management

```bash
# Start service
systemctl --user start rh-alert.service

# Stop service
systemctl --user stop rh-alert.service

# Restart service
systemctl --user restart rh-alert.service

# Enable auto-start on login
systemctl --user enable rh-alert.service

# Check status
systemctl --user status rh-alert.service

# View logs
journalctl --user -u rh-alert.service -f
journalctl --user -u rh-alert.service -n 50

# Check if socket is listening
[ -S /tmp/rh-alert.sock ] && echo "Socket active" || echo "Socket inactive"
```

## Comparison to Session-Side AlertManager

The alert system moves AlertManager execution from session context to daemon context:

| Aspect | Before (Session) | After (Daemon) |
|--------|------------------|----------------|
| Where it runs | Every session | Once in background |
| Duplicate checks | Yes (if multiple sessions) | No (centralized) |
| Email sending | Per-session attempt | Single attempt in daemon |
| State persistence | Memory only | Persistent files |
| Queue | In-memory queue per session | Centralized queue |
| API | Direct method calls | Socket-based JSON RPC |

## Troubleshooting

### Service won't start
```bash
# Check logs
journalctl --user -n 50 -u rh-alert.service

# Ensure script is executable
ls -la alert_service/alert_service.py
chmod +x alert_service/alert_service.py

# Verify Python path
which python3
```

### Socket not found / client can't connect
```bash
# Check if service is running
systemctl --user is-active rh-alert.service

# Check socket
ls -la /tmp/rh-alert.sock

# Restart service
systemctl --user restart rh-alert.service
```

### Alerts not triggering
```bash
# Check config
cat ~/.claude/alerts/config.json

# Verify cost logger is available
python3 -c "from cost_tracking.logger import CostLogger; CostLogger().get_stats()"

# Check recent alerts
ls -la ~/.claude/alerts/
```

## See Also

- [memory-service](../memory-service/) — Similar daemon pattern for memory operations
- [alert_manager.py](../tools/alert_manager.py) — Previous session-side implementation (now mostly moved to daemon)
- [cost_tracking](../cost_tracking/) — Cost monitoring
