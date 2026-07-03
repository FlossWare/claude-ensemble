/**
 * Fleet Utilities with ML-Driven Worker Count Optimization
 *
 * Drop-in replacement for fleet-utils.js that integrates worker count
 * optimizer. Replaces hardcoded worker counts with ML predictions.
 *
 * Usage:
 *   import { getWorkersOptimized } from './shared/fleet-utils-optimized.js';
 *
 *   // Auto-configure worker count based on task
 *   const workers = await getWorkersOptimized({
 *     task: 'Analyze 50 PDF files for compliance violations',
 *     estimatedDurationMs: 60000,
 *     inputSizeKb: 5000
 *   });
 *
 *   // Or use manual prediction
 *   const workers = await getWorkersOptimized({
 *     taskComplexity: 'high',
 *     requiresParallel: true,
 *     fallback: 6  // Use 6 if prediction fails
 *   });
 */

import { getWorkers, getFleet } from './fleet-utils.js';
import { predictOptimalWorkers, autoConfigureWorkers, estimateComplexity } from './worker-count-optimizer.js';

/**
 * Get workers with ML-optimized count
 *
 * @param {Object} options - Configuration options
 * @param {string} options.task - Task description (auto-configures all params)
 * @param {string} options.taskComplexity - 'low' | 'medium' | 'high'
 * @param {number} options.estimatedDurationMs - Expected task duration
 * @param {number} options.inputSizeKb - Input data size in KB
 * @param {boolean} options.requiresParallel - Does task benefit from parallelism?
 * @param {number} options.fallback - Fallback worker count (default: 8)
 * @param {Object} options.fleetOptions - Options passed to getWorkers()
 * @returns {Promise<Object[]>} Array of worker machines (optimized count)
 */
export async function getWorkersOptimized(options = {}) {
  let optimalCount;

  // Auto-configure from task description
  if (options.task) {
    optimalCount = await autoConfigureWorkers(options.task, options);
  } else {
    // Manual prediction
    optimalCount = await predictOptimalWorkers(options);
  }

  // Get all available workers
  const allWorkers = getWorkers(options.fleetOptions || {});

  // Return optimal subset (prioritized by fleet-utils sorting)
  return allWorkers.slice(0, optimalCount);
}

/**
 * Get fleet with ML-optimized count
 *
 * @param {Object} options - Same as getWorkersOptimized()
 * @returns {Promise<Object[]>} Array of fleet machines (optimized count)
 */
export async function getFleetOptimized(options = {}) {
  let optimalCount;

  if (options.task) {
    optimalCount = await autoConfigureWorkers(options.task, options);
  } else {
    optimalCount = await predictOptimalWorkers(options);
  }

  const allMachines = getFleet(options.fleetOptions || {});
  return allMachines.slice(0, optimalCount);
}

/**
 * Estimate optimal worker count without fetching fleet
 * Useful for planning and logging before execution.
 *
 * @param {string} taskDescription - Task description
 * @param {Object} options - Additional options
 * @returns {Promise<number>} Predicted optimal worker count
 */
export async function estimateWorkerCount(taskDescription, options = {}) {
  return autoConfigureWorkers(taskDescription, options);
}

// Re-export everything from fleet-utils for compatibility
export * from './fleet-utils.js';
