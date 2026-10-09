#!/usr/bin/env node
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const hook = path.join(root, 'hooks', 'session-end-memory-capture.js');
const requests = [];
let responseStatus = 200;
let responseBody = { ok: true, status: 'stored', event_id: 'fixture' };
const server = http.createServer((req, res) => {
  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', () => {
    requests.push({ method: req.method, url: req.url, body: JSON.parse(body) });
    res.writeHead(responseStatus, { 'content-type': 'application/json' });
    res.end(JSON.stringify(responseBody));
  });
});
const port = await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', () => resolve(server.address().port));
});
function run(input, url = `http://127.0.0.1:${port}`) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [hook], { env: { ...process.env, FLOSSWARE_MEMORY_URL: url }, stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.once('error', reject);
    child.once('close', code => resolve({ code, stdout, stderr }));
    child.stdin.end(JSON.stringify(input));
  });
}
try {
  const event = { hook_event_name: 'SessionEnd', session_id: 'session-123', transcript_path: '/private/not-sent.jsonl' };
  const first = await run(event);
  assert.equal(first.code, 0);
  assert.equal(first.stdout, '');
  assert.equal(first.stderr, '');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].method, 'POST');
  assert.equal(requests[0].url, '/memory/append-once');
  assert.equal(requests[0].body.name, 'session_events');
  assert.match(requests[0].body.event_id, /^claude-code:session-end:[a-f0-9]{64}$/);
  assert.deepEqual(requests[0].body.entry, { event_type: 'claude_code.session_end', hook_event_name: 'SessionEnd', session_id: 'session-123', source: 'claude-code' });
  assert.equal(JSON.stringify(requests[0].body).includes('transcript_path'), false);
  responseBody = { ok: true, status: 'duplicate', event_id: requests[0].body.event_id };
  const second = await run(event);
  assert.equal(second.code, 0);
  assert.equal(requests.length, 2);
  assert.equal(requests[1].body.event_id, requests[0].body.event_id);
  assert.deepEqual(requests[1].body.entry, requests[0].body.entry);
  const missing = await run({ hook_event_name: 'SessionEnd' });
  assert.equal(missing.code, 0);
  assert.match(missing.stderr, /no session_id/);
  responseStatus = 503;
  responseBody = { ok: false, error: 'unavailable' };
  const rejected = await run(event);
  assert.equal(rejected.code, 0);
  assert.match(rejected.stderr, /Memory capture unavailable/);
} finally {
  await new Promise(resolve => server.close(resolve));
}
console.log('SessionEnd Memory capture tests passed');
