# AI Learning System - Complete Implementation

## Overview

The learning system captures arbiter/worker decisions and provides feedback to improve future decisions over time.

## How It Works

### 1. Decision Capture (Post-Decision)

After every arbiter decision, capture:
- Which workers proposed
- What they proposed (approach, confidence, rationale)
- Which arbiter decided
- Which proposal was selected (and why)
- Which proposals were rejected (and why each one)
- Consensus score
- Timestamp

Stored in: `~/.claude/learning/decisions.jsonl`

### 2. Worker Feedback (Pre-Proposal)

Before workers propose, they get feedback:
- How often their model is selected for this task type
- Common rejection reasons for their model
- Their average confidence scores
- Suggestions to improve selection chances

Example:
```
Historical Performance:
Your model (haiku) was selected 3/15 times (20%) for test_plan tasks.
Consider more comprehensive approaches to increase selection rate.

Common rejections:
- "Missing UI validation steps" (3 times)
- "Incomplete test coverage" (2 times)
```

### 3. Arbiter Feedback (Pre-Decision)

Before arbiter decides, they get feedback:
- Selection frequency for each worker model
- Common rejection patterns
- Historical success rates
- Patterns to consider

Example:
```
Historical Selection Patterns:
- opus: selected 8 times
- sonnet: selected 5 times  
- haiku: selected 2 times

Consider proposal quality over historical frequency,
but use patterns to inform your decision.
```

### 4. Continuous Learning Loop

```
┌─────────────────┐
│  Worker Proposes│
│  (with feedback)│
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Arbiter Decides │
│  (with feedback)│
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Capture Decision│
│  (for learning) │
└────────┬────────┘
         │
         v
  [Next Decision Uses This Data]
```

## Integration Points

### code-test.js ✅
- Workers get feedback before proposing test plans
- Arbiter gets feedback before selecting
- Decision captured after selection

### code-solve.js (TODO)
- Workers get feedback before proposing bug fixes
- Arbiter gets feedback before selecting
- Decision captured after selection
- Can update outcome after fix is applied

### code-review.js (TODO)
- Workers get feedback before reviewing code
- Arbiter gets feedback before final verdict
- Decision captured after verdict

### pr-review.js (TODO)
- Workers get feedback before PR review
- Arbiter gets feedback before approval decision
- Decision captured after decision

## Learning Database Schema

```jsonl
{
  "timestamp": "2026-06-06T18:30:00Z",
  "workflow": "code-test",
  "task_type": "test_plan",
  "worker_models": ["opus", "sonnet", "haiku", "gemini"],
  "selected_model": "sonnet",
  "selected_index": 1,
  "arbiter_model": "opus",
  "why_accepted": "Most comprehensive test strategy...",
  "rejection_reasons": {
    "opus": "Lower confidence than sonnet",
    "haiku": "Missing UI validation steps",
    "gemini": "Incomplete integration testing"
  },
  "consensus_score": 85,
  "worker_confidences": [88, 92, 75, 65],
  "outcome": "success"
}
```

## Session-Level Learning (User Interactions)

**Goal**: Learn from ALL user interactions, not just arbiter/worker decisions

**Captures**:
- User corrections ("no, do it this way")
- User preferences ("I prefer X over Y")
- User feedback ("that worked great" / "that didn't work")
- Task-specific patterns ("for code reviews, always check X")

**Storage**: `~/.claude/memory/` (auto-memory system)

**Integration**:
1. After each interaction, check if there's feedback
2. Classify feedback type (correction, preference, success/failure)
3. Save to appropriate memory file
4. Feed back into future decisions

## Benefits

### For Workers
- Learn what makes proposals successful
- Avoid past rejection patterns
- Improve confidence calibration
- Adapt to user preferences over time

### For Arbiters
- More informed decisions
- Understand model strengths/weaknesses
- Identify consistent patterns
- Reduce bias toward specific models

### For Users
- Better decisions over time
- More consistent results
- Personalized to their preferences
- Transparent learning process

## Metrics Tracked

- **Model Selection Frequency**: How often each model is chosen
- **Rejection Patterns**: Common reasons for rejection
- **Confidence Calibration**: How well confidence predicts selection
- **Success Rates**: How often decisions lead to good outcomes
- **Arbiter Agreement**: Which arbiters align with outcomes

## Example Learning Insights

After 50 decisions:
```
Model Performance:
- sonnet: selected 22/50 times (44%) - highest for test plans
- opus: selected 15/50 times (30%) - best for complex strategies
- haiku: selected 8/50 times (16%) - often too simple
- gemini: selected 5/50 times (10%) - lower confidence

Top Rejection Reasons:
1. "Missing UI validation" (haiku, 8 times)
2. "Lower confidence than alternatives" (gemini, 6 times)
3. "Incomplete test coverage" (haiku, 5 times)

Success Rate: 82% (41/50 decisions led to successful outcomes)
```

## Future Enhancements

1. **Outcome Tracking**: Update decisions with actual outcomes
2. **Confidence Calibration**: Adjust model confidence based on success
3. **Cross-Workflow Learning**: Share patterns across workflows
4. **User Preference Integration**: Incorporate user corrections
5. **Model Evolution**: Track how models improve over time
6. **Automated Reporting**: Generate learning reports periodically

## Files

- `shared/learning-system.js` - Full learning system with exports
- `code-test.js` - Integrated with learning (inline version)
- `~/.claude/learning/decisions.jsonl` - Decision database

## Commands

```bash
# View recent decisions
tail -20 ~/.claude/learning/decisions.jsonl | jq

# Count decisions per model
grep -o '"selected_model":"[^"]*"' ~/.claude/learning/decisions.jsonl | sort | uniq -c

# View rejection patterns
grep -o '"rejection_reasons":{[^}]*}' ~/.claude/learning/decisions.jsonl

# Learning report (future)
/learning-report
```

## Privacy

All learning data is stored locally in `~/.claude/learning/`
- No data sent to external services
- User controls retention
- Can be cleared anytime: `rm -rf ~/.claude/learning`

