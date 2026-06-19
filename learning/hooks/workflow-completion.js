#!/usr/bin/env node

/**
 * Workflow Completion Hook
 *
 * Called after workflow completes to:
 * 1. Log execution summary to PostgreSQL
 * 2. Refresh model_performance materialized view
 * 3. Generate embeddings for experience memory (future)
 *
 * Usage:
 *   node workflow-completion.js <workflow-result.json>
 */

const { getExecutionMonitor, getDB, OUTCOMES } = require('../postgres-adapter.js');
const { readFileSync } = require('fs');

/**
 * Process workflow result and update database
 * @param {Object} result - Workflow result object
 */
async function processWorkflowCompletion(result) {
  const db = getDB();
  const monitor = getExecutionMonitor();

  try {
    // Extract execution data from workflow result
    const {
      workflow,
      model,
      task_type,
      quality_score,
      input_tokens,
      output_tokens,
      cost_usd,
      duration_ms,
      outcome,
      metadata
    } = result;

    // Validate required fields
    if (!workflow || !model || !outcome) {
      console.error('[workflow-completion] Missing required fields:', { workflow, model, outcome });
      process.exit(1);
    }

    // Normalize outcome to standard values
    const normalizedOutcome = normalizeOutcome(outcome);

    // Log execution to monitoring.execution_summary
    console.log(`[workflow-completion] Logging execution: ${workflow} / ${model} / ${normalizedOutcome}`);

    await monitor.logExecution({
      model,
      workflow,
      task_type: task_type || 'unknown',
      quality_score: quality_score || null,
      input_tokens: input_tokens || 0,
      output_tokens: output_tokens || 0,
      cost_usd: cost_usd || 0,
      duration_ms: duration_ms || 0,
      outcome: normalizedOutcome,
      metadata: metadata || null
    });

    // Refresh model_performance materialized view
    console.log('[workflow-completion] Refreshing model_performance view...');
    await db.query('REFRESH MATERIALIZED VIEW monitoring.model_performance');

    // Check model diversity (alert if >70% dominance)
    const dominance = await monitor.checkModelDominance(100, 70);
    if (dominance.isDominant) {
      console.warn(`[workflow-completion] WARNING: Model dominance detected!`);
      console.warn(`  Model: ${dominance.model} (${dominance.percentage.toFixed(1)}%)`);
      console.warn(`  Distribution:`, dominance.distribution);
      console.warn(`  Consider forcing diversity to prevent feedback loops.`);
    }

    console.log('[workflow-completion] Success!');
    process.exit(0);
  } catch (err) {
    console.error('[workflow-completion] Error:', err.message);
    console.error(err.stack);
    process.exit(1);
  } finally {
    await db.close();
  }
}

/**
 * Normalize outcome to standard values (success/failed/error)
 * Prevents query mismatches due to inconsistent outcome naming
 */
function normalizeOutcome(outcome) {
  if (!outcome || typeof outcome !== 'string') {
    return OUTCOMES.ERROR;
  }

  const lower = outcome.toLowerCase();

  if (lower === 'success' || lower === 'pass' || lower === 'completed') {
    return OUTCOMES.SUCCESS;
  } else if (lower === 'failed' || lower === 'fail' || lower === 'failure') {
    return OUTCOMES.FAILED;
  } else if (lower === 'error') {
    return OUTCOMES.ERROR;
  } else {
    console.warn(`[workflow-completion] Unknown outcome: '${outcome}', defaulting to 'failed'`);
    return OUTCOMES.FAILED;
  }
}

// Main execution
const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('Usage: node workflow-completion.js <workflow-result.json>');
  console.error('');
  console.error('Example workflow result JSON:');
  console.error(JSON.stringify({
    workflow: 'deep-research',
    model: 'claude-opus-4',
    task_type: 'research',
    quality_score: 0.85,
    input_tokens: 15000,
    output_tokens: 3000,
    cost_usd: 0.45,
    duration_ms: 120000,
    outcome: 'success',
    metadata: { query: 'example research query' }
  }, null, 2));
  process.exit(1);
}

const resultFile = args[0];

try {
  const resultData = readFileSync(resultFile, 'utf8');
  const result = JSON.parse(resultData);
  processWorkflowCompletion(result);
} catch (err) {
  console.error('[workflow-completion] Failed to read result file:', err.message);
  process.exit(1);
}
