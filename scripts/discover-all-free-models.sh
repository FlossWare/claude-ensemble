#!/bin/bash
# Multi-Provider Free Model Discovery Script
# Discovers free models from 20+ providers and pushes to PostgreSQL via REST API
# Sources: direct provider APIs, ClawLabsAI tracker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/learning"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUTPUT_FILE="$OUTPUT_DIR/all-free-models-$TIMESTAMP.json"
LATEST_LINK="$OUTPUT_DIR/all-free-models-latest.json"
LOG_FILE="$OUTPUT_DIR/multi-provider-discovery.log"

# REST API endpoint - try aio-01 first, fall back to localhost (SSH tunnel)
API_URL="${ORCHESTRATOR_URL:-http://aio-01:5000}"
if ! curl -s --connect-timeout 2 "$API_URL/health" > /dev/null 2>&1; then
  API_URL="http://localhost:5000"
  if ! curl -s --connect-timeout 2 "$API_URL/health" > /dev/null 2>&1; then
    echo "[$(date)] WARNING: REST API unreachable at aio-01:5000 and localhost:5000" | tee -a "$LOG_FILE"
    echo "[$(date)] Models will be saved to JSON only (no DB push)" | tee -a "$LOG_FILE"
    API_URL=""
  fi
fi

DB_UPSERTED=0

push_to_db() {
  local provider="$1"
  local models_json="$2"
  local auth_required="${3:-true}"
  local source="${4:-discovery}"

  if [ -z "$API_URL" ]; then
    return 0
  fi

  local count
  count=$(echo "$models_json" | jq 'length')
  if [ "$count" -eq 0 ] 2>/dev/null; then
    return 0
  fi

  local upsert_payload
  upsert_payload=$(echo "$models_json" | jq --arg auth "$auth_required" --arg src "$source" \
    '[.[] | {
      provider: .provider,
      model_id: .id,
      model_name: .name,
      context_length: .context_length,
      architecture: (if .architecture == null then null elif .architecture | type == "object" then (.architecture | tostring) else .architecture end),
      pricing: .pricing,
      auth_required: ($auth == "true"),
      source: $src
    }]')

  local response
  response=$(curl -s -X POST "$API_URL/models/upsert" \
    -H "Content-Type: application/json" \
    -d "{\"models\": $upsert_payload}" 2>/dev/null) || true

  local inserted updated
  inserted=$(echo "$response" | jq -r '.inserted // 0' 2>/dev/null) || inserted=0
  updated=$(echo "$response" | jq -r '.updated // 0' 2>/dev/null) || updated=0
  DB_UPSERTED=$((DB_UPSERTED + inserted + updated))
  echo "[$(date)]   DB: $inserted inserted, $updated updated ($provider)" | tee -a "$LOG_FILE"
}

echo "[$(date)] Starting multi-provider model discovery..." | tee -a "$LOG_FILE"
[ -n "$API_URL" ] && echo "[$(date)] REST API: $API_URL" | tee -a "$LOG_FILE"

ALL_RESULTS="[]"

# ---------------------------------------------------------------------------
# 1. OpenRouter - Free models (no auth needed for listing)
# ---------------------------------------------------------------------------
echo "[$(date)] Checking OpenRouter..." | tee -a "$LOG_FILE"
OPENROUTER_MODELS=$(curl -s --connect-timeout 10 https://openrouter.ai/api/v1/models 2>/dev/null | \
  jq -r '[.data[] | select(.pricing.prompt == "0" or .pricing.prompt == 0) |
  {
    provider: "openrouter",
    id: .id,
    name: .name,
    context_length: .context_length,
    architecture: .architecture,
    pricing: "free"
  }]' 2>/dev/null) || OPENROUTER_MODELS="[]"

OPENROUTER_COUNT=$(echo "$OPENROUTER_MODELS" | jq 'length')
echo "[$(date)]   Found $OPENROUTER_COUNT free models" | tee -a "$LOG_FILE"
ALL_RESULTS=$(echo "$ALL_RESULTS" "$OPENROUTER_MODELS" | jq -s 'add')
push_to_db "openrouter" "$OPENROUTER_MODELS" "true" "openrouter-api"

