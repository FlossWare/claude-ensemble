#!/usr/bin/env node
/**
 * Model Drift Detection CLI
 *
 * Detects model performance degradation and logs alerts.
 * Run daily via cron for automated drift monitoring.
 *
 * Usage:
 *   node monitoring/check-drift.cjs [options]
 *
 * Options:
 *   --threshold=0.10    Drift threshold (default: 0.10 = 10%)
 *   --min-samples=5     Minimum samples required (default: 5)
 *   --no-weights        Skip Thompson Sampling weight updates
 *   --no-review         Skip human review queue
 *   --json              Output JSON instead of human-readable
 *   --history=MODEL     Show drift history for a model
 *   --unacknowledged    Show unacknowledged alerts
 *   --acknowledge=ID    Acknowledge a specific alert
 *
 * Examples:
 *   # Daily drift check
 *   node monitoring/check-drift.cjs
 *
 *   # Check with custom threshold (15% drop)
 *   node monitoring/check-drift.cjs --threshold=0.15
 *
 *   # Show unacknowledged alerts
 *   node monitoring/check-drift.cjs --unacknowledged
 *
 *   # Acknowledge alert
 *   node monitoring/check-drift.cjs --acknowledge=42
 *
 *   # Show drift history for a model
 *   node monitoring/check-drift.cjs --history=opus
 *
 * Cron setup:
 *   0 3 * * * cd /path/to/project && node monitoring/check-drift.cjs >> /var/log/drift-detection.log 2>&1
 *
 * Created: 2026-06-28
 */

const {
  runDriftDetectionPipeline,
  getUnacknowledgedAlerts,
  acknowledgeDriftAlert,
  getModelDriftHistory,
  close
} = require('./drift-detector.cjs');

// Parse command-line arguments
function parseArgs(argv) {
  const args = {
    threshold: 0.10,
    minSamples: 5,
    updateWeights: true,
    queueReview: true,
    json: false,
    history: null,
    unacknowledged: false,
    acknowledge: null
  };

  for (const arg of argv.slice(2)) {
    if (arg.startsWith('--threshold=')) {
      args.threshold = parseFloat(arg.split('=')[1]);
    } else if (arg.startsWith('--min-samples=')) {
      args.minSamples = parseInt(arg.split('=')[1]);
    } else if (arg === '--no-weights') {
      args.updateWeights = false;
    } else if (arg === '--no-review') {
      args.queueReview = false;
    } else if (arg === '--json') {
      args.json = true;
    } else if (arg.startsWith('--history=')) {
      args.history = arg.split('=')[1];
    } else if (arg === '--unacknowledged') {
      args.unacknowledged = true;
    } else if (arg.startsWith('--acknowledge=')) {
      args.acknowledge = parseInt(arg.split('=')[1]);
    } else if (arg === '--help' || arg === '-h') {
      console.log(`
Model Drift Detection CLI

Usage: node monitoring/check-drift.cjs [options]

Options:
  --threshold=0.10    Drift threshold (default: 0.10 = 10%)
  --min-samples=5     Minimum samples required (default: 5)
  --no-weights        Skip Thompson Sampling weight updates
  --no-review         Skip human review queue
  --json              Output JSON instead of human-readable
  --history=MODEL     Show drift history for a model
  --unacknowledged    Show unacknowledged alerts
  --acknowledge=ID    Acknowledge a specific alert
  --help, -h          Show this help message

Examples:
  node monitoring/check-drift.cjs
  node monitoring/check-drift.cjs --threshold=0.15
  node monitoring/check-drift.cjs --unacknowledged
  node monitoring/check-drift.cjs --acknowledge=42
  node monitoring/check-drift.cjs --history=opus

Cron setup:
  0 3 * * * cd /path/to/project && node monitoring/check-drift.cjs
      `);
      process.exit(0);
    }
  }

  return args;
}

// Format drift alert for display
function formatAlert(alert, index = null) {
  const prefix = index !== null ? `[${index + 1}] ` : '';
  const severity = alert.severity === 'critical' ? '🚨 CRITICAL' : '⚠️  WARNING';
  const drop = alert.performance_drop_pct.toFixed(2);
  const date = new Date(alert.detection_date).toISOString().split('T')[0];

  return `
${prefix}${severity}: ${alert.model} (${alert.task_type || 'all tasks'})
  Performance drop: ${drop}% (${alert.current_7day_avg.toFixed(3)} → ${alert.historical_30day_avg.toFixed(3)})
  Samples: current=${alert.current_sample_count}, historical=${alert.historical_sample_count}
  Detected: ${date}
  Alert ID: ${alert.id}
  ${alert.acknowledged ? '✓ Acknowledged by ' + alert.acknowledged_by + ' at ' + new Date(alert.acknowledged_at).toISOString() : '❌ Not acknowledged'}
  `.trim();
}

