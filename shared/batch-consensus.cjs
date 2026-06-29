/**
 * Batch Processing API for Multi-AI Consensus
 *
 * Process arrays of questions/tasks using consensus mechanisms with:
 * - Parallel execution (up to 10 concurrent by default)
 * - Progress tracking via callbacks
 * - Graceful error handling (partial results returned)
 * - Integration with weighted voting and consensus cache
 * - Memory-efficient batching for large datasets
 *
 * Example Usage:
 *   const results = await batchConsensus(questions, {
 *     concurrency: 10,
 *     onProgress: (completed, total) => console.log(`${completed}/${total}`),
 *     taskType: 'research',
 *     workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
 *   });
 *
 * Created: 2026-06-28
 */

const { weightedVoting } = require('./weighted-voting.cjs');
const { lookupCache, storeCache } = require('./consensus-cache.cjs');

// ============================================================================
// CONFIGURATION
// ============================================================================

const DEFAULT_OPTIONS = {
  concurrency: 10,           // Max parallel operations
  taskType: 'general',       // Task type for capability weighting
  workers: ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'],
  minAgreement: 0.6,         // Min agreement threshold (0.0-1.0)
  useCache: true,            // Enable consensus cache
  onProgress: null,          // Progress callback: (completed, total, current) => void
  onError: null,             // Error callback: (error, question, index) => void
  stopOnError: false,        // Stop entire batch on first error
  retryFailed: false,        // Retry failed items once
  timeout: 30000,            // Per-item timeout (ms)
};

// ============================================================================
// BATCH PROCESSING
// ============================================================================

/**
 * Process array of questions/tasks with consensus voting.
 *
 * @param {Array<string>} questions - Array of questions or prompts
 * @param {Object} options - Configuration options
 * @returns {Promise<Array<Object>>} Array of results
 */
async function batchConsensus(questions, options = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  if (!Array.isArray(questions)) {
    throw new TypeError('questions must be an array');
  }

  if (questions.length === 0) {
    return [];
  }

  const useCache = opts.useCache;
  const results = new Array(questions.length).fill(null);
  const errors = [];

  // Process in chunks to limit concurrency
  const chunks = createChunks(questions, opts.concurrency);
  let completed = 0;

  for (const chunk of chunks) {
    const chunkPromises = chunk.map(({ question, index }) =>
      processQuestion(question, index, opts, useCache)
        .then(result => {
          results[index] = result;
          completed++;
          if (opts.onProgress) {
            opts.onProgress(completed, questions.length, result);
          }
          return result;
        })
        .catch(error => {
          const errorObj = {
            index,
            question,
            error: error.message,
            timestamp: new Date().toISOString(),
          };
          errors.push(errorObj);

          if (opts.onError) {
            opts.onError(error, question, index);
          }

          if (opts.stopOnError) {
            throw error;
          }

          // Return error marker instead of null
          results[index] = {
            question,
            error: error.message,
            confidence: 0,
            agreement: 0,
            outcome: 'error',
          };
          completed++;
          if (opts.onProgress) {
            opts.onProgress(completed, questions.length, results[index]);
          }
          return results[index];
        })
    );

    await Promise.all(chunkPromises);
  }

  // Retry failed items if requested
  if (opts.retryFailed && errors.length > 0) {
    const retryIndices = errors.map(e => e.index);
    const retryResults = await retryFailed(
      questions,
      retryIndices,
      opts,
      useCache,
      completed,
      questions.length
    );

    retryResults.forEach((result, i) => {
      const originalIndex = retryIndices[i];
      results[originalIndex] = result;
    });
  }

  return results;
}

/**
 * Process a single question with consensus voting.
 */
