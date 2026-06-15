#!/usr/bin/env node
/**
 * Session Integration Layer
 *
 * Hooks into orchestrator to enable cross-session communication:
 * - Auto-register session on first orchestrator call
 * - Auto-heartbeat on each orchestrator call
 * - Auto-share discoveries with other sessions
 * - Coordinate model selection across sessions
 *
 * Hot-reloaded by orchestrator for live updates.
 *
 * Features:
 * - Lazy initialization (session created on first use)
 * - Automatic heartbeat (every orchestrator call)
 * - Discovery propagation (new discoveries broadcast to all)
 * - Model coordination (avoid duplicate model usage)
 * - Request/response pattern (sessions can ask for help)
 *
 * Architecture:
 * - Wraps orchestrator calls with session hooks
 * - Monitors discoveries.json for new entries
 * - Broadcasts discoveries to all active sessions
 * - Listens for discovery messages from other sessions
 * - Applies remote discoveries to local learning DB
 *
 * Usage:
 *   import { wrapOrchestrator } from './session-integration.js';
 *
 *   // Wrap orchestrator for session integration
 *   const orch = await wrapOrchestrator();
 *
 *   // Use normally - session hooks run automatically
 *   const model = await orch.selectModel('code-review');
 *   // => Auto-registers session, sends heartbeat, checks for messages
 *
 *   // Share discovery with other sessions
 *   await shareDiscovery({
 *     id: 'disc-123',
 *     insight: 'fable fails on JSON',
 *     confidence: 0.92,
 *   });
 */

import { readFileSync, existsSync, statSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { hotImport } from '../shared/hot-reload.js';

// Get absolute path to orchestrator.js (relative to this file)
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ORCHESTRATOR_PATH = resolve(__dirname, '../orchestrator.js');

// ============================================================================
// CONSTANTS
// ============================================================================

const DISCOVERIES_PATH = resolve(__dirname, './discoveries.json');

// ============================================================================
// STATE
// ============================================================================

let _sessionInitialized = false;
let _sessionId = null;
let _lastDiscoveryCheck = 0;
let _knownDiscoveries = new Set();

// ============================================================================
// SESSION HOOKS
// ============================================================================

/**
 * Initialize session (lazy, called on first orchestrator use)
 */
async function _initSession() {
  if (_sessionInitialized) {
    return _sessionId;
  }

  try {
    const orchestrator = await hotImport(ORCHESTRATOR_PATH, { ttl: 1000 });

    // Detect capabilities from available models
    const capabilities = ['opus', 'sonnet', 'haiku', 'fable'];

    // Register session
    _sessionId = await orchestrator.initSession({
      capabilities,
      taskType: 'multi-model-orchestration',
      metadata: {
        version: '1.0.0',
        integrationEnabled: true,
      },
    });

    // Register message handlers
    await _registerMessageHandlers();

    _sessionInitialized = true;

    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Initialized: ${_sessionId}`);
    }

    return _sessionId;
  } catch (err) {
    console.warn(`[session-integration] Failed to initialize session: ${err.message}`);
    return null;
  }
}

/**
 * Auto-heartbeat (called on each orchestrator use)
 */
async function _autoHeartbeat() {
  try {
    const orchestrator = await hotImport(ORCHESTRATOR_PATH, { ttl: 1000 });
    await orchestrator.heartbeat();
  } catch (err) {
    // Silent fail - heartbeat is best-effort
  }
}

/**
 * Check for new discoveries and broadcast
 */
async function _checkAndShareDiscoveries() {
  try {
    // Rate limit: check at most every 5s
    const now = Date.now();
    if (now - _lastDiscoveryCheck < 5000) {
      return;
    }
    _lastDiscoveryCheck = now;

    if (!existsSync(DISCOVERIES_PATH)) {
      return;
    }

    // Check file modification time
    const stats = statSync(DISCOVERIES_PATH);
    const fileAge = now - stats.mtimeMs;

    // Only check recently modified files (within last 60s)
    if (fileAge > 60000) {
      return;
    }

    // Load discoveries
    const content = readFileSync(DISCOVERIES_PATH, 'utf-8');
    const data = JSON.parse(content);

    if (!data.discoveries || !Array.isArray(data.discoveries)) {
      return;
    }

    // Find new discoveries (not yet shared)
    const newDiscoveries = data.discoveries.filter(disc => {
      return !_knownDiscoveries.has(disc.id);
    });

    if (newDiscoveries.length === 0) {
      return;
    }

    // Share new discoveries with other sessions
    for (const discovery of newDiscoveries) {
      await shareDiscovery(discovery);
      _knownDiscoveries.add(discovery.id);
    }

    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Shared ${newDiscoveries.length} new discoveries`);
    }
  } catch (err) {
    // Silent fail - discovery sharing is best-effort
  }
}

