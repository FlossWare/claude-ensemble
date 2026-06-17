#!/usr/bin/env node
/**
 * Message Bus - Unit Tests
 *
 * Tests all core functionality of the file-based message bus
 */

const bus = require('./message-bus');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
    testsPassed++;
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  ${err.message}`);
    testsFailed++;
  }
}

function cleanup() {
  // Clear test channels
  ['test_basic', 'test_search', 'test_stats'].forEach(channel => {
    try {
      bus.clearChannel(channel);
    } catch (e) {
      // Ignore
    }
  });
}

console.log('Message Bus - Test Suite\n');

// Test 1: Post and read messages
test('postMessage creates message with metadata', () => {
  const msg = bus.postMessage('test_basic', { text: 'Hello' });
  assert(msg.id, 'Message should have ID');
  assert(msg.timestamp, 'Message should have timestamp');
  assert(msg.channel === 'test_basic', 'Message should have channel');
  assert(msg.text === 'Hello', 'Message should preserve content');
});

test('readMessages returns posted messages', () => {
  const msg = bus.postMessage('test_basic', { text: 'Test message' });
  const messages = bus.readMessages('test_basic');
  assert(messages.length > 0, 'Should have at least one message');
  const found = messages.find(m => m.id === msg.id);
  assert(found, 'Posted message should be readable');
});

test('readMessages returns empty array for non-existent channel', () => {
  const messages = bus.readMessages('nonexistent_channel_xyz');
  assert(Array.isArray(messages), 'Should return array');
  assert(messages.length === 0, 'Should be empty for non-existent channel');
});

// Test 2: Time filtering
test('readMessages filters by timestamp', () => {
  bus.clearChannel('test_basic');

  const msg1 = bus.postMessage('test_basic', { text: 'Old message' });
  const cutoffTime = new Date();

  // Small delay to ensure different timestamps
  const msg2 = bus.postMessage('test_basic', { text: 'New message' });

  const recent = bus.readMessages('test_basic', cutoffTime);
  assert(recent.length > 0, 'Should find recent messages');
  assert(recent.some(m => m.id === msg2.id), 'Should include new message');
});

// Test 3: Channel listing
test('listChannels returns all channels', () => {
  bus.postMessage('test_ch_1', { text: 'msg1' });
  bus.postMessage('test_ch_2', { text: 'msg2' });

  const channels = bus.listChannels();
  assert(channels.includes('test_ch_1'), 'Should list test_ch_1');
  assert(channels.includes('test_ch_2'), 'Should list test_ch_2');
});

// Test 4: Channel statistics
test('getChannelStats returns correct counts', () => {
  bus.clearChannel('test_stats');

  bus.postMessage('test_stats', { text: 'msg1' });
  bus.postMessage('test_stats', { text: 'msg2' });
  bus.postMessage('test_stats', { text: 'msg3' });

  const stats = bus.getChannelStats('test_stats');
  assert(stats.messageCount === 3, 'Should count 3 messages');
  assert(stats.oldestMessage, 'Should have oldestMessage');
  assert(stats.newestMessage, 'Should have newestMessage');
});

test('getChannelStats returns zeros for empty channel', () => {
  bus.clearChannel('test_empty');
  const stats = bus.getChannelStats('test_empty');
  assert(stats.messageCount === 0, 'Should show 0 messages');
  assert(stats.oldestMessage === null, 'Should have no oldestMessage');
});

// Test 5: Search functionality
test('searchMessages finds text matches', () => {
  bus.clearChannel('test_search');

  bus.postMessage('test_search', { text: 'apple pie' });
  bus.postMessage('test_search', { text: 'banana split' });
  bus.postMessage('test_search', { text: 'apple juice' });

  const results = bus.searchMessages('test_search', 'apple');
  assert(results.length === 2, 'Should find 2 messages with "apple"');
});

test('searchMessages is case-insensitive', () => {
  bus.clearChannel('test_search');

  bus.postMessage('test_search', { text: 'HELLO world' });
  bus.postMessage('test_search', { text: 'goodbye' });

  const results = bus.searchMessages('test_search', 'hello');
  assert(results.length === 1, 'Should find case-insensitive match');
});

test('searchMessages searches specific fields', () => {
  bus.clearChannel('test_search');

  bus.postMessage('test_search', { author: 'alice', text: 'message' });
  bus.postMessage('test_search', { author: 'bob', text: 'message' });

  const results = bus.searchMessages('test_search', 'alice', 'author');
  assert(results.length === 1, 'Should find by author field');
});

// Test 6: Message deletion
test('deleteMessage removes message', () => {
  bus.clearChannel('test_basic');

  const msg1 = bus.postMessage('test_basic', { text: 'keep' });
  const msg2 = bus.postMessage('test_basic', { text: 'delete' });

  const deleted = bus.deleteMessage('test_basic', msg2.id);
  assert(deleted === true, 'Should return true');

  const remaining = bus.readMessages('test_basic');
  assert(remaining.length === 1, 'Should have 1 message left');
  assert(remaining[0].id === msg1.id, 'Should keep correct message');
});

test('deleteMessage returns false for non-existent ID', () => {
  const result = bus.deleteMessage('test_basic', 'nonexistent_id');
  assert(result === false, 'Should return false for non-existent message');
});

// Test 7: Channel clearing
test('clearChannel deletes all messages', () => {
  bus.postMessage('test_basic', { text: 'msg1' });
  bus.postMessage('test_basic', { text: 'msg2' });

  bus.clearChannel('test_basic');

  const messages = bus.readMessages('test_basic');
  assert(messages.length === 0, 'Should have no messages after clear');
});

// Test 8: Channel name sanitization
test('sanitizes channel names', () => {
  bus.postMessage('my:channel@2024!', { text: 'test' });
  const channels = bus.listChannels();
  assert(channels.includes('my_channel_2024_'), 'Should sanitize special chars');
});

// Test 9: JSONL file format
test('stores messages in valid JSONL format', () => {
  const testChannel = 'test_format';
  bus.clearChannel(testChannel);

  bus.postMessage(testChannel, { text: 'line 1' });
  bus.postMessage(testChannel, { text: 'line 2' });

  const filePath = path.join(bus.MESSAGES_DIR, `${testChannel}.jsonl`);
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.trim().split('\n');

  assert(lines.length === 2, 'Should have 2 lines');

  // Verify each line is valid JSON
  lines.forEach(line => {
    const obj = JSON.parse(line);
    assert(obj.id, 'Each line should be valid JSON');
  });
});

// Test 10: Error handling
test('throws error for invalid channel', () => {
  assert.throws(() => {
    bus.postMessage(null, { text: 'test' });
  }, 'Should throw for null channel');
});

test('throws error for invalid message', () => {
  assert.throws(() => {
    bus.postMessage('channel', null);
  }, 'Should throw for null message');
});

// Cleanup
cleanup();

// Summary
console.log(`\nResults: ${testsPassed} passed, ${testsFailed} failed`);
if (testsFailed === 0) {
  console.log('✓ All tests passed!');
  process.exit(0);
} else {
  console.log('✗ Some tests failed');
  process.exit(1);
}
