#!/usr/bin/env bash
#
# learning-status.sh - Show learning system status and metrics
#
# Phase 1: Display current LIS scores, recent learnings, and improvement trends
#
# Usage:
#   ./scripts/learning-status.sh [options]
#
# Options:
#   --full          Show comprehensive metrics for all models/tasks
#   --model <name>  Show metrics for specific model
#   --task <type>   Show metrics for specific task type
#   --leaderboard   Show ranked list of all model/task combinations
#   --recent N      Show last N executions (default: 10)
#
# What this shows:
#   1. Current LIS (Learning Intelligence Score) - 0-100 aggregate
#   2. Recent learning sessions
#   3. Quality/cost/speed trends
#   4. Top performers
#   5. What's improving vs declining

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
NC='\033[0m'

# ============================================================================
# PARSE ARGS
# ============================================================================

SHOW_FULL=false
SHOW_LEADERBOARD=false
FILTER_MODEL=""
FILTER_TASK=""
RECENT_LIMIT=10

while [[ $# -gt 0 ]]; do
  case $1 in
    --full)
      SHOW_FULL=true
      shift
      ;;
    --leaderboard)
      SHOW_LEADERBOARD=true
      shift
      ;;
    --model)
      FILTER_MODEL="$2"
      shift 2
      ;;
    --task)
      FILTER_TASK="$2"
      shift 2
      ;;
    --recent)
      RECENT_LIMIT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ============================================================================
# MAIN STATUS DISPLAY
# ============================================================================

echo -e "${CYAN}${BOLD}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Learning System Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"

# Use Node.js to query the database and calculate metrics
node --input-type=module <<EOF
import {
  getDb,
  getExecutionCount,
  getRecentExecutions,
  getDistinctModelTasks,
  getMetadata
} from '$REPO_ROOT/shared/learning-logger.js';

import {
  calculateLIS,
  calculateQualityTrend,
  calculateCostEfficiency,
  getAllMetricsLeaderboard,
  getModelCombinationMetrics
} from '$REPO_ROOT/shared/learning-metrics.js';

// ============================================================================
// HELPERS
// ============================================================================

const COLORS = {
  red: '\x1b[0;31m',
  green: '\x1b[0;32m',
  yellow: '\x1b[1;33m',
  blue: '\x1b[0;34m',
  cyan: '\x1b[0;36m',
  magenta: '\x1b[0;35m',
  bold: '\x1b[1m',
  nc: '\x1b[0m'
};

