/**
 * Consensus Cache Stub
 *
 * Minimal stub to unblock batch-consensus.cjs until consensus-cache.cjs is fixed.
 * Issue #263 - syntax error in consensus-cache.cjs (5 missing closing braces)
 */

async function lookupCache(question, taskType) {
  // Stub: always return cache miss
  return null;
}

async function storeCache(question, taskType, consensusResult) {
  // Stub: silently ignore stores
  return null;
}

module.exports = {
  lookupCache,
  storeCache,
};
