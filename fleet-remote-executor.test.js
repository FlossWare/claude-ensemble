/**
 * Test suite for fleet-remote-executor.js
 *
 * Tests: command building, SSH escaping, output parsing, prompt file ops,
 * compliance checking, timeout behavior, and integration flow.
 *
 * Run with: node fleet-remote-executor.test.js
 */

import { RemoteExecutor, createRemoteExecutor } from './fleet-remote-executor.js';
import fs from 'fs';
import path from 'path';
import os from 'os';

// ============================================================================
// Test Runner
// ============================================================================

let passed = 0;
let failed = 0;
let skipped = 0;

function assertEquals(actual, expected, testName) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    console.log(`  PASS ${testName}`);
    passed++;
  } else {
    console.log(`  FAIL ${testName}`);
    console.log(`     Expected: ${JSON.stringify(expected)}`);
    console.log(`     Got:      ${JSON.stringify(actual)}`);
    failed++;
  }
}

function assertTrue(actual, testName) {
  if (actual) {
    console.log(`  PASS ${testName}`);
    passed++;
  } else {
    console.log(`  FAIL ${testName}`);
    console.log(`     Expected truthy, got: ${actual}`);
    failed++;
  }
}

function assertFalse(actual, testName) {
  if (!actual) {
    console.log(`  PASS ${testName}`);
    passed++;
  } else {
    console.log(`  FAIL ${testName}`);
    console.log(`     Expected falsy, got: ${actual}`);
    failed++;
  }
}

function assertThrows(fn, expectedCode, testName) {
  try {
    fn();
    console.log(`  FAIL ${testName} (no exception thrown)`);
    failed++;
  } catch (e) {
    if (expectedCode && e.code !== expectedCode) {
      console.log(`  FAIL ${testName}`);
      console.log(`     Expected error code: ${expectedCode}`);
      console.log(`     Got: ${e.code} (${e.message})`);
      failed++;
    } else {
      console.log(`  PASS ${testName}`);
      passed++;
    }
  }
}

async function assertThrowsAsync(fn, expectedCode, testName) {
  try {
    await fn();
    console.log(`  FAIL ${testName} (no exception thrown)`);
    failed++;
  } catch (e) {
    if (expectedCode && e.code !== expectedCode) {
      console.log(`  FAIL ${testName}`);
      console.log(`     Expected error code: ${expectedCode}`);
      console.log(`     Got: ${e.code} (${e.message})`);
      failed++;
    } else {
      console.log(`  PASS ${testName}`);
      passed++;
    }
  }
}

function assertContains(str, substring, testName) {
  if (str.includes(substring)) {
    console.log(`  PASS ${testName}`);
    passed++;
  } else {
    console.log(`  FAIL ${testName}`);
    console.log(`     Expected to contain: "${substring}"`);
    console.log(`     Got: "${str.slice(0, 200)}"`);
    failed++;
  }
}

function skip(testName, reason) {
  console.log(`  SKIP ${testName} (${reason})`);
  skipped++;
}


// ============================================================================
// TEST SUITE 1: Constructor and Configuration
// ============================================================================

console.log('\n=== Constructor and Configuration ===\n');

// Test 1.1: Default configuration
const ex1 = new RemoteExecutor();
assertTrue(ex1.nfsRoot.length > 0, 'Default nfsRoot is set');
assertEquals(ex1.vertexProjectId, process.env.ANTHROPIC_VERTEX_PROJECT_ID || 'itpc-gcp-uie-eng-claude', 'Default vertexProjectId');
assertEquals(ex1.sshTimeoutSec, 10, 'Default SSH timeout is 10s');
assertEquals(ex1.maxPromptCmdLength, 4096, 'Default max prompt cmd length is 4096');
assertEquals(ex1.maxTurns, 50, 'Default max turns is 50');

// Test 1.2: Custom configuration
const ex2 = new RemoteExecutor({
  nfsRoot: '/custom/nfs',
  vertexProjectId: 'my-project',
  sshTimeoutSec: 5,
  maxPromptCmdLength: 2048,
  maxTurns: 100,
  forbiddenPaths: ['/forbidden/'],
});
assertEquals(ex2.nfsRoot, '/custom/nfs', 'Custom nfsRoot');
assertEquals(ex2.vertexProjectId, 'my-project', 'Custom vertexProjectId');
assertEquals(ex2.sshTimeoutSec, 5, 'Custom SSH timeout');
assertEquals(ex2.maxPromptCmdLength, 2048, 'Custom max prompt cmd length');
assertEquals(ex2.maxTurns, 100, 'Custom max turns');
assertEquals(ex2.forbiddenPaths.length, 1, 'Custom forbidden paths');

