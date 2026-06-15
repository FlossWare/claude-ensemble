#!/usr/bin/env bash
# =============================================================================
# issue-dashboard.sh - Issue Transparency Dashboard (CLI)
#
# Shows real-time issue resolution status across the fleet:
#   - Open issues (count + list)
#   - Closed issues (count + average time to fix)
#   - In-progress fixes (which fleet agents working on what)
#   - Success rate (% issues auto-fixed without human intervention)
#
# Data sources:
#   - GitHub/GitLab CLI (gh/glab) for issue metadata
#   - Fleet dispatcher (pi-02:3004) for in-progress agent status
#   - Git log for resolution timing
#
# Usage:
#   ./issue-dashboard.sh                    # Full dashboard
#   ./issue-dashboard.sh --json             # JSON output (for Grafana/scripts)
#   ./issue-dashboard.sh --section open     # Only open issues
#   ./issue-dashboard.sh --section closed   # Only closed issues
#   ./issue-dashboard.sh --section active   # Only in-progress fixes
#   ./issue-dashboard.sh --section rate     # Only success rate
#   ./issue-dashboard.sh --repo owner/repo  # Specific repository
#   ./issue-dashboard.sh --prometheus       # Emit Prometheus metrics to stdout
#   ./issue-dashboard.sh --watch            # Auto-refresh every 30s
#
# Environment:
#   FLEET_DISPATCHER_URL  - Fleet dispatcher (default: http://pi-02:3004)
#   ISSUE_CACHE_TTL       - Cache TTL in seconds (default: 60)
#   ISSUE_DASHBOARD_REPO  - Default repo (auto-detected if unset)
# =============================================================================
set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

FLEET_DISPATCHER_URL="${FLEET_DISPATCHER_URL:-http://pi-02:3004}"
ISSUE_CACHE_TTL="${ISSUE_CACHE_TTL:-60}"
CACHE_DIR="/tmp/issue-dashboard-cache"

OUTPUT_FORMAT="cli"    # cli | json | prometheus
SECTION="all"          # all | open | closed | active | rate
TARGET_REPO=""
WATCH_MODE=0
WATCH_INTERVAL=30

# ============================================================================
# COLORS + VISUAL INDICATORS
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      OUTPUT_FORMAT="json"
      shift
      ;;
    --prometheus)
      OUTPUT_FORMAT="prometheus"
      shift
      ;;
    --section)
      SECTION="$2"
      shift 2
      ;;
    --repo)
      TARGET_REPO="$2"
      shift 2
      ;;
    --watch)
      WATCH_MODE=1
      shift
      ;;
    --interval)
      WATCH_INTERVAL="$2"
      shift 2
      ;;
    --help|-h)
      head -30 "$0" | tail -25
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# ============================================================================
# PREREQUISITES
# ============================================================================

detect_platform() {
  local remote_url
  remote_url=$(git remote get-url origin 2>/dev/null || echo "")

  if [[ -z "$remote_url" && -z "$TARGET_REPO" ]]; then
    echo "none"
    return
  fi

  if [[ "$remote_url" == *"gitlab"* ]] || command -v glab &>/dev/null && [[ "$remote_url" == *"gitlab"* ]]; then
    echo "gitlab"
  elif [[ "$remote_url" == *"github"* ]] || command -v gh &>/dev/null; then
    echo "github"
  else
    echo "unknown"
  fi
}

get_repo_slug() {
  if [[ -n "$TARGET_REPO" ]]; then
    echo "$TARGET_REPO"
    return
  fi

  local remote_url
  remote_url=$(git remote get-url origin 2>/dev/null || echo "")

  if [[ -z "$remote_url" ]]; then
    echo ""
    return
  fi

  # Extract owner/repo from URL
  echo "$remote_url" | sed -E 's#.*/([^/]+)/([^/]+?)(\.git)?$#\1/\2#'
}

