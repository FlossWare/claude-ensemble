#!/usr/bin/env node
/**
 * Work Distribution Module
 * Implements graceful degradation, load balancing, and dynamic batch sizing
 * for distributed fleet orchestration.
 *
 * Part of Fleet Resilience System (Layer 3: Graceful Degradation)
 */

// Note: FleetAttentionSchema removed - was unused ESM import in CommonJS file
// If needed, use dynamic import: const { FleetAttentionSchema } = await import('../fleet/attention-schema.mjs');

/**
 * Divide work across available workers with graceful degradation
 *
 * @param {Array<string>} taskIds - Array of task identifiers to distribute
 * @param {Array<Object>} workers - Array of worker nodes with health/capacity data
 * @param {Object} options - Configuration options
 * @returns {Array<Object>} Array of work batches per worker
 *
 * @example
 * const batches = divideWork(
 *   ['task1', 'task2', ...],
 *   [
 *     { id: 'server-01', healthy: true, capacity: 0.8, models: [...] },
 *     { id: 'server-02', healthy: true, capacity: 0.6, models: [...] }
 *   ],
 *   { strategy: 'capacity-weighted', minBatchSize: 1 }
 * );
 * // Returns: [
 * //   { workerId: 'server-01', taskIds: ['task1', 'task2', 'task3'], batchSize: 3 },
 * //   { workerId: 'server-02', taskIds: ['task4', 'task5'], batchSize: 2 }
 * // ]
 */
function divideWork(taskIds, workers, options = {}) {
  const {
    strategy = 'capacity-weighted',  // 'round-robin' | 'capacity-weighted' | 'least-busy'
    minBatchSize = 1,
    maxBatchSize = Infinity,
    allowUneven = true,
    degradationMode = 'auto'  // 'auto' | 'force-even' | 'force-weighted'
  } = options;

  // Validate and sanitize inputs
  if (!Array.isArray(taskIds)) {
    throw new Error('taskIds must be an array');
  }

  // FIXED: Reject empty strings (major - type coercion vulnerability)
  const validTaskIds = taskIds.filter(t => t && typeof t === 'string' && t.trim().length > 0);

  // Warn if tasks were dropped during sanitization
  if (validTaskIds.length < taskIds.length) {
    console.warn(`Dropped ${taskIds.length - validTaskIds.length} invalid task IDs (null/undefined/non-string/empty)`);
  }

  if (validTaskIds.length === 0) {
    throw new Error('taskIds must contain at least one valid non-empty string identifier');
  }

  if (!Array.isArray(workers) || workers.length === 0) {
    throw new Error('workers must be a non-empty array');
  }

  // FIXED: Enforce integer minBatchSize and maxBatchSize (minor - unsafe type coercion)
  if (!Number.isInteger(minBatchSize) || minBatchSize < 1) {
    throw new Error('minBatchSize must be an integer >= 1');
  }

  if (!Number.isInteger(maxBatchSize) || maxBatchSize < 1) {
    throw new Error('maxBatchSize must be an integer >= 1');
  }

  if (minBatchSize > maxBatchSize) {
    throw new Error(`minBatchSize (${minBatchSize}) cannot exceed maxBatchSize (${maxBatchSize})`);
  }

  // Filter healthy workers only (strict check: healthy must be explicitly true or undefined)
  const healthyWorkers = workers.filter(w => w.healthy === true || w.healthy === undefined);

  if (healthyWorkers.length === 0) {
    throw new Error('No healthy workers available');
  }

  // Apply sane default cap to maxBatchSize if Infinity (with absolute maximum)
  const effectiveMaxBatchSize = maxBatchSize === Infinity
    ? Math.min(10000, Math.max(1, Math.ceil(validTaskIds.length / healthyWorkers.length * 2)))
    : maxBatchSize;

  // FIXED: Check capacity upfront for round-robin (critical - infinite loop potential)
  if (strategy === 'round-robin') {
    const totalCapacity = healthyWorkers.length * effectiveMaxBatchSize;
    if (validTaskIds.length > totalCapacity) {
      throw new Error(`Insufficient capacity: ${validTaskIds.length} tasks require ${Math.ceil(validTaskIds.length / healthyWorkers.length)} tasks/worker but maxBatchSize is ${effectiveMaxBatchSize}`);
    }
  }

  // Select distribution strategy
  switch (strategy) {
    case 'round-robin':
      return distributeRoundRobin(validTaskIds, healthyWorkers, { minBatchSize, maxBatchSize: effectiveMaxBatchSize });

    case 'capacity-weighted':
      return distributeCapacityWeighted(validTaskIds, healthyWorkers, { minBatchSize, maxBatchSize: effectiveMaxBatchSize, allowUneven });

    case 'least-busy':
      return distributeLeastBusy(validTaskIds, healthyWorkers, { minBatchSize, maxBatchSize: effectiveMaxBatchSize });

    default:
      throw new Error(`Unknown distribution strategy: ${strategy}`);
  }
}

