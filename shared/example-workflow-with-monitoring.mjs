/**
 * Example Workflow with Resource Monitoring
 *
 * Demonstrates how to integrate workflow-resource-monitor.cjs
 * into a workflow file to track memory and CPU usage.
 *
 * Usage pattern:
 * 1. Start monitoring at workflow beginning
 * 2. Execute workflow phases
 * 3. Stop monitoring at workflow end
 * 4. (Optional) Link to workflow execution ID
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const { startMonitoring, stopMonitoring, getResourceByExecutionId } = require('./workflow-resource-monitor.cjs');

export default async function exampleWorkflow({ phase, parallel, agent, log }) {
  const workflowId = 'example-workflow-' + Date.now();

  log('Starting workflow with resource monitoring...');

  // Start resource monitoring
  startMonitoring(workflowId);

  let executionId = null;
  let resourceStats = null;

  try {
    // Phase 1: Initialize
    await phase('Initialize', async () => {
      log('Initializing workflow...');
      // Simulate initialization work
      await new Promise(resolve => setTimeout(resolve, 1000));
    });

    // Phase 2: Parallel Workers
    await phase('Execute Workers', async () => {
      log('Launching parallel workers...');

      const workers = await parallel([
        {
          name: 'Worker 1',
          async task() {
            // Simulate worker task
            await new Promise(resolve => setTimeout(resolve, 2000));
            return { result: 'Worker 1 complete', confidence: 0.95 };
          },
        },
        {
          name: 'Worker 2',
          async task() {
            // Simulate worker task
            await new Promise(resolve => setTimeout(resolve, 2000));
            return { result: 'Worker 2 complete', confidence: 0.92 };
          },
        },
        {
          name: 'Worker 3',
          async task() {
            // Simulate worker task
            await new Promise(resolve => setTimeout(resolve, 2000));
            return { result: 'Worker 3 complete', confidence: 0.88 };
          },
        },
      ]);

      log(`Completed ${workers.length} workers`);
    });

    // Phase 3: Synthesis
    await phase('Synthesize Results', async () => {
      log('Synthesizing results...');
      // Simulate synthesis
      await new Promise(resolve => setTimeout(resolve, 1000));
    });

    // Phase 4: Store workflow execution
    await phase('Store Workflow Data', async () => {
      // In a real workflow, you would store to workflow.executions table
      // and get the execution ID back
      executionId = Math.floor(Math.random() * 100000);
      log(`Stored workflow execution (ID: ${executionId})`);
    });

    log('Workflow completed successfully');

  } catch (error) {
    log(`Workflow failed: ${error.message}`);
    throw error;

  } finally {
    // Stop monitoring and get resource statistics
    // Link to workflow execution ID if available
    const options = executionId ? { workflowExecutionId: executionId } : {};
    resourceStats = await stopMonitoring(workflowId, options);

    if (resourceStats) {
      log('\n=== Resource Usage Statistics ===');
      log(`Duration: ${resourceStats.duration_ms}ms`);
      log(`Peak Memory: ${resourceStats.peak_memory_mb}MB`);
      log(`Avg Memory: ${resourceStats.avg_memory_mb}MB`);
      log(`Avg CPU: ${resourceStats.avg_cpu_percent}%`);
      log(`Max CPU: ${resourceStats.max_cpu_percent}%`);
      log(`Samples: ${resourceStats.sample_count}`);
      log('=================================\n');
    }
  }

  // Example: Query resource usage by execution ID later
  if (executionId) {
    const storedStats = await getResourceByExecutionId(executionId);
    if (storedStats) {
      log(`Resource usage record retrieved for execution ID ${executionId}`);
    }
  }

  return {
    success: true,
    workflowId,
    executionId,
    resourceStats,
  };
}

/**
 * Integration Pattern with Workflow Storage Adapter
 *
 * For workflows using workflow-storage-adapter.cjs:
 *
 * import { createRequire } from 'module';
 * const require = createRequire(import.meta.url);
 *
 * const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
 * const { startMonitoring, stopMonitoring } = require('./workflow-resource-monitor.cjs');
 *
 * export default async function myWorkflow({ phase, parallel, agent }) {
 *   const db = getWorkflowStorage();
 *   const workflowId = 'my-workflow-' + Date.now();
 *
 *   // Start resource monitoring
 *   startMonitoring(workflowId);
 *
 *   try {
 *     // Store workflow execution
 *     const execId = await db.storeExecution({
 *       workflow_id: workflowId,
 *       workflow_name: 'my-workflow',
 *       task_description: 'Process data',
 *       total_workers: 3,
 *       outcome: 'running'
 *     });
 *
 *     // Execute workflow phases...
 *     await phase('Process', async () => {
 *       // ... workflow logic ...
 *     });
 *
 *     // Update workflow outcome
 *     await db.pool.query(
 *       'UPDATE workflow.executions SET outcome = $1 WHERE id = $2',
 *       ['success', execId]
 *     );
 *
 *     // Stop monitoring and link to execution ID
 *     const resourceStats = await stopMonitoring(workflowId, {
 *       workflowExecutionId: execId
 *     });
 *
 *     return { success: true, execId, resourceStats };
 *
 *   } catch (error) {
 *     // Stop monitoring even on error
 *     await stopMonitoring(workflowId);
 *     throw error;
 *   }
 * }
 */
