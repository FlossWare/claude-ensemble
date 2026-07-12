# Redis Queue Monitoring

**Created:** 2026-07-11  
**Components:** queue-metrics.js, queue-metrics-prometheus.js

---

## Overview

Comprehensive monitoring for Redis-based queue system tracking:
- **Queue depth** - Number of pending items per queue
- **Throughput** - Items processed per second/minute
- **Processing times** - Min/avg/max latency
- **Error rates** - Errors per time window
- **Worker health** - Active workers and heartbeats

---

## Components

### 1. QueueMetrics Class (`tools/queue-metrics.js`)

Core metrics collection and reporting.

**Queues tracked:**
- `queue:scrape` - URL scraping tasks
- `queue:storage` - Document storage tasks
- `queue:embedding` - Vector embedding tasks

**Methods:**

```javascript
const QueueMetrics = require('./tools/queue-metrics');
const metrics = new QueueMetrics();

// Record processed item
await metrics.recordProcessed('scrape', processingTimeMs);

// Record error
await metrics.recordError('scrape', error);

// Worker heartbeat
await metrics.workerHeartbeat('worker-1', 'scrape', 'active');

// Get throughput (1min/5min windows)
const tp = await metrics.getThroughput('scrape', 60000);
// { count, itemsPerSec, itemsPerMin, avgProcessingMs, ... }

// Get error rate
const errors = await metrics.getErrorRate('scrape', 300000);
// { errorCount, totalProcessed, errorRate, recentErrors }

// Get active workers
const workers = await metrics.getActiveWorkers();
// [{ id, queue, status, lastSeen, age, pid }]

// Get complete snapshot
const snapshot = await metrics.getSnapshot();
```

### 2. CLI Tool

```bash
# Print metrics once
node tools/queue-metrics.js snapshot

# Watch continuously (default 5s)
node tools/queue-metrics.js watch

# Watch with custom interval
node tools/queue-metrics.js watch 2000

# JSON output
node tools/queue-metrics.js json
```

**Example output:**

```
=== Queue Metrics ===
Timestamp: 2026-07-11T10:30:45.123Z

Queue Depths:
  scrape: 127 items
  storage: 43 items
  embedding: 89 items

Throughput (1min / 5min):
  scrape:
    1min: 45.23 items/min (avg 342ms)
    5min: 38.91 items/min (avg 389ms)
  storage:
    1min: 67.12 items/min (avg 156ms)
    5min: 59.43 items/min (avg 178ms)

Error Rates (5min):
  scrape: 2.34% (12 errors / 512 processed)
    Recent: Connection timeout to example.com
  storage: 0.00% (0 errors / 234 processed)

Workers: 8 active
  scrape: 3 workers
  storage: 3 workers
  embedding: 2 workers
```

### 3. Prometheus Exporter (`tools/queue-metrics-prometheus.js`)

Exposes metrics in Prometheus format for scraping.

**Start exporter:**

```bash
# Default port 9091
node tools/queue-metrics-prometheus.js

# Custom port
METRICS_PORT=9092 node tools/queue-metrics-prometheus.js
```

**Endpoints:**
- `http://localhost:9091/metrics` - Prometheus metrics
- `http://localhost:9091/health` - Health check

**Metrics exposed:**

```prometheus
# Queue depths
queue_depth{queue="scrape"} 127
queue_depth{queue="storage"} 43

# Throughput
queue_throughput_items_per_second{queue="scrape",window="1min"} 0.7538
queue_throughput_items_per_second{queue="scrape",window="5min"} 0.6485

# Processing times
queue_processing_time_ms{queue="scrape",window="1min",stat="avg"} 342.15
queue_processing_time_ms{queue="scrape",window="1min",stat="min"} 123.00
queue_processing_time_ms{queue="scrape",window="1min",stat="max"} 1245.67

# Error metrics
queue_error_total{queue="scrape",window="5min"} 12
queue_processed_total{queue="scrape",window="5min"} 512
queue_error_rate{queue="scrape",window="5min"} 2.34

# Worker health
queue_workers_active{queue="all"} 8
queue_workers_active{queue="scrape"} 3
queue_worker_age_ms{worker="worker-1",queue="scrape"} 1234
```

---

## Integration

### In Worker Code

```javascript
const QueueMetrics = require('./tools/queue-metrics');
const metrics = new QueueMetrics();

async function processTask(task) {
  const startTime = Date.now();

  // Heartbeat
  await metrics.workerHeartbeat('worker-1', 'scrape', 'active');

  try {
    // Process task
    const result = await scrapeUrl(task.url);

    // Record success
    const processingTime = Date.now() - startTime;
    await metrics.recordProcessed('scrape', processingTime);

    return result;

  } catch (error) {
    // Record error
    await metrics.recordError('scrape', error);
    throw error;
  }
}

// Periodic heartbeat
setInterval(async () => {
  await metrics.workerHeartbeat('worker-1', 'scrape', 'active');
}, 10000); // Every 10s
```

