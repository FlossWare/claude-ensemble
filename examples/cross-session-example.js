#!/usr/bin/env node
/**
 * Cross-Session Communication - Example Usage
 *
 * Demonstrates the three main usage patterns:
 * 1. Automatic integration (recommended)
 * 2. Manual session control
 * 3. Custom message handling
 *
 * Usage:
 *   chmod +x examples/cross-session-example.js
 *   node examples/cross-session-example.js
 */

import { wrapOrchestrator, shareDiscovery, requestHelp } from '../learning/session-integration.js';
import { SessionManager } from '../learning/session-manager.js';

// ============================================================================
// PATTERN 1: Automatic Integration (Recommended)
// ============================================================================

async function example1_automatic() {
  console.log('\n=== Pattern 1: Automatic Integration ===\n');

  // Wrap orchestrator - session hooks added automatically
  const orch = await wrapOrchestrator();

  // Use orchestrator normally
  // Session is registered, heartbeat sent, messages checked automatically!
  const model = await orch.selectModel('code-review', { count: 1 });
  console.log(`Selected model: ${model}`);

  // Share a discovery - automatically broadcast to all sessions
  await shareDiscovery({
    id: `auto-disc-${Date.now()}`,
    pattern: 'example-pattern',
    insight: 'This discovery was shared automatically',
    confidence: 0.92,
  });
  console.log('✓ Discovery shared with all sessions');

  // Request help from other sessions
  const responses = await requestHelp({
    task: 'example-task',
    capabilities: ['any'],
  });
  console.log(`✓ Received ${responses.length} responses`);

  // Get session info
  const stats = await orch.getSessionStats();
  console.log(`\nSession info:`);
  console.log(`  Session ID: ${stats.sessionId}`);
  console.log(`  Active sessions: ${stats.activeSessions}`);
  console.log(`  Pending messages: ${stats.pendingMessages}`);
}

// ============================================================================
// PATTERN 2: Manual Session Control
// ============================================================================

async function example2_manual() {
  console.log('\n=== Pattern 2: Manual Session Control ===\n');

  // Create session with explicit configuration
  const manager = new SessionManager({
    sessionId: 'example-manual-session',
    capabilities: ['opus', 'sonnet', 'haiku'],
    taskType: 'example-task',
  });

  // Start session (heartbeat + polling daemons)
  await manager.start();
  console.log(`✓ Session started: ${manager.sessionId}`);

  // Send message to specific session
  await manager.sendMessage('other-session-id', {
    type: 'insight',
    data: { message: 'Hello from manual session!' },
  });
  console.log('✓ Message sent');

  // Broadcast to all sessions
  await manager.broadcast({
    type: 'discovery',
    data: {
      insight: 'Broadcasting from manual session',
      confidence: 0.88,
    },
  });
  console.log('✓ Broadcast sent');

  // Get active sessions
  const sessions = await manager.getActiveSessions();
  console.log(`\n✓ Found ${sessions.length} active sessions:`);
  for (const session of sessions) {
    console.log(`  - ${session.sessionId} (${session.taskType})`);
  }

  // Get messages
  const messages = await manager.getMessages();
  console.log(`\n✓ Pending messages: ${messages.length}`);

  // Get stats
  const stats = await manager.getStats();
  console.log(`\nSession statistics:`);
  console.log(`  Active sessions: ${stats.activeSessions}`);
  console.log(`  Pending messages: ${stats.pendingMessages}`);
  console.log(`  Uptime: ${Math.floor(stats.uptime / 1000)}s`);

  // Stop session (cleanup)
  await manager.stop();
  console.log('\n✓ Session stopped');
}

// ============================================================================
// PATTERN 3: Custom Message Handling
// ============================================================================

async function example3_custom_handlers() {
  console.log('\n=== Pattern 3: Custom Message Handling ===\n');

  const manager = new SessionManager({
    sessionId: 'example-handler-session',
    capabilities: ['all'],
    taskType: 'custom-handler-demo',
  });

  // Register custom message handlers BEFORE starting
  let discoveryCount = 0;
  let insightCount = 0;

  manager.onMessage('discovery', async (msg) => {
    discoveryCount++;
    console.log(`\n[DISCOVERY] From ${msg.from}:`);
    console.log(`  Insight: ${msg.data.insight || 'N/A'}`);
    console.log(`  Confidence: ${msg.data.confidence || 'N/A'}`);
  });

  manager.onMessage('insight', async (msg) => {
    insightCount++;
    console.log(`\n[INSIGHT] From ${msg.from}:`);
    console.log(`  ${msg.data.message || JSON.stringify(msg.data)}`);
  });

  manager.onMessage('request', async (msg) => {
    console.log(`\n[REQUEST] From ${msg.from}:`);
    console.log(`  Task: ${msg.data.task}`);

    // Respond to request
    if (msg.data.task === 'example-help') {
      await manager.sendMessage(msg.from, {
        type: 'response',
        data: {
          requestId: msg.data.id,
          canHelp: true,
          sessionId: manager.sessionId,
          message: 'I can help with example tasks!',
        },
      });
      console.log('  ✓ Sent response');
    }
  });

  // Start session (handlers will process incoming messages)
  await manager.start();
  console.log('✓ Session started with custom handlers');

  // Send some test messages
  await manager.broadcast({
    type: 'discovery',
    data: {
      insight: 'Test discovery from handler demo',
      confidence: 0.95,
    },
  });

  await manager.broadcast({
    type: 'insight',
    data: {
      message: 'Test insight from handler demo',
    },
  });

  // Wait a bit for messages to be processed
  await new Promise(resolve => setTimeout(resolve, 1000));

  console.log(`\n✓ Messages processed:`);
  console.log(`  Discoveries: ${discoveryCount}`);
  console.log(`  Insights: ${insightCount}`);

  // Stop session
  await manager.stop();
  console.log('\n✓ Session stopped');
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  console.log('Cross-Session Communication - Example Usage');
  console.log('==========================================');

  try {
    // Run examples
    await example1_automatic();
    await new Promise(resolve => setTimeout(resolve, 1000));

    await example2_manual();
    await new Promise(resolve => setTimeout(resolve, 1000));

    await example3_custom_handlers();

    console.log('\n==========================================');
    console.log('✓ All examples completed successfully!');
    console.log('\nNext steps:');
    console.log('  1. Run the interactive demo: ./learning/demo-session-communication.js');
    console.log('  2. Run tests: ./learning/test-session-communication.js');
    console.log('  3. Read the docs: docs/CROSS_SESSION_COMMUNICATION.md');
    console.log('  4. Check quickstart: docs/CROSS_SESSION_QUICKSTART.md');
  } catch (err) {
    console.error('\n✗ Error:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

// Run main
main();
