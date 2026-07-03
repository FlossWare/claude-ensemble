#!/bin/bash
# Worker API Client - All 8 nodes use this
# Just makes HTTP call to aio-01:8000 proxy

PROMPT="$1"
MODEL="${2:-llama-3.3-70b-versatile}"

if [ -z "$PROMPT" ]; then
  echo '{"error": "No prompt provided"}' >&2
  exit 1
fi

# Use Python for proper JSON escaping (handles all special chars)
ESCAPED=$(python3 -c 'import sys, json; print(json.dumps(sys.argv[1]))' "$PROMPT")

curl -s -X POST http://aio-01:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Worker-ID: $(hostname)" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":$ESCAPED}]}" \
  2>/dev/null | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' || echo "API Error"
