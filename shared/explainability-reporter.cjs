/**
 * Explainability Reporter for Multi-AI Consensus
 *
 * Shows why a specific model won consensus by breaking down:
 * 1. Weight components (tier × capability × confidence × history × calibration)
 * 2. Agreement/disagreement analysis
 * 3. Calibration adjustments applied
 * 4. Winner selection rationale (highest weight, MAD outliers excluded, etc.)
 *
 * Output formats:
 *   - Markdown (human-readable)
 *   - JSON (machine-readable)
 *
 * Integration:
 *   - Called by weighted-voting.cjs with optional --explain flag
 *   - Used in workflows to audit consensus decisions
 *   - Stored in PostgreSQL for long-term analysis
 *
 * Created: 2026-06-28
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// WEIGHT BREAKDOWN ANALYSIS
// ============================================================================

/**
 * Generate detailed weight breakdown for each vote
 *
 * Shows how final weight was calculated from component multipliers.
 *
 * @param {Object} vote - Vote object with weight components
 * @returns {Object} Weight breakdown
 */
function generateWeightBreakdown(vote) {
  const tierWeight = vote.tier_weight || 0;
  const capability = vote.capability_score || 0;
  const confidence = vote.normalized_confidence || 0;
  const history = vote.historical_accuracy || 0.5;
  const calibration = vote.calibration_penalty || 1.0;

  // Calculate intermediate steps
  const beforeCalibration = tierWeight * capability * confidence * history;
  const finalWeight = beforeCalibration * calibration;

  return {
    model: vote.model,
    components: {
      tier_weight: {
        value: tierWeight,
        description: 'Base model capability (opus=1.0, haiku=0.6)',
      },
      capability_score: {
        value: capability,
        description: 'Task-specific strength (0.0-1.0)',
      },
      confidence: {
        value: confidence,
        description: 'Model self-reported confidence (0.0-1.0)',
      },
      historical_accuracy: {
        value: history,
        description: 'Thompson Sampling avg quality (0.0-1.0)',
      },
      calibration_penalty: {
        value: calibration,
        description: 'Penalty for confidence/accuracy mismatch (0.25-1.0)',
        reason: vote.calibration_reason || 'unknown',
      },
    },
    calculation: {
      formula: 'tier × capability × confidence × history × calibration',
      before_calibration: beforeCalibration,
      after_calibration: finalWeight,
      calibration_impact: calibration < 1.0 ? `${((1 - calibration) * 100).toFixed(0)}% weight reduction` : 'no penalty',
    },
    final_weight: finalWeight,
  };
}

/**
 * Generate weight breakdown for all votes
 *
 * @param {Array<Object>} votes - All votes from voting result
 * @returns {Array<Object>} Breakdown for each vote
 */
function generateAllWeightBreakdowns(votes) {
  return votes.map(generateWeightBreakdown);
}

// ============================================================================
// AGREEMENT/DISAGREEMENT ANALYSIS
// ============================================================================

/**
 * Analyze which models agreed and disagreed
 *
 * Groups models by answer and identifies:
 *   - Majority coalition (agreed with winner)
 *   - Minority dissent (voted differently)
 *   - Strength of each coalition
 *
 * @param {Object} votingResult - Result from weighted voting
 * @returns {Object} Agreement analysis
 */
