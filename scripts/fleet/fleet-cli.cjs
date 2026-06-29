#!/usr/bin/env node

/**
 * Fleet CLI - Unified command-line interface for fleet management
 *
 * Provides easy access to:
 * - Model mesh orchestration
 * - Node health monitoring
 * - Deployment planning
 * - Fleet status and diagnostics
 */

const ModelMeshOrchestrator = require('./orchestrator-model-mesh.cjs');
const FleetNodeMonitor = require('./fleet-node-monitor.cjs');
const FleetDeploymentPlanner = require('./fleet-deployment-planner.cjs');
const FleetHardwareProber = require('./fleet-hardware-prober.cjs');
const FleetAutoDistributor = require('./fleet-auto-distributor.cjs');
const NASModelManager = require('./nas-model-manager.cjs');

class FleetCLI {
  constructor() {
    this.orchestrator = new ModelMeshOrchestrator();
    this.monitor = new FleetNodeMonitor();
    this.planner = new FleetDeploymentPlanner();
    this.prober = new FleetHardwareProber();
    this.distributor = new FleetAutoDistributor();
    this.nasManager = new NASModelManager();
  }

  /**
   * Show fleet status
   */
  async status() {
    console.log('Fleet Status');
    console.log('='.repeat(80));
    console.log('');

    const status = this.orchestrator.getFleetStatus();
    console.log(`Registry Version: ${status.registry_version}`);
    console.log(`Last Updated: ${status.last_updated}`);
    console.log(`Health: ${status.health.toUpperCase()}`);
    console.log('');

    console.log('Statistics:');
    console.log(`  Total Models: ${status.stats.total_models}`);
    console.log(`  Cloud API Models: ${status.stats.cloud_api_models}`);
    console.log(`  Local Ollama Models: ${status.stats.ollama_local_models}`);
    console.log(`  Available Models: ${status.stats.available_models}`);
    console.log(`  Total Nodes: ${status.stats.total_nodes}`);
    console.log(`  Online Nodes: ${status.stats.online_nodes}`);
    console.log(`  Duplication Count: ${status.stats.duplication_count}`);
    console.log('');

    console.log('Nodes:');
    status.nodes.forEach(node => {
      const statusIcon = node.online ? '✓' : '✗';
      console.log(`  ${statusIcon} ${node.name}: ${node.models} models (${node.status})`);
    });
    console.log('');

    if (status.top_models.length > 0) {
      console.log('Most Used Models:');
      status.top_models.forEach((model, idx) => {
        console.log(`  ${idx + 1}. ${model.model} (${model.usage_count} uses)`);
      });
    }
  }

  /**
   * List all available models
   */
  models() {
    const models = this.orchestrator.getAvailableModels();
    console.log(`Available Models: ${models.length}`);
    console.log('='.repeat(80));
    console.log('');

    const grouped = {
      'cloud-api': [],
      'local': []
    };

    models.forEach(model => {
      grouped[model.type].push(model);
    });

    if (grouped['cloud-api'].length > 0) {
      console.log('Cloud API Models:');
      grouped['cloud-api'].forEach(model => {
        const cost = model.cost_per_1m_tokens === 0 ? 'FREE' : `$${model.cost_per_1m_tokens}/1M`;
        console.log(`  ${model.name}`);
        console.log(`    Vendor: ${model.vendor}`);
        console.log(`    Node: ${model.node}`);
        console.log(`    Cost: ${cost}`);
        console.log(`    Capabilities: ${model.capabilities.join(', ')}`);
        console.log('');
      });
    }

    if (grouped['local'].length > 0) {
      console.log('Local Ollama Models:');
      grouped['local'].forEach(model => {
        console.log(`  ${model.name}`);
        console.log(`    Node: ${model.node}`);
        console.log(`    Capabilities: ${model.capabilities.join(', ')}`);
        console.log('');
      });
    }
  }

