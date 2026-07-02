# Multi-Provider Free Model Discovery System

## Overview

Automated discovery of **FREE ONLY** AI models from **6 providers**, running every 3 hours:
- **OpenRouter** (26 free models)
- **DeepInfra** (55 free models)
- **HuggingFace** (50 popular models, free inference API)
- **Groq** (17 free tier models - requires API key)
- **Cerebras** (3 free tier models - requires API key)
- **Together AI** (free models - requires API key)

**Total: 151 FREE models discovered**

## Cron Schedule

```bash
17 */3 * * *  # Every 3 hours at :17 past the hour
```

**Why :17?** Avoids the :00 and :30 minute marks where most cron jobs run, reducing API load.

## Files

- **Script:** `scripts/discover-all-free-models.sh` (multi-provider)
- **Old script:** `scripts/discover-free-models.sh` (OpenRouter only)
- **Latest results:** `learning/all-free-models-latest.json` (symlink)
- **Historical results:** `learning/all-free-models-YYYY-MM-DD_HH-MM-SS.json`
- **Log:** `learning/multi-provider-discovery.log`
- **Notifications:** `learning/.new-models-notification` (created when 5+ new models detected)

## Usage

### Manual discovery:
```bash
./scripts/discover-all-free-models.sh
```

### Check latest results:
```bash
cat learning/all-free-models-latest.json | jq '{total_models, breakdown}'
cat learning/all-free-models-latest.json | jq -r '.models[] | "\(.provider):\(.id)"'
```

### Filter by provider:
```bash
# OpenRouter free models
cat learning/all-free-models-latest.json | jq -r '.models[] | select(.provider == "openrouter") | .id'

# Groq models
cat learning/all-free-models-latest.json | jq -r '.models[] | select(.provider == "groq") | .id'

# Cerebras models
cat learning/all-free-models-latest.json | jq -r '.models[] | select(.provider == "cerebras") | .id'

# DeepInfra cheap models
cat learning/all-free-models-latest.json | jq -r '.models[] | select(.provider == "deepinfra") | .id' | head -20
```

### Check for new models:
```bash
cat learning/free-models-latest.json | jq '{new_models, removed_models, timestamp}'
```

### View notification:
```bash
cat learning/.new-models-notification
```

## Current Free Models (2026-07-02)

**Total:** 26 free models

### Top Picks:

**Large General (550B-80B):**
- `nvidia/nemotron-3-ultra-550b-a55b:free` ⭐ **TESTED & WORKING** - 550B parameters
- `nousresearch/hermes-3-llama-3.1-405b:free` - 405B parameters
- `nvidia/nemotron-3-super-120b-a12b:free` - 120B parameters
- `openai/gpt-oss-120b:free` - 120B parameters
- `qwen/qwen3-next-80b-a3b-instruct:free` - 80B parameters

**Code Specialists:**
- `qwen/qwen3-coder:free` - Code generation
- `cohere/north-mini-code:free` - Code generation

**Reasoning:**
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` - 30B reasoning
- `liquid/lfm-2.5-1.2b-thinking:free` - Chain-of-thought

**Vision/Multimodal:**
- `nvidia/nemotron-nano-12b-v2-vl:free` - Vision-language
- `google/lyria-3-pro-preview` - Multimodal preview

## Deprecated Models Removed

The following models were removed from the codebase (2026-07-02):

| Deprecated Model | Replacement | Status |
|-----------------|-------------|--------|
| `meta-llama/llama-3.1-405b-instruct` | `nousresearch/hermes-3-llama-3.1-405b:free` | ❌ Not on OpenRouter |
| `google/gemini-pro-1.5` | `google/gemma-4-31b-it:free` | ❌ Not on OpenRouter |
| `mistral/mixtral-8x7b-instruct` | `meta-llama/llama-3.3-70b-instruct:free` | ❌ Not on OpenRouter |

## Integration

Discovery results are used by:
- `workflows/test-api-proxy.mjs` - API proxy testing
- `learning/model-capability-matrix.json` - Capability routing
- `shared/fleet-utils.js` - Fleet orchestration

## Notifications

When 3+ new models are detected, a notification file is created at:
```
learning/.new-models-notification
```

Check for notifications:
```bash
if [ -f learning/.new-models-notification ]; then
  cat learning/.new-models-notification
  rm learning/.new-models-notification  # Clear after reading
fi
```

## Maintenance

### View cron job:
```bash
crontab -l | grep discover
```

### Check logs:
```bash
tail -f learning/model-discovery.log
```

### Disable cron:
```bash
crontab -l | grep -v discover-free-models > /tmp/crontab
crontab /tmp/crontab
```

### Re-enable cron:
```bash
(crontab -l; echo "17 */3 * * * /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/scripts/discover-free-models.sh") | crontab -
```

## History

- **2026-07-02:** System created
  - Initial discovery: 26 free models
  - Removed 3 deprecated models from codebase
  - Added cron job for every 3 hours
