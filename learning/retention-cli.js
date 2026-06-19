#!/usr/bin/env node

/**
 * Retention Policy CLI
 * Manage workflow embeddings retention policy
 *
 * Commands:
 *   cleanup <days>     - Run cleanup for embeddings older than <days>
 *   stats              - Show retention statistics
 *   search <query>     - Search similar workflows
 *   list               - List recent workflows
 */

const { getDB } = require('./postgres-adapter');
const { getWorkflowTracker } = require('./workflow-completion-tracker');

const command = process.argv[2];
const arg = process.argv[3];

async function runCleanup(days = 90) {
  const db = getDB();

  console.log(`Running retention cleanup (${days} days)...`);

  const result = await db.get(
    'SELECT * FROM learning.cleanup_old_workflow_embeddings($1)',
    [days]
  );

  console.log(`✓ Cleanup complete`);
  console.log(`  Deleted: ${result.deleted_count} embeddings`);
  console.log(`  Freed: ${result.freed_mb.toFixed(2)} MB`);

  await db.close();
}

async function showStats() {
  const tracker = getWorkflowTracker();

  console.log('Workflow Retention Statistics\n');

  const stats = await tracker.getStats();

  console.log('Overall Statistics:');
  console.log(`  Total Workflows: ${stats.total_workflows}`);
  console.log(`  Completed: ${stats.completed}`);
  console.log(`  Failed: ${stats.failed}`);
  console.log(`  Avg Duration: ${(stats.avg_duration_ms / 1000).toFixed(1)}s`);
  console.log(`  With Embeddings: ${stats.with_embeddings} (< 90 days)`);
  console.log(`  Embeddings Cleared: ${stats.embeddings_cleared} (≥ 90 days)`);
  console.log(`  Storage (embeddings): ${(stats.with_embeddings * 6 / 1024).toFixed(2)} MB`);

  await tracker.db.close();
}

async function searchWorkflows(query) {
  const tracker = getWorkflowTracker();

  console.log(`Searching for: "${query}"\n`);

  const results = await tracker.searchSimilar(query, 10);

  if (results.length === 0) {
    console.log('No results found');
  } else {
    results.forEach((result, idx) => {
      console.log(`${idx + 1}. ${result.workflow_name} (similarity: ${(1 - result.similarity).toFixed(3)})`);
      console.log(`   Query: ${result.query}`);
      console.log(`   Completed: ${result.completed_at}`);
      console.log(`   Duration: ${(result.duration_ms / 1000).toFixed(1)}s`);
      console.log(`   Result: ${result.result_summary?.substring(0, 100)}...`);
      console.log('');
    });
  }

  await tracker.db.close();
}

async function listWorkflows() {
  const db = getDB();

  console.log('Recent Workflows (last 20)\n');

  const workflows = await db.all(
    `SELECT workflow_name, session_id, query, status, completed_at, duration_ms,
            CASE WHEN embedding IS NOT NULL THEN 'Yes' ELSE 'No' END as has_embedding
     FROM learning.workflow_completions
     ORDER BY started_at DESC
     LIMIT 20`
  );

  workflows.forEach((wf, idx) => {
    console.log(`${idx + 1}. ${wf.workflow_name} [${wf.status}]`);
    console.log(`   Query: ${wf.query}`);
    console.log(`   Completed: ${wf.completed_at || 'In progress'}`);
    console.log(`   Duration: ${wf.duration_ms ? (wf.duration_ms / 1000).toFixed(1) + 's' : 'N/A'}`);
    console.log(`   Embedding: ${wf.has_embedding}`);
    console.log('');
  });

  await db.close();
}

async function main() {
  try {
    if (command === 'cleanup') {
      const days = parseInt(arg, 10) || 90;
      await runCleanup(days);
    } else if (command === 'stats') {
      await showStats();
    } else if (command === 'search') {
      if (!arg) {
        console.error('Usage: retention-cli.js search "<query>"');
        process.exit(1);
      }
      await searchWorkflows(arg);
    } else if (command === 'list') {
      await listWorkflows();
    } else {
      console.log('Retention Policy CLI');
      console.log('');
      console.log('Commands:');
      console.log('  cleanup <days>     - Run cleanup for embeddings older than <days> (default: 90)');
      console.log('  stats              - Show retention statistics');
      console.log('  search <query>     - Search similar workflows');
      console.log('  list               - List recent workflows');
      console.log('');
      console.log('Examples:');
      console.log('  node retention-cli.js cleanup 90');
      console.log('  node retention-cli.js stats');
      console.log('  node retention-cli.js search "deep research about AI"');
      console.log('  node retention-cli.js list');
      process.exit(1);
    }
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  }
}

main();
