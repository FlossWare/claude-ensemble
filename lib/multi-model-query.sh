#!/usr/bin/env bash
# Multi-model query helper — calls free API providers in parallel, returns JSON array.
# Usage: multi-model-query.sh --prompt "..." [--models "groq/llama-3.3-70b-versatile,..."] [--task-type code_review] [--timeout 30] [--max-tokens 2048]
#
# Tested working providers (2026-07-17):
#   groq     — llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768
#   cerebras — gpt-oss-120b, gemma-4-31b, zai-glm-4.7
#   cohere   — command-a-03-2025 (non-OpenAI response format, handled internally)
#   openrouter — various :free models (rate-limited, best-effort)

set -euo pipefail

API_BASE="http://aio-01:5000"
TMPDIR_BASE="${HOME}/.claude/.mmq-$$"
mkdir -p "$TMPDIR_BASE"
trap 'rm -rf "$TMPDIR_BASE"' EXIT

PROMPT=""
MODELS=""
TASK_TYPE="general"
TIMEOUT=30
MAX_TOKENS=2048
SYSTEM_PROMPT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)      PROMPT="$2"; shift 2 ;;
    --models)      MODELS="$2"; shift 2 ;;
    --task-type)   TASK_TYPE="$2"; shift 2 ;;
    --timeout)     TIMEOUT="$2"; shift 2 ;;
    --max-tokens)  MAX_TOKENS="$2"; shift 2 ;;
    --system)      SYSTEM_PROMPT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$PROMPT" ]]; then
  echo '{"error":"--prompt is required"}' >&2
  exit 1
fi

declare -A PROVIDER_ENDPOINTS=(
  ["groq"]="https://api.groq.com/openai/v1/chat/completions"
  ["openrouter"]="https://openrouter.ai/api/v1/chat/completions"
  ["cerebras"]="https://api.cerebras.ai/v1/chat/completions"
  ["deepseek"]="https://api.deepseek.com/chat/completions"
  ["mistral"]="https://api.mistral.ai/v1/chat/completions"
  ["deepinfra"]="https://api.deepinfra.com/v1/openai/chat/completions"
  ["cohere"]="https://api.cohere.com/v2/chat"
)

declare -A PROVIDER_KEYS=(
  ["groq"]="GROQ_API_KEY"
  ["openrouter"]="OPENROUTER_API_KEY"
  ["cerebras"]="CEREBRAS_API_KEY"
  ["deepseek"]="DEEPSEEK_API_KEY"
  ["mistral"]="MISTRAL_API_KEY"
  ["deepinfra"]="DEEPINFRA_API_KEY"
  ["cohere"]="COHERE_API_KEY"
)

# Default models per task type — prioritize providers confirmed working
declare -A TASK_DEFAULTS=(
  ["code_generation"]="groq/llama-3.3-70b-versatile,cerebras/gpt-oss-120b,cohere/command-a-03-2025"
  ["code_review"]="groq/llama-3.3-70b-versatile,cerebras/gpt-oss-120b,cohere/command-a-03-2025"
  ["categorization"]="groq/llama-3.3-70b-versatile,cerebras/gpt-oss-120b,cohere/command-a-03-2025"
  ["general"]="groq/llama-3.3-70b-versatile,cerebras/gpt-oss-120b,cohere/command-a-03-2025"
  ["security"]="groq/llama-3.3-70b-versatile,cerebras/gpt-oss-120b,cohere/command-a-03-2025"
  ["evolution"]="groq/llama-3.3-70b-versatile,cerebras/gemma-4-31b,groq/mixtral-8x7b-32768"
)

if [[ -z "$MODELS" ]]; then
  MODELS="${TASK_DEFAULTS[$TASK_TYPE]:-${TASK_DEFAULTS[general]}}"
fi

get_key() {
  local key_name="$1"
  local cache_file="$TMPDIR_BASE/key_${key_name}"
  if [[ -f "$cache_file" ]]; then
    cat "$cache_file"
    return
  fi
  local val
  val=$(curl -sf --connect-timeout 3 "${API_BASE}/secrets/${key_name}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('value',''))" 2>/dev/null || echo "")
  if [[ -n "$val" ]]; then
    echo "$val" > "$cache_file"
  fi
  echo "$val"
}

build_messages() {
  local sys_msg="$1"
  local user_msg="$2"
  if [[ -n "$sys_msg" ]]; then
    python3 -c "
import json, sys
msgs = [{'role':'system','content':sys.argv[1]},{'role':'user','content':sys.argv[2]}]
print(json.dumps(msgs))
" "$sys_msg" "$user_msg"
  else
    python3 -c "
import json, sys
msgs = [{'role':'user','content':sys.argv[1]}]
print(json.dumps(msgs))
" "$user_msg"
  fi
}

