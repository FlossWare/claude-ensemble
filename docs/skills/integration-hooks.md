# Active Learning Integration - How to Use

This guide shows how to integrate active learning into Claude's main decision loop and orchestrator.

## System Overview

The active learning system consists of three layers:

1. **claude-learning-integration.js** - Core intelligence functions for main loop
2. **orchestrator-brain.js** - Intelligent coordination for complex tasks
3. **learning/db.js + learning/thompson-sampling.js** - Data persistence and exploration/exploitation

## Integration Points

### 1. Before Making Decisions - Consult Learnings

**When:** Before choosing models, strategies, or spawning agents

**How:**
```javascript
import { consultLearnings } from './claude-learning-integration.js';

// Get guidance based on historical performance
const guidance = await consultLearnings('code-review');

console.log(guidance.best_models);      // ['opus', 'sonnet', 'haiku']
console.log(guidance.best_strategies);  // [{ strategy: 'consensus', avg_quality: 0.85 }]
console.log(guidance.recommendation);   // "Use opus with consensus strategy"
console.log(guidance.confidence);       // 0.82
```

**What You Get:**
- Best models for this task type (ranked by quality)
- Best strategies that worked historically
- Common failure patterns to avoid
- Optimal parameters from past successes
- Confidence score based on sample size

### 2. Model Selection - Use Thompson Sampling

**When:** Choosing which AI model(s) to use

**How:**
```javascript
import { selectModelIntelligently } from './claude-learning-integration.js';

// Single model with Thompson Sampling (balances exploration/exploitation)
const model = await selectModelIntelligently('code-review', {
  useThompson: true,
  count: 1
});
// => 'opus' (might explore 'fable' if uncertain)

// Multiple models for consensus
const workers = await selectModelIntelligently('security-review', {
  useThompson: true,
  count: 4
});
// => ['opus', 'gemini', 'sonnet', 'haiku']
```

**Why Thompson Sampling:**
- Automatically explores uncertain models
- Exploits known good performers
- Gets smarter over time
- No manual tuning needed

### 3. Knowledge Base Search - Access Past Learnings

**When:** User asks questions that might have been answered before

**How:**
```javascript
import { searchKnowledgeBases } from './claude-learning-integration.js';

const knowledge = await searchKnowledgeBases('How to handle async patterns?', {
  limit: 5,
  minConfidence: 0.6
});

console.log(knowledge.disseminator);   // Findings from disseminator project
console.log(knowledge.web_synthesis);  // Findings from web research
console.log(knowledge.total_found);    // Total relevant items
```

**What Gets Searched:**
- `~/.claude/learning/disseminator-knowledge.jsonl` (166 items)
- `~/.claude/learning/research/web-synthesis-*.jsonl` (344 findings)
- Future: PDF learnings, meta-learnings

### 4. Orchestrator Delegation - When to Coordinate

**When:** Deciding whether to handle task directly or delegate to orchestrator

**How:**
```javascript
import { shouldUseOrchestrator } from './claude-learning-integration.js';

const decision = await shouldUseOrchestrator({
  type: 'security-review',
  complexity: 0.8,
  multiDomain: true,
  modelCount: 5
});

if (decision.use_orchestrator) {
  console.log(decision.reasons);  // ['Needs 5 models', 'High complexity: 0.80']
  // Delegate to orchestrator-brain.js
} else {
  // Handle directly
}
```

**Orchestrator Triggers:**
- Needs 3+ models
- Complexity score ≥ 0.7
- Multi-domain task
- Historical success rate < 30%

### 5. Record Outcomes - Feed the Learning Loop

**When:** After every decision/execution

**How:**
```javascript
import { recordDecision } from './claude-learning-integration.js';

await recordDecision({
  task_type: 'code-review',
  model_used: 'opus',
  decision: 'Used multi-AI consensus with 4 workers',
  outcome: 'success',
  quality_score: 0.92,
  metadata: {
    workers: ['opus', 'sonnet', 'haiku', 'fable'],
    arbiter: 'gemini',
    consensus_score: 0.87,
    selected_via_thompson: true
  }
});
```