  /**
   * Show node details
   */
  node(nodeName) {
    const status = this.orchestrator.getNodeStatus(nodeName);

    if (!status.success) {
      console.error(`Error: ${status.error}`);
      return;
    }

    console.log(`Node: ${status.node}`);
    console.log('='.repeat(80));
    console.log('');
    console.log(`Status: ${status.status.toUpperCase()}`);
    console.log(`Last Heartbeat: ${status.last_heartbeat || 'Never'}`);
    console.log(`RAM: ${status.ram_gb}GB`);
    console.log(`CPU Cores: ${status.cpu_cores}`);
    console.log(`Roles: ${status.roles.join(', ')}`);
    console.log(`Total Models: ${status.total_models}`);
    console.log(`Available Models: ${status.available_models}`);
    console.log('');

    if (status.models.length > 0) {
      console.log('Models:');
      status.models.forEach(model => {
        const statusIcon = model.status === 'available' ? '✓' : '✗';
        const typeLabel = model.type === 'cloud-api' ? 'Cloud' : 'Local';
        console.log(`  ${statusIcon} ${model.name} [${typeLabel}/${model.vendor}] (${model.status})`);
      });
    }
  }

  /**
   * Route request to best model
   */
  route(capability, options = {}) {
    const result = this.orchestrator.routeRequest(capability, options);

    if (!result.success) {
      console.log('Routing Failed');
      console.log('='.repeat(80));
      console.log('');
      console.log(`Error: ${result.error}`);
      console.log(`Capability: ${result.capabilities.join(', ')}`);

      if (result.suggestion?.length > 0) {
        console.log('');
        console.log('Suggested Alternatives:');
        result.suggestion.forEach(alt => {
          console.log(`  ${alt.name}`);
          console.log(`    Matching: ${alt.matching_capabilities.join(', ')}`);
          console.log(`    Missing: ${alt.missing_capabilities.join(', ')}`);
          console.log(`    Node: ${alt.node} [${alt.type}]`);
          console.log('');
        });
      }
      return;
    }

    console.log('Route Found');
    console.log('='.repeat(80));
    console.log('');
    console.log(`Model: ${result.model}`);
    console.log(`Node: ${result.node}`);
    console.log(`Vendor: ${result.vendor}`);
    console.log(`Type: ${result.type}`);
    console.log(`Endpoint: ${result.endpoint}`);
    console.log(`Cost: ${result.cost_per_1m_tokens === 0 ? 'FREE' : `$${result.cost_per_1m_tokens}/1M`}`);
    console.log(`Score: ${result.score.toFixed(2)}`);

    if (result.alternatives?.length > 0) {
      console.log('');
      console.log('Alternatives:');
      result.alternatives.forEach((alt, idx) => {
        console.log(`  ${idx + 1}. ${alt.model} on ${alt.node} (score: ${alt.score.toFixed(2)})`);
      });
    }
  }

  /**
   * Health check
   */
  async health() {
    console.log('Running health check...');
    console.log('');

    const results = await this.orchestrator.healthCheck();

    console.log('Health Check Results');
    console.log('='.repeat(80));
    console.log('');

    Object.entries(results).forEach(([nodeName, result]) => {
      const statusIcon = result.status === 'online' ? '✓' : '✗';
      console.log(`${statusIcon} ${nodeName}: ${result.status.toUpperCase()}`);
      if (result.latency_ms !== undefined) {
        console.log(`  Latency: ${result.latency_ms}ms`);
      }
      if (result.error) {
        console.log(`  Error: ${result.error}`);
      }
      console.log('');
    });
  }

  /**
   * Start monitoring
   */
  async monitor() {
    console.log('Starting continuous monitoring...');
    console.log('Press Ctrl+C to stop');
    console.log('');
    await this.monitor.startMonitoring();
  }

  /**
   * Show deployment plan
   */
  plan() {
    const plan = this.planner.planFromRegistry();
    if (!plan) {
      console.error('Failed to generate deployment plan');
      return;
    }

    const registry = this.planner.loadRegistry();
    console.log(this.planner.generateDeploymentMap(plan, registry.nodes));
  }