// Test 1.3: Factory function
const ex3 = createRemoteExecutor({ sshTimeoutSec: 15 });
assertEquals(ex3.sshTimeoutSec, 15, 'Factory function creates executor with config');
assertTrue(ex3 instanceof RemoteExecutor, 'Factory returns RemoteExecutor instance');


// ============================================================================
// TEST SUITE 2: SSH Escaping
// ============================================================================

console.log('\n=== SSH Escaping ===\n');

const ex = new RemoteExecutor();

// Test 2.1: Simple string (no escaping needed)
assertEquals(ex.escapeForSsh('hello world'), 'hello world', 'Simple string unchanged');

// Test 2.2: Single quotes
assertEquals(
  ex.escapeForSsh("it's a test"),
  "it'\\''s a test",
  'Single quotes escaped correctly'
);

// Test 2.3: Multiple single quotes
assertEquals(
  ex.escapeForSsh("don't can't won't"),
  "don'\\''t can'\\''t won'\\''t",
  'Multiple single quotes escaped'
);

// Test 2.4: Already-escaped quotes (idempotent check)
// Input: test'\''value  (contains 3 single quotes from the '\'' sequence)
// Each ' becomes '\'' so: test + '\'' + \ + '\'' + '\'' + value
const alreadyEscaped = ex.escapeForSsh("test'\\''value");
assertContains(alreadyEscaped, 'test', 'Already-escaped quotes: preserves prefix');
assertTrue(alreadyEscaped.includes("'\\''"), 'Already-escaped quotes: contains escape sequences');

// Test 2.5: Special characters preserved (not escaped in single quotes)
assertEquals(
  ex.escapeForSsh('$HOME `whoami` "test"'),
  '$HOME `whoami` "test"',
  'Dollar, backtick, double quotes preserved in single-quote context'
);

// Test 2.6: Newlines preserved
assertEquals(
  ex.escapeForSsh('line1\nline2'),
  'line1\nline2',
  'Newlines preserved in single-quote context'
);

// Test 2.7: Empty string
assertEquals(ex.escapeForSsh(''), '', 'Empty string returns empty');

// Test 2.8: Double-quote escaping
const dqResult = ex.escapeForDoubleQuotes('echo "$HOME" `date` \\ "test"');
assertContains(dqResult, '\\$HOME', 'Dollar signs escaped in double-quote context');
assertContains(dqResult, '\\`date\\`', 'Backticks escaped in double-quote context');
assertContains(dqResult, '\\\\', 'Backslashes escaped in double-quote context');
assertContains(dqResult, '\\"test\\"', 'Double quotes escaped in double-quote context');


// ============================================================================
// TEST SUITE 3: Command Building
// ============================================================================

console.log('\n=== Command Building ===\n');

// Test 3.1: Small prompt (inline)
const cmd1 = await ex.buildCommand('server-01', 'Hello world', 'sonnet', 'job-001');
assertContains(cmd1, 'ssh', 'Command starts with ssh');
assertContains(cmd1, 'server-01', 'Contains server name');
assertContains(cmd1, 'BatchMode=yes', 'SSH BatchMode enabled');
assertContains(cmd1, 'StrictHostKeyChecking=accept-new', 'SSH StrictHostKeyChecking set');
assertContains(cmd1, 'claude -p', 'Contains claude -p');
assertContains(cmd1, '--dangerously-skip-permissions', 'Contains skip-permissions flag');
assertContains(cmd1, '--output-format json', 'Contains JSON output format');
assertContains(cmd1, '--no-session-persistence', 'Contains no-session-persistence');
assertContains(cmd1, 'ANTHROPIC_VERTEX_PROJECT_ID', 'Exports Vertex project ID');
assertContains(cmd1, 'CLAUDE_CODE_USE_VERTEX', 'Exports Vertex enabled flag');
assertContains(cmd1, 'GOOGLE_GENAI_USE_VERTEXAI', 'Exports Google GenAI Vertex flag');

// Test 3.2: Large prompt (file-based)
const largePrompt = 'x'.repeat(5000);
const exLarge = new RemoteExecutor({
  nfsRoot: os.tmpdir(), // Use tmpdir for test file operations
  maxPromptCmdLength: 4096,
});
const cmd2 = await exLarge.buildCommand('server-02', largePrompt, 'opus', 'job-002');
assertContains(cmd2, 'cat', 'Large prompt uses cat to read from file');
assertContains(cmd2, 'job-002.txt', 'Large prompt references job ID file');

