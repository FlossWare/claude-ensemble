#!/usr/bin/env node
/**
 * Migration Script: JSON State Files → PostgreSQL
 *
 * Migrates legacy JSON state files to postgres-adapter.js:
 * - bandit-state.json → workflow.strategy_performance
 * - active-inference-state.json → workflow.experiences
 *
 * Usage:
 *   node learning/migrate-json-to-postgres.js [--dry-run] [--backup]
 *
 * Options:
 *   --dry-run: Show what would be migrated without actually migrating
 *   --backup: Create backup of JSON files before migration
 *   --force: Overwrite existing PostgreSQL data (default: skip existing)
 */

import { readFileSync, writeFileSync, existsSync, copyFileSync } from 'fs';
import { join } from 'path';
import { getStrategyPerformance, getExperienceMemory } from './postgres-adapter.js';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const LEARNING_DIR = join(HOME, '.claude', 'learning');
const BANDIT_STATE_PATH = join(LEARNING_DIR, 'bandit-state.json');
const ACTIVE_INFERENCE_PATH = join(LEARNING_DIR, 'active-inference-state.json');

const ARGS = process.argv.slice(2);
const DRY_RUN = ARGS.includes('--dry-run');
const BACKUP = ARGS.includes('--backup');
const FORCE = ARGS.includes('--force');

// ============================================================================
// MIGRATION FUNCTIONS
// ============================================================================

/**
 * Migrate bandit-state.json to PostgreSQL workflow.strategy_performance
 */
async function migrateBanditState() {
  console.log('\n=== Migrating bandit-state.json ===\n');

  if (!existsSync(BANDIT_STATE_PATH)) {
    console.log('⚠ bandit-state.json not found, skipping');
    return { migrated: 0, skipped: 0, errors: 0 };
  }

  // Load JSON state
  let state;
  try {
    const data = readFileSync(BANDIT_STATE_PATH, 'utf-8');
    state = JSON.parse(data);
  } catch (err) {
    console.error(`✗ Failed to parse bandit-state.json: ${err.message}`);
    return { migrated: 0, skipped: 0, errors: 1 };
  }

  if (!state.models || typeof state.models !== 'object') {
    console.error('✗ Invalid bandit-state.json structure (missing models)');
    return { migrated: 0, skipped: 0, errors: 1 };
  }

  // Backup if requested
  if (BACKUP && !DRY_RUN) {
    const backupPath = `${BANDIT_STATE_PATH}.backup.${Date.now()}`;
    copyFileSync(BANDIT_STATE_PATH, backupPath);
    console.log(`✓ Backup created: ${backupPath}`);
  }

  const sp = getStrategyPerformance();
  const stats = { migrated: 0, skipped: 0, errors: 0 };

  // Migrate each model
  for (const [model, modelState] of Object.entries(state.models)) {
    try {
      console.log(`  ${model}:`);
      console.log(`    alpha=${modelState.alpha}, beta=${modelState.beta}`);
      console.log(`    total=${modelState.total}, avg_quality=${modelState.avg_quality}`);

      if (DRY_RUN) {
        console.log(`    [DRY RUN] Would migrate to PostgreSQL`);
        stats.migrated++;
        continue;
      }

      // Check if already exists
      const existing = await sp.getStrategy(model);
      if (existing && !FORCE) {
        console.log(`    ⚠ Already exists in PostgreSQL, skipping (use --force to overwrite)`);
        stats.skipped++;
        continue;
      }

      // Calculate successes/failures from alpha/beta
      // alpha = successes + prior (1), beta = failures + prior (1)
      const successes = Math.max(0, Math.round(modelState.alpha - 1));
      const failures = Math.max(0, Math.round(modelState.beta - 1));
      const total_reward = modelState.avg_quality * modelState.total;
      const avg_reward = modelState.avg_quality;

      // Migrate to PostgreSQL
      await sp.updateStrategy(model, {
        successes,
        failures,
        alpha: modelState.alpha,
        beta: modelState.beta,
        total_reward,
        avg_reward,
      });

      console.log(`    ✓ Migrated to PostgreSQL`);
      stats.migrated++;
    } catch (err) {
      console.error(`    ✗ Migration failed: ${err.message}`);
      stats.errors++;
    }
  }

  console.log(`\nBandit State Summary:`);
  console.log(`  Migrated: ${stats.migrated}`);
  console.log(`  Skipped: ${stats.skipped}`);
  console.log(`  Errors: ${stats.errors}`);

  return stats;
}

/**
 * Migrate active-inference-state.json to PostgreSQL workflow.experiences
 */
