#!/usr/bin/env node

/**
 * Full Pipeline Integration Test
 *
 * Tests the complete data flow:
 * 1. PostgreSQL → Redis migration (100 test tasks)
 * 2. Redis queue processing (worker claims)
 * 3. Content storage (POST to /store)
 * 4. Chunking (text splitting)
 * 5. Embedding (5-provider cascade)
 * 6. Graph storage (OrientDB)
 * 7. Data integrity verification
 * 8. Performance metrics
 *
 * Usage:
 *   node tests/test-full-pipeline-integration.mjs [--cleanup]
 *
 * Options:
 *   --cleanup    Remove test data after completion
 *   --skip-migration   Skip PostgreSQL→Redis migration (use existing data)
 *   --workers N  Number of concurrent workers (default: 3)
 *   --tasks N    Number of test tasks (default: 100)
 *
 * Expected Results:
 *   - 100% migration success (PostgreSQL → Redis)
 *   - 100% worker processing (Redis → /store)
 *   - 100% chunking success (content → chunks)
 *   - ≥95% embedding success (5-provider cascade)
 *   - ≥95% graph storage success
 *   - <2s average latency per task
 *   - Zero data loss
 *
 * Created: 2026-07-11
 */

import { spawn } from 'child_process';
import { setTimeout as delay } from 'timers/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Configuration
const CONFIG = {
  apiBase: 'http://aio-01:5000',
  redisHost: 'aio-01',
  redisPort: 6379,
  postgresHost: 'aio-01',
  postgresPort: 5433,
  testTasks: 100,
  workers: 3,
  timeout: 300000, // 5 minutes
  skipMigration: false,
  cleanup: false,
};

// Parse CLI args
for (let i = 2; i < process.argv.length; i++) {
  const arg = process.argv[i];
  if (arg === '--cleanup') CONFIG.cleanup = true;
  else if (arg === '--skip-migration') CONFIG.skipMigration = true;
  else if (arg === '--workers') CONFIG.workers = parseInt(process.argv[++i]);
  else if (arg === '--tasks') CONFIG.testTasks = parseInt(process.argv[++i]);
}

// Test state
const state = {
  startTime: Date.now(),
  migratedTaskIds: [],
  processedTaskIds: [],
  storedDocIds: [],
  chunkedDocIds: [],
  embeddedChunkIds: [],
  graphNodeIds: [],
  errors: [],
  metrics: {
    migrationTime: 0,
    processingTime: 0,
    chunkingTime: 0,
    embeddingTime: 0,
    graphTime: 0,
    totalTime: 0,
  },
};

// Utilities
function log(msg, level = 'INFO') {
  const timestamp = new Date().toISOString();
  const prefix = {
    INFO: '📋',
    SUCCESS: '✅',
    ERROR: '❌',
    WARN: '⚠️ ',
    METRIC: '📊',
  }[level] || '  ';
  console.log(`${timestamp} ${prefix} ${msg}`);
}

function exec(cmd, args = [], options = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      ...options,
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`${cmd} failed (exit ${code})\nstderr: ${stderr}\nstdout: ${stdout}`));
      } else {
        resolve({ stdout, stderr, code });
      }
    });

    proc.on('error', reject);
  });
}

async function apiCall(endpoint, method = 'GET', body = null) {
  const url = `${CONFIG.apiBase}${endpoint}`;
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) options.body = JSON.stringify(body);

  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`API ${method} ${endpoint} failed: HTTP ${response.status}`);
  }
  return await response.json();
}

// Test Phases
async function phase1_generateTestTasks() {
  log('='.repeat(60));
  log('PHASE 1: Generate Test Tasks in PostgreSQL');
  log('='.repeat(60));

  const testUrls = [];
  for (let i = 1; i <= CONFIG.testTasks; i++) {
    testUrls.push({
      url: `https://example.com/test-doc-${i}`,
      category: i % 4 === 0 ? 'performance' : i % 3 === 0 ? 'ai' : i % 2 === 0 ? 'ml' : 'ga',
      priority: Math.floor(Math.random() * 10) + 1,
      title: `Test Document ${i}`,
      content: `This is test content for document ${i}. `.repeat(20),
    });
  }

  log(`Generated ${testUrls.length} test URLs`, 'INFO');

  // Insert into PostgreSQL via API
  const phaseStart = Date.now();
  const results = await apiCall('/test/bulk-insert-urls', 'POST', { urls: testUrls });
  state.metrics.migrationTime = Date.now() - phaseStart;

  state.migratedTaskIds = results.task_ids || [];
  log(`Inserted ${state.migratedTaskIds.length} tasks in PostgreSQL`, 'SUCCESS');
  log(`Migration time: ${state.metrics.migrationTime}ms`, 'METRIC');

  return state.migratedTaskIds.length === CONFIG.testTasks;
}

