#!/usr/bin/env bash
#
# learning-dashboard.sh - Learning Intelligence Score (LIS) Dashboard
#
# Display comprehensive LIS dashboard with:
#   - Current LIS score (0-100 weighted average)
#   - Trend graph (last 30 days)
#   - Top improvements
#   - Recent learnings
#
# LIS = weighted average of:
#   - Quality improvement: 40%
#   - Cost reduction: 30%
#   - Speed improvement: 20%
#   - User satisfaction: 10%
#
# Usage:
#   ./scripts/learning-dashboard.sh [options]
#
# Options:
#   --model <name>      Filter by specific model
#   --task <type>       Filter by specific task type
#   --days <N>          Show trend for last N days (default: 30)
#   --json              Output raw JSON data
#   --export <file>     Export dashboard data to file
#   --compact           Show compact view
#
# Examples:
#   ./scripts/learning-dashboard.sh
#   ./scripts/learning-dashboard.sh --model opus --task code_review
#   ./scripts/learning-dashboard.sh --days 7 --compact
#   ./scripts/learning-dashboard.sh --json > lis-data.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ============================================================================
# PARSE ARGS
# ============================================================================

FILTER_MODEL=""
FILTER_TASK=""
TREND_DAYS=30
OUTPUT_JSON=false
EXPORT_FILE=""
COMPACT_MODE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --model)
      FILTER_MODEL="$2"
      shift 2
      ;;
    --task)
      FILTER_TASK="$2"
      shift 2
      ;;
    --days)
      TREND_DAYS="$2"
      shift 2
      ;;
    --json)
      OUTPUT_JSON=true
      shift
      ;;
    --export)
      EXPORT_FILE="$2"
      shift 2
      ;;
    --compact)
      COMPACT_MODE=true
      shift
      ;;
    -h|--help)
      head -n 40 "$0" | tail -n +2 | sed 's/^# //; s/^#//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# ============================================================================
# DASHBOARD IMPLEMENTATION
# ============================================================================

export FILTER_MODEL FILTER_TASK TREND_DAYS OUTPUT_JSON EXPORT_FILE COMPACT_MODE

