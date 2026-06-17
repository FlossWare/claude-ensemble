#!/usr/bin/env node

/**
 * STRATEGIC LEARNING PLANNER
 *
 * Converts active learning opportunities into executable experiments.
 *
 * Takes output from active-learning-engine.js and:
 *   1. Groups related opportunities into learning campaigns
 *   2. Builds dependency graph (some experiments enable others)
 *   3. Schedules experiments (fast/cheap first, then high-impact)
 *   4. Allocates budget (token budget, time budget, compute budget)
 *   5. Generates executable experiment prompts
 *   6. Tracks progress and validates outcomes
 *
 * Output:
 *   - Learning Campaign Plan (grouped experiments)
 *   - Experiment Priority Queue (ordered by ROI, dependencies)
 *   - Token Budget Allocation
 *   - Executable Experiment Templates (ready to run)
 *   - Success Metrics and Validation Rules
 *
 * Usage:
 *   node strategic-learning-planner.js [--opportunities FILE] [--budget TOKENS] [--output DIR]
 */

const fs = require('fs');
const path = require('path');

class StrategicLearningPlanner {
  constructor(opportunitiesPath = null) {
    this.opportunities = [];
    this.campaigns = [];
    this.experiments = [];
    this.budget = {
      tokens: 1000000,      // Default 1M tokens
      time_hours: 24,
      compute_credits: 100
    };

    if (opportunitiesPath) {
      this.opportunities = JSON.parse(fs.readFileSync(opportunitiesPath, 'utf8'));
    }
  }

  /**
   * Load opportunities from JSON
   */
  loadOpportunities(path) {
    const data = JSON.parse(fs.readFileSync(path, 'utf8'));
    this.opportunities = Array.isArray(data) ? data : (data.opportunities || []);
    return this.opportunities;
  }

  /**
   * Set budget constraints
   */
  setBudget(tokens, hours = 24, credits = 100) {
    this.budget = { tokens, time_hours: hours, compute_credits: credits };
  }

  /**
   * Create learning campaigns (group related opportunities)
   */
  createCampaigns() {
    const campaigns = {};

    // Organize opportunities by domain
    for (const opp of this.opportunities) {
      const domain = opp.domain || 'uncategorized';
      if (!campaigns[domain]) {
        campaigns[domain] = {
          name: this.formatDomainName(domain),
          domain,
          opportunities: [],
          total_impact: 0,
          total_cost: 0,
          total_efficiency: 0
        };
      }
      campaigns[domain].opportunities.push(opp);
      campaigns[domain].total_impact += opp.impact;
      campaigns[domain].total_cost += opp.cost;
    }

    // Sort opportunities within each campaign by efficiency
    for (const campaign of Object.values(campaigns)) {
      campaign.opportunities.sort((a, b) => {
        const effA = a.impact / Math.max(a.cost, 1);
        const effB = b.impact / Math.max(b.cost, 1);
        return effB - effA;
      });
      campaign.avg_efficiency = campaign.total_impact / Math.max(campaign.total_cost, 1);
    }

    // Sort campaigns by total impact
    this.campaigns = Object.values(campaigns).sort((a, b) => b.total_impact - a.total_impact);
    return this.campaigns;
  }

  /**
   * Build experiment priority queue
   */
  buildExperimentQueue() {
    const experiments = [];
    let tokensBudget = this.budget.tokens;
    let timeBudget = this.budget.time_hours;

    // Flatten opportunities from campaigns
    for (const campaign of this.campaigns) {
      for (const opp of campaign.opportunities) {
        const estimatedTokens = this.estimateTokens(opp);

        if (tokensBudget < estimatedTokens) {
          continue;  // Skip if over budget
        }

        const experiment = {
          id: opp.id,
          campaign: campaign.domain,
          opportunity: opp.name,
          type: opp.type,
          priority: 'pending',
          impact: opp.impact,
          cost: opp.cost,
          efficiency: opp.impact / Math.max(opp.cost, 1),
          estimated_tokens: estimatedTokens,
          estimated_time_hours: this.estimateTime(opp),
          tokens_remaining: tokensBudget - estimatedTokens,
          prompt: this.generateExperimentPrompt(opp),
          metrics: opp.recommendation.metrics,
          success_criteria: this.generateSuccessCriteria(opp),
          validation_rules: this.generateValidationRules(opp),
          dependencies: this.findDependencies(opp),
          status: 'ready'
        };

        experiments.push(experiment);
        tokensBudget -= estimatedTokens;
      }
    }

    // Sort by priority: executable experiments first (no dependencies), then by efficiency
    experiments.sort((a, b) => {
      const depsA = a.dependencies.length;
      const depsB = b.dependencies.length;
      if (depsA !== depsB) return depsA - depsB;
      return b.efficiency - a.efficiency;
    });

    this.experiments = experiments;
    return experiments;
  }

