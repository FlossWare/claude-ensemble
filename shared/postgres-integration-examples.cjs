#!/usr/bin/env node

/**
 * PostgreSQL Table Integration Examples
 *
 * Demonstrates usage of the four previously-unused tables:
 * - learning.diversity_violations
 * - learning.procedural_rules
 * - monitoring.execution_log
 * - monitoring.model_tuning
 *
 * Created: 2026-07-01 (Issues #251-254)
 */

const {
  recordDiversityViolation,
  queryDiversityViolations,
  calculateDiversityEntropy,
  recordProceduralRule,
  queryProceduralRules,
  logExecution,
  queryExecutionLog,
  recordModelTuning,
  queryModelTuning,
  pool
} = require('./postgres-table-integrations.cjs');

// ============================================================================
// EXAMPLE 1: DIVERSITY ENFORCEMENT
// ============================================================================

async function exampleDiversityEnforcement() {
  console.log('\n========================================');
  console.log('EXAMPLE 1: Diversity Enforcement');
  console.log('========================================\n');

  // Simulate model usage distribution
  const modelUsage = {
    'opus': 72,
    'sonnet': 18,
    'haiku': 8,
    'gpt-4o': 2
  };

  console.log('Current model usage:', modelUsage);

  // Calculate diversity entropy
  const entropy = calculateDiversityEntropy(modelUsage);
  console.log(`Diversity entropy: ${entropy.toFixed(3)} (lower = less diverse)\n`);

  // Check for ceiling violations (>70% usage)
  const total = Object.values(modelUsage).reduce((sum, count) => sum + count, 0);
  for (const [model, count] of Object.entries(modelUsage)) {
    const percentage = (count / total) * 100;
    if (percentage > 70) {
      console.log(`⚠ VIOLATION: ${model} exceeds 70% ceiling (${percentage.toFixed(1)}%)`);

      await recordDiversityViolation({
        violation_type: 'ceiling_breach',
        model: model,
        current_usage_pct: percentage,
        quota_limit_pct: 70,
        diversity_entropy: entropy,
        action_taken: 'forced_rotation'
      });

      console.log(`✓ Violation recorded, action: forced_rotation\n`);
    }
  }

  // Query recent violations
  const violations = await queryDiversityViolations({ limit: 5 });
  console.log(`Recent violations (last 5):`);
  violations.forEach(v => {
    console.log(`  - ${v.timestamp.toISOString().substring(0, 19)}: ${v.model} ${v.violation_type} (${v.current_usage_pct.toFixed(1)}%) → ${v.action_taken}`);
  });
}

// ============================================================================
// EXAMPLE 2: PROCEDURAL RULE LEARNING
// ============================================================================

async function exampleProceduralRules() {
  console.log('\n========================================');
  console.log('EXAMPLE 2: Procedural Rule Learning');
  console.log('========================================\n');

  // Record a successful pattern: Java code generation works best with deepseek-coder
  console.log('Recording rule: Java code generation → use deepseek-coder');
  await recordProceduralRule({
    condition: {
      task_type: 'code_generation',
      language: 'java',
      framework: 'maven',
      input_tokens_range: [1000, 5000]
    },
    action: 'use_deepseek_coder',
    confidence: 0.92,
    evidence_count: 5
  });
  console.log('✓ Rule recorded\n');

  // Record another pattern: Security reviews work best with opus
  console.log('Recording rule: Security review → use opus');
  await recordProceduralRule({
    condition: {
      task_type: 'security_review',
      severity: 'high',
      codebase_size: 'large'
    },
    action: 'use_opus',
    confidence: 0.88,
    evidence_count: 12
  });
  console.log('✓ Rule recorded\n');

  // Query for Java code generation rules
  console.log('Querying rules for: task_type=code_generation, language=java');
  const javaRules = await queryProceduralRules({
    task_type: 'code_generation',
    language: 'java'
  }, 0.8);

  if (javaRules.length > 0) {
    console.log(`Found ${javaRules.length} rule(s):`);
    javaRules.forEach(rule => {
      console.log(`  - Action: ${rule.action}`);
      console.log(`    Confidence: ${rule.confidence}`);
      console.log(`    Evidence: ${rule.evidence_count} observations`);
      console.log(`    Condition:`, rule.condition);
    });
  } else {
    console.log('No matching rules found');
  }
}

// ============================================================================
// EXAMPLE 3: DETAILED EXECUTION LOGGING
// ============================================================================

