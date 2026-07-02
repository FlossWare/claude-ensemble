#!/usr/bin/env node

/**
 * Custom Deep Research Workflow with Full Auto-Storage
 *
 * NOT using bundled Workflow runtime - this is a standalone workflow that:
 * 1. Uses Claude API directly for multi-agent research
 * 2. Calls auto-storage hooks for EVERY worker, arbiter, phase
 * 3. Stores to PostgreSQL: executions, worker_results, arbiter_decisions, phases, learnings
 * 4. Generates 384-dim embeddings via sentence-transformers
 * 5. Syncs to Neo4j graph database
 *
 * Run: node workflows/custom-deep-research.mjs "research question"
 */

import { execSync } from 'child_process';
import pg from 'pg';
import { readFileSync, writeFileSync } from 'fs';

const { Pool } = pg;

const pool = new Pool({
  host: 'laptop-01',
  port: 5432,
  database: 'learning',
  user: 'sfloess',
});

// Research question from command line
const QUESTION = process.argv[2];
if (!QUESTION) {
  console.error('Usage: node custom-deep-research.mjs "research question"');
  process.exit(1);
}

const WORKFLOW_ID = `research-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const START_TIME = Date.now();

// Generate 384-dim embeddings using sentence-transformers
function generateEmbedding(text) {
  try {
    const cleaned = text.replace(/\n/g, ' ').slice(0, 5000);
    // generate-embeddings.py expects JSON array input via stdin
    const result = execSync(
      `echo '${JSON.stringify([cleaned])}' | python3 /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/generate-embeddings.py`,
      { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024, timeout: 60000, shell: '/bin/bash' }
    );
    const response = JSON.parse(result.trim());
    return response.embeddings && response.embeddings[0] ? response.embeddings[0] : null;
  } catch (err) {
    console.error(`⚠ Embedding generation failed: ${err.message}`);
    return null;
  }
}

// Call Claude API via claude CLI
function callClaude(prompt, model = 'claude-sonnet-4-5') {
  try {
    const result = execSync(
      `claude --print --model ${model} ${JSON.stringify(prompt)}`,
      { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024, timeout: 300000 }
    );
    return result.trim();
  } catch (err) {
    console.error(`⚠ Claude API call failed: ${err.message}`);
    return null;
  }
}

// Store to PostgreSQL
async function storeExecution() {
  const embedding = generateEmbedding(QUESTION);

  const result = await pool.query(`
    INSERT INTO workflow.executions
      (workflow_id, workflow_name, task_description, task_embedding, total_workers, total_duration_ms, outcome, metadata)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    RETURNING id
  `, [
    WORKFLOW_ID,
    'custom-deep-research',
    QUESTION,
    embedding ? `[${embedding.join(',')}]` : null,
    0, // Will update after workers complete
    0, // Will update at end
    'success', // Valid outcomes: success, failed, error
    JSON.stringify({ question: QUESTION, started_at: new Date().toISOString() })
  ]);

  return result.rows[0].id;
}

async function storeWorker(executionId, workerId, model, task, result, durationMs) {
  const embedding = generateEmbedding(result.slice(0, 5000));

  await pool.query(`
    INSERT INTO workflow.worker_results
      (workflow_execution_id, worker_id, model, task_assigned, result, result_embedding, confidence, duration_ms, outcome)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
  `, [
    executionId,
    workerId,
    model,
    task,
    result,
    embedding ? `[${embedding.join(',')}]` : null,
    0.8,
    durationMs,
    'success'
  ]);
}

async function storePhase(executionId, phaseName, phaseOrder, durationMs) {
  await pool.query(`
    INSERT INTO workflow.phases
      (workflow_execution_id, phase_name, phase_order, duration_ms, outcome)
    VALUES ($1, $2, $3, $4, $5)
  `, [
    executionId,
    phaseName,
    phaseOrder,
    durationMs,
    'success'
  ]);
}

async function storeLearning(executionId, description, insight, importance, evidence) {
  const embedding = generateEmbedding(description);

  await pool.query(`
    INSERT INTO workflow.learnings
      (workflow_execution_id, workflow_name, description, description_embedding, actionable_insight, importance, evidence)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
  `, [
    executionId,
    'custom-deep-research',
    description,
    embedding ? `[${embedding.join(',')}]` : null,
    insight,
    importance,
    evidence
  ]);
}

async function main() {
  console.log(`\n🔬 Custom Deep Research Workflow`);
  console.log(`Question: ${QUESTION}`);
  console.log(`Workflow ID: ${WORKFLOW_ID}\n`);

  let executionId;

  try {
    // Store initial execution
    executionId = await storeExecution();
    console.log(`✅ Created execution ID: ${executionId}\n`);

    let workerCount = 0;
    let allFindings = [];

    // Phase 1: Decompose into search angles
    console.log('📋 PHASE 1: DECOMPOSE');
    const phaseStart1 = Date.now();

    const anglesPrompt = `Decompose this research question into 5 distinct search angles:

"${QUESTION}"

