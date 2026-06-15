/**
 * Ollama Client for claude-global-skills
 *
 * Provides SSH-based integration with Ollama models across the fleet.
 * Leverages fleet orchestrator for routing, executes via SSH + ollama CLI.
 *
 * Usage:
 *   import { ollamaAgent } from './shared/ollama-client.js';
 *   const result = await ollamaAgent(prompt, {
 *     model: 'starcoder2:7b',
 *     schema: BUG_SCHEMA,  // Optional - forces structured output
 *     host: 'server-01'     // Optional - auto-routes if omitted
 *   });
 */

import { execFileSync } from 'child_process';
import http from 'http';

/**
 * HTTP agent with keep-alive enabled for connection pooling
 * Reuses TCP connections instead of creating new ones per request
 *
 * Note: keepAlive effectiveness depends on pi-02 HTTP server support.
 * If server doesn't support keep-alive headers, agent still works but
 * creates new connections per request. Current config uses reasonable
 * defaults (30s probes, max 10 sockets).
 */
const httpAgent = new http.Agent({
  keepAlive: true,
  keepAliveMsecs: 30000,  // Send keep-alive probes every 30s
  maxSockets: 10,          // Max concurrent connections
  maxFreeSockets: 5        // Max idle connections to keep open
});

/**
 * Query fleet orchestrator for optimal host for a model
 */
async function routeToHost(modelName) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'pi-02',
      port: 8888,
      path: `/models`,
      method: 'GET',
      timeout: 5000,
      agent: httpAgent
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const response = JSON.parse(data);
          const model = response.models.find(m => m.name === modelName);

          if (!model) {
            // Fallback: try server-01 (most capable)
            resolve({ host: 'server-01', port: 11434, fallback: true });
            return;
          }

          // For now, default to server-01 (all 4 hosts have same models)
          // TODO: orchestrator should return host mapping
          resolve({ host: 'server-01', port: 11434 });
        } catch (err) {
          reject(new Error(`Failed to parse orchestrator response: ${err.message}`));
        }
      });
    });

    req.on('error', (err) => {
      // Orchestrator down - fallback to server-01
      resolve({ host: 'server-01', port: 11434, fallback: true });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ host: 'server-01', port: 11434, fallback: true });
    });

    req.end();
  });
}

/**
 * Execute Ollama via SSH + CLI (not HTTP API)
 *
 * Ollama HTTP API isn't exposed on network, so we use SSH to run ollama CLI
 */
function ollamaExecuteSSH(host, model, prompt, options = {}) {
  // Escape prompt for bash (single quotes prevent expansion)
  const escapedPrompt = prompt.replace(/'/g, "'\"'\"'");

  try {
    const result = execFileSync('ssh', [
      host,
      `ollama run ${model} '${escapedPrompt}' 2>/dev/null`
    ], {
      encoding: 'utf8',
      timeout: options.timeout || 120000,  // 2 min default
      maxBuffer: 10 * 1024 * 1024  // 10MB
    });

    return result.trim();
  } catch (err) {
    throw new Error(`SSH ollama execution failed on ${host}: ${err.message}`);
  }
}

/**
 * Parse structured output from Ollama response
 */
function parseStructuredOutput(text, schema) {
  // Extract JSON from text (may have markdown code blocks or extra text)
  let jsonText = text;

  // Remove markdown code blocks if present
  const jsonMatch = text.match(/```(?:json)?\s*(\{[\s\S]*\})\s*```/);
  if (jsonMatch) {
    jsonText = jsonMatch[1];
  }

  // Try to find JSON object
  const jsonObjectMatch = jsonText.match(/\{[\s\S]*\}/);
  if (jsonObjectMatch) {
    jsonText = jsonObjectMatch[0];
  }

  try {
    const parsed = JSON.parse(jsonText);

    // Basic validation against schema
    if (schema && schema.required) {
      for (const requiredField of schema.required) {
        if (!(requiredField in parsed)) {
          throw new Error(`Missing required field: ${requiredField}`);
        }
      }
    }

    return parsed;
  } catch (err) {
    throw new Error(`Failed to parse JSON: ${err.message}\nRaw: ${text.substring(0, 200)}`);
  }
}

/**
 * Ollama Agent - Drop-in replacement for Claude Code agent() API
 *
 * @param {string} prompt - The prompt to send
 * @param {object} options - Options
 * @param {string} options.model - Model name (e.g., 'starcoder2:7b')
 * @param {string} options.label - Label for logging
 * @param {object} options.schema - JSON schema for structured output
 * @param {string} options.host - Override host (skips routing)
 * @param {number} options.retries - Number of retries (default 2)
 * @returns {Promise<string|object>} Generated text or parsed object if schema provided
 */
