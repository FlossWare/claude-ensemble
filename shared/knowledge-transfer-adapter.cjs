/**
 * Knowledge Transfer Optimizer Adapter
 *
 * JavaScript adapter for Python-based knowledge transfer optimizer.
 * Integrates with workflow orchestration to inject prior knowledge into new tasks.
 *
 * Usage:
 *   const { createTransferPlan, applyTransferPlan, evaluateEffectiveness } = require('./shared/knowledge-transfer-adapter.cjs');
 *
 *   // Before workflow execution
 *   const plan = await createTransferPlan('Reverse engineer firmware binary');
 *
 *   // Execute workflow with context
 *   const execId = await db.storeExecution({ ... });
 *   await applyTransferPlan(plan, execId);
 *
 *   // Evaluate effectiveness
 *   const stats = await evaluateEffectiveness(30);
 *
 * Created: 2026-07-03
 */

const { spawn } = require('child_process');
const { promisify } = require('util');
const path = require('path');

const OPTIMIZER_SCRIPT = path.join(
  __dirname,
  '..',
  'tools',
  'knowledge_transfer_optimizer.py'
);

/**
 * Execute Python optimizer script and parse JSON output
 *
 * @param {string[]} args - Command-line arguments
 * @param {string|null} stdin - Optional stdin data
 * @returns {Promise<any>} Parsed JSON output
 */
