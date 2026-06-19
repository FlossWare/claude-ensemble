#!/usr/bin/env node

/**
 * Test script for workflow history migration
 *
 * Creates sample session files and runs migration to verify functionality
 */

import { mkdirSync, writeFileSync, rmSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { execSync } from 'child_process';

const TEST_DIR = join(homedir(), '.claude', 'learning', 'test-sessions');

// Create test directory
mkdirSync(TEST_DIR, { recursive: true });

// Sample session 1: Successful deep research
const session1 = {
  id: 'test_research_2026-06-19T10-00-00_abc123',
  query: 'Neural network architectures: Transformer variants and attention mechanisms',
  started: '2026-06-19T10:00:00.000Z',
  completed: '2026-06-19T10:15:00.000Z',
  phases: {
    scope: {
      status: 'completed',
      angles: [
        'Transformer architecture variants',
        'Attention mechanisms comparison',
        'Flash Attention implementation',
        'Performer and linear attention',
        'Multi-query attention strategies'
      ]
    },
    search: {
      status: 'completed',
      results: [
        { angle: 'Transformer architecture variants', urls: ['https://arxiv.org/1', 'https://arxiv.org/2'] },
        { angle: 'Attention mechanisms comparison', urls: ['https://arxiv.org/3', 'https://arxiv.org/4'] },
        { angle: 'Flash Attention implementation', urls: ['https://arxiv.org/5', 'https://arxiv.org/6'] },
        { angle: 'Performer and linear attention', urls: ['https://arxiv.org/7', 'https://arxiv.org/8'] },
        { angle: 'Multi-query attention strategies', urls: ['https://arxiv.org/9', 'https://arxiv.org/10'] }
      ]
    },
    fetch: {
      status: 'completed',
      sources: [
        { url: 'https://arxiv.org/1', title: 'GQA Paper', claims: ['GQA reduces KV cache 4x', 'MQA reduces cache 32x'] },
        { url: 'https://arxiv.org/2', title: 'Flash Attention', claims: ['Flash Attention is 3x faster', 'Memory usage reduced'] },
        { url: 'https://arxiv.org/3', title: 'Performer', claims: ['Performer uses FAVOR+ kernel', 'O(n) complexity'] }
      ]
    },
    verify: {
      status: 'completed',
      claims: [
        { claim: 'GQA reduces KV cache 4x', source: 'https://arxiv.org/1', accepted: true, confidence: 0.95 },
        { claim: 'MQA reduces cache 32x', source: 'https://arxiv.org/1', accepted: true, confidence: 0.92 },
        { claim: 'Flash Attention is 3x faster', source: 'https://arxiv.org/2', accepted: true, confidence: 0.88 },
        { claim: 'Memory usage reduced', source: 'https://arxiv.org/2', accepted: true, confidence: 0.85 },
        { claim: 'Performer uses FAVOR+ kernel', source: 'https://arxiv.org/3', accepted: true, confidence: 0.90 },
        { claim: 'O(n) complexity', source: 'https://arxiv.org/3', accepted: false, confidence: 0.45 }
      ]
    },
    synthesize: {
      status: 'completed',
      report: 'Research findings on transformer architectures...'
    }
  }
};

// Sample session 2: Failed research (verify phase failed)
const session2 = {
  id: 'test_research_2026-06-19T11-00-00_def456',
  query: 'Consciousness theory implementations in AI',
  started: '2026-06-19T11:00:00.000Z',
  failed: '2026-06-19T11:05:00.000Z',
  error: 'Agent failed: verification timeout',
  phases: {
    scope: {
      status: 'completed',
      angles: [
        'Integrated Information Theory',
        'Global Neuronal Workspace',
        'Recurrent Processing Theory'
      ]
    },
    search: {
      status: 'completed',
      results: [
        { angle: 'Integrated Information Theory', urls: ['https://example.com/1'] }
      ]
    },
    fetch: {
      status: 'completed',
      sources: [
        { url: 'https://example.com/1', title: 'IIT Paper', claims: ['Phi measures consciousness'] }
      ]
    },
    verify: {
      status: 'failed',
      error: 'verification timeout',
      claims: []
    },
    synthesize: {
      status: 'pending',
      report: ''
    }
  }
};

// Sample session 3: Partial completion (stopped at fetch)
const session3 = {
  id: 'test_research_2026-06-19T12-00-00_ghi789',
  query: 'Fine-tuning strategies for LLMs',
  started: '2026-06-19T12:00:00.000Z',
  phases: {
    scope: {
      status: 'completed',
      angles: ['LoRA', 'QLoRA', 'DoRA', 'QDoRA']
    },
    search: {
      status: 'completed',
      results: [
        { angle: 'LoRA', urls: ['https://arxiv.org/lora'] }
      ]
    },
    fetch: {
      status: 'running',
      sources: []
    },
    verify: {
      status: 'pending',
      claims: []
    },
    synthesize: {
      status: 'pending',
      report: ''
    }
  }
};

// Write test sessions
writeFileSync(join(TEST_DIR, 'session1.json'), JSON.stringify(session1, null, 2));
writeFileSync(join(TEST_DIR, 'session2.json'), JSON.stringify(session2, null, 2));
writeFileSync(join(TEST_DIR, 'session3.json'), JSON.stringify(session3, null, 2));

console.log('Test sessions created:');
console.log(`  - ${TEST_DIR}/session1.json (successful)`);
console.log(`  - ${TEST_DIR}/session2.json (failed)`);
console.log(`  - ${TEST_DIR}/session3.json (partial)`);

// Run migration in dry-run mode
console.log('\n=== Running migration (dry-run) ===\n');
try {
  execSync(
    `node /home/sfloess/.claude/learning/scripts/migrate-workflow-history.js --dry-run --session-dir ${TEST_DIR}`,
    { stdio: 'inherit' }
  );
} catch (err) {
  console.error('Migration test failed:', err.message);
  process.exit(1);
}

console.log('\n=== Test complete ===');
console.log(`Test directory: ${TEST_DIR}`);
console.log('To clean up: rm -rf ' + TEST_DIR);
