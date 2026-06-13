/**
 * OpenClaw Gateway HTTP Client
 *
 * Provides programmatic access to OpenClaw daemon via Gateway REST API.
 * Used for multi-AI consensus integration (execution verification worker).
 */

import http from 'http';

const OPENCLAW_DEFAULT_PORT = 18789;
const OPENCLAW_TIMEOUT_MS = 240000; // 4 minutes (2x standard timeout for execution)

/**
 * Query OpenClaw agent for a response
 *
 * @param {string} hostname - Target hostname (default: localhost)
 * @param {string} prompt - Query/task for OpenClaw agent
 * @param {object} options - Configuration options
 * @param {number} options.port - Gateway port (default: 18789)
 * @param {string} options.token - API token (from OPENCLAW_API_TOKEN env)
 * @param {number} options.timeout - Request timeout in ms (default: 240000)
 * @param {object} options.schema - JSON schema for structured response
 * @returns {Promise<object>} OpenClaw response
 */
export async function openclawQuery(hostname, prompt, options = {}) {
  const {
    port = OPENCLAW_DEFAULT_PORT,
    token = process.env.OPENCLAW_API_TOKEN,
    timeout = OPENCLAW_TIMEOUT_MS,
    schema = null,
  } = options;

  const payload = JSON.stringify({
    message: prompt,
    ...(schema && { response_format: schema }),
    instruction: `You are a verification worker in a multi-AI consensus system.
Your unique role: EXECUTE CODE to verify claims, don't just reason.

1. If the claim can be tested with code/commands, RUN IT
2. Report both reasoning AND execution results
3. Flag when execution contradicts reasoning

Return structured response with:
- reasoning: Your analysis
- execution_performed: boolean
- execution_results: { command, stdout, stderr, exit_code }
- verification_status: "passed" | "failed" | "not_testable"
- confidence: 0-100 (boost when you have execution proof)`
  });

  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname,
      port,
      path: '/api/sessions/main/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        'Content-Length': Buffer.byteLength(payload),
      },
      timeout,
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve({ text: data });
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`OpenClaw timeout after ${timeout}ms`));
    });

    req.write(payload);
    req.end();
  });
}

/**
 * Health check for OpenClaw Gateway
 *
 * @param {string} hostname - Target hostname
 * @param {number} port - Gateway port (default: 18789)
 * @returns {Promise<boolean>} True if OpenClaw is healthy
 */
export function openclawHealthCheck(hostname, port = OPENCLAW_DEFAULT_PORT) {
  return new Promise((resolve) => {
    const req = http.request({
      hostname,
      port,
      path: '/api/status',
      method: 'GET',
      timeout: 3000,
    }, (res) => resolve(res.statusCode === 200));

    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

/**
 * Get OpenClaw vote for multi-AI consensus
 *
 * Gracefully degrades if OpenClaw unavailable (returns null).
 *
 * @param {string} prompt - Consensus question
 * @param {object} schema - Response schema
 * @returns {Promise<object|null>} OpenClaw vote or null if unavailable
 */
export async function getOpenClawVote(prompt, schema) {
  try {
    const host = process.env.OPENCLAW_HOST || 'localhost';
    const healthy = await openclawHealthCheck(host);

    if (!healthy) {
      return null;
    }

    const response = await openclawQuery(host, prompt, { schema });
    return {
      model: 'openclaw',
      ...response,
      label: 'Verification (OpenClaw)',
    };
  } catch (error) {
    // OpenClaw unavailable -- graceful degradation, 6-model consensus continues
    console.warn('OpenClaw unavailable:', error.message);
    return null;
  }
}
