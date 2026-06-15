#!/usr/bin/env node

/**
 * Discovery Metadata Updater
 *
 * Tracks discovery application and evidence collection:
 * - Increment apply_count when discoveries are used in model selection
 * - Increment evidence_count when pattern matches successful execution
 * - Update confidence scores based on outcomes
 * - Mark low-confidence discoveries as inactive
 *
 * Usage:
 *   import { recordDiscoveryApplication, recordDiscoveryEvidence, updateConfidence } from './update-discovery-metadata.js';
 *
 *   // Called by orchestrator.js when a discovery is applied
 *   await recordDiscoveryApplication('discovery_001');
 *
 *   // Called by recordResult() when execution completes
 *   await recordDiscoveryEvidence('discovery_001', {
 *     qualityScore: 0.85,
 *     success: true,
 *     context: { task_type: 'security-review' }
 *   });
 *
 *   // Periodic update of all discovery confidence scores
 *   await updateAllConfidence();
 *
 *   node update-discovery-metadata.js --recompute  # Recompute all confidence scores
 *   node update-discovery-metadata.js --prune      # Mark low-confidence as inactive
 */

import { hotImportJSON } from '../shared/hot-reload.js';
import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================================
// CONSTANTS
// ============================================================================

const DISCOVERIES_PATH = join(__dirname, 'discoveries.json');
const MIN_CONFIDENCE_THRESHOLD = 0.60;  // Mark as inactive below this
const CONFIDENCE_DECAY_RATE = 0.95;     // Decay factor for failed predictions
const CONFIDENCE_BOOST_RATE = 1.05;     // Boost factor for successful predictions
const MAX_CONFIDENCE = 0.99;            // Cap confidence at 99%

// ============================================================================
// DISCOVERY APPLICATION TRACKING
// ============================================================================

/**
 * Record that a discovery was applied during model selection.
 *
 * Increments apply_count and updates last_applied timestamp.
 *
 * @param {string} discoveryId - Discovery ID
 * @returns {Promise<boolean>} Success
 */
export async function recordDiscoveryApplication(discoveryId) {
  try {
    const data = await _loadDiscoveries();
    const discovery = data.discoveries.find(d => d.id === discoveryId);

    if (!discovery) {
      if (process.env.LEARNING_DEBUG) {
        console.warn(`[update-discovery-metadata] Discovery not found: ${discoveryId}`);
      }
      return false;
    }

    // Increment apply count
    discovery.apply_count = (discovery.apply_count || 0) + 1;
    discovery.last_applied = new Date().toISOString();

    // Update global metadata
    data.metadata.last_applied = new Date().toISOString();
    data.metadata.apply_count = (data.metadata.apply_count || 0) + 1;

    await _saveDiscoveries(data);
    return true;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[update-discovery-metadata] Application tracking error: ${err.message}`);
    }
    return false;
  }
}

/**
 * Record multiple discoveries applied in a single selection.
 *
 * @param {string[]} discoveryIds - Array of discovery IDs
 * @returns {Promise<number>} Number of discoveries updated
 */
export async function recordMultipleApplications(discoveryIds) {
  try {
    const data = await _loadDiscoveries();
    let updated = 0;

    for (const discoveryId of discoveryIds) {
      const discovery = data.discoveries.find(d => d.id === discoveryId);
      if (!discovery) continue;

      discovery.apply_count = (discovery.apply_count || 0) + 1;
      discovery.last_applied = new Date().toISOString();
      updated++;
    }

    if (updated > 0) {
      data.metadata.last_applied = new Date().toISOString();
      data.metadata.apply_count = (data.metadata.apply_count || 0) + updated;
      await _saveDiscoveries(data);
    }

    return updated;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[update-discovery-metadata] Multiple application tracking error: ${err.message}`);
    }
    return 0;
  }
}

// ============================================================================
// EVIDENCE COLLECTION
// ============================================================================

/**
 * Record evidence for a discovery based on execution outcome.
 *
 * Increments evidence_count and adjusts confidence based on success/failure.
 *
 * @param {string} discoveryId - Discovery ID
 * @param {object} outcome - Execution outcome
 * @param {number} outcome.qualityScore - Quality score (0-1)
 * @param {boolean} outcome.success - Whether execution succeeded
 * @param {object} outcome.context - Execution context
 * @returns {Promise<boolean>} Success
 */
