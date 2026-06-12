/**
 * Fleet Utilities - Distributed execution across personal fleet
 *
 * Provides fleet discovery, health checking, and remote execution
 * with automatic Red Hat compliance enforcement.
 *
 * Usage:
 *   import { getWorkers, remoteExec } from './shared/fleet-utils.js';
 *   const workers = getWorkers({ minMemoryGb: 16 });
 *   const results = await Promise.all(workers.map(w =>
 *     remoteExec(w.hostname, 'make test')
 *   ));
 *
 * SECURITY: All SSH commands are properly escaped. Never build SSH
 * commands manually - always use remoteExec() or probeHealth().
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';

// In-memory cache for health probe results (per workflow invocation)
let healthCache = null;
let cacheTimestamp = 0;
const CACHE_TTL_MS = 30000; // 30 seconds

/**
 * Load fleet configuration from ~/.claude/fleet.json
 * @returns {Object} Fleet configuration
 */
export function loadFleetConfig() {
  const configPath = path.join(os.homedir(), '.claude', 'fleet.json');

  if (!fs.existsSync(configPath)) {
    throw new Error(
      `Fleet config not found: ${configPath}\n` +
      `Run this from a machine with fleet.json installed.`
    );
  }

  try {
    const raw = fs.readFileSync(configPath, 'utf8');
    return JSON.parse(raw);
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error(
        `Invalid JSON in fleet config: ${configPath}\n` +
        `Parse error: ${error.message}`
      );
    }
    throw error;
  }
}

/**
 * Validate compliance boundaries - throws if in forbidden path
 * Uses fs.realpathSync to prevent symlink bypasses
 * @param {Object} config - Fleet configuration
 * @throws {Error} If current directory violates compliance
 */
export function validateCompliance(config) {
  // Use realpath to prevent symlink bypasses
  const cwd = fs.realpathSync(process.cwd());
  const forbidden = config.compliance?.forbidden_paths || [];

  for (const p of forbidden) {
    // Normalize forbidden path too in case it contains symlinks
    const forbiddenReal = fs.existsSync(p) ? fs.realpathSync(p) : p;

    if (cwd.startsWith(forbiddenReal)) {
      throw new Error(
        `COMPLIANCE VIOLATION: Cannot use distributed fleet.\n` +
        `Current directory: ${cwd}\n` +
        `Forbidden path: ${forbiddenReal}\n` +
        `Reason: ${config.compliance?.reason || 'Unknown'}\n\n` +
        `Use --local-only to run without fleet.`
      );
    }
  }
}

/**
 * Validate hostname against allowed patterns
 * @param {string} hostname - Hostname to validate
 * @throws {Error} If hostname is invalid
 */
function validateHostname(hostname) {
  if (!hostname || typeof hostname !== 'string') {
    throw new Error('Hostname must be a non-empty string');
  }

  // Allow alphanumeric, dots, hyphens, underscores
  if (!/^[a-zA-Z0-9._-]+$/.test(hostname)) {
    throw new Error(
      `Invalid hostname: ${hostname}\n` +
      `Hostnames must contain only letters, numbers, dots, hyphens, and underscores.`
    );
  }

  // Prevent path traversal attempts
  if (hostname.includes('..') || hostname.includes('/')) {
    throw new Error(`Invalid hostname (path traversal detected): ${hostname}`);
  }
}

/**
 * Probe machine health via SSH
 * @param {string} hostname - Machine hostname
 * @param {number} timeoutMs - Timeout in milliseconds
 * @returns {boolean} True if machine is reachable
 */