# ---------------------------------------------------------------------------
# 2. DeepInfra - FREE models only (pricing null or 0)
# ---------------------------------------------------------------------------
echo "[$(date)] Checking DeepInfra..." | tee -a "$LOG_FILE"
DEEPINFRA_MODELS=$(curl -s --connect-timeout 10 https://api.deepinfra.com/v1/openai/models 2>/dev/null | \
  jq -r '[.data[] | select(
    (.metadata.pricing == null) or
    (.metadata.pricing.input_tokens == null) or
    (.metadata.pricing.input_tokens == 0)
  ) |
  {
    provider: "deepinfra",
    id: .id,
    name: .id,
    context_length: .metadata.context_length,
    architecture: null,
    pricing: "free"
  }]' 2>/dev/null) || DEEPINFRA_MODELS="[]"

DEEPINFRA_COUNT=$(echo "$DEEPINFRA_MODELS" | jq 'length')
echo "[$(date)]   Found $DEEPINFRA_COUNT free models" | tee -a "$LOG_FILE"
ALL_RESULTS=$(echo "$ALL_RESULTS" "$DEEPINFRA_MODELS" | jq -s 'add')
push_to_db "deepinfra" "$DEEPINFRA_MODELS" "false" "deepinfra-api"

# ---------------------------------------------------------------------------
# 3. HuggingFace - Top text-generation models (free inference API)
# ---------------------------------------------------------------------------
echo "[$(date)] Checking HuggingFace..." | tee -a "$LOG_FILE"
HUGGINGFACE_MODELS=$(curl -s --connect-timeout 10 "https://huggingface.co/api/models?pipeline_tag=text-generation&sort=downloads&direction=-1&limit=50" 2>/dev/null | \
  jq -r '[.[] | select(.downloads > 10000) |
  {
    provider: "huggingface",
    id: .id,
    name: .id,
    context_length: null,
    architecture: (.config.model_type // "unknown"),
    pricing: "free (inference API)"
  }]' 2>/dev/null) || HUGGINGFACE_MODELS="[]"

HUGGINGFACE_COUNT=$(echo "$HUGGINGFACE_MODELS" | jq 'length')
echo "[$(date)]   Found $HUGGINGFACE_COUNT popular models" | tee -a "$LOG_FILE"
ALL_RESULTS=$(echo "$ALL_RESULTS" "$HUGGINGFACE_MODELS" | jq -s 'add')
push_to_db "huggingface" "$HUGGINGFACE_MODELS" "false" "huggingface-api"

# ---------------------------------------------------------------------------
# 4. Groq - Free tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_GROQ_API_KEY" ] || [ -f ~/.config/groq/api-key ]; then
  echo "[$(date)] Checking Groq (authenticated)..." | tee -a "$LOG_FILE"
  GROQ_KEY=${PERSONAL_GROQ_API_KEY:-$(cat ~/.config/groq/api-key 2>/dev/null)}

  GROQ_MODELS=$(curl -s --connect-timeout 10 https://api.groq.com/openai/v1/models \
    -H "Authorization: Bearer $GROQ_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "groq",
      id: .id,
      name: .id,
      context_length: .context_window,
      architecture: null,
      pricing: "free tier"
    }]' 2>/dev/null) || GROQ_MODELS="[]"

  GROQ_COUNT=$(echo "$GROQ_MODELS" | jq 'length')
  echo "[$(date)]   Found $GROQ_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$GROQ_MODELS" | jq -s 'add')
  push_to_db "groq" "$GROQ_MODELS" "true" "groq-api"
else
  echo "[$(date)]   Skipping Groq (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 5. Cerebras - Free tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_CEREBRAS_API_KEY" ] || [ -f ~/.config/cerebras/api-key ]; then
  echo "[$(date)] Checking Cerebras (authenticated)..." | tee -a "$LOG_FILE"
  CEREBRAS_KEY=${PERSONAL_CEREBRAS_API_KEY:-$(cat ~/.config/cerebras/api-key 2>/dev/null)}

  CEREBRAS_MODELS=$(curl -s --connect-timeout 10 https://api.cerebras.ai/v1/models \
    -H "Authorization: Bearer $CEREBRAS_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "cerebras",
      id: .id,
      name: .id,
      context_length: null,
      architecture: null,
      pricing: "free tier"
    }]' 2>/dev/null) || CEREBRAS_MODELS="[]"

  CEREBRAS_COUNT=$(echo "$CEREBRAS_MODELS" | jq 'length')
  echo "[$(date)]   Found $CEREBRAS_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$CEREBRAS_MODELS" | jq -s 'add')
  push_to_db "cerebras" "$CEREBRAS_MODELS" "true" "cerebras-api"
