/**
 * Hot-Reload Integration Examples
 *
 * Demonstrates how to integrate hot-reload system into workflows, daemons,
 * and AI learning systems.
 *
 * Usage patterns:
 * 1. Workflow integration: Dynamic imports in consensus/orchestration
 * 2. Daemon integration: Reload modules on each cycle
 * 3. Discovery integration: Live updates to model selection rules
 */

import { hotImport, hotImportJSON } from '../shared/hot-reload.js';
import { applyDiscoveries } from './apply-discoveries.js';

// ============================================================================
// PATTERN 1: WORKFLOW HOT-RELOAD
// ============================================================================

/**
 * Example: Consensus workflow with hot-reload
 *
 * Reloads orchestrator on each task for live model selection updates.
 */
export async function runConsensusWithHotReload(taskType, options = {}) {
  // Hot-import orchestrator to get latest model selection logic
  const orchestrator = await hotImport('./orchestrator.js');

  // Select workers using latest Thompson Sampling state
  const workers = await orchestrator.selectWorkers(taskType, {
    count: 3,
    strategy: 'thompson',
  });

  console.log(`[consensus] Selected workers: ${workers.join(', ')}`);

  // Apply discoveries for context-aware filtering/biasing
  const context = {
    task_type: taskType,
    workflow: 'consensus',
    worker_count: workers.length,
    ...options.context,
  };

  const config = await applyDiscoveries(workers, context);

  console.log(`[consensus] Applied discoveries:`, {
    filtered_models: config.models,
    biases: config.biases,
    diversity_weight: config.diversity_weight,
  });

  // Execute with hot-reloaded consensus engine
  const consensus = await hotImport('../shared/consensus-engine.js');

  return {
    workers: config.models,
    config,
  };
}

// ============================================================================
// PATTERN 2: DAEMON HOT-RELOAD
// ============================================================================

/**
 * Example: Background daemon with hot-reload cycle
 *
 * Reloads all modules on each iteration to pick up code changes.
 */
export async function runDaemonCycle() {
  // Force reload on each cycle
  const logger = await hotImport('./shared/learning-logger.js', { force: true });
  const orchestrator = await hotImport('./orchestrator.js', { force: true });

  // Fetch latest execution stats
  const stats = logger.getExecutionCount();

  // Recompute Thompson Sampling parameters
  const thompsonStats = await orchestrator.getThompsonStats();

  console.log(`[daemon] Execution count: ${stats}`);
  console.log(`[daemon] Thompson stats:`, thompsonStats);

  return {
    execution_count: stats,
    thompson_stats: thompsonStats,
  };
}

/**
 * Example: Long-running daemon loop with hot-reload
 */
export async function runDaemonLoop(intervalSec = 30) {
  console.log(`[daemon] Starting hot-reload daemon (interval: ${intervalSec}s)`);

  const intervalId = setInterval(async () => {
    try {
      await runDaemonCycle();
    } catch (err) {
      console.error(`[daemon] Cycle error: ${err.message}`);
    }
  }, intervalSec * 1000);

  // Clean shutdown
  process.on('SIGINT', () => {
    console.log('\n[daemon] Shutting down...');
    clearInterval(intervalId);
    process.exit(0);
  });

  // Run first cycle immediately
  await runDaemonCycle();
}

// ============================================================================
// PATTERN 3: DISCOVERY-DRIVEN MODEL SELECTION
// ============================================================================

/**
 * Example: Model selection with discovery application
 *
 * Demonstrates how to use discoveries to filter/bias model selection.
 */