async function exampleExecutionLogging() {
  console.log('\n========================================');
  console.log('EXAMPLE 3: Detailed Execution Logging');
  console.log('========================================\n');

  // Log a worker execution
  console.log('Logging worker execution (opus)...');
  await logExecution({
    model: 'opus',
    model_role: 'worker',
    workflow: 'code-review',
    task_type: 'security',
    phase: 'analysis',
    label: 'SQL injection check',
    parameters: {
      file_pattern: '**/*.java',
      severity_threshold: 'high'
    },
    quality_score: 0.92,
    confidence: 0.88,
    consensus_score: 0.85,
    was_selected: true,
    input_tokens: 1500,
    output_tokens: 800,
    cost_usd: 0.015,
    duration_ms: 4200,
    outcome: 'SUCCESS',
    run_id: 'review-2026-07-01-001',
    execution_id: 'exec-001-worker-opus'
  });
  console.log('✓ Logged\n');

  // Log an arbiter execution
  console.log('Logging arbiter execution (sonnet)...');
  await logExecution({
    model: 'sonnet',
    model_role: 'arbiter',
    workflow: 'code-review',
    task_type: 'security',
    phase: 'synthesis',
    label: 'Select best security findings',
    worker_models: ['opus', 'gpt-4o', 'gemini-2.0-flash-exp'],
    selected_model: 'opus',
    quality_score: 0.90,
    confidence: 0.87,
    input_tokens: 5000,
    output_tokens: 1200,
    cost_usd: 0.018,
    duration_ms: 3800,
    outcome: 'SUCCESS',
    run_id: 'review-2026-07-01-001',
    execution_id: 'exec-001-arbiter-sonnet',
    selection_method: 'contextual_bandit'
  });
  console.log('✓ Logged\n');

  // Query recent executions
  console.log('Recent executions (last 5):');
  const executions = await queryExecutionLog({ limit: 5 });
  executions.forEach(exec => {
    console.log(`  - ${exec.timestamp.toISOString().substring(0, 19)}: ${exec.model} (${exec.model_role})`);
    console.log(`    Workflow: ${exec.workflow} / ${exec.task_type}`);
    console.log(`    Quality: ${exec.quality_score ? exec.quality_score.toFixed(2) : 'N/A'}, Outcome: ${exec.outcome}`);
    console.log(`    Tokens: ${exec.input_tokens}→${exec.output_tokens}, Cost: $${exec.cost_usd.toFixed(4)}`);
  });
}

// ============================================================================
// EXAMPLE 4: MODEL TUNING HISTORY
// ============================================================================

async function exampleModelTuning() {
  console.log('\n========================================');
  console.log('EXAMPLE 4: Model Tuning History');
  console.log('========================================\n');

  // Record tuning results for opus on security tasks
  console.log('Recording tuning for opus on security_review...');
  await recordModelTuning({
    model: 'opus',
    task_type: 'security_review',
    optimal_params: {
      temperature: 0.3,
      top_p: 0.9,
      max_tokens: 2000,
      presence_penalty: 0.1
    },
    avg_quality: 0.92,
    avg_confidence: 0.88,
    avg_cost_usd: 0.015,
    avg_duration_ms: 4200,
    sample_count: 50,
    success_rate: 0.94,
    selection_rate: 0.68,
    quality_trend: [0.85, 0.87, 0.90, 0.92],
    cost_trend: [0.018, 0.017, 0.016, 0.015]
  });
  console.log('✓ Recorded\n');

  // Record tuning for sonnet on code generation
  console.log('Recording tuning for sonnet on code_generation...');
  await recordModelTuning({
    model: 'sonnet',
    task_type: 'code_generation',
    optimal_params: {
      temperature: 0.5,
      top_p: 0.95,
      max_tokens: 3000
    },
    avg_quality: 0.85,
    avg_confidence: 0.82,
    avg_cost_usd: 0.008,
    avg_duration_ms: 3500,
    sample_count: 75,
    success_rate: 0.88,
    selection_rate: 0.45,
    quality_trend: [0.80, 0.82, 0.84, 0.85],
    cost_trend: [0.010, 0.009, 0.009, 0.008]
  });
  console.log('✓ Recorded\n');

  // Query tuning for security_review
  console.log('Querying tuning history for security_review:');
  const securityTuning = await queryModelTuning({ task_type: 'security_review' });
  securityTuning.forEach(tuning => {
    console.log(`  - ${tuning.model}:`);
    console.log(`    Optimal params:`, tuning.optimal_params);
    console.log(`    Quality: ${tuning.avg_quality.toFixed(3)}, Success: ${(tuning.success_rate * 100).toFixed(1)}%`);
    console.log(`    Cost: $${tuning.avg_cost_usd.toFixed(4)}, Duration: ${tuning.avg_duration_ms}ms`);
    console.log(`    Samples: ${tuning.sample_count}, Last updated: ${tuning.updated_at.toISOString().substring(0, 19)}`);
  });
}

