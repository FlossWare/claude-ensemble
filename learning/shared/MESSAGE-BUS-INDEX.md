# Message Bus - Implementation Index

## Phase 1: Simple File-Based Implementation

A lightweight message passing system using JSONL files for inter-agent communication in the Claude learning ecosystem.

### File Manifest

```
/home/sfloess/.claude/learning/shared/
├── message-bus.js                 (6.2 KB) - Core implementation
├── message-bus.example.js         (3.4 KB) - Working examples
├── test-message-bus.js            (7.1 KB) - Test suite (17 tests)
├── MESSAGE-BUS-README.md          (8.2 KB) - User guide
├── MESSAGE-BUS-API.md             (15 KB)  - Complete API reference
└── MESSAGE-BUS-INDEX.md           (this file)

/home/sfloess/.claude/learning/messages/
├── general.jsonl
├── findings.jsonl
├── experiments.jsonl
└── (other channels created at runtime)
```

## Quick Reference

### Core API (3 functions)

```javascript
const bus = require('./message-bus');

// Post a message
bus.postMessage(channel, message) → {id, timestamp, channel, ...message}

// Read messages
bus.readMessages(channel, since?) → object[]

// List channels
bus.listChannels() → string[]
```

### Extended API (4 functions)

```javascript
bus.getChannelStats(channel) → {channel, messageCount, oldestMessage, newestMessage}
bus.searchMessages(channel, query, field?) → object[]
bus.deleteMessage(channel, messageId) → boolean
bus.clearChannel(channel) → boolean
```

## Implementation Details

### Storage Format

**JSONL (JSON Lines)** - One message per line, newline-delimited

```json
{"id":"msg_1781364679974_v8w6z7gos","timestamp":"2026-06-13T15:31:19.974Z","channel":"general","text":"Hello","author":"claude"}
{"id":"msg_1781364679975_abc123def","timestamp":"2026-06-13T15:31:20.050Z","channel":"general","text":"World"}
```

### Message Structure

```javascript
{
  id: "msg_{timestamp}_{randomString}",  // Auto-generated
  timestamp: "2026-06-13T15:31:19.974Z", // ISO 8601
  channel: "channel_name",                // From parameter
  ...customFields                         // All user-provided data
}
```

### Channel Storage

- Location: `~/.claude/learning/messages/`
- File per channel: `{channel}.jsonl`
- Auto-creation: Directories and files created on first write
- Sanitization: Special chars replaced with underscores

## Test Coverage

✓ All 17 tests pass

- postMessage (metadata generation, content preservation)
- readMessages (retrieval, time filtering, empty channels)
- listChannels (enumeration, ordering)
- getChannelStats (counting, time ranges, empty states)
- searchMessages (text matching, case-insensitivity, field filtering)
- deleteMessage (removal, verification)
- clearChannel (bulk deletion)
- Sanitization (channel name safety)
- JSONL format (valid JSON per line)
- Error handling (type validation)

Run tests:
```bash
node /home/sfloess/.claude/learning/shared/test-message-bus.js
```

## Usage Patterns

### Pattern 1: Decision Tracking

```javascript
bus.postMessage('decisions', {
  type: 'decision',
  decision: 'Use Redis for cache layer',
  reasoning: 'Better scalability than files',
  alternatives: ['Memcached', 'File-based'],
  decidedBy: 'architecture-team',
  date: new Date().toISOString()
});
```

### Pattern 2: Finding/Issue Tracking

```javascript
bus.postMessage('findings', {
  findingId: 'FND-001',
  title: 'Performance bottleneck in middleware',
  severity: 'high',
  affectedComponent: 'api/auth',
  suggestedFix: 'Implement connection pooling',
  estimatedImpact: '40% latency reduction'
});
```

### Pattern 3: Experiment Tracking

```javascript
bus.postMessage('experiments', {
  experimentId: 'EXP-001',
  name: 'Test new caching strategy',
  hypothesis: 'Reduce DB queries by 50%',
  status: 'running',
  metrics: {
    baseline: { latency: 250 },
    current: { latency: 150 }
  }
});
```

### Pattern 4: Event Streaming

```javascript
bus.postMessage('events', {
  eventType: 'workflow_started',
  workflowId: 'wf_001',
  duration: { start: '2026-06-13T15:00:00Z', status: 'running' }
});
```

## Performance Characteristics

| Operation | Time | Scaling |
|-----------|------|---------|
| postMessage | O(1) | Linear file append |
| readMessages(full) | O(n) | n = messages in channel |
| readMessages(filtered) | O(n) | Must read entire file |
| listChannels | O(k) | k = number of channels |
| getChannelStats | O(n) | Scans entire file |
| searchMessages | O(n) | Full text scan |
| deleteMessage | O(n) | File rebuild |
| clearChannel | O(1) | File deletion |

**Limits:**
- ✓ Suitable: < 10,000 messages per channel
- ⚠ Marginal: 10K - 100K messages
- ✗ Upgrade Phase 2: > 100K messages or multi-node needed

