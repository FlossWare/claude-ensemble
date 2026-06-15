#!/usr/bin/env node
/**
 * Cross-Session Communication Demo
 *
 * Interactive demonstration of session communication features:
 * - Session registration and discovery
 * - Message passing and broadcast
 * - Discovery sharing
 * - Request/response pattern
 * - Real-time session monitoring
 *
 * Usage:
 *   chmod +x ./learning/demo-session-communication.js
 *   ./learning/demo-session-communication.js
 *
 * Or run multiple sessions in parallel:
 *   # Terminal 1
 *   SESSION_NAME="SessionA" ./learning/demo-session-communication.js
 *
 *   # Terminal 2
 *   SESSION_NAME="SessionB" ./learning/demo-session-communication.js
 */

import { SessionManager } from './session-manager.js';
import { wrapOrchestrator, shareDiscovery, requestHelp } from './session-integration.js';
import readline from 'readline';

// ============================================================================
// DEMO CONFIGURATION
// ============================================================================

const SESSION_NAME = process.env.SESSION_NAME || `Demo-${Date.now().toString(36)}`;
const COLORS = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
};

// ============================================================================
// UTILITIES
// ============================================================================

function log(message, color = 'reset') {
  console.log(`${COLORS[color]}${message}${COLORS.reset}`);
}

function header(text) {
  log('\n' + '='.repeat(60), 'bright');
  log(text, 'bright');
  log('='.repeat(60), 'bright');
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================================
// DEMO SESSION
// ============================================================================

class DemoSession {
  constructor(name) {
    this.name = name;
    this.manager = null;
    this.orch = null;
    this.running = false;
    this.messageCount = 0;
  }

  async start() {
    header(`Starting ${this.name}`);

    // Create session manager
    this.manager = new SessionManager({
      sessionId: this.name.toLowerCase().replace(/\s+/g, '-'),
      capabilities: ['opus', 'sonnet', 'haiku', 'fable'],
      taskType: 'demo',
    });

    // Register message handlers
    this.registerHandlers();

    // Start session (heartbeat + polling)
    await this.manager.start();

    log(`✓ Session started: ${this.manager.sessionId}`, 'green');

    // Wrap orchestrator
    this.orch = await wrapOrchestrator();
    log('✓ Orchestrator integration enabled', 'green');

    this.running = true;
  }

  registerHandlers() {
    // Discovery handler
    this.manager.onMessage('discovery', async (msg) => {
      this.messageCount++;
      log(`\n[DISCOVERY] From ${msg.from}:`, 'yellow');
      log(`  Insight: ${msg.data.insight}`, 'dim');
      log(`  Confidence: ${msg.data.confidence}`, 'dim');
    });

    // Insight handler
    this.manager.onMessage('insight', async (msg) => {
      this.messageCount++;
      log(`\n[INSIGHT] From ${msg.from}:`, 'cyan');
      log(`  ${msg.data.message || JSON.stringify(msg.data)}`, 'dim');
    });

    // Request handler
    this.manager.onMessage('request', async (msg) => {
      this.messageCount++;
      log(`\n[REQUEST] From ${msg.from}:`, 'magenta');
      log(`  ${msg.data.task || JSON.stringify(msg.data)}`, 'dim');

      // Respond to request
      if (msg.data.task === 'demo-help') {
        await this.manager.sendMessage(msg.from, {
          type: 'response',
          data: {
            requestId: msg.data.id,
            canHelp: true,
            sessionId: this.manager.sessionId,
            message: 'I can help with demo tasks!',
          },
        });
        log('  ✓ Sent response', 'green');
      }
    });

    // Response handler
    this.manager.onMessage('response', async (msg) => {
      this.messageCount++;
      log(`\n[RESPONSE] From ${msg.from}:`, 'blue');
      log(`  ${msg.data.message || JSON.stringify(msg.data)}`, 'dim');
    });

    // Coordination handler
    this.manager.onMessage('coordination', async (msg) => {
      this.messageCount++;
      log(`\n[COORDINATION] From ${msg.from}:`, 'blue');
      log(`  Action: ${msg.data.action}`, 'dim');
      if (msg.data.models) {
        log(`  Models: ${msg.data.models.join(', ')}`, 'dim');
      }
    });
  }

  async showActiveSessions() {
    const sessions = await this.manager.getActiveSessions();
    log(`\nActive sessions (${sessions.length}):`, 'bright');

    for (const session of sessions) {
      const isSelf = session.sessionId === this.manager.sessionId;
      const marker = isSelf ? '→' : ' ';
      const uptime = Math.floor((Date.now() - session.startTime) / 1000);

      log(`${marker} ${session.sessionId}`, isSelf ? 'green' : 'dim');
      log(`    Capabilities: ${session.capabilities.join(', ')}`, 'dim');
      log(`    Task: ${session.taskType}`, 'dim');
      log(`    Uptime: ${uptime}s`, 'dim');
    }
  }

  async sendBroadcast(message) {
    await this.manager.broadcast({
      type: 'insight',
      data: { message },
    });
    log(`✓ Broadcast sent: "${message}"`, 'green');
  }

  async shareTestDiscovery() {
    const discovery = {
      id: `demo-disc-${Date.now()}`,
      pattern: 'demo-pattern',
      insight: `Discovery from ${this.name}: Test pattern observed`,
      confidence: 0.85,
      evidence_count: 5,
      created_at: new Date().toISOString(),
    };

    await shareDiscovery(discovery);
    log(`✓ Shared discovery: ${discovery.id}`, 'green');
  }

  async requestDemoHelp() {
    log('Requesting help from other sessions...', 'yellow');

    const responses = await requestHelp({
      task: 'demo-help',
      capabilities: ['any'],
    });

    log(`✓ Received ${responses.length} responses`, 'green');

    for (const resp of responses) {
      log(`  From ${resp.sessionId}: ${resp.message}`, 'dim');
    }
  }

  async getStats() {
    const stats = await this.manager.getStats();
    log('\nSession statistics:', 'bright');
    log(`  Session ID: ${stats.sessionId}`, 'dim');
    log(`  Active sessions: ${stats.activeSessions}`, 'dim');
    log(`  Pending messages: ${stats.pendingMessages}`, 'dim');
    log(`  Messages received: ${this.messageCount}`, 'dim');
    log(`  Uptime: ${Math.floor(stats.uptime / 1000)}s`, 'dim');
  }

  async stop() {
    log('\nStopping session...', 'yellow');
    await this.manager.stop();
    this.running = false;
    log('✓ Session stopped', 'green');
  }
}

// ============================================================================
// INTERACTIVE MENU
// ============================================================================

async function showMenu(session) {
  log('\n' + '-'.repeat(60), 'dim');
  log('Commands:', 'bright');
  log('  1. Show active sessions', 'dim');
  log('  2. Send broadcast message', 'dim');
  log('  3. Share test discovery', 'dim');
  log('  4. Request help from sessions', 'dim');
  log('  5. Show session statistics', 'dim');
  log('  6. Run auto demo (all features)', 'dim');
  log('  q. Quit', 'dim');
  log('-'.repeat(60), 'dim');
}

async function runInteractive(session) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const question = (prompt) => new Promise((resolve) => {
    rl.question(prompt, resolve);
  });

  let running = true;

  while (running) {
    await showMenu(session);
    const choice = await question('\nChoose an option: ');

    switch (choice.trim()) {
      case '1':
        await session.showActiveSessions();
        break;

      case '2': {
        const message = await question('Enter message to broadcast: ');
        await session.sendBroadcast(message);
        break;
      }

      case '3':
        await session.shareTestDiscovery();
        break;

      case '4':
        await session.requestDemoHelp();
        break;

      case '5':
        await session.getStats();
        break;

      case '6':
        await runAutoDemo(session);
        break;

      case 'q':
      case 'Q':
        running = false;
        break;

      default:
        log('Invalid option', 'red');
    }
  }

  rl.close();
  await session.stop();
}

