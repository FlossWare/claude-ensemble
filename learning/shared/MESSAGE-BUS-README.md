# Message Bus - Phase 1 Implementation

## Overview

A simple, file-based message passing system for the Claude learning ecosystem. Messages are stored as JSONL (JSON Lines) files in `~/.claude/learning/messages/`, organized by channel.

**Phase 1:** File-based implementation (current)  
**Phase 2:** Redis upgrade for better performance and distribution

## Directory Structure

```
~/.claude/learning/
├── shared/
│   ├── message-bus.js              # Core implementation
│   ├── message-bus.example.js      # Usage examples
│   └── MESSAGE-BUS-README.md       # This file
└── messages/
    ├── general.jsonl               # General discussion channel
    ├── findings.jsonl              # Technical findings
    └── experiments.jsonl           # Experiment tracking
```

## Core API

### postMessage(channel, message)

Post a message to a channel.

**Parameters:**
- `channel` (string): Channel name (e.g., 'general', 'findings', 'experiments')
- `message` (object): Message content

**Returns:** Message object with added metadata (id, timestamp, channel)

**Example:**
```javascript
const bus = require('./message-bus');

const msg = bus.postMessage('findings', {
  text: 'Discovered optimization opportunity',
  type: 'performance',
  impact: 'high'
});
// Returns:
// {
//   id: 'msg_1781364679977_ov8wqtmmz',
//   timestamp: '2026-06-13T15:31:19.977Z',
//   channel: 'findings',
//   text: 'Discovered optimization opportunity',
//   type: 'performance',
//   impact: 'high'
// }
```

### readMessages(channel, since)

Read messages from a channel.

**Parameters:**
- `channel` (string): Channel name
- `since` (optional): ISO timestamp string or milliseconds since epoch

**Returns:** Array of message objects

**Example:**
```javascript
// Read all messages
const allMessages = bus.readMessages('general');

// Read recent messages (last hour)
const recentMessages = bus.readMessages('findings', 
  new Date(Date.now() - 3600000)
);

// Read messages since specific ISO timestamp
const since = bus.readMessages('experiments', 
  '2026-06-13T15:00:00.000Z'
);
```

### listChannels()

List all available channels.

**Returns:** Array of channel names

**Example:**
```javascript
const channels = bus.listChannels();
// Returns: ['experiments', 'findings', 'general']
```

## Extended API

### getChannelStats(channel)

Get statistics about a channel.

**Parameters:**
- `channel` (string): Channel name

**Returns:** Object with messageCount, oldestMessage, newestMessage timestamps

**Example:**
```javascript
const stats = bus.getChannelStats('general');
// Returns:
// {
//   channel: 'general',
//   messageCount: 5,
//   oldestMessage: '2026-06-13T10:00:00.000Z',
//   newestMessage: '2026-06-13T15:31:19.974Z'
// }
```

### searchMessages(channel, query, field)

Full-text search within a channel.

**Parameters:**
- `channel` (string): Channel name
- `query` (string|RegExp): Search string (case-insensitive) or regex
- `field` (optional): Specific field to search (default: all fields)

**Returns:** Array of matching message objects

**Example:**
```javascript
// Search all fields
const results = bus.searchMessages('findings', 'optimization');

// Search specific field
const byAuthor = bus.searchMessages('general', 'claude', 'author');

// Regex search
const regex = /performance|optimization/i;
const perfResults = bus.searchMessages('findings', regex);
```

### clearChannel(channel)

Delete all messages from a channel.

**Parameters:**
- `channel` (string): Channel name

**Returns:** true

**Example:**
```javascript
bus.clearChannel('experiments');
```

### deleteMessage(channel, messageId)

Delete a specific message by ID.

**Parameters:**
- `channel` (string): Channel name
- `messageId` (string): Message ID

**Returns:** boolean (true if found and deleted)

**Example:**
```javascript
const deleted = bus.deleteMessage('general', 'msg_1781364679974_v8w6z7gos');
```

## Message Format

Messages are stored as JSONL (JSON Lines) format - one JSON object per line.

**Structure:**
```json
{
  "id": "msg_1781364679974_v8w6z7gos",
  "timestamp": "2026-06-13T15:31:19.974Z",
  "channel": "general",
  "text": "Hello from general channel",
  "author": "claude",
  "priority": "normal"
}
```

