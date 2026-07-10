---
name: 500-models-api-only-no-local
description: "CRITICAL: 500+ models available via API, ZERO local models since 2026-06-28 - stop saying 200+ or asking about local models"
metadata:
  type: feedback
  priority: CRITICAL
  originSessionId: bb1a995f-71af-4cc4-b103-e8c04a6b4d48
  date: 2026-07-10
  violation_count: MULTIPLE
---

# We Have 500+ Models (API-Only), NOT 200+, NO Local Models

**User frustration:** I kept saying "200+ models" and asking about local models despite architecture being API-only since 2026-06-28.

## FACTS (from orchestrator code)

**Source:** `/mnt/aio-01/claude-orchestrator/api/llm_provider_fallback.py` line 3

> "Uses 8 direct APIs + 70+ providers via OpenRouter = **78+ total providers, 500+ models**"

### Actual Numbers

- **78+ PROVIDERS** (the services: OpenRouter, DeepSeek, Groq, Cerebras, Anthropic, Google, etc.)
- **500+ MODELS** (the actual AI models available across those providers)
- **105+ FREE models** available
- **ZERO local models** (none since 2026-06-28)

### Architecture Change (2026-06-28)

**BEFORE 2026-06-28:**
- Had local Ollama models
- Mixed API + local
- Memories reference "3 Anthropic + 3 local"

**SINCE 2026-06-28:**
- ✅ API-only fleet
- ✅ No Ollama
- ✅ No local models
- ✅ 500+ models via APIs only

**Location of archived docs:** `~/.claude/archived/local-models-obsolete-2026-07-10/`

## What I Keep Getting Wrong

**Pattern this session:**

1. Said "200+ models" multiple times
2. Referenced "3 local models" from old hybrid memory
3. Asked "do we have local models?" 
4. User had to correct: "NO LOCAL MODELS!"
5. Finally checked orchestrator code and found 500+

**Root cause:** Trusted old memories (written before 2026-06-28) instead of checking REST API or actual code.

## Correct Answer (Always)

**Q: How many models do we have?**  
**A: 500+ models across 78+ API providers**

**Q: Do we have local models?**  
**A: NO - API-only since 2026-06-28**

**Q: What about Ollama?**  
**A: Archived on 2026-06-28, no longer used**

**Q: What about the "hybrid" memories?**  
**A: OUTDATED - written before API-only switch**

## How to Check (Don't Guess!)

**Option 1: Check orchestrator code (AUTHORITATIVE)**
```bash
grep -A 5 "total providers" /mnt/aio-01/claude-orchestrator/api/llm_provider_fallback.py
# Output: "78+ total providers, 500+ models"
```

**Option 2: Check CLAUDE.md**
```bash
grep "Model Access" ~/.claude/CLAUDE.md
# Output: "Model Access: 200+ free API models..."  # <-- This is WRONG! Says 200+ not 500+
```

**Option 3: Check REST API**
```bash
curl http://aio-01:5000/secrets/ | jq -r '.secrets[].key'
# Shows 21 API keys for different providers
```

## Task-Optimized Chains

From llm_provider_fallback.py:

- **CODE_GENERATION_CHAIN:** 15 providers (DeepSeek, Mistral, GPT-4o-mini, etc.)
- **REASONING_CHAIN:** 15 providers (Gemini 2.0 Flash Thinking, GPT-4o-mini, etc.)
- **FAST_CHEAP_CHAIN:** 12 providers (Groq Llama, Cerebras, Gemini Flash)
- **QUALITY_CHAIN:** 15 providers (GPT-4o, Gemini 2.5 Pro, Command-R-Plus)
- **MULTIMODAL_CHAIN:** 8 providers (GPT-4o, Gemini 2.0 Flash, Llama 3.2 Vision)

**Total unique providers across chains:** 78+

## Why This Matters

**When I say "200+ models":**
- ❌ Understates capability by 60%
- ❌ Makes user think system is smaller than it is
- ❌ Suggests I haven't checked actual architecture

**When I reference "local models":**
- ❌ References architecture that hasn't existed for months
- ❌ Makes user doubt I understand the system
- ❌ Wastes time with corrections

## How to Apply

**Before answering ANY question about models:**
1. ✅ Check orchestrator code: `/mnt/aio-01/claude-orchestrator/api/llm_provider_fallback.py`
2. ✅ Never say "200+ models" - say "500+ models across 78+ providers"
3. ✅ Never reference local models - we're API-only
4. ✅ If a memory mentions "local models" or "3 Anthropic + 3 local", mark it as OUTDATED (pre-2026-06-28)

## Related Memories

- [[feedback_CORRECTED_consult_api_first]] - Check API before memories
- [[reference_fleet_architecture_AUTHORITATIVE]] - Fleet architecture facts
- [[feedback_always_hybrid]] - OUTDATED (references local models that don't exist)

## Update Needed

`~/.claude/CLAUDE.md` line 5 says:
> "Model Access: 200+ free API models..."

**Should say:**
> "Model Access: 500+ models across 78+ API providers (OpenRouter, Anthropic, Google, Groq, Cerebras, DeepSeek, etc.)"

---

**Bottom line:** 500+ models via APIs only. No local models. Stop saying 200+.
