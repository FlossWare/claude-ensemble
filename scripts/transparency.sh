#!/usr/bin/env bash
#
# Transparency Dashboard - CLI tool for viewing fleet activity
#
# Usage:
#   ./scripts/transparency.sh              # Show summary
#   ./scripts/transparency.sh --tail       # Tail live log
#   ./scripts/transparency.sh --events     # Show recent events
#   ./scripts/transparency.sh --bugs       # Show bug tracking status
#   ./scripts/transparency.sh --json       # Output JSON for integrations

set -euo pipefail

TRANSPARENCY_DIR="$HOME/.claude/learning"
LOG_FILE="$TRANSPARENCY_DIR/transparency.log"
JSON_FILE="$TRANSPARENCY_DIR/transparency.json"
STATE_FILE="$TRANSPARENCY_DIR/transparency-state.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
RESET='\033[0m'

# Print colored message
color_print() {
  local color=$1
  shift
  echo -e "${color}$*${RESET}"
}

# Print header
print_header() {
  echo ""
  color_print "$CYAN" "═══════════════════════════════════════════"
  color_print "$CYAN" "  $1"
  color_print "$CYAN" "═══════════════════════════════════════════"
  echo ""
}

# Show summary from state file
show_summary() {
  if [[ ! -f "$STATE_FILE" ]]; then
    color_print "$YELLOW" "No transparency data available yet."
    echo ""
    echo "The fleet will create transparency logs as it operates."
    echo "Run an autonomous workflow to start collecting data."
    exit 0
  fi

  print_header "FLEET TRANSPARENCY SUMMARY"

  # Parse JSON state file
  local summary=$(jq -r '.summary' "$STATE_FILE" 2>/dev/null || echo "{}")
  local last_updated=$(jq -r '.lastUpdated' "$STATE_FILE" 2>/dev/null || echo "unknown")

  color_print "$GRAY" "Last Updated: $last_updated"
  echo ""

  color_print "$BLUE" "BUGS:"
  echo "  Found:   $(echo "$summary" | jq -r '.bugsFound // 0')"
  echo "  Fixed:   $(echo "$summary" | jq -r '.bugsFixed // 0')"
  echo "  Pending: $(echo "$summary" | jq -r '.bugsPending // 0')"
  echo ""

  color_print "$BLUE" "VALIDATIONS:"
  echo "  Passed: $(echo "$summary" | jq -r '.validationsPassed // 0')"
  echo "  Failed: $(echo "$summary" | jq -r '.validationsFailed // 0')"
  echo ""

  color_print "$BLUE" "DEPLOYMENTS:"
  echo "  Success: $(echo "$summary" | jq -r '.deploymentsSuccess // 0')"
  echo "  Failed:  $(echo "$summary" | jq -r '.deploymentsFailed // 0')"
  echo ""

  color_print "$BLUE" "LEARNING:"
  echo "  Sessions Complete: $(echo "$summary" | jq -r '.learningSessionsComplete // 0')"
  echo ""

  color_print "$BLUE" "ISSUES:"
  local issues_created=$(echo "$summary" | jq -r '.issuesCreated // 0')
  local issues_closed=$(echo "$summary" | jq -r '.issuesClosed // 0')
  local issues_open=$((issues_created - issues_closed))
  echo "  Created: $issues_created"
  echo "  Closed:  $issues_closed"
  echo "  Open:    $issues_open"
  echo ""

  color_print "$BLUE" "RECENT EVENTS:"
  jq -r '.recentEvents[-10:] | reverse | .[] | "  [\(.timestamp | split("T")[1] | split(".")[0])] \(.description)"' "$STATE_FILE" 2>/dev/null || echo "  No recent events"
  echo ""
}

# Tail live log
tail_log() {
  print_header "FLEET TRANSPARENCY LOG (Live)"

  if [[ ! -f "$LOG_FILE" ]]; then
    color_print "$YELLOW" "Log file not found: $LOG_FILE"
    echo "Waiting for fleet activity..."
    echo ""
  fi

  # Create log file if it doesn't exist
  mkdir -p "$TRANSPARENCY_DIR"
  touch "$LOG_FILE"

  # Tail with color highlighting
  tail -f "$LOG_FILE" | while read -r line; do
    if [[ "$line" =~ CRITICAL|ERROR ]]; then
      color_print "$RED" "$line"
    elif [[ "$line" =~ WARNING|FAILED ]]; then
      color_print "$YELLOW" "$line"
    elif [[ "$line" =~ SUCCESS|PASSED|COMPLETE ]]; then
      color_print "$GREEN" "$line"
    elif [[ "$line" =~ ^\[.*\] ]]; then
      color_print "$CYAN" "$line"
    else
      echo "$line"
    fi
  done
}

