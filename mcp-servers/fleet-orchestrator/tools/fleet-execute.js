import { withRetry } from '../lib/retry.js';
import { CircuitBreaker } from '../lib/circuit-breaker.js';
import { getCostTracker } from '../lib/cost-tracker.js';
import { getWorkflowStorage } from '../../../shared/workflow-storage-adapter.cjs';
import { getWorkers, mapModelToProvider } from '../../../shared/fleet-utils.js';
import { executeOnWorker } from '../../../shared/execute-on-worker.js';

const circuitBreaker = new CircuitBreaker({ threshold: 5, resetTimeout: 30000 });
const costTracker = getCostTracker();

export async function fleetExecute({ task, model = 'auto', worker = 'auto', timeout_ms = 120000, track_execution = true, track_costs = true }) {
  // Get live worker list from fleet configuration
  const workers = getWorkers();
  const WORKERS = workers.map(w => w.hostname);

  // Validate worker selection before assignment
  if (worker !== 'auto' && !WORKERS.includes(worker)) {
    throw new Error('Invalid worker: ' + worker);
  }

  // Select worker - API call executes on this worker via SSH
  const selectedWorker = worker === 'auto' ? WORKERS[Math.floor(Math.random() * WORKERS.length)] : worker;

  // Select model
  const selectedModel = model === 'auto' ? 'sonnet' : model;

  // Execute with retry and circuit breaker
  return await circuitBreaker.execute(selectedWorker, async () => {
    return await withRetry(async () => {
      // Execute LLM API call on remote worker via SSH
      const apiResult = await executeOnWorker({
        worker: selectedWorker,
        model: selectedModel,
        task,
        maxTokens: 4096,
        timeoutMs: timeout_ms
      });

      // Get actual token counts from API result
      const inputTokens = apiResult.input_tokens || 0;
      const outputTokens = apiResult.output_tokens || 0;

      // Calculate actual cost using cost tracker
      let costData = {
        cost_usd: 0,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        cost_tracking: false
      };

      if (track_costs && (inputTokens > 0 || outputTokens > 0)) {
        try {
          const calculated = costTracker.calculateCost(selectedModel, inputTokens, outputTokens);
          costData = {
            cost_usd: calculated.total_cost_usd,
            input_tokens: calculated.input_tokens,
            output_tokens: calculated.output_tokens,
            input_cost_usd: calculated.input_cost_usd,
            output_cost_usd: calculated.output_cost_usd,
            provider: calculated.provider,
            cost_tracking: true
          };
        } catch (costError) {
          console.warn('Failed to calculate cost:', costError.message);
          costData.cost_tracking = false;
        }
      }

      const result = {
        success: true,
        task: task.slice(0, 100),
        model: selectedModel,
        worker: selectedWorker,
        execution_host: selectedWorker,
        output: apiResult.output,
        duration_ms: apiResult.duration_ms,
        ...costData,
        database_integrated: false,
        cost_tracked: false
      };

      // Track cost in PostgreSQL if enabled
      if (track_costs && costData.cost_tracking) {
        try {
          const costEntry = await costTracker.trackCost({
            model: selectedModel,
            input_tokens: inputTokens,
            output_tokens: outputTokens,
            worker_id: selectedWorker,
            task_hash: Buffer.from(task).toString('hex').slice(0, 64),
            metadata: {
              fleet_execute: true,
              duration_ms: result.duration_ms
            }
          });
          result.cost_tracked = true;
          result.cost_entry_id = costEntry.id;
        } catch (dbError) {
          console.warn('Failed to track cost in database:', dbError.message);
          // Continue without tracking - don't fail the execution
        }
      }

      // Track execution in workflow storage if enabled
      if (track_execution) {
        try {
          const storage = getWorkflowStorage();
          await storage.storeWorkerResult({
            workflow_execution_id: null,
            worker_id: selectedWorker,
            execution_host: selectedWorker,
            model: selectedModel,
            task_assigned: task.slice(0, 100),
            result: result.output ? result.output.slice(0, 500) : '',
            confidence: null,
            duration_ms: result.duration_ms,
            input_tokens: result.input_tokens,
            output_tokens: result.output_tokens,
            cost_usd: result.cost_usd,
            outcome: 'success',
            metadata: {
              fleet_execute: true,
              cost_tracked: result.cost_tracked,
              cost_tracking: result.cost_tracking
            }
          });
          result.database_integrated = true;
        } catch (dbError) {
          console.warn('Failed to track execution in workflow storage:', dbError.message);
          // Continue without tracking - don't fail the execution
        }
      }

      return result;
    }, {
      maxRetries: 3,
      backoffMs: 1000,
      backoffMultiplier: 2
    });
  });
}
