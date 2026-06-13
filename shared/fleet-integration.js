/**
 * Fleet Integration for Workflows
 *
 * Provides workflow-friendly fleet integration with args parsing,
 * auto-detection, and graceful fallback.
 *
 * Usage in workflows:
 *   import { shouldUseFleet, getFleetWorkers, distributeModels }
 *     from './shared/fleet-integration.js';
 *
 *   const workers = getFleetWorkers(args);
 *   const models = distributeModels(['opus', 'sonnet', 'haiku'], workers);
 */

import fs from 'fs';

/**
 * Parse fleet-related args from workflow args
 * @param {any} args - Workflow args (string or object)
 * @returns {Object} Parsed fleet options
 */
function parseFleetArgs(args) {
  const defaults = {
    useFleet: true,        // Auto-detect by default
    localOnly: false,      // Disable fleet
    fleetWorkers: null,    // Max workers (null = all available)
    skipHealthCheck: false // Skip SSH health probe
  };

  // Handle string args (CLI-style)
  if (typeof args === 'string') {
    return {
      ...defaults,
      useFleet: !args.includes('--local-only'),
      localOnly: args.includes('--local-only'),
      fleetWorkers: extractNumber(args, '--fleet-workers='),
      skipHealthCheck: args.includes('--skip-health-check')
    };
  }

  // Handle object args
  if (typeof args === 'object' && args !== null) {
    return {
      useFleet: args.useFleet !== false && args.localOnly !== true,
      localOnly: args.localOnly === true,
      fleetWorkers: args.fleetWorkers || args.workers || null,
      skipHealthCheck: args.skipHealthCheck === true
    };
  }

  return defaults;
}

/**
 * Extract number from string like "--fleet-workers=3"
 */
function extractNumber(str, prefix) {
  const match = str.match(new RegExp(prefix + '(\\d+)'));
  return match ? parseInt(match[1], 10) : null;
}

/**
 * Check if fleet should be used for this workflow invocation
 * @param {any} args - Workflow args
 * @returns {boolean} True if fleet should be used
 */
function shouldUseFleet(args) {
  const opts = parseFleetArgs(args);

  // Explicit local-only flag
  if (opts.localOnly) return false;

  // Check if we're in a compliance-forbidden path
  const cwd = process.cwd();
  const forbiddenPaths = ['/home/sfloess/Development/redhat/'];

  for (const path of forbiddenPaths) {
    if (cwd.startsWith(path)) {
      return false;  // Auto-disable for Red Hat work
    }
  }

  return opts.useFleet;
}

/**
 * Get fleet workers for workflow use
 * @param {any} args - Workflow args
 * @param {Object} options - Additional filter options
 * @returns {Promise<Object[]>} Array of worker machines (empty if fleet disabled)
 */
async function getFleetWorkers(args, options = {}) {
  const fleetOpts = parseFleetArgs(args);

  if (!shouldUseFleet(args)) {
    return [];
  }

  try {
    // Dynamic import of fleet-utils (may not exist in all environments)
    const fleetUtils = await import('./fleet-utils.js');

    const workers = fleetUtils.getWorkers({
      ...options,
      skipHealthCheck: fleetOpts.skipHealthCheck
    });

    // Limit to requested number of workers
    if (fleetOpts.fleetWorkers && fleetOpts.fleetWorkers > 0) {
      return workers.slice(0, fleetOpts.fleetWorkers);
    }

    return workers;
  } catch (error) {
    // Fleet utilities not available or error loading config
    // Gracefully fall back to local execution
    return [];
  }
}

/**
 * Distribute AI models across fleet workers
 * @param {string[]} models - Array of model names
 * @param {Object[]} workers - Array of worker machines (or empty for local)
 * @returns {Object[]} Array of { model, hostname, local }
 */
function distributeModels(models, workers) {
  if (!workers || workers.length === 0) {
    // All models run locally
    return models.map(model => ({
      model,
      hostname: 'local',
      local: true
    }));
  }

  // Distribute models across workers (round-robin)
  return models.map((model, i) => ({
    model,
    hostname: workers[i % workers.length].hostname,
    local: false
  }));
}

/**
 * Get execution summary for logging
 * @param {any} args - Workflow args
 * @param {Object[]} workers - Fleet workers (from getFleetWorkers)
 * @returns {string} Human-readable execution mode description
 */
function getExecutionSummary(args, workers) {
  const fleetOpts = parseFleetArgs(args);

  if (fleetOpts.localOnly) {
    return 'Local-only execution (--local-only flag)';
  }

  const cwd = process.cwd();
  if (cwd.startsWith('/home/sfloess/Development/redhat/')) {
    return 'Local-only execution (Red Hat compliance)';
  }

  if (!workers || workers.length === 0) {
    return 'Local-only execution (fleet unavailable)';
  }

  const hostnames = workers.map(w => w.hostname).join(', ');
  const specs = workers.map(w => `${w.cpus}C/${w.memory_gb}GB`).join(', ');

  return `Distributed execution: ${workers.length} workers (${hostnames}) [${specs}]`;
}

/**
 * Execute command across fleet workers (workflow-safe wrapper)
 * NOTE: This returns agent prompts, not direct SSH execution
 * (workflows must use agent() calls, not execSync)
 *
 * @param {Object[]} workers - Fleet workers
 * @param {string} command - Command to execute
 * @param {Object} options - Execution options
 * @returns {Array} Array of agent prompt objects for parallel() execution
 */
function createFleetAgentPrompts(workers, command, options = {}) {
  const basePrompt = options.prompt || `Execute: ${command}`;
  const schema = options.schema || null;

  return workers.map(worker => ({
    prompt: `${basePrompt} on ${worker.hostname}`,
    label: `${options.labelPrefix || 'exec'}-${worker.hostname}`,
    schema: schema,
    model: options.model || undefined
  }));
}

export {
  parseFleetArgs,
  shouldUseFleet,
  getFleetWorkers,
  distributeModels,
  getExecutionSummary,
  createFleetAgentPrompts
};
