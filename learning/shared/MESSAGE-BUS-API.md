# Message Bus - Complete API Reference

## Quick Start

```javascript
const bus = require('./message-bus');

// Post a message
const msg = bus.postMessage('general', {
  text: 'Hello world',
  author: 'user'
});

// Read messages
const messages = bus.readMessages('general');
console.log(messages);

// List channels
const channels = bus.listChannels();
console.log(channels);
```

## Core API Reference

### postMessage(channel, message)

Post a message to a channel. Messages are enriched with metadata and persisted as JSONL.

**Signature:**
```javascript
function postMessage(channel: string, message: object): object
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| channel | string | Yes | Channel identifier (alphanumeric, dash, underscore; special chars replaced) |
| message | object | Yes | Message content (any JSON-serializable object) |

**Returns:**
```javascript
{
  id: string,              // Unique message ID (auto-generated)
  timestamp: string,       // ISO 8601 timestamp (auto-generated)
  channel: string,         // Channel name (auto-added)
  ...spreadMessage         // All fields from message parameter
}
```

**Throws:**
- TypeError if channel is not a non-empty string
- TypeError if message is not an object

**Examples:**

Basic message:
```javascript
bus.postMessage('general', {
  text: 'Hello everyone'
});
```

Structured data:
```javascript
bus.postMessage('findings', {
  findingId: 'FND-001',
  title: 'Critical bug found',
  severity: 'high',
  component: 'auth/login',
  workaround: 'Use JWT tokens instead',
  timeToFix: '2 hours',
  assignedTo: 'alice'
});
```

Complex nested structure:
```javascript
bus.postMessage('experiments', {
  experiment: 'cache_strategy_v2',
  metrics: {
    baseline: { cpu: 45, memory: 512, latency: 250 },
    optimized: { cpu: 25, memory: 256, latency: 100 },
    improvement: '60% latency reduction'
  },
  testEnvironment: {
    nodes: 3,
    dataset: 'production_sample_10k'
  }
});
```

---

### readMessages(channel, since)

Read messages from a channel with optional time filtering.

**Signature:**
```javascript
function readMessages(channel: string, since?: string|number): object[]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| channel | string | Yes | Channel to read from |
| since | string \| number | No | ISO 8601 timestamp or milliseconds since epoch; returns only messages after this time |

