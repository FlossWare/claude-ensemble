#!/usr/bin/env node

/**
 * Real-Time Workflow Monitor
 *
 * Monitors active and recent workflows by reading workflow transcript
 * directories under ~/.claude/projects/. Shows which worker is executing
 * which agent in real-time with auto-refresh.
 *
 * Displays:
 * - Workflow name and run ID
 * - Agent label (e.g., "search:Fleet compute benchmarks")
 * - Worker hostname (from execution_host, SSH logs, or transcript mentions)
 * - Status (running / completed / error)
 * - Duration (elapsed for running, total for completed)
 *
 * Usage:
 *   node shared/workflow-monitor.mjs                     # All active workflows
 *   node shared/workflow-monitor.mjs <workflow-id>        # Specific workflow
 *   node shared/workflow-monitor.mjs --all                # Include completed
 *   node shared/workflow-monitor.mjs --once               # Single snapshot, no refresh
 *   node shared/workflow-monitor.mjs --json               # JSON output (single snapshot)
 *
 * Created: 2026-06-29
 */

import fs from 'fs';
import path from 'path';
import os from 'os';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const REFRESH_INTERVAL_MS = 2000;
const CLAUDE_PROJECTS_DIR = path.join(os.homedir(), '.claude', 'projects');

// Known fleet hostnames for extraction from transcript content
const KNOWN_HOSTS = [
  'server-01', 'server-02', 'server-03',
  'laptop-01',
  'pi-01', 'pi-02',
  'desktop-ap', 'server-ap',
  'aio-01',
];

const KNOWN_HOSTS_PATTERN = new RegExp(
  KNOWN_HOSTS.map(h => h.replace('-', '\\-')).join('|'),
  'g'
);

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
const filterWorkflowId = args.find(a => !a.startsWith('--'));
const showAll = args.includes('--all');
const onceMode = args.includes('--once');
const jsonMode = args.includes('--json');

// ---------------------------------------------------------------------------
// Data collection: find all workflow JSON files across all project sessions
// ---------------------------------------------------------------------------

/**
 * Recursively discover workflow JSON files under ~/.claude/projects.
 *
 * Workflow files are stored in two possible locations per session:
 *   <project>/<session-id>/workflows/wf_*.json
 *   <project>/<session-id>/subagents/workflows/wf_*.json
 *
 * Returns an array of { filePath, subagentDir } objects.
 */
function discoverWorkflowFiles() {
  const results = [];

  if (!fs.existsSync(CLAUDE_PROJECTS_DIR)) {
    return results;
  }

  // Walk project directories (not full recursive -- structured paths)
  let projectDirs;
  try {
    projectDirs = fs.readdirSync(CLAUDE_PROJECTS_DIR);
  } catch {
    return results;
  }

  for (const projDir of projectDirs) {
    const projPath = path.join(CLAUDE_PROJECTS_DIR, projDir);
    let stat;
    try { stat = fs.statSync(projPath); } catch { continue; }
    if (!stat.isDirectory()) continue;

    // Each project has session UUID directories
    let sessionDirs;
    try { sessionDirs = fs.readdirSync(projPath); } catch { continue; }

    for (const sessionDir of sessionDirs) {
      const sessionPath = path.join(projPath, sessionDir);
      let sessionStat;
      try { sessionStat = fs.statSync(sessionPath); } catch { continue; }
      if (!sessionStat.isDirectory()) continue;

      // Check both workflow locations
      const workflowDirs = [
        path.join(sessionPath, 'workflows'),
        path.join(sessionPath, 'subagents', 'workflows'),
      ];

      for (const wfDir of workflowDirs) {
        if (!fs.existsSync(wfDir)) continue;

        let wfFiles;
        try { wfFiles = fs.readdirSync(wfDir); } catch { continue; }

        for (const wfFile of wfFiles) {
          if (!wfFile.startsWith('wf_') || !wfFile.endsWith('.json')) continue;

          const filePath = path.join(wfDir, wfFile);

          // The subagent transcript directory may be at:
          // <session>/subagents/workflows/<runId>/
          const runId = wfFile.replace('.json', '');
          const subagentDir = path.join(sessionPath, 'subagents', 'workflows', runId);

          results.push({ filePath, subagentDir, runId });
        }
      }
    }
  }

  return results;
}

/**
 * Parse a workflow JSON file and extract monitoring data.
 *
 * @param {Object} entry - { filePath, subagentDir, runId }
 * @returns {Object|null} Parsed workflow data or null if invalid/filtered
 */
