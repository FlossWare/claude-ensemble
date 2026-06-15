#!/usr/bin/env node
/**
 * Message Polling Daemon
 *
 * Continuously polls session-messages.json for messages addressed to this session
 * and auto-responds to common requests (heartbeat, discovery, status, etc.).
 *
 * Features:
 * - Poll every 5s for new messages
 * - Auto-respond to heartbeat requests
 * - Auto-respond to discovery requests
 * - Auto-respond to status requests
 * - Auto-respond to capability queries
 * - Log all activity to ~/.claude/learning/logs/message-polling.log
 * - Graceful shutdown on SIGINT/SIGTERM
 * - Systemd-compatible daemon
 *
 * Architecture:
 * - Uses SessionManager for all session operations
 * - Registers message handlers for auto-response
 * - Runs in background as systemd service
 * - Logs to dedicated log file for debugging
 *
 * Usage:
 *   # Direct execution (foreground)
 *   ./message-polling-daemon.js
 *
 *   # Run as systemd service
 *   systemctl start claude-message-polling
 *
 *   # Enable on boot
 *   systemctl enable claude-message-polling
 *
 *   # View logs
 *   journalctl -u claude-message-polling -f
 *   # OR
 *   tail -f ~/.claude/learning/logs/message-polling.log
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, appendFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { homedir } from 'os';
import { SessionManager } from './session-manager.js';

// ============================================================================
// CONSTANTS
// ============================================================================

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const LOG_DIR = resolve(homedir(), '.claude/learning/logs');
const LOG_FILE = resolve(LOG_DIR, 'message-polling.log');
const POLL_INTERVAL = 5000; // 5s
const DISCOVERIES_PATH = resolve(__dirname, './discoveries.json');

// ============================================================================
// LOGGING
// ============================================================================

/**
 * Ensure log directory exists
 */
function ensureLogDir() {
  if (!existsSync(LOG_DIR)) {
    mkdirSync(LOG_DIR, { recursive: true });
  }
}

/**
 * Log message to file and console
 */
function log(level, message, data = null) {
  ensureLogDir();

  const timestamp = new Date().toISOString();
  const logLine = data
    ? `[${timestamp}] [${level}] ${message} | ${JSON.stringify(data)}\n`
    : `[${timestamp}] [${level}] ${message}\n`;

  // Write to log file
  try {
    appendFileSync(LOG_FILE, logLine);
  } catch (err) {
    console.error(`Failed to write to log: ${err.message}`);
  }

  // Also write to console
  const consoleLine = data
    ? `[${level}] ${message} | ${JSON.stringify(data)}`
    : `[${level}] ${message}`;

  if (level === 'ERROR') {
    console.error(consoleLine);
  } else if (level === 'WARN') {
    console.warn(consoleLine);
  } else {
    console.log(consoleLine);
  }
}

// ============================================================================
// DAEMON STATE
// ============================================================================

let manager = null;
let running = false;
let pollTimer = null;

// ============================================================================
// MESSAGE HANDLERS
// ============================================================================

/**
 * Handle heartbeat request
 */
async function handleHeartbeatRequest(msg) {
  try {
    log('INFO', `Heartbeat request from ${msg.from}`);

    // Send heartbeat response
    await manager.sendMessage(msg.from, {
      type: 'heartbeat-response',
      data: {
        sessionId: manager.sessionId,
        timestamp: Date.now(),
        uptime: process.uptime(),
        pid: process.pid,
      },
    });

    log('INFO', `Sent heartbeat response to ${msg.from}`);
  } catch (err) {
    log('ERROR', `Failed to handle heartbeat request: ${err.message}`);
  }
}

/**
 * Handle discovery request
 */