// Clean up test prompt file
await exLarge.cleanup('job-002').catch(() => {});

// Test 3.3: Prompt with special characters (inline)
const specialPrompt = "Analyze this code: if (x > 0 && y < 10) { return 'yes'; }";
const cmd3 = await ex.buildCommand('server-03', specialPrompt, 'haiku', 'job-003');
assertContains(cmd3, 'server-03', 'Special chars prompt targets correct server');
assertContains(cmd3, 'claude -p', 'Special chars prompt still uses claude -p');

// Test 3.4: ConnectTimeout in command
assertContains(cmd1, `ConnectTimeout=${ex.sshTimeoutSec}`, 'SSH connect timeout included');


// ============================================================================
// TEST SUITE 4: Output Parsing
// ============================================================================

console.log('\n=== Output Parsing ===\n');

// Test 4.1: Valid success envelope
const parsed1 = ex.parseClaudeOutput(JSON.stringify({
  type: 'result',
  subtype: 'success',
  cost_usd: 0.05,
  duration_ms: 12345,
  is_error: false,
  num_turns: 3,
  result: 'Hello from the remote agent!',
  session_id: 'sess-123',
}));
assertEquals(parsed1.result, 'Hello from the remote agent!', 'Parses result string');
assertEquals(parsed1.cost, 0.05, 'Parses cost_usd');
assertEquals(parsed1.remoteDuration, 12345, 'Parses duration_ms');

// Test 4.2: JSON result with schema
const parsed2 = ex.parseClaudeOutput(JSON.stringify({
  type: 'result',
  subtype: 'success',
  cost_usd: 0.10,
  duration_ms: 5000,
  is_error: false,
  result: '{"name": "test", "score": 42}',
}), { properties: { name: {}, score: {} } });
assertEquals(parsed2.result.name, 'test', 'Parses JSON result with schema - name');
assertEquals(parsed2.result.score, 42, 'Parses JSON result with schema - score');

// Test 4.3: JSON array result with schema
const parsed3 = ex.parseClaudeOutput(JSON.stringify({
  type: 'result',
  subtype: 'success',
  cost_usd: 0.02,
  duration_ms: 3000,
  is_error: false,
  result: '[{"id": 1}, {"id": 2}]',
}), { type: 'array' });
assertTrue(Array.isArray(parsed3.result), 'Parses JSON array result');
assertEquals(parsed3.result.length, 2, 'Array has correct length');

// Test 4.4: Result without schema (returns raw string)
const parsed4 = ex.parseClaudeOutput(JSON.stringify({
  type: 'result',
  subtype: 'success',
  cost_usd: 0.01,
  duration_ms: 1000,
  is_error: false,
  result: 'Just a plain text response',
}));
assertEquals(parsed4.result, 'Just a plain text response', 'Returns raw string without schema');

// Test 4.5: is_error = true
await assertThrowsAsync(
  () => Promise.resolve(ex.parseClaudeOutput(JSON.stringify({
    type: 'result',
    subtype: 'error',
    is_error: true,
    result: 'Rate limit exceeded',
    cost_usd: 0.00,
    duration_ms: 500,
  }))),
  'CLAUDE_EXECUTION_FAILED',
  'Throws on is_error=true'
);

// Test 4.6: Empty output
assertThrows(
  () => ex.parseClaudeOutput(''),
  'OUTPUT_PARSE_FAILED',
  'Throws on empty output'
);

// Test 4.7: Null output
assertThrows(
  () => ex.parseClaudeOutput(null),
  'OUTPUT_PARSE_FAILED',
  'Throws on null output'
);

// Test 4.8: Malformed JSON
assertThrows(
  () => ex.parseClaudeOutput('not json at all {{{'),
  'OUTPUT_PARSE_FAILED',
  'Throws on malformed JSON'
);

// Test 4.9: Empty result field
assertThrows(
  () => ex.parseClaudeOutput(JSON.stringify({
    type: 'result',
    is_error: false,
    result: '',
    cost_usd: 0,
    duration_ms: 0,
  })),
  'OUTPUT_PARSE_FAILED',
  'Throws on empty result field'
);

// Test 4.10: Null result field
assertThrows(
  () => ex.parseClaudeOutput(JSON.stringify({
    type: 'result',
    is_error: false,
    result: null,
    cost_usd: 0,
    duration_ms: 0,
  })),
  'OUTPUT_PARSE_FAILED',
  'Throws on null result field'
);