  /**
   * Estimate tokens needed for an experiment
   */
  estimateTokens(opp) {
    // Base tokens for experiment execution
    const typeTokens = {
      'knowledge_gap': 8000,
      'high_variance': 6000,
      'underexplored_space': 5000,
      'untested_combination': 7000,
      'divergent_performance': 10000,
      'low_confidence': 4000,
      'cost_anomaly': 3000
    };

    const base = typeTokens[opp.type] || 5000;
    const costMultiplier = opp.cost / 10;  // Cost score scales token estimate

    return Math.ceil(base * costMultiplier);
  }

  /**
   * Estimate wall-clock time for experiment
   */
  estimateTime(opp) {
    // Map to hours (rough estimates)
    const timeEstimates = {
      'cost_anomaly': 0.25,
      'low_confidence': 0.5,
      'underexplored_space': 0.75,
      'untested_combination': 1,
      'knowledge_gap': 1.5,
      'high_variance': 2,
      'divergent_performance': 2.5
    };

    return timeEstimates[opp.type] || 1;
  }

  /**
   * Find dependencies between experiments
   */
  findDependencies(opp) {
    // Some experiments depend on results of others
    const deps = [];

    if (opp.type === 'divergent_performance') {
      // Divergence experiments depend on first collecting enough model perf data
      deps.push({
        requirement: 'model_performance_baseline',
        reason: 'Need baseline model performance to identify divergence'
      });
    }

    if (opp.type === 'low_confidence') {
      // Low confidence depends on arbiter calibration data
      deps.push({
        requirement: 'arbiter_confidence_baseline',
        reason: 'Need to establish confidence calibration curve'
      });
    }

    return deps;
  }

  /**
   * Generate executable experiment prompt
   */
  generateExperimentPrompt(opp) {
    return `
LEARNING EXPERIMENT: ${opp.name}

OBJECTIVE:
${opp.recommendation.expectedOutcome}

EXPERIMENT DESIGN:
${opp.recommendation.experiment}

METRICS TO COLLECT:
${opp.recommendation.metrics.map(m => `  - ${m}`).join('\n')}

EXPECTED DURATION: ${this.estimateTime(opp).toFixed(1)} hours
EXPECTED TOKEN COST: ~${this.estimateTokens(opp)} tokens

EXECUTION STEPS:
1. Set up experiment environment with target model(s)/task type
2. Execute representative test cases
3. Collect all metrics listed above
4. Record outcomes in learning database
5. Validate against success criteria
6. Document findings

LEARNING GOAL:
Help the system make better decisions about ${opp.domain} by clarifying ${opp.name.toLowerCase()}.
`.trim();
  }

  /**
   * Generate success criteria
   */
  generateSuccessCriteria(opp) {
    return {
      minimum_samples: Math.max(3, Math.ceil(opp.cost / 5)),
      quality_improvement_required: 0.05,  // 5% improvement minimum
      confidence_threshold: 0.8,
      data_completeness: 0.95,  // 95% of metrics collected
      outcome_significance: 'p < 0.05'  // Statistical significance
    };
  }

  /**
   * Generate validation rules
   */
  generateValidationRules(opp) {
    return {
      reject_if: [
        'Missing > 5% of required metrics',
        'Confidence in outcome < 0.6',
        'Only 1 sample collected (need minimum 3)',
        'Contradicts previous high-confidence findings'
      ],
      validate_against: [
        'Existing execution_log outcomes',
        'Published model benchmarks',
        'User feedback when available',
        'Cost vs quality tradeoff analysis'
      ]
    };
  }