function parseWorkflow(entry) {
  const { filePath, subagentDir, runId } = entry;

  let data;
  try {
    const raw = fs.readFileSync(filePath, 'utf8');
    data = JSON.parse(raw);
  } catch {
    return null;
  }

  const status = data.status || 'unknown';
  const workflowName = data.workflowName || extractWorkflowNameFromScript(data.script) || 'unknown';
  const durationMs = data.durationMs || null;
  const startTime = data.startTime || (data.timestamp ? new Date(data.timestamp).getTime() : null);
  const agentCount = data.agentCount || 0;
  const totalTokens = data.totalTokens || 0;
  const defaultModel = data.defaultModel || null;

  // Extract agent details from workflowProgress
  const agents = [];
  const progressEntries = data.workflowProgress || [];

  for (const entry of progressEntries) {
    if (entry.type !== 'workflow_agent') continue;

    const agentState = mapState(entry.state);
    const agentDurationMs = entry.durationMs || null;
    const elapsed = entry.startedAt && !agentDurationMs
      ? Date.now() - entry.startedAt
      : agentDurationMs;

    // Try to extract hostname from agent transcripts
    const hostname = extractHostname(subagentDir, entry.agentId, entry.label);

    agents.push({
      index: entry.index,
      label: entry.label || `agent-${entry.index}`,
      agentId: entry.agentId,
      model: entry.model || defaultModel || 'unknown',
      state: agentState,
      phaseTitle: entry.phaseTitle || '',
      startedAt: entry.startedAt || null,
      durationMs: elapsed,
      tokens: entry.tokens || 0,
      toolCalls: entry.toolCalls || 0,
      hostname: hostname,
    });
  }

  // Filter by workflow ID if specified
  if (filterWorkflowId && runId !== filterWorkflowId) {
    return null;
  }

  // Filter out completed/failed workflows unless --all or specific ID requested
  if (!showAll && !filterWorkflowId) {
    const hasRunningAgents = agents.some(a => a.state === 'running' || a.state === 'pending');
    if (hasRunningAgents) {
      // Always show workflows with running/pending agents
    } else if (status === 'completed' || status === 'failed') {
      // Show completed workflows only if they finished within the last 5 minutes
      const endTime = startTime && durationMs ? startTime + durationMs : null;
      if (!endTime || Date.now() - endTime > 5 * 60 * 1000) {
        return null;
      }
    } else if (status === 'running') {
      // Running status in JSON but no running agents -- could be stale, show it
    } else {
      // Unknown status, skip unless recently started
      if (!startTime || Date.now() - startTime > 10 * 60 * 1000) {
        return null;
      }
    }
  }

  return {
    runId,
    workflowName,
    status,
    startTime,
    durationMs: durationMs || (startTime ? Date.now() - startTime : null),
    agentCount,
    totalTokens,
    defaultModel,
    agents,
    filePath,
  };
}

/**
 * Extract workflow name from the script field (fallback).
 */
function extractWorkflowNameFromScript(script) {
  if (!script || typeof script !== 'string') return null;
  const match = script.match(/name:\s*['"]([^'"]+)['"]/);
  return match ? match[1] : null;
}

/**
 * Map internal state values to display-friendly status strings.
 */
function mapState(state) {
  if (!state) return 'pending';
  switch (state) {
    case 'done': return 'completed';
    case 'running': return 'running';
    case 'queued': return 'pending';
    case 'error': case 'failed': return 'error';
    default: return state;
  }
}

/**
 * Extract worker hostname from agent transcript files.
 *
 * Checks multiple sources:
 * 1. Agent JSONL transcript for execution_host or SSH command patterns
 * 2. Agent JSONL transcript for fleet hostname mentions in tool outputs
 * 3. The agent label itself (may contain host info for fleet workflows)
 *
 * @param {string} subagentDir - Directory containing agent transcripts
 * @param {string} agentId - Agent identifier
 * @param {string} label - Agent label from workflowProgress
 * @returns {string|null} Hostname or null
 */