  /**
   * Rebalance suggestions
   */
  rebalance() {
    const result = this.orchestrator.rebalance();

    console.log('Fleet Rebalancing Analysis');
    console.log('='.repeat(80));
    console.log('');

    console.log(`Status: ${result.balanced ? 'BALANCED' : 'IMBALANCED'}`);
    console.log('');

    console.log('Current Loads:');
    Object.entries(result.current_loads).forEach(([nodeName, load]) => {
      const bar = '█'.repeat(Math.floor(load.utilization * 40));
      console.log(`  ${nodeName}: ${bar} ${(load.utilization * 100).toFixed(1)}%`);
      console.log(`    Current: ${load.current} models, Capacity: ${load.capacity}`);
    });
    console.log('');

    if (result.suggestions.length > 0) {
      console.log('Suggestions:');
      result.suggestions.forEach((suggestion, idx) => {
        console.log(`  ${idx + 1}. ${suggestion.type.toUpperCase()}`);
        console.log(`     From: ${suggestion.from.join(', ')}`);
        console.log(`     To: ${suggestion.to.join(', ')}`);
        console.log(`     Reason: ${suggestion.reason}`);
      });
    } else {
      console.log('No rebalancing needed - fleet is well-balanced');
    }
  }

  /**
   * Probe hardware on all nodes
   */
  async probeHardware() {
    console.log('Probing fleet hardware...\n');
    const profiles = await this.prober.probeFleet();
    const summary = this.prober.generateSummary(profiles);

    console.log('Fleet Hardware Summary');
    console.log('='.repeat(80));
    console.log('');
    console.log(`Reachable Nodes: ${summary.reachable_nodes}/${summary.total_nodes}`);
    console.log(`Total CPU Cores: ${summary.total_cpu_cores}`);
    console.log(`Total RAM: ${summary.total_ram_gb}GB`);
    console.log(`Total Disk: ${summary.total_disk_gb}GB`);
    console.log(`Nodes with GPU: ${summary.nodes_with_gpu}`);
    console.log(`Nodes with Ollama: ${summary.nodes_with_ollama}`);
    console.log('');
    console.log('Node Classification:');

    Object.entries(summary.nodes).forEach(([hostname, node]) => {
      const statusIcon = node.reachable ? '✓' : '✗';
      console.log(`  ${statusIcon} ${hostname}: ${node.tier_label}`);
      if (node.reachable) {
        console.log(`     ${node.cpu_cores} CPU, ${node.ram_gb}GB RAM, ${node.disk_gb}GB free`);
        if (node.has_ollama) {
          console.log(`     Ollama: ${node.ollama_models} models installed`);
        }
      }
    });

    this.prober.exportResults(profiles);
  }

  /**
   * Auto-distribute models based on hardware
   */
  async autoDistribute() {
    console.log('Starting hardware-aware auto-distribution...\n');
    const distribution = await this.distributor.autoDistribute();

    if (distribution) {
      console.log('\n' + this.distributor.generateReport(distribution));
      this.distributor.exportDistribution(distribution);

      console.log('\n📌 Next steps:');
      console.log('  1. Review the distribution plan in fleet-auto-distribution.json');
      console.log('  2. Run "fleet-cli.js update-registry" to apply the plan');
    }
  }

  /**
   * Auto-distribute and update registry
   */
  async updateRegistry() {
    console.log('Auto-distributing and updating registry...\n');
    const distribution = await this.distributor.autoDistribute();

    if (distribution) {
      console.log('\n' + this.distributor.generateReport(distribution));
      this.distributor.exportDistribution(distribution);
      await this.distributor.updateRegistry(distribution);

      console.log('\n✅ Registry updated successfully!');
      console.log('   Run "fleet-cli.js status" to see the new distribution');
    }
  }

  /**
   * Validate current distribution
   */
  async validate() {
    console.log('Validating fleet distribution...\n');

    const status = this.orchestrator.getFleetStatus();

    console.log('Validation Results');
    console.log('='.repeat(80));
    console.log('');

    // Check zero duplication
    const duplicateCheck = status.stats.duplication_count === 0;
    console.log(`Zero Duplication: ${duplicateCheck ? '✅ PASS' : '❌ FAIL'}`);
    if (!duplicateCheck) {
      console.log(`  Found ${status.stats.duplication_count} duplicated models`);
    }

    // Check all models assigned
    const totalModels = status.stats.total_models;
    console.log(`All Models Assigned: ${totalModels > 0 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Total: ${totalModels} models`);

    // Check node health
    const onlineNodes = status.stats.online_nodes;
    const totalNodes = status.stats.total_nodes;
    const healthCheck = onlineNodes > 0;
    console.log(`Node Health: ${healthCheck ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Online: ${onlineNodes}/${totalNodes} nodes`);

    console.log('');
    if (duplicateCheck && totalModels > 0 && healthCheck) {
      console.log('✅ Fleet distribution is valid!');
    } else {
      console.log('❌ Fleet distribution has issues. Consider running:');
      console.log('   fleet-cli.js update-registry');
    }
  }

