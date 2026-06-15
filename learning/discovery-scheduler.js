#!/usr/bin/env node

/**
 * Discovery Scheduler Daemon
 *
 * Runs discovery pattern generation on a schedule:
 * - Analyzes Thompson Sampling trends
 * - Analyzes execution logs for patterns
 * - Generates new discoveries
 * - Auto-appends high-confidence discoveries to discoveries.json
 * - Prunes low-confidence discoveries
 * - Updates confidence scores based on evidence
 *
 * Usage:
 *   node discovery-scheduler.js              # Run once and exit
 *   node discovery-scheduler.js --daemon     # Run continuously every 6 hours
 *   node discovery-scheduler.js --interval 2 # Custom interval (hours)
 *   node discovery-scheduler.js --status     # Show current stats
 *
 * Scheduling Strategy:
 * - Discovery generation: Every 6 hours (configurable)
 * - Confidence updates: Every discovery run
 * - Pruning: Every discovery run
 * - Logs all activities for audit trail
 */

import { hotImport } from '../shared/hot-reload.js';
import { writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const LOG_DIR = join(HOME, '.claude', 'learning', 'logs');
const LOG_FILE = join(LOG_DIR, 'discovery-scheduler.log');
const MIN_CONFIDENCE_FOR_AUTO_ADD = 0.75;  // Only auto-add high-confidence patterns
const DEFAULT_INTERVAL_HOURS = 6;

// Ensure log directory exists
if (!existsSync(LOG_DIR)) {
  mkdirSync(LOG_DIR, { recursive: true });
}

// Hot-reload dependencies
let discoverPatterns = null;
let updateMetadata = null;

async function getDiscoverPatterns() {
  if (!discoverPatterns) {
    discoverPatterns = await hotImport('./discover-patterns.js');
  }
  return discoverPatterns;
}

async function getUpdateMetadata() {
  if (!updateMetadata) {
    updateMetadata = await hotImport('./update-discovery-metadata.js');
  }
  return updateMetadata;
}

// ============================================================================
// LOGGING
// ============================================================================

function log(message, level = 'INFO') {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] [${level}] ${message}`;

  console.log(logLine);

  try {
    writeFileSync(LOG_FILE, logLine + '\n', { flag: 'a' });
  } catch (err) {
    // Ignore log write errors
  }
}

// ============================================================================
// CLI ARGUMENT PARSING
// ============================================================================

const args = process.argv.slice(2);
const isDaemon = args.includes('--daemon');
const isStatus = args.includes('--status');
const intervalIdx = args.indexOf('--interval');
const intervalHours = intervalIdx >= 0 ? parseFloat(args[intervalIdx + 1]) : DEFAULT_INTERVAL_HOURS;

// ============================================================================
// STATUS COMMAND
// ============================================================================

if (isStatus) {
  await printStatus();
  process.exit(0);
}

async function printStatus() {
  const metadata = await getUpdateMetadata();
  const stats = await metadata.getDiscoveryStats();

  if (!stats) {
    console.log('No discovery statistics available');
    return;
  }

  console.log('='.repeat(60));
  console.log('DISCOVERY SCHEDULER STATUS');
  console.log('='.repeat(60));
  console.log(`Total discoveries:   ${stats.total}`);
  console.log(`Active:              ${stats.active}`);
  console.log(`Inactive:            ${stats.inactive}`);
  console.log(`Avg confidence:      ${(stats.avg_confidence * 100).toFixed(1)}%`);
  console.log(`Avg evidence count:  ${stats.avg_evidence.toFixed(1)}`);
  console.log(`Avg apply count:     ${stats.avg_apply_count.toFixed(1)}`);
  console.log(`Avg quality impact:  ${(stats.avg_quality_impact * 100).toFixed(1)}%`);
  console.log('');
  console.log('By Type:');
  for (const [type, count] of Object.entries(stats.by_type)) {
    console.log(`  ${type.padEnd(20)} ${count}`);
  }
  console.log('');
  console.log('By Source:');
  for (const [source, count] of Object.entries(stats.by_source)) {
    console.log(`  ${source.padEnd(20)} ${count}`);
  }
  console.log('='.repeat(60));
}

// ============================================================================
// DISCOVERY CYCLE
// ============================================================================

/**
 * Run one discovery cycle:
 * 1. Update confidence scores based on evidence
 * 2. Prune low-confidence discoveries
 * 3. Generate new patterns
 * 4. Auto-add high-confidence patterns
 *
 * @returns {Promise<object>} Cycle results
 */
async function runDiscoveryCycle() {
  const startTime = Date.now();
  log('Starting discovery cycle');

  const results = {
    confidence_updated: 0,
    pruned: 0,
    discovered: 0,
    added: 0,
    duration_ms: 0,
  };

  try {
    const metadata = await getUpdateMetadata();

    // Step 1: Update confidence scores
    log('Updating confidence scores...');
    results.confidence_updated = await metadata.updateAllConfidence();
    log(`  Updated ${results.confidence_updated} discoveries`);

    // Step 2: Prune low-confidence discoveries
    log('Pruning low-confidence discoveries...');
    results.pruned = await metadata.pruneLowConfidence();
    if (results.pruned > 0) {
      log(`  Pruned ${results.pruned} discoveries`);
    } else {
      log('  No discoveries pruned');
    }

    // Step 3: Generate new patterns
    log('Generating new discovery patterns...');
    const discover = await getDiscoverPatterns();
    const newPatterns = await discover.discoverPatterns({
      minConfidence: MIN_CONFIDENCE_FOR_AUTO_ADD,
    });
    results.discovered = newPatterns.length;
    log(`  Discovered ${results.discovered} new patterns`);

    // Step 4: Auto-add high-confidence patterns
    if (newPatterns.length > 0) {
      log('Auto-adding high-confidence patterns...');
      const addResult = await discover.generateAndApply({
        minConfidence: MIN_CONFIDENCE_FOR_AUTO_ADD,
      });
      results.added = addResult.added;

      if (results.added > 0) {
        log(`  Added ${results.added} new discoveries`);

        // Log details of new discoveries
        for (const d of addResult.discoveries) {
          log(`    ${d.id}: ${d.description} (conf: ${(d.confidence * 100).toFixed(1)}%)`, 'INFO');
        }
      } else {
        log('  No new discoveries added (all already exist)');
      }
    }

    // Get final stats
    const stats = await metadata.getDiscoveryStats();
    log(`Final state: ${stats.active} active, ${stats.inactive} inactive, avg confidence ${(stats.avg_confidence * 100).toFixed(1)}%`);

  } catch (err) {
    log(`Discovery cycle error: ${err.message}`, 'ERROR');
    log(err.stack, 'ERROR');
  }

  results.duration_ms = Date.now() - startTime;
  log(`Discovery cycle complete in ${results.duration_ms}ms`);

  return results;
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

async function runOnce() {
  const result = await runDiscoveryCycle();

  console.log('');
  console.log('Discovery Cycle Results:');
  console.log(`  Confidence updated: ${result.confidence_updated} discoveries`);
  console.log(`  Pruned:             ${result.pruned} discoveries`);
  console.log(`  Discovered:         ${result.discovered} new patterns`);
  console.log(`  Added:              ${result.added} new discoveries`);
  console.log(`  Duration:           ${result.duration_ms}ms`);
  console.log('');

  return result;
}

if (isDaemon) {
  log(`Starting discovery scheduler daemon (interval: ${intervalHours}h)`);
  log(`Log file: ${LOG_FILE}`);
  log('Press Ctrl+C to stop');
  console.log('');

  // Run immediately
  await runOnce();

  // Then run on interval
  const intervalMs = intervalHours * 60 * 60 * 1000;
  log(`Next run scheduled in ${intervalHours} hours`);

  const intervalId = setInterval(async () => {
    log('Scheduled discovery cycle starting');
    await runOnce();
    log(`Next run scheduled in ${intervalHours} hours`);
  }, intervalMs);

  // Clean shutdown
  process.on('SIGINT', () => {
    log('Shutting down discovery scheduler...', 'INFO');
    clearInterval(intervalId);
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    log('Shutting down discovery scheduler...', 'INFO');
    clearInterval(intervalId);
    process.exit(0);
  });
} else {
  // Single run mode
  await runOnce();
  process.exit(0);
}
