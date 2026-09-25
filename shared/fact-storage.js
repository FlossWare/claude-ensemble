/**
 * Fact Storage Adapter
 *
 * Persistent storage for structured facts extracted from documents.
 * Stores subject-predicate-object triples with semantic embeddings for
 * similarity search, enabling knowledge graph traversal and fact retrieval.
 *
 * Architecture:
 * - PostgreSQL: Structured fact storage (SPO triples, provenance, metadata)
 * - pgvector: 1024-dim embeddings (all-mpnet-base-v2) for semantic similarity
 * - LLM-based extraction: Uses fleet models to extract facts from documents
 *
 * Database: PostgreSQL on aio-01:5433 (learning database)
 * Schema: facts.facts
 *
 * Usage:
 *   import { getFactStorage } from './shared/fact-storage.js';
 *   const fs = getFactStorage();
 *
 *   // Extract facts from a document
 *   const facts = await fs.extractFacts('doc-123', documentText, {
 *     domain: 'networking',
 *     model: 'sonnet'
 *   });
 *
 *   // Store a single fact manually
 *   const id = await fs.storeFact({
 *     document_id: 'doc-123',
 *     fact_text: 'PostgreSQL supports vector similarity search via pgvector',
 *     subject: 'PostgreSQL',
 *     predicate: 'supports',
 *     object: 'vector similarity search via pgvector'
 *   });
 *
 *   // Semantic search
 *   const results = await fs.searchFacts('database performance', { limit: 10 });
 *
 *   // Knowledge graph traversal
 *   const related = await fs.getFactsBySubject('PostgreSQL');
 *
 * Created: 2026-07-03 (Issue #299)
 */

import { Pool } from 'pg';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { chunkText as semanticChunkText } from './semantic-chunker-adapter.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// DATABASE CONNECTION
// ============================================================================

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('Fact storage pool error:', err.message);
});

// ============================================================================
// EMBEDDING GENERATION
// ============================================================================

/**
 * Generate embeddings via Python subprocess (sentence-transformers all-mpnet-base-v2)
 *
 * @param {string|string[]} texts - Text(s) to embed
 * @returns {Promise<number[]|number[][]|null>} 1024-dim vector(s) or null
 */
async function _generateEmbedding(texts) {
  const isArray = Array.isArray(texts);
  const textArray = isArray ? texts : [texts];

  if (textArray.length === 0 || textArray.some(t => typeof t !== 'string' || t.trim().length === 0)) {
    return null;
  }

  return new Promise((resolve) => {
    try {
      const pythonScript = path.join(__dirname, 'generate-embeddings.py');
      const proc = spawn('python3', ['-u', pythonScript], {
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 120000,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => { stdout += data.toString(); });
      proc.stderr.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code, signal) => {
        if (signal || (code !== null && code !== 0)) {
          resolve(null);
          return;
        }
        try {
          const result = JSON.parse(stdout);
          if (result.error || !result.embeddings || result.embeddings.length === 0) {
            resolve(null);
            return;
          }
          resolve(isArray ? result.embeddings : result.embeddings[0]);
        } catch (_err) {
          resolve(null);
        }
      });

      proc.on('error', () => resolve(null));
      proc.stdin.write(JSON.stringify(textArray));
      proc.stdin.end();
    } catch (_err) {
      resolve(null);
    }
  });
}

// ============================================================================
// FACT EXTRACTION (LLM-BASED)
// ============================================================================

/**
 * Build the LLM prompt for fact extraction from a document.
 *
 * The prompt instructs the model to return a JSON array of objects, each with
 * fact_text, subject, predicate, and object fields. The prompt is designed to
 * produce clean, parseable output across multiple model families.
 *
 * @param {string} text - Document text to extract facts from
 * @param {Object} [options]
 * @param {string} [options.domain] - Domain hint for extraction focus
 * @param {number} [options.maxFacts] - Maximum facts to extract (default: 50)
 * @returns {string} The extraction prompt
 */