else
  echo "[$(date)]   Skipping Cerebras (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 6. Together AI - FREE models only (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$TOGETHER_API_KEY" ] || [ -f ~/.config/together/api-key ]; then
  echo "[$(date)] Checking Together AI (authenticated)..." | tee -a "$LOG_FILE"
  TOGETHER_KEY=${TOGETHER_API_KEY:-$(cat ~/.config/together/api-key 2>/dev/null)}

  TOGETHER_MODELS=$(curl -s --connect-timeout 10 https://api.together.xyz/v1/models \
    -H "Authorization: Bearer $TOGETHER_KEY" 2>/dev/null | \
    jq -r '[.data[]? | select((.pricing.input == 0) or (.pricing.input == null)) |
    {
      provider: "together",
      id: .id,
      name: .display_name,
      context_length: .context_length,
      architecture: .type,
      pricing: "free"
    }]' 2>/dev/null) || TOGETHER_MODELS="[]"

  TOGETHER_COUNT=$(echo "$TOGETHER_MODELS" | jq 'length')
  echo "[$(date)]   Found $TOGETHER_COUNT free models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$TOGETHER_MODELS" | jq -s 'add')
  push_to_db "together" "$TOGETHER_MODELS" "true" "together-api"
else
  echo "[$(date)]   Skipping Together AI (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 7. Google Gemini - Free tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_GOOGLE_API_KEY" ] || [ -n "$GOOGLE_API_KEY" ]; then
  echo "[$(date)] Checking Google Gemini (authenticated)..." | tee -a "$LOG_FILE"
  GOOGLE_KEY=${PERSONAL_GOOGLE_API_KEY:-$GOOGLE_API_KEY}

  GOOGLE_MODELS=$(curl -s --connect-timeout 10 "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_KEY" 2>/dev/null | \
    jq -r '[.models[]? | select(.supportedGenerationMethods[]? == "generateContent") |
    {
      provider: "google-gemini",
      id: (.name | sub("models/"; "")),
      name: .displayName,
      context_length: .inputTokenLimit,
      architecture: null,
      pricing: "free tier"
    }]' 2>/dev/null) || GOOGLE_MODELS="[]"

  GOOGLE_COUNT=$(echo "$GOOGLE_MODELS" | jq 'length')
  echo "[$(date)]   Found $GOOGLE_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$GOOGLE_MODELS" | jq -s 'add')
  push_to_db "google-gemini" "$GOOGLE_MODELS" "true" "google-api"
else
  echo "[$(date)]   Skipping Google Gemini (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 8. Mistral AI - Free tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_MISTRAL_API_KEY" ] || [ -f ~/.config/mistral/api-key ]; then
  echo "[$(date)] Checking Mistral AI (authenticated)..." | tee -a "$LOG_FILE"
  MISTRAL_KEY=${PERSONAL_MISTRAL_API_KEY:-$(cat ~/.config/mistral/api-key 2>/dev/null)}

  MISTRAL_MODELS=$(curl -s --connect-timeout 10 https://api.mistral.ai/v1/models \
    -H "Authorization: Bearer $MISTRAL_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "mistral",
      id: .id,
      name: .id,
      context_length: .max_context_length,
      architecture: null,
      pricing: "free/paid"
    }]' 2>/dev/null) || MISTRAL_MODELS="[]"

  MISTRAL_COUNT=$(echo "$MISTRAL_MODELS" | jq 'length')
  echo "[$(date)]   Found $MISTRAL_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$MISTRAL_MODELS" | jq -s 'add')
  push_to_db "mistral" "$MISTRAL_MODELS" "true" "mistral-api"