export function probeHealth(hostname, timeoutMs = 2000) {
  validateHostname(hostname);

  try {
    // Fix: Use Math.max(1, Math.ceil(...)) to prevent timeout=0
    const timeoutSec = Math.max(1, Math.ceil(timeoutMs / 1000));

    // Quick SSH probe: just check if we can connect
    // SECURITY: StrictHostKeyChecking=accept-new accepts first connection, rejects key changes (prevents MITM)
    // SECURITY: BatchMode=yes prevents password prompts (prevents hangs)
    execSync(
      `ssh -o ConnectTimeout=${timeoutSec} -o BatchMode=yes -o StrictHostKeyChecking=accept-new ${hostname} 'echo ok'`,
      {
        encoding: 'utf8',
        timeout: timeoutMs,
        stdio: 'pipe'
      }
    );
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Get fleet with optional filtering and health checking
 * @param {Object} options - Filter options
 * @param {string[]} options.tags - Filter by tags (machine must have ALL)
 * @param {string[]} options.capabilities - Filter by capabilities (machine must have ALL)
 * @param {string} options.role - Filter by role (controller, worker)
 * @param {number} options.minMemoryGb - Minimum memory in GB
 * @param {number} options.minCpus - Minimum CPU count
 * @param {boolean} options.skipHealthCheck - Skip SSH health probe (default: false)
 * @param {boolean} options.localOnly - Return empty array (disable fleet)
 * @returns {Object[]} Array of available machines
 */
export function getFleet(options = {}) {
  const config = loadFleetConfig();

  // Check compliance first
  if (options.localOnly !== true) {
    validateCompliance(config);
  }

  // If local-only mode, return empty
  if (options.localOnly === true) {
    return [];
  }

  let machines = [...config.machines];

  // Filter by tags
  if (options.tags && options.tags.length > 0) {
    machines = machines.filter(m =>
      options.tags.every(tag => m.tags && m.tags.includes(tag))
    );
  }

  // Filter by capabilities
  if (options.capabilities && options.capabilities.length > 0) {
    machines = machines.filter(m =>
      options.capabilities.every(cap => m.capabilities && m.capabilities.includes(cap))
    );
  }

  // Filter by role
  if (options.role) {
    machines = machines.filter(m => m.role === options.role);
  }

  // Filter by memory
  if (options.minMemoryGb) {
    machines = machines.filter(m => m.memory_gb >= options.minMemoryGb);
  }

  // Filter by CPUs
  if (options.minCpus) {
    machines = machines.filter(m => m.cpus >= options.minCpus);
  }

  // Health check (with caching)
  if (options.skipHealthCheck !== true) {
    const now = Date.now();
    const useCached = healthCache && (now - cacheTimestamp < CACHE_TTL_MS);

    if (!useCached) {
      healthCache = new Map();
      cacheTimestamp = now;
    }

    const timeout = config.policies?.health_check_timeout_ms || 2000;

    machines = machines.filter(m => {
      // Only cache successful probes; always re-check failures
      if (useCached && healthCache.has(m.hostname) && healthCache.get(m.hostname) === true) {
        return true;
      }

      const healthy = probeHealth(m.hostname, timeout);
      healthCache.set(m.hostname, healthy);
      return healthy;
    });
  }

  // Sort by priority (lower number = higher priority)
  machines.sort((a, b) => (a.priority || 99) - (b.priority || 99));

  // Enforce max_parallel_workers policy if configured
  const maxWorkers = config.policies?.max_parallel_workers;
  if (maxWorkers && maxWorkers > 0 && machines.length > maxWorkers) {
    machines = machines.slice(0, maxWorkers);
  }

  return machines;
}

/**
 * Get worker machines (shorthand for getFleet with role=worker)
 * @param {Object} options - Filter options
 * @returns {Object[]} Array of available worker machines
 */
export function getWorkers(options = {}) {
  return getFleet({ ...options, role: 'worker' });
}

/**
 * Get controller machines (shorthand for getFleet with role=controller)
 * @param {Object} options - Filter options
 * @returns {Object[]} Array of available controller machines
 */
export function getController(options = {}) {
  const controllers = getFleet({ ...options, role: 'controller' });
  return controllers.length > 0 ? controllers[0] : null;
}

/**
 * Execute command on remote machine via SSH
 *
 * SECURITY NOTES:
 * - Commands are escaped using single-quote wrapping (prevents command injection)
 * - BatchMode=yes prevents password prompts (prevents hangs)
 * - StrictHostKeyChecking=yes requires known host (prevents MITM)
 * - Hostname is validated before use
 *
 * @param {string} hostname - Machine hostname
 * @param {string} command - Command to execute
 * @param {Object} options - Execution options
 * @param {number} options.timeout - Timeout in milliseconds
 * @param {boolean} options.throwOnError - Throw if command fails (default: false)
 * @param {string} options.cwd - Change to this directory before executing command
 * @returns {Object} { hostname, stdout, stderr, exitCode, success }
 */
export function remoteExec(hostname, command, options = {}) {
  validateHostname(hostname);

  if (!command || typeof command !== 'string') {
    throw new Error('Command must be a non-empty string');
  }

  const timeout = options.timeout || 120000; // 2 minutes default

  // Optionally prepend cd command
  let fullCommand = command;
  if (options.cwd) {
    fullCommand = `cd '${options.cwd.replace(/'/g, "'\\''")}' && ${command}`;
  }

  try {
    // SECURITY FIX: Single-quote escaping prevents command injection
    // Replace ' with '\'' (end quote, escaped quote, start quote)
    const escaped = fullCommand.replace(/'/g, "'\\''");

    // SECURITY: BatchMode=yes prevents password prompt hangs
    // SECURITY: StrictHostKeyChecking=accept-new accepts first connection, rejects key changes
    const sshCmd = `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new ${hostname} '${escaped}'`;

    const stdout = execSync(sshCmd, {
      encoding: 'utf8',
      timeout: timeout,
      stdio: 'pipe'
    });

    return {
      hostname,
      stdout: stdout.trim(),
      stderr: '',
      exitCode: 0,
      success: true
    };
  } catch (error) {
    const result = {
      hostname,
      stdout: error.stdout ? error.stdout.toString().trim() : '',
      stderr: error.stderr ? error.stderr.toString().trim() : error.message,
      exitCode: error.status || 1,
      success: false
    };

    if (options.throwOnError) {
      throw new Error(
        `Remote execution failed on ${hostname}:\n` +
        `Command: ${command}\n` +
        `Exit code: ${result.exitCode}\n` +
        `Stderr: ${result.stderr}`
      );
    }

    return result;
  }
}

/**
 * DEPRECATED: fanOut() removed
 *
 * For parallel execution across fleet workers, use the workflow parallel() API:
 *
 *   const workers = getWorkers();
 *   const results = await parallel(
 *     workers.map(w => () => remoteExec(w.hostname, 'make test'))
 *   );
 *
 * This provides true parallelism within the workflow system. fanOut() previously
 * used execSync which blocks the event loop, making "parallel" execution fake.
 *
 * If you need parallel execution outside workflow context, use Promise.all:
 *
 *   const results = await Promise.all(
 *     workers.map(w =>
 *       new Promise(resolve =>
 *         resolve(remoteExec(w.hostname, 'make test'))
 *       )
 *     )
 *   );
 *
 * But note: execSync still blocks, so this won't be truly parallel.
 * For true async, use child_process.exec (not execSync) with callbacks.
 */

/**
 * Clear health probe cache (useful for testing)
 */
export function clearHealthCache() {
  healthCache = null;
  cacheTimestamp = 0;
}
