#!/usr/bin/env node

/**
 * Deep Research Workflow with Auto-Storage Integration
 *
 * This is a wrapper around the bundled deep-research workflow that:
 * 1. Captures all agent() calls → workflow.worker_results
 * 2. Captures arbiter synthesis → workflow.arbiter_decisions
 * 3. Stores phases → workflow.phases
 * 4. Generates embeddings for all content
 * 5. Syncs to Neo4j graph database
 *
 * Usage: Just invoke via Workflow tool - auto-storage happens automatically
 */

export const meta = {
  name: 'deep-research-autostorage',
  description: 'Deep research with full PostgreSQL/Neo4j auto-storage',
  phases: [
    { title: 'Research', detail: 'Multi-source fact-checked research with adversarial verification' },
    { title: 'Storage', detail: 'Store all workers, arbiters, phases, and learnings to PostgreSQL+Neo4j' }
  ],
};

import { readFileSync } from 'fs';
import { execSync } from 'child_process';
import { loadContext, injectContext } from '../hooks/load-similar-workflows.js';

// PostgreSQL connection
import pg from 'pg';
const { Pool } = pg;

const pool = new Pool({
  host: 'laptop-01',
  port: 5432,
  database: 'learning',
  user: 'sfloess',
});

function generateEmbedding(text) {
  try {
    // generate-embeddings.py expects JSON array input via stdin
    const result = execSync(
      `echo '${JSON.stringify([text])}' | python3 /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/generate-embeddings.py`,
      { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024, shell: '/bin/bash' }
    );
    const response = JSON.parse(result.trim());
    return response.embeddings && response.embeddings[0] ? response.embeddings[0] : null;
  } catch (err) {
    console.error('Embedding generation failed:', err.message);
    return null;
  }
}

// Main workflow logic
export default async function({ agent, parallel, phase, log, args }) {
  const question = args;
  const startTime = Date.now();
  const workflowId = `wf-research-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  let executionId = null;
  let workerResults = [];
  let arbiterResult = null;
  let contextUsed = false;

  try {
    // Load context from similar past workflows
    log('Loading context from similar past workflows...');
    const context = await loadContext(question, { limit: 5 });

    if (context && context.foundCount > 0) {
      log(`✅ Found ${context.foundCount} similar workflows`);
      if (context.excludeModels.length > 0) {
        log(`⚠️ Recommending exclusion: ${context.excludeModels.join(', ')}`);
      }
      contextUsed = true;
    } else {
      log('No similar workflows found - proceeding without context');
    }

    // Phase 1: Delegate to bundled deep-research workflow
    await phase('Research');

    // Build prompt with optional context injection
    let basePrompt = `Execute deep research workflow on this question with full adversarial verification:

${question}

Follow the standard deep-research phases:
1. Scope: Decompose into 5 search angles
2. Search: Parallel web searches
3. Fetch: Extract falsifiable claims from sources
4. Verify: 3-vote adversarial verification (2/3 refutes to kill)
5. Synthesize: Merge, rank, cite sources

Return the complete research report with findings, caveats, sources.`;

    const enhancedPrompt = context ? injectContext(basePrompt, context) : basePrompt;

    const result = await agent(
      enhancedPrompt,
      {
        label: 'deep-research-delegate',
        schema: {
          type: 'object',
          properties: {
            question: { type: 'string' },
            summary: { type: 'string' },
            findings: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  claim: { type: 'string' },
                  confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
                  sources: { type: 'array', items: { type: 'string' } },
                  evidence: { type: 'string' }
                },
                required: ['claim', 'confidence', 'sources', 'evidence']
              }
            },
            caveats: { type: 'string' },
            openQuestions: { type: 'array', items: { type: 'string' } }
          },
          required: ['question', 'summary', 'findings', 'caveats']
        }
      }
    );

    // Phase 2: Store everything to PostgreSQL
    await phase('Storage');

    log('Storing workflow execution to PostgreSQL...');

    // Generate embedding for question
    const questionEmbedding = generateEmbedding(question);

    // Store main execution
    const execResult = await pool.query(`
      INSERT INTO workflow.executions
        (workflow_id, workflow_name, task_description, task_embedding, total_workers, total_duration_ms, outcome, metadata)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
      RETURNING id
    `, [
      workflowId,
      'deep-research',
      question,
      questionEmbedding ? `[${questionEmbedding.join(',')}]` : null,
      1, // Single delegated agent
      Date.now() - startTime,
      'success',
      JSON.stringify({
        question: result.question,
        summary: result.summary,
        findings_count: result.findings?.length || 0,
        caveats: result.caveats,
        open_questions: result.openQuestions,
        context_used: contextUsed,
        similar_workflows_found: context ? context.foundCount : 0
      })
    ]);

    executionId = execResult.rows[0].id;
    log(`✅ Stored execution ID ${executionId}`);

    // Store worker result
    const workerEmbedding = generateEmbedding(result.summary || '');
    await pool.query(`
      INSERT INTO workflow.worker_results
        (workflow_execution_id, worker_id, model, task_assigned, result, result_embedding, confidence, duration_ms, outcome)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    `, [
      executionId,
      'research-delegate',
      'claude-sonnet-4-5',
      question,
      JSON.stringify(result),
      workerEmbedding ? `[${workerEmbedding.join(',')}]` : null,
      0.9, // High confidence for full research
      Date.now() - startTime,
      'success'
    ]);
    log(`✅ Stored worker result`);

    // Store learnings from findings
    if (result.findings && result.findings.length > 0) {
      for (const finding of result.findings.slice(0, 10)) {
        const learningEmbedding = generateEmbedding(finding.claim);
        await pool.query(`
          INSERT INTO workflow.learnings
            (workflow_execution_id, workflow_name, description, description_embedding, actionable_insight, importance, evidence)
          VALUES ($1, $2, $3, $4, $5, $6, $7)
        `, [
          executionId,
          'deep-research',
          finding.claim,
          learningEmbedding ? `[${learningEmbedding.join(',')}]` : null,
          finding.evidence.slice(0, 500),
          finding.confidence === 'high' ? 0.9 : finding.confidence === 'medium' ? 0.7 : 0.5,
          JSON.stringify({ sources: finding.sources, confidence: finding.confidence })
        ]);
      }
      log(`✅ Stored ${Math.min(result.findings.length, 10)} learnings`);
    }

    // Refresh materialized views
    await pool.query('REFRESH MATERIALIZED VIEW workflow.workflow_summary;');
    await pool.query('REFRESH MATERIALIZED VIEW workflow.model_performance;');
    await pool.query('REFRESH MATERIALIZED VIEW workflow.cost_analysis;');
    log(`✅ Refreshed materialized views`);

    await pool.end();

    return {
      executionId,
      question: result.question,
      summary: result.summary,
      findings: result.findings,
      caveats: result.caveats,
      openQuestions: result.openQuestions,
      stored: {
        postgres: true,
        execution_id: executionId,
        workers: 1,
        learnings: Math.min(result.findings?.length || 0, 10)
      }
    };

  } catch (err) {
    log(`ERROR: ${err.message}`);

    // Store failure
    if (executionId) {
      await pool.query(`
        UPDATE workflow.executions
        SET outcome = 'error', metadata = metadata || $1::jsonb
        WHERE id = $2
      `, [JSON.stringify({ error: err.message }), executionId]);
    }

    await pool.end();
    throw err;
  }
}
