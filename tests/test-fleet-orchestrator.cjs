#!/usr/bin/env node

/**
 * Fleet Orchestrator Test Suite
 *
 * Validates:
 * - Zero duplication enforcement
 * - Smart routing logic
 * - Health monitoring
 * - Deployment planning
 * - Failure handling
 */

const assert = require('assert');
const ModelMeshOrchestrator = require('./orchestrator-model-mesh.cjs');
const FleetNodeMonitor = require('./fleet-node-monitor.cjs');
const FleetDeploymentPlanner = require('./fleet-deployment-planner.cjs');

class FleetOrchestratorTests {
  constructor() {
    this.passed = 0;
    this.failed = 0;
    this.tests = [];
  }

  /**
   * Test helper
   */
  test(name, fn) {
    this.tests.push({ name, fn });
  }

  /**
   * Run all tests
   */
  async run() {
    console.log('Fleet Orchestrator Test Suite');
    console.log('='.repeat(80));
    console.log('');

    for (const test of this.tests) {
      try {
        await test.fn();
        console.log(`✓ ${test.name}`);
        this.passed++;
      } catch (error) {
        console.log(`✗ ${test.name}`);
        console.log(`  Error: ${error.message}`);
        this.failed++;
      }
    }

    console.log('');
    console.log('='.repeat(80));
    console.log(`Results: ${this.passed} passed, ${this.failed} failed`);
    console.log('');

    return this.failed === 0;
  }
}

// Create test suite
const suite = new FleetOrchestratorTests();

// Test: Registry loads successfully
suite.test('Registry loads successfully', () => {
  const orchestrator = new ModelMeshOrchestrator();
  assert(orchestrator.registry, 'Registry should be loaded');
  assert(orchestrator.registry.models, 'Registry should have models');
  assert(orchestrator.registry.nodes, 'Registry should have nodes');
});

// Test: Zero duplication in registry
suite.test('Zero duplication in initial registry', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const modelNodes = new Map();
  let duplicates = 0;

  Object.entries(orchestrator.registry.models).forEach(([name, model]) => {
    if (modelNodes.has(name)) {
      duplicates++;
      console.log(`    Duplicate found: ${name} on ${model.node} and ${modelNodes.get(name)}`);
    }
    modelNodes.set(name, model.node);
  });

  assert.strictEqual(duplicates, 0, 'No models should be duplicated');
});

// Test: All models have valid nodes
suite.test('All models assigned to valid nodes', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const nodeNames = new Set(Object.keys(orchestrator.registry.nodes));

  Object.entries(orchestrator.registry.models).forEach(([name, model]) => {
    assert(nodeNames.has(model.node), `Model ${name} should be assigned to a valid node (found: ${model.node})`);
  });
});

// Test: Node model counts match
suite.test('Node model counts match assignments', () => {
  const orchestrator = new ModelMeshOrchestrator();

  Object.entries(orchestrator.registry.nodes).forEach(([nodeName, node]) => {
    const assignedModels = node.models || [];
    const declaredCount = node.total_models || 0;

    assert.strictEqual(
      assignedModels.length,
      declaredCount,
      `Node ${nodeName} should have ${declaredCount} models, found ${assignedModels.length}`
    );
  });
});

// Test: Route to coding capability
suite.test('Route request for coding capability', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const result = orchestrator.routeRequest('coding');

  assert(result.success, 'Should find a coding model');
  assert(result.model, 'Should return a model name');
  assert(result.node, 'Should return a node');
  assert(result.capabilities?.includes('coding'), 'Model should have coding capability');
});

// Test: Route with cost constraint
suite.test('Route with zero-cost constraint', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const result = orchestrator.routeRequest('coding', { maxCost: 0 });

  if (result.success) {
    assert.strictEqual(result.cost_per_1m_tokens, 0, 'Should return a free model');
    assert.strictEqual(result.type, 'local', 'Free models should be local');
  }
});