  /**
   * Show node capacity and utilization
   */
  showCapacity() {
    const status = this.orchestrator.getFleetStatus();

    console.log('Fleet Capacity and Utilization');
    console.log('='.repeat(80));
    console.log('');

    status.nodes.forEach(node => {
      const statusIcon = node.online ? '✓' : '✗';
      console.log(`${statusIcon} ${node.name}`);
      console.log(`  Status: ${node.status}`);
      console.log(`  Models: ${node.models}`);
      console.log(`  Type: ${node.cloud_models} cloud, ${node.local_models} local`);
      console.log('');
    });
  }

  /**
   * NAS: Download models to NAS
   */
  async nasDownload(args) {
    if (args.includes('--all')) {
      this.nasManager.downloadAllModels();
    } else if (args.includes('--high-priority')) {
      this.nasManager.downloadHighPriorityModels();
    } else if (args.length > 0) {
      this.nasManager.downloadModels(args);
    } else {
      console.error('Usage: fleet-cli.js nas-download [--all | --high-priority | <models...>]');
      console.error('');
      console.error('Examples:');
      console.error('  fleet-cli.js nas-download --high-priority');
      console.error('  fleet-cli.js nas-download codestral:22b qwen2.5-coder:7b');
      process.exit(1);
    }
  }

  /**
   * NAS: Distribute models from NAS to nodes
   */
  async nasDistribute(args) {
    if (args[0] === '--node' && args[1]) {
      this.nasManager.distributeToNode(args[1]);
    } else if (args.length === 1) {
      this.nasManager.distributeModel(args[0]);
    } else {
      this.nasManager.distributeAll();
    }
  }

  /**
   * NAS: Complete deployment workflow
   */
  async nasDeploy(args) {
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

    await this.nasManager.deployFleet(deployOptions);
  }

  /**
   * NAS: Show status
   */
  nasStatus() {
    console.log('NAS Model Distribution Status');
    console.log('='.repeat(80));
    console.log('');

    // Check NAS availability
    const nasAvailable = this.nasManager.checkNASAvailable();
    console.log(`NAS Available: ${nasAvailable ? '✓ YES' : '✗ NO'}`);
    console.log(`NAS Path: ${this.nasManager.nasModelsDir}`);
    console.log('');

    if (!nasAvailable) {
      console.log('⚠️  NAS is not mounted. Please mount NAS at /mnt/nas/ai-models');
      console.log('   or set NAS_MODELS_DIR environment variable.');
      return;
    }

    // Show inventory summary
    const summary = this.nasManager.getInventorySummary();
    if (summary) {
      console.log('Inventory:');
      console.log(`  Total Models: ${summary.total_models}`);
      console.log(`  Total Size: ${summary.total_size_gb}GB`);
      console.log(`  Last Updated: ${summary.last_updated || 'Never'}`);
      console.log('');

      if (summary.models.length > 0) {
        console.log('Models in NAS:');
        summary.models.forEach(model => {
          const distCount = summary.distribution_counts[model] || 0;
          console.log(`  - ${model} (distributed to ${distCount} nodes)`);
        });
        console.log('');
      }
    }

    // Show distribution stats
    const stats = this.nasManager.getDistributionStats();
    if (stats && stats.total_distributions > 0) {
      console.log('Distribution Statistics:');
      console.log(`  Total Distributions: ${stats.total_distributions}`);
      console.log(`  Successful: ${stats.successful}`);
      console.log(`  Failed: ${stats.failed}`);
      console.log(`  Models Distributed: ${stats.models_distributed}`);
      console.log(`  Nodes Served: ${stats.nodes_served}`);
      console.log('');
    }

    // Show missing models
    const missing = this.nasManager.getMissingModels();
    if (missing && missing.length > 0) {
      console.log(`⚠️  Missing Models: ${missing.length}`);
      console.log('   These models are assigned but not downloaded to NAS:');
      missing.slice(0, 10).forEach(model => {
        console.log(`   - ${model}`);
      });
      if (missing.length > 10) {
        console.log(`   ... and ${missing.length - 10} more`);
      }
      console.log('');
      console.log('💡 Run: fleet-cli.js nas-download --high-priority');
    }
  }

