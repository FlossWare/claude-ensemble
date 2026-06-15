/**
 * Vector Search Module - Semantic search using ChromaDB embeddings
 *
 * Replaces naive substring matching with semantic vector search.
 * Integrates with claude-learning-integration.js for intelligent knowledge retrieval.
 *
 * Features:
 * - ChromaDB persistent vector storage
 * - Automatic embedding generation via ChromaDB's default embedder
 * - Semantic similarity search (finds lexically different but semantically similar content)
 * - Collection-based indexing (disseminator, web-synthesis, decisions)
 * - Fallback to substring matching if ChromaDB unavailable
 *
 * Usage:
 *   import { initializeVectorStore, semanticSearch, indexKnowledgeBase } from './learning/vector-search.js';
 *
 *   // Initialize (creates/connects to ChromaDB)
 *   await initializeVectorStore();
 *
 *   // Index knowledge base
 *   await indexKnowledgeBase('disseminator', items);
 *
 *   // Semantic search
 *   const results = await semanticSearch('async error handling', {
 *     collections: ['disseminator', 'web-synthesis'],
 *     limit: 5,
 *     minConfidence: 0.5
 *   });
 */

import { existsSync, readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const CHROMA_PATH = join(HOME, '.claude', 'chroma');
const LEARNING_DIR = join(HOME, '.claude', 'learning');

// Collection names for different knowledge bases
const COLLECTIONS = {
  DISSEMINATOR: 'disseminator-knowledge',
  WEB_SYNTHESIS: 'web-synthesis',
  DECISIONS: 'decisions-log',
  META_LEARNINGS: 'meta-learnings',
};

// Cache for ChromaDB availability check
let chromaAvailable = null;
let chromaClient = null;

// ============================================================================
// CHROMADB INITIALIZATION
// ============================================================================

/**
 * Check if ChromaDB is available and can be used.
 * Caches result to avoid repeated checks.
 *
 * @returns {Promise<boolean>} True if ChromaDB is available
 */
async function isChromaAvailable() {
  if (chromaAvailable !== null) {
    return chromaAvailable;
  }

  try {
    // Try to import chromadb
    const chromadb = await import('chromadb');
    chromaAvailable = true;
    return true;
  } catch (err) {
    console.warn('[vector-search] ChromaDB not available:', err.message);
    console.warn('[vector-search] Install with: npm install chromadb');
    console.warn('[vector-search] Falling back to substring matching');
    chromaAvailable = false;
    return false;
  }
}

/**
 * Initialize ChromaDB client and ensure collections exist.
 * Creates persistent storage in ~/.claude/chroma
 *
 * @returns {Promise<Object>} ChromaDB client or null if unavailable
 */
export async function initializeVectorStore() {
  if (!await isChromaAvailable()) {
    return null;
  }

  if (chromaClient) {
    return chromaClient;
  }

  try {
    const { ChromaClient } = await import('chromadb');

    // Create client with persistent storage
    chromaClient = new ChromaClient({
      path: CHROMA_PATH,
    });

    console.log(`[vector-search] Initialized ChromaDB at ${CHROMA_PATH}`);

    // Ensure collections exist
    for (const [name, collectionName] of Object.entries(COLLECTIONS)) {
      try {
        await chromaClient.getOrCreateCollection({
          name: collectionName,
          metadata: { description: `Claude learning integration - ${name}` },
        });
      } catch (err) {
        console.warn(`[vector-search] Could not create collection ${collectionName}:`, err.message);
      }
    }

    return chromaClient;
  } catch (err) {
    console.error('[vector-search] Failed to initialize ChromaDB:', err.message);
    chromaAvailable = false;
    chromaClient = null;
    return null;
  }
}

// ============================================================================
// INDEXING - Add documents to vector store
// ============================================================================

/**
 * Index items into a ChromaDB collection.
 * Automatically generates embeddings for semantic search.
 *
 * @param {string} collectionName - Name of collection to index into
 * @param {Array<Object>} items - Items to index
 * @param {Object} options - Indexing options
 * @param {Function} options.textExtractor - Function to extract searchable text from item
 * @param {Function} options.metadataExtractor - Function to extract metadata from item
 * @param {Function} options.idExtractor - Function to generate unique ID from item
 * @returns {Promise<Object>} Indexing result
 */
export async function indexKnowledgeBase(collectionName, items, options = {}) {
  const client = await initializeVectorStore();
  if (!client) {
    return {
      success: false,
      indexed_count: 0,
      error: 'ChromaDB not available',
    };
  }

  const {
    textExtractor = _defaultTextExtractor,
    metadataExtractor = _defaultMetadataExtractor,
    idExtractor = _defaultIdExtractor,
  } = options;

  try {
    const collection = await client.getOrCreateCollection({
      name: collectionName,
      metadata: { last_indexed: new Date().toISOString() },
    });

    const documents = [];
    const metadatas = [];
    const ids = [];

    for (const item of items) {
      try {
        const text = textExtractor(item);
        const metadata = metadataExtractor(item);
        const id = idExtractor(item, items.indexOf(item));

        if (!text || !id) continue;

        documents.push(text);
        metadatas.push(metadata);
        ids.push(id);
      } catch (err) {
        console.warn('[vector-search] Error extracting item data:', err.message);
      }
    }

    if (documents.length === 0) {
      return {
        success: false,
        indexed_count: 0,
        error: 'No valid documents to index',
      };
    }

    // Upsert to collection (ChromaDB generates embeddings automatically)
    await collection.upsert({
      documents,
      metadatas,
      ids,
    });

    const count = await collection.count();

    console.log(`[vector-search] Indexed ${documents.length} items into ${collectionName}`);
    console.log(`[vector-search] Total items in collection: ${count}`);

    return {
      success: true,
      indexed_count: documents.length,
      total_items: count,
      collection_name: collectionName,
    };
  } catch (err) {
    console.error('[vector-search] Indexing error:', err.message);
    return {
      success: false,
      indexed_count: 0,
      error: err.message,
    };
  }
}

/**
 * Default text extractor - creates searchable text from common item structures
 */
function _defaultTextExtractor(item) {
  const parts = [];

  if (item.title) parts.push(`Title: ${item.title}`);
  if (item.name) parts.push(`Name: ${item.name}`);
  if (item.description) parts.push(`Description: ${item.description}`);
  if (item.content) parts.push(`Content: ${item.content}`);
  if (item.finding) parts.push(`Finding: ${item.finding}`);
  if (item.decision) parts.push(`Decision: ${item.decision}`);

  if (item.entities && Array.isArray(item.entities)) {
    parts.push(`Entities: ${item.entities.join(', ')}`);
  }

  if (item.topics && Array.isArray(item.topics)) {
    parts.push(`Topics: ${item.topics.join(', ')}`);
  }

  if (item.tags && Array.isArray(item.tags)) {
    parts.push(`Tags: ${item.tags.join(', ')}`);
  }

  return parts.join('\n').trim();
}

/**
 * Default metadata extractor - preserves key fields as searchable metadata
 */
function _defaultMetadataExtractor(item) {
  const metadata = {};

  // String fields (ChromaDB requires string values for metadata)
  const stringFields = [
    'title', 'name', 'type', 'source', 'task_type',
    'model_used', 'outcome', 'confidence', 'source_file'
  ];

  for (const field of stringFields) {
    if (item[field] !== undefined && item[field] !== null) {
      metadata[field] = String(item[field]);
    }
  }

  // Timestamp
  if (item.timestamp) {
    metadata.timestamp = String(item.timestamp);
  }

  // Arrays as comma-separated strings
  if (item.topics && Array.isArray(item.topics)) {
    metadata.topics = item.topics.slice(0, 10).join(',');
  }

  if (item.entities && Array.isArray(item.entities)) {
    metadata.entities = item.entities.slice(0, 10).join(',');
  }

  if (item.tags && Array.isArray(item.tags)) {
    metadata.tags = item.tags.slice(0, 10).join(',');
  }

  // Truncate long string fields to avoid ChromaDB metadata size limits
  for (const [key, value] of Object.entries(metadata)) {
    if (typeof value === 'string' && value.length > 500) {
      metadata[key] = value.substring(0, 497) + '...';
    }
  }

  return metadata;
}

/**
 * Default ID extractor - generates stable IDs from item content
 */
function _defaultIdExtractor(item, index) {
  // Use existing ID if available
  if (item.id) return String(item.id);

  // Generate from timestamp + title/name
  if (item.timestamp && (item.title || item.name)) {
    const base = `${item.timestamp}-${item.title || item.name}`;
    return _hashString(base);
  }

  // Generate from content hash
  if (item.content) {
    return _hashString(item.content);
  }

  // Fallback to index-based ID
  return `item-${index}-${Date.now()}`;
}

/**
 * Simple hash function for generating stable IDs
 */
function _hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash).toString(36);
}

