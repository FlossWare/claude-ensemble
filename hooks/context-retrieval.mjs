#!/usr/bin/env node

/**
 * Canonical Claude Code context retrieval.
 *
 * This is the single prompt-context retrieval path for Claude Ensemble.
 * The Memory service remains the storage/retrieval authority; this module
 * defines the client-side contract and separates:
 *
 *   memory   = episodic/experience records about what happened
 *   knowledge = durable Claude Code documents about what is currently known
 *
 * The backend may share infrastructure, but callers must not collapse the
 * two concepts into one generic "memory" result.
 */

import crypto from 'node:crypto';

const MEMORY_URL = process.env.FLOSSWARE_MEMORY_URL || 'http://127.0.0.1:8767';
const MEMORY_SEARCH_PATH = '/memory/search';
const REQUEST_TIMEOUT_MS = Number.parseInt(process.env.FLOSSWARE_MEMORY_TIMEOUT_MS || '1500', 10);
const DEFAULT_LIMIT = 10;
const MAX_CONTEXT_CHARS = 12000;

function buildSearchUrl() {
  return new URL(MEMORY_SEARCH_PATH, MEMORY_URL.endsWith('/') ? MEMORY_URL : `${MEMORY_URL}/`).toString();
}

function resultText(result) {
  if (!result || typeof result !== 'object') return '';
  if (typeof result.content !== 'string') return '';
  return result.content.trim();
}

function sourceType(result) {
  const file = typeof result?.file === 'string' ? result.file : '';
  const source = typeof result?.source === 'string' ? result.source : '';
  return source === 'claude-code' || file.startsWith('claude-code-') ? 'knowledge' : 'memory';
}

function dedupeResults(results) {
  const seen = new Set();
  const output = [];

  for (const result of results) {
    const content = resultText(result);
    if (!content) continue;

    const key = [
      sourceType(result),
      result.file || '',
      result.section || '',
      content,
    ].join('\u0000');

    if (seen.has(key)) continue;
    seen.add(key);
    output.push({ ...result, content });
  }

  return output;
}

function extractResults(payload) {
  if (!payload || typeof payload !== 'object' || payload.ok !== true) return [];
  return Array.isArray(payload.results) ? dedupeResults(payload.results) : [];
}

async function searchContext(query, { limit = DEFAULT_LIMIT } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(buildSearchUrl(), {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
      },
      body: JSON.stringify({ query, limit }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Memory service returned HTTP ${response.status}`);
    }

    return extractResults(await response.json());
  } finally {
    clearTimeout(timer);
  }
}

function retrieveContext(query, options = {}) {
  const text = typeof query === 'string' ? query.trim() : '';
  if (!text) {
    return Promise.resolve({
      query: '',
      memory: [],
      knowledge: [],
      total: 0,
      dedupe_key: null,
    });
  }

  return searchContext(text, options).then(results => {
    const memory = results.filter(result => sourceType(result) === 'memory');
    const knowledge = results.filter(result => sourceType(result) === 'knowledge');

    return {
      query: text,
      memory,
      knowledge,
      total: memory.length + knowledge.length,
      dedupe_key: crypto.createHash('sha256').update(text, 'utf8').digest('hex'),
    };
  });
}

function formatContext(context) {
  if (!context || !context.total) return '';

  const sections = [];
  if (context.memory.length) {
    sections.push(
      '### Relevant Memory (what happened)',
      ...context.memory.map((item, index) => `[${index + 1}] ${item.content}`),
    );
  }
  if (context.knowledge.length) {
    sections.push(
      '### Relevant Knowledge (what is currently known)',
      ...context.knowledge.map((item, index) => `[${index + 1}] ${item.content}`),
    );
  }

  let output = ['Relevant Claude Ensemble Context:', `Query: ${context.query}`, '', ...sections].join('\n');
  if (output.length > MAX_CONTEXT_CHARS) {
    output = output.slice(0, MAX_CONTEXT_CHARS) + '\n[Context truncated]';
  }
  return output;
}

export {
  dedupeResults,
  extractResults,
  formatContext,
  retrieveContext,
  resultText,
  sourceType,
};