PLATFORM=$(detect_platform)
REPO_SLUG=$(get_repo_slug)

# ============================================================================
# CACHE HELPERS
# ============================================================================

mkdir -p "$CACHE_DIR"

cache_key() {
  echo "${CACHE_DIR}/$(echo "$1" | md5sum | cut -d' ' -f1)"
}

cache_get() {
  local key
  key=$(cache_key "$1")
  if [[ -f "$key" ]]; then
    local age
    age=$(( $(date +%s) - $(stat -c %Y "$key" 2>/dev/null || echo 0) ))
    if [[ $age -lt $ISSUE_CACHE_TTL ]]; then
      cat "$key"
      return 0
    fi
  fi
  return 1
}

cache_set() {
  local key
  key=$(cache_key "$1")
  cat > "$key"
}

# ============================================================================
# DATA COLLECTION: OPEN ISSUES
# ============================================================================

fetch_open_issues() {
  local cached
  if cached=$(cache_get "open-issues-${REPO_SLUG}"); then
    echo "$cached"
    return
  fi

  local result=""
  case "$PLATFORM" in
    github)
      local repo_flag=""
      [[ -n "$TARGET_REPO" ]] && repo_flag="--repo $TARGET_REPO"
      result=$(gh issue list --state open --json number,title,labels,createdAt,assignees,url --limit 200 $repo_flag 2>/dev/null || echo "[]")
      ;;
    gitlab)
      result=$(glab issue list --state opened --per-page 200 --output-format json 2>/dev/null || echo "[]")
      # Normalize GitLab format to match GitHub JSON structure
      result=$(echo "$result" | jq '[.[] | {
        number: .iid,
        title: .title,
        labels: [.labels[]?],
        createdAt: .created_at,
        assignees: [.assignees[]? | {login: .username}],
        url: .web_url
      }]' 2>/dev/null || echo "[]")
      ;;
    *)
      result="[]"
      ;;
  esac

  echo "$result" | cache_set "open-issues-${REPO_SLUG}"
  echo "$result"
}

# ============================================================================
# DATA COLLECTION: CLOSED ISSUES
# ============================================================================

fetch_closed_issues() {
  local cached
  if cached=$(cache_get "closed-issues-${REPO_SLUG}"); then
    echo "$cached"
    return
  fi

  local result=""
  case "$PLATFORM" in
    github)
      local repo_flag=""
      [[ -n "$TARGET_REPO" ]] && repo_flag="--repo $TARGET_REPO"
      result=$(gh issue list --state closed --json number,title,labels,createdAt,closedAt,url --limit 200 $repo_flag 2>/dev/null || echo "[]")
      ;;
    gitlab)
      result=$(glab issue list --state closed --per-page 200 --output-format json 2>/dev/null || echo "[]")
      result=$(echo "$result" | jq '[.[] | {
        number: .iid,
        title: .title,
        labels: [.labels[]?],
        createdAt: .created_at,
        closedAt: .closed_at,
        url: .web_url
      }]' 2>/dev/null || echo "[]")
      ;;
    *)
      result="[]"
      ;;
  esac

  echo "$result" | cache_set "closed-issues-${REPO_SLUG}"
  echo "$result"
}

# ============================================================================
# DATA COLLECTION: FLEET AGENT STATUS (IN-PROGRESS FIXES)
# ============================================================================

fetch_fleet_status() {
  local cached
  if cached=$(cache_get "fleet-status"); then
    echo "$cached"
    return
  fi

  local result=""

  # Query fleet dispatcher for active jobs
  result=$(curl -sf --connect-timeout 3 "${FLEET_DISPATCHER_URL}/fleet/status" 2>/dev/null || echo '{"servers":[],"active_jobs":[]}')

  echo "$result" | cache_set "fleet-status"
  echo "$result"
}

