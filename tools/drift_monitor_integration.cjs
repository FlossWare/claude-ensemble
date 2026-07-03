#!/usr/bin/env node
/**
 * Drift Monitor Integration
 *
 * Integrates drift_detector.py with existing monitoring infrastructure:
 * - Calls drift_detector.py periodically
 * - Stores results in workflow.drift_detections table
 * - Triggers alerts on critical drift
 * - Feeds into performance_dashboard.py
 *
 * Usage:
 *   node tools/drift_monitor_integration.cjs [--once] [--days 30]
 *   node tools/drift_monitor_integration.cjs --continuous --interval 3600
 *
 * Integration points:
 * 1. workflow.drift_detections table (new)
 * 2. consensus-replay.cjs (trigger replay on drift)
 * 3. performance_dashboard.py (visualization)
 * 4. Alert system (Slack/email)
 *
 * Created: 2026-07-03
 */

const { Pool } = require('pg');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || 'sfloess',
  password: process.env.PGPASSWORD,
});

const DRIFT_DETECTOR_PATH = path.join(__dirname, 'drift_detector.py');
const DRIFT_REPORTS_DIR = path.join(process.env.HOME, '.claude', 'learning', 'drift_reports');

/**
 * Create drift_detections table if not exists
 */
async function ensureDriftTable() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS workflow.drift_detections (
        id SERIAL PRIMARY KEY,
        detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
        model VARCHAR(255) NOT NULL,
        drift_type VARCHAR(100),
        severity VARCHAR(20),
        affected_metrics TEXT[],
        signal_count INTEGER,
        sample_count INTEGER,
        time_range_start TIMESTAMP,
        time_range_end TIMESTAMP,
        details JSONB,
        report_path TEXT,
        resolved BOOLEAN DEFAULT FALSE,
        resolved_at TIMESTAMP,
        resolution_notes TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_drift_detections_model
        ON workflow.drift_detections(model);

      CREATE INDEX IF NOT EXISTS idx_drift_detections_detected_at
        ON workflow.drift_detections(detected_at DESC);

      CREATE INDEX IF NOT EXISTS idx_drift_detections_severity
        ON workflow.drift_detections(severity);

      CREATE INDEX IF NOT EXISTS idx_drift_detections_unresolved
        ON workflow.drift_detections(resolved)
        WHERE resolved = FALSE;
    `);

    console.log('✓ Ensured workflow.drift_detections table exists');
  } finally {
    client.release();
  }
}

/**
 * Run drift detector and parse results
 */
async function runDriftDetector(options = {}) {
  const { days = 30, model = null } = options;

  return new Promise((resolve, reject) => {
    const args = ['--save-report', '--days', days.toString()];
    if (model) {
      args.push('--model', model);
    }

    console.log(`Running drift detector: python3 ${DRIFT_DETECTOR_PATH} ${args.join(' ')}`);

    const proc = spawn('python3', [DRIFT_DETECTOR_PATH, ...args], {
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
      process.stdout.write(data); // Stream to console
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
      process.stderr.write(data);
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Drift detector exited with code ${code}\n${stderr}`));
        return;
      }

      // Read latest report
      const reportPath = path.join(DRIFT_REPORTS_DIR, 'latest_drift_report.json');
      if (!fs.existsSync(reportPath)) {
        reject(new Error('Drift report not found'));
        return;
      }

      const report = JSON.parse(fs.readFileSync(reportPath, 'utf-8'));
      resolve(report);
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn drift detector: ${err.message}`));
    });
  });
}

/**
 * Store drift detection results in database
 */
async function storeDriftResults(report) {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    const insertedIds = [];

    for (const [model, result] of Object.entries(report.models)) {
      if (!result.drift_detected) {
        continue; // Only store detected drifts
      }

      const insertResult = await client.query(`
        INSERT INTO workflow.drift_detections (
          detected_at,
          model,
          drift_type,
          severity,
          affected_metrics,
          signal_count,
          sample_count,
          time_range_start,
          time_range_end,
          details,
          report_path
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id
      `, [
        new Date(report.timestamp),
        model,
        result.drift_type,
        result.severity,
        result.affected_metrics || [],
        result.signal_count,
        result.sample_count,
        result.time_range?.start || null,
        result.time_range?.end || null,
        JSON.stringify(result),
        path.join(DRIFT_REPORTS_DIR, 'latest_drift_report.json')
      ]);

      const driftId = insertResult.rows[0].id;
      insertedIds.push({ id: driftId, model, severity: result.severity });

      console.log(`  ✓ Stored drift detection ID ${driftId} for ${model} (${result.severity})`);
    }

    await client.query('COMMIT');

    return insertedIds;

  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

/**
 * Trigger consensus replay for models with critical drift
 */
async function triggerReplayOnCriticalDrift(driftDetections) {
  const criticalDrifts = driftDetections.filter(d => d.severity === 'CRITICAL');

  if (criticalDrifts.length === 0) {
    return;
  }

  console.log(`\n🚨 Triggering consensus replay for ${criticalDrifts.length} critical drifts...`);

  for (const drift of criticalDrifts) {
    console.log(`  Model: ${drift.model}`);

    // TODO: Integrate with model_regression_monitor.cjs
    // This would select representative workflows for this model
    // and trigger consensus-replay to validate drift
    console.log(`  ⚠ Auto-replay integration pending (manual trigger recommended)`);
  }
}

/**
 * Send drift alerts (Slack/email/etc)
 */
async function sendDriftAlerts(report, driftDetections) {
  const criticalCount = driftDetections.filter(d => d.severity === 'CRITICAL').length;
  const highCount = driftDetections.filter(d => d.severity === 'HIGH').length;

  if (criticalCount === 0 && highCount === 0) {
    return; // No severe drifts to alert on
  }

  const alert = {
    timestamp: new Date().toISOString(),
    critical_drifts: criticalCount,
    high_drifts: highCount,
    total_drifts: driftDetections.length,
    models: driftDetections.map(d => d.model)
  };

  console.log('\n' + '='.repeat(60));
  console.log('⚠ DRIFT ALERT');
  console.log('='.repeat(60));
  console.log(`Critical drifts: ${criticalCount}`);
  console.log(`High severity drifts: ${highCount}`);
  console.log(`Models affected: ${alert.models.join(', ')}`);
  console.log('='.repeat(60));

  // TODO: Integrate with alert system (Slack webhook, email, etc)
  // For now, just log to file
  const alertsFile = path.join(DRIFT_REPORTS_DIR, 'drift_alerts.jsonl');
  fs.appendFileSync(alertsFile, JSON.stringify(alert) + '\n');
}

/**
 * Get unresolved drift detections
 */
async function getUnresolvedDrifts() {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT
        id,
        detected_at,
        model,
        drift_type,
        severity,
        affected_metrics,
        signal_count
      FROM workflow.drift_detections
      WHERE resolved = FALSE
      ORDER BY severity DESC, detected_at DESC
    `);

    return result.rows;
  } finally {
    client.release();
  }
}