/**
 * Round-robin distribution (simple, fair, no capacity awareness)
 * Best for: Homogeneous fleet with equal capacity
 */
function distributeRoundRobin(taskIds, workers, options) {
  const { minBatchSize, maxBatchSize } = options;
  const batches = workers.map(w => ({ workerId: w.id || w.name, taskIds: [], batchSize: 0 }));

  // Track full batches using Set for accurate state
  const fullBatchIndices = new Set();
  let workerIndex = 0;

  for (const taskId of taskIds) {
    // Check if all workers are full
    if (fullBatchIndices.size >= batches.length) {
      throw new Error(`All workers reached maxBatchSize (${maxBatchSize}). Cannot assign remaining ${taskIds.length - batches.flatMap(b => b.taskIds).length} tasks.`);
    }

    const batch = batches[workerIndex];

    // Enforce max batch size
    if (batch.taskIds.length < maxBatchSize) {
      batch.taskIds.push(taskId);
      batch.batchSize = batch.taskIds.length;

      // Check if this batch just became full
      if (batch.batchSize >= maxBatchSize) {
        fullBatchIndices.add(workerIndex);
      }

      workerIndex = (workerIndex + 1) % batches.length;
    } else {
      // Current worker is full, find next available
      let attempts = 0;
      do {
        workerIndex = (workerIndex + 1) % batches.length;
        attempts++;

        if (attempts >= batches.length) {
          throw new Error(`All workers full - cannot assign task ${taskId}`);
        }
      } while (fullBatchIndices.has(workerIndex));

      const nextBatch = batches[workerIndex];
      nextBatch.taskIds.push(taskId);
      nextBatch.batchSize = nextBatch.taskIds.length;

      if (nextBatch.batchSize >= maxBatchSize) {
        fullBatchIndices.add(workerIndex);
      }

      workerIndex = (workerIndex + 1) % batches.length;
    }
  }

  // Filter out batches below min size
  return batches.filter(b => b.batchSize >= minBatchSize);
}

/**
 * Capacity-weighted distribution (considers CPU, RAM, historical performance)
 * Best for: Heterogeneous fleet with varying capacity
 *
 * Algorithm:
 * 1. Calculate total capacity (sum of all worker capacity scores)
 * 2. Assign tasks proportionally to capacity ratio
 * 3. Round batch sizes while preserving totals
 */
function distributeCapacityWeighted(taskIds, workers, options) {
  const { minBatchSize, maxBatchSize, allowUneven } = options;

  // Calculate capacity scores (0.0 to 1.0)
  const workerCapacities = workers.map(w => ({
    workerId: w.id || w.name,
    capacity: calculateCapacity(w),
    worker: w
  }));

  const totalCapacity = workerCapacities.reduce((sum, w) => sum + w.capacity, 0);

  // Check for zero total capacity BEFORE using it in division
  if (totalCapacity === 0) {
    // FIXED: Preserve options in fallback (major - cascading failure)
    console.warn('Total capacity is 0 - falling back to round-robin distribution');
    return distributeRoundRobin(taskIds, workers, { ...options, strategy: 'round-robin' });
  }

  // Calculate ideal batch sizes (float values)
  const idealBatches = workerCapacities.map(w => ({
    workerId: w.workerId,
    idealSize: (w.capacity / totalCapacity) * taskIds.length,
    capacity: w.capacity,
    worker: w.worker
  }));

  // Round batch sizes while preserving total count
  const batches = balancedRounding(idealBatches, taskIds.length);

  // Enforce min/max constraints
  let remainingTasks = [...taskIds];
  const finalBatches = [];

  for (const batch of batches) {
    let batchSize = Math.max(minBatchSize, Math.min(maxBatchSize, batch.batchSize));

    // Skip if not enough tasks remaining
    if (remainingTasks.length === 0) break;

    // Adjust if we'd leave too few tasks for remaining workers
    if (!allowUneven && remainingTasks.length < batchSize) {
      batchSize = remainingTasks.length;
    }

    const assignedTasks = remainingTasks.splice(0, batchSize);

    if (assignedTasks.length >= minBatchSize) {
      finalBatches.push({
        workerId: batch.workerId,
        taskIds: assignedTasks,
        batchSize: assignedTasks.length,
        capacity: batch.capacity
      });
    }
  }

  // FIXED: Optimize redistribution (minor - inefficient redistribution)
  if (remainingTasks.length > 0 && finalBatches.length > 0) {
    for (const task of remainingTasks) {
      const batch = finalBatches.find(b => b.taskIds.length < maxBatchSize);
      if (batch) {
        batch.taskIds.push(task);
        batch.batchSize = batch.taskIds.length;
      } else {
        throw new Error(`Failed to assign task ${task} - all workers at maxBatchSize (${maxBatchSize})`);
      }
    }
  }

  // Check if distribution resulted in no valid batches
  if (finalBatches.length === 0 && taskIds.length > 0) {
    throw new Error(`Distribution resulted in no valid batches - minBatchSize (${minBatchSize}) may be too high for ${taskIds.length} tasks across ${workers.length} workers`);
  }

  return finalBatches;
}

