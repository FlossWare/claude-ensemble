# Adversarial Verification System - Integration Guide

**Created:** 2026-06-28  
**Status:** Ready for Integration  
**Cost:** $0-0.05 per consensus (using free models)

## Overview

Always-on adversarial verification system that runs AFTER consensus/arbiter synthesis but BEFORE final acceptance. Spawns 3-5 "refuter" agents whose job is to DISPROVE the proposed answer. Only accepts answers if ≥2/3 refuters fail to disprove.

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│ EXISTING CONSENSUS WORKFLOW                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Workers propose answers (3-6 agents)                    │
│     ↓                                                       │
│  2. Arbiter synthesizes top candidate (weighted voting)     │
│     ↓                                                       │
├─────────────────────────────────────────────────────────────┤
│ → ADVERSARIAL VERIFICATION (NEW)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  3. Spawn 3-5 refuters (parallel)                           │
│     │                                                       │
│     ├─ Refuter 1: Try to DISPROVE (free model)             │
│     ├─ Refuter 2: Try to DISPROVE (free model)             │
│     ├─ Refuter 3: Try to DISPROVE (free model)             │
│     ├─ Refuter 4: Try to DISPROVE (optional)               │
│     └─ Refuter 5: Try to DISPROVE (optional)               │
│     ↓                                                       │
│  4. Vote aggregation:                                       │
│     - Count refuters who voted REFUTE                       │
│     - Count refuters who failed to disprove (voted ACCEPT)  │
│     ↓                                                       │
│  5. Acceptance decision:                                    │
│     - If ≥2/3 failed to disprove → ACCEPT                   │
│     - If any critical issues → REJECT                       │
│     - Else → REJECT or ACCEPT_WITH_CAVEATS                  │
│     ↓                                                       │
├─────────────────────────────────────────────────────────────┤
│ STORAGE & LEARNING                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  6. Store to PostgreSQL:                                    │
│     - workflow.adversarial_verifications                    │
│     - Individual refuter votes (JSONB)                      │
│     - Critical/major issues found                           │
│     ↓                                                       │
│  7. Learn from failures:                                    │
│     - Cache refutation patterns                             │
│     - Optimize model selection                              │
│     - Track cost vs quality trade-offs                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Integration Pattern

### Option 1: Automatic Wrapper (Recommended)

Wraps any arbiter result with adversarial verification:

```javascript
import { wrapWithAdversarialVerification } from './shared/adversarial-verification-harness.mjs';

// Existing arbiter call
const arbiterResult = await agent(
  'Synthesize the best answer from worker results...',
  { label: 'arbiter' }
);

// Wrap with adversarial verification
const verified = await wrapWithAdversarialVerification({
  arbiterResult,
  originalTask: userQuestion,
  workflow_execution_id: executionId,
  promptType: 'general', // or 'code', 'factcheck', 'design'
  modelStrategy: 'free' // or 'balanced', 'critical', 'local'
});

// Check verdict
if (verified.verdict === 'REJECT') {
  log(`⚠️  Consensus rejected by adversarial verification:`);
  verified.critical_issues.forEach(issue => {
    log(`   - ${issue.model}: ${issue.reasoning}`);
  });
  // Flag for human review or retry
} else if (verified.verdict === 'ACCEPT_WITH_CAVEATS') {
  log(`⚠️  Consensus accepted with caveats:`);
  verified.major_issues.forEach(issue => {
    log(`   - ${issue.model}: ${issue.reasoning}`);
  });
}

// Return final result
return {
  answer: arbiterResult,
  adversarial_verification: verified,
  confidence: verified.confidence
};
```

### Option 2: Manual Verification

For custom verification logic:

```javascript
import { verifyAdversarially } from './shared/adversarial-verification-harness.mjs';

const result = await verifyAdversarially({
  answer: 'The proposed answer text',
  originalTask: 'What was the original question?',
  promptType: 'code', // Use code-specific refutation
  modelStrategy: 'balanced', // Mix free + cheap models
  numRefuters: 5, // Spawn 5 refuters for critical tasks
  workflow_execution_id: executionId
});

// result.accepted: boolean
// result.confidence: 'high' | 'medium' | 'low'
// result.verdict: 'ACCEPT' | 'ACCEPT_WITH_CAVEATS' | 'REJECT'
// result.critical_issues: Array of critical issues found
// result.cost_usd: Total verification cost
```

