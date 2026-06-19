/**
 * Embedding generation for semantic search
 * Uses local sentence-transformers models for privacy
 * Falls back to simple hash-based embedding if models unavailable
 */

const { spawn } = require('child_process');
const crypto = require('crypto');

// Cache for embeddings to avoid redundant computation
const embeddingCache = new Map();
const MAX_CACHE_SIZE = 1000;

/**
 * Generate embedding for text using sentence-transformers
 * @param {string} text - Text to embed
 * @param {object} options - Options
 * @param {string} options.model - Model to use (default: all-MiniLM-L6-v2)
 * @param {boolean} options.useCache - Use cache (default: true)
 * @returns {Promise<Array<number>>} Embedding vector
 */
async function generateEmbedding(text, options = {}) {
  const {
    model = 'all-MiniLM-L6-v2',  // 384-dim, fast, good quality
    useCache = true
  } = options;

  // Check cache
  const cacheKey = `${model}:${text}`;
  if (useCache && embeddingCache.has(cacheKey)) {
    return embeddingCache.get(cacheKey);
  }

  try {
    // Try sentence-transformers Python library
    const embedding = await generateWithSentenceTransformers(text, model);

    // Cache result
    if (useCache) {
      if (embeddingCache.size >= MAX_CACHE_SIZE) {
        // Evict oldest entry
        const firstKey = embeddingCache.keys().next().value;
        embeddingCache.delete(firstKey);
      }
      embeddingCache.set(cacheKey, embedding);
    }

    return embedding;
  } catch (err) {
    console.warn('[embeddings] sentence-transformers failed, using fallback:', err.message);
    // Fallback to simple embedding
    return generateFallbackEmbedding(text);
  }
}

/**
 * Generate embedding using sentence-transformers Python library
 * Requires: pip install sentence-transformers
 * @param {string} text - Text to embed
 * @param {string} model - Model name
 * @returns {Promise<Array<number>>} Embedding vector
 */
function generateWithSentenceTransformers(text, model) {
  return new Promise((resolve, reject) => {
    const pythonScript = `
import sys
import json
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('${model}')
text = sys.stdin.read()
embedding = model.encode(text).tolist()
print(json.dumps(embedding))
`;

    const python = spawn('python3', ['-c', pythonScript]);

    let stdout = '';
    let stderr = '';

    python.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    python.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    python.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Python exited with code ${code}: ${stderr}`));
        return;
      }

      try {
        const embedding = JSON.parse(stdout.trim());
        resolve(embedding);
      } catch (err) {
        reject(new Error(`Failed to parse embedding: ${err.message}`));
      }
    });

    python.stdin.write(text);
    python.stdin.end();
  });
}

/**
 * Generate fallback embedding when sentence-transformers unavailable
 * Uses TF-IDF-like approach with hash-based dimensionality reduction
 * @param {string} text - Text to embed
 * @param {number} dimensions - Embedding dimensions (default: 384)
 * @returns {Array<number>} Embedding vector
 */
function generateFallbackEmbedding(text, dimensions = 384) {
  // Tokenize and compute term frequencies
  const tokens = text.toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 2);

  const termFreq = new Map();
  tokens.forEach(token => {
    termFreq.set(token, (termFreq.get(token) || 0) + 1);
  });

  // Initialize embedding vector
  const embedding = new Array(dimensions).fill(0);

  // Hash each term to multiple dimensions and accumulate
  for (const [term, freq] of termFreq.entries()) {
    const hash = hashToDimensions(term, dimensions, 3);  // 3 dimensions per term
    hash.forEach(({ dim, weight }) => {
      embedding[dim] += weight * freq;
    });
  }

  // Normalize to unit length
  const norm = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
  if (norm > 0) {
    for (let i = 0; i < dimensions; i++) {
      embedding[i] /= norm;
    }
  }

  return embedding;
}

/**
 * Hash a term to multiple dimensions with weights
 * @param {string} term - Term to hash
 * @param {number} dimensions - Total dimensions
 * @param {number} count - Number of dimensions to map to
 * @returns {Array<{dim: number, weight: number}>} Dimension-weight pairs
 */
function hashToDimensions(term, dimensions, count) {
  const result = [];

  for (let i = 0; i < count; i++) {
    const hash = crypto.createHash('sha256')
      .update(`${term}:${i}`)
      .digest();

    // Use first 4 bytes for dimension, next 4 bytes for weight
    const dim = hash.readUInt32BE(0) % dimensions;
    const weight = (hash.readUInt32BE(4) / 0xFFFFFFFF) * 2 - 1;  // -1 to 1

    result.push({ dim, weight });
  }

  return result;
}

/**
 * Compute cosine similarity between two embeddings
 * @param {Array<number>} a - First embedding
 * @param {Array<number>} b - Second embedding
 * @returns {number} Cosine similarity (0 to 1)
 */
function cosineSimilarity(a, b) {
  if (a.length !== b.length) {
    throw new Error('Embeddings must have same dimensions');
  }

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  normA = Math.sqrt(normA);
  normB = Math.sqrt(normB);

  if (normA === 0 || normB === 0) {
    return 0;
  }

  return dotProduct / (normA * normB);
}

/**
 * Clear embedding cache
 */
function clearCache() {
  embeddingCache.clear();
}

module.exports = {
  generateEmbedding,
  generateWithSentenceTransformers,
  generateFallbackEmbedding,
  cosineSimilarity,
  clearCache
};
