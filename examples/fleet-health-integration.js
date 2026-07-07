#!/usr/bin/env node
/**
 * Fleet Health Predictor - Integration Example
 *
 * Demonstrates how to integrate predictive health checks into fleet workflows.
 */

import { getServerHealth, getPredictiveHealth, getWorkers } from '../shared/fleet-utils.js';

/**
 * Example 1: Pre-job health check
 * Check server health before assigning a job
 */
async function checkBeforeJobAssignment(hostname, jobId) {
  console.log(`\nChecking health of ${hostname} before assigning job ${jobId}...`);

  const health = await getServerHealth(hostname, { includePredictive: true });

  console.log(`  SSH reachable: ${health.reachable ? 'Yes' : 'No'}`);
  console.log(`  Combined status: ${health.combined_status}`);
  console.log(`  Degradation probability: ${(health.predictive_health.degradation_probability * 100).toFixed(1)}%`);
  console.log(`  Primary risk: ${health.predictive_health.primary_risk}`);
  console.log(`  Recommendation: ${health.recommendation}`);

  // Decision logic
  if (health.combined_status === 'unreachable') {
    console.log(`  ❌ REJECT: Server unreachable`);
    return { assigned: false, reason: 'unreachable' };
  }

  if (health.combined_status === 'degraded') {
    console.log(`  ⚠️  REJECT: Server degraded (${(health.predictive_health.degradation_probability * 100).toFixed(1)}% failure probability)`);
    return { assigned: false, reason: 'degraded' };
  }

  if (health.combined_status === 'at_risk') {
    console.log(`  ⚠️  ACCEPT (with caution): Server at risk but still usable`);
    return { assigned: true, reason: 'at_risk', monitor: true };
  }

  console.log(`  ✅ ACCEPT: Server healthy`);
  return { assigned: true, reason: 'healthy' };
}

/**
 * Example 2: Fleet-wide health scan
 * Get health status for all workers and prioritize healthy ones
 */
async function scanFleetHealth() {
  console.log('\n='.repeat(60));
  console.log('FLEET-WIDE HEALTH SCAN');
  console.log('='.repeat(60));

  const workers = getWorkers({ skipHealthCheck: true });
  console.log(`\nScanning ${workers.length} workers...\n`);

  const healthResults = [];

  for (const worker of workers) {
    try {
      const health = await getServerHealth(worker.hostname, { includePredictive: true });
      healthResults.push({
        hostname: worker.hostname,
        ...health
      });
    } catch (error) {
      console.error(`  ❌ ${worker.hostname}: ${error.message}`);
      healthResults.push({
        hostname: worker.hostname,
        reachable: false,
        combined_status: 'error',
        predictive_health: { degradation_probability: 1.0, primary_risk: 'error' }
      });
    }
  }

  // Sort by health (healthy first, degraded last)
  const sortOrder = { healthy: 0, at_risk: 1, degraded: 2, unreachable: 3, error: 4 };
  healthResults.sort((a, b) => sortOrder[a.combined_status] - sortOrder[b.combined_status]);

  // Display results
  console.log('Results:');
  healthResults.forEach(h => {
    const statusIcon = {
      healthy: '✅',
      at_risk: '⚠️ ',
      degraded: '❌',
      unreachable: '🔌',
      error: '💥'
    }[h.combined_status] || '?';

    const prob = (h.predictive_health.degradation_probability * 100).toFixed(1);
    console.log(`  ${statusIcon} ${h.hostname.padEnd(15)} ${h.combined_status.padEnd(12)} ${prob}% (${h.predictive_health.primary_risk})`);
  });

  // Summary
  const summary = {
    healthy: healthResults.filter(h => h.combined_status === 'healthy').length,
    at_risk: healthResults.filter(h => h.combined_status === 'at_risk').length,
    degraded: healthResults.filter(h => h.combined_status === 'degraded').length,
    unreachable: healthResults.filter(h => h.combined_status === 'unreachable').length,
    error: healthResults.filter(h => h.combined_status === 'error').length
  };

  console.log('\nSummary:');
  console.log(`  ✅ Healthy: ${summary.healthy}`);
  console.log(`  ⚠️  At Risk: ${summary.at_risk}`);
  console.log(`  ❌ Degraded: ${summary.degraded}`);
  console.log(`  🔌 Unreachable: ${summary.unreachable}`);
  console.log(`  💥 Errors: ${summary.error}`);

  return healthResults;
}

/**
 * Example 3: Proactive job migration
 * Migrate jobs from degraded servers to healthy ones
 */
