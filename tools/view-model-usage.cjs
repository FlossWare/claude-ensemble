#!/usr/bin/env node
/**
 * View Model Usage Statistics
 *
 * Shows which models are being used, why, and for what tasks.
 * CRITICAL for Red Hat compliance monitoring!
 */

const {
  getRecentUsage,
  getUsageStats,
  checkRedHatCompliance
} = require('../shared/model-usage-tracker.cjs');

const HOURS = process.argv[2] ? parseInt(process.argv[2]) : 24;

async function main() {
  console.log('========================================');
  console.log(`MODEL USAGE REPORT (last ${HOURS} hours)`);
  console.log('========================================\n');

  // Get statistics
  const stats = await getUsageStats(HOURS);

  console.log(`Total selections: ${stats.total}`);
  console.log(`Anthropic-only enforced: ${stats.anthropic_only_count} (${((stats.anthropic_only_count / stats.total) * 100).toFixed(1)}%)`);
  console.log(`Filtered selections: ${stats.filtered_count} (${((stats.filtered_count / stats.total) * 100).toFixed(1)}%)`);
  console.log('');

  // Model distribution
  console.log('MODEL DISTRIBUTION:');
  console.log('─────────────────────────────');
  const sortedModels = Object.entries(stats.model_distribution)
    .sort((a, b) => b[1].count - a[1].count);

  for (const [model, data] of sortedModels) {
    const bar = '█'.repeat(Math.round(parseFloat(data.percentage) / 2));
    console.log(`  ${model.padEnd(25)} ${data.count.toString().padStart(4)} (${data.percentage}) ${bar}`);
  }
  console.log('');

  // Task type distribution
  console.log('TASK TYPE DISTRIBUTION:');
  console.log('─────────────────────────────');
  const sortedTasks = Object.entries(stats.by_task_type)
    .sort((a, b) => b[1] - a[1]);

  for (const [taskType, count] of sortedTasks.slice(0, 15)) {
    const pct = ((count / stats.total) * 100).toFixed(1);
    const bar = '█'.repeat(Math.round(parseFloat(pct) / 2));
    console.log(`  ${taskType.padEnd(30)} ${count.toString().padStart(4)} (${pct}%) ${bar}`);
  }
  console.log('');

  // Red Hat compliance check
  console.log('RED HAT COMPLIANCE CHECK:');
  console.log('─────────────────────────────');
  const violations = await checkRedHatCompliance(HOURS);

  if (violations.length === 0) {
    console.log('✓ NO VIOLATIONS - All Red Hat tasks used Anthropic models only!');
  } else {
    console.log(`✗ ${violations.length} VIOLATIONS FOUND!`);
    console.log('');
    for (const v of violations) {
      console.log(`  ⚠️  ${v.timestamp}`);
      console.log(`      Task: ${v.task_type}`);
      console.log(`      Model: ${v.model} (NOT ANTHROPIC!)`);
      console.log(`      Workflow: ${v.workflow}`);
      console.log('');
    }
  }
  console.log('');

  // Recent selections
  console.log('RECENT SELECTIONS (last 10):');
  console.log('─────────────────────────────');
  const recent = await getRecentUsage({ limit: 10, hours: HOURS });

  for (const r of recent) {
    const time = new Date(r.timestamp).toLocaleTimeString();
    const anthropic = r.anthropic_only ? '[ANTHROPIC-ONLY]' : '';
    console.log(`  ${time} ${r.model.padEnd(20)} ${r.task_type || 'general'} ${anthropic}`);
    if (r.filter_reason && r.filter_reason !== 'No specific rules') {
      console.log(`           └─ ${r.filter_reason}`);
    }
  }
  console.log('');

  console.log('========================================');
  console.log('For PostgreSQL queries:');
  console.log('  psql -h aio-01 -p 5433 -U claude -d learning');
  console.log('  SELECT * FROM monitoring.model_usage_stats_24h;');
  console.log('  SELECT * FROM monitoring.model_usage ORDER BY timestamp DESC LIMIT 20;');
  console.log('========================================');
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
