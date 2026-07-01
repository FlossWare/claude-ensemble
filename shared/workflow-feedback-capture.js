/**
 * Workflow Feedback Capture System
 *
 * Automatically captures quality feedback from workflow executions
 * and stores it in workflow.feedback table for Thompson Sampling updates.
 *
 * Integration Points:
 * 1. fleet-workflow-wrapper.mjs complete() function
 * 2. adversarial-verification-harness.mjs verification results
 * 3. smart-consensus.js performance metrics
 * 4. quality-scorer.js quality calculations
 *
 * Database: workflow.feedback on aio-01:5433
 * Feedback Loop: feedback-loop-automation.js processes entries
 *
 * Created: 2026-07-01 (Issue #249)
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

// Import storage adapter (CJS)
const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');

/**
 * Workflow Feedback Capture Class
 */
export class WorkflowFeedbackCapture {
  constructor() {
    this.db = getWorkflowStorage();
  }

  /**
   * Capture automated feedback from workflow completion
   *
   * Called by: fleet-workflow-wrapper.mjs complete()
   *
   * @param {Object} params
   * @param {number} params.workflow_execution_id - Workflow execution ID
   * @param {number} params.quality_score - Quality score 0-1 (from complete())
   * @param {Object} params.metrics - Performance metrics (consensus, accuracy, etc.)
   * @param {string} params.outcome - 'success' | 'failed' | 'error'
   * @param {Object} params.metadata - Additional context
   * @returns {Promise<number>} Feedback ID
   */
  async captureWorkflowCompletion({
    workflow_execution_id,
    quality_score,
    metrics = {},
    outcome,
    metadata = {}
  }) {
    if (!workflow_execution_id) {
      console.warn('Cannot capture feedback: missing workflow_execution_id');
      return null;
    }

    // Convert quality score to 0-5 rating scale
    const rating = this._qualityScoreToRating(quality_score);

    // Generate automated feedback text
    const feedbackText = this._generateCompletionFeedback({
      quality_score,
      metrics,
      outcome,
      metadata
    });

    try {
      const feedbackId = await this.db.storeFeedback({
        workflow_execution_id,
        feedback_type: 'automated',
        quality_score,
        feedback_text: feedbackText,
        metadata: {
          rating, // 0-5 scale for Thompson Sampling
          source: 'workflow_completion',
          metrics,
          outcome,
          captured_at: new Date().toISOString(),
          ...metadata
        }
      });

      console.log(`✅ Automated feedback captured (ID: ${feedbackId}, rating: ${rating.toFixed(2)}/5.0)`);
      return feedbackId;

    } catch (error) {
      console.error(`Failed to capture workflow feedback: ${error.message}`);
      return null;
    }
  }

  /**
   * Capture adversarial verification feedback
   *
   * Called by: adversarial-verification-harness.mjs verifyAdversarially()
   *
   * @param {Object} params
   * @param {number} params.workflow_execution_id - Workflow execution ID
   * @param {Object} params.verificationResult - Adversarial verification result
   * @returns {Promise<number>} Feedback ID
   */
  async captureAdversarialVerification({
    workflow_execution_id,
    verificationResult
  }) {
    if (!workflow_execution_id) {
      console.warn('Cannot capture adversarial feedback: missing workflow_execution_id');
      return null;
    }

    const { verdict, confidence, refuters_failed, refuters_total, critical_issues, major_issues } = verificationResult;

    // Convert verdict to quality score
    const quality_score = this._verdictToQualityScore(verdict, confidence, critical_issues.length, major_issues.length);
    const rating = this._qualityScoreToRating(quality_score);

    // Generate feedback text
    const feedbackText = this._generateAdversarialFeedback(verificationResult);

    try {
      const feedbackId = await this.db.storeFeedback({
        workflow_execution_id,
        feedback_type: 'adversarial',
        quality_score,
        feedback_text: feedbackText,
        metadata: {
          rating,
          source: 'adversarial_verification',
          verdict,
          confidence,
          refuters_failed,
          refuters_total,
          critical_issues_count: critical_issues.length,
          major_issues_count: major_issues.length,
          captured_at: new Date().toISOString()
        }
      });

      console.log(`✅ Adversarial feedback captured (ID: ${feedbackId}, verdict: ${verdict}, rating: ${rating.toFixed(2)}/5.0)`);
      return feedbackId;

    } catch (error) {
      console.error(`Failed to capture adversarial feedback: ${error.message}`);
      return null;
    }
  }