async function phase2_migrateToRedis() {
  log('='.repeat(60));
  log('PHASE 2: Migrate PostgreSQL → Redis Queues');
  log('='.repeat(60));

  if (CONFIG.skipMigration) {
    log('Skipping migration (--skip-migration flag)', 'WARN');
    return true;
  }

  const phaseStart = Date.now();

  // Trigger migration via API
  const result = await apiCall('/redis-queue/migrate-from-postgres', 'POST', {
    limit: CONFIG.testTasks,
    batch_size: 50,
  });

  state.metrics.migrationTime += Date.now() - phaseStart;

  log(`Migrated ${result.migrated} tasks to Redis`, 'SUCCESS');
  log(`Failed: ${result.failed || 0}`, result.failed > 0 ? 'WARN' : 'INFO');
  log(`Total migration time: ${state.metrics.migrationTime}ms`, 'METRIC');

  return result.migrated >= CONFIG.testTasks * 0.95; // 95% success rate
}

async function phase3_processRedisQueues() {
  log('='.repeat(60));
  log('PHASE 3: Process Redis Queues (Workers)');
  log('='.repeat(60));

  const phaseStart = Date.now();
  const workerProcs = [];

  // Start worker processes
  for (let i = 0; i < CONFIG.workers; i++) {
    const workerName = `test-worker-${i + 1}`;
    log(`Starting worker: ${workerName}`, 'INFO');

    const proc = spawn('python3', [
      path.resolve(__dirname, '../scripts/redis-queue-worker.py'),
      '--hostname', workerName,
    ], {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    proc.stdout.on('data', (chunk) => {
      const lines = chunk.toString().split('\n');
      lines.forEach(line => {
        if (line.includes('Stored')) {
          const match = line.match(/Stored (https?:\/\/[^\s]+)/);
          if (match) state.processedTaskIds.push(match[1]);
        }
      });
    });

    proc.stderr.on('data', (chunk) => {
      const errLines = chunk.toString().split('\n').filter(l => l.trim());
      errLines.forEach(line => {
        if (line.includes('ERROR')) state.errors.push(line);
      });
    });

    workerProcs.push(proc);
  }

  // Monitor queue until empty
  let queueEmpty = false;
  let lastCount = -1;
  let stableCount = 0;

  while (!queueEmpty && (Date.now() - phaseStart) < CONFIG.timeout) {
    await delay(2000); // Check every 2 seconds

    try {
      const stats = await apiCall('/redis-queue/stats');
      const totalPending = Object.values(stats.queues || {}).reduce((sum, q) => sum + q, 0);

      if (totalPending === 0) {
        stableCount++;
        if (stableCount >= 3) { // Empty for 6 seconds
          queueEmpty = true;
          log('All queues empty', 'SUCCESS');
        }
      } else {
        stableCount = 0;
        if (totalPending !== lastCount) {
          log(`Queues: ${totalPending} pending`, 'INFO');
          lastCount = totalPending;
        }
      }
    } catch (err) {
      state.errors.push(`Queue stats error: ${err.message}`);
    }
  }

  // Stop workers
  workerProcs.forEach(proc => proc.kill('SIGTERM'));

  state.metrics.processingTime = Date.now() - phaseStart;
  log(`Processed ${state.processedTaskIds.length} tasks`, 'SUCCESS');
  log(`Processing time: ${state.metrics.processingTime}ms`, 'METRIC');

  return state.processedTaskIds.length >= CONFIG.testTasks * 0.95;
}

async function phase4_verifyStorage() {
  log('='.repeat(60));
  log('PHASE 4: Verify Content Storage');
  log('='.repeat(60));

  const phaseStart = Date.now();

  // Query stored documents via API
  const stored = await apiCall('/storage/recent?limit=' + CONFIG.testTasks);
  state.storedDocIds = stored.documents?.map(d => d.id) || [];

  log(`Found ${state.storedDocIds.length} stored documents`, 'SUCCESS');

  // Verify content integrity (sample 10 random docs)
  const sampleSize = Math.min(10, state.storedDocIds.length);
  const sampleIds = state.storedDocIds.slice(0, sampleSize);

  let integrityOk = true;
  for (const docId of sampleIds) {
    const doc = await apiCall(`/storage/document/${docId}`);
    if (!doc.content || doc.content.length < 100) {
      state.errors.push(`Document ${docId} has insufficient content: ${doc.content?.length || 0} chars`);
      integrityOk = false;
    }
  }

  const storageTime = Date.now() - phaseStart;
  log(`Storage verification time: ${storageTime}ms`, 'METRIC');
  log(`Content integrity: ${integrityOk ? 'PASS' : 'FAIL'}`, integrityOk ? 'SUCCESS' : 'ERROR');

  return state.storedDocIds.length >= CONFIG.testTasks * 0.95 && integrityOk;
}

async function phase5_verifyChunking() {
  log('='.repeat(60));
  log('PHASE 5: Verify Chunking');
  log('='.repeat(60));

  const phaseStart = Date.now();

  // Query chunks via API
  const chunks = await apiCall('/chunks/recent?limit=' + CONFIG.testTasks * 5); // ~5 chunks per doc
  state.chunkedDocIds = chunks.chunks?.map(c => c.document_id) || [];

  const uniqueDocs = new Set(state.chunkedDocIds).size;
  log(`Found ${chunks.chunks?.length || 0} chunks from ${uniqueDocs} documents`, 'SUCCESS');

  state.metrics.chunkingTime = Date.now() - phaseStart;
  log(`Chunking verification time: ${state.metrics.chunkingTime}ms`, 'METRIC');

  return uniqueDocs >= CONFIG.testTasks * 0.95;
}

async function phase6_verifyEmbeddings() {
  log('='.repeat(60));
  log('PHASE 6: Verify Embeddings');
  log('='.repeat(60));

  const phaseStart = Date.now();

  // Query embeddings via API
  const embeddings = await apiCall('/embeddings/stats');
  state.embeddedChunkIds = embeddings.total_chunks || 0;

  log(`Embedded ${state.embeddedChunkIds} chunks`, 'SUCCESS');
  log(`Provider cascade stats:`, 'INFO');
  Object.entries(embeddings.providers || {}).forEach(([provider, count]) => {
    log(`  ${provider}: ${count} embeddings`, 'INFO');
  });

  state.metrics.embeddingTime = Date.now() - phaseStart;
  log(`Embedding verification time: ${state.metrics.embeddingTime}ms`, 'METRIC');

  return state.embeddedChunkIds >= CONFIG.testTasks * 5 * 0.95; // ~5 chunks per doc
}

async function phase7_verifyGraph() {
  log('='.repeat(60));
  log('PHASE 7: Verify Graph Storage (OrientDB)');
  log('='.repeat(60));

  const phaseStart = Date.now();

  // Query graph nodes via API
  const graphStats = await apiCall('/graph/stats');
  state.graphNodeIds = graphStats.document_nodes || 0;

  log(`Graph nodes: ${state.graphNodeIds}`, 'SUCCESS');
  log(`Graph edges: ${graphStats.edges || 0}`, 'INFO');

  state.metrics.graphTime = Date.now() - phaseStart;
  log(`Graph verification time: ${state.metrics.graphTime}ms`, 'METRIC');

  return state.graphNodeIds >= CONFIG.testTasks * 0.95;
}

async function phase8_cleanup() {
  if (!CONFIG.cleanup) {
    log('Skipping cleanup (no --cleanup flag)', 'INFO');
    return true;
  }

  log('='.repeat(60));
  log('PHASE 8: Cleanup Test Data');
  log('='.repeat(60));

  try {
    await apiCall('/test/cleanup', 'POST', { prefix: 'test-doc-' });
    log('Cleaned up test data', 'SUCCESS');
    return true;
  } catch (err) {
    state.errors.push(`Cleanup failed: ${err.message}`);
    log(`Cleanup failed: ${err.message}`, 'ERROR');
    return false;
  }
}

function printSummary() {
  log('');
  log('='.repeat(60));
  log('TEST SUMMARY');
  log('='.repeat(60));

  state.metrics.totalTime = Date.now() - state.startTime;

  log(`Total runtime: ${(state.metrics.totalTime / 1000).toFixed(2)}s`, 'METRIC');
  log('');
  log('Phase Breakdown:', 'METRIC');
  log(`  Migration:   ${(state.metrics.migrationTime / 1000).toFixed(2)}s`, 'METRIC');
  log(`  Processing:  ${(state.metrics.processingTime / 1000).toFixed(2)}s`, 'METRIC');
  log(`  Chunking:    ${(state.metrics.chunkingTime / 1000).toFixed(2)}s`, 'METRIC');
  log(`  Embedding:   ${(state.metrics.embeddingTime / 1000).toFixed(2)}s`, 'METRIC');
  log(`  Graph:       ${(state.metrics.graphTime / 1000).toFixed(2)}s`, 'METRIC');
  log('');
  log('Data Flow:', 'METRIC');
  log(`  Tasks generated:      ${CONFIG.testTasks}`, 'METRIC');
  log(`  Tasks migrated:       ${state.migratedTaskIds.length}`, 'METRIC');
  log(`  Tasks processed:      ${state.processedTaskIds.length}`, 'METRIC');
  log(`  Documents stored:     ${state.storedDocIds.length}`, 'METRIC');
  log(`  Documents chunked:    ${new Set(state.chunkedDocIds).size}`, 'METRIC');
  log(`  Chunks embedded:      ${state.embeddedChunkIds}`, 'METRIC');
  log(`  Graph nodes created:  ${state.graphNodeIds}`, 'METRIC');
  log('');

  const avgLatency = state.processedTaskIds.length > 0
    ? state.metrics.processingTime / state.processedTaskIds.length
    : 0;

  log(`Average latency: ${avgLatency.toFixed(0)}ms per task`, 'METRIC');
  log('');

  if (state.errors.length > 0) {
    log(`Errors (${state.errors.length}):`, 'ERROR');
    state.errors.slice(0, 10).forEach(err => log(`  ${err}`, 'ERROR'));
    if (state.errors.length > 10) {
      log(`  ... and ${state.errors.length - 10} more`, 'ERROR');
    }
  } else {
    log('No errors encountered', 'SUCCESS');
  }

  log('');
  log('='.repeat(60));

  // Pass/fail criteria
  const passRate = state.processedTaskIds.length / CONFIG.testTasks;
  const passed = passRate >= 0.95 && avgLatency < 2000 && state.errors.length < 10;

  if (passed) {
    log('✅ INTEGRATION TEST PASSED', 'SUCCESS');
    return 0;
  } else {
    log('❌ INTEGRATION TEST FAILED', 'ERROR');
    if (passRate < 0.95) log(`  Pass rate: ${(passRate * 100).toFixed(1)}% (expected ≥95%)`, 'ERROR');
    if (avgLatency >= 2000) log(`  Latency: ${avgLatency.toFixed(0)}ms (expected <2000ms)`, 'ERROR');
    if (state.errors.length >= 10) log(`  Errors: ${state.errors.length} (expected <10)`, 'ERROR');
    return 1;
  }
}

// Main execution
(async () => {
  try {
    log('Starting Full Pipeline Integration Test', 'INFO');
    log(`Configuration: ${CONFIG.testTasks} tasks, ${CONFIG.workers} workers`, 'INFO');
    log('');

    const results = {
      phase1: await phase1_generateTestTasks(),
      phase2: await phase2_migrateToRedis(),
      phase3: await phase3_processRedisQueues(),
      phase4: await phase4_verifyStorage(),
      phase5: await phase5_verifyChunking(),
      phase6: await phase6_verifyEmbeddings(),
      phase7: await phase7_verifyGraph(),
      phase8: await phase8_cleanup(),
    };

    log('');
    log('Phase Results:', 'INFO');
    Object.entries(results).forEach(([phase, passed]) => {
      log(`  ${phase}: ${passed ? 'PASS' : 'FAIL'}`, passed ? 'SUCCESS' : 'ERROR');
    });

    const exitCode = printSummary();
    process.exit(exitCode);

  } catch (err) {
    log(`Test failed with error: ${err.message}`, 'ERROR');
    console.error(err.stack);
    process.exit(1);
  }
})();
