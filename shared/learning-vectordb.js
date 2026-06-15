/**
 * VectorDB Wrapper - Semantic task matching via ChromaDB
 *
 * JavaScript wrapper that delegates to the Python ChromaDB backend for
 * semantic similarity search over task embeddings. Supports:
 *   - Adding completed task embeddings with rich metadata
 *   - Semantic search (pure, filtered, hybrid relevance)
 *   - Cost-optimized lookups (find cheaper successful patterns)
 *   - Failure analysis (find similar failed tasks to learn from)
 *   - Pruning old/low-quality embeddings
 *
 * Architecture:
 *   This module spawns Python subprocesses for ChromaDB operations since
 *   ChromaDB has no native Node.js client. Operations are batched and
 *   cached to minimize subprocess overhead.
 *
 * Collection: task_embeddings
 * Embedding model: all-MiniLM-L6-v2 (384-dim, cosine distance)
 * Storage: ~/.claude/learning/db/chroma/
 *
 * Usage (ESM):
 *   import { addTask, searchSimilar, searchFiltered, close } from './shared/learning-vectordb.js';
 *
 *   // Add a completed task
 *   await addTask({
 *     taskId: 'task_123',
 *     taskType: 'code_review',
 *     description: 'Review auth module for security vulnerabilities',
 *     directory: '/src/auth',
 *     models: ['opus', 'sonnet', 'haiku'],
 *     arbiter: 'fable',
 *     quality: 0.92,
 *     cost: 0.15,
 *     outcome: 'success',
 *   });
 *
 *   // Find similar tasks
 *   const similar = await searchSimilar('Fix auth bypass vulnerability', 5);
 *
 *   // Find similar successful tasks that were cheap
 *   const cheap = await searchCostOptimized('Fix auth bypass', 0.10, 5);
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdirSync, writeFileSync, readFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const CHROMA_DIR = join(HOME, '.claude', 'learning', 'db', 'chroma');
const COLLECTION_NAME = 'task_embeddings';
const EMBEDDING_MODEL = 'all-MiniLM-L6-v2';
const MAX_EMBEDDINGS = 10000;
const PRUNING_AGE_DAYS = 180;
const PYTHON = process.env.PYTHON_PATH || 'python3';
const TIMEOUT_MS = 30000;

// ============================================================================
// PYTHON BRIDGE
// ============================================================================

/**
 * Execute a ChromaDB operation via Python subprocess.
 * Passes input as JSON via a temp file to avoid argument length limits.
 */
