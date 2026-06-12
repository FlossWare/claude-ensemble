#!/bin/bash
# =============================================================================
# bulk-code-doc.sh - Fleet-Distributed Code Documentation
# =============================================================================
# Distributes code documentation generation across fleet workers.
# Each worker runs /code-doc on its batch of source files, producing
# one markdown documentation file per source file.
#
# Architecture:
#   Controller (this script)
#     |-- SSH --> server-01: claude -p "document batch1 files"
#     |-- SSH --> server-02: claude -p "document batch2 files"
#     |-- SSH --> server-03: claude -p "document batch3 files"
#     |
#     v
#   Wait for all workers -> Collect per-file .md outputs
#
# Performance:
#   Per-file: ~20s (read + AST parse + generate docs)
#   Sequential: 500 files * 20s = ~167 min = 2.8 hours
#   Fleet (3 workers): ~56 min (3x speedup)
#   Break-even: 50+ files
#
# Usage:
#   ./bulk-code-doc.sh /path/to/project/src/
#   ./bulk-code-doc.sh --extensions "java,py" /path/to/src/
#   ./bulk-code-doc.sh --dry-run /path/to/project/
#
# Options:
#   --extensions <ext>     File extensions to document (default: all source)
#   --dry-run              Show distribution plan without executing
#   --distribution <m>     roundrobin or weighted (default: roundrobin)
#   --timeout <sec>        Per-worker timeout (default: 3600)
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

EXTENSIONS=""
PROJECT_DIR=""
WORKER_TIMEOUT=3600
DISTRIBUTION="roundrobin"

# ---------------------------------------------------------------------------
# ARGUMENT PARSING
# ---------------------------------------------------------------------------

FILE_INPUTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --extensions)   EXTENSIONS="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --distribution) DISTRIBUTION="$2"; shift 2 ;;
    --timeout)      WORKER_TIMEOUT="$2"; shift 2 ;;
    --output|-o)    OUTPUT_DIR="$2"; shift 2 ;;
    --notify)       export FLEET_NTFY_TOPIC="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS] <project_dir_or_files...>"
      echo ""
      echo "Distribute documentation generation across fleet workers."
      echo ""
      echo "Options:"
      echo "  --extensions <ext>    File extensions (e.g., 'java,py,js')"
      echo "  --dry-run             Show plan without executing"
      echo "  --distribution <m>    roundrobin or weighted (default: roundrobin)"
      echo "  --timeout <sec>       Per-worker timeout (default: 3600)"
      echo "  --output <dir>        Custom output directory"
      echo "  --notify <topic>      ntfy notification topic"
      exit 0
      ;;
    *)
      FILE_INPUTS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#FILE_INPUTS[@]} -eq 0 ]]; then
  echo "ERROR: No file inputs specified"
  exit 1
fi

# ---------------------------------------------------------------------------
# RESOLVE FILES
# ---------------------------------------------------------------------------

ITEMS_FILE=$(mktemp /tmp/fleet-doc-items-XXXXXX.txt)
_doc_cleanup() { rm -f "$ITEMS_FILE"; }
trap _doc_cleanup EXIT

