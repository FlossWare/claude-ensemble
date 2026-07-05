/**
 * Resource Limits - Prevent OOM by monitoring aio-01 memory
 *
 * Usage:
 *   import { checkMemoryBeforeWorkflow, getMaxConcurrentEmbeddingWorkers } from './shared/resource-limits.js';
 *
 *   checkMemoryBeforeWorkflow(); // Throws if <2GB available
 *   const workers = getMaxConcurrentEmbeddingWorkers(); // Returns 1-4 based on RAM
 */

import { execSync } from 'child_process';

/**
 * Check if sufficient memory available before launching workflow
 * @throws {Error} if less than 2GB available
 * @returns {Object} Memory stats {total, used, free, available}
 */
export function checkMemoryBeforeWorkflow() {
  try {
    const mem = execSync("ssh root@aio-01 'free -m | grep Mem'", { encoding: 'utf8' });
    const parts = mem.trim().split(/\s+/);
    const total = parseInt(parts[1]);
    const used = parseInt(parts[2]);
    const free = parseInt(parts[3]);

    // Available = free + reclaimable cache (estimate 30% of used)
    const available = free + Math.floor(used * 0.3);
    const MIN_REQUIRED_MB = 2000; // 2GB minimum

    if (available < MIN_REQUIRED_MB) {
      throw new Error(
        `Insufficient memory: ${available}MB available, ${MIN_REQUIRED_MB}MB required. ` +
        `Wait for other workflows to complete.`
      );
    }

    return { total, used, free, available };
  } catch (err) {
    if (err.message.includes('Insufficient memory')) {
      throw err;
    }
    console.warn('[resource-limits] Failed to check memory, proceeding cautiously:', err.message);
    return { total: 0, used: 0, free: 0, available: 0 };
  }
}

/**
 * Calculate max concurrent embedding workers based on available RAM
 * Each embedding worker uses ~500MB (sentence-transformers model)
 * @returns {number} 1-4 workers
 */
export function getMaxConcurrentEmbeddingWorkers() {
  try {
    const mem = execSync("ssh root@aio-01 'free -m | grep Mem'", { encoding: 'utf8' });
    const parts = mem.trim().split(/\s+/);
    const free = parseInt(parts[3]);

    // Each embedding worker uses ~500MB
    // Leave 2GB free for system
    const available = Math.max(0, free - 2000);
    const maxWorkers = Math.floor(available / 500);

    return Math.max(1, Math.min(maxWorkers, 4)); // 1-4 workers max
  } catch (err) {
    console.warn('[resource-limits] Failed to calculate workers, defaulting to 2:', err.message);
    return 2; // Safe default
  }
}

/**
 * Get current memory usage percentage
 * @returns {number} Percentage (0-100)
 */
export function getMemoryUsagePercent() {
  try {
    const mem = execSync("ssh root@aio-01 'free -m | grep Mem'", { encoding: 'utf8' });
    const parts = mem.trim().split(/\s+/);
    const total = parseInt(parts[1]);
    const used = parseInt(parts[2]);

    return Math.round((used / total) * 100);
  } catch (err) {
    console.warn('[resource-limits] Failed to get memory usage:', err.message);
    return 0;
  }
}
