/**
 * deploy-fleet-prometheus.js - Workflow-based Prometheus fleet deployment
 *
 * Integrates with fleet-utils.js for SSH execution and fleet discovery.
 * Can be invoked as a Claude Code workflow or standalone via node.
 *
 * Usage as workflow:
 *   claude /deploy-fleet-prometheus
 *   claude /deploy-fleet-prometheus --node-exporter-only
 *   claude /deploy-fleet-prometheus --dry-run
 *
 * Usage standalone:
 *   node deploy-fleet-prometheus.js
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';

// ---------------------------------------------------------------------------
// Fleet configuration (mirrors ~/.claude/fleet.json)
// ---------------------------------------------------------------------------
const FLEET = [
  { hostname: 'aio-01',    role: 'controller', arch: 'amd64', cpus: 2,  memory_gb: 7  },
  { hostname: 'server-01', role: 'worker',     arch: 'amd64', cpus: 8,  memory_gb: 15 },
  { hostname: 'server-02', role: 'worker',     arch: 'amd64', cpus: 8,  memory_gb: 31 },
  { hostname: 'server-03', role: 'worker',     arch: 'amd64', cpus: 8,  memory_gb: 31 },
  { hostname: 'pi-02',     role: 'sentinel',   arch: 'arm64', cpus: 4,  memory_gb: 1  },
];

const CONTROLLER = 'aio-01';
const SCRIPT_DIR = path.dirname(new URL(import.meta.url).pathname);

// ---------------------------------------------------------------------------
// SSH helpers (matching fleet-utils.js patterns)
// ---------------------------------------------------------------------------
function sshExec(hostname, command, { timeout = 120000, throwOnError = true } = {}) {
  const escaped = command.replace(/'/g, "'\\''");
  const sshCmd = `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes ${hostname} '${escaped}'`;

  try {
    const stdout = execSync(sshCmd, {
      encoding: 'utf8',
      timeout,
      stdio: 'pipe',
    });
    return { hostname, stdout: stdout.trim(), success: true, exitCode: 0 };
  } catch (error) {
    const result = {
      hostname,
      stdout: error.stdout?.toString().trim() || '',
      stderr: error.stderr?.toString().trim() || error.message,
      success: false,
      exitCode: error.status || 1,
    };
    if (throwOnError) {
      throw new Error(`SSH to ${hostname} failed: ${result.stderr}`);
    }
    return result;
  }
}

function scpFile(localPath, hostname, remotePath) {
  const cmd = `scp -o BatchMode=yes -o StrictHostKeyChecking=yes "${localPath}" ${hostname}:${remotePath}`;
  execSync(cmd, { encoding: 'utf8', timeout: 30000, stdio: 'pipe' });
}

function sshCheck(hostname) {
  try {
    execSync(
      `ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=yes ${hostname} 'echo ok'`,
      { encoding: 'utf8', timeout: 6000, stdio: 'pipe' }
    );
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Deployment functions
// ---------------------------------------------------------------------------
function checkFleetHealth(hosts) {
  console.log('[INFO] Checking fleet connectivity...');
  const results = {};
  const failed = [];

  for (const host of hosts) {
    const ok = sshCheck(host.hostname);
    results[host.hostname] = ok;
    console.log(`  ${ok ? '[OK]' : '[FAIL]'}  ${host.hostname}`);
    if (!ok) failed.push(host.hostname);
  }

  if (failed.length > 0) {
    throw new Error(`Cannot reach hosts: ${failed.join(', ')}. Fix SSH connectivity.`);
  }

  return results;
}

function deployNodeExporter(host, dryRun = false) {
  console.log(`[INFO] Deploying node_exporter to ${host.hostname}...`);

  if (dryRun) {
    console.log(`  [DRY-RUN] Would deploy node_exporter to ${host.hostname}`);
    return { hostname: host.hostname, success: true };
  }

  const scriptPath = path.join(SCRIPT_DIR, 'install-node-exporter.sh');
  if (!fs.existsSync(scriptPath)) {
    throw new Error(`Missing: ${scriptPath}`);
  }

  scpFile(scriptPath, host.hostname, '/tmp/install-node-exporter.sh');
  const result = sshExec(host.hostname,
    'sudo bash /tmp/install-node-exporter.sh && rm -f /tmp/install-node-exporter.sh',
    { timeout: 180000, throwOnError: false }
  );

  if (result.success) {
    console.log(`  [OK] node_exporter deployed to ${host.hostname}`);
  } else {
    console.error(`  [FAIL] node_exporter failed on ${host.hostname}: ${result.stderr}`);
  }

  return result;
}

function deployPrometheus(dryRun = false, ntfyTopic = 'fleet-alerts', ntfyUrl = 'https://ntfy.sh') {
  console.log(`[INFO] Deploying Prometheus + Alertmanager to ${CONTROLLER}...`);

  if (dryRun) {
    console.log(`  [DRY-RUN] Would deploy Prometheus to ${CONTROLLER}`);
    return { hostname: CONTROLLER, success: true };
  }

  const scriptPath = path.join(SCRIPT_DIR, 'install-prometheus.sh');
  scpFile(scriptPath, CONTROLLER, '/tmp/install-prometheus.sh');

  const result = sshExec(CONTROLLER,
    `sudo NTFY_TOPIC='${ntfyTopic}' NTFY_URL='${ntfyUrl}' bash /tmp/install-prometheus.sh && rm -f /tmp/install-prometheus.sh`,
    { timeout: 300000, throwOnError: false }
  );

  if (result.success) {
    console.log(`  [OK] Prometheus + Alertmanager deployed to ${CONTROLLER}`);
  } else {
    console.error(`  [FAIL] Prometheus deployment failed: ${result.stderr}`);
  }

  return result;
}

function deployGrafana(dryRun = false) {
  console.log(`[INFO] Deploying Grafana to ${CONTROLLER}...`);

  if (dryRun) {
    console.log(`  [DRY-RUN] Would deploy Grafana to ${CONTROLLER}`);
    return { hostname: CONTROLLER, success: true };
  }

  const scriptPath = path.join(SCRIPT_DIR, 'install-grafana.sh');
  scpFile(scriptPath, CONTROLLER, '/tmp/install-grafana.sh');

  const result = sshExec(CONTROLLER,
    'sudo bash /tmp/install-grafana.sh && rm -f /tmp/install-grafana.sh',
    { timeout: 300000, throwOnError: false }
  );

  if (result.success) {
    console.log(`  [OK] Grafana deployed to ${CONTROLLER}`);
  } else {
    console.error(`  [WARN] Grafana deployment failed (non-fatal): ${result.stderr}`);
  }

  return result;
}

function verifyDeployment(hosts) {
  console.log('\n[INFO] Verifying deployment...');
  const status = {};

  for (const host of hosts) {
    const result = sshExec(host.hostname,
      'systemctl is-active node_exporter 2>/dev/null || echo inactive',
      { throwOnError: false }
    );
    const active = result.stdout === 'active';
    status[host.hostname] = { node_exporter: active };
    console.log(`  ${active ? '[OK]' : '[WARN]'}  ${host.hostname}: node_exporter ${result.stdout}`);
  }

  // Check Prometheus services on controller
  for (const svc of ['prometheus', 'alertmanager', 'grafana-server']) {
    const result = sshExec(CONTROLLER,
      `systemctl is-active ${svc} 2>/dev/null || echo inactive`,
      { throwOnError: false }
    );
    const active = result.stdout === 'active';
    status[CONTROLLER][svc] = active;
    console.log(`  ${active ? '[OK]' : '[WARN]'}  ${CONTROLLER}: ${svc} ${result.stdout}`);
  }

  return status;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const nodeExporterOnly = args.includes('--node-exporter-only');
  const prometheusOnly = args.includes('--prometheus-only');
  const skipGrafana = args.includes('--skip-grafana');

  console.log('='.repeat(50));
  console.log('  Fleet Prometheus Deployment');
  console.log('='.repeat(50));
  console.log(`  Controller: ${CONTROLLER}`);
  console.log(`  Fleet: ${FLEET.map(h => h.hostname).join(', ')}`);
  if (dryRun) console.log('  *** DRY RUN MODE ***');
  console.log('');

  // Phase 0: Health check
  checkFleetHealth(FLEET);
  console.log('');

  // Phase 1: node_exporter
  if (!prometheusOnly) {
    console.log('--- Phase 1: node_exporter ---');
    const results = FLEET.map(host => deployNodeExporter(host, dryRun));
    const failures = results.filter(r => !r.success);
    if (failures.length > 0) {
      console.error(`[ERROR] ${failures.length} node_exporter deployments failed.`);
      process.exit(1);
    }
    console.log('');
  }

  // Phase 2: Prometheus + Alertmanager
  if (!nodeExporterOnly) {
    console.log('--- Phase 2: Prometheus + Alertmanager ---');
    const result = deployPrometheus(dryRun);
    if (!result.success) {
      console.error('[ERROR] Prometheus deployment failed.');
      process.exit(1);
    }
    console.log('');

    // Phase 3: Grafana
    if (!skipGrafana) {
      console.log('--- Phase 3: Grafana ---');
      deployGrafana(dryRun);
      console.log('');
    }
  }

  // Verify
  if (!dryRun) {
    const status = verifyDeployment(FLEET);
    console.log('');
  }

  // Summary
  console.log('='.repeat(50));
  console.log('  Deployment Complete');
  console.log('='.repeat(50));
  console.log('  Prometheus:   http://aio-01:9090');
  console.log('  Alertmanager: http://aio-01:9093');
  console.log('  Grafana:      http://aio-01:3000');
  console.log('');
  console.log('  ntfy alerts:  ntfy subscribe fleet-alerts');
  console.log('='.repeat(50));
}

main();
