/**
 * Knowledge System Adapter - Node.js wrapper for PostgreSQL + pgvector knowledge storage
 *
 * Replaces ChromaDB with PostgreSQL-backed semantic knowledge system.
 * Uses Python knowledge_system.py backend for embeddings and storage.
 *
 * Features:
 * - Semantic chunking for large content (>1500 chars)
 * - 384-dim embeddings via sentence-transformers
 * - Provenance tracking (created/updated history)
 * - Fast HNSW similarity search
 *
 * Database: PostgreSQL on aio-01:5433 (learning database)
 * Schema: knowledge.entries, knowledge.provenance
 *
 * Usage:
 *   import { getKnowledgeSystem } from './shared/knowledge-system-adapter.js';
 *   const ks = getKnowledgeSystem();
 *
 *   // Store knowledge
 *   const entryId = await ks.storeKnowledge({
 *     content: "PostgreSQL with pgvector provides fast semantic search",
 *     source: "web-research",
 *     source_type: "research_finding",
 *     metadata: { topic: "database", confidence: 0.95 }
 *   });
 *
 *   // Semantic search
 *   const results = await ks.semanticSearch("vector database", { limit: 10 });
 *
 *   // Get provenance
 *   const history = await ks.getProvenance(entryId);
 */

import { execFileSync } from 'child_process';
import { existsSync, writeFileSync, readFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// CONSTANTS
// ============================================================================

const PROJECT_ROOT = path.join(__dirname, '..');
const TOOLS_DIR = join(PROJECT_ROOT, 'tools');
const KNOWLEDGE_SYSTEM_PY = join(TOOLS_DIR, 'knowledge_system.py');

const PYTHON = process.env.PYTHON_PATH || 'python3';
const TIMEOUT_MS = 30000;

// Track availability
let _available = null;

// ============================================================================
// PYTHON BRIDGE
// ============================================================================

/**
 * Execute knowledge_system.py operation via Python subprocess
 */
function _execKnowledgeSystem(operation, payload) {
  const tmpIn = `/tmp/ks_in_${randomUUID()}.json`;
  const tmpOut = `/tmp/ks_out_${randomUUID()}.json`;

  try {
    const request = {
      operation,
      output_file: tmpOut,
      ...payload,
    };

    writeFileSync(tmpIn, JSON.stringify(request));

    // Call Python script
    execFileSync(PYTHON, [KNOWLEDGE_SYSTEM_PY, tmpIn], {
      timeout: TIMEOUT_MS,
      stdio: ['pipe', 'pipe', 'pipe'],
      encoding: 'utf-8',
    });

    if (existsSync(tmpOut)) {
      const result = JSON.parse(readFileSync(tmpOut, 'utf-8'));
      return result;
    }

    return { success: true };
  } catch (err) {
    if (process.env.KNOWLEDGE_DEBUG) {
      console.error(`[knowledge-system] ${operation} failed: ${err.message}`);
    }
    return { success: false, error: err.message };
  } finally {
    _safeUnlink(tmpIn);
    _safeUnlink(tmpOut);
  }
}

function _safeUnlink(path) {
  try {
    if (existsSync(path)) unlinkSync(path);
  } catch (_err) {
    // ignore
  }
}

// ============================================================================
// AVAILABILITY CHECK
// ============================================================================

/**
 * Check if knowledge_system.py is available
 */
export function isAvailable() {
  if (_available !== null) return _available;

  try {
    if (!existsSync(KNOWLEDGE_SYSTEM_PY)) {
      _available = false;
      return false;
    }

    // Try importing the module
    execFileSync(PYTHON, ['-c', 'import psycopg2; import sys; sys.path.insert(0, "' + TOOLS_DIR + '"); from knowledge_system import KnowledgeSystem; print("ok")'], {
      timeout: 5000,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    _available = true;
  } catch (_err) {
    _available = false;
  }

  return _available;
}

// ============================================================================
// KNOWLEDGE SYSTEM CLASS
// ============================================================================

class KnowledgeSystem {
  constructor() {
    if (!isAvailable()) {
      throw new Error('Knowledge system not available - check PostgreSQL connection and Python dependencies');
    }
  }

  /**
   * Store knowledge with semantic chunking and provenance tracking
   *
   * @param {Object} options
   * @param {string} options.content - Content to store (auto-chunked if >1500 chars)
   * @param {string} options.source - Source identifier (e.g., "web-research", "user-upload")
   * @param {string} [options.source_type] - Type of source (default: "manual")
   * @param {Object} [options.metadata] - Additional metadata
   * @param {string} [options.actor] - Who is storing this (default: "system")
   * @returns {Promise<number>} Entry ID (first chunk if content was chunked)
   */
  async storeKnowledge({ content, source, source_type = 'manual', metadata = {}, actor = 'system' }) {
    const result = _execKnowledgeSystem('store', {
      content,
      source,
      source_type,
      metadata: JSON.stringify(metadata),
      actor,
    });

    if (!result.success) {
      throw new Error(`Failed to store knowledge: ${result.error}`);
    }

    return result.entry_id;
  }

  /**
   * Semantic search using pgvector similarity
   *
   * @param {string} query - Natural language query
   * @param {Object} [options]
   * @param {number} [options.limit] - Max results (default: 10)
   * @param {string} [options.source_type] - Filter by source type
   * @param {number} [options.min_similarity] - Minimum similarity score 0.0-1.0 (default: 0.0)
   * @returns {Promise<Object[]>} Array of { id, content, source, source_type, metadata, created_at, similarity }
   */
  async semanticSearch(query, options = {}) {
    const { limit = 10, source_type, min_similarity = 0.0 } = options;

    const result = _execKnowledgeSystem('search', {
      query,
      limit,
      source_type,
      min_similarity,
    });

    if (!result.success) {
      throw new Error(`Search failed: ${result.error}`);
    }

    return result.results || [];
  }

  /**
   * Get provenance history for an entry
   *
   * @param {number} entry_id - Entry ID
   * @returns {Promise<Object[]>} Array of { action, actor, timestamp, details }
   */
  async getProvenance(entry_id) {
    const result = _execKnowledgeSystem('provenance', { entry_id });

    if (!result.success) {
      throw new Error(`Failed to get provenance: ${result.error}`);
    }

    return result.provenance || [];
  }

  /**
   * Update existing knowledge entry
   *
   * @param {number} entry_id - Entry ID to update
   * @param {string} content - New content
   * @param {string} [actor] - Who is updating (default: "system")
   * @returns {Promise<void>}
   */
  async updateKnowledge(entry_id, content, actor = 'system') {
    const result = _execKnowledgeSystem('update', {
      entry_id,
      content,
      actor,
    });

    if (!result.success) {
      throw new Error(`Failed to update knowledge: ${result.error}`);
    }
  }

  /**
   * Get statistics about stored knowledge
   *
   * @returns {Promise<Object>} { total_entries, by_source_type }
   */
  async getStats() {
    const result = _execKnowledgeSystem('stats', {});

    if (!result.success) {
      throw new Error(`Failed to get stats: ${result.error}`);
    }

    return result.stats || { total_entries: 0, by_source_type: {} };
  }
}

// ============================================================================
// SINGLETON
// ============================================================================

let _instance = null;

/**
 * Get singleton KnowledgeSystem instance
 * @returns {KnowledgeSystem}
 */
export function getKnowledgeSystem() {
  if (!_instance) {
    _instance = new KnowledgeSystem();
  }
  return _instance;
}

// ============================================================================
// CONVENIENCE HELPERS (backward compatibility with semantic-knowledge-search.js)
// ============================================================================

/**
 * Store web research finding
 */
export async function storeWebResearch(finding) {
  const ks = getKnowledgeSystem();

  const content = [
    `Title: ${finding.title || 'Untitled'}`,
    finding.abstract || finding.description || finding.finding || '',
    finding.topics ? `Topics: ${finding.topics.join(', ')}` : '',
    finding.tags ? `Tags: ${finding.tags.join(', ')}` : '',
  ].filter(Boolean).join('\n\n');

  return ks.storeKnowledge({
    content,
    source: finding.source || 'web-research',
    source_type: 'web_synthesis',
    metadata: {
      title: finding.title,
      url: finding.url,
      source_name: finding.source,
      topics: finding.topics,
      tags: finding.tags,
      relevance_score: finding.relevanceScore,
      timestamp: finding.timestamp || new Date().toISOString(),
    },
  });
}

/**
 * Store disseminator knowledge entry
 */
export async function storeDisseminatorKnowledge(entry) {
  const ks = getKnowledgeSystem();

  const content = [
    `Title: ${entry.title || 'Untitled'}`,
    `Type: ${entry.type || 'unknown'}`,
    entry.content || '',
    entry.entities ? `Entities: ${entry.entities.join(', ')}` : '',
  ].filter(Boolean).join('\n\n');

  return ks.storeKnowledge({
    content,
    source: entry.id || 'disseminator',
    source_type: 'disseminator',
    metadata: {
      title: entry.title,
      type: entry.type,
      entities: entry.entities,
      confidence: entry.confidence,
      quality_score: entry.quality_score,
      model_used: entry.model_used,
      extracted_at: entry.extracted_at,
    },
  });
}

/**
 * Unified search across all knowledge (backward compatible)
 */
export async function searchAll(query, options = {}) {
  const ks = getKnowledgeSystem();
  const { limit = 10, min_similarity = 0.5 } = options;

  // Search all knowledge
  const allResults = await ks.semanticSearch(query, { limit: limit * 2, min_similarity });

  // Split by source_type for backward compatibility
  const disseminator = allResults.filter(r => r.source_type === 'disseminator').slice(0, limit);
  const web_synthesis = allResults.filter(r => r.source_type === 'web_synthesis').slice(0, limit);

  return {
    query,
    disseminator,
    web_synthesis,
    total_found: disseminator.length + web_synthesis.length,
  };
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  isAvailable,
  getKnowledgeSystem,
  storeWebResearch,
  storeDisseminatorKnowledge,
  searchAll,
};
