#!/bin/bash
# Migrate workflows to use fleet telemetry (inline approach)
#
# This script applies the Phase 2 fleet telemetry pattern to workflows.
#
# Usage:
#   ./migrate-fleet-telemetry.sh [options]
#
# Options:
#   --dry-run          Show what would be changed (default)
#   --apply            Apply changes to all workflows
#   --sample N         Apply to first N workflows only (for testing)
#   --help             Show this help
#
# Examples:
#   ./migrate-fleet-telemetry.sh --dry-run
#   ./migrate-fleet-telemetry.sh --sample 3
#   ./migrate-fleet-telemetry.sh --apply

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="${SCRIPT_DIR}/workflows"
MODE="dry-run"
SAMPLE_COUNT=0

# Telemetry snippet to inject (after meta block)
read -r -d '' TELEMETRY_SNIPPET << 'EOF' || true
// Fleet telemetry - Phase 2 (dispatch + complete)
const FLEET_DISPATCHER = process.env.FLEET_DISPATCHER_URL || 'http://pi-02:3004'
const _fleetJobId = (() => {
  if (process.env.FLEET_DISPATCHER === 'false') return null
  return (async () => {
    try {
      const res = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'sonnet',
          prompt: '[workflow]',
          job_type: 'agent',
          estimated_ram_gb: 1.0,
          estimated_duration_seconds: 60
        })
      })
      if (!res.ok) return null
      const data = await res.json()
      return data?.job_id || null
    } catch { return null }
  })()
})()
const _startTime = Date.now()
const _completeFleetJob = async (success, error = null) => {
  if (!_fleetJobId) return
  try {
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: _fleetJobId,
        instance: 'workflow',
        success,
        duration_seconds: (Date.now() - _startTime) / 1000,
        job_type: 'agent',
        model: 'sonnet',
        error
      })
    }).catch(() => {})
  } catch {}
}
EOF

# Helper: Parse arguments
parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      --dry-run)
        MODE="dry-run"
        shift
        ;;
      --apply)
        MODE="apply"
        shift
        ;;
      --sample)
        SAMPLE_COUNT="$2"
        shift 2
        ;;
      --help)
        show_help
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        show_help
        exit 1
        ;;
    esac
  done
}

# Helper: Show help text
show_help() {
  cat << 'HELP'
Migrate workflows to fleet telemetry integration

Usage: ./migrate-fleet-telemetry.sh [options]

Options:
  --dry-run          Show what would be changed (default)
  --apply            Apply changes to all workflows
  --sample N         Apply to first N workflows only (for testing)
  --help             Show this help

Examples:
  # See what would change
  ./migrate-fleet-telemetry.sh --dry-run

  # Apply to 3 sample workflows for testing
  ./migrate-fleet-telemetry.sh --sample 3

  # Apply to all workflows
  ./migrate-fleet-telemetry.sh --apply

Description:
This script adds fleet telemetry (dispatch/complete) to all workflows.
The telemetry is:
  - Inline (no external dependencies)
  - Optional (works without fleet dispatcher)
  - Silent (failures don't break workflows)
  - Minimal (15 lines of code per workflow)

The pattern is:
  1. After meta block: Initialize fleet dispatch
  2. After agent() calls: Call _completeFleetJob(true/false)

For workflows with multiple agent() calls, you can:
  - Use a single job ID for the entire workflow
  - Or dispatch/complete around specific agent() calls
  - The pattern supports both approaches

HELP
}

# Helper: Check if workflow already has telemetry
has_telemetry() {
  local file="$1"
  grep -q "FLEET_DISPATCHER\|_fleetJobId\|_completeFleetJob" "$file" 2>/dev/null
  return $?
}

# Helper: Get line number after meta block
get_meta_end_line() {
  local file="$1"
  awk '
    /^export const meta/ { found=1; start=NR }
    found && /^}/ && NR > start { print NR; exit }
  ' "$file"
}

# Helper: Inject telemetry after meta block
inject_telemetry() {
  local file="$1"
  local meta_end=$(get_meta_end_line "$file")

  if [ -z "$meta_end" ]; then
    echo "  ⚠️  Could not find meta block end"
    return 1
  fi

  # Create temp file with telemetry injected
  {
    head -n "$meta_end" "$file"
    echo ""
    echo "$TELEMETRY_SNIPPET"
    echo ""
    tail -n +$((meta_end + 1)) "$file"
  } > "${file}.tmp"

  mv "${file}.tmp" "$file"
  return 0
}

# Main logic
parse_args "$@"

if [ ! -d "$WORKFLOWS_DIR" ]; then
  echo "❌ Workflows directory not found: $WORKFLOWS_DIR"
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Fleet Telemetry Migration"
echo "Mode: $MODE"
[ "$SAMPLE_COUNT" -gt 0 ] && echo "Sample count: $SAMPLE_COUNT" || echo "Target: All workflows"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

processed=0
skipped=0
total=0

for workflow in "$WORKFLOWS_DIR"/*.js; do
  # Skip non-workflow files
  [[ "$workflow" == *"test.js" ]] && continue
  [[ "$workflow" == *"-min.js" ]] && continue
  [[ ! -f "$workflow" ]] && continue

  name=$(basename "$workflow")
  ((total++))

  # Stop if sample limit reached
  if [ "$SAMPLE_COUNT" -gt 0 ] && [ $processed -ge "$SAMPLE_COUNT" ]; then
    break
  fi

  # Check if already has telemetry
  if has_telemetry "$workflow"; then
    echo "⏭️  $name (already has telemetry)"
    ((skipped++))
    continue
  fi

  echo -n "📝 $name ... "

  if [ "$MODE" = "dry-run" ]; then
    echo "would inject telemetry"
  else
    if inject_telemetry "$workflow"; then
      echo "✅ telemetry injected"
      ((processed++))
    else
      echo "❌ failed to inject"
    fi
  fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Summary:"
echo "  Total workflows: $total"
echo "  Processed: $processed"
echo "  Skipped: $skipped"
echo "  Mode: $MODE"
echo ""

if [ "$MODE" = "dry-run" ]; then
  echo "To apply these changes, run:"
  if [ "$SAMPLE_COUNT" -gt 0 ]; then
    echo "  ./migrate-fleet-telemetry.sh --sample $SAMPLE_COUNT"
  else
    echo "  ./migrate-fleet-telemetry.sh --apply"
  fi
else
  echo "✅ Migration complete"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
