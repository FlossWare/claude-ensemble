# Free AI API Keys Setup Guide

## Current Status

**Providers WITH Keys (Working):**
- ✅ **OpenRouter** - No key needed for free tier
- ✅ **DeepInfra** - No key needed for public models
- ✅ **HuggingFace** - No key needed for free inference
- ✅ **Groq** - API key configured (17 models)
- ✅ **Cerebras** - API key configured (3 models)
- ✅ **Google Gemini** - API key configured (39 models)

**Providers WITHOUT Keys (Missing):**
- ⚠️ **Together AI** - Free tier available
- ⚠️ **Mistral AI** - Free tier available
- ⚠️ **Fireworks AI** - Free tier available

## Current Discovery: 190 FREE Models

Breakdown:
- OpenRouter: 26 models
- DeepInfra: 55 models
- HuggingFace: 50 models
- Groq: 17 models
- Cerebras: 3 models
- Google Gemini: 39 models

## How to Get Free API Keys

### 1. Together AI (Free Tier)

**Sign up:** https://api.together.xyz/signup

**Free tier includes:**
- $25 free credits on signup
- Access to 100+ open source models
- Free tier continues after credits

**Setup:**
```bash
mkdir -p ~/.config/together
# After signup, get API key from https://api.together.xyz/settings/api-keys
echo "YOUR_API_KEY" > ~/.config/together/api-key
chmod 600 ~/.config/together/api-key
```

### 2. Mistral AI (Free Tier)

**Sign up:** https://console.mistral.ai/

**Free tier includes:**
- Free access to mistral-7b-instruct
- Rate limited but generous

**Setup:**
```bash
mkdir -p ~/.config/mistral
# Get API key from https://console.mistral.ai/api-keys/
echo "YOUR_API_KEY" > ~/.config/mistral/api-key
chmod 600 ~/.config/mistral/api-key
```

### 3. Fireworks AI (Free Tier)

**Sign up:** https://fireworks.ai/

**Free tier includes:**
- Free credits on signup
- Access to 100+ models
- Generous rate limits

**Setup:**
```bash
mkdir -p ~/.config/fireworks
# Get API key from https://fireworks.ai/api-keys
echo "YOUR_API_KEY" > ~/.config/fireworks/api-key
chmod 600 ~/.config/fireworks/api-key
```

### 4. Google Gemini (Already Configured)

**Verify:**
```bash
ls ~/.config/google/api-key
```

**If missing, get from:** https://makersuite.google.com/app/apikey

### 5. Groq (Already Configured)

**Verify:**
```bash
ls ~/.config/groq/api-key
```

**If missing, get from:** https://console.groq.com/keys

### 6. Cerebras (Already Configured)

**Verify:**
```bash
ls ~/.config/cerebras/api-key
```

## After Adding API Keys

Run discovery to see new models:
```bash
./scripts/discover-all-free-models.sh
cat learning/all-free-models-latest.json | jq '{total: .total_models, breakdown: .breakdown}'
```

## Potential Additional Models

If all 3 missing providers are added:
- **Together AI:** ~30-50 additional models
- **Mistral AI:** ~5-10 models
- **Fireworks AI:** ~20-30 models

**Estimated total with all providers:** 250-300 FREE models

## Provider Comparison

| Provider | Free Tier | API Key | Models | Rate Limits |
|----------|-----------|---------|--------|-------------|
| OpenRouter | ✅ | No | 26 | Generous |
| DeepInfra | ✅ | No | 55 | Moderate |
| HuggingFace | ✅ | No | 50 | Strict |
| Groq | ✅ | Yes | 17 | Very generous |
| Cerebras | ✅ | Yes | 3 | Generous |
| Google Gemini | ✅ | Yes | 39 | 15 RPM, 1M TPM |
| Together AI | ⚠️ | Yes | TBD | $25 credits |
| Mistral AI | ⚠️ | Yes | TBD | Moderate |
| Fireworks AI | ⚠️ | Yes | TBD | Credits-based |

## Notes

- All providers listed have genuine free tiers (not trials that expire)
- Rate limits vary but are sufficient for development/testing
- Some providers give credits that renew monthly
- OpenRouter aggregates many providers, so you get the best availability