Return ONLY a JSON array of 5 search query strings, nothing else.`;

    const anglesResult = callClaude(anglesPrompt);
    workerCount++;
    await storeWorker(executionId, 'decompose-worker', 'claude-sonnet-4-5', 'Decompose question', anglesResult, Date.now() - phaseStart1);

    const angles = JSON.parse(anglesResult);
    console.log(`  Found ${angles.length} search angles`);
    await storePhase(executionId, 'decompose', 1, Date.now() - phaseStart1);

    // Phase 2: Research each angle (5 workers in parallel via background jobs)
    console.log('\n🔍 PHASE 2: RESEARCH');
    const phaseStart2 = Date.now();

    for (let i = 0; i < angles.length; i++) {
      const angle = angles[i];
      console.log(`  Worker ${i+1}/5: ${angle.slice(0, 60)}...`);

      const workerStart = Date.now();
      const researchPrompt = `Research this specific angle and extract 3-5 key findings:

"${angle}"

For each finding, provide:
1. The claim (what you found)
2. Confidence level (high/medium/low)
3. 2-3 source URLs
4. Evidence summary

Return as JSON array of findings.`;

      const findings = callClaude(researchPrompt);
      workerCount++;

      await storeWorker(executionId, `research-worker-${i+1}`, 'claude-sonnet-4-5', angle, findings, Date.now() - workerStart);

      try {
        const parsed = JSON.parse(findings);
        allFindings.push(...(Array.isArray(parsed) ? parsed : []));
      } catch (e) {
        console.warn(`  ⚠ Could not parse findings from worker ${i+1}`);
      }
    }

    console.log(`  Collected ${allFindings.length} findings`);
    await storePhase(executionId, 'research', 2, Date.now() - phaseStart2);

    // Phase 3: Adversarial verification (arbiter)
    console.log('\n🎯 PHASE 3: VERIFICATION');
    const phaseStart3 = Date.now();

    const verifyPrompt = `Adversarially verify these research findings. Try to REFUTE weak claims:

${JSON.stringify(allFindings.slice(0, 20), null, 2)}

For each finding, determine:
1. Should it be ACCEPTED or REFUTED?
2. Confidence score 0.0-1.0
3. Reasoning

Return as JSON array matching input order.`;

    const verifications = callClaude(verifyPrompt, 'claude-opus-4-8'); // Use Opus for critical thinking
    workerCount++;

    await storeWorker(executionId, 'verify-arbiter', 'claude-opus-4-8', 'Adversarial verification', verifications, Date.now() - phaseStart3);
    await storePhase(executionId, 'verification', 3, Date.now() - phaseStart3);

    // Phase 4: Synthesize final report
    console.log('\n📝 PHASE 4: SYNTHESIS');
    const phaseStart4 = Date.now();

    const synthesisPrompt = `Synthesize a comprehensive research report:

Question: ${QUESTION}

Verified Findings:
${verifications}

Write a 300-500 word report with:
1. Executive summary
2. Key findings (numbered)
3. Caveats and limitations
4. Open questions for future research

Use markdown formatting.`;

    const report = callClaude(synthesisPrompt, 'claude-opus-4-8');
    workerCount++;

    await storeWorker(executionId, 'synthesis-arbiter', 'claude-opus-4-8', 'Synthesize final report', report, Date.now() - phaseStart4);
    await storePhase(executionId, 'synthesis', 4, Date.now() - phaseStart4);

    // Store learnings from top findings
    console.log('\n💡 STORING LEARNINGS');
    for (let i = 0; i < Math.min(allFindings.length, 10); i++) {
      const finding = allFindings[i];
      if (finding.claim) {
        await storeLearning(
          executionId,
          finding.claim,
          finding.evidence || '',
          finding.confidence === 'high' ? 0.9 : finding.confidence === 'medium' ? 0.7 : 0.5,
          JSON.stringify({ sources: finding.sources || [], confidence: finding.confidence })
        );
      }
    }
    console.log(`  Stored ${Math.min(allFindings.length, 10)} learnings`);

    // Update execution with final stats
    const totalDuration = Date.now() - START_TIME;
    await pool.query(`
      UPDATE workflow.executions
      SET
        total_workers = $1,
        total_duration_ms = $2,
        outcome = 'success',
        metadata = metadata || $3::jsonb
      WHERE id = $4
    `, [
      workerCount,
      totalDuration,
      JSON.stringify({
        completed_at: new Date().toISOString(),
        angles_count: angles.length,
        findings_count: allFindings.length,
        phases_completed: 4
      }),
      executionId
    ]);

    // Refresh materialized views
    await pool.query('REFRESH MATERIALIZED VIEW workflow.workflow_summary;');
    await pool.query('REFRESH MATERIALIZED VIEW workflow.model_performance;');
    await pool.query('REFRESH MATERIALIZED VIEW workflow.cost_analysis;');

    console.log(`\n✅ COMPLETE`);
    console.log(`   Execution ID: ${executionId}`);
    console.log(`   Workers: ${workerCount}`);
    console.log(`   Duration: ${(totalDuration / 1000).toFixed(1)}s`);
    console.log(`   Findings: ${allFindings.length}`);
    console.log(`\n${report}\n`);

    await pool.end();
    process.exit(0);

  } catch (err) {
    console.error(`\n❌ ERROR: ${err.message}`);

    if (executionId) {
      await pool.query(`
        UPDATE workflow.executions
        SET outcome = 'error', metadata = metadata || $1::jsonb
        WHERE id = $2
      `, [JSON.stringify({ error: err.message }), executionId]);
    }

    await pool.end();
    process.exit(1);
  }
}

main();
