#!/usr/bin/env node
/**
 * Resource Estimation Learning CLI
 *
 * Manage and monitor the ML-based resource estimation system (Issue #109)
 *
 * Usage:
 *   node tools/resource-estimation-cli.js stats                    # Show learning statistics
 *   node tools/resource-estimation-cli.js estimate <features>      # Get estimate
 *   node tools/resource-estimation-cli.js retrain                  # Force retraining
 *   node tools/resource-estimation-cli.js recent [limit]           # Show recent jobs
 *   node tools/resource-estimation-cli.js accuracy                 # Show accuracy metrics
 */

const {
  learnFromExecution,
  getLearnedEstimate,
  getLearningStats,
  forceRetrain,
  pool
} = require('../shared/resource-estimation-learner.cjs');

async function showStats() {
  console.log('\n📊 Resource Estimation Learning Statistics\n');
  console.log('='.repeat(80));

  const stats = await getLearningStats();

  console.log(`Total jobs tracked:           ${stats.total_jobs.toLocaleString()}`);
  console.log(`Model retrains:               ${stats.retrain_count}`);
  console.log(`Jobs since last retrain:      ${stats.jobs_since_retrain}`);
  console.log(`Consecutive high errors:      ${stats.consecutive_high_errors}`);
  console.log(`Last retrain:                 ${stats.last_retrain ? new Date(stats.last_retrain).toLocaleString() : 'Never'}`);

  console.log('\n--- 7-Day Averages ---');
  console.log(`Avg duration error:           ${(stats.avg_duration_error_7d * 100).toFixed(1)}%`);
  console.log(`Avg RAM error:                ${(stats.avg_ram_error_7d * 100).toFixed(1)}%`);

  console.log('\n--- Current Model Performance ---');
  if (stats.current_duration_mae !== null) {
    console.log(`Duration MAE:                 ${stats.current_duration_mae.toFixed(2)}s`);
    console.log(`RAM MAE:                      ${stats.current_ram_mae.toFixed(3)}GB`);
    console.log(`Improvement vs baseline:      ${stats.improvement_pct.toFixed(1)}%`);
  } else {
    console.log('No trained model yet (need 10+ jobs)');
  }

  console.log('='.repeat(80));
  console.log('\n✅ Use "node tools/resource-estimation-cli.js retrain" to force retraining\n');
}

async function getEstimate(features) {
  const featureObj = JSON.parse(features);
  console.log('\n🔮 Getting resource estimate\n');
  console.log('Features:', JSON.stringify(featureObj, null, 2));

  const estimate = await getLearnedEstimate(featureObj);

  if (!estimate) {
    console.log('\n❌ No learned model available (will use heuristic)');
    process.exit(1);
  }

  console.log('\n📈 Estimate:');
  console.log(`  Duration:  ${estimate.duration}s`);
  console.log(`  RAM:       ${estimate.ram}GB`);
  console.log('');
}

async function performRetrain() {
  console.log('\n🔄 Force retraining resource estimation model...\n');
  await forceRetrain();
  console.log('\n✅ Retraining complete\n');
  await showStats();
}

