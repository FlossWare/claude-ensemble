#!/bin/bash
# =============================================================================
# bulk-security-scan.sh - Fleet-Distributed Security Scanning
# =============================================================================
# Distributes code security scanning across fleet workers.
# Each worker runs /code-security on its batch of source files.
#
# Architecture:
#   Controller (this script)
#     |-- SSH --> server-01: claude -p "scan batch1 files"
#     |-- SSH --> server-02: claude -p "scan batch2 files"
#     |-- SSH --> server-03: claude -p "scan batch3 files"
#     |
#     v
#   Wait for all workers -> Merge + deduplicate findings by file:line:type
#
# Performance:
#   Per-file: ~2s scan
#   Sequential: 500 files * 2s = ~17 min
#   Fleet (3 workers): ~6 min (3x speedup)
#   Break-even: 50+ files
#
# Usage:
#   ./bulk-security-scan.sh /path/to/project/
#   ./bulk-security-scan.sh --type secrets /path/to/src/
#   ./bulk-security-scan.sh --dry-run /path/to/project/
#   ./bulk-security-scan.sh --extensions "java,py,js" /path/to/src/
#
# Options:
#   --type <type>          Scan type: all, secrets, injection, xss (default: all)
#   --extensions <ext>     Comma-separated file extensions to scan (default: all)
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

SCAN_TYPE="all"
EXTENSIONS=""
WORKER_TIMEOUT=3600
DISTRIBUTION="roundrobin"

# ---------------------------------------------------------------------------
# ARGUMENT PARSING
# ---------------------------------------------------------------------------

FILE_INPUTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type|-t)     SCAN_TYPE="$2"; shift 2 ;;
    --extensions)  EXTENSIONS="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=true; shift ;;
    --distribution) DISTRIBUTION="$2"; shift 2 ;;
    --timeout)     WORKER_TIMEOUT="$2"; shift 2 ;;
    --output|-o)   OUTPUT_DIR="$2"; shift 2 ;;
    --notify)      export FLEET_NTFY_TOPIC="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS] <project_dir_or_files...>"
      echo ""
      echo "Distribute security scanning across fleet workers."
      echo ""
      echo "Options:"
      echo "  --type <type>         Scan type: all|secrets|injection|xss (default: all)"
      echo "  --extensions <ext>    File extensions to scan (e.g., 'java,py,js')"
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
  echo "Usage: $0 [OPTIONS] <project_dir_or_files...>"
  exit 1
fi

# ---------------------------------------------------------------------------
# RESOLVE FILES
# ---------------------------------------------------------------------------

ITEMS_FILE=$(mktemp /tmp/fleet-security-items-XXXXXX.txt)
_security_cleanup() { rm -f "$ITEMS_FILE"; }
trap _security_cleanup EXIT

# Build find expression for extensions
FIND_EXPR=""
if [[ -n "$EXTENSIONS" ]]; then
  IFS=',' read -ra EXTS <<< "$EXTENSIONS"
  for i in "${!EXTS[@]}"; do
    ext="${EXTS[$i]}"
    if [[ $i -eq 0 ]]; then
      FIND_EXPR="-name '*.${ext}'"
    else
      FIND_EXPR="${FIND_EXPR} -o -name '*.${ext}'"
    fi
  done
fi

