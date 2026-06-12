#!/bin/bash
# =============================================================================
# bulk-pdf-ingest.sh - Fleet-Distributed PDF Deep Research
# =============================================================================
# USER'S PRIMARY USE CASE: 600 PDFs to ingest
#
# Distributes PDF deep research across fleet workers (3 sessions).
# Each worker gets an independent Claude Code session running
# /ai-pdf-deep-research on its batch of PDFs.
#
# Architecture:
#   Controller (this script)
#     |-- SSH --> server-01: claude -p "process batch1 of PDFs"
#     |-- SSH --> server-02: claude -p "process batch2 of PDFs"
#     |-- SSH --> server-03: claude -p "process batch3 of PDFs"
#     |
#     v
#   Wait for all workers -> Merge markdown reports + JSON findings
#
# Performance:
#   Per-PDF: ~10 min (read + 6-model extract + 3-vote verify + synthesize)
#   Sequential: ~10 min/PDF * 600 = 100 hours
#   Fleet (3 workers): ~33 hours (3x speedup, saves 67 hours)
#   Break-even: 10+ PDFs
#
# Usage:
#   ./bulk-pdf-ingest.sh /path/to/pdfs/
#   ./bulk-pdf-ingest.sh /path/to/*.pdf
#   ./bulk-pdf-ingest.sh --topic "quantum computing" /data/papers/
#   ./bulk-pdf-ingest.sh --dry-run /path/to/pdfs/
#   ./bulk-pdf-ingest.sh --batch-size 5 --distribution weighted /data/papers/
#
# Options:
#   --topic <topic>        Research topic/question for analysis
#   --batch-size <n>       PDFs per Claude session call (default: 3)
#   --dry-run              Show distribution plan without executing
#   --distribution <m>     roundrobin or weighted (default: weighted)
#   --timeout <sec>        Per-worker timeout in seconds (default: 14400)
#   --output <dir>         Custom output directory
#   --notify <topic>       ntfy topic for completion notifications
#   --help                 Show this help
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/fleet-bulk-lib.sh"

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

TOPIC="general analysis"
BATCH_SIZE=3  # PDFs per individual /ai-pdf-deep-research call

# Override lib defaults
WORKER_TIMEOUT=14400  # 4 hours per worker
DISTRIBUTION="weighted"  # server-02/03 get more (more memory)

# ---------------------------------------------------------------------------
# ARGUMENT PARSING
# ---------------------------------------------------------------------------

PDF_INPUTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic)
      TOPIC="$2"
      shift 2
      ;;
    --batch-size)
      BATCH_SIZE="$2"
      shift 2
      ;;
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
    --help|-h)
      echo "Usage: $0 [OPTIONS] <pdf_dir_or_files...>"
      echo ""
      echo "Distribute PDF deep research across fleet workers."
      echo ""
      echo "Options:"
      echo "  --topic <topic>        Research topic (default: 'general analysis')"
      echo "  --batch-size <n>       PDFs per Claude call (default: 3)"
      echo "  --dry-run              Show plan without executing"
      echo "  --distribution <m>     roundrobin or weighted (default: weighted)"
      echo "  --timeout <sec>        Per-worker timeout (default: 14400 = 4h)"
      echo "  --output <dir>         Custom output directory"
      echo "  --notify <topic>       ntfy notification topic"
      echo "  --help                 Show this help"
      echo ""
      echo "Examples:"
      echo "  $0 /data/papers/"
      echo "  $0 --topic 'climate change' --batch-size 5 /data/papers/*.pdf"
      echo "  $0 --dry-run /data/papers/"
      exit 0
      ;;
    *)
      PDF_INPUTS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#PDF_INPUTS[@]} -eq 0 ]]; then
  echo "ERROR: No PDF inputs specified"
  echo "Usage: $0 [OPTIONS] <pdf_dir_or_files...>"
  exit 1
fi

# ---------------------------------------------------------------------------
# RESOLVE PDF FILES
# ---------------------------------------------------------------------------

ITEMS_FILE=$(mktemp /tmp/fleet-pdf-items-XXXXXX.txt)

# Clean up temp file on exit (in addition to fleet_cleanup from lib)
_pdf_cleanup() { rm -f "$ITEMS_FILE"; }
trap _pdf_cleanup EXIT

for input in "${PDF_INPUTS[@]}"; do
  if [[ -d "$input" ]]; then
    # Directory: find all PDFs recursively
    find "$input" -type f \( -name "*.pdf" -o -name "*.PDF" \) | sort >> "$ITEMS_FILE"
  elif [[ -f "$input" ]]; then
    case "$input" in
      *.pdf|*.PDF) realpath "$input" >> "$ITEMS_FILE" ;;
      *) fleet_log WARN "Skipping non-PDF: $input" ;;
    esac
  else
    fleet_log WARN "Not found: $input"
  fi
done

TOTAL_PDFS=$(wc -l < "$ITEMS_FILE")

