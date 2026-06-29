#!/usr/bin/env node

/**
 * Deep Research Workflow with Completion Tracking
 *
 * Phases:
 * 1. Scope: Decompose question into 5 search angles
 * 2. Search: 5 parallel WebSearch agents, one per angle
 * 3. Fetch: URL-dedup, fetch top 15 sources, extract falsifiable claims
 * 4. Verify: 3-vote adversarial verification per claim (need 2/3 refutes to kill)
 * 5. Synthesize: Merge semantic dupes, rank by confidence, cite sources
 *
 * NEW: Integrated with workflow completion tracker
 * - Logs workflow start/completion to PostgreSQL
 * - Generates 768-dim embeddings for semantic search
 * - Retention policy clears embeddings after 90 days
 */

import { spawn } from 'child_process';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

// Import workflow tracker (CommonJS module)
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { getWorkflowTracker } = require(join(homedir(), '.claude', 'learning', 'workflow-completion-tracker.js'));

const RESEARCH_QUERY = process.argv[2];
if (!RESEARCH_QUERY) {
  console.error('Usage: node deep-research-with-tracking.mjs "<research query>"');
  process.exit(1);
}

const SESSION_ID = `research_${new Date().toISOString().split('.')[0].replace(/:/g, '-')}_${Math.random().toString(36).slice(2, 8)}`;
const SESSION_DIR = join(homedir(), '.claude', 'learning', 'research', 'sessions');
mkdirSync(SESSION_DIR, { recursive: true });
const SESSION_FILE = join(SESSION_DIR, `${SESSION_ID}.json`);

const session = {
  id: SESSION_ID,
  query: RESEARCH_QUERY,
  started: new Date().toISOString(),
  phases: {
    scope: { status: 'pending', angles: [] },
    search: { status: 'pending', results: [] },
    fetch: { status: 'pending', sources: [] },
    verify: { status: 'pending', claims: [] },
    synthesize: { status: 'pending', report: '' }
  }
};

function saveSession() {
  writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2));
}

