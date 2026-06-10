---
type: feedback
date: 2026-06-10
---

# Feedback: Use Gemini in Multi-AI with Graceful Fallback

**Use Gemini in multi-AI workflows, but handle API failures gracefully.**

## User Request
"please use gemini as well for multi-ai but if it fails (like api token issue) ignore and don't use it until you can again"

## Why
- Gemini provides additional perspective in multi-AI consensus
- More diverse model opinions → better consensus quality
- API token issues or rate limits shouldn't block workflows
- Graceful degradation is better than hard failures

## How to Apply

### In Workflow Worker Lists
```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',  // Claude models (always available)
  'gemini-1.5-pro',           // Gemini (via MCP) - try, but allow to fail
]

const verifications = await parallel(WORKERS.map(model => () =>
  agent(prompt, { model, schema })
    .catch(() => null)  // <-- CRITICAL: Catch failures, return null
))

const validReviews = verifications.filter(Boolean)  // Filter out failures
```

### Current Pattern (CORRECT)
- Workers return `null` on failure via `.catch(() => null)`
- Results are filtered with `.filter(Boolean)`
- Arbiter works with whatever workers succeeded
- If ALL workers fail, workflow reports error (appropriate)

### What NOT to Do
- Don't skip Gemini by default - always include it
- Don't fail the entire workflow if Gemini fails
- Don't retry Gemini failures indefinitely (one attempt is enough)
- Don't use Gemini as arbiter (opus is more reliable for that role)

## When Gemini Fails
- API token issues: Common, temporary - ignore for this run
- Rate limits: Ignore for this run, try again next time
- Connection errors: Ignore for this run
- Model unavailable: Ignore until available again

The workflow continues with remaining workers (opus/sonnet/haiku minimum).

## Examples in Codebase
- code-security.js line 278: WORKERS includes gemini-1.5-pro (commented)
- code-test.js line 23: ARBITER_PREFERENCE lists gemini-1.5-pro as fallback
- All workflows use `.catch(() => null)` pattern for resilience

## Related
- [[feedback_gemini_arbiter_fallback]] - Gemini as arbiter fallback
- [[feedback_multi_model_arbiter_workers]] - Multi-model consensus pattern
