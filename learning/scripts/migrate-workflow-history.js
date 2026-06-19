#!/usr/bin/env node

/**
 * Workflow History Migration Script
 *
 * Scans SESSION_FILE JSONL files (e.g., deep-research session files) and backfills
 * into PostgreSQL schema. Parses JSON, extracts execution metadata, workers, arbiter
 * decisions. Generates embeddings for historical data. Marks as migrated to avoid
 * reprocessing. This provides historical baseline for Thompson Sampling.
 *
 * Usage:
 *   node migrate-workflow-history.js [--dry-run] [--force] [--session-dir <path>]
 *
 * Options:
 *   --dry-run       Show what would be migrated without writing to database
 *   --force         Re-migrate already migrated sessions
 *   --session-dir   Override default session directory (~/.claude/learning/research/sessions)
 */

import { readdirSync, readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { getDB, getWorkflowsLearning, getStrategyPerformance, OUTCOMES } from '../postgres-adapter.js';

const ARGS = process.argv.slice(2);
const DRY_RUN = ARGS.includes('--dry-run');
const FORCE = ARGS.includes('--force');
const SESSION_DIR_INDEX = ARGS.indexOf('--session-dir');
const DEFAULT_SESSION_DIR = join(homedir(), '.claude', 'learning', 'research', 'sessions');
const SESSION_DIR = SESSION_DIR_INDEX >= 0 ? ARGS[SESSION_DIR_INDEX + 1] : DEFAULT_SESSION_DIR;
const MIGRATION_STATE_FILE = join(homedir(), '.claude', 'learning', 'migration-state.json');

// Track which sessions have been migrated
let migrationState = { migratedSessions: [], lastRun: null };
if (existsSync(MIGRATION_STATE_FILE)) {
  try {
    migrationState = JSON.parse(readFileSync(MIGRATION_STATE_FILE, 'utf8'));
  } catch (err) {
    console.warn('Failed to load migration state, starting fresh:', err.message);
  }
}

function saveMigrationState() {
  migrationState.lastRun = new Date().toISOString();
  writeFileSync(MIGRATION_STATE_FILE, JSON.stringify(migrationState, null, 2));
}

/**
 * Generate simple embedding vector from text using character frequency
 * This is a placeholder - in production, use a proper embedding model
 * @param {string} text - Text to embed
 * @param {number} dim - Embedding dimension (default 128)
 * @returns {Array<number>} Embedding vector
 */
function generateEmbedding(text, dim = 128) {
  const normalized = text.toLowerCase();
  const vector = new Array(dim).fill(0);

  // Character frequency distribution
  for (let i = 0; i < normalized.length; i++) {
    const charCode = normalized.charCodeAt(i);
    const idx = charCode % dim;
    vector[idx] += 1.0;
  }

  // Normalize to unit length
  const magnitude = Math.sqrt(vector.reduce((sum, val) => sum + val * val, 0));
  if (magnitude > 0) {
    for (let i = 0; i < dim; i++) {
      vector[i] /= magnitude;
    }
  }

  return vector;
}

/**
 * Extract metadata from session phases
 */
function extractPhaseMetadata(session) {
  const phases = session.phases || {};
  const metadata = {
    session_id: session.id,
    query: session.query,
    started: session.started,
    completed: session.completed || session.failed,
    phases: {}
  };

  for (const [phaseName, phaseData] of Object.entries(phases)) {
    metadata.phases[phaseName] = {
      status: phaseData.status,
      error: phaseData.error || null,
      data_count: 0
    };

    // Count data items per phase
    if (phaseName === 'scope' && phaseData.angles) {
      metadata.phases[phaseName].data_count = phaseData.angles.length;
    } else if (phaseName === 'search' && phaseData.results) {
      metadata.phases[phaseName].data_count = phaseData.results.length;
    } else if (phaseName === 'fetch' && phaseData.sources) {
      metadata.phases[phaseName].data_count = phaseData.sources.length;
    } else if (phaseName === 'verify' && phaseData.claims) {
      metadata.phases[phaseName].data_count = phaseData.claims.length;
    }
  }

  return metadata;
}

/**
 * Calculate quality score from session data
 */
function calculateQualityScore(session) {
  const phases = session.phases || {};

  // If verify phase completed, use claim acceptance ratio
  if (phases.verify && phases.verify.claims) {
    const totalClaims = phases.verify.claims.length;
    const acceptedClaims = phases.verify.claims.filter(c => c.accepted).length;
    return totalClaims > 0 ? acceptedClaims / totalClaims : 0;
  }

  // Otherwise, calculate based on phase completion
  const totalPhases = Object.keys(phases).length;
  const completedPhases = Object.values(phases).filter(p => p.status === 'completed').length;
  return totalPhases > 0 ? completedPhases / totalPhases : 0;
}

/**
 * Determine outcome from session data
 */
function determineOutcome(session) {
  if (session.failed) {
    return OUTCOMES.ERROR;
  }

  if (session.completed) {
    return OUTCOMES.SUCCESS;
  }

  // Check if any phase failed
  const phases = session.phases || {};
  const hasFailedPhase = Object.values(phases).some(p => p.status === 'failed');
  if (hasFailedPhase) {
    return OUTCOMES.FAILED;
  }

  // Still running or incomplete
  return OUTCOMES.FAILED;
}

/**
 * Extract worker models used in multi-model operations
 */
function extractWorkerModels(session) {
  const workers = new Set();

  // Check verify phase for 3-vote models
  const phases = session.phases || {};
  if (phases.verify && phases.verify.claims) {
    // Deep research uses opus/sonnet/haiku for verification
    workers.add('claude-opus-4');
    workers.add('claude-sonnet-4');
    workers.add('claude-haiku-4');
  }

  return Array.from(workers);
}

/**
 * Calculate task difficulty from session metadata
 */
function assessTaskDifficulty(session) {
  const phases = session.phases || {};

  // Count completed phases
  const completedCount = Object.values(phases).filter(p => p.status === 'completed').length;
  const totalCount = Object.keys(phases).length;

  // Check for errors
  const hasErrors = session.failed || Object.values(phases).some(p => p.status === 'failed');

  // Difficulty assessment
  if (hasErrors) {
    return 'hard';
  }

  const completionRatio = completedCount / totalCount;
  if (completionRatio >= 0.8) {
    return 'easy';
  } else if (completionRatio >= 0.5) {
    return 'moderate';
  } else {
    return 'hard';
  }
}

/**
 * Calculate duration from session timestamps
 */
function calculateDuration(session) {
  if (!session.started) {
    return null;
  }

  const endTime = session.completed || session.failed || new Date().toISOString();
  const startMs = new Date(session.started).getTime();
  const endMs = new Date(endTime).getTime();

  return endMs - startMs;
}

/**
 * Migrate a single session file to PostgreSQL
 */
async function migrateSession(sessionFile, workflowsLearning, strategyPerf) {
  const sessionData = JSON.parse(readFileSync(sessionFile, 'utf8'));
  const sessionId = sessionData.id;

  console.log(`\n  Processing session: ${sessionId}`);

  // Skip if already migrated (unless --force)
  if (!FORCE && migrationState.migratedSessions.includes(sessionId)) {
    console.log('    ✓ Already migrated (use --force to re-migrate)');
    return { skipped: true };
  }

  // Extract metadata
  const metadata = extractPhaseMetadata(sessionData);
  const qualityScore = calculateQualityScore(sessionData);
  const outcome = determineOutcome(sessionData);
  const workerModels = extractWorkerModels(sessionData);
  const taskDifficulty = assessTaskDifficulty(sessionData);
  const durationMs = calculateDuration(sessionData);

  // Generate embedding from query
  const embedding = generateEmbedding(sessionData.query || '', 128);

  console.log(`    Quality: ${(qualityScore * 100).toFixed(1)}%`);
  console.log(`    Outcome: ${outcome}`);
  console.log(`    Difficulty: ${taskDifficulty}`);
  console.log(`    Workers: ${workerModels.join(', ')}`);
  console.log(`    Duration: ${durationMs ? (durationMs / 1000).toFixed(1) + 's' : 'N/A'}`);

  if (DRY_RUN) {
    console.log('    [DRY RUN] Would insert into workflows.learnings');
    return { inserted: false, dryRun: true };
  }

  try {
    // Record workflow run
    await workflowsLearning.recordRun({
      run_id: sessionId,
      workflow_name: 'deep-research',
      status: sessionData.completed ? 'completed' : sessionData.failed ? 'failed' : 'running',
      input_args: { query: sessionData.query },
      output_result: sessionData.phases.synthesize?.report ?
        { report: sessionData.phases.synthesize.report } : null,
      error_message: sessionData.error || null,
      duration_ms: durationMs
    });

    // Record workflow learning
    await workflowsLearning.recordLearning({
      run_id: sessionId,
      workflow_name: 'deep-research',
      learning_type: 'task_difficulty',
      task_difficulty: taskDifficulty,
      task_type: 'research_synthesis',
      task_summary: sessionData.query || '',
      quality_score: qualityScore,
      outcome: outcome,
      model_count: workerModels.length,
      duration_ms: durationMs,
      cost_usd: 0, // Not tracked in legacy sessions
      metadata: metadata,
      embedding: `[${embedding.join(',')}]`
    });

    // Update Thompson Sampling strategy performance
    // Use workflow completion as success signal
    const strategy = 'deep-research-workflow';
    const success = outcome === OUTCOMES.SUCCESS;
    const reward = qualityScore;

    await strategyPerf.record(strategy, success, reward);

    console.log('    ✓ Migrated successfully');

    // Mark as migrated
    migrationState.migratedSessions.push(sessionId);

    return { inserted: true };
  } catch (err) {
    console.error(`    ✗ Migration failed: ${err.message}`);
    return { error: err.message };
  }
}

/**
 * Main migration function
 */
async function main() {
  console.log('Workflow History Migration');
  console.log('='.repeat(80));
  console.log(`Session Directory: ${SESSION_DIR}`);
  console.log(`Dry Run: ${DRY_RUN ? 'YES' : 'NO'}`);
  console.log(`Force Re-migration: ${FORCE ? 'YES' : 'NO'}`);
  console.log('='.repeat(80));

  // Check if session directory exists
  if (!existsSync(SESSION_DIR)) {
    console.log(`\n✗ Session directory does not exist: ${SESSION_DIR}`);
    console.log('  No sessions to migrate. This is normal if workflows haven\'t been run yet.');
    process.exit(0);
  }

  // Find all session JSON files
  const files = readdirSync(SESSION_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => join(SESSION_DIR, f));

  if (files.length === 0) {
    console.log('\n✗ No session files found to migrate');
    process.exit(0);
  }

  console.log(`\nFound ${files.length} session file(s)`);

  // Initialize database connections
  const db = getDB();
  const workflowsLearning = getWorkflowsLearning();
  const strategyPerf = getStrategyPerformance();

  // Migrate each session
  const results = {
    total: files.length,
    inserted: 0,
    skipped: 0,
    errors: 0
  };

  for (const file of files) {
    try {
      const result = await migrateSession(file, workflowsLearning, strategyPerf);

      if (result.inserted) {
        results.inserted++;
      } else if (result.skipped) {
        results.skipped++;
      } else if (result.error) {
        results.errors++;
      }
    } catch (err) {
      console.error(`\n✗ Failed to process ${file}:`, err.message);
      results.errors++;
    }
  }

  // Save migration state
  if (!DRY_RUN) {
    saveMigrationState();
  }

  // Close database connection
  await db.close();

  // Summary
  console.log('\n' + '='.repeat(80));
  console.log('Migration Summary');
  console.log('='.repeat(80));
  console.log(`Total sessions:     ${results.total}`);
  console.log(`Inserted:           ${results.inserted}`);
  console.log(`Skipped:            ${results.skipped}`);
  console.log(`Errors:             ${results.errors}`);

  if (DRY_RUN) {
    console.log('\n[DRY RUN] No data was written to database');
    console.log('Run without --dry-run to perform actual migration');
  } else {
    console.log('\n✓ Migration complete!');
    console.log(`Migration state saved: ${MIGRATION_STATE_FILE}`);
  }

  process.exit(results.errors > 0 ? 1 : 0);
}

// Run migration
main().catch(err => {
  console.error('\n✗ Migration failed:', err);
  process.exit(1);
});