// ============================================================================
// SAMPLE QUERIES
// ============================================================================

async function sampleQueries() {
  console.log('\n========================================');
  console.log('SAMPLE QUERIES');
  console.log('========================================\n');

  console.log('1. Models with most diversity violations (last 30 days):\n');
  const violationStats = await pool.query(`
    SELECT model, violation_type, COUNT(*) as count, AVG(current_usage_pct) as avg_usage
    FROM learning.diversity_violations
    WHERE timestamp > NOW() - INTERVAL '30 days'
    GROUP BY model, violation_type
    ORDER BY count DESC
    LIMIT 5
  `);
  violationStats.rows.forEach(row => {
    console.log(`   ${row.model}: ${row.count} ${row.violation_type} violations (avg ${row.avg_usage.toFixed(1)}%)`);
  });

  console.log('\n2. Most reliable procedural rules (confidence > 0.8, evidence > 10):\n');
  const reliableRules = await pool.query(`
    SELECT action, confidence, evidence_count, last_updated
    FROM learning.procedural_rules
    WHERE confidence > 0.8 AND evidence_count > 10
    ORDER BY confidence DESC, evidence_count DESC
    LIMIT 5
  `);
  reliableRules.rows.forEach(row => {
    console.log(`   ${row.action}: confidence=${row.confidence.toFixed(3)}, evidence=${row.evidence_count}`);
  });

  console.log('\n3. Model selection rates by workflow (from execution_log):\n');
  const selectionRates = await pool.query(`
    SELECT model, workflow,
           COUNT(*) as total,
           SUM(CASE WHEN was_selected THEN 1 ELSE 0 END) as selected,
           (SUM(CASE WHEN was_selected THEN 1 ELSE 0 END)::float / COUNT(*) * 100) as selection_pct
    FROM monitoring.execution_log
    WHERE workflow IS NOT NULL
    GROUP BY model, workflow
    HAVING COUNT(*) > 5
    ORDER BY selection_pct DESC
    LIMIT 10
  `);
  selectionRates.rows.forEach(row => {
    console.log(`   ${row.model} in ${row.workflow}: ${row.selection_pct.toFixed(1)}% (${row.selected}/${row.total})`);
  });

  console.log('\n4. Model tuning quality improvements over time:\n');
  const tuningImprovements = await pool.query(`
    SELECT model, task_type,
           quality_trend->0 as initial_quality,
           quality_trend->-1 as final_quality,
           (quality_trend->-1)::float - (quality_trend->0)::float as improvement
    FROM monitoring.model_tuning
    WHERE jsonb_array_length(quality_trend) >= 2
    ORDER BY improvement DESC
    LIMIT 5
  `);
  tuningImprovements.rows.forEach(row => {
    console.log(`   ${row.model} (${row.task_type}): ${row.initial_quality} → ${row.final_quality} (+${(parseFloat(row.improvement) * 100).toFixed(1)}%)`);
  });

  console.log('\n5. Cost efficiency by model (from execution_log):\n');
  const costEfficiency = await pool.query(`
    SELECT model,
           COUNT(*) as executions,
           AVG(quality_score) as avg_quality,
           AVG(cost_usd) as avg_cost,
           (AVG(quality_score) / NULLIF(AVG(cost_usd), 0)) as quality_per_dollar
    FROM monitoring.execution_log
    WHERE outcome = 'SUCCESS' AND cost_usd > 0
    GROUP BY model
    HAVING COUNT(*) > 5
    ORDER BY quality_per_dollar DESC
    LIMIT 5
  `);
  costEfficiency.rows.forEach(row => {
    console.log(`   ${row.model}: ${row.avg_quality.toFixed(3)} quality @ $${row.avg_cost.toFixed(4)} (${row.quality_per_dollar.toFixed(0)} quality/$)`);
  });
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  try {
    await exampleDiversityEnforcement();
    await exampleProceduralRules();
    await exampleExecutionLogging();
    await exampleModelTuning();
    await sampleQueries();

    console.log('\n========================================');
    console.log('All examples complete!');
    console.log('========================================\n');

  } catch (error) {
    console.error('Error:', error.message);
    console.error(error.stack);
  } finally {
    await pool.end();
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  exampleDiversityEnforcement,
  exampleProceduralRules,
  exampleExecutionLogging,
  exampleModelTuning,
  sampleQueries
};
