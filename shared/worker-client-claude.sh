#!/bin/bash
# Claude Code Worker Client - Executes prompts with Bash tool access
# Used by fleet orchestrator for command execution tasks

PROMPT="$1"
MODEL="${2:-sonnet}"

if [ -z "$PROMPT" ]; then
  echo '{"error": "No prompt provided"}' >&2
  exit 1
fi

# Use Claude Code with /fast mode for quick responses
# Suppress interactive prompts with --yes flag if available
RESPONSE=$(echo "$PROMPT" | claude --model "$MODEL" 2>&1)

# Extract just the response (skip prompts/metadata)
echo "$RESPONSE" | tail -n +2
