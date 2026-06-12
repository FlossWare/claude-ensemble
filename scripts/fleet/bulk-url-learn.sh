#!/bin/bash
# =============================================================================
# bulk-url-learn.sh - Fleet-Distributed URL Learning
# =============================================================================
# Distributes web learning across fleet workers (3 sessions).
# Each worker gets an independent Claude Code session running
# /ai-web-learn-production on its batch of URLs.
#
# Architecture:
#   Controller (this script)
#     |-- SSH --> server-01: claude -p "learn from batch1 URLs"
#     |-- SSH --> server-02: claude -p "learn from batch2 URLs"
#     |-- SSH --> server-03: claude -p "learn from batch3 URLs"
#     |
#     v
#   Wait for all workers -> Merge JSON fact extractions
#   -> Single-writer ChromaDB insert on server-02 (high memory)
#
# ChromaDB Strategy:
#   Each worker outputs JSON fact files (not direct ChromaDB writes).
#   After merge, controller runs single ChromaDB insert on DB_HOST
#   to avoid concurrent write conflicts.
#
# Performance:
#   Per-URL: ~10s (fetch + multi-model extract + embed + store)
#   Sequential: 1000 URLs * 10s = ~2.8 hours
#   Fleet (3 workers): ~56 min (3x speedup)
#   Break-even: 20+ URLs
#
# Usage:
#   ./bulk-url-learn.sh urls.txt
#   ./bulk-url-learn.sh --topic "kubernetes" urls.txt
#   ./bulk-url-learn.sh --db-host server-02 urls.txt
#   ./bulk-url-learn.sh --dry-run urls.txt
#   cat urls.txt | ./bulk-url-learn.sh -
#
# Options:
#   --topic <topic>        Knowledge domain for embeddings
#   --db-host <host>       ChromaDB host for final merge (default: server-02)
#   --batch-size <n>       URLs per Claude call (default: 10)
#   --dry-run              Show distribution plan without executing
#   --distribution <m>     roundrobin or weighted (default: roundrobin)
#   --timeout <sec>        Per-worker timeout (default: 3600 = 1h)
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

TOPIC="general"
BATCH_SIZE=10
DB_HOST="server-02"
WORKER_TIMEOUT=3600
DISTRIBUTION="roundrobin"

# ---------------------------------------------------------------------------
# ARGUMENT PARSING
# ---------------------------------------------------------------------------

URL_INPUTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic)       TOPIC="$2"; shift 2 ;;
    --batch-size)  BATCH_SIZE="$2"; shift 2 ;;
    --db-host)     DB_HOST="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=true; shift ;;
    --distribution) DISTRIBUTION="$2"; shift 2 ;;
    --timeout)     WORKER_TIMEOUT="$2"; shift 2 ;;
    --output|-o)   OUTPUT_DIR="$2"; shift 2 ;;
    --notify)      export FLEET_NTFY_TOPIC="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS] <url_file_or_urls...>"
      echo ""
      echo "Distribute URL learning across fleet workers."
      echo ""
      echo "Options:"
      echo "  --topic <topic>       Knowledge domain (default: 'general')"
      echo "  --batch-size <n>      URLs per Claude call (default: 10)"
      echo "  --db-host <host>      ChromaDB host (default: server-02)"
      echo "  --dry-run             Show plan without executing"
      echo "  --distribution <m>    roundrobin or weighted (default: roundrobin)"
      echo "  --timeout <sec>       Per-worker timeout (default: 3600)"
      echo "  --output <dir>        Custom output directory"
      echo "  --notify <topic>      ntfy notification topic"
      echo ""
      echo "Input formats:"
      echo "  $0 urls.txt                     # File with one URL per line"
      echo "  $0 https://a.com https://b.com  # URLs as arguments"
      echo "  cat urls.txt | $0 -             # Read from stdin"
      exit 0
      ;;
    *)
      URL_INPUTS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#URL_INPUTS[@]} -eq 0 ]]; then
  echo "ERROR: No URL inputs specified"
  echo "Usage: $0 [OPTIONS] <url_file_or_urls...>"
  exit 1
fi

# ---------------------------------------------------------------------------
# RESOLVE URLS
# ---------------------------------------------------------------------------

ITEMS_FILE=$(mktemp /tmp/fleet-url-items-XXXXXX.txt)
_url_cleanup() { rm -f "$ITEMS_FILE"; }
trap _url_cleanup EXIT

