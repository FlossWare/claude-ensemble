/**
 * Semantic Knowledge Search - ChromaDB-backed semantic search for knowledge bases
 *
 * Replaces naive substring matching with vector embedding search so that
 * queries like "async error handling" find learnings titled "promise rejection
 * patterns". Uses the same Python-bridge architecture as learning-vectordb.js
 * but with dedicated collections for knowledge base content.
 *
 * Collections:
 *   - disseminator_knowledge: Disseminator KB entries (title + content + entities)
 *   - web_synthesis: Web research findings (title + finding + topics)
 *
 * Embedding model: all-MiniLM-L6-v2 (384-dim, cosine distance) via ChromaDB default
 * Storage: ~/.claude/learning/db/chroma-kb/
 *
 * Usage:
 *   import { searchDisseminator, searchWebSynthesis, indexDisseminatorKB,
 *            indexWebSynthesis, isAvailable } from './shared/semantic-knowledge-search.js';
 *
 *   // Index existing JSONL data into ChromaDB (run once or when data changes)
 *   await indexDisseminatorKB();
 *   await indexWebSynthesis();
 *
 *   // Semantic search
 *   const results = await searchDisseminator('async error handling', { limit: 5 });
 *   // Returns entries about promise rejections, error boundaries, try/catch, etc.
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdirSync, writeFileSync, readFileSync, unlinkSync, readdirSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';
import { validateReadPath, validateWritePath } from './path-validator.js';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const LEARNING_DIR = join(HOME, '.claude', 'learning');
const CHROMA_KB_DIR = join(LEARNING_DIR, 'db', 'chroma-kb');
const DISSEMINATOR_KB_FILE = join(LEARNING_DIR, 'disseminator-knowledge.jsonl');
const RESEARCH_DIR = join(LEARNING_DIR, 'research');

const DISSEMINATOR_COLLECTION = 'disseminator_knowledge';
const WEB_SYNTHESIS_COLLECTION = 'web_synthesis';

const PYTHON = process.env.PYTHON_PATH || 'python3';
const TIMEOUT_MS = 30000;
const INDEX_BATCH_SIZE = 100;

// Track whether ChromaDB availability has been checked
let _chromaAvailable = null;

// ============================================================================
// PYTHON BRIDGE
// ============================================================================

/**
 * Execute a ChromaDB operation via Python subprocess.
 * Uses temp files for JSON I/O to avoid argument length limits.
 */
