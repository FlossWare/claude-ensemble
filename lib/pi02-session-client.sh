#!/usr/bin/env bash
# pi-02 Session Client - Register and maintain heartbeat with pi-02 orchestrator

PI02_API="${PI02_API:-http://pi-02:3002}"
SESSION_FILE="$(ls -t ~/.claude/sessions/*.json 2>/dev/null | grep -v registry | head -1)"
HEARTBEAT_INTERVAL="${HEARTBEAT_INTERVAL:-60}"

# Get session info
get_session_info() {
    if [[ ! -f "$SESSION_FILE" ]]; then
        echo "ERROR: No session file found" >&2
        return 1
    fi

    SESSION_ID=$(jq -r '.sessionId' "$SESSION_FILE")
    PID=$(jq -r '.pid' "$SESSION_FILE")
    CWD=$(jq -r '.cwd' "$SESSION_FILE")
    VERSION=$(jq -r '.version' "$SESSION_FILE")

    export SESSION_ID PID CWD VERSION
}

# Register session with pi-02
register_session() {
    get_session_info || return 1

    local payload=$(cat <<EOF
{
  "sessionId": "$SESSION_ID",
  "node": "$(hostname)",
  "pid": $PID,
  "cwd": "$CWD",
  "version": "$VERSION",
  "status": "active"
}
EOF
)

    local response=$(curl -s -X POST "$PI02_API/sessions/register" \
        -H "Content-Type: application/json" \
        -d "$payload")

    if echo "$response" | jq -e '.status' > /dev/null 2>&1; then
        echo "✓ Session registered with pi-02: $SESSION_ID"
        return 0
    else
        echo "✗ Failed to register: $response" >&2
        return 1
    fi
}

# Send heartbeat
heartbeat() {
    get_session_info || return 1

    local working_on="${1:-}"
    local files_locked="${2:-[]}"

    local payload=$(cat <<EOF
{
  "sessionId": "$SESSION_ID",
  "working_on": "$working_on",
  "files_locked": $files_locked
}
EOF
)

    curl -s -X POST "$PI02_API/sessions/heartbeat" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null 2>&1
}

# Unregister session (on exit)
unregister_session() {
    get_session_info || return 1

    curl -s -X DELETE "$PI02_API/sessions/$SESSION_ID" > /dev/null 2>&1
    echo "✓ Session unregistered from pi-02"
}

# Start heartbeat loop in background
start_heartbeat_loop() {
    (
        while true; do
            sleep $HEARTBEAT_INTERVAL
            heartbeat "$@" 2>/dev/null || break
        done
    ) &
    HEARTBEAT_PID=$!
    echo $HEARTBEAT_PID > "$HOME/.claude/.pi02-heartbeat.pid"
}

# Stop heartbeat loop
stop_heartbeat_loop() {
    if [[ -f "$HOME/.claude/.pi02-heartbeat.pid" ]]; then
        local pid=$(cat "$HOME/.claude/.pi02-heartbeat.pid")
        kill $pid 2>/dev/null || true
        rm -f "$HOME/.claude/.pi02-heartbeat.pid"
    fi
}

# Check conflicts before starting work
check_conflicts() {
    local files="$@"
    local files_json=$(printf '%s\n' "$files" | jq -R . | jq -s .)

    local payload=$(cat <<EOF
{
  "files": $files_json
}
EOF
)

    local response=$(curl -s -X POST "$PI02_API/sessions/conflicts" \
        -H "Content-Type: application/json" \
        -d "$payload")

    if echo "$response" | jq -e '.has_conflicts == true' > /dev/null 2>&1; then
        echo "⚠️  Conflicts detected!" >&2
        echo "$response" | jq '.conflicts' >&2
        return 1
    else
        echo "✓ No conflicts"
        return 0
    fi
}

# Get messages from pi-02
get_messages() {
    get_session_info || return 1

    curl -s "$PI02_API/messages/receive?sessionId=$SESSION_ID" | jq '.messages'
}

# Main command dispatcher
case "${1:-}" in
    register)
        register_session
        ;;
    heartbeat)
        heartbeat "$2" "$3"
        ;;
    unregister)
        unregister_session
        ;;
    start-heartbeat)
        register_session && start_heartbeat_loop
        ;;
    stop-heartbeat)
        stop_heartbeat_loop && unregister_session
        ;;
    conflicts)
        shift
        check_conflicts "$@"
        ;;
    messages)
        get_messages
        ;;
    *)
        echo "Usage: pi02-session-client.sh <command>"
        echo ""
        echo "Commands:"
        echo "  register           - Register session with pi-02"
        echo "  heartbeat [msg]    - Send heartbeat"
        echo "  unregister         - Unregister session"
        echo "  start-heartbeat    - Register and start heartbeat loop"
        echo "  stop-heartbeat     - Stop heartbeat and unregister"
        echo "  conflicts <files>  - Check for file conflicts"
        echo "  messages           - Get messages for this session"
        ;;
esac
