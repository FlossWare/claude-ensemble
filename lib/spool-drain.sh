#!/usr/bin/env bash
# Drains local spool backlog when orchestrator becomes available.
# Run via cron (*/5 * * * *) or call from session-start.
set -euo pipefail
source "$HOME/.claude/lib/ingest-core.sh"

SPOOL_FILE="$HOME/.claude/spool/ingest-backlog.jsonl"

[ -f "$SPOOL_FILE" ] || exit 0
[ -s "$SPOOL_FILE" ] || exit 0

API=$(detect_api) || exit 0

TEMP=$(mktemp)
REMAINING=$(mktemp)
cp "$SPOOL_FILE" "$TEMP"

processed=0
failed=0

while IFS= read -r line; do
    [ -z "$line" ] && continue

    body=$(python3 -c "
import json, sys
print(json.dumps({'queue': 'knowledge', 'data': json.loads(sys.argv[1]), 'priority': 1}))
" "$line" 2>/dev/null) || { echo "$line" >> "$REMAINING"; failed=$((failed + 1)); continue; }

    status=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 --max-time 3 \
        -X POST "$API/queue/add" \
        -H "Content-Type: application/json" \
        -d "$body" 2>/dev/null) || status="000"

    if [ "$status" = "200" ] || [ "$status" = "201" ]; then
        processed=$((processed + 1))
    else
        echo "$line" >> "$REMAINING"
        failed=$((failed + 1))
        break
    fi
done < "$TEMP"

if [ -s "$REMAINING" ]; then
    (
        flock -w 2 200 || exit 1
        cp "$REMAINING" "$SPOOL_FILE"
    ) 200>"${SPOOL_FILE}.lock"
else
    rm -f "$SPOOL_FILE"
fi

rm -f "$TEMP" "$REMAINING"

[ $processed -gt 0 ] && echo "Drained $processed items from spool ($failed remaining)"