node --input-type=module <<'EOF'
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { writeFileSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = process.env.REPO_ROOT || join(__dirname, '..');

// Import from learning/calculate-lis.js
const calculateLISPath = join(REPO_ROOT, 'learning', 'calculate-lis.js');
const {
  computeLIS,
  computeQualityTrend,
  computeCostEfficiency,
  computeSpeedImprovement,
  computeAllMetrics,
  computeLeaderboard,
  recomputeModelPerformance,
  WEIGHTS
} = await import(calculateLISPath);

// Import from learning/db.js
const dbPath = join(REPO_ROOT, 'learning', 'db.js');
const {
  getDb,
  query,
  queryOne,
  getRecentExecutions,
  getDistinctModelTasks
} = await import(dbPath);

// ============================================================================
// CONFIGURATION
// ============================================================================

const FILTER_MODEL = process.env.FILTER_MODEL || '';
const FILTER_TASK = process.env.FILTER_TASK || '';
const TREND_DAYS = parseInt(process.env.TREND_DAYS || '30', 10);
const OUTPUT_JSON = process.env.OUTPUT_JSON === 'true';
const EXPORT_FILE = process.env.EXPORT_FILE || '';
const COMPACT_MODE = process.env.COMPACT_MODE === 'true';

const COLORS = {
  red: '\x1b[0;31m',
  green: '\x1b[0;32m',
  yellow: '\x1b[1;33m',
  blue: '\x1b[0;34m',
  cyan: '\x1b[0;36m',
  magenta: '\x1b[0;35m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  nc: '\x1b[0m'
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function formatScore(score) {
  let color = COLORS.yellow;
  let symbol = '●';

  if (score >= 90) { color = COLORS.green; symbol = '★'; }
  else if (score >= 75) { color = COLORS.green; symbol = '◆'; }
  else if (score >= 60) { color = COLORS.yellow; symbol = '●'; }
  else if (score >= 40) { color = COLORS.yellow; symbol = '○'; }
  else { color = COLORS.red; symbol = '✗'; }

  return `${color}${symbol} ${score.toFixed(1)}${COLORS.nc}`;
}

function formatTrend(value, inverted = false) {
  const threshold = 0.5;
  const adjustedValue = inverted ? -value : value;

  if (adjustedValue > threshold) {
    return `${COLORS.green}↑ +${Math.abs(value).toFixed(1)}%${COLORS.nc}`;
  } else if (adjustedValue < -threshold) {
    return `${COLORS.red}↓ ${value.toFixed(1)}%${COLORS.nc}`;
  } else {
    return `${COLORS.yellow}→ ${value.toFixed(1)}%${COLORS.nc}`;
  }
}

function sparkline(values, width = 20, max = null) {
  if (!values || values.length === 0) return ''.padEnd(width, '░');

  const maxVal = max || Math.max(...values, 1);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;

  const blocks = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];

  const sampledValues = [];
  const step = Math.max(1, Math.floor(values.length / width));
  for (let i = 0; i < width && i * step < values.length; i++) {
    sampledValues.push(values[i * step]);
  }

  return sampledValues.map(v => {
    const normalized = (v - minVal) / range;
    const blockIndex = Math.min(blocks.length - 1, Math.floor(normalized * blocks.length));
    return blocks[blockIndex];
  }).join('');
}

function progressBar(value, max = 100, width = 40) {
  const filled = Math.round((value / max) * width);
  const empty = width - filled;

  let color = COLORS.cyan;
  if (value >= 90) color = COLORS.green;
  else if (value >= 75) color = COLORS.green;
  else if (value >= 60) color = COLORS.yellow;
  else if (value < 40) color = COLORS.red;

  return `${color}${'█'.repeat(filled)}${COLORS.nc}${'░'.repeat(empty)}`;
}

function calculateGlobalLIS() {
  const leaderboard = computeLeaderboard({ minSamples: 5 });
  if (leaderboard.length === 0) return null;

  const scores = leaderboard.map(lb => lb.lis.score);
  const avgLIS = scores.reduce((a, b) => a + b, 0) / scores.length;

  const allQuality = leaderboard.map(lb => lb.qualityTrend).filter(Boolean);
  const avgQualityImprovement = allQuality.length > 0
    ? allQuality.reduce((sum, qt) => sum + qt.improvementPercent, 0) / allQuality.length
    : 0;

  const allCost = leaderboard.map(lb => lb.costEfficiency).filter(Boolean);
  const avgCostEfficiency = allCost.length > 0
    ? allCost.reduce((sum, ce) => sum + ce.costEfficiencyScore, 0) / allCost.length
    : 0;

  const allSpeed = leaderboard.map(lb => lb.speedImprovement).filter(Boolean);
  const avgSpeedImprovement = allSpeed.length > 0
    ? allSpeed.reduce((sum, si) => sum + si.speedImprovement, 0) / allSpeed.length
    : 0;

  return {
    score: avgLIS,
    qualityImprovement: avgQualityImprovement,
    costReduction: avgCostEfficiency,
    speedImprovement: avgSpeedImprovement,
    userSatisfaction: 0, // Placeholder - would need user feedback data
    sampleCount: leaderboard.length
  };
}

function getTrendHistory(days = 30) {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);

  const dailyStats = query(
    `SELECT DATE(timestamp) as day,
            AVG(quality_score) as avg_quality,
            AVG(cost_usd) as avg_cost,
            AVG(duration_ms) as avg_duration,
            COUNT(*) as count
     FROM execution_log
     WHERE timestamp >= ? AND quality_score IS NOT NULL
     GROUP BY DATE(timestamp)
     ORDER BY day ASC`,
    [cutoffDate.toISOString()]
  );

  return dailyStats;
}

function getTopImprovements(limit = 5) {
  const modelTasks = getDistinctModelTasks();
  const improvements = [];

  for (const { model, task_type } of modelTasks) {
    const qualityTrend = computeQualityTrend(model, task_type);
    if (qualityTrend && qualityTrend.trend === 'improving') {
      improvements.push({
        model,
        taskType: task_type,
        improvement: qualityTrend.improvementPercent,
        confidence: qualityTrend.confidence,
        metric: 'quality'
      });
    }

    const speedTrend = computeSpeedImprovement(model, task_type);
    if (speedTrend && speedTrend.speedImprovement > 5) {
      improvements.push({
        model,
        taskType: task_type,
        improvement: speedTrend.speedImprovement,
        confidence: 0.8,
        metric: 'speed'
      });
    }
  }

  improvements.sort((a, b) => b.improvement - a.improvement);
  return improvements.slice(0, limit);
}

function getRecentLearnings(limit = 10) {
  const recent = getRecentExecutions(limit);
  return recent.map(exec => ({
    timestamp: exec.timestamp,
    model: exec.model,
    taskType: exec.task_type,
    quality: exec.quality_score,
    cost: exec.cost_usd,
    duration: exec.duration_ms,
    outcome: exec.outcome
  }));
}

// ============================================================================
// DATABASE CHECK
// ============================================================================

const db = getDb();
if (!db) {
  console.error(`${COLORS.red}❌ Learning database unavailable${COLORS.nc}`);
  console.error(`   Database path: ~/.claude/learning/db/learning.db`);
  console.error(`   Run: ./scripts/learning-session.sh <workflow>`);
  process.exit(1);
}

// ============================================================================
// COMPUTE METRICS
// ============================================================================

// Recompute model performance if needed
const lastRecompute = queryOne(`SELECT value FROM metadata WHERE key = 'last_model_performance_recompute'`);
const now = new Date();
const shouldRecompute = !lastRecompute ||
  (now - new Date(lastRecompute.value)) > 5 * 60 * 1000; // 5 minutes

if (shouldRecompute) {
  recomputeModelPerformance({ minSamples: 3 });
}

const globalLIS = calculateGlobalLIS();
const trendHistory = getTrendHistory(TREND_DAYS);
const topImprovements = getTopImprovements(COMPACT_MODE ? 3 : 5);
const recentLearnings = getRecentLearnings(COMPACT_MODE ? 5 : 10);
const leaderboard = computeLeaderboard({ minSamples: 5 });

// Apply filters
let filteredLeaderboard = leaderboard;
if (FILTER_MODEL) {
  filteredLeaderboard = filteredLeaderboard.filter(lb => lb.model === FILTER_MODEL);
}
if (FILTER_TASK) {
  filteredLeaderboard = filteredLeaderboard.filter(lb => lb.taskType === FILTER_TASK);
}

// ============================================================================
// JSON OUTPUT
// ============================================================================

if (OUTPUT_JSON) {
  const jsonData = {
    globalLIS,
    trendHistory,
    topImprovements,
    recentLearnings,
    leaderboard: filteredLeaderboard,
    weights: WEIGHTS,
    timestamp: new Date().toISOString()
  };

  console.log(JSON.stringify(jsonData, null, 2));

  if (EXPORT_FILE) {
    writeFileSync(EXPORT_FILE, JSON.stringify(jsonData, null, 2));
    console.error(`${COLORS.green}✓ Exported to ${EXPORT_FILE}${COLORS.nc}`);
  }

  process.exit(0);
}

// ============================================================================
// VISUAL DASHBOARD
// ============================================================================

console.log();
console.log(`${COLORS.cyan}${COLORS.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLORS.nc}`);
console.log(`${COLORS.cyan}${COLORS.bold}  Learning Intelligence Score (LIS) Dashboard${COLORS.nc}`);
console.log(`${COLORS.cyan}${COLORS.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLORS.nc}`);
console.log();

// ============================================================================
// GLOBAL LIS SCORE
// ============================================================================

if (globalLIS) {
  console.log(`${COLORS.bold}📊 Current LIS Score${COLORS.nc}`);
  console.log();

  const scoreDisplay = formatScore(globalLIS.score);
  const bar = progressBar(globalLIS.score, 100, 50);

  console.log(`   ${scoreDisplay}  ${bar}  ${globalLIS.score.toFixed(1)}/100`);
  console.log();

  if (!COMPACT_MODE) {
    console.log(`   ${COLORS.dim}Components (weighted):${COLORS.nc}`);
    console.log(`   • Quality improvement  ${COLORS.cyan}${(WEIGHTS.quality * 100).toFixed(0)}%${COLORS.nc}  ${formatTrend(globalLIS.qualityImprovement)}`);
    console.log(`   • Cost efficiency      ${COLORS.cyan}${(WEIGHTS.cost * 100).toFixed(0)}%${COLORS.nc}  ${formatScore(globalLIS.costReduction).padEnd(20)} (${globalLIS.costReduction.toFixed(1)}/100)`);
    console.log(`   • Speed improvement    ${COLORS.cyan}${(WEIGHTS.speed * 100).toFixed(0)}%${COLORS.nc}  ${formatTrend(globalLIS.speedImprovement)}`);
    console.log(`   • Consistency          ${COLORS.cyan}${(WEIGHTS.consistency * 100).toFixed(0)}%${COLORS.nc}  ${COLORS.yellow}baseline${COLORS.nc}`);
    console.log();
    console.log(`   ${COLORS.dim}Based on ${globalLIS.sampleCount} model/task combinations${COLORS.nc}`);
    console.log();
  }
} else {
  console.log(`${COLORS.yellow}⚠️  Insufficient data for global LIS calculation${COLORS.nc}`);
  console.log(`   Need at least 5 samples per model/task combination`);
  console.log();
}

// ============================================================================
// TREND GRAPH
// ============================================================================

console.log(`${COLORS.bold}📈 Trend (Last ${TREND_DAYS} Days)${COLORS.nc}`);
console.log();

if (trendHistory.length > 0) {
  const qualityValues = trendHistory.map(th => th.avg_quality);
  const costValues = trendHistory.map(th => th.avg_cost * 10000); // Scale for visibility
  const speedValues = trendHistory.map(th => 10000 / (th.avg_duration || 1)); // Inverse for "faster is better"

  console.log(`   Quality:  ${COLORS.green}${sparkline(qualityValues, 60)}${COLORS.nc}  (avg: ${(qualityValues.reduce((a,b) => a+b, 0) / qualityValues.length).toFixed(3)})`);
  console.log(`   Cost:     ${COLORS.yellow}${sparkline(costValues, 60)}${COLORS.nc}  (trend)`);
  console.log(`   Speed:    ${COLORS.cyan}${sparkline(speedValues, 60)}${COLORS.nc}  (trend)`);
  console.log();

  if (!COMPACT_MODE) {
    const firstDay = trendHistory[0].day;
    const lastDay = trendHistory[trendHistory.length - 1].day;
    console.log(`   ${COLORS.dim}${firstDay} → ${lastDay} (${trendHistory.length} days with data)${COLORS.nc}`);
    console.log();
  }
} else {
  console.log(`   ${COLORS.yellow}No trend data available for last ${TREND_DAYS} days${COLORS.nc}`);
  console.log();
}

// ============================================================================
// TOP IMPROVEMENTS
// ============================================================================

console.log(`${COLORS.bold}🚀 Top Improvements${COLORS.nc}`);
console.log();

if (topImprovements.length > 0) {
  for (const improvement of topImprovements) {
    const metricIcon = improvement.metric === 'quality' ? '🎯' : '⚡';
    const metricName = improvement.metric === 'quality' ? 'Quality' : 'Speed';
    const confidenceStars = '★'.repeat(Math.min(5, Math.ceil(improvement.confidence * 5)));

    console.log(`   ${metricIcon} ${COLORS.bold}${improvement.model}${COLORS.nc} · ${improvement.taskType}`);
    console.log(`      ${metricName}: ${formatTrend(improvement.improvement)}  ${COLORS.dim}confidence: ${confidenceStars}${COLORS.nc}`);
    console.log();
  }
} else {
  console.log(`   ${COLORS.yellow}No significant improvements detected yet${COLORS.nc}`);
  console.log();
}

// ============================================================================
// TOP PERFORMERS
// ============================================================================

if (!COMPACT_MODE && filteredLeaderboard.length > 0) {
  console.log(`${COLORS.bold}🏆 Top Performers${COLORS.nc}`);
  console.log();

  const displayCount = Math.min(5, filteredLeaderboard.length);
  console.log(`   ${'Rank'.padEnd(6)} ${'Model'.padEnd(14)} ${'Task'.padEnd(20)} ${'LIS'.padEnd(12)} ${'Quality'.padEnd(10)} ${'Cost'.padEnd(10)} ${'Speed'}`);
  console.log(`   ${'-'.repeat(90)}`);

  for (let i = 0; i < displayCount; i++) {
    const lb = filteredLeaderboard[i];
    const rank = `#${i + 1}`.padEnd(6);
    const model = lb.model.padEnd(14);
    const task = (lb.taskType || 'unknown').padEnd(20);
    const lis = lb.lis.score.toFixed(1).padEnd(12);
    const quality = lb.lis.components.quality.toFixed(0).padEnd(10);
    const cost = lb.lis.components.cost.toFixed(0).padEnd(10);
    const speed = lb.lis.components.speed.toFixed(0);

    console.log(`   ${rank} ${model} ${task} ${lis} ${quality} ${cost} ${speed}`);
  }

  console.log();
}

// ============================================================================
// RECENT LEARNINGS
// ============================================================================

console.log(`${COLORS.bold}🕒 Recent Learnings${COLORS.nc}`);
console.log();

if (recentLearnings.length > 0) {
  for (const learning of recentLearnings) {
    const time = new Date(learning.timestamp).toLocaleString('en-US', {
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });

    const outcomeIcon = learning.outcome === 'success' ? `${COLORS.green}✓${COLORS.nc}` :
                       learning.outcome === 'failed' ? `${COLORS.red}✗${COLORS.nc}` :
                       `${COLORS.yellow}?${COLORS.nc}`;

    const quality = learning.quality ? learning.quality.toFixed(3) : 'N/A';
    const cost = learning.cost ? `$${learning.cost.toFixed(4)}` : '$0';

    console.log(`   ${outcomeIcon} ${COLORS.dim}${time}${COLORS.nc}  ${learning.model.padEnd(12)} ${(learning.taskType || 'unknown').padEnd(20)} Q:${quality} C:${cost}`);
  }
  console.log();
} else {
  console.log(`   ${COLORS.yellow}No recent learnings${COLORS.nc}`);
  console.log();
}

// ============================================================================
// FOOTER
// ============================================================================

console.log(`${COLORS.cyan}${COLORS.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLORS.nc}`);
console.log();
console.log(`${COLORS.dim}LIS Calculation: ${(WEIGHTS.quality*100).toFixed(0)}% Quality + ${(WEIGHTS.cost*100).toFixed(0)}% Cost + ${(WEIGHTS.speed*100).toFixed(0)}% Speed + ${(WEIGHTS.consistency*100).toFixed(0)}% Consistency${COLORS.nc}`);
console.log(`${COLORS.dim}Score Ratings: ★ Excellent (90+) · ◆ Good (75-89) · ● Fair (60-74) · ○ Poor (40-59) · ✗ Very Poor (<40)${COLORS.nc}`);
console.log();

if (FILTER_MODEL || FILTER_TASK) {
  console.log(`${COLORS.cyan}Active filters: ${FILTER_MODEL || 'all models'} / ${FILTER_TASK || 'all tasks'}${COLORS.nc}`);
  console.log();
}

console.log(`${COLORS.dim}Options: --model <name> --task <type> --days <N> --json --export <file> --compact${COLORS.nc}`);
console.log();

// ============================================================================
// EXPORT
// ============================================================================

if (EXPORT_FILE && !OUTPUT_JSON) {
  const exportData = {
    globalLIS,
    trendHistory,
    topImprovements,
    recentLearnings,
    leaderboard: filteredLeaderboard,
    weights: WEIGHTS,
    timestamp: new Date().toISOString()
  };

  writeFileSync(EXPORT_FILE, JSON.stringify(exportData, null, 2));
  console.log(`${COLORS.green}✓ Dashboard data exported to ${EXPORT_FILE}${COLORS.nc}`);
  console.log();
}

EOF
