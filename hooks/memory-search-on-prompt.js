#!/usr/bin/env node

/**
 * Memory Search Hook - Triggered on User Prompt
 *
 * Non-blocking Claude Code UserPromptSubmit hook. Queries the canonical
 * Claude Ensemble Memory REST service and injects relevant Knowledge into
 * Claude's context.
 *
 * The hook deliberately has no local memory-search implementation. The
 * Memory service is the canonical Knowledge boundary.
 */

const MEMORY_URL = process.env.FLOSSWARE_MEMORY_URL || 'http://127.0.0.1:8767';
const MEMORY_SEARCH_PATH = '/memory/search';
const REQUEST_TIMEOUT_MS = Number.parseInt(process.env.FLOSSWARE_MEMORY_TIMEOUT_MS || '1500', 10);
const MAX_CONTEXT_CHARS = 12000;
const KEYWORDS = ['remember', 'recall', 'context', 'feedback', 'earlier', 'before', 'prior', 'decided'];

function extractQuery(prompt) {
  const text = typeof prompt === 'string' ? prompt.trim() : '';
  if (!text) return null;

  for (const keyword of KEYWORDS) {
    const match = text.match(new RegExp(`\\b${keyword}\\b`, 'i'));
    if (match) {
      const query = text.slice(match.index).replace(/^[^a-z0-9]+/i, '').trim();
      return query || text;
    }
  }

  return null;
}

async function readHookPrompt() {
  if (process.env.CLAUDE_PROMPT) return process.env.CLAUDE_PROMPT;
  if (process.stdin.isTTY) return '';

  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  if (!input.trim()) return '';

  try {
    const event = JSON.parse(input);
    return typeof event.prompt === 'string' ? event.prompt : '';
  } catch {
    return '';
  }
}

function buildSearchUrl() {
  return new URL(MEMORY_SEARCH_PATH, MEMORY_URL.endsWith('/') ? MEMORY_URL : `${MEMORY_URL}/`).toString();
}

function extractResults(payload) {
  if (!payload || typeof payload !== 'object' || payload.ok !== true) return [];
  return Array.isArray(payload.results) ? payload.results : [];
}

function resultText(result) {
  if (typeof result === 'string') return result;

  if (!result || typeof result !== 'object') return '';

  const fields = [
    result.content,
    result.text,
    result.body,
    result.memory,
    result.document,
    result.summary,
    result.description,
    result.name,
  ];

  return fields
    .filter(value => typeof value === 'string' && value.trim())
    .join('\n')
    .trim();
}

function formatContext(query, payload) {
  const results = extractResults(payload)
    .map(resultText)
    .filter(Boolean)
    .slice(0, 10);

  if (!results.length) return '';

  let context = [
    'Relevant Claude Ensemble Knowledge:',
    `Memory query: ${query}`,
    '',
    ...results.map((value, index) => `[${index + 1}] ${value}`),
  ].join('\n');

  if (context.length > MAX_CONTEXT_CHARS) {
    context = context.slice(0, MAX_CONTEXT_CHARS) + '\n[Knowledge truncated]';
  }

  return context;
}

async function searchMemory(query) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(buildSearchUrl(), {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
      },
      body: JSON.stringify({ query }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Memory service returned HTTP ${response.status}`);
    }

    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function main() {
  const prompt = await readHookPrompt();
  const query = extractQuery(prompt);
  if (!query) return;

  try {
    const payload = await searchMemory(query);
    const additionalContext = formatContext(query, payload);
    if (!additionalContext) return;

    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'UserPromptSubmit',
        additionalContext,
      },
    }) + '\n');
  } catch (error) {
    // Memory is augmentation, never a reason to block Claude Code.
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Memory search unavailable: ${message}\n`);
  }
}

main().catch(error => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`Memory search unavailable: ${message}\n`);
});