async function handleDiscoveryRequest(msg) {
  try {
    log('INFO', `Discovery request from ${msg.from}`);

    // Load discoveries
    const discoveries = loadDiscoveries();

    // Filter by criteria if provided
    let filtered = discoveries;
    if (msg.data.filter) {
      const { minConfidence, maxAge, category } = msg.data.filter;

      filtered = discoveries.filter(disc => {
        if (minConfidence && disc.confidence < minConfidence) return false;
        if (maxAge && Date.now() - disc.timestamp > maxAge) return false;
        if (category && disc.category !== category) return false;
        return true;
      });
    }

    // Send discoveries
    await manager.sendMessage(msg.from, {
      type: 'discovery-response',
      data: {
        sessionId: manager.sessionId,
        discoveries: filtered.slice(0, 100), // Limit to 100
        total: filtered.length,
        timestamp: Date.now(),
      },
    });

    log('INFO', `Sent ${filtered.length} discoveries to ${msg.from}`);
  } catch (err) {
    log('ERROR', `Failed to handle discovery request: ${err.message}`);
  }
}

/**
 * Handle status request
 */
async function handleStatusRequest(msg) {
  try {
    log('INFO', `Status request from ${msg.from}`);

    const stats = await manager.getStats();

    // Send status
    await manager.sendMessage(msg.from, {
      type: 'status-response',
      data: {
        sessionId: manager.sessionId,
        status: 'active',
        uptime: process.uptime(),
        pid: process.pid,
        stats,
        timestamp: Date.now(),
      },
    });

    log('INFO', `Sent status to ${msg.from}`);
  } catch (err) {
    log('ERROR', `Failed to handle status request: ${err.message}`);
  }
}

/**
 * Handle capability query
 */
async function handleCapabilityQuery(msg) {
  try {
    log('INFO', `Capability query from ${msg.from}`);

    const capabilities = {
      models: ['opus', 'sonnet', 'haiku', 'fable'],
      features: [
        'message-polling',
        'auto-response',
        'discovery-sharing',
        'heartbeat',
        'status',
      ],
      version: '1.0.0',
    };

    // Send capabilities
    await manager.sendMessage(msg.from, {
      type: 'capability-response',
      data: {
        sessionId: manager.sessionId,
        capabilities,
        timestamp: Date.now(),
      },
    });

    log('INFO', `Sent capabilities to ${msg.from}`);
  } catch (err) {
    log('ERROR', `Failed to handle capability query: ${err.message}`);
  }
}

/**
 * Handle introduction message (from new session)
 */
async function handleIntroduction(msg) {
  try {
    log('INFO', `Introduction from ${msg.from}`);

    // Send introduction response
    await manager.sendMessage(msg.from, {
      type: 'introduction-response',
      data: {
        sessionId: manager.sessionId,
        greeting: 'Hello! I am the message polling daemon.',
        capabilities: {
          models: ['opus', 'sonnet', 'haiku', 'fable'],
          features: ['message-polling', 'auto-response'],
        },
        timestamp: Date.now(),
      },
    });

    log('INFO', `Sent introduction response to ${msg.from}`);
  } catch (err) {
    log('ERROR', `Failed to handle introduction: ${err.message}`);
  }
}

/**
 * Handle generic request
 */
async function handleGenericRequest(msg) {
  try {
    log('INFO', `Generic request from ${msg.from}`, msg.data);

    // Check what's being requested
    const { requestType } = msg.data;

    switch (requestType) {
      case 'heartbeat':
        await handleHeartbeatRequest(msg);
        break;
      case 'discovery':
        await handleDiscoveryRequest(msg);
        break;
      case 'status':
        await handleStatusRequest(msg);
        break;
      case 'capability':
        await handleCapabilityQuery(msg);
        break;
      default:
        log('WARN', `Unknown request type: ${requestType}`);
    }
  } catch (err) {
    log('ERROR', `Failed to handle generic request: ${err.message}`);
  }
}

// ============================================================================
// DISCOVERY LOADING
// ============================================================================

/**
 * Load discoveries from discoveries.json
 */