// Main function
async function main() {
  const args = parseArgs(process.argv);

  try {
    // Show drift history for a specific model
    if (args.history) {
      console.log(`📊 Drift history for model: ${args.history}\n`);
      const history = await getModelDriftHistory(args.history, 30);

      if (history.length === 0) {
        console.log('No drift alerts found for this model.');
      } else {
        for (let i = 0; i < history.length; i++) {
          console.log(formatAlert(history[i], i));
          console.log('');
        }
      }

      await close();
      return;
    }

    // Show unacknowledged alerts
    if (args.unacknowledged) {
      console.log('🚨 Unacknowledged drift alerts:\n');
      const alerts = await getUnacknowledgedAlerts();

      if (alerts.length === 0) {
        console.log('✅ No unacknowledged alerts.');
      } else {
        for (let i = 0; i < alerts.length; i++) {
          console.log(formatAlert(alerts[i], i));
          console.log('');
        }
      }

      await close();
      return;
    }

    // Acknowledge a specific alert
    if (args.acknowledge) {
      const username = process.env.USER || 'unknown';
      const success = await acknowledgeDriftAlert(args.acknowledge, username);

      if (success) {
        console.log(`✅ Alert #${args.acknowledge} acknowledged by ${username}`);
      } else {
        console.error(`❌ Failed to acknowledge alert #${args.acknowledge} (not found)`);
        process.exit(1);
      }

      await close();
      return;
    }

    // Run drift detection pipeline
    console.log('🔍 Model Performance Drift Detection');
    console.log(`Threshold: ${(args.threshold * 100).toFixed(0)}% drop`);
    console.log(`Minimum samples: ${args.minSamples}`);
    console.log('');

    const results = await runDriftDetectionPipeline({
      driftThreshold: args.threshold,
      minSamples: args.minSamples,
      updateWeights: args.updateWeights,
      queueReview: args.queueReview
    });

    if (args.json) {
      console.log(JSON.stringify(results, null, 2));
    } else {
      if (results.success) {
        console.log('');
        console.log(`✅ Drift detection complete (${results.duration_ms}ms)`);
        console.log('');

        if (results.drift_alerts.length === 0) {
          console.log('✅ No drift detected. All models performing normally.');
        } else {
          console.log(`🚨 Detected ${results.drift_alerts.length} drift alert(s):\n`);

          for (let i = 0; i < results.drift_alerts.length; i++) {
            const alert = results.drift_alerts[i];
            console.log(`[${i + 1}] ${alert.severity === 'critical' ? '🚨 CRITICAL' : '⚠️  WARNING'}: ${alert.model} (${alert.task_type || 'all tasks'})`);
            console.log(`    Performance drop: ${alert.performance_drop_pct.toFixed(2)}%`);
            console.log(`    Current (7-day): ${alert.current_7day_avg.toFixed(3)} (n=${alert.current_sample_count})`);
            console.log(`    Historical (30-day): ${alert.historical_30day_avg.toFixed(3)} (n=${alert.historical_sample_count})`);
            console.log(`    Alert ID: ${results.alert_ids[i]}`);
            console.log('');
          }

          console.log('Actions taken:');
          console.log(`  ✓ Logged ${results.alert_ids.length} alerts to monitoring.drift_alerts`);
          if (args.updateWeights) {
            console.log('  ✓ Updated Thompson Sampling weights (recommended)');
          }
          if (args.queueReview) {
            console.log('  ✓ Queued human review');
          }
          console.log('');
          console.log('Next steps:');
          console.log('  1. Review alerts: node monitoring/check-drift.cjs --unacknowledged');
          console.log('  2. Acknowledge: node monitoring/check-drift.cjs --acknowledge=<ID>');
          console.log('  3. Investigate model API changes, regional routing, or fine-tuning updates');
        }
      } else {
        console.error('');
        console.error(`❌ Drift detection failed: ${results.error}`);
        process.exit(1);
      }
    }

    await close();

  } catch (err) {
    console.error('❌ Error:', err.message);
    if (!args.json) {
      console.error('');
      console.error('Stack trace:');
      console.error(err.stack);
    }
    await close();
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

module.exports = { main };