**Standard Fields:**
- `id`: Unique message identifier (auto-generated)
- `timestamp`: ISO 8601 timestamp (auto-generated)
- `channel`: Channel name (auto-added from parameter)
- Additional fields: User-provided content

## Usage Patterns

### Pattern 1: Logging Decisions

```javascript
bus.postMessage('general', {
  type: 'decision',
  decision: 'Use Redis for distributed cache',
  reasoning: 'Better performance than file-based',
  alternatives: ['Memcached', 'File-based'],
  decidedBy: 'team-lead',
  date: new Date().toISOString()
});
```

### Pattern 2: Tracking Findings

```javascript
bus.postMessage('findings', {
  findingId: 'find_001',
  title: 'Performance bottleneck in async handler',
  severity: 'high',
  affectedComponent: 'api/middleware',
  suggestedFix: 'Implement connection pooling',
  estimatedImpact: '40% reduction in response time'
});
```

### Pattern 3: Experiment Tracking

```javascript
bus.postMessage('experiments', {
  experimentId: 'exp_001',
  name: 'Test new caching strategy',
  hypothesis: 'Reduce DB queries by 50%',
  status: 'running',
  startTime: new Date().toISOString(),
  metrics: {
    dbQueries: 150,
    responseTime: 250
  }
});
```

### Pattern 4: Search and Analysis

```javascript
// Find all high-priority findings
const critical = bus.searchMessages('findings', 'high', 'severity');

// Find recent experiments
const recent = bus.readMessages('experiments', 
  new Date(Date.now() - 86400000) // Last 24 hours
);

// Analyze decision history
const decisions = bus.searchMessages('general', 'decision', 'type');
```

## Implementation Details

### File Organization

- **Directory:** `~/.claude/learning/messages/`
- **File Pattern:** `{channel-name}.jsonl`
- **Format:** JSON Lines (one JSON object per line)
- **Encoding:** UTF-8

### Channel Sanitization

Channel names are sanitized to prevent directory traversal:
- Invalid characters are replaced with underscores
- Only alphanumeric, dash, underscore allowed
- Example: `my-channel:2024` → `my-channel_2024`

### Message ID Format

```
msg_{timestamp}_{randomString}
```

Example: `msg_1781364679974_v8w6z7gos`

### Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| postMessage | O(1) | Append to file |
| readMessages | O(n) | Read entire file, filter in memory |
| listChannels | O(k) | List directory, k = number of channels |
| searchMessages | O(n) | Linear scan through all messages |
| deleteMessage | O(n) | Rebuild entire file without deleted message |

**Limitations:**
- Not suitable for channels with 100,000+ messages
- No distributed access support (Phase 2 will use Redis)
- Synchronous I/O only (no async support)

## Error Handling

All functions throw errors for invalid inputs:

```javascript
// Invalid channel
bus.postMessage(null, {text: 'hello'});
// Error: Channel must be a non-empty string

// Invalid message
bus.postMessage('general', null);
// Error: Message must be an object

// Reading non-existent channel
const msgs = bus.readMessages('nonexistent');
// Returns: [] (empty array, no error)
```

## Testing

Run the example to verify installation:

```bash
cd ~/.claude/learning/shared
node message-bus.example.js
```

Expected output:
- Three messages posted to different channels
- Channels listed
- Statistics retrieved
- Search performed
- File structure displayed

## Migration Path to Phase 2

When ready to upgrade to Redis:

1. Create new `message-bus-redis.js` with same API
2. Keep file-based version for backward compatibility
3. Add factory function to select implementation:
   ```javascript
   const impl = process.env.USE_REDIS === 'true' 
     ? require('./message-bus-redis')
     : require('./message-bus');
   ```
4. Migrate data from JSONL files to Redis
5. Update consumers to use factory pattern

## Related Documentation

- `MESSAGE-BUS-API.md` - Detailed API reference
- `MESSAGE-BUS-EXAMPLES.md` - Advanced usage examples
- `DEPLOYMENT.md` - Deployment guide (includes message bus)

## License

Part of the Claude learning ecosystem.
