#!/bin/bash
# Free Model Discovery Script
# Runs every 3 hours to check for new free models on OpenRouter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/learning"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUTPUT_FILE="$OUTPUT_DIR/free-models-discovery-$TIMESTAMP.json"
LATEST_LINK="$OUTPUT_DIR/free-models-latest.json"
LOG_FILE="$OUTPUT_DIR/model-discovery.log"

echo "[$(date)] Starting free model discovery..." | tee -a "$LOG_FILE"

# Fetch all free models from OpenRouter
echo "[$(date)] Querying OpenRouter API..." | tee -a "$LOG_FILE"

FREE_MODELS=$(curl -s https://openrouter.ai/api/v1/models | \
  jq -r '.data[] | select(.pricing.prompt == "0" or .pricing.prompt == 0) |
  {
    id: .id,
    name: .name,
    context_length: .context_length,
    architecture: .architecture,
    pricing: .pricing,
    top_provider: .top_provider
  }')

MODEL_COUNT=$(echo "$FREE_MODELS" | jq -s 'length')
echo "[$(date)] Found $MODEL_COUNT free models" | tee -a "$LOG_FILE"

# Compare with previous discovery
if [ -f "$LATEST_LINK" ]; then
  PREV_MODELS=$(jq -r '.models[].id' "$LATEST_LINK" | sort)
  CURR_MODELS=$(echo "$FREE_MODELS" | jq -r '.id' | sort)

  NEW_MODELS=$(comm -13 <(echo "$PREV_MODELS") <(echo "$CURR_MODELS"))
  REMOVED_MODELS=$(comm -23 <(echo "$PREV_MODELS") <(echo "$CURR_MODELS"))

  NEW_COUNT=$(echo "$NEW_MODELS" | grep -v '^$' | wc -l)
  REMOVED_COUNT=$(echo "$REMOVED_MODELS" | grep -v '^$' | wc -l)

  if [ "$NEW_COUNT" -gt 0 ]; then
    echo "[$(date)] 🆕 NEW MODELS DETECTED ($NEW_COUNT):" | tee -a "$LOG_FILE"
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
  "source": "OpenRouter API",
  "total_free_models": $MODEL_COUNT,
  "new_models": $NEW_COUNT,
  "removed_models": $REMOVED_COUNT,
  "models": $(echo "$FREE_MODELS" | jq -s '.')
}
EOF

# Update latest symlink
ln -sf "$(basename "$OUTPUT_FILE")" "$LATEST_LINK"

echo "[$(date)] Discovery complete - saved to $OUTPUT_FILE" | tee -a "$LOG_FILE"

# Notify if significant changes (3+ new models)
if [ "$NEW_COUNT" -ge 3 ]; then
  echo "[$(date)] ⚠️  SIGNIFICANT CHANGE: $NEW_COUNT new models detected!" | tee -a "$LOG_FILE"

  # Create notification file for user
  cat > "$OUTPUT_DIR/.new-models-notification" << EOF
New free models detected on $(date):

$NEW_MODELS

Run: cat $OUTPUT_FILE | jq '.models[] | select(.id | IN($NEW_MODELS))'
EOF

  echo "Notification created at $OUTPUT_DIR/.new-models-notification" | tee -a "$LOG_FILE"
fi

echo "[$(date)] Done" | tee -a "$LOG_FILE"
