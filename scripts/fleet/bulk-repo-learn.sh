#!/bin/bash
# =============================================================================
# bulk-repo-learn.sh - Fleet-Distributed Repository Code Learning
# =============================================================================
# Distributes code learning across fleet workers (3 sessions).
# Each worker runs /ai-web-code-learn-production on its batch of repositories.
#
# Architecture:
#   Controller (this script)
#     |-- SSH --> server-01: claude -p "learn from batch1 repos"
#     |-- SSH --> server-02: claude -p "learn from batch2 repos"
#     |-- SSH --> server-03: claude -p "learn from batch3 repos"
#     |
#     v
#   Wait for all workers -> Merge code patterns + embeddings
#
# Performance:
#   Per-repo: ~6 min (clone + discover + AST analyze + extract patterns)
#   Sequential: 50 repos * 6 min = 300 min = 5 hours
#   Fleet (3 workers): ~100 min (3x speedup)
#   Break-even: 5+ repos
#
# Usage:
#   ./bulk-repo-learn.sh repos.txt
#   ./bulk-repo-learn.sh https://github.com/user/repo1 https://github.com/user/repo2
#   ./bulk-repo-learn.sh --topic "microservices" repos.txt
#   ./bulk-repo-learn.sh --dry-run repos.txt
#
# Options:
#   --topic <topic>        Learning focus area
#   --dry-run              Show distribution plan without executing
#   --distribution <m>     roundrobin or weighted (default: weighted)
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

TOPIC=""
WORKER_TIMEOUT=7200
DISTRIBUTION="weighted"  # Larger repos need more memory

# ---------------------------------------------------------------------------
# ARGUMENT PARSING
# ---------------------------------------------------------------------------

REPO_INPUTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic)        TOPIC="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --distribution) DISTRIBUTION="$2"; shift 2 ;;
    --timeout)      WORKER_TIMEOUT="$2"; shift 2 ;;
    --output|-o)    OUTPUT_DIR="$2"; shift 2 ;;
    --notify)       export FLEET_NTFY_TOPIC="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS] <repos_file_or_urls...>"
      echo ""
      echo "Distribute repository code learning across fleet workers."
      echo ""
      echo "Options:"
      echo "  --topic <topic>       Learning focus area"
      echo "  --dry-run             Show plan without executing"
      echo "  --distribution <m>    roundrobin or weighted (default: weighted)"
      echo "  --timeout <sec>       Per-worker timeout (default: 7200)"
      echo "  --output <dir>        Custom output directory"
      echo "  --notify <topic>      ntfy notification topic"
      echo ""
      echo "Input formats:"
      echo "  $0 repos.txt                                    # File with repo URLs"
      echo "  $0 https://github.com/org/repo1 /local/repo2   # URLs/paths as args"
      exit 0
      ;;
    *)
      REPO_INPUTS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#REPO_INPUTS[@]} -eq 0 ]]; then
  echo "ERROR: No repository inputs specified"
  exit 1
fi

# ---------------------------------------------------------------------------
# RESOLVE REPOS
# ---------------------------------------------------------------------------

ITEMS_FILE=$(mktemp /tmp/fleet-repo-items-XXXXXX.txt)
_repo_cleanup() { rm -f "$ITEMS_FILE"; }
trap _repo_cleanup EXIT

for input in "${REPO_INPUTS[@]}"; do
  if [[ -f "$input" ]]; then
    grep -v '^\s*#' "$input" | grep -v '^\s*$' >> "$ITEMS_FILE"
  elif [[ "$input" == http* || "$input" == git@* || -d "$input" ]]; then
    echo "$input" >> "$ITEMS_FILE"
  else
    fleet_log WARN "Skipping: $input"
  fi
done

TOTAL_REPOS=$(wc -l < "$ITEMS_FILE")

if [[ $TOTAL_REPOS -eq 0 ]]; then
  fleet_log ERROR "No repositories found"
  exit 1
fi

echo ""
echo "=================================================================="
echo "  BULK REPOSITORY LEARNING"
echo "=================================================================="
echo "  Repos: ${TOTAL_REPOS}"
echo "  Topic: ${TOPIC:-general}"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# FLEET SETUP
# ---------------------------------------------------------------------------

fleet_check_compliance
fleet_discover_workers

START_TIME=$(date +%s)
fleet_init_session "repo-learn" "${OUTPUT_DIR:-}"

if [[ "$DISTRIBUTION" == "weighted" ]]; then
  fleet_distribute_weighted "$ITEMS_FILE"
else
  fleet_distribute_roundrobin "$ITEMS_FILE"
fi