fetch_active_issue_agents() {
  # Check for worktrees with issue-fixing branches
  local worktrees
  worktrees=$(git worktree list 2>/dev/null | grep "issue-\|fix/" || echo "")

  # Check for running claude processes working on issues
  local claude_procs
  claude_procs=$(ps aux 2>/dev/null | grep -E "claude.*issue|claude.*fix/" | grep -v grep || echo "")

  # Check SSH sessions on fleet workers doing issue work
  local fleet_config="${HOME}/.claude/fleet.json"
  local worker_activity="[]"

  if [[ -f "$fleet_config" ]]; then
    local workers
    workers=$(jq -r '.machines[] | select(.role == "worker") | .hostname' "$fleet_config" 2>/dev/null)

    local activities="["
    local first=1

    for worker in $workers; do
      local worker_status
      worker_status=$(ssh -o BatchMode=yes -o ConnectTimeout=2 "$worker" \
        'ps aux 2>/dev/null | grep -E "claude.*issue|claude.*fix/" | grep -v grep | head -5' 2>/dev/null || echo "")

      local worker_worktrees
      worker_worktrees=$(ssh -o BatchMode=yes -o ConnectTimeout=2 "$worker" \
        'find /home/*/Development -name "worktrees" -path "*/.claude/*" -exec find {} -maxdepth 1 -name "issue-*" -type d \; 2>/dev/null | head -10' 2>/dev/null || echo "")

      if [[ -n "$worker_status" || -n "$worker_worktrees" ]]; then
        [[ $first -eq 0 ]] && activities+=","
        first=0

        local issue_nums=""
        if [[ -n "$worker_worktrees" ]]; then
          issue_nums=$(echo "$worker_worktrees" | grep -oP 'issue-\K\d+' | tr '\n' ',' | sed 's/,$//')
        fi

        local proc_count=0
        if [[ -n "$worker_status" ]]; then
          proc_count=$(echo "$worker_status" | wc -l)
        fi

        activities+=$(jq -n \
          --arg host "$worker" \
          --arg issues "$issue_nums" \
          --argjson procs "$proc_count" \
          --arg worktrees "$worker_worktrees" \
          '{
            hostname: $host,
            issues_in_progress: ($issues | split(",") | map(select(length > 0))),
            active_processes: $procs,
            worktree_paths: ($worktrees | split("\n") | map(select(length > 0)))
          }')
      fi
    done

    worker_activity="${activities}]"
  fi

  # Combine local + fleet activity
  jq -n \
    --arg worktrees "$worktrees" \
    --arg procs "$claude_procs" \
    --argjson fleet "$worker_activity" \
    '{
      local_worktrees: ($worktrees | split("\n") | map(select(length > 0))),
      local_processes: ($procs | split("\n") | map(select(length > 0)) | length),
      fleet_workers: $fleet
    }'
}

# ============================================================================
# DATA COLLECTION: AUTO-FIX SUCCESS RATE
# ============================================================================