async function showRecentJobs(limit = 20) {
  console.log(`\n📋 Recent ${limit} Jobs\n`);
  console.log('='.repeat(120));

  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT
        timestamp,
        model,
        job_type,
        prompt_length,
        schema_complexity,
        estimated_duration,
        estimated_ram,
        actual_duration,
        actual_ram,
        duration_error,
        ram_error
      FROM monitoring.resource_estimation_log
      ORDER BY timestamp DESC
      LIMIT $1
    `, [limit]);

    console.log('Timestamp           | Model    | Type          | Prompt | Schema | Est.Dur | Act.Dur | Dur.Err | Est.RAM | Act.RAM | RAM.Err');
    console.log('-'.repeat(120));

    for (const row of result.rows) {
      const timestamp = new Date(row.timestamp).toLocaleString().padEnd(20);
      const model = row.model.padEnd(8);
      const jobType = row.job_type.padEnd(13);
      const promptLen = row.prompt_length.toString().padEnd(6);
      const schemaComp = row.schema_complexity.toString().padEnd(6);
      const estDur = `${row.estimated_duration}s`.padEnd(7);
      const actDur = `${row.actual_duration}s`.padEnd(7);
      const durErr = `${(row.duration_error * 100).toFixed(0)}%`.padEnd(7);
      const estRam = `${row.estimated_ram}GB`.padEnd(7);
      const actRam = `${row.actual_ram}GB`.padEnd(7);
      const ramErr = `${(row.ram_error * 100).toFixed(0)}%`.padEnd(7);

      console.log(`${timestamp} | ${model} | ${jobType} | ${promptLen} | ${schemaComp} | ${estDur} | ${actDur} | ${durErr} | ${estRam} | ${actRam} | ${ramErr}`);
    }

    console.log('='.repeat(120));
    console.log('');

  } finally {
    client.release();
  }
}

async function showAccuracy() {
  console.log('\n📊 Model Accuracy Over Time\n');
  console.log('='.repeat(80));

  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT
        trained_at,
        job_count,
        duration_mae,
        duration_rmse,
        ram_mae,
        ram_rmse,
        improvement_pct
      FROM monitoring.resource_estimation_coefficients
      ORDER BY trained_at DESC
      LIMIT 10
    `);

    if (result.rows.length === 0) {
      console.log('No training history yet');
      console.log('='.repeat(80));
      return;
    }

    console.log('Trained At          | Jobs | Dur.MAE | Dur.RMSE | RAM.MAE | RAM.RMSE | Improvement');
    console.log('-'.repeat(80));

    for (const row of result.rows) {
      const trained = new Date(row.trained_at).toLocaleString().padEnd(20);
      const jobs = row.job_count.toString().padEnd(4);
      const durMae = `${row.duration_mae.toFixed(2)}s`.padEnd(7);
      const durRmse = `${row.duration_rmse.toFixed(2)}s`.padEnd(8);
      const ramMae = `${row.ram_mae.toFixed(3)}GB`.padEnd(7);
      const ramRmse = `${row.ram_rmse.toFixed(3)}GB`.padEnd(8);
      const improvement = `${row.improvement_pct.toFixed(1)}%`.padEnd(11);

      console.log(`${trained} | ${jobs} | ${durMae} | ${durRmse} | ${ramMae} | ${ramRmse} | ${improvement}`);
    }

    console.log('='.repeat(80));
    console.log('');

  } finally {
    client.release();
  }
}

async function main() {
  const command = process.argv[2];

  try {
    switch (command) {
      case 'stats':
        await showStats();
        break;

      case 'estimate':
        if (!process.argv[3]) {
          console.error('Usage: resource-estimation-cli.js estimate \'{"prompt_length":1500,"model":"opus","schema_complexity":5,"job_type":"code-review"}\'');
          process.exit(1);
        }
        await getEstimate(process.argv[3]);
        break;

      case 'retrain':
        await performRetrain();
        break;

      case 'recent':
        const limit = parseInt(process.argv[3]) || 20;
        await showRecentJobs(limit);
        break;

      case 'accuracy':
        await showAccuracy();
        break;

      default:
        console.log(`
Resource Estimation Learning CLI

Usage:
  node tools/resource-estimation-cli.js stats                    Show learning statistics
  node tools/resource-estimation-cli.js estimate <features>      Get estimate for features
  node tools/resource-estimation-cli.js retrain                  Force model retraining
  node tools/resource-estimation-cli.js recent [limit]           Show recent jobs
  node tools/resource-estimation-cli.js accuracy                 Show accuracy metrics over time

Examples:
  node tools/resource-estimation-cli.js stats
  node tools/resource-estimation-cli.js estimate '{"prompt_length":1500,"model":"opus","schema_complexity":5,"job_type":"code-review"}'
  node tools/resource-estimation-cli.js recent 50
        `);
        process.exit(1);
    }

    await pool.end();
    process.exit(0);

  } catch (error) {
    console.error('\n❌ Error:', error.message);
    console.error(error.stack);
    await pool.end();
    process.exit(1);
  }
}

main();
