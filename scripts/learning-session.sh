#!/usr/bin/env bash
#
# learning-session.sh - Manual trigger for supervised learning session
#
# Phase 1: User-initiated workflow execution with automatic logging
# This script starts a learning session that captures all workflow executions
# automatically via the learning logger hooks.
#
# Usage:
#   ./scripts/learning-session.sh [workflow-name] [args...]
#
# Examples:
#   ./scripts/learning-session.sh code-review --high
#   ./scripts/learning-session.sh ai-consensus-debate "analyze this architecture"
#   ./scripts/learning-session.sh code-sdlc-auto
#
# What this does:
#   1. Logs session start to execution database
#   2. Executes the requested workflow
#   3. Workflow execution is automatically logged (via learning-logger.js)
#   4. Logs session end with outcome
#   5. Displays what was learned
#
# NO DAEMON - This is manual/supervised Phase 1 only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_PATH="$HOME/.claude/learning/db/learning.db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Generate session ID
SESSION_ID="session-$(date +%Y%m%d-%H%M%S)-$$"
RUN_ID="run-$(uuidgen 2>/dev/null || echo "$(date +%s)-$$")"

# ============================================================================
# HELPERS
# ============================================================================

log_info() {
  echo -e "${BLUE}[learning-session]${NC} $*"
}

log_success() {
  echo -e "${GREEN}[learning-session]${NC} $*"
}

log_error() {
  echo -e "${RED}[learning-session]${NC} $*" >&2
}

log_session_start() {
  local workflow="$1"
  local timestamp
  timestamp="$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"

  # Log to metadata table
  node --input-type=module <<EOF
import { setMetadata } from '$REPO_ROOT/shared/learning-logger.js';
setMetadata('last_session_id', '$SESSION_ID');
setMetadata('last_session_workflow', '$workflow');
setMetadata('last_session_start', '$timestamp');
setMetadata('last_session_run_id', '$RUN_ID');
EOF
}

log_session_end() {
  local outcome="$1"
  local notes="${2:-}"
  local timestamp
  timestamp="$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"

  node --input-type=module <<EOF
import { setMetadata } from '$REPO_ROOT/shared/learning-logger.js';
setMetadata('last_session_end', '$timestamp');
setMetadata('last_session_outcome', '$outcome');
if ('$notes') {
  setMetadata('last_session_notes', '$notes');
}
EOF
}

display_session_summary() {
  echo ""
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}  Learning Session Summary${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

  # Get session stats from database
  node --input-type=module <<EOF
import { getDb, getRecentExecutions, getMetadata } from '$REPO_ROOT/shared/learning-logger.js';

const db = getDb();
if (!db) {
  console.log('  ❌ Database unavailable - no learning data captured');
  process.exit(0);
}

const runId = '$RUN_ID';
const executions = db.prepare(\`
  SELECT
    COUNT(*) as total,
    COUNT(DISTINCT model) as models_used,
    AVG(quality_score) as avg_quality,
    SUM(cost_usd) as total_cost,
    SUM(duration_ms) as total_duration
  FROM execution_log
  WHERE run_id = ?
\`).get(runId);

console.log(\`  Session ID: $SESSION_ID\`);
console.log(\`  Run ID:     $RUN_ID\`);
console.log(\`
  📊 Execution Stats:
     - Total executions: \${executions.total || 0}
     - Models used:      \${executions.models_used || 0}
     - Avg quality:      \${executions.avg_quality ? executions.avg_quality.toFixed(3) : 'N/A'}
     - Total cost:       \\\$\${executions.total_cost ? executions.total_cost.toFixed(4) : '0.0000'}
     - Total duration:   \${executions.total_duration ? (executions.total_duration / 1000).toFixed(1) + 's' : 'N/A'}
\`);

// Show recent executions for this run
if (executions.total > 0) {
  console.log(\`  Recent executions:\`);
  const recent = db.prepare(\`
    SELECT model, task_type, quality_score, cost_usd, outcome
    FROM execution_log
    WHERE run_id = ?
    ORDER BY timestamp DESC
    LIMIT 5
  \`).all(runId);

  recent.forEach(e => {
    const quality = e.quality_score ? e.quality_score.toFixed(3) : 'N/A';
    const cost = e.cost_usd ? '\$' + e.cost_usd.toFixed(4) : '\$0';
    const outcome = e.outcome === 'success' ? '✓' : (e.outcome === 'error' ? '✗' : '?');
    console.log(\`     \${outcome} \${e.model.padEnd(12)} \${e.task_type || 'unknown'} - Q:\${quality} C:\${cost}\`);
  });
}
EOF

  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  log_info "View full status with: ${YELLOW}./scripts/learning-status.sh${NC}"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
  if [[ $# -lt 1 ]]; then
    log_error "Usage: $0 <workflow-name> [args...]"
    echo ""
    echo "Examples:"
    echo "  $0 code-review --high"
    echo "  $0 ai-consensus-debate 'analyze this architecture'"
    echo "  $0 code-sdlc-auto"
    echo ""
    exit 1
  fi

  local workflow="$1"
  shift
  local workflow_args=("$@")

  log_info "Starting supervised learning session"
  log_info "Workflow: ${YELLOW}$workflow${NC}"
  log_info "Run ID:   ${YELLOW}$RUN_ID${NC}"

  # Log session start
  log_session_start "$workflow"

  # Execute workflow
  # The workflow itself will log to the database via learning-logger.js
  local outcome="success"
  local notes=""

  echo ""
  log_info "Executing workflow..."
  echo ""

  if node "$REPO_ROOT/workflows/${workflow}.js" "${workflow_args[@]}"; then
    outcome="success"
    log_success "Workflow completed successfully"
  else
    outcome="error"
    notes="Workflow execution failed with exit code $?"
    log_error "Workflow execution failed"
  fi

  # Log session end
  log_session_end "$outcome" "$notes"

  # Display summary
  display_session_summary

  if [[ "$outcome" == "success" ]]; then
    exit 0
  else
    exit 1
  fi
}

# Handle interrupts gracefully
trap 'log_session_end "interrupted" "User interrupted"; exit 130' INT TERM

main "$@"