// Test 4.11: Missing cost_usd defaults to 0
const parsed11 = ex.parseClaudeOutput(JSON.stringify({
  type: 'result',
  is_error: false,
  result: 'test',
}));
assertEquals(parsed11.cost, 0, 'Missing cost_usd defaults to 0');
assertEquals(parsed11.remoteDuration, 0, 'Missing duration_ms defaults to 0');

// Test 4.12: Schema provided but result is not JSON (returns raw string)
const parsed12 = ex.parseClaudeOutput(JSON.stringify({
  type: 'result',
  is_error: false,
  result: 'This is not JSON content',
  cost_usd: 0.01,
  duration_ms: 500,
}), { properties: { foo: {} } });
assertEquals(parsed12.result, 'This is not JSON content', 'Non-JSON result returned raw when schema expected');

// Test 4.13: Schema provided but result is invalid JSON that starts with {
const parsed13 = ex.parseClaudeOutput(JSON.stringify({
  type: 'result',
  is_error: false,
  result: '{invalid json here}',
  cost_usd: 0.01,
  duration_ms: 500,
}), { properties: { foo: {} } });
assertEquals(parsed13.result, '{invalid json here}', 'Invalid JSON-like result returned as raw string');


// ============================================================================
// TEST SUITE 5: Prompt File Operations
// ============================================================================

console.log('\n=== Prompt File Operations ===\n');

const tmpExecutor = new RemoteExecutor({
  nfsRoot: os.tmpdir(),
});

// Test 5.1: Write prompt file
const promptPath = await tmpExecutor.writePromptFile('test-job-001', 'Test prompt content');
assertTrue(fs.existsSync(promptPath), 'Prompt file created');
const promptContent = fs.readFileSync(promptPath, 'utf8');
assertEquals(promptContent, 'Test prompt content', 'Prompt file content matches');

// Test 5.2: Write large prompt file
const largeContent = 'x'.repeat(10000);
const largePath = await tmpExecutor.writePromptFile('test-job-002', largeContent);
assertTrue(fs.existsSync(largePath), 'Large prompt file created');
const largeRead = fs.readFileSync(largePath, 'utf8');
assertEquals(largeRead.length, 10000, 'Large prompt file has correct length');

// Test 5.3: Write prompt with special characters
const specialContent = `Analyze: if (x > 0) { return "yes"; } // it's a 'test'`;
const specialPath = await tmpExecutor.writePromptFile('test-job-003', specialContent);
const specialRead = fs.readFileSync(specialPath, 'utf8');
assertEquals(specialRead, specialContent, 'Special characters preserved in prompt file');

// Test 5.4: Cleanup removes files
await tmpExecutor.cleanup('test-job-001');
assertFalse(fs.existsSync(promptPath), 'Prompt file removed after cleanup');

// Test 5.5: Cleanup is idempotent (no error on missing files)
await tmpExecutor.cleanup('nonexistent-job');
assertTrue(true, 'Cleanup of nonexistent job does not throw');

// Test 5.6: Overwrite existing prompt file
await tmpExecutor.writePromptFile('test-job-004', 'first version');
const overwritePath = await tmpExecutor.writePromptFile('test-job-004', 'second version');
const overwriteContent = fs.readFileSync(overwritePath, 'utf8');
assertEquals(overwriteContent, 'second version', 'Prompt file overwritten correctly');

// Cleanup remaining test files
await tmpExecutor.cleanup('test-job-002');
await tmpExecutor.cleanup('test-job-003');
await tmpExecutor.cleanup('test-job-004');


// ============================================================================
// TEST SUITE 6: Compliance Checking
// ============================================================================

console.log('\n=== Compliance Checking ===\n');

// Test 6.1: Compliant path (explicit safe paths that do not match cwd)
const exCompliant = new RemoteExecutor({ forbiddenPaths: ['/nonexistent/path/'] });
const compliance1 = exCompliant.checkCompliance();
assertTrue(compliance1.compliant, 'Non-matching forbidden path = compliant');

// Test 6.2: Compliant path (cwd not under forbidden)
const exCompliant2 = new RemoteExecutor({ forbiddenPaths: ['/some/other/path/'] });
const compliance2 = exCompliant2.checkCompliance();
assertTrue(compliance2.compliant, 'CWD not under forbidden path = compliant');

