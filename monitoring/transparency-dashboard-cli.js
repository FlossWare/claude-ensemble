#!/usr/bin/env node

/**
 * CLI Real-Time Transparency Dashboard
 *
 * Terminal-based alternative to Grafana for monitoring autonomous learning system
 * Provides live updates on system activity, decisions, fleet distribution, and learning progress
 *
 * Usage:
 *   node transparency-dashboard-cli.js [options]
 *
 * Options:
 *   --refresh <seconds>    Refresh interval (default: 5)
 *   --view <name>          Initial view: overview|fleet|learning|decisions|audit (default: overview)
 *   --compact              Compact mode (less vertical space)
 *   --no-color             Disable colors
 *   --export <file>        Export data to JSON file
 */

import blessed from 'blessed';
import contrib from 'blessed-contrib';
import {
  getRecentExecutions,
  getModelTaskStats,
  getDistinctModelTasks,
  getAllTuning,
  getAllCombinations,
  getExecutionCount,
  getDb,
} from '../shared/learning-logger.js';
import { calculateLIS, getComprehensiveMetrics, getAllMetricsLeaderboard } from '../shared/learning-metrics.js';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  refreshInterval: parseInt(process.env.DASHBOARD_REFRESH || '5') * 1000,
  maxHistoryPoints: 50,
  colorScheme: {
    success: 'green',
    failure: 'red',
    warning: 'yellow',
    info: 'blue',
    highlight: 'cyan',
  },
};

// ============================================================================
// BLESSED SCREEN SETUP
// ============================================================================

const screen = blessed.screen({
  smartCSR: true,
  title: 'Autonomous Learning System - Transparency Dashboard',
  dockBorders: true,
  fullUnicode: true,
  autoPadding: true,
});

const grid = new contrib.grid({ rows: 12, cols: 12, screen: screen });

// ============================================================================
// UI COMPONENTS
// ============================================================================

// Top status bar
const statusBar = grid.set(0, 0, 1, 12, blessed.text, {
  content: '🔴 LIVE: Loading...',
  tags: true,
  style: {
    fg: 'white',
    bg: 'blue',
    bold: true,
  },
});

// Fleet activity map (top-left)
const fleetTable = grid.set(1, 0, 4, 6, contrib.table, {
  keys: true,
  fg: 'white',
  selectedFg: 'white',
  selectedBg: 'blue',
  interactive: false,
  label: '🗺️  Fleet Activity Map',
  width: '50%',
  height: '33%',
  border: { type: 'line', fg: 'cyan' },
  columnSpacing: 2,
  columnWidth: [20, 12, 12, 10, 8],
});

// Active workflows (top-right)
const workflowTable = grid.set(1, 6, 4, 6, contrib.table, {
  keys: true,
  fg: 'white',
  selectedFg: 'white',
  selectedBg: 'blue',
  interactive: false,
  label: '⚙️  Active Workflows',
  border: { type: 'line', fg: 'cyan' },
  columnSpacing: 2,
  columnWidth: [18, 10, 10, 10, 8],
});

// Learning Intelligence Score (middle-left)
const lisGauge = grid.set(5, 0, 2, 3, contrib.gauge, {
  label: '🧠 Learning Intelligence Score',
  stroke: 'green',
  fill: 'white',
  border: { type: 'line', fg: 'cyan' },
});

// Model performance comparison (middle-center)
const modelBarChart = grid.set(5, 3, 2, 5, contrib.bar, {
  label: '🎯 Model Performance (Quality)',
  barWidth: 4,
  barSpacing: 6,
  xOffset: 0,
  maxHeight: 9,
  border: { type: 'line', fg: 'cyan' },
});

// Cost tracking (middle-right)
const costDonut = grid.set(5, 8, 2, 4, contrib.donut, {
  label: '💰 Cost Distribution',
  radius: 8,
  arcWidth: 3,
  remainColor: 'black',
  border: { type: 'line', fg: 'cyan' },
});

// Quality trend over time (bottom-left)
const qualityLine = grid.set(7, 0, 3, 6, contrib.line, {
  style: {
    line: 'yellow',
    text: 'green',
    baseline: 'black',
  },
  xLabelPadding: 3,
  xPadding: 5,
  showLegend: true,
  wholeNumbersOnly: false,
  label: '📈 Quality Trend',
  border: { type: 'line', fg: 'cyan' },
});

// Recent decisions log (bottom-right)
const decisionsLog = grid.set(7, 6, 3, 6, contrib.log, {
  fg: 'white',
  selectedFg: 'green',
  label: '🧠 Autonomous Decisions',
  border: { type: 'line', fg: 'cyan' },
  scrollable: true,
  alwaysScroll: true,
  scrollbar: {
    ch: ' ',
    track: {
      bg: 'cyan',
    },
    style: {
      inverse: true,
    },
  },
});

// Issue tracker (bottom section)
const issueTable = grid.set(10, 0, 2, 12, contrib.table, {
  keys: true,
  fg: 'white',
  selectedFg: 'white',
  selectedBg: 'red',
  interactive: false,
  label: '🔍 Issue Tracker (Failures & Errors)',
  border: { type: 'line', fg: 'red' },
  columnSpacing: 2,
  columnWidth: [20, 15, 15, 30],
});

