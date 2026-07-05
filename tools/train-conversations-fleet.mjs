#!/usr/bin/env node
/**
 * Train on Conversations - TRUE Fleet Orchestrator Parallel Execution
 * Uses shared/fleet-ssh-orchestrator.js for actual SSH distribution
 */

import { executeParallel } from '../shared/fleet-ssh-orchestrator.js';
import { getDB } from '../learning/postgres-adapter.js';
import { execSync } from 'child_process';
import { readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';

const HOME = process.env.HOME;

async function main() {
  console.log('='.repeat(60));
  console.log('TRAIN ON CONVERSATIONS - FLEET ORCHESTRATOR');
  console.log('='.repeat(60));

  // Phase 1: Find all conversation files (limit to avoid buffer overflow)
  console.log('\nPhase 1: Finding conversation files...');
  const findCmd = `find ${HOME}/.claude/projects -name "*.jsonl" -type f | head -50`;
  const allFiles = execSync(findCmd, { maxBuffer: 10 * 1024 * 1024 }).toString().trim().split('\n');
  console.log(`✓ Found ${allFiles.length} conversation files (first 50)`);

  // Process all found conversations
  const firstBatch = allFiles;
  console.log(`\nPhase 2: Processing first ${firstBatch.length} conversations IN PARALLEL`);

  // Create tasks for fleet orchestrator
  const tasks = firstBatch.map((file, idx) => ({
    id: `conv-${idx}`,
    prompt: `Extract learnings from conversation JSONL: ${file}

1. Read JSONL file
2. Parse each line
3. Extract user requests (type=user)
4. Extract tool uses (type=assistant, tool_use)
5. Identify patterns

Return JSON:
{
  "file": "${file}",
  "user_requests": ["request 1", "request 2"],
  "tool_uses": ["Bash", "Read", "Edit"],
  "patterns": ["pattern 1", "pattern 2"]
}`
  }));

  console.log(`\nDistributing ${tasks.length} tasks across fleet...`);
  console.log('Workers: server-01, server-02, server-03, laptop-01, pi-01, pi-02, desktop-ap, server-ap');

  // Execute in PARALLEL using fleet orchestrator
  const startTime = Date.now();

  const results = await executeParallel({
    tasks,
    executionId: 'conversation-training-' + Date.now(),
    skipPreValidation: true  // Skip health checks
  });

  const elapsed = (Date.now() - startTime) / 1000;

  console.log(`\n✓ Completed in ${elapsed.toFixed(1)}s`);
  console.log(`  Throughput: ${(tasks.length / elapsed).toFixed(1)} conversations/sec`);

  // Phase 3: Process results
  console.log('\nPhase 3: Processing results...');

  const extractions = results.workers || [];
  const successful = extractions.filter(e => e.status === 'success');

  console.log(`  Successful: ${successful.length}/${extractions.length}`);

  // Aggregate all learnings
  const allRequests = [];
  const allToolUses = [];
  const allPatterns = [];

  successful.forEach(extraction => {
    try {
      const data = JSON.parse(extraction.result);
      if (data.user_requests) allRequests.push(...data.user_requests);
      if (data.tool_uses) allToolUses.push(...data.tool_uses);
      if (data.patterns) allPatterns.push(...data.patterns);
    } catch (err) {
      console.error(`  Warning: Could not parse result from ${extraction.worker}`);
    }
  });

  console.log(`  Total user requests: ${allRequests.length}`);
  console.log(`  Total tool uses: ${allToolUses.length}`);
  console.log(`  Total patterns: ${allPatterns.length}`);

  // Phase 4: Store in PostgreSQL
  console.log('\nPhase 4: Storing in PostgreSQL...');

  const db = getDB();

  // Create table if not exists
  await db.query(`
    CREATE TABLE IF NOT EXISTS learning.conversation_learnings (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      learning_type TEXT NOT NULL,
      content TEXT NOT NULL,
      embedding VECTOR(384),
      source_file TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    )
  `);

  // Insert learnings
  let inserted = 0;

  for (const request of allRequests.slice(0, 100)) {
    await db.query(`
      INSERT INTO learning.conversation_learnings (learning_type, content)
      VALUES ($1, $2)
    `, ['user_request', request]);
    inserted++;
  }

  for (const pattern of allPatterns.slice(0, 100)) {
    await db.query(`
      INSERT INTO learning.conversation_learnings (learning_type, content)
      VALUES ($1, $2)
    `, ['pattern', pattern]);
    inserted++;
  }

  console.log(`✓ Inserted ${inserted} learnings into PostgreSQL`);

  // Create index
  try {
    await db.query(`
      CREATE INDEX IF NOT EXISTS conversation_learnings_type_idx
      ON learning.conversation_learnings (learning_type)
    `);
    console.log('✓ Created index');
  } catch (err) {
    console.log('  Index already exists');
  }

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('TRAINING COMPLETE');
  console.log('='.repeat(60));
  console.log(`Conversations processed: ${successful.length}`);
  console.log(`Learnings extracted: ${allRequests.length + allPatterns.length}`);
  console.log(`Stored in PostgreSQL: ${inserted}`);
  console.log(`Fleet throughput: ${(tasks.length / elapsed).toFixed(1)} conversations/sec`);
  console.log(`\nNext: Process remaining ${allFiles.length - firstBatch.length} conversations`);
  console.log('='.repeat(60));

  process.exit(0);
}

main().catch(err => {
  console.error('FATAL ERROR:', err);
  process.exit(1);
});