/**
 * Register message handlers
 */
async function _registerMessageHandlers() {
  try {
    const orchestrator = await hotImport(ORCHESTRATOR_PATH, { ttl: 1000 });

    // Handle discovery messages from other sessions
    await orchestrator.onMessage('discovery', async (msg) => {
      await _handleDiscoveryMessage(msg);
    });

    // Handle insight messages
    await orchestrator.onMessage('insight', async (msg) => {
      await _handleInsightMessage(msg);
    });

    // Handle request messages (session asking for help)
    await orchestrator.onMessage('request', async (msg) => {
      await _handleRequestMessage(msg);
    });

    // Handle coordination messages (model selection coordination)
    await orchestrator.onMessage('coordination', async (msg) => {
      await _handleCoordinationMessage(msg);
    });

    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Registered message handlers`);
    }
  } catch (err) {
    console.warn(`[session-integration] Failed to register handlers: ${err.message}`);
  }
}

/**
 * Handle discovery message from another session
 */
async function _handleDiscoveryMessage(msg) {
  try {
    const discovery = msg.data;

    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Received discovery from ${msg.from}: ${discovery.id}`);
    }

    // Apply discovery to local learning DB
    const { default: updateMetadata } = await import('./update-discovery-metadata.js');

    // Import discovery (merge with local discoveries)
    await updateMetadata.importDiscovery(discovery);

    // Mark as known
    _knownDiscoveries.add(discovery.id);
  } catch (err) {
    if (process.env.SESSION_DEBUG) {
      console.error(`[session-integration] Failed to handle discovery: ${err.message}`);
    }
  }
}

/**
 * Handle insight message
 */
async function _handleInsightMessage(msg) {
  try {
    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Received insight from ${msg.from}:`, msg.data);
    }

    // Log insight for future use
    // TODO: Store insights in a dedicated insights.json file
  } catch (err) {
    // Silent fail
  }
}

/**
 * Handle request message (session asking for help)
 */
async function _handleRequestMessage(msg) {
  try {
    const request = msg.data;

    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Received request from ${msg.from}:`, request);
    }

    // Check if we can help
    const canHelp = await _canHandleRequest(request);

    if (canHelp) {
      // Send response
      const orchestrator = await hotImport(ORCHESTRATOR_PATH, { ttl: 1000 });
      await orchestrator.sendMessage(msg.from, {
        type: 'response',
        data: {
          requestId: request.id,
          canHelp: true,
          sessionId: _sessionId,
          capabilities: request.capabilities,
        },
      });
    }
  } catch (err) {
    // Silent fail
  }
}

/**
 * Handle coordination message
 */