calculate_success_rate() {
  local closed_issues="$1"

  # Count issues closed by automation (look for bot/automation labels or commit patterns)
  local total_closed
  total_closed=$(echo "$closed_issues" | jq 'length')

  if [[ "$total_closed" -eq 0 ]]; then
    jq -n '{
      total_closed: 0,
      auto_fixed: 0,
      human_fixed: 0,
      success_rate_pct: 0,
      method: "label+commit heuristic"
    }'
    return
  fi

  # Heuristic 1: Issues with automation-related labels
  local auto_labeled
  auto_labeled=$(echo "$closed_issues" | jq '[.[] | select(
    (.labels // []) | map(. as $l |
      ($l | type) as $t |
      if $t == "object" then ($l.name // "" | ascii_downcase)
      elif $t == "string" then ($l | ascii_downcase)
      else ""
      end
    ) | any(. == "auto-fix" or . == "bot" or . == "automated" or . == "auto-resolved" or . == "claude-fix")
  )] | length')

  # Heuristic 2: Check git log for automated commit patterns
  local auto_commits=0
  if command -v git &>/dev/null && git rev-parse --git-dir &>/dev/null; then
    auto_commits=$(git log --oneline --all --grep="auto-fix\|auto-resolve\|autonomous\|code-solve-auto\|Auto-fixed" --since="90 days ago" 2>/dev/null | wc -l || echo 0)
  fi

  # Heuristic 3: Check for fix/ branches that were merged (auto-created by code-solve-auto)
  local auto_branches=0
  if command -v git &>/dev/null && git rev-parse --git-dir &>/dev/null; then
    auto_branches=$(git branch -r --merged 2>/dev/null | grep -cE "fix/issue-" || echo 0)
  fi

  # Estimate auto-fixed count (use max of heuristics, capped at total)
  local auto_fixed
  auto_fixed=$(( auto_labeled > auto_commits ? auto_labeled : auto_commits ))
  auto_fixed=$(( auto_fixed > auto_branches ? auto_fixed : auto_branches ))
  [[ $auto_fixed -gt $total_closed ]] && auto_fixed=$total_closed

  local human_fixed=$(( total_closed - auto_fixed ))
  local success_rate=0
  [[ $total_closed -gt 0 ]] && success_rate=$(( auto_fixed * 100 / total_closed ))

  jq -n \
    --argjson total "$total_closed" \
    --argjson auto "$auto_fixed" \
    --argjson human "$human_fixed" \
    --argjson rate "$success_rate" \
    '{
      total_closed: $total,
      auto_fixed: $auto,
      human_fixed: $human,
      success_rate_pct: $rate,
      method: "label+commit+branch heuristic"
    }'
}

# ============================================================================
# DATA COLLECTION: RESOLUTION TIMING
# ============================================================================

calculate_avg_fix_time() {
  local closed_issues="$1"

  local total_closed
  total_closed=$(echo "$closed_issues" | jq 'length')

  if [[ "$total_closed" -eq 0 ]]; then
    echo "0"
    return
  fi

  # Calculate average hours from createdAt to closedAt
  echo "$closed_issues" | jq '
    [.[] | select(.createdAt != null and .closedAt != null) |
      ((.closedAt | sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601) -
       (.createdAt | sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601)) / 3600
    ] |
    if length > 0 then (add / length * 10 | round / 10)
    else 0
    end
  ' 2>/dev/null || echo "0"
}

# ============================================================================
# RENDER: CLI OUTPUT
# ============================================================================

render_cli_header() {
  echo ""
  echo -e "${BOLD}${BLUE}=================================================================${RESET}"
  echo -e "${BOLD}${WHITE}             ISSUE TRANSPARENCY DASHBOARD${RESET}"
  echo -e "${BOLD}${BLUE}=================================================================${RESET}"
  echo -e "${DIM}  Repo: ${REPO_SLUG:-<local>}  |  Platform: ${PLATFORM}  |  $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
  echo -e "${BOLD}${BLUE}=================================================================${RESET}"
  echo ""
}

render_cli_open_issues() {
  local open_issues="$1"
  local count
  count=$(echo "$open_issues" | jq 'length')

  echo -e "${BOLD}${YELLOW}  OPEN ISSUES: ${count}${RESET}"
  echo -e "${GRAY}  ----------------------------------------------------------------${RESET}"

  if [[ "$count" -eq 0 ]]; then
    echo -e "  ${GREEN}No open issues${RESET}"
  else
    echo "$open_issues" | jq -r '.[:20] | .[] | "  #\(.number)\t\(.title[:60])\t\(.labels | map(if type == "object" then .name else . end) | join(","))"' 2>/dev/null | \
    while IFS=$'\t' read -r num title labels; do
      local label_str=""
      [[ -n "$labels" ]] && label_str=" ${DIM}[${labels}]${RESET}"
      printf "  ${RED}%-6s${RESET} %-55s%s\n" "$num" "$title" "$label_str"
    done

    if [[ "$count" -gt 20 ]]; then
      echo -e "  ${DIM}... and $((count - 20)) more${RESET}"
    fi
  fi
  echo ""
}

