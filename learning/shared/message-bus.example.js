#!/usr/bin/env node
/**
 * Message Bus - Usage Examples
 *
 * Phase 1 implementation: Simple file-based message passing
 * Messages stored in ~/.claude/learning/messages/ as JSONL files
 */

const bus = require('./message-bus');

// Example 1: Post messages to different channels
console.log('=== Posting Messages ===\n');

const msg1 = bus.postMessage('general', {
  text: 'Hello from general channel',
  author: 'claude',
  priority: 'normal'
});
console.log('Posted to general:', msg1);

const msg2 = bus.postMessage('findings', {
  text: 'Discovered optimization opportunity',
  type: 'performance',
  impact: 'high'
});
console.log('Posted to findings:', msg2);

const msg3 = bus.postMessage('experiments', {
  text: 'Testing new approach',
  experiment_id: 'exp_001',
  status: 'running'
});
console.log('Posted to experiments:', msg3);

// Example 2: List all channels
console.log('\n=== Available Channels ===\n');
const channels = bus.listChannels();
console.log('Channels:', channels);

// Example 3: Read all messages from a channel
console.log('\n=== Reading from general channel ===\n');
const generalMessages = bus.readMessages('general');
console.log(`Found ${generalMessages.length} messages:`, generalMessages);

// Example 4: Read messages since a specific timestamp
console.log('\n=== Reading with time filter ===\n');
const recentMessages = bus.readMessages('findings', new Date(Date.now() - 60000)); // Last minute
console.log(`Found ${recentMessages.length} recent messages`);

// Example 5: Get channel statistics
console.log('\n=== Channel Statistics ===\n');
const stats = bus.getChannelStats('general');
console.log('General channel stats:', stats);

// Example 6: Search messages
console.log('\n=== Searching Messages ===\n');
const searchResults = bus.searchMessages('findings', 'optimization');
console.log(`Found ${searchResults.length} messages matching 'optimization'`);

// Example 7: Clear a channel
console.log('\n=== Clearing channel ===\n');
// bus.clearChannel('experiments');
console.log('(skipped clearing experiments for demo purposes)');

// Example 8: Show file structure
console.log('\n=== File Structure ===\n');
console.log('Messages directory:', bus.MESSAGES_DIR);
console.log('\nChannel files created:');
const fs = require('fs');
const path = require('path');
if (fs.existsSync(bus.MESSAGES_DIR)) {
  fs.readdirSync(bus.MESSAGES_DIR).forEach(file => {
    const filePath = path.join(bus.MESSAGES_DIR, file);
    const stats = fs.statSync(filePath);
    console.log(`  ${file} (${stats.size} bytes)`);
  });
}

console.log('\n=== API Reference ===\n');
console.log(`
Core API:
  postMessage(channel, message)      - Add message to channel
  readMessages(channel, since)       - Read all messages (optionally since timestamp)
  listChannels()                     - List all channel names

Extended API:
  getChannelStats(channel)           - Get message count and timestamp range
  clearChannel(channel)              - Delete all messages in channel
  deleteMessage(channel, id)         - Delete a specific message by ID
  searchMessages(channel, query)     - Full-text search within channel

Constants:
  MESSAGES_DIR                       - Path to messages directory

Example:
  const bus = require('./message-bus');
  bus.postMessage('general', { text: 'Hello', author: 'user' });
  const msgs = bus.readMessages('general');
`);
