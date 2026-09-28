#!/bin/bash
# GA Tuning Scheduler - runs genetic algorithm parameter optimization
# Executes Sunday 2 AM, updates settings.json with optimized parameters
# Maintains zero API call overhead

set -e

# Resolve symlink to actual script location
if [ -L "${BASH_SOURCE[0]}" ]; then
  SCRIPT_REAL="$( readlink -f "${BASH_SOURCE[0]}" )"
else
  SCRIPT_REAL="${BASH_SOURCE[0]}"
fi

# Get repo root (parent of tools/ directory)
REPO_ROOT="$( cd "$( dirname "$SCRIPT_REAL" )/.." && pwd )"

WORK_DIR="/tmp/ga-tuning-work"
LOG_FILE="$REPO_ROOT/tools/ga-tuning-schedule.log"
EVOLUTION_LOG="$REPO_ROOT/ga_tuning/parameter_evolution.md"

# Create working directory
mkdir -p "$WORK_DIR"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== GA Tuning Scheduled Run ==="
log "Repo root: $REPO_ROOT"
log "Working directory: $WORK_DIR"

# Step 1: Run GA optimization (zero API calls)
log "Step 1: Running genetic algorithm optimization..."
if ! python3 "$REPO_ROOT/ga_tuning/ga_tuner.py" > "$WORK_DIR/ga_output.json" 2>&1; then
  log "ERROR: GA tuning failed"
  cat "$WORK_DIR/ga_output.json" >> "$LOG_FILE"
  exit 1
fi

log "Step 2: Extracting optimized parameters..."
if ! python3 "$REPO_ROOT/ga_tuning/extract_and_apply_parameters.py" \
  --ga-output "$WORK_DIR/ga_output.json" \
  --settings-path "$REPO_ROOT/settings.json" \
  --evolution-log "$EVOLUTION_LOG" 2>&1 | tee -a "$LOG_FILE"; then
  log "ERROR: Parameter extraction failed"
  exit 1
fi

log "Step 3: Validating updated settings..."
if ! python3 -c "
import json
import sys

try:
    with open('$REPO_ROOT/settings.json') as f:
        settings = json.load(f)

    print('[Settings] Valid JSON structure')
    print(f'[Settings] Compression level: {settings.get(\"compression_level\", \"missing\")}')
    print(f'[Settings] Cache TTL: {settings.get(\"ga_tuning_cache_ttl\", \"missing\")} seconds')

except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"; then
  log "ERROR: Settings validation failed"
  exit 1
fi

log "Step 4: Logging evolution..."
if [ -f "$EVOLUTION_LOG" ]; then
  log "Evolution logged to: $EVOLUTION_LOG"
  head -3 "$EVOLUTION_LOG" | sed 's/^/[Evolution] /'
fi

log "✅ GA Tuning Complete"
log "Next run: Sunday 2:00 AM"

# Cleanup
rm -rf "$WORK_DIR" 2>/dev/null || true

exit 0
