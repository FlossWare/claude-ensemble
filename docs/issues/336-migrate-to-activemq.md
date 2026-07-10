# Issue #336: Migrate to ActiveMQ for distributed queue management

**Labels:** enhancement, infrastructure, technical-debt  
**Status:** Open  
**Created:** 2026-07-10  

## Current State

**Queue System:** PostgreSQL-based queues (queue.chunk, queue.embed, queue.graph, queue.store)

**Current Performance:**
- 6 concurrent workers across fleet
- ~25 items/sec throughput
- Simple SQL-based monitoring
- ACID guarantees via transactions

**Working well for:**
- Current scale (< 10 workers)
- Batch processing workloads
- Easy debugging with SQL queries

## Problem

PostgreSQL queues have limitations:
1. **Lock contention** at scale (50+ concurrent workers)
2. **Polling overhead** (workers repeatedly query for new items)
3. **No push notifications** (workers must poll)
4. **Limited throughput** compared to dedicated message brokers
5. **Table bloat** from high insert/delete volume

## Proposed Solution

**Migrate to ActiveMQ** (or RabbitMQ/Redis Streams) for distributed queue management.

**Benefits:**
- **Push-based delivery** (no polling)
- **Higher throughput** (thousands of messages/sec)
- **Better scaling** (100+ concurrent consumers)
- **Message persistence** (durable queues)
- **Advanced routing** (topics, fanout, dead-letter queues)
- **Standard protocols** (AMQP, STOMP, MQTT)

## Implementation Plan

1. **Deploy ActiveMQ broker** on aio-01 (or dedicated queue server)
2. **Create queues:** chunk, embed, graph, store
3. **Update workers** to use ActiveMQ client instead of PostgreSQL polling
4. **Migrate existing items** from PostgreSQL to ActiveMQ
5. **Update API endpoints** to publish to ActiveMQ instead of PostgreSQL
6. **Add monitoring** (ActiveMQ web console, Prometheus exporter)
7. **Parallel run** (both systems) for migration validation
8. **Cutover** and deprecate PostgreSQL queues

## When to Implement

**Triggers for migration:**
- Fleet scales beyond 50 concurrent workers
- Throughput requirements exceed 100 items/sec
- Sub-second latency needed for queue operations
- PostgreSQL lock contention becomes bottleneck

**Not urgent** - current system working adequately for current scale.

## Technical Considerations

**ActiveMQ setup:**
```bash
# Install ActiveMQ
sudo dnf install -y activemq

# Configure
sudo systemctl enable activemq
sudo systemctl start activemq

# Web console: http://aio-01:8161/admin
```

**Python client example:**
```python
import stomp

conn = stomp.Connection([('aio-01', 61613)])
conn.connect('admin', 'password', wait=True)

# Publish
conn.send('/queue/chunk', json.dumps({'document_id': 'uuid'}))

# Subscribe
conn.subscribe('/queue/chunk', id=1)
```

**Alternative options:**
- RabbitMQ (more features, AMQP standard)
- Redis Streams (simpler, in-memory)
- Apache Kafka (high-throughput, log-based)

## Acceptance Criteria

- [ ] ActiveMQ broker deployed and monitored
- [ ] All 4 queues migrated (chunk, embed, graph, store)
- [ ] Workers updated to use ActiveMQ client
- [ ] API endpoints publish to ActiveMQ
- [ ] Monitoring integrated (Prometheus + Grafana)
- [ ] PostgreSQL queue tables marked deprecated
- [ ] Documentation updated

## References

- PostgreSQL queue implementation: `/mnt/aio-01/claude-orchestrator/api/app/blueprints/queue.py`
- Worker scripts: `/tmp/*-worker.py`
- Current queue schema: `queue.chunk`, `queue.embed`, `queue.graph`, `queue.store`

## Priority

**Low** - Optimize current system first, migrate when scale requires it.
