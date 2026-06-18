#!/usr/bin/env bash
# Session Activity Tracker - Monitor and broadcast all session activity

PI02_API="${PI02_API:-http://pi-02:3002}"
WATCH_INTERVAL="${WATCH_INTERVAL:-5}"
SESSION_FILE="$(ls -t ~/.claude/sessions/*.json 2>/dev/null | grep -v registry | head -1)"

# State tracking
declare -A LAST_FILE_TIMES
declare -A LAST_GIT_SHA
LAST_BROADCAST=""

get_session_id() {
    if [[ -f "$SESSION_FILE" ]]; then
        jq -r '.sessionId' "$SESSION_FILE"
    else
        echo "unknown"
    fi
}

# Detect file changes in current directory
detect_file_changes() {
    local cwd="${1:-$(pwd)}"
    local changes=()

    # Find recently modified files (last 10 seconds)
    while IFS= read -r file; do
        local mtime=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null)
        local now=$(date +%s)
        local age=$((now - mtime))

        if [[ $age -lt 10 ]]; then
            # Check if this is a new change
            local last_time="${LAST_FILE_TIMES[$file]:-0}"
            if [[ $mtime -gt $last_time ]]; then
                changes+=("$file")
                LAST_FILE_TIMES[$file]=$mtime
            fi
        fi
    done < <(find "$cwd" -type f -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.sh" 2>/dev/null | head -100)

    if [[ ${#changes[@]} -gt 0 ]]; then
        echo "${changes[@]}"
    fi
}

# Detect git commits
detect_git_commits() {
    if [[ ! -d .git ]]; then
        return
    fi

    local current_sha=$(git rev-parse HEAD 2>/dev/null)
    local current_branch=$(git branch --show-current 2>/dev/null)

    if [[ -z "$current_sha" ]]; then
        return
    fi

    local repo_key="$(pwd):$current_branch"
    local last_sha="${LAST_GIT_SHA[$repo_key]}"

    if [[ -n "$last_sha" && "$current_sha" != "$last_sha" ]]; then
        # New commit detected
        local commit_msg=$(git log -1 --pretty=format:"%s" 2>/dev/null)
        local author=$(git log -1 --pretty=format:"%an" 2>/dev/null)
        local files_changed=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | wc -l)

        echo "COMMIT:$current_branch:$commit_msg:$files_changed files"
    fi

    LAST_GIT_SHA[$repo_key]=$current_sha
}

# Detect current task from various sources
detect_current_task() {
    local task=""

    # Check if there's a task file
    if [[ -f ~/.claude/.current-task ]]; then
        task=$(cat ~/.claude/.current-task)
    fi

    # Check git branch for task info
    if [[ -z "$task" && -d .git ]]; then
        local branch=$(git branch --show-current 2>/dev/null)
        if [[ -n "$branch" && "$branch" != "main" && "$branch" != "master" ]]; then
            task="Working on branch: $branch"
        fi
    fi

    # Check most recently edited file
    if [[ -z "$task" ]]; then
        local recent_file=$(find . -type f \( -name "*.ts" -o -name "*.js" -o -name "*.py" \) -mmin -5 2>/dev/null | head -1)
        if [[ -n "$recent_file" ]]; then
            task="Editing: $(basename "$recent_file")"
        fi
    fi

    echo "$task"
}

# Broadcast activity to pi-02
broadcast_activity() {
    local activity_type="$1"
    local activity_data="$2"
    local session_id=$(get_session_id)

    if [[ -z "$session_id" || "$session_id" == "unknown" ]]; then
        return
    fi

    # Build activity payload
    local payload=$(cat <<EOF
{
  "sessionId": "$session_id",
  "activity": {
    "type": "$activity_type",
    "data": "$activity_data",
    "timestamp": "$(date -Iseconds)"
  }
}
EOF
)

    # Send heartbeat with activity
    curl -s -X POST "$PI02_API/sessions/heartbeat" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null 2>&1

    # Also broadcast as message to all sessions
    local broadcast_payload=$(cat <<EOF
{
  "from": "$session_id",
  "to": "all",
  "type": "activity_broadcast",
  "payload": {
    "activity_type": "$activity_type",
    "data": "$activity_data",
    "node": "$(hostname)",
    "cwd": "$(pwd)"
  }
}
EOF
)

    curl -s -X POST "$PI02_API/messages/send" \
        -H "Content-Type: application/json" \
        -d "$broadcast_payload" > /dev/null 2>&1
}

# Main monitoring loop
monitor_activity() {
    local last_task=""
    local last_files=""

    echo "🔍 Session Activity Tracker started"
    echo "Monitoring: $(pwd)"
    echo "Interval: ${WATCH_INTERVAL}s"
    echo ""

    while true; do
        # Detect current task
        local current_task=$(detect_current_task)
        if [[ -n "$current_task" && "$current_task" != "$last_task" ]]; then
            echo "[$(date +%H:%M:%S)] Task changed: $current_task"
            broadcast_activity "task_change" "$current_task"
            last_task="$current_task"
        fi

        # Detect file changes
        local changed_files=$(detect_file_changes)
        if [[ -n "$changed_files" ]]; then
            local file_list=$(echo "$changed_files" | tr ' ' '\n' | head -5 | tr '\n' ',' | sed 's/,$//')
            if [[ "$file_list" != "$last_files" ]]; then
                echo "[$(date +%H:%M:%S)] Files changed: $file_list"
                broadcast_activity "file_change" "$file_list"
                last_files="$file_list"
            fi
        fi

        # Detect git commits
        local git_activity=$(detect_git_commits)
        if [[ -n "$git_activity" ]]; then
            echo "[$(date +%H:%M:%S)] Git: $git_activity"
            broadcast_activity "git_commit" "$git_activity"
        fi

        sleep $WATCH_INTERVAL
    done
}

# CLI commands
case "${1:-}" in
    monitor)
        monitor_activity
        ;;

    broadcast)
        shift
        local type="${1:-manual}"
        local data="${2:-}"
        broadcast_activity "$type" "$data"
        ;;

    task)
        shift
        local task="$@"
        echo "$task" > ~/.claude/.current-task
        broadcast_activity "task_start" "$task"
        echo "✓ Task set: $task"
        ;;

    *)
        echo "Usage: session-activity-tracker.sh <command>"
        echo ""
        echo "Commands:"
        echo "  monitor              - Start activity monitoring loop"
        echo "  broadcast <type> <data> - Manual broadcast"
        echo "  task <description>   - Set current task"
        echo ""
        echo "Examples:"
        echo "  session-activity-tracker.sh monitor"
        echo "  session-activity-tracker.sh task 'Implementing OAuth login'"
        echo "  session-activity-tracker.sh broadcast file_edit 'src/auth/login.ts'"
        ;;
esac