function _buildExtractionPrompt(text, options = {}) {
  const { domain, maxFacts = 50 } = options;

  const domainHint = domain
    ? `\nFocus on facts relevant to the "${domain}" domain.`
    : '';

  return `Extract structured facts from the following document as subject-predicate-object triples.

Rules:
- Each fact must be a single, self-contained statement.
- Subject: the entity the fact is about.
- Predicate: the relationship or action (use lowercase verb phrases like "is", "has", "supports", "runs_on", "provides", "uses").
- Object: the target entity or value.
- fact_text: a natural language sentence expressing the fact.
- Extract at most ${maxFacts} facts.
- Return ONLY a JSON array, no markdown fences, no commentary.
${domainHint}

Document:
---
${text}
---

Return a JSON array of objects with keys: fact_text, subject, predicate, object

Example output:
[
  {
    "fact_text": "PostgreSQL supports vector similarity search",
    "subject": "PostgreSQL",
    "predicate": "supports",
    "object": "vector similarity search"
  }
]`;
}

/**
 * Parse the LLM response into an array of fact objects.
 * Handles common LLM output quirks: markdown fences, trailing commas,
 * text before/after the JSON array.
 *
 * @param {string} response - Raw LLM response text
 * @returns {Object[]} Array of { fact_text, subject, predicate, object }
 */
function _parseExtractionResponse(response) {
  if (!response || typeof response !== 'string') {
    return [];
  }

  let text = response.trim();

  // Strip markdown code fences if present
  text = text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '');

  // Find the JSON array boundaries
  const startIdx = text.indexOf('[');
  const endIdx = text.lastIndexOf(']');

  if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) {
    return [];
  }

  text = text.substring(startIdx, endIdx + 1);

  // Remove trailing commas before ] (common LLM mistake)
  text = text.replace(/,\s*]/g, ']');

  try {
    const parsed = JSON.parse(text);

    if (!Array.isArray(parsed)) {
      return [];
    }

    // Validate and filter each fact
    return parsed.filter((fact) => {
      return (
        fact &&
        typeof fact === 'object' &&
        typeof fact.fact_text === 'string' && fact.fact_text.trim().length > 0 &&
        typeof fact.subject === 'string' && fact.subject.trim().length > 0 &&
        typeof fact.predicate === 'string' && fact.predicate.trim().length > 0 &&
        typeof fact.object === 'string' && fact.object.trim().length > 0
      );
    }).map((fact) => ({
      fact_text: fact.fact_text.trim(),
      subject: fact.subject.trim(),
      predicate: fact.predicate.trim(),
      object: fact.object.trim(),
    }));
  } catch (_err) {
    return [];
  }
}

// ============================================================================
// FACT STORAGE CLASS
// ============================================================================

/**
 * FactStorageDB - PostgreSQL-backed storage for structured facts
 *
 * Provides CRUD operations, semantic search, and knowledge graph traversal
 * over subject-predicate-object triples extracted from documents.
 */
class FactStorageDB {
  constructor() {
    this.pool = pool;
  }

  /**
   * Execute a database transaction with automatic rollback on failure.
   *
   * @param {Function} callback - Async function receiving a pg client
   * @returns {Promise<any>} Result from callback
   */
  async transaction(callback) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  // --------------------------------------------------------------------------
  // STORE OPERATIONS
  // --------------------------------------------------------------------------