if [[ "$DRY_RUN" == "true" ]]; then
  fleet_dry_run_report "repo-learn"
  exit 0
fi

# ---------------------------------------------------------------------------
# DISPATCH WORKERS
# ---------------------------------------------------------------------------

fleet_log PHASE "Dispatch Repo Learning Workers"

FLEET_WORKER_PIDS=()
FLEET_WORKER_HOSTS=()

for worker in "${FLEET_WORKERS[@]}"; do
  batch_file="${FLEET_RESULTS_DIR}/batch-${worker}.txt"
  if [[ ! -f "$batch_file" ]]; then continue; fi

  item_count=$(wc -l < "$batch_file")
  output_dir="${FLEET_RESULTS_DIR}/output-${worker}"
  mkdir -p "$output_dir"

  repos_json=$(python3 -c "
import json
with open('${batch_file}') as f:
    repos = [line.strip() for line in f if line.strip()]
print(json.dumps(repos))
")

  topic_clause=""
  if [[ -n "$TOPIC" ]]; then
    topic_clause="Focus on patterns related to: ${TOPIC}"
  fi

  read -r -d '' worker_prompt << PROMPT_EOF || true
You are a fleet worker learning from source code repositories.

TASK: Analyze ${item_count} repositories and extract code patterns.
OUTPUT DIRECTORY: ${output_dir}
${topic_clause}

REPOSITORY LIST (JSON array):
${repos_json}

INSTRUCTIONS:
1. For each repository, run /ai-web-code-learn-production:
   /ai-web-code-learn-production { "repos": ["<repo_url>"] }
2. After each repo, write patterns to ${output_dir}/repo-NNN.json
   Format: {"repo":"...","patterns":[{"pattern":"...","category":"...","file":"...","code":"..."}]}
3. Write progress to ${FLEET_PROGRESS_DIR}/progress-${worker}.json after each repo.
4. Analyze ALL ${item_count} repos. Skip failures with warnings.
5. Write ${output_dir}/summary.json at end:
   {"worker":"${worker}","repos_analyzed":N,"patterns_extracted":N,"status":"complete"}
PROMPT_EOF

  worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
  worker_status="${FLEET_RESULTS_DIR}/worker-${worker}.status"
  worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"

  fleet_log INFO "Launching on ${worker}: ${item_count} repos"

  escaped_prompt=$(echo "$worker_prompt" | sed "s/'/'\\\\''/g")

  (
    timeout "${WORKER_TIMEOUT}" \
      ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$worker" \
        "cd '${NFS_ROOT}' && claude -p \
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

fleet_wait_workers 60
wait_result=$?

fleet_collect_results

fleet_log PHASE "Merge Code Patterns"

MERGED_PATTERNS="${FLEET_RESULTS_DIR}/merged-patterns.json"

python3 << 'MERGE_SCRIPT'
import json, glob, os

results_dir = os.environ.get("FLEET_RESULTS_DIR", ".")
all_patterns = []
repos_count = 0

for worker_dir in sorted(glob.glob(os.path.join(results_dir, "output-*"))):
    for repo_file in sorted(glob.glob(os.path.join(worker_dir, "repo-*.json"))):
        try:
            with open(repo_file) as f:
                data = json.load(f)
                patterns = data.get("patterns", [])
                all_patterns.extend(patterns)
                repos_count += 1
                print(f"  {os.path.basename(repo_file)}: {len(patterns)} patterns")
        except Exception as e:
            print(f"  WARNING: {repo_file}: {e}")

# Deduplicate by pattern content
seen = set()
unique = []
for p in all_patterns:
    key = p.get("pattern", str(p))[:200]
    if key not in seen:
        seen.add(key)
        unique.append(p)

merged_file = os.path.join(results_dir, "merged-patterns.json")
with open(merged_file, "w") as f:
    json.dump({
        "repos_analyzed": repos_count,
        "total_patterns": len(unique),
        "duplicates_removed": len(all_patterns) - len(unique),
        "patterns": unique
    }, f, indent=2)

print(f"\nMerged: {len(unique)} patterns from {repos_count} repos")
MERGE_SCRIPT

export FLEET_RESULTS_DIR

fleet_summary "REPO-LEARN" "$START_TIME" "$TOTAL_REPOS"

echo "Output files:"
echo "  Merged patterns: ${MERGED_PATTERNS}"
echo "  Worker outputs:  ${FLEET_RESULTS_DIR}/output-*/"
echo "  Fleet log:       ${FLEET_LOG_FILE}"

fleet_notify "Repo Learning Complete" \
  "${TOTAL_REPOS} repos analyzed by ${#FLEET_WORKER_HOSTS[@]} workers" "default"

exit ${wait_result:-0}
