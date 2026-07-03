/**
 * Hybrid Knowledge Search - PostgreSQL + ChromaDB
 *
 * Integrates knowledge_system.py (PostgreSQL knowledge.* tables)
 * with existing ChromaDB semantic search.
 *
 * Strategy:
 * 1. Search PostgreSQL knowledge.concepts for exact/similar matches
 * 2. Search ChromaDB for semantic similarity
 * 3. Merge and rank results
 *
 * Usage:
 *   import { searchKnowledge } from './knowledge-search-hybrid.js';
 *   const results = await searchKnowledge('error handling', { limit: 10 });
 */

import { execFileSync } from 'child_process';
import { writeFileSync, readFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';

const HOME = process.env.HOME || '/tmp';
const TOOLS_DIR = join(HOME, 'Development', 'redhat', 'scm', 'gitlab', 'cee', 'sfloess', 'claude-global-skills', 'tools');
const PYTHON = 'python3';

/**
 * Search PostgreSQL knowledge.concepts table
 */
async function searchPostgresKnowledge(query, options = {}) {
  const limit = options.limit || 10;

  try {
    // SECURE: Pass query as JSON via stdin, not string interpolation
    const script = `
import sys
import json
sys.path.insert(0, '${TOOLS_DIR}')
from knowledge_tools import query_knowledge

# Read query from stdin (safe from injection)
input_data = json.loads(sys.stdin.read())
query = input_data['query']
limit = input_data['limit']

results = query_knowledge(query, limit=limit)
print(json.dumps(results))
`;

    const tmpFile = `/tmp/kg-search-${randomUUID()}.py`;
    writeFileSync(tmpFile, script);

    // Pass query via stdin (safe from injection)
    const output = execFileSync(PYTHON, [tmpFile], {
      encoding: 'utf-8',
      timeout: 10000,
      input: JSON.stringify({ query, limit })
    });

    unlinkSync(tmpFile);

    return JSON.parse(output);
  } catch (e) {
    console.warn('[knowledge-search-hybrid] PostgreSQL search failed:', e.message);
    return [];
  }
}

/**
 * Search ChromaDB (fallback to existing semantic-knowledge-search.js)
 */
async function searchChromaDB(query, options = {}) {
  try {
    const { searchDisseminator } = await import('./semantic-knowledge-search.js');
    return await searchDisseminator(query, options);
  } catch (e) {
    console.warn('[knowledge-search-hybrid] ChromaDB search failed:', e.message);
    return [];
  }
}

/**
 * Hybrid search: PostgreSQL + ChromaDB
 *
 * @param {string} query - Search query
 * @param {object} options - { limit, usePostgres, useChroma }
 * @returns {Promise<Array>} Merged and ranked results
 */
export async function searchKnowledge(query, options = {}) {
  const {
    limit = 10,
    usePostgres = true,
    useChroma = true
  } = options;

  const results = [];

  // Search PostgreSQL knowledge.concepts
  if (usePostgres) {
    const pgResults = await searchPostgresKnowledge(query, { limit });
    results.push(...pgResults.map(r => ({ ...r, source: 'postgres' })));
  }

  // Search ChromaDB
  if (useChroma) {
    const chromaResults = await searchChromaDB(query, { limit });
    results.push(...chromaResults.map(r => ({ ...r, source: 'chroma' })));
  }

  // Deduplicate and rank
  // FIXED (#289): Proper ranking algorithm using hybrid BM25 + vector similarity
  return rankResults(results, query, limit);
}

/**
 * Rank results using hybrid scoring:
 * - Vector similarity (cosine distance from pgvector/ChromaDB)
 * - BM25 text matching (term frequency, document frequency)
 * - Source weighting (PostgreSQL knowledge graph gets boost)
 *
 * @param {Array} results - Raw results from multiple sources
 * @param {string} query - Original query for BM25 scoring
 * @param {number} limit - Max results to return
 * @returns {Array} Ranked and deduplicated results
 */
function rankResults(results, query, limit) {
  if (results.length === 0) return [];

  // Deduplicate by content hash
  const seen = new Set();
  const deduped = results.filter(r => {
    const hash = hashContent(r);
    if (seen.has(hash)) return false;
    seen.add(hash);
    return true;
  });

  // Calculate BM25 scores
  const queryTerms = tokenize(query);
  const bm25Scores = deduped.map(r => ({
    result: r,
    bm25: calculateBM25(queryTerms, r, deduped)
  }));

  // Combine scores: 60% vector similarity + 30% BM25 + 10% source weight
  const scored = bm25Scores.map(({ result, bm25 }) => {
    const vectorScore = result.distance ? (1 - result.distance) : (result.score || 0.5);
    const sourceWeight = result.source === 'postgres' ? 1.0 : 0.8; // Boost knowledge graph
    const hybridScore = (0.6 * vectorScore) + (0.3 * bm25) + (0.1 * sourceWeight);

    return {
      ...result,
      hybrid_score: hybridScore,
      bm25_score: bm25,
      vector_score: vectorScore
    };
  });

  // Sort by hybrid score descending
  scored.sort((a, b) => b.hybrid_score - a.hybrid_score);

  return scored.slice(0, limit);
}

/**
 * Simple content hash for deduplication
 */
function hashContent(result) {
  const content = result.content || result.document || result.text || '';
  return content.toLowerCase().trim().substring(0, 100);
}

/**
 * Tokenize query into terms (simple word-based)
 */
function tokenize(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 2); // Filter stopwords by length
}