  /**
   * Format domain name for display
   */
  formatDomainName(domain) {
    return domain
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  /**
   * Generate comprehensive learning plan
   */
  generateLearningPlan() {
    this.createCampaigns();
    this.buildExperimentQueue();

    const plan = {
      timestamp: new Date().toISOString(),
      budget: this.budget,
      campaigns: this.campaigns.map(c => ({
        name: c.name,
        domain: c.domain,
        total_impact: c.total_impact.toFixed(1),
        total_cost: c.total_cost.toFixed(1),
        avg_efficiency: c.avg_efficiency.toFixed(2),
        opportunity_count: c.opportunities.length
      })),
      experiments: this.experiments.map(e => ({
        id: e.id,
        campaign: e.campaign,
        opportunity: e.opportunity,
        priority: e.priority,
        impact: e.impact.toFixed(1),
        cost: e.cost.toFixed(1),
        efficiency: e.efficiency.toFixed(2),
        estimated_tokens: e.estimated_tokens,
        estimated_time_hours: e.estimated_time_hours.toFixed(2),
        status: e.status,
        dependencies: e.dependencies,
        success_criteria: e.success_criteria
      })),
      summary: {
        total_opportunities: this.opportunities.length,
        total_campaigns: this.campaigns.length,
        executable_experiments: this.experiments.length,
        total_estimated_tokens: this.experiments.reduce((s, e) => s + e.estimated_tokens, 0),
        total_estimated_time_hours: this.experiments.reduce((s, e) => s + e.estimated_time_hours, 0),
        token_budget: this.budget.tokens,
        tokens_allocated: this.experiments.reduce((s, e) => s + e.estimated_tokens, 0),
        tokens_remaining: this.budget.tokens - this.experiments.reduce((s, e) => s + e.estimated_tokens, 0)
      }
    };

    return plan;
  }

  /**
   * Output learning plan as formatted text
   */
  formatPlan(plan) {
    console.log('\n' + '='.repeat(100));
    console.log('STRATEGIC LEARNING PLAN');
    console.log('='.repeat(100));

    console.log('\nBUDGET ALLOCATION:');
    console.log(`  Token Budget: ${plan.budget.tokens.toLocaleString()} tokens`);
    console.log(`  Time Budget: ${plan.budget.time_hours} hours`);

    console.log('\nCAMPAIGNS (Grouped Learning Initiatives):');
    for (const campaign of plan.campaigns) {
      console.log(`\n  ${campaign.name}`);
      console.log(`    Domain: ${campaign.domain}`);
      console.log(`    Impact: ${campaign.total_impact}/100 | Cost: ${campaign.total_cost}/100 | Efficiency: ${campaign.avg_efficiency}`);
      console.log(`    Opportunities: ${campaign.opportunity_count}`);
    }

    console.log('\n\nEXPERIMENT QUEUE (Top 10):');
    const top10 = plan.experiments.slice(0, 10);
    for (let i = 0; i < top10.length; i++) {
      const exp = top10[i];
      console.log(`\n  [${i + 1}] ${exp.opportunity}`);
      console.log(`      Impact: ${exp.impact} | Cost: ${exp.cost} | Efficiency: ${exp.efficiency}`);
      console.log(`      Estimated: ${exp.estimated_tokens} tokens, ${exp.estimated_time_hours}h`);
      console.log(`      Dependencies: ${exp.dependencies.length > 0 ? exp.dependencies.map(d => d.requirement).join(', ') : 'None'}`);
    }

    console.log('\n\nBUDGET SUMMARY:');
    console.log(`  Total Token Budget: ${plan.summary.token_budget.toLocaleString()}`);
    console.log(`  Allocated: ${plan.summary.tokens_allocated.toLocaleString()}`);
    console.log(`  Remaining: ${plan.summary.tokens_remaining.toLocaleString()}`);
    console.log(`  Experiments: ${plan.summary.executable_experiments}`);
    console.log(`  Estimated Time: ${plan.summary.total_estimated_time_hours.toFixed(1)} hours`);

    console.log('\n' + '='.repeat(100) + '\n');
  }

  /**
   * Save plan to files
   */
  savePlan(outputDir) {
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    const plan = this.generateLearningPlan();

    // Save plan JSON
    fs.writeFileSync(
      path.join(outputDir, 'learning-plan.json'),
      JSON.stringify(plan, null, 2)
    );

    // Save experiment prompts
    const promptFile = path.join(outputDir, 'experiment-prompts.md');
    let promptsMarkdown = '# Learning Experiments\n\n';
    for (const exp of this.experiments) {
      promptsMarkdown += `## ${exp.opportunity}\n\n`;
      promptsMarkdown += `**ID:** ${exp.id}\n`;
      promptsMarkdown += `**Campaign:** ${exp.campaign}\n`;
      promptsMarkdown += `**Priority:** ${exp.priority}\n`;
      promptsMarkdown += `**Efficiency:** ${exp.efficiency.toFixed(2)} (Impact: ${exp.impact} / Cost: ${exp.cost})\n\n`;
      promptsMarkdown += '```\n' + exp.prompt + '\n```\n\n';
      promptsMarkdown += `**Metrics:** ${exp.metrics.join(', ')}\n`;
      promptsMarkdown += `**Success Criteria:** ${JSON.stringify(exp.success_criteria, null, 2)}\n\n`;
      promptsMarkdown += '---\n\n';
    }
    fs.writeFileSync(promptFile, promptsMarkdown);

    console.error(`[StrategicPlanner] Plan saved to ${outputDir}`);
    console.error(`  - learning-plan.json`);
    console.error(`  - experiment-prompts.md`);

    return { plan, outputDir };
  }
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  let opportunitiesPath = null;
  let budgetTokens = 1000000;
  let outputDir = './learning-plan';

  // Parse arguments
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--opportunities') opportunitiesPath = args[++i];
    else if (args[i] === '--budget') budgetTokens = parseInt(args[++i]);
    else if (args[i] === '--output') outputDir = args[++i];
  }

  const planner = new StrategicLearningPlanner(opportunitiesPath);
  planner.setBudget(budgetTokens);

  const plan = planner.generateLearningPlan();
  planner.formatPlan(plan);
  planner.savePlan(outputDir);

  // Output JSON for programmatic use
  console.log(JSON.stringify(plan, null, 2));
}

if (require.main === module) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { StrategicLearningPlanner };