export async function recordDiscoveryEvidence(discoveryId, outcome) {
  try {
    const data = await _loadDiscoveries();
    const discovery = data.discoveries.find(d => d.id === discoveryId);

    if (!discovery) {
      return false;
    }

    // Increment evidence count
    discovery.evidence_count = (discovery.evidence_count || 0) + 1;

    // Track quality impact
    const previousImpact = discovery.quality_impact || 0;
    const newImpact = outcome.qualityScore - 0.5; // Baseline is 0.5

    // Running average of quality impact
    const totalEvidence = discovery.evidence_count;
    discovery.quality_impact = (previousImpact * (totalEvidence - 1) + newImpact) / totalEvidence;

    // Adjust confidence based on outcome
    if (outcome.success) {
      // Successful prediction → boost confidence
      discovery.confidence = Math.min(
        MAX_CONFIDENCE,
        discovery.confidence * CONFIDENCE_BOOST_RATE
      );
    } else {
      // Failed prediction → decay confidence
      discovery.confidence = discovery.confidence * CONFIDENCE_DECAY_RATE;

      // Mark as inactive if confidence drops too low
      if (discovery.confidence < MIN_CONFIDENCE_THRESHOLD) {
        discovery.status = 'inactive';
        discovery.inactive_reason = 'Low confidence due to failed predictions';
        discovery.inactivated_at = new Date().toISOString();
      }
    }

    discovery.last_evidence = new Date().toISOString();

    await _saveDiscoveries(data);
    return true;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[update-discovery-metadata] Evidence recording error: ${err.message}`);
    }
    return false;
  }
}

// ============================================================================
// CONFIDENCE UPDATES
// ============================================================================

/**
 * Update confidence score for a discovery based on historical evidence.
 *
 * Recalculates confidence from scratch using Bayesian approach:
 * - Prior: discovered_confidence
 * - Evidence: evidence_count, quality_impact
 * - Posterior: updated confidence
 *
 * @param {string} discoveryId - Discovery ID
 * @returns {Promise<number>} Updated confidence score
 */
export async function updateConfidence(discoveryId) {
  try {
    const data = await _loadDiscoveries();
    const discovery = data.discoveries.find(d => d.id === discoveryId);

    if (!discovery) {
      return 0;
    }

    // Get initial confidence (prior)
    const prior = discovery.discovered_confidence || discovery.confidence;

    // Evidence strength based on sample count
    const evidenceCount = discovery.evidence_count || 0;
    const applyCount = discovery.apply_count || 0;

    if (evidenceCount === 0 && applyCount === 0) {
      // No evidence yet, keep original confidence
      return discovery.confidence;
    }

    // Calculate success rate from evidence
    // If quality_impact > 0, pattern is working
    const qualityImpact = discovery.quality_impact || 0;
    const successRate = Math.max(0, Math.min(1, 0.5 + qualityImpact));

    // Bayesian update: posterior = (prior * weight + evidence * (1-weight))
    // Weight decreases as evidence accumulates
    const weight = 1 / (1 + Math.log10(evidenceCount + 1));
    const posterior = prior * weight + successRate * (1 - weight);

    discovery.confidence = Math.max(
      0,
      Math.min(MAX_CONFIDENCE, posterior)
    );

    // Mark as inactive if confidence too low
    if (discovery.confidence < MIN_CONFIDENCE_THRESHOLD && discovery.status === 'active') {
      discovery.status = 'inactive';
      discovery.inactive_reason = 'Confidence below threshold after evidence collection';
      discovery.inactivated_at = new Date().toISOString();
    }

    // Reactivate if confidence recovers
    if (discovery.confidence >= MIN_CONFIDENCE_THRESHOLD && discovery.status === 'inactive') {
      discovery.status = 'active';
      discovery.inactive_reason = null;
      discovery.reactivated_at = new Date().toISOString();
    }

    await _saveDiscoveries(data);
    return discovery.confidence;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[update-discovery-metadata] Confidence update error: ${err.message}`);
    }
    return 0;
  }
}

/**
 * Update confidence scores for all discoveries.
 *
 * @returns {Promise<number>} Number of discoveries updated
 */
export async function updateAllConfidence() {
  try {
    const data = await _loadDiscoveries();
    let updated = 0;

    for (const discovery of data.discoveries) {
      // Store original confidence as discovered_confidence if not set
      if (!discovery.discovered_confidence) {
        discovery.discovered_confidence = discovery.confidence;
      }

      const before = discovery.confidence;
      await updateConfidence(discovery.id);
      const after = data.discoveries.find(d => d.id === discovery.id).confidence;

      if (Math.abs(after - before) > 0.01) {
        updated++;
      }
    }

    // Update metadata
    const activeCount = data.discoveries.filter(d => d.status === 'active').length;
    const inactiveCount = data.discoveries.filter(d => d.status === 'inactive').length;
    const avgConfidence = data.discoveries.reduce((sum, d) => sum + d.confidence, 0) / data.discoveries.length;

    data.metadata.active_discoveries = activeCount;
    data.metadata.inactive_discoveries = inactiveCount;
    data.metadata.avg_confidence = avgConfidence;
    data.metadata.last_confidence_update = new Date().toISOString();

    await _saveDiscoveries(data);
    return updated;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[update-discovery-metadata] Bulk confidence update error: ${err.message}`);
    }
    return 0;
  }
}

// ============================================================================
// PRUNING
// ============================================================================

/**
 * Mark low-confidence discoveries as inactive.
 *
 * @param {number} threshold - Confidence threshold (default: MIN_CONFIDENCE_THRESHOLD)
 * @returns {Promise<number>} Number of discoveries pruned
 */
export async function pruneLowConfidence(threshold = MIN_CONFIDENCE_THRESHOLD) {
  try {
    const data = await _loadDiscoveries();
    let pruned = 0;

    for (const discovery of data.discoveries) {
      if (discovery.status === 'active' && discovery.confidence < threshold) {
        discovery.status = 'inactive';
        discovery.inactive_reason = `Confidence below threshold (${(discovery.confidence * 100).toFixed(1)}% < ${(threshold * 100).toFixed(1)}%)`;
        discovery.inactivated_at = new Date().toISOString();
        pruned++;
      }
    }

    if (pruned > 0) {
      // Update metadata
      const activeCount = data.discoveries.filter(d => d.status === 'active').length;
      const inactiveCount = data.discoveries.filter(d => d.status === 'inactive').length;

      data.metadata.active_discoveries = activeCount;
      data.metadata.inactive_discoveries = inactiveCount;
      data.metadata.last_pruned = new Date().toISOString();

      await _saveDiscoveries(data);
    }

    return pruned;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[update-discovery-metadata] Pruning error: ${err.message}`);
    }
    return 0;
  }
}

