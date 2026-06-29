#!/usr/bin/env node

/**
 * Deep Research Workflow with Always-On Adversarial Verification
 *
 * This is an example integration showing how adversarial verification
 * fits into existing consensus workflows.
 *
 * Flow:
 * 1. Decompose query into search angles (workers)
 * 2. Parallel web searches
 * 3. Fetch and extract claims from sources
 * 4. Arbiter synthesizes research report
 * 5. → ADVERSARIAL VERIFICATION ← (NEW)
 * 6. Store results to PostgreSQL
 *
 * Run: node workflows/deep-research-with-adversarial.mjs "research question"
 */

import { execSync } from 'child_process';
import pg from 'pg';
import { wrapWithAdversarialVerification } from '../shared/adversarial-verification-harness.mjs';
import { getWorkflowStorage } from '../shared/workflow-storage-adapter.cjs';

const { Pool } = pg;

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
});

// Research question from command line
const QUESTION = process.argv[2];
if (!QUESTION) {
  console.error('Usage: node deep-research-with-adversarial.mjs "research question"');
  process.exit(1);
}

const WORKFLOW_ID = `research-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const START_TIME = Date.now();
const db = getWorkflowStorage();

// Call Claude API via claude CLI (stub - replace with actual API)
function callClaude(prompt, model = 'claude-sonnet-4-5') {
  try {
    const result = execSync(
      `claude --print --model ${model} ${JSON.stringify(prompt)}`,
      { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024, timeout: 300000 }
    );
    return result.trim();
  } catch (err) {
    console.error(`⚠ Claude API call failed: ${err.message}`);
    return `Error: ${err.message}`;
  }
}

// PHASE 1: Decompose into search angles
async function phase1_decompose() {
  console.log('\n=== PHASE 1: DECOMPOSE ===');
  const phaseStart = Date.now();

  const prompt = `Decompose this research question into 5 distinct search angles:

Question: ${QUESTION}

Return ONLY a JSON array: ["angle 1", "angle 2", "angle 3", "angle 4", "angle 5"]`;

  const result = callClaude(prompt, 'claude-sonnet-4-5');

  try {
    const angles = JSON.parse(result);
    console.log(`✅ Decomposed into ${angles.length} angles`);
    return { angles, duration: Date.now() - phaseStart };
  } catch {
    // Fallback
    return {
      angles: [QUESTION, QUESTION, QUESTION, QUESTION, QUESTION],
      duration: Date.now() - phaseStart
    };
  }
}

// PHASE 2: Parallel search (workers)
async function phase2_search(angles, executionId) {
  console.log('\n=== PHASE 2: PARALLEL SEARCH (WORKERS) ===');
  const phaseStart = Date.now();

  const searchPromises = angles.map(async (angle, idx) => {
    const workerStart = Date.now();
    const prompt = `Search for: ${angle}\n\nReturn top 3 URLs as JSON: ["url1", "url2", "url3"]`;

    const result = callClaude(prompt, 'claude-haiku-4');

    try {
      const urls = JSON.parse(result);

      // Store worker result
      await db.storeWorkerResult({
        workflow_execution_id: executionId,
        worker_id: `search-worker-${idx + 1}`,
        model: 'claude-haiku-4',
        task_assigned: angle,
        result: JSON.stringify(urls),
        confidence: 0.8,
        duration_ms: Date.now() - workerStart,
        input_tokens: Math.ceil(prompt.length / 4),
        output_tokens: Math.ceil(result.length / 4),
        cost_usd: 0.0001, // Haiku is cheap
        outcome: 'success'
      });

      console.log(`   Worker ${idx + 1}: Found ${urls.length} URLs`);
      return urls;
    } catch {
      return [];
    }
  });

  const results = await Promise.all(searchPromises);
  const allUrls = [...new Set(results.flat())];

  console.log(`✅ Found ${allUrls.length} unique URLs`);
  return { urls: allUrls, duration: Date.now() - phaseStart };
}

// PHASE 3: Fetch sources (workers)
async function phase3_fetch(urls, executionId) {
  console.log('\n=== PHASE 3: FETCH SOURCES (WORKERS) ===');
  const phaseStart = Date.now();

  const fetchPromises = urls.slice(0, 10).map(async (url, idx) => {
    const workerStart = Date.now();
    const prompt = `Extract key claims from: ${url}\n\nReturn JSON: { "claims": ["claim1", "claim2", "claim3"] }`;

    const result = callClaude(prompt, 'claude-haiku-4');

    try {
      const data = JSON.parse(result);

      // Store worker result
      await db.storeWorkerResult({
        workflow_execution_id: executionId,
        worker_id: `fetch-worker-${idx + 1}`,
        model: 'claude-haiku-4',
        task_assigned: `Fetch ${url}`,
        result: JSON.stringify(data.claims || []),
        confidence: 0.75,
        duration_ms: Date.now() - workerStart,
        input_tokens: Math.ceil(prompt.length / 4),
        output_tokens: Math.ceil(result.length / 4),
        cost_usd: 0.0001,
        outcome: 'success'
      });

      console.log(`   Fetcher ${idx + 1}: Extracted ${data.claims?.length || 0} claims`);
      return { url, claims: data.claims || [] };
    } catch {
      return { url, claims: [] };
    }
  });

  const sources = await Promise.all(fetchPromises);
  const allClaims = sources.flatMap(s => s.claims);

  console.log(`✅ Extracted ${allClaims.length} claims from ${sources.length} sources`);
  return { claims: allClaims, duration: Date.now() - phaseStart };
}

// PHASE 4: Synthesize report (arbiter)
async function phase4_synthesize(claims, executionId) {
  console.log('\n=== PHASE 4: SYNTHESIZE REPORT (ARBITER) ===');
  const phaseStart = Date.now();

  const claimsSummary = claims.slice(0, 50).map(c => `- ${c}`).join('\n');

  const prompt = `Synthesize a research report from these claims:

