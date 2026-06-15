#!/usr/bin/env node

/**
 * Test Hardware-Aware Auto-Distribution System
 *
 * Validates that the hardware probing and auto-distribution works correctly.
 */

const FleetHardwareProber = require('./fleet-hardware-prober.cjs');
const FleetAutoDistributor = require('./fleet-auto-distributor.cjs');
const fs = require('fs');
const path = require('path');

class DistributionTester {
  constructor() {
    this.prober = new FleetHardwareProber();
    this.distributor = new FleetAutoDistributor();
    this.results = {
      timestamp: new Date().toISOString(),
      tests: [],
      passed: 0,
      failed: 0
    };
  }

  /**
   * Run a test and record result
   */
  test(name, fn) {
    console.log(`\n🧪 Test: ${name}`);
    try {
      const result = fn();
      if (result) {
        console.log(`   ✅ PASS`);
        this.results.tests.push({ name, status: 'PASS', error: null });
        this.results.passed++;
      } else {
        console.log(`   ❌ FAIL`);
        this.results.tests.push({ name, status: 'FAIL', error: 'Test returned false' });
        this.results.failed++;
      }
    } catch (error) {
      console.log(`   ❌ FAIL: ${error.message}`);
      this.results.tests.push({ name, status: 'FAIL', error: error.message });
      this.results.failed++;
    }
  }

  /**
   * Test hardware probe on localhost
   */
  async testLocalhostProbe() {
    console.log('\n=== Testing Hardware Probe ===\n');

    const profile = await this.prober.probeNode('localhost');

    this.test('Localhost reachable', () => profile.reachable === true);
    this.test('CPU cores detected', () => profile.cpu?.cores > 0);
    this.test('RAM detected', () => profile.ram?.total_gb > 0);
    this.test('Disk space detected', () => profile.disk?.total_gb > 0);
    this.test('Node classification', () => {
      const classification = this.prober.classifyNode(profile);
      return classification.tier >= 1 && classification.tier <= 4;
    });

    console.log('\nLocalhost Profile:');
    console.log(`  CPU: ${profile.cpu?.cores || 0} cores`);
    console.log(`  RAM: ${profile.ram?.total_gb || 0}GB (${profile.ram?.available_gb || 0}GB available)`);
    console.log(`  Disk: ${profile.disk?.available_gb || 0}GB free`);
    console.log(`  Ollama: ${profile.ollama?.installed ? 'Installed' : 'Not installed'}`);
    if (profile.ollama?.installed) {
      console.log(`  Ollama Models: ${profile.ollama?.model_count || 0}`);
    }
  }

  /**
   * Test model requirements loading
   */
  testModelRequirements() {
    console.log('\n=== Testing Model Requirements ===\n');

    const requirements = this.distributor.loadModelRequirements();

    this.test('Requirements file exists', () => requirements !== null);
    this.test('Models defined', () => Object.keys(requirements.models).length > 0);
    this.test('Cloud API models defined', () => {
      const cloudModels = Object.values(requirements.models).filter(m => m.type === 'cloud-api');
      return cloudModels.length > 0;
    });
    this.test('Local models defined', () => {
      const localModels = Object.values(requirements.models).filter(m => m.type === 'local');
      return localModels.length > 0;
    });
    this.test('Model has RAM requirements', () => {
      const model = requirements.models['deepseek-r1:32b'];
      return model && model.ram_gb > 0;
    });

    console.log(`\n  Total models: ${Object.keys(requirements.models).length}`);
    const cloudCount = Object.values(requirements.models).filter(m => m.type === 'cloud-api').length;
    const localCount = Object.values(requirements.models).filter(m => m.type === 'local').length;
    console.log(`  Cloud API: ${cloudCount}`);
    console.log(`  Local Ollama: ${localCount}`);
  }

  /**
   * Test auto-distribution algorithm
   */
  async testAutoDistribution() {
    console.log('\n=== Testing Auto-Distribution ===\n');

    const distribution = await this.distributor.autoDistribute(['localhost']);

    this.test('Distribution generated', () => distribution !== null);
    this.test('Localhost assignment exists', () => distribution.assignments.localhost !== undefined);
    this.test('Models assigned to localhost', () => {
      return distribution.assignments.localhost?.models.length > 0;
    });
    this.test('Zero duplication', () => {
      const modelCounts = new Map();
      Object.values(distribution.assignments).forEach(assignment => {
        assignment.models.forEach(model => {
          modelCounts.set(model, (modelCounts.get(model) || 0) + 1);
        });
      });
      const duplicates = Array.from(modelCounts.values()).filter(count => count > 1);
      return duplicates.length === 0;
    });
    this.test('No capacity violations', () => {
      const capacityViolations = distribution.violations.filter(v => v.type === 'no_capacity');
      return capacityViolations.length === 0;
    });
    this.test('Statistics calculated', () => {
      return distribution.stats && distribution.stats.total_models > 0;
    });
    this.test('Distribution is valid', () => distribution.valid === true);

    console.log('\nDistribution Summary:');
    console.log(`  Total models: ${distribution.stats.total_models}`);
    console.log(`  Cloud API: ${distribution.stats.cloud_api_models}`);
    console.log(`  Local: ${distribution.stats.local_models}`);
    console.log(`  Violations: ${distribution.violations.length}`);
    console.log(`  Valid: ${distribution.valid ? 'Yes' : 'No'}`);
  }