// ============================================================================
// STATISTICS
// ============================================================================

/**
 * Get discovery metadata statistics.
 *
 * @returns {Promise<object>} Discovery statistics
 */
export async function getDiscoveryStats() {
  try {
    const data = await _loadDiscoveries();

    const stats = {
      total: data.discoveries.length,
      active: data.discoveries.filter(d => d.status === 'active').length,
      inactive: data.discoveries.filter(d => d.status === 'inactive').length,
      avg_confidence: 0,
      avg_evidence: 0,
      avg_apply_count: 0,
      avg_quality_impact: 0,
      by_type: {},
      by_source: {},
    };

    let totalConfidence = 0;
    let totalEvidence = 0;
    let totalApplyCount = 0;
    let totalQualityImpact = 0;
    let qualityImpactCount = 0;

    for (const discovery of data.discoveries) {
      totalConfidence += discovery.confidence || 0;
      totalEvidence += discovery.evidence_count || 0;
      totalApplyCount += discovery.apply_count || 0;

      if (discovery.quality_impact !== undefined) {
        totalQualityImpact += discovery.quality_impact;
        qualityImpactCount++;
      }

      // Count by type
      stats.by_type[discovery.type] = (stats.by_type[discovery.type] || 0) + 1;

      // Count by source
      const source = discovery.source || 'manual';
      stats.by_source[source] = (stats.by_source[source] || 0) + 1;
    }

    if (data.discoveries.length > 0) {
      stats.avg_confidence = totalConfidence / data.discoveries.length;
      stats.avg_evidence = totalEvidence / data.discoveries.length;
      stats.avg_apply_count = totalApplyCount / data.discoveries.length;
    }

    if (qualityImpactCount > 0) {
      stats.avg_quality_impact = totalQualityImpact / qualityImpactCount;
    }

    return stats;
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[update-discovery-metadata] Stats error: ${err.message}`);
    }
    return null;
  }
}

// ============================================================================
// FILE I/O HELPERS
// ============================================================================

async function _loadDiscoveries() {
  return await hotImportJSON(DISCOVERIES_PATH, {
    force: true,
    defaultValue: {
      version: 1,
      created: new Date().toISOString(),
      updated: new Date().toISOString(),
      notes: 'AI-discovered patterns and insights for model selection.',
      discoveries: [],
      metadata: {
        total_discoveries: 0,
        active_discoveries: 0,
        inactive_discoveries: 0,
        avg_confidence: 0,
        last_applied: null,
        apply_count: 0,
      },
    },
  });
}

async function _saveDiscoveries(data) {
  data.updated = new Date().toISOString();
  writeFileSync(DISCOVERIES_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

// ============================================================================
// CLI INTERFACE
// ============================================================================

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);

  if (args.includes('--recompute')) {
    console.log('[update-discovery-metadata] Recomputing confidence scores...');
    const updated = await updateAllConfidence();
    console.log(`  Updated: ${updated} discoveries`);

    const stats = await getDiscoveryStats();
    console.log(`  Active:  ${stats.active} discoveries`);
    console.log(`  Avg Confidence: ${(stats.avg_confidence * 100).toFixed(1)}%`);
  } else if (args.includes('--prune')) {
    console.log('[update-discovery-metadata] Pruning low-confidence discoveries...');
    const pruned = await pruneLowConfidence();
    console.log(`  Pruned: ${pruned} discoveries`);

    const stats = await getDiscoveryStats();
    console.log(`  Active:  ${stats.active} discoveries`);
    console.log(`  Inactive: ${stats.inactive} discoveries`);
  } else if (args.includes('--stats')) {
    const stats = await getDiscoveryStats();
    console.log('='.repeat(60));
    console.log('DISCOVERY STATISTICS');
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
  } else {
    console.log('Usage:');
    console.log('  node update-discovery-metadata.js --recompute   # Recompute all confidence scores');
    console.log('  node update-discovery-metadata.js --prune       # Mark low-confidence as inactive');
    console.log('  node update-discovery-metadata.js --stats       # Show discovery statistics');
  }
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  recordDiscoveryApplication,
  recordMultipleApplications,
  recordDiscoveryEvidence,
  updateConfidence,
  updateAllConfidence,
  pruneLowConfidence,
  getDiscoveryStats,
};
