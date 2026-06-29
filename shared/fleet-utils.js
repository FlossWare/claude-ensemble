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
    const config = JSON.parse(raw);

    // Normalize: convert 'nodes' to 'machines' if needed
    if (config.nodes && !config.machines) {
      config.machines = config.nodes;
    }

    return config;
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

  // Normalize: convert 'host' to 'hostname' if needed
  machines = machines.map(m => {
    if (m.host && !m.hostname) {
      return { ...m, hostname: m.host };
    }
    return m;
  });

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
 * Execute command on OpenClaw worker with automatic SSH fallback
 *
 * This is the bridge between fleet-utils (SSH) and openclaw-fleet (OpenClaw).
 * It tries OpenClaw first, falls back to SSH if unavailable.
 *
 * @param {string} hostname - Worker hostname
 * @param {string} command - Command to execute
 * @param {Object} options - Execution options
 * @param {boolean} options.useOpenClaw - Try OpenClaw first (default: true if env var set)
 * @param {number} options.timeout - Timeout in milliseconds
 * @returns {Object} { hostname, stdout, stderr, exitCode, success }
 */
export async function remoteExecWithOpenClaw(hostname, command, options = {}) {
  const {
    useOpenClaw = process.env.OPENCLAW_ENABLED === 'true',
    timeout = 120000,
  } = options;

  // Try OpenClaw first if enabled
  if (useOpenClaw) {
    try {
      // Lazy import to avoid circular dependencies
      const { openclawExec } = await import('./openclaw-fleet.js');
      const result = await openclawExec(hostname, command, { timeout });

      // If successful, return immediately
      if (result.success) {
        return result;
      }

      // If OpenClaw failed, fall through to SSH
      if (result.reason !== 'openclaw_unavailable') {
        console.warn(`OpenClaw execution failed on ${hostname}, trying SSH:`, result.stderr);
      }
    } catch (error) {
      console.warn(`OpenClaw unavailable, falling back to SSH:`, error.message);
    }
  }

  // SSH fallback (original behavior)
  return remoteExec(hostname, command, { timeout, ...options });
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

/**
 * Provider API endpoint configuration.
 * Maps provider names to their chat/completions endpoints and request formatters.
 */
const PROVIDER_CONFIG = {
  anthropic: {
    url: 'https://api.anthropic.com/v1/messages',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('anthropic', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.content?.[0]?.text || '',
      input_tokens: data.usage?.input_tokens || 0,
      output_tokens: data.usage?.output_tokens || 0,
      model: data.model || '',
      stop_reason: data.stop_reason || null
    })
  },
  openai: {
    url: 'https://api.openai.com/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('openai', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  google: {
    url: (model) => `https://generativelanguage.googleapis.com/v1beta/models/${resolveModelId('google', model)}:generateContent`,
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'x-goog-api-key': apiKey
    }),
    body: (model, prompt, maxTokens) => ({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { maxOutputTokens: maxTokens }
    }),
    parseResponse: (data) => ({
      output: data.candidates?.[0]?.content?.parts?.[0]?.text || '',
      input_tokens: data.usageMetadata?.promptTokenCount || 0,
      output_tokens: data.usageMetadata?.candidatesTokenCount || 0,
      model: '',
      stop_reason: data.candidates?.[0]?.finishReason || null
    })
  },
  groq: {
    url: 'https://api.groq.com/openai/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('groq', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  deepinfra: {
    url: 'https://api.deepinfra.com/v1/openai/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('deepinfra', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  together: {
    url: 'https://api.together.xyz/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('together', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  mistral: {
    url: 'https://api.mistral.ai/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('mistral', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  cohere: {
    url: 'https://api.cohere.com/v1/chat',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('cohere', model),
      message: prompt,
      max_tokens: maxTokens
    }),
    parseResponse: (data) => ({
      output: data.text || '',
      input_tokens: data.meta?.tokens?.input_tokens || 0,
      output_tokens: data.meta?.tokens?.output_tokens || 0,
      model: '',
      stop_reason: data.finish_reason || null
    })
  },
  ai21: {
    url: 'https://api.ai21.com/studio/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('ai21', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  deepseek: {
    url: 'https://api.deepseek.com/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('deepseek', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  cerebras: {
    url: 'https://api.cerebras.ai/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('cerebras', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  openrouter: {
    url: 'https://openrouter.ai/api/v1/chat/completions',
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      model: resolveModelId('openrouter', model),
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }]
    }),
    parseResponse: (data) => ({
      output: data.choices?.[0]?.message?.content || '',
      input_tokens: data.usage?.prompt_tokens || 0,
      output_tokens: data.usage?.completion_tokens || 0,
      model: data.model || '',
      stop_reason: data.choices?.[0]?.finish_reason || null
    })
  },
  cloudflare: {
    url: (model) => `https://api.cloudflare.com/client/v4/accounts/${process.env.CLOUDFLARE_ACCOUNT_ID || 'YOUR_ACCOUNT_ID'}/ai/run/${resolveModelId('cloudflare', model)}`,
    headers: (apiKey) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    }),
    body: (model, prompt, maxTokens) => ({
      messages: [{ role: 'user', content: prompt }],
      max_tokens: maxTokens
    }),
    parseResponse: (data) => ({
      output: data.result?.response || '',
      input_tokens: 0,
      output_tokens: 0,
      model: '',
      stop_reason: null
    })
  }
};