/**
 * Least-busy distribution (dynamic, considers current workload)
 * Best for: Workflows with varying task durations
 */
function distributeLeastBusy(taskIds, workers, options) {
  const { minBatchSize, maxBatchSize } = options;

  // Create worker load tracking (copy to avoid mutation)
  const workerLoads = workers.map(w => ({
    workerId: w.id || w.name,
    currentLoad: w.currentLoad || 0,
    capacity: calculateCapacity(w),
    assignedTasks: []
  }));

  // Assign tasks to least-busy worker iteratively
  for (const taskId of taskIds) {
    // Filter out workers that are already at capacity
    const availableWorkers = workerLoads.filter(w => w.assignedTasks.length < maxBatchSize);

    if (availableWorkers.length === 0) {
      throw new Error(`All workers reached maxBatchSize (${maxBatchSize}). Cannot assign task ${taskId}`);
    }

    // Find least-busy worker among available
    let leastBusy = availableWorkers[0];
    for (let i = 1; i < availableWorkers.length; i++) {
      if (availableWorkers[i].currentLoad < leastBusy.currentLoad) {
        leastBusy = availableWorkers[i];
      }
    }

    leastBusy.assignedTasks.push(taskId);
    leastBusy.currentLoad += 1;  // Increment estimated load
  }

  // Convert to batch format
  return workerLoads
    .filter(w => w.assignedTasks.length >= minBatchSize)
    .map(w => ({
      workerId: w.workerId,
      taskIds: w.assignedTasks,
      batchSize: w.assignedTasks.length,
      currentLoad: w.currentLoad
    }));
}

/**
 * Calculate worker capacity score (0.0 to 1.0)
 * Considers: CPU, RAM, model availability, historical performance
 */
const warnedWorkers = new Set();  // Cache to prevent console spam

function calculateCapacity(worker) {
  // Validate worker object
  if (!worker) {
    throw new Error('Worker object is null or undefined');
  }

  // Explicit capacity score (if provided)
  if (typeof worker.capacity === 'number') {
    return Math.max(0, Math.min(1, worker.capacity));
  }

  // Calculate from system metrics
  let score = 0;
  let factors = 0;

  // CPU capacity (0.0 = 100% used, 1.0 = 0% used)
  if (typeof worker.cpu === 'number') {
    score += Math.max(0, Math.min(1, worker.cpu));
    factors++;
  }

  // FIXED: Validate RAM fields as numbers (minor - inconsistent validation)
  if (typeof worker.memory === 'number') {
    score += Math.max(0, Math.min(1, worker.memory));
    factors++;
  } else if (typeof worker.ram_used_mb === 'number' && typeof worker.ram_total_mb === 'number' && worker.ram_total_mb > 0) {
    // FIXED: Skip metric on corrupted data instead of calculating negative capacity (critical - silent data corruption)
    if (worker.ram_used_mb > worker.ram_total_mb) {
      const workerId = worker.id || worker.name || 'unknown';
      console.warn(`Worker ${workerId}: RAM used (${worker.ram_used_mb}MB) exceeds total (${worker.ram_total_mb}MB) - skipping RAM metric`);
    } else {
      const ramCapacity = 1 - (worker.ram_used_mb / worker.ram_total_mb);
      score += Math.max(0, Math.min(1, ramCapacity));
      factors++;
    }
  }

  // Model availability (more models = higher capacity)
  if (Array.isArray(worker.models) && worker.models.length > 0) {
    const modelScore = Math.min(1, worker.models.length / 10);  // Cap at 10 models
    score += modelScore;
    factors++;
  }

  // Historical performance (if available)
  if (typeof worker.avgReward === 'number') {
    score += Math.max(0, Math.min(1, worker.avgReward));
    factors++;
  }

  // Default to 0.5 if no data (with cached warning to prevent spam)
  if (factors === 0) {
    const workerId = worker.id || worker.name || 'unknown';
    if (!warnedWorkers.has(workerId)) {
      console.warn(`Worker ${workerId} has no capacity metrics - defaulting to 0.5`);
      warnedWorkers.add(workerId);
    }
    return 0.5;
  }

  return score / factors;
}

