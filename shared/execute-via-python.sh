#!/bin/bash
#
# Universal Python-based worker execution
# Works on ALL architectures and Python versions
#

set -e

WORKER=$1
MODEL=$2
TASK=$3
MAX_TOKENS=${4:-100}
TIMEOUT_MS=${5:-30000}

if [[ -z "$WORKER" ]] || [[ -z "$MODEL" ]] || [[ -z "$TASK" ]]; then
  echo "Usage: $0 <worker> <model> <task> [max_tokens] [timeout_ms]"
  exit 1
fi

# Validate WORKER to prevent command injection (allow hostnames, IPs, and FQDN only)
if [[ ! "$WORKER" =~ ^[a-zA-Z0-9._-]+$ ]]; then
  echo "{\"error\":\"Invalid worker hostname: contains disallowed characters\"}"
  exit 1
fi

# Validate MAX_TOKENS and TIMEOUT_MS are numeric
if [[ ! "$MAX_TOKENS" =~ ^[0-9]+$ ]] || [[ ! "$TIMEOUT_MS" =~ ^[0-9]+$ ]]; then
  echo "{\"error\":\"MAX_TOKENS and TIMEOUT_MS must be numeric\"}"
  exit 1
fi

# Map model to provider
map_provider() {
  local model=$1
  if [[ "$model" == *"cerebras"* ]] || [[ "$model" == *"zai-glm"* ]]; then
    echo "cerebras"
  elif [[ "$model" == *"gemini"* ]]; then
    echo "google"
  elif [[ "$model" == *"command"* ]]; then
    echo "cohere"
  elif [[ "$model" == *"deepseek"* ]]; then
    echo "deepseek"
  else
    echo "groq"
  fi
}

# Provider config
get_provider_config() {
  local provider=$1
  local model=$2

  case "$provider" in
    groq)
      echo '{"url":"https://api.groq.com/openai/v1/chat/completions","key_env":"GROQ_API_KEY"}'
      ;;
    cerebras)
      echo '{"url":"https://api.cerebras.ai/v1/chat/completions","key_env":"CEREBRAS_API_KEY"}'
      ;;
    google)
      echo "{\"url\":\"https://generativelanguage.googleapis.com/v1beta/models/$model:generateContent\",\"key_env\":\"GOOGLE_API_KEY\"}"
      ;;
    cohere)
      echo '{"url":"https://api.cohere.com/v2/chat","key_env":"COHERE_API_KEY"}'
      ;;
    deepseek)
      echo '{"url":"https://api.deepseek.com/v1/chat/completions","key_env":"DEEPSEEK_API_KEY"}'
      ;;
  esac
}

PROVIDER=$(map_provider "$MODEL")
CONFIG=$(get_provider_config "$PROVIDER" "$MODEL")
URL=$(echo "$CONFIG" | jq -r '.url')
KEY_ENV=$(echo "$CONFIG" | jq -r '.key_env')

# Get API key from local environment
API_KEY=$(bash -c "source ~/.bashrc && echo \$$KEY_ENV")

if [[ -z "$API_KEY" ]]; then
  echo "{\"error\":\"Missing $KEY_ENV in environment\"}"
  exit 1
fi

# Build JSON payload safely using jq to escape all values
PAYLOAD=$(jq -n \
  --arg task "$TASK" \
  --arg model "$MODEL" \
  --argjson max_tokens "$MAX_TOKENS" \
  --arg url "$URL" \
  --arg key_env "$KEY_ENV" \
  --arg api_key "$API_KEY" \
  '{task: $task, model: $model, max_tokens: $max_tokens, url: $url, key_env: $key_env, api_key: $api_key}')

# Execute on worker (use -- to prevent option injection via WORKER)
# Pipe pre-built JSON via printf to avoid heredoc shell expansion
printf '%s\n' "$PAYLOAD" | ssh -- "claude@${WORKER}" "python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/python-worker.py"