render_cli_closed_issues() {
  local closed_issues="$1"
  local avg_hours="$2"
  local count
  count=$(echo "$closed_issues" | jq 'length')

  # Format average time
  local time_str
  if (( $(echo "$avg_hours > 24" | bc -l 2>/dev/null || echo 0) )); then
    local days
    days=$(echo "$avg_hours / 24" | bc -l 2>/dev/null | xargs printf "%.1f" 2>/dev/null || echo "?")
    time_str="${days} days"
  else
    time_str="${avg_hours} hours"
  fi

  echo -e "${BOLD}${GREEN}  CLOSED ISSUES: ${count}${RESET}    ${DIM}(avg time to fix: ${time_str})${RESET}"
  echo -e "${GRAY}  ----------------------------------------------------------------${RESET}"

  if [[ "$count" -eq 0 ]]; then
    echo -e "  ${DIM}No closed issues${RESET}"
  else
    # Show last 10 closed
    echo "$closed_issues" | jq -r '
      sort_by(.closedAt) | reverse | .[:10] | .[] |
      "  #\(.number)\t\(.title[:50])\t\(.closedAt // "unknown")"
    ' 2>/dev/null | \
    while IFS=$'\t' read -r num title closed; do
      local closed_fmt
      closed_fmt=$(echo "$closed" | cut -c1-10)
      printf "  ${GREEN}%-6s${RESET} %-50s ${DIM}closed %s${RESET}\n" "$num" "$title" "$closed_fmt"
    done

    if [[ "$count" -gt 10 ]]; then
      echo -e "  ${DIM}... and $((count - 10)) more${RESET}"
    fi
  fi
  echo ""
}

render_cli_active_agents() {
  local active_data="$1"

  local local_worktrees
  local_worktrees=$(echo "$active_data" | jq -r '.local_worktrees | length')
  local local_procs
  local_procs=$(echo "$active_data" | jq -r '.local_processes')
  local fleet_workers
  fleet_workers=$(echo "$active_data" | jq -r '.fleet_workers | length')

  local total_active=$(( local_worktrees + local_procs ))

  echo -e "${BOLD}${CYAN}  IN-PROGRESS FIXES${RESET}"
  echo -e "${GRAY}  ----------------------------------------------------------------${RESET}"

  # Local activity
  if [[ $local_worktrees -gt 0 ]]; then
    echo -e "  ${CYAN}Local worktrees:${RESET}"
    echo "$active_data" | jq -r '.local_worktrees[] | "    \(.)"' 2>/dev/null
  fi

  # Fleet worker activity
  if [[ $fleet_workers -gt 0 ]]; then
    echo ""
    echo -e "  ${PURPLE}Fleet workers:${RESET}"
    echo "$active_data" | jq -r '
      .fleet_workers[] |
      "    \(.hostname): \(if (.issues_in_progress | length) > 0 then "issues " + (.issues_in_progress | map("#\(.)") | join(", ")) else "active (\(.active_processes) procs)" end)"
    ' 2>/dev/null | while read -r line; do
      echo -e "  ${PURPLE}${line}${RESET}"
    done
  fi

  if [[ $total_active -eq 0 && $fleet_workers -eq 0 ]]; then
    echo -e "  ${DIM}No active issue-fixing agents${RESET}"
  fi
  echo ""
}