/**
 * Balanced rounding algorithm (preserves total count)
 *
 * Problem: Math.round(3.3) + Math.round(1.7) = 3 + 2 = 5 (but total was 5.0)
 * Solution: Largest Remainder Method (LRM)
 *
 * Note: Returns batches sorted by remainder (descending). Final batch sizes
 * after shortfall distribution may not be in descending order.
 *
 * @param {Array<Object>} idealBatches - Array with idealSize (float) per worker
 * @param {number} totalTasks - Total number of tasks to distribute
 * @returns {Array<Object>} Array with batchSize (int) per worker
 */
function balancedRounding(idealBatches, totalTasks) {
  // FIXED: Validate totalTasks is integer (major - precision error accumulation)
  if (!Number.isInteger(totalTasks)) {
    throw new Error('totalTasks must be an integer');
  }

  // Step 1: Floor all values (copy to avoid mutation of input)
  const batches = idealBatches.map(b => ({
    workerId: b.workerId,
    batchSize: Math.floor(b.idealSize),
    remainder: b.idealSize - Math.floor(b.idealSize),
    capacity: b.capacity
  }));

  // Step 2: Calculate shortfall
  const assignedTotal = batches.reduce((sum, b) => sum + b.batchSize, 0);
  let shortfall = totalTasks - assignedTotal;

  // Validate shortfall is non-negative (floating-point precision check)
  if (shortfall < 0) {
    console.warn(`Negative shortfall detected (${shortfall}) - floating-point precision issue. Setting to 0.`);
    shortfall = 0;
  }

  // Step 3: Sort by remainder (largest first) - creates new sorted array
  const sortedBatches = batches.slice().sort((a, b) => b.remainder - a.remainder);

  // Step 4: Distribute shortfall to workers with largest remainders
  for (let i = 0; i < shortfall && i < sortedBatches.length; i++) {
    sortedBatches[i].batchSize += 1;
  }

  // Step 5: Verify total (with stricter tolerance for floating point errors)
  const finalTotal = sortedBatches.reduce((sum, b) => sum + b.batchSize, 0);

  // FIXED: Stricter tolerance (major - precision error accumulation)
  if (Math.abs(finalTotal - totalTasks) > 0.001) {
    throw new Error(`Rounding error: expected ${totalTasks}, got ${finalTotal} (diff: ${Math.abs(finalTotal - totalTasks)})`);
  }

  // Step 6: Force-fix if off by 1 (floating point precision)
  if (finalTotal < totalTasks) {
    sortedBatches[0].batchSize += (totalTasks - finalTotal);
  } else if (finalTotal > totalTasks) {
    const deficit = finalTotal - totalTasks;

    // FIXED: Remove from largest batch to preserve LRM invariant (minor - asymmetric error handling)
    const largestBatch = sortedBatches.reduce((max, b) => b.batchSize > max.batchSize ? b : max);

    // Ensure we don't make batchSize negative
    if (largestBatch.batchSize < deficit) {
      throw new Error(`Cannot fix rounding error: largest batch size (${largestBatch.batchSize}) is less than deficit (${deficit})`);
    }

    largestBatch.batchSize -= deficit;
  }

  return sortedBatches;
}

