# Quick Integration Guide

## For Workflow Authors

### Calling ai-extract-learning from Your Workflow

```javascript
// At the end of your workflow
const learningResult = await workflow('ai-extract-learning', {
  run_id: runId,                    // Required: unique run identifier
  workflow_name: 'my-workflow',     // Required: workflow name
  execution_data: {                 // Required: workflow-specific data
    // Include relevant execution details
    issue_number: 42,
    approach: 'fixed bug',
    files_changed: ['src/app.js'],
    consensus_score: 0.85
  },
  execution_id: executionId,        // Optional: link to monitoring.execution_summary
  quality_score: 0.9,               // Optional: quality score
  strategy: 'base',                 // Optional: extraction strategy
  save_to_memory: false             // Optional: save to memory files
});

// learningResult contains:
// - status: 'success' | 'failed'
// - workflow: workflow name
// - learnings: extracted learning object
// - learning_id: database ID
```

### Execution Data by Workflow Type

#### code-solve
```javascript
execution_data: {
  issue_number: 42,
  issue_title: 'Fix null pointer exception',
  fix_approach: 'Added null check before dereference',
  files_changed: ['src/app.js', 'test/app.test.js'],
  consensus_score: 0.85,
  commit_hash: 'abc123'
}
```

#### code-review
```javascript
execution_data: {
  findings_count: 5,
  severity_breakdown: {
    high: 1,
    medium: 2,
    low: 2
  },
  categories: ['null-safety', 'error-handling'],
  effort_level: 'medium'
}
```

#### code-test
```javascript
execution_data: {
  tests_run: 150,
  pass_rate: 95.3,
  failures: [
    { name: 'test_null_handling', reason: 'AssertionError' }
  ],
  build_status: 'passed'
}
```

#### code-security
```javascript
execution_data: {
  vulnerabilities_count: 3,
  max_severity: 'high',
  vuln_categories: ['sql-injection', 'xss'],
  owasp_categories: ['A03:2021', 'A01:2021']
}
```

## Querying Learnings

### From JavaScript

```javascript
const { storage } = require('~/.claude/learning/storage');

// Get learnings by workflow
const learnings = await storage.getLearningsByWorkflow('code-solve', 20);

// Semantic search
const similar = await storage.findSimilarLearnings(
  'null pointer exceptions in Java',
  10,
  {
    workflowName: 'code-solve',
    minQualityScore: 0.7
  }
);

// Recent learnings
const recent = await storage.getRecentLearnings(50);

// Statistics
const stats = await storage.getLearningStats();
console.log(`Total learnings: ${stats.reduce((sum, s) => sum + s.total_learnings, 0)}`);
```

### From SQL

```sql
-- Recent learnings with execution details
SELECT
  run_id,
  workflow_name,
  timestamp,
  model,
  outcome,
  quality_score,
  jsonb_array_length(recommendations) as rec_count
FROM workflows.recent_learnings
ORDER BY timestamp DESC
LIMIT 10;

-- Find learnings by tech stack
SELECT
  workflow_name,
  tech_stack,
  recommendations
FROM workflows.learnings
WHERE tech_stack @> '["Java"]'
ORDER BY timestamp DESC;

-- High-priority memory suggestions
SELECT
  workflow_name,
  jsonb_array_elements(memory_suggestions) ->> 'content' as suggestion
FROM workflows.learnings
WHERE memory_suggestions @> '[{"priority": "high"}]'
ORDER BY timestamp DESC
LIMIT 20;

-- Common bugs across workflows
SELECT
  workflow_name,
  jsonb_array_elements_text(common_bugs) as bug_pattern,
  COUNT(*) as occurrences
FROM workflows.learnings
WHERE common_bugs IS NOT NULL
GROUP BY workflow_name, bug_pattern
ORDER BY occurrences DESC;

-- Tech stack usage
SELECT
  jsonb_array_elements_text(tech_stack) as technology,
  COUNT(*) as usage_count
FROM workflows.learnings
WHERE tech_stack IS NOT NULL
GROUP BY technology
ORDER BY usage_count DESC;

-- Semantic similarity search
WITH query_embedding AS (
  SELECT embedding
  FROM workflows.learnings
  WHERE workflow_name = 'code-solve'
  ORDER BY timestamp DESC
  LIMIT 1
)
SELECT
  l.workflow_name,
  l.recommendations,
  l.embedding <=> q.embedding as distance
FROM workflows.learnings l, query_embedding q
WHERE l.embedding IS NOT NULL
ORDER BY distance
LIMIT 10;
```

## Automatic Extraction (Post-Workflow Hook)

### Enable Automatic Learning

Add to `~/.claude/settings.json`:
```json
{
  "hooks": {
    "workflow:complete": [
      "~/.claude/workflows/hooks/post-workflow-learning.js"
    ]
  }
}
```

### Disable for Specific Workflow

Return `skip_learning_extraction: true` in your workflow result:
```javascript
return {
  status: 'success',
  // ... other result fields
  skip_learning_extraction: true  // Opt out of automatic extraction
};
```

## Learning Object Structure

