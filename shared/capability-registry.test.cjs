/**
 * Capability Registry Tests
 *
 * Test suite for model capability tracking and registration.
 * Tests cover:
 * - Capability registration and updates
 * - Quality filtering and model selection
 * - Metrics aggregation and confidence calculation
 * - Execution history tracking
 * - Auto-population from workflow history
 *
 * Usage: npm test -- capability-registry.test.cjs
 */

const assert = require('assert');
const {
  registerCapability,
  getCapableModels,
  updateCapabilityMetrics,
  getModelCapabilities,
  getModelSummary,
  getCapabilityCoverage,
  findBestModel,
  getExecutionHistory,
  getCapability,
  autoPopulateFromHistory,
  cleanupExecutionHistory,
  pool
} = require('./capability-registry.cjs');

// Test utilities
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Test data generators
function generateMetrics(quality = 0.85, cost = 0.05, latency = 2000) {
  return {
    quality_score: quality,
    cost_usd: cost,
    latency_ms: latency,
    success: true
  };
}

// Test suite
describe('Capability Registry', () => {
  const testModel = 'test-model-' + Date.now();
  const testCapability = 'test_capability_' + Date.now();
  let capabilityId = null;

  before(async function() {
    this.timeout(10000);
    console.log('Setting up test database connection...');
    // Verify connection
    try {
      await pool.query('SELECT NOW()');
      console.log('Database connection OK');
    } catch (error) {
      console.error('Database connection failed:', error.message);
      process.exit(1);
    }
  });

  after(async function() {
    // Clean up test data
    try {
      await pool.query(
        `DELETE FROM learning.model_capabilities WHERE model LIKE $1`,
        ['test-model-%']
      );
      await pool.end();
    } catch (error) {
      console.warn('Cleanup warning:', error.message);
    }
  });

  describe('registerCapability', () => {
    it('should register a new capability', async function() {
      this.timeout(5000);
      const result = await registerCapability(testModel, testCapability, generateMetrics());
      assert.ok(result.id, 'Should return capability ID');
      capabilityId = result.id;
    });

    it('should register multiple capabilities for same model', async function() {
      this.timeout(5000);
      const cap1 = await registerCapability(testModel, 'capability_1', generateMetrics(0.90));
      const cap2 = await registerCapability(testModel, 'capability_2', generateMetrics(0.85));
      assert.ok(cap1.id !== cap2.id, 'Different capabilities should have different IDs');
    });

    it('should handle failed executions', async function() {
      this.timeout(5000);
      const metrics = generateMetrics(0.50);
      metrics.success = false;
      const result = await registerCapability(testModel, 'failed_capability', metrics);
      assert.ok(result.id, 'Should register even with failed execution');
    });
  });

  describe('getCapableModels', () => {
    before(async function() {
      this.timeout(5000);
      // Register test data
      await registerCapability('test-model-1', 'code_generation', generateMetrics(0.92, 0.05, 2500));
      await registerCapability('test-model-2', 'code_generation', generateMetrics(0.88, 0.02, 1800));
      await registerCapability('test-model-3', 'code_generation', generateMetrics(0.75, 0.001, 800));
    });

    it('should return capable models', async function() {
      this.timeout(5000);
      const models = await getCapableModels('code_generation');
      assert.ok(models.length > 0, 'Should return capable models');
      assert.ok(models[0].quality_score >= models[1].quality_score, 'Should sort by quality');
    });

    it('should filter by quality requirement', async function() {
      this.timeout(5000);
      const models = await getCapableModels('code_generation', { min_quality: 0.90 });
      assert.ok(models.every(m => m.quality_score >= 0.90), 'All models should meet quality requirement');
    });

    it('should filter by cost requirement', async function() {
      this.timeout(5000);
      const models = await getCapableModels('code_generation', { max_cost: 0.03 });
      assert.ok(models.every(m => m.avg_cost <= 0.03), 'All models should meet cost requirement');
    });

    it('should filter by latency requirement', async function() {
      this.timeout(5000);
      const models = await getCapableModels('code_generation', { max_latency_ms: 2000 });
      assert.ok(models.every(m => m.avg_latency_ms <= 2000), 'All models should meet latency requirement');
    });

    it('should return empty array when no models match', async function() {
      this.timeout(5000);
      const models = await getCapableModels('nonexistent_capability');
      assert.strictEqual(models.length, 0, 'Should return empty array');
    });
  });

  describe('updateCapabilityMetrics', () => {
    before(async function() {
      this.timeout(5000);
      const result = await registerCapability(testModel, 'metrics_test', generateMetrics(0.80, 0.04, 2000));
      capabilityId = result.id;
    });

    it('should update capability metrics', async function() {
      this.timeout(5000);
      await updateCapabilityMetrics(capabilityId, generateMetrics(0.90, 0.05, 2200));
      const cap = await getCapability(testModel, 'metrics_test');
      assert.ok(cap.quality_score > 0.80, 'Quality should improve with higher score');
      assert.strictEqual(cap.executions, 2, 'Execution count should increment');
    });

    it('should track failure count', async function() {
      this.timeout(5000);
      const metrics = generateMetrics(0.70, 0.05, 2200);
      metrics.success = false;
      await updateCapabilityMetrics(capabilityId, metrics);
      const cap = await getCapability(testModel, 'metrics_test');
      assert.ok(cap.failure_count > 0, 'Failure count should increment');
    });

    it('should increase confidence with more executions', async function() {
      this.timeout(5000);
      await updateCapabilityMetrics(capabilityId, generateMetrics(0.85));
      await updateCapabilityMetrics(capabilityId, generateMetrics(0.88));
      const cap = await getCapability(testModel, 'metrics_test');
      assert.ok(cap.confidence > 0.3, 'Confidence should increase with more executions');
    });

    it('should cap confidence at 1.0', async function() {
      this.timeout(5000);
      // Register with many executions
      const result = await registerCapability('test-model-high-exec', 'test_cap', generateMetrics());
      for (let i = 0; i < 20; i++) {
        await updateCapabilityMetrics(result.id, generateMetrics());
      }
      const cap = await getCapability('test-model-high-exec', 'test_cap');
      assert.ok(cap.confidence <= 1.0, 'Confidence should not exceed 1.0');
    });
  });

  describe('getModelCapabilities', () => {
    before(async function() {
      this.timeout(5000);
      const model = 'test-model-caps-' + Date.now();
      await registerCapability(model, 'cap1', generateMetrics(0.90));
      await registerCapability(model, 'cap2', generateMetrics(0.85));
      await registerCapability(model, 'cap3', generateMetrics(0.80));
    });

    it('should return all capabilities for a model', async function() {
      this.timeout(5000);
      const model = 'test-model-caps-' + (Date.now() - 10);
      const caps = await getModelCapabilities(model);
      assert.ok(caps.length >= 3, 'Should return multiple capabilities');
    });

    it('should sort by quality score', async function() {
      this.timeout(5000);
      const model = 'test-model-caps-' + (Date.now() - 10);
      const caps = await getModelCapabilities(model);
      for (let i = 0; i < caps.length - 1; i++) {
        assert.ok(caps[i].quality_score >= caps[i + 1].quality_score, 'Should be sorted by quality');
      }
    });
  });

  describe('getModelSummary', () => {
    it('should return summary of all models', async function() {
      this.timeout(5000);
      const summary = await getModelSummary();
      assert.ok(Array.isArray(summary), 'Should return array');
      assert.ok(summary.length > 0, 'Should have at least one model');
      assert.ok(summary[0].num_capabilities >= 0, 'Should include capability count');
    });

    it('should include performance metrics', async function() {
      this.timeout(5000);
      const summary = await getModelSummary();
      assert.ok(summary[0].avg_quality !== undefined, 'Should include avg_quality');
      assert.ok(summary[0].avg_cost !== undefined, 'Should include avg_cost');
      assert.ok(summary[0].total_executions !== undefined, 'Should include total_executions');
    });
  });

  describe('getCapabilityCoverage', () => {
    it('should return coverage of all capabilities', async function() {
      this.timeout(5000);
      const coverage = await getCapabilityCoverage();
      assert.ok(Array.isArray(coverage), 'Should return array');
    });

    it('should filter by specific capability', async function() {
      this.timeout(5000);
      const coverage = await getCapabilityCoverage('code_generation');
      assert.ok(Array.isArray(coverage), 'Should return array');
      if (coverage.length > 0) {
        assert.strictEqual(coverage[0].capability, 'code_generation', 'Should filter by capability');
      }
    });
  });

  describe('findBestModel', () => {
    before(async function() {
      this.timeout(5000);
      await registerCapability('test-best-1', 'best_test', generateMetrics(0.95, 0.10, 3000));
      await registerCapability('test-best-2', 'best_test', generateMetrics(0.85, 0.02, 1500));
    });

    it('should return highest-quality model', async function() {
      this.timeout(5000);
      const best = await findBestModel('best_test');
      assert.ok(best, 'Should find a model');
      assert.strictEqual(best.quality_score, 0.95, 'Should return highest quality');
    });

    it('should respect quality filters', async function() {
      this.timeout(5000);
      const best = await findBestModel('best_test', { min_quality: 0.90 });
      assert.ok(best, 'Should find qualifying model');
      assert.ok(best.quality_score >= 0.90, 'Should meet quality requirement');
    });

    it('should return null when no models match', async function() {
      this.timeout(5000);
      const best = await findBestModel('nonexistent', { min_quality: 0.95 });
      assert.strictEqual(best, null, 'Should return null for no matches');
    });
  });

  describe('getExecutionHistory', () => {
    let testCapId = null;

    before(async function() {
      this.timeout(5000);
      const result = await registerCapability('test-hist', 'history_test', generateMetrics());
      testCapId = result.id;
      // Add more executions
      for (let i = 0; i < 5; i++) {
        await updateCapabilityMetrics(testCapId, generateMetrics(0.85 + i * 0.01));
      }
    });

    it('should return execution history', async function() {
      this.timeout(5000);
      const history = await getExecutionHistory(testCapId);
      assert.ok(history.length > 0, 'Should have execution history');
    });

    it('should limit results', async function() {
      this.timeout(5000);
      const history = await getExecutionHistory(testCapId, 2);
      assert.ok(history.length <= 2, 'Should respect limit');
    });

    it('should sort by most recent first', async function() {
      this.timeout(5000);
      const history = await getExecutionHistory(testCapId);
      for (let i = 0; i < history.length - 1; i++) {
        assert.ok(new Date(history[i].executed_at) >= new Date(history[i + 1].executed_at),
          'Should be sorted by most recent first');
      }
    });
  });

  describe('getCapability', () => {
    before(async function() {
      this.timeout(5000);
      await registerCapability('test-get', 'get_test', generateMetrics(0.87));
    });

    it('should retrieve existing capability', async function() {
      this.timeout(5000);
      const cap = await getCapability('test-get', 'get_test');
      assert.ok(cap, 'Should find capability');
      assert.strictEqual(cap.model, 'test-get');
      assert.strictEqual(cap.capability, 'get_test');
    });

    it('should return null for nonexistent capability', async function() {
      this.timeout(5000);
      const cap = await getCapability('nonexistent', 'nonexistent');
      assert.strictEqual(cap, null, 'Should return null');
    });
  });

  describe('cleanupExecutionHistory', () => {
    it('should delete old execution records', async function() {
      this.timeout(5000);
      const result = await cleanupExecutionHistory({ days_to_keep: 0 });
      assert.ok(result.deleted >= 0, 'Should return deleted count');
    });
  });

  describe('autoPopulateFromHistory', () => {
    it('should auto-populate from execution history', async function() {
      this.timeout(10000);
      const result = await autoPopulateFromHistory({
        from_date: '2026-06-01',
        min_executions: 1
      });
      assert.ok(result.created >= 0, 'Should return created count');
      assert.ok(result.updated >= 0, 'Should return updated count');
    });
  });
});

// Run tests if executed directly
if (require.main === module) {
  console.log('Run with: npm test -- capability-registry.test.cjs');
  console.log('Or: npx mocha capability-registry.test.cjs');
}
