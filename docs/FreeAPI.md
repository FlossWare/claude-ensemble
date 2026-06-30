# Free API Integration

**Last Updated:** 2026-06-30  
**Status:** ⚠️ All free APIs currently blocked or rate-limited

## Overview

This system was designed to use free AI API tiers to distribute consensus workloads across the fleet without incurring costs. However, data center IP addresses are commonly blocked by free API providers using Cloudflare protection.

## Intended Free API Providers

### 1. Groq (Fast Inference)
**Status:** ❌ BLOCKED  
**Error:** HTTP 403 error code 1010 (Cloudflare blocking data center IPs)  
**API Key Location:** `$GROQ_API_KEY` in `~/.api-keys`  
**Models:**
- `llama-3.3-70b-versatile`
- `llama-3.1-8b-instant`
- `mixtral-8x7b-32768`

**Rate Limit:** 30 requests/min (when working)  
**URL:** https://api.groq.com/openai/v1/chat/completions

**Why it fails:**
```
HTTP 403: error code: 1010
```
Cloudflare detects requests from data center IPs (server-01/02/03, laptop-01, pi-01/02) and blocks them. This is a common anti-abuse measure for free tiers.

### 2. OpenAI (gpt-4o-mini)
**Status:** ❌ QUOTA EXCEEDED  
**Error:** HTTP 429 "You exceeded your current quota"  
**API Key Location:** `$OPENAI_API_KEY` in `~/.api-keys`  
**Models:**
- `gpt-4o-mini`
- `gpt-3.5-turbo`

**Rate Limit:** Depends on tier (currently exhausted)  
**URL:** https://api.openai.com/v1/chat/completions

**Why it fails:**
```
HTTP 429: You exceeded your current quota, please check your plan and billing details
```
Free tier quota exhausted. OpenAI free tier is very limited and shared across all projects using this key.

### 3. Google AI Studio (Gemini)
**Status:** ❌ AUTH FAILED  
**Error:** HTTP 401 "Invalid authentication credentials"  
**API Key Location:** `$GOOGLE_API_KEY` in `~/.api-keys`  
**Models:**
- `gemini-2.0-flash-exp`
- `gemini-1.5-pro`

**Rate Limit:** 15 RPM, 1M requests/day (when working)  
**URL:** https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent

**Why it fails:**
```
HTTP 401: Request had invalid authentication credentials. Expected OAuth 2 access token, login cookie or other valid authentication credential
```
API key format may be incorrect or expired. Google AI Studio uses a different auth mechanism than standard Google Cloud APIs.

### 4. DeepSeek
**Status:** ❌ MODEL NOT FOUND  
**Error:** HTTP 404 "The model `deepseek-chat` does not exist"  
**API Key Location:** `$DEEPSEEK_API_KEY` in `~/.api-keys`  
**Models:**
- `deepseek-chat` (attempted)

**URL:** https://api.deepseek.com/v1/chat/completions

**Why it fails:**
```
HTTP 404: The model `deepseek-chat` does not exist or you do not have access to it
```
Model name may be incorrect, or API endpoint may have changed.

## Other Free APIs (Not Yet Tested)

### DeepInfra
**Models:**
- `meta-llama/Meta-Llama-3.1-70B-Instruct`
- `mistralai/Mixtral-8x22B-Instruct-v0.1`

**Key:** `$DEEPINFRA_API_KEY` (not currently in environment)

### Together AI
**Models:**
- `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo`
- `mistralai/Mixtral-8x22B-Instruct-v0.1`

**Key:** `$TOGETHER_API_KEY` (not currently in environment)

### Cohere
**Status:** ⚠️ HAS KEY, NOT TESTED  
**Models:**
- `command-r-plus`

**Key:** `$COHERE_API_KEY` in `~/.api-keys`  
**URL:** https://api.cohere.ai/v1/chat

### HuggingFace Inference API
**Models:**
- `meta-llama/Meta-Llama-3-70B-Instruct`
- `mistralai/Mixtral-8x7B-Instruct-v0.1`

**Key:** `$HUGGINGFACE_API_KEY` (not currently in environment)

### Fireworks AI
**Models:**
- `accounts/fireworks/models/llama-v3p1-70b-instruct`

