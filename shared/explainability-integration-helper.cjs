/**
 * Explainability Integration Helper
 *
 * Simple utilities to add explainability to existing weighted voting calls.
 *
 * Usage:
 *   const { withExplainability } = require('./explainability-integration-helper.cjs');
 *
 *   // Wrap any weighted voting call
 *   const result = await withExplainability(
 *     () => runWeightedVoting(votes, taskType, options),
 *     { format: 'markdown', output: '/tmp/report.md' }
 *   );
 *
 * Created: 2026-07-01
 * Issue: #266
 */

const { explain } = require('./explainability-reporter.cjs');

// ============================================================================
// ENVIRONMENT VARIABLE CONTROLS
// ============================================================================

/**
 * Check if explainability is enabled globally
 *
 * Set CONSENSUS_EXPLAIN=1 to enable explainability for all consensus decisions.
 *
 * @returns {boolean}
 */
function isExplainabilityEnabled() {
  return process.env.CONSENSUS_EXPLAIN === '1' ||
         process.env.CONSENSUS_EXPLAIN === 'true' ||
         process.env.DEBUG_CONSENSUS === '1';
}

/**
 * Get default output directory for reports
 *
 * Set CONSENSUS_EXPLAIN_DIR to override (default: /tmp/consensus-reports)
 *
 * @returns {string}
 */
function getExplainOutputDir() {
  return process.env.CONSENSUS_EXPLAIN_DIR || '/tmp/consensus-reports';
}

/**
 * Get default format
 *
 * Set CONSENSUS_EXPLAIN_FORMAT to override (default: markdown)
 *
 * @returns {string}
 */
function getExplainFormat() {
  return process.env.CONSENSUS_EXPLAIN_FORMAT || 'markdown';
}

// ============================================================================
// WRAPPER FUNCTIONS
// ============================================================================

/**
 * Wrap a weighted voting call with automatic explainability
 *
 * If CONSENSUS_EXPLAIN=1, automatically generates report.
 * Otherwise, only generates if explainOptions provided.
 *
 * @param {Function} votingFn - Function that returns voting result (async)
 * @param {Object} explainOptions - Explainability options (optional)
 * @param {string} explainOptions.format - 'json' | 'markdown' | 'both'
 * @param {string} explainOptions.output - Output file path
 * @param {boolean} explainOptions.force - Force explain even if env var not set
 * @returns {Promise<Object>} Voting result with optional explainability
 */
async function withExplainability(votingFn, explainOptions = {}) {
  // Execute voting function
  const result = await votingFn();

  // Check if we should explain
  const shouldExplain = explainOptions.force ||
                        isExplainabilityEnabled() ||
                        explainOptions.format ||
                        explainOptions.output;

  if (!shouldExplain) {
    return result;
  }

  // Generate explainability report
  try {
    const votingResult = result.voting_result || result;

    if (votingResult.status !== 'success') {
      console.warn('[explainability] Skipping report - voting failed');
      return result;
    }

    const explainResult = await explain(votingResult, {
      format: explainOptions.format || getExplainFormat(),
      outputPath: explainOptions.output,
    });

    // Attach to result
    result.explainability = explainResult;

    if (explainResult.file_path) {
      console.log(`✓ Explainability report: ${explainResult.file_path}`);
    }
  } catch (err) {
    console.warn(`[explainability] Could not generate report: ${err.message}`);
  }

  return result;
}

/**
 * Add explainability options to voting options
 *
 * Merges environment-based defaults with user options.
 *
 * @param {Object} votingOptions - Original voting options
 * @param {Object} overrides - Override options
 * @returns {Object} Voting options with explainability settings
 */
function addExplainOptions(votingOptions = {}, overrides = {}) {
  const explain = overrides.explain !== undefined
    ? overrides.explain
    : isExplainabilityEnabled();

  if (!explain) {
    return votingOptions;
  }

  return {
    ...votingOptions,
    explain: true,
    explainFormat: overrides.explainFormat || getExplainFormat(),
    explainOutputPath: overrides.explainOutputPath,
  };
}

// ============================================================================
// CONDITIONAL LOGGING
// ============================================================================

/**
 * Log explainability info (only if enabled)
 *
 * @param {string} message - Message to log
 */
function explainLog(message) {
  if (isExplainabilityEnabled()) {
    console.log(`[explain] ${message}`);
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Environment checks
  isExplainabilityEnabled,
  getExplainOutputDir,
  getExplainFormat,

  // Wrappers
  withExplainability,
  addExplainOptions,

  // Logging
  explainLog,
};
