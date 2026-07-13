#!/usr/bin/env node
/**
 * Test Auto Rollback System
 *
 * Demonstrates:
 * - Automatic rollback on verification failure
 * - Git-based rollback
 * - File system rollback
 * - Multiple checkpoint management
 */

const fs = require('fs');
const path = require('path');
const { withRollback, createCheckpoint, rollbackToCheckpoint, RollbackManager } = require('../lib/auto-rollback.js');

const TEST_DIR = path.join(process.cwd(), '.test-rollback');
const TEST_FILE = path.join(TEST_DIR, 'test-file.txt');

// Setup test directory
function setup() {
  if (!fs.existsSync(TEST_DIR)) {
    fs.mkdirSync(TEST_DIR, { recursive: true });
  }
  fs.writeFileSync(TEST_FILE, 'Original content\n', 'utf8');
  console.log('✅ Test setup complete');
}

// Cleanup test directory
function cleanup() {
  if (fs.existsSync(TEST_DIR)) {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  }
  console.log('✅ Test cleanup complete');
}

// Test 1: Basic rollback on error
async function testBasicRollback() {
  console.log('\n=== Test 1: Basic Rollback on Error ===');

  const originalContent = fs.readFileSync(TEST_FILE, 'utf8');

  try {
    await withRollback(async () => {
      // Make changes
      fs.writeFileSync(TEST_FILE, 'Modified content\n', 'utf8');
      console.log('✓ Made changes to file');

      // Simulate verification failure
      throw new Error('Verification failed (simulated)');
    }, {
      files: [TEST_FILE],
      verbose: true
    });
  } catch (err) {
    console.log(`✓ Caught expected error: ${err.message}`);
  }

  const restoredContent = fs.readFileSync(TEST_FILE, 'utf8');

  if (restoredContent === originalContent) {
    console.log('✅ Test 1 PASSED: File restored to original content');
  } else {
    console.error('❌ Test 1 FAILED: File not restored');
    console.error(`  Expected: ${originalContent}`);
    console.error(`  Got: ${restoredContent}`);
  }
}

// Test 2: Successful execution (no rollback)
async function testSuccessfulExecution() {
  console.log('\n=== Test 2: Successful Execution (No Rollback) ===');

  const result = await withRollback(async () => {
    // Make changes
    fs.writeFileSync(TEST_FILE, 'New content\n', 'utf8');
    console.log('✓ Made changes to file');

    return { success: true };
  }, {
    files: [TEST_FILE],
    verbose: true
  });

  const newContent = fs.readFileSync(TEST_FILE, 'utf8');

  if (newContent === 'New content\n' && result.success) {
    console.log('✅ Test 2 PASSED: Changes preserved on success');
  } else {
    console.error('❌ Test 2 FAILED: Changes not preserved');
  }
}

// Test 3: Rollback with verification function
async function testVerificationRollback() {
  console.log('\n=== Test 3: Rollback with Verification Function ===');

  fs.writeFileSync(TEST_FILE, 'Original content\n', 'utf8');
  const originalContent = fs.readFileSync(TEST_FILE, 'utf8');

  try {
    await withRollback(async () => {
      // Make changes
      fs.writeFileSync(TEST_FILE, 'Invalid content\n', 'utf8');
      console.log('✓ Made changes to file');

      return { content: 'Invalid content\n' };
    }, {
      files: [TEST_FILE],
      verify: async (result) => {
        // Verification function that fails
        console.log('✓ Running verification');
        return result.content.includes('Valid'); // Will fail
      },
      verbose: true
    });
  } catch (err) {
    console.log(`✓ Caught expected error: ${err.message}`);
  }

  const restoredContent = fs.readFileSync(TEST_FILE, 'utf8');

  if (restoredContent === originalContent) {
    console.log('✅ Test 3 PASSED: File restored after verification failure');
  } else {
    console.error('❌ Test 3 FAILED: File not restored');
  }
}

// Test 4: Multiple checkpoints
async function testMultipleCheckpoints() {
  console.log('\n=== Test 4: Multiple Checkpoints ===');

  const manager = new RollbackManager({ verbose: true });

  // Create checkpoint 1
  fs.writeFileSync(TEST_FILE, 'State 1\n', 'utf8');
  const checkpoint1 = manager.createCheckpoint({
    description: 'Checkpoint 1',
    files: [TEST_FILE]
  });
  console.log(`✓ Created checkpoint 1: ${checkpoint1}`);

  // Make changes
  fs.writeFileSync(TEST_FILE, 'State 2\n', 'utf8');

  // Create checkpoint 2
  const checkpoint2 = manager.createCheckpoint({
    description: 'Checkpoint 2',
    files: [TEST_FILE]
  });
  console.log(`✓ Created checkpoint 2: ${checkpoint2}`);

  // Make more changes
  fs.writeFileSync(TEST_FILE, 'State 3\n', 'utf8');

  // Rollback to checkpoint 1
  manager.rollbackToCheckpoint(checkpoint1);
  const content1 = fs.readFileSync(TEST_FILE, 'utf8');

  if (content1 === 'State 1\n') {
    console.log('✅ Test 4 PASSED: Rollback to checkpoint 1 successful');
  } else {
    console.error('❌ Test 4 FAILED: Rollback to checkpoint 1 failed');
  }
}

// Test 5: Git rollback (if in git repo)
async function testGitRollback() {
  console.log('\n=== Test 5: Git Rollback ===');

  const manager = new RollbackManager({ verbose: true });

  if (!manager.isGitRepo()) {
    console.log('⚠️  Test 5 SKIPPED: Not in a git repository');
    return;
  }

  try {
    // Create checkpoint with git
    const checkpoint = manager.createCheckpoint({
      description: 'Git rollback test'
    });

    console.log(`✓ Created git checkpoint: ${checkpoint}`);

    // Make some changes
    fs.writeFileSync(TEST_FILE, 'Modified for git test\n', 'utf8');

    // Rollback
    const success = manager.rollbackToCheckpoint(checkpoint);

    if (success) {
      console.log('✅ Test 5 PASSED: Git rollback successful');
    } else {
      console.error('❌ Test 5 FAILED: Git rollback failed');
    }
  } catch (err) {
    console.error(`❌ Test 5 FAILED: ${err.message}`);
  }
}

// Run all tests
async function runAllTests() {
  console.log('Starting Auto Rollback Tests\n');

  setup();

  try {
    await testBasicRollback();
    await testSuccessfulExecution();
    await testVerificationRollback();
    await testMultipleCheckpoints();
    await testGitRollback();

    console.log('\n=== All Tests Complete ===');
  } catch (err) {
    console.error(`\n❌ Test suite failed: ${err.message}`);
  } finally {
    cleanup();
  }
}

// Run tests if executed directly
if (require.main === module) {
  runAllTests().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { runAllTests };
