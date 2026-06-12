#!/bin/bash
# =============================================================================
# fleet-bulk-lib.sh - Common Fleet Orchestration Library
# =============================================================================
# Shared functions for all bulk fleet skills.
# Provides: fleet discovery, batch distribution, worker dispatch,
#           progress monitoring, error handling, and result merging.
#
# Source this file in any bulk skill script:
#   source "$(dirname "$0")/fleet-bulk-lib.sh"
#
# Depends on:
#   - ~/.claude/fleet.json (fleet configuration)
#   - SSH access to fleet workers (key-based, BatchMode)
#   - NFS-shared ~/Development across all machines
#   - claude CLI installed on all workers
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

FLEET_CONFIG="${HOME}/.claude/fleet.json"
NFS_ROOT="${HOME}/Development"
SKILLS_DIR="${HOME}/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"

# Vertex AI environment variables (required for Claude Code with Vertex)
export ANTHROPIC_VERTEX_PROJECT_ID="${ANTHROPIC_VERTEX_PROJECT_ID:-itpc-gcp-uie-eng-claude}"
export CLAUDE_CODE_USE_VERTEX="${CLAUDE_CODE_USE_VERTEX:-1}"
export GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-True}"

# Worker hostnames (from fleet.json, role=worker)
FLEET_WORKERS=()

# Result collection directory
FLEET_RESULTS_DIR=""

# Progress tracking
FLEET_PROGRESS_DIR=""

# Logging
FLEET_LOG_FILE=""

# Colors (ANSI)
readonly C_RED='\033[0;31m'
readonly C_GREEN='\033[0;32m'
readonly C_YELLOW='\033[1;33m'
readonly C_BLUE='\033[0;34m'
readonly C_CYAN='\033[0;36m'
readonly C_BOLD='\033[1m'
readonly C_DIM='\033[2m'
readonly C_RESET='\033[0m'

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

fleet_log() {
  local level="$1"
  shift
  local msg="$*"
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')

  case "$level" in
    INFO)    echo -e "${C_BLUE}[${ts}]${C_RESET} ${C_BOLD}INFO${C_RESET}  $msg" ;;
    OK)      echo -e "${C_GREEN}[${ts}]${C_RESET} ${C_GREEN}OK${C_RESET}    $msg" ;;
    WARN)    echo -e "${C_YELLOW}[${ts}]${C_RESET} ${C_YELLOW}WARN${C_RESET}  $msg" ;;
    ERROR)   echo -e "${C_RED}[${ts}]${C_RESET} ${C_RED}ERROR${C_RESET} $msg" ;;
    PHASE)   echo -e "\n${C_CYAN}[${ts}]${C_RESET} ${C_CYAN}${C_BOLD}=== $msg ===${C_RESET}" ;;
    WORKER)  echo -e "${C_DIM}[${ts}]${C_RESET} ${C_DIM}WORKER${C_RESET} $msg" ;;
  esac

  # Also append to log file if set
  if [[ -n "${FLEET_LOG_FILE:-}" ]]; then
    echo "[${ts}] ${level} ${msg}" >> "$FLEET_LOG_FILE"
  fi
}

# ---------------------------------------------------------------------------
# FLEET DISCOVERY
# ---------------------------------------------------------------------------

