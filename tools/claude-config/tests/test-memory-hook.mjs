#!/usr/bin/env node
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtemp, rm, cp } from 'node:fs/promises';
import os from 'node:os';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const hook = path.join(root, 'hooks', 'memory-search-on-prompt.js');

function runHook({ url, input, env = {}, hookPath = hook, cwd = root }) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [hookPath], {
      cwd,
      env: { ...process.env, ...env, FLOSSWARE_MEMORY_URL: url },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', code => resolve({ code, stdout, stderr }));

    child.stdin.end(JSON.stringify(input));
  });
}

function listen(server) {
  return new Promise((resolve, reject) => {
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
    server.on('error', reject);
  });
}

function close(server) {
  return new Promise(resolve => server.close(resolve));
}

const requests = [];
const server = http.createServer((req, res) => {
  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', () => {
    requests.push({ method: req.method, url: req.url, body });
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({
      ok: true,
      results: [
        {
          file: 'project-architecture',
          section: 'Claude Code and Claude Ensemble',
          score: 0.9,
          content: 'Claude Code is the host; Claude Ensemble is the augmentation layer.',
        },
      ],
    }));
  });
});

const port = await listen(server);
try {
  const result = await runHook({
    url: `http://127.0.0.1:${port}/`,
    input: {
      hook_event_name: 'UserPromptSubmit',
      prompt: 'Recall what we decided about Claude Ensemble relative to Claude Code',
    },
  });

  assert.equal(result.code, 0);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].method, 'POST');
  assert.equal(requests[0].url, '/memory/search');
  assert.deepEqual(JSON.parse(requests[0].body), {
    query: 'what we decided about Claude Ensemble relative to Claude Code',
  });

  const output = JSON.parse(result.stdout);
  assert.equal(output.hookSpecificOutput.hookEventName, 'UserPromptSubmit');
  assert.match(output.hookSpecificOutput.additionalContext, /Claude Code is the host/);

  // The deployed hook is copied outside the repository package scope. It must
  // remain executable there, where package.json cannot make .js files ESM.
  const standaloneDir = await mkdtemp(path.join(os.tmpdir(), 'flossware-memory-hook-'));
  const standaloneHook = path.join(standaloneDir, 'memory-search-on-prompt.js');
  await cp(hook, standaloneHook);
  try {
    const standalone = await runHook({
      url: `http://127.0.0.1:${port}/`,
      hookPath: standaloneHook,
      cwd: standaloneDir,
      input: {
        hook_event_name: 'UserPromptSubmit',
        prompt: 'Recall the standalone hook contract',
      },
    });
    assert.equal(standalone.code, 0);
    assert.match(JSON.parse(standalone.stdout).hookSpecificOutput.additionalContext, /augmentation layer/);
  } finally {
    await rm(standaloneDir, { recursive: true, force: true });
  }

  const noQuery = await runHook({
    url: `http://127.0.0.1:${port}/`,
    input: { hook_event_name: 'UserPromptSubmit', prompt: 'Fix the failing test' },
  });
  assert.equal(noQuery.code, 0);
  assert.equal(requests.length, 1);
  assert.equal(noQuery.stdout, '');

  const unavailable = await runHook({
    url: 'http://127.0.0.1:1/',
    input: {
      hook_event_name: 'UserPromptSubmit',
      prompt: 'Recall the architecture decision',
    },
  });
  assert.equal(unavailable.code, 0);
  assert.equal(unavailable.stdout, '');
  assert.match(unavailable.stderr, /Memory search unavailable/);
} finally {
  await close(server);
}

console.log('memory hook REST tests passed');
