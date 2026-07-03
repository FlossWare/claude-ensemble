# Consensus Patterns - Quick Start

Copy-paste integration code for immediate use.

---

## 1. Auto-Enhanced Workflow (Recommended)

```javascript
const { enhanceWorkflowWithPatterns } = require('./shared/pattern-enhanced-workflow.cjs');
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.cjs');

export default enhanceWorkflowWithPatterns(async ({ phase, parallel, agent, patternStats }) => {
  const db = getWorkflowStorage();
  const workflowId = 'wf-' + Date.now();
  
  // Store workflow start
  const execId = await db.storeExecution({
    workflow_id: workflowId,
    workflow_name: 'your-workflow-name',
    task_description: 'Your task description',
    total_workers: 6,
    total_duration_ms: 0, // Update at end
    outcome: 'success'
  });
  
  try {
    // Phase 1: Analysis (patterns auto-applied to all tasks)
    await phase('Analysis', async () => {
      const workers = await parallel([
        'Debug performance bottleneck in API endpoint',
        'Optimize database query that takes 30 seconds',
        'Refactor complex authentication logic'
      ]);
      
      // Store worker results
      for (let i = 0; i < workers.length; i++) {
        await db.storeWorkerResult({
          workflow_execution_id: execId,
          worker_id: `worker-${i}`,
          model: 'opus', // or actual model used
          task_assigned: workers[i].task || 'unknown',
          result: workers[i].result || '',
          confidence: 0.85,
          duration_ms: 5000,
          input_tokens: 1500,
          output_tokens: 800,
          cost_usd: 0.05,
          outcome: 'success'
        });
      }
    });
    
    // Phase 2: Synthesis
    await phase('Synthesis', async () => {
      const arbiter = await agent('Synthesize the analysis results into actionable recommendations');
      
      await db.storeArbiterDecision({
        workflow_execution_id: execId,
        arbiter_model: 'opus',
        worker_result_ids: [], // Worker result IDs
        decision: arbiter.output || '',
        reasoning: 'Multi-model consensus',
        confidence: 0.90,
        duration_ms: 3000,
        input_tokens: 2000,
        output_tokens: 500,
        cost_usd: 0.03
      });
    });
    
    // Log pattern usage
    console.log(`\n✓ Workflow complete`);
    console.log(`  Patterns applied: ${patternStats.patternsApplied}`);
    console.log(`  Categories: ${[...new Set(patternStats.categoriesDetected)].join(', ')}`);
    
    return { success: true, workflowId, execId };
    
  } catch (error) {
    await db.pool.query(
      `UPDATE workflow.executions SET outcome = 'error' WHERE id = $1`,
      [execId]
    );
    throw error;
  }
}, {
  enablePatterns: true,      // Enable pattern injection
  minConfidence: 0.7,         // Minimum 70% consensus
  maxPatterns: 2,             // Max 2 patterns per task
  storePatternUsage: true     // Store usage metadata
});
```

---

## 2. Manual Pattern Application

```javascript
const { getConsensusPatterns } = require('./shared/consensus-pattern-adapter.cjs');
const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.cjs');

export default async function({ agent, parallel }) {
  const patternDB = getConsensusPatterns();
  const workflowDB = getWorkflowStorage();
  
  // Get patterns for specific task
  const taskDescription = 'Debug why the application crashes after 1000 requests';
  const patterns = await patternDB.getPatternsForTask(taskDescription, 0.7, 3);
  
  console.log(`Found ${patterns.length} relevant patterns:`);
  patterns.forEach(p => {
    console.log(`- ${p.problem_category}: ${Math.round(p.pattern_confidence * 100)}% (${p.models_used} models)`);
  });
  
  // Augment task with patterns
  const enhancedTask = await patternDB.augmentTaskWithPatterns(taskDescription, 0.7, 2);
  
  // Execute with enhanced task
  const result = await agent(enhancedTask);
  
  return result;
}
```

---

## 3. Pattern Preview (No Execution)