for input in "${URL_INPUTS[@]}"; do
  if [[ "$input" == "-" ]]; then
    cat >> "$ITEMS_FILE"
  elif [[ -f "$input" ]]; then
    grep -v '^\s*#' "$input" | grep -v '^\s*$' >> "$ITEMS_FILE"
  elif [[ "$input" == http* ]]; then
    echo "$input" >> "$ITEMS_FILE"
  else
    fleet_log WARN "Skipping invalid input: $input"
  fi
done

TOTAL_URLS=$(wc -l < "$ITEMS_FILE")

if [[ $TOTAL_URLS -eq 0 ]]; then
  fleet_log ERROR "No URLs found in input"
  exit 1
fi

echo ""
echo "=================================================================="
echo "  BULK URL LEARNING"
echo "=================================================================="
echo "  URLs:        ${TOTAL_URLS}"
echo "  Topic:       ${TOPIC}"
echo "  Batch size:  ${BATCH_SIZE} URLs per Claude call"
echo "  ChromaDB:    ${DB_HOST}"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# FLEET SETUP
# ---------------------------------------------------------------------------

fleet_check_compliance
fleet_discover_workers

START_TIME=$(date +%s)
fleet_init_session "url-learn" "${OUTPUT_DIR:-}"

if [[ "$DISTRIBUTION" == "weighted" ]]; then
  fleet_distribute_weighted "$ITEMS_FILE"
else
  fleet_distribute_roundrobin "$ITEMS_FILE"
fi

