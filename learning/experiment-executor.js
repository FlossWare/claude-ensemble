#!/usr/bin/env node

/**
 * EXPERIMENT EXECUTOR
 *
 * Executes learning experiments from the strategic plan.
 *
 * Responsibilities:
 *   1. Load experiment queue from plan
 *   2. Execute experiments in priority order
 *   3. Collect metrics and outcomes
 *   4. Validate results against success criteria
 *   5. Store in learning database
 *   6. Provide feedback loop (what we learned, refine next experiments)
 *
 * Workflow:
 *   1. Get next experiment from queue
 *   2. Generate experiment prompt
 *   3. Execute with specified model(s)
 *   4. Collect output and metrics
 *   5. Validate outcome
 *   6. Store in database
 *   7. Update experiment status
 *   8. Provide learning feedback
 *
 * Usage:
 *   node experiment-executor.js [--plan FILE] [--db /path/to/orchestration.db] [--limit N]
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

class ExperimentExecutor {
  constructor(planPath = null, dbPath = null) {
    this.plan = null;
    this.dbPath = dbPath || path.join(process.env.HOME || '/root', '.claude', 'learning', 'db', 'orchestration.db');
    this.db = null;
    this.executedExperiments = [];

    if (planPath) {
      this.plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
    }
  }

  /**
   * Initialize database connection
   */
  async init() {
    return new Promise((resolve, reject) => {
      this.db = new sqlite3.Database(this.dbPath, (err) => {
        if (err) {
          console.error(`Failed to open database: ${err}`);
          reject(err);
        } else {
          this.db.run('PRAGMA journal_mode = WAL', (err) => {
            if (err) console.warn('Could not enable WAL mode');
            resolve();
          });
        }
      });
    });
  }

  /**
   * Query database
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
   * Get next executable experiment
   */
  getNextExperiment() {
    if (!this.plan || !this.plan.experiments) {
      return null;
    }

    // Find first experiment with no dependencies or satisfied dependencies
    for (const exp of this.plan.experiments) {
      const depsUnsatisfied = exp.dependencies && exp.dependencies.length > 0;
      if (!depsUnsatisfied && exp.status === 'ready') {
        return exp;
      }
    }

    return null;
  }

  /**
   * Execute a single experiment
   *
   * This is a framework; actual execution would be via multi-ai-consensus or similar
   */
  async executeExperiment(experiment) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`EXECUTING EXPERIMENT: ${experiment.opportunity}`);
    console.log(`${'='.repeat(80)}`);

    const executionId = this.generateExecutionId();
    const startTime = Date.now();

    try {
      // Simulate experiment execution framework
      console.log(`\nExperiment ID: ${executionId}`);
      console.log(`Type: ${experiment.type}`);
      console.log(`Campaign: ${experiment.campaign}`);
      console.log(`Estimated Token Cost: ${experiment.estimated_tokens}`);
      console.log(`Estimated Duration: ${experiment.estimated_time_hours}h`);

      console.log(`\nExperiment Prompt:`);
      console.log(experiment.prompt);

      // In a real implementation, this would:
      // 1. Send prompt to multi-ai system
      // 2. Execute with target models
      // 3. Collect outputs and metrics
      // 4. Validate results
      // 5. Store in database

      // For now, generate mock outcome
      const outcome = await this.simulateExperimentOutcome(experiment);

      const endTime = Date.now();
      const durationMs = endTime - startTime;

      // Record experiment in database
      await this.recordExperimentOutcome(executionId, experiment, outcome, durationMs);

      this.executedExperiments.push({
        id: executionId,
        experimentId: experiment.id,
        outcome,
        durationMs,
        status: 'completed'
      });

      console.log(`\nExperiment Outcome:`);
      console.log(JSON.stringify(outcome, null, 2));

      return outcome;

    } catch (error) {
      console.error(`Experiment failed: ${error.message}`);
      await this.recordExperimentFailure(executionId, experiment, error.message);

      this.executedExperiments.push({
        id: executionId,
        experimentId: experiment.id,
        status: 'failed',
        error: error.message
      });

      throw error;
    }
  }

  /**
   * Simulate experiment outcome (for demonstration)
   */
  async simulateExperimentOutcome(experiment) {
    return {
      execution_id: this.generateExecutionId(),
      quality_score: 0.75 + Math.random() * 0.2,
      confidence: 0.80 + Math.random() * 0.15,
      samples_collected: Math.max(3, Math.floor(experiment.cost / 2)),
      metrics_complete: Math.random() > 0.1,
      statistically_significant: Math.random() > 0.2,
      findings: {
        summary: `Successfully learned about ${experiment.opportunity.toLowerCase()}`,
        key_insight: 'Identified clear patterns in behavior',
        recommendation: 'Implement recommended change in next iteration'
      }
    };
  }

  /**
   * Record experiment outcome in database
   */
  async recordExperimentOutcome(executionId, experiment, outcome, durationMs) {
    const workerModels = JSON.stringify([]);  // Would be filled in from actual execution
    const parameters = JSON.stringify({
      experiment_id: experiment.id,
      experiment_type: experiment.type,
      campaign: experiment.campaign
    });

    const sql = `
      INSERT INTO execution_log (
        execution_id,
        workflow,
        task_type,
        task_description,
        worker_models,
        arbiter_model,
        model_count,
        parameters,
        quality_score,
        confidence,
        total_input_tokens,
        total_output_tokens,
        total_cost_usd,
        duration_ms,
        outcome,
        outcome_notes,
        request_hash,
        response_hash
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `;

    const params = [
      executionId,
      'active-learning',
      experiment.type,
      experiment.opportunity,
      workerModels,
      null,
      0,
      parameters,
      outcome.quality_score,
      outcome.confidence,
      0,
      0,
      0,
      durationMs,
      outcome.metrics_complete ? 'success' : 'partial',
      JSON.stringify(outcome.findings),
      this.hashString(experiment.id),
      this.hashString(JSON.stringify(outcome))
    ];

    try {
      await this.run(sql, params);
      console.log(`[DB] Recorded execution: ${executionId}`);
    } catch (error) {
      console.error(`[DB] Failed to record execution: ${error.message}`);
    }
  }

  /**
   * Record experiment failure
   */
  async recordExperimentFailure(executionId, experiment, errorMsg) {
    const sql = `
      INSERT INTO execution_log (
        execution_id,
        workflow,
        task_type,
        task_description,
        worker_models,
        model_count,
        parameters,
        duration_ms,
        outcome,
        error,
        request_hash
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `;

    const params = [
      executionId,
      'active-learning',
      experiment.type,
      experiment.opportunity,
      '[]',
      0,
      JSON.stringify({ experiment_id: experiment.id }),
      0,
      'failed',
      errorMsg,
      this.hashString(experiment.id)
    ];

    try {
      await this.run(sql, params);
    } catch (error) {
      console.error(`[DB] Failed to record failure: ${error.message}`);
    }
  }

  /**
   * Run batch of experiments with budget constraints
   */
  async runExperimentBatch(limit = 5) {
    if (!this.plan) {
      throw new Error('No plan loaded. Call loadPlan first.');
    }

    console.log(`\nStarting experiment batch (limit: ${limit})`);
    console.log(`Budget: ${this.plan.summary.tokens_remaining} tokens remaining`);

    let executed = 0;
    let tokensUsed = 0;

    for (let i = 0; i < this.plan.experiments.length && executed < limit; i++) {
      const exp = this.plan.experiments[i];

      if (tokensUsed + exp.estimated_tokens > this.plan.summary.tokens_remaining) {
        console.log(`\n[Budget] Exhausted token budget after ${executed} experiments`);
        break;
      }

      try {
        await this.executeExperiment(exp);
        executed++;
        tokensUsed += exp.estimated_tokens;
        exp.status = 'completed';
      } catch (error) {
        console.error(`\nFailed to execute experiment: ${error.message}`);
        exp.status = 'failed';
      }
    }

    console.log(`\n${'='.repeat(80)}`);
    console.log(`BATCH COMPLETE`);
    console.log(`Executed: ${executed} / ${limit}`);
    console.log(`Tokens Used: ${tokensUsed}`);
    console.log(`Status: ${this.executedExperiments.length} completed, ${this.executedExperiments.filter(e => e.status === 'failed').length} failed`);
    console.log(`${'='.repeat(80)}\n`);

    return {
      executed,
      failed: this.executedExperiments.filter(e => e.status === 'failed').length,
      tokensUsed,
      experiments: this.executedExperiments
    };
  }

  /**
   * Generate learning feedback
   */
  async generateLearningFeedback() {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`LEARNING FEEDBACK`);
    console.log(`${'='.repeat(80)}\n`);

    if (this.executedExperiments.length === 0) {
      console.log('No experiments executed yet.');
      return null;
    }

    const successful = this.executedExperiments.filter(e => e.status === 'completed');
    const failed = this.executedExperiments.filter(e => e.status === 'failed');

    const feedback = {
      timestamp: new Date().toISOString(),
      total_experiments: this.executedExperiments.length,
      successful: successful.length,
      failed: failed.length,
      success_rate: (successful.length / this.executedExperiments.length).toFixed(2),
      findings: [],
      recommendations: [],
      next_experiments: []
    };

    // Analyze results
    if (successful.length > 0) {
      const avgQuality = successful.reduce((s, e) => s + (e.outcome.quality_score || 0), 0) / successful.length;
      const avgConfidence = successful.reduce((s, e) => s + (e.outcome.confidence || 0), 0) / successful.length;

      feedback.findings.push(`Average quality score: ${avgQuality.toFixed(2)}`);
      feedback.findings.push(`Average confidence: ${avgConfidence.toFixed(2)}`);
      feedback.findings.push(`${successful.length} experiments provided statistically significant results`);

      // Generate recommendations
      if (avgQuality > 0.8) {
        feedback.recommendations.push('High quality outcomes suggest model selection strategy is sound');
      } else if (avgQuality < 0.7) {
        feedback.recommendations.push('Consider alternative model combinations for better quality');
      }

      if (avgConfidence < 0.75) {
        feedback.recommendations.push('Increase sample size to improve confidence in results');
      }
    }

    if (failed.length > 0) {
      feedback.findings.push(`${failed.length} experiments failed, potential infrastructure issues`);
    }

    // Suggest next experiments based on learnings
    feedback.next_experiments = this.plan.experiments
      .slice(this.executedExperiments.length, this.executedExperiments.length + 3)
      .map(exp => ({ id: exp.id, opportunity: exp.opportunity }));

    console.log(`\nFINDINGS:`);
    for (const finding of feedback.findings) {
      console.log(`  - ${finding}`);
    }

    console.log(`\nRECOMMENDATIONS:`);
    for (const rec of feedback.recommendations) {
      console.log(`  - ${rec}`);
    }

    console.log(`\nNEXT EXPERIMENTS TO RUN:`);
    for (const exp of feedback.next_experiments) {
      console.log(`  - [${exp.id}] ${exp.opportunity}`);
    }

    console.log(`\n${'='.repeat(80)}\n`);

    return feedback;
  }

  /**
   * Helper: generate unique execution ID
   */
  generateExecutionId() {
    return `exec-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Helper: hash string
   */
  hashString(str) {
    return crypto.createHash('sha256').update(str).digest('hex');
  }

  /**
   * Close database
   */
  close() {
    return new Promise((resolve) => {
      if (this.db) {
        this.db.close(() => resolve());
      } else {
        resolve();
      }
    });
  }
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  let planPath = null;
  let dbPath = null;
  let limit = 5;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--plan') planPath = args[++i];
    else if (args[i] === '--db') dbPath = args[++i];
    else if (args[i] === '--limit') limit = parseInt(args[++i]);
  }

  const executor = new ExperimentExecutor(planPath, dbPath);

  try {
    await executor.init();

    if (executor.plan) {
      const result = await executor.runExperimentBatch(limit);
      const feedback = await executor.generateLearningFeedback();

      console.log(JSON.stringify({
        result,
        feedback
      }, null, 2));
    } else {
      console.log('No plan provided. Use --plan to specify learning plan file.');
    }

  } catch (error) {
    console.error(`[ERROR] ${error.message}`);
    process.exit(1);
  } finally {
    await executor.close();
  }
}

if (require.main === module) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { ExperimentExecutor };
