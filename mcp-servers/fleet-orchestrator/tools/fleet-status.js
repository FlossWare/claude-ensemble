import { exec } from 'child_process';
import { promisify } from 'util';
import { getWorkers } from '../../../shared/fleet-utils.js';

const execAsync = promisify(exec);

const PROVIDERS = ['anthropic', 'openai', 'google', 'groq', 'deepinfra', 'together', 'mistral', 'cohere', 'ai21'];

export async function fleetStatus({ detailed = false }) {
  // Get live worker list from fleet configuration
  const workers = getWorkers();
  const WORKERS = workers.map(w => w.hostname);

  const workerStatuses = await Promise.all(
    WORKERS.map(async (worker) => {
      try {
        const start = Date.now();
        await execAsync(`ssh -o ConnectTimeout=2 claude@${worker} echo ping`, { timeout: 2000 });
        const latency = Date.now() - start;

        let load = null;
        if (detailed) {
          try {
            const { stdout } = await execAsync(`ssh claude@${worker} "uptime | awk -F'load average:' '{print \\$2}' | awk '{print \\$1}'"`);
            load = parseFloat(stdout.trim().replace(',', ''));
          } catch (e) {
            load = -1;
          }
        }

        return {
          worker,
          hostname: worker,
          healthy: true,
          latency_ms: latency,
          load: load,
          status: 'online'
        };
      } catch (error) {
        return {
          worker,
          hostname: worker,
          healthy: false,
          error: error.message,
          status: 'offline'
        };
      }
    })
  );

  const healthyCount = workerStatuses.filter(w => w.healthy).length;

  return {
    timestamp: new Date().toISOString(),
    total_workers: WORKERS.length,
    healthy_workers: healthyCount,
    unhealthy_workers: WORKERS.length - healthyCount,
    workers: workerStatuses,
    providers: PROVIDERS,
    summary: {
      status: healthyCount === WORKERS.length ? 'all_healthy' : healthyCount > 0 ? 'degraded' : 'critical',
      availability_percent: Math.round((healthyCount / WORKERS.length) * 100)
    }
  };
}
