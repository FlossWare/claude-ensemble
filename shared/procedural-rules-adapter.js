#!/usr/bin/env node

/**
 * Procedural Rules Adapter (JavaScript)
 *
 * Extracts and queries procedural rules from successful executions.
 * Wires into learning.procedural_rules table.
 *
 * Created: 2026-07-01 (Issue #253)
 */

import pg from 'pg';
import crypto from 'crypto';

const { Pool } = pg;

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD
});

/**
 * Extract procedural rule from successful execution
 *
 * @param {Object} rule - Rule data
 * @param {Object} rule.condition - Condition dict (task_type, language, framework, etc.)
 * @param {string} rule.action - Action to take when condition matches
 * @param {number} rule.confidence - Confidence score (0-1)
 * @param {number} rule.evidence_count - Number of observations (default: 1)
 *
 * @example
 * await recordProceduralRule({
 *   condition: {
 *     task_type: 'code_generation',
 *     language: 'java',
 *     framework: 'maven'
 *   },
 *   action: 'use_deepseek_coder',
 *   confidence: 0.92,
 *   evidence_count: 5
 * });
 */
export async function recordProceduralRule(rule) {
  const { condition, action, confidence, evidence_count = 1 } = rule;

  // Create deterministic hash
  const conditionHash = crypto
    .createHash('sha256')
    .update(JSON.stringify(condition, Object.keys(condition).sort()))
    .digest('hex')
    .slice(0, 16);

  try {
    await pool.query(`
      INSERT INTO learning.procedural_rules
      (condition_hash, condition, action, confidence, evidence_count)
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (condition_hash, action) DO UPDATE SET
        confidence = GREATEST(procedural_rules.confidence, EXCLUDED.confidence),
        evidence_count = procedural_rules.evidence_count + EXCLUDED.evidence_count,
        last_updated = NOW()
    `, [conditionHash, JSON.stringify(condition), action, confidence, evidence_count]);

    return { success: true, condition_hash: conditionHash };
  } catch (error) {
    console.error('Failed to record procedural rule:', error.message);
    return { success: false, error: error.message };
  }
}

/**
 * Query procedural rules matching condition
 *
 * @param {Object} condition - Condition to match
 * @param {number} minConfidence - Minimum confidence threshold (default: 0.7)
 * @returns {Promise<Array>} Matching rules sorted by confidence
 *
 * @example
 * const rules = await queryProceduralRules(
 *   { task_type: 'code_generation', language: 'java' },
 *   0.8
 * );
 */
export async function queryProceduralRules(condition, minConfidence = 0.7) {
  const conditionHash = crypto
    .createHash('sha256')
    .update(JSON.stringify(condition, Object.keys(condition).sort()))
    .digest('hex')
    .slice(0, 16);

  try {
    // Try exact match first
    let result = await pool.query(`
      SELECT condition, action, confidence, evidence_count, last_updated
      FROM learning.procedural_rules
      WHERE condition_hash = $1 AND confidence >= $2
      ORDER BY confidence DESC, evidence_count DESC
    `, [conditionHash, minConfidence]);

    if (result.rows.length > 0) {
      return result.rows.map(row => {
        const parsed = typeof row.condition === 'string' ? JSON.parse(row.condition) : row.condition;
        return {
          condition: parsed,
          action: row.action,
          confidence: row.confidence,
          evidence_count: row.evidence_count,
          last_updated: row.last_updated
        };
      });
    }

    // Fallback: JSONB containment
    result = await pool.query(`
      SELECT condition, action, confidence, evidence_count, last_updated
      FROM learning.procedural_rules
      WHERE condition @> $1::jsonb AND confidence >= $2
      ORDER BY confidence DESC, evidence_count DESC
      LIMIT 10
    `, [JSON.stringify(condition), minConfidence]);

    return result.rows.map(row => {
      const parsed = typeof row.condition === 'string' ? JSON.parse(row.condition) : row.condition;
      return {
        condition: parsed,
        action: row.action,
        confidence: row.confidence,
        evidence_count: row.evidence_count,
        last_updated: row.last_updated
      };
    });
  } catch (error) {
    console.error('Failed to query procedural rules:', error.message);
    return [];
  }
}

