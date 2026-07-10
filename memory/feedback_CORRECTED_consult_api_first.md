---
name: consult-api-first-not-memories
description: "CRITICAL: Always query aio-01:5000 REST API FIRST before trusting local memory files - memories get stale, API is source of truth"
metadata:
  type: feedback
  priority: CRITICAL
  originSessionId: bb1a995f-71af-4cc4-b103-e8c04a6b4d48
  date: 2026-07-10
---

# ALWAYS Consult REST API Before Local Memories

**User feedback:** "Shouldn't u consult the rest api before local memories"

**Why this matters:**
- REST API at aio-01:5000 is the **SOURCE OF TRUTH**
- Memory files get **STALE** (written weeks/months ago)
- Architecture changes (e.g., local models removed 2026-06-28)
- Memories contradict each other when outdated

## What I Keep Doing WRONG

**Pattern:**
1. User asks question
2. I grep memory files
3. I answer based on stale memory
4. User corrects me: "we don't have that anymore!"
5. Repeat...

**Examples from this session:**
- Memory said "3 Anthropic + 3 local models"
- Reality: NO local models since 2026-06-28 (API-only)
- Memory said "6 models maximum"
- Reality: 78+ providers, 500+ models available
- I trusted memories instead of checking API

## Correct Order of Operations

**BLOCKING REQUIREMENT:**

When answering ANY question about:
- Fleet architecture
- Available models
- Multi-AI configuration
- System capabilities
- Infrastructure status

**DO THIS FIRST:**
1. ✅ Query REST API: `curl http://aio-01:5000/...`
2. ✅ Check database: via REST API endpoints
3. ✅ Read actual code: `/mnt/aio-01/claude-orchestrator/api/...`
4. ❌ THEN (and only then) consult memory files for context

**Never trust memories alone!**

## REST API Endpoints to Check FIRST

**Fleet & Infrastructure:**
```bash
# Fleet architecture (machines, roles)
curl http://aio-01:5000/inventory/machines | jq

# Graph database state
curl http://aio-01:5000/graph/stats | jq

# Service health
curl http://aio-01:5000/health | jq
```

**Models & Capabilities:**
```bash
# Available API keys (21 providers)
curl http://aio-01:5000/secrets/ | jq

# Check specific implementation
cat /mnt/aio-01/claude-orchestrator/api/llm_provider_fallback.py
```

**Learning & Memory:**
```bash
# Memory storage (PostgreSQL)
curl http://aio-01:5000/learning/memory?limit=5 | jq

# Workflow tracking
curl http://aio-01:5000/workflows/ | jq
```

## Why Memories Get Stale

**Changes since memories were written:**
- 2026-06-11: Memory says "6 models max" (written when we had limited local models)
- 2026-06-28: Switched to API-only (local models removed)
- 2026-07-10: NOW: 78+ providers, 500+ models available

**Memory can't self-update!** Only API reflects current state.

## How to Apply

**Before answering user questions:**
1. Identify what system component they're asking about
2. Query REST API for current state
3. Check actual implementation code if needed
4. Use memories ONLY for user preferences/feedback, not facts
5. If memory conflicts with API, **API wins**

**Save updated facts to NEW memory with current date!**

## What Memories ARE Good For

✅ **User preferences:**
- "Always use fleet"
- "Never do X"
- "Cost is not a priority"

✅ **Project decisions:**
- "We chose approach A over B because..."
- "Deadline is 2026-07-15"

✅ **Feedback patterns:**
- "I keep doing X wrong"
- "User corrected this 3 times"

❌ **NOT for system facts:**
- Available models (changes constantly)
- Fleet architecture (query database!)
- Endpoint availability (API changes)
- Component status (check actual code)

## Related Violations

This session I violated:
- [[feedback_always_use_fleet]] - By not checking API first
- [[reference_fleet_architecture_AUTHORITATIVE]] - By trusting old memories

**Root cause:** Assumed memories were up-to-date instead of verifying with API.

---

**Meta-lesson:** If user says "shouldn't you check X first?" - the answer is ALWAYS YES.
