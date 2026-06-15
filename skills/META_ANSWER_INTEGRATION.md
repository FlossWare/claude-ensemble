# Meta-Answer Skill - Claude Code Integration Guide

This document explains how to integrate the `/meta-answer` skill into Claude Code's skill system to enable full agent spawning with the meta-learning loop.

## Files Created

1. **meta-answer.md** - User-facing documentation
2. **meta-answer.sh** - Shell script launcher (shows workflow, delegates to Claude Code)
3. **meta-answer.js** - Complete JavaScript implementation with learning loop
4. **META_ANSWER_INTEGRATION.md** - This integration guide

## How It Works

The `/meta-answer` skill implements the complete meta-learning loop:

```
User Question
     ↓
Thompson Sampling Model Selection (orchestrator.selectModel)
     ↓
Agent Execution with Selected Model
     ↓
Log to Learning Database (learning-logger.logExecution)
     ↓
Update Thompson Sampling State (orchestrator.recordResult)
     ↓
Return Answer to User
```

## Implementation Details

### 1. Model Selection (Thompson Sampling)

```javascript
import { selectModel } from '../orchestrator.js';

const model = await selectModel('meta-answer', {
  strategy: 'thompson',
  count: 1
});
// => 'sonnet' (or 'opus', 'haiku', 'fable', etc.)
```

Thompson Sampling:
- Maintains Beta(alpha, beta) distribution for each model
- Alpha = successes (quality_score >= 0.7)
- Beta = failures (quality_score < 0.7)
- Samples from each distribution, picks highest sample
- Balances exploration (uncertain models) vs exploitation (proven models)

### 2. Agent Execution

In Claude Code, this would use the Agent tool:

```javascript
// Pseudo-code for Claude Code integration
const agent = await Agent.spawn({
  model: model,
  description: 'Meta-answer with Thompson Sampling',
  prompt: userQuestion,
});

const answer = agent.response;
```

The current JavaScript implementation has a placeholder `executeWithModel()` function that simulates this. Replace it with actual Agent spawning in the Claude Code skill handler.

### 3. Learning Database Logging

```javascript
import { logExecution } from '../shared/learning-logger.js';

const executionId = logExecution({
  run_id: randomUUID(),
  model: selectedModel,
  model_role: 'worker',
  workflow: 'meta-answer',
  task_type: 'meta-answer',
  quality_score: 0.8, // Default, can be adjusted
  confidence: 0.85,
  input_tokens: estimateTokens(question),
  output_tokens: estimateTokens(answer),
  cost_usd: estimateCost(model, question, answer),
  duration_ms: durationMs,
  outcome: 'success',
});
```

Logged to: `~/.claude/learning/db/learning.db`

### 4. Thompson Sampling State Update

```javascript
import { recordResult } from '../orchestrator.js';

const updatedState = recordResult(selectedModel, qualityScore);
// => { alpha: 19, beta: 1, total: 18, avg_quality: 0.823 }
```

State persisted to: `~/.claude/learning/bandit-state.json`

## Claude Code Skill Handler Integration

To integrate with Claude Code's skill system, the skill handler should:

1. **Parse the user's question** from skill arguments
2. **Call the meta-answer workflow**:
   ```javascript
   import metaAnswer from './skills/meta-answer.js';
   
   const result = await metaAnswer(userQuestion, {
     qualityScore: 0.8, // Or adjust based on user feedback
     debug: false
   });
   ```
3. **Replace the placeholder `executeWithModel()` function** with actual Agent spawning
4. **Return the result** to the user

### Modified executeWithModel Function

Replace the placeholder in `meta-answer.js` with:

```javascript
async function executeWithModel(model, question, options = {}) {
  const { debug = false } = options;

  if (debug) {
    console.log(`[meta-answer] Executing with model: ${model}`);
    console.log(`[meta-answer] Question: ${question}`);
  }

  // Spawn agent with selected model via Claude Code's Agent tool
  const agent = await Agent.spawn({
    model: model,
    description: 'Meta-answer with Thompson Sampling',
    prompt: question,
  });

  return agent.response;
}
```

## Quality Score Adjustment

The default quality score is 0.8 (good quality). The user can provide feedback to adjust:

- **1.0** - Perfect answer
- **0.9** - Excellent answer
- **0.8** - Good answer (default)
- **0.7** - Acceptable answer (threshold)
- **0.5** - Mediocre answer
- **0.3** - Poor answer
- **0.0** - Completely wrong

To allow user feedback:

```javascript
// After showing the answer, ask for feedback (optional)
const feedback = await getUserFeedback(); // Implementation depends on UI

const adjustedQualityScore = mapFeedbackToQuality(feedback);

// Re-log with adjusted score if feedback provided
if (adjustedQualityScore !== DEFAULT_QUALITY_SCORE) {
  recordResult(selectedModel, adjustedQualityScore);
}
```

## Testing

### Test Model Selection