**Returns:**
- Array of message objects (empty array if channel doesn't exist)
- Messages in chronological order (oldest first)

**Throws:**
- TypeError if channel is not a non-empty string

**Examples:**

Read all messages:
```javascript
const allMsgs = bus.readMessages('general');
// Returns: [{id, timestamp, channel, ...}, ...]
```

Read recent messages (last hour):
```javascript
const oneHourAgo = new Date(Date.now() - 3600000);
const recent = bus.readMessages('findings', oneHourAgo);
```

Read messages since ISO timestamp:
```javascript
const since = '2026-06-13T12:00:00.000Z';
const msgs = bus.readMessages('experiments', since);
```

Read messages in last N minutes:
```javascript
function readLast(channel, minutes) {
  const since = new Date(Date.now() - minutes * 60000);
  return bus.readMessages(channel, since);
}

const last10min = readLast('general', 10);
```

---

### listChannels()

List all available channels.

**Signature:**
```javascript
function listChannels(): string[]
```

**Parameters:** None

**Returns:**
- Array of channel names (empty array if no channels exist)
- Sorted alphabetically

**Throws:** Never

**Examples:**

Basic usage:
```javascript
const channels = bus.listChannels();
// Returns: ['experiments', 'findings', 'general']
```

Channel existence check:
```javascript
function channelExists(name) {
  return bus.listChannels().includes(name);
}

if (channelExists('findings')) {
  // Process findings
}
```

Iterate channels:
```javascript
bus.listChannels().forEach(channel => {
  const stats = bus.getChannelStats(channel);
  console.log(`${channel}: ${stats.messageCount} messages`);
});
```

---

## Extended API Reference

### getChannelStats(channel)

Get statistics about a channel.

**Signature:**
```javascript
function getChannelStats(channel: string): object
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| channel | string | Yes | Channel to analyze |

**Returns:**
```javascript
{
  channel: string,           // Channel name
  messageCount: number,      // Total messages in channel
  oldestMessage: string|null, // ISO timestamp of oldest message (null if empty)
  newestMessage: string|null  // ISO timestamp of newest message (null if empty)
}
```

**Throws:**
- TypeError if channel is not a non-empty string

**Examples:**

Basic stats:
```javascript
const stats = bus.getChannelStats('general');
// Returns:
// {
//   channel: 'general',
//   messageCount: 42,
//   oldestMessage: '2026-06-01T08:15:00.000Z',
//   newestMessage: '2026-06-13T15:31:19.974Z'
// }
```

Check if channel is empty:
```javascript
if (bus.getChannelStats('general').messageCount === 0) {
  console.log('General channel is empty');
}
```

Get time span:
```javascript
const stats = bus.getChannelStats('findings');
if (stats.oldestMessage && stats.newestMessage) {
  const oldest = new Date(stats.oldestMessage);
  const newest = new Date(stats.newestMessage);
  const daysSpan = (newest - oldest) / (1000 * 60 * 60 * 24);
  console.log(`Channel spans ${daysSpan} days`);
}
```

---

### searchMessages(channel, query, field)

Full-text search within a channel.

**Signature:**
```javascript
function searchMessages(
  channel: string,
  query: string | RegExp,
  field?: string
): object[]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| channel | string | Yes | Channel to search |
| query | string \| RegExp | Yes | Search term (case-insensitive if string) or regex pattern |
| field | string | No | Specific field to search (searches all fields if omitted) |

**Returns:**
- Array of matching message objects
- Empty array if no matches or channel doesn't exist
- In chronological order (oldest first)

**Throws:**
- TypeError if channel is not a non-empty string

**Examples:**

Search all fields:
```javascript
const results = bus.searchMessages('findings', 'performance');
// Matches messages containing 'performance' in any field
```

Search specific field:
```javascript
const byAuthor = bus.searchMessages('general', 'alice', 'author');
// Only matches author field

const byStatus = bus.searchMessages('experiments', 'completed', 'status');
// Only matches status field
```

Case-sensitive regex search:
```javascript
const results = bus.searchMessages('findings', /^HIGH|CRITICAL$/i);
// Matches messages with HIGH or CRITICAL in any field

const perfPattern = /(optimize|bottleneck|cache)/i;
const perfIssues = bus.searchMessages('findings', perfPattern);
```

Compound search:
```javascript
// Find high-priority findings by specific author
const highPriority = bus.searchMessages('findings', 'high', 'priority')
  .filter(msg => msg.author === 'alice');

// Find recent critical items
const critical = bus.searchMessages('findings', 'CRITICAL')
  .filter(msg => new Date(msg.timestamp) > new Date(Date.now() - 86400000));
```

---

### clearChannel(channel)

Delete all messages from a channel.

**Signature:**
```javascript
function clearChannel(channel: string): boolean
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| channel | string | Yes | Channel to clear |

**Returns:**
- `true` (always succeeds, even if channel doesn't exist)

**Throws:**
- TypeError if channel is not a non-empty string

**Examples:**

Clear a channel:
```javascript
bus.clearChannel('experiments');
// All messages in experiments.jsonl are deleted
```

Clear with confirmation:
```javascript
const stats = bus.getChannelStats('general');
console.log(`Clearing ${stats.messageCount} messages from general`);
bus.clearChannel('general');
```

Conditional clearing:
```javascript
if (bus.getChannelStats('temp').messageCount > 1000) {
  bus.clearChannel('temp');
  console.log('Cleaned up temp channel');
}
```

---

### deleteMessage(channel, messageId)

Delete a specific message by ID.

**Signature:**
```javascript
function deleteMessage(channel: string, messageId: string): boolean
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| channel | string | Yes | Channel containing message |
| messageId | string | Yes | Message ID to delete (from message.id) |

**Returns:**
- `true` if message found and deleted
- `false` if message not found

**Throws:**
- TypeError if channel is not a non-empty string

**Examples:**

Delete specific message:
```javascript
const msg = bus.postMessage('general', { text: 'test' });
const deleted = bus.deleteMessage('general', msg.id);
// Returns: true
```

Delete with error handling:
```javascript
if (!bus.deleteMessage('general', 'msg_invalid_id')) {
  console.log('Message not found');
}
```

Selective deletion:
```javascript
const allMessages = bus.readMessages('general');
const toDelete = allMessages.filter(m => m.spam === true);
toDelete.forEach(msg => {
  bus.deleteMessage('general', msg.id);
});
```

Remove messages by criteria:
```javascript
function deleteWhere(channel, predicate) {
  const messages = bus.readMessages(channel);
  const matching = messages.filter(predicate);
  matching.forEach(msg => {
    bus.deleteMessage(channel, msg.id);
  });
  return matching.length;
}

// Delete messages older than 30 days
const threshold = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
const deleted = deleteWhere('general', msg =>
  new Date(msg.timestamp) < threshold
);
console.log(`Deleted ${deleted} old messages`);
```

---

## Constants

### MESSAGES_DIR

The root directory where all message channel files are stored.

**Type:** `string`

**Value:** `~/.claude/learning/messages` (expanded to absolute path)

**Usage:**
```javascript
const bus = require('./message-bus');
console.log(bus.MESSAGES_DIR);
// Prints: /home/user/.claude/learning/messages

// List files manually
const fs = require('fs');
fs.readdirSync(bus.MESSAGES_DIR).forEach(file => {
  console.log(file);
});
```

---

## Data Types

### Message Object

A message object in memory and in JSONL files.

**Standard Structure:**
```javascript
{
  id: string,              // Unique identifier, format: msg_{timestamp}_{random}
  timestamp: string,       // ISO 8601 string, created at post time
  channel: string,         // Channel name (copied from parameter)
  ...customFields          // Any additional fields provided
}
```

**Example:**
```javascript
{
  id: 'msg_1781364679974_v8w6z7gos',
  timestamp: '2026-06-13T15:31:19.974Z',
  channel: 'findings',
  severity: 'high',
  title: 'Database timeout',
  affectedServices: ['auth', 'payments'],
  estimatedUsers: 5000
}
```

### Channel Stats Object

Returned by `getChannelStats()`.

```javascript
{
  channel: string,         // Channel name
  messageCount: number,    // Total messages (>= 0)
  oldestMessage: string|null,  // ISO timestamp or null if empty
  newestMessage: string|null   // ISO timestamp or null if empty
}
```

---

## Error Patterns

### Input Validation

```javascript
try {
  bus.postMessage(null, {});
} catch (err) {
  console.error(err.message);
  // "Channel must be a non-empty string"
}

try {
  bus.postMessage('channel', null);
} catch (err) {
  console.error(err.message);
  // "Message must be an object"
}
```

### Safe Reading

```javascript
// readMessages never throws for non-existent channels
const msgs = bus.readMessages('does_not_exist');
console.log(msgs); // []

// Safely check before deleting
if (bus.deleteMessage('channel', 'fake_id')) {
  console.log('Deleted successfully');
} else {
  console.log('Message not found');
}
```

---

## Performance Notes

| Operation | Time | Notes |
|-----------|------|-------|
| postMessage | O(1) | File append operation |
| readMessages(full) | O(n) | n = total messages in channel |
| readMessages(filtered) | O(n) | Must read entire file to filter |
| listChannels | O(k) | k = number of channel files |
| getChannelStats | O(n) | Reads entire file |
| searchMessages | O(n) | Full scan, n = total messages |
| deleteMessage | O(n) | Rebuilds file |
| clearChannel | O(1) | File deletion |

**Recommendations:**
- Suitable for channels with < 10,000 messages
- Upgrade to Phase 2 (Redis) for larger datasets
- Use time filters to reduce scan time

---

## Integration Examples

### Logger Integration

```javascript
class MessageBusLogger {
  constructor(channel = 'logs') {
    this.channel = channel;
  }

  log(level, message, meta = {}) {
    bus.postMessage(this.channel, {
      level,
      message,
      timestamp: new Date(),
      ...meta
    });
  }

  error(msg, meta) { this.log('ERROR', msg, meta); }
  warn(msg, meta) { this.log('WARN', msg, meta); }
  info(msg, meta) { this.log('INFO', msg, meta); }
}

const logger = new MessageBusLogger('app-logs');
logger.error('Connection timeout', { service: 'database' });
```

### Event Stream

```javascript
class EventStream {
  emit(eventType, data) {
    bus.postMessage('events', {
      type: eventType,
      data,
      emittedAt: new Date()
    });
  }

  getEvents(since) {
    return bus.readMessages('events', since);
  }

  listen(callback, intervalMs = 1000) {
    let lastCheck = new Date();
    setInterval(() => {
      const events = this.getEvents(lastCheck);
      lastCheck = new Date();
      events.forEach(callback);
    }, intervalMs);
  }
}
```

### Analytics Collector

```javascript
class Analytics {
  track(event, properties = {}) {
    bus.postMessage('analytics', {
      event,
      properties,
      timestamp: new Date(),
      userId: process.env.USER_ID
    });
  }

  getMetrics(event, startTime, endTime) {
    const events = bus.readMessages('analytics', startTime);
    return events
      .filter(e => e.event === event && new Date(e.timestamp) <= endTime)
      .map(e => e.properties);
  }

  report() {
    const stats = bus.getChannelStats('analytics');
    return {
      totalEvents: stats.messageCount,
      period: `${stats.oldestMessage} to ${stats.newestMessage}`
    };
  }
}
```

---

## Related Files

- `message-bus.js` - Implementation
- `MESSAGE-BUS-README.md` - User guide
- `message-bus.example.js` - Working examples
- `test-message-bus.js` - Test suite

## Version

Phase 1 - File-based implementation  
Next: Phase 2 - Redis upgrade
