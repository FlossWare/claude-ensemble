# Fleet Health Monitor Integration

**Issue:** #257  
**Status:** ✅ Wired In  
**Files:**
- `tools/fleet_health_monitor.py` - Main monitoring service
- `shared/fleet_health_client.py` - Client library for querying health status
- `scripts/fleet-health-monitor.service` - Systemd service definition
- `scripts/deploy-fleet-health-monitor.sh` - Deployment script
- `scripts/test-fleet-health-integration.py` - Integration test suite

## What It Does

The Fleet Health Monitor provides automatic worker health tracking and integration with the orchestration layer:

1. **Continuous Monitoring** - Checks all 8 workers every 60 seconds via SSH
2. **PostgreSQL Storage** - Stores health check results in `monitoring.health_checks` table
3. **Auto-Recovery** - Attempts to restart SSH service after 3 consecutive failures
4. **Fleet Integration** - `fleet_executor.py` automatically filters unhealthy workers

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  aio-01: Fleet Health Monitor (systemd service)                 │
│  ├─ Monitors 8 workers every 60s                                │
│  ├─ Stores results in PostgreSQL (monitoring.health_checks)     │
│  └─ Auto-recovery after 3 failures                              │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ SSH health checks
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Workers (8 nodes)                                               │
│  server-01, server-02, server-03, laptop-01                     │
│  pi-01, pi-02, server-ap, desktop-ap                            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ Query health status
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  shared/fleet_executor.py                                       │
│  ├─ Imports fleet_health_client                                 │
│  ├─ Filters unhealthy workers before dispatching                │
│  └─ Falls back gracefully if health check unavailable           │
└─────────────────────────────────────────────────────────────────┘
```

## PostgreSQL Schema

```sql
CREATE TABLE monitoring.health_checks (
    id SERIAL PRIMARY KEY,
    worker_id TEXT NOT NULL,           -- e.g., 'server-01'
    status TEXT NOT NULL,              -- 'healthy', 'unhealthy', 'timeout', 'error'
    response_time_ms INTEGER,          -- SSH connection time
    error_message TEXT,                -- Error details if failed
    checked_at TIMESTAMP DEFAULT NOW() -- Check timestamp
);
```

## Deployment

### Prerequisites

1. PostgreSQL running on aio-01:5433 with database `learning`
2. User `claude` with passwordless PostgreSQL access
3. SSH user `claude` with passwordless access to all 8 workers
4. systemd on aio-01 (service runs as user sfloess)

### Installation

```bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
./scripts/deploy-fleet-health-monitor.sh
```

This will:
1. Verify PostgreSQL connection
2. Test SSH connectivity to workers
3. Install systemd service
4. Start monitoring service
5. Create PostgreSQL schema

### Verification

```bash
# Check service status
sudo systemctl status fleet-health-monitor

# View logs
sudo journalctl -u fleet-health-monitor -f

# Query health data
python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/fleet_health_client.py

# Run integration tests
python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/scripts/test-fleet-health-integration.py
```

## Usage

### From Python (fleet_executor.py)

Health checking is **enabled by default** in `execute_on_fleet_parallel`:

```python
from fleet_executor import execute_on_fleet_parallel

# Health check automatically enabled
results = execute_on_fleet_parallel(
    workers=["server-01", "server-02", "server-03"],
    model="gpt-4o-mini",
    tasks=["Analyze X", "Analyze Y", "Analyze Z"]
)
# Unhealthy workers are automatically filtered out

# Disable health check if needed
results = execute_on_fleet_parallel(
    workers=["server-01", "server-02", "server-03"],
    model="gpt-4o-mini",
    tasks=["Analyze X", "Analyze Y", "Analyze Z"],
    check_health=False
)
```

### Query Health Status

```python
from fleet_health_client import (
    get_healthy_workers,
    get_worker_health_status,
    get_fleet_summary
)

# Get list of healthy workers
healthy = get_healthy_workers()
# ['server-01', 'server-02', 'laptop-01', ...]

# Get detailed status for one worker
status = get_worker_health_status('server-01')
# {
#   'worker': 'server-01',
#   'status': 'healthy',
#   'response_time_ms': 45,
#   'avg_response_time_ms': 52.3,
#   'consecutive_failures': 0,
#   'healthy': True,
#   'last_check': '2026-07-01T10:30:15'
# }

# Get fleet summary
summary = get_fleet_summary()
# {
#   'total_workers': 8,
#   'healthy_workers': 7,
#   'unhealthy_workers': 1,
#   'healthy_worker_list': ['server-01', 'server-02', ...],
#   'worker_details': { ... },
#   'timestamp': '2026-07-01T10:30:20'
# }
```

### From SQL

```sql
-- Recent health checks
SELECT worker_id, status, response_time_ms, checked_at
FROM monitoring.health_checks
ORDER BY checked_at DESC
LIMIT 20;

-- Workers with failures
SELECT worker_id, COUNT(*) as failures
FROM monitoring.health_checks
WHERE status != 'healthy'
  AND checked_at > NOW() - INTERVAL '1 hour'