// ============================================================================
// SEMANTIC SEARCH
// ============================================================================

/**
 * Perform semantic search across knowledge bases using vector embeddings.
 * Finds semantically similar content even with different wording.
 *
 * Example: Query "async error handling" will find "promise rejection patterns"
 *
 * @param {string} query - Natural language search query
 * @param {Object} options - Search options
 * @param {string[]} options.collections - Collections to search (default: all)
 * @param {number} options.limit - Max results per collection (default: 5)
 * @param {number} options.minConfidence - Minimum similarity score (default: 0.5)
 * @returns {Promise<Object>} Search results from all collections
 */
export async function semanticSearch(query, options = {}) {
  const {
    collections = Object.values(COLLECTIONS),
    limit = 5,
    minConfidence = 0.5,
  } = options;

  const client = await initializeVectorStore();
  if (!client) {
    // Fallback to substring matching
    console.warn('[vector-search] ChromaDB unavailable, using substring fallback');
    return _substringSearchFallback(query, { limit, minConfidence });
  }

  const results = {
    query,
    method: 'semantic',
    total_found: 0,
  };

  try {
    for (const collectionName of collections) {
      try {
        const collection = await client.getCollection({ name: collectionName });

        // Query ChromaDB with semantic similarity
        const queryResults = await collection.query({
          queryTexts: [query],
          nResults: limit,
        });

        // Transform results to consistent format
        const items = [];
        if (queryResults.documents && queryResults.documents[0]) {
          for (let i = 0; i < queryResults.documents[0].length; i++) {
            const distance = queryResults.distances?.[0]?.[i];
            const metadata = queryResults.metadatas?.[0]?.[i] || {};
            const document = queryResults.documents[0][i];

            // Convert distance to similarity score (0-1, higher is better)
            // ChromaDB returns L2 distance, smaller is more similar
            const similarity = 1 / (1 + (distance || 0));

            // Skip low-confidence results
            if (similarity < minConfidence) continue;

            items.push({
              document,
              metadata,
              similarity,
              confidence: similarity,
              id: queryResults.ids?.[0]?.[i],
            });
          }
        }

        // Map collection name to result key
        const resultKey = _collectionToResultKey(collectionName);
        results[resultKey] = items;
        results.total_found += items.length;

        console.log(`[vector-search] Found ${items.length} results in ${collectionName}`);
      } catch (err) {
        console.warn(`[vector-search] Could not search collection ${collectionName}:`, err.message);
        const resultKey = _collectionToResultKey(collectionName);
        results[resultKey] = [];
      }
    }

    return results;
  } catch (err) {
    console.error('[vector-search] Search error:', err.message);
    return {
      query,
      method: 'semantic',
      total_found: 0,
      error: err.message,
    };
  }
}