function analyzeAgreement(votingResult) {
  if (!votingResult.all_groups || votingResult.all_groups.length === 0) {
    return {
      consensus_type: 'unknown',
      majority: [],
      minorities: [],
    };
  }

  const winner = votingResult.winner;
  const allGroups = votingResult.all_groups;

  // Extract models by answer group
  const majority = {
    answer: winner.answer,
    total_weight: winner.total_weight,
    vote_count: winner.vote_count,
    percentage: (winner.consensus_strength * 100).toFixed(1),
    models: winner.votes.map(v => ({
      model: v.model,
      weight: v.weight,
      confidence: v.confidence,
    })),
  };

  const minorities = allGroups.slice(1).map(group => ({
    answer: group.answer,
    total_weight: group.total_weight,
    vote_count: group.vote_count,
    percentage: group.percentage,
    // Note: Full vote details not in all_groups, would need to reconstruct
  }));

  // Determine consensus type
  let consensusType;
  const strength = winner.consensus_strength;

  if (strength === 1.0) {
    consensusType = 'unanimous';
  } else if (strength >= 0.80) {
    consensusType = 'strong_majority';
  } else if (strength >= 0.60) {
    consensusType = 'moderate_majority';
  } else if (strength >= 0.40) {
    consensusType = 'weak_majority';
  } else {
    consensusType = 'plurality';
  }

  return {
    consensus_type: consensusType,
    majority,
    minorities,
    num_unique_answers: allGroups.length,
  };
}

// ============================================================================
// WINNER SELECTION RATIONALE
// ============================================================================

/**
 * Explain why the winner was selected
 *
 * Covers:
 *   - Voting algorithm used (weighted-average, median, mad, etc.)
 *   - Tie-breaking rules applied (if any)
 *   - BFT outliers excluded (if MAD enabled)
 *   - Sybil attack protection (if vote flooding detected)
 *   - Edge cases handled (if any)
 *
 * @param {Object} votingResult - Result from weighted voting
 * @param {Object} options - Options used in voting
 * @returns {Object} Selection rationale
 */
function explainWinnerSelection(votingResult, options = {}) {
  const rationale = {
    algorithm: votingResult.algorithm || 'weighted_voting',
    strategy: options.strategy || 'weighted-average',
    reasons: [],
  };

  // Primary reason: highest weight
  if (votingResult.winner) {
    rationale.reasons.push({
      type: 'highest_total_weight',
      description: `Winner had highest total weight: ${votingResult.winner.total_weight.toFixed(3)}`,
      votes_supporting: votingResult.winner.vote_count,
    });
  }

  // Tie-breaking (if runner-up close)
  if (votingResult.runner_up) {
    const weightDiff = votingResult.runner_up.weight_difference;
    const margin = (weightDiff / votingResult.winner.total_weight * 100).toFixed(1);

    if (parseFloat(margin) < 5.0) {
      rationale.reasons.push({
        type: 'narrow_margin',
        description: `Close race: margin of ${margin}% over runner-up`,
        warning: 'Consider arbiter review for close decisions',
      });
    }
  }

  // BFT outlier filtering (if MAD enabled)
  if (votingResult.bft_analysis) {
    const bft = votingResult.bft_analysis;

    if (bft.outliers_detected > 0) {
      rationale.reasons.push({
        type: 'bft_outlier_filtering',
        description: `${bft.outliers_detected} outliers excluded via MAD (Median Absolute Deviation)`,
        mad_threshold: bft.threshold,
        median_confidence: bft.median,
        mad_value: bft.mad,
        outliers: bft.outliers,
      });
    }

    if (bft.warning === 'high_disagreement') {
      rationale.reasons.push({
        type: 'high_disagreement_protected',
        description: 'High disagreement detected - minority opinions protected from outlier suppression',
        disagreement_percentage: bft.disagreement_percentage,
      });
    }
  }

  // Sybil attack protection (if vote flooding detected)
  if (votingResult.sybil_analysis) {
    const sybil = votingResult.sybil_analysis;

    if (sybil.detected) {
      rationale.reasons.push({
        type: 'sybil_attack_protection',
        description: `Vote flooding detected: ${sybil.count}/${sybil.total} votes from '${sybil.family}' family`,
        action_taken: sybil.action_taken,
        votes_before: sybil.votes_before,
        votes_after: sybil.votes_after,
        votes_dropped: sybil.votes_dropped,
      });
    }
  }

  // Edge cases
  if (votingResult.tie_detected) {
    rationale.reasons.push({
      type: 'tie_detected',
      description: `Top 2 answers within ${votingResult.tie_margin} weight difference`,
      recommendation: 'Require arbiter review',
    });
  }

  if (votingResult.edge_case_warning) {
    rationale.reasons.push({
      type: 'edge_case',
      description: votingResult.edge_case_warning,
    });
  }

  return rationale;
}