/**
 * Resolve drift detection (manual or auto after verification)
 */
async function resolveDrift(driftId, notes) {
  const client = await pool.connect();
  try {
    await client.query(`
      UPDATE workflow.drift_detections
      SET resolved = TRUE,
          resolved_at = NOW(),
          resolution_notes = $2
      WHERE id = $1
    `, [driftId, notes]);

    console.log(`✓ Resolved drift detection ID ${driftId}`);
  } finally {
    client.release();
  }
}

/**
 * Continuous monitoring loop
 */
async function continuousMonitoring(options = {}) {
  const { interval = 3600, days = 7 } = options; // Default: check every hour, analyze last 7 days

  console.log('Starting continuous drift monitoring');
  console.log(`Check interval: ${interval}s (${interval / 60} minutes)`);
  console.log(`Analysis window: ${days} days`);
  console.log('Press Ctrl+C to stop\n');

  const runCheck = async () => {
    try {
      console.log(`\n${'='.repeat(60)}`);
      console.log(`Drift Check: ${new Date().toISOString()}`);
      console.log('='.repeat(60));

      const report = await runDriftDetector({ days });

      if (report.drift_detected) {
        const driftDetections = await storeDriftResults(report);
        await sendDriftAlerts(report, driftDetections);
        await triggerReplayOnCriticalDrift(driftDetections);
      } else {
        console.log('✓ No drift detected across all models');
      }

      // Show unresolved drifts
      const unresolved = await getUnresolvedDrifts();
      if (unresolved.length > 0) {
        console.log(`\n⚠ ${unresolved.length} unresolved drift detections:`);
        unresolved.slice(0, 5).forEach(d => {
          console.log(`  - ${d.model} (${d.severity}) detected ${d.detected_at.toISOString()}`);
        });
      }

    } catch (error) {
      console.error('Drift check failed:', error.message);
    }
  };

  // Run initial check
  await runCheck();

  // Schedule periodic checks
  setInterval(runCheck, interval * 1000);
}

/**
 * Main entry point
 */
async function main() {
  const args = process.argv.slice(2);

  // Parse arguments
  let continuous = false;
  let interval = 3600;
  let days = 30;
  let model = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--continuous') {
      continuous = true;
    } else if (args[i] === '--interval' && args[i + 1]) {
      interval = parseInt(args[i + 1]);
    } else if (args[i] === '--days' && args[i + 1]) {
      days = parseInt(args[i + 1]);
    } else if (args[i] === '--model' && args[i + 1]) {
      model = args[i + 1];
    } else if (args[i] === '--once') {
      continuous = false;
    }
  }

  try {
    // Ensure database table exists
    await ensureDriftTable();

    if (continuous) {
      await continuousMonitoring({ interval, days });
    } else {
      // One-time check
      console.log('Running one-time drift detection...\n');

      const report = await runDriftDetector({ days, model });

      if (report.drift_detected) {
        console.log('\n=== Storing drift detections ===');
        const driftDetections = await storeDriftResults(report);

        console.log(`\n✓ Stored ${driftDetections.length} drift detections`);

        await sendDriftAlerts(report, driftDetections);
        await triggerReplayOnCriticalDrift(driftDetections);
      } else {
        console.log('\n✓ No drift detected');
      }

      await pool.end();
    }

  } catch (error) {
    console.error('Error:', error.message);
    await pool.end();
    process.exit(1);
  }
}

// Run if invoked directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = {
  ensureDriftTable,
  runDriftDetector,
  storeDriftResults,
  getUnresolvedDrifts,
  resolveDrift,
  continuousMonitoring
};