/**
 * Map collection names to result keys for backward compatibility
 */
function _collectionToResultKey(collectionName) {
  const mapping = {
    [COLLECTIONS.DISSEMINATOR]: 'disseminator',
    [COLLECTIONS.WEB_SYNTHESIS]: 'web_synthesis',
    [COLLECTIONS.DECISIONS]: 'decisions',
    [COLLECTIONS.META_LEARNINGS]: 'meta_learnings',
  };
  return mapping[collectionName] || collectionName;
}

// ============================================================================
// FALLBACK - Substring matching when ChromaDB unavailable
// ============================================================================

/**
 * Fallback to naive substring matching when ChromaDB is unavailable.
 * This is the original implementation - kept for compatibility.
 *
 * @param {string} query - Search query
 * @param {Object} options - Search options
 * @returns {Promise<Object>} Search results
 */
async function _substringSearchFallback(query, options = {}) {
  const { limit = 5, minConfidence = 0.5 } = options;

  const results = {
    query,
    method: 'substring-fallback',
    disseminator: [],
    web_synthesis: [],
    total_found: 0,
  };

  const queryLower = query.toLowerCase();

  // Search disseminator knowledge base
  const disseminatorPath = join(LEARNING_DIR, 'disseminator-knowledge.jsonl');
  if (existsSync(disseminatorPath)) {
    results.disseminator = _searchJSONL(disseminatorPath, queryLower, limit, minConfidence);
  }

  // Search web synthesis
  const researchDir = join(LEARNING_DIR, 'research');
  if (existsSync(researchDir)) {
    const files = readdirSync(researchDir)
      .filter(f => f.startsWith('web-synthesis-') && f.endsWith('.jsonl'));

    const allMatches = [];
    for (const file of files) {
      const matches = _searchJSONL(join(researchDir, file), queryLower, limit * 2, minConfidence);
      allMatches.push(...matches.map(m => ({ ...m, source_file: file })));
    }

    results.web_synthesis = allMatches
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, limit);
  }

  results.total_found = results.disseminator.length + results.web_synthesis.length;

  return results;
}

/**
 * Search a JSONL file using substring matching
 */
