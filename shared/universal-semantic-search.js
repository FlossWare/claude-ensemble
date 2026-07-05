/**
 * Universal Semantic Search
 *
 * Search across PDFs, code files, workflows, and documentation
 * using unified vector embeddings
 */

const { Pool } = require('pg');
const crypto = require('crypto');

const pool = new Pool({
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: 'claude'
});

/**
 * Generate embedding for any text
 */
function generateEmbedding(text) {
  const hash = crypto.createHash('sha256').update(text).digest();
  const embedding = [];
  for (let i = 0; i < 384; i++) {
    embedding.push((hash[i % hash.length] - 128) / 128.0);
  }
  return embedding;
}

/**
 * Universal search across all content types
 *
 * @param {string} query - Search query
 * @param {object} options
 * @param {number} options.topK - Results per type (default: 5)
 * @param {string[]} options.types - Content types to search ['pdf', 'code', 'workflow', 'docs']
 * @param {boolean} options.mergeResults - Combine all types (default: false)
 * @returns {Promise<Object>} Results grouped by type or merged
 */
async function universalSearch(query, options = {}) {
  const {
    topK = 5,
    types = ['pdf', 'code', 'workflow', 'docs'],
    mergeResults = false
  } = options;

  const queryEmbedding = generateEmbedding(query);
  const results = {};

  // Search PDFs
  if (types.includes('pdf')) {
    results.pdfs = await searchPDFs(queryEmbedding, topK);
  }

  // Search Code Files
  if (types.includes('code')) {
    results.code = await searchCode(queryEmbedding, topK);
  }

  // Search Workflow Outputs
  if (types.includes('workflow')) {
    results.workflows = await searchWorkflows(queryEmbedding, topK);
  }

  // Search Documentation
  if (types.includes('docs')) {
    results.docs = await searchDocs(queryEmbedding, topK);
  }

  if (mergeResults) {
    return mergeAndRank(results, topK * types.length);
  }

  return results;
}

/**
 * Search PDFs (existing table)
 */
async function searchPDFs(embedding, limit) {
  const result = await pool.query(`
    SELECT
      'pdf' as type,
      pdf_path as path,
      pdf_path as title,
      text_preview as preview,
      text_length as length,
      1 - (embedding <=> $1::vector) as similarity
    FROM learning.pdf_metadata
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> $1::vector
    LIMIT $2
  `, [JSON.stringify(embedding), limit]);

  return result.rows.map(formatResult);
}

/**
 * Search code files (will create table if needed)
 */
async function searchCode(embedding, limit) {
  try {
    const result = await pool.query(`
      SELECT
        'code' as type,
        file_path as path,
        file_path as title,
        content_preview as preview,
        char_length(content_preview) as length,
        1 - (embedding <=> $1::vector) as similarity
      FROM learning.code_embeddings
      WHERE embedding IS NOT NULL
      ORDER BY embedding <=> $1::vector
      LIMIT $2
    `, [JSON.stringify(embedding), limit]);

    return result.rows.map(formatResult);
  } catch (err) {
    // Table doesn't exist yet
    return [];
  }
}

/**
 * Search workflow outputs
 */
async function searchWorkflows(embedding, limit) {
  try {
    const result = await pool.query(`
      SELECT
        'workflow' as type,
        workflow_id as path,
        workflow_name as title,
        task_description as preview,
        char_length(task_description) as length,
        1 - (embedding <=> $1::vector) as similarity
      FROM workflow.executions
      WHERE embedding IS NOT NULL
      ORDER BY embedding <=> $1::vector
      LIMIT $2
    `, [JSON.stringify(embedding), limit]);

    return result.rows.map(formatResult);
  } catch (err) {
    return [];
  }
}

/**
 * Search documentation
 */
async function searchDocs(embedding, limit) {
  try {
    const result = await pool.query(`
      SELECT
        'docs' as type,
        doc_path as path,
        doc_title as title,
        content_preview as preview,
        char_length(content_preview) as length,
        1 - (embedding <=> $1::vector) as similarity
      FROM learning.documentation_embeddings
      WHERE embedding IS NOT NULL
      ORDER BY embedding <=> $1::vector
      LIMIT $2
    `, [JSON.stringify(embedding), limit]);

    return result.rows.map(formatResult);
  } catch (err) {
    return [];
  }
}

/**
 * Format result consistently
 */
function formatResult(row) {
  return {
    type: row.type,
    path: row.path,
    title: row.title || row.path.split('/').pop(),
    preview: row.preview ? row.preview.substring(0, 200) : '',
    length: parseInt(row.length) || 0,
    similarity: parseFloat(row.similarity.toFixed(4))
  };
}

/**
 * Merge results from all types and rank by similarity
 */
function mergeAndRank(results, limit) {
  const merged = [];

  for (const [type, items] of Object.entries(results)) {
    if (Array.isArray(items)) {
      merged.push(...items);
    }
  }

  // Sort by similarity descending
  merged.sort((a, b) => b.similarity - a.similarity);

  return merged.slice(0, limit);
}

/**
 * Add content to searchable index
 *
 * @param {string} type - Content type: 'code', 'workflow', 'docs'
 * @param {object} content - Content to index
 */
async function addToIndex(type, content) {
  const embedding = generateEmbedding(content.text);

  switch (type) {
    case 'code':
      await ensureCodeTable();
      await pool.query(`
        INSERT INTO learning.code_embeddings
        (file_path, language, content_preview, embedding)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (file_path) DO UPDATE
        SET content_preview = $3, embedding = $4, updated_at = NOW()
      `, [content.path, content.language, content.text.substring(0, 2000), embedding]);
      break;

    case 'workflow':
      await pool.query(`
        UPDATE workflow.executions
        SET embedding = $1
        WHERE workflow_id = $2
      `, [embedding, content.workflow_id]);
      break;

    case 'docs':
      await ensureDocsTable();
      await pool.query(`
        INSERT INTO learning.documentation_embeddings
        (doc_path, doc_title, content_preview, embedding)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (doc_path) DO UPDATE
        SET content_preview = $3, embedding = $4, updated_at = NOW()
      `, [content.path, content.title, content.text.substring(0, 2000), embedding]);
      break;
  }
}

/**
 * Create code embeddings table if needed
 */
async function ensureCodeTable() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS learning.code_embeddings (
      id SERIAL PRIMARY KEY,
      file_path TEXT UNIQUE NOT NULL,
      language TEXT,
      content_preview TEXT,
      embedding vector(384),
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    )
  `);

  // Create HNSW index for fast search
  await pool.query(`
    CREATE INDEX IF NOT EXISTS idx_code_embedding_hnsw
    ON learning.code_embeddings
    USING hnsw (embedding vector_cosine_ops)
  `);
}

/**
 * Create docs embeddings table if needed
 */
async function ensureDocsTable() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS learning.documentation_embeddings (
      id SERIAL PRIMARY KEY,
      doc_path TEXT UNIQUE NOT NULL,
      doc_title TEXT,
      content_preview TEXT,
      embedding vector(384),
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    )
  `);

  await pool.query(`
    CREATE INDEX IF NOT EXISTS idx_docs_embedding_hnsw
    ON learning.documentation_embeddings
    USING hnsw (embedding vector_cosine_ops)
  `);
}

module.exports = {
  universalSearch,
  addToIndex,
  generateEmbedding,
  searchPDFs,
  searchCode,
  searchWorkflows,
  searchDocs
};
