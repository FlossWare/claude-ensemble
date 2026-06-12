#!/bin/bash
# =============================================================================
# bulk-research.sh - Fleet-Distributed Deep Research
# =============================================================================
# Distributes deep research topics across fleet workers (3 sessions).
# Each worker runs independent Claude Code sessions processing its topics
# with /deep-research (web search + fetch + extract + verify).
#
# Architecture:
#   Controller (this script)
#     |-- SSH --> server-01: claude -p "research batch1 topics"
#     |-- SSH --> server-02: claude -p "research batch2 topics"
#     |-- SSH --> server-03: claude -p "research batch3 topics"
#     |
#     v
#   Wait for all workers -> Concatenate markdown reports
#
# Performance:
#   Per-topic: ~2 min (search + fetch 10 URLs + extract + verify)
#   Sequential: 100 topics * 2 min = 200 min = 3.3 hours
#   Fleet (3 workers): ~66 min (3x speedup)
#   Break-even: 15+ topics
#
# Usage:
#   ./bulk-research.sh topics.txt
#   ./bulk-research.sh "topic 1" "topic 2" "topic 3"
#   ./bulk-research.sh --topics topics.txt --output research-report.md
#   ./bulk-research.sh --dry-run topics.txt
#
# Options:
#   --dry-run              Show distribution plan without executing
#   --distribution <m>     roundrobin or weighted (default: roundrobin)
#   --timeout <sec>        Per-worker timeout (default: 7200 = 2h)
#   --output <dir>         Custom output directory
#   --notify <topic>       ntfy notification topic
#   --help                 Show this help
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/fleet-bulk-lib.sh"

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

WORKER_TIMEOUT=7200  # 2 hours per worker
DISTRIBUTION="roundrobin"  # Topics are roughly equal cost

# ---------------------------------------------------------------------------
# ARGUMENT PARSING
# ---------------------------------------------------------------------------

TOPIC_INPUTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)      DRY_RUN=true; shift ;;
    --distribution) DISTRIBUTION="$2"; shift 2 ;;
    --timeout)      WORKER_TIMEOUT="$2"; shift 2 ;;
    --output|-o)    OUTPUT_DIR="$2"; shift 2 ;;
    --notify)       export FLEET_NTFY_TOPIC="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS] <topics_file_or_topics...>"
      echo ""
      echo "Distribute deep research across fleet workers."
      echo ""
      echo "Options:"
      echo "  --dry-run             Show plan without executing"
      echo "  --distribution <m>    roundrobin or weighted (default: roundrobin)"
      echo "  --timeout <sec>       Per-worker timeout (default: 7200)"
      echo "  --output <dir>        Custom output directory"
      echo "  --notify <topic>      ntfy notification topic"
      echo ""
      echo "Input formats:"
      echo "  $0 topics.txt                         # File with one topic per line"
      echo "  $0 'quantum computing' 'dark matter'  # Topics as arguments"
      echo "  cat topics.txt | $0 -                 # Read from stdin"
      exit 0
      ;;
    *)
      TOPIC_INPUTS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#TOPIC_INPUTS[@]} -eq 0 ]]; then
  echo "ERROR: No topic inputs specified"
  echo "Usage: $0 [OPTIONS] <topics_file_or_topics...>"
  exit 1
fi

# ---------------------------------------------------------------------------
# RESOLVE TOPICS
# ---------------------------------------------------------------------------

ITEMS_FILE=$(mktemp /tmp/fleet-research-items-XXXXXX.txt)
_research_cleanup() { rm -f "$ITEMS_FILE"; }
trap _research_cleanup EXIT

for input in "${TOPIC_INPUTS[@]}"; do
  if [[ "$input" == "-" ]]; then
    cat >> "$ITEMS_FILE"
  elif [[ -f "$input" ]]; then
    grep -v '^\s*#' "$input" | grep -v '^\s*$' >> "$ITEMS_FILE"
  else
    # Direct topic string
    echo "$input" >> "$ITEMS_FILE"
  fi
done

TOTAL_TOPICS=$(wc -l < "$ITEMS_FILE")

if [[ $TOTAL_TOPICS -eq 0 ]]; then
  fleet_log ERROR "No topics found in input"
  exit 1
fi

echo ""
echo "=================================================================="
echo "  BULK DEEP RESEARCH"
echo "=================================================================="
echo "  Topics:  ${TOTAL_TOPICS}"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# FLEET SETUP
# ---------------------------------------------------------------------------

fleet_check_compliance
fleet_discover_workers

START_TIME=$(date +%s)
fleet_init_session "research" "${OUTPUT_DIR:-}"

if [[ "$DISTRIBUTION" == "weighted" ]]; then
  fleet_distribute_weighted "$ITEMS_FILE"
else
  fleet_distribute_roundrobin "$ITEMS_FILE"
fi

