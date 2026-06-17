#!/usr/bin/env node

/**
 * ACTIVE LEARNING ENGINE
 *
 * Identifies the most valuable learning opportunities (highest impact, lowest cost)
 * and prioritizes research and data collection.
 *
 * System identifies:
 *   1. Knowledge gaps with highest impact (uncertainty in frequent decisions)
 *   2. High-variance outcomes (quality unstable across similar executions)
 *   3. Underexplored parameter spaces (few executions, high potential value)
 *   4. Model combinations never tested together
 *   5. Task types with divergent model performance (unclear winner)
 *
 * Outputs prioritized learning agenda with:
 *   - Learning opportunity name
 *   - Impact score (0-100): how much value fixing this gap provides
 *   - Cost score (0-100): how expensive to run experiments (tokens, time, models)
 *   - Efficiency = impact / cost (highest first = best ROI)
 *   - Recommended experiment (sample prompt, model setup, metrics to collect)
 *   - Expected outcome (what we'll learn)
 *
 * Usage:
 *   node active-learning-engine.js [--db /path/to/orchestration.db] [--limit N] [--cost-budget TOKENS]
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

// ============================================================================
// CONFIGURATION
// ============================================================================

const DEFAULT_DB = path.join(process.env.HOME || '/root', '.claude', 'learning', 'db', 'orchestration.db');
const LEARNING_DIR = path.dirname(DEFAULT_DB);

class ActiveLearningEngine {
  constructor(dbPath = DEFAULT_DB) {
    this.dbPath = dbPath;
    this.db = null;
    this.opportunities = [];
  }

  /**
   * Initialize database connection
   */
  async init() {
    return new Promise((resolve, reject) => {
      // Ensure directory exists
      if (!fs.existsSync(LEARNING_DIR)) {
        fs.mkdirSync(LEARNING_DIR, { recursive: true });
      }

      this.db = new sqlite3.Database(this.dbPath, (err) => {
        if (err) {
          console.error(`Failed to open database at ${this.dbPath}:`, err);
          reject(err);
        } else {
          // Enable WAL mode
          this.db.run('PRAGMA journal_mode = WAL', (err) => {
            if (err) console.warn('Could not enable WAL mode:', err);
            resolve();
          });
        }
      });
    });
  }

  /**
   * Query database with promise wrapper
   */
  query(sql, params = []) {
    return new Promise((resolve, reject) => {
      this.db.all(sql, params, (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      });
    });
  }

  /**
   * Get single row
   */
  queryOne(sql, params = []) {
    return new Promise((resolve, reject) => {
      this.db.get(sql, params, (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      });
    });
  }

  /**
   * Run arbitrary SQL
   */
  run(sql, params = []) {
    return new Promise((resolve, reject) => {
      this.db.run(sql, params, function(err) {
        if (err) reject(err);
        else resolve({ lastID: this.lastID, changes: this.changes });
      });
    });
  }

  /**
   * Main entry point: identify all learning opportunities
   */
  async identifyOpportunities() {
    console.error('[ActiveLearning] Analyzing execution history...');

    const opportunities = [];

    // Check if we have data
    const executionCount = await this.queryOne('SELECT COUNT(*) as cnt FROM execution_log');
    if (!executionCount || executionCount.cnt === 0) {
      console.error('[ActiveLearning] No execution history found. Run some workflows first.');
      return [];
    }

    console.error(`[ActiveLearning] Analyzing ${executionCount.cnt} executions...`);

    // Run all detection strategies in parallel
    const [
      gaps,
      variance,
      exploration,
      combinations,
      divergence,
      confidence,
      costAdj
    ] = await Promise.all([
      this.detectKnowledgeGaps(),
      this.detectHighVariance(),
      this.detectUnderexploredSpace(),
      this.detectUntested Combinations(),
      this.detectDivergentPerformance(),
      this.detectLowConfidenceAreas(),
      this.detectCostAnomalies()
    ]);

    opportunities.push(...gaps, ...variance, ...exploration, ...combinations, ...divergence, ...confidence, ...costAdj);

    // Sort by efficiency (impact / cost)
    opportunities.sort((a, b) => {
      const effA = a.impact / Math.max(a.cost, 1);
      const effB = b.impact / Math.max(b.cost, 1);
      return effB - effA;
    });

    this.opportunities = opportunities;
    return opportunities;
  }

  /**
   * OPPORTUNITY 1: Knowledge Gaps
   *
   * Detect decisions made with high uncertainty.
   * High impact: these decisions happen frequently and affect quality.
   * Low cost: we can measure via existing executions.
   */
  async detectKnowledgeGaps() {
    const gaps = [];

    // Gap 1: Which model selection strategy works best for each task type?
    const taskTypes = await this.query(`
      SELECT DISTINCT task_type
      FROM execution_log
      WHERE task_type IS NOT NULL
      GROUP BY task_type
      HAVING COUNT(*) >= 5
    `);

    for (const { task_type } of taskTypes) {
      const workers = await this.query(`
        SELECT DISTINCT model
        FROM (
          SELECT json_each.value as model
          FROM execution_log, json_each(json(worker_models))
          WHERE task_type = ? AND outcome = 'success'
        )
      `, [task_type]);

      if (workers.length >= 2) {
        const variance = await this.queryOne(`
          SELECT
            AVG(quality_score) as avg_q,
            CAST((MAX(quality_score) - MIN(quality_score)) as REAL) as range_q,
            COUNT(*) as n
          FROM execution_log
          WHERE task_type = ? AND quality_score IS NOT NULL
        `, [task_type]);

        if (variance && variance.range_q > 0.1) {
          gaps.push({
            id: `knowledge-gap-model-selection-${task_type}`,
            name: `Which model selection strategy optimizes ${task_type} quality?`,
            type: 'knowledge_gap',
            impact: Math.min(100, variance.range_q * 100 + variance.n),
            cost: 8,  // 3-4 runs with 2 models each
            domain: 'model_selection',
            context: { task_type, model_count: workers.length, quality_variance: variance.range_q },
            recommendation: {
              experiment: `Run 5 executions of ${task_type} tasks with different model sets (e.g., [opus], [sonnet], [opus+sonnet], [opus+sonnet+haiku]). Track quality_score and consensus_score.`,
              metrics: ['quality_score', 'consensus_score', 'total_cost_usd', 'duration_ms', 'selected_model'],
              expectedOutcome: `Learn optimal model count and combination for ${task_type}`
            }
          });
        }
      }
    }

    return gaps;
  }

  /**
   * OPPORTUNITY 2: High Variance Outcomes
   *
   * Detect task/model combinations with unstable results.
   * High impact: fixing variance improves reliability.
   * Low cost: investigate via existing data + targeted experiments.
   */
  async detectHighVariance() {
    const variance = [];

    const workflows = await this.query(`
      SELECT DISTINCT workflow
      FROM execution_log
      WHERE workflow IS NOT NULL
      GROUP BY workflow
      HAVING COUNT(*) >= 10
    `);

    for (const { workflow } of workflows) {
      const stats = await this.queryOne(`
        SELECT
          COUNT(*) as n,
          AVG(quality_score) as avg_q,
          MIN(quality_score) as min_q,
          MAX(quality_score) as max_q,
          SQRT(SUM((quality_score - (SELECT AVG(quality_score) FROM execution_log WHERE workflow = ?)) *
                   (quality_score - (SELECT AVG(quality_score) FROM execution_log WHERE workflow = ?))) / COUNT(*)) as stddev_q
        FROM execution_log
        WHERE workflow = ? AND quality_score IS NOT NULL
      `, [workflow, workflow, workflow]);

      if (stats && stats.stddev_q && stats.stddev_q > 0.15) {
        variance.push({
          id: `high-variance-${workflow}`,
          name: `High variance in ${workflow} outcomes (stddev=${stats.stddev_q.toFixed(2)})`,
          type: 'high_variance',
          impact: Math.min(100, stats.stddev_q * 200 * stats.n),
          cost: 5,
          domain: 'workflow_reliability',
          context: { workflow, avg_quality: stats.avg_q, stddev: stats.stddev_q, sample_count: stats.n },
          recommendation: {
            experiment: `Identify confounding variables in ${workflow}: input complexity, model combination, parameters. Stratify next 10 runs by these variables.`,
            metrics: ['quality_score', 'model_count', 'task_type', 'duration_ms', 'parameter_hash'],
            expectedOutcome: `Identify which parameter/model choice causes variance in ${workflow}`
          }
        });
      }
    }

    return variance;
  }

  /**
   * OPPORTUNITY 3: Underexplored Parameter Space
   *
   * Detect parameter combinations with few samples.
   * High impact: parameters directly affect quality/cost.
   * Low cost: we can test with one experiment.
   */
  async detectUnderexploredSpace() {
    const exploration = [];

    // Find rare model combinations
    const combinations = await this.query(`
      SELECT
        worker_models,
        arbiter_model,
        COUNT(*) as n,
        AVG(quality_score) as avg_q,
        AVG(total_cost_usd) as avg_cost
      FROM execution_log
      WHERE outcome = 'success' AND worker_models IS NOT NULL
      GROUP BY worker_models, arbiter_model
      ORDER BY n ASC
      LIMIT 10
    `);

    for (const combo of combinations) {
      if (combo.n < 3) {  // Very few samples
        exploration.push({
          id: `explore-combo-${combo.worker_models}-${combo.arbiter_model || 'none'}`,
          name: `Underexplored model combo: ${combo.worker_models.substring(0, 30)}...`,
          type: 'underexplored_space',
          impact: 25 + Math.random() * 50,  // Medium impact (promising but uncertain)
          cost: 4,  // 1-2 runs
          domain: 'model_combination',
          context: { worker_models: combo.worker_models, arbiter_model: combo.arbiter_model, samples: combo.n },
          recommendation: {
            experiment: `Run 2-3 diverse tasks with model combo [${combo.worker_models}], arbiter=${combo.arbiter_model}. Collect full metrics.`,
            metrics: ['quality_score', 'consensus_score', 'selected_model', 'total_cost_usd'],
            expectedOutcome: `Validate whether this model combo is viable or should be avoided`
          }
        });
      }
    }

    return exploration;
  }

  /**
   * OPPORTUNITY 4: Untested Model Combinations
   *
   * Detect high-potential model pairs that have never been tested.
   * High impact: may discover better combinations.
   * Medium cost: requires at least one targeted experiment.
   */
  async detectUntestedCombinations() {
    const untested = [];

    const allModels = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'];
    const testedPairs = await this.query(`
      SELECT DISTINCT worker_models FROM execution_log
      WHERE worker_models IS NOT NULL
    `);

    const testedSet = new Set(testedPairs.map(p => p.worker_models));

    // Generate promising untested combinations (based on known good pairs)
    const highQualityCombos = [
      '["opus","sonnet"]',
      '["opus","haiku"]',
      '["sonnet","haiku"]',
      '["opus","sonnet","haiku"]',
      '["gpt-4o","opus"]',
      '["gemini","opus"]'
    ];

    for (const combo of highQualityCombos) {
      if (!testedSet.has(combo)) {
        untested.push({
          id: `untested-combo-${combo}`,
          name: `Never tested: ${combo}`,
          type: 'untested_combination',
          impact: 60,
          cost: 5,
          domain: 'model_combination',
          context: { worker_models: JSON.parse(combo) },
          recommendation: {
            experiment: `Run 3 representative tasks with worker_models=${combo}. Use Fable as arbiter.`,
            metrics: ['quality_score', 'consensus_score', 'diversity_score', 'selected_model', 'total_cost_usd'],
            expectedOutcome: `Discover if ${combo} is a viable high-quality combo`
          }
        });
      }
    }

    return untested;
  }

  /**
   * OPPORTUNITY 5: Divergent Model Performance
   *
   * Detect task types where models disagree (high diversity).
   * High impact: unclear which model is right (need more data).
   * Medium cost: investigate via existing ratings + new experiments.
   */
  async detectDivergentPerformance() {
    const divergence = [];

    const taskTypes = await this.query(`
      SELECT DISTINCT task_type FROM execution_log
      WHERE task_type IS NOT NULL
      GROUP BY task_type
      HAVING COUNT(*) >= 5
    `);

    for (const { task_type } of taskTypes) {
      const modelPerfs = await this.query(`
        SELECT
          json_each.value as model,
          COUNT(*) as n,
          AVG(quality_score) as avg_q,
          MAX(quality_score) - MIN(quality_score) as range_q
        FROM execution_log, json_each(json(worker_models))
        WHERE task_type = ? AND quality_score IS NOT NULL
        GROUP BY model
        HAVING COUNT(*) >= 3
        ORDER BY avg_q DESC
      `, [task_type]);

      if (modelPerfs.length >= 2) {
        const best = modelPerfs[0].avg_q;
        const worst = modelPerfs[modelPerfs.length - 1].avg_q;
        const divergence_score = best - worst;

        if (divergence_score > 0.2) {
          divergence.push({
            id: `divergent-perf-${task_type}`,
            name: `Models diverge on ${task_type}: ${(divergence_score * 100).toFixed(0)}% quality gap`,
            type: 'divergent_performance',
            impact: Math.min(100, divergence_score * 150),
            cost: 6,
            domain: 'model_selection',
            context: {
              task_type,
              best_model: modelPerfs[0].model,
              worst_model: modelPerfs[modelPerfs.length - 1].model,
              gap: divergence_score,
              model_count: modelPerfs.length
            },
            recommendation: {
              experiment: `Run 5 diverse ${task_type} tasks. Compare all models directly. Get user ratings on outputs.`,
              metrics: ['quality_score', 'selected_model', 'user_rating', 'task_difficulty'],
              expectedOutcome: `Understand why models diverge on ${task_type} and which to prefer`
            }
          });
        }
      }
    }

    return divergence;
  }

  /**
   * OPPORTUNITY 6: Low Confidence Predictions
   *
   * Detect where arbiter confidence is low.
   * High impact: low confidence = risky decisions.
   * Medium cost: collect user feedback to validate.
   */
  async detectLowConfidenceAreas() {
    const lowConf = [];

    const lowConfExecs = await this.query(`
      SELECT
        workflow,
        task_type,
        COUNT(*) as n,
        AVG(confidence) as avg_conf,
        AVG(quality_score) as avg_q
      FROM execution_log
      WHERE confidence IS NOT NULL AND confidence < 0.7
      GROUP BY workflow, task_type
      HAVING COUNT(*) >= 3
      ORDER BY avg_conf ASC
      LIMIT 5
    `);

    for (const exec of lowConfExecs) {
      lowConf.push({
        id: `low-conf-${exec.workflow}-${exec.task_type}`,
        name: `Low arbiter confidence in ${exec.workflow}/${exec.task_type} (${(exec.avg_conf * 100).toFixed(0)}%)`,
        type: 'low_confidence',
        impact: Math.min(100, (1 - exec.avg_conf) * 100),
        cost: 3,  // Just need user ratings
        domain: 'arbiter_calibration',
        context: { workflow: exec.workflow, task_type: exec.task_type, avg_confidence: exec.avg_conf, sample_count: exec.n },
        recommendation: {
          experiment: `Collect user feedback on next 10 ${exec.workflow} executions. Compare arbiter confidence to actual user satisfaction.`,
          metrics: ['confidence', 'user_rating', 'selected_model', 'actual_quality'],
          expectedOutcome: `Recalibrate arbiter confidence scores for ${exec.workflow}`
        }
      });
    }

    return lowConf;
  }

  /**
   * OPPORTUNITY 7: Cost Anomalies
   *
   * Detect model/parameter combos that are unexpectedly expensive.
   * High impact: cost directly affects budget.
   * Low cost: analyze existing data.
   */
  async detectCostAnomalies() {
    const anomalies = [];

    const costStats = await this.query(`
      SELECT
        json_each.value as model,
        task_type,
        COUNT(*) as n,
        AVG(total_cost_usd) as avg_cost,
        MAX(total_cost_usd) as max_cost,
        AVG(quality_score) as avg_q,
        AVG(total_cost_usd) / NULLIF(AVG(quality_score), 0) as cost_per_quality
      FROM execution_log, json_each(json(worker_models))
      WHERE task_type IS NOT NULL AND total_cost_usd > 0
      GROUP BY model, task_type
      HAVING COUNT(*) >= 3
      ORDER BY cost_per_quality DESC
      LIMIT 5
    `);

    for (const stat of costStats) {
      if (stat.cost_per_quality > 1.0) {  // More than $1 per quality point
        anomalies.push({
          id: `cost-anomaly-${stat.model}-${stat.task_type}`,
          name: `Expensive: ${stat.model} on ${stat.task_type} costs $${stat.cost_per_quality.toFixed(2)}/quality`,
          type: 'cost_anomaly',
          impact: 40 + (stat.n * 2),  // Impact scales with frequency
          cost: 2,  // Just analysis
          domain: 'cost_optimization',
          context: {
            model: stat.model,
            task_type: stat.task_type,
            avg_cost: stat.avg_cost,
            avg_quality: stat.avg_q,
            cost_per_quality: stat.cost_per_quality,
            sample_count: stat.n
          },
          recommendation: {
            experiment: `Compare ${stat.model} with cheaper alternative (e.g., sonnet) on same ${stat.task_type} tasks. Same quality? Switch to cheaper model.`,
            metrics: ['total_cost_usd', 'quality_score', 'model'],
            expectedOutcome: `Identify cost optimization: replace ${stat.model} with cheaper equivalent on ${stat.task_type}`
          }
        });
      }
    }

    return anomalies;
  }

  /**
   * Close database
   */
  close() {
    return new Promise((resolve, reject) => {
      if (this.db) {
        this.db.close((err) => {
          if (err) reject(err);
          else resolve();
        });
      } else {
        resolve();
      }
    });
  }

  /**
   * Format opportunities for display
   */
  formatOpportunities(opportunities, limit = 20) {
    const sorted = opportunities.slice(0, limit);

    console.log('\n' + '='.repeat(100));
    console.log('ACTIVE LEARNING OPPORTUNITIES');
    console.log('='.repeat(100));

    sorted.forEach((opp, idx) => {
      const efficiency = opp.impact / Math.max(opp.cost, 1);
      console.log(`\n[${idx + 1}] ${opp.name}`);
      console.log(`    Type: ${opp.type} | Domain: ${opp.domain}`);
      console.log(`    Impact: ${opp.impact.toFixed(0)}/100 | Cost: ${opp.cost.toFixed(0)}/100 | Efficiency: ${efficiency.toFixed(1)}`);
      console.log(`    \n    Experiment: ${opp.recommendation.experiment}`);
      console.log(`    Expected Outcome: ${opp.recommendation.expectedOutcome}`);
      if (opp.context) {
        console.log(`    Context: ${JSON.stringify(opp.context)}`);
      }
    });

    console.log('\n' + '='.repeat(100));
    console.log(`SUMMARY: ${sorted.length} opportunities identified`);
    console.log(`Total potential impact: ${sorted.reduce((s, o) => s + o.impact, 0).toFixed(0)}/100`);
    console.log(`Total estimated cost: ${sorted.reduce((s, o) => s + o.cost, 0).toFixed(0)}/100`);
    console.log('='.repeat(100) + '\n');

    return sorted;
  }

  /**
   * Save opportunities to JSON
   */
  async saveOpportunities(outputPath) {
    const data = {
      timestamp: new Date().toISOString(),
      total_opportunities: this.opportunities.length,
      opportunities: this.opportunities,
      summary: {
        by_domain: {},
        by_type: {},
        efficiency_ranking: this.opportunities
          .map((o, idx) => ({
            rank: idx + 1,
            name: o.name,
            efficiency: o.impact / Math.max(o.cost, 1)
          }))
          .slice(0, 10)
      }
    };

    // Aggregate by domain and type
    for (const opp of this.opportunities) {
      data.summary.by_domain[opp.domain] = (data.summary.by_domain[opp.domain] || 0) + 1;
      data.summary.by_type[opp.type] = (data.summary.by_type[opp.type] || 0) + 1;
    }

    fs.writeFileSync(outputPath, JSON.stringify(data, null, 2));
    console.error(`[ActiveLearning] Opportunities saved to ${outputPath}`);

    return outputPath;
  }
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  let dbPath = DEFAULT_DB;
  let limit = 20;
  let outputPath = null;

  // Parse arguments
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--db') dbPath = args[++i];
    else if (args[i] === '--limit') limit = parseInt(args[++i]);
    else if (args[i] === '--output') outputPath = args[++i];
  }

  const engine = new ActiveLearningEngine(dbPath);

  try {
    await engine.init();
    const opportunities = await engine.identifyOpportunities();
    const formatted = engine.formatOpportunities(opportunities, limit);

    if (outputPath) {
      await engine.saveOpportunities(outputPath);
    }

    // Output as JSON for programmatic use
    console.log(JSON.stringify(formatted.map(o => ({
      id: o.id,
      name: o.name,
      type: o.type,
      domain: o.domain,
      impact: parseFloat(o.impact.toFixed(1)),
      cost: parseFloat(o.cost.toFixed(1)),
      efficiency: parseFloat((o.impact / Math.max(o.cost, 1)).toFixed(1)),
      context: o.context,
      recommendation: o.recommendation
    })), null, 2));

  } catch (error) {
    console.error('[ERROR]', error.message);
    process.exit(1);
  } finally {
    await engine.close();
  }
}

if (require.main === module) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { ActiveLearningEngine };