  /**
   * Store a single fact with optional embedding generation.
   *
   * @param {Object} factData
   * @param {string} factData.document_id - Source document identifier
   * @param {string} factData.fact_text - Natural language fact statement
   * @param {string} factData.subject - Subject entity
   * @param {string} factData.predicate - Relationship / verb
   * @param {string} factData.object - Object entity or value
   * @param {string} [factData.document_title] - Human-readable document title
   * @param {number} [factData.confidence] - Extraction confidence 0.0-1.0 (default: 1.0)
   * @param {string} [factData.extraction_model] - Model used for extraction
   * @param {string} [factData.extraction_method] - Method: 'llm', 'regex', 'manual' (default: 'llm')
   * @param {string} [factData.domain] - Domain category
   * @param {string[]} [factData.tags] - Classification tags
   * @param {Object} [factData.metadata] - Arbitrary metadata
   * @returns {Promise<number>} Fact record ID
   *
   * @example
   *   const id = await factStorage.storeFact({
   *     document_id: 'doc-firmware-001',
   *     fact_text: 'The RAX-75 uses a Broadcom BCM6755 SoC',
   *     subject: 'RAX-75',
   *     predicate: 'uses',
   *     object: 'Broadcom BCM6755 SoC',
   *     domain: 'networking',
   *     confidence: 0.95,
   *     extraction_model: 'sonnet'
   *   });
   */
  async storeFact(factData) {
    const {
      document_id,
      fact_text,
      subject,
      predicate,
      object: obj,
      document_title = null,
      confidence = 1.0,
      extraction_model = null,
      extraction_method = 'llm',
      domain = null,
      tags = [],
      metadata = {},
    } = factData;

    // Generate embedding for semantic search (graceful fallback to NULL)
    const embedding = await _generateEmbedding(fact_text);

    return await this.transaction(async (client) => {
      const result = await client.query(
        `INSERT INTO facts.facts
         (document_id, document_title, fact_text, subject, predicate, object,
          fact_embedding, confidence, extraction_model, extraction_method,
          domain, tags, metadata, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
         RETURNING id`,
        [
          document_id,
          document_title,
          fact_text,
          subject,
          predicate,
          obj,
          embedding ? JSON.stringify(embedding) : null,
          confidence,
          extraction_model,
          extraction_method,
          domain,
          tags,
          JSON.stringify(metadata),
        ]
      );
      return result.rows[0].id;
    });
  }

  /**
   * Store multiple facts in a single transaction (batch insert).
   *
   * Generates embeddings in a single batch call for efficiency, then inserts
   * all facts atomically. If embedding generation fails, facts are stored
   * without embeddings.
   *
   * @param {Object[]} factsArray - Array of fact objects (same shape as storeFact)
   * @returns {Promise<number[]>} Array of fact record IDs
   *
   * @example
   *   const ids = await factStorage.storeFacts([
   *     { document_id: 'doc-1', fact_text: '...', subject: '...', predicate: '...', object: '...' },
   *     { document_id: 'doc-1', fact_text: '...', subject: '...', predicate: '...', object: '...' },
   *   ]);
   */
  async storeFacts(factsArray) {
    if (!factsArray || factsArray.length === 0) {
      return [];
    }

    // Batch embed all fact texts at once
    const factTexts = factsArray.map((f) => f.fact_text);
    const embeddings = await _generateEmbedding(factTexts);

    return await this.transaction(async (client) => {
      const ids = [];

      for (let i = 0; i < factsArray.length; i++) {
        const f = factsArray[i];
        const embedding = Array.isArray(embeddings) && embeddings[i]
          ? embeddings[i]
          : null;

        const result = await client.query(
          `INSERT INTO facts.facts
           (document_id, document_title, fact_text, subject, predicate, object,
            fact_embedding, confidence, extraction_model, extraction_method,
            domain, tags, metadata, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
           RETURNING id`,
          [
            f.document_id,
            f.document_title || null,
            f.fact_text,
            f.subject,
            f.predicate,
            f.object,
            embedding ? JSON.stringify(embedding) : null,
            f.confidence || 1.0,
            f.extraction_model || null,
            f.extraction_method || 'llm',
            f.domain || null,
            f.tags || [],
            JSON.stringify(f.metadata || {}),
          ]
        );
        ids.push(result.rows[0].id);
      }

      return ids;
    });
  }

  // --------------------------------------------------------------------------
  // EXTRACTION
  // --------------------------------------------------------------------------