**What Happens:**
1. Logs to `~/.claude/learning/decisions.jsonl`
2. Records to `learning.db` for analytics
3. Updates Thompson Sampling bandits
4. Feeds future `consultLearnings()` calls

## Orchestrator Brain Usage

For complex coordination tasks, use the orchestrator brain:

### Analyze Task Complexity

```javascript
import { analyzeTaskComplexity } from './orchestrator-brain.js';

const analysis = await analyzeTaskComplexity({
  type: 'multi-domain-security-review',
  description: 'Review security across frontend, backend, and infrastructure',
  subtasks: ['frontend-review', 'backend-review', 'infra-review'],
  domains: ['security', 'architecture', 'testing'],
  quality_requirement: 0.9,
  time_pressure: 0.3
});

console.log(analysis.complexity_score);      // 0.78
console.log(analysis.complexity_level);      // 'high'
console.log(analysis.estimated_models);      // 4
console.log(analysis.estimated_duration_ms); // 120000
console.log(analysis.recommendation);        // 'hierarchical'
```

### Select Agent Strategy

```javascript
import { selectAgentStrategy } from './orchestrator-brain.js';

const strategy = await selectAgentStrategy(task, analysis);

console.log(strategy.strategy);        // 'hierarchical'
console.log(strategy.worker_models);   // ['opus', 'sonnet', 'haiku', 'fable', 'gemini', 'gpt-4o']
console.log(strategy.arbiter_model);   // 'fable'
console.log(strategy.confidence);      // 0.85
console.log(strategy.reasoning);       // 'Multi-domain task → specialized sub-teams'
```

**Available Strategies:**
- `single-agent` - Simple tasks
- `parallel-workers` - Independent subtasks
- `pipeline` - Sequential stages
- `consensus` - Multi-AI agreement
- `hierarchical` - Specialized sub-teams
- `debate` - Adversarial validation

### Coordinate Task Execution

```javascript
import { coordinateTask } from './orchestrator-brain.js';

const result = await coordinateTask(task, strategy);

console.log(result.success);              // true
console.log(result.coordination_id);      // 'uuid'
console.log(result.result.quality_score); // 0.88
console.log(result.duration_ms);          // 115000
```

### Learn from Coordination

```javascript
import { learnFromCoordination } from './orchestrator-brain.js';

const learning = await learnFromCoordination(result);

console.log(learning.learning_id);  // 'uuid'
console.log(learning.insight);      // 'Excellent result with hierarchical strategy'
```

## Example: Full Integration Flow

```javascript
import {
  consultLearnings,
  selectModelIntelligently,
  searchKnowledgeBases,
  shouldUseOrchestrator,
  recordDecision
} from './claude-learning-integration.js';

import {
  analyzeTaskComplexity,
  selectAgentStrategy,
  coordinateTask,
  learnFromCoordination
} from './orchestrator-brain.js';

async function handleTask(task) {
  // 1. Consult learnings
  const guidance = await consultLearnings(task.type);
  console.log(`Historical guidance: ${guidance.recommendation}`);

  // 2. Search knowledge bases if question
  if (task.isQuestion) {
    const knowledge = await searchKnowledgeBases(task.query);
    if (knowledge.total_found > 0) {
      console.log(`Found ${knowledge.total_found} relevant past learnings`);
      // Use knowledge to inform answer
    }
  }

  // 3. Decide coordination approach
  const orchestratorDecision = await shouldUseOrchestrator({
    type: task.type,
    complexity: task.complexity || 0.5,
    multiDomain: task.domains && task.domains.length > 1,
    modelCount: task.requiresMultiAI ? 4 : 1
  });

  let result;
  
  if (orchestratorDecision.use_orchestrator) {
    console.log(`Delegating to orchestrator: ${orchestratorDecision.reasons.join(', ')}`);
    
    // 4. Use orchestrator brain
    const analysis = await analyzeTaskComplexity(task);
    const strategy = await selectAgentStrategy(task, analysis);
    
    result = await coordinateTask(task, strategy);
    await learnFromCoordination(result);
    
  } else {
    console.log('Handling directly');
    
    // 5. Select model intelligently
    const model = await selectModelIntelligently(task.type, {
      useThompson: true,
      count: 1
    });
    
    // 6. Execute task
    result = await executeTask(task, model);
  }

  // 7. Record decision
  await recordDecision({
    task_type: task.type,
    model_used: result.model,
    decision: orchestratorDecision.use_orchestrator ? 'Delegated to orchestrator' : 'Handled directly',
    outcome: result.success ? 'success' : 'failure',
    quality_score: result.quality_score || 0.5,
    metadata: {
      used_orchestrator: orchestratorDecision.use_orchestrator,
      strategy: result.strategy,
      selected_via_thompson: true
    }
  });

  return result;
}
```