for input in "${FILE_INPUTS[@]}"; do
  if [[ -d "$input" ]]; then
    PROJECT_DIR="${PROJECT_DIR:-$(realpath "$input")}"

    if [[ -n "$EXTENSIONS" ]]; then
      IFS=',' read -ra EXTS <<< "$EXTENSIONS"
      find_expr=""
      for i in "${!EXTS[@]}"; do
        ext="${EXTS[$i]}"
        if [[ $i -eq 0 ]]; then
          find_expr="-name '*.${ext}'"
        else
          find_expr="${find_expr} -o -name '*.${ext}'"
        fi
      done
      eval "find '$input' -type f \\( ${find_expr} \\) \
        -not -path '*/node_modules/*' -not -path '*/.git/*' \
        -not -path '*/vendor/*' -not -path '*/target/*' \
        -not -path '*/build/*'" | sort >> "$ITEMS_FILE"
    else
      find "$input" -type f \
        \( -name "*.java" -o -name "*.py" -o -name "*.js" -o -name "*.ts" \
           -o -name "*.tsx" -o -name "*.jsx" -o -name "*.rb" -o -name "*.go" \
           -o -name "*.rs" -o -name "*.kt" -o -name "*.scala" -o -name "*.cs" \
           -o -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" \
           -o -name "*.sh" -o -name "*.php" \) \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/vendor/*" \
        -not -path "*/target/*" \
        -not -path "*/build/*" | sort >> "$ITEMS_FILE"
    fi
  elif [[ -f "$input" ]]; then
    PROJECT_DIR="${PROJECT_DIR:-$(dirname "$(realpath "$input")")}"
    realpath "$input" >> "$ITEMS_FILE"
  fi
done

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
TOTAL_FILES=$(wc -l < "$ITEMS_FILE")

if [[ $TOTAL_FILES -eq 0 ]]; then
  fleet_log ERROR "No source files found"
  exit 1
fi

if ! fleet_is_nfs "$PROJECT_DIR"; then
  fleet_log ERROR "Project not on NFS: $PROJECT_DIR"
  fleet_log ERROR "Workers need shared access. Project must be under ${NFS_ROOT}"
  exit 1
fi

echo ""
echo "=================================================================="
echo "  BULK CODE DOCUMENTATION"
echo "=================================================================="
echo "  Files:      ${TOTAL_FILES}"
echo "  Project:    ${PROJECT_DIR}"
echo "  Extensions: ${EXTENSIONS:-all source files}"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# FLEET SETUP
# ---------------------------------------------------------------------------

fleet_check_compliance
fleet_discover_workers

START_TIME=$(date +%s)
fleet_init_session "code-doc" "${OUTPUT_DIR:-}"

fleet_distribute_roundrobin "$ITEMS_FILE"

if [[ "$DRY_RUN" == "true" ]]; then
  fleet_dry_run_report "code-doc"
  exit 0
fi

# ---------------------------------------------------------------------------
# DISPATCH WORKERS
# ---------------------------------------------------------------------------

fleet_log PHASE "Dispatch Documentation Workers"

FLEET_WORKER_PIDS=()
FLEET_WORKER_HOSTS=()

for worker in "${FLEET_WORKERS[@]}"; do
  batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
  if [[ ! -f "$batch_file" ]]; then continue; fi

  item_count=$(wc -l < "$batch_file")
  output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
  mkdir -p "$output_dir"

  files_json=$(python3 -c "
import json
with open('${batch_file}') as f:
    files = [line.strip() for line in f if line.strip()]
print(json.dumps(files))
")

  read -r -d '' worker_prompt << PROMPT_EOF || true
You are a fleet worker generating code documentation.

TASK: Generate documentation for ${item_count} source files.
PROJECT: ${PROJECT_DIR}
OUTPUT DIRECTORY: ${output_dir}

FILE LIST (JSON array):
${files_json}

INSTRUCTIONS:
1. cd to ${PROJECT_DIR} for repo context.
2. For each source file, use /code-doc to generate documentation.
3. Save each file's documentation to ${output_dir}/<filename>.md
   where <filename> mirrors the source file path with / replaced by --.
   Example: src/main/App.java -> src--main--App.java.md
4. Each doc should include:
   - File purpose and overview
   - Public API documentation (classes, functions, methods)
   - Parameter descriptions and return types
   - Usage examples where applicable
5. Write progress to ${FLEET_PROGRESS_DIR}/progress-${worker}.json periodically.
6. Document ALL ${item_count} files. Skip binary files.
7. Write ${output_dir}/summary.json:
   {"worker":"${worker}","files_documented":N,"status":"complete"}
PROMPT_EOF

  worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
  worker_status="${FLEET_RESULTS_DIR}/worker-${worker}.status"
  worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"

  fleet_log INFO "Launching on ${worker}: ${item_count} files"

  escaped_prompt=$(echo "$worker_prompt" | sed "s/'/'\\\\''/g")

  (
    timeout "${WORKER_TIMEOUT}" \
      ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$worker" \
        "cd '${PROJECT_DIR}' && claude -p \
          --dangerously-skip-permissions \
          --output-format text \
          --max-turns 300 \
          --no-session-persistence \
          '${escaped_prompt}'" \
      > "$worker_out" 2>&1
    echo $? > "$worker_status"
  ) &

  pid=$!
  echo "$pid" > "$worker_pid_file"
  FLEET_WORKER_PIDS+=("$pid")
  FLEET_WORKER_HOSTS+=("$worker")
done

fleet_log INFO "Dispatched ${#FLEET_WORKER_PIDS[@]} workers"

# ---------------------------------------------------------------------------
# WAIT AND MERGE
# ---------------------------------------------------------------------------

fleet_wait_workers 30
wait_result=$?

fleet_collect_results

fleet_log PHASE "Collect Documentation Files"

DOCS_DIR="${FLEET_RESULTS_DIR}/docs"
fleet_merge_files "$DOCS_DIR"

# Count generated docs
doc_count=$(find "$DOCS_DIR" -name "*.md" 2>/dev/null | wc -l)

fleet_summary "CODE-DOC" "$START_TIME" "$TOTAL_FILES"

echo "Output files:"
echo "  Documentation:   ${DOCS_DIR}/ (${doc_count} files)"
echo "  Worker outputs:  ${FLEET_RESULTS_DIR}/output-*/"
echo "  Fleet log:       ${FLEET_LOG_FILE}"

fleet_notify "Code Documentation Complete" \
  "${TOTAL_FILES} files documented by ${#FLEET_WORKER_HOSTS[@]} workers" "default"

exit ${wait_result:-0}