else
  echo "[$(date)]   Skipping Mistral AI (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 9. Fireworks AI - Free tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$FIREWORKS_API_KEY" ] || [ -f ~/.config/fireworks/api-key ]; then
  echo "[$(date)] Checking Fireworks AI (authenticated)..." | tee -a "$LOG_FILE"
  FIREWORKS_KEY=${FIREWORKS_API_KEY:-$(cat ~/.config/fireworks/api-key 2>/dev/null)}

  FIREWORKS_MODELS=$(curl -s --connect-timeout 10 https://api.fireworks.ai/inference/v1/models \
    -H "Authorization: Bearer $FIREWORKS_KEY" 2>/dev/null | \
    jq -r '[.data[]? | select(.pricing?.input == 0 or .pricing == null) |
    {
      provider: "fireworks",
      id: .id,
      name: .name,
      context_length: .context_length,
      architecture: null,
      pricing: "free"
    }]' 2>/dev/null) || FIREWORKS_MODELS="[]"

  FIREWORKS_COUNT=$(echo "$FIREWORKS_MODELS" | jq 'length')
  echo "[$(date)]   Found $FIREWORKS_COUNT free models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$FIREWORKS_MODELS" | jq -s 'add')
  push_to_db "fireworks" "$FIREWORKS_MODELS" "true" "fireworks-api"
else
  echo "[$(date)]   Skipping Fireworks AI (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 10. Cohere - Free tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_COHERE_API_KEY" ]; then
  echo "[$(date)] Checking Cohere (authenticated)..." | tee -a "$LOG_FILE"

  COHERE_MODELS=$(curl -s --connect-timeout 10 https://api.cohere.com/v2/models \
    -H "Authorization: Bearer $PERSONAL_COHERE_API_KEY" 2>/dev/null | \
    jq -r '[.models[]? |
    {
      provider: "cohere",
      id: .name,
      name: .name,
      context_length: null,
      architecture: null,
      pricing: "free tier"
    }]' 2>/dev/null) || COHERE_MODELS="[]"

  COHERE_COUNT=$(echo "$COHERE_MODELS" | jq 'length')
  echo "[$(date)]   Found $COHERE_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$COHERE_MODELS" | jq -s 'add')
  push_to_db "cohere" "$COHERE_MODELS" "true" "cohere-api"
else
  echo "[$(date)]   Skipping Cohere (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 11. Cloudflare Workers AI - Free tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_CLOUDFLARE_API_KEY" ] && [ -n "$PERSONAL_CLOUDFLARE_ACCOUNT_ID" ]; then
  echo "[$(date)] Checking Cloudflare Workers AI (authenticated)..." | tee -a "$LOG_FILE"

  CF_MODELS=$(curl -s --connect-timeout 10 "https://api.cloudflare.com/client/v4/accounts/$PERSONAL_CLOUDFLARE_ACCOUNT_ID/ai/models/search" \
    -H "Authorization: Bearer $PERSONAL_CLOUDFLARE_API_KEY" 2>/dev/null | \
    jq -r '[.result[]? |
    {
      provider: "cloudflare",
      id: .name,
      name: .name,
      context_length: null,
      architecture: (.task.name // "unknown"),
      pricing: "free"
    }]' 2>/dev/null) || CF_MODELS="[]"

  CF_COUNT=$(echo "$CF_MODELS" | jq 'length')
  echo "[$(date)]   Found $CF_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$CF_MODELS" | jq -s 'add')
  push_to_db "cloudflare" "$CF_MODELS" "true" "cloudflare-api"
else
  echo "[$(date)]   Skipping Cloudflare Workers AI (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 12. Jina AI - Free tier (embeddings/reranking, authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_JINA_API_KEY" ]; then
  echo "[$(date)] Checking Jina AI (authenticated)..." | tee -a "$LOG_FILE"

  JINA_MODELS=$(curl -s --connect-timeout 10 https://api.jina.ai/v1/models \
    -H "Authorization: Bearer $PERSONAL_JINA_API_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "jina",
      id: .id,
      name: .id,
      context_length: null,
      architecture: null,
      pricing: "free tier"
    }]' 2>/dev/null) || JINA_MODELS="[]"

  JINA_COUNT=$(echo "$JINA_MODELS" | jq 'length')
  echo "[$(date)]   Found $JINA_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$JINA_MODELS" | jq -s 'add')
  push_to_db "jina" "$JINA_MODELS" "true" "jina-api"