  /**
   * Extract facts from a document using LLM-based extraction.
   *
   * Builds a structured prompt, sends it to the specified model via
   * an extraction callback, parses the response into SPO triples, and
   * stores all extracted facts in the database.
   *
   * @param {string} documentId - Unique document identifier
   * @param {string} documentText - Full document text
   * @param {Object} [options]
   * @param {string} [options.documentTitle] - Human-readable title
   * @param {string} [options.domain] - Domain hint for extraction
   * @param {string} [options.model] - Model name for provenance tracking
   * @param {number} [options.maxFacts] - Maximum facts to extract (default: 50)
   * @param {Function} [options.llmCall] - Async function(prompt) => string response.
   *   If not provided, returns the prompt for external execution.
   * @param {Object} [options.metadata] - Extra metadata to attach to each fact
   * @returns {Promise<Object>} { facts: Object[], ids: number[], prompt?: string }
   *
   * @example
   *   // With an LLM callback
   *   const result = await factStorage.extractFacts('doc-1', docText, {
   *     domain: 'networking',
   *     model: 'sonnet',
   *     llmCall: async (prompt) => {
   *       const resp = await callClaude(prompt);
   *       return resp.text;
   *     }
   *   });
   *   console.log(`Extracted ${result.facts.length} facts`);
   *
   *   // Without an LLM callback (get the prompt, call externally)
   *   const result = await factStorage.extractFacts('doc-1', docText);
   *   // result.prompt contains the extraction prompt to send to your LLM
   */
  async extractFacts(documentId, documentText, options = {}) {
    const {
      documentTitle = null,
      domain = null,
      model = null,
      maxFacts = 50,
      llmCall = null,
      metadata = {},
    } = options;

    // For large documents (>500 chars), chunk before extraction
    // This prevents LLM context overflow and improves extraction quality
    if (documentText.length > 500 && llmCall) {
      const chunks = semanticChunkText(documentText, { minChunkSize: 300, maxChunkSize: 3000, overlapSize: 150 });

      if (chunks && chunks.length > 1) {
        const allFacts = [];
        const allIds = [];
        const factsPerChunk = Math.max(5, Math.ceil(maxFacts / chunks.length));

        for (let i = 0; i < chunks.length; i++) {
          const chunkContent = chunks[i].content || chunks[i];
          const chunkPrompt = _buildExtractionPrompt(chunkContent, { domain, maxFacts: factsPerChunk });

          let chunkResponse;
          try {
            chunkResponse = await llmCall(chunkPrompt);
          } catch (err) {
            console.warn(`Chunk ${i + 1}/${chunks.length} extraction failed: ${err.message}`);
            continue;
          }

          const chunkFacts = _parseExtractionResponse(chunkResponse);
          if (chunkFacts.length === 0) continue;

          const enrichedChunkFacts = chunkFacts.map((fact) => ({
            ...fact,
            document_id: documentId,
            document_title: documentTitle,
            domain,
            extraction_model: model,
            extraction_method: 'llm',
            metadata: {
              ...metadata,
              chunk_index: i,
              total_chunks: chunks.length,
              raw_response_length: chunkResponse.length,
            },
          }));

          const chunkIds = await this.storeFacts(enrichedChunkFacts);
          allFacts.push(...enrichedChunkFacts);
          allIds.push(...chunkIds);
        }

        return { facts: allFacts, ids: allIds };
      }
    }

    // Small document or single chunk: process directly
    const prompt = _buildExtractionPrompt(documentText, { domain, maxFacts });

    // If no LLM callback provided, return the prompt for external execution
    if (!llmCall) {
      return { facts: [], ids: [], prompt };
    }

    // Call the LLM
    let response;
    try {
      response = await llmCall(prompt);
    } catch (err) {
      throw new Error(`LLM extraction call failed: ${err.message}`);
    }

    // Parse the response
    const extractedFacts = _parseExtractionResponse(response);

    if (extractedFacts.length === 0) {
      return { facts: [], ids: [] };
    }

    // Enrich each fact with document metadata
    const enrichedFacts = extractedFacts.map((fact) => ({
      ...fact,
      document_id: documentId,
      document_title: documentTitle,
      domain,
      extraction_model: model,
      extraction_method: 'llm',
      metadata: { ...metadata, raw_response_length: response.length },
    }));

    // Batch store all extracted facts
    const ids = await this.storeFacts(enrichedFacts);

    return { facts: enrichedFacts, ids };
  }

