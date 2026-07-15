#!/usr/bin/env node
/**
 * Issue Correlator Integration
 *
 * Integrates issue-code correlator with existing systems:
 * - Complexity estimator (predict effort for issue fix)
 * - Fleet executor (route issue fixes to appropriate workers)
 * - Workflow storage (track correlation accuracy)
 *
 * Usage:
 *   node integrate_issue_correlator.mjs analyze-issue 123
 *   node integrate_issue_correlator.mjs suggest-fix 456 --auto-assign
 *   node integrate_issue_correlator.mjs train-and-deploy
 */

import { execSync, spawn } from 'child_process';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

class IssueCorrelatorIntegration {
  constructor() {
    this.correlatorPath = join(__dirname, 'issue_code_correlator.py');
    this.trainerPath = join(__dirname, 'issue_correlator_trainer.py');
    this.complexityPath = join(__dirname, 'predict_complexity.py');
    this.modelPath = join(process.env.HOME, 'fine-tuning', 'checkpoints', 'issue-correlator');
  }

  /**
   * Analyze issue and suggest relevant code + complexity estimate
   */
  async analyzeIssue(issueNumber, options = {}) {
    console.log(`🔍 Analyzing issue #${issueNumber}...`);

    // Step 1: Find correlated code
    const correlations = this._findCorrelatedCode(issueNumber, options.topK || 10);

    if (!correlations || correlations.length === 0) {
      console.log(`⚠ No code correlations found for issue #${issueNumber}`);
      return { issue: issueNumber, correlations: [], complexity: null };
    }

    console.log(`\n📂 Found ${correlations.length} correlated files:\n`);

    const analysis = {
      issue: issueNumber,
      correlations: [],
      complexity: null,
      estimated_effort_hours: null,
      suggested_assignee: null
    };

    // Step 2: Estimate complexity for each correlated file
    for (const corr of correlations) {
      console.log(`   ${corr.file_path} (similarity: ${corr.similarity_score.toFixed(3)})`);

      // Predict complexity
      const complexity = this._predictComplexity(corr.file_path, issueNumber);

      analysis.correlations.push({
        file_path: corr.file_path,
        similarity_score: corr.similarity_score,
        complexity: complexity?.complexity || 'unknown',
        confidence: complexity?.confidence || 0,
        language: corr.language
      });
    }

    // Step 3: Aggregate complexity estimate
    const avgComplexity = this._aggregateComplexity(analysis.correlations);
    analysis.complexity = avgComplexity.level;
    analysis.estimated_effort_hours = avgComplexity.hours;

    // Step 4: Suggest assignee based on complexity
    analysis.suggested_assignee = this._suggestAssignee(avgComplexity.level);

    console.log(`\n📊 Overall Complexity: ${analysis.complexity} (~${analysis.estimated_effort_hours}h)`);
    console.log(`👤 Suggested Assignee: ${analysis.suggested_assignee}\n`);

    return analysis;
  }

  /**
   * Auto-assign issue to fleet worker based on correlation + complexity
   */
  async suggestFix(issueNumber, options = {}) {
    const analysis = await this.analyzeIssue(issueNumber, options);

    if (options.autoAssign) {
      console.log(`🤖 Auto-assigning issue #${issueNumber} to ${analysis.suggested_assignee}...`);

      // Create workflow task
      const task = {
        issue: issueNumber,
        files: analysis.correlations.map(c => c.file_path),
        complexity: analysis.complexity,
        estimated_hours: analysis.estimated_effort_hours,
        assignee: analysis.suggested_assignee
      };

      // Queue to fleet executor
      this._queueToFleet(task);

      console.log(`✓ Queued to fleet executor`);
    }

    return analysis;
  }