### Prometheus Scrape Config

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'redis-queues'
    static_configs:
      - targets: ['localhost:9091']
    scrape_interval: 15s
```

### Grafana Dashboard

**Sample queries:**

```promql
# Queue depth over time
queue_depth{queue="scrape"}

# Throughput rate
rate(queue_processed_total{queue="scrape"}[5m])

# Error rate percentage
queue_error_rate{queue="scrape"}

# Processing time p95
histogram_quantile(0.95, queue_processing_time_ms{queue="scrape"})

# Active workers
sum(queue_workers_active) by (queue)

# Stale workers (no heartbeat >30s)
queue_worker_age_ms > 30000
```

---

## Testing

```bash
# Run test suite
node tools/test-queue-metrics.js
```

**Tests verify:**
1. Recording processed items
2. Recording errors
3. Worker heartbeats
4. Snapshot generation
5. Formatted output
6. Specific metric queries
7. Worker tracking

---

## Monitoring Best Practices

### 1. Queue Depth Alerts

```promql
# Alert if queue depth > 1000 for 5min
queue_depth > 1000
```

**Action:** Scale up workers or investigate bottleneck

### 2. Throughput Degradation

```promql
# Alert if throughput drops >50% from 5min average
queue_throughput_items_per_second{window="1min"} < 
  queue_throughput_items_per_second{window="5min"} * 0.5
```

**Action:** Check worker health, database connections

### 3. High Error Rate

```promql
# Alert if error rate >5% for 5min
queue_error_rate > 5
```

**Action:** Check recent errors, investigate root cause

### 4. Stale Workers

```promql
# Alert if worker hasn't sent heartbeat in 30s
queue_worker_age_ms > 30000
```

**Action:** Restart worker, check for crashes

### 5. Processing Time Spikes

```promql
# Alert if avg processing time >2x normal
queue_processing_time_ms{stat="avg",window="1min"} >
  queue_processing_time_ms{stat="avg",window="5min"} * 2
```

**Action:** Check database performance, network latency

---

## Data Retention

**Metrics stored in Redis:**
- Processing events: Last 1 hour
- Errors: Last 1 hour
- Worker heartbeats: 60 second TTL

**Prometheus retention:** Configured in `prometheus.yml` (default 15 days)

---

## Architecture

```
┌─────────────┐
│   Workers   │
│ (scrape,    │
│  storage,   │
│  embedding) │
└──────┬──────┘
       │ recordProcessed()
       │ recordError()
       │ workerHeartbeat()
       ▼
┌─────────────────┐
│  QueueMetrics   │
│   (Redis        │
│   Sentinel)     │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────────┐
│  CLI   │ │  Prometheus  │
│  Tool  │ │  Exporter    │
└────────┘ │  :9091       │
           └───────┬──────┘
                   │
                   ▼
           ┌──────────────┐
           │  Prometheus  │
           │    Server    │
           └───────┬──────┘
                   │
                   ▼
           ┌──────────────┐
           │   Grafana    │
           │  Dashboard   │
           └──────────────┘
```

---

## Troubleshooting

### No metrics showing

**Check:**
1. Redis Sentinel connectivity
2. Worker heartbeats being sent
3. Metrics recording calls in worker code

```bash
# Test Redis connection
node -e "const QueueMetrics = require('./tools/queue-metrics'); new QueueMetrics().getSnapshot().then(console.log)"
```

### Prometheus scrape failing

**Check:**
1. Exporter running: `curl http://localhost:9091/health`
2. Firewall allows port 9091
3. Prometheus scrape config correct

### Stale metrics

**Cause:** Metrics only stored for 1 hour

**Solution:** Increase retention in `queue-metrics.js`:

```javascript
// Keep last 24 hours instead of 1 hour
const oneDayAgo = now - (24 * 60 * 60 * 1000);
await this.redis.zremrangebyscore(metricsKey, '-inf', oneDayAgo);
```

---

## Future Enhancements

- [ ] Histogram metrics for processing time distribution
- [ ] Per-worker throughput tracking
- [ ] Queue backlog prediction (time to empty)
- [ ] Auto-scaling triggers based on depth/throughput
- [ ] Dead letter queue metrics
- [ ] Priority queue metrics
- [ ] Cost tracking per queue

---

## Related Documentation

- `docs/REDIS_QUEUES.md` - Queue architecture
- `docs/WORKER_POOLS.md` - Worker pool design
- `~/.claude/FLEET.md` - Fleet configuration

---

**Questions?** Check existing metrics with:

```bash
node tools/queue-metrics.js watch
```