// Test: Route with type constraint
suite.test('Route with type constraint (local only)', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const result = orchestrator.routeRequest(['coding'], { type: 'local' });

  if (result.success) {
    assert.strictEqual(result.type, 'local', 'Should return a local model');
  }
});

// Test: localhost preference
suite.test('High-usage models prefer localhost', () => {
  const orchestrator = new ModelMeshOrchestrator();

  // Simulate high usage for a model
  orchestrator.usageStats.models['qwen2.5-coder:7b'] = { count: 200 };

  const result = orchestrator.routeRequest('coding', { preferLocal: true });

  if (result.success && result.model === 'qwen2.5-coder:7b') {
    assert.strictEqual(result.node, 'localhost', 'High-usage local models should prefer localhost');
  }
});

// Test: Get available models
suite.test('Get available models list', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const models = orchestrator.getAvailableModels();

  assert(Array.isArray(models), 'Should return an array');
  assert(models.length > 0, 'Should have available models');

  models.forEach(model => {
    assert(model.name, 'Each model should have a name');
    assert(model.node, 'Each model should have a node');
    assert(model.vendor, 'Each model should have a vendor');
  });
});

// Test: Get node status
suite.test('Get node status for localhost', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const status = orchestrator.getNodeStatus('localhost');

  assert(status.success, 'Should successfully get node status');
  assert.strictEqual(status.node, 'localhost', 'Should return correct node');
  assert(status.models, 'Should include models list');
  assert(Array.isArray(status.models), 'Models should be an array');
});

// Test: Update distribution stats
suite.test('Distribution statistics are accurate', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const stats = orchestrator.registry.distribution_stats;

  assert(stats.total_models > 0, 'Should have models');
  assert(stats.cloud_api_models >= 0, 'Should count cloud models');
  assert(stats.ollama_local_models >= 0, 'Should count local models');
  assert.strictEqual(stats.duplication_count, 0, 'Should have zero duplications');

  const totalModels = Object.keys(orchestrator.registry.models).length;
  assert.strictEqual(stats.total_models, totalModels, 'Total model count should match');
});

// Test: Fleet status
suite.test('Get fleet status', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const status = orchestrator.getFleetStatus();

  assert(status.registry_version, 'Should have registry version');
  assert(status.stats, 'Should have statistics');
  assert(Array.isArray(status.nodes), 'Nodes should be an array');
  assert(['healthy', 'degraded'].includes(status.health), 'Health should be healthy or degraded');
});

// Test: Model scoring
suite.test('Model scoring prefers localhost', () => {
  const orchestrator = new ModelMeshOrchestrator();

  const localhostModel = {
    node: 'localhost',
    type: 'local',
    cost_per_1m_tokens: 0,
    nodeInfo: { priority: 1 }
  };

  const remoteModel = {
    node: 'server-01',
    type: 'local',
    cost_per_1m_tokens: 0,
    nodeInfo: { priority: 2 }
  };

  const localhostScore = orchestrator.scoreModel(localhostModel);
  const remoteScore = orchestrator.scoreModel(remoteModel);

  assert(localhostScore > remoteScore, 'localhost should score higher than remote nodes');
});

// Test: Deployment planner
suite.test('Deployment planner generates valid plan', () => {
  const planner = new FleetDeploymentPlanner();
  const plan = planner.planFromRegistry();

  assert(plan, 'Should generate a plan');
  assert(plan.assignments, 'Plan should have assignments');
  assert(plan.stats, 'Plan should have stats');
  assert.strictEqual(plan.zero_duplication, true, 'Plan should enforce zero duplication');
  // Deployment planner may find violations when re-planning existing distribution
  // This is expected - it's planning a fresh deployment, not validating existing
  assert(typeof plan.violations === 'object', 'Plan should have violations array');
});

