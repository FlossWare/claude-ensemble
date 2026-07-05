#!/usr/bin/env node

/**
 * Test NAS Distribution System
 *
 * Validates the NAS model distribution system components
 */

const fs = require('fs');
const path = require('path');
const NASModelManager = require('../lib/nas-model-manager.cjs');

class NASDistributionTest {
  constructor() {
    this.manager = new NASModelManager();
    this.results = {
      passed: [],
      failed: [],
      warnings: []
    };
  }

  log(message) {
    console.log(`  ${message}`);
  }

  pass(testName, message) {
    this.results.passed.push(testName);
    console.log(`✅ ${testName}: ${message}`);
  }

  fail(testName, message) {
    this.results.failed.push(testName);
    console.log(`❌ ${testName}: ${message}`);
  }

  warn(testName, message) {
    this.results.warnings.push(testName);
    console.log(`⚠️  ${testName}: ${message}`);
  }

  /**
   * Test 1: Scripts exist and are executable
   */
  testScriptsExist() {
    console.log('\n[Test 1] Checking scripts...');

    const scripts = [
      'scripts/download-to-nas.sh',
      'scripts/distribute-to-nodes.sh',
      'nas-model-manager.cjs'
    ];

    for (const script of scripts) {
      const scriptPath = path.join(__dirname, script);

      if (!fs.existsSync(scriptPath)) {
        this.fail('script-exists', `Script not found: ${script}`);
        continue;
      }

      try {
        const stats = fs.statSync(scriptPath);
        // Check if executable (user execute bit)
        if ((stats.mode & 0o100) === 0) {
          this.fail('script-executable', `Script not executable: ${script}`);
        } else {
          this.pass('script-check', `${script} exists and is executable`);
        }
      } catch (error) {
        this.fail('script-stat', `Failed to stat ${script}: ${error.message}`);
      }
    }
  }

  /**
   * Test 2: NAS availability check
   */
  testNASAvailability() {
    console.log('\n[Test 2] Checking NAS availability...');

    const nasPath = this.manager.nasModelsDir;
    this.log(`NAS path: ${nasPath}`);

    if (this.manager.checkNASAvailable()) {
      this.pass('nas-available', `NAS is mounted at ${nasPath}`);
    } else {
      this.warn('nas-not-mounted', `NAS not mounted at ${nasPath} (use NAS_MODELS_DIR or mount NAS)`);
    }
  }

  /**
   * Test 3: Fleet registry exists
   */
  testFleetRegistry() {
    console.log('\n[Test 3] Checking fleet registry...');

    const registryPath = this.manager.fleetRegistry;
    this.log(`Registry path: ${registryPath}`);

    if (!fs.existsSync(registryPath)) {
      this.fail('registry-missing', 'Fleet registry not found');
      return;
    }

    try {
      const registry = this.manager.loadFleetRegistry();
      if (!registry) {
        this.fail('registry-load', 'Failed to load fleet registry');
        return;
      }

      this.pass('registry-exists', 'Fleet registry loaded successfully');

      // Check structure
      if (!registry.models || !registry.nodes) {
        this.fail('registry-structure', 'Invalid registry structure (missing models or nodes)');
        return;
      }

      const modelCount = Object.keys(registry.models).length;
      const nodeCount = Object.keys(registry.nodes).length;

      this.log(`  Models: ${modelCount}`);
      this.log(`  Nodes: ${nodeCount}`);

      this.pass('registry-structure', `Registry has ${modelCount} models, ${nodeCount} nodes`);
    } catch (error) {
      this.fail('registry-parse', `Failed to parse registry: ${error.message}`);
    }
  }

  /**
   * Test 4: Model requirements exists
   */
  testModelRequirements() {
    console.log('\n[Test 4] Checking model requirements...');

    const requirementsPath = this.manager.modelRequirements;
    this.log(`Requirements path: ${requirementsPath}`);

    if (!fs.existsSync(requirementsPath)) {
      this.fail('requirements-missing', 'Model requirements not found');
      return;
    }

    try {
      const data = fs.readFileSync(requirementsPath, 'utf8');
      const requirements = JSON.parse(data);

      if (!requirements.models) {
        this.fail('requirements-structure', 'Invalid requirements structure (missing models)');
        return;
      }

      const totalModels = Object.keys(requirements.models).length;
      const localModels = Object.values(requirements.models)
        .filter(m => m.type === 'local').length;

      this.log(`  Total models: ${totalModels}`);
      this.log(`  Local models: ${localModels}`);

      this.pass('requirements-exists', `Model requirements has ${localModels} local models`);
    } catch (error) {
      this.fail('requirements-parse', `Failed to parse requirements: ${error.message}`);
    }
  }