/**
 * Resolve shorthand model names to full API model IDs.
 * @param {string} provider - Provider name
 * @param {string} model - Model shorthand or full name
 * @returns {string} Full model ID for the API
 */
function resolveModelId(provider, model) {
  const MODEL_ID_MAP = {
    anthropic: {
      'opus': 'claude-opus-4',
      'sonnet': 'claude-sonnet-4-5',
      'haiku': 'claude-haiku-4'
    },
    openai: {
      'gpt-4o': 'gpt-4o',
      'gpt-4-turbo': 'gpt-4-turbo',
      'gpt-3.5-turbo': 'gpt-3.5-turbo'
    },
    google: {
      'gemini': 'gemini-1.5-pro',
      'gemini-2.0-flash-exp': 'gemini-2.0-flash-exp',
      'gemini-1.5-pro': 'gemini-1.5-pro'
    },
    groq: {
      'llama-3.3-70b-versatile': 'llama-3.3-70b-versatile',
      'llama-3.1-8b-instant': 'llama-3.1-8b-instant',
      'mixtral-8x7b-32768': 'mixtral-8x7b-32768'
    },
    deepinfra: {
      'meta-llama/Meta-Llama-3.1-70B-Instruct': 'meta-llama/Meta-Llama-3.1-70B-Instruct'
    },
    together: {
      'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo': 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo'
    },
    mistral: {
      'mistral-large-latest': 'mistral-large-latest',
      'mistral-small-latest': 'mistral-small-latest'
    },
    cohere: {
      'command-r-plus': 'command-r-plus'
    },
    ai21: {
      'jamba-1.5-large': 'jamba-1.5-large',
      'jamba-1.5-mini': 'jamba-1.5-mini'
    },
    deepseek: {
      'deepseek-chat': 'deepseek-chat',
      'deepseek-coder': 'deepseek-coder',
      'deepseek-reasoner': 'deepseek-reasoner'
    },
    cerebras: {
      'llama-3.3-70b': 'llama-3.3-70b',
      'llama-3.1-8b': 'llama-3.1-8b'
    },
    openrouter: {
      'meta-llama/llama-3.3-70b-instruct': 'meta-llama/llama-3.3-70b-instruct',
      'anthropic/claude-sonnet-4': 'anthropic/claude-sonnet-4',
      'google/gemini-2.0-flash-exp': 'google/gemini-2.0-flash-exp'
    },
    cloudflare: {
      '@cf/meta/llama-3.3-70b-instruct-fp8-fast': '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
      '@cf/meta/llama-3.1-8b-instruct': '@cf/meta/llama-3.1-8b-instruct'
    }
  };

  return MODEL_ID_MAP[provider]?.[model] || model;
}

/**
 * Map model shorthand to provider name.
 * @param {string} model - Model name or shorthand
 * @returns {string} Provider name
 */