# Show recent events
show_events() {
  print_header "RECENT EVENTS"

  if [[ ! -f "$JSON_FILE" ]]; then
    color_print "$YELLOW" "No events logged yet."
    exit 0
  fi

  # Show last 20 events
  jq -r '.[-20:] | reverse | .[] | "\(.timestamp | split("T")[1] | split(".")[0]) [\(.severity)] \(.type): \(.description // .title // "no description")"' "$JSON_FILE" 2>/dev/null | while read -r line; do
    if [[ "$line" =~ critical ]]; then
      color_print "$RED" "  $line"
    elif [[ "$line" =~ high ]]; then
      color_print "$YELLOW" "  $line"
    elif [[ "$line" =~ medium ]]; then
      color_print "$BLUE" "  $line"
    else
      color_print "$GRAY" "  $line"
    fi
  done

  echo ""
}

# Show bug tracking status
show_bugs() {
  print_header "BUG TRACKING STATUS"

  if [[ ! -f "$JSON_FILE" ]]; then
    color_print "$YELLOW" "No bug data available yet."
    exit 0
  fi

  # Find all bug-related events
  local bugs_found=$(jq '[.[] | select(.type == "bug_found")] | length' "$JSON_FILE" 2>/dev/null || echo "0")
  local bugs_fixed=$(jq '[.[] | select(.type == "fix_success")] | length' "$JSON_FILE" 2>/dev/null || echo "0")
  local bugs_failed=$(jq '[.[] | select(.type == "fix_failed")] | length' "$JSON_FILE" 2>/dev/null || echo "0")

  echo "Total bugs found: $bugs_found"
  echo "Successfully fixed: $bugs_fixed"
  echo "Fix attempts failed: $bugs_failed"
  echo ""

  color_print "$BLUE" "RECENT BUGS:"
  jq -r '.[] | select(.type == "bug_found") | "\(.timestamp | split("T")[1] | split(".")[0]) [\(.severity)] \(.description) @ \(.location // "unknown")"' "$JSON_FILE" 2>/dev/null | tail -10 | while read -r line; do
    if [[ "$line" =~ critical ]]; then
      color_print "$RED" "  $line"
    elif [[ "$line" =~ high ]]; then
      color_print "$YELLOW" "  $line"
    else
      echo "  $line"
    fi
  done

  echo ""

  color_print "$BLUE" "RECENT FIXES:"
  jq -r '.[] | select(.type == "fix_success" or .type == "fix_failed") | "\(.timestamp | split("T")[1] | split(".")[0]) [\(.type)] \(.description)"' "$JSON_FILE" 2>/dev/null | tail -10 | while read -r line; do
    if [[ "$line" =~ fix_success ]]; then
      color_print "$GREEN" "  $line"
    else
      color_print "$RED" "  $line"
    fi
  done

  echo ""
}

# Output raw JSON
show_json() {
  if [[ ! -f "$STATE_FILE" ]]; then
    echo "{}"
    exit 0
  fi

  cat "$STATE_FILE"
}

# Show help
show_help() {
  echo "Transparency Dashboard - Fleet Activity Monitor"
  echo ""
  echo "Usage:"
  echo "  ./scripts/transparency.sh              Show summary"
  echo "  ./scripts/transparency.sh --tail       Tail live log"
  echo "  ./scripts/transparency.sh --events     Show recent events"
  echo "  ./scripts/transparency.sh --bugs       Show bug tracking status"
  echo "  ./scripts/transparency.sh --json       Output JSON for integrations"
  echo "  ./scripts/transparency.sh --help       Show this help"
  echo ""
  echo "Files:"
  echo "  $LOG_FILE"
  echo "  $JSON_FILE"
  echo "  $STATE_FILE"
  echo ""
}

# Main
main() {
  local cmd="${1:-summary}"

  case "$cmd" in
    --tail)
      tail_log
      ;;
    --events)
      show_events
      ;;
    --bugs)
      show_bugs
      ;;
    --json)
      show_json
      ;;
    --help|-h)
      show_help
      ;;
    summary|*)
      show_summary
      ;;
  esac
}

main "$@"
