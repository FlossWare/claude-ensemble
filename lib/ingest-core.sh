#!/usr/bin/env bash
# Shared library for knowledge base auto-ingestion hooks.
# Source this from any hook: source ~/.claude/lib/ingest-core.sh

set -euo pipefail

SPOOL_DIR="$HOME/.claude/spool"
SPOOL_FILE="$SPOOL_DIR/ingest-backlog.jsonl"
SPOOL_MAX_BYTES=52428800  # 50MB
DEDUP_FILE="/tmp/claude-ingest-seen-$$"
API_CACHE="/tmp/claude-ingest-api"

_ensure_spool_dir() {
    [ -d "$SPOOL_DIR" ] || mkdir -p "$SPOOL_DIR"
}

detect_api() {
    if [ -f "$API_CACHE" ]; then
        local cached
        cached=$(cat "$API_CACHE" 2>/dev/null)
        if [ -n "$cached" ]; then
            echo "$cached"
            return 0
        fi
    fi

    for endpoint in "http://localhost:5000" "http://aio-01:5000"; do
        if curl -sf --connect-timeout 1 --max-time 2 "$endpoint/health" >/dev/null 2>&1; then
            echo "$endpoint" > "$API_CACHE"
            echo "$endpoint"
            return 0
        fi
    done
    return 1
}

queue_push() {
    local queue="$1"
    local payload="$2"
    local api
    api=$(detect_api) || { spool_write "$payload"; return 1; }

    local body
    body=$(python3 -c "
import json, sys
print(json.dumps({'queue': sys.argv[1], 'data': json.loads(sys.argv[2]), 'priority': 1}))
" "$queue" "$payload" 2>/dev/null) || { spool_write "$payload"; return 1; }

    local status
    status=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 --max-time 3 \
        -X POST "$api/queue/add" \
        -H "Content-Type: application/json" \
        -d "$body" 2>/dev/null) || status="000"

    if [ "$status" = "200" ] || [ "$status" = "201" ]; then
        return 0
    else
        spool_write "$payload"
        return 1
    fi
}

spool_write() {
    local payload="$1"
    _ensure_spool_dir

    if [ -f "$SPOOL_FILE" ]; then
        local size
        size=$(stat -c%s "$SPOOL_FILE" 2>/dev/null || echo 0)
        if [ "$size" -gt "$SPOOL_MAX_BYTES" ]; then
            mv "$SPOOL_FILE" "${SPOOL_FILE}.1"
        fi
    fi

    (
        flock -w 2 200 || exit 1
        echo "$payload" >> "$SPOOL_FILE"
    ) 200>"${SPOOL_FILE}.lock"
}

content_hash() {
    echo -n "$1" | sha256sum | cut -c1-16
}

maybe_skip() {
    local hash="$1"
    if [ -f "$DEDUP_FILE" ] && grep -qF "$hash" "$DEDUP_FILE" 2>/dev/null; then
        return 0  # skip
    fi
    echo "$hash" >> "$DEDUP_FILE"
    return 1  # proceed
}

build_envelope() {
    local event_type="$1"
    local payload="$2"

    local hash
    hash=$(content_hash "$payload")

    python3 -c "
import json, sys, os
from datetime import datetime, timezone

envelope = {
    'source': 'claude-code-hook',
    'event_type': sys.argv[1],
    'session_id': os.environ.get('CLAUDE_SESSION_ID', 'unknown'),
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'cwd': os.environ.get('PWD', os.getcwd()),
    'content_hash': sys.argv[2],
    'payload': json.loads(sys.argv[3])
}
print(json.dumps(envelope))
" "$event_type" "$hash" "$payload"
}

read_stdin_json() {
    python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(json.dumps(data))
except:
    print('{}')
"
}