async function ollamaAgent(prompt, options = {}) {
  const modelName = options.model || 'phi3.5:latest';
  const label = options.label || modelName;
  const retries = options.retries || 2;

  // Route to best host
  let routing;
  if (options.host) {
    routing = { host: options.host };
  } else {
    routing = await routeToHost(modelName);
  }

  console.error(`[ollama] ${label} → ${routing.host} (${modelName})`);

  // If schema requested, augment prompt
  let augmentedPrompt = prompt;
  if (options.schema) {
    augmentedPrompt = `${prompt}

IMPORTANT: Return ONLY valid JSON matching this schema. No other text.
${JSON.stringify(options.schema, null, 2)}`;
  }

  // Execute with retries
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const rawResponse = ollamaExecuteSSH(
        routing.host,
        modelName,
        augmentedPrompt,
        options
      );

      // Parse structured output if schema provided
      if (options.schema) {
        try {
          return parseStructuredOutput(rawResponse, options.schema.properties ? options.schema : null);
        } catch (parseErr) {
          if (attempt < retries) {
            console.error(`[ollama] ${label} parse failed (attempt ${attempt + 1}/${retries + 1}): ${parseErr.message}`);
            lastError = parseErr;
            continue;
          }
          throw parseErr;
        }
      }

      return rawResponse;

    } catch (err) {
      lastError = err;
      if (attempt < retries) {
        console.error(`[ollama] ${label} failed (attempt ${attempt + 1}/${retries + 1}): ${err.message}`);
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
      }
    }
  }

  console.error(`[ollama] ${label} FAILED after ${retries + 1} attempts: ${lastError.message}`);
  return null;
}

/**
 * Batch multiple Ollama calls in parallel
 */
async function ollamaParallel(agentCalls) {
  return Promise.all(agentCalls.map(call => call()));
}

/**
 * Get available models from orchestrator
 */
async function getAvailableModels() {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'pi-02',
      port: 8888,
      path: '/models',
      method: 'GET',
      timeout: 5000,
      agent: httpAgent
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const response = JSON.parse(data);
          resolve(response.models.map(m => m.name));
        } catch (err) {
          reject(err);
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Orchestrator timeout'));
    });

    req.end();
  });
}

/**
 * Test Ollama connectivity
 */
async function testOllamaConnection(host = 'server-01', model = 'phi3.5:latest') {
  try {
    const response = await ollamaAgent('Reply with just "OK"', { host, model, timeout: 30000 });
    return { success: true, response };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

export {
  ollamaAgent,
  ollamaParallel,
  getAvailableModels,
  testOllamaConnection,
  routeToHost
};

// CLI test interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];

  switch (command) {
    case 'test':
      const testHost = process.argv[3] || 'server-01';
      console.log(`Testing Ollama on ${testHost}...`);
      testOllamaConnection(testHost)
        .then(result => {
          console.log('Ollama connection test:', result.success ? '✅ PASS' : '❌ FAIL');
          if (result.success) console.log('Response:', result.response);
          else console.error('Error:', result.error);
          process.exit(result.success ? 0 : 1);
        });
      break;

    case 'models':
      getAvailableModels()
        .then(models => {
          console.log(`Available Ollama models (${models.length}):`);
          models.forEach(m => console.log(`  - ${m}`));
        })
        .catch(err => {
          console.error('Failed to get models:', err.message);
          process.exit(1);
        });
      break;

    case 'generate':
      const genHost = process.argv[3] || 'server-01';
      const genModel = process.argv[4] || 'phi3.5:latest';
      const genPrompt = process.argv[5] || 'Say hello in one sentence';
      console.log(`Generating with ${genModel} on ${genHost}...`);
      ollamaAgent(genPrompt, { host: genHost, model: genModel })
        .then(response => {
          console.log('Generated response:');
          console.log(response);
        })
        .catch(err => {
          console.error('Generation failed:', err.message);
          process.exit(1);
        });
      break;

    default:
      console.log(`Ollama Client CLI

Usage:
  node ollama-client.js test [host]                    Test connection
  node ollama-client.js models                         List available models
  node ollama-client.js generate [host] [model] "..."  Generate text

Examples:
  node ollama-client.js test server-01
  node ollama-client.js models
  node ollama-client.js generate server-01 starcoder2:7b "Write hello world in Java"
`);
  }
}