  /**
   * Ingest an LLM response that was generated from an extractFacts prompt.
   *
   * Use this when you called extractFacts without an llmCall callback,
   * sent the prompt externally, and now have the response to ingest.
   *
   * @param {string} documentId - Document identifier (same as in extractFacts)
   * @param {string} llmResponse - Raw LLM response text
   * @param {Object} [options]
   * @param {string} [options.documentTitle] - Document title
   * @param {string} [options.domain] - Domain category
   * @param {string} [options.model] - Model used for extraction
   * @param {Object} [options.metadata] - Extra metadata
   * @returns {Promise<Object>} { facts: Object[], ids: number[] }
   */
  async ingestExtractionResponse(documentId, llmResponse, options = {}) {
    const {
      documentTitle = null,
      domain = null,
      model = null,
      metadata = {},
    } = options;

    const extractedFacts = _parseExtractionResponse(llmResponse);

    if (extractedFacts.length === 0) {
      return { facts: [], ids: [] };
    }

    const enrichedFacts = extractedFacts.map((fact) => ({
      ...fact,
      document_id: documentId,
      document_title: documentTitle,
      domain,
      extraction_model: model,
      extraction_method: 'llm',
      metadata,
    }));

    const ids = await this.storeFacts(enrichedFacts);

    return { facts: enrichedFacts, ids };
  }

  // --------------------------------------------------------------------------
  // QUERY OPERATIONS
  // --------------------------------------------------------------------------

  /**
   * Retrieve a single fact by ID.
   *
   * @param {number} factId - Fact record ID
   * @returns {Promise<Object|null>} Fact object or null if not found
   */
  async getFactById(factId) {
    const result = await this.pool.query(
      `SELECT id, document_id, document_title, fact_text, subject, predicate, object,
              confidence, extraction_model, extraction_method, domain, tags,
              metadata, created_at, updated_at
       FROM facts.facts
       WHERE id = $1`,
      [factId]
    );
    return result.rows[0] || null;
  }

  /**
   * Get all facts extracted from a specific document.
   *
   * @param {string} documentId - Document identifier
   * @param {Object} [options]
   * @param {number} [options.limit] - Max results (default: 1000)
   * @param {number} [options.minConfidence] - Minimum confidence filter (default: 0.0)
   * @returns {Promise<Object[]>} Array of fact objects
   */
  async getFactsByDocument(documentId, options = {}) {
    const { limit = 1000, minConfidence = 0.0 } = options;

    const result = await this.pool.query(
      `SELECT id, document_id, document_title, fact_text, subject, predicate, object,
              confidence, extraction_model, extraction_method, domain, tags,
              metadata, created_at
       FROM facts.facts
       WHERE document_id = $1 AND confidence >= $2
       ORDER BY created_at ASC
       LIMIT $3`,
      [documentId, minConfidence, limit]
    );
    return result.rows;
  }

  /**
   * Get all facts where the given entity appears as the subject.
   * Useful for knowledge graph traversal ("tell me about X").
   *
   * @param {string} subject - Subject entity to search for
   * @param {Object} [options]
   * @param {number} [options.limit] - Max results (default: 100)
   * @param {boolean} [options.caseInsensitive] - Case-insensitive match (default: true)
   * @returns {Promise<Object[]>} Array of fact objects
   */
  async getFactsBySubject(subject, options = {}) {
    const { limit = 100, caseInsensitive = true } = options;

    const whereClause = caseInsensitive
      ? 'LOWER(subject) = LOWER($1)'
      : 'subject = $1';

    const result = await this.pool.query(
      `SELECT id, document_id, fact_text, subject, predicate, object,
              confidence, domain, tags, created_at
       FROM facts.facts
       WHERE ${whereClause}
       ORDER BY confidence DESC
       LIMIT $2`,
      [subject, limit]
    );
    return result.rows;
  }

  /**
   * Get all facts where the given entity appears as the object.
   * Useful for reverse graph traversal ("what references X").
   *
   * @param {string} object - Object entity to search for
   * @param {Object} [options]
   * @param {number} [options.limit] - Max results (default: 100)
   * @param {boolean} [options.caseInsensitive] - Case-insensitive match (default: true)
   * @returns {Promise<Object[]>} Array of fact objects
   */
  async getFactsByObject(object, options = {}) {
    const { limit = 100, caseInsensitive = true } = options;

    const whereClause = caseInsensitive
      ? 'LOWER(object) = LOWER($1)'
      : 'object = $1';

    const result = await this.pool.query(
      `SELECT id, document_id, fact_text, subject, predicate, object,
              confidence, domain, tags, created_at
       FROM facts.facts
       WHERE ${whereClause}
       ORDER BY confidence DESC
       LIMIT $2`,
      [object, limit]
    );
    return result.rows;
  }