  /**
   * Test 5: Inventory loading (if NAS available)
   */
  testInventoryLoading() {
    console.log('\n[Test 5] Checking inventory...');

    if (!this.manager.checkNASAvailable()) {
      this.warn('inventory-skip', 'Skipping inventory test (NAS not available)');
      return;
    }

    const inventory = this.manager.loadInventory();

    if (!inventory) {
      this.warn('inventory-not-found', 'Inventory not found (run download-to-nas.sh first)');
      return;
    }

    const modelCount = Object.keys(inventory.models || {}).length;
    this.log(`  Models in NAS: ${modelCount}`);

    if (modelCount === 0) {
      this.warn('inventory-empty', 'No models in NAS inventory (run download-to-nas.sh)');
    } else {
      this.pass('inventory-loaded', `Inventory contains ${modelCount} models`);

      // Show summary
      const summary = this.manager.getInventorySummary();
      this.log(`  Total size: ${summary.total_size_gb}GB`);
      this.log(`  Last updated: ${summary.last_updated}`);
    }
  }

  /**
   * Test 6: Distribution log (if NAS available)
   */
  testDistributionLog() {
    console.log('\n[Test 6] Checking distribution log...');

    if (!this.manager.checkNASAvailable()) {
      this.warn('dist-log-skip', 'Skipping distribution log test (NAS not available)');
      return;
    }

    const log = this.manager.loadDistributionLog();

    if (!log) {
      this.warn('dist-log-not-found', 'Distribution log not found');
      return;
    }

    const distCount = log.distributions?.length || 0;
    this.log(`  Distributions: ${distCount}`);

    if (distCount === 0) {
      this.warn('dist-log-empty', 'No distributions logged yet');
    } else {
      this.pass('dist-log-loaded', `Distribution log has ${distCount} entries`);

      const stats = this.manager.getDistributionStats();
      if (stats) {
        this.log(`  Successful: ${stats.successful}`);
        this.log(`  Failed: ${stats.failed}`);
      }
    }
  }

  /**
   * Test 7: Missing models check
   */
  testMissingModels() {
    console.log('\n[Test 7] Checking for missing models...');

    if (!this.manager.checkNASAvailable()) {
      this.warn('missing-skip', 'Skipping missing models test (NAS not available)');
      return;
    }

    const missing = this.manager.getMissingModels();

    if (!missing) {
      this.fail('missing-check', 'Failed to check missing models');
      return;
    }

    if (missing.length === 0) {
      this.pass('no-missing', 'All assigned models are downloaded to NAS');
    } else {
      this.warn('models-missing', `${missing.length} models assigned but not downloaded`);
      missing.slice(0, 5).forEach(model => {
        this.log(`  - ${model}`);
      });
      if (missing.length > 5) {
        this.log(`  ... and ${missing.length - 5} more`);
      }
    }
  }

  /**
   * Test 8: Schema validation
   */
  testSchemas() {
    console.log('\n[Test 8] Checking schemas...');

    const schemas = [
      'schemas/model-inventory.schema.json',
      'schemas/distribution-log.schema.json'
    ];

    for (const schema of schemas) {
      const schemaPath = path.join(__dirname, schema);

      if (!fs.existsSync(schemaPath)) {
        this.fail('schema-missing', `Schema not found: ${schema}`);
        continue;
      }

      try {
        const data = fs.readFileSync(schemaPath, 'utf8');
        const schemaObj = JSON.parse(data);

        if (!schemaObj.$schema) {
          this.warn('schema-meta', `Schema missing $schema field: ${schema}`);
        } else {
          this.pass('schema-valid', `${schema} is valid JSON Schema`);
        }
      } catch (error) {
        this.fail('schema-parse', `Failed to parse ${schema}: ${error.message}`);
      }
    }
  }

