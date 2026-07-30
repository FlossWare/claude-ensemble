#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:5000}"
CONFIG_DIR="${HOME}/.config/opencode"

mkdir -p "$CONFIG_DIR"

if ! curl -s -m 5 "${API_BASE}/health" > /dev/null 2>&1; then
  echo "ERROR: API not reachable at ${API_BASE}" >&2
  exit 1
fi

declare -A PROVIDER_MAP=(
  [ANTHROPIC_API_KEY]="anthropic"
  [OPENROUTER_API_KEY]="openrouter"
  [GROQ_API_KEY]="groq"
  [CEREBRAS_API_KEY]="cerebras"
  [DEEPSEEK_API_KEY]="deepseek"
  [GOOGLE_API_KEY]="google"
  [MISTRAL_API_KEY]="mistral"
  [OPENAI_API_KEY]="openai"
  [COHERE_API_KEY]="cohere"
  [DEEPINFRA_API_KEY]="deepinfra"
)

keys_json=$(curl -s -m 10 "${API_BASE}/secrets/")
available_keys=$(echo "$keys_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for s in d.get('secrets', []):
    print(s.get('key', s) if isinstance(s, dict) else s)
" 2>/dev/null)

providers=""
count=0
for key_var in "${!PROVIDER_MAP[@]}"; do
  provider="${PROVIDER_MAP[$key_var]}"
  if echo "$available_keys" | grep -q "^${key_var}$" 2>/dev/null; then
    [[ $count -gt 0 ]] && providers+=","
    providers+="
    \"${provider}\": {
      \"options\": {
        \"apiKey\": \"{env:${key_var}}\"
      }
    }"
    count=$((count + 1))
  fi
done

cat > "${CONFIG_DIR}/opencode.json" <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "groq/llama-4-scout-17b-16e-instruct",
  "provider": {${providers}
  }
}
EOF

echo "Generated ${CONFIG_DIR}/opencode.json with ${count} providers"
