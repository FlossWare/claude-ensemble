#!/usr/bin/env node
/**
 * Dry-Run Model Selection Preview
 *
 * Preview which models would be selected for different task types
 * WITHOUT actually executing workflows or logging to database.
 *
 * Usage:
 *   node tools/dry-run-model-selection.cjs <task_type>
 *   node tools/dry-run-model-selection.cjs redhat_code_review
 *   node tools/dry-run-model-selection.cjs --compare code_review,redhat_code_review
 *   node tools/dry-run-model-selection.cjs --check-model opus redhat_code_review
 */

const {
  previewModelSelection,
  compareTaskTypes,
  checkModelAvailability,
} = require('../shared/model-preview.cjs');

async function main() {
  const args = process.argv.slice(2);

  // Mode 1: Compare multiple task types
  if (args[0] === '--compare') {
    const taskTypes = args[1] ? args[1].split(',') : [
      'redhat_code_review',
      'code_review',
      'security_audit',
      'documentation',
    ];

    console.log('========================================');
    console.log('TASK TYPE COMPARISON');
    console.log('========================================\n');

    const comparison = await compareTaskTypes(taskTypes);

    for (const [taskType, preview] of Object.entries(comparison)) {
      console.log(`${taskType}:`);
      console.log(`  Anthropic-only: ${preview.rules.anthropic_only}`);
      console.log(`  Whitelist: ${preview.rules.whitelist.join(', ') || 'none'}`);
      console.log(`  Blacklist: ${preview.rules.blacklist.join(', ') || 'none'}`);
      console.log(`  Pool: ${preview.result.rotation_pool.join(', ')}`);
      console.log(`  Selected: ${preview.result.selected_model}`);
      console.log('');
    }

    return;
  }

  // Mode 2: Check specific model availability
  if (args[0] === '--check-model') {
    const model = args[1] || 'opus';
    const taskType = args[2] || 'general';

    console.log('========================================');
    console.log('MODEL AVAILABILITY CHECK');
    console.log('========================================\n');

    const check = await checkModelAvailability(model, taskType);

    console.log(`Model: ${check.model}`);
    console.log(`Task: ${check.taskType}`);
    console.log(`Available: ${check.available ? '✓ YES' : '✗ NO'}`);
    console.log(`In rotation pool: ${check.in_rotation_pool ? '✓ YES' : '✗ NO'}`);
    if (check.pool_position) {
      console.log(`Pool position: #${check.pool_position}`);
    }
    console.log(`Reason: ${check.reason}`);
    console.log('');

    return;
  }

  // Mode 3: Single task type preview (default)
  const taskType = args[0] || 'general';

  console.log('========================================');
  console.log(`DRY-RUN: MODEL SELECTION PREVIEW`);
  console.log(`Task Type: ${taskType}`);
  console.log('========================================\n');

  const preview = await previewModelSelection({ taskType });

  // Task rules
  console.log('TASK RULES:');
  console.log('─────────────────────────────');
  console.log(`  Anthropic-only: ${preview.rules.anthropic_only ? 'YES ✓' : 'NO'}`);
  console.log(`  Whitelist: ${preview.rules.whitelist.length > 0 ? preview.rules.whitelist.join(', ') : 'none'}`);
  console.log(`  Blacklist: ${preview.rules.blacklist.length > 0 ? preview.rules.blacklist.join(', ') : 'none'}`);
  console.log(`  Min score: ${preview.rules.min_score}`);
  console.log(`  Reason: ${preview.rules.reason}`);
  console.log('');

  // Model counts
  console.log('MODEL COUNTS:');
  console.log('─────────────────────────────');
  console.log(`  Total available: ${preview.models.total_available}`);
  console.log(`  Anthropic models: ${preview.models.anthropic_count}`);
  console.log(`  Third-party models: ${preview.models.third_party_count}`);
  console.log(`  After filtering: ${preview.models.after_filtering}`);
  console.log(`  Rotation pool size: ${preview.models.rotation_pool_size}`);
  console.log(`  Removed by filters: ${preview.filtering.removed_count}`);
  console.log('');

  // Categorized models
  if (preview.categorized.anthropic.length > 0) {
    console.log('ANTHROPIC MODELS AVAILABLE:');
    console.log('─────────────────────────────');
    for (const model of preview.categorized.anthropic) {
      const filtered = !preview.result.all_filtered_models.includes(model);
      const status = filtered ? '✗ FILTERED OUT' : '✓ AVAILABLE';
      console.log(`  ${model.padEnd(30)} ${status}`);
    }
    console.log('');
  }

  if (preview.categorized.third_party.length > 0) {
    console.log('THIRD-PARTY MODELS AVAILABLE:');
    console.log('─────────────────────────────');
    for (const model of preview.categorized.third_party) {
      const filtered = !preview.result.all_filtered_models.includes(model);
      const status = filtered ? '✗ FILTERED OUT' : '✓ AVAILABLE';
      console.log(`  ${model.padEnd(30)} ${status}`);
    }
    console.log('');
  }

  // Filtering details
  if (preview.filtering.removed_count > 0) {
    console.log('FILTERING DETAILS:');
    console.log('─────────────────────────────');

    if (preview.filtering.by_anthropic_only.length > 0) {
      console.log(`  Removed by Anthropic-only (${preview.filtering.by_anthropic_only.length}):`);
      for (const model of preview.filtering.by_anthropic_only) {
        console.log(`    - ${model}`);
      }
    }

    if (preview.filtering.by_whitelist.length > 0) {
      console.log(`  Removed by whitelist (${preview.filtering.by_whitelist.length}):`);
      for (const model of preview.filtering.by_whitelist) {
        console.log(`    - ${model}`);
      }
    }

    if (preview.filtering.by_blacklist.length > 0) {
      console.log(`  Removed by blacklist (${preview.filtering.by_blacklist.length}):`);
      for (const model of preview.filtering.by_blacklist) {
        console.log(`    - ${model}`);
      }
    }

    console.log('');
  }

  // Rotation pool
  console.log('ROTATION POOL (top 6):');
  console.log('─────────────────────────────');
  if (preview.result.rotation_pool.length > 0) {
    for (let i = 0; i < preview.result.rotation_pool.length; i++) {
      const model = preview.result.rotation_pool[i];
      const isAnthropicFlag = preview.categorized.anthropic.includes(model) ? '[ANTHROPIC]' : '[THIRD-PARTY]';
      const nextFlag = i === 0 ? ' ← WOULD BE SELECTED NEXT' : '';
      console.log(`  ${(i + 1)}. ${model.padEnd(25)} ${isAnthropicFlag}${nextFlag}`);
    }
  } else {
    console.log('  ⚠️  NO MODELS AVAILABLE! All were filtered out!');
  }
  console.log('');

  // Summary
  console.log('========================================');
  console.log('SUMMARY');
  console.log('========================================');
  console.log(`Task: ${taskType}`);
  console.log(`Selected model: ${preview.result.selected_model}`);
  console.log(`Pool size: ${preview.result.rotation_pool.length}`);
  console.log(`Compliance: ${preview.rules.anthropic_only ? 'Anthropic-only enforced ✓' : 'Third-party models allowed'}`);
  console.log('');

  console.log('This was a DRY-RUN - no workflows executed, no database logging.');
  console.log('');
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
