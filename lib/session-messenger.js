#!/usr/bin/env node
// Session Messenger - Inter-session communication via file-based message queue
// Messages stored in ~/.claude/sessions/messages/

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

const SESSIONS_DIR = path.join(os.homedir(), '.claude', 'sessions');
const MESSAGES_DIR = path.join(SESSIONS_DIR, 'messages');
const INBOX_DIR = path.join(MESSAGES_DIR, 'inbox');
const OUTBOX_DIR = path.join(MESSAGES_DIR, 'outbox');
const ARCHIVE_DIR = path.join(MESSAGES_DIR, 'archive');

class SessionMessenger {
  constructor(sessionId = null) {
    this.sessionId = sessionId || this.getCurrentSessionId();
    this.ensureDirectories();
  }

  ensureDirectories() {
    for (const dir of [MESSAGES_DIR, INBOX_DIR, OUTBOX_DIR, ARCHIVE_DIR]) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }
  }

  getCurrentSessionId() {
    try {
      const sessionFiles = fs.readdirSync(SESSIONS_DIR)
        .filter(f => f.endsWith('.json') && f !== 'registry.json')
        .map(f => path.join(SESSIONS_DIR, f));

      for (const file of sessionFiles) {
        const data = JSON.parse(fs.readFileSync(file, 'utf8'));
        if (data.pid === process.pid) {
          return data.sessionId;
        }
      }
    } catch (err) {
      // Fallback to PID
    }
    return `pid-${process.pid}`;
  }

  // Send message to another session
  send(toSessionId, message) {
    const messageId = crypto.randomBytes(8).toString('hex');
    const timestamp = new Date().toISOString();

    const envelope = {
      id: messageId,
      from: this.sessionId,
      to: toSessionId,
      timestamp,
      type: message.type || 'message',
      priority: message.priority || 'normal',
      payload: message.payload || message,
      requires_response: message.requires_response || false,
      expires_at: message.expires_at || null
    };

    const filename = `${timestamp.replace(/[:.]/g, '-')}_${messageId}.json`;
    const filepath = path.join(INBOX_DIR, filename);

    fs.writeFileSync(filepath, JSON.stringify(envelope, null, 2), 'utf8');

    console.log(`Message ${messageId} sent to ${toSessionId}`);
    return envelope;
  }

  // Broadcast message to all sessions
  broadcast(message) {
    const SessionRegistry = require('./session-registry');
    const registry = new SessionRegistry();
    const sessions = registry.getActiveSessions();

    const results = [];
    for (const sessionId of Object.keys(sessions)) {
      if (sessionId !== this.sessionId) {
        results.push(this.send(sessionId, message));
      }
    }

    console.log(`Broadcast sent to ${results.length} session(s)`);
    return results;
  }

  // Receive messages for this session
  receive(options = {}) {
    const { unread_only = true, type = null, from = null } = options;

    const messages = fs.readdirSync(INBOX_DIR)
      .filter(f => f.endsWith('.json'))
      .map(f => {
        try {
          const filepath = path.join(INBOX_DIR, f);
          const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
          return { ...data, _file: f, _path: filepath };
        } catch (err) {
          return null;
        }
      })
      .filter(Boolean)
      .filter(msg => msg.to === this.sessionId || msg.to === 'all')
      .filter(msg => !type || msg.type === type)
      .filter(msg => !from || msg.from === from)
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));

    return messages;
  }

  // Mark message as read (archive it)
  markRead(messageId) {
    const messages = this.receive({ unread_only: true });
    const message = messages.find(m => m.id === messageId);

    if (!message) {
      console.warn(`Message ${messageId} not found`);
      return false;
    }

    const archivePath = path.join(ARCHIVE_DIR, message._file);
    fs.renameSync(message._path, archivePath);

    console.log(`Message ${messageId} archived`);
    return true;
  }

  // Reply to a message
  reply(originalMessageId, replyPayload) {
    const messages = this.receive({ unread_only: false });
    const original = messages.find(m => m.id === originalMessageId);

    if (!original) {
      throw new Error(`Original message ${originalMessageId} not found`);
    }

    return this.send(original.from, {
      type: 'reply',
      payload: replyPayload,
      in_reply_to: originalMessageId
    });
  }

  // Clean up expired messages
  cleanup() {
    const now = Date.now();
    let cleaned = 0;

    for (const dir of [INBOX_DIR, OUTBOX_DIR]) {
      const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));

      for (const file of files) {
        try {
          const filepath = path.join(dir, file);
          const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));

          if (data.expires_at && new Date(data.expires_at).getTime() < now) {
            fs.unlinkSync(filepath);
            cleaned++;
          }
        } catch (err) {
          // Ignore errors
        }
      }
    }

    console.log(`Cleaned up ${cleaned} expired message(s)`);
    return cleaned;
  }

  // List all messages
  list(options = {}) {
    const messages = this.receive(options);

    if (messages.length === 0) {
      console.log('No messages');
      return;
    }

    console.log(`\n${messages.length} message(s):\n`);

    for (const msg of messages) {
      console.log(`[${msg.id.slice(0, 8)}] ${msg.type} from ${msg.from.slice(0, 8)}...`);
      console.log(`  Time: ${msg.timestamp}`);
      console.log(`  Priority: ${msg.priority}`);

      if (typeof msg.payload === 'string') {
        console.log(`  Message: ${msg.payload}`);
      } else {
        console.log(`  Payload: ${JSON.stringify(msg.payload, null, 2)}`);
      }

      console.log('');
    }
  }
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];
  const messenger = new SessionMessenger();

  switch (command) {
    case 'send':
      const toSession = process.argv[3];
      const message = process.argv[4];
      if (!toSession || !message) {
        console.error('Usage: session-messenger.js send <sessionId> <message>');
        process.exit(1);
      }
      messenger.send(toSession, { payload: message });
      break;

    case 'broadcast':
      const broadcastMsg = process.argv[3];
      if (!broadcastMsg) {
        console.error('Usage: session-messenger.js broadcast <message>');
        process.exit(1);
      }
      messenger.broadcast({ payload: broadcastMsg });
      break;

    case 'receive':
    case 'list':
      messenger.list();
      break;

    case 'read':
      const msgId = process.argv[3];
      if (!msgId) {
        console.error('Usage: session-messenger.js read <messageId>');
        process.exit(1);
      }
      messenger.markRead(msgId);
      break;

    case 'reply':
      const replyToId = process.argv[3];
      const replyText = process.argv[4];
      if (!replyToId || !replyText) {
        console.error('Usage: session-messenger.js reply <messageId> <message>');
        process.exit(1);
      }
      messenger.reply(replyToId, replyText);
      break;

    case 'cleanup':
      messenger.cleanup();
      break;

    default:
      console.log('Usage: session-messenger.js <command> [args]');
      console.log('Commands:');
      console.log('  send <sessionId> <message> - Send message to specific session');
      console.log('  broadcast <message> - Send message to all sessions');
      console.log('  receive|list - List all messages for this session');
      console.log('  read <messageId> - Mark message as read (archive)');
      console.log('  reply <messageId> <message> - Reply to a message');
      console.log('  cleanup - Remove expired messages');
  }
}

module.exports = SessionMessenger;
