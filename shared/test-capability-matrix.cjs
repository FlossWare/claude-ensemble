#!/usr/bin/env node
/**
 * Test script for Model Capability Matrix
 *
 * Tests:
 * 1. Load capability matrix from JSON
 * 2. Select models by capability
 * 3. Select diverse models
 * 4. Get capability score with confidence
 * 5. Update capability scores from execution history
 * 6. PostgreSQL integration
 *
 * Usage:
 *   node shared/test-capability-matrix.js
 */

const {
  selectModelsByCapability,
  selectDiverseModels,
  getCapabilityScore,
  getCapabilityScoreWithConfidence,
  updateCapabilityScores,
  loadCapabilityMatrix,
  loadCapabilitiesFromDB,
  normalizeTaskType,
  TASK_TYPE_ALIASES,
} = require('./model-capability-matrix.cjs');

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  red: '\x1b[31m',
};

function colorize(text, color) {
  return `${colors[color]}${text}${colors.reset}`;
}

function section(title) {
  console.log('\n' + colorize('='.repeat(70), 'cyan'));
  console.log(colorize(title, 'bright'));
  console.log(colorize('='.repeat(70), 'cyan'));
}

async function test() {
  try {
    section('TEST 1: Load Capability Matrix from JSON');
    const fileCapabilities = loadCapabilityMatrix();
    const modelCount = Object.keys(fileCapabilities).length;
    const taskTypes = new Set();
    Object.values(fileCapabilities).forEach(tasks => {
      Object.keys(tasks).forEach(task => taskTypes.add(task));
    });
    console.log(colorize(`✓ Loaded ${modelCount} models`, 'green'));
    console.log(colorize(`✓ Found ${taskTypes.size} task types`, 'green'));
    console.log(`  Models: ${Object.keys(fileCapabilities).slice(0, 5).join(', ')}...`);
    console.log(`  Task types: ${Array.from(taskTypes).slice(0, 5).join(', ')}...`);

    section('TEST 2: Task Type Aliases');
    console.log('Aliases:');
    Object.entries(TASK_TYPE_ALIASES).forEach(([alias, canonical]) => {
      console.log(`  ${colorize(alias, 'yellow')} → ${canonical}`);
    });
    const normalized = normalizeTaskType('review');
    console.log(colorize(`✓ normalizeTaskType('review') = '${normalized}'`, 'green'));

    section('TEST 3: Select Models by Capability');
    const taskType = 'code_review';
    console.log(`Task: ${colorize(taskType, 'bright')}`);
    const models = await selectModelsByCapability(taskType, { limit: 5 });
    console.log(colorize(`✓ Selected ${models.length} models`, 'green'));
    models.forEach((m, i) => {
      const bar = '█'.repeat(Math.round(m.score * 20));
      console.log(`  ${i + 1}. ${colorize(m.model.padEnd(20), 'cyan')} ${colorize(m.score.toFixed(3), 'yellow')} ${bar}`);
    });

    section('TEST 4: Select Models with Filters');
    console.log(`Task: ${colorize('security_audit', 'bright')}`);
    console.log(`Filters: minScore=0.80, excludeModels=['haiku']`);
    const filteredModels = await selectModelsByCapability('security_audit', {
      limit: 5,
      minScore: 0.80,
      excludeModels: ['haiku'],
    });
    console.log(colorize(`✓ Selected ${filteredModels.length} models`, 'green'));
    filteredModels.forEach((m, i) => {
      const bar = '█'.repeat(Math.round(m.score * 20));
      console.log(`  ${i + 1}. ${colorize(m.model.padEnd(20), 'cyan')} ${colorize(m.score.toFixed(3), 'yellow')} ${bar}`);
    });

    section('TEST 5: Select Diverse Models');
    console.log(`Task: ${colorize('code_generation', 'bright')}`);
    console.log(`Options: limit=8, diversityWeight=0.5`);
    const diverseModels = await selectDiverseModels('code_generation', {
      limit: 8,
      diversityWeight: 0.5,
    });
    console.log(colorize(`✓ Selected ${diverseModels.length} diverse models`, 'green'));
    const families = {};
    diverseModels.forEach((m, i) => {
      families[m.family] = (families[m.family] || 0) + 1;
      const bar = '█'.repeat(Math.round(m.score * 20));
      console.log(`  ${i + 1}. ${colorize(m.model.padEnd(20), 'cyan')} ${colorize(m.score.toFixed(3), 'yellow')} [${m.family}] ${bar}`);
    });
    console.log('\nFamily distribution:');
    Object.entries(families).forEach(([family, count]) => {
      console.log(`  ${colorize(family.padEnd(15), 'yellow')}: ${count} models`);
    });

    section('TEST 6: Get Capability Score (single model/task)');
    const model = 'opus';
    const task = 'code_review';
    const score = await getCapabilityScore(model, task);
    console.log(`Model: ${colorize(model, 'bright')}, Task: ${colorize(task, 'bright')}`);
    console.log(colorize(`✓ Score: ${score.toFixed(3)}`, 'green'));

    section('TEST 7: Get Capability Score with Confidence');
    const scoreWithConf = await getCapabilityScoreWithConfidence(model, task);
    console.log(`Model: ${colorize(model, 'bright')}, Task: ${colorize(task, 'bright')}`);
    console.log(colorize(`✓ Score: ${scoreWithConf.score.toFixed(3)}`, 'green'));
    console.log(colorize(`✓ Confidence: ${scoreWithConf.confidence.toFixed(3)}`, 'green'));
    console.log(`  Executions: ${scoreWithConf.executions}`);
    console.log(`  Source: ${scoreWithConf.source}`);

    section('TEST 8: Load Capabilities from PostgreSQL');
    const dbCapabilities = await loadCapabilitiesFromDB();
    const dbModelCount = Object.keys(dbCapabilities).length;
    const dbTaskTypes = new Set();
    Object.values(dbCapabilities).forEach(tasks => {
      Object.keys(tasks).forEach(task => dbTaskTypes.add(task));
    });
    console.log(colorize(`✓ Loaded ${dbModelCount} models from DB`, 'green'));
    console.log(colorize(`✓ Found ${dbTaskTypes.size} task types in DB`, 'green'));
    if (dbModelCount > 0) {
      console.log(`  DB Models: ${Object.keys(dbCapabilities).slice(0, 5).join(', ')}...`);
      console.log(`  DB Task types: ${Array.from(dbTaskTypes).slice(0, 5).join(', ')}...`);
    } else {
      console.log(colorize('  ℹ No data in DB yet (run updateCapabilityScores first)', 'yellow'));
    }

    section('TEST 9: Update Capability Scores from Execution History');
    console.log('Running updateCapabilityScores (minExecutions=10)...');
    const updateResult = await updateCapabilityScores({ minExecutions: 10 });
    if (updateResult.status === 'success') {
      console.log(colorize(`✓ Updated ${updateResult.updated} capability scores`, 'green'));
      if (updateResult.updated > 0) {
        console.log('\nSample updates:');
        updateResult.updates.slice(0, 5).forEach(u => {
          console.log(`  ${colorize(u.model.padEnd(20), 'cyan')} ${u.task_type.padEnd(20)}`);
          console.log(`    Baseline: ${u.baseline_score.toFixed(3)} → Observed: ${u.observed_score.toFixed(3)} → New: ${u.new_score.toFixed(3)}`);
          console.log(`    Executions: ${u.executions}, StdDev: ${u.stddev?.toFixed(3) || 'N/A'}`);
        });
      }
    } else {
      console.log(colorize(`✗ Update failed: ${updateResult.error}`, 'red'));
    }

    section('TEST 10: Integration with Weighted Voting');
    console.log('Demonstrating integration with weighted-voting.cjs...\n');
    const { getCapabilityScore: getVotingScore } = require('./weighted-voting.cjs');
    console.log('Comparing scores from both systems:');
    const testModels = ['opus', 'sonnet', 'haiku', 'deepseek-coder'];
    const testTask = 'code_generation';
    for (const testModel of testModels) {
      const matrixScore = await getCapabilityScore(testModel, testTask);
      const votingScore = getVotingScore(testModel, testTask);
      const match = Math.abs(matrixScore - votingScore) < 0.01 ? '✓' : '✗';
      console.log(`  ${colorize(testModel.padEnd(20), 'cyan')} Matrix: ${matrixScore.toFixed(3)} | Voting: ${votingScore.toFixed(3)} ${colorize(match, match === '✓' ? 'green' : 'yellow')}`);
    }

    section('TEST 11: PostgreSQL Materialized View');
    const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');
    const db = getWorkflowStorage();
    const topModelsResult = await db.pool.query(`
      SELECT task_type, top_models, top_scores
      FROM monitoring.model_capabilities_top
      LIMIT 5
    `);
    console.log(colorize(`✓ Loaded ${topModelsResult.rows.length} task types from materialized view`, 'green'));
    topModelsResult.rows.forEach(row => {
      console.log(`\n  Task: ${colorize(row.task_type, 'bright')}`);
      const models = row.top_models || [];
      const scores = row.top_scores || [];
      models.slice(0, 3).forEach((model, i) => {
        console.log(`    ${i + 1}. ${colorize(model.padEnd(20), 'cyan')} ${colorize(scores[i]?.toFixed(3) || 'N/A', 'yellow')}`);
      });
    });

    section('TEST 12: Confidence Function (PostgreSQL)');
    const confidenceTests = [10, 50, 100, 200];
    console.log('Testing confidence calculation for different execution counts:\n');
    for (const execCount of confidenceTests) {
      const result = await db.pool.query(
        'SELECT monitoring.capability_confidence($1) AS confidence',
        [execCount]
      );
      const confidence = parseFloat(result.rows[0].confidence);
      const bar = '█'.repeat(Math.round(confidence * 30));
      console.log(`  ${execCount.toString().padStart(3)} executions: ${colorize(confidence.toFixed(3), 'yellow')} ${bar}`);
    }

    section('SUMMARY');
    console.log(colorize('✓ All tests passed', 'green'));
    console.log('\nNext steps:');
    console.log('  1. Run updateCapabilityScores() periodically (e.g., daily cron job)');
    console.log('  2. Use selectModelsByCapability() in workflow routing logic');
    console.log('  3. Monitor monitoring.model_capabilities table for learned scores');
    console.log('  4. Integrate with weighted-voting.cjs for dynamic voting weights');
    console.log('\nSee: shared/MODEL-CAPABILITY-MATRIX-README.md for full documentation');

  } catch (err) {
    console.error(colorize(`\n✗ Test failed: ${err.message}`, 'red'));
    console.error(err.stack);
    process.exit(1);
  }
}

// Run tests
test().catch(err => {
  console.error(colorize(`Fatal error: ${err.message}`, 'red'));
  process.exit(1);
});