if [[ $TOTAL_PDFS -eq 0 ]]; then
  fleet_log ERROR "No PDF files found in: ${PDF_INPUTS[*]}"
  exit 1
fi

# Verify all PDFs are on NFS
NON_NFS=0
while IFS= read -r pdf; do
  if ! fleet_is_nfs "$pdf"; then
    fleet_log WARN "PDF not on NFS: $pdf"
    NON_NFS=$((NON_NFS + 1))
  fi
done < "$ITEMS_FILE"

if [[ $NON_NFS -gt 0 ]]; then
  fleet_log ERROR "${NON_NFS} PDFs are not on NFS (${NFS_ROOT})"
  fleet_log ERROR "Fleet workers can only access files under ${NFS_ROOT}"
  fleet_log ERROR "Copy PDFs to NFS first, e.g.: cp *.pdf ~/Development/data/pdfs/"
  exit 1
fi

echo ""
echo "=================================================================="
echo "  BULK PDF DEEP RESEARCH"
echo "=================================================================="
echo "  PDFs:       ${TOTAL_PDFS}"
echo "  Topic:      ${TOPIC}"
echo "  Batch size: ${BATCH_SIZE} PDFs per Claude call"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# FLEET SETUP
# ---------------------------------------------------------------------------

fleet_check_compliance
fleet_discover_workers

START_TIME=$(date +%s)
fleet_init_session "pdf-ingest" "${OUTPUT_DIR:-}"

# Distribute PDFs across workers
if [[ "$DISTRIBUTION" == "weighted" ]]; then
  fleet_distribute_weighted "$ITEMS_FILE"
else
  fleet_distribute_roundrobin "$ITEMS_FILE"
fi

