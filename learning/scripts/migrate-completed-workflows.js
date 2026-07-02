#!/usr/bin/env node

/**
 * Migrate completed workflow outputs to PostgreSQL workflow storage
 *
 * Reads *.output files from /tmp/claude-1000/.../tasks/ and populates:
 * - workflow.executions (with embeddings)
 * - workflow.phases
 * - workflow.learnings
 */

import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import pg from 'pg';
import { execSync } from 'child_process';

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

async function migrateWorkflow(taskId, outputFile) {
  const content = readFileSync(outputFile, 'utf8');

  // Parse workflow result
  let wrapper, result;
  try {
    wrapper = JSON.parse(content);
    // Deep research workflows wrap result in {result: {...}}
    result = wrapper.result || wrapper;
  } catch (err) {
    console.error(`Failed to parse ${taskId}: ${err.message.slice(0, 80)}`);
    return null;
  }

  // Skip non-workflow outputs (bash commands, git outputs, etc.)
  if (!result.question && !result.task && !result.workflow_name) {
    return null;
  }

  // Extract question/task description
  const taskDescription = result.question || result.task || result.workflow_name || 'Unknown task';

  // Generate embedding
  console.log(`Generating embedding for: ${taskDescription.slice(0, 80)}...`);
  const embedding = generateEmbedding(taskDescription);

  // Extract metadata from result
  const metadata = {
    question: result.question,
    summary: result.summary,
    findings_count: result.findings?.length || 0,
    caveats: result.caveats,
    open_questions: result.openQuestions,
    task_id: taskId,
    source_file: outputFile
  };

  // Insert into workflow.executions
  const workflowId = `wf-${taskId}-${Date.now()}`;

  try {
    const insertResult = await pool.query(`
      INSERT INTO workflow.executions
        (workflow_id, workflow_name, task_description, task_embedding, total_workers, total_duration_ms, outcome, metadata)
      VALUES
        ($1, $2, $3, $4, $5, $6, $7, $8)
      RETURNING id
    `, [
      workflowId,
      'deep-research',
      taskDescription,
      embedding ? `[${embedding.join(',')}]` : null,
      result.agent_count || result.total_workers || 0,
      result.duration_ms || 0,
      result.failures ? 'partial_success' : 'success',
      JSON.stringify(metadata)
    ]);

    const executionId = insertResult.rows[0].id;
    console.log(`✅ Migrated ${taskId} → execution_id=${executionId} (${wrapper.agentCount || 0} agents)`);

    // Insert learnings if available
    if (result.findings && result.findings.length > 0) {
      for (const finding of result.findings.slice(0, 5)) { // Top 5 findings
        await pool.query(`
          INSERT INTO workflow.learnings
            (workflow_execution_id, workflow_name, description, actionable_insight, importance, evidence)
          VALUES
            ($1, $2, $3, $4, $5, $6)
        `, [
          executionId,
          'deep-research',
          finding.claim || finding.title || 'Finding',
          finding.evidence || finding.summary || '',
          parseFloat(finding.confidence === 'high' ? 0.9 : finding.confidence === 'medium' ? 0.7 : 0.5),
          JSON.stringify({ sources: finding.sources, vote: finding.vote })
        ]);
      }
    }

    return executionId;
  } catch (err) {
    console.error(`Failed to insert ${taskId}: ${err.message}`);
    return null;
  }
}

async function main() {
  const tasksDir = '/tmp/claude-1000/-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills/4d1f43c9-cfc0-4917-a842-a238f5415111/tasks';

  const files = readdirSync(tasksDir).filter(f => f.endsWith('.output'));

  console.log(`Found ${files.length} workflow outputs to migrate\n`);

  let migrated = 0;
  let failed = 0;

  for (const file of files) {
    const taskId = file.replace('.output', '');
    const outputFile = join(tasksDir, file);

    const result = await migrateWorkflow(taskId, outputFile);
    if (result) {
      migrated++;
    } else {
      failed++;
    }
  }

  console.log(`\n✅ Migration complete:`);
  console.log(`   Migrated: ${migrated}`);
  console.log(`   Failed: ${failed}`);
  console.log(`   Total: ${files.length}`);

  // Refresh materialized views
  console.log('\nRefreshing materialized views...');
  await pool.query('REFRESH MATERIALIZED VIEW workflow.workflow_summary;');
  await pool.query('REFRESH MATERIALIZED VIEW workflow.model_performance;');
  await pool.query('REFRESH MATERIALIZED VIEW workflow.cost_analysis;');
  console.log('✅ Views refreshed');

  await pool.end();
}

main().catch(err => {
  console.error('Migration failed:', err);
  process.exit(1);
});