export function mapModelToProvider(model) {
  if (!model || typeof model !== 'string') return 'anthropic';

  const m = model.toLowerCase();
  if (m.includes('claude') || m === 'opus' || m === 'sonnet' || m === 'haiku') return 'anthropic';
  if (m.includes('gpt') || m.startsWith('o1') || m.startsWith('o3')) return 'openai';
  if (m.includes('gemini')) return 'google';
  if (m.includes('llama') && !m.includes('together') && !m.includes('deepinfra')) return 'groq';
  if (m.includes('mixtral') && m.includes('32768')) return 'groq';
  if (m.includes('deepinfra') || m === 'meta-llama/Meta-Llama-3.1-70B-Instruct') return 'deepinfra';
  if (m.includes('together') || m.includes('Turbo')) return 'together';
  if (m.includes('mistral')) return 'mistral';
  if (m.includes('command') || m.includes('cohere')) return 'cohere';
  if (m.includes('jamba') || m.includes('ai21')) return 'ai21';
  if (m.includes('deepseek')) return 'deepseek';
  if (m.includes('cerebras')) return 'cerebras';
  if (m.includes('openrouter')) return 'openrouter';
  if (m.includes('@cf/') || m.includes('cloudflare') || m.includes('workers-ai')) return 'cloudflare';
  return 'anthropic';
}

/**
 * Execute a task on an LLM API directly (no SSH, no remote execution).
 *
 * This is the core function that replaces dummy echo commands with real LLM API calls.
 * It resolves credentials, selects the correct provider endpoint, makes the HTTP request,
 * and returns a normalized result with output text, token counts, and timing.
 *
 * @param {Object} options - Execution options
 * @param {string} options.task - The prompt/task to send to the LLM
 * @param {string} [options.model='sonnet'] - Model shorthand or full name
 * @param {number} [options.maxTokens=4096] - Maximum output tokens
 * @param {number} [options.timeoutMs=120000] - Request timeout in milliseconds
 * @param {string} [options.apiKey] - Override API key (otherwise looked up from env/config)
 * @returns {Promise<Object>} { output, input_tokens, output_tokens, model, provider, duration_ms, success }
 * @throws {Error} If no API key found or provider unknown
 *
 * @example
 *   import { executeRemoteLLMTask } from './shared/fleet-utils.js';
 *   const result = await executeRemoteLLMTask({ task: 'Explain monads', model: 'sonnet' });
 *   console.log(result.output);
 */
export async function executeRemoteLLMTask(options) {
  const {
    task,
    model = 'sonnet',
    provider: providerOverride,
    maxTokens = 4096,
    timeoutMs = 120000,
    apiKey: apiKeyOverride
  } = options;

  if (!task || typeof task !== 'string') {
    throw new Error('task must be a non-empty string');
  }

  const provider = providerOverride || mapModelToProvider(model);
  const providerConfig = PROVIDER_CONFIG[provider];

  if (!providerConfig) {
    throw new Error(`Unknown provider "${provider}" for model "${model}". Supported: ${Object.keys(PROVIDER_CONFIG).join(', ')}`);
  }

  // Resolve API key: explicit override > env var > credentials.json
  let apiKey = apiKeyOverride;
  if (!apiKey) {
    const envVarName = `${provider.toUpperCase()}_API_KEY`;
    apiKey = process.env[envVarName];
  }
  if (!apiKey) {
    const credPath = path.join(os.homedir(), '.claude', 'credentials.json');
    if (fs.existsSync(credPath)) {
      try {
        const creds = JSON.parse(fs.readFileSync(credPath, 'utf8'));
        apiKey = creds[provider];
      } catch (e) {
        // ignore parse errors
      }
    }
  }

  if (!apiKey) {
    throw new Error(
      `No API key found for provider "${provider}" (model: "${model}").\n` +
      `Set ${provider.toUpperCase()}_API_KEY env var or add to ~/.claude/credentials.json`
    );
  }

  // Build request
  const url = typeof providerConfig.url === 'function'
    ? providerConfig.url(model)
    : providerConfig.url;
  const headers = providerConfig.headers(apiKey);
  const body = JSON.stringify(providerConfig.body(model, task, maxTokens));

  const startTime = Date.now();

  // Make the HTTP request using native fetch (Node 18+)
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body,
      signal: controller.signal
    });

    clearTimeout(timer);
    const duration_ms = Date.now() - startTime;

    if (!response.ok) {
      const errorBody = await response.text().catch(() => '');
      throw new Error(
        `API request failed: HTTP ${response.status} ${response.statusText}\n` +
        `Provider: ${provider}, Model: ${model}\n` +
        `Response: ${errorBody.slice(0, 500)}`
      );
    }

    const data = await response.json();
    const parsed = providerConfig.parseResponse(data);

    return {
      ...parsed,
      provider,
      duration_ms,
      success: true
    };
  } catch (error) {
    clearTimeout(timer);
    const duration_ms = Date.now() - startTime;

    if (error.name === 'AbortError') {
      throw new Error(
        `API request timed out after ${timeoutMs}ms.\n` +
        `Provider: ${provider}, Model: ${model}`
      );
    }

    // Re-throw with context if it's not already our error
    if (!error.message.includes('API request failed')) {
      throw new Error(
        `API request error: ${error.message}\n` +
        `Provider: ${provider}, Model: ${model}, Duration: ${duration_ms}ms`
      );
    }

    throw error;
  }
}