/**
 * Calculate BM25 score
 * BM25(q, d) = Σ IDF(qi) * (f(qi, d) * (k1 + 1)) / (f(qi, d) + k1 * (1 - b + b * |d| / avgdl))
 *
 * @param {Array<string>} queryTerms - Query tokens
 * @param {Object} doc - Document to score
 * @param {Array} corpus - All documents (for IDF calculation)
 * @returns {number} BM25 score (0-1 normalized)
 */
function calculateBM25(queryTerms, doc, corpus) {
  const k1 = 1.5;  // Term frequency saturation
  const b = 0.75;  // Length normalization

  const docText = (doc.content || doc.document || doc.text || '').toLowerCase();
  const docTerms = tokenize(docText);
  const docLength = docTerms.length;

  // Average document length in corpus
  const avgDocLength = corpus.reduce((sum, d) => {
    const text = (d.content || d.document || d.text || '').toLowerCase();
    return sum + tokenize(text).length;
  }, 0) / corpus.length;

  let score = 0;

  for (const term of queryTerms) {
    // Term frequency in document
    const tf = docTerms.filter(t => t === term).length;
    if (tf === 0) continue;

    // Inverse document frequency
    const docsWithTerm = corpus.filter(d => {
      const text = (d.content || d.document || d.text || '').toLowerCase();
      return text.includes(term);
    }).length;
    const idf = Math.log((corpus.length - docsWithTerm + 0.5) / (docsWithTerm + 0.5) + 1);

    // BM25 component
    const numerator = tf * (k1 + 1);
    const denominator = tf + k1 * (1 - b + b * (docLength / avgDocLength));
    score += idf * (numerator / denominator);
  }

  // Normalize to 0-1 range
  return Math.min(1, score / (queryTerms.length + 1));
}

/**
 * Check if hybrid search is available
 */
export async function isAvailable() {
  try {
    // Test PostgreSQL connection
    const testScript = `
import sys
sys.path.insert(0, '${TOOLS_DIR}')
from knowledge_tools import query_knowledge
query_knowledge('test', limit=1)
print('OK')
`;

    const tmpFile = `/tmp/kg-test-${randomUUID()}.py`;
    writeFileSync(tmpFile, testScript);
    execFileSync(PYTHON, [tmpFile], { timeout: 5000 });
    unlinkSync(tmpFile);

    return true;
  } catch (e) {
    return false;
  }
}

export default {
  searchKnowledge,
  isAvailable
};
