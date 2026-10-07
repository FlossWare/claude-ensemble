/**
 * Post-workflow hook: Extract and store learnings
 * Automatically runs after workflow completion
 *
 * Hook registration in settings.json:
 * {
 *   "hooks": {
 *     "workflow:complete": [
 *       "~/.claude/workflows/hooks/post-workflow-learning.js"
 *     ]
 *   }
 * }
 */

const { execSync } = require('child_process');
const { getExecutionMonitor } = require('~/.claude/learning/postgres-adapter');
const { storeLearnings } = require('~/.claude/learning/storage');

/**
 * Hook entry point
 * @param {object} context - Hook context
 * @param {string} context.workflowName - Name of completed workflow
 * @param {string} context.runId - Unique run identifier
 * @param {object} context.result - Workflow result object
 * @param {number} context.executionId - ID from monitoring.execution_summary
 * @param {string} context.status - Workflow status (success/failed/error)
 */
async function onWorkflowComplete(context) {
  const {
    workflowName,
    runId,
    result = {},
    executionId = null,
    status = 'success'
  } = context;

  // Skip learning extraction for the learning workflow itself (avoid recursion)
  if (workflowName === 'ai-extract-learning') {
    return;
  }

  // Only extract learnings from successful workflows
  // (Failed workflows can still be valuable, but need different analysis)
  if (status !== 'success') {
    console.log(`[hook] Skipping learning extraction for ${workflowName} (status: ${status})`);
    return;
  }

  // Check if workflow opted out of automatic learning
  if (result.skip_learning_extraction === true) {
    console.log(`[hook] Workflow ${workflowName} opted out of learning extraction`);
    return;
  }

  console.log(`[hook] Extracting learnings from ${workflowName}...`);

  try {
    // Build execution data for learning extraction
    const executionData = await buildExecutionData(workflowName, result, executionId);

    // Call ai-extract-learning workflow
    // Note: This is a simplified version - actual implementation would use workflow()
    // For now, we'll use a direct approach
    const { extractLearningsFromResult } = require('./learning-extractor');

    const learnings = await extractLearningsFromResult(workflowName, executionData);

    if (!learnings) {
      console.log(`[hook] No learnings extracted from ${workflowName}`);
      return;
    }

    // Store learnings in database
    const learningId = await storeLearnings(runId, learnings, {
      executionId,
      workflowName,
      strategy: 'auto-hook',
      qualityScore: result.quality_score || null
    });

    console.log(`[hook] Stored learning #${learningId} for ${workflowName}`);

    // Log high-priority memory suggestions
    if (learnings.memory_suggestions?.length > 0) {
      const highPriority = learnings.memory_suggestions.filter(s => s.priority === 'high');
      if (highPriority.length > 0) {
        console.log(`[hook] 🔴 ${highPriority.length} high-priority memory suggestions:`);
        highPriority.forEach(s => {
          console.log(`  [${s.type}] ${s.content}`);
        });
      }
    }

  } catch (err) {
    console.error(`[hook] Failed to extract learnings from ${workflowName}:`, err.message);
    // Don't throw - hooks should not break workflow execution
  }
}

/**
 * Build execution data for learning extraction
 * Fetches execution details from database and combines with result
 */
async function buildExecutionData(workflowName, result, executionId) {
  const data = {
    ...result
  };

  // If we have executionId, fetch execution details
  if (executionId) {
    try {
      const monitor = getExecutionMonitor();
      const execution = await monitor.db.get(
        'SELECT * FROM monitoring.execution_summary WHERE id = $1',
        [executionId]
      );

      if (execution) {
        data.model = execution.model;
        data.quality_score = execution.quality_score;
        data.duration_ms = execution.duration_ms;
        data.input_tokens = execution.input_tokens;
        data.output_tokens = execution.output_tokens;
        data.outcome = execution.outcome;
      }
    } catch (err) {
      console.warn(`[hook] Could not fetch execution details:`, err.message);
    }
  }

  return data;
}

module.exports = {
  onWorkflowComplete
};