async function _executePython(args, stdin = null) {
  return new Promise((resolve, reject) => {
    const proc = spawn('python3', [OPTIMIZER_SCRIPT, ...args], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Optimizer failed (exit ${code}): ${stderr}`));
        return;
      }

      try {
        // Extract JSON from output (may have text before/after)
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const result = JSON.parse(jsonMatch[0]);
          resolve(result);
        } else {
          // No JSON found, return raw output
          resolve({ stdout, stderr });
        }
      } catch (err) {
        reject(new Error(`Failed to parse JSON output: ${err.message}\n${stdout}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn optimizer: ${err.message}`));
    });

    if (stdin) {
      proc.stdin.write(stdin);
      proc.stdin.end();
    }
  });
}

/**
 * Create knowledge transfer plan for a new task
 *
 * Retrieves similar workflows, assesses transfer potential, and distills
 * key learnings to inject as context.
 *
 * @param {string} taskDescription - Task to execute
 * @param {Object} options - Options
 * @param {boolean} options.forceRefresh - Bypass cache (default: false)
 * @param {string} options.outputFile - Save plan to file
 * @returns {Promise<Object>} Transfer plan
 *
 * Example:
 *   const plan = await createTransferPlan('Fix authentication bug', { forceRefresh: true });
 *   console.log(plan.key_learnings);
 *   console.log(plan.estimated_duration_ms);
 */
async function createTransferPlan(taskDescription, options = {}) {
  const args = ['--quiet', '--output', '/tmp/transfer-plan.json'];

  if (options.forceRefresh) {
    args.push('--force-refresh');
  }

  args.push(taskDescription);

  try {
    await _executePython(args);

    // Read the output file
    const fs = require('fs');
    const planJson = fs.readFileSync('/tmp/transfer-plan.json', 'utf-8');
    const plan = JSON.parse(planJson);

    // Convert ISO date strings back to Date objects
    plan.created_at = new Date(plan.created_at);
    plan.positive_transfers = plan.positive_transfers.map(tc => ({
      ...tc,
      created_at: new Date(tc.created_at)
    }));
    plan.negative_transfers = plan.negative_transfers.map(tc => ({
      ...tc,
      created_at: new Date(tc.created_at)
    }));

    return plan;
  } catch (err) {
    console.warn(`[knowledge-transfer] Failed to create plan: ${err.message}`);
    // Return empty plan on failure
    return {
      task_description: taskDescription,
      task_hash: '',
      candidates_retrieved: 0,
      positive_transfers: [],
      negative_transfers: [],
      key_learnings: [],
      common_patterns: {},
      common_pitfalls: {},
      recommended_models: [],
      estimated_duration_ms: null,
      estimated_confidence: 0.5,
      created_at: new Date(),
      retrieval_duration_ms: 0,
      assessment_duration_ms: 0
    };
  }
}

/**
 * Apply transfer plan to a workflow execution
 *
 * Records which prior knowledge was used for the workflow, allowing
 * measurement of transfer effectiveness over time.
 *
 * @param {Object} plan - Transfer plan from createTransferPlan()
 * @param {number} workflowExecutionId - Workflow execution ID
 * @returns {Promise<void>}
 *
 * Example:
 *   const plan = await createTransferPlan('Fix bug');
 *   const execId = await db.storeExecution({ ... });
 *   await applyTransferPlan(plan, execId);
 */
async function applyTransferPlan(plan, workflowExecutionId) {
  const args = [
    '--quiet',
    '--output', '/tmp/transfer-plan-applied.json',
    '--apply', String(workflowExecutionId),
    plan.task_description
  ];

  try {
    await _executePython(args);
  } catch (err) {
    console.warn(`[knowledge-transfer] Failed to apply plan: ${err.message}`);
    // Non-fatal - continue workflow execution
  }
}

/**
 * Evaluate knowledge transfer effectiveness
 *
 * Compares workflows that used context vs those that didn't:
 * - Success rate improvement
 * - Duration improvement
 * - Confidence improvement
 *
 * @param {number} windowDays - Analysis window in days (default: 30)
 * @returns {Promise<Object>} Effectiveness statistics
 *
 * Example:
 *   const stats = await evaluateEffectiveness(30);
 *   console.log(stats.improvement.success_rate_delta);  // +15.3%
 */
async function evaluateEffectiveness(windowDays = 30) {
  const args = [
    '--evaluate',
    '--window', String(windowDays),
    '--output', '/tmp/transfer-effectiveness.json',
    '--quiet'
  ];

  try {
    await _executePython(args);

    const fs = require('fs');
    const statsJson = fs.readFileSync('/tmp/transfer-effectiveness.json', 'utf-8');
    return JSON.parse(statsJson);
  } catch (err) {
    console.warn(`[knowledge-transfer] Failed to evaluate effectiveness: ${err.message}`);
    return {
      with_context: { total: 0, success_rate: 0.5 },
      no_context: { total: 0, success_rate: 0.5 },
      improvement: { success_rate_delta: 0.0 }
    };
  }
}

/**
 * Format transfer plan as context string for injection into workflow prompt
 *
 * @param {Object} plan - Transfer plan
 * @param {Object} options - Formatting options
 * @param {number} options.maxLearnings - Max learnings to include (default: 5)
 * @param {number} options.maxPatterns - Max patterns to include (default: 3)
 * @returns {string} Formatted context string
 *
 * Example:
 *   const plan = await createTransferPlan('Implement OAuth2');
 *   const context = formatAsContext(plan, { maxLearnings: 3 });
 *   const prompt = `Task: ${task}\n\nPrior Knowledge:\n${context}`;
 */
function formatAsContext(plan, options = {}) {
  const maxLearnings = options.maxLearnings || 5;
  const maxPatterns = options.maxPatterns || 3;

  let context = '';

  // Estimated duration
  if (plan.estimated_duration_ms) {
    context += `Estimated Duration: ${(plan.estimated_duration_ms / 1000).toFixed(1)}s\n`;
    context += `Estimated Confidence: ${(plan.estimated_confidence * 100).toFixed(0)}%\n\n`;
  }

  // Key learnings from similar tasks
  if (plan.key_learnings.length > 0) {
    context += 'Key Learnings from Similar Tasks:\n';
    plan.key_learnings.slice(0, maxLearnings).forEach((learning, i) => {
      context += `${i + 1}. [${learning.learning_type}] ${learning.description}\n`;
      context += `   → ${learning.actionable_insight}\n`;
    });
    context += '\n';
  }

  // Common success patterns
  if (Object.keys(plan.common_patterns).length > 0) {
    context += 'Common Success Patterns:\n';
    const patterns = Object.entries(plan.common_patterns)
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxPatterns);
    patterns.forEach(([pattern, count]) => {
      context += `- ${pattern} (${count}x)\n`;
    });
    context += '\n';
  }

  // Common pitfalls to avoid
  if (Object.keys(plan.common_pitfalls).length > 0) {
    context += 'Common Pitfalls to Avoid:\n';
    const pitfalls = Object.entries(plan.common_pitfalls)
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxPatterns);
    pitfalls.forEach(([pitfall, count]) => {
      context += `- ${pitfall} (${count}x)\n`;
    });
    context += '\n';
  }

  // Recommended models
  if (plan.recommended_models.length > 0) {
    context += 'Recommended Models:\n';
    plan.recommended_models.slice(0, 3).forEach(([model, rate]) => {
      context += `- ${model}: ${(rate * 100).toFixed(0)}% success\n`;
    });
    context += '\n';
  }

  return context;
}

/**
 * Pre-workflow hook: load context before execution
 *
 * Call this before workflow execution to inject prior knowledge.
 *
 * @param {string} taskDescription - Task to execute
 * @param {Object} options - Options
 * @param {boolean} options.applyAfterCreation - Auto-apply after workflow created (default: false)
 * @param {boolean} options.includeContext - Include formatted context in return (default: true)
 * @returns {Promise<Object>} { plan, context }
 *
 * Example:
 *   const { plan, context } = await beforeWorkflow('Fix auth bug');
 *   const prompt = `Task: ${task}\n\nContext:\n${context}`;
 */
async function beforeWorkflow(taskDescription, options = {}) {
  const plan = await createTransferPlan(taskDescription);

  const result = {
    plan,
    context: options.includeContext !== false ? formatAsContext(plan) : ''
  };

  return result;
}

/**
 * Post-workflow hook: record context usage
 *
 * Call this after workflow execution to record which context was used.
 *
 * @param {Object} plan - Transfer plan from beforeWorkflow()
 * @param {number} workflowExecutionId - Workflow execution ID
 * @returns {Promise<void>}
 *
 * Example:
 *   const { plan } = await beforeWorkflow('Fix bug');
 *   // ... execute workflow ...
 *   const execId = await db.storeExecution({ ... });
 *   await afterWorkflow(plan, execId);
 */
async function afterWorkflow(plan, workflowExecutionId) {
  await applyTransferPlan(plan, workflowExecutionId);
}

/**
 * Check if knowledge transfer is improving outcomes
 *
 * Quick health check to see if context injection is helping.
 *
 * @param {number} windowDays - Analysis window in days (default: 30)
 * @returns {Promise<boolean>} True if context is improving success rate
 */
async function isTransferEffective(windowDays = 30) {
  try {
    const stats = await evaluateEffectiveness(windowDays);

    // Effective if success rate improves by at least 5%
    return stats.improvement?.success_rate_delta >= 0.05;
  } catch (err) {
    console.warn(`[knowledge-transfer] Health check failed: ${err.message}`);
    return false;
  }
}

module.exports = {
  createTransferPlan,
  applyTransferPlan,
  evaluateEffectiveness,
  formatAsContext,
  beforeWorkflow,
  afterWorkflow,
  isTransferEffective
};