**Key:** `$FIREWORKS_API_KEY` (not currently in environment)

## Architecture

### How Free APIs Were Integrated

**1. Environment Variables**
All API keys stored in `~/.api-keys` and sourced on session start:

```bash
# On aio-01 (orchestrator)
source ~/.api-keys

# Contains:
export GROQ_API_KEY="gsk_..."
export OPENAI_API_KEY="sk-proj-..."
export GOOGLE_API_KEY="AIza..."
export DEEPSEEK_API_KEY="sk-..."
export COHERE_API_KEY="LBD..."
export CLOUDFLARE_API_KEY="cfat_..."
export OPENROUTER_API_KEY="sk-or-v1-..."
# etc.
```

**2. Fleet Executor (`shared/fleet_executor.py`)**

Maps model names to providers and API endpoints:

```python
PROVIDERS = {
    'openai': {
        'url': 'https://api.openai.com/v1/chat/completions',
        'key_env': 'OPENAI_API_KEY',
    },
    'groq': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key_env': 'GROQ_API_KEY',
    },
    'google': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'key_env': 'GOOGLE_API_KEY',
    },
    # etc.
}

def map_model_to_provider(model):
    model_lower = model.lower()
    if 'groq' in model_lower or 'llama' in model_lower or 'mixtral' in model_lower:
        return 'groq'
    if 'gpt' in model_lower:
        return 'openai'
    if 'gemini' in model_lower:
        return 'google'
    # etc.
```

**3. Worker Execution via SSH**

Orchestrator on aio-01 SSHs to workers and passes API key in request:

```python
# On aio-01 (orchestrator)
result = subprocess.run(
    ['ssh', f'claude@{worker}', 'python3', worker_script],
    input=json.dumps({
        'task': 'What is 2+2?',
        'model': 'groq/llama-3.3-70b-versatile',
        'api_key': os.environ['GROQ_API_KEY'],  # Passed from orchestrator
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        # etc.
    }),
    capture_output=True,
    text=True
)
```

Worker (`shared/python-worker.py`) receives params via stdin and makes HTTP request:

```python
# On remote worker (server-01, pi-01, etc.)
import json, sys, urllib.request

params = json.loads(sys.stdin.read())

request = urllib.request.Request(
    params['url'],
    data=json.dumps({
        'model': params['model'],
        'messages': [{'role': 'user', 'content': params['task']}],
        'max_tokens': params['max_tokens']
    }).encode(),
    headers={
        'Authorization': f"Bearer {params['api_key']}",
        'Content-Type': 'application/json'
    }
)

response = urllib.request.urlopen(request)
result = json.loads(response.read())
```

**4. Retry Logic with Exponential Backoff**

```python
def execute_on_worker(..., max_retries=2, backoff_seconds=1.0):
    RETRY_CODES = {429, 500, 502, 503, 504}  # Transient errors
    
    for attempt in range(max_retries + 1):
        result = _execute_worker_attempt(...)
        
        if http_code in RETRY_CODES and attempt < max_retries:
            delay = backoff_seconds * (2 ** attempt)  # 1s, 2s, 4s
            time.sleep(delay)
            continue
        
        return result
```

**5. Orchestrator Script**

`orchestrate.py` on aio-01 distributes tasks to all 6 workers:

```python
#!/usr/bin/env python3
from shared.fleet_executor import execute_on_fleet_parallel

workers = ["server-01", "server-02", "server-03", "laptop-01", "pi-01", "pi-02"]
tasks = ["What is 2+2?"] * 6  # Same task for consensus

results = execute_on_fleet_parallel(
    workers=workers,
    model="groq/llama-3.3-70b-versatile",
    tasks=tasks,
    max_tokens=4000,
    max_retries=2,
    backoff_seconds=1.0
)
```

## Current Issues

### Issue 1: Cloudflare Blocking (403 Error Code 1010)

**Affected:** Groq, Cerebras, OpenRouter  
**Cause:** Free API providers use Cloudflare to block data center IPs  
**Detection:** HTTP 403 with `error code: 1010`

**Why this happens:**
- Our workers run on servers/VMs with data center IP addresses
- Cloudflare fingerprints these as "automated/bot traffic"
- Free tiers block data center IPs to prevent abuse

