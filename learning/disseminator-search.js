#!/usr/bin/env node
/**
 * Disseminator Knowledge Search
 *
 * Search the disseminator knowledge base using:
 * - Text search (keyword matching)
 * - Vector similarity search (semantic)
 * - Filtered by type, confidence, date
 *
 * Usage:
 *   node disseminator-search.js "IFD endpoint configuration"
 *   node disseminator-search.js --type=cicd_pipeline_knowledge "gitlab"
 *   node disseminator-search.js --min-confidence=0.8 "deployment"
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const KNOWLEDGE_FILE = path.join(process.env.HOME, '.claude/learning/disseminator-knowledge.jsonl');
const VECTOR_FILE = path.join(process.env.HOME, '.claude/learning/disseminator-vectors.jsonl');

function loadKnowledge() {
  if (!fs.existsSync(KNOWLEDGE_FILE)) {
    return [];
  }

  return fs.readFileSync(KNOWLEDGE_FILE, 'utf8')
    .trim()
    .split('\n')
    .filter(l => l.trim())
    .map(l => JSON.parse(l));
}

function loadVectors() {
  if (!fs.existsSync(VECTOR_FILE)) {
    return [];
  }

  return fs.readFileSync(VECTOR_FILE, 'utf8')
    .trim()
    .split('\n')
    .filter(l => l.trim())
    .map(l => JSON.parse(l));
}

function createQueryEmbedding(query) {
  // Simple deterministic embedding for search
  const hash = crypto.createHash('sha256').update(query).digest();
  const embedding = new Float32Array(100);

  for (let i = 0; i < 100; i++) {
    const byte1 = hash[(i * 2) % 32];
    const byte2 = hash[((i * 2) + 1) % 32];
    embedding[i] = ((byte1 ^ byte2) / 255) * 2 - 1;
  }

  // Normalize
  let norm = 0;
  for (let i = 0; i < 100; i++) {
    norm += embedding[i] * embedding[i];
  }
  norm = Math.sqrt(norm);
  for (let i = 0; i < 100; i++) {
    embedding[i] /= norm;
  }

  return Array.from(embedding);
}

function cosineSimilarity(a, b) {
  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

function textSearch(knowledge, query, options = {}) {
  const queryLower = query.toLowerCase();
  const results = [];

  for (const item of knowledge) {
    // Apply filters
    if (options.type && item.type !== options.type) continue;
    if (options.minConfidence && item.confidence < options.minConfidence) continue;

    // Text matching
    const titleMatch = (item.title || '').toLowerCase().includes(queryLower);
    const contentMatch = (item.content || '').toLowerCase().includes(queryLower);
    const entityMatch = (item.entities || []).some(e => e.toLowerCase().includes(queryLower));

    if (titleMatch || contentMatch || entityMatch) {
      let score = 0;
      if (titleMatch) score += 1.0;
      if (contentMatch) score += 0.5;
      if (entityMatch) score += 0.3;

      results.push({
        ...item,
        search_score: score,
        search_method: 'text',
      });
    }
  }

  return results.sort((a, b) => b.search_score - a.search_score);
}

function vectorSearch(vectors, knowledge, query, options = {}) {
  const queryEmbed = createQueryEmbedding(query);
  const results = [];

  for (const vector of vectors) {
    const similarity = cosineSimilarity(queryEmbed, vector.embedding);

    // Find corresponding knowledge item
    const knowledgeItem = knowledge.find(k => k.id === vector.id);
    if (!knowledgeItem) continue;

    // Apply filters
    if (options.type && knowledgeItem.type !== options.type) continue;
    if (options.minConfidence && knowledgeItem.confidence < options.minConfidence) continue;

    if (similarity > 0.3) { // Threshold
      results.push({
        ...knowledgeItem,
        search_score: similarity,
        search_method: 'vector',
      });
    }
  }

  return results.sort((a, b) => b.search_score - a.search_score);
}

function hybridSearch(knowledge, vectors, query, options = {}) {
  // Combine text and vector search
  const textResults = textSearch(knowledge, query, options);
  const vectorResults = vectorSearch(vectors, knowledge, query, options);

  // Merge and deduplicate
  const resultsMap = new Map();

  for (const result of textResults) {
    resultsMap.set(result.id, {
      ...result,
      text_score: result.search_score,
      vector_score: 0,
    });
  }

  for (const result of vectorResults) {
    if (resultsMap.has(result.id)) {
      resultsMap.get(result.id).vector_score = result.search_score;
    } else {
      resultsMap.set(result.id, {
        ...result,
        text_score: 0,
        vector_score: result.search_score,
      });
    }
  }

  // Calculate hybrid score
  const hybridResults = Array.from(resultsMap.values()).map(item => ({
    ...item,
    search_score: (item.text_score * 0.6) + (item.vector_score * 0.4),
    search_method: 'hybrid',
  }));

  return hybridResults.sort((a, b) => b.search_score - a.search_score);
}

function displayResults(results, query) {
  console.log('═'.repeat(80));
  console.log(`  🔍 SEARCH RESULTS FOR: "${query}"`);
  console.log('═'.repeat(80));
  console.log(`  Found ${results.length} results\n`);

  if (results.length === 0) {
    console.log('  No results found.\n');
    return;
  }

  for (let i = 0; i < Math.min(results.length, 10); i++) {
    const item = results[i];
    console.log(`${i + 1}. ${item.title}`);
    console.log(`   Type: ${item.type}`);
    console.log(`   Confidence: ${item.confidence.toFixed(2)} | Score: ${item.search_score.toFixed(3)} | Method: ${item.search_method}`);
    console.log(`   ${item.content.substring(0, 200)}${item.content.length > 200 ? '...' : ''}`);
    console.log(`   Entities: ${(item.entities || []).join(', ')}`);
    console.log(`   Source: ${item.source_path}`);
    console.log(`   Model: ${item.model_used} | Extracted: ${new Date(item.extracted_at).toLocaleString()}`);
    console.log();
  }

  if (results.length > 10) {
    console.log(`  ... and ${results.length - 10} more results`);
    console.log();
  }

  console.log('═'.repeat(80));
}

// CLI
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help')) {
    console.log(`
Usage: node disseminator-search.js [options] "query"

Options:
  --type=TYPE              Filter by extraction type
  --min-confidence=N       Minimum confidence (0.0-1.0)
  --method=text|vector|hybrid   Search method (default: hybrid)

Examples:
  node disseminator-search.js "IFD endpoint"
  node disseminator-search.js --type=cicd_pipeline_knowledge "gitlab"
  node disseminator-search.js --min-confidence=0.8 "deployment"
  node disseminator-search.js --method=vector "kubernetes"
`);
    process.exit(0);
  }

  // Parse options
  const options = {};
  let query = '';

  for (const arg of args) {
    if (arg.startsWith('--type=')) {
      options.type = arg.split('=')[1];
    } else if (arg.startsWith('--min-confidence=')) {
      options.minConfidence = parseFloat(arg.split('=')[1]);
    } else if (arg.startsWith('--method=')) {
      options.method = arg.split('=')[1];
    } else {
      query += (query ? ' ' : '') + arg;
    }
  }

  if (!query) {
    console.error('Error: Query required');
    process.exit(1);
  }

  // Load data
  const knowledge = loadKnowledge();
  const vectors = loadVectors();

  if (knowledge.length === 0) {
    console.error('No knowledge base found. Run disseminator-learner.js first.');
    process.exit(1);
  }

  // Search
  let results;
  const method = options.method || 'hybrid';

  if (method === 'text') {
    results = textSearch(knowledge, query, options);
  } else if (method === 'vector') {
    results = vectorSearch(vectors, knowledge, query, options);
  } else {
    results = hybridSearch(knowledge, vectors, query, options);
  }

  displayResults(results, query);
}

module.exports = {
  textSearch,
  vectorSearch,
  hybridSearch,
};