# Discover online fleet workers from fleet.json
# Sets FLEET_WORKERS array with hostnames of healthy workers.
# Args: none (reads from FLEET_CONFIG)
fleet_discover_workers() {
  fleet_log PHASE "Fleet Discovery"

  if [[ ! -f "$FLEET_CONFIG" ]]; then
    fleet_log ERROR "Fleet config not found: $FLEET_CONFIG"
    return 1
  fi

  # Extract worker hostnames from fleet.json
  local all_workers
  all_workers=$(python3 -c "
import json, sys
with open('${FLEET_CONFIG}') as f:
    cfg = json.load(f)
for m in cfg.get('machines', []):
    if m.get('role') == 'worker':
        print(m['hostname'])
" 2>/dev/null)

  if [[ -z "$all_workers" ]]; then
    fleet_log ERROR "No workers found in fleet.json"
    return 1
  fi

  # Health check each worker via SSH probe
  FLEET_WORKERS=()
  local total=0
  local online=0

  while IFS= read -r hostname; do
    total=$((total + 1))
    if ssh -o ConnectTimeout=3 -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
         "$hostname" 'echo ok' &>/dev/null; then
      FLEET_WORKERS+=("$hostname")
      online=$((online + 1))
      fleet_log OK "Worker ${hostname}: ONLINE"
    else
      fleet_log WARN "Worker ${hostname}: OFFLINE (skipping)"
    fi
  done <<< "$all_workers"

  fleet_log INFO "Fleet: ${online}/${total} workers online: ${FLEET_WORKERS[*]}"

  if [[ ${#FLEET_WORKERS[@]} -eq 0 ]]; then
    fleet_log ERROR "No workers online -- cannot distribute"
    return 1
  fi

  return 0
}

# ---------------------------------------------------------------------------
# COMPLIANCE CHECK
# ---------------------------------------------------------------------------

# Verify current directory is not under forbidden paths
fleet_check_compliance() {
  local cwd
  cwd=$(realpath "$(pwd)")

  local forbidden
  forbidden=$(python3 -c "
import json
with open('${FLEET_CONFIG}') as f:
    cfg = json.load(f)
for p in cfg.get('compliance', {}).get('forbidden_paths', []):
    print(p)
" 2>/dev/null)

  while IFS= read -r fp; do
    if [[ -n "$fp" && "$cwd" == "$fp"* ]]; then
      fleet_log ERROR "COMPLIANCE VIOLATION: Cannot use fleet in $cwd"
      fleet_log ERROR "Forbidden path: $fp"
      return 1
    fi
  done <<< "$forbidden"

  return 0
}

# ---------------------------------------------------------------------------
# SETUP
# ---------------------------------------------------------------------------

# Initialize fleet session directories.
# Args:
#   $1 - skill name (e.g., "pdf-ingest", "url-learn")
#   $2 - (optional) custom output directory
fleet_init_session() {
  local skill_name="$1"
  local custom_output="${2:-}"
  local session_id
  session_id="$(date +%Y%m%d-%H%M%S)-$$"

  # Results directory (NFS-visible so workers can write)
  if [[ -n "$custom_output" ]]; then
    FLEET_RESULTS_DIR="$custom_output"
  else
    FLEET_RESULTS_DIR="${NFS_ROOT}/fleet-results/${skill_name}/${session_id}"
  fi
  mkdir -p "$FLEET_RESULTS_DIR"

  # Progress tracking directory (NFS-visible)
  FLEET_PROGRESS_DIR="${FLEET_RESULTS_DIR}/.progress"
  mkdir -p "$FLEET_PROGRESS_DIR"

  # Log file
  FLEET_LOG_FILE="${FLEET_RESULTS_DIR}/fleet.log"
  touch "$FLEET_LOG_FILE"

  fleet_log INFO "Session: ${session_id}"
  fleet_log INFO "Results: ${FLEET_RESULTS_DIR}"
  fleet_log INFO "Progress: ${FLEET_PROGRESS_DIR}"
  fleet_log INFO "Log: ${FLEET_LOG_FILE}"
}

# ---------------------------------------------------------------------------
# BATCH DISTRIBUTION
# ---------------------------------------------------------------------------

# Distribute items across workers using round-robin.
# Writes per-worker batch files to FLEET_RESULTS_DIR.
# Args:
#   $1 - path to file containing items (one per line)
# Outputs:
#   Creates $FLEET_RESULTS_DIR/batch-<hostname>.txt for each worker
#   Prints distribution summary
fleet_distribute_roundrobin() {
  local items_file="$1"
  local total
  total=$(wc -l < "$items_file")
  local num_workers=${#FLEET_WORKERS[@]}

  fleet_log PHASE "Distribute Items"
  fleet_log INFO "Total items: ${total}, Workers: ${num_workers}"

  # Create batch files
  local idx=0
  while IFS= read -r item; do
    local worker_idx=$((idx % num_workers))
    local worker="${FLEET_WORKERS[$worker_idx]}"
    echo "$item" >> "${FLEET_RESULTS_DIR}/batch-${worker}.txt"
    idx=$((idx + 1))
  done < "$items_file"

  # Log distribution
  for worker in "${FLEET_WORKERS[@]}"; do
    local batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
    if [[ -f "$batch_file" ]]; then
      local count
      count=$(wc -l < "$batch_file")
      fleet_log INFO "  ${worker}: ${count} items"
    else
      fleet_log WARN "  ${worker}: 0 items (no batch file)"
    fi
  done
}

# Distribute items weighted by worker memory.
# Workers with more memory get proportionally more items.
# Args:
#   $1 - path to file containing items (one per line)
fleet_distribute_weighted() {
  local items_file="$1"
  local total
  total=$(wc -l < "$items_file")

  fleet_log PHASE "Distribute Items (Weighted)"
  fleet_log INFO "Total items: ${total}, Workers: ${#FLEET_WORKERS[@]}"

  # Get memory per worker from fleet.json
  local worker_mem
  worker_mem=$(python3 -c "
import json
with open('${FLEET_CONFIG}') as f:
    cfg = json.load(f)
workers = {m['hostname']: m.get('memory_gb', 8) for m in cfg['machines'] if m['role'] == 'worker'}
for h in '${FLEET_WORKERS[*]}'.split():
    print(f'{h} {workers.get(h, 8)}')
" 2>/dev/null)

  # Calculate total memory
  local total_mem=0
  declare -A mem_map
  while IFS=' ' read -r host mem; do
    mem_map[$host]=$mem
    total_mem=$((total_mem + mem))
  done <<< "$worker_mem"

  # Read all items into array
  local -a items
  mapfile -t items < "$items_file"

  # Distribute proportionally
  local assigned=0
  local worker_count=${#FLEET_WORKERS[@]}
  local widx=0

  for worker in "${FLEET_WORKERS[@]}"; do
    widx=$((widx + 1))
    local mem=${mem_map[$worker]:-8}
    local share

    if [[ $widx -eq $worker_count ]]; then
      # Last worker gets remainder
      share=$((total - assigned))
    else
      share=$(python3 -c "import math; print(round(${mem} / ${total_mem} * ${total}))")
      # Clamp to remaining
      if [[ $((assigned + share)) -gt $total ]]; then
        share=$((total - assigned))
      fi
    fi

    # Write items for this worker
    local batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
    for ((i = assigned; i < assigned + share; i++)); do
      echo "${items[$i]}" >> "$batch_file"
    done

    fleet_log INFO "  ${worker} (${mem}GB): ${share} items"
    assigned=$((assigned + share))
  done
}

# ---------------------------------------------------------------------------
# WORKER DISPATCH
# ---------------------------------------------------------------------------

# Launch Claude Code sessions on workers via SSH.
# Each worker runs an independent Claude session processing its batch.
#
# Args:
#   $1 - skill slash-command name (e.g., "/ai-pdf-deep-research")
#   $2 - prompt template. Use {{ITEMS}} as placeholder for the items list,
#         {{BATCH_FILE}} for batch file path, {{OUTPUT_DIR}} for output dir,
#         {{WORKER}} for hostname.
#   $3 - (optional) max timeout in seconds per worker (default: 7200 = 2 hours)
#   $4 - (optional) permission mode (default: "default")
#
# Side effects:
#   - Launches background SSH processes
#   - Creates $FLEET_RESULTS_DIR/worker-<hostname>.pid
#   - Creates $FLEET_RESULTS_DIR/worker-<hostname>.out (stdout/stderr)
#   - Creates $FLEET_RESULTS_DIR/worker-<hostname>.status (exit code)
fleet_dispatch_workers() {
  local skill_cmd="$1"
  local prompt_template="$2"
  local timeout_sec="${3:-7200}"
  local perm_mode="${4:-default}"

  fleet_log PHASE "Dispatch Workers"

  local pids=()
  local hostnames=()

  for worker in "${FLEET_WORKERS[@]}"; do
    local batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
    if [[ ! -f "$batch_file" ]]; then
      fleet_log WARN "No batch for ${worker}, skipping"
      continue
    fi

    local items
    items=$(cat "$batch_file")
    local item_count
    item_count=$(wc -l < "$batch_file")

    local output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
    mkdir -p "$output_dir"

    # Build the prompt by replacing placeholders
    local prompt="$prompt_template"
    prompt="${prompt//\{\{ITEMS\}\}/$items}"
    prompt="${prompt//\{\{BATCH_FILE\}\}/$batch_file}"
    prompt="${prompt//\{\{OUTPUT_DIR\}\}/$output_dir}"
    prompt="${prompt//\{\{WORKER\}\}/$worker}"
    prompt="${prompt//\{\{ITEM_COUNT\}\}/$item_count}"

    local worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
    local worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"
    local worker_status_file="${FLEET_RESULTS_DIR}/worker-${worker}.status"

    fleet_log INFO "Launching on ${worker}: ${item_count} items, timeout=${timeout_sec}s"

    # Launch Claude Code session via SSH in background
    # Key flags:
    #   -p (print mode, non-interactive)
    #   --dangerously-skip-permissions (workers run unattended)
    #   --output-format json (structured output)
    #   --max-turns 200 (generous for bulk processing)
    #   --no-session-persistence (ephemeral, no disk clutter)
    (
      timeout "${timeout_sec}" \
        ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$worker" \
          "export ANTHROPIC_VERTEX_PROJECT_ID='${ANTHROPIC_VERTEX_PROJECT_ID:-itpc-gcp-uie-eng-claude}' && \
           export CLAUDE_CODE_USE_VERTEX='${CLAUDE_CODE_USE_VERTEX:-1}' && \
           export GOOGLE_GENAI_USE_VERTEXAI='${GOOGLE_GENAI_USE_VERTEXAI:-True}' && \
           cd '${NFS_ROOT}' && \
           claude -p \
            --dangerously-skip-permissions \
            --output-format json \
            --max-turns 200 \
            --no-session-persistence \
            '${prompt//\'/\'\\\'\'}'" \
        > "$worker_out" 2>&1
      echo \$? > "$worker_status_file"
    ) &

    local pid=$!
    echo "$pid" > "$worker_pid_file"
    pids+=("$pid")
    hostnames+=("$worker")

    fleet_log WORKER "${worker} PID=${pid}"
  done

  if [[ ${#pids[@]} -eq 0 ]]; then
    fleet_log ERROR "No workers dispatched"
    return 1
  fi

  fleet_log INFO "Dispatched ${#pids[@]} workers: ${hostnames[*]}"

  # Store for later use
  export FLEET_WORKER_PIDS=("${pids[@]}")
  export FLEET_WORKER_HOSTS=("${hostnames[@]}")
}

# Alternative dispatch: run a specific bash command on each worker
# (not a Claude session, but a raw command like grep, find, etc.)
# Args:
#   $1 - command template ({{BATCH_FILE}}, {{OUTPUT_DIR}}, {{WORKER}} placeholders)
#   $2 - (optional) timeout in seconds (default: 3600)
fleet_dispatch_raw() {
  local cmd_template="$1"
  local timeout_sec="${2:-3600}"

  fleet_log PHASE "Dispatch Workers (Raw Commands)"

  local pids=()
  local hostnames=()

  for worker in "${FLEET_WORKERS[@]}"; do
    local batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
    if [[ ! -f "$batch_file" ]]; then
      fleet_log WARN "No batch for ${worker}, skipping"
      continue
    fi

    local output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
    mkdir -p "$output_dir"

    local cmd="$cmd_template"
    cmd="${cmd//\{\{BATCH_FILE\}\}/$batch_file}"
    cmd="${cmd//\{\{OUTPUT_DIR\}\}/$output_dir}"
    cmd="${cmd//\{\{WORKER\}\}/$worker}"

    local worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
    local worker_status_file="${FLEET_RESULTS_DIR}/worker-${worker}.status"
    local worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"

    fleet_log INFO "Launching raw command on ${worker}"

    (
      timeout "${timeout_sec}" \
        ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$worker" \
          "$cmd" \
        > "$worker_out" 2>&1
      echo $? > "$worker_status_file"
    ) &

    local pid=$!
    echo "$pid" > "$worker_pid_file"
    pids+=("$pid")
    hostnames+=("$worker")
  done

  export FLEET_WORKER_PIDS=("${pids[@]}")
  export FLEET_WORKER_HOSTS=("${hostnames[@]}")

  fleet_log INFO "Dispatched ${#pids[@]} raw commands"
}

# ---------------------------------------------------------------------------
# WAIT AND MONITOR
# ---------------------------------------------------------------------------

# Wait for all dispatched workers to complete.
# Shows progress updates every $1 seconds.
# Args:
#   $1 - (optional) progress check interval in seconds (default: 30)
fleet_wait_workers() {
  local interval="${1:-30}"

  fleet_log PHASE "Waiting for Workers"

  if [[ ${#FLEET_WORKER_PIDS[@]} -eq 0 ]]; then
    fleet_log WARN "No worker PIDs to wait for"
    return 0
  fi

  local total=${#FLEET_WORKER_PIDS[@]}
  local completed=0
  local failed=0
  local start_time
  start_time=$(date +%s)

  while [[ $completed -lt $total ]]; do
    completed=0
    failed=0

    for i in "${!FLEET_WORKER_PIDS[@]}"; do
      local pid="${FLEET_WORKER_PIDS[$i]}"
      local host="${FLEET_WORKER_HOSTS[$i]}"
      local status_file="${FLEET_RESULTS_DIR}/worker-${host}.status"

      if ! kill -0 "$pid" 2>/dev/null; then
        completed=$((completed + 1))
        if [[ -f "$status_file" ]]; then
          local exit_code
          exit_code=$(cat "$status_file")
          if [[ "$exit_code" != "0" ]]; then
            failed=$((failed + 1))
          fi
        fi
      fi
    done

    local elapsed=$(( $(date +%s) - start_time ))
    local elapsed_min=$(( elapsed / 60 ))
    local elapsed_sec=$(( elapsed % 60 ))

    fleet_log INFO "Progress: ${completed}/${total} workers done (${failed} failed) [${elapsed_min}m${elapsed_sec}s elapsed]"

    # Check progress files if available
    if [[ -d "$FLEET_PROGRESS_DIR" ]]; then
      for pfile in "$FLEET_PROGRESS_DIR"/progress-*.json; do
        if [[ -f "$pfile" ]]; then
          local phost
          phost=$(basename "$pfile" | sed 's/progress-//;s/\.json//')
          local pcontent
          pcontent=$(cat "$pfile" 2>/dev/null || echo '{}')
          fleet_log WORKER "${phost}: ${pcontent}"
        fi
      done
    fi

    if [[ $completed -lt $total ]]; then
      sleep "$interval"
    fi
  done

  # Final status report
  local end_time
  end_time=$(date +%s)
  local total_elapsed=$(( end_time - start_time ))
  local total_min=$(( total_elapsed / 60 ))
  local total_sec=$(( total_elapsed % 60 ))

  fleet_log INFO "All workers complete: ${total} total, ${failed} failed [${total_min}m${total_sec}s]"

  # Return failure count
  return "$failed"
}

# ---------------------------------------------------------------------------
# RESULT COLLECTION
# ---------------------------------------------------------------------------

# Collect and report worker results.
# Returns 0 if majority succeeded, 1 if majority failed.
fleet_collect_results() {
  fleet_log PHASE "Collect Results"

  local total=${#FLEET_WORKER_HOSTS[@]}
  local succeeded=0
  local failed=0
  local failed_hosts=()

  for host in "${FLEET_WORKER_HOSTS[@]}"; do
    local status_file="${FLEET_RESULTS_DIR}/worker-${host}.status"
    local out_file="${FLEET_RESULTS_DIR}/worker-${host}.out"

    if [[ -f "$status_file" ]]; then
      local exit_code
      exit_code=$(cat "$status_file")
      if [[ "$exit_code" == "0" ]]; then
        succeeded=$((succeeded + 1))
        fleet_log OK "${host}: SUCCESS"
      else
        failed=$((failed + 1))
        failed_hosts+=("$host")
        fleet_log ERROR "${host}: FAILED (exit ${exit_code})"
        if [[ -f "$out_file" ]]; then
          fleet_log ERROR "  Last 5 lines of output:"
          tail -5 "$out_file" | while IFS= read -r line; do
            fleet_log ERROR "    ${line}"
          done
        fi
      fi
    else
      failed=$((failed + 1))
      failed_hosts+=("$host")
      fleet_log ERROR "${host}: NO STATUS (possibly killed/timeout)"
    fi
  done

  fleet_log INFO "Results: ${succeeded}/${total} succeeded, ${failed}/${total} failed"

  if [[ ${#failed_hosts[@]} -gt 0 ]]; then
    fleet_log WARN "Failed workers: ${failed_hosts[*]}"
  fi

  # Majority failure check
  local threshold=$(( (total + 1) / 2 ))
  if [[ $failed -ge $threshold ]]; then
    fleet_log ERROR "MAJORITY FAILURE: ${failed}/${total} workers failed"
    return 1
  fi

  return 0
}

# ---------------------------------------------------------------------------
# RESULT MERGING
# ---------------------------------------------------------------------------

# Merge JSON output files from all workers into a single array.
# Args:
#   $1 - output file path for merged JSON
#   $2 - (optional) JSON key to extract from each worker output (default: entire output)
fleet_merge_json() {
  local output_file="$1"
  local json_key="${2:-}"

  fleet_log PHASE "Merge Results (JSON)"

  local merged_items=()

  for host in "${FLEET_WORKER_HOSTS[@]}"; do
    local out_file="${FLEET_RESULTS_DIR}/worker-${host}.out"
    if [[ ! -f "$out_file" ]]; then
      fleet_log WARN "No output from ${host}"
      continue
    fi

    # Try to extract JSON from worker output
    # Claude --output-format json wraps result in {"result": "...", "cost_usd": ...}
    local worker_json
    if [[ -n "$json_key" ]]; then
      worker_json=$(python3 -c "
import json, sys
try:
    data = json.load(open('${out_file}'))
    result = data.get('result', data)
    if isinstance(result, str):
        result = json.loads(result)
    items = result.get('${json_key}', [])
    if isinstance(items, list):
        for item in items:
            print(json.dumps(item))
    else:
        print(json.dumps(items))
except Exception as e:
    print(json.dumps({'error': str(e), 'host': '${host}'}), file=sys.stderr)
" 2>>"${FLEET_LOG_FILE}")
    else
      worker_json=$(python3 -c "
import json, sys
try:
    data = json.load(open('${out_file}'))
    result = data.get('result', data)
    if isinstance(result, str):
        result = json.loads(result)
    if isinstance(result, list):
        for item in result:
            print(json.dumps(item))
    else:
        print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e), 'host': '${host}'}), file=sys.stderr)
" 2>>"${FLEET_LOG_FILE}")
    fi

    if [[ -n "$worker_json" ]]; then
      while IFS= read -r line; do
        merged_items+=("$line")
      done <<< "$worker_json"
    fi
  done

  # Write merged JSON array
  (
    echo "["
    local count=0
    local total=${#merged_items[@]}
    for item in "${merged_items[@]}"; do
      count=$((count + 1))
      if [[ $count -lt $total ]]; then
        echo "  ${item},"
      else
        echo "  ${item}"
      fi
    done
    echo "]"
  ) > "$output_file"

  fleet_log OK "Merged ${#merged_items[@]} items into ${output_file}"
}

# Merge markdown output files from all workers into a single file.
# Args:
#   $1 - output file path for merged markdown
#   $2 - (optional) section separator (default: "---")
fleet_merge_markdown() {
  local output_file="$1"
  local separator="${2:----}"

  fleet_log PHASE "Merge Results (Markdown)"

  local count=0

  for host in "${FLEET_WORKER_HOSTS[@]}"; do
    local out_file="${FLEET_RESULTS_DIR}/worker-${host}.out"
    local output_dir="${FLEET_RESULTS_DIR}/output-${host}"

    # Check for markdown files in output directory
    if [[ -d "$output_dir" ]]; then
      for md_file in "$output_dir"/*.md; do
        if [[ -f "$md_file" ]]; then
          if [[ $count -gt 0 ]]; then
            echo -e "\n${separator}\n" >> "$output_file"
          fi
          cat "$md_file" >> "$output_file"
          count=$((count + 1))
        fi
      done
    fi

    # If no markdown files in output dir, try extracting from worker output
    if [[ $count -eq 0 && -f "$out_file" ]]; then
      # Try to extract result text from Claude JSON output
      local result_text
      result_text=$(python3 -c "
import json
try:
    data = json.load(open('${out_file}'))
    result = data.get('result', '')
    if isinstance(result, str):
        print(result)
    elif isinstance(result, dict):
        print(result.get('narrative', result.get('report', json.dumps(result, indent=2))))
    else:
        print(str(result))
except:
    with open('${out_file}') as f:
        print(f.read())
" 2>/dev/null)

      if [[ -n "$result_text" ]]; then
        if [[ $count -gt 0 ]]; then
          echo -e "\n${separator}\n" >> "$output_file"
        fi
        echo "## Results from ${host}" >> "$output_file"
        echo "" >> "$output_file"
        echo "$result_text" >> "$output_file"
        count=$((count + 1))
      fi
    fi
  done

  fleet_log OK "Merged ${count} sections into ${output_file}"
}

# Merge per-file outputs (each worker produced files, collect them all).
# Args:
#   $1 - target directory to collect all output files
fleet_merge_files() {
  local target_dir="$1"

  fleet_log PHASE "Merge Results (Files)"
  mkdir -p "$target_dir"

  local count=0

  for host in "${FLEET_WORKER_HOSTS[@]}"; do
    local output_dir="${FLEET_RESULTS_DIR}/output-${host}"
    if [[ -d "$output_dir" ]]; then
      local file_count
      file_count=$(find "$output_dir" -type f | wc -l)
      if [[ $file_count -gt 0 ]]; then
        cp -r "$output_dir"/* "$target_dir"/ 2>/dev/null || true
        count=$((count + file_count))
        fleet_log INFO "  ${host}: ${file_count} files"
      fi
    fi
  done

  fleet_log OK "Collected ${count} files into ${target_dir}"
}

# ---------------------------------------------------------------------------
# PROGRESS TRACKING
# ---------------------------------------------------------------------------

# Write progress update for a worker (called FROM worker context via NFS)
# Args:
#   $1 - worker hostname
#   $2 - items completed
#   $3 - items total
#   $4 - (optional) current item name
fleet_update_progress() {
  local worker="$1"
  local completed="$2"
  local total="$3"
  local current="${4:-}"

  if [[ -d "${FLEET_PROGRESS_DIR}" ]]; then
    cat > "${FLEET_PROGRESS_DIR}/progress-${worker}.json" << PROGRESS_EOF
{"worker":"${worker}","completed":${completed},"total":${total},"current":"${current}","timestamp":"$(date -Iseconds)"}
PROGRESS_EOF
  fi
}

# Read aggregated progress from all workers
fleet_read_progress() {
  if [[ ! -d "${FLEET_PROGRESS_DIR}" ]]; then
    echo "No progress directory"
    return
  fi

  local total_completed=0
  local total_items=0

  for pfile in "$FLEET_PROGRESS_DIR"/progress-*.json; do
    if [[ -f "$pfile" ]]; then
      local pdata
      pdata=$(cat "$pfile" 2>/dev/null || echo '{}')
      local completed
      completed=$(echo "$pdata" | python3 -c "import json,sys; print(json.load(sys.stdin).get('completed',0))" 2>/dev/null || echo 0)
      local total
      total=$(echo "$pdata" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo 0)
      total_completed=$((total_completed + completed))
      total_items=$((total_items + total))
    fi
  done

  if [[ $total_items -gt 0 ]]; then
    local pct=$((total_completed * 100 / total_items))
    echo "${total_completed}/${total_items} (${pct}%)"
  else
    echo "0/0 (0%)"
  fi
}

# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------

# Send notification via ntfy (if available)
# Args:
#   $1 - title
#   $2 - message
#   $3 - (optional) priority (default, low, high, urgent)
fleet_notify() {
  local title="$1"
  local message="$2"
  local priority="${3:-default}"

  # Check if ntfy topic is configured
  local ntfy_topic="${FLEET_NTFY_TOPIC:-}"
  if [[ -z "$ntfy_topic" ]]; then
    return 0  # silently skip if not configured
  fi

  curl -s \
    -H "Title: ${title}" \
    -H "Priority: ${priority}" \
    -d "${message}" \
    "https://ntfy.sh/${ntfy_topic}" &>/dev/null || true
}

# ---------------------------------------------------------------------------
# DRY RUN
# ---------------------------------------------------------------------------

# Show distribution plan without executing
# Args:
#   $1 - skill name
fleet_dry_run_report() {
  local skill_name="$1"

  fleet_log PHASE "DRY RUN REPORT: ${skill_name}"

  echo ""
  echo "Fleet Workers: ${FLEET_WORKERS[*]}"
  echo ""
  echo "Distribution:"

  for worker in "${FLEET_WORKERS[@]}"; do
    local batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
    if [[ -f "$batch_file" ]]; then
      local count
      count=$(wc -l < "$batch_file")
      echo "  ${worker}: ${count} items"
      echo "    First 3:"
      head -3 "$batch_file" | while IFS= read -r item; do
        echo "      - ${item}"
      done
      if [[ $count -gt 3 ]]; then
        echo "      ... and $((count - 3)) more"
      fi
    fi
  done

  echo ""
  echo "Results would be written to: ${FLEET_RESULTS_DIR}"
  echo ""
  echo "To execute for real, remove --dry-run flag."
}

# ---------------------------------------------------------------------------
# CLEANUP
# ---------------------------------------------------------------------------

# Kill any remaining worker processes
fleet_cleanup() {
  if [[ ${#FLEET_WORKER_PIDS[@]:-0} -gt 0 ]]; then
    for pid in "${FLEET_WORKER_PIDS[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        fleet_log WARN "Killing remaining worker PID=${pid}"
        kill "$pid" 2>/dev/null || true
      fi
    done
  fi
}

# Trap cleanup on script exit
trap fleet_cleanup EXIT

# ---------------------------------------------------------------------------
# SUMMARY REPORT
# ---------------------------------------------------------------------------

# Print final summary with timing and results
# Args:
#   $1 - skill name
#   $2 - start timestamp (from `date +%s`)
#   $3 - total items processed
fleet_summary() {
  local skill_name="$1"
  local start_ts="$2"
  local total_items="$3"

  local end_ts
  end_ts=$(date +%s)
  local elapsed=$((end_ts - start_ts))
  local elapsed_min=$((elapsed / 60))
  local elapsed_sec=$((elapsed % 60))

  local per_item=0
  if [[ $total_items -gt 0 ]]; then
    per_item=$((elapsed / total_items))
  fi

  echo ""
  echo "=================================================================="
  echo "  FLEET BULK ${skill_name} COMPLETE"
  echo "=================================================================="
  echo "  Workers:    ${#FLEET_WORKER_HOSTS[@]}"
  echo "  Items:      ${total_items}"
  echo "  Time:       ${elapsed_min}m ${elapsed_sec}s"
  echo "  Per item:   ~${per_item}s"
  echo "  Results:    ${FLEET_RESULTS_DIR}"
  echo "  Log:        ${FLEET_LOG_FILE}"
  echo "=================================================================="
  echo ""
}

# ---------------------------------------------------------------------------
# ARGUMENT PARSING HELPERS
# ---------------------------------------------------------------------------

# Parse common fleet bulk arguments.
# Sets global variables: DRY_RUN, DISTRIBUTION, TIMEOUT, OUTPUT_DIR
DRY_RUN=false
DISTRIBUTION="roundrobin"
WORKER_TIMEOUT=7200
OUTPUT_DIR=""

fleet_parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --distribution)
        DISTRIBUTION="$2"
        shift 2
        ;;
      --timeout)
        WORKER_TIMEOUT="$2"
        shift 2
        ;;
      --output|-o)
        OUTPUT_DIR="$2"
        shift 2
        ;;
      --notify)
        export FLEET_NTFY_TOPIC="$2"
        shift 2
        ;;
      *)
        # Pass through to caller
        break
        ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# NFS HELPERS
# ---------------------------------------------------------------------------

# Check if a path is on NFS (visible to all workers)
fleet_is_nfs() {
  local path="$1"
  [[ "$path" == "${NFS_ROOT}"* ]]
}

# Resolve path to NFS-visible path
fleet_nfs_path() {
  local path="$1"
  if fleet_is_nfs "$path"; then
    echo "$path"
  else
    fleet_log WARN "Path ${path} is not on NFS -- workers may not be able to access it"
    echo "$path"
  fi
}
