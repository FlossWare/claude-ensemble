#!/bin/bash
#
# Fleet Multi-Session Distribution Script
#
# Generic multi-session orchestration for fleet-distributed bulk processing.
# Launches independent Claude Code sessions on each worker, merges results.
#
# Usage:
#   ./fleet-distribute.sh <workflow> <items...>
#
# Examples:
#   ./fleet-distribute.sh ai-pdf-deep-research *.pdf
#   ./fleet-distribute.sh ai-web-learn-bulk url1 url2 url3
#   ./fleet-distribute.sh code-security-bulk src/**/*.java
#
# Architecture:
# 1. Parse items from command line
# 2. Discover fleet workers (via fleet.json)
# 3. Split items into N batches (round-robin)
# 4. Launch `ssh <worker> "cd <project> && claude --workflow <skill> --args '<batch>'" &`
# 5. Wait for all workers
# 6. Collect outputs from /tmp on each worker
# 7. Merge results
#
# Environment:
#   FLEET_MIN_WORKERS - Minimum workers required (default: 2)
#   FLEET_TIMEOUT - Per-worker timeout in seconds (default: 600)
#   FLEET_DISTRIBUTION - 'round-robin' or 'weighted' (default: round-robin)
#   FLEET_OUTPUT_DIR - Output directory (default: /tmp/fleet-output)
#   FLEET_DRY_RUN - If 'true', show distribution without executing
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

WORKFLOW="${1:?Usage: $0 <workflow> <items...>}"
shift
ITEMS=("$@")

MIN_WORKERS="${FLEET_MIN_WORKERS:-2}"
TIMEOUT="${FLEET_TIMEOUT:-600}"
DISTRIBUTION="${FLEET_DISTRIBUTION:-round-robin}"
OUTPUT_DIR="${FLEET_OUTPUT_DIR:-/tmp/fleet-output}"
DRY_RUN="${FLEET_DRY_RUN:-false}"

PROJECT_DIR="$(pwd)"
NFS_ROOT="/home/sfloess/Development"

TIMESTAMP="$(date +%s)"
SESSION_ID="fleet-${WORKFLOW}-${TIMESTAMP}"

# ============================================================================
# HELPERS
# ============================================================================

log() {
  echo "[$(date +%H:%M:%S)] $*" >&2
}

error() {
  echo "ERROR: $*" >&2
  exit 1
}

# ============================================================================
# FLEET DISCOVERY
# ============================================================================

log "Discovering fleet workers..."

# Parse fleet.json for worker hostnames
FLEET_CONFIG="${HOME}/.claude/fleet.json"
[[ -f "$FLEET_CONFIG" ]] || error "Fleet config not found: $FLEET_CONFIG"

# Extract worker hostnames using jq
WORKERS=($(jq -r '.machines[] | select(.role == "worker") | .hostname' "$FLEET_CONFIG"))