GROUP BY worker_id
ORDER BY failures DESC;

-- Average response times
SELECT worker_id,
       AVG(response_time_ms) as avg_response,
       COUNT(*) as checks
FROM monitoring.health_checks
WHERE status = 'healthy'
  AND checked_at > NOW() - INTERVAL '1 hour'
GROUP BY worker_id
ORDER BY avg_response;
```

## Integration Points

### 1. Fleet Executor (shared/fleet_executor.py)

**Modified:** `execute_on_fleet_parallel()` function
- Added `check_health=True` parameter
- Imports `get_healthy_workers()` from `fleet_health_client`
- Filters workers before dispatching tasks
- Gracefully falls back if health check fails

**Behavior:**
- If health check succeeds: Only dispatch to healthy workers
- If health check fails: Log warning and dispatch to all workers
- If no workers are healthy: Return error

### 2. Orchestration Layer (orchestrate.py)

No changes needed - uses `execute_on_fleet_parallel()` which now includes health checks by default.

### 3. Monitoring Service (systemd)

**Service:** `fleet-health-monitor.service`
- Runs as user: sfloess
- Restarts automatically on failure
- Logs to journald
- Resource limits: 256MB RAM, 50% CPU

### 4. PostgreSQL (monitoring schema)

**Table:** `monitoring.health_checks`
- Created automatically on first run
- No indexes needed (small dataset, recent queries only)
- Retention: Manual cleanup recommended (keep last 7 days)

## Configuration

### Health Check Interval

Edit `tools/fleet_health_monitor.py`:

```python
CHECK_INTERVAL = 60  # seconds (default: 60)
```

### Failure Threshold

```python
FAILURE_THRESHOLD = 3  # consecutive failures before recovery (default: 3)
```

### Recovery Wait

```python
RECOVERY_WAIT = 300  # seconds to wait after recovery attempt (default: 5 min)
```

### Health Check Timeout

Edit `shared/fleet_health_client.py`:

```python
# In get_healthy_workers()
max_age_seconds = 300  # Only consider checks from last 5 minutes
max_failures = 2       # Max consecutive failures to still be healthy
```

## Maintenance

### View Service Logs

```bash
sudo journalctl -u fleet-health-monitor -f
```

### Restart Service

```bash
sudo systemctl restart fleet-health-monitor
```

### Database Cleanup

```sql
-- Delete health checks older than 7 days
DELETE FROM monitoring.health_checks
WHERE checked_at < NOW() - INTERVAL '7 days';
```

### Manual Health Check

```bash
# Run monitor once (foreground)
python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/fleet_health_monitor.py

# Query current status
python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/fleet_health_client.py
```

## Troubleshooting

### Service won't start

```bash
# Check service status
sudo systemctl status fleet-health-monitor

# Check logs
sudo journalctl -u fleet-health-monitor -n 50

# Common issues:
# 1. PostgreSQL not running on aio-01:5433
# 2. User 'claude' doesn't have database access
# 3. SSH keys not configured for passwordless access
# 4. Python dependencies missing (psycopg2)
```

### Health checks always fail

```bash
# Test SSH manually
ssh -o ConnectTimeout=5 claude@server-01 echo OK

# Test PostgreSQL
python3 -c "import psycopg2; psycopg2.connect(host='aio-01', port=5433, database='learning', user='claude').close()"

# Check firewall
sudo firewall-cmd --list-all
```

### Workers incorrectly marked unhealthy

```bash
# Check recent checks
psql -h aio-01 -p 5433 -U claude -d learning -c "
  SELECT worker_id, status, response_time_ms, error_message, checked_at
  FROM monitoring.health_checks
  WHERE worker_id = 'server-01'
  ORDER BY checked_at DESC
  LIMIT 10;
"

# Reset health state (manual intervention)
# Stop service, clear table, restart
sudo systemctl stop fleet-health-monitor
psql -h aio-01 -p 5433 -U claude -d learning -c "TRUNCATE monitoring.health_checks;"
sudo systemctl start fleet-health-monitor
```

## Testing

Run the integration test suite:

```bash
python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/scripts/test-fleet-health-integration.py
```

Tests verify:
1. ✅ Health client can query PostgreSQL
2. ✅ Fleet executor filters unhealthy workers
3. ✅ PostgreSQL stores health data
4. ✅ Systemd service is running

## Future Enhancements

- [ ] Grafana dashboard for health visualization
- [ ] Alert on consecutive failures (webhook integration)
- [ ] Auto-scaling based on worker availability
- [ ] Performance metrics (not just up/down status)
- [ ] Integration with Prometheus metrics

## Related Files

- `monitoring/fleet-resource-monitor.js` - Resource usage monitoring (CPU, RAM, disk)
- `monitoring/api-health-monitor.cjs` - API provider health monitoring
- `shared/fleet-topology.js` - Fleet topology definition (JavaScript)
- `lib/fleet-api-policy.json` - Fleet API-only policy enforcement

---

**Last Updated:** 2026-07-01  
**Status:** Production Ready ✅  
**Issue:** #257 (wiring in built-but-unused features)