/**
 * Rebalance work after node failure
 *
 * WARNING: Only redistributes tasks that are in 'pending' or 'failed' state.
 * Tasks 'in_progress' on healthy workers are NOT reassigned.
 *
 * IMPORTANT: taskStates parameter is REQUIRED and must include _timestamp for staleness checks.
 *
 * @param {string} failedWorkerId - ID of the failed worker
 * @param {Array<string>} failedTaskIds - Tasks from failed node
 * @param {Array<Object>} currentBatches - Current work distribution with task states
 * @param {Array<Object>} availableWorkers - Healthy workers (excluding failed)
 * @param {Object} taskStates - Map of taskId -> state ('pending'|'in_progress'|'failed') with _timestamp [REQUIRED]
 * @returns {Array<Object>} Updated batches with redistributed work
 */
function rebalanceAfterFailure(failedWorkerId, failedTaskIds, currentBatches, availableWorkers, taskStates) {
  // Require taskStates parameter
  if (!taskStates || typeof taskStates !== 'object') {
    throw new Error('taskStates parameter is required - must be a map of taskId -> state with _timestamp');
  }

  // FIXED: Validate taskStates timestamp to prevent stale state race condition (critical - race condition)
  const STALENESS_THRESHOLD_MS = 5000;
  if (!taskStates._timestamp || Date.now() - taskStates._timestamp > STALENESS_THRESHOLD_MS) {
    throw new Error(`Stale task state: timestamp is ${taskStates._timestamp ? Date.now() - taskStates._timestamp + 'ms old' : 'missing'}. Maximum age: ${STALENESS_THRESHOLD_MS}ms`);
  }

  // Require failedWorkerId to prevent reassigning from healthy workers
  if (!failedWorkerId || typeof failedWorkerId !== 'string') {
    throw new Error('failedWorkerId parameter is required - must be a string identifying the failed worker');
  }

  // Validate failedTaskIds exist in current batches
  const allCurrentTaskIds = new Set(currentBatches.flatMap(b => b.taskIds));
  const unknownFailedTasks = failedTaskIds.filter(id => !allCurrentTaskIds.has(id));

  if (unknownFailedTasks.length > 0) {
    console.warn(`Warning: ${unknownFailedTasks.length} failed task IDs not found in current batches: ${unknownFailedTasks.slice(0, 5).join(', ')}${unknownFailedTasks.length > 5 ? '...' : ''}`);
  }

  // FIXED: Only extract tasks from the failed worker's batch (critical - logic error preventing reassignment from healthy workers)
  const failedBatch = currentBatches.find(b => b.workerId === failedWorkerId);
  const safeToReassign = failedBatch
    ? failedBatch.taskIds.filter(taskId => {
        const state = taskStates[taskId];
        // Only reassign if explicitly marked as pending or failed
        return state === 'pending' || state === 'failed';
      })
    : [];

  // FIXED: Validate failedTaskIds against taskStates to prevent resource leak (major - resource leak)
  const actuallyFailed = failedTaskIds.filter(id => {
    const state = taskStates[id];
    return state === 'failed' || state === 'pending';
  });

  if (actuallyFailed.length !== failedTaskIds.length) {
    const incorrectlyMarked = failedTaskIds.filter(id => !actuallyFailed.includes(id));
    throw new Error(`${incorrectlyMarked.length} tasks in failedTaskIds are not actually failed/pending: ${incorrectlyMarked.slice(0, 5).join(', ')}${incorrectlyMarked.length > 5 ? '...' : ''}`);
  }

  // Combine failed + safe-to-reassign tasks (avoid duplicates with Set)
  const allTasksSet = new Set([...actuallyFailed, ...safeToReassign]);
  const allTasks = Array.from(allTasksSet);

  // Re-distribute from scratch
  return divideWork(allTasks, availableWorkers, {
    strategy: 'capacity-weighted',
    allowUneven: true
  });
}

/**
 * Calculate optimal batch size based on task characteristics
 *
 * @param {number} totalTasks - Total number of tasks
 * @param {number} workerCount - Number of available workers
 * @param {Object} taskProfile - Task characteristics
 * @param {Array<Object>} workers - Worker objects with RAM/CPU data (optional)
 * @returns {Object} Recommended min/max batch sizes
 */
