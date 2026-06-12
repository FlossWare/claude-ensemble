#!/bin/bash
# =============================================================================
# bulk-code-review.sh - Fleet-Distributed Code Review
# =============================================================================
# Distributes code review across fleet workers (3 sessions).
# Each worker runs /code-review on its batch of changed files.
#
# IMPORTANT: Workers need repo context. The project must be on NFS
# so all workers can read the same files and git history.
#
# Architecture:
#   Controller (this script)
#     |-- SSH --> server-01: claude -p "review batch1 files in /nfs/repo"
#     |-- SSH --> server-02: claude -p "review batch2 files in /nfs/repo"
#     |-- SSH --> server-03: claude -p "review batch3 files in /nfs/repo"
#     |
#     v
#   Wait for all workers -> Merge + deduplicate findings by file:line:type
#
# Performance:
#   Per-file: ~30s (multi-model review + impact analysis)
#   Sequential: 200 files * 30s = 100 min
#   Fleet (3 workers): ~33 min (3x speedup)
#   Break-even: 30+ files
#
# Usage:
#   ./bulk-code-review.sh /path/to/nfs/project/
#   ./bulk-code-review.sh --pr 123
#   ./bulk-code-review.sh --effort high /path/to/project/
#   ./bulk-code-review.sh --dry-run /path/to/project/
#
# Options:
#   --pr <number>          Review files from a PR (uses gh pr view)
#   --effort <level>       Review effort: low, medium, high (default: medium)
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

PR_NUMBER=""
EFFORT="medium"
PROJECT_DIR=""
WORKER_TIMEOUT=3600
DISTRIBUTION="roundrobin"

# ---------------------------------------------------------------------------
# ARGUMENT PARSING
# ---------------------------------------------------------------------------

FILE_INPUTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr)           PR_NUMBER="$2"; shift 2 ;;
    --effort)       EFFORT="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --distribution) DISTRIBUTION="$2"; shift 2 ;;
    --timeout)      WORKER_TIMEOUT="$2"; shift 2 ;;
    --output|-o)    OUTPUT_DIR="$2"; shift 2 ;;
    --notify)       export FLEET_NTFY_TOPIC="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS] <project_dir_or_files...>"
      echo ""
      echo "Distribute code review across fleet workers."
      echo ""
      echo "Options:"
      echo "  --pr <number>         Review PR changed files"
      echo "  --effort <level>      low|medium|high (default: medium)"
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

# ---------------------------------------------------------------------------
# RESOLVE FILES
# ---------------------------------------------------------------------------

ITEMS_FILE=$(mktemp /tmp/fleet-review-items-XXXXXX.txt)
_review_cleanup() { rm -f "$ITEMS_FILE"; }
trap _review_cleanup EXIT

# If PR number given, get changed files from it
if [[ -n "$PR_NUMBER" ]]; then
  fleet_log INFO "Fetching changed files from PR #${PR_NUMBER}..."
  gh pr view "$PR_NUMBER" --json files -q '.files[].path' >> "$ITEMS_FILE" 2>/dev/null || {
    fleet_log ERROR "Failed to fetch PR #${PR_NUMBER} files"
    exit 1
  }
  PROJECT_DIR=$(pwd)
fi

for input in "${FILE_INPUTS[@]}"; do
  if [[ -d "$input" ]]; then
    PROJECT_DIR="${PROJECT_DIR:-$(realpath "$input")}"
    # Find source files (review-worthy extensions)
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
      -not -path "*/build/*" \
      -not -path "*/dist/*" | sort >> "$ITEMS_FILE"
  elif [[ -f "$input" ]]; then
    PROJECT_DIR="${PROJECT_DIR:-$(dirname "$(realpath "$input")")}"
    realpath "$input" >> "$ITEMS_FILE"
  fi
done

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"

TOTAL_FILES=$(wc -l < "$ITEMS_FILE")

if [[ $TOTAL_FILES -eq 0 ]]; then
  fleet_log ERROR "No files to review"
  exit 1
fi

# Verify project is on NFS
if ! fleet_is_nfs "$PROJECT_DIR"; then
  fleet_log ERROR "Project not on NFS: $PROJECT_DIR"
  fleet_log ERROR "Workers need shared repo access. Project must be under ${NFS_ROOT}"
  exit 1
fi

