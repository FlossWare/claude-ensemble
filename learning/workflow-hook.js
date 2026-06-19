/**
 * Workflow Completion Hook
 * Automatically logs workflow executions to PostgreSQL
 *
 * Usage: Import and call logWorkflowExecution() at the end of any consensus workflow
 */

const { getWorkflowStorage } = require('./workflow-storage');

/**
 * Log a complete workflow execution
 * Call this at the end of ai-consensus-* workflows
 *
 * @param {Object} data - Workflow execution data
 * @param {string} data.workflow_type - Type of consensus workflow
 * @param {string} data.prompt - Original user prompt
 * @param {Array} data.workers - Array of worker results [{model, response, confidence, ...}]
 * @param {Object} data.arbiter - Arbiter decision {model, response, confidence, votes, reasoning}
 * @param {number} data.duration_ms - Total execution time
 * @param {number} data.total_cost_usd - Total API cost
 * @param {string} data.outcome - 'success', 'failed', or 'error'
 * @param {Object} data.metadata - Additional context
 */
async function logWorkflowExecution(data) {
  const storage = getWorkflowStorage();

  try {
    // 1. Log execution start
    const execution_id = await storage.logExecutionStart({
      workflow_type: data.workflow_type,
      prompt: data.prompt,
      metadata: data.metadata
    });

    // 2. Log all worker results
    for (const worker of data.workers) {
      await storage.logWorkerResult({
        execution_id,
        model: worker.model,
        response: worker.response,
        confidence: worker.confidence,
        quality_score: worker.quality_score,
        input_tokens: worker.input_tokens,
        output_tokens: worker.output_tokens,
        cost_usd: worker.cost_usd,
        duration_ms: worker.duration_ms,
        metadata: worker.metadata
      });
    }

    // 3. Log arbiter decision
    await storage.logArbiterDecision({
      execution_id,
      arbiter_model: data.arbiter.model,
      final_response: data.arbiter.response,
      confidence: data.arbiter.confidence,
      worker_votes: data.arbiter.votes,
      reasoning: data.arbiter.reasoning,
      input_tokens: data.arbiter.input_tokens,
      output_tokens: data.arbiter.output_tokens,
      cost_usd: data.arbiter.cost_usd,
      duration_ms: data.arbiter.duration_ms
    });

    // 4. Update execution end
    await storage.logExecutionEnd(execution_id, {
      duration_ms: data.duration_ms,
      total_cost_usd: data.total_cost_usd,
      outcome: data.outcome
    });

    // 5. Refresh materialized views (async, don't wait)
    storage.refreshViews().catch(err => {
      console.warn('[workflow-hook] Failed to refresh views:', err.message);
    });

    return execution_id;

  } catch (error) {
    console.error('[workflow-hook] Failed to log workflow execution:', error.message);
    // Don't throw - logging failures shouldn't break the workflow
    return null;
  }
}

/**
 * Query similar past executions based on prompt
 * Useful for finding relevant historical results
 */
async function findSimilarExecutions(prompt, limit = 10) {
  const storage = getWorkflowStorage();
  return await storage.findSimilarExecutions(prompt, limit);
}

/**
 * Get workflow statistics
 */
async function getWorkflowStats() {
  const storage = getWorkflowStorage();
  const summary = await storage.getSummary();
  const modelPerf = await storage.getModelPerformance();

  return {
    summary,
    modelPerformance: modelPerf
  };
}

module.exports = {
  logWorkflowExecution,
  findSimilarExecutions,
  getWorkflowStats
};