async function migrateActiveInferenceState() {
  console.log('\n=== Migrating active-inference-state.json ===\n');

  if (!existsSync(ACTIVE_INFERENCE_PATH)) {
    console.log('⚠ active-inference-state.json not found, skipping');
    return { migrated: 0, skipped: 0, errors: 0 };
  }

  // Load JSON state
  let state;
  try {
    const data = readFileSync(ACTIVE_INFERENCE_PATH, 'utf-8');
    state = JSON.parse(data);
  } catch (err) {
    console.error(`✗ Failed to parse active-inference-state.json: ${err.message}`);
    return { migrated: 0, skipped: 0, errors: 1 };
  }

  // Backup if requested
  if (BACKUP && !DRY_RUN) {
    const backupPath = `${ACTIVE_INFERENCE_PATH}.backup.${Date.now()}`;
    copyFileSync(ACTIVE_INFERENCE_PATH, backupPath);
    console.log(`✓ Backup created: ${backupPath}`);
  }

  const em = getExperienceMemory();
  const stats = { migrated: 0, skipped: 0, errors: 0 };

  // Active inference state is typically a single state object, not a collection
  // We'll store it as a single experience
  try {
    console.log(`  Active Inference State:`);
    console.log(`    ${JSON.stringify(state).substring(0, 100)}...`);

    if (DRY_RUN) {
      console.log(`    [DRY RUN] Would migrate to PostgreSQL`);
      stats.migrated++;
    } else {
      // Create a hash of the state for deduplication
      const crypto = await import('crypto');
      const stateHash = crypto.createHash('sha256')
        .update(JSON.stringify(state))
        .digest('hex');

      // Store as experience
      await em.addExperience({
        problem_type: 'active_inference',
        problem_hash: stateHash,
        context: state,
        embedding: null, // No embedding for now
        strategy: 'active_inference',
        success: true,
        reward: 1.0,
        novelty_score: 0.0,
        importance: 0.5,
      });

      console.log(`    ✓ Migrated to PostgreSQL`);
      stats.migrated++;
    }
  } catch (err) {
    console.error(`    ✗ Migration failed: ${err.message}`);
    stats.errors++;
  }

  console.log(`\nActive Inference Summary:`);
  console.log(`  Migrated: ${stats.migrated}`);
  console.log(`  Skipped: ${stats.skipped}`);
  console.log(`  Errors: ${stats.errors}`);

  return stats;
}

/**
 * Main migration entry point
 */
async function main() {
  console.log('\n╔══════════════════════════════════════════════════════════════╗');
  console.log('║  JSON → PostgreSQL Migration                                 ║');
  console.log('╚══════════════════════════════════════════════════════════════╝');

  if (DRY_RUN) {
    console.log('\n⚠ DRY RUN MODE - No changes will be made\n');
  }

  if (FORCE) {
    console.log('\n⚠ FORCE MODE - Will overwrite existing PostgreSQL data\n');
  }

  try {
    // Migrate bandit state
    const banditStats = await migrateBanditState();

    // Migrate active inference state
    const aiStats = await migrateActiveInferenceState();

    // Summary
    console.log('\n╔══════════════════════════════════════════════════════════════╗');
    console.log('║  Migration Complete                                          ║');
    console.log('╚══════════════════════════════════════════════════════════════╝');
    console.log(`\nTotal Migrated: ${banditStats.migrated + aiStats.migrated}`);
    console.log(`Total Skipped: ${banditStats.skipped + aiStats.skipped}`);
    console.log(`Total Errors: ${banditStats.errors + aiStats.errors}`);

    if (DRY_RUN) {
      console.log('\n✓ Dry run complete. Run without --dry-run to perform migration.');
    } else if (banditStats.errors === 0 && aiStats.errors === 0) {
      console.log('\n✓ Migration successful!');
      console.log('\nNext steps:');
      console.log('  1. Verify PostgreSQL data: psql -h aio-01 -p 5433 -U $USER -d learning');
      console.log('  2. Test thompson-sampling.js with migrated data');
      console.log('  3. Delete JSON files after verification (manual step)');
    } else {
      console.log('\n⚠ Migration completed with errors. Review output above.');
      process.exit(1);
    }
  } catch (err) {
    console.error(`\n✗ Migration failed: ${err.message}`);
    if (process.env.LEARNING_DEBUG) {
      console.error(err.stack);
    }
    process.exit(1);
  }
}

// Run migration
main().catch(err => {
  console.error(`Fatal error: ${err.message}`);
  process.exit(1);
});