## State Files

The system maintains several state files:

### Learning Database
- **Path:** `~/.claude/learning/db/learning.db`
- **Purpose:** Main metrics, performance data, quality ratings
- **Schema:** execution_log, model_performance, parameter_tuning, quality_ratings

### Thompson Sampling State
- **Path:** `~/.claude/learning/bandit-state.json`
- **Purpose:** Beta distributions for each model (exploration/exploitation)
- **Format:** `{ models: { opus: { alpha: 42, beta: 8, ... }, ... } }`

### Decisions Log
- **Path:** `~/.claude/learning/decisions.jsonl`
- **Purpose:** Every decision made by main loop
- **Format:** One JSON object per line

### Orchestrator Decisions
- **Path:** `~/.claude/learning/orchestrator-decisions.jsonl`
- **Purpose:** Every coordination decision made by orchestrator
- **Format:** One JSON object per line

### Orchestrator Learnings
- **Path:** `~/.claude/learning/orchestrator-learnings.jsonl`
- **Purpose:** Insights extracted from coordination outcomes
- **Format:** One JSON object per line

### Knowledge Bases
- **Path:** `~/.claude/learning/disseminator-knowledge.jsonl` (166 items)
- **Path:** `~/.claude/learning/research/web-synthesis-*.jsonl` (344 items)
- **Purpose:** Past learnings from projects and web research

## Monitoring Intelligence

Check how smart the system is getting:

```javascript
import { getDecisionSummary } from './claude-learning-integration.js';
import { getIntelligenceSummary } from './orchestrator-brain.js';

// Main loop intelligence
const decisions = await getDecisionSummary({ limit: 100 });
console.log(`Success rate: ${(decisions.success_rate * 100).toFixed(1)}%`);
console.log(`Avg quality: ${decisions.avg_quality.toFixed(2)}`);

// Orchestrator intelligence
const intelligence = await getIntelligenceSummary();
console.log(`Models tracked: ${intelligence.thompson_sampling.models_tracked}`);
console.log(`Learnings: ${intelligence.learnings.total} (${intelligence.learnings.success_patterns} success patterns)`);
```

## Best Practices

1. **Always consult learnings before decisions** - Even if you ignore the guidance, it's free intelligence
2. **Use Thompson Sampling by default** - It automatically balances exploration/exploitation
3. **Record every outcome** - More data = smarter system
4. **Search knowledge bases for questions** - Avoid re-discovering what we already know
5. **Delegate complex tasks to orchestrator** - It's designed for coordination
6. **Monitor intelligence summary regularly** - See if the system is learning

## What's Different Now

**BEFORE:**
- Claude picks models based on... vibes?
- No memory of what worked before
- Same mistakes repeated
- Manual model selection
- Orchestrator just passes messages

**AFTER:**
- Claude consults historical performance
- Thompson Sampling explores + exploits
- Knowledge bases searched automatically
- Decisions recorded and learned from
- Orchestrator makes intelligent coordination decisions
- System gets smarter over time

## Migration Path

To integrate into existing workflows:

1. **Add consultation phase** before model selection
2. **Replace hardcoded model selection** with `selectModelIntelligently()`
3. **Add knowledge base search** for question-answering tasks
4. **Check orchestrator delegation** for complex tasks
5. **Record outcomes** after execution

The system gracefully degrades - if data is missing, it falls back to sensible defaults.