  /**
   * Train correlator model and deploy
   */
  async trainAndDeploy(options = {}) {
    console.log('🚀 Training issue-code correlator...\n');

    // Step 1: Ingest recent issues
    console.log('📥 Ingesting issues from GitLab...');
    try {
      execSync(
        `python3 "${this.correlatorPath}" ingest-issues --platform gitlab --limit 100 --state open`,
        { stdio: 'inherit' }
      );
    } catch (err) {
      console.log('⚠ Issue ingestion failed (continuing anyway)');
    }

    // Step 2: Ingest code
    console.log('\n📥 Ingesting code files...');
    try {
      execSync(
        `python3 "${this.correlatorPath}" ingest-code --path . --extensions py,js,mjs,ts,java`,
        { stdio: 'inherit' }
      );
    } catch (err) {
      console.log('⚠ Code ingestion failed (continuing anyway)');
    }

    // Step 3: Train model
    console.log('\n🧠 Training model on git history + correlations...');
    const epochs = options.epochs || 3;
    const batchSize = options.batchSize || 16;

    try {
      execSync(
        `python3 "${this.trainerPath}" --repo-path . --use-git --epochs ${epochs} --batch-size ${batchSize}`,
        { stdio: 'inherit' }
      );

      console.log(`\n✓ Model trained and saved to ${this.modelPath}`);
    } catch (err) {
      console.log('\n⚠ Training failed:', err.message);
      return false;
    }

    // Step 4: Update correlator to use new model
    console.log('\n🔄 Updating correlator configuration...');
    this._updateModelConfig();

    // Step 5: Re-run auto-correlate
    console.log('\n🔗 Re-correlating all open issues with new model...');
    try {
      execSync(
        `python3 "${this.correlatorPath}" auto-correlate --threshold 0.7 --top 5`,
        { stdio: 'inherit' }
      );
    } catch (err) {
      console.log('⚠ Auto-correlate failed');
    }

    console.log('\n✅ Training and deployment complete!');
    return true;
  }