## Prompt Types

| Type | Use Case | Focus |
|------|----------|-------|
| `general` | Default for any task | Logic errors, assumptions, edge cases |
| `code` | Code review/generation | Security, bugs, race conditions, API misuse |
| `factcheck` | Research/facts | Misinformation, unsupported claims, contradictions |
| `design` | Architecture/planning | Scalability, coupling, performance, alternatives |

## Model Strategies

| Strategy | Models | Cost/verification | Speed | Use Case |
|----------|--------|-------------------|-------|----------|
| `free` | Gemini, Llama, Qwen, DeepSeek | $0 | Fast | Default for most tasks |
| `balanced` | Haiku, GPT-4o-mini, Gemini, Llama | $0.01-0.05 | Fast | Important tasks |
| `critical` | Opus, GPT-4o, Gemini Pro, Sonnet | $0.10-0.50 | Slower | High-stakes decisions |
| `local` | Ollama models (CPU) | $0 | Slower | Offline/private tasks |

## Acceptance Criteria

```
ACCEPT:
  - ≥2/3 refuters failed to disprove
  - No critical issues
  - No major issues
  → Confidence: HIGH

ACCEPT_WITH_CAVEATS:
  - ≥2/3 refuters failed to disprove
  - No critical issues
  - Has major issues (non-blocking)
  → Confidence: MEDIUM

REJECT:
  - <2/3 refuters failed to disprove
  OR
  - Any critical issues found
  → Confidence: LOW
```

## Cost Optimization

### 1. Use Free Models by Default

```javascript
// $0 per verification
const verified = await wrapWithAdversarialVerification({
  arbiterResult,
  originalTask,
  modelStrategy: 'free' // Gemini, Llama, DeepSeek (all free)
});
```

### 2. Cache Refutation Patterns

```javascript
// Find similar past refutations (avoid re-checking same patterns)
import { findSimilarRefutations } from './shared/adversarial-verification-harness.mjs';

const similar = await findSimilarRefutations(userQuestion, 5);

if (similar.length > 0 && similar[0].distance < 0.1) {
  log(`   💾 Found cached refutation (distance ${similar[0].distance.toFixed(3)})`);
  // Reuse cached issues instead of spawning new refuters
}
```

### 3. Adaptive Strategy Selection

```javascript
// Use free models for low-stakes, critical models for high-stakes
const strategy = taskImportance === 'critical' ? 'critical' : 'free';

const verified = await wrapWithAdversarialVerification({
  arbiterResult,
  originalTask,
  modelStrategy: strategy
});
```

## Database Schema

Run this to create the table:

```bash
psql -h laptop-01 -U sfloess -d learning -f db/schema/adversarial-verifications.sql
```

Schema:
```sql
workflow.adversarial_verifications (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER,
  answer_candidate TEXT,
  original_task TEXT,
  verdict VARCHAR(50), -- ACCEPT | ACCEPT_WITH_CAVEATS | REJECT
  confidence VARCHAR(20), -- high | medium | low
  refuters_failed INTEGER, -- How many failed to disprove (good)
  refuters_total INTEGER,
  critical_issues_count INTEGER,
  major_issues_count INTEGER,
  votes JSONB, -- Individual refuter votes
  cost_usd NUMERIC(10, 6),
  duration_ms INTEGER,
  created_at TIMESTAMP
)
```

## Example Workflow Integration

### deep-research.mjs (Updated)

```javascript
// Phase 5: Synthesize (existing)
const report = await agent('Synthesize research report...', { label: 'synthesis' });

// NEW: Adversarial verification BEFORE returning
const verified = await wrapWithAdversarialVerification({
  arbiterResult: report,
  originalTask: researchQuery,
  workflow_execution_id: executionId,
  promptType: 'factcheck', // Research = fact-checking
  modelStrategy: 'free'
});

if (verified.verdict === 'REJECT') {
  log(`⚠️  Research rejected by adversarial verification`);
  log(`   Critical issues: ${verified.critical_issues.length}`);
  
  // Retry synthesis with issues as context
  const retryReport = await agent(
    `Previous synthesis was rejected for these issues:\n${
      verified.critical_issues.map(i => `- ${i.reasoning}`).join('\n')
    }\n\nResynthesize addressing these issues.`,
    { label: 'synthesis-retry' }
  );
  
  return { report: retryReport, verification: verified };
}

return { report, verification: verified };
```

