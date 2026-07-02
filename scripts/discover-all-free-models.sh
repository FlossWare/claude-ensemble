#!/bin/bash
# Multi-Provider Free Model Discovery Script
# Checks: OpenRouter, DeepInfra, HuggingFace, Groq, Cerebras, Together AI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/learning"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUTPUT_FILE="$OUTPUT_DIR/all-free-models-$TIMESTAMP.json"
LATEST_LINK="$OUTPUT_DIR/all-free-models-latest.json"
LOG_FILE="$OUTPUT_DIR/multi-provider-discovery.log"

echo "[$(date)] Starting multi-provider model discovery..." | tee -a "$LOG_FILE"

# Initialize results
ALL_RESULTS="[]"

# 1. OpenRouter - Free models
echo "[$(date)] Checking OpenRouter..." | tee -a "$LOG_FILE"
OPENROUTER_MODELS=$(curl -s https://openrouter.ai/api/v1/models | \
  jq -r '.data[] | select(.pricing.prompt == "0" or .pricing.prompt == 0) |
  {
    provider: "openrouter",
    id: .id,
    name: .name,
    context_length: .context_length,
    architecture: .architecture,
    pricing: "free"
  }' | jq -s '.')

OPENROUTER_COUNT=$(echo "$OPENROUTER_MODELS" | jq 'length')
echo "[$(date)]   Found $OPENROUTER_COUNT free models" | tee -a "$LOG_FILE"
ALL_RESULTS=$(echo "$ALL_RESULTS" "$OPENROUTER_MODELS" | jq -s 'add')

# 2. DeepInfra - FREE models only (pricing null or 0)
echo "[$(date)] Checking DeepInfra..." | tee -a "$LOG_FILE"
DEEPINFRA_MODELS=$(curl -s https://api.deepinfra.com/v1/openai/models | \
  jq -r '.data[] | select(
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
  }' | jq -s '.')

DEEPINFRA_COUNT=$(echo "$DEEPINFRA_MODELS" | jq 'length')
echo "[$(date)]   Found $DEEPINFRA_COUNT free models" | tee -a "$LOG_FILE"
ALL_RESULTS=$(echo "$ALL_RESULTS" "$DEEPINFRA_MODELS" | jq -s 'add')

# 3. HuggingFace - Top downloaded text-generation models (free inference API)
echo "[$(date)] Checking HuggingFace..." | tee -a "$LOG_FILE"
HUGGINGFACE_MODELS=$(curl -s "https://huggingface.co/api/models?pipeline_tag=text-generation&sort=downloads&direction=-1&limit=50" | \
  jq -r '.[] | select(.downloads > 10000) |
  {
    provider: "huggingface",
    id: .id,
    name: .id,
    context_length: null,
    architecture: (.config.model_type // "unknown"),
    pricing: "free (inference API)",
    downloads: .downloads
  }' | jq -s '.')

HUGGINGFACE_COUNT=$(echo "$HUGGINGFACE_MODELS" | jq 'length')
echo "[$(date)]   Found $HUGGINGFACE_COUNT popular models" | tee -a "$LOG_FILE"
ALL_RESULTS=$(echo "$ALL_RESULTS" "$HUGGINGFACE_MODELS" | jq -s 'add')

# 4. Groq - Check if API key exists
if [ -n "$GROQ_API_KEY" ] || [ -f ~/.config/groq/api-key ]; then
  echo "[$(date)] Checking Groq (authenticated)..." | tee -a "$LOG_FILE"
  GROQ_KEY=${GROQ_API_KEY:-$(cat ~/.config/groq/api-key 2>/dev/null)}

  GROQ_MODELS=$(curl -s https://api.groq.com/openai/v1/models \
    -H "Authorization: Bearer $GROQ_KEY" | \
    jq -r '.data[]? |
    {
      provider: "groq",
      id: .id,
      name: .id,
      context_length: .context_window,
      architecture: null,
      pricing: "free tier"
    }' | jq -s '.')

  GROQ_COUNT=$(echo "$GROQ_MODELS" | jq 'length')
  echo "[$(date)]   Found $GROQ_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$GROQ_MODELS" | jq -s 'add')
else
  echo "[$(date)]   Skipping Groq (no API key)" | tee -a "$LOG_FILE"
fi

# 5. Cerebras - Check if API key exists
if [ -n "$CEREBRAS_API_KEY" ] || [ -f ~/.config/cerebras/api-key ]; then
  echo "[$(date)] Checking Cerebras (authenticated)..." | tee -a "$LOG_FILE"
  CEREBRAS_KEY=${CEREBRAS_API_KEY:-$(cat ~/.config/cerebras/api-key 2>/dev/null)}

  CEREBRAS_MODELS=$(curl -s https://api.cerebras.ai/v1/models \
    -H "Authorization: Bearer $CEREBRAS_KEY" | \
    jq -r '.data[]? |
    {
      provider: "cerebras",
      id: .id,
      name: .id,
      context_length: null,
      architecture: null,
      pricing: "free tier"
    }' | jq -s '.')

  CEREBRAS_COUNT=$(echo "$CEREBRAS_MODELS" | jq 'length')
  echo "[$(date)]   Found $CEREBRAS_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$CEREBRAS_MODELS" | jq -s 'add')
else
  echo "[$(date)]   Skipping Cerebras (no API key)" | tee -a "$LOG_FILE"
fi

# 6. Together AI - FREE models only
if [ -n "$TOGETHER_API_KEY" ] || [ -f ~/.config/together/api-key ]; then
  echo "[$(date)] Checking Together AI (authenticated)..." | tee -a "$LOG_FILE"
  TOGETHER_KEY=${TOGETHER_API_KEY:-$(cat ~/.config/together/api-key 2>/dev/null)}

  TOGETHER_MODELS=$(curl -s https://api.together.xyz/v1/models \
    -H "Authorization: Bearer $TOGETHER_KEY" | \
    jq -r '.data[]? | select((.pricing.input == 0) or (.pricing.input == null)) |
    {
      provider: "together",
      id: .id,
      name: .display_name,
      context_length: .context_length,
      architecture: .type,
      pricing: "free"
    }' | jq -s '.')

  TOGETHER_COUNT=$(echo "$TOGETHER_MODELS" | jq 'length')
  echo "[$(date)]   Found $TOGETHER_COUNT free models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$TOGETHER_MODELS" | jq -s 'add')
else
  echo "[$(date)]   Skipping Together AI (no API key)" | tee -a "$LOG_FILE"
fi

# 7. Google Gemini - Free tier (gemini-1.5-flash, etc)
if [ -n "$GOOGLE_API_KEY" ] || [ -f ~/.config/google/api-key ]; then
  echo "[$(date)] Checking Google Gemini (authenticated)..." | tee -a "$LOG_FILE"
  GOOGLE_KEY=${GOOGLE_API_KEY:-$(cat ~/.config/google/api-key 2>/dev/null)}

  GOOGLE_MODELS=$(curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_KEY" | \
    jq -r '.models[]? | select(.supportedGenerationMethods[]? == "generateContent") |
    {
      provider: "google-gemini",
      id: .name | sub("models/"; ""),
      name: .displayName,
      context_length: .inputTokenLimit,
      architecture: null,
      pricing: "free tier"
    }' | jq -s '.')

  GOOGLE_COUNT=$(echo "$GOOGLE_MODELS" | jq 'length')
  echo "[$(date)]   Found $GOOGLE_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$GOOGLE_MODELS" | jq -s 'add')
else
  echo "[$(date)]   Skipping Google Gemini (no API key)" | tee -a "$LOG_FILE"
fi

# 8. Mistral AI - Free tier models
if [ -n "$MISTRAL_API_KEY" ] || [ -f ~/.config/mistral/api-key ]; then
  echo "[$(date)] Checking Mistral AI (authenticated)..." | tee -a "$LOG_FILE"
  MISTRAL_KEY=${MISTRAL_API_KEY:-$(cat ~/.config/mistral/api-key 2>/dev/null)}

  MISTRAL_MODELS=$(curl -s https://api.mistral.ai/v1/models \
    -H "Authorization: Bearer $MISTRAL_KEY" | \
    jq -r '.data[]? |
    {
      provider: "mistral",
      id: .id,
      name: .id,
      context_length: .max_context_length,
      architecture: null,
      pricing: "free/paid"
    }' | jq -s '.')

  MISTRAL_COUNT=$(echo "$MISTRAL_MODELS" | jq 'length')
  echo "[$(date)]   Found $MISTRAL_COUNT models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$MISTRAL_MODELS" | jq -s 'add')
else
  echo "[$(date)]   Skipping Mistral AI (no API key)" | tee -a "$LOG_FILE"
fi

# 9. Fireworks AI - Free tier
if [ -n "$FIREWORKS_API_KEY" ] || [ -f ~/.config/fireworks/api-key ]; then
  echo "[$(date)] Checking Fireworks AI (authenticated)..." | tee -a "$LOG_FILE"
  FIREWORKS_KEY=${FIREWORKS_API_KEY:-$(cat ~/.config/fireworks/api-key 2>/dev/null)}

  FIREWORKS_MODELS=$(curl -s https://api.fireworks.ai/inference/v1/models \
    -H "Authorization: Bearer $FIREWORKS_KEY" | \
    jq -r '.data[]? | select(.pricing?.input == 0 or .pricing == null) |
    {
      provider: "fireworks",
      id: .id,
      name: .name,
      context_length: .context_length,
      architecture: null,
      pricing: "free"
    }' | jq -s '.')

  FIREWORKS_COUNT=$(echo "$FIREWORKS_MODELS" | jq 'length')
  echo "[$(date)]   Found $FIREWORKS_COUNT free models" | tee -a "$LOG_FILE"
  ALL_RESULTS=$(echo "$ALL_RESULTS" "$FIREWORKS_MODELS" | jq -s 'add')
else
  echo "[$(date)]   Skipping Fireworks AI (no API key)" | tee -a "$LOG_FILE"
fi

# Count totals
TOTAL_MODELS=$(echo "$ALL_RESULTS" | jq 'length')
PROVIDERS=$(echo "$ALL_RESULTS" | jq -r '.[] | .provider' | sort -u | tr '\n' ', ' | sed 's/,$//')

echo "[$(date)] Discovery complete: $TOTAL_MODELS models from $PROVIDERS" | tee -a "$LOG_FILE"

# Compare with previous discovery
if [ -f "$LATEST_LINK" ]; then
  PREV_IDS=$(jq -r '.models[] | "\(.provider):\(.id)"' "$LATEST_LINK" | sort)
  CURR_IDS=$(echo "$ALL_RESULTS" | jq -r '.[] | "\(.provider):\(.id)"' | sort)

  NEW_MODELS=$(comm -13 <(echo "$PREV_IDS") <(echo "$CURR_IDS"))
  REMOVED_MODELS=$(comm -23 <(echo "$PREV_IDS") <(echo "$CURR_IDS"))

  NEW_COUNT=$(echo "$NEW_MODELS" | grep -v '^$' | wc -l)
  REMOVED_COUNT=$(echo "$REMOVED_MODELS" | grep -v '^$' | wc -l)

  if [ "$NEW_COUNT" -gt 0 ]; then
    echo "[$(date)] 🆕 NEW MODELS ($NEW_COUNT):" | tee -a "$LOG_FILE"
    echo "$NEW_MODELS" | while read -r model; do
      [ -n "$model" ] && echo "  - $model" | tee -a "$LOG_FILE"
    done
  fi

  if [ "$REMOVED_COUNT" -gt 0 ]; then
    echo "[$(date)] ❌ REMOVED MODELS ($REMOVED_COUNT):" | tee -a "$LOG_FILE"
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

# Create discovery report
cat > "$OUTPUT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "providers": ["openrouter", "deepinfra", "huggingface", "groq", "cerebras", "together", "google-gemini", "mistral", "fireworks"],
  "total_models": $TOTAL_MODELS,
  "new_models": $NEW_COUNT,
  "removed_models": $REMOVED_COUNT,
  "breakdown": {
    "openrouter": $OPENROUTER_COUNT,
    "deepinfra": $DEEPINFRA_COUNT,
    "huggingface": $HUGGINGFACE_COUNT
  },
  "models": $(echo "$ALL_RESULTS" | jq .)
}
EOF

# Update latest symlink
ln -sf "$(basename "$OUTPUT_FILE")" "$LATEST_LINK"

echo "[$(date)] Results saved to $OUTPUT_FILE" | tee -a "$LOG_FILE"

# Notify if significant changes (5+ new models)
if [ "$NEW_COUNT" -ge 5 ]; then
  echo "[$(date)] ⚠️  SIGNIFICANT CHANGE: $NEW_COUNT new models!" | tee -a "$LOG_FILE"

  cat > "$OUTPUT_DIR/.new-models-notification" << EOF
🆕 NEW MODELS DETECTED ($(date))

$NEW_MODELS

Total new: $NEW_COUNT
View details: cat $OUTPUT_FILE | jq '.models[] | select(.provider + ":" + .id | IN($NEW_MODELS))'
EOF

  echo "Notification created: $OUTPUT_DIR/.new-models-notification" | tee -a "$LOG_FILE"
fi

echo "[$(date)] Done" | tee -a "$LOG_FILE"