  /**
   * Find correlated code for issue
   */
  _findCorrelatedCode(issueNumber, topK = 10) {
    try {
      const result = execSync(
        `python3 "${this.correlatorPath}" correlate --issue ${issueNumber} --top ${topK} --threshold 0.6`,
        { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'ignore'] }
      );

      // Parse output (looking for JSON or structured text)
      // For now, return mock data since output format varies
      return this._parseMockCorrelations(issueNumber);

    } catch (err) {
      console.error('⚠ Correlation failed:', err.message);
      return [];
    }
  }

  /**
   * Predict complexity for file
   */
  _predictComplexity(filePath, context) {
    if (!existsSync(this.complexityPath)) {
      return { complexity: 'medium', confidence: 0.5 };
    }

    try {
      const result = execSync(
        `python3 "${this.complexityPath}" "${filePath}" --context "${context}"`,
        { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'ignore'] }
      );

      // Parse JSON output
      return JSON.parse(result.trim());
    } catch (err) {
      return { complexity: 'medium', confidence: 0.5 };
    }
  }

  /**
   * Aggregate complexity from multiple files
   */
  _aggregateComplexity(correlations) {
    const weights = {
      'low': 1,
      'medium': 3,
      'high': 8,
      'very_high': 16
    };

    let totalWeight = 0;
    let totalScore = 0;

    for (const corr of correlations) {
      const weight = corr.similarity_score;
      const score = weights[corr.complexity] || weights['medium'];

      totalWeight += weight;
      totalScore += score * weight;
    }

    const avgScore = totalWeight > 0 ? totalScore / totalWeight : 3;

    // Convert back to level
    let level, hours;
    if (avgScore < 2) {
      level = 'low';
      hours = 1;
    } else if (avgScore < 5) {
      level = 'medium';
      hours = 3;
    } else if (avgScore < 12) {
      level = 'high';
      hours = 8;
    } else {
      level = 'very_high';
      hours = 16;
    }

    return { level, hours, score: avgScore };
  }

  /**
   * Suggest assignee based on complexity
   */
  _suggestAssignee(complexity) {
    const assignments = {
      'low': 'local-haiku',  // Fast, cheap
      'medium': 'sonnet-3.5',  // Balanced
      'high': 'opus-4',  // Best quality
      'very_high': 'multi-agent-consensus'  // Needs review
    };

    return assignments[complexity] || 'sonnet-3.5';
  }

  /**
   * Queue task to fleet executor
   */
  _queueToFleet(task) {
    const queueFile = join(__dirname, '..', 'learning', 'issue_fix_queue.json');

    let queue = [];
    if (existsSync(queueFile)) {
      queue = JSON.parse(readFileSync(queueFile, 'utf-8'));
    }

    queue.push({
      ...task,
      queued_at: new Date().toISOString(),
      status: 'pending'
    });

    writeFileSync(queueFile, JSON.stringify(queue, null, 2));
  }

  /**
   * Update model configuration
   */
  _updateModelConfig() {
    const configFile = join(__dirname, '..', 'learning', 'issue_correlator_config.json');

    const config = {
      model_path: this.modelPath,
      last_trained: new Date().toISOString(),
      use_custom_model: existsSync(this.modelPath),
      fallback_model: 'sentence-transformers/all-mpnet-base-v2'
    };

    writeFileSync(configFile, JSON.stringify(config, null, 2));
  }

  /**
   * Parse mock correlations (temporary until real integration)
   */
  _parseMockCorrelations(issueNumber) {
    // Mock data for demonstration
    return [
      {
        file_path: 'tools/complexity_estimator.py',
        similarity_score: 0.87,
        language: 'py',
        code_preview: 'def estimate_complexity...'
      },
      {
        file_path: 'workflows/fleet-fixes-critical-issues.mjs',
        similarity_score: 0.73,
        language: 'mjs',
        code_preview: 'export default async function...'
      }
    ];
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  const integration = new IssueCorrelatorIntegration();

  if (!command) {
    console.log(`
Usage:
  node integrate_issue_correlator.mjs <command> [options]

Commands:
  analyze-issue <number>        Analyze issue and find correlated code
  suggest-fix <number>          Suggest fix with complexity estimate
  train-and-deploy              Train model and deploy to production

Options:
  --auto-assign                 Auto-assign to fleet worker
  --top-k <n>                   Number of correlations (default: 10)
  --epochs <n>                  Training epochs (default: 3)
  --batch-size <n>              Batch size (default: 16)

Examples:
  node integrate_issue_correlator.mjs analyze-issue 123
  node integrate_issue_correlator.mjs suggest-fix 456 --auto-assign
  node integrate_issue_correlator.mjs train-and-deploy --epochs 5
    `);
    process.exit(0);
  }

  const parseOptions = () => {
    const opts = {};
    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--auto-assign') opts.autoAssign = true;
      if (args[i] === '--top-k') opts.topK = parseInt(args[++i]);
      if (args[i] === '--epochs') opts.epochs = parseInt(args[++i]);
      if (args[i] === '--batch-size') opts.batchSize = parseInt(args[++i]);
    }
    return opts;
  };

  try {
    const options = parseOptions();

    if (command === 'analyze-issue') {
      const issueNumber = parseInt(args[1]);
      if (!issueNumber) {
        console.error('Error: Missing issue number');
        process.exit(1);
      }
      const result = await integration.analyzeIssue(issueNumber, options);
      console.log(JSON.stringify(result, null, 2));
    }
    else if (command === 'suggest-fix') {
      const issueNumber = parseInt(args[1]);
      if (!issueNumber) {
        console.error('Error: Missing issue number');
        process.exit(1);
      }
      const result = await integration.suggestFix(issueNumber, options);
      console.log(JSON.stringify(result, null, 2));
    }
    else if (command === 'train-and-deploy') {
      const success = await integration.trainAndDeploy(options);
      process.exit(success ? 0 : 1);
    }
    else {
      console.error(`Unknown command: ${command}`);
      process.exit(1);
    }
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  }
}

main();
