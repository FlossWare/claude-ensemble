# MCP Fleet Orchestrator Monitoring Guide

## Key Metrics

### Latency
- **p50**: < 2s (median response time)
- **p95**: < 5s (95th percentile)
- **p99**: < 10s (99th percentile - ALERT if exceeded)

### Error Rate
- **Target**: < 1%
- **Warning**: > 2%
- **Critical**: > 5% (ALERT)

### Queue Depth
- **Normal**: < 10 pending requests
- **Warning**: > 20
- **Critical**: > 50

### Cost
- **Daily budget**: $10
- **Alert**: > $8/day

## Grafana Queries

### Average Latency by Model
```promql
avg(workflow_duration_ms{workflow="fleet-execute"}) by (model)
```

### Error Rate
```promql
rate(workflow_errors_total[5m]) / rate(workflow_requests_total[5m]) * 100
```

### Queue Depth
```promql
workflow_queue_depth{service="fleet-orchestrator"}
```

## Troubleshooting

### High Latency
1. Check SSH connectivity: `ssh claude@server-01 echo "ping"`
2. Check API provider status
3. Check worker load: `ssh claude@server-01 uptime`

### High Error Rate
1. Check logs: `tail -f ~/.claude/mcp-servers/fleet-orchestrator/logs/error.log`
2. Check circuit breaker state
3. Verify API credentials

### Queue Buildup
1. Scale workers horizontally
2. Check for stuck tasks
3. Increase timeout thresholds