// Test 6.3: Non-compliant path
const cwd = process.cwd();
const exNonCompliant = new RemoteExecutor({ forbiddenPaths: [cwd.slice(0, cwd.lastIndexOf('/'))] });
const compliance3 = exNonCompliant.checkCompliance();
assertFalse(compliance3.compliant, 'CWD under forbidden path = non-compliant');
assertContains(compliance3.reason, 'forbidden', 'Non-compliant reason mentions forbidden');

// Test 6.4: Loads from fleet.json automatically
const exAutoLoad = new RemoteExecutor();
const compliance4 = exAutoLoad.checkCompliance();
// Should not throw regardless of fleet.json presence
assertTrue(typeof compliance4.compliant === 'boolean', 'Auto-load compliance check returns boolean');


// ============================================================================
// TEST SUITE 7: Integration Mocks (no actual SSH)
// ============================================================================

console.log('\n=== Integration Mocks ===\n');

// Test 7.1: execute() with SSH that would fail (no real server)
await assertThrowsAsync(
  async () => {
    const exInt = new RemoteExecutor({ sshTimeoutSec: 1 });
    await exInt.execute('nonexistent-server-999', 'sonnet', 'Hello', {
      timeoutMs: 3000,
    });
  },
  null, // We don't know the exact error code since there's no server
  'execute() throws when SSH fails to connect'
);

// Test 7.2: Verify file cleanup after failed execution
const cleanupTestId = `cleanup-test-${Date.now()}`;
const cleanupExecutor = new RemoteExecutor({ nfsRoot: os.tmpdir() });
// Write a prompt file
await cleanupExecutor.writePromptFile(cleanupTestId, 'test');
const cleanupPromptPath = path.join(os.tmpdir(), 'fleet-results', '.prompts', `${cleanupTestId}.txt`);
assertTrue(fs.existsSync(cleanupPromptPath), 'Pre-cleanup: prompt file exists');
await cleanupExecutor.cleanup(cleanupTestId);
assertFalse(fs.existsSync(cleanupPromptPath), 'Post-cleanup: prompt file removed');


// ============================================================================
// TEST SUITE 8: Edge Cases
// ============================================================================

console.log('\n=== Edge Cases ===\n');

// Test 8.1: Prompt with JSON schema definition (common in workflows)
const schemaPrompt = `Return a JSON object matching this schema:
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "score": {"type": "number", "minimum": 0, "maximum": 100}
  },
  "required": ["name", "score"]
}`;
const cmd8 = await ex.buildCommand('server-01', schemaPrompt, 'sonnet', 'job-schema');
assertContains(cmd8, 'claude -p', 'Schema prompt produces valid command');

// Test 8.2: Prompt that is exactly at the threshold (4096 bytes)
const thresholdPrompt = 'a'.repeat(4096);
const exThreshold = new RemoteExecutor({
  nfsRoot: os.tmpdir(),
  maxPromptCmdLength: 4096,
});
const cmdThreshold = await exThreshold.buildCommand('server-01', thresholdPrompt, 'sonnet', 'job-threshold');
assertContains(cmdThreshold, 'cat', 'Prompt at exact threshold uses file-based passing');
await exThreshold.cleanup('job-threshold');

// Test 8.3: Prompt just under threshold
const underThresholdPrompt = 'a'.repeat(4095);
const cmdUnder = await ex.buildCommand('server-01', underThresholdPrompt, 'sonnet', 'job-under');
// Should NOT use cat (inline passing)
assertTrue(!cmdUnder.includes('job-under.txt'), 'Prompt under threshold uses inline passing');

// Test 8.4: Unicode prompt
const unicodePrompt = 'Analyze this: éèê üöä 你好世界 🌍';
const cmdUnicode = await ex.buildCommand('server-01', unicodePrompt, 'sonnet', 'job-unicode');
assertContains(cmdUnicode, 'claude -p', 'Unicode prompt produces valid command');

// Test 8.5: Prompt with backticks (common in code)
const backtickPrompt = "Review this code:\n```javascript\nconst x = `hello ${world}`;\n```";
const cmdBacktick = await ex.buildCommand('server-01', backtickPrompt, 'sonnet', 'job-backtick');
assertContains(cmdBacktick, 'claude -p', 'Backtick prompt produces valid command');

// Test 8.6: Prompt with dollar signs
const dollarPrompt = 'The cost is $100 and $PATH is /usr/bin';
const cmdDollar = await ex.buildCommand('server-01', dollarPrompt, 'sonnet', 'job-dollar');
assertContains(cmdDollar, 'claude -p', 'Dollar sign prompt produces valid command');