```javascript
const { getPatternSuggestions } = require('./shared/pattern-enhanced-workflow.cjs');

// Preview patterns before committing to workflow
const suggestions = await getPatternSuggestions(
  'Optimize slow database query',
  { minConfidence: 0.8, maxPatterns: 3 }
);

console.log('Pattern Suggestions:\n');
suggestions.forEach((s, i) => {
  console.log(`${i + 1}. ${s.category} (${Math.round(s.confidence * 100)}%, ${s.models_used} models)`);
  console.log(`   Approach: ${s.approach}`);
  console.log(`   Steps: ${s.steps.length} reasoning steps`);
  console.log(`   Avoid: ${s.avoid.length} common errors\n`);
});
```

---

## 4. Direct Database Queries

```javascript
const { getConsensusPatterns } = require('./shared/consensus-pattern-adapter.cjs');

const db = getConsensusPatterns();

// Get pattern by category
const debugPattern = await db.getPatternByCategory('debugging', 0.7);

// Get top N patterns
const topPatterns = await db.getTopPatterns(10, 0.8);

// Get multiple categories
const patterns = await db.getPatternsByCategories(['debugging', 'optimization', 'refactoring'], 0.7);

// Get all categories
const categories = await db.getCategories();

// Get stats
const stats = await db.getStats();
console.log(`${stats.total_patterns} patterns, ${stats.avg_confidence} avg confidence`);

// Format pattern for display
const formatted = db.formatPatternContext(debugPattern);
console.log(formatted);
```

---

## 5. Disable Patterns for Specific Calls

```javascript
const { enhanceWorkflowWithPatterns } = require('./shared/pattern-enhanced-workflow.cjs');

export default enhanceWorkflowWithPatterns(async ({ agent, parallel }) => {
  // This task gets patterns
  const result1 = await agent('Debug complex system issue');
  
  // This task SKIPS patterns (disablePatterns flag)
  const result2 = await agent('Simple task: return current timestamp', {
    disablePatterns: true
  });
  
  return { result1, result2 };
});
```

---

## 6. Pattern-Aware Agent Wrapper

```javascript
const { createPatternAwareAgent } = require('./shared/pattern-enhanced-workflow.cjs');

// Create enhanced agent function
const myAgent = async (task, options) => {
  // Your agent implementation
  return await callLLM(task, options);
};

const enhancedAgent = createPatternAwareAgent(myAgent, {
  minConfidence: 0.8,
  maxPatterns: 1
});

// Use enhanced agent
const result = await enhancedAgent('Debug memory leak');
```

---

## 7. Custom Query (Advanced)

```javascript
const { getConsensusPatterns } = require('./shared/consensus-pattern-adapter.cjs');

const db = getConsensusPatterns();

// Direct SQL for custom queries
const result = await db.pool.query(`
  SELECT 
    problem_category,
    pattern_confidence,
    models_used,
    successful_approach
  FROM learning.reasoning_patterns
  WHERE pattern_confidence >= 0.9 AND models_used >= 30
  ORDER BY pattern_confidence DESC
  LIMIT 5
`);

console.log('Highest confidence patterns:');
result.rows.forEach(row => {
  console.log(`${row.problem_category}: ${row.pattern_confidence} (${row.models_used} models)`);
});
```

---

## Test Your Integration

```bash
# Validate deployment
node shared/test-pattern-integration.cjs

# Run examples
node shared/pattern-integration-example.cjs

# Check database
psql -h aio-01 -p 5433 -U sfloess -d learning -c \
  "SELECT problem_category, pattern_confidence, models_used FROM learning.reasoning_patterns ORDER BY pattern_confidence DESC"
```

---

## Available Categories

Use these category names with `getPatternByCategory()`:

- abstraction
- analogy
- causal-reasoning
- code-complexity
- constraint-satisfaction
- counterfactual
- debugging
- ethical-reasoning
- game-theory
- inference
- induction
- language-ambiguity
- logical-deduction
- mathematical-proof
- multi-step-planning
- optimization
- paradox-resolution
- probability
- recursive-thinking
- system-design

---

## Complete Documentation

See `docs/CONSENSUS_PATTERNS_INTEGRATION.md` for full API reference, best practices, and troubleshooting.