  /**
   * Get all facts matching a specific predicate (relationship type).
   *
   * @param {string} predicate - Predicate to filter by
   * @param {Object} [options]
   * @param {number} [options.limit] - Max results (default: 100)
   * @returns {Promise<Object[]>} Array of fact objects
   */
  async getFactsByPredicate(predicate, options = {}) {
    const { limit = 100 } = options;

    const result = await this.pool.query(
      `SELECT id, document_id, fact_text, subject, predicate, object,
              confidence, domain, tags, created_at
       FROM facts.facts
       WHERE LOWER(predicate) = LOWER($1)
       ORDER BY confidence DESC
       LIMIT $2`,
      [predicate, limit]
    );
    return result.rows;
  }

  /**
   * Find an exact SPO triple match.
   *
   * @param {string} subject
   * @param {string} predicate
   * @param {string} object
   * @returns {Promise<Object|null>} Matching fact or null
   */
  async findTriple(subject, predicate, object) {
    const result = await this.pool.query(
      `SELECT id, document_id, fact_text, subject, predicate, object,
              confidence, domain, tags, metadata, created_at
       FROM facts.facts
       WHERE LOWER(subject) = LOWER($1)
         AND LOWER(predicate) = LOWER($2)
         AND LOWER(object) = LOWER($3)
       LIMIT 1`,
      [subject, predicate, object]
    );
    return result.rows[0] || null;
  }

  // --------------------------------------------------------------------------
  // SEMANTIC SEARCH
  // --------------------------------------------------------------------------

  /**
   * Search facts by semantic similarity to a query string.
   *
   * Generates an embedding for the query and uses pgvector cosine distance
   * to find the most similar facts. Falls back to text search if embedding
   * generation is unavailable.
   *
   * @param {string} query - Natural language query
   * @param {Object} [options]
   * @param {number} [options.limit] - Max results (default: 10)
   * @param {number} [options.minSimilarity] - Minimum similarity 0.0-1.0 (default: 0.0)
   * @param {string} [options.domain] - Filter by domain
   * @param {string} [options.documentId] - Filter by document
   * @param {number} [options.minConfidence] - Minimum confidence (default: 0.0)
   * @returns {Promise<Object[]>} Array of facts with similarity scores
   *
   * @example
   *   const results = await factStorage.searchFacts('router SoC processor', {
   *     domain: 'networking',
   *     limit: 5,
   *     minSimilarity: 0.5
   *   });
   */
  async searchFacts(query, options = {}) {
    const {
      limit = 10,
      minSimilarity = 0.0,
      domain = null,
      documentId = null,
      minConfidence = 0.0,
    } = options;

    const queryEmbedding = await _generateEmbedding(query);

    // If embedding generation succeeded, use vector similarity
    if (queryEmbedding) {
      const conditions = ['confidence >= $2'];
      const params = [JSON.stringify(queryEmbedding), minConfidence];
      let paramIdx = 3;

      if (domain) {
        conditions.push(`domain = $${paramIdx}`);
        params.push(domain);
        paramIdx++;
      }
      if (documentId) {
        conditions.push(`document_id = $${paramIdx}`);
        params.push(documentId);
        paramIdx++;
      }
      if (minSimilarity > 0) {
        conditions.push(`1 - (fact_embedding <=> $1::vector) >= $${paramIdx}`);
        params.push(minSimilarity);
        paramIdx++;
      }

      params.push(limit);

      const result = await this.pool.query(
        `SELECT id, document_id, document_title, fact_text, subject, predicate, object,
                confidence, domain, tags, metadata, created_at,
                1 - (fact_embedding <=> $1::vector) AS similarity
         FROM facts.facts
         WHERE fact_embedding IS NOT NULL AND ${conditions.join(' AND ')}
         ORDER BY fact_embedding <=> $1::vector
         LIMIT $${paramIdx}`,
        params
      );
      return result.rows;
    }

    // Fallback: text-based search using ILIKE
    const conditions = ['confidence >= $2'];
    const params = [`%${query}%`, minConfidence];
    let paramIdx = 3;

    if (domain) {
      conditions.push(`domain = $${paramIdx}`);
      params.push(domain);
      paramIdx++;
    }
    if (documentId) {
      conditions.push(`document_id = $${paramIdx}`);
      params.push(documentId);
      paramIdx++;
    }

    params.push(limit);

    const result = await this.pool.query(
      `SELECT id, document_id, document_title, fact_text, subject, predicate, object,
              confidence, domain, tags, metadata, created_at,
              1.0 AS similarity
       FROM facts.facts
       WHERE (fact_text ILIKE $1 OR subject ILIKE $1 OR object ILIKE $1)
         AND ${conditions.join(' AND ')}
       ORDER BY confidence DESC
       LIMIT $${paramIdx}`,
      params
    );
    return result.rows;
  }