// ============================================================================
// EXPLAINABILITY REPORT GENERATION
// ============================================================================

/**
 * Generate comprehensive explainability report
 *
 * Combines:
 *   - Weight breakdown per model
 *   - Agreement/disagreement analysis
 *   - Calibration adjustments
 *   - Winner selection rationale
 *
 * @param {Object} votingResult - Result from weighted voting
 * @param {Object} options - Options used in voting
 * @returns {Object} Complete explainability report
 */
function generateReport(votingResult, options = {}) {
  if (!votingResult || votingResult.status !== 'success') {
    return {
      status: 'error',
      error: 'voting_failed',
      message: votingResult?.message || 'No voting result available',
    };
  }

  const winner = votingResult.winner;

  return {
    status: 'success',
    summary: {
      winning_answer: winner.answer,
      consensus_level: winner.consensus_level,
      consensus_strength: (winner.consensus_strength * 100).toFixed(1) + '%',
      total_weight: winner.total_weight.toFixed(3),
      vote_count: winner.vote_count,
    },

    weight_breakdown: {
      winner_votes: generateAllWeightBreakdowns(winner.votes),
      total_weight_calculation: {
        formula: 'sum(tier × capability × confidence × history × calibration)',
        total: winner.total_weight.toFixed(3),
      },
    },

    agreement_analysis: analyzeAgreement(votingResult),

    calibration_adjustments: {
      description: 'Penalties applied for confidence/accuracy mismatch',
      penalties_applied: winner.votes.filter(v => v.calibration_penalty < 1.0).map(v => ({
        model: v.model,
        penalty: v.calibration_penalty,
        reason: v.calibration_reason,
        impact: `${((1 - v.calibration_penalty) * 100).toFixed(0)}% weight reduction`,
      })),
      num_models_penalized: winner.votes.filter(v => v.calibration_penalty < 1.0).length,
    },

    winner_selection: explainWinnerSelection(votingResult, options),

    metadata: {
      algorithm: votingResult.algorithm,
      task_type: votingResult.task_type,
      bft_enabled: votingResult.bft_enabled || false,
      total_votes: votingResult.metadata?.total_votes || 0,
      filtered_votes: votingResult.metadata?.filtered_votes || 0,
      discarded_votes: votingResult.metadata?.discarded_votes || 0,
    },
  };
}

// ============================================================================
// OUTPUT FORMATTING
// ============================================================================

/**
 * Format report as Markdown
 *
 * @param {Object} report - Explainability report
 * @returns {string} Markdown-formatted report
 */
