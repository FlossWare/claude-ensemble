# Consensus Pattern Integration

**Status:** DEPLOYED (2026-07-03)  
**Database:** `learning.reasoning_patterns` (PostgreSQL, aio-01:5433)  
**Patterns:** 20 categories, 85% average confidence, multi-model validated

## Quick Start

### 1. Direct Pattern Retrieval

```javascript
const { getConsensusPatterns } = require('./shared/consensus-pattern-adapter.cjs');

const db = getConsensusPatterns();

// Get pattern by category
const debugPattern = await db.getPatternByCategory('debugging', 0.7);
console.log(debugPattern.successful_approach);

// Get top patterns
const topPatterns = await db.getTopPatterns(5, 0.8);
```

### 2. Auto-Augment Workflow Tasks

```javascript
const { enhanceWorkflowWithPatterns } = require('./shared/pattern-enhanced-workflow.cjs');

// Wrap your workflow
export default enhanceWorkflowWithPatterns(async ({ agent, parallel, log }) => {
  // Agent calls automatically enhanced with relevant patterns
  const result = await agent('Debug memory leak in connection pool');
  
  // Parallel tasks automatically enhanced
  const results = await parallel([
    'Optimize slow database query',
    'Design scalable architecture',
    'Refactor complex code'
  ]);
  
  return result;
}, {
  enablePatterns: true,
  minConfidence: 0.7,
  maxPatterns: 2
});
```

### 3. Manual Task Augmentation

```javascript
const { getConsensusPatterns } = require('./shared/consensus-pattern-adapter.cjs');

const db = getConsensusPatterns();
const taskDescription = 'Debug why the application crashes after 1000 requests';

// Auto-detect categories and augment
const enhancedTask = await db.augmentTaskWithPatterns(taskDescription, 0.7, 2);
// enhancedTask now includes proven debugging approaches
```

### 4. Pattern Suggestions (Debugging Helper)

```javascript
const { getPatternSuggestions } = require('./shared/pattern-enhanced-workflow.cjs');

const suggestions = await getPatternSuggestions(
  'Optimize database query that takes 30 seconds',
  { maxPatterns: 3 }
);

suggestions.forEach(s => {
  console.log(`${s.category}: ${s.approach}`);
});
```

## Available Pattern Categories

**20 Categories** (from multi-model consensus):

1. **abstraction** - Generalization and modeling
2. **analogy** - Comparative reasoning
3. **causal-reasoning** - Cause-effect analysis
4. **code-complexity** - Simplification and refactoring
5. **constraint-satisfaction** - Requirement handling
6. **counterfactual** - Alternative scenarios
7. **debugging** - Error detection and fixing
8. **ethical-reasoning** - Moral considerations
9. **game-theory** - Strategic decision-making
10. **inference** - Drawing conclusions from evidence
11. **induction** - Pattern generalization
12. **language-ambiguity** - Interpretation clarification
13. **logical-deduction** - Formal reasoning
14. **mathematical-proof** - Rigorous demonstration
15. **multi-step-planning** - Sequential strategy
16. **optimization** - Performance improvement
17. **paradox-resolution** - Contradiction handling
18. **probability** - Uncertainty reasoning
19. **recursive-thinking** - Self-referential problems
20. **system-design** - Architecture planning

## Auto-Detection Heuristics

The system automatically detects pattern categories from task descriptions:

| Category | Trigger Keywords |
|----------|-----------------|
| `debugging` | debug, bug, error, fix, broken, issue |
| `optimization` | optimize, improve, performance, faster, efficient |
| `code-complexity` | complex, simplify, refactor, maintainability |
| `system-design` | architecture, design, system, component, module |
| `multi-step-planning` | plan, strategy, approach, steps, sequence |

See `consensus-pattern-adapter.cjs` line 147 for complete detection rules.

## Pattern Structure

Each pattern contains:

```javascript
{
  id: 1,
  problem_description: "How to debug complex systems",
  problem_category: "debugging",
  consensus_threshold: 0.85,
  models_used: 38,
  successful_approach: "Isolate, reproduce, binary search...",
  common_reasoning_steps: [
    "Step 1: Isolate the problem domain",
    "Step 2: Create minimal reproduction",
    "Step 3: Binary search error location",
    ...
  ],
  error_patterns_to_avoid: [
    "Don't make assumptions without verification",
    "Don't skip logging/instrumentation",
    ...
  ],
  pattern_confidence: 0.85,
  examples: {...},
  created_at: "2026-07-03T..."
}
```

## Workflow Integration Options

### Option 1: Full Workflow Wrapper (Recommended)

Automatically enhances all `agent()` and `parallel()` calls:

```javascript
const { enhanceWorkflowWithPatterns } = require('./shared/pattern-enhanced-workflow.cjs');

export default enhanceWorkflowWithPatterns(async (context) => {
  // All tasks automatically enhanced
}, {
  enablePatterns: true,      // Enable/disable patterns
  minConfidence: 0.7,         // Minimum pattern confidence
  maxPatterns: 2,             // Max patterns per task
  storePatternUsage: true     // Store usage metadata
});
```

### Option 2: Pattern-Aware Agent Wrapper

More control for specific agents:

```javascript
const { createPatternAwareAgent } = require('./shared/pattern-enhanced-workflow.cjs');

const enhancedAgent = createPatternAwareAgent(myAgent, {
  minConfidence: 0.8,
  maxPatterns: 1
});

const result = await enhancedAgent('Debug memory leak');
```

### Option 3: Manual Augmentation

Full control over when and how patterns apply:

```javascript
const { getConsensusPatterns } = require('./shared/consensus-pattern-adapter.cjs');

const db = getConsensusPatterns();
const patterns = await db.getPatternsForTask(taskDescription, 0.7, 3);

if (patterns.length > 0) {
  const enhancedTask = await db.augmentTaskWithPatterns(taskDescription);
  // Use enhancedTask
}
```

## Disabling Patterns for Specific Calls

Even with workflow wrapper enabled, you can disable for specific calls:

```javascript
const result = await agent('Task description', {
  disablePatterns: true  // Skip pattern injection for this call
});
```

## Pattern Usage Metadata

When `storePatternUsage: true`, workflow metadata includes:

```javascript
{
  pattern_usage: {
    patterns_applied: 6,
    categories: ['debugging', 'optimization', 'system-design'],
    avg_confidence: 0.84
  }
}
```

Access during workflow:

```javascript
export default enhanceWorkflowWithPatterns(async ({ patternStats }) => {
  // Do work...
  
  console.log(`Applied ${patternStats.patternsApplied} patterns`);
  console.log(`Categories: ${patternStats.categoriesDetected.join(', ')}`);
});
```

## Database Queries

Direct SQL access for custom queries:

```javascript
const { getConsensusPatterns } = require('./shared/consensus-pattern-adapter.cjs');
const db = getConsensusPatterns();

// Custom query
const result = await db.pool.query(`
  SELECT * FROM learning.reasoning_patterns
  WHERE pattern_confidence >= 0.9 AND models_used >= 30
  ORDER BY pattern_confidence DESC
`);
```

## Statistics and Monitoring

```javascript
const db = getConsensusPatterns();

// Get database statistics
const stats = await db.getStats();
console.log(`${stats.total_patterns} patterns, ${stats.avg_confidence} avg confidence`);

// Get all categories
const categories = await db.getCategories();
console.log(`Available: ${categories.join(', ')}`);
```

## Examples

Run the complete example suite:

```bash
node shared/pattern-integration-example.cjs
```

Examples demonstrate:
- Direct pattern retrieval
- Auto-detection and task augmentation
- Pattern suggestions
- Workflow integration (simulated)
- Pattern formatting
- Category exploration

## Performance

- **Pattern retrieval:** ~1ms (PostgreSQL indexed queries)
- **Category auto-detection:** ~0.1ms (keyword matching)
- **Task augmentation:** ~2ms (includes retrieval + formatting)
- **Embedding generation:** N/A (patterns use category matching, not embeddings)

## Best Practices

1. **Use workflow wrapper for consistency** - Automatic pattern application across all tasks
2. **Set minimum confidence ≥0.7** - Ensures patterns validated by majority consensus
3. **Limit to 2-3 patterns per task** - Avoid overwhelming context
4. **Monitor pattern stats** - Check `patternStats` to verify patterns applied
5. **Disable for trivial tasks** - Use `disablePatterns: true` for simple queries

## Data Source

Patterns extracted from:
- **38-model democratic consensus** (June 2026)
- **18 Ollama models** + **20 cloud FREE APIs**
- **64 total patterns extracted** → 20 highest-confidence retained
- **Categories validated** by multi-provider agreement

## Files

- `shared/consensus-pattern-adapter.cjs` - Database adapter
- `shared/pattern-enhanced-workflow.cjs` - Workflow wrapper
- `shared/pattern-integration-example.cjs` - Examples
- `docs/CONSENSUS_PATTERNS_INTEGRATION.md` - This file

## Database Schema

```sql
CREATE TABLE learning.reasoning_patterns (
  id SERIAL PRIMARY KEY,
  problem_description TEXT NOT NULL,
  problem_category VARCHAR(100) NOT NULL,
  consensus_threshold NUMERIC(3,2) NOT NULL,
  models_used INTEGER NOT NULL,
  successful_approach TEXT NOT NULL,
  common_reasoning_steps JSONB NOT NULL,
  error_patterns_to_avoid JSONB NOT NULL,
  pattern_confidence NUMERIC(3,2) NOT NULL,
  examples JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reasoning_patterns_category ON learning.reasoning_patterns(problem_category);
CREATE INDEX idx_reasoning_patterns_confidence ON learning.reasoning_patterns(pattern_confidence DESC);
```

## Future Enhancements

Potential improvements:

1. **Embedding-based similarity** - Match patterns by semantic similarity (not just category keywords)
2. **Pattern validation tracking** - Monitor which patterns improve task outcomes
3. **Dynamic confidence adjustment** - Update confidence based on real-world performance
4. **Pattern versioning** - Track pattern evolution over time
5. **User-specific patterns** - Personalized patterns from user's workflow history

## Troubleshooting

**No patterns found:**
- Check `db.getCategories()` to see available categories
- Lower `minConfidence` threshold (e.g., 0.5)
- Use `db.getTopPatterns()` as fallback

**Patterns not applying:**
- Verify `enablePatterns: true` in wrapper options
- Check `patternStats` after workflow completes
- Ensure task descriptions are descriptive (not single words)

**Database connection errors:**
- Verify PostgreSQL accessible: `psql -h aio-01 -p 5433 -U sfloess -d learning`
- Check environment: `PGHOST=aio-01 PGPORT=5433 PGDATABASE=learning`

## Support

For issues or questions:
- Check examples: `node shared/pattern-integration-example.cjs`
- Review code: `shared/consensus-pattern-adapter.cjs`
- Inspect database: `psql -h aio-01 -p 5433 -U sfloess -d learning`