// ============================================================================
// DATA FETCHING
// ============================================================================

let qualityHistory = [];
let executionHistory = [];

async function fetchDashboardData() {
  const db = getDb();
  if (!db) {
    return null;
  }

  const data = {
    timestamp: new Date().toISOString(),
    recentExecutions: getRecentExecutions(100),
    executionCount: getExecutionCount(),
    distinctModelTasks: getDistinctModelTasks(),
    allTuning: getAllTuning(),
    allCombinations: getAllCombinations(),
    leaderboard: getAllMetricsLeaderboard({ minSamples: 5 }),
  };

  // Calculate aggregate LIS score
  let totalLIS = 0;
  let lisCount = 0;
  for (const { model, task_type } of data.distinctModelTasks) {
    const lis = calculateLIS(model, task_type, { minSamples: 5 });
    if (lis) {
      totalLIS += lis.score;
      lisCount++;
    }
  }
  data.aggregateLIS = lisCount > 0 ? totalLIS / lisCount : 0;

  // Get active workflows (last 5 minutes)
  const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
  data.activeExecutions = data.recentExecutions.filter(
    (e) => e.timestamp > fiveMinutesAgo
  );

  // Get failures/errors (last hour)
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
  data.recentIssues = data.recentExecutions.filter(
    (e) => (e.outcome === 'failure' || e.error) && e.timestamp > oneHourAgo
  );

  // Track quality history for trending
  const avgQuality =
    data.recentExecutions
      .filter((e) => e.quality_score !== null)
      .reduce((sum, e) => sum + e.quality_score, 0) /
      data.recentExecutions.filter((e) => e.quality_score !== null).length || 0;

  qualityHistory.push(avgQuality);
  if (qualityHistory.length > CONFIG.maxHistoryPoints) {
    qualityHistory.shift();
  }

  executionHistory.push(data.activeExecutions.length);
  if (executionHistory.length > CONFIG.maxHistoryPoints) {
    executionHistory.shift();
  }

  return data;
}

// ============================================================================
// UI RENDERING
// ============================================================================

function updateStatusBar(data) {
  if (!data) {
    statusBar.setContent('{red-fg}❌ OFFLINE: Database unavailable{/red-fg}');
    return;
  }

  const activeCount = data.activeExecutions.length;
  const activeWorkflows = new Set(data.activeExecutions.map((e) => e.workflow)).size;
  const activeModels = new Set(data.activeExecutions.map((e) => e.model)).size;
  const errorCount = data.recentIssues.length;

  const status = activeCount > 0 ? '{green-fg}🟢 LIVE{/green-fg}' : '{yellow-fg}🟡 IDLE{/yellow-fg}';

  statusBar.setContent(
    `${status} | ` +
    `Active: ${activeCount} executions | ` +
    `${activeWorkflows} workflows | ` +
    `${activeModels} AI models | ` +
    `Errors: ${errorCount} | ` +
    `Total: ${data.executionCount} | ` +
    `LIS: ${data.aggregateLIS.toFixed(1)}/100 | ` +
    `Updated: ${new Date().toLocaleTimeString()}`
  );
}

function updateFleetTable(data) {
  if (!data || data.activeExecutions.length === 0) {
    fleetTable.setData({
      headers: ['Time', 'Model', 'Workflow', 'Task', 'Status'],
      data: [['No active executions', '', '', '', '']],
    });
    return;
  }

  const rows = data.activeExecutions.slice(0, 15).map((e) => {
    const time = new Date(e.timestamp).toLocaleTimeString();
    const status = e.outcome === 'success' ? '✅' : e.outcome === 'failure' ? '❌' : '⏳';
    return [
      time,
      e.model || 'unknown',
      e.workflow || 'N/A',
      e.task_type || 'N/A',
      status,
    ];
  });

  fleetTable.setData({
    headers: ['Time', 'Model', 'Workflow', 'Task', 'Status'],
    data: rows,
  });
}

function updateWorkflowTable(data) {
  if (!data) return;

  // Group by workflow
  const workflowGroups = {};
  for (const exec of data.activeExecutions) {
    const wf = exec.workflow || 'unknown';
    if (!workflowGroups[wf]) {
      workflowGroups[wf] = {
        count: 0,
        models: new Set(),
        avgDuration: 0,
        success: 0,
        failure: 0,
      };
    }
    workflowGroups[wf].count++;
    workflowGroups[wf].models.add(exec.model);
    workflowGroups[wf].avgDuration += exec.duration_ms || 0;
    if (exec.outcome === 'success') workflowGroups[wf].success++;
    if (exec.outcome === 'failure') workflowGroups[wf].failure++;
  }

  const rows = Object.entries(workflowGroups)
    .slice(0, 15)
    .map(([wf, stats]) => {
      const avgDur = stats.count > 0 ? (stats.avgDuration / stats.count).toFixed(0) : 0;
      return [
        wf,
        stats.count.toString(),
        stats.models.size.toString(),
        `${avgDur}ms`,
        `${stats.success}/${stats.failure}`,
      ];
    });

  workflowTable.setData({
    headers: ['Workflow', 'Count', 'Models', 'Avg Time', 'OK/Fail'],
    data: rows.length > 0 ? rows : [['No active workflows', '', '', '', '']],
  });
}

