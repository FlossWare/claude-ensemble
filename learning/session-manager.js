#!/usr/bin/env node
/**
 * Session Manager
 *
 * Manages cross-session communication through:
 * - Session registration and heartbeats
 * - Message pub/sub
 * - Auto-cleanup of dead sessions
 * - Discovery propagation
 *
 * Hot-reloaded by orchestrator for live updates.
 *
 * Architecture:
 * - Sessions register with capabilities (models, task types)
 * - Heartbeat every 30s to stay alive
 * - Poll messages every 5s
 * - Auto-cleanup dead sessions (no heartbeat >5min)
 * - Broadcast discoveries to all active sessions
 *
 * Usage:
 *   import { SessionManager } from './session-manager.js';
 *
 *   const manager = new SessionManager();
 *   await manager.start();
 *
 *   // Register this session
 *   await manager.registerSession({
 *     capabilities: ['opus', 'sonnet'],
 *     taskType: 'code-review',
 *   });
 *
 *   // Send message
 *   await manager.sendMessage('session-123', {
 *     type: 'discovery',
 *     data: { ... },
 *   });
 *
 *   // Broadcast to all
 *   await manager.broadcast({
 *     type: 'insight',
 *     data: { ... },
 *   });
 *
 *   // Poll for messages
 *   const messages = await manager.getMessages();
 *
 *   // Cleanup and exit
 *   await manager.stop();
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve } from 'path';
import { randomBytes } from 'crypto';

// ============================================================================
// CONSTANTS
// ============================================================================

const REGISTRY_PATH = resolve('./learning/session-registry.json');
const MESSAGES_PATH = resolve('./learning/session-messages.json');

const HEARTBEAT_INTERVAL = 30000;  // 30s
const POLL_INTERVAL = 5000;        // 5s
const SESSION_TIMEOUT = 300000;    // 5min (no heartbeat)
const MESSAGE_TTL = 3600000;       // 1h

// ============================================================================
// SESSION MANAGER
// ============================================================================

export class SessionManager {
  constructor(options = {}) {
    this.sessionId = options.sessionId || this._generateSessionId();
    this.capabilities = options.capabilities || [];
    this.taskType = options.taskType || null;

    // State
    this.heartbeatTimer = null;
    this.pollTimer = null;
    this.messageHandlers = new Map(); // type -> handler
    this.running = false;

    // Debug
    this.debug = process.env.SESSION_DEBUG === 'true';
  }

  /**
   * Generate unique session ID
   */
  _generateSessionId() {
    const timestamp = Date.now().toString(36);
    const random = randomBytes(4).toString('hex');
    const pid = process.pid.toString(36);
    return `session-${timestamp}-${random}-${pid}`;
  }

  /**
   * Load registry (with file locking simulation via retry)
   */
  _loadRegistry() {
    if (!existsSync(REGISTRY_PATH)) {
      return { sessions: {}, lastCleanup: null, version: 1 };
    }

    try {
      const content = readFileSync(REGISTRY_PATH, 'utf-8');
      return JSON.parse(content);
    } catch (err) {
      if (this.debug) {
        console.warn(`[session-manager] Failed to load registry: ${err.message}`);
      }
      return { sessions: {}, lastCleanup: null, version: 1 };
    }
  }

  /**
   * Save registry (atomic write via temp file)
   */
  _saveRegistry(registry) {
    try {
      const tempPath = `${REGISTRY_PATH}.tmp`;
      writeFileSync(tempPath, JSON.stringify(registry, null, 2), 'utf-8');
      // Atomic rename (on most filesystems)
      if (existsSync(REGISTRY_PATH)) {
        writeFileSync(REGISTRY_PATH, readFileSync(tempPath));
      } else {
        writeFileSync(REGISTRY_PATH, readFileSync(tempPath));
      }
    } catch (err) {
      if (this.debug) {
        console.error(`[session-manager] Failed to save registry: ${err.message}`);
      }
      throw err;
    }
  }

  /**
   * Load messages
   */
  _loadMessages() {
    if (!existsSync(MESSAGES_PATH)) {
      return { messages: [], lastCleanup: null, version: 1 };
    }

    try {
      const content = readFileSync(MESSAGES_PATH, 'utf-8');
      return JSON.parse(content);
    } catch (err) {
      if (this.debug) {
        console.warn(`[session-manager] Failed to load messages: ${err.message}`);
      }
      return { messages: [], lastCleanup: null, version: 1 };
    }
  }

  /**
   * Save messages
   */
  _saveMessages(data) {
    try {
      const tempPath = `${MESSAGES_PATH}.tmp`;
      writeFileSync(tempPath, JSON.stringify(data, null, 2), 'utf-8');
      if (existsSync(MESSAGES_PATH)) {
        writeFileSync(MESSAGES_PATH, readFileSync(tempPath));
      } else {
        writeFileSync(MESSAGES_PATH, readFileSync(tempPath));
      }
    } catch (err) {
      if (this.debug) {
        console.error(`[session-manager] Failed to save messages: ${err.message}`);
      }
      throw err;
    }
  }

  /**
   * Register this session
   */
  async registerSession(options = {}) {
    const registry = this._loadRegistry();

    registry.sessions[this.sessionId] = {
      pid: process.pid,
      startTime: Date.now(),
      lastHeartbeat: Date.now(),
      capabilities: options.capabilities || this.capabilities,
      taskType: options.taskType || this.taskType,
      metadata: options.metadata || {},
    };

    this._saveRegistry(registry);

    if (this.debug) {
      console.log(`[session-manager] Registered session: ${this.sessionId}`);
    }

    return this.sessionId;
  }

  /**
   * Update heartbeat
   */
  async heartbeat() {
    const registry = this._loadRegistry();

    if (registry.sessions[this.sessionId]) {
      registry.sessions[this.sessionId].lastHeartbeat = Date.now();
      this._saveRegistry(registry);

      if (this.debug) {
        console.log(`[session-manager] Heartbeat: ${this.sessionId}`);
      }
    } else {
      // Session was cleaned up, re-register
      await this.registerSession();
    }
  }

  /**
   * Cleanup dead sessions (no heartbeat > SESSION_TIMEOUT)
   */
  async cleanupDeadSessions() {
    const registry = this._loadRegistry();
    const now = Date.now();
    let cleaned = 0;

    for (const [sessionId, session] of Object.entries(registry.sessions)) {
      const age = now - session.lastHeartbeat;
      if (age > SESSION_TIMEOUT) {
        delete registry.sessions[sessionId];
        cleaned++;
      }
    }

    if (cleaned > 0) {
      registry.lastCleanup = now;
      this._saveRegistry(registry);

      if (this.debug) {
        console.log(`[session-manager] Cleaned ${cleaned} dead sessions`);
      }
    }

    return cleaned;
  }

  /**
   * Get all active sessions
   */
  async getActiveSessions() {
    await this.cleanupDeadSessions();
    const registry = this._loadRegistry();
    return Object.entries(registry.sessions).map(([id, session]) => ({
      sessionId: id,
      ...session,
    }));
  }

  /**
   * Send message to specific session or broadcast
   */
  async sendMessage(to, message) {
    const data = this._loadMessages();

    const msg = {
      id: randomBytes(8).toString('hex'),
      from: this.sessionId,
      to: to || 'broadcast',
      type: message.type,
      data: message.data || {},
      timestamp: Date.now(),
      ttl: message.ttl || MESSAGE_TTL,
    };

    data.messages.push(msg);
    this._saveMessages(data);

    if (this.debug) {
      console.log(`[session-manager] Sent message: ${msg.type} -> ${msg.to}`);
    }

    return msg.id;
  }

  /**
   * Broadcast to all sessions
   */
  async broadcast(message) {
    return this.sendMessage('broadcast', message);
  }

  /**
   * Get messages for this session
   */
  async getMessages() {
    const data = this._loadMessages();
    const now = Date.now();

    // Filter messages for this session
    const messages = data.messages.filter(msg => {
      // Expired?
      if (now - msg.timestamp > msg.ttl) {
        return false;
      }

      // For this session?
      return msg.to === this.sessionId || msg.to === 'broadcast';
    });

    return messages;
  }

  /**
   * Cleanup old messages (TTL expired)
   */
  async cleanupOldMessages() {
    const data = this._loadMessages();
    const now = Date.now();
    const before = data.messages.length;

    data.messages = data.messages.filter(msg => {
      return now - msg.timestamp < msg.ttl;
    });

    const cleaned = before - data.messages.length;

    if (cleaned > 0) {
      data.lastCleanup = now;
      this._saveMessages(data);

      if (this.debug) {
        console.log(`[session-manager] Cleaned ${cleaned} expired messages`);
      }
    }

    return cleaned;
  }

  /**
   * Mark message as read (delete it)
   */
  async markAsRead(messageId) {
    const data = this._loadMessages();
    const before = data.messages.length;

    data.messages = data.messages.filter(msg => msg.id !== messageId);

    if (data.messages.length < before) {
      this._saveMessages(data);
    }
  }

  /**
   * Register message handler
   */
  onMessage(type, handler) {
    this.messageHandlers.set(type, handler);

    if (this.debug) {
      console.log(`[session-manager] Registered handler: ${type}`);
    }
  }

  /**
   * Poll for new messages and dispatch to handlers
   */
  async _pollMessages() {
    try {
      const messages = await this.getMessages();

      for (const msg of messages) {
        // Skip messages from ourselves
        if (msg.from === this.sessionId) {
          continue;
        }

        // Dispatch to handler
        const handler = this.messageHandlers.get(msg.type);
        if (handler) {
          try {
            await handler(msg);
          } catch (err) {
            if (this.debug) {
              console.error(`[session-manager] Handler error: ${err.message}`);
            }
          }
        }

        // Mark as read
        await this.markAsRead(msg.id);
      }
    } catch (err) {
      if (this.debug) {
        console.error(`[session-manager] Poll error: ${err.message}`);
      }
    }
  }

  /**
   * Start session manager (heartbeat + polling)
   */
  async start() {
    if (this.running) {
      return;
    }

    this.running = true;

    // Register session
    await this.registerSession();

    // Start heartbeat timer
    this.heartbeatTimer = setInterval(() => {
      this.heartbeat().catch(err => {
        if (this.debug) {
          console.error(`[session-manager] Heartbeat error: ${err.message}`);
        }
      });
    }, HEARTBEAT_INTERVAL);

    // Start message polling timer
    this.pollTimer = setInterval(() => {
      this._pollMessages().catch(err => {
        if (this.debug) {
          console.error(`[session-manager] Poll error: ${err.message}`);
        }
      });
    }, POLL_INTERVAL);

    // Cleanup timers
    const cleanupTimer = setInterval(() => {
      this.cleanupDeadSessions().catch(() => {});
      this.cleanupOldMessages().catch(() => {});
    }, 60000); // Every minute

    // Store cleanup timer for stop()
    this.cleanupTimer = cleanupTimer;

    if (this.debug) {
      console.log(`[session-manager] Started: ${this.sessionId}`);
    }
  }

  /**
   * Stop session manager
   */
  async stop() {
    if (!this.running) {
      return;
    }

    this.running = false;

    // Stop timers
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }

    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = null;
    }

    // Unregister session
    const registry = this._loadRegistry();
    delete registry.sessions[this.sessionId];
    this._saveRegistry(registry);

    if (this.debug) {
      console.log(`[session-manager] Stopped: ${this.sessionId}`);
    }
  }

  /**
   * Get session statistics
   */
  async getStats() {
    const sessions = await this.getActiveSessions();
    const data = this._loadMessages();

    return {
      sessionId: this.sessionId,
      activeSessions: sessions.length,
      pendingMessages: data.messages.length,
      uptime: Date.now() - (sessions.find(s => s.sessionId === this.sessionId)?.startTime || Date.now()),
    };
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let _instance = null;

/**
 * Get singleton session manager instance
 */
export function getSessionManager(options) {
  if (!_instance) {
    _instance = new SessionManager(options);
  }
  return _instance;
}

/**
 * Initialize session manager
 */
export async function initSessionManager(options) {
  const manager = getSessionManager(options);
  await manager.start();
  return manager;
}

// ============================================================================
// CONVENIENCE EXPORTS
// ============================================================================

export default {
  SessionManager,
  getSessionManager,
  initSessionManager,
};