function _chromaExec(operation, payload) {
  const tmpIn = join(CHROMA_KB_DIR, `.tmp_in_${randomUUID()}.json`);
  const tmpOut = join(CHROMA_KB_DIR, `.tmp_out_${randomUUID()}.json`);

  try {
    // Validate paths before use
    const validTmpIn = validateWritePath(tmpIn);
    const validTmpOut = validateWritePath(tmpOut);

    if (!existsSync(CHROMA_KB_DIR)) {
      mkdirSync(CHROMA_KB_DIR, { recursive: true });
    }

    const request = {
      operation,
      chroma_dir: CHROMA_KB_DIR,
      output_file: validTmpOut,
      ...payload,
    };

    writeFileSync(validTmpIn, JSON.stringify(request));

    execFileSync(PYTHON, ['-c', _PYTHON_BRIDGE, validTmpIn], {
      timeout: TIMEOUT_MS,
      stdio: ['pipe', 'pipe', 'pipe'],
      encoding: 'utf-8',
    });

    if (existsSync(validTmpOut)) {
      const result = JSON.parse(readFileSync(validTmpOut, 'utf-8'));
      return result;
    }

    return { success: true };
  } catch (err) {
    if (process.env.LEARNING_DEBUG) {
      console.error(`[semantic-knowledge-search] ChromaDB ${operation} failed: ${err.message}`);
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
 * Check if ChromaDB is available (Python + chromadb installed).
 * Result is cached for the process lifetime.
 */
export function isAvailable() {
  if (_chromaAvailable !== null) return _chromaAvailable;

  try {
    execFileSync(PYTHON, ['-c', 'import chromadb; print("ok")'], {
      timeout: 5000,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    _chromaAvailable = true;
  } catch (_err) {
    _chromaAvailable = false;
  }

  return _chromaAvailable;
}

// ============================================================================
// INDEXING - Disseminator Knowledge Base
// ============================================================================

/**
 * Index the disseminator knowledge base JSONL file into ChromaDB.
 * Each entry becomes a document with its title, content, and entities
 * combined into rich text for embedding. Metadata is stored for filtering.
 *
 * This is idempotent -- re-indexing upserts by entry ID.
 *
 * @param {Object} [options]
 * @param {string} [options.kbFile] - Path to JSONL file (default: disseminator-knowledge.jsonl)
 * @param {number} [options.minConfidence] - Skip entries below this confidence (default: 0)
 * @returns {Object} { success, indexed, skipped, errors }
 */
export async function indexDisseminatorKB(options = {}) {
  const { kbFile = DISSEMINATOR_KB_FILE, minConfidence = 0 } = options;

  // Validate path before reading
  const validKbFile = validateReadPath(kbFile);

  if (!existsSync(validKbFile)) {
    return { success: false, error: `KB file not found: ${validKbFile}`, indexed: 0 };
  }

  const lines = readFileSync(validKbFile, 'utf-8').trim().split('\n').filter(Boolean);

  let indexed = 0;
  let skipped = 0;
  let errors = 0;

  // Process in batches
  for (let i = 0; i < lines.length; i += INDEX_BATCH_SIZE) {
    const batch = lines.slice(i, i + INDEX_BATCH_SIZE);
    const documents = [];
    const metadatas = [];
    const ids = [];

    for (const line of batch) {
      try {
        const item = JSON.parse(line);

        if (item.confidence && item.confidence < minConfidence) {
          skipped++;
          continue;
        }

        // Build rich document text for embedding
        const docParts = [];
        if (item.title) docParts.push(`Title: ${item.title}`);
        if (item.type) docParts.push(`Type: ${item.type}`);
        if (item.content) docParts.push(`Content: ${item.content}`);
        if (item.entities && item.entities.length > 0) {
          docParts.push(`Entities: ${item.entities.join(', ')}`);
        }
        const docText = docParts.join('\n');

        if (!docText.trim()) {
          skipped++;
          continue;
        }

        // Build metadata for filtering
        const meta = {};
        if (item.id) meta.entry_id = String(item.id);
        if (item.type) meta.type = String(item.type);
        if (item.title) meta.title = String(item.title).slice(0, 500);
        if (item.confidence !== undefined) meta.confidence = Number(item.confidence);
        if (item.quality_score !== undefined) meta.quality_score = Number(item.quality_score);
        if (item.model_used) meta.model_used = String(item.model_used);
        if (item.extracted_at) meta.extracted_at = String(item.extracted_at);
        if (item.entities) meta.entities = item.entities.join(',').slice(0, 500);
        meta.source = 'disseminator';
        meta.timestamp = item.extracted_at
          ? Math.floor(new Date(item.extracted_at).getTime() / 1000)
          : Math.floor(Date.now() / 1000);

        documents.push(docText);
        metadatas.push(meta);
        ids.push(item.id || `dk_${randomUUID()}`);
      } catch (_err) {
        errors++;
      }
    }

    if (documents.length > 0) {
      const result = _chromaExec('upsert', {
        collection: DISSEMINATOR_COLLECTION,
        documents,
        metadatas,
        ids,
      });

      if (result.success !== false) {
        indexed += documents.length;
      } else {
        errors += documents.length;
      }
    }
  }

  return { success: errors === 0, indexed, skipped, errors };
}

// ============================================================================
// INDEXING - Web Synthesis
// ============================================================================

/**
 * Index web synthesis JSONL files into ChromaDB.
 * Scans the research directory for web-synthesis-*.jsonl files.
 *
 * @param {Object} [options]
 * @param {string} [options.researchDir] - Path to research directory
 * @param {number} [options.minConfidence] - Skip entries below this confidence (default: 0)
 * @returns {Object} { success, indexed, skipped, errors, files_processed }
 */
export async function indexWebSynthesis(options = {}) {
  const { researchDir = RESEARCH_DIR, minConfidence = 0 } = options;

  // Validate research directory path
  const validResearchDir = validateReadPath(researchDir);

  if (!existsSync(validResearchDir)) {
    return { success: false, error: `Research dir not found: ${validResearchDir}`, indexed: 0 };
  }

  const files = readdirSync(validResearchDir)
    .filter(f => f.startsWith('web-synthesis-') && f.endsWith('.jsonl'));

  let totalIndexed = 0;
  let totalSkipped = 0;
  let totalErrors = 0;

  for (const file of files) {
    const filePath = validateReadPath(join(validResearchDir, file));
    const lines = readFileSync(filePath, 'utf-8').trim().split('\n').filter(Boolean);

    for (let i = 0; i < lines.length; i += INDEX_BATCH_SIZE) {
      const batch = lines.slice(i, i + INDEX_BATCH_SIZE);
      const documents = [];
      const metadatas = [];
      const ids = [];

      for (const line of batch) {
        try {
          const item = JSON.parse(line);

          if (item.confidence && item.confidence < minConfidence) {
            totalSkipped++;
            continue;
          }

          // Build rich document text for embedding
          const docParts = [];
          if (item.title) docParts.push(`Title: ${item.title}`);
          if (item.type) docParts.push(`Type: ${item.type}`);
          if (item.finding) docParts.push(`Finding: ${item.finding}`);
          if (item.description) docParts.push(`Description: ${item.description}`);
          if (item.abstract) docParts.push(`Abstract: ${item.abstract}`);
          if (item.topics && item.topics.length > 0) {
            docParts.push(`Topics: ${item.topics.join(', ')}`);
          }
          if (item.tags && item.tags.length > 0) {
            docParts.push(`Tags: ${item.tags.join(', ')}`);
          }
          const docText = docParts.join('\n');

          if (!docText.trim()) {
            totalSkipped++;
            continue;
          }

          // Build metadata
          const meta = {};
          if (item.id) meta.entry_id = String(item.id);
          if (item.type) meta.type = String(item.type);
          if (item.title) meta.title = String(item.title).slice(0, 500);
          if (item.source) meta.source_name = String(item.source);
          if (item.url) meta.url = String(item.url).slice(0, 500);
          if (item.confidence !== undefined) meta.confidence = Number(item.confidence);
          if (item.relevanceScore !== undefined) meta.relevance_score = Number(item.relevanceScore);
          if (item.topics) meta.topics = item.topics.join(',').slice(0, 500);
          if (item.tags) meta.tags = item.tags.join(',').slice(0, 500);
          if (item.source_tags) meta.source_tags = item.source_tags.join(',').slice(0, 500);
          meta.source = 'web_synthesis';
          meta.source_file = file;
          meta.timestamp = item.timestamp
            ? Math.floor(new Date(item.timestamp).getTime() / 1000)
            : Math.floor(Date.now() / 1000);

          documents.push(docText);
          metadatas.push(meta);
          ids.push(item.id || `ws_${randomUUID()}`);
        } catch (_err) {
          totalErrors++;
        }
      }

      if (documents.length > 0) {
        const result = _chromaExec('upsert', {
          collection: WEB_SYNTHESIS_COLLECTION,
          documents,
          metadatas,
          ids,
        });

        if (result.success !== false) {
          totalIndexed += documents.length;
        } else {
          totalErrors += documents.length;
        }
      }
    }
  }

  return {
    success: totalErrors === 0,
    indexed: totalIndexed,
    skipped: totalSkipped,
    errors: totalErrors,
    files_processed: files.length,
  };
}

// ============================================================================
// SEMANTIC SEARCH
// ============================================================================

/**
 * Semantic search over the disseminator knowledge base.
 *
 * @param {string} query - Natural language query
 * @param {Object} [options]
 * @param {number} [options.limit] - Max results (default: 5)
 * @param {number} [options.minConfidence] - Minimum confidence filter (default: 0.5)
 * @param {string} [options.type] - Filter by entry type
 * @returns {Object[]} Array of { id, title, content, confidence, entities, similarity, metadata }
 */
export async function searchDisseminator(query, options = {}) {
  const { limit = 5, minConfidence = 0.5, type } = options;

  // Build ChromaDB where filter
  const whereConditions = [];
  if (minConfidence > 0) {
    whereConditions.push({ confidence: { '$gte': minConfidence } });
  }
  if (type) {
    whereConditions.push({ type: type });
  }

  const where = whereConditions.length > 1
    ? { '$and': whereConditions }
    : whereConditions.length === 1
      ? whereConditions[0]
      : undefined;

  const result = _chromaExec('query', {
    collection: DISSEMINATOR_COLLECTION,
    query_texts: [query],
    n_results: limit,
    where,
  });

  return _formatSearchResults(result, 'disseminator');
}

/**
 * Semantic search over web synthesis findings.
 *
 * @param {string} query - Natural language query
 * @param {Object} [options]
 * @param {number} [options.limit] - Max results (default: 5)
 * @param {number} [options.minConfidence] - Minimum confidence filter (default: 0.5)
 * @param {string} [options.source] - Filter by source (e.g., 'hackernews', 'arxiv')
 * @returns {Object[]} Array of { id, title, finding, topics, similarity, metadata }
 */
export async function searchWebSynthesis(query, options = {}) {
  const { limit = 5, minConfidence = 0.5, source } = options;

  const whereConditions = [];
  if (minConfidence > 0) {
    whereConditions.push({ confidence: { '$gte': minConfidence } });
  }
  if (source) {
    whereConditions.push({ source_name: source });
  }

  const where = whereConditions.length > 1
    ? { '$and': whereConditions }
    : whereConditions.length === 1
      ? whereConditions[0]
      : undefined;

  const result = _chromaExec('query', {
    collection: WEB_SYNTHESIS_COLLECTION,
    query_texts: [query],
    n_results: limit,
    where,
  });

  return _formatSearchResults(result, 'web_synthesis');
}

/**
 * Unified semantic search across ALL knowledge bases.
 * Searches disseminator and web synthesis in parallel, merges and re-ranks.
 *
 * @param {string} query - Natural language query
 * @param {Object} [options]
 * @param {number} [options.limit] - Max results per source (default: 5)
 * @param {number} [options.minConfidence] - Minimum confidence (default: 0.5)
 * @returns {Object} { disseminator: [...], web_synthesis: [...], total_found }
 */
export async function searchAll(query, options = {}) {
  const { limit = 5, minConfidence = 0.5 } = options;

  const disseminator = await searchDisseminator(query, { limit, minConfidence });
  const webSynthesis = await searchWebSynthesis(query, { limit, minConfidence });

  return {
    query,
    disseminator,
    web_synthesis: webSynthesis,
    total_found: disseminator.length + webSynthesis.length,
  };
}

/**
 * Get the number of indexed entries in each collection.
 *
 * @returns {Object} { disseminator_count, web_synthesis_count }
 */
export async function getIndexStats() {
  const dResult = _chromaExec('count', { collection: DISSEMINATOR_COLLECTION });
  const wResult = _chromaExec('count', { collection: WEB_SYNTHESIS_COLLECTION });

  return {
    disseminator_count: dResult.count || 0,
    web_synthesis_count: wResult.count || 0,
    chroma_dir: CHROMA_KB_DIR,
  };
}

// ============================================================================
// AUTO-INDEX
// ============================================================================

/**
 * Ensure knowledge bases are indexed. Checks if collections exist and have
 * data; if empty, triggers indexing. Designed to be called lazily on first
 * search to avoid blocking startup.
 *
 * @returns {Object} { already_indexed, newly_indexed }
 */
export async function ensureIndexed() {
  const stats = await getIndexStats();
  const result = { already_indexed: false, newly_indexed: false };

  // If both collections have data, assume indexed
  if (stats.disseminator_count > 0 && stats.web_synthesis_count > 0) {
    result.already_indexed = true;
    return result;
  }

  // Index what is missing
  if (stats.disseminator_count === 0 && existsSync(DISSEMINATOR_KB_FILE)) {
    await indexDisseminatorKB();
    result.newly_indexed = true;
  }

  if (stats.web_synthesis_count === 0 && existsSync(RESEARCH_DIR)) {
    await indexWebSynthesis();
    result.newly_indexed = true;
  }

  return result;
}

// ============================================================================
// INTERNAL HELPERS
// ============================================================================

/**
 * Format ChromaDB query results into a clean array.
 */
function _formatSearchResults(result, source) {
  if (!result || result.success === false || !result.ids) {
    return [];
  }

  const ids = result.ids[0] || result.ids || [];
  const documents = result.documents?.[0] || result.documents || [];
  const metadatas = result.metadatas?.[0] || result.metadatas || [];
  const distances = result.distances?.[0] || result.distances || [];

  const formatted = [];
  for (let i = 0; i < ids.length; i++) {
    const distance = distances[i] || 0;
    const similarity = Math.max(0, 1 - distance);
    const meta = metadatas[i] || {};

    const entry = {
      id: ids[i],
      source,
      similarity,
      relevance: similarity,  // Alias for backward compatibility
      document: documents[i] || '',
      metadata: meta,
    };

    // Extract commonly accessed fields from metadata for convenience
    if (meta.title) entry.title = meta.title;
    if (meta.type) entry.type = meta.type;
    if (meta.confidence !== undefined) entry.confidence = meta.confidence;
    if (meta.entities) entry.entities = meta.entities.split(',');
    if (meta.topics) entry.topics = meta.topics.split(',');
    if (meta.url) entry.url = meta.url;
    if (meta.source_file) entry.source_file = meta.source_file;

    formatted.push(entry);
  }

  return formatted;
}

// ============================================================================
// PYTHON BRIDGE SCRIPT
// ============================================================================

const _PYTHON_BRIDGE = `
import sys, json
from pathlib import Path

def main():
    input_file = sys.argv[1]
    with open(input_file) as f:
        req = json.load(f)

    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=req['chroma_dir'],
        settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )

    collection_name = req.get('collection', 'default')
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={'hnsw:space': 'cosine'}
    )

    op = req['operation']
    result = {'success': True}

    if op == 'upsert':
        collection.upsert(
            documents=req['documents'],
            metadatas=req['metadatas'],
            ids=req['ids']
        )
    elif op == 'add':
        collection.add(
            documents=req['documents'],
            metadatas=req['metadatas'],
            ids=req['ids']
        )
    elif op == 'query':
        kwargs = {
            'query_texts': req['query_texts'],
            'n_results': req.get('n_results', 5),
        }
        if req.get('where'):
            kwargs['where'] = req['where']

        qr = collection.query(**kwargs)
        result = {
            'success': True,
            'ids': qr['ids'],
            'documents': qr['documents'],
            'metadatas': qr['metadatas'],
            'distances': qr['distances']
        }
    elif op == 'count':
        result = {'success': True, 'count': collection.count()}
    elif op == 'delete':
        collection.delete(ids=req['ids'])
    elif op == 'get':
        gr = collection.get(ids=req['ids'])
        result = {
            'success': True,
            'ids': gr['ids'],
            'documents': gr['documents'],
            'metadatas': gr['metadatas']
        }
    else:
        result = {'success': False, 'error': f'Unknown operation: {op}'}

    if 'output_file' in req:
        with open(req['output_file'], 'w') as f:
            json.dump(result, f)

if __name__ == '__main__':
    main()
`;

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  isAvailable,
  indexDisseminatorKB,
  indexWebSynthesis,
  searchDisseminator,
  searchWebSynthesis,
  searchAll,
  getIndexStats,
  ensureIndexed,
};
