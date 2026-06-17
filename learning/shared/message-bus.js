#!/usr/bin/env node
/**
 * Phase 1: Simple file-based message passing system
 *
 * Provides a basic message bus using JSONL files in ~/.claude/learning/messages/
 * Each channel has its own .jsonl file for storing messages
 *
 * Future: Phase 2 will upgrade to Redis for better performance and distribution
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const MESSAGES_DIR = path.join(os.homedir(), '.claude', 'learning', 'messages');

/**
 * Ensure messages directory exists
 */
function ensureDir() {
  if (!fs.existsSync(MESSAGES_DIR)) {
    fs.mkdirSync(MESSAGES_DIR, { recursive: true });
  }
}

/**
 * Get the file path for a channel
 * @param {string} channel - Channel name
 * @returns {string} Full path to channel.jsonl file
 */
function getChannelPath(channel) {
  // Sanitize channel name to prevent directory traversal
  const sanitized = channel.replace(/[^a-z0-9_-]/gi, '_');
  return path.join(MESSAGES_DIR, `${sanitized}.jsonl`);
}

/**
 * Post a message to a channel
 * @param {string} channel - Channel name (e.g., 'general', 'findings', 'experiments')
 * @param {object} message - Message object (will be converted to JSON)
 * @returns {object} Message with added metadata (id, timestamp)
 */
function postMessage(channel, message) {
  ensureDir();

  if (!channel || typeof channel !== 'string') {
    throw new Error('Channel must be a non-empty string');
  }

  if (!message || typeof message !== 'object') {
    throw new Error('Message must be an object');
  }

  const channelPath = getChannelPath(channel);

  // Create enriched message with metadata
  const enrichedMessage = {
    id: generateMessageId(),
    timestamp: new Date().toISOString(),
    channel,
    ...message
  };

  // Append to channel file as JSONL
  const line = JSON.stringify(enrichedMessage) + '\n';
  fs.appendFileSync(channelPath, line, 'utf8');

  return enrichedMessage;
}

/**
 * Read messages from a channel
 * @param {string} channel - Channel name
 * @param {string|number} since - ISO timestamp or milliseconds since epoch (optional)
 * @returns {array} Array of message objects
 */
function readMessages(channel, since = null) {
  ensureDir();

  if (!channel || typeof channel !== 'string') {
    throw new Error('Channel must be a non-empty string');
  }

  const channelPath = getChannelPath(channel);

  // Return empty array if channel doesn't exist
  if (!fs.existsSync(channelPath)) {
    return [];
  }

  const content = fs.readFileSync(channelPath, 'utf8').trim();
  if (!content) {
    return [];
  }

  const messages = content
    .split('\n')
    .filter(line => line.trim())
    .map(line => JSON.parse(line));

  // Filter by timestamp if provided
  if (since) {
    const sinceTime = typeof since === 'string'
      ? new Date(since).getTime()
      : since;

    return messages.filter(msg => {
      const msgTime = new Date(msg.timestamp).getTime();
      return msgTime >= sinceTime;
    });
  }

  return messages;
}

/**
 * List all available channels
 * @returns {array} Array of channel names
 */
function listChannels() {
  ensureDir();

  if (!fs.existsSync(MESSAGES_DIR)) {
    return [];
  }

  return fs.readdirSync(MESSAGES_DIR)
    .filter(file => file.endsWith('.jsonl'))
    .map(file => file.replace('.jsonl', ''));
}

/**
 * Get channel statistics
 * @param {string} channel - Channel name
 * @returns {object} Stats object with message count, oldest/newest timestamps
 */
function getChannelStats(channel) {
  const messages = readMessages(channel);

  if (messages.length === 0) {
    return {
      channel,
      messageCount: 0,
      oldestMessage: null,
      newestMessage: null
    };
  }

  return {
    channel,
    messageCount: messages.length,
    oldestMessage: messages[0].timestamp,
    newestMessage: messages[messages.length - 1].timestamp
  };
}

/**
 * Clear all messages from a channel
 * @param {string} channel - Channel name
 * @returns {boolean} True if successful
 */
function clearChannel(channel) {
  ensureDir();
  const channelPath = getChannelPath(channel);

  if (fs.existsSync(channelPath)) {
    fs.unlinkSync(channelPath);
  }

  return true;
}

/**
 * Delete a specific message by ID (rebuilds file without the message)
 * @param {string} channel - Channel name
 * @param {string} messageId - Message ID to delete
 * @returns {boolean} True if message was found and deleted
 */
function deleteMessage(channel, messageId) {
  ensureDir();
  const channelPath = getChannelPath(channel);

  if (!fs.existsSync(channelPath)) {
    return false;
  }

  const messages = readMessages(channel);
  const filtered = messages.filter(msg => msg.id !== messageId);

  if (filtered.length === messages.length) {
    // Message not found
    return false;
  }

  // Rewrite file without the deleted message
  const lines = filtered.map(msg => JSON.stringify(msg) + '\n').join('');
  fs.writeFileSync(channelPath, lines, 'utf8');

  return true;
}

/**
 * Search messages by content
 * @param {string} channel - Channel name
 * @param {string|RegExp} query - Search string or regex
 * @param {string} field - Field to search in (default: 'text' or 'message')
 * @returns {array} Matching messages
 */
function searchMessages(channel, query, field = null) {
  const messages = readMessages(channel);

  const searchRegex = typeof query === 'string'
    ? new RegExp(query, 'i')
    : query;

  return messages.filter(msg => {
    if (field && msg[field]) {
      return searchRegex.test(String(msg[field]));
    }

    // Search across all string fields
    return Object.values(msg).some(val => {
      if (typeof val === 'string') {
        return searchRegex.test(val);
      }
      if (typeof val === 'object' && val !== null) {
        return searchRegex.test(JSON.stringify(val));
      }
      return false;
    });
  });
}

/**
 * Generate a unique message ID
 * @returns {string} Unique ID
 */
function generateMessageId() {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Export API
module.exports = {
  // Core API
  postMessage,
  readMessages,
  listChannels,

  // Extended API
  getChannelStats,
  clearChannel,
  deleteMessage,
  searchMessages,

  // Utilities
  generateMessageId,
  MESSAGES_DIR
};