  /**
   * NAS: Show bandwidth savings
   */
  nasSavings() {
    console.log('NAS Bandwidth Savings Analysis');
    console.log('='.repeat(80));
    console.log('');

    if (!this.nasManager.checkNASAvailable()) {
      console.log('⚠️  NAS is not available. Cannot calculate savings.');
      return;
    }

    const savings = this.nasManager.calculateBandwidthSavings();
    if (!savings) {
      console.log('No data available to calculate savings.');
      return;
    }

    console.log('Deployment Comparison');
    console.log('-'.repeat(80));
    console.log('');

    console.log('Models:');
    console.log(`  Total Models: ${savings.total_models}`);
    console.log(`  Total Size: ${savings.total_model_size_gb}GB`);
    console.log(`  Nodes Served: ${savings.nodes_served}`);
    console.log(`  Data Transferred: ${savings.total_data_transferred_gb}GB`);
    console.log('');

    console.log('Internet Approach (download to each node separately):');
    console.log(`  Time: ${savings.internet_approach.time_hours} hours (${savings.internet_approach.time_minutes} min)`);
    console.log(`  Bandwidth: ${savings.total_data_transferred_gb}GB internet`);
    console.log('');

    console.log('NAS Approach (download once, distribute via LAN):');
    console.log(`  Time: ${savings.nas_approach.time_hours} hours (${savings.nas_approach.time_minutes} min)`);
    console.log(`  Bandwidth: ${savings.total_model_size_gb}GB internet + LAN distribution`);
    console.log('');

    console.log('💰 SAVINGS:');
    console.log(`  Time Saved: ${savings.savings.time_hours} hours (${savings.savings.time_minutes} min)`);
    console.log(`  Bandwidth Saved: ${savings.savings.bandwidth_gb}GB`);
    console.log(`  Efficiency Gain: ${savings.savings.efficiency_gain}`);
    console.log('');

    console.log('✅ NAS distribution is approximately 10× faster than internet download to each node!');
  }