/**
 * Extract rules from execution summary data
 *
 * Analyzes monitoring.execution_summary for patterns and creates rules
 *
 * @param {Object} filters - Filters for execution data
 * @param {number} filters.minQuality - Minimum quality score (default: 0.75)
 * @param {number} filters.minConfidence - Minimum confidence (default: 0.7)
 * @param {number} filters.limit - Max executions to analyze (default: 100)
 * @returns {Promise<Object>} Extraction results
 */
export async function extractRulesFromExecutions(filters = {}) {
  const { minQuality = 0.75, minConfidence = 0.7, limit = 100 } = filters;

  try {
    // Get successful executions with high quality
    const result = await pool.query(`
      SELECT model, workflow, task_type, quality_score, outcome
      FROM monitoring.execution_summary
      WHERE outcome = 'success'
        AND quality_score >= $1
      ORDER BY quality_score DESC
      LIMIT $2
    `, [minQuality, limit]);

    const executions = result.rows;
    const rulesCreated = [];

    // Group by (workflow, task_type) → model
    const patterns = {};

    for (const exec of executions) {
      if (!exec.workflow || !exec.task_type) continue;

      const key = `${exec.workflow}::${exec.task_type}`;
      if (!patterns[key]) {
        patterns[key] = {};
      }

      if (!patterns[key][exec.model]) {
        patterns[key][exec.model] = { count: 0, totalQuality: 0 };
      }

      patterns[key][exec.model].count++;
      patterns[key][exec.model].totalQuality += exec.quality_score;
    }

    // Create rules for strong patterns
    for (const [key, models] of Object.entries(patterns)) {
      const [workflow, taskType] = key.split('::');

      for (const [model, stats] of Object.entries(models)) {
        const avgQuality = stats.totalQuality / stats.count;

        if (stats.count >= 2 && avgQuality >= minQuality) {
          const condition = { workflow, task_type: taskType };
          const action = `use_model_${model}`;
          const confidence = Math.min(0.95, avgQuality);

          const ruleResult = await recordProceduralRule({
            condition,
            action,
            confidence,
            evidence_count: stats.count
          });

          if (ruleResult.success) {
            rulesCreated.push({
              condition,
              action,
              confidence,
              evidence_count: stats.count
            });
          }
        }
      }
    }

    return {
      executions_analyzed: executions.length,
      patterns_found: Object.keys(patterns).length,
      rules_created: rulesCreated.length,
      rules: rulesCreated
    };
  } catch (error) {
    console.error('Failed to extract rules from executions:', error.message);
    return { error: error.message };
  }
}

/**
 * Get recommended action for a given condition
 *
 * @param {Object} condition - Current task condition
 * @param {number} minConfidence - Minimum confidence threshold (default: 0.7)
 * @returns {Promise<Object|null>} Recommended action or null
 *
 * @example
 * const recommendation = await getRecommendedAction({
 *   workflow: 'code-generation',
 *   task_type: 'java_maven'
 * });
 * // Returns: { action: 'use_model_deepseek', confidence: 0.92, evidence_count: 10 }
 */
export async function getRecommendedAction(condition, minConfidence = 0.7) {
  const rules = await queryProceduralRules(condition, minConfidence);

  if (rules.length === 0) {
    return null;
  }

  // Return highest confidence rule
  const topRule = rules[0];
  return {
    action: topRule.action,
    confidence: topRule.confidence,
    evidence_count: topRule.evidence_count,
    last_updated: topRule.last_updated
  };
}

/**
 * Close the connection pool
 */
export async function closePool() {
  await pool.end();
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('Procedural Rules Adapter');
  console.log('Usage:');
  console.log('  import { recordProceduralRule, queryProceduralRules, extractRulesFromExecutions } from "./procedural-rules-adapter.js"');
  console.log('\nExample: Extract rules from recent executions');

  const result = await extractRulesFromExecutions({ minQuality: 0.75, limit: 100 });
  console.log('\nExtraction Results:');
  console.log(JSON.stringify(result, null, 2));

  await closePool();
}