function extractHostname(subagentDir, agentId, label) {
  // Check label for host hints
  if (label) {
    const labelHosts = label.match(KNOWN_HOSTS_PATTERN);
    if (labelHosts && labelHosts.length > 0) {
      return labelHosts[0];
    }
  }

  // Check agent JSONL transcript for host mentions
  if (!subagentDir || !agentId || !fs.existsSync(subagentDir)) {
    return null;
  }

  const jsonlPath = path.join(subagentDir, `${agentId}.jsonl`);
  if (!fs.existsSync(jsonlPath)) {
    return null;
  }

  try {
    // Read only the last 8KB to keep it fast (host info usually near the end)
    const stat = fs.statSync(jsonlPath);
    const readSize = Math.min(stat.size, 8192);
    const fd = fs.openSync(jsonlPath, 'r');
    const buffer = Buffer.alloc(readSize);
    fs.readSync(fd, buffer, 0, readSize, Math.max(0, stat.size - readSize));
    fs.closeSync(fd);
    const tail = buffer.toString('utf8');

    // Look for execution_host in JSON content
    const execHostMatch = tail.match(/"execution_host"\s*:\s*"([^"]+)"/);
    if (execHostMatch) {
      return execHostMatch[1];
    }

    // Look for SSH command patterns: ssh claude@<host>
    const sshMatch = tail.match(/ssh\s+(?:\S+@)?((?:server|laptop|pi|desktop|aio)-\S+)/);
    if (sshMatch) {
      return sshMatch[1];
    }

    // Look for any fleet hostname mentions in tool outputs
    const hostMatches = tail.match(KNOWN_HOSTS_PATTERN);
    if (hostMatches && hostMatches.length > 0) {
      // Return the most frequently mentioned host
      const counts = {};
      for (const h of hostMatches) {
        counts[h] = (counts[h] || 0) + 1;
      }
      return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
    }
  } catch {
    // Transcript read failed, not critical
  }

  return null;
}

// ---------------------------------------------------------------------------
// Display formatting
// ---------------------------------------------------------------------------

/**
 * Format milliseconds into human-readable duration string.
 */
