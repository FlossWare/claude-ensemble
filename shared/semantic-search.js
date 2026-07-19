/**
 * Semantic Search for PDF Library
 *
 * Uses pgvector embeddings to find similar PDFs by meaning
 */

import pg from 'pg';
import { generateEmbedding as generateEmbeddingCloudflare } from './generate-embedding.mjs';

const { Pool } = pg;

const pool = new Pool({
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: 'claude'
});

/**
 * Generate embedding for query text using Cloudflare AI
 */
async function generateQueryEmbedding(text) {
  return await generateEmbeddingCloudflare(text);
}

/**
 * Semantic search for PDFs
 *
 * @param {string} query - Search query
 * @param {object} options - Search options
 * @param {number} options.topK - Number of results (default: 10)
 * @param {string} options.category - Filter by category
 * @param {string} options.topic - Filter by topic (requires OrientDB join)
 * @returns {Promise<Array>} Similar PDFs with scores
 */
async function semanticSearch(query, options = {}) {
  const {
    topK = 10,
    category = null,
    topic = null
  } = options;

  // Generate embedding for query (async now!)
  const queryEmbedding = await generateQueryEmbedding(query);

  // Build SQL query
  let sql = `
    SELECT
      pdf_path,
      text_preview,
      text_length,
      (embedding <=> $1::vector) as distance,
      1 - (embedding <=> $1::vector) as similarity
    FROM learning.pdf_metadata
    WHERE embedding IS NOT NULL
  `;

  const params = [JSON.stringify(queryEmbedding)];

  // Add category filter if provided
  if (category) {
    sql += ` AND pdf_path LIKE $${params.length + 1}`;
    params.push(`%/${category}/%`);
  }

  sql += ` ORDER BY distance LIMIT $${params.length + 1}`;
  params.push(topK);

  const result = await pool.query(sql, params);

  // Format results
  return result.rows.map(row => ({
    pdf_path: row.pdf_path,
    filename: row.pdf_path.split('/').pop(),
    preview: row.text_preview,
    text_length: row.text_length,
    similarity_score: parseFloat(row.similarity.toFixed(4)),
    distance: parseFloat(row.distance.toFixed(4))
  }));
}

/**
 * Find PDFs about a specific topic
 */
async function findByTopic(topic, limit = 10) {
  return semanticSearch(topic, { topK: limit });
}

/**
 * Find similar PDFs to a given PDF
 */
async function findSimilar(pdfPath, limit = 5) {
  const result = await pool.query(
    `SELECT text_preview FROM learning.pdf_metadata WHERE pdf_path = $1`,
    [pdfPath]
  );

  if (result.rows.length === 0) {
    throw new Error('PDF not found');
  }

  return semanticSearch(result.rows[0].text_preview, { topK: limit + 1 });
}

export {
  semanticSearch,
  findByTopic,
  findSimilar,
  generateQueryEmbedding
};