  /**
   * Show help
   */
  help() {
    console.log(`
Fleet CLI - Distributed Multi-Vendor Model Fleet Manager

Usage:
  fleet-cli.js <command> [arguments]

Commands:
  status                      Show overall fleet status
  models                      List all available models
  node <name>                 Show node details
  route <capability>          Find best model for capability
  health                      Run health check on all nodes
  monitor                     Start continuous monitoring (Ctrl+C to stop)
  plan                        Show deployment plan
  rebalance                   Show rebalancing suggestions
  probe-hardware              Probe hardware capabilities on all nodes
  auto-distribute             Auto-distribute models based on hardware
  update-registry             Auto-distribute and update registry
  validate                    Validate current distribution
  show-capacity               Show node capacity and utilization
  help                        Show this help message

Hardware-Aware Auto-Distribution:
  probe-hardware              Probe CPU, RAM, disk, GPU on all nodes
  auto-distribute             Calculate optimal distribution (no changes)
  update-registry             Calculate and apply optimal distribution
  validate                    Check if distribution is valid

NAS Model Distribution (Centralized Download & Distribution):
  nas-download [options]      Download models to NAS central repository
    --all                     Download all local models
    --high-priority           Download high-priority models only
    <models...>               Download specific models
  nas-distribute [options]    Distribute models from NAS to nodes
    --node <name>             Distribute to specific node
    <model>                   Distribute specific model
    (no args)                 Distribute all per registry
  nas-deploy [options]        Complete deployment workflow
    --all                     Download all + distribute
    --high-priority           Download high-priority + distribute
    --node <name>             Deploy to specific node
  nas-status                  Show NAS inventory and distribution status
  nas-savings                 Calculate bandwidth/time savings with NAS

Examples:
  fleet-cli.js status
  fleet-cli.js models
  fleet-cli.js node localhost
  fleet-cli.js route coding
  fleet-cli.js health
  fleet-cli.js monitor
  fleet-cli.js plan
  fleet-cli.js rebalance
  fleet-cli.js probe-hardware
  fleet-cli.js auto-distribute
  fleet-cli.js update-registry
  fleet-cli.js validate
  fleet-cli.js show-capacity

Capabilities (for routing):
  coding, reasoning, math, chat, fast, heavy, multimodal, vision,
  debugging, sql, embedding, multilingual

Advanced Routing:
  You can also use the orchestrator API directly from Node.js:

  const ModelMeshOrchestrator = require('./orchestrator-model-mesh.cjs');
  const orchestrator = new ModelMeshOrchestrator();

  // Route with constraints
  const result = orchestrator.routeRequest(['coding', 'reasoning'], {
    type: 'local',           // Prefer local models
    maxCost: 0,              // Free models only
    preferNode: 'localhost'  // Prefer localhost
  });

  if (result.success) {
    console.log('Use model:', result.model, 'on', result.node);
  }

Documentation:
  - orchestrator-model-mesh.js: Core routing and orchestration
  - fleet-node-monitor.js: Health monitoring and heartbeats
  - fleet-deployment-planner.js: Deployment planning and optimization
  - fleet-hardware-prober.js: Real-time hardware capability detection
  - fleet-auto-distributor.js: Hardware-aware auto-distribution
  - nas-model-manager.cjs: NAS centralized distribution
  - fleet-model-registry.json: Model and node registry
  - model-requirements.json: Model resource requirements database
  - NAS_MODEL_DISTRIBUTION.md: Full NAS documentation
  - NAS_QUICKSTART.md: Quick start guide

Zero Duplication Policy:
  Each model exists on exactly ONE node. No duplication anywhere.
  This ensures clean separation and no confusion about which instance to use.

Auto-Distribution Algorithm:
  1. Probe hardware on each node (CPU, RAM, disk, GPU)
  2. Load model requirements database
  3. Sort models by resource requirements (heavy → light)
  4. Bin-packing: assign each model to best-fit node
  5. Validate: zero duplication, capacity limits
  6. Update registry with optimal distribution
    `);
  }
}

// CLI entry point
if (require.main === module) {
  const cli = new FleetCLI();
  const command = process.argv[2];
  const args = process.argv.slice(3);

  (async () => {
    switch (command) {
      case 'status':
        await cli.status();
        break;

      case 'models':
        cli.models();
        break;

      case 'node':
        if (args.length === 0) {
          console.error('Error: Node name required');
          console.error('Usage: fleet-cli.js node <name>');
          process.exit(1);
        }
        cli.node(args[0]);
        break;

      case 'route':
        if (args.length === 0) {
          console.error('Error: Capability required');
          console.error('Usage: fleet-cli.js route <capability>');
          process.exit(1);
        }
        cli.route(args[0]);
        break;

      case 'health':
        await cli.health();
        break;

      case 'monitor':
        await cli.monitor();
        break;

      case 'plan':
        cli.plan();
        break;

      case 'rebalance':
        cli.rebalance();
        break;

      case 'probe-hardware':
        await cli.probeHardware();
        break;

      case 'auto-distribute':
        await cli.autoDistribute();
        break;

      case 'update-registry':
        await cli.updateRegistry();
        break;

      case 'validate':
        await cli.validate();
        break;

      case 'show-capacity':
        cli.showCapacity();
        break;

      case 'nas-download':
        await cli.nasDownload(args);
        break;

      case 'nas-distribute':
        await cli.nasDistribute(args);
        break;

      case 'nas-deploy':
        await cli.nasDeploy(args);
        break;

      case 'nas-status':
        cli.nasStatus();
        break;

      case 'nas-savings':
        cli.nasSavings();
        break;

      case 'help':
      case '--help':
      case '-h':
        cli.help();
        break;

      default:
        if (command) {
          console.error(`Unknown command: ${command}`);
          console.error('Run "fleet-cli.js help" for usage information');
        } else {
          cli.help();
        }
        process.exit(1);
    }
  })();
}

// Export for use as library
module.exports = FleetCLI;