async function proactiveMigration() {
  console.log('\n='.repeat(60));
  console.log('PROACTIVE JOB MIGRATION');
  console.log('='.repeat(60));

  const healthResults = await scanFleetHealth();

  const degraded = healthResults.filter(h => h.combined_status === 'degraded');
  const healthy = healthResults.filter(h => h.combined_status === 'healthy');

  if (degraded.length === 0) {
    console.log('\n✅ No degraded servers - no migration needed');
    return;
  }

  if (healthy.length === 0) {
    console.log('\n❌ No healthy servers available for migration!');
    return;
  }

  console.log(`\n⚠️  Found ${degraded.length} degraded server(s), migrating to ${healthy.length} healthy server(s)...\n`);

  for (const server of degraded) {
    const target = healthy[0]; // Simple round-robin (could be smarter)
    console.log(`  Migrate jobs: ${server.hostname} → ${target.hostname}`);
    console.log(`    Reason: ${server.predictive_health.primary_risk} (${(server.predictive_health.degradation_probability * 100).toFixed(1)}% failure probability)`);
    console.log(`    Action: ${server.recommendation}`);
    console.log(`    Urgency: ${server.urgency}`);

    // In real implementation:
    // - Get active jobs from server.hostname
    // - Move to target.hostname
    // - Update fleet.jobs table
  }

  console.log('\n✅ Migration plan complete (dry-run)');
}

/**
 * Example 4: Continuous monitoring loop
 * Monitor fleet health and alert on degradation
 */
async function continuousMonitoring(intervalMinutes = 5) {
  console.log('\n='.repeat(60));
  console.log('CONTINUOUS MONITORING MODE');
  console.log('='.repeat(60));
  console.log(`Checking fleet health every ${intervalMinutes} minutes...\n`);

  while (true) {
    const timestamp = new Date().toISOString();
    console.log(`\n[${timestamp}] Health check cycle`);

    try {
      const healthResults = await scanFleetHealth();

      const degraded = healthResults.filter(h => h.combined_status === 'degraded');
      const atRisk = healthResults.filter(h => h.combined_status === 'at_risk');

      if (degraded.length > 0) {
        console.log(`\n⚠️  ALERT: ${degraded.length} degraded server(s) require action!`);
        degraded.forEach(s => {
          console.log(`    - ${s.hostname}: ${s.recommendation} (urgency: ${s.urgency})`);
        });
      }

      if (atRisk.length > 0) {
        console.log(`\n⚠️  WARNING: ${atRisk.length} server(s) at risk`);
        atRisk.forEach(s => {
          console.log(`    - ${s.hostname}: ${(s.predictive_health.degradation_probability * 100).toFixed(1)}% (${s.predictive_health.primary_risk})`);
        });
      }

      if (degraded.length === 0 && atRisk.length === 0) {
        console.log('\n✅ All servers healthy');
      }
    } catch (error) {
      console.error(`\n❌ Health check failed: ${error.message}`);
    }

    // Wait for next cycle
    console.log(`\nNext check in ${intervalMinutes} minutes...`);
    await new Promise(resolve => setTimeout(resolve, intervalMinutes * 60 * 1000));
  }
}

/**
 * CLI entry point
 */
async function main() {
  const args = process.argv.slice(2);
  const command = args[0] || 'help';

  switch (command) {
    case 'check':
      // Check single server
      const hostname = args[1] || 'server-01';
      const jobId = args[2] || 'job-12345';
      await checkBeforeJobAssignment(hostname, jobId);
      break;

    case 'scan':
      // Scan all workers
      await scanFleetHealth();
      break;

    case 'migrate':
      // Proactive migration
      await proactiveMigration();
      break;

    case 'monitor':
      // Continuous monitoring
      const interval = parseInt(args[1] || '5', 10);
      await continuousMonitoring(interval);
      break;

    case 'help':
    default:
      console.log(`
Fleet Health Predictor - Integration Examples

Usage:
  node examples/fleet-health-integration.js <command> [options]

Commands:
  check <hostname> [jobId]   Check health before job assignment
  scan                       Scan all fleet workers
  migrate                    Generate proactive migration plan
  monitor [interval]         Continuous monitoring (default: 5 min)
  help                       Show this help

Examples:
  node examples/fleet-health-integration.js check server-01 job-123
  node examples/fleet-health-integration.js scan
  node examples/fleet-health-integration.js migrate
  node examples/fleet-health-integration.js monitor 10
      `);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error(`Fatal error: ${error.message}`);
    process.exit(1);
  });
}

// Exports
export {
  checkBeforeJobAssignment,
  scanFleetHealth,
  proactiveMigration,
  continuousMonitoring
};