  /**
   * Capture consensus performance feedback
   *
   * Called by: smart-consensus.js after arbiter decision
   *
   * @param {Object} params
   * @param {number} params.workflow_execution_id - Workflow execution ID
   * @param {Object} params.performance - Performance metrics from consensus
   * @param {Object} params.attribution - Attribution summary
   * @returns {Promise<number>} Feedback ID
   */
  async captureConsensusPerformance({
    workflow_execution_id,
    performance,
    attribution
  }) {
    if (!workflow_execution_id) {
      console.warn('Cannot capture consensus feedback: missing workflow_execution_id');
      return null;
    }

    const { consensus, accuracy, findings, precision } = performance;

    // Calculate quality score from consensus metrics
    const quality_score = (consensus * 0.4 + accuracy * 0.4 + precision * 0.2);
    const rating = this._qualityScoreToRating(quality_score);

    // Generate feedback text
    const feedbackText = this._generateConsensusFeedback({ performance, attribution });

    try {
      const feedbackId = await this.db.storeFeedback({
        workflow_execution_id,
        feedback_type: 'automated',
        quality_score,
        feedback_text: feedbackText,
        metadata: {
          rating,
          source: 'consensus_performance',
          consensus_rate: consensus,
          accuracy,
          findings_count: findings,
          precision,
          captured_at: new Date().toISOString()
        }
      });

      console.log(`✅ Consensus feedback captured (ID: ${feedbackId}, consensus: ${(consensus * 100).toFixed(0)}%, rating: ${rating.toFixed(2)}/5.0)`);
      return feedbackId;

    } catch (error) {
      console.error(`Failed to capture consensus feedback: ${error.message}`);
      return null;
    }
  }

  /**
   * Capture quality scoring feedback
   *
   * Called by: quality-scorer.js after quality calculation
   *
   * @param {Object} params
   * @param {number} params.workflow_execution_id - Workflow execution ID
   * @param {Object} params.qualityScore - Quality score breakdown
   * @returns {Promise<number>} Feedback ID
   */
  async captureQualityScore({
    workflow_execution_id,
    qualityScore
  }) {
    if (!workflow_execution_id) {
      console.warn('Cannot capture quality score feedback: missing workflow_execution_id');
      return null;
    }

    const { score, critical_count, high_count, medium_count, low_count, meets_threshold } = qualityScore;

    // Normalize score (0-100 → 0-1)
    const quality_score = score / 100;
    const rating = this._qualityScoreToRating(quality_score);

    // Generate feedback text
    const feedbackText = this._generateQualityScoreFeedback(qualityScore);

    try {
      const feedbackId = await this.db.storeFeedback({
        workflow_execution_id,
        feedback_type: 'automated',
        quality_score,
        feedback_text: feedbackText,
        metadata: {
          rating,
          source: 'quality_scorer',
          score,
          critical_count,
          high_count,
          medium_count,
          low_count,
          meets_threshold,
          captured_at: new Date().toISOString()
        }
      });

      console.log(`✅ Quality score feedback captured (ID: ${feedbackId}, score: ${score}/100, rating: ${rating.toFixed(2)}/5.0)`);
      return feedbackId;

    } catch (error) {
      console.error(`Failed to capture quality score feedback: ${error.message}`);
      return null;
    }
  }