function _searchJSONL(filePath, queryLower, limit, minConfidence) {
  try {
    const lines = readFileSync(filePath, 'utf-8').trim().split('\n').filter(Boolean);
    const matches = [];

    for (const line of lines) {
      try {
        const item = JSON.parse(line);

        // Skip low-confidence items
        if (item.confidence && item.confidence < minConfidence) continue;

        // Substring matching
        const titleMatch = item.title?.toLowerCase().includes(queryLower);
        const contentMatch = item.content?.toLowerCase().includes(queryLower);
        const findingMatch = item.finding?.toLowerCase().includes(queryLower);
        const entityMatch = item.entities?.some(e => e.toLowerCase().includes(queryLower));
        const topicMatch = item.topics?.some(t => t.toLowerCase().includes(queryLower));

        if (titleMatch || contentMatch || findingMatch || entityMatch || topicMatch) {
          matches.push({
            ...item,
            relevance: (titleMatch ? 0.5 : 0) +
                      (contentMatch ? 0.3 : 0) +
                      (findingMatch ? 0.3 : 0) +
                      (entityMatch ? 0.2 : 0) +
                      (topicMatch ? 0.2 : 0),
          });
        }
      } catch (_err) {
        // Skip malformed lines
      }
    }

    return matches
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, limit);
  } catch (err) {
    console.warn(`[vector-search] Error searching ${filePath}:`, err.message);
    return [];
  }
}

// ============================================================================
// AUTO-INDEXING - Index knowledge bases on startup/update
// ============================================================================

/**
 * Auto-index all knowledge bases found in learning directory.
 * Called on startup or when knowledge bases are updated.
 *
 * @returns {Promise<Object>} Indexing summary
 */
export async function autoIndexKnowledgeBases() {
  const client = await initializeVectorStore();
  if (!client) {
    console.log('[vector-search] ChromaDB not available, skipping auto-indexing');
    return { success: false, error: 'ChromaDB not available' };
  }

  const summary = {
    success: true,
    indexed: {},
    errors: [],
  };

  try {
    // Index disseminator knowledge
    const disseminatorPath = join(LEARNING_DIR, 'disseminator-knowledge.jsonl');
    if (existsSync(disseminatorPath)) {
      const items = _loadJSONL(disseminatorPath);
      const result = await indexKnowledgeBase(COLLECTIONS.DISSEMINATOR, items);
      summary.indexed[COLLECTIONS.DISSEMINATOR] = result.indexed_count;
      if (!result.success) summary.errors.push(result.error);
    }

    // Index web synthesis
    const researchDir = join(LEARNING_DIR, 'research');
    if (existsSync(researchDir)) {
      const files = readdirSync(researchDir)
        .filter(f => f.startsWith('web-synthesis-') && f.endsWith('.jsonl'));

      const allItems = [];
      for (const file of files) {
        const items = _loadJSONL(join(researchDir, file));
        allItems.push(...items.map(item => ({ ...item, source_file: file })));
      }

      if (allItems.length > 0) {
        const result = await indexKnowledgeBase(COLLECTIONS.WEB_SYNTHESIS, allItems);
        summary.indexed[COLLECTIONS.WEB_SYNTHESIS] = result.indexed_count;
        if (!result.success) summary.errors.push(result.error);
      }
    }

    // Index decisions log
    const decisionsPath = join(LEARNING_DIR, 'decisions.jsonl');
    if (existsSync(decisionsPath)) {
      const items = _loadJSONL(decisionsPath);
      const result = await indexKnowledgeBase(COLLECTIONS.DECISIONS, items);
      summary.indexed[COLLECTIONS.DECISIONS] = result.indexed_count;
      if (!result.success) summary.errors.push(result.error);
    }

    // Index meta-learnings
    const metaPath = join(LEARNING_DIR, 'meta-learnings.jsonl');
    if (existsSync(metaPath)) {
      const items = _loadJSONL(metaPath);
      const result = await indexKnowledgeBase(COLLECTIONS.META_LEARNINGS, items);
      summary.indexed[COLLECTIONS.META_LEARNINGS] = result.indexed_count;
      if (!result.success) summary.errors.push(result.error);
    }

    console.log('[vector-search] Auto-indexing complete:', summary);
    return summary;
  } catch (err) {
    console.error('[vector-search] Auto-indexing error:', err.message);
    return {
      success: false,
      error: err.message,
      indexed: summary.indexed,
    };
  }
}

/**
 * Load items from a JSONL file
 */
function _loadJSONL(filePath) {
  try {
    const lines = readFileSync(filePath, 'utf-8').trim().split('\n').filter(Boolean);
    return lines
      .map(line => {
        try {
          return JSON.parse(line);
        } catch (_err) {
          return null;
        }
      })
      .filter(Boolean);
  } catch (err) {
    console.warn(`[vector-search] Error loading ${filePath}:`, err.message);
    return [];
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
  initializeVectorStore,
  indexKnowledgeBase,
  semanticSearch,
  autoIndexKnowledgeBases,
  COLLECTIONS,
};