for input in "${FILE_INPUTS[@]}"; do
  if [[ -d "$input" ]]; then
    if [[ -n "$FIND_EXPR" ]]; then
      eval "find '$input' -type f \\( ${FIND_EXPR} \\) \
        -not -path '*/node_modules/*' \
        -not -path '*/.git/*' \
        -not -path '*/vendor/*' \
        -not -path '*/target/*' \
        -not -path '*/build/*' \
        -not -path '*/__pycache__/*'" | sort >> "$ITEMS_FILE"
    else
      find "$input" -type f \
        \( -name "*.java" -o -name "*.py" -o -name "*.js" -o -name "*.ts" \
           -o -name "*.rb" -o -name "*.go" -o -name "*.rs" -o -name "*.php" \
           -o -name "*.kt" -o -name "*.scala" -o -name "*.cs" -o -name "*.c" \
           -o -name "*.cpp" -o -name "*.h" -o -name "*.sh" -o -name "*.yaml" \
           -o -name "*.yml" -o -name "*.xml" -o -name "*.json" -o -name "*.toml" \
           -o -name "*.cfg" -o -name "*.ini" -o -name "*.env" -o -name "Dockerfile" \
           -o -name "*.tf" -o -name "*.hcl" \) \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/vendor/*" \
        -not -path "*/target/*" \
        -not -path "*/build/*" \
        -not -path "*/__pycache__/*" | sort >> "$ITEMS_FILE"
    fi
  elif [[ -f "$input" ]]; then
    realpath "$input" >> "$ITEMS_FILE"
  else
    fleet_log WARN "Not found: $input"
  fi
done

TOTAL_FILES=$(wc -l < "$ITEMS_FILE")

if [[ $TOTAL_FILES -eq 0 ]]; then
  fleet_log ERROR "No source files found"
  exit 1
fi

echo ""
echo "=================================================================="
echo "  BULK SECURITY SCAN"
echo "=================================================================="
echo "  Files:     ${TOTAL_FILES}"
echo "  Scan type: ${SCAN_TYPE}"
echo "  Extensions: ${EXTENSIONS:-all source files}"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# FLEET SETUP
# ---------------------------------------------------------------------------

fleet_check_compliance
fleet_discover_workers

START_TIME=$(date +%s)
fleet_init_session "security-scan" "${OUTPUT_DIR:-}"

fleet_distribute_roundrobin "$ITEMS_FILE"

# ---------------------------------------------------------------------------
# DRY RUN
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "true" ]]; then
  fleet_dry_run_report "security-scan"
  exit 0
fi

# ---------------------------------------------------------------------------
# DISPATCH WORKERS
# ---------------------------------------------------------------------------

fleet_log PHASE "Dispatch Security Scan Workers"

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

  files_json=$(python3 -c "
import json
with open('${batch_file}') as f:
    files = [line.strip() for line in f if line.strip()]
print(json.dumps(files))
")

  read -r -d '' worker_prompt << PROMPT_EOF || true
You are a fleet worker performing security scanning.

TASK: Scan ${item_count} source files for security vulnerabilities.
SCAN TYPE: ${SCAN_TYPE}
OUTPUT DIRECTORY: ${output_dir}

FILE LIST (JSON array):
${files_json}

INSTRUCTIONS:
1. Run /code-security on the files, scanning for:
   - Hardcoded secrets/credentials
   - SQL injection vulnerabilities
   - XSS vulnerabilities
   - Path traversal
   - Command injection
   - Insecure cryptography
   - TOCTOU race conditions
   - Any other security issues
2. Write findings to ${output_dir}/findings.json:
   {"findings":[{"file":"...","line":N,"type":"...","severity":"critical|high|medium|low","description":"...","fix":"..."}]}
3. Write progress to ${FLEET_PROGRESS_DIR}/progress-${worker}.json periodically.
4. Scan ALL ${item_count} files. Skip binary/unreadable files.
5. Write ${output_dir}/summary.json at end:
   {"worker":"${worker}","files_scanned":N,"findings_count":N,"by_severity":{"critical":N,"high":N,"medium":N,"low":N},"status":"complete"}
PROMPT_EOF

  worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
  worker_status="${FLEET_RESULTS_DIR}/worker-${worker}.status"
  worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"

  fleet_log INFO "Launching on ${worker}: ${item_count} files"

  escaped_prompt=$(echo "$worker_prompt" | sed "s/'/'\\\\''/g")

  (
    timeout "${WORKER_TIMEOUT}" \
      ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$worker" \
        "cd '${NFS_ROOT}' && claude -p \
          --dangerously-skip-permissions \
          --output-format text \
          --max-turns 200 \
          --no-session-persistence \
          '${escaped_prompt}'" \
      > "$worker_out" 2>&1
    echo $? > "$worker_status"
  ) &

  pid=$!
  echo "$pid" > "$worker_pid_file"
  FLEET_WORKER_PIDS+=("$pid")
  FLEET_WORKER_HOSTS+=("$worker")

  fleet_log WORKER "${worker} PID=${pid}, ${item_count} files"
done

fleet_log INFO "Dispatched ${#FLEET_WORKER_PIDS[@]} workers"

# ---------------------------------------------------------------------------
# WAIT AND MERGE
# ---------------------------------------------------------------------------

fleet_wait_workers 30
wait_result=$?

fleet_collect_results

fleet_log PHASE "Merge and Deduplicate Findings"

MERGED_FINDINGS="${FLEET_RESULTS_DIR}/merged-findings.json"

python3 << 'MERGE_SCRIPT'
import json
import glob
import os

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

# Sort by severity
severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
unique.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 4))

# Count by severity
by_severity = {}
for f in unique:
    sev = f.get("severity", "unknown")
    by_severity[sev] = by_severity.get(sev, 0) + 1

merged_file = os.path.join(results_dir, "merged-findings.json")
with open(merged_file, "w") as out:
    json.dump({
        "total_findings": len(unique),
        "duplicates_removed": len(all_findings) - len(unique),
        "by_severity": by_severity,
        "findings": unique
    }, out, indent=2)

print(f"\nMerged: {len(unique)} unique findings ({len(all_findings) - len(unique)} duplicates removed)")
for sev, count in sorted(by_severity.items(), key=lambda x: severity_order.get(x[0], 4)):
    print(f"  {sev}: {count}")
MERGE_SCRIPT

export FLEET_RESULTS_DIR

fleet_log OK "Findings: ${MERGED_FINDINGS}"

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

fleet_summary "SECURITY-SCAN" "$START_TIME" "$TOTAL_FILES"

echo "Output files:"
echo "  Findings:        ${MERGED_FINDINGS}"
echo "  Worker outputs:  ${FLEET_RESULTS_DIR}/output-*/"
echo "  Worker logs:     ${FLEET_RESULTS_DIR}/worker-*.out"
echo "  Fleet log:       ${FLEET_LOG_FILE}"
echo ""

fleet_notify "Security Scan Complete" \
  "${TOTAL_FILES} files scanned by ${#FLEET_WORKER_HOSTS[@]} workers" \
  "default"

exit ${wait_result:-0}