  /**
   * Test bin-packing algorithm
   */
  async testBinPacking() {
    console.log('\n=== Testing Bin-Packing Algorithm ===\n');

    // Create mock hardware profiles
    const mockProfiles = {
      'node-1': {
        hostname: 'node-1',
        reachable: true,
        cpu: { cores: 8 },
        ram: { total_gb: 31, available_gb: 28 },
        disk: { total_gb: 500, available_gb: 400 },
        ollama: { installed: true, models: [], model_count: 0 },
        api_keys: {}
      },
      'node-2': {
        hostname: 'node-2',
        reachable: true,
        cpu: { cores: 4 },
        ram: { total_gb: 15, available_gb: 12 },
        disk: { total_gb: 200, available_gb: 150 },
        ollama: { installed: true, models: [], model_count: 0 },
        api_keys: {}
      }
    };

    // Create distribution
    const distribution = {
      timestamp: new Date().toISOString(),
      hardware_profiles: mockProfiles,
      assignments: {
        'node-1': { models: [], cloud_api_count: 0, local_count: 0, total_size_gb: 0, ram_used_gb: 0, ram_available_gb: 28, ram_total_gb: 31 },
        'node-2': { models: [], cloud_api_count: 0, local_count: 0, total_size_gb: 0, ram_used_gb: 0, ram_available_gb: 12, ram_total_gb: 15 }
      },
      violations: []
    };

    // Test models with different sizes
    const testModels = [
      { name: 'large-model', type: 'local', ram_gb: 19, cpu_cores_min: 4 },
      { name: 'medium-model', type: 'local', ram_gb: 9, cpu_cores_min: 2 },
      { name: 'small-model', type: 'local', ram_gb: 4, cpu_cores_min: 2 }
    ];

    // Assign models
    const usageStats = { models: {} };
    testModels.forEach(model => {
      const nodeName = this.distributor.selectNodeForLocalModel(model, mockProfiles, distribution, usageStats);
      if (nodeName) {
        distribution.assignments[nodeName].models.push(model.name);
        distribution.assignments[nodeName].ram_used_gb += model.ram_gb;
        distribution.assignments[nodeName].ram_available_gb -= model.ram_gb;
      }
    });

    this.test('Large model assigned to node-1', () => distribution.assignments['node-1'].models.includes('large-model'));
    this.test('Medium model assigned', () => {
      return distribution.assignments['node-1'].models.includes('medium-model') ||
             distribution.assignments['node-2'].models.includes('medium-model');
    });
    this.test('Small model assigned', () => {
      return distribution.assignments['node-1'].models.includes('small-model') ||
             distribution.assignments['node-2'].models.includes('small-model');
    });
    this.test('All models assigned', () => {
      const totalAssigned = Object.values(distribution.assignments).reduce((sum, a) => sum + a.models.length, 0);
      return totalAssigned === testModels.length;
    });

    console.log('\nBin-Packing Results:');
    Object.entries(distribution.assignments).forEach(([nodeName, assignment]) => {
      console.log(`  ${nodeName}: ${assignment.models.join(', ')}`);
      console.log(`    RAM used: ${assignment.ram_used_gb}GB / ${assignment.ram_total_gb}GB`);
    });
  }

  /**
   * Run all tests
   */
  async runAll() {
    console.log('╔═══════════════════════════════════════════════════════════════╗');
    console.log('║  Hardware-Aware Auto-Distribution Test Suite                 ║');
    console.log('╚═══════════════════════════════════════════════════════════════╝');

    await this.testLocalhostProbe();
    this.testModelRequirements();
    await this.testAutoDistribution();
    await this.testBinPacking();

    console.log('\n' + '='.repeat(80));
    console.log('Test Results Summary');
    console.log('='.repeat(80));
    console.log(`Total Tests: ${this.results.tests.length}`);
    console.log(`Passed: ${this.results.passed} ✅`);
    console.log(`Failed: ${this.results.failed} ❌`);
    console.log('');

    if (this.results.failed > 0) {
      console.log('Failed Tests:');
      this.results.tests
        .filter(t => t.status === 'FAIL')
        .forEach(t => {
          console.log(`  ❌ ${t.name}: ${t.error}`);
        });
    }

    const exitCode = this.results.failed > 0 ? 1 : 0;
    console.log('');
    console.log(exitCode === 0 ? '✅ All tests passed!' : '❌ Some tests failed');

    // Save results
    const resultsPath = path.join(__dirname, 'test-results-distribution.json');
    fs.writeFileSync(resultsPath, JSON.stringify(this.results, null, 2));
    console.log(`\nResults saved to: ${resultsPath}`);

    return exitCode;
  }
}

// Run tests
if (require.main === module) {
  const tester = new DistributionTester();
  tester.runAll().then(exitCode => {
    process.exit(exitCode);
  }).catch(error => {
    console.error('Test runner failed:', error);
    process.exit(1);
  });
}

module.exports = DistributionTester;