async function _handleCoordinationMessage(msg) {
  try {
    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Received coordination from ${msg.from}:`, msg.data);
    }

    // TODO: Coordinate model selection with other sessions
    // Example: "I'll use opus" -> other sessions avoid opus
  } catch (err) {
    // Silent fail
  }
}

/**
 * Check if we can handle a request
 */
async function _canHandleRequest(request) {
  // TODO: Check our capabilities against request
  // For now, always return false (passive mode)
  return false;
}

// ============================================================================
// PUBLIC API
// ============================================================================

/**
 * Wrap orchestrator with session hooks
 *
 * @returns {Promise<Object>} Wrapped orchestrator
 */
export async function wrapOrchestrator() {
  const orchestrator = await hotImport('./orchestrator.js', { ttl: 1000 });

  // Create proxy that adds session hooks
  return new Proxy(orchestrator, {
    get(target, prop) {
      const original = target[prop];

      // Don't wrap non-functions
      if (typeof original !== 'function') {
        return original;
      }

      // Don't wrap session management functions (avoid recursion)
      if ([
        'registerSession',
        'sendMessage',
        'broadcast',
        'getMessages',
        'heartbeat',
        'getActiveSessions',
        'onMessage',
        'initSession',
        'getSessionStats',
      ].includes(prop)) {
        return original;
      }

      // Wrap function with session hooks
      return async function (...args) {
        // Initialize session on first use
        if (!_sessionInitialized) {
          await _initSession();
        }

        // Auto-heartbeat
        await _autoHeartbeat();

        // Check for new discoveries
        await _checkAndShareDiscoveries();

        // Call original function
        return original.apply(target, args);
      };
    },
  });
}

/**
 * Share discovery with other sessions
 *
 * @param {Object} discovery - Discovery object
 */
export async function shareDiscovery(discovery) {
  try {
    if (!_sessionInitialized) {
      await _initSession();
    }

    const orchestrator = await hotImport(ORCHESTRATOR_PATH, { ttl: 1000 });

    await orchestrator.broadcast({
      type: 'discovery',
      data: discovery,
      ttl: 3600000, // 1h
    });

    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Shared discovery: ${discovery.id}`);
    }
  } catch (err) {
    console.warn(`[session-integration] Failed to share discovery: ${err.message}`);
  }
}

/**
 * Request help from other sessions
 *
 * @param {Object} request - Request object
 * @returns {Promise<Object[]>} Responses from other sessions
 */
export async function requestHelp(request) {
  try {
    if (!_sessionInitialized) {
      await _initSession();
    }

    const orchestrator = await hotImport(ORCHESTRATOR_PATH, { ttl: 1000 });

    const requestId = `req-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

    await orchestrator.broadcast({
      type: 'request',
      data: {
        id: requestId,
        ...request,
      },
      ttl: 60000, // 1min
    });

    // Wait for responses (poll for 5s)
    const responses = [];
    const deadline = Date.now() + 5000;

    while (Date.now() < deadline) {
      const messages = await orchestrator.getMessages();

      for (const msg of messages) {
        if (msg.type === 'response' && msg.data.requestId === requestId) {
          responses.push(msg.data);
        }
      }

      if (responses.length > 0) {
        break;
      }

      await new Promise(resolve => setTimeout(resolve, 500));
    }

    return responses;
  } catch (err) {
    console.warn(`[session-integration] Failed to request help: ${err.message}`);
    return [];
  }
}

/**
 * Coordinate model selection with other sessions
 *
 * @param {string[]} models - Models we plan to use
 */
export async function coordinateModels(models) {
  try {
    if (!_sessionInitialized) {
      await _initSession();
    }

    const orchestrator = await hotImport(ORCHESTRATOR_PATH, { ttl: 1000 });

    await orchestrator.broadcast({
      type: 'coordination',
      data: {
        action: 'using-models',
        models,
        sessionId: _sessionId,
      },
      ttl: 30000, // 30s
    });

    if (process.env.SESSION_DEBUG) {
      console.log(`[session-integration] Coordinated models: ${models.join(', ')}`);
    }
  } catch (err) {
    // Silent fail
  }
}

/**
 * Get session ID
 */
export function getSessionId() {
  return _sessionId;
}

/**
 * Get session initialized status
 */
export function isSessionInitialized() {
  return _sessionInitialized;
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  wrapOrchestrator,
  shareDiscovery,
  requestHelp,
  coordinateModels,
  getSessionId,
  isSessionInitialized,
};
