#!/usr/bin/env node

/**
 * NAS Model Manager - Centralized model distribution system
 *
 * Manages downloading models to NAS and distributing them to fleet nodes.
 * Integrates with fleet-auto-distributor for optimal model placement.
 *
 * Features:
 * - Download models once to NAS (save bandwidth)
 * - Distribute via gigabit LAN (fast local network)
 * - Track model inventory and distribution status
 * - Calculate bandwidth savings
 * - Verify model integrity
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class NASModelManager {
  constructor(options = {}) {
    this.nasModelsDir = options.nasModelsDir || process.env.NAS_MODELS_DIR || '/mnt/nas/ai-models';
    this.modelsDir = path.join(this.nasModelsDir, 'ollama');
    this.manifestsDir = path.join(this.nasModelsDir, 'manifests');
    this.inventoryFile = path.join(this.manifestsDir, 'model-inventory.json');
    this.distributionLog = path.join(this.manifestsDir, 'distribution-log.json');
    this.scriptsDir = path.join(__dirname, 'scripts');
    this.downloadScript = path.join(this.scriptsDir, 'download-to-nas.sh');
    this.distributeScript = path.join(this.scriptsDir, 'distribute-to-nodes.sh');
    this.fleetRegistry = path.join(__dirname, 'fleet-model-registry.json');
    this.modelRequirements = path.join(__dirname, 'model-requirements.json');
  }

  /**
   * Check if NAS is mounted and accessible
   */
  checkNASAvailable() {
    try {
      return fs.existsSync(this.nasModelsDir);
    } catch (error) {
      return false;
    }
  }

  /**
   * Load model inventory
   */
  loadInventory() {
    try {
      if (!fs.existsSync(this.inventoryFile)) {
        return {
          _comment: "NAS Model Inventory - Central repository of downloaded models",
          _version: "1.0",
          _last_updated: new Date().toISOString(),
          nas_path: this.nasModelsDir,
          models: {}
        };
      }

      const data = fs.readFileSync(this.inventoryFile, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load inventory:', error.message);
      return null;
    }
  }

  /**
   * Load distribution log
   */
  loadDistributionLog() {
    try {
      if (!fs.existsSync(this.distributionLog)) {
        return {
          _comment: "Distribution log - Track model deployment to nodes",
          distributions: []
        };
      }

      const data = fs.readFileSync(this.distributionLog, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load distribution log:', error.message);
      return null;
    }
  }

  /**
   * Load fleet registry
   */
  loadFleetRegistry() {
    try {
      if (!fs.existsSync(this.fleetRegistry)) {
        return null;
      }

      const data = fs.readFileSync(this.fleetRegistry, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load fleet registry:', error.message);
      return null;
    }
  }

  /**
   * Download model to NAS
   */
  downloadModel(modelName) {
    console.log(`Downloading model to NAS: ${modelName}`);

    try {
      const result = execSync(`${this.downloadScript} "${modelName}"`, {
        encoding: 'utf8',
        stdio: 'inherit'
      });

      return {
        success: true,
        model: modelName
      };
    } catch (error) {
      return {
        success: false,
        model: modelName,
        error: error.message
      };
    }
  }

  /**
   * Download multiple models
   */
  downloadModels(modelNames) {
    console.log(`Downloading ${modelNames.length} models to NAS...`);

    const results = {
      success: [],
      failed: []
    };

    for (const model of modelNames) {
      const result = this.downloadModel(model);
      if (result.success) {
        results.success.push(model);
      } else {
        results.failed.push({ model, error: result.error });
      }
    }

    return results;
  }

  /**
   * Download all local models from model-requirements.json
   */
  downloadAllModels() {
    console.log('Downloading all local models...');

    try {
      execSync(`${this.downloadScript} --all`, {
        encoding: 'utf8',
        stdio: 'inherit'
      });

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Download high-priority models
   */
  downloadHighPriorityModels() {
    console.log('Downloading high-priority models...');

    try {
      execSync(`${this.downloadScript} --high-priority`, {
        encoding: 'utf8',
        stdio: 'inherit'
      });

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Distribute model to assigned node(s)
   */
  distributeModel(modelName) {
    console.log(`Distributing model: ${modelName}`);

    try {
      execSync(`${this.distributeScript} "${modelName}"`, {
        encoding: 'utf8',
        stdio: 'inherit'
      });

      return {
        success: true,
        model: modelName
      };
    } catch (error) {
      return {
        success: false,
        model: modelName,
        error: error.message
      };
    }
  }

  /**
   * Distribute all models to specific node
   */
  distributeToNode(nodeName) {
    console.log(`Distributing models to node: ${nodeName}`);

    try {
      execSync(`${this.distributeScript} --node "${nodeName}"`, {
        encoding: 'utf8',
        stdio: 'inherit'
      });

      return {
        success: true,
        node: nodeName
      };
    } catch (error) {
      return {
        success: false,
        node: nodeName,
        error: error.message
      };
    }
  }

  /**
   * Distribute all models according to fleet registry
   */
  distributeAll() {
    console.log('Distributing all models to fleet...');

    try {
      execSync(this.distributeScript, {
        encoding: 'utf8',
        stdio: 'inherit'
      });

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Get inventory summary
   */
  getInventorySummary() {
    const inventory = this.loadInventory();
    if (!inventory) {
      return null;
    }

    const models = Object.keys(inventory.models || {});
    let totalSize = 0;
    const distributionCounts = {};

    for (const [modelName, modelInfo] of Object.entries(inventory.models || {})) {
      totalSize += modelInfo.size_gb || 0;

      const nodeCount = modelInfo.distributed_to?.length || 0;
      distributionCounts[modelName] = nodeCount;
    }

    return {
      total_models: models.length,
      total_size_gb: totalSize.toFixed(2),
      models: models,
      distribution_counts: distributionCounts,
      last_updated: inventory._last_updated,
      nas_path: inventory.nas_path
    };
  }

  /**
   * Get distribution statistics
   */
  getDistributionStats() {
    const log = this.loadDistributionLog();
    const inventory = this.loadInventory();

    if (!log || !inventory) {
      return null;
    }

    const stats = {
      total_distributions: log.distributions.length,
      successful: log.distributions.filter(d => d.status === 'success').length,
      failed: log.distributions.filter(d => d.status === 'failed').length,
      models_distributed: new Set(log.distributions.map(d => d.model)).size,
      nodes_served: new Set(log.distributions.map(d => d.node)).size,
      last_distribution: log.distributions[log.distributions.length - 1]
    };

    return stats;
  }

  /**
   * Calculate bandwidth savings
   *
   * Compares downloading from internet to each node vs.
   * downloading once to NAS and distributing via LAN
   */
  calculateBandwidthSavings() {
    const inventory = this.loadInventory();
    if (!inventory) {
      return null;
    }

    const internetSpeedMbps = 100; // Typical internet speed
    const lanSpeedMbps = 1000;     // Gigabit LAN

    let totalDataTransferred = 0;
    let totalNodesServed = 0;

    for (const [modelName, modelInfo] of Object.entries(inventory.models || {})) {
      const sizeGB = modelInfo.size_gb || 0;
      const nodesServed = modelInfo.distributed_to?.length || 0;

      totalDataTransferred += sizeGB * nodesServed;
      totalNodesServed += nodesServed;
    }

    // Calculate time to download
    const internetDownloadTimeMinutes = (totalDataTransferred * 8192 / internetSpeedMbps) / 60;
    const nasDownloadTimeMinutes = (totalDataTransferred * 8192 / lanSpeedMbps) / 60;

    // NAS approach: download once to NAS + distribute via LAN
    const modelsCount = Object.keys(inventory.models).length;
    const totalModelSize = Object.values(inventory.models).reduce((sum, m) => sum + (m.size_gb || 0), 0);

    const nasApproachTimeMinutes =
      (totalModelSize * 8192 / internetSpeedMbps) / 60 +  // Download to NAS
      (totalDataTransferred * 8192 / lanSpeedMbps) / 60;  // Distribute to nodes

    // Internet approach: download to each node separately
    const internetApproachTimeMinutes = internetDownloadTimeMinutes;

    const timeSavedMinutes = internetApproachTimeMinutes - nasApproachTimeMinutes;
    const bandwidthSavedGB = totalDataTransferred - totalModelSize;

    return {
      total_models: modelsCount,
      total_model_size_gb: totalModelSize.toFixed(2),
      total_data_transferred_gb: totalDataTransferred.toFixed(2),
      nodes_served: totalNodesServed,
      internet_approach: {
        time_minutes: internetApproachTimeMinutes.toFixed(1),
        time_hours: (internetApproachTimeMinutes / 60).toFixed(2)
      },
      nas_approach: {
        time_minutes: nasApproachTimeMinutes.toFixed(1),
        time_hours: (nasApproachTimeMinutes / 60).toFixed(2)
      },
      savings: {
        time_minutes: timeSavedMinutes.toFixed(1),
        time_hours: (timeSavedMinutes / 60).toFixed(2),
        bandwidth_gb: bandwidthSavedGB.toFixed(2),
        efficiency_gain: ((timeSavedMinutes / internetApproachTimeMinutes) * 100).toFixed(1) + '%'
      }
    };
  }

  /**
   * Verify model integrity
   */
  verifyModel(modelName) {
    console.log(`Verifying model: ${modelName}`);

    try {
      execSync(`${this.downloadScript} --verify "${modelName}"`, {
        encoding: 'utf8',
        stdio: 'inherit'
      });

      return {
        success: true,
        model: modelName
      };
    } catch (error) {
      return {
        success: false,
        model: modelName,
        error: error.message
      };
    }
  }

  /**
   * Get models missing from NAS (assigned but not downloaded)
   */
  getMissingModels() {
    const registry = this.loadFleetRegistry();
    const inventory = this.loadInventory();

    if (!registry || !inventory) {
      return null;
    }

    const assignedModels = new Set();
    const downloadedModels = new Set(Object.keys(inventory.models || {}));

    // Get all local models from registry
    for (const [modelName, modelInfo] of Object.entries(registry.models || {})) {
      if (modelInfo.type === 'local') {
        assignedModels.add(modelName);
      }
    }

    // Find missing models
    const missing = [];
    for (const model of assignedModels) {
      if (!downloadedModels.has(model)) {
        missing.push(model);
      }
    }

    return missing;
  }

  /**
   * Complete deployment workflow
   *
   * 1. Download models to NAS
   * 2. Distribute to nodes
   */
  async deployFleet(options = {}) {
    const results = {
      download: null,
      distribution: null,
      success: false
    };

    console.log('Starting fleet deployment workflow...\n');

    // Step 1: Download models to NAS
    if (options.downloadAll) {
      console.log('Step 1: Downloading all models to NAS...');
      results.download = this.downloadAllModels();
    } else if (options.downloadHighPriority) {
      console.log('Step 1: Downloading high-priority models to NAS...');
      results.download = this.downloadHighPriorityModels();
    } else if (options.models?.length > 0) {
      console.log(`Step 1: Downloading ${options.models.length} models to NAS...`);
      results.download = this.downloadModels(options.models);
    } else {
      console.log('Step 1: Skipping download (no models specified)');
      results.download = { success: true, skipped: true };
    }

    if (results.download && !results.download.success) {
      console.error('Download failed, aborting deployment');
      return results;
    }

    console.log('\n');

    // Step 2: Distribute to nodes
    if (options.node) {
      console.log(`Step 2: Distributing to node: ${options.node}...`);
      results.distribution = this.distributeToNode(options.node);
    } else {
      console.log('Step 2: Distributing to all nodes...');
      results.distribution = this.distributeAll();
    }

    results.success = results.distribution?.success || false;

    console.log('\n');
    console.log('Deployment Summary');
    console.log('==================');
    console.log(`Download: ${results.download?.success ? 'SUCCESS' : 'FAILED'}`);
    console.log(`Distribution: ${results.distribution?.success ? 'SUCCESS' : 'FAILED'}`);
    console.log(`Overall: ${results.success ? 'SUCCESS' : 'FAILED'}`);

    return results;
  }

  /**
   * Generate deployment report
   */
  generateReport() {
    const inventory = this.getInventorySummary();
    const stats = this.getDistributionStats();
    const savings = this.calculateBandwidthSavings();
    const missing = this.getMissingModels();

    const report = {
      timestamp: new Date().toISOString(),
      nas_available: this.checkNASAvailable(),
      inventory,
      distribution: stats,
      bandwidth_savings: savings,
      missing_models: missing,
      recommendations: []
    };

    // Add recommendations
    if (missing && missing.length > 0) {
      report.recommendations.push({
        priority: 'high',
        action: 'download_missing_models',
        message: `${missing.length} models are assigned but not downloaded to NAS`,
        models: missing
      });
    }

    if (stats && stats.failed > 0) {
      report.recommendations.push({
        priority: 'medium',
        action: 'retry_failed_distributions',
        message: `${stats.failed} distributions failed and may need retry`
      });
    }

    if (inventory && inventory.total_size_gb > 500) {
      report.recommendations.push({
        priority: 'low',
        action: 'check_nas_capacity',
        message: `NAS is storing ${inventory.total_size_gb}GB of models, verify capacity`
      });
    }

    return report;
  }
}

// Export for use in other modules
module.exports = NASModelManager;

// CLI interface
if (require.main === module) {
  const manager = new NASModelManager();
  const command = process.argv[2];
  const args = process.argv.slice(3);

  (async () => {
    switch (command) {
      case 'download':
        if (args.includes('--all')) {
          manager.downloadAllModels();
        } else if (args.includes('--high-priority')) {
          manager.downloadHighPriorityModels();
        } else if (args.length > 0) {
          manager.downloadModels(args);
        } else {
          console.error('Please specify models to download or use --all / --high-priority');
          process.exit(1);
        }
        break;

      case 'distribute':
        if (args[0] === '--node' && args[1]) {
          manager.distributeToNode(args[1]);
        } else if (args.length === 1) {
          manager.distributeModel(args[0]);
        } else {
          manager.distributeAll();
        }
        break;

      case 'deploy':
        const deployOptions = {};
        if (args.includes('--all')) {
          deployOptions.downloadAll = true;
        } else if (args.includes('--high-priority')) {
          deployOptions.downloadHighPriority = true;
        }
        if (args.includes('--node')) {
          const nodeIdx = args.indexOf('--node');
          deployOptions.node = args[nodeIdx + 1];
        }

        await manager.deployFleet(deployOptions);
        break;

      case 'summary':
        const summary = manager.getInventorySummary();
        console.log('\nNAS Model Inventory Summary');
        console.log('============================');
        console.log(JSON.stringify(summary, null, 2));
        break;

      case 'stats':
        const stats = manager.getDistributionStats();
        console.log('\nDistribution Statistics');
        console.log('=======================');
        console.log(JSON.stringify(stats, null, 2));
        break;

      case 'savings':
        const savings = manager.calculateBandwidthSavings();
        console.log('\nBandwidth Savings Analysis');
        console.log('==========================');
        console.log(JSON.stringify(savings, null, 2));
        break;

      case 'report':
        const report = manager.generateReport();
        console.log('\nNAS Model Manager Report');
        console.log('========================');
        console.log(JSON.stringify(report, null, 2));
        break;

      case 'verify':
        if (args.length === 0) {
          console.error('Please specify model name to verify');
          process.exit(1);
        }
        manager.verifyModel(args[0]);
        break;

      case 'missing':
        const missing = manager.getMissingModels();
        console.log('\nModels Missing from NAS');
        console.log('========================');
        if (missing && missing.length > 0) {
          missing.forEach(model => console.log(`  - ${model}`));
          console.log(`\nTotal: ${missing.length} models`);
        } else {
          console.log('All assigned models are downloaded to NAS');
        }
        break;

      default:
        console.log(`
NAS Model Manager - Centralized model distribution system

Usage:
  nas-model-manager.cjs <command> [options]

Commands:
  download [models...]          Download models to NAS
  download --all                Download all local models
  download --high-priority      Download high-priority models

  distribute [model]            Distribute model to assigned node
  distribute --node <name>      Distribute all models to specific node
  distribute                    Distribute all models to fleet

  deploy [--all | --high-priority] [--node <name>]
                                Complete deployment workflow

  summary                       Show inventory summary
  stats                         Show distribution statistics
  savings                       Calculate bandwidth savings
  report                        Generate comprehensive report
  verify <model>                Verify model integrity
  missing                       Show models missing from NAS

Examples:
  nas-model-manager.cjs download --high-priority
  nas-model-manager.cjs distribute --node server-02
  nas-model-manager.cjs deploy --all
  nas-model-manager.cjs report
  nas-model-manager.cjs savings
        `);
        process.exit(0);
    }
  })();
}
