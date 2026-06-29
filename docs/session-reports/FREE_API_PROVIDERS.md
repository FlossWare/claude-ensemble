# Free AI API Providers

This document lists free AI API providers that can expand your model access beyond the local fleet.

## Already Configured APIs

You currently have these API keys configured:

- **Groq** - Very fast inference (free tier)
- **Cerebras** - Extremely fast inference (free tier)
- **DeepSeek** - Free access to DeepSeek models
- **Cloudflare Workers AI** - Free tier
- **OpenRouter** - Free + paid models aggregator
- **Google Gemini** - Free tier available
- **OpenAI** - Paid (GPT-4, etc.)
- **Anthropic** - Paid (Claude, etc.)

## Additional Free APIs (Require Sign-Up)

### 1. Together.ai
- **URL:** https://api.together.xyz/signup
- **Free Credits:** $25 on sign-up
- **Models:** 50+ including Llama 3.x, Mixtral, Qwen, CodeLlama, and more
- **API Key Location:** https://api.together.xyz/settings/api-keys
- **Environment Variable:** `TOGETHER_API_KEY`

### 2. Fireworks.ai
- **URL:** https://fireworks.ai/login
- **Free Tier:** Yes
- **Notable:** Very fast inference speeds
- **Models:** Llama, Mixtral, Gemma, and specialized models
- **API Key Location:** Dashboard after login
- **Environment Variable:** `FIREWORKS_API_KEY`

### 3. Hugging Face
- **URL:** https://huggingface.co/join
- **Free Tier:** Yes
- **Models:** 100,000+ models via Inference API
- **API Key Location:** https://huggingface.co/settings/tokens
- **Environment Variable:** `HUGGINGFACE_API_KEY`
- **Note:** Create a "Read" token for API access

### 4. Mistral AI
- **URL:** https://console.mistral.ai/
- **Free Tier:** Yes
- **Models:** Direct access to Mistral models (Mistral 7B, Mixtral, etc.)
- **API Key Location:** Console after login
- **Environment Variable:** `MISTRAL_API_KEY`

## Other Notable Free/Trial APIs

### 5. Cohere
- **URL:** https://cohere.com/
- **Free Trial:** Yes
- **Models:** Command, Embed, Rerank

### 6. AI21 Labs
- **URL:** https://www.ai21.com/
- **Free Tier:** Yes
- **Models:** Jurassic models

### 7. Perplexity
- **URL:** https://www.perplexity.ai/
- **Free Tier:** Limited
- **Note:** Primarily a search/answer product

### 8. Anyscale
- **URL:** https://www.anyscale.com/
- **Free Tier:** Yes
- **Models:** Llama, Mistral via Ray

## How to Add API Keys

After signing up for any of the above services, use the helper script:

```bash
/tmp/add-api-keys.sh
```

Or manually add to `~/.bashrc`:

```bash
export TOGETHER_API_KEY='your-key-here'
export FIREWORKS_API_KEY='your-key-here'
export HUGGINGFACE_API_KEY='your-key-here'
export MISTRAL_API_KEY='your-key-here'
```

Then reload:
```bash
source ~/.bashrc
```

## Do You Need These?

With your current setup, you have:
- **~47 local Ollama models** on NAS (free, no API limits)
- **9 GGUF models** for llama.cpp
- **7 existing API providers** (5 free, 2 paid)

The additional free APIs are useful for:
- **Access to latest models** before they're available locally
- **No local compute needed** for heavy workloads
- **Trying new models** without downloading
- **Backup options** when local resources are busy

But with your extensive local collection, they're optional!

## Rate Limits (Approximate)

| Provider | Free Tier Limit |
|----------|----------------|
| Groq | 30 requests/min |
| Cerebras | Generous free tier |
| DeepSeek | Good free tier |
| Together.ai | $25 credits |
| Fireworks.ai | Varies by model |
| Hugging Face | 1000 requests/day (varies) |
| Mistral AI | Rate limited |

---

**Last Updated:** 2026-06-16
**Location:** ~/FREE_API_PROVIDERS.md
