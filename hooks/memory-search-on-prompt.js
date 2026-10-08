#!/usr/bin/env node

/**
 * Canonical Claude Code context retrieval hook.
 *
 * UserPromptSubmit is the single prompt-time context retrieval path.
 * Retrieval is relevance-driven: the complete user prompt is the query.
 *
 * The Memory service is shared infrastructure, but results are separated
 * into two contracts:
 *   - Memory: episodic/experience records, what happened.
 *   - Knowledge: durable Claude Code documents, what is currently known.
 *
 * The hook is non-blocking and fail-open. It deliberately does not inspect
 * magic prompt keywords such as "remember" or "recall".
 */

const MEMORY_URL = process.env.FLOSSWARE_MEMORY_URL || 'http://127.0.0.1:8767';
const MEMORY_SEARCH_PATH = '/memory/search';
const REQUEST_TIMEOUT_MS = Number.parseInt(process.env.FLOSSWARE_MEMORY_TIMEOUT_MS || '1500', 10);
const MAX_CONTEXT_CHARS = 12000;
const MAX_RESULTS = 10;

function buildSearchUrl() {
  return new URL(MEMORY_SEARCH_PATH, MEMORY_URL.endsWith('/') ? MEMORY_URL : `${MEMORY_URL}/`).toString();
}

function resultText(result) {
  if (!result || typeof result !== 'object') return '';
  if (typeof result.content !== 'string') return '';
  return result.content.trim();
}

function resultSource(result) {
  const file = typeof result?.file === 'string' ? result.file : '';
  const source = typeof result?.source === 'string' ? result.source : '';
  return source === 'claude-code' || file.startsWith('claude-code-') ? 'knowledge' : 'memory';
}

function dedupeResults(results) {
  const seen = new Set();
  const deduped = [];

  for (const result of results) {
    const content = resultText(result);
    if (!content) continue;

    const key = [
      resultSource(result),
      result.file || '',
      result.section || '',
      content,
    ].join('\u0000');

    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push({ ...result, content });
  }

  return deduped;
}

function extractResults(payload) {
  if (!payload || typeof payload !== 'object' || payload.ok !== true) return [];
  return Array.isArray(payload.results) ? dedupeResults(payload.results) : [];
}

function partitionResults(results) {
  const memory = [];
  const knowledge = [];

  for (const result of results.slice(0, MAX_RESULTS)) {
    (resultSource(result) === 'knowledge' ? knowledge : memory).push(result);
  }

  return { memory, knowledge };
}

function formatContext(query, payload) {
  const results = extractResults(payload);
  const { memory, knowledge } = partitionResults(results);
  if (!memory.length && !knowledge.length) return '';

  const lines = [
    'Relevant Claude Ensemble Context:',
    `Query: ${query}`,
    '',
  ];

  if (memory.length) {
    lines.push('### Relevant Memory (what happened)');
    for (const [index, result] of memory.entries()) {
      lines.push(`[${index + 1}] ${result.content}`);
    }
    lines.push('');
  }

  if (knowledge.length) {
    lines.push('### Relevant Knowledge (what is currently known)');
    for (const [index, result] of knowledge.entries()) {
      lines.push(`[${index + 1}] ${result.content}`);
    }
  }

  let context = lines.join('\n').trim();
  if (context.length > MAX_CONTEXT_CHARS) {
    context = context.slice(0, MAX_CONTEXT_CHARS) + '\n[Context truncated]';
  }

  return context;
}

function contextDedupeKey(query) {
  let hash = 2166136261;
  for (let index = 0; index < query.length; index += 1) {
    hash ^= query.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

async function readHookEvent() {
  if (process.env.CLAUDE_PROMPT) {
    return { prompt: process.env.CLAUDE_PROMPT };
  }
  if (process.stdin.isTTY) return { prompt: '' };

  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  const input = Buffer.concat(chunks).toString('utf8');
  if (!input.trim()) return { prompt: '' };

  try {
    const event = JSON.parse(input);
    return {
      prompt: typeof event.prompt === 'string' ? event.prompt : '',
      sessionId: typeof event.session_id === 'string' ? event.session_id : '',
    };
  } catch {
    return { prompt: '' };
  }
}

async function searchContext(query) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(buildSearchUrl(), {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
      },
      body: JSON.stringify({ query, limit: MAX_RESULTS }),
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
  const event = await readHookEvent();
  const query = typeof event.prompt === 'string' ? event.prompt.trim() : '';
  if (!query) return;

  try {
    const payload = await searchContext(query);
    const additionalContext = formatContext(query, payload);
    if (!additionalContext) return;

    const results = extractResults(payload);
    const { memory, knowledge } = partitionResults(results);
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'UserPromptSubmit',
        additionalContext,
        contextRetrieval: {
          queryHash: contextDedupeKey(query),
          memoryCount: memory.length,
          knowledgeCount: knowledge.length,
        },
      },
    }) + '\n');
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Memory search unavailable: ${message}\n`);
  }
}

main().catch(error => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`Memory search unavailable: ${message}\\n`);
});