function formatTrend(trend, value) {
  if (trend === 'improving') {
    return \`\${COLORS.green}↑ \${value > 0 ? '+' : ''}\${value.toFixed(1)}%\${COLORS.nc}\`;
  } else if (trend === 'declining') {
    return \`\${COLORS.red}↓ \${value.toFixed(1)}%\${COLORS.nc}\`;
  } else {
    return \`\${COLORS.yellow}→ stable\${COLORS.nc}\`;
  }
}

function formatLIS(lis) {
  const score = lis.score;
  let color = COLORS.yellow;
  let rating = 'Fair';

  if (score >= 90) { color = COLORS.green; rating = 'Excellent'; }
  else if (score >= 75) { color = COLORS.green; rating = 'Good'; }
  else if (score >= 60) { color = COLORS.yellow; rating = 'Fair'; }
  else if (score >= 40) { color = COLORS.yellow; rating = 'Poor'; }
  else { color = COLORS.red; rating = 'Very Poor'; }

  return \`\${color}\${score.toFixed(1)}\${COLORS.nc} (\${rating})\`;
}

function bar(value, max = 100, width = 20) {
  const filled = Math.round((value / max) * width);
  const empty = width - filled;
  return \`\${COLORS.cyan}\${'█'.repeat(filled)}\${COLORS.nc}\${'░'.repeat(empty)}\`;
}

// ============================================================================
// DATABASE CHECK
// ============================================================================

const db = getDb();
if (!db) {
  console.log(\`\${COLORS.red}❌ Learning database unavailable\${COLORS.nc}\`);
  console.log(\`   Database path: \$HOME/.claude/learning/db/learning.db\`);
  console.log(\`   Run a workflow first to initialize: ./scripts/learning-session.sh code-review\`);
  process.exit(1);
}

const totalExecutions = getExecutionCount();
if (totalExecutions === 0) {
  console.log(\`\${COLORS.yellow}⚠️  No executions logged yet\${COLORS.nc}\`);
  console.log(\`   Run a learning session to start: ./scripts/learning-session.sh <workflow>\`);
  process.exit(0);
}

// ============================================================================
// OVERVIEW
// ============================================================================

console.log(\`\${COLORS.bold}📊 Overview\${COLORS.nc}\`);
console.log(\`   Total executions:  \${totalExecutions}\`);

const modelTasks = getDistinctModelTasks();
console.log(\`   Model/task combos: \${modelTasks.length}\`);
console.log(\`   Models tracked:    \${[...new Set(modelTasks.map(mt => mt.model))].length}\`);
console.log(\`   Task types:        \${[...new Set(modelTasks.map(mt => mt.task_type))].length}\`);

const lastSession = getMetadata('last_session_id');
if (lastSession) {
  console.log(\`   Last session:      \${lastSession}\`);
}

console.log();

// ============================================================================
// TOP PERFORMERS (LIS Leaderboard)
// ============================================================================

console.log(\`\${COLORS.bold}🏆 Top Performers (by LIS Score)\${COLORS.nc}\`);
console.log();

const showFull = process.env.SHOW_FULL === 'true';
const showLeaderboard = process.env.SHOW_LEADERBOARD === 'true';
const filterModel = process.env.FILTER_MODEL || '';
const filterTask = process.env.FILTER_TASK || '';

let leaderboard = getAllMetricsLeaderboard({ minSamples: 5 });

// Apply filters
if (filterModel) {
  leaderboard = leaderboard.filter(lb => lb.model === filterModel);
}
if (filterTask) {
  leaderboard = leaderboard.filter(lb => lb.taskType === filterTask);
}

const displayCount = showFull || showLeaderboard ? leaderboard.length : Math.min(5, leaderboard.length);

if (leaderboard.length === 0) {
  console.log(\`   \${COLORS.yellow}No metrics available yet (need min 5 samples per model/task)\${COLORS.nc}\`);
} else {
  console.log(\`   \${'Rank'.padEnd(6)} \${'Model'.padEnd(12)} \${'Task'.padEnd(20)} \${'LIS'.padEnd(15)} \${'Q'.padEnd(6)} \${'C'.padEnd(6)} \${'S'.padEnd(6)}\`);
  console.log(\`   \${'-'.repeat(80)}\`);

  for (let i = 0; i < displayCount; i++) {
    const lb = leaderboard[i];
    const rank = (i + 1).toString().padEnd(6);
    const model = lb.model.padEnd(12);
    const task = (lb.taskType || 'unknown').padEnd(20);
    const lisScore = formatLIS(lb.lis);
    const qScore = lb.lis.components.quality.toFixed(0).padEnd(6);
    const cScore = lb.lis.components.cost.toFixed(0).padEnd(6);
    const sScore = lb.lis.components.speed.toFixed(0).padEnd(6);

    console.log(\`   \${rank} \${model} \${task} \${lisScore.padEnd(25)} \${qScore} \${cScore} \${sScore}\`);
  }

  if (!showFull && !showLeaderboard && leaderboard.length > 5) {
    console.log();
    console.log(\`   \${COLORS.cyan}... and \${leaderboard.length - 5} more (use --leaderboard to show all)\${COLORS.nc}\`);
  }
}

console.log();

// ============================================================================
// RECENT TRENDS
// ============================================================================

console.log(\`\${COLORS.bold}📈 Recent Trends\${COLORS.nc}\`);
console.log();

if (leaderboard.length > 0) {
  // Show top 3 performers' trends
  const topPerformers = leaderboard.slice(0, 3);

  for (const performer of topPerformers) {
    const { model, taskType, qualityTrend, costEfficiency } = performer;

    console.log(\`   \${COLORS.bold}\${model}\${COLORS.nc} - \${taskType}\`);

    if (qualityTrend) {
      const trend = formatTrend(qualityTrend.trend, qualityTrend.improvementPercent);
      console.log(\`      Quality:    \${trend} (mean: \${qualityTrend.mean.toFixed(3)})\`);
    }

    if (costEfficiency) {
      const costTrend = costEfficiency.trendSlope < 0 ? 'improving' :
                        costEfficiency.trendSlope > 0 ? 'declining' : 'stable';
      const costPct = Math.abs(costEfficiency.trendSlope * 100);
      const formattedCost = formatTrend(costTrend, -costPct);
      console.log(\`      Cost/Q:     \${formattedCost} (\$\${costEfficiency.costPerQualityPoint.toFixed(4)}/Q)\`);
    }

    console.log();
  }
} else {
  console.log(\`   \${COLORS.yellow}No trend data available yet\${COLORS.nc}\`);
  console.log();
}

// ============================================================================
// MODEL COMBINATIONS
// ============================================================================

const combinations = getModelCombinationMetrics({ minSamples: 2 });
if (combinations.length > 0) {
  console.log(\`\${COLORS.bold}🤝 Model Combinations (Synergy)\${COLORS.nc}\`);
  console.log();

  const topCombos = combinations.slice(0, 3);
  for (const combo of topCombos) {
    const workers = combo.workers.join(', ');
    const synergy = combo.synergy > 0.05 ? \`\${COLORS.green}+\${(combo.synergy * 100).toFixed(1)}%\${COLORS.nc}\` :
                    combo.synergy < -0.05 ? \`\${COLORS.red}\${(combo.synergy * 100).toFixed(1)}%\${COLORS.nc}\` :
                    \`\${COLORS.yellow}0.0%\${COLORS.nc}\`;

    console.log(\`   \${combo.taskType}\`);
    console.log(\`      Workers: \${workers}\`);
    console.log(\`      Arbiter: \${combo.arbiter || 'none'}\`);
    console.log(\`      Synergy: \${synergy} \${combo.synergyStar}\`);
    console.log(\`      Quality: \${combo.avgQuality.toFixed(3)} | Cost: \$\${combo.avgCost.toFixed(4)} | Uses: \${combo.usageCount}\`);
    console.log();
  }
}

// ============================================================================
// RECENT EXECUTIONS
// ============================================================================

console.log(\`\${COLORS.bold}🕒 Recent Executions\${COLORS.nc}\`);
console.log();

const recentLimit = parseInt(process.env.RECENT_LIMIT || '10', 10);
const recent = getRecentExecutions(recentLimit);

if (recent.length > 0) {
  console.log(\`   \${'Time'.padEnd(20)} \${'Model'.padEnd(12)} \${'Task'.padEnd(20)} \${'Quality'.padEnd(8)} \${'Cost'.padEnd(10)} \${'Outcome'}\`);
  console.log(\`   \${'-'.repeat(80)}\`);

  for (const exec of recent) {
    const time = new Date(exec.timestamp).toLocaleString('en-US', {
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).padEnd(20);
    const model = exec.model.padEnd(12);
    const task = (exec.task_type || 'unknown').padEnd(20);
    const quality = exec.quality_score ? exec.quality_score.toFixed(3).padEnd(8) : 'N/A'.padEnd(8);
    const cost = exec.cost_usd ? ('\$' + exec.cost_usd.toFixed(4)).padEnd(10) : '\$0'.padEnd(10);
    const outcome = exec.outcome === 'success' ? \`\${COLORS.green}✓\${COLORS.nc}\` :
                    exec.outcome === 'error' ? \`\${COLORS.red}✗\${COLORS.nc}\` :
                    \`\${COLORS.yellow}?\${COLORS.nc}\`;

    console.log(\`   \${time} \${model} \${task} \${quality} \${cost} \${outcome}\`);
  }
} else {
  console.log(\`   \${COLORS.yellow}No recent executions\${COLORS.nc}\`);
}

console.log();

// ============================================================================
// FOOTER
// ============================================================================

console.log(\`\${COLORS.cyan}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\${COLORS.nc}\`);
console.log();
console.log(\`LIS Components: Q=Quality, C=Cost, S=Speed (all 0-100)\`);
console.log(\`Trend: \${COLORS.green}↑ improving\${COLORS.nc} | \${COLORS.yellow}→ stable\${COLORS.nc} | \${COLORS.red}↓ declining\${COLORS.nc}\`);
console.log();
console.log(\`Options:\`);
console.log(\`  --full          Show all metrics\`);
console.log(\`  --leaderboard   Show complete leaderboard\`);
console.log(\`  --model <name>  Filter by model\`);
console.log(\`  --task <type>   Filter by task type\`);
console.log(\`  --recent N      Show last N executions (default: 10)\`);
console.log();
EOF