async function processQuestion(question, index, opts, useCache) {
  // Check cache first
  if (useCache) {
    try {
      const cached = await lookupCache(question, opts.taskType);
      if (cached && cached.result) {
        return {
          question,
          answer: cached.result.winner,
          confidence: cached.result.confidence,
          agreement: cached.result.agreement,
          votes: cached.result.votes,
          models: cached.result.models || opts.workers,
          cached: true,
          timestamp: new Date().toISOString(),
        };
      }
    } catch (cacheError) {
      // Cache lookup failed, continue without cache
      console.warn(`[batch-consensus] Cache lookup failed: ${cacheError.message}`);
    }
  }

  // Execute with timeout
  const timeoutPromise = new Promise((_, reject) =>
    setTimeout(() => reject(new Error('Timeout')), opts.timeout)
  );

  const consensusPromise = getConsensus(question, opts);

  const result = await Promise.race([consensusPromise, timeoutPromise]);

  // Store in cache
  if (useCache && result.outcome === 'success') {
    try {
      await storeCache(question, opts.taskType, {
        winner: result.answer,
        confidence: result.confidence,
        agreement: result.agreement,
        votes: result.votes,
        models: result.models,
        weights: result.weights,
      });
    } catch (cacheError) {
      // Cache store failed, continue without cache
      console.warn(`[batch-consensus] Cache store failed: ${cacheError.message}`);
    }
  }

  return {
    ...result,
    question,
    cached: false,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Get consensus for a single question.
 */
async function getConsensus(question, opts) {
  // Simulate worker responses (in production, call actual models)
  const workerPromises = opts.workers.map(async (model) => {
    // This would call actual model APIs in production
    // For now, simulate with placeholder
    return simulateWorkerResponse(question, model, opts.taskType);
  });

  const workerResults = await Promise.all(workerPromises);

  // Use weighted voting
  const voteResult = await weightedVoting(
    workerResults,
    opts.taskType,
    {
      minConfidence: opts.minAgreement,
      strategy: 'weighted-average',
    }
  );

  // Handle voting result
  if (voteResult.status === 'error') {
    throw new Error(voteResult.message || voteResult.error);
  }

  // Extract winner from result
  const winner = voteResult.winner?.answer || voteResult.winner?.value || 'Unknown';
  const confidence = voteResult.winner?.confidence || 0;
  const consensusLevel = voteResult.winner?.consensus_level || 'unknown';

  // Calculate agreement from vote counts
  const totalVotes = Object.values(voteResult.winner?.votes || {}).reduce((a, b) => a + b, 0);
  const winnerVotes = voteResult.winner?.vote_count || 0;
  const agreement = totalVotes > 0 ? winnerVotes / totalVotes : 0;

  return {
    answer: winner,
    confidence,
    agreement,
    votes: voteResult.winner?.votes || {},
    models: opts.workers,
    weights: voteResult.vote_weights || {},
    consensusLevel,
    outcome: agreement >= opts.minAgreement ? 'success' : 'low_agreement',
  };
}

/**
 * Simulate worker response (placeholder for actual model calls).
 * In production, this would call real model APIs.
 */
async function simulateWorkerResponse(question, model, taskType) {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, Math.random() * 100));

  // Simulate response with varying confidence
  const answers = ['Answer A', 'Answer B', 'Answer C'];
  const answer = answers[Math.floor(Math.random() * answers.length)];
  const confidence = 0.5 + Math.random() * 0.5; // 0.5-1.0

  return {
    model,
    answer,
    confidence,
    reasoning: `${model} analysis of: ${question}`,
  };
}

/**
 * Retry failed questions.
 */
async function retryFailed(questions, indices, opts, useCache, baseCompleted, total) {
  const retryQuestions = indices.map(i => questions[i]);
  const results = [];

  for (let i = 0; i < retryQuestions.length; i++) {
    try {
      const result = await processQuestion(
        retryQuestions[i],
        indices[i],
        opts,
        useCache
      );
      results.push(result);

      if (opts.onProgress) {
        opts.onProgress(
          baseCompleted + i + 1,
          total,
          result
        );
      }
    } catch (error) {
      results.push({
        question: retryQuestions[i],
        error: error.message,
        confidence: 0,
        agreement: 0,
        outcome: 'error',
      });
    }
  }

  return results;
}