function formatAsMarkdown(report) {
  if (report.status !== 'success') {
    return `# Explainability Report: ERROR\n\n${report.message || 'Unknown error'}`;
  }

  const md = [];

  // Header
  md.push('# Multi-AI Consensus Explainability Report');
  md.push('');

  // Summary
  md.push('## Summary');
  md.push('');
  md.push(`- **Winning Answer:** \`${JSON.stringify(report.summary.winning_answer)}\``);
  md.push(`- **Consensus Level:** ${report.summary.consensus_level} (${report.summary.consensus_strength})`);
  md.push(`- **Total Weight:** ${report.summary.total_weight}`);
  md.push(`- **Supporting Votes:** ${report.summary.vote_count}`);
  md.push('');

  // Agreement Analysis
  md.push('## Agreement Analysis');
  md.push('');
  md.push(`**Consensus Type:** ${report.agreement_analysis.consensus_type}`);
  md.push('');

  const majority = report.agreement_analysis.majority;
  md.push(`### Majority Coalition (${majority.percentage}%)`);
  md.push('');
  md.push('| Model | Weight | Confidence |');
  md.push('|-------|--------|------------|');
  majority.models.forEach(m => {
    md.push(`| ${m.model} | ${m.weight.toFixed(3)} | ${(m.confidence * 100).toFixed(0)}% |`);
  });
  md.push('');

  if (report.agreement_analysis.minorities.length > 0) {
    md.push('### Minority Opinions');
    md.push('');
    report.agreement_analysis.minorities.forEach((minority, idx) => {
      md.push(`**Alternative ${idx + 1}** (${minority.percentage}% weight):`);
      md.push(`- Answer: \`${JSON.stringify(minority.answer)}\``);
      md.push(`- Vote count: ${minority.vote_count}`);
      md.push('');
    });
  }

  // Weight Breakdown
  md.push('## Weight Breakdown');
  md.push('');
  md.push('**Formula:** `tier × capability × confidence × history × calibration`');
  md.push('');

  report.weight_breakdown.winner_votes.forEach((vote, idx) => {
    md.push(`### ${idx + 1}. ${vote.model}`);
    md.push('');
    md.push('| Component | Value | Description |');
    md.push('|-----------|-------|-------------|');

    Object.entries(vote.components).forEach(([key, comp]) => {
      md.push(`| ${key} | ${comp.value.toFixed(3)} | ${comp.description} |`);
    });

    md.push('');
    md.push(`**Calculation:**`);
    md.push(`- Before calibration: ${vote.calculation.before_calibration.toFixed(4)}`);
    md.push(`- After calibration: ${vote.calculation.after_calibration.toFixed(4)}`);
    md.push(`- Impact: ${vote.calculation.calibration_impact}`);
    md.push('');
  });

  // Calibration Adjustments
  if (report.calibration_adjustments.num_models_penalized > 0) {
    md.push('## Calibration Adjustments');
    md.push('');
    md.push(`**Models Penalized:** ${report.calibration_adjustments.num_models_penalized}`);
    md.push('');
    md.push('| Model | Penalty | Reason | Impact |');
    md.push('|-------|---------|--------|--------|');

    report.calibration_adjustments.penalties_applied.forEach(p => {
      md.push(`| ${p.model} | ${p.penalty.toFixed(2)}× | ${p.reason} | ${p.impact} |`);
    });
    md.push('');
  } else {
    md.push('## Calibration Adjustments');
    md.push('');
    md.push('✓ No penalties applied - all models well-calibrated');
    md.push('');
  }

  // Winner Selection Rationale
  md.push('## Winner Selection Rationale');
  md.push('');
  md.push(`**Algorithm:** ${report.winner_selection.algorithm}`);
  md.push(`**Strategy:** ${report.winner_selection.strategy}`);
  md.push('');

  report.winner_selection.reasons.forEach((reason, idx) => {
    md.push(`### ${idx + 1}. ${reason.type.replace(/_/g, ' ').toUpperCase()}`);
    md.push('');
    md.push(reason.description);

    if (reason.warning) {
      md.push('');
      md.push(`⚠️ **Warning:** ${reason.warning}`);
    }

    if (reason.type === 'bft_outlier_filtering') {
      md.push('');
      md.push(`- MAD threshold: ${reason.mad_threshold}`);
      md.push(`- Median confidence: ${(reason.median_confidence * 100).toFixed(0)}%`);
      md.push(`- MAD value: ${reason.mad_value.toFixed(3)}`);
      md.push(`- Outliers excluded: ${reason.outliers.length}`);
    }

    if (reason.type === 'sybil_attack_protection') {
      md.push('');
      md.push(`- Votes before: ${reason.votes_before}`);
      md.push(`- Votes after: ${reason.votes_after}`);
      md.push(`- Votes dropped: ${reason.votes_dropped}`);
    }

    md.push('');
  });

  // Metadata
  md.push('## Metadata');
  md.push('');
  md.push(`- Task type: ${report.metadata.task_type}`);
  md.push(`- Total votes: ${report.metadata.total_votes}`);
  md.push(`- Filtered votes: ${report.metadata.filtered_votes}`);
  md.push(`- Discarded votes: ${report.metadata.discarded_votes}`);
  md.push(`- BFT enabled: ${report.metadata.bft_enabled ? 'Yes' : 'No'}`);
  md.push('');

  return md.join('\n');
}