function calculateOptimalBatchSize(totalTasks, workerCount, taskProfile = {}, workers = []) {
  const {
    avgDurationMs = 30000,      // 30s average task duration
    parallelizable = true,      // Can tasks run in parallel?
    memoryPerTask = 100,        // MB per task
    cpuPerTask = 0.1           // CPU cores per task (0.1 = 10% of 1 core)
  } = taskProfile;

  // FIXED: Validate resource requirements (major - division by zero risk)
  if (memoryPerTask < 0 || cpuPerTask < 0) {
    throw new Error('memoryPerTask and cpuPerTask must be >= 0');
  }

  // Base batch size: total / workers
  const baseSize = Math.ceil(totalTasks / workerCount);

  // Adjust for task duration (longer tasks = smaller batches for better load balancing)
  const durationFactor = avgDurationMs > 60000 ? 0.5 : 1.0;

  // Adjust for parallelizability
  const parallelFactor = parallelizable ? 1.5 : 1.0;

  let minBatchSize = Math.max(1, Math.floor(baseSize * 0.5 * durationFactor));
  let maxBatchSize = Math.ceil(baseSize * 2.0 * parallelFactor);

  // Constrain by worker resources if available (skip if resource requirement is 0)
  if (workers.length > 0) {
    const minWorkerRAM = Math.min(...workers.map(w => w.ram_total_mb || Infinity).filter(r => r !== Infinity));
    const minWorkerCPU = Math.min(...workers.map(w => w.cpu_cores || Infinity).filter(c => c !== Infinity));

    // FIXED: Skip constraint if memoryPerTask is 0 (major - division by zero risk)
    if (minWorkerRAM !== Infinity && memoryPerTask > 0) {
      const ramConstrainedMax = Math.floor(minWorkerRAM * 0.8 / memoryPerTask);  // 80% RAM usage max

      // Error if task requirements exceed worker capacity
      if (ramConstrainedMax === 0) {
        throw new Error(`Task memory requirements (${memoryPerTask}MB) exceed worker capacity (${minWorkerRAM}MB * 0.8). Reduce memoryPerTask or use workers with more RAM.`);
      }

      maxBatchSize = Math.min(maxBatchSize, ramConstrainedMax);
    }

    // FIXED: Skip constraint if cpuPerTask is 0 (major - division by zero risk)
    if (minWorkerCPU !== Infinity && cpuPerTask > 0) {
      const cpuConstrainedMax = Math.floor(minWorkerCPU / cpuPerTask);

      // Error if task requirements exceed worker capacity
      if (cpuConstrainedMax === 0) {
        throw new Error(`Task CPU requirements (${cpuPerTask} cores) exceed worker capacity (${minWorkerCPU} cores). Reduce cpuPerTask or use workers with more CPU.`);
      }

      maxBatchSize = Math.min(maxBatchSize, cpuConstrainedMax);
    }
  }

  return {
    minBatchSize,
    maxBatchSize,
    recommendedSize: baseSize,
    reasoning: {
      baseSize,
      durationFactor,
      parallelFactor,
      workerCount,
      totalTasks
    }
  };
}

/**
 * Validate work distribution (health checks)
 *
 * @param {Array<Object>} batches - Work distribution to validate
 * @param {Array<string>} originalTasks - Original task list
 * @returns {Object} Validation result
 */
