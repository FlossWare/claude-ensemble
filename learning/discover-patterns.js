#!/usr/bin/env node

/**
 * Discovery Pattern Generator
 *
 * Automatically discovers optimization patterns from execution logs and Thompson
 * Sampling trends. Generates new discoveries in discoveries.json format.
 *
 * Pattern Sources:
 * 1. Thompson Sampling trends (e.g., "sonnet 95% success, haiku 50% → prefer sonnet")
 * 2. Execution log analysis (e.g., "fable fails on schema tasks")
 * 3. Cost/quality tradeoffs (e.g., "haiku = 90% quality at 10% cost")
 * 4. Task-specific performance patterns
 *
 * Confidence Scoring:
 * - Based on sample size (more samples → higher confidence)
 * - Based on effect size (larger improvement → higher confidence)
 * - Minimum 10 samples required for pattern discovery
 * - Minimum 0.70 confidence required to activate
 *
 * Usage:
 *   import { discoverPatterns, generateDiscoveries } from './discover-patterns.js';
 *
 *   const discoveries = await discoverPatterns();
 *   // => [{ id, type, pattern, description, conditions, action, confidence, ... }]
 *
 *   node discover-patterns.js              # Generate and print discoveries
 *   node discover-patterns.js --apply      # Generate and append to discoveries.json
 *   node discover-patterns.js --min-conf 0.8  # Custom confidence threshold
 */

import { hotImport, hotImportJSON } from '../shared/hot-reload.js';
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
const MIN_SAMPLES = 10;           // Minimum executions to discover a pattern
const MIN_CONFIDENCE = 0.70;      // Minimum confidence to activate
const MIN_EFFECT_SIZE = 0.10;     // Minimum quality difference to matter
const COST_THRESHOLD = 0.50;      // Cost savings threshold (50% cheaper)

// Hot-reload dependencies
let thompson = null;
let db = null;

async function getThompson() {
  if (!thompson) {
    thompson = await hotImport('./thompson-sampling.js');
  }
  return thompson;
}

async function getDb() {
  if (!db) {
    const logger = await hotImport('../shared/learning-logger.js');
    db = logger.getDb();
  }
  return db;
}

// ============================================================================
// THOMPSON SAMPLING PATTERN DISCOVERY
// ============================================================================

/**
 * Discover patterns from Thompson Sampling trends.
 *
 * Patterns:
 * - Model superiority: "sonnet outperforms haiku by 15%"
 * - Model failures: "fable fails 80% of time on task X"
 * - Cost effectiveness: "haiku matches sonnet quality at 10% cost"
 *
 * @returns {Promise<object[]>} Array of discovered patterns
 */
async function discoverThompsonPatterns() {
  const ts = await getThompson();
  const stats = ts.getAllModelStats();

  if (!stats || stats.length === 0) {
    return [];
  }

  const discoveries = [];

  // Pattern 1: Model superiority (one model significantly better)
  for (let i = 0; i < stats.length; i++) {
    for (let j = i + 1; j < stats.length; j++) {
      const m1 = stats[i];
      const m2 = stats[j];

      // Require minimum samples
      if (m1.total < MIN_SAMPLES || m2.total < MIN_SAMPLES) continue;

      // Calculate effect size
      const effectSize = Math.abs(m1.success_rate - m2.success_rate);
      if (effectSize < MIN_EFFECT_SIZE) continue;

      const [better, worse] = m1.success_rate > m2.success_rate
        ? [m1, m2]
        : [m2, m1];

      // Confidence based on sample size and effect size
      const confidence = calculateConfidence(
        effectSize,
        Math.min(better.total, worse.total)
      );

      if (confidence < MIN_CONFIDENCE) continue;

      discoveries.push({
        id: `discovery_thompson_${better.model}_over_${worse.model}`,
        type: 'model_preference',
        pattern: `prefer-${better.model}-over-${worse.model}`,
        description: `${better.model} outperforms ${worse.model} (success rate: ${(better.success_rate * 100).toFixed(1)}% vs ${(worse.success_rate * 100).toFixed(1)}%)`,
        conditions: {},
        action: {
          type: 'bias_models',
          params: {
            bias: {
              [better.model]: 1.5,
              [worse.model]: 0.7,
            },
          },
        },
        confidence,
        evidence_count: better.total + worse.total,
        quality_impact: effectSize,
        discovered_at: new Date().toISOString(),
        status: 'active',
        source: 'thompson-sampling',
      });
    }
  }

  // Pattern 2: Model failures (success rate < 50%)
  for (const model of stats) {
    if (model.total < MIN_SAMPLES) continue;

    if (model.success_rate < 0.5) {
      const confidence = calculateConfidence(
        0.5 - model.success_rate,
        model.total
      );

      if (confidence < MIN_CONFIDENCE) continue;

      discoveries.push({
        id: `discovery_avoid_${model.model}`,
        type: 'model_filter',
        pattern: `avoid-${model.model}-low-success`,
        description: `${model.model} has low success rate (${(model.success_rate * 100).toFixed(1)}%)`,
        conditions: {},
        action: {
          type: 'filter_models',
          params: {
            exclude: [model.model],
          },
        },
        confidence,
        evidence_count: model.total,
        quality_impact: -(0.5 - model.success_rate),
        discovered_at: new Date().toISOString(),
        status: 'active',
        source: 'thompson-sampling',
      });
    }
  }

  return discoveries;
}