render_cli_success_rate() {
  local rate_data="$1"

  local total
  total=$(echo "$rate_data" | jq '.total_closed')
  local auto
  auto=$(echo "$rate_data" | jq '.auto_fixed')
  local human
  human=$(echo "$rate_data" | jq '.human_fixed')
  local rate
  rate=$(echo "$rate_data" | jq '.success_rate_pct')

  echo -e "${BOLD}${WHITE}  AUTO-FIX SUCCESS RATE${RESET}"
  echo -e "${GRAY}  ----------------------------------------------------------------${RESET}"

  # Visual bar
  local bar_width=40
  local filled=$(( rate * bar_width / 100 ))
  [[ $filled -gt $bar_width ]] && filled=$bar_width

  local bar_color="$RED"
  [[ $rate -ge 30 ]] && bar_color="$YELLOW"
  [[ $rate -ge 60 ]] && bar_color="$GREEN"

  printf "  ["
  for ((i=0; i<filled; i++)); do printf "${bar_color}#${RESET}"; done
  for ((i=filled; i<bar_width; i++)); do printf "${GRAY}-${RESET}"; done
  printf "] ${BOLD}${rate}%%${RESET}\n"

  echo ""
  echo -e "  ${GREEN}Auto-fixed:${RESET}  ${auto} issues"
  echo -e "  ${YELLOW}Human-fixed:${RESET} ${human} issues"
  local method
  method=$(echo "$rate_data" | jq -r '.method' 2>/dev/null || echo "heuristic")
  echo -e "  ${DIM}Total closed: ${total} | Detection: ${method}${RESET}"
  echo ""
}

render_cli_footer() {
  echo -e "${BOLD}${BLUE}=================================================================${RESET}"
  echo -e "${DIM}  Fleet dispatcher: ${FLEET_DISPATCHER_URL}${RESET}"
  echo -e "${DIM}  Cache TTL: ${ISSUE_CACHE_TTL}s | Clear cache: rm -rf ${CACHE_DIR}${RESET}"
  echo -e "${BOLD}${BLUE}=================================================================${RESET}"
  echo ""
}

# ============================================================================
# RENDER: JSON OUTPUT
# ============================================================================

render_json() {
  local open_issues="$1"
  local closed_issues="$2"
  local avg_hours="$3"
  local active_data="$4"
  local rate_data="$5"

  jq -n \
    --arg repo "$REPO_SLUG" \
    --arg platform "$PLATFORM" \
    --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson open "$open_issues" \
    --argjson closed "$closed_issues" \
    --argjson avg_fix_hours "$avg_hours" \
    --argjson active "$active_data" \
    --argjson rate "$rate_data" \
    '{
      repository: $repo,
      platform: $platform,
      timestamp: $timestamp,
      open_issues: {
        count: ($open | length),
        issues: $open
      },
      closed_issues: {
        count: ($closed | length),
        avg_fix_time_hours: $avg_fix_hours,
        issues: $closed
      },
      in_progress: $active,
      success_rate: $rate
    }'
}

# ============================================================================
# RENDER: PROMETHEUS METRICS
# ============================================================================