function _chromaExec(operation, payload) {
  const tmpIn = join(CHROMA_DIR, `.tmp_${randomUUID()}.json`);
  const tmpOut = join(CHROMA_DIR, `.tmp_${randomUUID()}.json`);

  try {
    if (!existsSync(CHROMA_DIR)) {
      mkdirSync(CHROMA_DIR, { recursive: true });
    }

    const request = {
      operation,
      collection: COLLECTION_NAME,
      chroma_dir: CHROMA_DIR,
      embedding_model: EMBEDDING_MODEL,
      output_file: tmpOut,
      ...payload,
    };

    writeFileSync(tmpIn, JSON.stringify(request));

    execFileSync(PYTHON, ['-c', _PYTHON_BRIDGE, tmpIn], {
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
    if (process.env.LEARNING_DEBUG) {
      console.error(`[learning-vectordb] ChromaDB ${operation} failed: ${err.message}`);
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
// DOCUMENT FORMATTING
// ============================================================================

/**
 * Build the document text that gets embedded.
 * Includes key metadata fields in the text for richer semantic matching.
 */
function _buildDocumentText(data) {
  const parts = [];

  if (data.taskType) parts.push(`task_type: ${data.taskType}`);
  if (data.description) parts.push(`Description: ${data.description}`);
  if (data.directory) {
    // Normalize: remove user-specific prefix
    const normalized = data.directory.replace(/^\/home\/[^/]+\//, '~/');
    parts.push(`Directory: ${normalized}`);
  }
  if (data.complexity) parts.push(`Complexity: ${data.complexity}`);
  if (data.outcome) parts.push(`Outcome: ${data.outcome}`);

  return parts.join('\n');
}

/**
 * Build metadata dict for ChromaDB storage.
 */
function _buildMetadata(data) {
  const meta = {};

  if (data.taskId) meta.task_id = String(data.taskId);
  if (data.taskType) meta.task_type = String(data.taskType);
  if (data.directory) meta.directory = String(data.directory);
  if (data.fileExtensions) {
    meta.file_extensions = Array.isArray(data.fileExtensions)
      ? data.fileExtensions.join(',')
      : String(data.fileExtensions);
  }
  if (data.complexity) meta.complexity = String(data.complexity);
  if (data.models) {
    meta.models_used = Array.isArray(data.models)
      ? data.models.join(',')
      : String(data.models);
  }
  if (data.arbiter) meta.arbiter_model = String(data.arbiter);
  if (data.workerCount !== undefined) meta.worker_count = Number(data.workerCount);
  if (data.strategy) meta.consensus_strategy = String(data.strategy);
  if (data.quality !== undefined) meta.quality_score = Number(data.quality);
  if (data.cost !== undefined) meta.cost_usd = Number(data.cost);
  if (data.durationSeconds !== undefined) meta.duration_seconds = Number(data.durationSeconds);
  if (data.outcome) meta.outcome = String(data.outcome);
  if (data.toolsUsed) {
    meta.tools_used = Array.isArray(data.toolsUsed)
      ? data.toolsUsed.join(',')
      : String(data.toolsUsed);
  }
  if (data.dependencies) {
    meta.dependencies = Array.isArray(data.dependencies)
      ? data.dependencies.join(',')
      : String(data.dependencies);
  }
  if (data.tags) {
    meta.tags = Array.isArray(data.tags)
      ? data.tags.join(',')
      : String(data.tags);
  }

  // Always include timestamp
  meta.timestamp = data.timestamp || Math.floor(Date.now() / 1000);

  return meta;
}

// ============================================================================
// PUBLIC API - WRITE OPERATIONS
// ============================================================================

/**
 * Add a completed task embedding to the vector store.
 *
 * @param {Object} data - Task data
 * @param {string} data.taskId - Unique task identifier
 * @param {string} data.taskType - Category: code_review, bug_fix, feature_add, etc.
 * @param {string} data.description - What the task did
 * @param {string} [data.directory] - Primary directory path
 * @param {string[]} [data.fileExtensions] - File types involved
 * @param {string} [data.complexity] - low, medium, high, critical
 * @param {string[]} [data.models] - Models used
 * @param {string} [data.arbiter] - Arbiter model
 * @param {number} [data.workerCount] - Number of workers
 * @param {string} [data.strategy] - Consensus strategy
 * @param {number} [data.quality] - Quality score 0.0-1.0
 * @param {number} [data.cost] - Total cost USD
 * @param {number} [data.durationSeconds] - Execution time
 * @param {string} [data.outcome] - success, partial, failed
 * @param {string[]} [data.toolsUsed] - Tools used
 * @param {string[]} [data.tags] - User-defined tags
 * @returns {Object} { success, id } or { success: false, error }
 */
export async function addTask(data) {
  const taskId = data.taskId || `task_${randomUUID()}`;
  const documentText = _buildDocumentText(data);
  const metadata = _buildMetadata(data);

  const result = _chromaExec('add', {
    documents: [documentText],
    metadatas: [metadata],
    ids: [taskId],
  });

  if (result.success !== false) {
    return { success: true, id: taskId };
  }
  return result;
}

/**
 * Add multiple task embeddings in batch.
 *
 * @param {Object[]} tasks - Array of task data objects (same shape as addTask)
 * @returns {Object} { success, ids } or { success: false, error }
 */
export async function addTaskBatch(tasks) {
  const documents = [];
  const metadatas = [];
  const ids = [];

  for (const data of tasks) {
    const taskId = data.taskId || `task_${randomUUID()}`;
    documents.push(_buildDocumentText(data));
    metadatas.push(_buildMetadata(data));
    ids.push(taskId);
  }

  const result = _chromaExec('add', { documents, metadatas, ids });

  if (result.success !== false) {
    return { success: true, ids };
  }
  return result;
}

/**
 * Update metadata for an existing task embedding.
 *
 * @param {string} taskId - Task ID to update
 * @param {Object} metadata - Metadata fields to update
 * @returns {Object} { success } or { success: false, error }
 */
export async function updateTask(taskId, metadata) {
  return _chromaExec('update', {
    ids: [taskId],
    metadatas: [metadata],
  });
}

/**
 * Delete a task embedding.
 *
 * @param {string} taskId - Task ID to delete
 * @returns {Object} { success } or { success: false, error }
 */
export async function deleteTask(taskId) {
  return _chromaExec('delete', { ids: [taskId] });
}

// ============================================================================
// PUBLIC API - SEARCH OPERATIONS
// ============================================================================

/**
 * Pure semantic search across all tasks.
 *
 * @param {string} queryText - Natural language query
 * @param {number} [topK=5] - Number of results
 * @returns {Object[]} Array of { id, document, metadata, distance, similarity }
 */
export async function searchSimilar(queryText, topK = 5) {
  const result = _chromaExec('query', {
    query_texts: [queryText],
    n_results: topK,
  });

  return _formatResults(result);
}

/**
 * Semantic search with metadata filters.
 *
 * @param {string} queryText - Natural language query
 * @param {Object} where - ChromaDB metadata filter
 * @param {number} [topK=5] - Number of results
 * @returns {Object[]} Array of { id, document, metadata, distance, similarity }
 */
export async function searchFiltered(queryText, where, topK = 5) {
  const result = _chromaExec('query', {
    query_texts: [queryText],
    where,
    n_results: topK,
  });

  return _formatResults(result);
}

/**
 * Find similar tasks that were completed successfully with high quality.
 *
 * @param {string} queryText - Task description
 * @param {string} [taskType] - Optional task type filter
 * @param {number} [minQuality=0.7] - Minimum quality score
 * @param {number} [topK=5] - Number of results
 * @returns {Object[]} Results sorted by relevance
 */
export async function searchHighQuality(queryText, taskType, minQuality = 0.7, topK = 5) {
  const where = {
    '$and': [
      { outcome: 'success' },
      { quality_score: { '$gte': minQuality } },
    ],
  };

  if (taskType) {
    where['$and'].push({ task_type: taskType });
  }

  return searchFiltered(queryText, where, topK);
}

/**
 * Find similar tasks that used cheaper models successfully.
 *
 * @param {string} queryText - Task description
 * @param {number} maxCost - Maximum cost in USD
 * @param {number} [topK=10] - Number of results
 * @returns {Object[]} Results sorted by relevance
 */
export async function searchCostOptimized(queryText, maxCost, topK = 10) {
  return searchFiltered(queryText, {
    '$and': [
      { outcome: 'success' },
      { cost_usd: { '$lt': maxCost } },
    ],
  }, topK);
}

/**
 * Find similar failed tasks to learn from mistakes.
 *
 * @param {string} queryText - Task description
 * @param {number} [topK=20] - Number of results
 * @returns {Object[]} Failed tasks similar to the query
 */
export async function searchFailures(queryText, topK = 20) {
  return searchFiltered(queryText, { outcome: 'failed' }, topK);
}

/**
 * Find tasks in the same directory context.
 *
 * @param {string} queryText - Task description
 * @param {string} directory - Directory path to match
 * @param {number} [topK=10] - Number of results
 * @returns {Object[]} Results from the same directory
 */
export async function searchByDirectory(queryText, directory, topK = 10) {
  return searchFiltered(queryText, { directory }, topK);
}

/**
 * Hybrid relevance search: semantic similarity + metadata scoring.
 * Applies boosts for task_type match, directory overlap, high quality, and recency.
 *
 * @param {string} queryText - Natural language query
 * @param {Object} context - Current task context
 * @param {string} [context.taskType] - Current task type
 * @param {string} [context.directory] - Current directory
 * @param {number} [topK=10] - Number of initial candidates
 * @param {number} [finalK=5] - Number of final results after reranking
 * @returns {Object[]} Reranked results with hybrid scores
 */
export async function searchHybrid(queryText, context = {}, topK = 10, finalK = 5) {
  // Get more candidates than needed for reranking
  const candidates = await searchSimilar(queryText, topK);

  if (candidates.length === 0) return [];

  const now = Math.floor(Date.now() / 1000);
  const ninetyDaysAgo = now - 90 * 24 * 60 * 60;

  // Score each candidate with hybrid relevance
  const scored = candidates.map(result => {
    let hybridScore = result.similarity || (1 - (result.distance || 0));

    // Task type match bonus (+0.2)
    if (context.taskType && result.metadata?.task_type === context.taskType) {
      hybridScore += 0.2;
    }

    // Directory overlap bonus (+0.15)
    if (context.directory && result.metadata?.directory) {
      if (result.metadata.directory.startsWith(context.directory) ||
          context.directory.startsWith(result.metadata.directory)) {
        hybridScore += 0.15;
      }
    }

    // High quality bonus (+0.1)
    if (result.metadata?.quality_score && result.metadata.quality_score >= 0.8) {
      hybridScore += 0.1;
    }

    // Recency bonus (+0.1 for tasks < 90 days old)
    if (result.metadata?.timestamp && result.metadata.timestamp > ninetyDaysAgo) {
      hybridScore += 0.1;
    }

    return { ...result, hybridScore };
  });

  // Sort by hybrid score and return top finalK
  scored.sort((a, b) => b.hybridScore - a.hybridScore);
  return scored.slice(0, finalK);
}

// ============================================================================
// PUBLIC API - MANAGEMENT
// ============================================================================

/**
 * Get the total number of embeddings in the collection.
 */
export async function count() {
  const result = _chromaExec('count', {});
  return result.count || 0;
}

/**
 * Get a task embedding by ID.
 *
 * @param {string} taskId - Task ID
 * @returns {Object|null} { id, document, metadata } or null
 */
export async function getTask(taskId) {
  const result = _chromaExec('get', { ids: [taskId] });

  if (result.ids && result.ids.length > 0) {
    return {
      id: result.ids[0],
      document: result.documents?.[0] || '',
      metadata: result.metadatas?.[0] || {},
    };
  }
  return null;
}

/**
 * Prune old, low-quality embeddings to stay under MAX_EMBEDDINGS.
 * Removes tasks with quality_score < threshold that are older than PRUNING_AGE_DAYS.
 *
 * @param {number} [qualityThreshold=0.5] - Remove items below this quality
 * @returns {Object} { pruned, remaining }
 */
export async function prune(qualityThreshold = 0.5) {
  const cutoffTimestamp = Math.floor(Date.now() / 1000) - PRUNING_AGE_DAYS * 24 * 60 * 60;

  const result = _chromaExec('prune', {
    quality_threshold: qualityThreshold,
    cutoff_timestamp: cutoffTimestamp,
    max_embeddings: MAX_EMBEDDINGS,
  });

  return {
    pruned: result.pruned || 0,
    remaining: result.remaining || 0,
  };
}

/**
 * Check if ChromaDB is available (Python + chromadb installed).
 */
export function isAvailable() {
  try {
    execFileSync(PYTHON, ['-c', 'import chromadb; print("ok")'], {
      timeout: 5000,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return true;
  } catch (_err) {
    return false;
  }
}

// ============================================================================
// INTERNAL HELPERS
// ============================================================================

function _formatResults(result) {
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
    formatted.push({
      id: ids[i],
      document: documents[i] || '',
      metadata: metadatas[i] || {},
      distance,
      similarity: 1 - distance,
    });
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

    collection = client.get_or_create_collection(
        name=req['collection'],
        metadata={'hnsw:space': 'cosine'}
    )

    op = req['operation']
    result = {'success': True}

    if op == 'add':
        collection.add(
            documents=req['documents'],
            metadatas=req['metadatas'],
            ids=req['ids']
        )
    elif op == 'update':
        collection.update(
            ids=req['ids'],
            metadatas=req.get('metadatas'),
            documents=req.get('documents')
        )
    elif op == 'delete':
        collection.delete(ids=req['ids'])
    elif op == 'query':
        qr = collection.query(
            query_texts=req['query_texts'],
            n_results=req.get('n_results', 5),
            where=req.get('where')
        )
        result = {
            'success': True,
            'ids': qr['ids'],
            'documents': qr['documents'],
            'metadatas': qr['metadatas'],
            'distances': qr['distances']
        }
    elif op == 'get':
        gr = collection.get(ids=req['ids'])
        result = {
            'success': True,
            'ids': gr['ids'],
            'documents': gr['documents'],
            'metadatas': gr['metadatas']
        }
    elif op == 'count':
        result = {'success': True, 'count': collection.count()}
    elif op == 'prune':
        qt = req.get('quality_threshold', 0.5)
        ct = req.get('cutoff_timestamp', 0)
        mx = req.get('max_embeddings', 10000)

        total = collection.count()
        if total <= mx:
            result = {'success': True, 'pruned': 0, 'remaining': total}
        else:
            # Get all items with low quality and old timestamp
            all_items = collection.get(include=['metadatas'])
            to_delete = []
            for i, meta in enumerate(all_items['metadatas']):
                qs = meta.get('quality_score', 1.0)
                ts = meta.get('timestamp', 9999999999)
                if qs < qt and ts < ct:
                    to_delete.append(all_items['ids'][i])

            if to_delete:
                collection.delete(ids=to_delete)

            remaining = collection.count()
            result = {
                'success': True,
                'pruned': len(to_delete),
                'remaining': remaining
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
  addTask,
  addTaskBatch,
  updateTask,
  deleteTask,
  searchSimilar,
  searchFiltered,
  searchHighQuality,
  searchCostOptimized,
  searchFailures,
  searchByDirectory,
  searchHybrid,
  count,
  getTask,
  prune,
  isAvailable,
};
