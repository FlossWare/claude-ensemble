# Workflow Skills Integration Guide

**Status:** ✅ Complete (Session 5, 2026-09-27)

All 4 workflow skills are now integrated with Thompson/Learning/Alert ecosystem. They automatically learn which models perform best for each task type.

---

## Quick Start

### 1. PR Review Skill

```bash
# Interactive PR review (asks before approve/reject)
claude code /code-pr-review

# Autonomous variant (auto-approves/rejects)
claude code /code-pr-review-auto
```

**What it does:**
- Detects GitHub/GitLab platform
- Fetches open PRs
- Multi-AI consensus review (opus, sonnet, haiku)
- Arbiter decision synthesis
- User confirms before posting

**Integration points:**
- ✅ Thompson selects which models to use for review
- ✅ Learning records: was PR approved? quality rating (2-4 scale)
- ✅ Cost tracking logs tokens per reviewer
- ✅ Request correlation IDs trace all calls
- ✅ Circuit breaker fallback if Thompson unavailable

---

### 2. Documentation Skill

```bash
# Interactive doc generation (asks before creating PR)
claude code /code-doc

# Autonomous variant (auto-creates doc PRs)
claude code /code-doc-auto
```

**What it does:**
- Scans codebase for undocumented functions/classes
- Analyzes signatures and complexity
- Multi-AI doc generation with consensus
- Arbiter merges documentation
- User confirms before creating PR

**Integration points:**
- ✅ Thompson selects models for doc generation
- ✅ Learning records: did docs match quality expectations? (rating 2-4)
- ✅ Cost tracking logs token usage per doc generator
- ✅ Request correlation IDs for debugging
- ✅ Circuit breaker fallback

---

## How Skills Learn

### 1. Model Selection via Thompson

When a skill runs:
```
1. Skill starts → generates requestId (e.g., skill_pr_review_a1b2c3)
2. Thompson called → recommends best model for task type
   - First run: "No data yet, recommend haiku (cheapest)"
   - Later runs: "Sonnet is 30% better quality for code_review, recommend it"
3. Selected model runs workflow
```

### 2. Outcome Recording

After skill completes:
```
skill → learning.process_outcome(
  task_id='workflow_123',
  task_type='code_review',           # Task type for Thompson
  model='sonnet',                    # Which model was used
  rating=4,                          # Quality rating (2-4 scale)
  tokens=5000,                       # Input + output tokens
  cost=0.032,                        # USD cost
  request_id='skill_pr_review_a1b2c3' # For tracing
)
```

### 3. Thompson Learns

```
Thompson updates priors:
  code_review + sonnet:
    - successes: 1
    - failures: 0
    - total_cost: $0.032
    - total_tokens: 5000
    - calls: 1
    - success_rate: 100%

Next code_review:
  Thompson samples posterior → recommends sonnet again
  (builds confidence over time)
```

---

## Quality Ratings (2-4 Scale)

Each outcome recorded with quality rating:

| Rating | Meaning | Example |
|--------|---------|---------|
| 4 | Excellent | PR review found critical bug, user approved immediately |
| 3 | Acceptable | Docs generated but needed minor fixes |
| 2 | Poor | Wrong analysis, misleading documentation |

**How rating is determined:**
- **Interactive skills** (`code-pr-review`, `code-doc`): You rate (4=approved, 2=rejected, 3=needs changes)
- **Autonomous skills** (auto variants): Consensus model rates based on acceptance criteria

---

## Cost Tracking

Every agent call is logged:

```bash
# View all costs
cat cost_tracking/api_costs.jsonl | jq .

# Example entry:
{
  "timestamp": "2026-09-27T01:20:00",
  "model": "sonnet",
  "input_tokens": 3500,
  "output_tokens": 1200,
  "cost_usd": 0.0321,
  "task_name": "code_review",
  "source": "workflow",
  "request_id": "skill_pr_review_a1b2c3"
}

# Summary stats
python3 -c "
import json
with open('cost_tracking/api_costs.jsonl') as f:
    logs = [json.loads(line) for line in f]
total = sum(l['cost_usd'] for l in logs)
print(f'Total cost: \${total:.2f}')
print(f'Calls: {len(logs)}')
print(f'By model: {set(l[\"model\"] for l in logs)}')
"
```

---

## Request Correlation IDs

Every workflow run gets a unique ID for tracing:

```
Generated: skill_pr_review_a1b2c3
  ↓
Passed to Thompson.select_model(request_id='...')
  ↓
Passed to agent() calls in workflow
  ↓
Logged to Learning service
  ↓
Logged to cost_tracking

Usage: Find all activity for one workflow run
grep 'skill_pr_review_a1b2c3' cost_tracking/api_costs.jsonl
grep 'skill_pr_review_a1b2c3' learning/post_task_outcomes/*.json
```

---

## Circuit Breaker (Graceful Degradation)

If Thompson or Learning services are unavailable:

```javascript
// Graceful fallback in skill code:
try {
  const selectedModel = await selectModelViaThompson('code_review', requestId)
} catch (err) {
  log(`⚠️ Thompson unavailable, falling back to haiku`)
  selectedModel = 'haiku'  // Default cheapest model
}

// Learning recording is non-blocking:
try {
  await recordOutcomeToLearning(...)
} catch (err) {
  log(`⚠️ Learning failed (non-blocking)`)
  // Workflow continues regardless
}
```

