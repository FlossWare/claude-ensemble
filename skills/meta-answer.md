# Meta-Answer - Adaptive Model Selection with Learning

Get answers to any question using Thompson Sampling to intelligently select the best AI model based on historical performance. The system learns from each interaction to continuously improve model selection.

## Features

- **Thompson Sampling** - Balances exploration/exploitation to find the best model
- **Adaptive Learning** - Improves selection over time based on quality scores
- **Automatic Logging** - Records results to the learning database
- **Meta-Learning Loop** - Each answer helps the system learn which models excel at which tasks
- **Quality Scoring** - Default 0.8 score, adjustable based on actual quality

## Usage

```bash
# Ask any question
/meta-answer How should I architect this authentication system?

# Technical questions
/meta-answer What's the best way to handle async errors in JavaScript?

# Code review
/meta-answer Is this caching approach optimal?

# Architecture decisions
/meta-answer Should I use microservices or monolith for this project?
```

## How It Works

1. **Model Selection** - Thompson Sampling selects the best model based on historical success rates
2. **Agent Execution** - Spawns an agent with the selected model to answer your question
3. **Answer Delivery** - Returns the model's response to you
4. **Learning** - Records the execution with a quality score (default 0.8)
5. **Adaptation** - Future selections benefit from this learning

## Thompson Sampling

Thompson Sampling is a Bayesian approach to the multi-armed bandit problem:

- Maintains a Beta distribution for each model (alpha=successes, beta=failures)
- Samples from each model's distribution and picks the highest sample
- Naturally balances exploration (trying uncertain models) and exploitation (using proven models)
- Converges to optimal model selection over time

Success is defined as quality_score >= 0.7.

## Quality Scoring

The default quality score is 0.8 (good quality), but you can adjust based on:

- **1.0** - Perfect answer, exactly what you needed
- **0.9** - Excellent answer with minor improvements possible
- **0.8** - Good answer (default)
- **0.7** - Acceptable answer, met basic requirements
- **0.5** - Mediocre answer, significant issues
- **0.3** - Poor answer, mostly wrong
- **0.0** - Completely wrong or unhelpful

## Example

```bash
$ /meta-answer How do I implement retry logic with exponential backoff?

Selecting model via Thompson Sampling...
Selected: sonnet (success_rate=0.85, uncertainty=0.12)

Agent: Running with model 'sonnet'

Answer:
Here's an approach to implement retry logic with exponential backoff:

1. Start with a base delay (e.g., 100ms)
2. On each retry, multiply by a factor (e.g., 2x)
3. Add random jitter to prevent thundering herd
4. Cap maximum delay to avoid infinite waits
5. Limit total retry attempts

[... detailed code example ...]

Logged execution: model=sonnet, quality=0.8, task_type=meta-answer
Thompson Sampling updated: alpha=12, beta=3, success_rate=0.80
```

## Learning Database

All executions are logged to `~/.claude/learning/db/learning.db`:

- Model used
- Task type
- Quality score
- Confidence
- Duration, tokens, cost
- Timestamp

Background learner processes this data to:
- Update Thompson Sampling priors
- Calculate model performance metrics
- Identify optimal model combinations
- Track quality trends over time

## Thompson State

Bandit state persists to `~/.claude/learning/bandit-state.json`:

```json
{
  "version": 1,
  "updated": "2026-06-13T12:34:56.789Z",
  "models": {
    "opus": { "alpha": 15, "beta": 3, "total": 17, "avg_quality": 0.88 },
    "sonnet": { "alpha": 42, "beta": 8, "total": 49, "avg_quality": 0.84 },
    "haiku": { "alpha": 23, "beta": 12, "total": 34, "avg_quality": 0.76 }
  }
}
```

## Comparison: Meta-Answer vs AI-Prompt

**Meta-Answer**:
- Single model selected via Thompson Sampling
- Fast (one model execution)
- Learns and improves over time
- Lower cost
- Best for routine questions

**AI-Prompt** (Multi-Model Consensus):
- Multiple models respond independently
- Arbiter synthesizes consensus
- More comprehensive analysis
- Higher cost (3+ models)
- Best for critical decisions requiring multiple perspectives

## Use Cases

- **Routine Questions** - Quick answers with intelligent model selection
- **Learning Systems** - Build systems that improve over time
- **Cost Optimization** - Avoid expensive multi-model consensus when not needed
- **Performance Tracking** - See which models excel at which tasks
- **Adaptive Workflows** - Workflows that automatically optimize model selection

## Benefits

**Over Fixed Model**:
- Adapts to model performance changes
- Discovers best model for each task type
- Balances exploration and exploitation

**Over Random Selection**:
- Converges to optimal model
- Uses historical performance data
- Continuously improves

**Over Always-Opus**:
- Lower cost for tasks where cheaper models excel
- Still uses Opus when quality data suggests it's best
- Data-driven instead of assumption-based

## Files

- `~/.claude/skills/meta-answer.md` (this file)
- `~/.claude/skills/meta-answer.sh` (skill launcher)
- `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/orchestrator.js`
- `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/thompson-sampling.js`
- `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/learning-logger.js`

## Related Skills

- `/ai-prompt` - Multi-model consensus for complex decisions
- `/ai-consensus` - Multi-AI consensus with arbiter synthesis
- `/workflow-status` - View learning database statistics

---

**Version**: 1.0  
**Created**: 2026-06-13  
**Global**: Meta-learning adaptive model selection