else
  echo "[$(date)]   Skipping Jina AI (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 13. Pollinations AI - No auth required, unlimited
# ---------------------------------------------------------------------------
echo "[$(date)] Checking Pollinations AI (no auth)..." | tee -a "$LOG_FILE"
POLLINATIONS_MODELS=$(curl -s --connect-timeout 10 https://text.pollinations.ai/models 2>/dev/null | \
  jq -r '[.[]? | {
    provider: "pollinations",
    id: .name,
    name: (.description // .name),
    context_length: null,
    architecture: null,
    pricing: "free (no auth)"
  }]' 2>/dev/null) || POLLINATIONS_MODELS="[]"

POLLINATIONS_COUNT=$(echo "$POLLINATIONS_MODELS" | jq 'length')
echo "[$(date)]   Found $POLLINATIONS_COUNT models" | tee -a "$LOG_FILE"
ALL_RESULTS=$(echo "$ALL_RESULTS" "$POLLINATIONS_MODELS" | jq -s 'add')
push_to_db "pollinations" "$POLLINATIONS_MODELS" "false" "pollinations-api"

# ---------------------------------------------------------------------------
# 14. ZeroLimitAI - Free tier (authenticated, 100 calls/day)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_ZEROLIMITAI_API_KEY" ]; then
  echo "[$(date)] Checking ZeroLimitAI (authenticated)..." | tee -a "$LOG_FILE"

  ZEROLIMIT_MODELS=$(curl -s --connect-timeout 10 https://www.zerolimitai.com/api/v1/models \
    -H "Authorization: Bearer $PERSONAL_ZEROLIMITAI_API_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "zerolimitai",
      id: .id,
      name: (.name // .id),
      context_length: null,
      architecture: null,
      pricing: "free (100/day)"
    }]' 2>/dev/null) || ZEROLIMIT_MODELS="[]"

  # If API doesn't list models, register the auto-route model
  ZEROLIMIT_COUNT=$(echo "$ZEROLIMIT_MODELS" | jq 'length')
  if [ "$ZEROLIMIT_COUNT" -eq 0 ]; then
    ZEROLIMIT_MODELS='[{"provider":"zerolimitai","id":"auto","name":"ZeroOptimize Auto","context_length":null,"architecture":null,"pricing":"free (100/day)"}]'
    ZEROLIMIT_COUNT=1
  fi

  echo "[$(date)]   Found $ZEROLIMIT_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$ZEROLIMIT_MODELS" | jq -s 'add')
  push_to_db "zerolimitai" "$ZEROLIMIT_MODELS" "true" "zerolimitai-api"
else
  echo "[$(date)]   Skipping ZeroLimitAI (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 15. NVIDIA NIM - Free tier (authenticated, 40 RPM)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_NVIDIA_API_KEY" ]; then
  echo "[$(date)] Checking NVIDIA NIM (authenticated)..." | tee -a "$LOG_FILE"

  NVIDIA_MODELS=$(curl -s --connect-timeout 10 https://integrate.api.nvidia.com/v1/models \
    -H "Authorization: Bearer $PERSONAL_NVIDIA_API_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "nvidia-nim",
      id: .id,
      name: (.name // .id),
      context_length: null,
      architecture: null,
      pricing: "free (40 RPM)"
    }]' 2>/dev/null) || NVIDIA_MODELS="[]"

  NVIDIA_COUNT=$(echo "$NVIDIA_MODELS" | jq 'length')
  echo "[$(date)]   Found $NVIDIA_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$NVIDIA_MODELS" | jq -s 'add')
  push_to_db "nvidia-nim" "$NVIDIA_MODELS" "true" "nvidia-api"
