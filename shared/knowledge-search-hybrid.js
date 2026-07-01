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
    // Use knowledge_tools.py wrapper
    const script = `
import sys
sys.path.insert(0, '${TOOLS_DIR}')
from knowledge_tools import query_knowledge
import json

results = query_knowledge('${query.replace(/'/g, "\\'")}', limit=${limit})
print(json.dumps(results))
`;

    const tmpFile = `/tmp/kg-search-${randomUUID()}.py`;
    writeFileSync(tmpFile, script);

    const output = execFileSync(PYTHON, [tmpFile], {
      encoding: 'utf-8',
      timeout: 10000
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
  // TODO: Implement proper ranking algorithm
  return results.slice(0, limit);
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