function updateLISGauge(data) {
  if (!data) return;
  lisGauge.setPercent(Math.round(data.aggregateLIS));
}

function updateModelBarChart(data) {
  if (!data || data.allTuning.length === 0) return;

  const topModels = data.allTuning
    .filter((t) => t.sample_count >= 5)
    .sort((a, b) => b.avg_quality - a.avg_quality)
    .slice(0, 8);

  const titles = topModels.map((t) => `${t.model}:${t.task_type}`);
  const values = topModels.map((t) => Math.round(t.avg_quality * 100));

  modelBarChart.setData({
    titles: titles,
    data: values,
  });
}

function updateCostDonut(data) {
  if (!data || data.recentExecutions.length === 0) return;

  const costByModel = {};
  for (const exec of data.recentExecutions) {
    const model = exec.model || 'unknown';
    costByModel[model] = (costByModel[model] || 0) + (exec.cost_usd || 0);
  }

  const donutData = Object.entries(costByModel)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([model, cost]) => ({
      label: model,
      percent: cost,
    }));

  costDonut.setData(donutData);
}

function updateQualityLine(data) {
  if (!data || qualityHistory.length === 0) return;

  const x = Array.from({ length: qualityHistory.length }, (_, i) => i.toString());
  const y = qualityHistory;

  qualityLine.setData([
    {
      title: 'Quality Score',
      x: x,
      y: y,
      style: {
        line: 'yellow',
      },
    },
  ]);
}

function updateDecisionsLog(data) {
  if (!data) return;

  // Show recent executions with decision rationale
  const decisionsWithNotes = data.recentExecutions
    .filter((e) => e.outcome_notes)
    .slice(0, 20);

  for (const decision of decisionsWithNotes) {
    const time = new Date(decision.timestamp).toLocaleTimeString();
    const color = decision.outcome === 'success' ? 'green' : 'red';
    decisionsLog.log(
      `[${time}] {${color}-fg}${decision.model}{/${color}-fg} - ${decision.workflow || 'N/A'}: ${decision.outcome_notes}`
    );
  }
}

function updateIssueTable(data) {
  if (!data || data.recentIssues.length === 0) {
    issueTable.setData({
      headers: ['Time', 'Workflow', 'Model', 'Error'],
      data: [['No recent issues', '', '', '']],
    });
    return;
  }

  const rows = data.recentIssues.slice(0, 10).map((e) => {
    const time = new Date(e.timestamp).toLocaleTimeString();
    return [
      time,
      e.workflow || 'N/A',
      e.model || 'unknown',
      (e.error || e.outcome_notes || 'Unknown error').substring(0, 40),
    ];
  });

  issueTable.setData({
    headers: ['Time', 'Workflow', 'Model', 'Error'],
    data: rows,
  });
}

async function updateDashboard() {
  const data = await fetchDashboardData();

  updateStatusBar(data);
  updateFleetTable(data);
  updateWorkflowTable(data);
  updateLISGauge(data);
  updateModelBarChart(data);
  updateCostDonut(data);
  updateQualityLine(data);
  updateDecisionsLog(data);
  updateIssueTable(data);

  screen.render();
}

// ============================================================================
// KEYBOARD SHORTCUTS
// ============================================================================

screen.key(['escape', 'q', 'C-c'], () => {
  return process.exit(0);
});

screen.key(['r'], async () => {
  decisionsLog.log('{blue-fg}🔄 Refreshing dashboard...{/blue-fg}');
  await updateDashboard();
});

screen.key(['h', '?'], () => {
  decisionsLog.log('{cyan-fg}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{/cyan-fg}');
  decisionsLog.log('{cyan-fg}KEYBOARD SHORTCUTS:{/cyan-fg}');
  decisionsLog.log('  {yellow-fg}r{/yellow-fg}      - Refresh dashboard');
  decisionsLog.log('  {yellow-fg}h / ?{/yellow-fg}  - Show this help');
  decisionsLog.log('  {yellow-fg}q / ESC{/yellow-fg} - Quit');
  decisionsLog.log('{cyan-fg}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{/cyan-fg}');
});

// ============================================================================
// STARTUP
// ============================================================================

(async function main() {
  decisionsLog.log('{green-fg}🚀 Autonomous Learning System Dashboard Starting...{/green-fg}');
  decisionsLog.log('{blue-fg}Press {yellow-fg}h{/yellow-fg} for help, {yellow-fg}q{/yellow-fg} to quit{/blue-fg}');

  // Initial render
  await updateDashboard();

  // Set up auto-refresh
  setInterval(async () => {
    await updateDashboard();
  }, CONFIG.refreshInterval);

  screen.render();
})();