# ---------------------------------------------------------------------------
# DRY RUN
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "true" ]]; then
  fleet_dry_run_report "pdf-ingest"

  seq_hours=$((TOTAL_PDFS * 10 / 60))
  fleet_hours=$((TOTAL_PDFS * 10 / 60 / ${#FLEET_WORKERS[@]}))
  echo "Estimated time:"
  echo "  Sequential: ~${seq_hours}h"
  echo "  Fleet (${#FLEET_WORKERS[@]} workers): ~${fleet_hours}h"
  echo "  Savings: ~$((seq_hours - fleet_hours))h"
  exit 0
fi

# ---------------------------------------------------------------------------
# DISPATCH WORKERS
# ---------------------------------------------------------------------------

fleet_log PHASE "Dispatch PDF Workers"

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

  # Build JSON array of PDF paths for this worker
  pdf_json_array=$(python3 -c "
import json
with open('${batch_file}') as f:
    pdfs = [line.strip() for line in f if line.strip()]
print(json.dumps(pdfs))
")

  # Calculate number of sub-batches
  num_batches=$(python3 -c "import math; print(math.ceil(${item_count} / ${BATCH_SIZE}))")

  # Build the worker prompt
  # The worker will iterate through PDFs in sub-batches of BATCH_SIZE,
  # calling /ai-pdf-deep-research for each sub-batch
  read -r -d '' worker_prompt << PROMPT_EOF || true
You are a fleet worker processing PDFs for bulk deep research.

TASK: Process ${item_count} PDFs in ${num_batches} batches of ${BATCH_SIZE}.
TOPIC: ${TOPIC}
OUTPUT DIRECTORY: ${output_dir}

PDF LIST (JSON array):
${pdf_json_array}

INSTRUCTIONS:
1. Split the PDF list into batches of ${BATCH_SIZE} PDFs each
2. For each batch, run the /ai-pdf-deep-research skill with those PDFs
3. After each batch completes, write the findings to ${output_dir}/batch-NNN.md
   (NNN = batch number: 001, 002, etc.)
4. Also write a progress file after each batch:
   Write to ${FLEET_PROGRESS_DIR}/progress-${worker}.json:
   {"worker":"${worker}","completed":BATCHES_DONE,"total":${num_batches},"timestamp":"CURRENT_TIME"}
5. Process ALL ${item_count} PDFs. Do not stop early.
6. If a PDF fails to read, log the error and continue with the next one.

For each batch, invoke:
/ai-pdf-deep-research { "pdfs": [<batch PDFs>], "topic": "${TOPIC}" }

After ALL batches complete, write a summary to ${output_dir}/summary.json with:
{
  "worker": "${worker}",
  "total_pdfs": ${item_count},
  "batches_completed": <number>,
  "findings_count": <total findings across all batches>,
  "status": "complete"
}
PROMPT_EOF

  worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
  worker_status="${FLEET_RESULTS_DIR}/worker-${worker}.status"
  worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"

  fleet_log INFO "Launching on ${worker}: ${item_count} PDFs in ${num_batches} batches"

  # Escape single quotes in prompt for SSH
  escaped_prompt=$(echo "$worker_prompt" | sed "s/'/'\\\\''/g")

  (
    timeout "${WORKER_TIMEOUT}" \
      ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$worker" \
        "export ANTHROPIC_VERTEX_PROJECT_ID='${ANTHROPIC_VERTEX_PROJECT_ID:-itpc-gcp-uie-eng-claude}' && \
         export CLAUDE_CODE_USE_VERTEX='${CLAUDE_CODE_USE_VERTEX:-1}' && \
         export GOOGLE_GENAI_USE_VERTEXAI='${GOOGLE_GENAI_USE_VERTEXAI:-True}' && \
         cd '${NFS_ROOT}' && claude -p \
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

  fleet_log WORKER "${worker} PID=${pid}, ${item_count} PDFs"
done

if [[ ${#FLEET_WORKER_PIDS[@]} -eq 0 ]]; then
  fleet_log ERROR "No workers dispatched"
  exit 1
fi

fleet_log INFO "Dispatched ${#FLEET_WORKER_PIDS[@]} workers"

seq_est=$((TOTAL_PDFS * 10))
fleet_est=$((TOTAL_PDFS * 10 / ${#FLEET_WORKER_PIDS[@]}))
fleet_log INFO "Estimated time: ~$((fleet_est / 60))h (vs ~$((seq_est / 60))h sequential)"

# ---------------------------------------------------------------------------
# WAIT FOR WORKERS
# ---------------------------------------------------------------------------

fleet_wait_workers 60  # progress check every 60 seconds
wait_result=$?

# ---------------------------------------------------------------------------
# COLLECT RESULTS
# ---------------------------------------------------------------------------

fleet_collect_results

# ---------------------------------------------------------------------------
# MERGE RESULTS
# ---------------------------------------------------------------------------

fleet_log PHASE "Merge Results"

MERGED_REPORT="${FLEET_RESULTS_DIR}/merged-report.md"
MERGED_JSON="${FLEET_RESULTS_DIR}/merged-findings.json"

# Write report header
cat > "$MERGED_REPORT" << REPORT_HEADER
# Bulk PDF Deep Research Report

**Topic:** ${TOPIC}
**Total PDFs:** ${TOTAL_PDFS}
**Workers:** ${#FLEET_WORKER_HOSTS[@]} (${FLEET_WORKER_HOSTS[*]})
**Distribution:** ${DISTRIBUTION}
**Date:** $(date '+%Y-%m-%d %H:%M:%S')

---

REPORT_HEADER

# Collect all per-batch markdown outputs
batch_count=0
for worker in "${FLEET_WORKER_HOSTS[@]}"; do
  output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
  if [[ -d "$output_dir" ]]; then
    for md_file in "$output_dir"/batch-*.md; do
      if [[ -f "$md_file" ]]; then
        echo "" >> "$MERGED_REPORT"
        echo "## Worker: ${worker} - $(basename "$md_file")" >> "$MERGED_REPORT"
        echo "" >> "$MERGED_REPORT"
        cat "$md_file" >> "$MERGED_REPORT"
        echo "" >> "$MERGED_REPORT"
        echo "---" >> "$MERGED_REPORT"
        batch_count=$((batch_count + 1))
      fi
    done
  fi
done

# If no batch files found, fall back to extracting from worker stdout
if [[ $batch_count -eq 0 ]]; then
  fleet_log WARN "No batch markdown files found, extracting from worker output"
  fleet_merge_markdown "$MERGED_REPORT" "---"
fi

# Merge JSON summaries from workers
all_summaries="${FLEET_RESULTS_DIR}/all-summaries.json"
echo "[" > "$all_summaries"
first=true
for worker in "${FLEET_WORKER_HOSTS[@]}"; do
  summary_file="${FLEET_RESULTS_DIR}/output-${worker}/summary.json"
  if [[ -f "$summary_file" ]]; then
    if [[ "$first" == "true" ]]; then
      first=false
    else
      echo "," >> "$all_summaries"
    fi
    cat "$summary_file" >> "$all_summaries"
  fi
done
echo "]" >> "$all_summaries"

fleet_log OK "Merged report: ${MERGED_REPORT}"
fleet_log OK "Batch outputs: ${batch_count} files"

# ---------------------------------------------------------------------------
# FINAL SUMMARY
# ---------------------------------------------------------------------------

fleet_summary "PDF-INGEST" "$START_TIME" "$TOTAL_PDFS"

echo "Output files:"
echo "  Merged report:  ${MERGED_REPORT}"
echo "  Worker outputs:  ${FLEET_RESULTS_DIR}/output-*/"
echo "  Worker logs:     ${FLEET_RESULTS_DIR}/worker-*.out"
echo "  Fleet log:       ${FLEET_LOG_FILE}"
echo ""

# Notification
fleet_notify "PDF Ingest Complete" \
  "${TOTAL_PDFS} PDFs processed by ${#FLEET_WORKER_HOSTS[@]} workers" \
  "default"

exit ${wait_result:-0}
