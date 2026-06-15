#!/usr/bin/env node
/**
 * Fleet Resource Monitor
 *
 * Collects resource usage metrics from fleet nodes via SSH:
 * - CPU usage (per-core and overall)
 * - RAM usage (total, used, available, cached)
 * - Disk I/O (read/write throughput and IOPS)
 * - Network I/O (bytes/packets in/out per interface)
 * - Active processes (top 10 by CPU/RAM)
 *
 * Usage:
 *   node monitoring/fleet-resource-monitor.js [--node server-01] [--interval 5] [--json]
 */

import { execSync } from 'child_process';
import { escapeShell, validateHostname, loadFleetConfig } from '../fleet-utils.js';

/**
 * Parse command-line arguments
 */
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    node: null,        // Specific node, or null for all nodes
    interval: 0,       // 0 = one-shot, >0 = continuous polling
    json: false,       // JSON output format
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--node':
        options.node = args[++i];
        break;
      case '--interval':
        options.interval = parseInt(args[++i], 10);
        break;
      case '--json':
        options.json = true;
        break;
      case '--help':
        console.log(`
Fleet Resource Monitor

Usage:
  node monitoring/fleet-resource-monitor.js [OPTIONS]

Options:
  --node <name>       Monitor specific node only (default: all nodes)
  --interval <sec>    Poll interval in seconds (default: 0 = one-shot)
  --json              Output in JSON format (default: human-readable)
  --help              Show this help

Examples:
  node monitoring/fleet-resource-monitor.js
  node monitoring/fleet-resource-monitor.js --node server-01
  node monitoring/fleet-resource-monitor.js --interval 5 --json
        `);
        process.exit(0);
      default:
        console.error(`Unknown option: ${args[i]}`);
        process.exit(1);
    }
  }

  return options;
}

/**
 * Execute SSH command on remote node and return stdout
 * @param {string} node - Node hostname
 * @param {string} command - Shell command to execute
 * @returns {string} Command stdout
 */
