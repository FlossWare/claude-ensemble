#!/bin/bash
# Worker API Client - SECURE version
# Executes commands via strict allowlist, NOT eval

PROMPT="$1"
MODEL="${2:-llama-3.3-70b-versatile}"

if [ -z "$PROMPT" ]; then
  echo '{"error": "No prompt provided"}' >&2
  exit 1
fi

# SECURE: Strict allowlist - only these exact patterns execute
case "$PROMPT" in
  # Pattern: cd + python3 tools test
  "cd /mnt/aio-01/claude-orchestrator && python3 tools/"*".py --test")
    cd /mnt/aio-01/claude-orchestrator || exit 1
    # Extract just the python3 command part
    cmd="${PROMPT#cd /mnt/aio-01/claude-orchestrator && }"
    exec $cmd
    ;;

  # Pattern: python3 arithmetic (2 + 2 only for now)
  'python3 -c "print(2 + 2)"')
    exec python3 -c "print(2 + 2)"
    ;;

  # Pattern: echo with quoted string (alphanumeric + spaces only)
  echo\ \"*\")
    # Extract quoted string, validate alphanumeric + spaces
    str="${PROMPT#echo \"}"
    str="${str%\"}"
    if [[ "$str" =~ ^[a-zA-Z0-9\ ]+$ ]]; then
      echo "$str"
      exit 0
    fi
    ;;

  # Pattern: Simple status commands
  "ls"|"pwd"|"hostname"|"date"|"whoami"|"uptime")
    exec $PROMPT
    ;;
esac

# NOT in allowlist - send to LLM API (DO NOT EXECUTE)
ESCAPED=$(echo "$PROMPT" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')

curl -s -X POST http://aio-01:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Worker-ID: $(hostname)" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"$ESCAPED\"}]}" \
  2>/dev/null | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' || echo "API Error"