**Benefits:**
- Skills work even if Thompson/Learning down
- No cascading failures
- Service degradation instead of hard failure
- Work still gets cost-tracked and logged locally

---

## Security: Command Injection Prevention

All parameters (taskId, requestId, model, etc.) are:
1. Marshaled to JSON
2. JSON passed to Python subprocess
3. Parsed in Python before use
4. **Never interpolated into shell commands**

**Why:** Prevents shell injection if parameters contain quotes or metacharacters.

---

## Monitoring Skills

### Check Recent Outcomes

```bash
# List all recorded outcomes
ls learning/post_task_outcomes/

# View specific outcome
cat learning/post_task_outcomes/task_001_code_review.json | jq .

# Example output:
{
  "task_id": "workflow_001",
  "task_type": "code_review",
  "model": "sonnet",
  "rating": 4,
  "tokens_used": 5000,
  "cost_usd": 0.032,
  "timestamp": "2026-09-27T01:20:00",
  "request_id": "skill_pr_review_a1b2c3"
}
```

### View Thompson State

```bash
# See all models + success rates
cat learning/thompson-sampling-state.json | jq .task_types.code_review

# Example:
{
  "sonnet": {
    "successes": 3,
    "failures": 0,
    "total_cost": 0.096,
    "calls": 3,
    "success_rate": 1.0,
    "last_updated": "2026-09-27T01:20:00"
  }
}
```

### Check Cost Trends

```bash
# Total spend by model
python3 -c "
import json
by_model = {}
with open('cost_tracking/api_costs.jsonl') as f:
  for line in f:
    data = json.loads(line)
    model = data['model']
    by_model[model] = by_model.get(model, 0) + data['cost_usd']
for model, cost in sorted(by_model.items()):
  print(f'{model}: \${cost:.4f}')
"
```

---

## Example: First PR Review with Learning

```bash
# User runs skill
claude code /code-pr-review

# Skill flow:
requestId = skill_pr_review_abc123  # Generated at start

thompson.select_model('code_review')  # → Returns 'haiku' (no data)

# Review runs with haiku, opus, sonnet (consensus)

# User confirms: Approve
rating = 4

# Outcome recorded:
learning.process_outcome(
  'workflow_001',
  'code_review',
  'haiku',  # Model that was selected
  4,        # User approved
  3500,     # Input tokens
  1200,     # Output tokens
  'skill_pr_review_abc123'
)

# Cost logged:
cost_tracking.log_call(
  'haiku', 3500, 1200,
  'code_review',
  request_id='skill_pr_review_abc123'
)

# Next run with code_review:
thompson.select_model('code_review')
# Thompson sees: haiku: 1/1 success (100%)
# → Recommends haiku again
# (Confidence grows with more data)
```

---

## Troubleshooting

### Skills Slow or Hanging

Check Thompson service:
```bash
ps aux | grep thompson
# Should see: python3 thompson-service/thompson_service.py

# If not running:
systemctl --user start rh-thompson.service
```

### Learning Not Recording

Check socket:
```bash
ls -la /tmp/rh-learning.sock
# Should exist if Learning service running

# Check logs:
tail -50 ~/.claude/rh-learning-service.log
```

### Cost Spikes

View recent costs:
```bash
# Last 10 calls
tail -10 cost_tracking/api_costs.jsonl | jq .cost_usd

# By task type
python3 -c "
import json
by_task = {}
with open('cost_tracking/api_costs.jsonl') as f:
  for line in f:
    data = json.loads(line)
    task = data.get('task_name', 'unknown')
    by_task[task] = by_task.get(task, 0) + data['cost_usd']
for task, cost in sorted(by_task.items()):
  print(f'{task}: \${cost:.2f}')
"
```

---

## Implementation Details

### Thompson Model Selection

Function: `selectModelViaThompson(taskType, requestId, fallback='haiku')`
- Calls Python subprocess (shared/thompson_client.py)
- Parameters passed via JSON (prevents injection)
- Timeout: 3 seconds (fallback to haiku if slow)
- Returns: model name string

### Learning Recording

Function: `recordOutcomeToLearning(taskId, taskType, model, rating, tokens, cost, requestId)`
- Calls Python subprocess (learning/learning_client.py)
- Non-blocking (errors silently caught)
- Timeout: 3 seconds
- Records to learning service socket

### Cost Logging

Function: `logCostMetrics(model, inputTokens, outputTokens, taskName, requestId)`
- Calculates cost from tokens (pricing: haiku/sonnet/opus)
- Logs to cost_tracking/api_costs.jsonl
- Non-blocking (errors silently caught)
- Timeout: 2 seconds

---

## Files Modified

**Session 5 Integration (2026-09-27):**
- `tools/code-pr-review.js` — +230 lines (Thompson + Learning)
- `tools/code-doc.js` — +195 lines (Thompson + Learning)
- `tools/code-pr-review-auto.js` — +98 lines
- `tools/code-doc-auto.js` — +72 lines

**Total:** 521 lines of integration code

**Security fixes (commit bacef22):**
- Command injection prevention
- JSON marshaling for subprocess parameters
- All 4 files hardened

---

## Next Steps

1. **Use the skills** — PR reviews and doc generation auto-learn
2. **Monitor Thompson** — Check `learning/thompson-sampling-state.json`
3. **Track costs** — View `cost_tracking/api_costs.jsonl`
4. **Review outcomes** — Check `learning/post_task_outcomes/`
5. **Integrate more skills** — Same 6-point pattern for new skills

Skills are ready and learning!