echo ""
echo "=================================================================="
echo "  BULK CODE REVIEW"
echo "=================================================================="
echo "  Files:   ${TOTAL_FILES}"
echo "  Project: ${PROJECT_DIR}"
echo "  Effort:  ${EFFORT}"
echo "  PR:      ${PR_NUMBER:-none}"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# FLEET SETUP
# ---------------------------------------------------------------------------

fleet_check_compliance
fleet_discover_workers

START_TIME=$(date +%s)
fleet_init_session "code-review" "${OUTPUT_DIR:-}"

fleet_distribute_roundrobin "$ITEMS_FILE"

if [[ "$DRY_RUN" == "true" ]]; then
  fleet_dry_run_report "code-review"
  exit 0
fi

# ---------------------------------------------------------------------------
# DISPATCH WORKERS
# ---------------------------------------------------------------------------

fleet_log PHASE "Dispatch Code Review Workers"

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
You are a fleet worker performing code review.

TASK: Review ${item_count} source files for bugs, issues, and improvements.
PROJECT: ${PROJECT_DIR}
EFFORT: ${EFFORT}
OUTPUT DIRECTORY: ${output_dir}

FILE LIST (JSON array):
${files_json}

INSTRUCTIONS:
1. cd to ${PROJECT_DIR} so you have full repo context.
2. For each file, run /code-review with effort=${EFFORT}:
   /code-review --effort ${EFFORT}
   Read the file and review it for bugs, code smells, and improvements.
3. Write findings to ${output_dir}/findings.json:
   {"findings":[{"file":"...","line":N,"type":"bug|smell|security|perf","severity":"critical|high|medium|low","description":"...","suggestion":"..."}]}
4. Write progress to ${FLEET_PROGRESS_DIR}/progress-${worker}.json periodically.
5. Review ALL ${item_count} files.
6. Write ${output_dir}/summary.json:
   {"worker":"${worker}","files_reviewed":N,"issues_found":N,"by_severity":{},"status":"complete"}
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

fleet_log PHASE "Merge Review Findings"

MERGED_FINDINGS="${FLEET_RESULTS_DIR}/merged-review.json"

python3 << 'MERGE_SCRIPT'
import json, glob, os

results_dir = os.environ.get("FLEET_RESULTS_DIR", ".")
all_findings = []

for worker_dir in sorted(glob.glob(os.path.join(results_dir, "output-*"))):
    findings_file = os.path.join(worker_dir, "findings.json")
    if os.path.exists(findings_file):
        try:
            with open(findings_file) as f:
                data = json.load(f)
                findings = data.get("findings", data if isinstance(data, list) else [])
                all_findings.extend(findings)
                print(f"  {os.path.basename(worker_dir)}: {len(findings)} findings")
        except Exception as e:
            print(f"  WARNING: {findings_file}: {e}")

# Deduplicate by file:line:type
seen = set()
unique = []
for f in all_findings:
    key = f"{f.get('file','')}:{f.get('line','')}:{f.get('type','')}"
    if key not in seen:
        seen.add(key)
        unique.append(f)

severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
unique.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 4))

by_severity = {}
for f in unique:
    sev = f.get("severity", "unknown")
    by_severity[sev] = by_severity.get(sev, 0) + 1

merged_file = os.path.join(results_dir, "merged-review.json")
with open(merged_file, "w") as out:
    json.dump({
        "total_findings": len(unique),
        "duplicates_removed": len(all_findings) - len(unique),
        "by_severity": by_severity,
        "findings": unique
    }, out, indent=2)

print(f"\nMerged: {len(unique)} findings ({len(all_findings) - len(unique)} duplicates)")
for sev, count in sorted(by_severity.items(), key=lambda x: severity_order.get(x[0], 4)):
    print(f"  {sev}: {count}")
MERGE_SCRIPT

export FLEET_RESULTS_DIR

fleet_summary "CODE-REVIEW" "$START_TIME" "$TOTAL_FILES"

echo "Output files:"
echo "  Findings:        ${MERGED_FINDINGS}"
echo "  Worker outputs:  ${FLEET_RESULTS_DIR}/output-*/"
echo "  Fleet log:       ${FLEET_LOG_FILE}"

fleet_notify "Code Review Complete" \
  "${TOTAL_FILES} files reviewed by ${#FLEET_WORKER_HOSTS[@]} workers" "default"

exit ${wait_result:-0}
