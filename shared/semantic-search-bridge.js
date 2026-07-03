/**
 * Semantic Search Bridge - JavaScript interface to semantic-search.py
 *
 * Calls the Python HybridSearch (RRF), Reranker, and AdvancedFilter classes
 * via execFileSync, passing data through temp files to avoid argument length
 * limits. Follows the same Python-bridge pattern as knowledge-search-hybrid.js
 * and semantic-knowledge-search.js.
 *
 * Usage:
 *   import { hybridSearch, rerank, advancedFilter } from './shared/semantic-search-bridge.js';
 *
 *   // Hybrid search (RRF merge)
 *   const merged = hybridSearch(semanticResults, keywordResults, { topK: 10 });
 *
 *   // Reranking
 *   const top = rerank('query text', candidates, { topK: 5 });
 *
 *   // Advanced filtering
 *   const filtered = advancedFilter(results, { type: { $gte: 'feedback' } });
 */

import { execFileSync } from 'child_process';
import { writeFileSync, readFileSync, unlinkSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { randomUUID } from 'crypto';
import { fileURLToPath } from 'url';

// ============================================================================
// CONSTANTS
// ============================================================================

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PYTHON = process.env.PYTHON_PATH || 'python3';
const SEMANTIC_SEARCH_PY = join(__dirname, 'semantic-search.py');
const TMP_DIR = process.env.TMPDIR || '/tmp';
const TIMEOUT_MS = 30000;
const RERANK_TIMEOUT_MS = 120000; // Reranker may need to download cross-encoder model on first use

// ============================================================================
// PYTHON BRIDGE SCRIPT
// ============================================================================

/**
 * Inline Python script that loads semantic-search.py and dispatches operations.
 * Reads a JSON request from a temp file (argv[1]), writes JSON response to
 * the output path specified in the request.
 */
const _PYTHON_BRIDGE = `
import sys, json, os, importlib.util

# Load the request
with open(sys.argv[1], 'r') as f:
    req = json.load(f)

# Load semantic-search.py via importlib (hyphenated filename is not a valid
# Python module name, so a normal import would fail)
_spec = importlib.util.spec_from_file_location(
    'semantic_search',
    os.path.join(req['module_dir'], 'semantic-search.py')
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
HybridSearch = _mod.HybridSearch
Reranker = _mod.Reranker
AdvancedFilter = _mod.AdvancedFilter

operation = req['operation']
result = None

if operation == 'hybrid_search':
    hybrid = HybridSearch(
        semantic_weight=req.get('semantic_weight', 0.7),
        keyword_weight=req.get('keyword_weight', 0.3),
        k=req.get('k', 60)
    )
    result = hybrid.merge(
        req['semantic_results'],
        req['keyword_results'],
        top_k=req.get('top_k', 10)
    )

elif operation == 'rerank':
    reranker = Reranker(model=req.get('model', 'cross-encoder/ms-marco-MiniLM-L-6-v2'))
    result = reranker.rerank(
        req['query'],
        req['candidates'],
        top_k=req.get('top_k', 5)
    )

elif operation == 'advanced_filter':
    result = AdvancedFilter.apply(
        req['results'],
        req['filter_query']
    )

else:
    result = {'error': f'Unknown operation: {operation}'}

# Write output
with open(req['output_file'], 'w') as f:
    json.dump(result, f)
`;

// ============================================================================
// INTERNAL HELPERS
// ============================================================================

/**
 * Execute a Python operation via the bridge script.
 * Uses temp files for JSON I/O to handle large payloads safely.
 *
 * @param {string} operation - Operation name (hybrid_search, rerank, advanced_filter)
 * @param {Object} payload - Operation-specific parameters
 * @param {number} [timeoutMs] - Override default timeout (ms)
 * @returns {any} Parsed JSON result from Python
 * @throws {Error} If Python execution fails or times out
 */
function _execPython(operation, payload, timeoutMs) {
  const id = randomUUID().slice(0, 8);
  const tmpIn = join(TMP_DIR, `.sem-search-in-${id}.json`);
  const tmpOut = join(TMP_DIR, `.sem-search-out-${id}.json`);

  try {
    const request = {
      operation,
      module_dir: __dirname,
      output_file: tmpOut,
      ...payload,
    };

    writeFileSync(tmpIn, JSON.stringify(request));

    execFileSync(PYTHON, ['-c', _PYTHON_BRIDGE, tmpIn], {
      encoding: 'utf-8',
      timeout: timeoutMs || TIMEOUT_MS,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    if (!existsSync(tmpOut)) {
      throw new Error(`Python bridge did not produce output file for operation: ${operation}`);
    }

    const raw = readFileSync(tmpOut, 'utf-8');
    return JSON.parse(raw);
  } finally {
    _cleanup(tmpIn);
    _cleanup(tmpOut);
  }
}

/**
 * Silently remove a temp file if it exists.
 * @param {string} filepath - Path to remove
 */
function _cleanup(filepath) {
  try {
    if (existsSync(filepath)) {
      unlinkSync(filepath);
    }
  } catch (_) {
    // Ignore cleanup errors
  }
}

// ============================================================================
// PUBLIC API
// ============================================================================

/**
 * Merge semantic and keyword search results using Reciprocal Rank Fusion (RRF).
 *
 * Each result must have at least an `id` field. Additional fields (text, score,
 * metadata, etc.) are preserved in the output. The merged results include a
 * `hybrid_score` field representing the RRF-weighted rank.
 *
 * @param {Array<Object>} semanticResults - Results from vector/embedding search
 * @param {Array<Object>} keywordResults - Results from keyword/text search
 * @param {Object} [options] - Configuration
 * @param {number} [options.topK=10] - Number of results to return
 * @param {number} [options.semanticWeight=0.7] - Weight for semantic results (0-1)
 * @param {number} [options.keywordWeight=0.3] - Weight for keyword results (0-1)
 * @param {number} [options.k=60] - RRF parameter (from the original paper)
 * @returns {Array<Object>} Merged results sorted by hybrid_score descending
 *
 * @example
 *   const merged = hybridSearch(
 *     [{ id: 'doc1', score: 0.95, text: 'Multi-model consensus' }],
 *     [{ id: 'doc1', score: 0.70, text: 'Multi-model consensus' }],
 *     { topK: 5 }
 *   );
 */
export function hybridSearch(semanticResults, keywordResults, options = {}) {
  if (!Array.isArray(semanticResults) || !Array.isArray(keywordResults)) {
    throw new TypeError('semanticResults and keywordResults must be arrays');
  }

  // Fast path: if both inputs are empty, skip the Python call
  if (semanticResults.length === 0 && keywordResults.length === 0) {
    return [];
  }

  return _execPython('hybrid_search', {
    semantic_results: semanticResults,
    keyword_results: keywordResults,
    top_k: options.topK ?? 10,
    semantic_weight: options.semanticWeight ?? 0.7,
    keyword_weight: options.keywordWeight ?? 0.3,
    k: options.k ?? 60,
  });
}

/**
 * Rerank candidate documents using a cross-encoder model.
 *
 * Two-stage retrieval: use a fast bi-encoder for initial recall, then rerank
 * the top candidates with a more accurate cross-encoder. Falls back to
 * returning candidates as-is if sentence-transformers is not installed.
 *
 * Each candidate should have a `document` or `text` field for scoring.
 *
 * @param {string} query - The search query
 * @param {Array<Object>} candidates - Candidate documents to rerank
 * @param {Object} [options] - Configuration
 * @param {number} [options.topK=5] - Number of top results to return
 * @param {string} [options.model='cross-encoder/ms-marco-MiniLM-L-6-v2'] - Cross-encoder model
 * @returns {Array<Object>} Reranked results with `rerank_score` field
 *
 * @example
 *   const top = rerank('arbiter pattern', candidates, { topK: 3 });
 */
export function rerank(query, candidates, options = {}) {
  if (typeof query !== 'string' || !query.trim()) {
    throw new TypeError('query must be a non-empty string');
  }
  if (!Array.isArray(candidates)) {
    throw new TypeError('candidates must be an array');
  }

  if (candidates.length === 0) {
    return [];
  }

  return _execPython('rerank', {
    query,
    candidates,
    top_k: options.topK ?? 5,
    model: options.model ?? 'cross-encoder/ms-marco-MiniLM-L-6-v2',
  }, RERANK_TIMEOUT_MS);
}

/**
 * Apply MongoDB-style filters to search results.
 *
 * Filters operate on the `metadata` field of each result. Supports:
 * - Comparison: $eq, $ne, $gt, $gte, $lt, $lte
 * - Logical: $and, $or, $not
 * - Array: $in, $nin
 * - String: $regex, $glob
 *
 * @param {Array<Object>} results - Results to filter (each with a `metadata` field)
 * @param {Object} filterQuery - MongoDB-style filter expression
 * @returns {Array<Object>} Filtered results
 *
 * @example
 *   // Exact match
 *   advancedFilter(results, { type: 'feedback' });
 *
 *   // Range + type
 *   advancedFilter(results, { type: 'feedback', score: { $gte: 0.8 } });
 *
 *   // Logical OR
 *   advancedFilter(results, { $or: [{ type: 'feedback' }, { type: 'user' }] });
 *
 *   // Regex
 *   advancedFilter(results, { name: { $regex: '^multi-' } });
 */
export function advancedFilter(results, filterQuery) {
  if (!Array.isArray(results)) {
    throw new TypeError('results must be an array');
  }
  if (!filterQuery || typeof filterQuery !== 'object') {
    throw new TypeError('filterQuery must be an object');
  }

  if (results.length === 0) {
    return [];
  }

  return _execPython('advanced_filter', {
    results,
    filter_query: filterQuery,
  });
}

/**
 * Check whether the Python semantic-search module is available.
 *
 * @returns {boolean} true if semantic-search.py exists and Python can import it
 */
export function isAvailable() {
  try {
    if (!existsSync(SEMANTIC_SEARCH_PY)) {
      return false;
    }
    execFileSync(PYTHON, ['-c', `
import importlib.util, os
spec = importlib.util.spec_from_file_location(
    'semantic_search',
    os.path.join('${__dirname.replace(/'/g, "\\'")}', 'semantic-search.py')
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert hasattr(mod, 'HybridSearch')
assert hasattr(mod, 'Reranker')
assert hasattr(mod, 'AdvancedFilter')
print('ok')
`], {
      encoding: 'utf-8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return true;
  } catch (_) {
    return false;
  }
}