render_prometheus() {
  local open_issues="$1"
  local closed_issues="$2"
  local avg_hours="$3"
  local active_data="$4"
  local rate_data="$5"

  local repo_label
  repo_label=$(echo "$REPO_SLUG" | sed 's/[^a-zA-Z0-9_]/_/g')

  local open_count
  open_count=$(echo "$open_issues" | jq 'length')
  local closed_count
  closed_count=$(echo "$closed_issues" | jq 'length')
  local auto_fixed
  auto_fixed=$(echo "$rate_data" | jq '.auto_fixed')
  local human_fixed
  human_fixed=$(echo "$rate_data" | jq '.human_fixed')
  local success_rate
  success_rate=$(echo "$rate_data" | jq '.success_rate_pct')
  local active_local
  active_local=$(echo "$active_data" | jq '.local_processes + (.local_worktrees | length)')
  local active_fleet
  active_fleet=$(echo "$active_data" | jq '[.fleet_workers[]? | .active_processes] | add // 0')

  cat <<PROM
# HELP issues_open_total Number of open issues
# TYPE issues_open_total gauge
issues_open_total{repo="${repo_label}"} ${open_count}

# HELP issues_closed_total Number of closed issues
# TYPE issues_closed_total gauge
issues_closed_total{repo="${repo_label}"} ${closed_count}

# HELP issues_avg_fix_hours Average hours to fix an issue
# TYPE issues_avg_fix_hours gauge
issues_avg_fix_hours{repo="${repo_label}"} ${avg_hours}

# HELP issues_auto_fixed_total Issues auto-fixed by AI agents
# TYPE issues_auto_fixed_total gauge
issues_auto_fixed_total{repo="${repo_label}"} ${auto_fixed}

# HELP issues_human_fixed_total Issues fixed by humans
# TYPE issues_human_fixed_total gauge
issues_human_fixed_total{repo="${repo_label}"} ${human_fixed}

# HELP issues_auto_fix_success_rate_pct Percentage of issues auto-fixed
# TYPE issues_auto_fix_success_rate_pct gauge
issues_auto_fix_success_rate_pct{repo="${repo_label}"} ${success_rate}

# HELP issues_agents_active_local Locally active issue-fixing agents
# TYPE issues_agents_active_local gauge
issues_agents_active_local{repo="${repo_label}"} ${active_local}

# HELP issues_agents_active_fleet Fleet agents fixing issues
# TYPE issues_agents_active_fleet gauge
issues_agents_active_fleet{repo="${repo_label}"} ${active_fleet}
PROM
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

run_dashboard() {
  # Collect data
  local open_issues closed_issues avg_hours active_data rate_data

  if [[ "$SECTION" == "all" || "$SECTION" == "open" ]]; then
    open_issues=$(fetch_open_issues)
  else
    open_issues="[]"
  fi

  if [[ "$SECTION" == "all" || "$SECTION" == "closed" || "$SECTION" == "rate" ]]; then
    closed_issues=$(fetch_closed_issues)
  else
    closed_issues="[]"
  fi

  avg_hours=$(calculate_avg_fix_time "$closed_issues")

  if [[ "$SECTION" == "all" || "$SECTION" == "active" ]]; then
    active_data=$(fetch_active_issue_agents)
  else
    active_data='{"local_worktrees":[],"local_processes":0,"fleet_workers":[]}'
  fi

  if [[ "$SECTION" == "all" || "$SECTION" == "rate" ]]; then
    rate_data=$(calculate_success_rate "$closed_issues")
  else
    rate_data='{"total_closed":0,"auto_fixed":0,"human_fixed":0,"success_rate_pct":0,"method":"skipped"}'
  fi

  # Render
  case "$OUTPUT_FORMAT" in
    json)
      render_json "$open_issues" "$closed_issues" "$avg_hours" "$active_data" "$rate_data"
      ;;
    prometheus)
      render_prometheus "$open_issues" "$closed_issues" "$avg_hours" "$active_data" "$rate_data"
      ;;
    cli)
      render_cli_header

      if [[ "$SECTION" == "all" || "$SECTION" == "open" ]]; then
        render_cli_open_issues "$open_issues"
      fi

      if [[ "$SECTION" == "all" || "$SECTION" == "closed" ]]; then
        render_cli_closed_issues "$closed_issues" "$avg_hours"
      fi

      if [[ "$SECTION" == "all" || "$SECTION" == "active" ]]; then
        render_cli_active_agents "$active_data"
      fi

      if [[ "$SECTION" == "all" || "$SECTION" == "rate" ]]; then
        render_cli_success_rate "$rate_data"
      fi

      render_cli_footer
      ;;
  esac
}

# ============================================================================
# WATCH MODE
# ============================================================================

if [[ $WATCH_MODE -eq 1 ]]; then
  while true; do
    clear
    run_dashboard
    echo -e "${DIM}  Auto-refreshing every ${WATCH_INTERVAL}s (Ctrl+C to stop)${RESET}"
    sleep "$WATCH_INTERVAL"
    # Invalidate cache on refresh
    rm -rf "$CACHE_DIR"
    mkdir -p "$CACHE_DIR"
  done
else
  run_dashboard
fi