function validateDistribution(batches, originalTasks) {
  const errors = [];
  const warnings = [];

  // Check 1: All tasks assigned + uniqueness
  const assignedTasks = batches.flatMap(b => b.taskIds);
  const assignedTasksSet = new Set(assignedTasks);
  const originalTasksSet = new Set(originalTasks);

  // Check for missing tasks
  const missingTasks = originalTasks.filter(t => !assignedTasksSet.has(t));
  if (missingTasks.length > 0) {
    errors.push(`Missing tasks: ${missingTasks.length} tasks not assigned`);
  }

  // FIXED: O(n) duplicate detection using Set (major - performance DoS)
  if (assignedTasks.length !== assignedTasksSet.size) {
    const seen = new Set();
    const duplicates = assignedTasks.filter(t => seen.has(t) ? true : (seen.add(t), false));
    const uniqueDuplicates = [...new Set(duplicates)];
    errors.push(`Duplicate tasks: ${uniqueDuplicates.slice(0, 10).join(', ')}${uniqueDuplicates.length > 10 ? ` (+ ${uniqueDuplicates.length - 10} more)` : ''}`);
  }

  // Check for task count mismatch (catches duplicates + missing)
  if (assignedTasksSet.size !== originalTasksSet.size) {
    errors.push(`Task count mismatch: expected ${originalTasksSet.size}, got ${assignedTasksSet.size} unique tasks`);
  }

  // Check 2: Batch size consistency
  for (const batch of batches) {
    if (batch.batchSize !== batch.taskIds.length) {
      warnings.push(`Worker ${batch.workerId}: batchSize mismatch (${batch.batchSize} vs ${batch.taskIds.length})`);
    }
  }

  // Check 3: Load imbalance detection
  if (batches.length > 1) {
    const sizes = batches.map(b => b.batchSize);
    const maxSize = Math.max(...sizes);
    const minSize = Math.min(...sizes);
    const imbalance = maxSize / (minSize || 1);

    if (imbalance > 3.0) {
      warnings.push(`High load imbalance: ${imbalance.toFixed(2)}x difference between workers`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    stats: {
      totalBatches: batches.length,
      totalTasks: assignedTasks.length,
      uniqueTasks: assignedTasksSet.size,
      avgBatchSize: assignedTasks.length / batches.length,
      minBatchSize: Math.min(...batches.map(b => b.batchSize)),
      maxBatchSize: Math.max(...batches.map(b => b.batchSize))
    }
  };
}

/**
 * Graceful degradation manager
 * Handles transitions: 5 workers → 4 → 3 → 2 → 1 → laptop-01 solo
 */
class GracefulDegradationManager {
  constructor() {
    this.degradationThresholds = {
      optimal: 5,      // 5+ workers
      degraded: 3,     // 3-4 workers
      minimal: 2,      // 2 workers
      fallback: 1      // 1 worker (laptop-01 solo)
    };
  }

  /**
   * Determine degradation mode based on worker count
   */
  getDegradationMode(workerCount) {
    if (workerCount >= this.degradationThresholds.optimal) {
      return { mode: 'optimal', strategy: 'capacity-weighted', parallelism: 'full' };
    } else if (workerCount >= this.degradationThresholds.degraded) {
      return { mode: 'degraded', strategy: 'capacity-weighted', parallelism: 'reduced' };
    } else if (workerCount >= this.degradationThresholds.minimal) {
      return { mode: 'minimal', strategy: 'round-robin', parallelism: 'limited' };
    } else {
      return { mode: 'fallback', strategy: 'local-only', parallelism: 'none' };
    }
  }

  /**
   * Adapt distribution strategy to degradation mode
   */
  adaptStrategy(taskIds, workers) {
    // Validate workers array
    if (!workers || workers.length === 0) {
      throw new Error('No workers available for distribution');
    }

    const degradationMode = this.getDegradationMode(workers.length);

    if (degradationMode.mode === 'fallback') {
      // FIXED: Validate worker object (minor - hardcoded assumption)
      if (!workers[0] || typeof workers[0] !== 'object') {
        throw new Error('Invalid worker object at index 0');
      }

      // Solo mode: all work on first available worker (no hardcoded 'laptop-01')
      const workerId = workers[0].id || workers[0].name;
      if (!workerId) {
        throw new Error('Fallback worker has no id or name property');
      }

      return [{
        workerId: workerId,
        taskIds: taskIds,
        batchSize: taskIds.length,
        mode: 'fallback'
      }];
    }

    // Adjust batch sizing based on degradation
    const batchConfig = calculateOptimalBatchSize(
      taskIds.length,
      workers.length,
      { avgDurationMs: degradationMode.mode === 'minimal' ? 60000 : 30000 }
    );

    const batches = divideWork(taskIds, workers, {
      strategy: degradationMode.strategy,
      minBatchSize: batchConfig.minBatchSize,
      maxBatchSize: batchConfig.maxBatchSize,
      allowUneven: degradationMode.mode !== 'optimal'
    });

    // Add mode field for consistent return type
    return batches.map(b => ({ ...b, mode: degradationMode.mode }));
  }
}

// Export public API
module.exports = {
  divideWork,
  rebalanceAfterFailure,
  calculateOptimalBatchSize,
  validateDistribution,
  calculateCapacity,
  GracefulDegradationManager,

  // Export internal functions for testing
  _internal: {
    distributeRoundRobin,
    distributeCapacityWeighted,
    distributeLeastBusy,
    balancedRounding
  }
};
