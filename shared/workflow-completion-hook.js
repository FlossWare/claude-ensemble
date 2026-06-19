/**
 * Workflow Completion Hook
 *
 * Automatically stores workflow execution data when workflows complete.
 * Integrates with existing workflow orchestrators.
 *
 * Usage:
 *   const { onWorkflowComplete } = require('./shared/workflow-completion-hook');
 *
 *   // At end of workflow
 *   await onWorkflowComplete({
 *     workflow_id: 'research-001',
 *     workflow_name: 'deep-research',
 *     task: 'Research quantum computing',
 *     workers: [...],
 *     arbiter: {...},
 *     phases: [...],
 *     duration_ms: 45000,
 *     outcome: 'success'
 *   });
 */

const { getWorkflowStorage } = require('./workflow-storage-adapter');

/**
 * Store complete workflow execution data
 *
 * @param {Object} data - Workflow completion data
 * @param {string} data.workflow_id - Unique workflow identifier
 * @param {string} data.workflow_name - Workflow name
 * @param {string} data.task - Original task/prompt
 * @param {Array} data.workers - Worker execution results
 * @param {Object} data.arbiter - Arbiter decision data
 * @param {Array} data.phases - Workflow phases
 * @param {number} data.duration_ms - Total execution time
 * @param {string} data.outcome - 'success' | 'failed' | 'error'
 * @param {Object} data.metadata - Additional metadata
 * @returns {Promise<number>} Workflow execution ID
 */
async function onWorkflowComplete(data) {
  const storage = getWorkflowStorage();

  try {
    // Store main execution
    const executionId = await storage.storeExecution({
      workflow_id: data.workflow_id,
      workflow_name: data.workflow_name,
      task_description: data.task,
      total_workers: data.workers?.length || 0,
      total_duration_ms: data.duration_ms,
      outcome: data.outcome,
      metadata: data.metadata || {}
    });

    console.log(`[workflow-storage] Stored execution ${data.workflow_id} (ID: ${executionId})`);

    // Store worker results
    if (data.workers && data.workers.length > 0) {
      const workerIds = [];
      for (const worker of data.workers) {
        const workerId = await storage.storeWorkerResult({
          workflow_execution_id: executionId,
          worker_id: worker.worker_id || worker.id,
          model: worker.model,
          task_assigned: worker.task || data.task,
          result: worker.result || worker.output,
          confidence: worker.confidence || 0.5,
          duration_ms: worker.duration_ms || 0,
          input_tokens: worker.input_tokens || 0,
          output_tokens: worker.output_tokens || 0,
          cost_usd: worker.cost_usd || 0,
          outcome: worker.outcome || 'success',
          metadata: worker.metadata || {}
        });
        workerIds.push(workerId);
      }
      console.log(`[workflow-storage] Stored ${workerIds.length} worker results`);
    }

    // Store arbiter decision
    if (data.arbiter) {
      const arbiterId = await storage.storeArbiterDecision({
        workflow_execution_id: executionId,
        arbiter_model: data.arbiter.model || 'unknown',
        worker_result_ids: data.arbiter.worker_result_ids || [],
        decision: data.arbiter.decision || data.arbiter.result,
        reasoning: data.arbiter.reasoning || '',
        confidence: data.arbiter.confidence || 0.5,
        duration_ms: data.arbiter.duration_ms || 0,
        input_tokens: data.arbiter.input_tokens || 0,
        output_tokens: data.arbiter.output_tokens || 0,
        cost_usd: data.arbiter.cost_usd || 0,
        metadata: data.arbiter.metadata || {}
      });
      console.log(`[workflow-storage] Stored arbiter decision (ID: ${arbiterId})`);
    }

    // Store phases
    if (data.phases && data.phases.length > 0) {
      for (let i = 0; i < data.phases.length; i++) {
        const phase = data.phases[i];
        await storage.storePhase({
          workflow_execution_id: executionId,
          phase_name: phase.name,
          phase_order: phase.order || i + 1,
          duration_ms: phase.duration_ms || 0,
          outcome: phase.outcome || 'success',
          metadata: phase.metadata || {}
        });
      }
      console.log(`[workflow-storage] Stored ${data.phases.length} phases`);
    }

    // Auto-extract learnings from failure patterns
    if (data.outcome === 'failed' || data.outcome === 'error') {
      await storage.storeLearnings({
        workflow_execution_id: executionId,
        learning_type: 'failure',
        description: `Workflow ${data.workflow_name} failed: ${data.metadata?.error || 'Unknown error'}`,
        actionable_insight: 'Investigate failure pattern and add retry logic',
        importance: 0.6,
        metadata: {
          auto_extracted: true,
          error: data.metadata?.error
        }
      });
      console.log(`[workflow-storage] Auto-extracted failure learning`);
    }

    return executionId;

  } catch (err) {
    console.error(`[workflow-storage] Error storing workflow data:`, err);
    throw err;
  }
}

/**
 * Store feedback on workflow execution
 *
 * @param {string} workflowId - Workflow ID
 * @param {Object} feedback - Feedback data
 * @returns {Promise<number>} Feedback record ID
 */
async function storeFeedback(workflowId, feedback) {
  const storage = getWorkflowStorage();

  // Get workflow execution ID from workflow_id
  const workflow = await storage.getWorkflowComplete(workflowId);
  if (!workflow) {
    throw new Error(`Workflow ${workflowId} not found`);
  }

  return await storage.storeFeedback({
    workflow_execution_id: workflow.execution.id,
    feedback_type: feedback.type || 'user',
    quality_score: feedback.score || 0.5,
    feedback_text: feedback.text || '',
    metadata: feedback.metadata || {}
  });
}

/**
 * Store learning from workflow execution
 *
 * @param {string} workflowId - Workflow ID
 * @param {Object} learning - Learning data
 * @returns {Promise<number>} Learning record ID
 */
async function storeLearning(workflowId, learning) {
  const storage = getWorkflowStorage();

  // Get workflow execution ID from workflow_id
  const workflow = await storage.getWorkflowComplete(workflowId);
  if (!workflow) {
    throw new Error(`Workflow ${workflowId} not found`);
  }

  return await storage.storeLearnings({
    workflow_execution_id: workflow.execution.id,
    learning_type: learning.type || 'pattern',
    description: learning.description,
    actionable_insight: learning.insight,
    importance: learning.importance || 0.5,
    metadata: learning.metadata || {}
  });
}

module.exports = {
  onWorkflowComplete,
  storeFeedback,
  storeLearning
};
