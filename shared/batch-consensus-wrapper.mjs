/**
 * ESM Wrapper for batch-consensus.cjs
 *
 * Provides ESM-compatible imports for batch consensus functionality.
 * Re-exports all functions from batch-consensus.cjs.
 *
 * Usage:
 *   import { batchConsensus, batchConsensusStream } from './shared/batch-consensus-wrapper.mjs';
 *
 * Created: 2026-07-01
 * Issue: #263
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const {
  batchConsensus,
  batchConsensusStream,
  analyzeBatchResults,
  generateBatchReport,
  DEFAULT_OPTIONS,
} = require('./batch-consensus.cjs');

export {
  batchConsensus,
  batchConsensusStream,
  analyzeBatchResults,
  generateBatchReport,
  DEFAULT_OPTIONS,
};

/**
 * Helper: Run batch consensus with custom worker function
 *
 * This allows workflows to use their own agent/model invocation logic
 * while still benefiting from batch processing, caching, and progress tracking.
 *
 * @param {Array<string>} questions - Questions to process
 * @param {Function} workerFn - Custom worker function: (question) => Promise<{model, answer, confidence}>
 * @param {Object} options - Batch options
 * @returns {Promise<Array<Object>>} Results
 */
export async function batchConsensusWithWorker(questions, workerFn, options = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  if (!Array.isArray(questions)) {
    throw new TypeError('questions must be an array');
  }

  if (typeof workerFn !== 'function') {
    throw new TypeError('workerFn must be a function');
  }

  const results = [];
  const chunks = createChunks(questions, opts.concurrency);
  let completed = 0;

  for (const chunk of chunks) {
    const chunkPromises = chunk.map(async ({ question, index }) => {
      try {
        // Use custom worker function
        const result = await workerFn(question);

        completed++;
        if (opts.onProgress) {
          opts.onProgress(completed, questions.length, result);
        }

        return {
          question,
          answer: result.answer,
          confidence: result.confidence,
          models: result.models || [result.model],
          votes: result.votes || {},
          cached: false,
          timestamp: new Date().toISOString(),
        };
      } catch (error) {
        if (opts.onError) {
          opts.onError(error, question, index);
        }

        if (opts.stopOnError) {
          throw error;
        }

        completed++;
        if (opts.onProgress) {
          opts.onProgress(completed, questions.length, { error: error.message });
        }

        return {
          question,
          error: error.message,
          confidence: 0,
          outcome: 'error',
        };
      }
    });

    const chunkResults = await Promise.all(chunkPromises);
    results.push(...chunkResults);
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