# ---------------------------------------------------------------------------
# DRY RUN
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "true" ]]; then
  fleet_dry_run_report "url-learn"

  seq_sec=$((TOTAL_URLS * 10))
  fleet_sec=$((seq_sec / ${#FLEET_WORKERS[@]}))
  echo "Estimated time:"
  echo "  Sequential: ~$((seq_sec / 60))m"
  echo "  Fleet (${#FLEET_WORKERS[@]} workers): ~$((fleet_sec / 60))m"
  echo "  Savings: ~$(((seq_sec - fleet_sec) / 60))m"
  exit 0
fi

# ---------------------------------------------------------------------------
# DISPATCH WORKERS
# ---------------------------------------------------------------------------

fleet_log PHASE "Dispatch URL Learning Workers"

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

  url_json_array=$(python3 -c "
import json
with open('${batch_file}') as f:
    urls = [line.strip() for line in f if line.strip()]
print(json.dumps(urls))
")

  num_batches=$(python3 -c "import math; print(math.ceil(${item_count} / ${BATCH_SIZE}))")

  read -r -d '' worker_prompt << PROMPT_EOF || true
You are a fleet worker learning from web URLs.

TASK: Process ${item_count} URLs in ${num_batches} batches of ${BATCH_SIZE}.
TOPIC: ${TOPIC}
OUTPUT DIRECTORY: ${output_dir}

URL LIST (JSON array):
${url_json_array}

INSTRUCTIONS:
1. Split the URL list into batches of ${BATCH_SIZE} URLs each.
2. For each batch, run /ai-web-learn-production:
   /ai-web-learn-production { "urls": [<batch URLs>], "topic": "${TOPIC}" }
3. After each batch, write extracted facts to ${output_dir}/facts-NNN.json
   Format: {"facts":[{"fact":"...","source":"url","confidence":0.95,"category":"..."}]}
4. Write progress to ${FLEET_PROGRESS_DIR}/progress-${worker}.json after each batch.
5. Process ALL URLs. Skip failures with warnings.
6. Write ${output_dir}/summary.json at end:
   {"worker":"${worker}","urls_processed":N,"facts_extracted":N,"status":"complete"}
PROMPT_EOF

  worker_out="${FLEET_RESULTS_DIR}/worker-${worker}.out"
  worker_status="${FLEET_RESULTS_DIR}/worker-${worker}.status"
  worker_pid_file="${FLEET_RESULTS_DIR}/worker-${worker}.pid"

  fleet_log INFO "Launching on ${worker}: ${item_count} URLs"

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

  fleet_log WORKER "${worker} PID=${pid}, ${item_count} URLs"
done

if [[ ${#FLEET_WORKER_PIDS[@]} -eq 0 ]]; then
  fleet_log ERROR "No workers dispatched"
  exit 1
fi

fleet_log INFO "Dispatched ${#FLEET_WORKER_PIDS[@]} workers"

# ---------------------------------------------------------------------------
# WAIT
# ---------------------------------------------------------------------------

fleet_wait_workers 30
wait_result=$?

# ---------------------------------------------------------------------------
# COLLECT AND MERGE
# ---------------------------------------------------------------------------

fleet_collect_results

fleet_log PHASE "Merge Extracted Facts"

MERGED_FACTS="${FLEET_RESULTS_DIR}/merged-facts.json"

python3 << 'MERGE_SCRIPT'
import json
import glob
import os

results_dir = os.environ.get("FLEET_RESULTS_DIR", "")
if not results_dir:
    # Fallback: find from script args
    import sys
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "."

all_facts = []
url_count = 0

for worker_dir in sorted(glob.glob(os.path.join(results_dir, "output-*"))):
    for facts_file in sorted(glob.glob(os.path.join(worker_dir, "facts-*.json"))):
        try:
            with open(facts_file) as f:
                data = json.load(f)
                facts = data.get("facts", data if isinstance(data, list) else [])
                all_facts.extend(facts)
                print(f"  {os.path.basename(worker_dir)}/{os.path.basename(facts_file)}: {len(facts)} facts")
        except Exception as e:
            print(f"  WARNING: {facts_file}: {e}")

    summary_file = os.path.join(worker_dir, "summary.json")
    if os.path.exists(summary_file):
        try:
            with open(summary_file) as f:
                url_count += json.load(f).get("urls_processed", 0)
        except:
            pass

# Deduplicate by fact content
seen = set()
unique = []
for fact in all_facts:
    key = fact.get("fact", str(fact))[:200]
    if key not in seen:
        seen.add(key)
        unique.append(fact)

merged_file = os.path.join(results_dir, "merged-facts.json")
with open(merged_file, "w") as f:
    json.dump({
        "total_facts": len(unique),
        "duplicates_removed": len(all_facts) - len(unique),
        "urls_processed": url_count,
        "facts": unique
    }, f, indent=2)

print(f"\nMerged: {len(unique)} unique facts ({len(all_facts) - len(unique)} duplicates removed)")
MERGE_SCRIPT

# Export for the python script
export FLEET_RESULTS_DIR

fleet_log OK "Merged facts: ${MERGED_FACTS}"

# ---------------------------------------------------------------------------
# CHROMADB INSERT (single-writer)
# ---------------------------------------------------------------------------

fleet_log PHASE "ChromaDB Insert (${DB_HOST})"

if ssh -o BatchMode=yes -o ConnectTimeout=3 "$DB_HOST" 'echo ok' &>/dev/null; then
  fleet_log INFO "Inserting into ChromaDB on ${DB_HOST}..."

  read -r -d '' chromadb_prompt << CHROMA_EOF || true
Read the merged facts file at ${MERGED_FACTS} and insert all facts into ChromaDB.
Use the /ai-web-learn-production skill ChromaDB integration.
Topic/collection: ${TOPIC}
Report how many facts were stored.
CHROMA_EOF

  escaped_chromadb=$(echo "$chromadb_prompt" | sed "s/'/'\\\\''/g")

  timeout 1800 \
    ssh -o BatchMode=yes "$DB_HOST" \
      "cd '${NFS_ROOT}' && claude -p \
        --dangerously-skip-permissions \
        --output-format text \
        --max-turns 50 \
        --no-session-persistence \
        '${escaped_chromadb}'" \
    > "${FLEET_RESULTS_DIR}/chromadb-insert.out" 2>&1 || true

  fleet_log OK "ChromaDB insert complete"
else
  fleet_log WARN "${DB_HOST} unavailable -- facts saved as JSON only"
  fleet_log INFO "Manual insert later: read ${MERGED_FACTS}"
fi

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

fleet_summary "URL-LEARN" "$START_TIME" "$TOTAL_URLS"

echo "Output files:"
echo "  Merged facts:    ${MERGED_FACTS}"
echo "  Worker outputs:  ${FLEET_RESULTS_DIR}/output-*/"
echo "  Worker logs:     ${FLEET_RESULTS_DIR}/worker-*.out"
echo "  Fleet log:       ${FLEET_LOG_FILE}"
echo ""

fleet_notify "URL Learning Complete" \
  "${TOTAL_URLS} URLs processed by ${#FLEET_WORKER_HOSTS[@]} workers" \
  "default"

exit ${wait_result:-0}