/**
 * Format report as JSON
 *
 * @param {Object} report - Explainability report
 * @returns {string} JSON-formatted report
 */
function formatAsJSON(report) {
  return JSON.stringify(report, null, 2);
}

// ============================================================================
// STORAGE
// ============================================================================

/**
 * Store explainability report in PostgreSQL
 *
 * Schema:
 *   CREATE TABLE workflow.explainability_reports (
 *     id SERIAL PRIMARY KEY,
 *     workflow_execution_id TEXT NOT NULL,
 *     voting_result_id INTEGER REFERENCES workflow.weighted_votes(id),
 *     report JSONB NOT NULL,
 *     format TEXT DEFAULT 'json',
 *     created_at TIMESTAMP DEFAULT NOW()
 *   );
 *
 * @param {Object} report - Explainability report
 * @param {string} workflowExecutionId - Workflow execution ID
 * @param {number} votingResultId - Foreign key to weighted_votes table (optional)
 * @returns {Promise<void>}
 */
async function storeReport(report, workflowExecutionId, votingResultId = null) {
  try {
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();

    // Create table if not exists (idempotent)
    await db.pool.query(`
      CREATE TABLE IF NOT EXISTS workflow.explainability_reports (
        id SERIAL PRIMARY KEY,
        workflow_execution_id TEXT NOT NULL,
        voting_result_id INTEGER,
        report JSONB NOT NULL,
        format TEXT DEFAULT 'json',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // Insert report
    await db.pool.query(`
      INSERT INTO workflow.explainability_reports
      (workflow_execution_id, voting_result_id, report, format)
      VALUES ($1, $2, $3, $4)
    `, [
      workflowExecutionId,
      votingResultId,
      JSON.stringify(report),
      'json',
    ]);

    console.log(`✓ Explainability report stored (execution: ${workflowExecutionId})`);
  } catch (err) {
    console.warn(`[explainability-reporter] Could not store report: ${err.message}`);
    // Non-fatal - continue workflow
  }
}

// ============================================================================
// HIGH-LEVEL API
// ============================================================================

/**
 * Generate and optionally store explainability report
 *
 * @param {Object} votingResult - Result from weighted voting
 * @param {Object} options - Options
 * @param {string} options.format - Output format: 'json', 'markdown', 'both' (default: 'json')
 * @param {string} options.outputPath - Optional file path to write report
 * @param {string} options.workflowExecutionId - Workflow ID for PostgreSQL storage
 * @param {number} options.votingResultId - Foreign key to weighted_votes table
 * @param {Object} options.votingOptions - Original voting options (for context)
 * @returns {Promise<Object>} { report, markdown?, json?, file_path? }
 */
async function explain(votingResult, options = {}) {
  const format = options.format || 'json';
  const report = generateReport(votingResult, options.votingOptions || {});

  const result = {
    report,
  };

  // Generate formatted outputs
  if (format === 'json' || format === 'both') {
    result.json = formatAsJSON(report);
  }

  if (format === 'markdown' || format === 'both') {
    result.markdown = formatAsMarkdown(report);
  }

  // Write to file if requested
  if (options.outputPath) {
    const content = format === 'markdown' ? result.markdown : result.json;
    const ext = format === 'markdown' ? '.md' : '.json';
    const filePath = options.outputPath.endsWith(ext) ? options.outputPath : options.outputPath + ext;

    fs.writeFileSync(filePath, content);
    result.file_path = filePath;
    console.log(`✓ Explainability report written to ${filePath}`);
  }

  // Store in PostgreSQL if workflow ID provided
  if (options.workflowExecutionId) {
    await storeReport(report, options.workflowExecutionId, options.votingResultId);
  }

  return result;
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // High-level API
  explain,

  // Report generation
  generateReport,

  // Individual analyzers
  generateWeightBreakdown,
  generateAllWeightBreakdowns,
  analyzeAgreement,
  explainWinnerSelection,

  // Formatting
  formatAsMarkdown,
  formatAsJSON,

  // Storage
  storeReport,
};