/**
 * Create chunks from array with indices.
 */
function createChunks(array, chunkSize) {
  const chunks = [];
  for (let i = 0; i < array.length; i += chunkSize) {
    const chunk = array.slice(i, i + chunkSize).map((item, idx) => ({
      question: item,
      index: i + idx,
    }));
    chunks.push(chunk);
  }
  return chunks;
}

// ============================================================================
// STREAMING API
// ============================================================================

/**
 * Process questions as a stream for very large datasets.
 * Yields results as they complete.
 *
 * @param {Array<string>} questions - Array of questions
 * @param {Object} options - Configuration options
 * @yields {Object} Individual results as they complete
 */
async function* batchConsensusStream(questions, options = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const useCache = opts.useCache;

  const chunks = createChunks(questions, opts.concurrency);

  for (const chunk of chunks) {
    const chunkPromises = chunk.map(({ question, index }) =>
      processQuestion(question, index, opts, useCache)
        .catch(error => ({
          question,
          error: error.message,
          confidence: 0,
          agreement: 0,
          outcome: 'error',
        }))
    );

    const results = await Promise.all(chunkPromises);

    for (const result of results) {
      yield result;
    }
  }
}

// ============================================================================
// STATISTICS & REPORTING
// ============================================================================

/**
 * Analyze batch results and return statistics.
 */
function analyzeBatchResults(results) {
  const total = results.length;
  const successful = results.filter(r => r.outcome === 'success').length;
  const errors = results.filter(r => r.outcome === 'error').length;
  const lowAgreement = results.filter(r => r.outcome === 'low_agreement').length;
  const cached = results.filter(r => r.cached).length;

  const avgConfidence = results
    .filter(r => r.confidence)
    .reduce((sum, r) => sum + r.confidence, 0) / total;

  const avgAgreement = results
    .filter(r => r.agreement)
    .reduce((sum, r) => sum + r.agreement, 0) / total;

  return {
    total,
    successful,
    errors,
    lowAgreement,
    cached,
    cacheHitRate: cached / total,
    successRate: successful / total,
    avgConfidence: avgConfidence || 0,
    avgAgreement: avgAgreement || 0,
  };
}

/**
 * Generate a report from batch results.
 */
function generateBatchReport(results, options = {}) {
  const stats = analyzeBatchResults(results);
  const includeDetails = options.includeDetails !== false;

  let report = `
Batch Consensus Report
=====================
Total Questions: ${stats.total}
Successful: ${stats.successful} (${(stats.successRate * 100).toFixed(1)}%)
Errors: ${stats.errors}
Low Agreement: ${stats.lowAgreement}
Cache Hits: ${stats.cached} (${(stats.cacheHitRate * 100).toFixed(1)}%)

Average Confidence: ${(stats.avgConfidence * 100).toFixed(1)}%
Average Agreement: ${(stats.avgAgreement * 100).toFixed(1)}%
`;

  if (includeDetails) {
    report += '\n\nFailed Questions:\n';
    results
      .filter(r => r.outcome === 'error')
      .forEach((r, i) => {
        report += `  ${i + 1}. ${r.question}\n`;
        report += `     Error: ${r.error}\n`;
      });

    report += '\n\nLow Agreement Questions:\n';
    results
      .filter(r => r.outcome === 'low_agreement')
      .forEach((r, i) => {
        report += `  ${i + 1}. ${r.question}\n`;
        report += `     Agreement: ${(r.agreement * 100).toFixed(1)}%\n`;
      });
  }

  return report;
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  batchConsensus,
  batchConsensusStream,
  analyzeBatchResults,
  generateBatchReport,
  DEFAULT_OPTIONS,
};
