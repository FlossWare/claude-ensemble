#!/usr/bin/env node

/**
 * Canonical SessionEnd capture adapter.
 *
 * Captures only stable, non-transcript session metadata. It never reads the
 * transcript, triggers Learning, mutates learner state, or promotes Knowledge.
 * Delivery is idempotent through Memory's append-once endpoint.
 */
import { createHash } from 'node:crypto';

const MEMORY_URL = process.env.FLOSSWARE_MEMORY_URL || 'http://127.0.0.1:8767';
const REQUEST_TIMEOUT_MS = Number.parseInt(process.env.FLOSSWARE_MEMORY_TIMEOUT_MS || '1500', 10);
const EVENT_NAME = 'claude_code.session_end';

function readEvent() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', chunk => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
    process.stdin.on('error', reject);
    process.stdin.on('end', () => {
      try {
        const input = Buffer.concat(chunks).toString('utf8');
        resolve(input.trim() ? JSON.parse(input) : {});
      } catch {
        reject(new Error('invalid Claude Code hook JSON'));
      }
    });
  });
}

function eventId(sessionId) {
  const digest = createHash('sha256').update(sessionId, 'utf8').digest('hex');
  return `claude-code:session-end:${digest}`;
}

async function capture(event) {
  const sessionId = typeof event?.session_id === 'string' ? event.session_id.trim() : '';
  if (!sessionId) {
    process.stderr.write('Memory capture skipped: SessionEnd event has no session_id\n');
    return;
  }

  // Keep the entry deterministic so retries have the same payload digest.
  const entry = {
    event_type: EVENT_NAME,
    hook_event_name: 'SessionEnd',
    session_id: sessionId,
    source: 'claude-code',
  };
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const endpoint = new URL('/memory/append-once', MEMORY_URL.endsWith('/') ? MEMORY_URL : `${MEMORY_URL}/`);
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ name: 'session_events', event_id: eventId(sessionId), entry }),
      signal: controller.signal,
    });
    let result;
    try {
      result = await response.json();
    } catch {
      throw new Error(`Memory service returned invalid JSON (HTTP ${response.status})`);
    }
    if (!response.ok || result?.ok !== true || !['stored', 'duplicate'].includes(result?.status)) {
      throw new Error(result?.error || `Memory service rejected capture (HTTP ${response.status})`);
    }
  } finally {
    clearTimeout(timeout);
  }
}

async function main() {
  try {
    await capture(await readEvent());
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Memory capture unavailable: ${message}\n`);
  }
}

main().catch(error => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`Memory capture unavailable: ${message}\n`);
});
