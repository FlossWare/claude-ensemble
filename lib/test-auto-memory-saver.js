#!/usr/bin/env node
/**
 * Test auto-memory-saver.js error handling
 */

const { saveMemory, saveAllMemories } = require('./auto-memory-saver.js');
const fs = require('fs');
const path = require('path');

const TEMP_DIR = '/tmp/memory-saver-test';

// Override MEMORY_DIR for testing
const originalMemoryDir = process.env.MEMORY_DIR;
process.env.MEMORY_DIR = TEMP_DIR;

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✅ ${name}`);
    passed++;
  } catch (err) {
    console.error(`❌ ${name}: ${err.message}`);
    failed++;
  }
}

function cleanup() {
  if (fs.existsSync(TEMP_DIR)) {
    fs.rmSync(TEMP_DIR, { recursive: true, force: true });
  }
}

// Setup
cleanup();

console.log('Running auto-memory-saver tests...\n');

// Test 1: Missing parameters
test('saveMemory with missing parameters should throw', () => {
  try {
    saveMemory('feedback', '', 'desc', 'content');
    throw new Error('Should have thrown');
  } catch (err) {
    if (!err.message.includes('Missing required parameters')) {
      throw err;
    }
  }
});

// Test 2: Valid save
test('saveMemory with valid parameters should succeed', () => {
  const result = saveMemory('feedback', 'test-memory', 'Test description', 'Test content');
  if (!fs.existsSync(result)) {
    throw new Error('File was not created');
  }
});

// Test 3: Invalid learnings object
test('saveAllMemories with invalid input should throw', () => {
  try {
    saveAllMemories(null);
    throw new Error('Should have thrown');
  } catch (err) {
    if (!err.message.includes('Invalid learnings object')) {
      throw err;
    }
  }
});

// Test 4: Valid learnings with some invalid items
test('saveAllMemories should handle partial failures', () => {
  const learnings = {
    feedback: [
      { name: 'valid-1', description: 'Valid item', content: 'Content' },
      { name: 'invalid-1', description: 'Missing content' }, // Missing content
      { name: 'valid-2', description: 'Another valid', content: 'More content' }
    ]
  };

  const saved = saveAllMemories(learnings);

  if (saved.length !== 2) {
    throw new Error(`Expected 2 saved items, got ${saved.length}`);
  }
});

// Test 5: Empty learnings
test('saveAllMemories with empty object should succeed', () => {
  const saved = saveAllMemories({});
  if (saved.length !== 0) {
    throw new Error(`Expected 0 saved items, got ${saved.length}`);
  }
});

// Test 6: Directory creation
test('saveMemory should create directory if missing', () => {
  cleanup();
  const result = saveMemory('project', 'auto-create-test', 'Test', 'Content');
  if (!fs.existsSync(TEMP_DIR)) {
    throw new Error('Directory was not created');
  }
});

// Cleanup
cleanup();
process.env.MEMORY_DIR = originalMemoryDir;

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
