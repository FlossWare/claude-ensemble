#!/bin/bash
# Worker API Client - FIXED to execute commands directly
# Detects shell commands and executes them instead of describing them

PROMPT="$1"
MODEL="${2:-llama-3.3-70b-versatile}"

if [ -z "$PROMPT" ]; then
  echo '{"error": "No prompt provided"}' >&2
  exit 1
fi

# Check if prompt looks like a shell command
# Patterns: starts with cd/python/node/bash/sh/exec OR contains &&/||/;
if [[ "$PROMPT" =~ ^(cd|python|python3|node|bash|sh|exec|npm|git|ls|cat|echo|find|grep|curl|wget|ssh|scp|rsync) ]] || \
   [[ "$PROMPT" =~ (&&|\|\||;|\|) ]]; then
  
  # EXECUTE the command directly
  eval "$PROMPT" 2>&1
  exit $?
else
  # Send to LLM API (for non-command prompts)
  ESCAPED=$(echo "$PROMPT" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
  
  curl -s -X POST http://aio-01:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "X-Worker-ID: $(hostname)" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"$ESCAPED\"}]}" \
    2>/dev/null | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' || echo "API Error"
fi