function sshExec(node, command) {
  validateHostname(node);

  // Escape command for SSH double-quote wrapper
  const escapedCmd = command
    .replace(/\\/g, '\\\\')
    .replace(/\$/g, '\\$')
    .replace(/`/g, '\\`')
    .replace(/"/g, '\\"')
    .replace(/!/g, '\\!');

  const sshCmd = `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -- ${escapeShell(node)} "${escapedCmd}"`;

  try {
    return execSync(sshCmd, {
      encoding: 'utf8',
      timeout: 10000,
      stdio: ['pipe', 'pipe', 'pipe']
    }).trim();
  } catch (error) {
    console.error(`SSH command failed on ${node}: ${error.message}`);
    return null;
  }
}

/**
 * Collect CPU metrics from a node
 * @param {string} node - Node hostname
 * @returns {Object} CPU metrics
 */
function collectCPU(node) {
  // Get CPU count and architecture
  const cpuInfo = sshExec(node, "nproc && uname -m");
  if (!cpuInfo) return null;

  const [cores, arch] = cpuInfo.split('\n');

  // Get CPU usage from /proc/stat
  // Format: cpu  user nice system idle iowait irq softirq steal guest guest_nice
  const stat1 = sshExec(node, "cat /proc/stat | grep '^cpu '");
  if (!stat1) return null;

  // Sleep 100ms and get second sample
  const stat2 = sshExec(node, "cat /proc/stat | grep '^cpu ' && sleep 0.1 && cat /proc/stat | grep '^cpu '");
  if (!stat2) return null;

  const lines = stat2.split('\n');
  const [cpu1Line, cpu2Line] = lines;

  const cpu1 = cpu1Line.split(/\s+/).slice(1).map(Number);
  const cpu2 = cpu2Line.split(/\s+/).slice(1).map(Number);

  // Calculate deltas
  const user = cpu2[0] - cpu1[0];
  const nice = cpu2[1] - cpu1[1];
  const system = cpu2[2] - cpu1[2];
  const idle = cpu2[3] - cpu1[3];
  const iowait = cpu2[4] - cpu1[4];
  const irq = cpu2[5] - cpu1[5];
  const softirq = cpu2[6] - cpu1[6];

  const total = user + nice + system + idle + iowait + irq + softirq;
  const usage = total > 0 ? ((total - idle) / total) * 100 : 0;

  // Get per-core load from uptime
  const uptime = sshExec(node, "uptime");
  const loadMatch = uptime ? uptime.match(/load average: ([\d.]+), ([\d.]+), ([\d.]+)/) : null;
  const [, load1, load5, load15] = loadMatch || [null, 0, 0, 0];

  return {
    cores: parseInt(cores, 10),
    arch,
    usage_pct: usage.toFixed(2),
    user_pct: total > 0 ? ((user / total) * 100).toFixed(2) : 0,
    system_pct: total > 0 ? ((system / total) * 100).toFixed(2) : 0,
    iowait_pct: total > 0 ? ((iowait / total) * 100).toFixed(2) : 0,
    load_1m: parseFloat(load1),
    load_5m: parseFloat(load5),
    load_15m: parseFloat(load15),
  };
}

/**
 * Collect RAM metrics from a node
 * @param {string} node - Node hostname
 * @returns {Object} RAM metrics
 */
function collectRAM(node) {
  // Get memory info from /proc/meminfo
  const meminfo = sshExec(node, "cat /proc/meminfo");
  if (!meminfo) return null;

  const parse = (key) => {
    const match = meminfo.match(new RegExp(`^${key}:\\s+(\\d+)`, 'm'));
    return match ? parseInt(match[1], 10) : 0;
  };

  const totalKB = parse('MemTotal');
  const freeKB = parse('MemFree');
  const availableKB = parse('MemAvailable');
  const buffersKB = parse('Buffers');
  const cachedKB = parse('Cached');
  const swapTotalKB = parse('SwapTotal');
  const swapFreeKB = parse('SwapFree');

  const totalGB = totalKB / 1024 / 1024;
  const usedGB = (totalKB - availableKB) / 1024 / 1024;
  const availGB = availableKB / 1024 / 1024;
  const cachedGB = (buffersKB + cachedKB) / 1024 / 1024;
  const swapUsedGB = (swapTotalKB - swapFreeKB) / 1024 / 1024;

  const usagePct = totalGB > 0 ? (usedGB / totalGB) * 100 : 0;
  const ramPressure = usagePct > 90 ? 'critical' : usagePct > 75 ? 'high' : usagePct > 50 ? 'medium' : 'low';

  return {
    total_gb: totalGB.toFixed(2),
    used_gb: usedGB.toFixed(2),
    available_gb: availGB.toFixed(2),
    cached_gb: cachedGB.toFixed(2),
    usage_pct: usagePct.toFixed(2),
    swap_used_gb: swapUsedGB.toFixed(2),
    ram_pressure: ramPressure,
  };
}

/**
 * Collect disk I/O metrics from a node
 * @param {string} node - Node hostname
 * @returns {Object} Disk I/O metrics per device
 */
function collectDiskIO(node) {
  // Get disk I/O stats from /proc/diskstats
  // Format: major minor name reads reads_merged sectors_read time_reading writes writes_merged sectors_written time_writing ...
  const diskstats1 = sshExec(node, "cat /proc/diskstats | grep -E ' (sd[a-z]|nvme[0-9]+n[0-9]+|vd[a-z]) '");
  if (!diskstats1) return null;

  // Sleep 1 second and get second sample
  const diskstats2 = sshExec(node, "sleep 1 && cat /proc/diskstats | grep -E ' (sd[a-z]|nvme[0-9]+n[0-9]+|vd[a-z]) '");
  if (!diskstats2) return null;

  const parseDiskstats = (line) => {
    const parts = line.trim().split(/\s+/);
    return {
      device: parts[2],
      reads: parseInt(parts[3], 10),
      sectors_read: parseInt(parts[5], 10),
      writes: parseInt(parts[7], 10),
      sectors_written: parseInt(parts[9], 10),
    };
  };

  const devices1 = diskstats1.split('\n').map(parseDiskstats);
  const devices2 = diskstats2.split('\n').map(parseDiskstats);

  const ioMetrics = {};
  for (const dev2 of devices2) {
    const dev1 = devices1.find(d => d.device === dev2.device);
    if (!dev1) continue;

    const readKBps = ((dev2.sectors_read - dev1.sectors_read) * 512) / 1024;
    const writeKBps = ((dev2.sectors_written - dev1.sectors_written) * 512) / 1024;
    const readIOPS = dev2.reads - dev1.reads;
    const writeIOPS = dev2.writes - dev1.writes;

    ioMetrics[dev2.device] = {
      read_kbps: readKBps.toFixed(2),
      write_kbps: writeKBps.toFixed(2),
      read_iops: readIOPS,
      write_iops: writeIOPS,
    };
  }

  return ioMetrics;
}

/**
 * Collect network I/O metrics from a node
 * @param {string} node - Node hostname
 * @returns {Object} Network I/O metrics per interface
 */
function collectNetworkIO(node) {
  // Get network stats from /proc/net/dev
  // Format: interface: bytes packets errs drop fifo frame compressed multicast
  const netdev1 = sshExec(node, "cat /proc/net/dev | tail -n +3");
  if (!netdev1) return null;

  // Sleep 1 second and get second sample
  const netdev2 = sshExec(node, "sleep 1 && cat /proc/net/dev | tail -n +3");
  if (!netdev2) return null;

  const parseNetdev = (line) => {
    const parts = line.trim().split(/\s+/);
    return {
      interface: parts[0].replace(':', ''),
      rx_bytes: parseInt(parts[1], 10),
      rx_packets: parseInt(parts[2], 10),
      tx_bytes: parseInt(parts[9], 10),
      tx_packets: parseInt(parts[10], 10),
    };
  };

  const ifaces1 = netdev1.split('\n').map(parseNetdev);
  const ifaces2 = netdev2.split('\n').map(parseNetdev);

  const netMetrics = {};
  for (const iface2 of ifaces2) {
    // Skip loopback
    if (iface2.interface === 'lo') continue;

    const iface1 = ifaces1.find(i => i.interface === iface2.interface);
    if (!iface1) continue;

    const rxKBps = (iface2.rx_bytes - iface1.rx_bytes) / 1024;
    const txKBps = (iface2.tx_bytes - iface1.tx_bytes) / 1024;
    const rxPps = iface2.rx_packets - iface1.rx_packets;
    const txPps = iface2.tx_packets - iface1.tx_packets;

    netMetrics[iface2.interface] = {
      rx_kbps: rxKBps.toFixed(2),
      tx_kbps: txKBps.toFixed(2),
      rx_pps: rxPps,
      tx_pps: txPps,
    };
  }

  return netMetrics;
}

/**
 * Collect active processes from a node
 * @param {string} node - Node hostname
 * @returns {Object} Top processes by CPU and RAM
 */
function collectProcesses(node) {
  // Top 10 by CPU
  const topCPU = sshExec(node, "ps aux --sort=-%cpu | head -n 11 | tail -n 10 | awk '{print $2,$3,$4,$11}'");
  if (!topCPU) return null;

  // Top 10 by RAM
  const topRAM = sshExec(node, "ps aux --sort=-%mem | head -n 11 | tail -n 10 | awk '{print $2,$3,$4,$11}'");
  if (!topRAM) return null;

  const parseProcs = (output) => {
    return output.split('\n').map(line => {
      const parts = line.trim().split(/\s+/);
      return {
        pid: parseInt(parts[0], 10),
        cpu_pct: parseFloat(parts[1]),
        mem_pct: parseFloat(parts[2]),
        command: parts.slice(3).join(' '),
      };
    });
  };

  return {
    top_cpu: parseProcs(topCPU),
    top_mem: parseProcs(topRAM),
  };
}

/**
 * Collect all metrics from a node
 * @param {string} node - Node hostname
 * @returns {Object} All metrics
 */
function collectNodeMetrics(node) {
  console.error(`[${node}] Collecting metrics...`);

  const metrics = {
    node,
    timestamp: new Date().toISOString(),
    cpu: collectCPU(node),
    ram: collectRAM(node),
    disk_io: collectDiskIO(node),
    network_io: collectNetworkIO(node),
    processes: collectProcesses(node),
  };

  return metrics;
}

/**
 * Format metrics for human-readable output
 * @param {Object} metrics - Node metrics
 * @returns {string} Formatted output
 */
function formatMetrics(metrics) {
  const lines = [];
  lines.push(`\n${'='.repeat(60)}`);
  lines.push(`Node: ${metrics.node}`);
  lines.push(`Time: ${metrics.timestamp}`);
  lines.push(`${'='.repeat(60)}`);

  if (metrics.cpu) {
    lines.push('\nCPU:');
    lines.push(`  Cores: ${metrics.cpu.cores} (${metrics.cpu.arch})`);
    lines.push(`  Usage: ${metrics.cpu.usage_pct}%`);
    lines.push(`  User: ${metrics.cpu.user_pct}%  System: ${metrics.cpu.system_pct}%  IOWait: ${metrics.cpu.iowait_pct}%`);
    lines.push(`  Load: ${metrics.cpu.load_1m} (1m)  ${metrics.cpu.load_5m} (5m)  ${metrics.cpu.load_15m} (15m)`);
  }

  if (metrics.ram) {
    lines.push('\nRAM:');
    lines.push(`  Total: ${metrics.ram.total_gb} GB`);
    lines.push(`  Used: ${metrics.ram.used_gb} GB (${metrics.ram.usage_pct}%)`);
    lines.push(`  Available: ${metrics.ram.available_gb} GB`);
    lines.push(`  Cached: ${metrics.ram.cached_gb} GB`);
    lines.push(`  Swap Used: ${metrics.ram.swap_used_gb} GB`);
    lines.push(`  Pressure: ${metrics.ram.ram_pressure}`);
  }

  if (metrics.disk_io) {
    lines.push('\nDisk I/O:');
    for (const [device, io] of Object.entries(metrics.disk_io)) {
      lines.push(`  ${device}:`);
      lines.push(`    Read:  ${io.read_kbps} KB/s (${io.read_iops} IOPS)`);
      lines.push(`    Write: ${io.write_kbps} KB/s (${io.write_iops} IOPS)`);
    }
  }

  if (metrics.network_io) {
    lines.push('\nNetwork I/O:');
    for (const [iface, io] of Object.entries(metrics.network_io)) {
      lines.push(`  ${iface}:`);
      lines.push(`    RX: ${io.rx_kbps} KB/s (${io.rx_pps} pps)`);
      lines.push(`    TX: ${io.tx_kbps} KB/s (${io.tx_pps} pps)`);
    }
  }

  if (metrics.processes) {
    lines.push('\nTop Processes (CPU):');
    for (const proc of metrics.processes.top_cpu.slice(0, 5)) {
      lines.push(`  ${proc.pid}  CPU:${proc.cpu_pct.toFixed(1)}%  RAM:${proc.mem_pct.toFixed(1)}%  ${proc.command}`);
    }

    lines.push('\nTop Processes (RAM):');
    for (const proc of metrics.processes.top_mem.slice(0, 5)) {
      lines.push(`  ${proc.pid}  CPU:${proc.cpu_pct.toFixed(1)}%  RAM:${proc.mem_pct.toFixed(1)}%  ${proc.command}`);
    }
  }

  return lines.join('\n');
}

/**
 * Main monitoring loop
 */
async function main() {
  const options = parseArgs();

  // Determine nodes to monitor
  let nodes = [];
  if (options.node) {
    nodes = [options.node];
  } else {
    try {
      const config = loadFleetConfig();
      nodes = Object.keys(config.serverCapabilities);
    } catch (error) {
      console.error('Failed to load fleet config:', error.message);
      console.error('Specify --node <hostname> to monitor a specific node');
      process.exit(1);
    }
  }

  // Monitoring loop
  do {
    const allMetrics = [];

    for (const node of nodes) {
      try {
        const metrics = collectNodeMetrics(node);
        allMetrics.push(metrics);

        if (!options.json) {
          console.log(formatMetrics(metrics));
        }
      } catch (error) {
        console.error(`Failed to collect metrics from ${node}:`, error.message);
      }
    }

    if (options.json) {
      console.log(JSON.stringify(allMetrics, null, 2));
    }

    if (options.interval > 0) {
      await new Promise(resolve => setTimeout(resolve, options.interval * 1000));
    }
  } while (options.interval > 0);
}

main().catch(error => {
  console.error('Fatal error:', error.message);
  process.exit(1);
});
