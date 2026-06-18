#!/usr/bin/env node
/**
 * Fleet API Policy Enforcer
 *
 * Ensures worker nodes (aio-01, server-01/02/03) only use:
 * - Local Ollama models
 * - Free APIs (Groq, DeepInfra, Together, etc.)
 *
 * laptop-01 (primary) can use paid APIs (Anthropic, OpenAI)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const POLICY_FILE = path.join(__dirname, 'fleet-api-policy.json');

class FleetAPIEnforcer {
  constructor() {
    this.policy = null;
    this.currentNode = os.hostname();
    this.loadPolicy();
  }

  loadPolicy() {
    try {
      const policyData = fs.readFileSync(POLICY_FILE, 'utf8');
      this.policy = JSON.parse(policyData);
    } catch (err) {
      console.error(`Failed to load fleet API policy: ${err.message}`);
      throw err;
    }
  }

  /**
   * Check if a node can use a specific model/API
   * @param {string} nodeId - Node identifier (laptop-01, aio-01, etc.)
   * @param {string} model - Model name (claude-opus-4, gpt-4o, llama-3.1-8b, etc.)
   * @returns {Object} { allowed: boolean, reason: string, alternative?: string }
   */
  checkAccess(nodeId, model) {
    const node = this.policy.nodes[nodeId];
    if (!node) {
      return {
        allowed: false,
        reason: `Unknown node: ${nodeId}`
      };
    }

    // Check local models first (always allowed)
    if (this.isLocalModel(model)) {
      return {
        allowed: true,
        reason: 'Local Ollama model'
      };
    }

    // Check if it's a free API
    const freeAPI = this.findFreeAPI(model);
    if (freeAPI && node.free_apis) {
      return {
        allowed: true,
        reason: `Free API: ${freeAPI.provider}`
      };
    }

    // Check if it's a paid API
    const paidAPI = this.findPaidAPI(model);
    if (paidAPI) {
      if (node.paid_apis && paidAPI.allowed_nodes.includes(nodeId)) {
        return {
          allowed: true,
          reason: `Paid API allowed on ${nodeId}`
        };
      } else {
        // Find alternative
        const alternative = this.findAlternative(model);
        return {
          allowed: false,
          reason: `Paid API ${paidAPI.provider} not allowed on ${nodeId} (worker node)`,
          alternative: alternative ? `Suggest ${alternative}` : 'Route to laptop-01 or use free alternative'
        };
      }
    }

    // Unknown model
    return {
      allowed: false,
      reason: `Unknown model: ${model}`,
      alternative: 'Use local Ollama model or free API'
    };
  }

  /**
   * Check if model is local (Ollama)
   */
  isLocalModel(model) {
    const localModels = this.policy.local_models.ollama.models;
    return localModels.some(m => model.includes(m) || m.includes(model));
  }

  /**
   * Find free API provider for model
   */
  findFreeAPI(model) {
    return this.policy.free_apis.find(api =>
      api.models.some(m => model.includes(m) || m.includes(model))
    );
  }

  /**
   * Find paid API provider for model
   */
  findPaidAPI(model) {
    return this.policy.paid_apis.find(api =>
      api.models.some(m => model.includes(m) || m.includes(model))
    );
  }

  /**
   * Find free alternative to paid model
   */
  findAlternative(model) {
    // Map paid models to free alternatives
    const alternatives = {
      'claude-opus-4': 'llama-3.3-70b-versatile (Groq)',
      'claude-sonnet-4.5': 'llama-3.1-70b-instruct (DeepInfra)',
      'gpt-4o': 'llama-3.1-70b-instruct (Together)',
      'gpt-4-turbo': 'mixtral-8x22b-instruct (DeepInfra)',
      'gemini-2.0-flash-exp': 'mistral-large-latest (Mistral AI free tier)'
    };

    for (const [paid, free] of Object.entries(alternatives)) {
      if (model.includes(paid)) {
        return free;
      }
    }

    return 'llama-3.1-70b-instruct (free via Groq/DeepInfra/Together)';
  }

  /**
   * Route task to appropriate node based on model requirements
   * @param {string} model - Requested model
   * @param {Array<string>} availableNodes - Available fleet nodes
   * @returns {Object} { node: string, model: string, reason: string }
   */
  routeTask(model, availableNodes = null) {
    const nodes = availableNodes || Object.keys(this.policy.nodes);

    // Try local/free models on any node first (prefer non-laptop-01)
    const workerNodes = nodes.filter(n => n !== 'laptop-01');
    for (const node of workerNodes) {
      const access = this.checkAccess(node, model);
      if (access.allowed) {
        return {
          node,
          model,
          reason: `Routed to ${node}: ${access.reason}`
        };
      }
    }

    // If paid API, must use laptop-01
    const laptopAccess = this.checkAccess('laptop-01', model);
    if (laptopAccess.allowed) {
      return {
        node: 'laptop-01',
        model,
        reason: `Routed to laptop-01: ${laptopAccess.reason}`
      };
    }

    // Fallback: Use free alternative on worker node
    const alternative = this.findAlternative(model);
    const altModel = alternative.split(' ')[0]; // Extract model name
    return {
      node: workerNodes[0] || 'laptop-01',
      model: altModel,
      reason: `Substituted ${model} with free alternative: ${alternative}`
    };
  }

  /**
   * Get list of models available on a specific node
   */
  getAvailableModels(nodeId) {
    const node = this.policy.nodes[nodeId];
    if (!node) return [];

    const models = [];

    // Local models
    if (node.local_models) {
      models.push(...this.policy.local_models.ollama.models.map(m => ({
        model: m,
        provider: 'ollama',
        type: 'local',
        cost: 0
      })));
    }

    // Free APIs
    if (node.free_apis) {
      for (const api of this.policy.free_apis) {
        models.push(...api.models.map(m => ({
          model: m,
          provider: api.provider,
          type: 'free_api',
          cost: 0,
          rate_limit: api.rate_limit
        })));
      }
    }

    // Paid APIs (only if allowed)
    if (node.paid_apis) {
      for (const api of this.policy.paid_apis) {
        if (api.allowed_nodes.includes(nodeId)) {
          models.push(...api.models.map(m => ({
            model: m,
            provider: api.provider,
            type: 'paid_api',
            cost: 'varies'
          })));
        }
      }
    }

    return models;
  }

  /**
   * Generate policy enforcement report
   */
  generateReport() {
    const report = {
      policy_version: this.policy.version,
      nodes: {}
    };

    for (const [nodeId, nodeConfig] of Object.entries(this.policy.nodes)) {
      const availableModels = this.getAvailableModels(nodeId);
      report.nodes[nodeId] = {
        role: nodeConfig.role,
        local_models: nodeConfig.local_models,
        free_apis: nodeConfig.free_apis,
        paid_apis: nodeConfig.paid_apis,
        available_model_count: availableModels.length,
        cost_estimate: nodeConfig.paid_apis ? 'variable' : '$0'
      };
    }

    return report;
  }
}