export async function selectModelWithDiscoveries(taskType, context = {}) {
  // Hot-import orchestrator for latest Thompson Sampling state
  const orchestrator = await hotImport('./orchestrator.js');

  // Get base model recommendations
  const baseModels = await orchestrator.selectWorkers(taskType, {
    count: 4,
    strategy: 'thompson',
  });

  console.log(`[selection] Base models: ${baseModels.join(', ')}`);

  // Apply discoveries to filter/bias
  const fullContext = {
    task_type: taskType,
    ...context,
  };

  const config = await applyDiscoveries(baseModels, fullContext);

  console.log(`[selection] Filtered models: ${config.models.join(', ')}`);
  console.log(`[selection] Biases:`, config.biases);
  console.log(`[selection] Diversity weight: ${config.diversity_weight}`);

  // Apply biases to Thompson Sampling (conceptual - would need implementation)
  // In practice, you would multiply Thompson samples by bias weights
  const finalModels = config.models.slice(0, config.worker_count);

  return {
    models: finalModels,
    biases: config.biases,
    diversity_weight: config.diversity_weight,
    worker_count: config.worker_count,
  };
}

// ============================================================================
// PATTERN 4: LEARNING FEEDBACK LOOP
// ============================================================================

/**
 * Example: Record execution result and reload discoveries
 *
 * After execution completes, update Thompson Sampling and check for new discoveries.
 */
export async function recordExecutionResult(model, qualityScore, context = {}) {
  // Hot-import orchestrator to update Thompson Sampling
  const orchestrator = await hotImport('./orchestrator.js', { force: true });

  // Record result
  const updated = await orchestrator.recordResult(model, qualityScore);

  console.log(`[feedback] Recorded result for ${model}: quality=${qualityScore}`);
  console.log(`[feedback] Updated Thompson state:`, updated);

  // Check if this result triggers new discoveries
  // (In practice, this would be handled by background learning processes)
  const discoveries = await hotImportJSON('./learning/discoveries.json', { force: true });

  console.log(`[feedback] Active discoveries: ${discoveries.metadata.total_discoveries}`);

  return {
    thompson_state: updated,
    active_discoveries: discoveries.metadata.total_discoveries,
  };
}

// ============================================================================
// PATTERN 5: WEB LEARNING INTEGRATION
// ============================================================================

/**
 * Example: PDF/Web research with hot-reload
 *
 * Demonstrates how research workflows can pick up model selection updates.
 */
export async function runResearchWithHotReload(topic, options = {}) {
  // Hot-import orchestrator for latest model selection
  const orchestrator = await hotImport('./orchestrator.js');

  // Select model for research task
  const context = {
    task_type: 'web-research',
    requires_schema: false,
    quality_threshold: 0.8,
    ...options.context,
  };

  const selection = await selectModelWithDiscoveries('web-research', context);

  console.log(`[research] Selected model: ${selection.models[0]}`);
  console.log(`[research] Context:`, context);

  // Execute research (conceptual - would use actual research workflow)
  return {
    topic,
    model: selection.models[0],
    config: selection,
  };
}

// ============================================================================
// PATTERN 6: ORCHESTRATOR HOT-RELOAD WRAPPER
// ============================================================================

/**
 * Example: Wrapper for orchestrator with automatic hot-reload
 *
 * Provides a clean API that always uses hot-reloaded orchestrator.
 */
export class HotOrchestrator {
  async selectModel(taskType, options = {}) {
    const orchestrator = await hotImport('./orchestrator.js');
    return orchestrator.selectModel(taskType, options);
  }

  async selectWorkers(taskType, options = {}) {
    const orchestrator = await hotImport('./orchestrator.js');
    return orchestrator.selectWorkers(taskType, options);
  }

  async recordResult(model, qualityScore) {
    const orchestrator = await hotImport('./orchestrator.js');
    return orchestrator.recordResult(model, qualityScore);
  }

  async getThompsonStats() {
    const orchestrator = await hotImport('./orchestrator.js');
    return orchestrator.getThompsonStats();
  }

  async getModelMetrics(model, taskType, days = 30) {
    const orchestrator = await hotImport('./orchestrator.js');
    return orchestrator.getModelMetrics(model, taskType, days);
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
  runConsensusWithHotReload,
  runDaemonCycle,
  runDaemonLoop,
  selectModelWithDiscoveries,
  recordExecutionResult,
  runResearchWithHotReload,
  HotOrchestrator,
};