  // --------------------------------------------------------------------------
  // KNOWLEDGE GRAPH OPERATIONS
  // --------------------------------------------------------------------------

  /**
   * Get all entities connected to a given entity (both as subject and object).
   * Returns a neighborhood view of the knowledge graph.
   *
   * @param {string} entity - Entity name to explore
   * @param {Object} [options]
   * @param {number} [options.limit] - Max results per direction (default: 50)
   * @returns {Promise<Object>} { outgoing: [...], incoming: [...] }
   */
  async getEntityNeighborhood(entity, options = {}) {
    const { limit = 50 } = options;

    const [outgoing, incoming] = await Promise.all([
      this.pool.query(
        `SELECT id, predicate, object AS connected_entity, confidence, domain
         FROM facts.facts
         WHERE LOWER(subject) = LOWER($1)
         ORDER BY confidence DESC
         LIMIT $2`,
        [entity, limit]
      ),
      this.pool.query(
        `SELECT id, predicate, subject AS connected_entity, confidence, domain
         FROM facts.facts
         WHERE LOWER(object) = LOWER($1)
         ORDER BY confidence DESC
         LIMIT $2`,
        [entity, limit]
      ),
    ]);

    return {
      outgoing: outgoing.rows,
      incoming: incoming.rows,
    };
  }

  /**
   * Get all unique entities (subjects and objects) in the fact store,
   * optionally filtered by domain.
   *
   * @param {Object} [options]
   * @param {string} [options.domain] - Filter by domain
   * @param {number} [options.limit] - Max results (default: 500)
   * @returns {Promise<Object[]>} Array of { entity, role_count, as_subject, as_object }
   */
  async listEntities(options = {}) {
    const { domain = null, limit = 500 } = options;

    const domainFilter = domain ? 'WHERE domain = $2' : '';
    const params = domain ? [limit, domain] : [limit];

    const result = await this.pool.query(
      `WITH entities AS (
         SELECT subject AS entity, 'subject' AS role FROM facts.facts ${domainFilter}
         UNION ALL
         SELECT object AS entity, 'object' AS role FROM facts.facts ${domainFilter}
       )
       SELECT
         entity,
         COUNT(*) AS role_count,
         COUNT(*) FILTER (WHERE role = 'subject') AS as_subject,
         COUNT(*) FILTER (WHERE role = 'object') AS as_object
       FROM entities
       GROUP BY entity
       ORDER BY role_count DESC
       LIMIT $1`,
      params
    );
    return result.rows;
  }

  // --------------------------------------------------------------------------
  // UPDATE & DELETE
  // --------------------------------------------------------------------------