function loadDiscoveries() {
  try {
    if (!existsSync(DISCOVERIES_PATH)) {
      return [];
    }

    const content = readFileSync(DISCOVERIES_PATH, 'utf-8');
    const data = JSON.parse(content);

    return data.discoveries || [];
  } catch (err) {
    log('ERROR', `Failed to load discoveries: ${err.message}`);
    return [];
  }
}

// ============================================================================
// DAEMON LIFECYCLE
// ============================================================================

/**
 * Start daemon
 */
async function startDaemon() {
  try {
    log('INFO', '========================================');
    log('INFO', 'Starting Message Polling Daemon');
    log('INFO', '========================================');

    // Create session manager
    manager = new SessionManager({
      capabilities: {
        daemon: 'message-polling',
        autoResponse: true,
        models: ['opus', 'sonnet', 'haiku', 'fable'],
      },
      taskType: 'message-polling-daemon',
    });

    // Enable debug mode
    manager.debug = true;

    // Start session manager
    await manager.start();

    log('INFO', `Session started: ${manager.sessionId}`);

    // Register message handlers
    manager.onMessage('request', handleGenericRequest);
    manager.onMessage('heartbeat-request', handleHeartbeatRequest);
    manager.onMessage('discovery-request', handleDiscoveryRequest);
    manager.onMessage('status-request', handleStatusRequest);
    manager.onMessage('capability-query', handleCapabilityQuery);
    manager.onMessage('introduction', handleIntroduction);

    log('INFO', 'Registered message handlers');

    // Send introduction broadcast
    await manager.broadcast({
      type: 'introduction',
      data: {
        daemon: 'message-polling',
        capabilities: {
          autoResponse: true,
          models: ['opus', 'sonnet', 'haiku', 'fable'],
        },
      },
    });

    log('INFO', 'Sent introduction broadcast');

    running = true;

    log('INFO', 'Daemon started successfully');
    log('INFO', `Polling every ${POLL_INTERVAL}ms`);
    log('INFO', `Logging to: ${LOG_FILE}`);
  } catch (err) {
    log('ERROR', `Failed to start daemon: ${err.message}`);
    process.exit(1);
  }
}

/**
 * Stop daemon
 */
async function stopDaemon() {
  try {
    if (!running) {
      return;
    }

    log('INFO', '========================================');
    log('INFO', 'Stopping Message Polling Daemon');
    log('INFO', '========================================');

    running = false;

    // Send goodbye broadcast
    if (manager) {
      await manager.broadcast({
        type: 'goodbye',
        data: {
          sessionId: manager.sessionId,
          reason: 'daemon-shutdown',
        },
      });

      log('INFO', 'Sent goodbye broadcast');

      // Stop session manager
      await manager.stop();

      log('INFO', 'Session stopped');
    }

    log('INFO', 'Daemon stopped successfully');
    process.exit(0);
  } catch (err) {
    log('ERROR', `Failed to stop daemon: ${err.message}`);
    process.exit(1);
  }
}

// ============================================================================
// SIGNAL HANDLERS
// ============================================================================

/**
 * Handle shutdown signals
 */
function setupSignalHandlers() {
  process.on('SIGINT', async () => {
    log('INFO', 'Received SIGINT');
    await stopDaemon();
  });

  process.on('SIGTERM', async () => {
    log('INFO', 'Received SIGTERM');
    await stopDaemon();
  });

  process.on('uncaughtException', (err) => {
    log('ERROR', `Uncaught exception: ${err.message}`, { stack: err.stack });
    stopDaemon();
  });

  process.on('unhandledRejection', (reason, promise) => {
    log('ERROR', `Unhandled rejection: ${reason}`, { promise });
  });
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  setupSignalHandlers();
  await startDaemon();

  // Keep process alive
  process.stdin.resume();
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    log('ERROR', `Fatal error: ${err.message}`, { stack: err.stack });
    process.exit(1);
  });
}

// ============================================================================
// EXPORTS
// ============================================================================

export {
  startDaemon,
  stopDaemon,
  log,
};
