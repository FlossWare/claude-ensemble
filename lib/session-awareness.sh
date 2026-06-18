#!/usr/bin/env bash
# Session Awareness - Make sessions actively aware of each other

PI02_API="${PI02_API:-http://pi-02:3002}"
CHECK_INTERVAL="${CHECK_INTERVAL:-10}"

get_session_id() {
    local session_file=$(ls -t ~/.claude/sessions/*.json 2>/dev/null | grep -v registry | head -1)
    if [[ -f "$session_file" ]]; then
        jq -r '.sessionId' "$session_file"
    else
        echo "unknown"
    fi
}

# Show notification to user
notify_user() {
    local title="$1"
    local message="$2"
    local urgency="${3:-normal}"

    # Console output
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "🔔 $title"
    echo "───────────────────────────────────────────────────────────"
    echo "$message"
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    # Desktop notification (if available)
    if command -v notify-send &> /dev/null; then
        notify-send -u "$urgency" "$title" "$message"
    fi

    # Write to awareness log
    echo "[$(date -Iseconds)] $title: $message" >> ~/.claude/.session-awareness.log
}

# Check for new sessions
check_new_sessions() {
    local known_sessions_file=~/.claude/.known-sessions
    touch "$known_sessions_file"

    local current_sessions=$(curl -s "$PI02_API/sessions/list" | jq -r '.sessions[].session_id')
    local my_session=$(get_session_id)

    while IFS= read -r session_id; do
        if [[ "$session_id" == "$my_session" ]]; then
            continue
        fi

        if ! grep -q "$session_id" "$known_sessions_file" 2>/dev/null; then
            # New session detected
            local session_info=$(curl -s "$PI02_API/sessions/$session_id")
            local node=$(echo "$session_info" | jq -r '.node')
            local working_on=$(echo "$session_info" | jq -r '.working_on // "unknown"')

            notify_user "New Session Detected" \
                "Session ${session_id:0:8}... started on $node\nWorking on: $working_on" \
                "normal"

            echo "$session_id" >> "$known_sessions_file"
        fi
    done <<< "$current_sessions"

    # Clean up known sessions that are gone
    while IFS= read -r known_session; do
        if ! echo "$current_sessions" | grep -q "$known_session"; then
            sed -i "/$known_session/d" "$known_sessions_file"
        fi
    done < "$known_sessions_file"
}

# Check for activity broadcasts
check_activity_broadcasts() {
    local my_session=$(get_session_id)
    local messages=$(curl -s "$PI02_API/messages/receive?sessionId=$my_session")

    echo "$messages" | jq -c '.messages[]' | while IFS= read -r msg; do
        local msg_id=$(echo "$msg" | jq -r '.id')
        local msg_type=$(echo "$msg" | jq -r '.type')
        local from_session=$(echo "$msg" | jq -r '.from')
        local payload=$(echo "$msg" | jq -r '.payload')

        if [[ "$msg_type" == "activity_broadcast" ]]; then
            local activity_type=$(echo "$payload" | jq -r '.activity_type')
            local activity_data=$(echo "$payload" | jq -r '.data')
            local node=$(echo "$payload" | jq -r '.node')

            case "$activity_type" in
                file_change)
                    notify_user "File Changed on $node" \
                        "Session ${from_session:0:8}... modified: $activity_data" \
                        "low"
                    ;;
                git_commit)
                    notify_user "Git Commit on $node" \
                        "Session ${from_session:0:8}...: $activity_data" \
                        "normal"
                    ;;
                task_start|task_change)
                    notify_user "Task Update on $node" \
                        "Session ${from_session:0:8}... is now: $activity_data" \
                        "low"
                    ;;
                conflict_warning)
                    notify_user "⚠️  CONFLICT WARNING" \
                        "Session ${from_session:0:8}... on $node:\n$activity_data" \
                        "critical"
                    ;;
            esac

            # Mark as delivered
            curl -s -X POST "$PI02_API/messages/$msg_id/delivered" > /dev/null 2>&1
        fi
    done
}

# Check for conflicts with current work
check_for_conflicts() {
    # Get recently modified files
    local recent_files=$(find . -type f \( -name "*.ts" -o -name "*.js" -o -name "*.py" \) -mmin -1 2>/dev/null)

    if [[ -z "$recent_files" ]]; then
        return
    fi

    local files_json=$(echo "$recent_files" | jq -R . | jq -s .)
    local response=$(curl -s -X POST "$PI02_API/sessions/conflicts" \
        -H "Content-Type: application/json" \
        -d "{\"files\": $files_json}")

    if echo "$response" | jq -e '.has_conflicts == true' > /dev/null 2>&1; then
        local conflicts=$(echo "$response" | jq -r '.conflicts | to_entries[] | "\(.key): " + (.value | map(.session_id[0:8] + "... on " + .node) | join(", "))')

        notify_user "⚠️  FILE CONFLICT DETECTED" \
            "You are editing files that another session is working on:\n\n$conflicts\n\nCoordinate before continuing!" \
            "critical"
    fi
}

# Show current fleet status
show_fleet_status() {
    local status=$(curl -s "$PI02_API/status")
    local total_sessions=$(echo "$status" | jq -r '.sessions.total')
    local my_session=$(get_session_id)

    echo "╔════════════════════════════════════════════════════════╗"
    echo "║           FLEET STATUS - $(date +%H:%M:%S)                    ║"
    echo "╠════════════════════════════════════════════════════════╣"
    echo "║ Total Sessions: $total_sessions                                  ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""

    echo "$status" | jq -r '.sessions.by_node | to_entries[] |
        "Node: \(.key)\n" +
        (.value | map("  • Session \(.session_id[0:8])... (PID \(.pid))\n    " +
        (if .working_on then "Working on: \(.working_on)" else "Idle" end)) | join("\n")) +
        "\n"'
}

# Announce this session to others
announce_presence() {
    local my_session=$(get_session_id)
    if [[ "$my_session" == "unknown" ]]; then
        return
    fi

    # Register if not already
    ~/.claude/lib/pi02-session-client.sh register > /dev/null 2>&1

    # Broadcast presence
    local payload=$(cat <<EOF
{
  "from": "$my_session",
  "to": "all",
  "type": "presence_announcement",
  "payload": {
    "action": "joined",
    "node": "$(hostname)",
    "cwd": "$(pwd)",
    "user": "$USER"
  }
}
EOF
)

    curl -s -X POST "$PI02_API/messages/send" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null 2>&1

    echo "✓ Announced presence to fleet"
}

# Main awareness loop
run_awareness_loop() {
    echo "🔍 Session Awareness started"
    echo "Monitoring fleet activity every ${CHECK_INTERVAL}s"
    echo ""

    # Announce presence
    announce_presence

    # Initial fleet status
    show_fleet_status

    while true; do
        sleep $CHECK_INTERVAL

        # Check for new sessions
        check_new_sessions

        # Check for activity broadcasts
        check_activity_broadcasts

        # Check for conflicts
        check_for_conflicts
    done
}

# CLI commands
case "${1:-}" in
    start)
        run_awareness_loop
        ;;

    announce)
        announce_presence
        ;;

    status)
        show_fleet_status
        ;;

    check-conflicts)
        check_for_conflicts
        ;;

    notify)
        shift
        notify_user "Manual Notification" "$@"
        ;;

    *)
        echo "Usage: session-awareness.sh <command>"
        echo ""
        echo "Commands:"
        echo "  start             - Start awareness monitoring loop"
        echo "  announce          - Announce presence to fleet"
        echo "  status            - Show fleet status"
        echo "  check-conflicts   - Check for file conflicts now"
        echo "  notify <message>  - Send manual notification"
        echo ""
        echo "Examples:"
        echo "  session-awareness.sh start"
        echo "  session-awareness.sh announce"
        echo "  session-awareness.sh status"
        ;;
esac