  /**
   * Manual feedback capture (user/human review)
   *
   * @param {Object} params
   * @param {number} params.workflow_execution_id - Workflow execution ID
   * @param {number} params.rating - User rating 0-5
   * @param {string} params.feedback_text - User comments
   * @param {Object} params.metadata - Additional context
   * @returns {Promise<number>} Feedback ID
   */
  async captureUserFeedback({
    workflow_execution_id,
    rating,
    feedback_text,
    metadata = {}
  }) {
    if (!workflow_execution_id) {
      console.warn('Cannot capture user feedback: missing workflow_execution_id');
      return null;
    }

    if (rating < 0 || rating > 5) {
      throw new Error(`Invalid rating: ${rating} (must be 0-5)`);
    }

    // Convert rating to quality score
    const quality_score = rating / 5.0;

    try {
      const feedbackId = await this.db.storeFeedback({
        workflow_execution_id,
        feedback_type: 'user',
        quality_score,
        feedback_text,
        metadata: {
          rating,
          source: 'user_review',
          captured_at: new Date().toISOString(),
          ...metadata
        }
      });

      console.log(`✅ User feedback captured (ID: ${feedbackId}, rating: ${rating}/5.0)`);
      return feedbackId;

    } catch (error) {
      console.error(`Failed to capture user feedback: ${error.message}`);
      return null;
    }
  }

  /**
   * Convert quality score (0-1) to rating (0-5)
   * @private
   */
  _qualityScoreToRating(quality_score) {
    // Ensure quality_score is in valid range
    const clamped = Math.max(0, Math.min(1, quality_score || 0));
    return clamped * 5.0;
  }

  /**
   * Convert adversarial verdict to quality score
   * @private
   */
  _verdictToQualityScore(verdict, confidence, criticalCount, majorCount) {
    let baseScore = 0;

    switch (verdict) {
      case 'ACCEPT':
        baseScore = 0.9;
        break;
      case 'ACCEPT_WITH_CAVEATS':
        baseScore = 0.7;
        break;
      case 'REJECT':
        baseScore = 0.3;
        break;
      default:
        baseScore = 0.5;
    }

    // Adjust for confidence
    if (confidence === 'high') {
      baseScore *= 1.0;
    } else if (confidence === 'medium') {
      baseScore *= 0.9;
    } else if (confidence === 'low') {
      baseScore *= 0.8;
    }

    // Penalize critical/major issues
    const issuePenalty = (criticalCount * 0.2) + (majorCount * 0.1);
    baseScore = Math.max(0, baseScore - issuePenalty);

    return baseScore;
  }

  /**
   * Generate automated feedback text for workflow completion
   * @private
   */
  _generateCompletionFeedback({ quality_score, metrics, outcome, metadata }) {
    const parts = [`Workflow completed: ${outcome}`];

    if (quality_score !== undefined) {
      parts.push(`Quality score: ${(quality_score * 100).toFixed(0)}%`);
    }

    if (metrics.consensus !== undefined) {
      parts.push(`Consensus: ${(metrics.consensus * 100).toFixed(0)}%`);
    }

    if (metrics.accuracy !== undefined) {
      parts.push(`Accuracy: ${(metrics.accuracy * 100).toFixed(0)}%`);
    }

    if (metadata.workers_used) {
      parts.push(`Workers: ${metadata.workers_used}`);
    }

    return parts.join(', ');
  }

  /**
   * Generate feedback text for adversarial verification
   * @private
   */
  _generateAdversarialFeedback({ verdict, confidence, refuters_failed, refuters_total, critical_issues, major_issues }) {
    const parts = [
      `Adversarial verification: ${verdict}`,
      `Confidence: ${confidence}`,
      `Refuters failed to disprove: ${refuters_failed}/${refuters_total}`
    ];

    if (critical_issues.length > 0) {
      parts.push(`Critical issues: ${critical_issues.length}`);
    }

    if (major_issues.length > 0) {
      parts.push(`Major issues: ${major_issues.length}`);
    }

    return parts.join(', ');
  }