else
  echo "[$(date)]   Skipping NVIDIA NIM (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 16. SambaNova - Free tier (authenticated, 20 RPM)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_SAMBANOVA_API_KEY" ]; then
  echo "[$(date)] Checking SambaNova (authenticated)..." | tee -a "$LOG_FILE"

  SAMBANOVA_MODELS=$(curl -s --connect-timeout 10 https://api.sambanova.ai/v1/models \
    -H "Authorization: Bearer $PERSONAL_SAMBANOVA_API_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "sambanova",
      id: .id,
      name: (.name // .id),
      context_length: null,
      architecture: null,
      pricing: "free (20 RPM)"
    }]' 2>/dev/null) || SAMBANOVA_MODELS="[]"

  SAMBANOVA_COUNT=$(echo "$SAMBANOVA_MODELS" | jq 'length')
  echo "[$(date)]   Found $SAMBANOVA_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$SAMBANOVA_MODELS" | jq -s 'add')
  push_to_db "sambanova" "$SAMBANOVA_MODELS" "true" "sambanova-api"
else
  echo "[$(date)]   Skipping SambaNova (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 17. GitHub Models - Free tier (uses GH token)
# ---------------------------------------------------------------------------
if [ -n "$GH_TOKEN" ] || [ -n "$GITHUB_TOKEN" ]; then
  echo "[$(date)] Checking GitHub Models (authenticated)..." | tee -a "$LOG_FILE"
  GH_KEY=${GH_TOKEN:-$GITHUB_TOKEN}

  GITHUB_MODELS=$(curl -s --connect-timeout 10 https://models.inference.ai.azure.com/models \
    -H "Authorization: Bearer $GH_KEY" 2>/dev/null | \
    jq -r '[.[]? |
    {
      provider: "github-models",
      id: .id,
      name: (.friendly_name // .name // .id),
      context_length: .max_input_tokens,
      architecture: null,
      pricing: "free (GitHub account)"
    }]' 2>/dev/null) || GITHUB_MODELS="[]"

  GITHUB_MODELS_COUNT=$(echo "$GITHUB_MODELS" | jq 'length')
  echo "[$(date)]   Found $GITHUB_MODELS_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$GITHUB_MODELS" | jq -s 'add')
  push_to_db "github-models" "$GITHUB_MODELS" "true" "github-models-api"
else
  echo "[$(date)]   Skipping GitHub Models (no GH_TOKEN)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 18. DeepSeek - Free/paid tier (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_DEEPSEEK_API_KEY" ]; then
  echo "[$(date)] Checking DeepSeek (authenticated)..." | tee -a "$LOG_FILE"

  DEEPSEEK_MODELS=$(curl -s --connect-timeout 10 https://api.deepseek.com/models \
    -H "Authorization: Bearer $PERSONAL_DEEPSEEK_API_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "deepseek",
      id: .id,
      name: (.name // .id),
      context_length: null,
      architecture: null,
      pricing: "low cost"
    }]' 2>/dev/null) || DEEPSEEK_MODELS="[]"

  DEEPSEEK_COUNT=$(echo "$DEEPSEEK_MODELS" | jq 'length')
  echo "[$(date)]   Found $DEEPSEEK_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$DEEPSEEK_MODELS" | jq -s 'add')
  push_to_db "deepseek" "$DEEPSEEK_MODELS" "true" "deepseek-api"
else
  echo "[$(date)]   Skipping DeepSeek (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 19. Thinking Machines Lab - Inkling (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_THINKMACHINES_API_KEY" ]; then
  echo "[$(date)] Checking Thinking Machines Lab (authenticated)..." | tee -a "$LOG_FILE"

  TML_MODELS=$(curl -s --connect-timeout 10 https://api.thinkingmachines.ai/v1/models \
    -H "Authorization: Bearer $PERSONAL_THINKMACHINES_API_KEY" 2>/dev/null | \
    jq -r '[.data[]? |
    {
      provider: "thinking-machines",
      id: .id,
      name: (.name // .id),
      context_length: null,
      architecture: null,
      pricing: "free tier"
    }]' 2>/dev/null) || TML_MODELS="[]"

  TML_COUNT=$(echo "$TML_MODELS" | jq 'length')
  echo "[$(date)]   Found $TML_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$TML_MODELS" | jq -s 'add')
  push_to_db "thinking-machines" "$TML_MODELS" "true" "tml-api"
else
  echo "[$(date)]   Skipping Thinking Machines Lab (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 20. ClawLabsAI Tracker - Daily-updated JSON of free models (no auth)