MESSAGES_JSON=$(build_messages "$SYSTEM_PROMPT" "$PROMPT")

query_model() {
  local spec="$1"
  local idx="$2"
  local out_file="$TMPDIR_BASE/result_${idx}.json"

  local provider="${spec%%/*}"
  local model_id="${spec#*/}"

  local endpoint="${PROVIDER_ENDPOINTS[$provider]:-}"
  local key_name="${PROVIDER_KEYS[$provider]:-}"

  if [[ -z "$endpoint" ]]; then
    python3 -c "import json; print(json.dumps({'model':$(python3 -c "import json; print(json.dumps('$spec'))"),'success':False,'error':'unknown provider','response':'','latency_ms':0}))" > "$out_file"
    return
  fi

  local api_key
  api_key=$(get_key "$key_name")
  if [[ -z "$api_key" ]]; then
    python3 -c "import json; print(json.dumps({'model':$(python3 -c "import json; print(json.dumps('$spec'))"),'success':False,'error':'no API key','response':'','latency_ms':0}))" > "$out_file"
    return
  fi

  local start_ms
  start_ms=$(python3 -c "import time; print(int(time.time()*1000))")

  local body
  body=$(python3 -c "
import json, sys
body = {
    'model': sys.argv[1],
    'messages': json.loads(sys.argv[2]),
    'max_tokens': int(sys.argv[3]),
    'temperature': 0.3
}
print(json.dumps(body))
" "$model_id" "$MESSAGES_JSON" "$MAX_TOKENS")

  local resp
  resp=$(curl -sf --max-time "$TIMEOUT" \
    -H "Authorization: Bearer ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$body" \
    "$endpoint" 2>/dev/null || echo '{"error":"request_failed"}')

  local end_ms
  end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
  local latency=$(( end_ms - start_ms ))

  # Parse response — handle both OpenAI-compatible and Cohere formats
  python3 -c "
import json, sys
resp = json.loads(sys.argv[1])
spec = sys.argv[2]
latency = int(sys.argv[3])
provider = sys.argv[4]

content = ''
success = False
error = ''

if provider == 'cohere':
    # Cohere v2: {message: {content: [{type:'text', text:'...'}]}}
    msg = resp.get('message', {})
    parts = msg.get('content', [])
    if isinstance(parts, list) and len(parts) > 0:
        content = parts[0].get('text', '')
        success = True
    elif 'message' in resp and isinstance(resp['message'], str):
        error = resp['message']
    else:
        error = 'unexpected cohere format'
elif 'choices' in resp and len(resp['choices']) > 0:
    msg = resp['choices'][0].get('message', {})
    content = msg.get('content', '')
    success = True
elif 'error' in resp:
    err = resp['error']
    if isinstance(err, dict):
        error = err.get('message', str(err))
    else:
        error = str(err)
else:
    error = 'unexpected response format'

usage = resp.get('usage', {})
prompt_tokens = usage.get('prompt_tokens', 0)
completion_tokens = usage.get('completion_tokens', 0)
total_tokens = prompt_tokens + completion_tokens

# Check if response is parseable as JSON (for structured output quality)
parseable = False
if success and content:
    stripped = content.strip()
    if stripped.startswith('```'):
        lines = stripped.split('\\n')
        stripped = '\\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
    try:
        json.loads(stripped)
        parseable = True
    except:
        pass

result = {
    'model': spec,
    'success': success,
    'response': content,
    'error': error,
    'latency_ms': latency,
    'prompt_tokens': prompt_tokens,
    'completion_tokens': completion_tokens,
    'total_tokens': total_tokens,
    'parseable_json': parseable
}
print(json.dumps(result))
" "$resp" "$spec" "$latency" "$provider" > "$out_file"
}

IFS=',' read -ra MODEL_LIST <<< "$MODELS"
pids=()
for i in "${!MODEL_LIST[@]}"; do
  model="${MODEL_LIST[$i]}"
  model=$(echo "$model" | xargs)
  query_model "$model" "$i" &
  pids+=($!)
done

for pid in "${pids[@]}"; do
  wait "$pid" 2>/dev/null || true
done

python3 -c "
import json, glob, sys, os
results = []
tmpdir = sys.argv[1]
for f in sorted(glob.glob(os.path.join(tmpdir, 'result_*.json'))):
    try:
        with open(f) as fh:
            results.append(json.load(fh))
    except:
        pass
print(json.dumps(results))
" "$TMPDIR_BASE"