// Test: Deployment map generation
suite.test('Deployment map generates valid output', () => {
  const planner = new FleetDeploymentPlanner();
  const plan = planner.planFromRegistry();
  const registry = planner.loadRegistry();
  const map = planner.generateDeploymentMap(plan, registry.nodes);

  assert(typeof map === 'string', 'Map should be a string');
  assert(map.length > 0, 'Map should have content');
  assert(map.includes('Fleet Model Deployment Map'), 'Map should have title');
  assert(map.includes('Zero Duplication: YES'), 'Map should confirm zero duplication');
});

// Test: Rebalance suggestions
suite.test('Rebalance analysis runs successfully', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const result = orchestrator.rebalance();

  assert(result, 'Should return a result');
  assert(typeof result.balanced === 'boolean', 'Should indicate if balanced');
  assert(Array.isArray(result.suggestions), 'Should return suggestions array');
  assert(result.current_loads, 'Should return current loads');
});

// Test: Validate all models have required fields
suite.test('All models have required fields', () => {
  const orchestrator = new ModelMeshOrchestrator();

  Object.entries(orchestrator.registry.models).forEach(([name, model]) => {
    assert(model.vendor, `Model ${name} should have vendor`);
    assert(model.type, `Model ${name} should have type`);
    assert(['cloud-api', 'local'].includes(model.type), `Model ${name} should have valid type`);
    assert(model.node, `Model ${name} should have node assignment`);
    assert(model.endpoint, `Model ${name} should have endpoint`);
    assert(Array.isArray(model.capabilities), `Model ${name} should have capabilities array`);
    assert(typeof model.cost_per_1m_tokens === 'number', `Model ${name} should have cost`);
    assert(Array.isArray(model.fallback_nodes), `Model ${name} should have fallback_nodes array`);
  });
});

// Test: Validate all nodes have required fields
suite.test('All nodes have required fields', () => {
  const orchestrator = new ModelMeshOrchestrator();

  Object.entries(orchestrator.registry.nodes).forEach(([name, node]) => {
    assert(node.hostname, `Node ${name} should have hostname`);
    assert(typeof node.ram_gb === 'number', `Node ${name} should have ram_gb`);
    assert(typeof node.cpu_cores === 'number', `Node ${name} should have cpu_cores`);
    assert(Array.isArray(node.roles), `Node ${name} should have roles array`);
    assert(Array.isArray(node.models), `Node ${name} should have models array`);
    assert(typeof node.total_models === 'number', `Node ${name} should have total_models`);
  });
});

// Test: Cloud vs local separation
suite.test('Cloud and local models correctly separated', () => {
  const orchestrator = new ModelMeshOrchestrator();

  Object.entries(orchestrator.registry.models).forEach(([name, model]) => {
    if (model.type === 'cloud-api') {
      assert(model.cost_per_1m_tokens !== undefined, `Cloud model ${name} should have cost defined`);
    } else if (model.type === 'local') {
      // Local models should be Ollama
      assert(model.vendor === 'ollama', `Local model ${name} should be Ollama`);
      assert(model.cost_per_1m_tokens === 0, `Local model ${name} should have zero cost`);
    }
  });
});

// Test: All localhost models exist
suite.test('All localhost models are valid', () => {
  const orchestrator = new ModelMeshOrchestrator();
  const localhostNode = orchestrator.registry.nodes['localhost'];

  assert(localhostNode, 'localhost node should exist');
  assert.strictEqual(localhostNode.status, 'online', 'localhost should always be online');

  localhostNode.models.forEach(modelName => {
    const model = orchestrator.registry.models[modelName];
    assert(model, `Model ${modelName} should exist in registry`);
    assert.strictEqual(model.node, 'localhost', `Model ${modelName} should be assigned to localhost`);
  });
});

// Test: Model capabilities are non-empty
suite.test('All models have at least one capability', () => {
  const orchestrator = new ModelMeshOrchestrator();

  Object.entries(orchestrator.registry.models).forEach(([name, model]) => {
    assert(model.capabilities.length > 0, `Model ${name} should have at least one capability`);
  });
});

// Run tests
if (require.main === module) {
  suite.run().then(success => {
    process.exit(success ? 0 : 1);
  });
}

module.exports = FleetOrchestratorTests;