```bash
node -e "
import { selectModel } from './orchestrator.js';
const model = await selectModel('meta-answer', { strategy: 'thompson' });
console.log('Selected:', model);
"
```

### Test Full Workflow

```bash
node skills/meta-answer.js "How do I implement retry logic?"
```

Expected output:
- Model selection via Thompson Sampling
- Simulated agent execution (placeholder)
- Database logging
- Thompson state update
- Learning statistics

### Test Thompson Stats

```bash
node -e "
import { getThompsonStats } from './orchestrator.js';
const stats = getThompsonStats();
console.log(JSON.stringify(stats, null, 2));
"
```

## Dependencies

All dependencies are already in place:

- **orchestrator.js** - Model selection with Thompson Sampling
- **learning/thompson-sampling.js** - Thompson Sampling implementation
- **shared/learning-logger.js** - Learning database logging
- **better-sqlite3** - Database driver (already installed)

## Database Schema

The learning database (`~/.claude/learning/db/learning.db`) has the following relevant tables:

- **execution_log** - All executions (model, quality_score, etc.)
- **model_tuning** - Aggregated model performance metrics
- **model_combinations** - Multi-model combination performance

The background learner (`background-learner.js`) processes this data to update tuning tables.

## Thompson Sampling State

Persisted to `~/.claude/learning/bandit-state.json`:

```json
{
  "version": 1,
  "updated": "2026-06-13T14:34:56.789Z",
  "models": {
    "opus": { "alpha": 32, "beta": 69, "total": 101, "avg_quality": 0.52 },
    "sonnet": { "alpha": 19, "beta": 1, "total": 18, "avg_quality": 0.82 },
    "haiku": { "alpha": 299, "beta": 702, "total": 1001, "avg_quality": 0.50 },
    "fable": { "alpha": 9, "beta": 2, "total": 9, "avg_quality": 0.73 }
  }
}
```

## Usage Examples

### Basic Usage

```bash
/meta-answer How do I implement retry logic with exponential backoff?
```

### With Quality Feedback

```bash
/meta-answer What's the best way to handle async errors in JavaScript?

# After seeing the answer:
# - If perfect: system adjusts quality to 1.0
# - If poor: system adjusts quality to 0.3
# - Otherwise: uses default 0.8
```

### View Learning Stats

```bash
# View Thompson Sampling statistics
node -e "import { getThompsonStats } from './orchestrator.js'; console.log(JSON.stringify(getThompsonStats(), null, 2));"

# View recent executions
node -e "import { getRecentExecutions } from './shared/learning-logger.js'; console.log(JSON.stringify(getRecentExecutions(10), null, 2));"
```

## Comparison with Other Skills

### /meta-answer vs /ai-prompt

| Feature | /meta-answer | /ai-prompt |
|---------|--------------|------------|
| Models | 1 (Thompson Sampling) | 3+ (Consensus) |
| Speed | Fast | Slower |
| Cost | Low | Higher |
| Learning | Yes (Thompson) | Yes (Database) |
| Use Case | Routine questions | Critical decisions |

### /meta-answer vs /ai-consensus

| Feature | /meta-answer | /ai-consensus |
|---------|--------------|---------------|
| Selection | Thompson Sampling | Fixed workers |
| Adaptation | Learns over time | Static |
| Arbiter | No (single model) | Yes |
| Consensus | No | Yes |

## Future Enhancements

1. **User Feedback Integration** - Allow users to rate answers and adjust quality scores
2. **Task-Specific Models** - Maintain separate Thompson states per task type
3. **Context-Aware Selection** - Consider question complexity, domain, etc.
4. **Multi-Model Fallback** - If Thompson model fails, try next-best model
5. **Cost Constraints** - Prefer cheaper models when budget-constrained
6. **Confidence Calibration** - Use confidence scores from agents to adjust quality

## Troubleshooting

### Model Selection Always Returns Same Model

- Check Thompson state: `cat ~/.claude/learning/bandit-state.json`
- If one model has very high alpha/beta ratio, it will be selected often
- Reset state if needed: `rm ~/.claude/learning/bandit-state.json`

### Database Logging Fails

- Check DB exists: `ls -la ~/.claude/learning/db/learning.db`
- Check permissions: `ls -la ~/.claude/learning/db/`
- Enable debug: `LEARNING_DEBUG=1 node skills/meta-answer.js "test"`

### Thompson Sampling Not Learning

- Verify `recordResult()` is called after each execution
- Check quality scores are in [0, 1] range
- Verify state file is writable: `ls -la ~/.claude/learning/bandit-state.json`

## Summary

The `/meta-answer` skill is ready for integration into Claude Code. The main integration point is replacing the placeholder `executeWithModel()` function with actual Agent spawning via Claude Code's Agent tool. All other components (Thompson Sampling, database logging, state management) are fully implemented and tested.

---

**Created**: 2026-06-13  
**Version**: 1.0  
**Contact**: See repository maintainers