  /**
   * Update a fact's metadata, confidence, or tags.
   *
   * @param {number} factId - Fact record ID
   * @param {Object} updates - Fields to update
   * @param {number} [updates.confidence] - New confidence score
   * @param {string} [updates.domain] - New domain
   * @param {string[]} [updates.tags] - New tags array
   * @param {Object} [updates.metadata] - Metadata to merge (shallow merge)
   * @returns {Promise<boolean>} true if updated, false if not found
   */
  async updateFact(factId, updates) {
    const setClauses = [];
    const params = [factId];
    let paramIdx = 2;

    if (updates.confidence !== undefined) {
      setClauses.push(`confidence = $${paramIdx}`);
      params.push(updates.confidence);
      paramIdx++;
    }
    if (updates.domain !== undefined) {
      setClauses.push(`domain = $${paramIdx}`);
      params.push(updates.domain);
      paramIdx++;
    }
    if (updates.tags !== undefined) {
      setClauses.push(`tags = $${paramIdx}`);
      params.push(updates.tags);
      paramIdx++;
    }
    if (updates.metadata !== undefined) {
      setClauses.push(`metadata = metadata || $${paramIdx}::jsonb`);
      params.push(JSON.stringify(updates.metadata));
      paramIdx++;
    }

    if (setClauses.length === 0) {
      return false;
    }

    setClauses.push('updated_at = NOW()');

    const result = await this.pool.query(
      `UPDATE facts.facts SET ${setClauses.join(', ')} WHERE id = $1`,
      params
    );
    return result.rowCount > 0;
  }

  /**
   * Delete a single fact by ID.
   *
   * @param {number} factId - Fact record ID
   * @returns {Promise<boolean>} true if deleted, false if not found
   */
  async deleteFact(factId) {
    const result = await this.pool.query(
      'DELETE FROM facts.facts WHERE id = $1',
      [factId]
    );
    return result.rowCount > 0;
  }

  /**
   * Delete all facts from a specific document.
   *
   * @param {string} documentId - Document identifier
   * @returns {Promise<number>} Number of facts deleted
   */
  async deleteFactsByDocument(documentId) {
    const result = await this.pool.query(
      'DELETE FROM facts.facts WHERE document_id = $1',
      [documentId]
    );
    return result.rowCount;
  }

  // --------------------------------------------------------------------------
  // STATISTICS & MAINTENANCE
  // --------------------------------------------------------------------------

  /**
   * Get summary statistics for the fact store.
   *
   * @returns {Promise<Object>} Statistics object
   */
  async getStats() {
    const result = await this.pool.query(`
      SELECT
        COUNT(*) AS total_facts,
        COUNT(DISTINCT document_id) AS total_documents,
        COUNT(DISTINCT subject) AS unique_subjects,
        COUNT(DISTINCT predicate) AS unique_predicates,
        COUNT(DISTINCT object) AS unique_objects,
        COUNT(*) FILTER (WHERE fact_embedding IS NOT NULL) AS facts_with_embeddings,
        AVG(confidence) AS avg_confidence,
        MIN(created_at) AS earliest_fact,
        MAX(created_at) AS latest_fact
      FROM facts.facts
    `);
    return result.rows[0];
  }

  /**
   * Get fact counts grouped by domain.
   *
   * @returns {Promise<Object[]>} Array of { domain, fact_count, avg_confidence }
   */
  async getStatsByDomain() {
    const result = await this.pool.query(`
      SELECT
        COALESCE(domain, 'unclassified') AS domain,
        COUNT(*) AS fact_count,
        AVG(confidence) AS avg_confidence,
        COUNT(DISTINCT document_id) AS document_count
      FROM facts.facts
      GROUP BY domain
      ORDER BY fact_count DESC
    `);
    return result.rows;
  }

  /**
   * Refresh materialized views (call periodically or after bulk inserts).
   *
   * @returns {Promise<void>}
   */
  async refreshViews() {
    await this.pool.query('SELECT facts.refresh_views()');
  }

  /**
   * Close the database connection pool.
   * Call this on application shutdown.
   *
   * @returns {Promise<void>}
   */
  async close() {
    await this.pool.end();
  }
}

// ============================================================================
// SINGLETON & EXPORTS
// ============================================================================

let _instance = null;

/**
 * Get singleton FactStorageDB instance.
 *
 * @returns {FactStorageDB}
 */
function getFactStorage() {
  if (!_instance) {
    _instance = new FactStorageDB();
  }
  return _instance;
}

export {
  getFactStorage,
  FactStorageDB,
  // Expose internals for testing
  _buildExtractionPrompt,
  _parseExtractionResponse,
  _generateEmbedding,
};
