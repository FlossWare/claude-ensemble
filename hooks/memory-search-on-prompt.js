#!/usr/bin/env node
/**
 * Memory Search Hook - Triggered on User Prompt
 *
 * Non-blocking Claude Code UserPromptSubmit hook. Searches local Markdown
 * memories when the prompt asks for remembered/prior context.
 *
 * The repository is an ES-module package, so this hook intentionally uses
 * ESM imports. The deployed hook keeps its .js extension.
 */

import fs from 'node:fs';
import path from 'node:path';

const MEMORY_DIR = process.env.CLAUDE_MEMORY || `${process.env.HOME}/.claude/memory`;
const KEYWORDS = ['remember', 'recall', 'context', 'feedback', 'earlier', 'before', 'prior'];

function extractQuery(prompt) {
  for (const kw of KEYWORDS) {
    const regex = new RegExp(`\\\\b${kw}\\\\b[^?!.]*?([a-z][a-z0-9\\\\s\\\\-/]+)`, 'i');
    const match = prompt.match(regex);
    if (match) return match[1].trim();
  }
  return null;
}

function tfIdfSearch(query, memories) {
  const queryTerms = query.toLowerCase().split(/\\s+/);
  return memories.map(mem => {
    const content = `${mem.name} ${mem.description} ${mem.content || ''}`.toLowerCase();
    let score = 0;
    for (const term of queryTerms) {
      const regex = new RegExp(`\\\\b${term}\\\\b`, 'g');
      score += (content.match(regex) || []).length;
    }
    return { ...mem, tfidf_score: score };
  }).filter(m => m.tfidf_score > 0)
    .sort((a, b) => b.tfidf_score - a.tfidf_score)
    .slice(0, 10);
}

function loadMemories() {
  if (!fs.existsSync(MEMORY_DIR)) return [];

  const memories = [];
  const files = fs.readdirSync(MEMORY_DIR)
    .filter(file => file.endsWith('.md') && file !== 'MEMORY.md');

  for (const file of files) {
    const content = fs.readFileSync(path.join(MEMORY_DIR, file), 'utf8');
    const lines = content.split('\n');
    let name = file.replace(/\.md$/, '');
    let description = '';
    let type = 'reference';

    for (const line of lines) {
      if (line.startsWith('name:')) name = line.split(':')[1].trim();
      else if (line.startsWith('description:')) description = line.split(':')[1].trim();
      else if (line.includes('type:')) type = line.split(':')[1].trim();
    }

    memories.push({
      file,
      name,
      description,
      type,
      content: lines.slice(5).join('\n').slice(0, 300)
    });
  }

  return memories;
}

function reciprocalRankFusion(tfidfResults, weight = 0.6, k = 60) {
  const scores = {};
  for (let i = 0; i < tfidfResults.length; i++) {
    const file = tfidfResults[i].file;
    scores[file] = (scores[file] || 0) + weight / (k + i + 1);
  }

  return Object.entries(scores)
    .sort((a, b) => b[1] - a[1])
    .map(([file, score]) => ({
      ...tfidfResults.find(memory => memory.file === file),
      final_score: score
    }))
    .slice(0, 3);
}

try {
  const prompt = process.env.CLAUDE_PROMPT || '';
  const query = extractQuery(prompt);

  if (!query) process.exit(0);

  console.error(`\\n🧠 Memory Search: "${query}"`);

  const memories = loadMemories();
  if (memories.length === 0) {
    console.error('   (No memories found)');
    process.exit(0);
  }

  const tfidfResults = tfIdfSearch(query, memories);
  if (tfidfResults.length === 0) {
    console.error('   (No matching memories)');
    process.exit(0);
  }

  console.error('\\n📌 Relevant Memories:');
  reciprocalRankFusion(tfidfResults).forEach((mem, i) => {
    console.error(`   ${i + 1}. ${mem.name} [${mem.type}]`);
    console.error(`      ${mem.description}`);
    console.error(`      File: ${mem.file}`);
  });
  console.error('');
} catch (error) {
  // UserPromptSubmit must never block Claude Code.
  console.error(`Error in memory search: ${error.message}`);
}
