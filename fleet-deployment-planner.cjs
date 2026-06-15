#!/usr/bin/env node

/**
 * Fleet Deployment Planner
 *
 * Plans optimal model distribution across fleet nodes with:
 * - Zero duplication enforcement
 * - Resource-aware placement (RAM, CPU)
 * - Locality optimization (frequently used models on localhost)
 * - Cost awareness (cloud vs local)
 * - Load balancing
 */

const fs = require('fs');
const path = require('path');

class FleetDeploymentPlanner {
  constructor(registryPath = null) {
    this.registryPath = registryPath || path.join(__dirname, 'fleet-model-registry.json');
    this.usageStatsPath = path.join(__dirname, 'fleet-usage-stats.json');
  }

  /**
   * Load registry
   */
  loadRegistry() {
    try {
      const data = fs.readFileSync(this.registryPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error('Failed to load registry:', error.message);
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
   * Calculate optimal deployment plan
   * @param {Array} models - List of models to deploy
   * @param {Object} nodes - Available nodes
   * @returns {Object} Deployment plan
   */
  planDeployment(models, nodes) {
    const plan = {
      timestamp: new Date().toISOString(),
      total_models: models.length,
      assignments: {},
      stats: {},
      violations: [],
      recommendations: []
    };

    // Initialize node assignments
    Object.keys(nodes).forEach(nodeName => {
      plan.assignments[nodeName] = {
        models: [],
        total_size_gb: 0,
        cloud_api_count: 0,
        local_count: 0,
        utilization: 0
      };
    });

    // Separate cloud and local models
    const cloudModels = models.filter(m => m.type === 'cloud-api');
    const localModels = models.filter(m => m.type === 'local');

    // Sort local models by size (largest first) for better bin-packing
    localModels.sort((a, b) => (b.model_size_gb || 0) - (a.model_size_gb || 0));

    // Load usage stats
    const usageStats = this.loadUsageStats();

    // Assign cloud API models first (they're free to place)
    this.assignCloudModels(cloudModels, nodes, plan, usageStats);

    // Assign local models (resource-constrained)
    this.assignLocalModels(localModels, nodes, plan, usageStats);

    // Calculate statistics
    this.calculateStats(plan, nodes);

    // Validate zero duplication
    this.validateZeroDuplication(plan);

    // Generate recommendations
    this.generateRecommendations(plan, nodes);

    return plan;
  }

  /**
   * Assign cloud API models to nodes
   */
  assignCloudModels(cloudModels, nodes, plan, usageStats) {
    // Sort by usage frequency (most-used first)
    const sorted = cloudModels.sort((a, b) => {
      const aUsage = usageStats.models[a.name]?.count || 0;
      const bUsage = usageStats.models[b.name]?.count || 0;
      return bUsage - aUsage;
    });

    // Distribute across nodes by role preference
    sorted.forEach(model => {
      const nodeName = this.selectNodeForCloudModel(model, nodes, plan);
      plan.assignments[nodeName].models.push(model.name);
      plan.assignments[nodeName].cloud_api_count++;
    });
  }

  /**
   * Select best node for a cloud API model
   */
  selectNodeForCloudModel(model, nodes, plan) {
    const usageStats = this.loadUsageStats();
    const modelUsage = usageStats.models[model.name]?.count || 0;

    // High-usage models go to localhost (zero latency)
    if (modelUsage > 100 || model.capabilities?.includes('arbiter')) {
      return 'localhost';
    }

    // Fast models go to nodes with fast role
    if (model.capabilities?.includes('fast')) {
      const fastNodes = Object.entries(nodes)
        .filter(([name, node]) => node.roles?.includes('fast'))
        .sort((a, b) => a[1].cpu_cores - b[1].cpu_cores);
      if (fastNodes.length > 0) return fastNodes[0][0];
    }

    // Coding models go to code specialist nodes
    if (model.capabilities?.includes('coding')) {
      const codeNodes = Object.entries(nodes)
        .filter(([name, node]) => node.roles?.includes('code-specialist'))
        .sort((a, b) => plan.assignments[a[0]].cloud_api_count - plan.assignments[b[0]].cloud_api_count);
      if (codeNodes.length > 0) return codeNodes[0][0];
    }

    // Heavy/reasoning models go to high-RAM nodes
    if (model.capabilities?.includes('reasoning') || model.capabilities?.includes('heavy')) {
      const heavyNodes = Object.entries(nodes)
        .filter(([name, node]) => node.ram_gb >= 30)
        .sort((a, b) => plan.assignments[a[0]].cloud_api_count - plan.assignments[b[0]].cloud_api_count);
      if (heavyNodes.length > 0) return heavyNodes[0][0];
    }

    // Default: least-loaded node
    const leastLoaded = Object.entries(plan.assignments)
      .filter(([name]) => nodes[name]) // exclude non-existent nodes
      .sort((a, b) => a[1].cloud_api_count - b[1].cloud_api_count);
    return leastLoaded[0][0];
  }

  /**
   * Assign local Ollama models to nodes
   */
  assignLocalModels(localModels, nodes, plan, usageStats) {
    // For each model, find best-fit node
    localModels.forEach(model => {
      const nodeName = this.selectNodeForLocalModel(model, nodes, plan, usageStats);

      if (!nodeName) {
        plan.violations.push({
          type: 'no_capacity',
          model: model.name,
          size_gb: model.model_size_gb,
          message: `No node has capacity for ${model.name} (${model.model_size_gb}GB)`
        });
        return;
      }

      plan.assignments[nodeName].models.push(model.name);
      plan.assignments[nodeName].local_count++;
      plan.assignments[nodeName].total_size_gb += model.model_size_gb || 0;
    });
  }

  /**
   * Select best node for a local Ollama model
   */
  selectNodeForLocalModel(model, nodes, plan, usageStats) {
    const modelSize = model.model_size_gb || 0;
    const modelUsage = usageStats.models[model.name]?.count || 0;

    // High-usage models prefer localhost
    const localhostPreference = modelUsage > 50;

    // Find nodes with capacity
    const candidates = Object.entries(nodes)
      .filter(([name, node]) => {
        // Skip nodes without local-ollama role
        if (!node.roles?.includes('local-ollama')) return false;

        // Check RAM capacity (leave 2GB free for OS)
        const used = plan.assignments[name].total_size_gb;
        const available = node.ram_gb - 2 - used;
        return available >= modelSize;
      })
      .map(([name, node]) => {
        const used = plan.assignments[name].total_size_gb;
        const available = node.ram_gb - 2 - used;

        let score = 0;

        // Prefer localhost for high-usage models
        if (name === 'localhost' && localhostPreference) score += 100;

        // Prefer nodes with matching roles
        if (model.capabilities?.includes('coding') && node.roles?.includes('code-specialist')) score += 50;
        if (model.capabilities?.includes('heavy') && node.roles?.includes('heavy')) score += 50;
        if (model.params && parseInt(model.params) >= 32 && node.ram_gb >= 30) score += 30;

        // Best-fit (prefer node where model fits with least wasted space)
        const waste = available - modelSize;
        score -= waste; // Less waste is better

        // Load balancing (prefer less-loaded nodes)
        score -= plan.assignments[name].local_count * 10;

        return { name, score, available };
      })
      .sort((a, b) => b.score - a.score);

    return candidates.length > 0 ? candidates[0].name : null;
  }

  /**
   * Calculate deployment statistics
   */
  calculateStats(plan, nodes) {
    Object.entries(plan.assignments).forEach(([nodeName, assignment]) => {
      const node = nodes[nodeName];
      if (!node) return;

      // Calculate utilization
      const ramUsed = assignment.total_size_gb;
      const ramTotal = node.ram_gb - 2; // Reserve 2GB for OS
      assignment.utilization = ramTotal > 0 ? (ramUsed / ramTotal) * 100 : 0;
      assignment.ram_used_gb = ramUsed;
      assignment.ram_total_gb = ramTotal;
      assignment.ram_available_gb = Math.max(0, ramTotal - ramUsed);
    });

    plan.stats = {
      total_assignments: Object.values(plan.assignments).reduce((sum, a) => sum + a.models.length, 0),
      cloud_api_total: Object.values(plan.assignments).reduce((sum, a) => sum + a.cloud_api_count, 0),
      local_total: Object.values(plan.assignments).reduce((sum, a) => sum + a.local_count, 0),
      total_size_gb: Object.values(plan.assignments).reduce((sum, a) => sum + a.total_size_gb, 0),
      avg_utilization: Object.values(plan.assignments).reduce((sum, a) => sum + a.utilization, 0) / Object.keys(plan.assignments).length
    };
  }

  /**
   * Validate zero duplication
   */
  validateZeroDuplication(plan) {
    const modelCounts = new Map();

    Object.values(plan.assignments).forEach(assignment => {
      assignment.models.forEach(modelName => {
        modelCounts.set(modelName, (modelCounts.get(modelName) || 0) + 1);
      });
    });

    const duplicates = Array.from(modelCounts.entries())
      .filter(([name, count]) => count > 1);

    if (duplicates.length > 0) {
      duplicates.forEach(([name, count]) => {
        plan.violations.push({
          type: 'duplication',
          model: name,
          count: count,
          message: `Model ${name} assigned to ${count} nodes (should be 1)`
        });
      });
    }

    plan.zero_duplication = duplicates.length === 0;
  }

  /**
   * Generate recommendations
   */
  generateRecommendations(plan, nodes) {
    // Check for overutilized nodes
    Object.entries(plan.assignments).forEach(([nodeName, assignment]) => {
      if (assignment.utilization > 90) {
        plan.recommendations.push({
          type: 'warning',
          node: nodeName,
          message: `Node ${nodeName} is ${assignment.utilization.toFixed(1)}% utilized - consider offloading models`
        });
      }
    });

    // Check for underutilized nodes
    Object.entries(plan.assignments).forEach(([nodeName, assignment]) => {
      if (assignment.utilization < 20 && assignment.models.length === 0) {
        plan.recommendations.push({
          type: 'info',
          node: nodeName,
          message: `Node ${nodeName} is idle - consider adding models`
        });
      }
    });

    // Check for capacity violations
    if (plan.violations.length > 0) {
      plan.recommendations.push({
        type: 'error',
        message: `${plan.violations.length} violations detected - deployment may fail`
      });
    }

    // Check for load imbalance
    const utilizationValues = Object.values(plan.assignments).map(a => a.utilization);
    const maxUtil = Math.max(...utilizationValues);
    const minUtil = Math.min(...utilizationValues.filter(u => u > 0));
    if (maxUtil - minUtil > 50) {
      plan.recommendations.push({
        type: 'warning',
        message: `Load imbalance detected: ${minUtil.toFixed(1)}% to ${maxUtil.toFixed(1)}% - consider rebalancing`
      });
    }
  }

  /**
   * Plan deployment from current registry
   */
  planFromRegistry() {
    const registry = this.loadRegistry();
    if (!registry) {
      console.error('Failed to load registry');
      return null;
    }

    const models = Object.entries(registry.models).map(([name, model]) => ({
      name,
      ...model
    }));

    return this.planDeployment(models, registry.nodes);
  }

  /**
   * Generate deployment script
   */
  generateDeploymentScript(plan) {
    const script = [];
    script.push('#!/bin/bash');
    script.push('# Fleet Model Deployment Script');
    script.push(`# Generated: ${new Date().toISOString()}`);
    script.push('');
    script.push('set -e');
    script.push('');

    Object.entries(plan.assignments).forEach(([nodeName, assignment]) => {
      if (assignment.models.length === 0) return;

      script.push(`# Deploy to ${nodeName}`);
      script.push(`echo "Deploying to ${nodeName}..."`);

      const localModels = assignment.models.filter(m => {
        const registry = this.loadRegistry();
        return registry.models[m]?.type === 'local';
      });

      if (localModels.length > 0) {
        if (nodeName === 'localhost') {
          script.push('# Localhost - models already present');
          localModels.forEach(modelName => {
            script.push(`ollama pull ${modelName} || echo "Model ${modelName} already exists"`);
          });
        } else {
          script.push(`# Remote node - copy models from localhost`);
          localModels.forEach(modelName => {
            script.push(`ssh ${nodeName} "ollama pull ${modelName}"`);
          });
        }
      }

      script.push('');
    });

    script.push('echo "Deployment complete!"');
    return script.join('\n');
  }

  /**
   * Export deployment plan
   */
  exportPlan(plan, outputPath = null) {
    const exportPath = outputPath || path.join(__dirname, 'fleet-deployment-plan.json');
    try {
      fs.writeFileSync(exportPath, JSON.stringify(plan, null, 2));
      console.log(`Deployment plan exported to ${exportPath}`);
      return true;
    } catch (error) {
      console.error('Failed to export plan:', error.message);
      return false;
    }
  }

  /**
   * Generate visual deployment map
   */
  generateDeploymentMap(plan, nodes) {
    const map = [];
    map.push('Fleet Model Deployment Map');
    map.push('='.repeat(80));
    map.push('');

    Object.entries(plan.assignments).forEach(([nodeName, assignment]) => {
      const node = nodes[nodeName];
      if (!node) return;

      map.push(`Node: ${nodeName}`);
      map.push(`  RAM: ${assignment.ram_used_gb.toFixed(1)}GB / ${assignment.ram_total_gb.toFixed(1)}GB (${assignment.utilization.toFixed(1)}%)`);
      map.push(`  CPU: ${node.cpu_cores} cores`);
      map.push(`  Roles: ${node.roles.join(', ')}`);
      map.push(`  Models: ${assignment.models.length} (${assignment.cloud_api_count} cloud, ${assignment.local_count} local)`);

      if (assignment.models.length > 0) {
        map.push('  Assignments:');
        assignment.models.forEach(modelName => {
          const registry = this.loadRegistry();
          const model = registry.models[modelName];
          const type = model?.type === 'cloud-api' ? '[Cloud]' : '[Local]';
          const size = model?.model_size_gb ? `${model.model_size_gb.toFixed(1)}GB` : '';
          map.push(`    - ${modelName} ${type} ${size}`.trim());
        });
      }
      map.push('');
    });

    map.push('Summary');
    map.push('-'.repeat(80));
    map.push(`Total Models: ${plan.stats.total_assignments}`);
    map.push(`Cloud API: ${plan.stats.cloud_api_total}`);
    map.push(`Local Ollama: ${plan.stats.local_total}`);
    map.push(`Total Size: ${plan.stats.total_size_gb.toFixed(1)}GB`);
    map.push(`Avg Utilization: ${plan.stats.avg_utilization.toFixed(1)}%`);
    map.push(`Zero Duplication: ${plan.zero_duplication ? 'YES' : 'NO'}`);
    map.push('');

    if (plan.violations.length > 0) {
      map.push('Violations');
      map.push('-'.repeat(80));
      plan.violations.forEach(v => {
        map.push(`[${v.type.toUpperCase()}] ${v.message}`);
      });
      map.push('');
    }

    if (plan.recommendations.length > 0) {
      map.push('Recommendations');
      map.push('-'.repeat(80));
      plan.recommendations.forEach(r => {
        map.push(`[${r.type.toUpperCase()}] ${r.message}`);
      });
      map.push('');
    }

    return map.join('\n');
  }
}

// Export for use in other modules
module.exports = FleetDeploymentPlanner;

// CLI interface
if (require.main === module) {
  const planner = new FleetDeploymentPlanner();
  const command = process.argv[2];

  switch (command) {
    case 'plan':
      const plan = planner.planFromRegistry();
      if (plan) {
        console.log(JSON.stringify(plan, null, 2));
      }
      break;

    case 'map':
      const mapPlan = planner.planFromRegistry();
      if (mapPlan) {
        const registry = planner.loadRegistry();
        console.log(planner.generateDeploymentMap(mapPlan, registry.nodes));
      }
      break;

    case 'script':
      const scriptPlan = planner.planFromRegistry();
      if (scriptPlan) {
        const script = planner.generateDeploymentScript(scriptPlan);
        const scriptPath = path.join(__dirname, 'deploy-fleet.sh');
        fs.writeFileSync(scriptPath, script, { mode: 0o755 });
        console.log(`Deployment script written to ${scriptPath}`);
      }
      break;

    case 'export':
      const exportPlan = planner.planFromRegistry();
      if (exportPlan) {
        const outputPath = process.argv[3] || null;
        planner.exportPlan(exportPlan, outputPath);
      }
      break;

    default:
      console.log(`
Fleet Deployment Planner - Optimal model distribution planning

Usage:
  fleet-deployment-planner.js <command> [options]

Commands:
  plan                Generate deployment plan (JSON)
  map                 Show visual deployment map
  script              Generate deployment shell script
  export [path]       Export plan to JSON file

Examples:
  fleet-deployment-planner.js plan
  fleet-deployment-planner.js map
  fleet-deployment-planner.js script
  fleet-deployment-planner.js export /tmp/deployment-plan.json
      `);
  }
}