  /**
   * Generate feedback text for consensus performance
   * @private
   */
  _generateConsensusFeedback({ performance, attribution }) {
    const parts = [
      `Consensus performance: ${(performance.consensus * 100).toFixed(0)}% agreement`,
      `Accuracy: ${(performance.accuracy * 100).toFixed(0)}%`,
      `Findings: ${performance.findings}`,
      `Precision: ${(performance.precision * 100).toFixed(0)}%`
    ];

    if (attribution?.consensusRate !== undefined) {
      parts.push(`Attribution consensus: ${(attribution.consensusRate * 100).toFixed(0)}%`);
    }

    return parts.join(', ');
  }

  /**
   * Generate feedback text for quality scoring
   * @private
   */
  _generateQualityScoreFeedback({ score, critical_count, high_count, medium_count, low_count, meets_threshold }) {
    const parts = [
      `Quality score: ${score}/100`,
      `Critical: ${critical_count}`,
      `High: ${high_count}`,
      `Medium: ${medium_count}`,
      `Low: ${low_count}`,
      `Meets threshold: ${meets_threshold ? 'YES' : 'NO'}`
    ];

    return parts.join(', ');
  }

  // ============================================================================
  // EXPERIMENT INTEGRATION (Issue #267)
  // ============================================================================

  /**
   * Run A/B experiment comparing two quality scorers
   *
   * Tests baseline vs treatment quality scoring algorithm using ground truth data,
   * then promotes the winner if accuracy improves significantly.
   *
   * @param {Object} config
   * @param {Function} config.baselineScorer - Baseline scorer: (workflowResult) => score (0-1)
   * @param {Function} config.treatmentScorer - Treatment scorer: (workflowResult) => score (0-1)
   * @param {Array<Object>} config.testCases - Test cases with ground truth
   * @param {Object} config.testCases[].workflow_result - Workflow result to score
   * @param {number} config.testCases[].ground_truth - Ground truth quality (0-1)
   * @param {number} [config.minImprovementPct=3] - Min improvement % to promote
   * @returns {Promise<Object>} Experiment result with verdict
   *
   * Example:
   *   const result = await feedbackCapture.experimentQualityScorer({
   *     baselineScorer: currentScorer,
   *     treatmentScorer: newScorer,
   *     testCases: [
   *       { workflow_result: {...}, ground_truth: 0.85 },
   *       { workflow_result: {...}, ground_truth: 0.72 },
   *       ...
   *     ],
   *     minImprovementPct: 3
   *   });
   *
   *   if (result.verdict === 'keep') {
   *     console.log('✅ New quality scorer is more accurate');
   *   }
   */
  async experimentQualityScorer(config) {
    const {
      baselineScorer,
      treatmentScorer,
      testCases,
      minImprovementPct = 3
    } = config;

    if (!baselineScorer || typeof baselineScorer !== 'function') {
      throw new Error('baselineScorer must be a function: (workflowResult) => score');
    }

    if (!treatmentScorer || typeof treatmentScorer !== 'function') {
      throw new Error('treatmentScorer must be a function: (workflowResult) => score');
    }

    if (!Array.isArray(testCases) || testCases.length < 5) {
      throw new Error('testCases must be an array with at least 5 test cases');
    }

    // Import experiment manager (lazy load)
    const { createRequire } = await import('module');
    const require = createRequire(import.meta.url);
    const { runExperiment } = require('./experiment-manager.cjs');

    const collector = async (scorer) => {
      const accuracyScores = [];

      for (const testCase of testCases) {
        try {
          const predictedScore = scorer(testCase.workflow_result);
          const groundTruth = testCase.ground_truth;

          // Accuracy: how close is predicted to ground truth?
          // Use inverse of absolute error, normalized to [0, 1]
          const error = Math.abs(predictedScore - groundTruth);
          const accuracy = 1 - error; // 0 error = 1 accuracy, 1 error = 0 accuracy

          accuracyScores.push(accuracy);

        } catch (error) {
          console.error(`Error scoring test case:`, error.message);
          accuracyScores.push(0);
        }
      }

      return accuracyScores;
    };

    const result = await runExperiment({
      name: `quality_scorer_${Date.now()}`,
      hypothesis: 'New quality scorer correlates better with ground truth',
      metric: 'accuracy',
      baseline: baselineScorer,
      treatment: treatmentScorer,
      collector,
      success_criteria: {
        min_improvement_pct: minImprovementPct,
        alpha: 0.05,
        bootstrap_iterations: 1000
      },
      metadata: {
        experiment_type: 'quality_scorer_comparison',
        test_cases: testCases.length,
        integration: 'workflow-feedback-capture'
      }
    });

    // Log results
    if (result.verdict === 'keep') {
      console.log(`✅ [experimentQualityScorer] Treatment scorer is more accurate`);
      console.log(`   Improvement: ${result.improvement_pct.toFixed(2)}% (p=${result.p_value.toFixed(4)})`);
      console.log(`   Baseline accuracy: ${(result.baseline_mean * 100).toFixed(1)}%`);
      console.log(`   Treatment accuracy: ${(result.treatment_mean * 100).toFixed(1)}%`);
      console.log(`   Effect size: ${result.effect_size.toFixed(3)} (Cohen's d)`);
    } else if (result.verdict === 'remove') {
      console.log(`❌ [experimentQualityScorer] Treatment scorer is less accurate`);
      console.log(`   Regression: ${result.improvement_pct.toFixed(2)}% (p=${result.p_value.toFixed(4)})`);
    } else {
      console.log(`⚠️  [experimentQualityScorer] Inconclusive: ${result.reason}`);
    }

    return result;
  }
}