function formatDuration(ms) {
  if (!ms || ms < 0) return '--';
  if (ms < 1000) return `${ms}ms`;

  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainSec = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainSec}s`;

  const hours = Math.floor(minutes / 60);
  const remainMin = minutes % 60;
  return `${hours}h ${remainMin}m`;
}

/**
 * Format a timestamp as HH:MM:SS.
 */
function formatTime(timestamp) {
  if (!timestamp) return '--:--:--';
  const d = new Date(timestamp);
  return d.toLocaleTimeString('en-US', { hour12: false });
}

/**
 * Truncate a string to maxLen characters, appending "..." if truncated.
 */
function truncate(str, maxLen) {
  if (!str) return '';
  if (str.length <= maxLen) return str;
  return str.substring(0, maxLen - 3) + '...';
}

/**
 * Pad or truncate a string to exactly `len` characters.
 */
function pad(str, len) {
  if (!str) str = '';
  if (str.length > len) return str.substring(0, len - 1) + '.';
  return str.padEnd(len);
}

/**
 * Status indicator character (no emojis per instructions).
 */
function statusIndicator(status) {
  switch (status) {
    case 'running':   return '[RUN]';
    case 'completed': return '[OK] ';
    case 'pending':   return '[...]';
    case 'error':     return '[ERR]';
    default:          return '[???]';
  }
}

/**
 * Render a single workflow and its agents to the console.
 */
function renderWorkflow(wf) {
  const lines = [];

  // Workflow header
  const wfStatus = wf.status === 'completed' ? 'COMPLETED' : wf.status.toUpperCase();
  lines.push(`${'='.repeat(90)}`);
  lines.push(
    `WORKFLOW: ${wf.workflowName}  |  ${wf.runId}  |  ${wfStatus}  |  ${formatDuration(wf.durationMs)}`
  );
  lines.push(
    `  Started: ${formatTime(wf.startTime)}  |  Agents: ${wf.agentCount}  |  ` +
    `Tokens: ${(wf.totalTokens || 0).toLocaleString()}  |  Model: ${wf.defaultModel || 'default'}`
  );
  lines.push(`${'-'.repeat(90)}`);

  if (wf.agents.length === 0) {
    lines.push('  (no agent progress data available)');
  } else {
    // Table header
    lines.push(
      `  ${pad('Status', 7)} ${pad('Phase', 12)} ${pad('Agent Label', 40)} ` +
      `${pad('Host', 12)} ${pad('Duration', 10)} ${pad('Model', 20)}`
    );
    lines.push(`  ${'-'.repeat(85)}`);

    // Group agents by phase
    let currentPhase = '';
    for (const agent of wf.agents) {
      if (agent.phaseTitle !== currentPhase) {
        currentPhase = agent.phaseTitle;
      }

      const statusStr = statusIndicator(agent.state);
      const phaseStr = pad(truncate(agent.phaseTitle, 12), 12);
      const labelStr = pad(truncate(agent.label, 40), 40);
      const hostStr = pad(agent.hostname || '(local)', 12);
      const durStr = pad(formatDuration(agent.durationMs), 10);
      const modelStr = truncate(agent.model, 20);

      lines.push(`  ${statusStr}  ${phaseStr} ${labelStr} ${hostStr} ${durStr} ${modelStr}`);
    }
  }

  lines.push('');
  return lines.join('\n');
}

/**
 * Render a fleet utilization summary across all displayed workflows.
 */
function renderFleetSummary(workflows) {
  const lines = [];
  const hostStats = {};
  let totalRunning = 0;
  let totalCompleted = 0;
  let totalPending = 0;

  for (const wf of workflows) {
    for (const agent of wf.agents) {
      const host = agent.hostname || '(local)';
      if (!hostStats[host]) {
        hostStats[host] = { running: 0, completed: 0, total: 0 };
      }
      hostStats[host].total++;

      if (agent.state === 'running') {
        hostStats[host].running++;
        totalRunning++;
      } else if (agent.state === 'completed') {
        hostStats[host].completed++;
        totalCompleted++;
      } else {
        totalPending++;
      }
    }
  }

  lines.push('='.repeat(90));
  lines.push('FLEET SUMMARY');
  lines.push('-'.repeat(90));
  lines.push(
    `  Active Workflows: ${workflows.length}  |  ` +
    `Running Agents: ${totalRunning}  |  ` +
    `Completed: ${totalCompleted}  |  ` +
    `Pending: ${totalPending}`
  );

  if (Object.keys(hostStats).length > 0) {
    lines.push('');
    lines.push('  Host Distribution:');
    const sortedHosts = Object.entries(hostStats).sort((a, b) => b[1].total - a[1].total);
    for (const [host, stats] of sortedHosts) {
      const bar = '#'.repeat(Math.min(stats.total, 40));
      lines.push(
        `    ${pad(host, 14)} ${pad(String(stats.total) + ' total', 10)} ` +
        `${stats.running > 0 ? stats.running + ' running' : ''}  ${bar}`
      );
    }
  }

  lines.push('='.repeat(90));
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// JSON output mode
// ---------------------------------------------------------------------------

function renderJson(workflows) {
  const output = workflows.map(wf => ({
    runId: wf.runId,
    workflowName: wf.workflowName,
    status: wf.status,
    startTime: wf.startTime ? new Date(wf.startTime).toISOString() : null,
    durationMs: wf.durationMs,
    agentCount: wf.agentCount,
    totalTokens: wf.totalTokens,
    defaultModel: wf.defaultModel,
    agents: wf.agents.map(a => ({
      index: a.index,
      label: a.label,
      agentId: a.agentId,
      model: a.model,
      state: a.state,
      phaseTitle: a.phaseTitle,
      hostname: a.hostname,
      durationMs: a.durationMs,
      tokens: a.tokens,
      toolCalls: a.toolCalls,
    })),
  }));

  return JSON.stringify(output, null, 2);
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------

function collectAndRender() {
  const entries = discoverWorkflowFiles();
  const workflows = entries
    .map(parseWorkflow)
    .filter(Boolean)
    .sort((a, b) => (b.startTime || 0) - (a.startTime || 0));

  if (jsonMode) {
    process.stdout.write(renderJson(workflows) + '\n');
    return workflows;
  }

  // Clear screen for refresh (only in continuous mode)
  if (!onceMode) {
    process.stdout.write('\x1b[2J\x1b[H');
  }

  // Header
  const now = new Date().toLocaleTimeString('en-US', { hour12: false });
  process.stdout.write(
    `WORKFLOW MONITOR  |  ${now}  |  ` +
    `Refresh: ${REFRESH_INTERVAL_MS / 1000}s  |  ` +
    `Scanning: ${entries.length} workflow files\n\n`
  );

  if (workflows.length === 0) {
    if (filterWorkflowId) {
      process.stdout.write(`No workflow found with ID: ${filterWorkflowId}\n`);
      process.stdout.write(`\nTip: Run without arguments to see all active workflows.\n`);
    } else {
      process.stdout.write('No active workflows found.\n');
      process.stdout.write(`\nTip: Use --all to include completed workflows.\n`);
    }
  } else {
    for (const wf of workflows) {
      process.stdout.write(renderWorkflow(wf) + '\n');
    }
    process.stdout.write(renderFleetSummary(workflows) + '\n');
  }

  if (!onceMode && !jsonMode) {
    process.stdout.write(`\nPress Ctrl+C to exit. Refreshing every ${REFRESH_INTERVAL_MS / 1000}s...\n`);
  }

  return workflows;
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

if (onceMode || jsonMode) {
  collectAndRender();
} else {
  // Initial render
  collectAndRender();

  // Refresh loop
  const interval = setInterval(() => {
    try {
      collectAndRender();
    } catch (err) {
      process.stderr.write(`Monitor error: ${err.message}\n`);
    }
  }, REFRESH_INTERVAL_MS);

  // Clean exit on Ctrl+C
  process.on('SIGINT', () => {
    clearInterval(interval);
    process.stdout.write('\nMonitor stopped.\n');
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    clearInterval(interval);
    process.exit(0);
  });
}