// Export
module.exports = FleetAPIEnforcer;

// CLI usage
if (require.main === module) {
  const enforcer = new FleetAPIEnforcer();

  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'check') {
    const nodeId = args[1];
    const model = args[2];
    const result = enforcer.checkAccess(nodeId, model);
    console.log(JSON.stringify(result, null, 2));
  } else if (command === 'route') {
    const model = args[1];
    const result = enforcer.routeTask(model);
    console.log(JSON.stringify(result, null, 2));
  } else if (command === 'list') {
    const nodeId = args[1];
    const models = enforcer.getAvailableModels(nodeId);
    console.log(JSON.stringify(models, null, 2));
  } else if (command === 'report') {
    const report = enforcer.generateReport();
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log(`Usage:
  node fleet-api-enforcer.js check <nodeId> <model>    # Check if node can use model
  node fleet-api-enforcer.js route <model>             # Route task to appropriate node
  node fleet-api-enforcer.js list <nodeId>             # List models available on node
  node fleet-api-enforcer.js report                    # Generate policy report

Examples:
  node fleet-api-enforcer.js check server-01 claude-opus-4
  node fleet-api-enforcer.js route gpt-4o
  node fleet-api-enforcer.js list aio-01
  node fleet-api-enforcer.js report`);
  }
}