Original Question: ${QUESTION}

Claims:
${claimsSummary}

Write a comprehensive report (max 500 words) with:
1. Key findings
2. Patterns across sources
3. Confidence levels
4. Caveats and limitations

Return markdown text.`;

  const report = callClaude(prompt, 'claude-opus-4');

  // Store arbiter decision
  await db.storeArbiterDecision({
    workflow_execution_id: executionId,
    arbiter_model: 'claude-opus-4',
    worker_result_ids: [], // All fetch workers contributed
    decision: report,
    reasoning: 'Synthesized from claims extracted by fetch workers',
    confidence: 0.85,
    duration_ms: Date.now() - phaseStart,
    input_tokens: Math.ceil(prompt.length / 4),
    output_tokens: Math.ceil(report.length / 4),
    cost_usd: 0.015 // Opus is more expensive
  });

  console.log(`✅ Report synthesized (${report.length} chars)`);
  return { report, duration: Date.now() - phaseStart };
}

// PHASE 5: ADVERSARIAL VERIFICATION (NEW!)
async function phase5_adversarial_verification(report, executionId) {
  console.log('\n=== PHASE 5: ADVERSARIAL VERIFICATION ===');

  const verified = await wrapWithAdversarialVerification({
    arbiterResult: report,
    originalTask: QUESTION,
    workflow_execution_id: executionId,
    promptType: 'factcheck', // Research = fact-checking
    modelStrategy: 'free' // Use free models (Gemini, Llama, DeepSeek)
  });

  // Log results
  if (verified.verdict === 'REJECT') {
    console.log(`\n⚠️  REPORT REJECTED BY ADVERSARIAL VERIFICATION`);
    console.log(`   Confidence: ${verified.confidence}`);
    console.log(`   Refuters failed to disprove: ${verified.refuters_failed}/${verified.refuters_total}`);
    console.log(`   Critical issues: ${verified.critical_issues.length}`);
    console.log(`   Major issues: ${verified.major_issues.length}`);

    if (verified.critical_issues.length > 0) {
      console.log(`\n   🚨 CRITICAL ISSUES FOUND:`);
      verified.critical_issues.forEach((issue, idx) => {
        console.log(`      ${idx + 1}. [${issue.model}] ${issue.reasoning}`);
        if (issue.counterexample) {
          console.log(`         Counterexample: ${issue.counterexample}`);
        }
      });
    }

  } else if (verified.verdict === 'ACCEPT_WITH_CAVEATS') {
    console.log(`\n⚠️  Report accepted WITH CAVEATS`);
    console.log(`   Confidence: ${verified.confidence}`);
    console.log(`   Major issues: ${verified.major_issues.length}`);

    verified.major_issues.forEach((issue, idx) => {
      console.log(`      ${idx + 1}. [${issue.model}] ${issue.reasoning}`);
    });

  } else {
    console.log(`\n✅ Report ACCEPTED by adversarial verification`);
    console.log(`   Confidence: ${verified.confidence}`);
    console.log(`   All ${verified.refuters_total} refuters failed to disprove`);
  }

  console.log(`   Cost: $${verified.cost_usd.toFixed(4)}`);
  console.log(`   Duration: ${(verified.duration_ms / 1000).toFixed(1)}s`);

  return verified;
}

// Main execution
(async () => {
  try {
    console.log('Deep Research Workflow with Adversarial Verification');
    console.log(`Question: ${QUESTION}`);
    console.log(`Workflow ID: ${WORKFLOW_ID}`);

    // Create execution record
    const executionId = await db.storeExecution({
      workflow_id: WORKFLOW_ID,
      workflow_name: 'deep-research-adversarial',
      task_description: QUESTION,
      total_workers: 0, // Will update
      total_duration_ms: 0,
      outcome: 'success',
      metadata: { started_at: new Date().toISOString() }
    });

    console.log(`\n📝 Execution ID: ${executionId}`);

    // Execute phases
    const p1 = await phase1_decompose();
    await db.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'decompose',
      phase_order: 1,
      duration_ms: p1.duration,
      outcome: 'success'
    });

    const p2 = await phase2_search(p1.angles, executionId);
    await db.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'search',
      phase_order: 2,
      duration_ms: p2.duration,
      outcome: 'success'
    });

    const p3 = await phase3_fetch(p2.urls, executionId);
    await db.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'fetch',
      phase_order: 3,
      duration_ms: p3.duration,
      outcome: 'success'
    });

    const p4 = await phase4_synthesize(p3.claims, executionId);
    await db.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'synthesize',
      phase_order: 4,
      duration_ms: p4.duration,
      outcome: 'success'
    });

    // NEW: Adversarial verification
    const p5 = await phase5_adversarial_verification(p4.report, executionId);
    await db.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'adversarial_verification',
      phase_order: 5,
      duration_ms: p5.duration_ms,
      outcome: p5.verdict === 'ACCEPT' ? 'success' : 'warning',
      metadata: {
        verdict: p5.verdict,
        confidence: p5.confidence,
        refuters_failed: p5.refuters_failed,
        critical_issues: p5.critical_issues.length
      }
    });

    // Update execution with final stats
    const totalDuration = Date.now() - START_TIME;
    await pool.query(`
      UPDATE workflow.executions
      SET total_duration_ms = $1, outcome = $2, metadata = metadata || $3::jsonb
      WHERE id = $4
    `, [
      totalDuration,
      p5.verdict === 'REJECT' ? 'warning' : 'success',
      JSON.stringify({
        completed_at: new Date().toISOString(),
        adversarial_verification: {
          verdict: p5.verdict,
          confidence: p5.confidence,
          cost_usd: p5.cost_usd
        }
      }),
      executionId
    ]);

    // Store learnings
    await db.storeLearnings({
      workflow_execution_id: executionId,
      learning_type: 'pattern',
      description: `Research workflow with adversarial verification`,
      actionable_insight: `Adversarial verification caught ${p5.critical_issues.length} critical + ${p5.major_issues.length} major issues`,
      importance: p5.verdict === 'REJECT' ? 0.9 : 0.7,
      metadata: {
        refuters_total: p5.refuters_total,
        refuters_failed: p5.refuters_failed,
        cost_usd: p5.cost_usd
      }
    });

    // Store feedback
    await db.storeFeedback({
      workflow_execution_id: executionId,
      feedback_type: 'adversarial',
      quality_score: p5.verdict === 'ACCEPT' ? 0.9 : p5.verdict === 'ACCEPT_WITH_CAVEATS' ? 0.7 : 0.3,
      feedback_text: `Adversarial verification: ${p5.verdict}`,
      metadata: {
        critical_issues: p5.critical_issues,
        major_issues: p5.major_issues
      }
    });

    // Print final report
    console.log('\n' + '='.repeat(80));
    console.log('RESEARCH REPORT');
    console.log('='.repeat(80));
    console.log(p4.report);
    console.log('\n' + '='.repeat(80));
    console.log('\nADVERSARIAL VERIFICATION SUMMARY');
    console.log('='.repeat(80));
    console.log(`Verdict: ${p5.verdict}`);
    console.log(`Confidence: ${p5.confidence}`);
    console.log(`Refuters failed to disprove: ${p5.refuters_failed}/${p5.refuters_total}`);
    console.log(`Critical issues: ${p5.critical_issues.length}`);
    console.log(`Major issues: ${p5.major_issues.length}`);
    console.log(`Cost: $${p5.cost_usd.toFixed(4)}`);
    console.log(`Total duration: ${(totalDuration / 1000).toFixed(1)}s`);
    console.log('='.repeat(80));

    await pool.end();
    await db.close();

    process.exit(p5.verdict === 'REJECT' ? 1 : 0);

  } catch (err) {
    console.error('\n❌ Workflow failed:', err.message);
    console.error(err.stack);

    await pool.end();
    await db.close();

    process.exit(1);
  }
})();