## Future: Phase 2 Upgrade

### Redis Implementation

When scaling requirements demand:

```javascript
// Phase 2 API (same interface, different backend)
const impl = process.env.USE_REDIS === 'true'
  ? require('./message-bus-redis')
  : require('./message-bus');

const msg = impl.postMessage('general', {text: 'hello'});
```

### Migration Strategy

1. **Keep Phase 1** for backward compatibility
2. **Implement Phase 2** with same API
3. **Add factory** for backend selection
4. **Migrate data** from JSONL to Redis
5. **Deprecate Phase 1** when Phase 2 stable

### Phase 2 Benefits

- Sub-millisecond latency
- Distributed multi-node support
- Advanced data structures (sorted sets, streams)
- Built-in expiration
- Pub/Sub for real-time messaging

## Integration Guide

### Using in Workflows

```javascript
// workflow.js
const bus = require('./shared/message-bus');

module.exports = {
  meta: {
    name: 'my-workflow',
    description: 'Logs decisions and findings'
  },

  async execute(input) {
    // Post decision
    bus.postMessage('decisions', {
      workflow: 'my-workflow',
      decision: 'Use approach X',
      timestamp: new Date()
    });

    // Post findings
    const findings = analyze(input);
    findings.forEach(f => {
      bus.postMessage('findings', {
        workflow: 'my-workflow',
        ...f
      });
    });

    return { success: true };
  }
};
```

### Using in Utilities

```javascript
// utils/logger.js
const bus = require('../shared/message-bus');

class MessageBusLogger {
  constructor(channel = 'logs', context = {}) {
    this.channel = channel;
    this.context = context;
  }

  log(level, message, meta = {}) {
    bus.postMessage(this.channel, {
      level,
      message,
      timestamp: new Date(),
      ...this.context,
      ...meta
    });
  }

  error(msg, meta) { this.log('ERROR', msg, meta); }
  warn(msg, meta) { this.log('WARN', msg, meta); }
  info(msg, meta) { this.log('INFO', msg, meta); }
}

module.exports = MessageBusLogger;
```

### Using in Analysis

```javascript
// analysis/metrics.js
const bus = require('../shared/message-bus');

function analyzeChannelActivity(channel, hours = 24) {
  const since = new Date(Date.now() - hours * 60 * 60 * 1000);
  const messages = bus.readMessages(channel, since);

  return {
    channel,
    period: `${hours}h`,
    totalMessages: messages.length,
    oldestMessage: messages[0]?.timestamp,
    newestMessage: messages[messages.length - 1]?.timestamp,
    types: countByField(messages, 'type'),
    severities: countByField(messages, 'severity')
  };
}

function countByField(messages, field) {
  return messages.reduce((acc, msg) => {
    const val = msg[field] || 'unknown';
    acc[val] = (acc[val] || 0) + 1;
    return acc;
  }, {});
}
```

## Troubleshooting

### Issue: Channel files not being created

**Check:** Directory exists and is writable
```bash
ls -la ~/.claude/learning/messages/
```

**Solution:** Ensure directory has write permissions
```bash
mkdir -p ~/.claude/learning/messages
chmod 755 ~/.claude/learning/messages
```

### Issue: Messages not persisting

**Check:** File size and content
```bash
wc -l ~/.claude/learning/messages/*.jsonl
head ~/.claude/learning/messages/general.jsonl
```

**Solution:** Verify Node.js has write permissions to home directory

### Issue: Slow searches on large channels

**Recommendation:** Migrate to Phase 2 Redis or implement:
- Indexing by date ranges
- Separate archive channels for old messages
- Compression for historical data

## Documentation Map

| File | Purpose | Audience |
|------|---------|----------|
| message-bus.js | Implementation | Developers modifying code |
| message-bus.example.js | Working examples | Users learning API |
| test-message-bus.js | Test suite | QA, developers verifying changes |
| MESSAGE-BUS-README.md | User guide | End users, integrators |
| MESSAGE-BUS-API.md | API reference | Developers building on top |
| MESSAGE-BUS-INDEX.md | This file | Quick navigation |

## Example Commands

```bash
# Test installation
node ~/.claude/learning/shared/message-bus.example.js

# Run test suite
node ~/.claude/learning/shared/test-message-bus.js

# Inspect messages
cat ~/.claude/learning/messages/general.jsonl | jq .

# Count messages per channel
for f in ~/.claude/learning/messages/*.jsonl; do
  echo "$(basename $f): $(wc -l < $f) messages"
done

# Export channel as JSON
node -e "
  const bus = require('./message-bus');
  console.log(JSON.stringify(bus.readMessages('general'), null, 2));
" > general.json
```

## Status

**Phase 1:** ✅ Complete
- 4 implementation files
- 3 documentation files
- 17 passing tests
- Ready for production use (under scaling limits)

**Next:** Phase 2 (Redis) - TBD

---

**Created:** 2026-06-13  
**Version:** 1.0.0  
**Status:** Stable