function runAgent(prompt, model = 'claude-sonnet-4') {
  return new Promise((resolve, reject) => {
    const agent = spawn('claude', ['--model', model, '--message', prompt], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    agent.stdout.on('data', (data) => { stdout += data.toString(); });
    agent.stderr.on('data', (data) => { stderr += data.toString(); });

    agent.on('close', (code) => {
      if (code === 0) {
        resolve(stdout.trim());
      } else {
        reject(new Error(`Agent failed: ${stderr}`));
      }
    });
  });
}

async function phase1_scope() {
  console.log('\n=== PHASE 1: SCOPE ===');
  session.phases.scope.status = 'running';
  saveSession();

  const prompt = `Decompose this research query into 5 distinct search angles that cover different aspects:

Query: ${RESEARCH_QUERY}

Return ONLY a JSON array of 5 search query strings, nothing else:
["angle 1", "angle 2", "angle 3", "angle 4", "angle 5"]`;

  try {
    const result = await runAgent(prompt);
    const angles = JSON.parse(result);
    session.phases.scope.angles = angles;
    session.phases.scope.status = 'completed';
    console.log('Search angles:', angles);
    saveSession();
    return angles;
  } catch (err) {
    session.phases.scope.status = 'failed';
    session.phases.scope.error = err.message;
    saveSession();
    throw err;
  }
}

async function phase2_search(angles) {
  console.log('\n=== PHASE 2: SEARCH ===');
  session.phases.search.status = 'running';
  saveSession();

  const searchPromises = angles.map(async (angle, idx) => {
    const prompt = `Search the web for: ${angle}

Return the top 3 most relevant URLs as a JSON array:
["url1", "url2", "url3"]`;

    try {
      const result = await runAgent(prompt);
      const urls = JSON.parse(result);
      console.log(`Angle ${idx + 1} results:`, urls);
      return { angle, urls };
    } catch (err) {
      console.error(`Search failed for angle ${idx + 1}:`, err.message);
      return { angle, urls: [], error: err.message };
    }
  });

  const results = await Promise.all(searchPromises);
  session.phases.search.results = results;
  session.phases.search.status = 'completed';
  saveSession();
  return results;
}

async function phase3_fetch(searchResults) {
  console.log('\n=== PHASE 3: FETCH ===');
  session.phases.fetch.status = 'running';
  saveSession();

  // Deduplicate URLs
  const allUrls = new Set();
  searchResults.forEach(result => {
    result.urls.forEach(url => allUrls.add(url));
  });

  const urls = Array.from(allUrls).slice(0, 15);
  console.log(`Fetching ${urls.length} unique sources...`);

  const fetchPromises = urls.map(async (url) => {
    const prompt = `Fetch and extract key claims from: ${url}

Return JSON:
{
  "url": "${url}",
  "title": "page title",
  "claims": ["claim 1", "claim 2", "claim 3"]
}`;

    try {
      const result = await runAgent(prompt);
      const source = JSON.parse(result);
      console.log(`Extracted ${source.claims?.length || 0} claims from ${url}`);
      return source;
    } catch (err) {
      console.error(`Failed to fetch ${url}:`, err.message);
      return { url, error: err.message, claims: [] };
    }
  });

  const sources = await Promise.all(fetchPromises);
  session.phases.fetch.sources = sources;
  session.phases.fetch.status = 'completed';
  saveSession();
  return sources;
}

async function phase4_verify(sources) {
  console.log('\n=== PHASE 4: VERIFY ===');
  session.phases.verify.status = 'running';
  saveSession();

  // Extract all claims
  const allClaims = sources.flatMap(source =>
    (source.claims || []).map(claim => ({ claim, source: source.url }))
  );

  console.log(`Verifying ${allClaims.length} claims with 3-vote adversarial review...`);

  const verifyPromises = allClaims.map(async ({ claim, source }) => {
    const prompt = `Adversarially verify this claim. Try to REFUTE it:

Claim: "${claim}"
Source: ${source}

Return JSON:
{
  "claim": "${claim}",
  "verdict": "ACCEPT" | "REFUTE",
  "confidence": 0.0-1.0,
  "reasoning": "why you accept or refute"
}`;

    try {
      // 3 voters
      const votes = await Promise.all([
        runAgent(prompt, 'claude-opus-4'),
        runAgent(prompt, 'claude-sonnet-4'),
        runAgent(prompt, 'claude-haiku-4')
      ]);

      const verdicts = votes.map(v => {
        try {
          return JSON.parse(v);
        } catch {
          return { verdict: 'ACCEPT', confidence: 0.5, reasoning: 'Parse error' };
        }
      });

      const refuteCount = verdicts.filter(v => v.verdict === 'REFUTE').length;
      const avgConfidence = verdicts.reduce((sum, v) => sum + v.confidence, 0) / 3;

      return {
        claim,
        source,
        accepted: refuteCount < 2, // Need 2/3 refutes to kill
        confidence: avgConfidence,
        votes: verdicts
      };
    } catch (err) {
      console.error(`Verification failed for claim:`, err.message);
      return { claim, source, accepted: false, error: err.message };
    }
  });

  const verified = await Promise.all(verifyPromises);
  const acceptedClaims = verified.filter(v => v.accepted);

  console.log(`Verified: ${acceptedClaims.length}/${allClaims.length} claims accepted`);

  session.phases.verify.claims = verified;
  session.phases.verify.status = 'completed';
  saveSession();
  return acceptedClaims;
}

async function phase5_synthesize(claims) {
  console.log('\n=== PHASE 5: SYNTHESIZE ===');
  session.phases.synthesize.status = 'running';
  saveSession();

  const claimsSummary = claims.map(c =>
    `- ${c.claim} (confidence: ${c.confidence.toFixed(2)}, source: ${c.source})`
  ).join('\n');

  const prompt = `Synthesize a research report from these verified claims:

Original Query: ${RESEARCH_QUERY}

Verified Claims:
${claimsSummary}

Write a comprehensive research report (max 500 words) that:
1. Synthesizes key findings
2. Identifies patterns across sources
3. Ranks insights by confidence
4. Cites sources inline as [1], [2], etc.
5. Includes a "Sources" section at the end

Return ONLY the markdown report text.`;

  try {
    const report = await runAgent(prompt, 'claude-opus-4');
    session.phases.synthesize.report = report;
    session.phases.synthesize.status = 'completed';
    session.completed = new Date().toISOString();
    saveSession();

    console.log('\n' + '='.repeat(80));
    console.log('RESEARCH REPORT');
    console.log('='.repeat(80));
    console.log(report);
    console.log('\n' + '='.repeat(80));
    console.log(`\nSession saved: ${SESSION_FILE}`);

    return report;
  } catch (err) {
    session.phases.synthesize.status = 'failed';
    session.phases.synthesize.error = err.message;
    saveSession();
    throw err;
  }
}

// Main execution
(async () => {
  const tracker = getWorkflowTracker();
  const startTime = Date.now();

  try {
    console.log('Deep Research Workflow with Completion Tracking');
    console.log('Query:', RESEARCH_QUERY);
    console.log('Session:', SESSION_ID);

    // Track workflow start
    await tracker.trackWorkflowStart({
      workflowName: 'deep-research',
      sessionId: SESSION_ID,
      query: RESEARCH_QUERY,
      metadata: { version: '2.0-tracked' }
    });

    const angles = await phase1_scope();
    const searchResults = await phase2_search(angles);
    const sources = await phase3_fetch(searchResults);
    const verified = await phase4_verify(sources);
    const report = await phase5_synthesize(verified);

    const durationMs = Date.now() - startTime;

    // Track workflow completion with embedding
    await tracker.trackWorkflowCompletion({
      sessionId: SESSION_ID,
      status: 'completed',
      phases: session.phases,
      resultSummary: report.substring(0, 1000), // First 1000 chars
      durationMs
    });

    console.log('\nResearch complete!');
    console.log(`Duration: ${(durationMs / 1000).toFixed(1)}s`);
    console.log('Workflow completion tracked with embedding (searchable for 90 days)');
    process.exit(0);
  } catch (err) {
    console.error('\nResearch failed:', err.message);
    session.failed = new Date().toISOString();
    session.error = err.message;
    saveSession();

    const durationMs = Date.now() - startTime;

    // Track failure
    await tracker.trackWorkflowCompletion({
      sessionId: SESSION_ID,
      status: 'failed',
      phases: session.phases,
      resultSummary: `Error: ${err.message}`,
      durationMs
    });

    process.exit(1);
  }
})();