# ---------------------------------------------------------------------------
echo "[$(date)] Checking ClawLabsAI free-ai-models tracker..." | tee -a "$LOG_FILE"
CLAWLABS_RAW=$(curl -s --connect-timeout 10 \
  https://raw.githubusercontent.com/ClawLabsAI/free-ai-models/main/data/models.json 2>/dev/null) || CLAWLABS_RAW=""

if [ -n "$CLAWLABS_RAW" ] && echo "$CLAWLABS_RAW" | jq empty 2>/dev/null; then
  CLAWLABS_MODELS=$(echo "$CLAWLABS_RAW" | \
    jq -r '[.models[]? |
    {
      provider: ((.provider // "clawlabs") | ascii_downcase | gsub(" "; "-") | gsub("[^a-z0-9-]"; "")),
      id: .id,
      name: (.name // .id),
      context_length: .context_window,
      architecture: null,
      pricing: "free"
    }]' 2>/dev/null) || CLAWLABS_MODELS="[]"

  CLAWLABS_COUNT=$(echo "$CLAWLABS_MODELS" | jq 'length')
  echo "[$(date)]   Found $CLAWLABS_COUNT models from ClawLabsAI tracker" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$CLAWLABS_MODELS" | jq -s 'add')
  push_to_db "clawlabs-tracker" "$CLAWLABS_MODELS" "false" "clawlabs-tracker"
else
  echo "[$(date)]   ClawLabsAI tracker unavailable or invalid JSON" | tee -a "$LOG_FILE"
  CLAWLABS_COUNT=0
fi

# ---------------------------------------------------------------------------
# 21. Eden AI - Multi-provider aggregator (authenticated)
# ---------------------------------------------------------------------------
if [ -n "$PERSONAL_EDENAI_API_KEY" ]; then
  echo "[$(date)] Checking Eden AI (authenticated)..." | tee -a "$LOG_FILE"

  # Eden AI is a multi-provider aggregator with 18+ providers
  EDENAI_MODELS='[
    {"provider":"edenai","id":"openai/gpt-4o","name":"GPT-4o (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"openai/gpt-4o-mini","name":"GPT-4o Mini (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"google/gemini-2.5-flash","name":"Gemini 2.5 Flash (via Eden AI)","context_length":1000000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"google/gemini-2.0-flash","name":"Gemini 2.0 Flash (via Eden AI)","context_length":1000000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"anthropic/claude-sonnet","name":"Claude Sonnet (via Eden AI)","context_length":200000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"mistralai/mistral-small","name":"Mistral Small (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"mistralai/mistral-large","name":"Mistral Large (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"meta/llama-3.3-70b","name":"Llama 3.3 70B (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"meta/llama-4-scout","name":"Llama 4 Scout (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"deepseek/deepseek-v3","name":"DeepSeek V3 (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"deepseek/deepseek-r1","name":"DeepSeek R1 (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"cohere/command-r-plus","name":"Command R+ (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"xai/grok","name":"Grok (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"perplexity/sonar","name":"Perplexity Sonar (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"groq/llama-3.3-70b","name":"Llama 3.3 70B via Groq (Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"cerebras/llama-3.3-70b","name":"Llama 3.3 70B via Cerebras (Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"qwen/qwen3-235b","name":"Qwen3 235B (via Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"},
    {"provider":"edenai","id":"cloudflare/llama-3.3-70b","name":"Llama 3.3 70B via Cloudflare (Eden AI)","context_length":128000,"architecture":null,"pricing":"aggregator"}
  ]'

  EDENAI_COUNT=$(echo "$EDENAI_MODELS" | jq 'length')
  echo "[$(date)]   Registered $EDENAI_COUNT known models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$EDENAI_MODELS" | jq -s 'add')
  push_to_db "edenai" "$EDENAI_MODELS" "true" "edenai-manual"
else
  echo "[$(date)]   Skipping Eden AI (no API key)" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# Count totals
# ---------------------------------------------------------------------------
TOTAL_MODELS=$(echo "$ALL_RESULTS" | jq 'length')
PROVIDERS=$(echo "$ALL_RESULTS" | jq -r '[.[] | .provider] | unique | join(", ")')

echo "[$(date)] Discovery complete: $TOTAL_MODELS models from [$PROVIDERS]" | tee -a "$LOG_FILE"
[ -n "$API_URL" ] && echo "[$(date)] Total upserted to DB: $DB_UPSERTED" | tee -a "$LOG_FILE"

# Compare with previous discovery
if [ -f "$LATEST_LINK" ]; then
  PREV_IDS=$(jq -r '.models[] | "\(.provider):\(.id)"' "$LATEST_LINK" 2>/dev/null | sort) || PREV_IDS=""
  CURR_IDS=$(echo "$ALL_RESULTS" | jq -r '.[] | "\(.provider):\(.id)"' | sort)

  NEW_MODELS=$(comm -13 <(echo "$PREV_IDS") <(echo "$CURR_IDS"))
  REMOVED_MODELS=$(comm -23 <(echo "$PREV_IDS") <(echo "$CURR_IDS"))

  NEW_COUNT=$(echo "$NEW_MODELS" | grep -v '^$' | wc -l)
  REMOVED_COUNT=$(echo "$REMOVED_MODELS" | grep -v '^$' | wc -l)

  if [ "$NEW_COUNT" -gt 0 ]; then
    echo "[$(date)] NEW MODELS ($NEW_COUNT):" | tee -a "$LOG_FILE"
    echo "$NEW_MODELS" | while read -r model; do
      [ -n "$model" ] && echo "  + $model" | tee -a "$LOG_FILE"
    done
  fi

  if [ "$REMOVED_COUNT" -gt 0 ]; then
    echo "[$(date)] REMOVED MODELS ($REMOVED_COUNT):" | tee -a "$LOG_FILE"
    echo "$REMOVED_MODELS" | while read -r model; do
      [ -n "$model" ] && echo "  - $model" | tee -a "$LOG_FILE"
    done
  fi

  if [ "$NEW_COUNT" -eq 0 ] && [ "$REMOVED_COUNT" -eq 0 ]; then
    echo "[$(date)] No changes detected" | tee -a "$LOG_FILE"
  fi
else
  echo "[$(date)] First discovery run - baseline created" | tee -a "$LOG_FILE"
  NEW_COUNT=0
  REMOVED_COUNT=0
fi

# Create discovery report (JSON file)
cat > "$OUTPUT_FILE" << REPORT_EOF
{
  "timestamp": "$(date -Iseconds)",
  "total_models": $TOTAL_MODELS,
  "new_models": $NEW_COUNT,
  "removed_models": $REMOVED_COUNT,
  "db_upserted": $DB_UPSERTED,
  "api_url": "$API_URL",
  "models": $(echo "$ALL_RESULTS" | jq .)
}
REPORT_EOF

ln -sf "$(basename "$OUTPUT_FILE")" "$LATEST_LINK"

echo "[$(date)] Results saved to $OUTPUT_FILE" | tee -a "$LOG_FILE"

# Notify if significant changes (5+ new models)
if [ "$NEW_COUNT" -ge 5 ]; then
  echo "[$(date)] SIGNIFICANT CHANGE: $NEW_COUNT new models!" | tee -a "$LOG_FILE"

  cat > "$OUTPUT_DIR/.new-models-notification" << NOTIF_EOF
NEW MODELS DETECTED ($(date))

$NEW_MODELS

Total new: $NEW_COUNT
DB upserted: $DB_UPSERTED
NOTIF_EOF

  echo "Notification created: $OUTPUT_DIR/.new-models-notification" | tee -a "$LOG_FILE"
fi

# Print DB summary if API available
if [ -n "$API_URL" ]; then
  echo "" | tee -a "$LOG_FILE"
  echo "[$(date)] DB Status:" | tee -a "$LOG_FILE"
  DB_COUNT=$(curl -s "$API_URL/models/count" 2>/dev/null) || DB_COUNT="{}"
  echo "  Total models in DB: $(echo "$DB_COUNT" | jq -r '.total_models // "unknown"')" | tee -a "$LOG_FILE"
  echo "  Active providers:   $(echo "$DB_COUNT" | jq -r '.active_providers // "unknown"')" | tee -a "$LOG_FILE"
  echo "  No-auth models:     $(echo "$DB_COUNT" | jq -r '.no_auth_models // "unknown"')" | tee -a "$LOG_FILE"
fi

echo "[$(date)] Done" | tee -a "$LOG_FILE"