if [[ ${#WORKERS[@]} -lt $MIN_WORKERS ]]; then
  error "Insufficient workers: ${#WORKERS[@]}/${MIN_WORKERS} required"
fi

log "Fleet available: ${#WORKERS[@]} workers (${WORKERS[*]})"

# ============================================================================
# NFS CHECK
# ============================================================================

if [[ ! "$PROJECT_DIR" =~ ^$NFS_ROOT ]]; then
  error "Project not on NFS: $PROJECT_DIR (must be under $NFS_ROOT)"
fi

log "Project directory: $PROJECT_DIR (NFS-shared)"

# ============================================================================
# DISTRIBUTION
# ============================================================================

log "Distributing ${#ITEMS[@]} items across ${#WORKERS[@]} workers ($DISTRIBUTION)..."

# Split items into batches (round-robin)
declare -A BATCHES

for i in "${!ITEMS[@]}"; do
  worker_idx=$((i % ${#WORKERS[@]}))
  worker="${WORKERS[$worker_idx]}"
  BATCHES[$worker]+="${ITEMS[$i]}"$'\n'
done

# Log distribution
for worker in "${WORKERS[@]}"; do
  count=$(echo -n "${BATCHES[$worker]}" | grep -c '^' || echo 0)
  log "  $worker: $count items"
done

if [[ "$DRY_RUN" == "true" ]]; then
  log "DRY RUN: Exiting without execution"
  exit 0
fi

# ============================================================================
# EXECUTE ON WORKERS
# ============================================================================

log ""
log "Launching independent Claude Code sessions on workers..."

mkdir -p "$OUTPUT_DIR"

# Launch workers in parallel
pids=()

for worker in "${WORKERS[@]}"; do
  # Get batch for this worker
  batch_items="${BATCHES[$worker]}"
  [[ -z "$batch_items" ]] && continue

  # Convert batch to JSON array
  batch_json=$(echo "$batch_items" | jq -R -s -c 'split("\n") | map(select(length > 0))')

  # Build args JSON
  args_json=$(jq -n \
    --argjson items "$batch_json" \
    --arg workflow "$WORKFLOW" \
    '{items: $items, workflow: $workflow}')

  # Output file on worker (local /tmp)
  output_file="/tmp/${SESSION_ID}-${worker}.json"

  # Build remote command
  remote_cmd="cd '$PROJECT_DIR' && claude --workflow '$WORKFLOW' --args '$args_json' > '$output_file' 2>&1"

  log "  $worker: starting..."

  # Execute via SSH (background)
  ssh -o BatchMode=yes \
      -o StrictHostKeyChecking=accept-new \
      -o ConnectTimeout=5 \
      "$worker" \
      "$remote_cmd" &

  pids+=($!)
done

# ============================================================================
# WAIT FOR WORKERS
# ============================================================================

log ""
log "Waiting for workers to complete (timeout: ${TIMEOUT}s)..."

# Wait with timeout
start_time=$(date +%s)
failed_workers=()

for i in "${!pids[@]}"; do
  pid="${pids[$i]}"
  worker="${WORKERS[$i]}"

  # Wait for this PID with timeout
  elapsed=$(($(date +%s) - start_time))
  remaining=$((TIMEOUT - elapsed))

  if [[ $remaining -le 0 ]]; then
    log "  $worker: TIMEOUT"
    kill "$pid" 2>/dev/null || true
    failed_workers+=("$worker")
    continue
  fi

  if wait "$pid"; then
    log "  $worker: SUCCESS"
  else
    log "  $worker: FAILED (exit $?)"
    failed_workers+=("$worker")
  fi
done

# ============================================================================
# COLLECT RESULTS
# ============================================================================

log ""
log "Collecting results from workers..."

successful_workers=()

for worker in "${WORKERS[@]}"; do
  output_file="/tmp/${SESSION_ID}-${worker}.json"
  local_output="$OUTPUT_DIR/${worker}.json"

  # Fetch output from worker
  if ssh -o BatchMode=yes \
         -o ConnectTimeout=5 \
         "$worker" \
         "cat '$output_file' 2>/dev/null && rm -f '$output_file'" \
         > "$local_output" 2>/dev/null; then
    log "  $worker: collected results"
    successful_workers+=("$worker")
  else
    log "  $worker: failed to collect results"
    failed_workers+=("$worker")
  fi
done

# ============================================================================
# MERGE RESULTS
# ============================================================================

if [[ ${#successful_workers[@]} -eq 0 ]]; then
  error "All workers failed: ${failed_workers[*]}"
fi

log ""
log "Merging results from ${#successful_workers[@]} workers..."

# Merge JSON outputs (simple concatenation of arrays)
merged_output="$OUTPUT_DIR/merged-result.json"

# Build merged JSON
jq -s '{
  workers_used: length,
  results: map(.) | add,
  workers: [.[].worker_hostname] | unique,
  timestamp: now | todate
}' "$OUTPUT_DIR"/*.json > "$merged_output"

log "Results merged: $merged_output"

# ============================================================================
# SUMMARY
# ============================================================================

log ""
log "=========================================="
log "FLEET MULTI-SESSION EXECUTION COMPLETE"
log "=========================================="
log "Workflow: $WORKFLOW"
log "Items: ${#ITEMS[@]}"
log "Workers used: ${#successful_workers[@]}/${#WORKERS[@]}"
log "Failed: ${#failed_workers[@]}"
[[ ${#failed_workers[@]} -gt 0 ]] && log "Failed workers: ${failed_workers[*]}"
log "Results: $merged_output"
log "=========================================="

# Print merged result
cat "$merged_output"