```javascript
{
  // User patterns
  user_patterns: {
    preferences: [
      'Prefers squash merges',
      'Likes detailed commit messages'
    ],
    expertise_level: {
      'javascript': 'advanced',
      'python': 'intermediate',
      'java': 'beginner'
    },
    workflow_usage: [
      'Runs code-review before PRs',
      'Uses code-test after each commit'
    ]
  },

  // Code patterns
  code_patterns: {
    common_bugs: [
      'Null pointer exceptions',
      'Missing error handling'
    ],
    architecture_insights: [
      'Uses MVC pattern',
      'REST API with Express'
    ],
    tech_stack: [
      'Node.js',
      'PostgreSQL',
      'React'
    ],
    quality_trends: [
      'Test coverage improving',
      'Code review findings decreasing'
    ]
  },

  // Recommendations
  recommendations: [
    'Add null checks before dereferencing',
    'Consider TypeScript for type safety',
    'Implement rate limiting on API endpoints'
  ],

  // Memory suggestions
  memory_suggestions: [
    {
      type: 'user',           // user | feedback | project | reference
      content: 'User prefers squash merges over merge commits',
      priority: 'high'        // high | medium | low
    },
    {
      type: 'project',
      content: 'Codebase uses Express for REST API',
      priority: 'medium'
    }
  ]
}
```

## Examples

### Example 1: Extract Learnings from Code Review

```javascript
// In code-review workflow
const reviewResult = {
  findings_count: 8,
  severity_breakdown: { high: 2, medium: 3, low: 3 },
  categories: ['null-safety', 'error-handling', 'performance'],
  effort_level: 'high'
};

// Extract learnings
const learning = await workflow('ai-extract-learning', {
  run_id: `code-review-${Date.now()}`,
  workflow_name: 'code-review',
  execution_data: reviewResult,
  strategy: 'base'
});

console.log(`Stored learning #${learning.learning_id}`);
console.log(`Found ${learning.learnings.recommendations.length} recommendations`);
```

### Example 2: Find Similar Past Issues

```javascript
const { findSimilarLearnings } = require('~/.claude/learning/storage');

// User reports a null pointer exception
const similar = await findSimilarLearnings(
  'null pointer exception when processing user input',
  5,
  { workflowName: 'code-solve' }
);

// Show how similar issues were fixed
similar.forEach(s => {
  console.log(`Past fix (distance: ${s.distance.toFixed(3)}):`);
  s.recommendations.forEach(rec => console.log(`  - ${rec}`));
});
```

### Example 3: Build User Expertise Profile

```javascript
const { getDB } = require('~/.claude/learning/postgres-adapter');

const expertise = await getDB().query(`
  SELECT
    key as domain,
    value as level,
    COUNT(*) as occurrences
  FROM workflows.learnings,
       jsonb_each_text(expertise_levels)
  GROUP BY key, value
  ORDER BY occurrences DESC
`);

console.log('User Expertise Profile:');
expertise.forEach(e => {
  console.log(`  ${e.domain}: ${e.level} (${e.occurrences} observations)`);
});
```

### Example 4: Track Quality Trends

```javascript
const { getDB } = require('~/.claude/learning/postgres-adapter');

const trends = await getDB().query(`
  SELECT
    DATE(timestamp) as date,
    AVG(quality_score) as avg_quality,
    COUNT(*) as workflow_count
  FROM workflows.learnings
  WHERE quality_score IS NOT NULL
    AND timestamp > NOW() - INTERVAL '30 days'
  GROUP BY DATE(timestamp)
  ORDER BY date DESC
`);

console.log('Quality Trend (last 30 days):');
trends.forEach(t => {
  console.log(`  ${t.date}: ${t.avg_quality.toFixed(2)} (${t.workflow_count} workflows)`);
});
```

## Performance Tips

1. **Use indexes:** JSONB queries are fast with GIN indexes (already created)
2. **Limit results:** Always use `LIMIT` for large result sets
3. **Cache embeddings:** Embedding cache reduces redundant computation
4. **Batch queries:** Use `IN` or `ANY` for multiple workflow lookups
5. **Async operations:** Use `Promise.all()` for parallel queries

```javascript
// Good: Parallel queries
const [recent, stats, similar] = await Promise.all([
  getRecentLearnings(10),
  getLearningStats(),
  findSimilarLearnings('query text', 5)
]);

// Bad: Sequential queries
const recent = await getRecentLearnings(10);
const stats = await getLearningStats();
const similar = await findSimilarLearnings('query text', 5);
```

## Troubleshooting

### "Table does not exist"
```bash
# Run schema creation
psql -h /var/run/postgresql -U $USER -d learning \
  -f ~/.claude/learning/schema-workflows.sql
```

### "Cannot generate embeddings"
```bash
# Install sentence-transformers
pip install sentence-transformers

# Or use fallback (automatic)
# System falls back to hash-based embeddings if library unavailable
```

### "Foreign key violation"
```javascript
// Don't specify execution_id if not available
await storeLearnings(runId, learnings, {
  executionId: null,  // Safe default
  workflowName: 'my-workflow'
});
```

### "Slow similarity search"
```sql
-- Check if HNSW index exists
SELECT indexname FROM pg_indexes
WHERE tablename = 'learnings' AND indexname LIKE '%embedding%';

-- If missing, create it
CREATE INDEX idx_learnings_embedding
  ON workflows.learnings
  USING hnsw (embedding vector_cosine_ops);
```
