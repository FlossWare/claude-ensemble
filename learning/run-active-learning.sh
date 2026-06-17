#!/bin/bash

# Active Learning Pipeline - Quick Start
# Orchestrates the full active learning workflow:
#   1. Identify opportunities (discovery phase)
#   2. Build strategic plan (planning phase)
#   3. Execute experiments (execution phase)
#   4. Report findings (feedback phase)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_PATH="${HOME}/.claude/learning/db/orchestration.db"
OUTPUT_DIR="${SCRIPT_DIR}/active-learning-results"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULT_DIR="${OUTPUT_DIR}/${TIMESTAMP}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

check_requirement() {
  if ! command -v "$1" &> /dev/null; then
    log_error "Missing required tool: $1"
    exit 1
  fi
}

# ============================================================================
# PHASE 1: DISCOVERY - Identify Opportunities
# ============================================================================

phase_discovery() {
  log_info "Phase 1: DISCOVERY - Identifying learning opportunities..."

  if [ ! -f "$DB_PATH" ]; then
    log_warn "Learning database not found at $DB_PATH"
    log_warn "Skipping discovery phase. Run some workflows first to populate the database."
    return 1
  fi

  mkdir -p "$RESULT_DIR"

  log_info "Analyzing execution history..."
  node "${SCRIPT_DIR}/active-learning-engine.js" \
    --db "$DB_PATH" \
    --limit 20 \
    --output "${RESULT_DIR}/opportunities.json" \
    > "${RESULT_DIR}/discovery.log" 2>&1

  if [ -f "${RESULT_DIR}/opportunities.json" ]; then
    local count=$(jq 'length' "${RESULT_DIR}/opportunities.json" 2>/dev/null || echo "0")
    log_success "Identified $count learning opportunities"
    return 0
  else
    log_error "Failed to identify opportunities"
    return 1
  fi
}

# ============================================================================
# PHASE 2: PLANNING - Build Strategic Experiment Plan
# ============================================================================

phase_planning() {
  log_info "Phase 2: PLANNING - Building strategic learning plan..."

  if [ ! -f "${RESULT_DIR}/opportunities.json" ]; then
    log_error "No opportunities file found. Run discovery phase first."
    return 1
  fi

  log_info "Converting opportunities to executable experiments..."
  node "${SCRIPT_DIR}/strategic-learning-planner.js" \
    --opportunities "${RESULT_DIR}/opportunities.json" \
    --budget 1000000 \
    --output "${RESULT_DIR}/plan" \
    > "${RESULT_DIR}/planning.log" 2>&1

  if [ -f "${RESULT_DIR}/plan/learning-plan.json" ]; then
    local count=$(jq '.summary.executable_experiments' "${RESULT_DIR}/plan/learning-plan.json" 2>/dev/null || echo "0")
    log_success "Created learning plan with $count experiments"

    # Display plan summary
    echo ""
    echo -e "${BLUE}Learning Plan Summary:${NC}"
    jq '.summary' "${RESULT_DIR}/plan/learning-plan.json" | sed 's/^/  /'

    return 0
  else
    log_error "Failed to create learning plan"
    return 1
  fi
}

# ============================================================================
# PHASE 3: EXECUTION - Run Experiments
# ============================================================================

phase_execution() {
  local batch_size="${1:-5}"

  log_info "Phase 3: EXECUTION - Running learning experiments..."

  if [ ! -f "${RESULT_DIR}/plan/learning-plan.json" ]; then
    log_error "No plan found. Run planning phase first."
    return 1
  fi

  log_info "Executing up to $batch_size experiments..."
  node "${SCRIPT_DIR}/experiment-executor.js" \
    --plan "${RESULT_DIR}/plan/learning-plan.json" \
    --db "$DB_PATH" \
    --limit "$batch_size" \
    > "${RESULT_DIR}/execution.log" 2>&1

  log_success "Experiment execution complete"
  return 0
}

# ============================================================================
# PHASE 4: FEEDBACK - Generate Learning Report
# ============================================================================

