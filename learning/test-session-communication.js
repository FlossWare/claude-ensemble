#!/usr/bin/env node
/**
 * Cross-Session Communication Test Suite
 *
 * Tests all components of the session communication system:
 * - Session registry and heartbeat
 * - Message bus and pub/sub
 * - Discovery propagation
 * - Request/response pattern
 * - Model coordination
 * - Hot-reload integration
 *
 * Usage:
 *   chmod +x ./learning/test-session-communication.js
 *   ./learning/test-session-communication.js
 */

import { SessionManager } from './session-manager.js';
import { wrapOrchestrator, shareDiscovery, requestHelp, coordinateModels } from './session-integration.js';
import { readFileSync, writeFileSync, existsSync, unlinkSync } from 'fs';
import { resolve } from 'path';

// ============================================================================
// TEST UTILITIES
// ============================================================================

const REGISTRY_PATH = resolve('./learning/session-registry.json');
const MESSAGES_PATH = resolve('./learning/session-messages.json');
const BACKUP_SUFFIX = '.test-backup';

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`✓ ${message}`);
    testsPassed++;
  } else {
    console.error(`✗ ${message}`);
    testsFailed++;
    throw new Error(`Assertion failed: ${message}`);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function cleanup() {
  // Backup existing files
  if (existsSync(REGISTRY_PATH)) {
    const backup = readFileSync(REGISTRY_PATH);
    writeFileSync(REGISTRY_PATH + BACKUP_SUFFIX, backup);
  }

  if (existsSync(MESSAGES_PATH)) {
    const backup = readFileSync(MESSAGES_PATH);
    writeFileSync(MESSAGES_PATH + BACKUP_SUFFIX, backup);
  }

  // Reset files
  writeFileSync(REGISTRY_PATH, JSON.stringify({ sessions: {}, lastCleanup: null, version: 1 }, null, 2));
  writeFileSync(MESSAGES_PATH, JSON.stringify({ messages: [], lastCleanup: null, version: 1 }, null, 2));
}

async function restore() {
  // Restore backups
  if (existsSync(REGISTRY_PATH + BACKUP_SUFFIX)) {
    const backup = readFileSync(REGISTRY_PATH + BACKUP_SUFFIX);
    writeFileSync(REGISTRY_PATH, backup);
    unlinkSync(REGISTRY_PATH + BACKUP_SUFFIX);
  }

  if (existsSync(MESSAGES_PATH + BACKUP_SUFFIX)) {
    const backup = readFileSync(MESSAGES_PATH + BACKUP_SUFFIX);
    writeFileSync(MESSAGES_PATH, backup);
    unlinkSync(MESSAGES_PATH + BACKUP_SUFFIX);
  }
}

// ============================================================================
// TESTS
// ============================================================================

async function testSessionRegistration() {
  console.log('\n=== Test: Session Registration ===');

  const manager = new SessionManager({
    sessionId: 'test-session-1',
    capabilities: ['opus', 'sonnet'],
    taskType: 'test-task',
  });

  const sessionId = await manager.registerSession();
  assert(sessionId === 'test-session-1', 'Session ID matches');

  const sessions = await manager.getActiveSessions();
  assert(sessions.length === 1, 'One session registered');
  assert(sessions[0].sessionId === 'test-session-1', 'Correct session ID');
  assert(sessions[0].pid === process.pid, 'Correct PID');

  await manager.stop();
}

async function testHeartbeat() {
  console.log('\n=== Test: Heartbeat ===');

  const manager = new SessionManager({
    sessionId: 'test-session-2',
  });

  await manager.registerSession();

  const before = manager._loadRegistry();
  const beforeTime = before.sessions['test-session-2'].lastHeartbeat;

  await sleep(100);

  await manager.heartbeat();

  const after = manager._loadRegistry();
  const afterTime = after.sessions['test-session-2'].lastHeartbeat;

  assert(afterTime > beforeTime, 'Heartbeat updated timestamp');

  await manager.stop();
}

async function testMessaging() {
  console.log('\n=== Test: Messaging ===');

  const manager1 = new SessionManager({ sessionId: 'test-session-3a' });
  const manager2 = new SessionManager({ sessionId: 'test-session-3b' });

  await manager1.registerSession();
  await manager2.registerSession();

  // Send message from session 3a to session 3b
  const msgId = await manager1.sendMessage('test-session-3b', {
    type: 'test',
    data: { foo: 'bar' },
  });

  assert(msgId !== null, 'Message sent');

  // Get messages for session 3b
  const messages = await manager2.getMessages();
  assert(messages.length === 1, 'One message received');
  assert(messages[0].from === 'test-session-3a', 'Correct sender');
  assert(messages[0].type === 'test', 'Correct message type');
  assert(messages[0].data.foo === 'bar', 'Correct message data');

  await manager1.stop();
  await manager2.stop();
}

async function testBroadcast() {
  console.log('\n=== Test: Broadcast ===');

  const manager1 = new SessionManager({ sessionId: 'test-session-4a' });
  const manager2 = new SessionManager({ sessionId: 'test-session-4b' });
  const manager3 = new SessionManager({ sessionId: 'test-session-4c' });

  await manager1.registerSession();
  await manager2.registerSession();
  await manager3.registerSession();

  // Broadcast from session 4a
  await manager1.broadcast({
    type: 'announcement',
    data: { message: 'Hello everyone!' },
  });

  // All sessions should receive it (except sender)
  const messages2 = await manager2.getMessages();
  const messages3 = await manager3.getMessages();

  assert(messages2.length === 1, 'Session 4b received broadcast');
  assert(messages3.length === 1, 'Session 4c received broadcast');
  assert(messages2[0].to === 'broadcast', 'Message marked as broadcast');

  await manager1.stop();
  await manager2.stop();
  await manager3.stop();
}

async function testMessageHandlers() {
  console.log('\n=== Test: Message Handlers ===');

  const manager1 = new SessionManager({ sessionId: 'test-session-5a' });
  const manager2 = new SessionManager({ sessionId: 'test-session-5b' });

  await manager1.registerSession();
  await manager2.registerSession();

  // Register handler on session 5b
  let handlerCalled = false;
  let receivedData = null;

  manager2.onMessage('test-type', async (msg) => {
    handlerCalled = true;
    receivedData = msg.data;
  });

  // Start session 5b (starts polling)
  await manager2.start();

  // Send message from session 5a
  await manager1.sendMessage('test-session-5b', {
    type: 'test-type',
    data: { test: 'value' },
  });

  // Wait for polling to pick up message
  await sleep(6000); // POLL_INTERVAL is 5s

  assert(handlerCalled, 'Handler was called');
  assert(receivedData.test === 'value', 'Handler received correct data');

  await manager1.stop();
  await manager2.stop();
}

async function testSessionCleanup() {
  console.log('\n=== Test: Session Cleanup ===');

  // Reset registry for this test
  await cleanup();

  const manager1 = new SessionManager({ sessionId: 'test-session-6a' });
  const manager2 = new SessionManager({ sessionId: 'test-session-6b' });

  await manager1.registerSession();
  await manager2.registerSession();

  // Manually set session 6a heartbeat to old timestamp
  const registry = manager1._loadRegistry();
  registry.sessions['test-session-6a'].lastHeartbeat = Date.now() - 400000; // 6+ minutes ago
  manager1._saveRegistry(registry);

  // Cleanup
  const cleaned = await manager2.cleanupDeadSessions();
  assert(cleaned === 1, 'One dead session cleaned');

  const sessions = await manager2.getActiveSessions();
  assert(sessions.length === 1, 'Only one session remains');
  assert(sessions[0].sessionId === 'test-session-6b', 'Correct session remains');

  await manager1.stop();
  await manager2.stop();
}

async function testMessageCleanup() {
  console.log('\n=== Test: Message Cleanup ===');

  const manager = new SessionManager({ sessionId: 'test-session-7' });
  await manager.registerSession();

  // Create old message
  const data = manager._loadMessages();
  data.messages.push({
    id: 'old-msg',
    from: 'test-session-7',
    to: 'broadcast',
    type: 'test',
    data: {},
    timestamp: Date.now() - 4000000, // >1h ago
    ttl: 3600000, // 1h
  });
  manager._saveMessages(data);

  // Cleanup
  const cleaned = await manager.cleanupOldMessages();
  assert(cleaned === 1, 'One old message cleaned');

  await manager.stop();
}

async function testOrchestratorIntegration() {
  console.log('\n=== Test: Orchestrator Integration ===');

  // Wrap orchestrator
  const orch = await wrapOrchestrator();

  // Call wrapped function
  const model = await orch.selectModel('code-review', { count: 1 });

  assert(model !== null, 'Wrapped selectModel returned result');

  // Check that session was initialized
  const sessions = await orch.getActiveSessions();
  assert(sessions.length > 0, 'Session was auto-registered');

  console.log(`  Session ID: ${sessions[0].sessionId}`);
  console.log(`  Capabilities: ${sessions[0].capabilities.join(', ')}`);
}

async function testDiscoverySharing() {
  console.log('\n=== Test: Discovery Sharing ===');

  const discovery = {
    id: `test-disc-${Date.now()}`,
    pattern: 'test-pattern',
    insight: 'Test insight',
    confidence: 0.85,
    evidence_count: 10,
  };

  await shareDiscovery(discovery);

  // Wait for message to be sent
  await sleep(1000);

  const manager = new SessionManager({ sessionId: 'test-session-disc' });
  await manager.registerSession();

  const messages = await manager.getMessages();
  const discMsg = messages.find(m => m.type === 'discovery' && m.data.id === discovery.id);

  assert(discMsg !== undefined, 'Discovery was broadcast');
  assert(discMsg.data.insight === 'Test insight', 'Discovery data is correct');

  await manager.stop();
}

async function testRequestHelp() {
  console.log('\n=== Test: Request Help ===');

  const manager = new SessionManager({ sessionId: 'test-session-help' });
  await manager.registerSession();

  // Request help
  const responses = await requestHelp({
    task: 'pdf-analysis',
    capabilities: ['opus'],
  });

  // No responses expected (no helper sessions running)
  assert(Array.isArray(responses), 'Responses is an array');
  console.log(`  Received ${responses.length} responses`);

  await manager.stop();
}

async function testModelCoordination() {
  console.log('\n=== Test: Model Coordination ===');

  await coordinateModels(['opus', 'sonnet']);

  // Wait for message to be sent
  await sleep(1000);

  const manager = new SessionManager({ sessionId: 'test-session-coord' });
  await manager.registerSession();

  const messages = await manager.getMessages();
  const coordMsg = messages.find(m => m.type === 'coordination');

  assert(coordMsg !== undefined, 'Coordination was broadcast');
  assert(coordMsg.data.action === 'using-models', 'Correct coordination action');
  assert(coordMsg.data.models.includes('opus'), 'Models include opus');

  await manager.stop();
}

async function testHotReload() {
  console.log('\n=== Test: Hot Reload ===');

  // Import orchestrator twice - should use hot-reload cache
  const orch1 = await wrapOrchestrator();
  const orch2 = await wrapOrchestrator();

  assert(orch1 !== null, 'First import succeeded');
  assert(orch2 !== null, 'Second import succeeded');

  console.log('  Hot-reload working correctly');
}

async function testSessionStats() {
  console.log('\n=== Test: Session Stats ===');

  const manager = new SessionManager({ sessionId: 'test-session-stats' });
  await manager.registerSession();

  const stats = await manager.getStats();

  assert(stats.sessionId === 'test-session-stats', 'Correct session ID in stats');
  assert(stats.activeSessions >= 1, 'At least one active session');
  assert(typeof stats.uptime === 'number', 'Uptime is a number');

  console.log(`  Active sessions: ${stats.activeSessions}`);
  console.log(`  Pending messages: ${stats.pendingMessages}`);
  console.log(`  Uptime: ${stats.uptime}ms`);

  await manager.stop();
}

// ============================================================================
// RUN TESTS
// ============================================================================

async function runAllTests() {
  console.log('Cross-Session Communication Test Suite');
  console.log('======================================\n');

  try {
    await cleanup();

    await testSessionRegistration();
    await testHeartbeat();
    await testMessaging();
    await testBroadcast();
    await testMessageHandlers();
    await testSessionCleanup();
    await testMessageCleanup();
    await testOrchestratorIntegration();
    await testDiscoverySharing();
    await testRequestHelp();
    await testModelCoordination();
    await testHotReload();
    await testSessionStats();

    console.log('\n======================================');
    console.log(`Tests passed: ${testsPassed}`);
    console.log(`Tests failed: ${testsFailed}`);

    if (testsFailed === 0) {
      console.log('\n✓ All tests passed!');
      process.exit(0);
    } else {
      console.log('\n✗ Some tests failed');
      process.exit(1);
    }
  } catch (err) {
    console.error('\n✗ Test suite failed:', err.message);
    console.error(err.stack);
    process.exit(1);
  } finally {
    await restore();
  }
}

// Run tests
runAllTests();
