# Fleet Health Predictor

**GitLab Issue:** #108  
**Status:** Implemented  
**Version:** 1.0.0

## Overview

AI-based predictive server failure detection system that analyzes Prometheus metrics to prevent fleet worker failures **before** they occur.

**Target:** Prevent 80% of unexpected failures, zero jobs lost  
**Threshold:** 70% degradation probability → mark server degraded

## Architecture

### Three-Model AI Pipeline

1. **Haiku** (Fast Analysis)
   - Time-series anomaly detection
   - Pattern recognition (memory leaks, temperature creep, disk saturation)
   - Output: Degradation probability + primary risk

2. **Sonnet** (Validation)
   - Cross-check Haiku's findings against raw data
   - False positive detection
   - Missed pattern identification
   - Output: Validated probability + confidence

3. **Opus** (Migration Decisions)
   - Critical decision-making (migrate jobs vs. monitor)
   - Cost-benefit analysis (migration disruption vs. failure risk)
   - Target server selection
   - Output: Action plan + urgency level

### Metrics Analyzed

From Prometheus (7-day history):

- **CPU temperature** (hwmon sensors) - Thermal degradation
- **Memory usage** (node_memory) - Memory leak detection
- **Disk I/O wait** (node_cpu iowait) - I/O saturation
- **Load average** (node_load1) - Sustained high load
- **Memory RSS** (node_memory_Active_bytes) - Process memory growth
- **Disk usage** (node_filesystem) - Storage exhaustion

### Circuit Breaker Thresholds

Immediate failure thresholds (80% trigger = immediate analysis):

| Metric | Threshold | 80% Trigger |
|--------|-----------|-------------|
| CPU usage | 90% | 72% |
| Memory usage | 95% | 76% |
| Load avg/core | 3.0 | 2.4 |
| Disk I/O wait | 50% | 40% |
| CPU temp | 85°C | 68°C |

## Usage

### Command Line

```bash
# Analyze all fleet workers
node tools/fleet-health-predictor.js --all

# Analyze specific server
node tools/fleet-health-predictor.js --hostname server-01

# Custom threshold
node tools/fleet-health-predictor.js --hostname laptop-01 --threshold 0.60

# Help
node tools/fleet-health-predictor.js --help
```

### Programmatic API

```javascript
import { getServerHealth, getPredictiveHealth } from './shared/fleet-utils.js';

// Get enhanced health status (SSH + predictive)
const health = await getServerHealth('server-01');
console.log(health);
// {
//   reachable: true,
//   predictive_health: {
//     degradation_probability: 0.85,
//     primary_risk: 'memory_leak',
//     action: 'migrate_immediately',
//     urgency: 'critical',
//     predicted_at: '2026-07-07T12:34:56Z'
//   },
//   combined_status: 'degraded',
//   recommendation: 'migrate_immediately',
//   urgency: 'critical'
// }

// Get only predictive analysis
const predictive = await getPredictiveHealth('server-01');
console.log(predictive);
// {
//   degradation_probability: 0.85,
//   primary_risk: 'memory_leak',
//   action: 'migrate_immediately',
//   urgency: 'critical',
//   predicted_at: '2026-07-07T12:34:56Z'
// }
```

## Deployment

### 1. Prerequisites

- Prometheus running on `pi-02:9090` with node_exporter on all fleet workers
- PostgreSQL on `aio-01:5433` with `learning` database
- Node.js 18+ on pi-02

### 2. Cron Setup (pi-02)

```bash
# Copy cron script
scp bin/fleet-health-predictor-cron.sh pi-02:/home/claude/bin/
ssh pi-02 chmod +x /home/claude/bin/fleet-health-predictor-cron.sh

# Add to crontab (every 5 minutes)
ssh pi-02 'crontab -l | grep -v fleet-health-predictor; echo "*/5 * * * * /home/claude/bin/fleet-health-predictor-cron.sh"' | ssh pi-02 crontab -
```

### 3. Verify Installation

```bash
# Test single run
ssh pi-02 "cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node tools/fleet-health-predictor.js --hostname server-01"

# Check logs
ssh pi-02 tail -f /var/log/fleet-health-predictor.log
```

## Database Schema

### Table: `monitoring.health_predictions`

```sql
CREATE TABLE monitoring.health_predictions (
  id SERIAL PRIMARY KEY,
  hostname TEXT NOT NULL,
  degradation_probability REAL NOT NULL,
  primary_risk TEXT,  -- memory_leak | cpu_thermal | disk_saturation | load_spike | none
  time_to_failure_hours REAL,
  validated_probability REAL,
  validation_confidence REAL,
  decision_action TEXT,  -- migrate_immediately | schedule_migration | monitor_closely | no_action
  decision_urgency TEXT,  -- critical | high | medium | low
  evidence JSONB,
  reasoning TEXT,
  predicted_at TIMESTAMP DEFAULT NOW(),
  INDEX idx_hostname_predicted (hostname, predicted_at DESC)
);
```

### Query Examples

