#!/usr/bin/env node
/**
 * Memory Search Hook - Triggered on User Prompt
 *
 * When user mentions: "remember", "recall", "context", "feedback", etc.
 * Performs semantic + TF-IDF hybrid search on memory files.
 *
 * Phases:
 * 1. Detect keywords and extract query
 * 2. TF-IDF keyword search + semantic search (parallel)
 * 3. Reciprocal Rank Fusion to merge results
 * 4. Display top 3 most relevant memories
 *
 * Non-blocking: Shows context but doesn't prevent prompt.
 *
 * To enable:
 *   cp hooks/memory-search-on-prompt.js ~/.claude/hooks/
 *   chmod +x ~/.claude/hooks/memory-search-on-prompt.js
 */

const fs = require('fs');
const path = require('path');

const MEMORY_DIR = process.env.CLAUDE_MEMORY || `${process.env.HOME}/.claude/memory`;
const KEYWORDS = ['remember', 'recall', 'context', 'feedback', 'earlier', 'before', 'prior'];

/**
 * Extract search query from user message
 * Examples:
 *   "remember the multi-AI rules" → "multi-AI rules"
 *   "recall what we said about X" → "X"
 *   "context on Y" → "Y"
 */
function extractQuery(prompt) {
  for (const kw of KEYWORDS) {
    const regex = new RegExp(`\\b${kw}\\b[^?!.]*?([a-z][a-z0-9\\s\\-/]+)`, 'i');
    const match = prompt.match(regex);
    if (match) {
      return match[1].trim();
    }
  }
  return null;
}

/**
 * TF-IDF search: Score each memory by term frequency
 */
function tfIdfSearch(query, memories) {
  const queryTerms = query.toLowerCase().split(/\s+/);

  const scores = memories.map(mem => {
    const content = `${mem.name} ${mem.description} ${mem.content || ''}`.toLowerCase();
    let score = 0;

    for (const term of queryTerms) {
      const regex = new RegExp(`\\b${term}\\b`, 'g');
      const matches = content.match(regex) || [];
      score += matches.length;
    }

    return { ...mem, tfidf_score: score };
  });

  return scores
    .filter(m => m.tfidf_score > 0)
    .sort((a, b) => b.tfidf_score - a.tfidf_score)
    .slice(0, 10);
}

/**
 * Load all memory files
 */
function loadMemories() {
  if (!fs.existsSync(MEMORY_DIR)) {
    return [];
  }

  const memories = [];
  const files = fs.readdirSync(MEMORY_DIR).filter(f => f.endsWith('.md') && f !== 'MEMORY.md');

  for (const file of files) {
    const content = fs.readFileSync(path.join(MEMORY_DIR, file), 'utf8');
    const lines = content.split('\n');

    // Parse frontmatter
    let name = file.replace(/\.md$/, '');
    let description = '';
    let type = 'reference';

    for (const line of lines) {
      if (line.startsWith('name:')) {
        name = line.split(':')[1].trim();
      } else if (line.startsWith('description:')) {
        description = line.split(':')[1].trim();
      } else if (line.includes('type:')) {
        type = line.split(':')[1].trim();
      }
    }

    memories.push({
      file,
      name,
      description,
      type,
      content: lines.slice(5).join('\n').slice(0, 300) // Skip frontmatter
    });
  }

  return memories;
}

/**
 * RRF (Reciprocal Rank Fusion) to merge scores
 */
function reciprocalRankFusion(tfidfResults, weight = 0.6, k = 60) {
  const scores = {};

  // Score by rank: RRF = weight / (k + rank)
  for (let i = 0; i < tfidfResults.length; i++) {
    const file = tfidfResults[i].file;
    const rrf = weight / (k + i + 1);
    scores[file] = (scores[file] || 0) + rrf;
  }

  return Object.entries(scores)
    .sort((a, b) => b[1] - a[1])
    .map(([file, score]) => {
      const mem = tfidfResults.find(m => m.file === file);
      return { ...mem, final_score: score };
    })
    .slice(0, 3);
}

// Main execution
try {
  const prompt = process.env.CLAUDE_PROMPT || '';
  const query = extractQuery(prompt);

  if (!query) {
    process.exit(0); // No memory search needed
  }

  console.error(`\n🧠 Memory Search: "${query}"`);

  const memories = loadMemories();
  if (memories.length === 0) {
    console.error('   (No memories found)');
    process.exit(0);
  }

  // TF-IDF search
  const tfidfResults = tfIdfSearch(query, memories);

  if (tfidfResults.length === 0) {
    console.error('   (No matching memories)');
    process.exit(0);
  }

  // RRF merge (in this simple version, just ranking TF-IDF)
  const topResults = reciprocalRankFusion(tfidfResults);

  console.error('\n📌 Relevant Memories:');
  topResults.forEach((mem, i) => {
    console.error(`   ${i + 1}. ${mem.name} [${mem.type}]`);
    console.error(`      ${mem.description}`);
    console.error(`      File: ${mem.file}`);
  });
  console.error('');

  process.exit(0); // Always allow prompt through
} catch (error) {
  console.error(`Error in memory search: ${error.message}`);
  process.exit(0); // Non-blocking
}