**Potential solutions:**
1. ❌ Proxy through residential IPs (against ToS)
2. ❌ Use VPN (still detectable, against ToS)
3. ✅ Use paid API tiers (no Cloudflare blocking)
4. ✅ Run from residential IP (laptop-01 only, not scalable)

### Issue 2: OpenAI Quota Exhausted (429)

**Affected:** OpenAI (gpt-4o-mini, gpt-3.5-turbo)  
**Cause:** Free tier quota very limited  
**Detection:** HTTP 429 "exceeded your current quota"

**Solutions:**
1. Wait for quota reset (monthly)
2. Add payment method to OpenAI account
3. Use alternative providers

### Issue 3: Google Auth Issues (401)

**Affected:** Google AI Studio (Gemini)  
**Cause:** API key format or authentication method mismatch  
**Detection:** HTTP 401 "invalid authentication credentials"

**Potential causes:**
- API key expired
- Wrong auth format (API key vs OAuth)
- API not enabled in Google Cloud Console

**Solutions:**
1. Regenerate API key from https://aistudio.google.com/app/apikey
2. Verify API is enabled
3. Check if OAuth2 required instead of API key

### Issue 4: DeepSeek Model Not Found (404)

**Affected:** DeepSeek  
**Cause:** Incorrect model name or API changes  
**Detection:** HTTP 404 "model does not exist"

**Solutions:**
1. Check DeepSeek documentation for correct model names
2. Try alternative model names (`deepseek-coder`, `deepseek-chat-v2`)
3. Verify API endpoint hasn't changed

## Testing Free APIs

**Test script location:** `/tmp/test-free-apis.py`

```bash
# On aio-01
source ~/.api-keys
python3 /tmp/test-free-apis.py
```

**Expected output:**
```
=== Testing Groq ===
❌ FAILED: HTTP 403: error code: 1010

=== Testing OpenAI ===
❌ FAILED: HTTP 429: exceeded quota

=== Testing Google ===
❌ FAILED: HTTP 401: invalid auth

=== Testing DeepSeek ===
❌ FAILED: HTTP 404: model not found
```

## Deployment

### API Keys Deployed To:
- ✅ **aio-01:** `/home/sfloess/.api-keys` (orchestrator)
- ✅ **server-01/02/03:** `/home/claude/.api-keys` (workers)
- ✅ **pi-01/02:** `/home/claude/.api-keys` (workers)

**Note:** Workers don't actually use their local API keys. The orchestrator (aio-01) loads keys from its environment and passes them in SSH requests to workers.

### Files

**Orchestrator:**
- `/home/sfloess/Development/.../orchestrate.py` - Main orchestration script

**Fleet Executor:**
- `shared/fleet_executor.py` - Python-based distributed execution
- `shared/python-worker.py` - Worker script (executes on remote nodes)

**Configuration:**
- `~/.api-keys` - Environment variables with API keys
- `~/.bashrc` - Sources `.api-keys` on login

## Alternative: Paid APIs

When free APIs fail, the system can fall back to paid APIs:

**Working paid APIs:**
- ❓ Anthropic (requires `$ANTHROPIC_API_KEY` - not currently set)
- ❌ OpenAI (quota exceeded even on paid tier)

**To use Anthropic:**
```bash
# Add to ~/.api-keys
export ANTHROPIC_API_KEY="sk-ant-..."

# Test
python3 orchestrate.py "What is 2+2?" claude-sonnet-4
```

## Recommendations

### Short Term
1. **Fix Google Auth:** Regenerate API key from AI Studio
2. **Fix DeepSeek:** Check documentation for correct model names
3. **Add Anthropic Key:** For paid fallback
4. **Test Cohere:** Already have key, not yet tested

### Long Term
1. **Accept Cloudflare Blocking:** Free APIs won't work from data center IPs
2. **Budget for Paid APIs:** $50-100/month for fleet consensus workloads
3. **Hybrid Approach:** 
   - Use local Ollama models for non-critical tasks
   - Use paid APIs for high-quality consensus
   - Avoid free APIs entirely (unreliable)

## Related Documentation

- `lib/fleet-api-policy.json` - API access policy per node
- `shared/FLEET-SSH-README.md` - SSH-based fleet orchestration
- `README.md` - Overall system architecture