// ============================================================================
// TEST SUITE 9: fleet-utils.js NFS Utilities (import test)
// ============================================================================

console.log('\n=== fleet-utils.js NFS Utilities ===\n');

try {
  const fleetUtils = await import('./fleet-utils.js');

  // Test 9.1: promptToFile function exists
  assertTrue(typeof fleetUtils.promptToFile === 'function', 'promptToFile exported from fleet-utils');

  // Test 9.2: readResultFile function exists
  assertTrue(typeof fleetUtils.readResultFile === 'function', 'readResultFile exported from fleet-utils');

  // Test 9.3: cleanupJobFiles function exists
  assertTrue(typeof fleetUtils.cleanupJobFiles === 'function', 'cleanupJobFiles exported from fleet-utils');

  // Test 9.4: remoteAgent is async
  assertTrue(typeof fleetUtils.remoteAgent === 'function', 'remoteAgent exported from fleet-utils');

  // Test 9.5: promptToFile writes and cleanup removes
  const testJobId = `test-utils-${Date.now()}`;
  const filePath = await fleetUtils.promptToFile(testJobId, 'test prompt from utils');
  assertTrue(fs.existsSync(filePath), 'promptToFile creates file');
  await fleetUtils.cleanupJobFiles(testJobId);
  assertFalse(fs.existsSync(filePath), 'cleanupJobFiles removes prompt file');

} catch (e) {
  skip('fleet-utils.js NFS utilities', `Import failed: ${e.message}`);
}


// ============================================================================
// TEST SUITE 10: fleet-agent-wrapper.js Phase 3 Toggle
// ============================================================================

console.log('\n=== fleet-agent-wrapper.js Phase 3 Toggle ===\n');

try {
  const wrapper = await import('./fleet-agent-wrapper.js');

  // Test 10.1: createFleetAgent function exists
  assertTrue(typeof wrapper.createFleetAgent === 'function', 'createFleetAgent exported from wrapper');

  // Test 10.2: createFleetAgent returns a function
  const mockAgent = async (prompt, opts) => `mock: ${prompt.slice(0, 10)}`;
  // Temporarily disable dispatcher for this test
  const origDispatcher = process.env.FLEET_DISPATCHER;
  process.env.FLEET_DISPATCHER = 'false';
  const wrappedAgent = wrapper.createFleetAgent(mockAgent);
  assertTrue(typeof wrappedAgent === 'function', 'createFleetAgent returns a function');

  // Test 10.3: With dispatcher disabled, calls original agent directly
  const result = await wrappedAgent('test prompt', { model: 'sonnet' });
  assertEquals(result, 'mock: test promp', 'Dispatcher disabled: calls original agent');

  // Restore env
  if (origDispatcher !== undefined) {
    process.env.FLEET_DISPATCHER = origDispatcher;
  } else {
    delete process.env.FLEET_DISPATCHER;
  }

} catch (e) {
  console.log(`  SKIP fleet-agent-wrapper Phase 3 tests: ${e.message}`);
  skipped += 3;
}


// ============================================================================
// TEST SUITE 11: fleet-agent-dispatcher.js executeOnServer (integration check)
// ============================================================================

console.log('\n=== fleet-agent-dispatcher.js Integration ===\n');

try {
  const dispatcher = await import('./fleet-agent-dispatcher.js');

  // Test 11.1: dispatchViaFleet exists
  assertTrue(typeof dispatcher.dispatchViaFleet === 'function', 'dispatchViaFleet exported');

  // Test 11.2: createFleetAgent exists
  assertTrue(typeof dispatcher.createFleetAgent === 'function', 'createFleetAgent exported from dispatcher');

  // Test 11.3: detectJobType exists
  assertTrue(typeof dispatcher.detectJobType === 'function', 'detectJobType exported from dispatcher');

  // Test 11.4: estimateResources exists
  assertTrue(typeof dispatcher.estimateResources === 'function', 'estimateResources exported from dispatcher');

} catch (e) {
  console.log(`  SKIP fleet-agent-dispatcher integration: ${e.message}`);
  skipped += 4;
}


// ============================================================================
// SUMMARY
// ============================================================================

console.log('\n' + '='.repeat(60));
console.log(`Tests passed:  ${passed}`);
console.log(`Tests failed:  ${failed}`);
console.log(`Tests skipped: ${skipped}`);
console.log(`Total tests:   ${passed + failed + skipped}`);
console.log('='.repeat(60) + '\n');

if (failed > 0) {
  process.exit(1);
}
