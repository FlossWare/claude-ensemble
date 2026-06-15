---
name: session-2026-06-15-orchestrator
description: Enhanced orchestrator with AI-driven learning (Thompson Sampling + PostgreSQL feedback)
metadata: 
  node_type: memory
  type: project
  date: 2026-06-15
  status: deployed
  originSessionId: 4feb3522-355a-4346-ae03-e690a9d9a11a
---

# Session 2026-06-15: Orchestrator Enhancement

## Context

User requested documentation audit and cleanup, then asked me to integrate the pi-02 orchestrator for all routing decisions.

## Key Insight from User

**"the orchestrator ought to be consulting ai for everything and learning from everything"**

Clarification: Orchestrator should **USE AI** (not BE an AI):
- Use Thompson Sampling algorithm for model selection
- Learn from feedback (record outcomes in PostgreSQL)
- Adaptive routing that improves over time

## What We Completed

### 1. Documentation Review & Cleanup
- ✅ Multi-AI doc review workflow: 491 files → 8 validated issues created in GitLab
- ✅ Cleaned up 64 redundant docs (473 → 409 files, saved 892KB)
  - Archived 13 obsolete files
  - Deleted 16 duplicates/stubs
  - Consolidated 52 files into 12 canonical docs

### 2. Orchestrator Integration
- ✅ Created `shared/orchestrator-client.js` - API wrapper for querying pi-02:8888
- ✅ Updated `ai-consensus.js` to query orchestrator for model selection
- ✅ Red Hat compliance: 3 Anthropic models (auto-detected via workspace path)
- ✅ Non-proprietary: 6 diverse models (maximum quality)

### 3. AI-Driven Learning Layer (NEW!)
- ✅ Created `shared/orchestrator-learning-adapter.js` - PostgreSQL integration
- ✅ Created `orchestrator-service-enhanced.mjs` - v2.0 with learning
- ✅ **Deployed to pi-02** and verified working

## Orchestrator Enhanced Features

**New Capabilities:**

1. **Thompson Sampling Model Selection**
   - Queries `learning.strategy_performance` for historical quality data
   - Samples from Beta(alpha, beta) distribution
   - Balances exploration (try new models) vs exploitation (use best)
   - Endpoint: `POST http://pi-02:8888/route-thompson`

2. **Feedback Recording**
   - Records task outcomes (success, quality, cost, duration)
   - Updates Thompson Sampling state (alpha/beta parameters)
   - Stores analytics in `monitoring.execution_summary`
   - Endpoint: `POST http://pi-02:8888/feedback`

3. **Model Rankings**
   - Returns models sorted by avg_reward
   - Optional taskType filter
   - Endpoint: `GET http://pi-02:8888/rankings`

**Verification:**
```bash
curl http://pi-02:8888/health
# Returns:
# - version: "2.0-learning"
# - learning_enabled: true
# - feedback_count: 0 (starts at zero)
# - models_available: 12

curl -X POST http://pi-02:8888/route-thompson \
  -H 'Content-Type: application/json' \
  -d '{"taskType": "code-review", "count": 3}'
# Returns 3 models via Thompson Sampling
```

## Files Created/Modified

**New Files:**
- `shared/orchestrator-client.js` - Client library for orchestrator API
- `shared/orchestrator-learning-adapter.js` - PostgreSQL learning integration
- `orchestrator-service-enhanced.mjs` - Enhanced orchestrator service
- `memory/reference_orchestrator_usage.md` - API documentation

**Modified:**
- `ai-consensus.js` - Now queries orchestrator for model selection
  - Auto-detects Red Hat context (3 models) vs non-proprietary (6 models)
  - Graceful fallback if orchestrator unavailable

**Deployed to pi-02:**
- `~/.claude/fleet/orchestrator-service-enhanced.mjs` - Running on port 8888
- `~/.claude/shared/orchestrator-learning-adapter.js` - Learning adapter
- `~/.claude/node_modules/pg/` - PostgreSQL client (installed)

## Git Commits

1. `08223bf` - docs: cleanup 64 redundant documentation files
2. `47d5e24` - feat: integrate pi-02 orchestrator for dynamic model routing
3. `df67800` - feat: add AI-driven learning to orchestrator

## Current State

**Orchestrator Status:**
- ✅ Running on pi-02:8888 (PID 383113)
- ✅ PostgreSQL connected (laptop-01:5432/learning)
- ✅ Thompson Sampling active
- ✅ Feedback loop operational
- ✅ 12 models available across fleet

**What Workflows Should Do Now:**
```javascript
// OLD (hardcoded):
const workers = ['opus', 'sonnet', 'haiku']

// NEW (orchestrator-driven):
const workers = await getWorkerModels(taskType, task, isRedHat)
// Returns 3 models for Red Hat, 6 for non-proprietary
// Selected via Thompson Sampling based on historical quality
```

## Next Steps (for future sessions)

1. **Update all workflows to use orchestrator:**
   - code-review.js
   - doc-review.js
   - All workflows in workflows/ directory
   - Should query `/route-thompson` before execution

2. **Wire feedback loop:**
   - After each workflow completes, POST feedback to `/feedback`
   - Include: model, success, quality score, cost, duration
   - This trains the orchestrator to route better over time

3. **Monitor learning:**
   - Check `/rankings` periodically to see which models excel
   - Verify Thompson Sampling is working (alpha/beta increasing)
   - Query `learning.strategy_performance` table for stats

4. **Test Red Hat compliance:**
   - Verify workspace path detection works
   - Ensure only Anthropic models used in /redhat/ paths
   - Test that non-proprietary gets 6 models

## Red Hat Compliance Notes

**Auto-Detection Logic:**
```javascript
const cwd = process.cwd()
const isRedHat = cwd.includes('/redhat/') || cwd.includes('/rh/')

if (isRedHat) {
  // Limit to 3 Anthropic models: opus, sonnet, haiku
  // Query orchestrator with { onlyAnthropic: true }
} else {
  // Use full 6-model consensus: fable, opus, sonnet, haiku, gpt-4o, gemini
}
```

## PostgreSQL Schema Used

**Tables:**
- `learning.strategy_performance` - Thompson Sampling state (alpha, beta, avg_reward)
- `monitoring.execution_summary` - Detailed execution logs

**Key Operations:**
```sql
-- Select best model via Thompson Sampling
SELECT strategy, alpha, beta FROM learning.strategy_performance;

-- Record feedback
UPDATE learning.strategy_performance 
SET alpha = alpha + 1, successes = successes + 1 
WHERE strategy = 'opus';

-- Get rankings
SELECT strategy, avg_reward FROM learning.strategy_performance 
ORDER BY avg_reward DESC;
```

## Important Context for Next Session

**User Expectation:**
- Orchestrator should handle ALL routing decisions
- Should use AI (Thompson Sampling algorithm)
- Should learn from every task outcome
- Should improve automatically over time

**What "Use AI" Means:**
- NOT: Put an LLM inside the orchestrator
- YES: Use Thompson Sampling (mathematical AI algorithm)
- YES: Learn from feedback (PostgreSQL database)
- YES: Adaptive behavior (gets smarter with data)

**Orchestrator is:**
- Routing service (not execution service)
- Learning system (records outcomes)
- Decision engine (Thompson Sampling)

**Orchestrator is NOT:**
- Task executor (use Workflow tool for that)
- LLM itself (it's a control system)
- Fixed/static (it adapts based on feedback)

## Session End State

**Working Directory:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills`

**Git Status:** Clean (all commits pushed to GitLab main)

**Orchestrator:** Running on pi-02, enhanced version deployed, learning active

**User Request:** Exit session (wants to remember current work)
