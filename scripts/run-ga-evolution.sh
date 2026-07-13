#!/bin/bash
# Fleet-wide GA Evolution Runner
# Distributes GA tools across workers in parallel, collects results.
# Designed for cron: run periodically to evolve strategies with fresh data.
#
# Usage: ./run-ga-evolution.sh [--quick]
#   --quick: Run with smaller populations (for testing)

set -euo pipefail

TOOLS_DIR="/mnt/aio-01/claude-orchestrator/tools"
LOG_DIR="/home/claude/workers"
API_BASE="http://aio-01:5000"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)

WORKERS=(server-01 server-02 server-03 pi-01 desktop-ap server-ap)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Check API health
if ! curl -sf "${API_BASE}/health" >/dev/null 2>&1; then
    log "ERROR: API at ${API_BASE} is not healthy. Aborting."
    exit 1
fi

log "Starting fleet-wide GA evolution run (${TIMESTAMP})"
log "Workers: ${WORKERS[*]}"

# Assignments: worker -> (script, log_name)
declare -A ASSIGNMENTS=(
    ["server-01"]="genetic_model_optimizer.py|ga-model-optimizer"
    ["server-02"]="ga_team_selection_fixed.py|ga-team-selection"
    ["server-03"]="ga_engine.py|ga-fleet-evolution"
    ["pi-01"]="ga_training_data_curator.py|ga-training-curator"
    ["desktop-ap"]="ga_prompt_evolution_fixed.py|ga-prompt-evolution"
    ["server-ap"]="ga_adversarial_verification_fixed.py|ga-adversarial"
)

# Launch on each worker
PIDS=()
for worker in "${WORKERS[@]}"; do
    IFS='|' read -r script logname <<< "${ASSIGNMENTS[$worker]}"
    logfile="${LOG_DIR}/${logname}-${TIMESTAMP}.log"

    log "Launching ${script} on ${worker}..."
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "claude@${worker}" \
        "cd ${TOOLS_DIR}/.. && python3 tools/${script}" \
        > "/tmp/ga-${worker}-${TIMESTAMP}.log" 2>&1 &
    PIDS+=($!)
done

log "All ${#PIDS[@]} GA tools launched. Waiting for completion..."

# Wait for all with timeout (30 minutes max)
TIMEOUT=1800
START=$SECONDS
FAILED=0
COMPLETED=0

for i in "${!PIDS[@]}"; do
    pid=${PIDS[$i]}
    worker=${WORKERS[$i]}

    remaining=$((TIMEOUT - (SECONDS - START)))
    if [ $remaining -le 0 ]; then
        log "TIMEOUT: Killing remaining processes"
        kill "${PIDS[@]}" 2>/dev/null || true
        break
    fi

    if wait "$pid" 2>/dev/null; then
        COMPLETED=$((COMPLETED + 1))
        log "  ${worker}: completed successfully"
    else
        FAILED=$((FAILED + 1))
        log "  ${worker}: FAILED (exit code $?)"
        tail -5 "/tmp/ga-${worker}-${TIMESTAMP}.log" 2>/dev/null || true
    fi
done

ELAPSED=$((SECONDS - START))

# Collect results summary
log ""
log "=== GA EVOLUTION SUMMARY ==="
log "Duration: ${ELAPSED}s"
log "Completed: ${COMPLETED}/${#WORKERS[@]}"
log "Failed: ${FAILED}"

# Query stored results
log ""
log "Current best solutions:"
curl -sf "${API_BASE}/ga/best-solutions" 2>/dev/null | python3 -c "
import sys, json
try:
    solutions = json.load(sys.stdin)
    for s in solutions[:10]:
        notes = s.get('notes') or ''
        fitness = s.get('fitness') or 0
        print(f'  {s[\"use_case\"]}: fitness={fitness:.3f}')
except: pass
" 2>/dev/null || true

log ""
log "GA evolution run complete."
