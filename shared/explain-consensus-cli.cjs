#!/usr/bin/env node
/**
 * Consensus Explainability CLI
 *
 * Demonstrates explainability reporter with real or mock voting results.
 *
 * Usage:
 *   # Explain mock consensus decision
 *   node explain-consensus-cli.cjs --mock
 *
 *   # Explain from voting result JSON file
 *   node explain-consensus-cli.cjs --file /path/to/voting-result.json
 *
 *   # Explain from PostgreSQL workflow execution ID
 *   node explain-consensus-cli.cjs --workflow-id exec-12345
 *
 *   # Output formats
 *   node explain-consensus-cli.cjs --mock --format markdown
 *   node explain-consensus-cli.cjs --mock --format both --output /tmp/report
 *
 * Created: 2026-07-01
 * Issue: #266
 */

const fs = require('fs');
const path = require('path');
const { explain } = require('./explainability-reporter.cjs');

// ============================================================================
// CLI ARGUMENT PARSING
// ============================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    source: null,
    format: 'markdown',
    output: null,
    workflowId: null,
    file: null,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === '--mock') {
      options.source = 'mock';
    } else if (arg === '--file' && args[i + 1]) {
      options.source = 'file';
      options.file = args[++i];
    } else if (arg === '--workflow-id' && args[i + 1]) {
      options.source = 'workflow';
      options.workflowId = args[++i];
    } else if (arg === '--format' && args[i + 1]) {
      options.format = args[++i];
    } else if (arg === '--output' && args[i + 1]) {
      options.output = args[++i];
    } else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    }
  }

  if (!options.source) {
    console.error('ERROR: Must specify --mock, --file, or --workflow-id');
    printHelp();
    process.exit(1);
  }

  return options;
}

function printHelp() {
  console.log(`
Consensus Explainability CLI

Usage:
  node explain-consensus-cli.cjs [OPTIONS]

Sources:
  --mock                    Use mock voting result (demo)
  --file <path>             Load voting result from JSON file
  --workflow-id <id>        Load from PostgreSQL workflow execution ID

Options:
  --format <fmt>            Output format: 'json' | 'markdown' | 'both' (default: markdown)
  --output <path>           Write report to file (optional)
  --help, -h                Show this help

Examples:
  # Demo with mock data
  node explain-consensus-cli.cjs --mock

  # Explain from file
  node explain-consensus-cli.cjs --file /tmp/voting-result.json --format both

  # Explain from database
  node explain-consensus-cli.cjs --workflow-id exec-12345 --output /tmp/report.md
`);
}

// ============================================================================
// MOCK DATA
// ============================================================================

function getMockVotingResult() {
  return {
    status: 'success',
    algorithm: 'weighted_voting',
    task_type: 'architecture_design',
    bft_enabled: true,
    winner: {
      answer: {
        architecture: 'microservices',
        database: 'postgresql',
        rationale: 'Scalability and flexibility for independent service evolution',
      },
      total_weight: 3.75,
      vote_count: 4,
      consensus_strength: 0.78,
      consensus_level: 'strong',
      votes: [
        {
          model: 'opus',
          weight: 1.2,
          confidence: 0.92,
          tier_weight: 1.0,
          capability_score: 0.95,
          normalized_confidence: 0.92,
          historical_accuracy: 0.85,
          calibration_penalty: 1.0,
        },
        {
          model: 'gpt-4o',
          weight: 1.05,
          confidence: 0.88,
          tier_weight: 0.95,
          capability_score: 0.90,
          normalized_confidence: 0.88,
          historical_accuracy: 0.80,
          calibration_penalty: 0.95,
          calibration_reason: 'slight overconfidence (claimed 88%, actual 80%)',
        },
        {
          model: 'sonnet',
          weight: 0.95,
          confidence: 0.85,
          tier_weight: 0.9,
          capability_score: 0.88,
          normalized_confidence: 0.85,
          historical_accuracy: 0.82,
          calibration_penalty: 1.0,
        },
        {
          model: 'gemini',
          weight: 0.55,
          confidence: 0.72,
          tier_weight: 0.85,
          capability_score: 0.75,
          normalized_confidence: 0.72,
          historical_accuracy: 0.68,
          calibration_penalty: 0.85,
          calibration_reason: 'moderate overconfidence (claimed 72%, actual 68%)',
        },
      ],
    },
    all_groups: [
      {
        answer: {
          architecture: 'microservices',
          database: 'postgresql',
          rationale: 'Scalability and flexibility for independent service evolution',
        },
        total_weight: 3.75,
        vote_count: 4,
        percentage: 78.0,
      },
      {
        answer: {
          architecture: 'monolith',
          database: 'mysql',
          rationale: 'Simpler deployment and lower operational overhead',
        },
        total_weight: 1.05,
        vote_count: 2,
        percentage: 22.0,
      },
    ],
    bft_analysis: {
      outliers_detected: 1,
      threshold: 3.5,
      median: 0.85,
      mad: 0.08,
      outliers: [
        { model: 'haiku', confidence: 0.45, reason: 'MAD > 3.5 from median' },
      ],
    },
    metadata: {
      total_votes: 6,
      filtered_votes: 1,
      discarded_votes: 0,
    },
  };
}

// ============================================================================
// DATA LOADING
// ============================================================================

async function loadVotingResult(options) {
  if (options.source === 'mock') {
    console.log('Using mock voting result...\n');
    return getMockVotingResult();
  }

  if (options.source === 'file') {
    console.log(`Loading voting result from ${options.file}...\n`);
    const data = fs.readFileSync(options.file, 'utf8');
    return JSON.parse(data);
  }

  if (options.source === 'workflow') {
    console.log(`Loading voting result from workflow ${options.workflowId}...\n`);
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Query voting result from workflow execution
    const result = await db.pool.query(
      `SELECT voting_result FROM workflow.weighted_votes
       WHERE workflow_execution_id = $1
       ORDER BY created_at DESC LIMIT 1`,
      [options.workflowId]
    );

    if (result.rows.length === 0) {
      throw new Error(`No voting result found for workflow ${options.workflowId}`);
    }

    return result.rows[0].voting_result;
  }

  throw new Error('Invalid source: ' + options.source);
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const options = parseArgs();

  try {
    // Load voting result
    const votingResult = await loadVotingResult(options);

    // Generate explainability report
    const result = await explain(votingResult, {
      format: options.format,
      outputPath: options.output,
    });

    // Print report to console (unless writing to file)
    if (!options.output) {
      if (options.format === 'markdown' || options.format === 'both') {
        console.log(result.markdown);
      } else {
        console.log(result.json);
      }
    } else {
      console.log(`✓ Explainability report written to ${result.file_path}`);
    }

    // Print summary stats
    console.log('\n' + '='.repeat(70));
    console.log('SUMMARY STATISTICS');
    console.log('='.repeat(70));
    console.log(`Winning Answer: ${JSON.stringify(result.report.summary.winning_answer).substring(0, 60)}...`);
    console.log(`Consensus Level: ${result.report.summary.consensus_level}`);
    console.log(`Consensus Strength: ${result.report.summary.consensus_strength}`);
    console.log(`Total Weight: ${result.report.summary.total_weight}`);
    console.log(`Supporting Votes: ${result.report.summary.vote_count}`);
    console.log(`Consensus Type: ${result.report.agreement_analysis.consensus_type}`);
    console.log(`Calibration Penalties: ${result.report.calibration_adjustments.num_models_penalized} models`);
    console.log('='.repeat(70));

  } catch (err) {
    console.error('ERROR:', err.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { parseArgs, getMockVotingResult, loadVotingResult };