/**
 * Determine whether to use fleet distribution based on flags, availability, and break-even threshold.
 *
 * Fleet mode decision tree:
 * 1. If --local flag: return { mode: 'local', workers: [], reason: '...' }
 * 2. If --fleet flag: load fleet, throw if unavailable, return { mode: 'fleet', workers: [...], reason: '...' }
 * 3. Auto-detect: load fleet (may be empty), check break-even threshold
 *    - No workers available: local
 *    - Item count < threshold: local (overhead not worth it)
 *    - Item count >= threshold: fleet
 *
 * @param {Array|string} args - Command-line arguments (may include --fleet or --local)
 * @param {number} itemCount - Number of items to process (PDFs, URLs, files, repos, etc.)
 * @param {number} breakEvenThreshold - Minimum item count before fleet is worthwhile (e.g., 10 PDFs, 20 URLs)
 * @returns {Object} { mode: 'fleet'|'local', workers: Array<Object>, reason: string }
 * @throws {Error} If --fleet required but fleet unavailable
 *
 * @example
 *   const args = ['file1.pdf', 'file2.pdf', '--fleet'];
 *   const decision = resolveFleetMode(args, 2, 10);
 *   if (decision.mode === 'fleet') {
 *     console.log(`Distribute across ${decision.workers.length} workers`);
 *   }
 */
export function resolveFleetMode(args, itemCount, breakEvenThreshold = 10) {
  // Normalize args to array
  const argArray = Array.isArray(args) ? args : (typeof args === 'string' ? args.split(/\s+/) : []);

  // Check for explicit --local flag (takes priority)
  if (argArray.includes('--local')) {
    return {
      mode: 'local',
      workers: [],
      reason: 'Explicit --local flag'
    };
  }

  // Check for explicit --fleet flag
  if (argArray.includes('--fleet')) {
    let workers = [];
    try {
      workers = getWorkers({ skipHealthCheck: false });
    } catch (error) {
      throw new Error(
        `Fleet required (--fleet flag) but unavailable:\n` +
        `${error.message}\n\n` +
        `Troubleshooting:\n` +
        `  1. Ensure ~/.claude/fleet.json exists\n` +
        `  2. Run: cat ~/.claude/fleet.json | jq '.machines[] | .hostname'\n` +
        `  3. Test connectivity: ssh <hostname> echo OK\n` +
        `  4. Remove --fleet flag to auto-detect (or use --local for sequential)`
      );
    }

    if (workers.length === 0) {
      throw new Error(
        `Fleet required (--fleet flag) but no workers are healthy.\n` +
        `Check fleet.json and worker SSH accessibility.`
      );
    }

    return {
      mode: 'fleet',
      workers,
      reason: `${workers.length} workers available (--fleet flag)`
    };
  }

  // Auto-detect: Try to load fleet, but don't fail if unavailable
  let workers = [];
  try {
    workers = getWorkers({ skipHealthCheck: false });
  } catch (error) {
    // Fleet unavailable - continue with local mode
    workers = [];
  }

  // No workers available - use local
  if (workers.length === 0) {
    return {
      mode: 'local',
      workers: [],
      reason: 'No fleet workers available (auto-detect)'
    };
  }

  // Workers available - check break-even threshold
  if (itemCount < breakEvenThreshold) {
    return {
      mode: 'local',
      workers: [],
      reason: `Item count (${itemCount}) below break-even threshold (${breakEvenThreshold})`
    };
  }

  // Fleet is viable
  return {
    mode: 'fleet',
    workers,
    reason: `${workers.length} workers available, ${itemCount} items >= ${breakEvenThreshold} threshold`
  };
}