phase_feedback() {
  log_info "Phase 4: FEEDBACK - Generating learning report..."

  if [ ! -d "${RESULT_DIR}" ]; then
    log_error "No results directory found"
    return 1
  fi

  cat > "${RESULT_DIR}/REPORT.md" <<EOF
# Active Learning Execution Report

**Timestamp:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Results Directory:** $RESULT_DIR

## Phase Summary

### Phase 1: Discovery
- Identified learning opportunities from execution history
- See: \`opportunities.json\`

### Phase 2: Planning
- Converted opportunities to executable experiment queue
- See: \`plan/learning-plan.json\`
- See: \`plan/experiment-prompts.md\`

### Phase 3: Execution
- Ran learning experiments
- See: \`execution.log\`

### Phase 4: Feedback
- Generated learning insights and recommendations
- See: \`REPORT.md\` (this file)

## Files Generated

\`\`\`
${RESULT_DIR}/
├── opportunities.json              # Discovered learning opportunities
├── plan/
│   ├── learning-plan.json          # Prioritized experiment queue
│   └── experiment-prompts.md       # Readable experiment descriptions
├── discovery.log                   # Discovery phase logs
├── planning.log                    # Planning phase logs
├── execution.log                   # Execution phase logs
└── REPORT.md                       # This file
\`\`\`

## Key Metrics

EOF

  if [ -f "${RESULT_DIR}/opportunities.json" ]; then
    echo "" >> "${RESULT_DIR}/REPORT.md"
    echo "### Opportunities Identified" >> "${RESULT_DIR}/REPORT.md"
    echo "" >> "${RESULT_DIR}/REPORT.md"

    jq '.summary.by_domain' "${RESULT_DIR}/opportunities.json" | \
      jq 'to_entries | .[] | "- **\(.key)**: \(.value) opportunities"' -r >> "${RESULT_DIR}/REPORT.md"
  fi

  if [ -f "${RESULT_DIR}/plan/learning-plan.json" ]; then
    echo "" >> "${RESULT_DIR}/REPORT.md"
    echo "### Experiment Plan" >> "${RESULT_DIR}/REPORT.md"
    echo "" >> "${RESULT_DIR}/REPORT.md"

    jq '.summary' "${RESULT_DIR}/plan/learning-plan.json" | \
      jq -r '"- Total experiments: \(.executable_experiments)\n- Total token budget: \(.total_estimated_tokens)\n- Estimated time: \(.total_estimated_time_hours) hours\n- Tokens remaining: \(.tokens_remaining)"' >> "${RESULT_DIR}/REPORT.md"
  fi

  log_success "Report generated at ${RESULT_DIR}/REPORT.md"
  return 0
}

# ============================================================================
# MAIN
# ============================================================================

main() {
  log_info "╔════════════════════════════════════════════════════════════════╗"
  log_info "║         ACTIVE LEARNING PIPELINE - FULL ORCHESTRATION          ║"
  log_info "╚════════════════════════════════════════════════════════════════╝"
  log_info ""

  # Check requirements
  check_requirement "node"
  check_requirement "jq"

  # Verify database exists or will be created
  mkdir -p "$(dirname "$DB_PATH")"

  # Run phases
  if phase_discovery; then
    if phase_planning; then
      read -p "Run experiments? [y/N] " -n 1 -r
      echo
      if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Batch size (default: 5): " batch_size
        batch_size=${batch_size:-5}
        phase_execution "$batch_size"
      else
        log_info "Skipping execution phase"
      fi

      phase_feedback
    fi
  fi

  log_info ""
  log_success "Pipeline complete!"
  log_info "Results saved to: ${RESULT_DIR}"
  log_info ""
  log_info "Next steps:"
  log_info "  1. Review opportunities.json"
  log_info "  2. Review plan/learning-plan.json"
  log_info "  3. Run experiments: ./run-active-learning.sh --execute"
  log_info "  4. View results in: ${RESULT_DIR}"
  log_info ""
}

# Parse command-line arguments
if [[ ${1:-} == "--help" ]] || [[ ${1:-} == "-h" ]]; then
  cat <<EOF
Active Learning Pipeline

Usage: ./run-active-learning.sh [OPTIONS]

Options:
  --discover          Run discovery phase only
  --plan              Run planning phase only
  --execute [N]       Execute N experiments (default: 5)
  --all               Run full pipeline (discover → plan → execute → feedback)
  --help              Show this help message

Examples:
  ./run-active-learning.sh --discover
  ./run-active-learning.sh --plan
  ./run-active-learning.sh --execute 10
  ./run-active-learning.sh --all

Results are saved to: active-learning-results/[timestamp]/
EOF
  exit 0
fi

# Handle specific phases if requested
if [[ ${1:-} == "--discover" ]]; then
  phase_discovery
elif [[ ${1:-} == "--plan" ]]; then
  if [ ! -f "${RESULT_DIR}/opportunities.json" ]; then
    phase_discovery || exit 1
  fi
  phase_planning
elif [[ ${1:-} == "--execute" ]]; then
  batch_size=${2:-5}
  if [ ! -f "${RESULT_DIR}/plan/learning-plan.json" ]; then
    phase_discovery || exit 1
    phase_planning || exit 1
  fi
  phase_execution "$batch_size"
  phase_feedback
elif [[ ${1:-} == "--all" ]]; then
  phase_discovery || exit 1
  phase_planning || exit 1
  phase_execution "${2:-5}"
  phase_feedback
else
  main
fi