/**
 * Singleton instance
 */
let _feedbackCapture = null;

/**
 * Get singleton feedback capture instance
 */
export function getFeedbackCapture() {
  if (!_feedbackCapture) {
    _feedbackCapture = new WorkflowFeedbackCapture();
  }
  return _feedbackCapture;
}

/**
 * Convenience function: Capture workflow completion feedback
 */
export async function captureWorkflowFeedback(params) {
  const capture = getFeedbackCapture();
  return await capture.captureWorkflowCompletion(params);
}

/**
 * Convenience function: Capture adversarial verification feedback
 */
export async function captureAdversarialFeedback(params) {
  const capture = getFeedbackCapture();
  return await capture.captureAdversarialVerification(params);
}

/**
 * Convenience function: Capture consensus performance feedback
 */
export async function captureConsensusFeedback(params) {
  const capture = getFeedbackCapture();
  return await capture.captureConsensusPerformance(params);
}

/**
 * Convenience function: Capture quality score feedback
 */
export async function captureQualityFeedback(params) {
  const capture = getFeedbackCapture();
  return await capture.captureQualityScore(params);
}

/**
 * Convenience function: Capture user feedback
 */
export async function captureUserFeedback(params) {
  const capture = getFeedbackCapture();
  return await capture.captureUserFeedback(params);
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('Workflow Feedback Capture');
  console.log('='.repeat(80));
  console.log('');
  console.log('Usage:');
  console.log('  import { captureWorkflowFeedback } from "./workflow-feedback-capture.js";');
  console.log('');
  console.log('  await captureWorkflowFeedback({');
  console.log('    workflow_execution_id: 123,');
  console.log('    quality_score: 0.85,');
  console.log('    metrics: { consensus: 0.9, accuracy: 0.87 },');
  console.log('    outcome: "success"');
  console.log('  });');
  console.log('');
  console.log('See workflow.feedback table for captured data.');
}
