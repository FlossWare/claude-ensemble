# Red Hat AI Compliance - CLARIFIED
**Updated:** 2026-06-16 00:30 UTC

## 🔐 Red Hat Proprietary Code Rules

### laptop-01 ONLY

**For Red Hat proprietary code work on laptop-01:**

✅ **ALLOWED APIs (Cloud):**
- Anthropic via Vertex AI (4 models)
  - claude-fable-5
  - claude-opus-4-8
  - claude-sonnet-4-6
  - claude-haiku-4-5

❌ **PROHIBITED (No local models on laptop-01 for RH work):**
- Ollama models
- Any local inference
- Must use cloud APIs only

**Reason:** Red Hat requires cloud-based APIs (Anthropic via Vertex) - NO local models allowed for RH proprietary code.

---

## 🌐 All Other Servers (server-01/02/03, aio-01)

**For personal/non-RH work:**

✅ **ALLOWED:**
- All FREE cloud APIs (Groq, OpenRouter, Cerebras, DeepSeek, Cloudflare)
- All FREE local Ollama models (via NFS from NAS)
- No restrictions

---

## Current Configuration

### laptop-01
- **Current:** Uses local Ollama models (20 models via NFS)
- **Should be:** ONLY Anthropic cloud APIs for RH work
- **Action needed:** Remove/disable Ollama on laptop-01

### server-01/02/03
- **Current:** All use NFS models from `/mnt/nas/ai-models/ollama-from-laptop-01`
- **Status:** ✅ CORRECT - can use any models (not used for RH work)

---

## Action Plan

1. **Disable Ollama on laptop-01** (RH compliance)
   ```bash
   systemctl --user stop ollama
   systemctl --user disable ollama
   ```

2. **Keep servers with NFS models** (personal work OK)
   - server-01/02/03 continue using `/mnt/nas` models
   - All FREE, no cost

3. **laptop-01 uses ONLY:**
   - Anthropic APIs via `ANTHROPIC_VERTEX_PROJECT_ID`
   - No local models
   - No other cloud APIs for RH work