  /**
   * Test 9: Integration check
   */
  testIntegration() {
    console.log('\n[Test 9] Checking integration with fleet system...');

    const registry = this.manager.loadFleetRegistry();

    if (!registry) {
      this.fail('integration-skip', 'Cannot test integration without fleet registry');
      return;
    }

    // Check if there are local models assigned
    const localModels = Object.values(registry.models || {})
      .filter(m => m.type === 'local');

    if (localModels.length === 0) {
      this.warn('no-local-models', 'No local models assigned in fleet registry');
      return;
    }

    this.pass('integration-ready', `Fleet has ${localModels.length} local models ready for NAS distribution`);

    // Check nodes with local models
    const nodesWithLocal = Object.entries(registry.nodes || {})
      .filter(([name, node]) => node.local_models > 0);

    this.log(`  Nodes with local models: ${nodesWithLocal.length}`);
    nodesWithLocal.forEach(([name, node]) => {
      this.log(`    - ${name}: ${node.local_models} models`);
    });
  }

  /**
   * Test 10: Bandwidth savings calculator
   */
  testBandwidthSavings() {
    console.log('\n[Test 10] Testing bandwidth savings calculator...');

    if (!this.manager.checkNASAvailable()) {
      this.warn('savings-skip', 'Skipping bandwidth test (NAS not available)');
      return;
    }

    const inventory = this.manager.loadInventory();
    const modelCount = Object.keys(inventory?.models || {}).length;

    if (modelCount === 0) {
      this.warn('savings-no-data', 'No models to calculate savings (NAS empty)');
      return;
    }

    try {
      const savings = this.manager.calculateBandwidthSavings();

      if (!savings) {
        this.fail('savings-calc', 'Failed to calculate bandwidth savings');
        return;
      }

      this.pass('savings-calculated', 'Bandwidth savings calculated successfully');

      this.log(`  Models: ${savings.total_models}`);
      this.log(`  Total size: ${savings.total_model_size_gb}GB`);
      this.log(`  Data transferred: ${savings.total_data_transferred_gb}GB`);
      this.log(`  Nodes served: ${savings.nodes_served}`);
      this.log(`  Time saved: ${savings.savings.time_hours} hours`);
      this.log(`  Bandwidth saved: ${savings.savings.bandwidth_gb}GB`);
      this.log(`  Efficiency gain: ${savings.savings.efficiency_gain}`);
    } catch (error) {
      this.fail('savings-error', `Savings calculation error: ${error.message}`);
    }
  }

  /**
   * Run all tests
   */
  async runAll() {
    console.log('NAS Model Distribution System - Test Suite');
    console.log('===========================================\n');

    this.testScriptsExist();
    this.testNASAvailability();
    this.testFleetRegistry();
    this.testModelRequirements();
    this.testInventoryLoading();
    this.testDistributionLog();
    this.testMissingModels();
    this.testSchemas();
    this.testIntegration();
    this.testBandwidthSavings();

    // Summary
    console.log('\n');
    console.log('Test Summary');
    console.log('============');
    console.log(`✅ Passed: ${this.results.passed.length}`);
    console.log(`❌ Failed: ${this.results.failed.length}`);
    console.log(`⚠️  Warnings: ${this.results.warnings.length}`);

    if (this.results.failed.length > 0) {
      console.log('\nFailed tests:');
      this.results.failed.forEach(test => console.log(`  - ${test}`));
    }

    if (this.results.warnings.length > 0) {
      console.log('\nWarnings:');
      this.results.warnings.forEach(test => console.log(`  - ${test}`));
    }

    console.log('\n');

    // Recommendations
    if (this.results.warnings.includes('nas-not-mounted')) {
      console.log('💡 Recommendation: Mount NAS at /mnt/nas/ai-models or set NAS_MODELS_DIR');
    }

    if (this.results.warnings.includes('inventory-empty')) {
      console.log('💡 Recommendation: Run ./scripts/download-to-nas.sh --high-priority');
    }

    if (this.results.warnings.includes('models-missing')) {
      console.log('💡 Recommendation: Run ./nas-model-manager.cjs missing to see which models to download');
    }

    // Exit code
    return this.results.failed.length === 0 ? 0 : 1;
  }
}

// Run tests
if (require.main === module) {
  const tester = new NASDistributionTest();
  tester.runAll().then(exitCode => {
    process.exit(exitCode);
  });
}

module.exports = NASDistributionTest;
