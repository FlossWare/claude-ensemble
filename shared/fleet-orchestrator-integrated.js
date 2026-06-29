import { withRetry } from '../mcp-servers/fleet-orchestrator/lib/retry.js';
import { CircuitBreaker } from '../mcp-servers/fleet-orchestrator/lib/circuit-breaker.js';
import { getWorkers, mapModelToProvider } from './fleet-utils.js';
import { executeOnWorker } from './execute-on-worker.js';

const circuitBreaker = new CircuitBreaker({ threshold: 5, resetTimeout: 30000 });

export { mapModelToProvider };

export async function selectModel(task) {
  const complexity = task.length > 500 ? 'high' : task.length > 100 ? 'medium' : 'low';
  return complexity === 'high' ? 'opus' : complexity === 'medium' ? 'sonnet' : 'haiku';
}

export async function executeOnModel(model, prompt, worker = 'auto') {
  const workers = getWorkers();
  const workerHostnames = workers.map(w => w.hostname);
  const selectedWorker = worker === 'auto' ? workerHostnames[Math.floor(Math.random() * workerHostnames.length)] : worker;

  return await circuitBreaker.execute(selectedWorker, async () => {
    return await withRetry(async () => {
      // SSH to worker and execute LLM API call there
      const apiResult = await executeOnWorker({
        worker: selectedWorker,
        model,
        task: prompt,
        maxTokens: 4096,
        timeoutMs: 30000
      });

      return {
        output: apiResult.output,
        model: apiResult.model || model,
        worker: selectedWorker,
        execution_host: apiResult.execution_host,
        actually_executed_on_worker: apiResult.actually_executed_on_worker,
        ssh_overhead_ms: apiResult.ssh_overhead_ms,
        input_tokens: apiResult.input_tokens,
        output_tokens: apiResult.output_tokens,
        duration_ms: apiResult.duration_ms,
        provider: apiResult.provider
      };
    }, {
      maxRetries: 3,
      backoffMs: 1000,
      backoffMultiplier: 2
    });
  });
}

export { withRetry, CircuitBreaker };
