---
name: remember
description: Reload critical memories and infrastructure context
---

# Remember - Memory Refresh

Force-reload critical context from past sessions.

## What This Does

Reads and summarizes:
1. Infrastructure endpoints (orchestrator, fleet, database)
2. User preferences from feedback memories
3. Recent project context
4. Available API keys and models

## Usage

```
/remember
```

Or just ask:
- "refresh my memory"
- "what do you know about my preferences"
- "remind me of the infrastructure"

## Implementation

When this skill is invoked, you should:

1. **Run the session-start hook** to get fresh infrastructure status
2. **Read ~/.claude/MEMORY_INDEX.md** to see critical preferences
3. **Summarize** the key points in 4-5 bullets

**Example response:**

```
🔄 Memory refreshed from past sessions:

**Infrastructure:**
- Orchestrator: http://aio-01:5000 (status: healthy)
- 21 API keys available via /secrets/KEY_NAME
- Fleet: 9 nodes, 200+ models (API-only)

**Your preferences:**
- ⚠️ Always use multi-AI consensus (not single model)
- ⚠️ Always use fleet for parallel work
- ⚠️ Always verify before committing (multi-AI review)
- ⚠️ Cost is NOT a priority (quality over cost)

**Memory files:** 81 total in ~/Development/.../memory/

Use `/remember` anytime to refresh this context.
```

Keep it concise since the user has many sessions running.