# ---------------------------------------------------------------------------
# DRY RUN
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "true" ]]; then
  fleet_dry_run_report "research"

  seq_min=$((TOTAL_TOPICS * 2))
  fleet_min=$((seq_min / ${#FLEET_WORKERS[@]}))
  echo "Estimated time:"
  echo "  Sequential: ~${seq_min}m"
  echo "  Fleet (${#FLEET_WORKERS[@]} workers): ~${fleet_min}m"
  echo "  Savings: ~$((seq_min - fleet_min))m"
  exit 0
fi

# ---------------------------------------------------------------------------
# DISPATCH WORKERS
# ---------------------------------------------------------------------------

fleet_log PHASE "Dispatch Research Workers"

FLEET_WORKER_PIDS=()
FLEET_WORKER_HOSTS=()

for worker in "${FLEET_WORKERS[@]}"; do
  batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
  if [[ ! -f "$batch_file" ]]; then
    continue
  fi

  item_count=$(wc -l < "$batch_file")
  output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
  mkdir -p "$output_dir"

  # Build JSON array of topics
  topics_json=$(python3 -c "
import json
with open('${batch_file}') as f:
    topics = [line.strip() for line in f if line.strip()]
print(json.dumps(topics))
")

  read -r -d '' worker_prompt << PROMPT_EOF || true
You are a fleet worker conducting deep research on multiple topics.

TASK: Research ${item_count} topics, one at a time.
OUTPUT DIRECTORY: ${output_dir}

TOPIC LIST (JSON array):
${topics_json}

INSTRUCTIONS:
1. For each topic in the list, run /deep-research with that topic as the query.
2. After each topic completes, save the research report to:
   ${output_dir}/topic-NNN.md (NNN = topic number: 001, 002, etc.)
   Include the topic as the first heading.
3. Write progress to ${FLEET_PROGRESS_DIR}/progress-${worker}.json after each topic:
   {"worker":"${worker}","completed":DONE,"total":${item_count},"current":"TOPIC_NAME"}
4. Research ALL ${item_count} topics. If one fails, log the error and continue.
5. At the end, write ${output_dir}/summary.json:
   {"worker":"${worker}","topics_completed":N,"total":${item_count},"status":"complete"}
PROMPT_EOF

  worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
  worker_status="${FLEET_RESULTS_DIR}/worker-${worker}.status"
  worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"

  fleet_log INFO "Launching on ${worker}: ${item_count} topics"

  escaped_prompt=$(echo "$worker_prompt" | sed "s/'/'\\\\''/g")

  (
    timeout "${WORKER_TIMEOUT}" \
      ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$worker" \
        "cd '${NFS_ROOT}' && claude -p \
          --dangerously-skip-permissions \
          --output-format text \
          --max-turns 500 \
          --no-session-persistence \
          '${escaped_prompt}'" \
      > "$worker_out" 2>&1
    echo $? > "$worker_status"
  ) &

  pid=$!
  echo "$pid" > "$worker_pid_file"
  FLEET_WORKER_PIDS+=("$pid")
  FLEET_WORKER_HOSTS+=("$worker")

  fleet_log WORKER "${worker} PID=${pid}, ${item_count} topics"
done

if [[ ${#FLEET_WORKER_PIDS[@]} -eq 0 ]]; then
  fleet_log ERROR "No workers dispatched"
  exit 1
fi

fleet_log INFO "Dispatched ${#FLEET_WORKER_PIDS[@]} workers"

# ---------------------------------------------------------------------------
# WAIT
# ---------------------------------------------------------------------------

fleet_wait_workers 60
wait_result=$?

# ---------------------------------------------------------------------------
# COLLECT AND MERGE
# ---------------------------------------------------------------------------

fleet_collect_results

fleet_log PHASE "Merge Research Reports"

MERGED_REPORT="${FLEET_RESULTS_DIR}/merged-research-report.md"

# Write header
cat > "$MERGED_REPORT" << REPORT_HEADER
# Bulk Deep Research Report

**Topics Researched:** ${TOTAL_TOPICS}
**Workers:** ${#FLEET_WORKER_HOSTS[@]} (${FLEET_WORKER_HOSTS[*]})
**Date:** $(date '+%Y-%m-%d %H:%M:%S')

---

## Table of Contents

REPORT_HEADER

# Build table of contents and concatenate reports
topic_num=0
for worker in "${FLEET_WORKER_HOSTS[@]}"; do
  output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
  if [[ -d "$output_dir" ]]; then
    for md_file in "$output_dir"/topic-*.md; do
      if [[ -f "$md_file" ]]; then
        topic_num=$((topic_num + 1))
        # Extract first heading as topic name
        topic_name=$(head -5 "$md_file" | grep -m1 '^#' | sed 's/^#* *//' || echo "Topic ${topic_num}")
        echo "${topic_num}. ${topic_name}" >> "$MERGED_REPORT"
      fi
    done
  fi
done

echo "" >> "$MERGED_REPORT"
echo "---" >> "$MERGED_REPORT"
echo "" >> "$MERGED_REPORT"

# Concatenate all topic reports
for worker in "${FLEET_WORKER_HOSTS[@]}"; do
  output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
  if [[ -d "$output_dir" ]]; then
    for md_file in "$output_dir"/topic-*.md; do
      if [[ -f "$md_file" ]]; then
        cat "$md_file" >> "$MERGED_REPORT"
        echo "" >> "$MERGED_REPORT"
        echo "---" >> "$MERGED_REPORT"
        echo "" >> "$MERGED_REPORT"
      fi
    done
  fi
done

# If no topic files, try extracting from worker output
if [[ $topic_num -eq 0 ]]; then
  fleet_log WARN "No topic files found, using raw worker output"
  fleet_merge_markdown "$MERGED_REPORT" "---"
fi

fleet_log OK "Merged report: ${MERGED_REPORT} (${topic_num} topics)"

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

fleet_summary "RESEARCH" "$START_TIME" "$TOTAL_TOPICS"

echo "Output files:"
echo "  Merged report:   ${MERGED_REPORT}"
echo "  Per-topic files: ${FLEET_RESULTS_DIR}/output-*/topic-*.md"
echo "  Worker logs:     ${FLEET_RESULTS_DIR}/worker-*.out"
echo "  Fleet log:       ${FLEET_LOG_FILE}"
echo ""

fleet_notify "Research Complete" \
  "${TOTAL_TOPICS} topics researched by ${#FLEET_WORKER_HOSTS[@]} workers" \
  "default"

exit ${wait_result:-0}