```sql
-- Get latest prediction for a server
SELECT * FROM monitoring.health_predictions
WHERE hostname = 'server-01'
ORDER BY predicted_at DESC
LIMIT 1;

-- Get all degraded servers (>70% probability)
SELECT hostname, degradation_probability, primary_risk, decision_action
FROM monitoring.health_predictions
WHERE predicted_at > NOW() - INTERVAL '1 hour'
  AND degradation_probability > 0.70
ORDER BY degradation_probability DESC;

-- Historical accuracy analysis
SELECT 
  hostname,
  AVG(degradation_probability) as avg_degradation,
  COUNT(*) as prediction_count,
  MAX(predicted_at) as last_prediction
FROM monitoring.health_predictions
WHERE predicted_at > NOW() - INTERVAL '7 days'
GROUP BY hostname
ORDER BY avg_degradation DESC;
```

## Integration with Existing Systems

### 1. Fleet Orchestrator

```javascript
import { getServerHealth } from './shared/fleet-utils.js';

// Before job assignment
const health = await getServerHealth(candidateServer);

if (health.combined_status === 'degraded') {
  console.log(`⚠️  ${candidateServer} is degraded - selecting alternative`);
  // Select different server
} else if (health.combined_status === 'at_risk') {
  console.log(`⚠️  ${candidateServer} is at risk - prioritizing other servers`);
  // Deprioritize but still usable
}
```

### 2. Circuit Breaker

Enhanced circuit breaker with predictive degradation:

```javascript
// Traditional circuit breaker (reactive)
if (cpuUsage > 90) {
  tripCircuitBreaker(server);
}

// Predictive circuit breaker (proactive)
const health = await getPredictiveHealth(server);
if (health.degradation_probability > 0.70) {
  tripCircuitBreaker(server, 'predictive_degradation');
}
```

### 3. Grafana Dashboards

Query predictions from PostgreSQL:

```sql
-- Prometheus-style metric for Grafana
SELECT 
  hostname as instance,
  degradation_probability as value,
  EXTRACT(EPOCH FROM predicted_at) as time
FROM monitoring.health_predictions
WHERE predicted_at > NOW() - INTERVAL '24 hours'
ORDER BY predicted_at;
```

## Decision Matrix

| Degradation Probability | Status | Action | Jobs Migrated |
|------------------------|--------|--------|---------------|
| 0-50% | Healthy | Monitor | No |
| 50-70% | At Risk | Monitor Closely | No |
| 70-85% | Degraded | Schedule Migration | Yes (within 4h) |
| 85-95% | Critical | Migrate Immediately | Yes (within 1h) |
| 95-100% | Failing | Emergency Migration | Yes (immediate) |

## Performance Benchmarks

- **Analysis time:** 15-30 seconds per server (Haiku + Sonnet + Opus)
- **Prometheus query:** 2-5 seconds (7-day range)
- **Database insert:** <100ms
- **Total cycle time:** ~2 minutes for 8 servers

## Cost Estimation

Per 5-minute cycle (8 servers):

- Haiku: 8 × 1500 tokens × $0.25/MTok = $0.003
- Sonnet: 8 × 1800 tokens × $3/MTok = $0.043
- Opus: 2 × 2500 tokens × $15/MTok = $0.075 (only for critical servers)

**Total:** ~$0.12/cycle = **$34/day** = **$1,020/month**

**ROI:** Single prevented failure (job restart + reputation damage) = $500-1000+

## Monitoring and Alerting

### Grafana Alert Rules

```yaml
# Alert when server marked degraded
- alert: ServerPredictiveDegradation
  expr: fleet_health_degradation_probability > 0.70
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: "Server {{ $labels.instance }} predicted to fail"
    description: "Degradation probability: {{ $value }}%"

# Alert when critical action required
- alert: ServerCriticalAction
  expr: fleet_health_urgency == "critical"
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Immediate action required for {{ $labels.instance }}"
    description: "Action: {{ $labels.action }}"
```

## Troubleshooting

### Prometheus Connection Failed

```bash
# Test Prometheus connectivity
curl http://pi-02:9090/api/v1/query?query=up

# Check node_exporter on workers
ssh server-01 'systemctl status node_exporter'
```

### PostgreSQL Connection Failed

```bash
# Test PostgreSQL connectivity
psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT 1"

# Check if table exists
psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT COUNT(*) FROM monitoring.health_predictions"
```

### AI Analysis Timeout

```bash
# Check API keys
echo $ANTHROPIC_API_KEY | head -c 20

# Test direct API call
node -e "import('./shared/fleet-utils.js').then(m => m.executeRemoteLLMTask({task:'test',model:'haiku'}))"
```

## Future Enhancements

1. **ML-based anomaly detection** - Train custom models on historical failures
2. **Seasonal pattern recognition** - Identify recurring degradation patterns
3. **Correlation analysis** - Detect cascading failures across fleet
4. **Automated job migration** - Execute migrations without human approval (after trust threshold)
5. **Cost optimization** - Adjust analysis frequency based on risk level

## References

- **Issue:** #108 (GitLab)
- **Code:** `tools/fleet-health-predictor.js`
- **Integration:** `shared/fleet-utils.js` (`getServerHealth()`, `getPredictiveHealth()`)
- **Cron:** `bin/fleet-health-predictor-cron.sh`
- **Database:** `monitoring.health_predictions` table
- **Prometheus:** `http://pi-02:9090`

## License

Internal use only - Part of claude-global-skills fleet orchestration system.