### code-review.mjs (Updated)

```javascript
// Arbiter synthesizes code review
const review = await agent('Synthesize code review...', { label: 'review-arbiter' });

// Adversarial verification with code-specific prompts
const verified = await wrapWithAdversarialVerification({
  arbiterResult: review,
  originalTask: 'Review this code diff',
  workflow_execution_id: executionId,
  promptType: 'code', // Use security-focused refutation
  modelStrategy: 'balanced' // Mix free + cheap for code review
});

// Only accept if no critical security issues
if (verified.critical_issues.length > 0) {
  log(`🚨 CRITICAL SECURITY ISSUES FOUND:`);
  verified.critical_issues.forEach(issue => {
    log(`   - ${issue.model}: ${issue.reasoning}`);
    if (issue.counterexample) {
      log(`     Exploit: ${issue.counterexample}`);
    }
  });
}

return { review, security_verified: verified.verdict !== 'REJECT' };
```

## Monitoring & Analytics

### Query Recent Rejections

```sql
SELECT
  av.verdict,
  av.confidence,
  av.critical_issues_count,
  av.major_issues_count,
  av.cost_usd,
  we.workflow_name,
  we.task_description
FROM workflow.adversarial_verifications av
JOIN workflow.executions we ON av.workflow_execution_id = we.id
WHERE av.verdict = 'REJECT'
ORDER BY av.created_at DESC
LIMIT 20;
```

### Model Performance (Refuter Accuracy)

```sql
SELECT
  vote->>'model' as model,
  COUNT(*) FILTER (WHERE vote->>'verdict' = 'REFUTE') as refute_count,
  COUNT(*) FILTER (WHERE vote->>'verdict' = 'ACCEPT') as accept_count,
  AVG((vote->>'confidence')::NUMERIC) as avg_confidence,
  COUNT(*) as total_votes
FROM workflow.adversarial_verifications,
     jsonb_array_elements(votes) as vote
GROUP BY vote->>'model'
ORDER BY total_votes DESC;
```

### Cost Analysis

```sql
SELECT * FROM workflow.adversarial_stats;

-- Output:
-- verdict              | confidence | total | avg_success_rate | avg_cost | total_cost
-- ACCEPT              | high       | 245   | 0.95            | 0.0012   | 0.29
-- ACCEPT_WITH_CAVEATS | medium     | 78    | 0.72            | 0.0015   | 0.12
-- REJECT              | low        | 12    | 0.41            | 0.0018   | 0.02
```

## CLI Usage

Test verification without integration:

```bash
# Verify an answer
node shared/adversarial-verification-harness.mjs verify \
  "The answer is 42" \
  "What is the meaning of life?" \
  free

# Find similar refutations (cache lookup)
node shared/adversarial-verification-harness.mjs similar \
  "What is the best JavaScript framework?"
```

## Rollout Plan

1. **Week 1:** Deploy schema to PostgreSQL
2. **Week 1:** Integrate into 1-2 test workflows (deep-research, code-review)
3. **Week 2:** Monitor for 7 days, collect metrics
4. **Week 2:** Tune acceptance thresholds based on data
5. **Week 3:** Roll out to all consensus workflows
6. **Week 4:** Optimize cost via caching and model selection

## Success Metrics

- **False positive rate:** <5% (answers incorrectly rejected)
- **False negative rate:** <2% (bad answers accepted)
- **Average cost:** <$0.02 per verification (using free models)
- **Latency overhead:** <10s (parallel refuters)
- **User-reported issues:** Decrease by 50% (fewer bad outputs)

## Next Steps

1. ✅ Schema deployed (`db/schema/adversarial-verifications.sql`)
2. ✅ Harness implemented (`shared/adversarial-verification-harness.mjs`)
3. ⏳ Integrate into `workflows/deep-research.mjs`
4. ⏳ Integrate into `workflows/code-review.mjs`
5. ⏳ Deploy to PostgreSQL (run schema)
6. ⏳ Test with 10-20 workflows
7. ⏳ Tune thresholds based on results
8. ⏳ Roll out globally

---

**Questions?** See:
- Implementation: `shared/adversarial-verification-harness.mjs`
- Schema: `db/schema/adversarial-verifications.sql`
- Examples: This document (above)
