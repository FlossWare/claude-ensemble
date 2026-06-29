#!/usr/bin/env node

/**
 * Fleet Auto-Distributor
 *
 * Automatically distributes models across fleet nodes based on:
 * - Real-time hardware capabilities (probed)
 * - Model resource requirements
 * - Zero duplication enforcement
 * - Locality optimization (high-frequency models on localhost)
 * - Load balancing
 *
 * Algorithm:
 * 1. Probe all nodes for hardware capabilities
 * 2. Load model requirements database
 * 3. Sort models by requirements (heavy → light)
 * 4. Bin-packing: assign each model to best-fit node
 * 5. Validate constraints (zero duplication, capacity limits)
 */

const fs = require('fs');
const path = require('path');
const FleetHardwareProber = require('./fleet-hardware-prober.cjs');

class FleetAutoDistributor {
  constructor() {
    this.prober = new FleetHardwareProber();
    this.requirementsPath = path.join(__dirname, 'model-requirements.json');
    this.registryPath = path.join(__dirname, 'fleet-model-registry.json');
    this.usageStatsPath = path.join(__dirname, 'fleet-usage-stats.json');
  }

  /**
   * Load model requirements database
   */
  loadModelRequirements() {
    try {
      const data = fs.readFileSync(this.requirementsPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load model requirements:', error.message);
      return null;
    }
  }

  /**
   * Load usage statistics
   */
  loadUsageStats() {
    try {
      const data = fs.readFileSync(this.usageStatsPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      return { models: {} };
    }
  }

  /**
   * Auto-distribute models based on hardware capabilities
   */
  async autoDistribute(nodeList = []) {
    console.log('🔬 Step 1: Probing hardware capabilities...\n');

    // Probe hardware
    const hardwareProfiles = await this.prober.probeFleet(nodeList);
    const summary = this.prober.generateSummary(hardwareProfiles);

    console.log('\nHardware Summary:');
    console.log(`  Reachable nodes: ${summary.reachable_nodes}/${summary.total_nodes}`);
    console.log(`  Total CPU cores: ${summary.total_cpu_cores}`);
    console.log(`  Total RAM: ${summary.total_ram_gb}GB`);
    console.log(`  Total disk: ${summary.total_disk_gb}GB\n`);

    // Load model requirements
    console.log('📊 Step 2: Loading model requirements...\n');
    const requirementsDb = this.loadModelRequirements();
    if (!requirementsDb) {
      console.error('Failed to load model requirements');
      return null;
    }

    const models = Object.entries(requirementsDb.models).map(([name, reqs]) => ({
      name,
      ...reqs
    }));

    console.log(`  Loaded ${models.length} model definitions\n`);

    // Load usage stats
    const usageStats = this.loadUsageStats();

    // Separate cloud and local models
    const cloudModels = models.filter(m => m.type === 'cloud-api');
    const localModels = models.filter(m => m.type === 'local');

    console.log('📦 Step 3: Distributing models...\n');
    console.log(`  Cloud API models: ${cloudModels.length}`);
    console.log(`  Local Ollama models: ${localModels.length}\n`);

    // Initialize distribution plan
    const distribution = {
      timestamp: new Date().toISOString(),
      hardware_profiles: hardwareProfiles,
      assignments: {},
      violations: [],
      stats: {}
    };

    // Initialize assignments for reachable nodes
    Object.entries(hardwareProfiles).forEach(([hostname, profile]) => {
      if (profile.reachable) {
        distribution.assignments[hostname] = {
          models: [],
          cloud_api_count: 0,
          local_count: 0,
          total_size_gb: 0,
          ram_used_gb: 0,
          ram_available_gb: profile.ram?.available_gb || 0,
          ram_total_gb: profile.ram?.total_gb || 0
        };
      }
    });

    // Assign cloud models first
    this.assignCloudModels(cloudModels, hardwareProfiles, distribution, usageStats);

    // Assign local models (resource-constrained)
    this.assignLocalModels(localModels, hardwareProfiles, distribution, usageStats);

    // Calculate statistics
    this.calculateStats(distribution);

    // Validate constraints
    this.validateDistribution(distribution);

    return distribution;
  }

  /**
   * Assign cloud API models to nodes
   */
  assignCloudModels(cloudModels, hardwareProfiles, distribution, usageStats) {
    // Sort by usage frequency (most-used first)
    const sorted = cloudModels.sort((a, b) => {
      const aUsage = usageStats.models?.[a.name]?.count || 0;
      const bUsage = usageStats.models?.[b.name]?.count || 0;
      if (bUsage !== aUsage) return bUsage - aUsage;
      // Tie-break by priority
      const priorityMap = { high: 3, medium: 2, low: 1 };
      return (priorityMap[b.priority] || 1) - (priorityMap[a.priority] || 1);
    });

    sorted.forEach(model => {
      const nodeName = this.selectNodeForCloudModel(model, hardwareProfiles, distribution, usageStats);
      if (nodeName) {
        distribution.assignments[nodeName].models.push(model.name);
        distribution.assignments[nodeName].cloud_api_count++;
      } else {
        distribution.violations.push({
          type: 'no_node',
          model: model.name,
          message: `No suitable node found for cloud model ${model.name}`
        });
      }
    });
  }

  /**
   * Select best node for a cloud API model
   */
  selectNodeForCloudModel(model, hardwareProfiles, distribution, usageStats) {
    const modelUsage = usageStats.models?.[model.name]?.count || 0;

    // Check for required API key
    const reachableNodes = Object.entries(hardwareProfiles)
      .filter(([name, profile]) => profile.reachable);

    // High-frequency models prefer localhost (zero latency)
    if (modelUsage > 100 || model.frequency === 'high' || model.priority === 'high') {
      const localhost = reachableNodes.find(([name]) => name === 'localhost');
      if (localhost) return localhost[0];
    }

    // Otherwise, distribute evenly across nodes
    // Find least-loaded node
    const candidates = reachableNodes
      .map(([name, profile]) => ({
        name,
        load: distribution.assignments[name]?.cloud_api_count || 0,
        cpu: profile.cpu?.cores || 0
      }))
      .sort((a, b) => {
        // Prefer less-loaded nodes
        if (a.load !== b.load) return a.load - b.load;
        // Tie-break by CPU (more is better for cloud APIs)
        return b.cpu - a.cpu;
      });

    return candidates.length > 0 ? candidates[0].name : null;
  }

  /**
   * Assign local Ollama models to nodes
   */
  assignLocalModels(localModels, hardwareProfiles, distribution, usageStats) {
    // Sort by size (largest first) for better bin-packing
    const sorted = localModels.sort((a, b) => {
      const sizeA = a.ram_gb || 0;
      const sizeB = b.ram_gb || 0;
      return sizeB - sizeA;
    });

    sorted.forEach(model => {
      const nodeName = this.selectNodeForLocalModel(model, hardwareProfiles, distribution, usageStats);

      if (!nodeName) {
        distribution.violations.push({
          type: 'no_capacity',
          model: model.name,
          size_gb: model.ram_gb,
          message: `No node has capacity for ${model.name} (${model.ram_gb}GB)`
        });
        return;
      }

      distribution.assignments[nodeName].models.push(model.name);
      distribution.assignments[nodeName].local_count++;
      distribution.assignments[nodeName].total_size_gb += model.ram_gb || 0;
      distribution.assignments[nodeName].ram_used_gb += model.ram_gb || 0;
      distribution.assignments[nodeName].ram_available_gb -= model.ram_gb || 0;
    });
  }

  /**
   * Select best node for a local Ollama model using best-fit bin-packing
   */
  selectNodeForLocalModel(model, hardwareProfiles, distribution, usageStats) {
    const modelSize = model.ram_gb || 0;
    const modelUsage = usageStats.models?.[model.name]?.count || 0;
    const modelCpu = model.cpu_cores_min || 1;

    // High-usage models prefer localhost
    const localhostPreference = modelUsage > 50 || model.frequency === 'high';

    // Find nodes with:
    // 1. Ollama installed
    // 2. Sufficient RAM (model size + 2GB buffer for OS)
    // 3. Sufficient CPU cores
    const candidates = Object.entries(hardwareProfiles)
      .filter(([name, profile]) => {
        if (!profile.reachable) return false;
        if (!profile.ollama?.installed) return false;

        const assignment = distribution.assignments[name];
        const ramUsed = assignment.ram_used_gb || 0;
        const ramTotal = profile.ram?.total_gb || 0;
        const ramAvailable = ramTotal - ramUsed - 2; // 2GB buffer for OS
        const cpuCores = profile.cpu?.cores || 0;

        return ramAvailable >= modelSize && cpuCores >= modelCpu;
      })
      .map(([name, profile]) => {
        const assignment = distribution.assignments[name];
        const ramUsed = assignment.ram_used_gb || 0;
        const ramTotal = profile.ram?.total_gb || 0;
        const ramAvailable = ramTotal - ramUsed - 2;

        let score = 0;

        // Localhost preference for high-usage models
        if (name === 'localhost' && localhostPreference) {
          score += 1000;
        }

        // Best-fit: prefer node where model fits with least wasted space
        const waste = ramAvailable - modelSize;
        score -= waste; // Less waste is better

        // Load balancing: penalize overloaded nodes
        const utilization = ramUsed / ramTotal;
        score -= utilization * 100;

        // Penalize nodes with many models already
        score -= assignment.local_count * 10;

        return {
          name,
          score,
          ramAvailable,
          ramUsed,
          ramTotal,
          utilization
        };
      })
      .sort((a, b) => b.score - a.score);

    return candidates.length > 0 ? candidates[0].name : null;
  }

  /**
   * Calculate distribution statistics
   */
  calculateStats(distribution) {
    distribution.stats = {
      total_models: 0,
      cloud_api_models: 0,
      local_models: 0,
      total_size_gb: 0,
      nodes: {},
      violations: distribution.violations.length
    };

    Object.entries(distribution.assignments).forEach(([nodeName, assignment]) => {
      distribution.stats.total_models += assignment.models.length;
      distribution.stats.cloud_api_models += assignment.cloud_api_count;
      distribution.stats.local_models += assignment.local_count;
      distribution.stats.total_size_gb += assignment.total_size_gb;

      const ramTotal = assignment.ram_total_gb - 2; // Exclude OS buffer
      const utilization = ramTotal > 0 ? (assignment.ram_used_gb / ramTotal) * 100 : 0;

      distribution.stats.nodes[nodeName] = {
        models: assignment.models.length,
        cloud_api: assignment.cloud_api_count,
        local: assignment.local_count,
        ram_used_gb: assignment.ram_used_gb,
        ram_total_gb: ramTotal,
        utilization: utilization.toFixed(1)
      };
    });
  }

  /**
   * Validate distribution constraints
   */
  validateDistribution(distribution) {
    // Validate zero duplication
    const modelCounts = new Map();

    Object.values(distribution.assignments).forEach(assignment => {
      assignment.models.forEach(modelName => {
        modelCounts.set(modelName, (modelCounts.get(modelName) || 0) + 1);
      });
    });

    const duplicates = Array.from(modelCounts.entries())
      .filter(([name, count]) => count > 1);

    if (duplicates.length > 0) {
      duplicates.forEach(([name, count]) => {
        distribution.violations.push({
          type: 'duplication',
          model: name,
          count: count,
          message: `Model ${name} assigned to ${count} nodes (should be 1)`
        });
      });
    }

    distribution.valid = distribution.violations.length === 0;
    distribution.zero_duplication = duplicates.length === 0;
  }

  /**
   * Generate visual distribution report
   */
  generateReport(distribution) {
    const lines = [];

    lines.push('🚀 Fleet Auto-Distribution Results');
    lines.push('='.repeat(80));
    lines.push('');

    // Hardware summary
    lines.push('🔬 Hardware Probe Results:');
    Object.entries(distribution.hardware_profiles).forEach(([hostname, profile]) => {
      const classification = this.prober.classifyNode(profile);
      if (profile.reachable) {
        const cpu = profile.cpu?.cores || 0;
        const ram = profile.ram?.total_gb || 0;
        const disk = profile.disk?.available_gb || 0;
        const gpu = profile.gpu?.present ? ', GPU' : '';
        lines.push(`  ${hostname}: ${ram}GB RAM, ${cpu} CPU, ${disk}GB free${gpu} → ${classification.tier_label}`);
      } else {
        lines.push(`  ${hostname}: OFFLINE (skipped)`);
      }
    });
    lines.push('');

    // Distribution summary
    lines.push('📊 Auto-Distribution:');
    Object.entries(distribution.assignments).forEach(([nodeName, assignment]) => {
      if (assignment.models.length === 0) return;

      const utilization = distribution.stats.nodes[nodeName]?.utilization || 0;
      const bar = '█'.repeat(Math.floor(parseFloat(utilization) / 2.5));

      lines.push(`  ${nodeName} (${assignment.ram_total_gb}GB): ${assignment.models.length} models, ${assignment.ram_used_gb.toFixed(1)}GB used`);
      lines.push(`    Utilization: ${bar} ${utilization}%`);
      lines.push(`    Cloud: ${assignment.cloud_api_count}, Local: ${assignment.local_count}`);
    });
    lines.push('');

    // Statistics
    lines.push('📈 Statistics:');
    lines.push(`  Total Models: ${distribution.stats.total_models}`);
    lines.push(`  Cloud API: ${distribution.stats.cloud_api_models}`);
    lines.push(`  Local Ollama: ${distribution.stats.local_models}`);
    lines.push(`  Total Size: ${distribution.stats.total_size_gb.toFixed(1)}GB`);
    lines.push(`  Violations: ${distribution.violations.length}`);
    lines.push('');

    // Validation status
    if (distribution.valid) {
      lines.push('✅ Distribution valid: All models assigned, zero duplication, all constraints met');
    } else {
      lines.push('❌ Distribution has violations:');
      distribution.violations.forEach(v => {
        lines.push(`  [${v.type.toUpperCase()}] ${v.message}`);
      });
    }

    return lines.join('\n');
  }

  /**
   * Update registry with new distribution
   */
  async updateRegistry(distribution) {
    try {
      // Load existing registry
      let registry = {};
      try {
        const data = fs.readFileSync(this.registryPath, 'utf8');
        registry = JSON.parse(data);
      } catch (error) {
        console.log('Creating new registry...');
        registry = {
          _comment: "Unified Model Registry - Auto-generated by fleet-auto-distributor",
          _version: "1.0",
          models: {},
          nodes: {},
          distribution_stats: {}
        };
      }

      // Load model requirements for full model details
      const requirementsDb = this.loadModelRequirements();

      // Update model assignments
      const modelAssignments = new Map();
      Object.entries(distribution.assignments).forEach(([nodeName, assignment]) => {
        assignment.models.forEach(modelName => {
          modelAssignments.set(modelName, nodeName);
        });
      });

      // Update models section
      modelAssignments.forEach((nodeName, modelName) => {
        const requirements = requirementsDb.models[modelName];
        if (!registry.models[modelName]) {
          registry.models[modelName] = {};
        }

        registry.models[modelName] = {
          ...registry.models[modelName],
          vendor: requirements.vendor,
          type: requirements.type,
          node: nodeName,
          capabilities: registry.models[modelName]?.capabilities || [],
          cost_per_1m_tokens: registry.models[modelName]?.cost_per_1m_tokens || 0,
          context_window: registry.models[modelName]?.context_window || 0,
          model_size_gb: requirements.ram_gb,
          params: registry.models[modelName]?.params || '',
          status: 'available',
          fallback_nodes: []
        };
      });

      // Update nodes section
      Object.entries(distribution.assignments).forEach(([nodeName, assignment]) => {
        const profile = distribution.hardware_profiles[nodeName];
        const stats = distribution.stats.nodes[nodeName] || {};

        registry.nodes[nodeName] = {
          hostname: nodeName,
          status: profile.reachable ? 'online' : 'offline',
          last_heartbeat: new Date().toISOString(),
          ram_gb: profile.ram?.total_gb || 0,
          cpu_cores: profile.cpu?.cores || 0,
          roles: this.inferNodeRoles(profile, assignment),
          models: assignment.models,
          total_models: assignment.models.length,
          cloud_models: assignment.cloud_api_count,
          local_models: assignment.local_count,
          priority: nodeName === 'localhost' ? 1 : 2
        };
      });

      // Update distribution stats
      registry.distribution_stats = {
        total_models: distribution.stats.total_models,
        cloud_api_models: distribution.stats.cloud_api_models,
        ollama_local_models: distribution.stats.local_models,
        total_nodes: Object.keys(distribution.assignments).length,
        duplication_count: distribution.zero_duplication ? 0 : 1,
        models_per_node: {},
        distribution_strategy: "hardware-aware-auto-distribution"
      };

      Object.entries(distribution.stats.nodes).forEach(([nodeName, nodeStats]) => {
        registry.distribution_stats.models_per_node[nodeName] = nodeStats.models;
      });

      registry._last_updated = new Date().toISOString();

      // Save registry
      fs.writeFileSync(this.registryPath, JSON.stringify(registry, null, 2));
      console.log(`\n✅ Registry updated: ${this.registryPath}`);

      return true;
    } catch (error) {
      console.error('Failed to update registry:', error.message);
      return false;
    }
  }

  /**
   * Infer node roles based on hardware profile and assignments
   */
  inferNodeRoles(profile, assignment) {
    const roles = [];
    const ram = profile.ram?.total_gb || 0;
    const cpu = profile.cpu?.cores || 0;

    if (profile.hostname === 'localhost') {
      roles.push('primary');
    }

    if (assignment.cloud_api_count > 0) {
      roles.push('cloud-api');
    }

    if (profile.ollama?.installed) {
      roles.push('local-ollama');
    }

    if (ram >= 30) {
      roles.push('heavy');
    } else if (ram >= 15) {
      roles.push('medium');
    } else {
      roles.push('lightweight');
    }

    if (cpu >= 8) {
      roles.push('fast');
    }

    return roles;
  }

  /**
   * Export distribution plan
   */
  exportDistribution(distribution, outputPath = null) {
    const exportPath = outputPath || path.join(__dirname, 'fleet-auto-distribution.json');
    try {
      fs.writeFileSync(exportPath, JSON.stringify(distribution, null, 2));
      console.log(`\n📦 Distribution plan exported: ${exportPath}`);
      return true;
    } catch (error) {
      console.error('Failed to export distribution:', error.message);
      return false;
    }
  }
}

// Export for use in other modules
module.exports = FleetAutoDistributor;

// CLI interface
if (require.main === module) {
  const distributor = new FleetAutoDistributor();
  const command = process.argv[2];
  const args = process.argv.slice(3);

  (async () => {
    switch (command) {
      case 'auto-distribute':
      case 'distribute':
        console.log('Starting hardware-aware auto-distribution...\n');
        const distribution = await distributor.autoDistribute(args);
        if (distribution) {
          console.log('\n' + distributor.generateReport(distribution));
          distributor.exportDistribution(distribution);
        }
        break;

      case 'update-registry':
        console.log('Auto-distributing and updating registry...\n');
        const dist = await distributor.autoDistribute(args);
        if (dist) {
          console.log('\n' + distributor.generateReport(dist));
          distributor.exportDistribution(dist);
          await distributor.updateRegistry(dist);
        }
        break;

      default:
        console.log(`
Fleet Auto-Distributor - Hardware-aware automatic model distribution

Usage:
  fleet-auto-distributor.js <command> [nodes...]

Commands:
  auto-distribute [nodes...]     Auto-distribute models based on hardware
  update-registry [nodes...]     Auto-distribute and update registry

Examples:
  fleet-auto-distributor.js auto-distribute
  fleet-auto-distributor.js auto-distribute localhost server-01 server-02
  fleet-auto-distributor.js update-registry

Output:
  - fleet-auto-distribution.json: Distribution plan
  - fleet-model-registry.json: Updated registry (with update-registry command)
  - fleet-hardware-profiles.json: Hardware probe results
        `);
        process.exit(0);
    }
  })();
}
