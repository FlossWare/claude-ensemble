/**
 * Batch Consensus Helper Functions
 *
 * Integration helpers for using batch-consensus with existing consensus patterns.
 * Created: 2026-07-01 (Issue #263)
 */

import { batchConsensusWithWorker } from './batch-consensus-wrapper.mjs';
import { multiModelReview, arbiterDecision } from './consensus-engine.js';

/**
 * Batch multi-model review for multiple files/prompts
 *
 * @param {Array<string>} prompts - Array of review prompts
 * @param {Object} schema - JSON schema for worker responses
 * @param {Object} options - Review options (passed to multiModelReview)
 * @returns {Promise<Array<Object>>} Array of review results
 *
 * Example:
 *   const filePrompts = files.map(f => `Review ${f.path}:\n${f.content}`);
 *   const reviews = await batchMultiModelReview(filePrompts, FINDING_SCHEMA, {
 *     workers: ['opus', 'sonnet', 'gpt-4o'],
 *     concurrency: 3
 *   });
 */
export async function batchMultiModelReview(prompts, schema, options = {}) {
  const {
    workers = ['sonnet', 'opus', 'haiku', 'gpt-4o', 'gemini', 'cerebras-120b'],
    concurrency = 5,
    onProgress = null,
    ...reviewOptions
  } = options;

  const reviewWorker = async (prompt) => {
    const reviews = await multiModelReview(prompt, schema, {
      workers,
      ...reviewOptions
    });

    // Return consensus result
    return {
      model: 'multi-model-review',
      models: reviews.allReviews.map(r => r?.model || 'unknown'),
      answer: reviews,
      confidence: calculateReviewConfidence(reviews),
      votes: reviews.allReviews
    };
  };

  return await batchConsensusWithWorker(prompts, reviewWorker, {
    concurrency,
    onProgress,
    onError: options.onError,
    stopOnError: options.stopOnError || false,
    timeout: options.timeout || 60000 // 60s per review
  });
}

/**
 * Batch arbiter decisions for multiple review sets
 *
 * @param {Array<Object>} reviewSets - Array of { context, reviews, decisionType }
 * @param {Object} options - Arbiter options
 * @returns {Promise<Array<Object>>} Array of arbiter decisions
 *
 * Example:
 *   const decisions = await batchArbiterDecisions(
 *     reviewSets.map(rs => ({
 *       context: rs.context,
 *       reviews: rs.reviews,
 *       decisionType: 'issue'
 *     })),
 *     { strategy: 'weighted', concurrency: 3 }
 *   );
 */
export async function batchArbiterDecisions(reviewSets, options = {}) {
  const {
    concurrency = 5,
    onProgress = null,
    ...arbiterOptions
  } = options;

  const arbiterWorker = async (reviewSet) => {
    const { context, reviews, decisionType = 'issue' } = reviewSet;

    const decision = await arbiterDecision(context, reviews, {
      decisionType,
      ...arbiterOptions
    });

    return {
      model: 'arbiter',
      models: [decision.arbiter],
      answer: decision,
      confidence: decision.consensus_score / 100,
      votes: []
    };
  };

  return await batchConsensusWithWorker(reviewSets, arbiterWorker, {
    concurrency,
    onProgress,
    timeout: options.timeout || 30000
  });
}

/**
 * Calculate review confidence from multi-model reviews
 * (Helper function used internally)
 */
function calculateReviewConfidence(reviews) {
  const allReviews = reviews.allReviews || [];
  if (allReviews.length === 0) return 0;

  const avgConfidence = allReviews.reduce((sum, r) => {
    const conf = r?.confidence || 0;
    return sum + conf;
  }, 0) / allReviews.length;

  return avgConfidence / 100; // Normalize to 0-1
}

/**
 * Process array of questions with consensus voting
 *
 * @param {Array<string>} questions - Array of questions
 * @param {Object} options - Worker configuration
 * @returns {Promise<Array<Object>>} Consensus results
 *
 * Example:
 *   const answers = await batchConsensusQuestions(
 *     ['What is 2+2?', 'What is the capital of France?'],
 *     {
 *       workers: ['opus', 'sonnet', 'haiku'],
 *       schema: { type: 'object', properties: { answer: { type: 'string' } } },
 *       concurrency: 5
 *     }
 *   );
 */
export async function batchConsensusQuestions(questions, options = {}) {
  const {
    workers = ['opus', 'sonnet', 'haiku'],
    schema,
    concurrency = 10,
    onProgress = null
  } = options;

  if (!schema) {
    throw new Error('schema is required for batchConsensusQuestions');
  }

  const questionWorker = async (question) => {
    // Run all workers in parallel
    const workerPromises = workers.map(model =>
      agent(question, { schema, model })
    );

    const workerResults = await Promise.all(workerPromises);

    // Simple majority vote
    const answerCounts = {};
    workerResults.forEach(result => {
      const answer = JSON.stringify(result);
      answerCounts[answer] = (answerCounts[answer] || 0) + 1;
    });

    const winner = Object.entries(answerCounts)
      .sort((a, b) => b[1] - a[1])[0];

    const winnerAnswer = JSON.parse(winner[0]);
    const winnerCount = winner[1];
    const confidence = winnerCount / workers.length;

    return {
      model: 'consensus-vote',
      models: workers,
      answer: winnerAnswer,
      confidence,
      votes: workerResults
    };
  };

  return await batchConsensusWithWorker(questions, questionWorker, {
    concurrency,
    onProgress,
    timeout: options.timeout || 30000
  });
}

/**
 * Helper: Merge findings from multiple reviews
 */
export function mergeFindings(reviews) {
  const allFindings = reviews.flatMap(r => r?.findings || []);

  // Deduplicate by file + line + title
  const uniqueFindings = [];
  const seen = new Set();

  allFindings.forEach(finding => {
    const key = `${finding.file}:${finding.line}:${finding.title}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniqueFindings.push(finding);
    }
  });

  // Sort by severity: critical > high > medium > low
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  uniqueFindings.sort((a, b) =>
    severityOrder[a.severity] - severityOrder[b.severity]
  );

  return uniqueFindings;
}