// ============================================================================
// EXECUTION LOG PATTERN DISCOVERY
// ============================================================================

/**
 * Discover patterns from execution log analysis.
 *
 * Patterns:
 * - Task-specific performance (e.g., "opus best for security reviews")
 * - Schema compliance issues (e.g., "fable fails on JSON output")
 * - Cost-quality tradeoffs (e.g., "haiku matches sonnet at 10% cost")
 * - Complexity-based routing (e.g., "haiku sufficient for simple tasks")
 *
 * @param {object} options - Discovery options
 * @returns {Promise<object[]>} Array of discovered patterns
 */
async function discoverExecutionPatterns(options = {}) {
  const database = await getDb();
  if (!database) return [];

  const discoveries = [];

  try {
    // Pattern 1: Task-specific model performance
    const taskPerformance = database.prepare(`
      SELECT
        model,
        task_type,
        COUNT(*) as sample_count,
        AVG(quality_score) as avg_quality,
        AVG(confidence) as avg_confidence,
        AVG(cost_usd) as avg_cost,
        SUM(CASE WHEN quality_score >= 0.7 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as success_rate
      FROM execution_log
      WHERE
        quality_score IS NOT NULL
        AND task_type IS NOT NULL
        AND created_at > datetime('now', '-30 days')
      GROUP BY model, task_type
      HAVING sample_count >= ?
      ORDER BY task_type, avg_quality DESC
    `).all(MIN_SAMPLES);

    // Group by task_type to find best performer
    const byTask = {};
    for (const row of taskPerformance) {
      if (!byTask[row.task_type]) {
        byTask[row.task_type] = [];
      }
      byTask[row.task_type].push(row);
    }

    for (const [taskType, models] of Object.entries(byTask)) {
      if (models.length < 2) continue;

      const best = models[0];
      const others = models.slice(1);

      // Find if best model significantly outperforms others
      for (const other of others) {
        const effectSize = best.avg_quality - other.avg_quality;
        if (effectSize < MIN_EFFECT_SIZE) continue;

        const confidence = calculateConfidence(
          effectSize,
          Math.min(best.sample_count, other.sample_count)
        );

        if (confidence < MIN_CONFIDENCE) continue;

        discoveries.push({
          id: `discovery_task_${taskType}_${best.model}`,
          type: 'task_routing',
          pattern: `${taskType}-prefer-${best.model}`,
          description: `${best.model} performs best for ${taskType} tasks (quality: ${(best.avg_quality * 100).toFixed(1)}% vs ${(other.avg_quality * 100).toFixed(1)}%)`,
          conditions: {
            task_type: taskType,
          },
          action: {
            type: 'bias_models',
            params: {
              bias: {
                [best.model]: 1.5,
                [other.model]: 0.8,
              },
            },
          },
          confidence,
          evidence_count: best.sample_count + other.sample_count,
          quality_impact: effectSize,
          discovered_at: new Date().toISOString(),
          status: 'active',
          source: 'execution-log',
        });
      }
    }

    // Pattern 2: Schema compliance issues
    // Look for models that fail when requires_schema=true or output_format=json
    const schemaPerformance = database.prepare(`
      SELECT
        model,
        COUNT(*) as sample_count,
        AVG(quality_score) as avg_quality,
        SUM(CASE WHEN quality_score >= 0.7 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as success_rate
      FROM execution_log
      WHERE
        quality_score IS NOT NULL
        AND (
          parameters LIKE '%"requires_schema":true%'
          OR parameters LIKE '%"output_format":"json"%'
        )
        AND created_at > datetime('now', '-30 days')
      GROUP BY model
      HAVING sample_count >= ?
    `).all(MIN_SAMPLES);

    for (const row of schemaPerformance) {
      // Detect models with poor schema compliance
      if (row.success_rate < 0.6) {
        const confidence = calculateConfidence(
          0.7 - row.success_rate,
          row.sample_count
        );

        if (confidence < MIN_CONFIDENCE) continue;

        discoveries.push({
          id: `discovery_schema_avoid_${row.model}`,
          type: 'model_filter',
          pattern: `never-${row.model}-for-structured-output`,
          description: `${row.model} struggles with structured output (success rate: ${(row.success_rate * 100).toFixed(1)}%)`,
          conditions: {
            requires_schema: true,
          },
          action: {
            type: 'filter_models',
            params: {
              exclude: [row.model],
            },
          },
          confidence,
          evidence_count: row.sample_count,
          quality_impact: 0.7 - row.success_rate,
          discovered_at: new Date().toISOString(),
          status: 'active',
          source: 'execution-log',
        });
      }
    }

    // Pattern 3: Cost-quality tradeoffs
    // Find cheaper models that match expensive ones
    const costQualityTradeoffs = database.prepare(`
      SELECT
        model,
        COUNT(*) as sample_count,
        AVG(quality_score) as avg_quality,
        AVG(cost_usd) as avg_cost
      FROM execution_log
      WHERE
        quality_score IS NOT NULL
        AND cost_usd IS NOT NULL
        AND cost_usd > 0
        AND created_at > datetime('now', '-30 days')
      GROUP BY model
      HAVING sample_count >= ?
      ORDER BY avg_cost ASC
    `).all(MIN_SAMPLES);

    for (let i = 0; i < costQualityTradeoffs.length; i++) {
      const cheap = costQualityTradeoffs[i];

      for (let j = i + 1; j < costQualityTradeoffs.length; j++) {
        const expensive = costQualityTradeoffs[j];

        // Check if cheap model has similar quality
        const qualityDiff = Math.abs(cheap.avg_quality - expensive.avg_quality);
        const costRatio = cheap.avg_cost / expensive.avg_cost;

        // Cheap model must be at least 50% cheaper
        if (costRatio > COST_THRESHOLD) continue;

        // Quality must be within 5%
        if (qualityDiff > 0.05) continue;

        const confidence = calculateConfidence(
          1 - costRatio,
          Math.min(cheap.sample_count, expensive.sample_count)
        );

        if (confidence < MIN_CONFIDENCE) continue;

        discoveries.push({
          id: `discovery_cost_${cheap.model}_vs_${expensive.model}`,
          type: 'model_preference',
          pattern: `cost-effective-${cheap.model}`,
          description: `${cheap.model} matches ${expensive.model} quality at ${(costRatio * 100).toFixed(0)}% cost`,
          conditions: {
            cost_sensitivity: 'high',
            budget_constraint: true,
          },
          action: {
            type: 'filter_models',
            params: {
              exclude: [expensive.model],
              prefer: [cheap.model],
            },
          },
          confidence,
          evidence_count: cheap.sample_count + expensive.sample_count,
          quality_impact: -qualityDiff,
          cost_savings: 1 - costRatio,
          discovered_at: new Date().toISOString(),
          status: 'active',
          source: 'execution-log',
        });
      }
    }

  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[discover-patterns] Execution pattern discovery error: ${err.message}`);
    }
  }

  return discoveries;
}

// ============================================================================
// CONFIDENCE CALCULATION
// ============================================================================

/**
 * Calculate confidence score based on effect size and sample count.
 *
 * Confidence increases with:
 * - Larger effect sizes (more obvious patterns)
 * - More samples (statistical significance)
 *
 * Formula: min(0.99, effectSize * log10(samples) / 2)
 *
 * @param {number} effectSize - Effect size (0-1)
 * @param {number} sampleCount - Number of samples
 * @returns {number} Confidence score (0-1)
 */
function calculateConfidence(effectSize, sampleCount) {
  if (sampleCount < MIN_SAMPLES) return 0;

  // Base confidence from effect size
  let confidence = effectSize;

  // Boost confidence based on sample count
  // log10(10) = 1.0, log10(100) = 2.0, log10(1000) = 3.0
  const sampleBoost = Math.log10(sampleCount) / 2;
  confidence *= sampleBoost;

  // Cap at 0.99 (never 100% certain)
  return Math.min(0.99, Math.max(0, confidence));
}

// ============================================================================
// DISCOVERY GENERATION
// ============================================================================

/**
 * Generate all discoveries from all sources.
 *
 * @param {object} options - Generation options
 * @param {number} options.minConfidence - Minimum confidence threshold
 * @param {number} options.minSamples - Minimum sample count
 * @returns {Promise<object[]>} Array of discoveries
 */
export async function discoverPatterns(options = {}) {
  const minConfidence = options.minConfidence || MIN_CONFIDENCE;

  const [thompsonPatterns, executionPatterns] = await Promise.all([
    discoverThompsonPatterns(),
    discoverExecutionPatterns(options),
  ]);

  // Combine and deduplicate
  const allPatterns = [...thompsonPatterns, ...executionPatterns];

  // Filter by confidence
  const filtered = allPatterns.filter(p => p.confidence >= minConfidence);

  // Deduplicate by pattern name (keep highest confidence)
  const deduped = {};
  for (const pattern of filtered) {
    const key = pattern.pattern;
    if (!deduped[key] || deduped[key].confidence < pattern.confidence) {
      deduped[key] = pattern;
    }
  }

  return Object.values(deduped);
}

/**
 * Generate discoveries and append to discoveries.json
 *
 * @param {object} options - Generation options
 * @returns {Promise<object>} Result with added count
 */
export async function generateAndApply(options = {}) {
  const newDiscoveries = await discoverPatterns(options);

  if (newDiscoveries.length === 0) {
    return {
      added: 0,
      total: 0,
      discoveries: [],
    };
  }

  // Load existing discoveries
  let data;
  try {
    data = await hotImportJSON(DISCOVERIES_PATH, {
      force: true,
      defaultValue: {
        version: 1,
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        notes: 'AI-discovered patterns and insights for model selection. Updated automatically by learning systems.',
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
  } catch (err) {
    console.error(`Error loading discoveries: ${err.message}`);
    return { added: 0, total: 0, discoveries: [] };
  }

  // Deduplicate against existing discoveries by ID
  const existingIds = new Set(data.discoveries.map(d => d.id));
  const toAdd = newDiscoveries.filter(d => !existingIds.has(d.id));

  if (toAdd.length === 0) {
    return {
      added: 0,
      total: data.discoveries.length,
      discoveries: [],
    };
  }

  // Append new discoveries
  data.discoveries.push(...toAdd);
  data.updated = new Date().toISOString();

  // Update metadata
  const activeCount = data.discoveries.filter(d => d.status === 'active').length;
  const inactiveCount = data.discoveries.filter(d => d.status === 'inactive').length;
  const avgConfidence = data.discoveries.reduce((sum, d) => sum + d.confidence, 0) / data.discoveries.length;

  data.metadata = {
    total_discoveries: data.discoveries.length,
    active_discoveries: activeCount,
    inactive_discoveries: inactiveCount,
    avg_confidence: avgConfidence,
    last_generated: new Date().toISOString(),
    apply_count: data.metadata?.apply_count || 0,
  };

  // Write back to file
  try {
    writeFileSync(DISCOVERIES_PATH, JSON.stringify(data, null, 2), 'utf-8');
  } catch (err) {
    console.error(`Error writing discoveries: ${err.message}`);
    return { added: 0, total: data.discoveries.length, discoveries: [] };
  }

  return {
    added: toAdd.length,
    total: data.discoveries.length,
    discoveries: toAdd,
  };
}

// ============================================================================
// CLI INTERFACE
// ============================================================================

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const shouldApply = args.includes('--apply');
  const minConfIdx = args.indexOf('--min-conf');
  const minConfidence = minConfIdx >= 0 ? parseFloat(args[minConfIdx + 1]) : MIN_CONFIDENCE;

  const options = { minConfidence };

  if (shouldApply) {
    // Generate and apply
    const result = await generateAndApply(options);

    console.log(`[discover-patterns] Discovery generation complete`);
    console.log(`  Added:    ${result.added} new discoveries`);
    console.log(`  Total:    ${result.total} discoveries`);
    console.log('');

    if (result.discoveries.length > 0) {
      console.log('--- NEW DISCOVERIES ---');
      for (const d of result.discoveries) {
        console.log(`  ${d.id}`);
        console.log(`    Pattern:     ${d.pattern}`);
        console.log(`    Description: ${d.description}`);
        console.log(`    Confidence:  ${(d.confidence * 100).toFixed(1)}%`);
        console.log(`    Evidence:    ${d.evidence_count} samples`);
        console.log(`    Source:      ${d.source}`);
        console.log('');
      }
    }
  } else {
    // Just print discoveries
    const discoveries = await discoverPatterns(options);

    console.log(`[discover-patterns] Found ${discoveries.length} patterns`);
    console.log('');

    for (const d of discoveries) {
      console.log(`${d.id}`);
      console.log(`  Pattern:     ${d.pattern}`);
      console.log(`  Description: ${d.description}`);
      console.log(`  Confidence:  ${(d.confidence * 100).toFixed(1)}%`);
      console.log(`  Evidence:    ${d.evidence_count} samples`);
      console.log(`  Source:      ${d.source}`);
      console.log('');
    }

    console.log('Run with --apply to add these to discoveries.json');
  }
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  discoverPatterns,
  generateAndApply,
};