// ============================================================================
// AUTO DEMO
// ============================================================================

async function runAutoDemo(session) {
  header('Running Automated Demo');

  log('\n1. Showing active sessions...', 'yellow');
  await session.showActiveSessions();
  await sleep(2000);

  log('\n2. Broadcasting message...', 'yellow');
  await session.sendBroadcast(`Hello from ${session.name}! This is an automated demo.`);
  await sleep(2000);

  log('\n3. Sharing discovery...', 'yellow');
  await session.shareTestDiscovery();
  await sleep(2000);

  log('\n4. Requesting help...', 'yellow');
  await session.requestDemoHelp();
  await sleep(2000);

  log('\n5. Showing statistics...', 'yellow');
  await session.getStats();

  log('\n✓ Demo complete!', 'green');
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  header('Cross-Session Communication Demo');
  log(`Session name: ${SESSION_NAME}`, 'cyan');

  const session = new DemoSession(SESSION_NAME);

  try {
    await session.start();

    // Check for auto mode
    if (process.env.AUTO_DEMO === 'true') {
      await runAutoDemo(session);
      await sleep(5000); // Keep session alive to receive messages
      await session.stop();
    } else {
      await runInteractive(session);
    }
  } catch (err) {
    log(`\nError: ${err.message}`, 'red');
    console.error(err.stack);
    process.exit(1);
  }
}

// Handle Ctrl+C gracefully
process.on('SIGINT', async () => {
  log('\n\nReceived SIGINT, shutting down...', 'yellow');
  process.exit(0);
});

// Run main
main();
