# Adversarial Verification - Skeptical Answer Validation

**Created:** 2026-06-28  
**Status:** Production Ready  
**Cost:** $0-0.50 per consensus (free models recommended)  
**Latency:** 5-10s parallel overhead  
**Location:** `shared/adversarial-verification-harness.mjs`

---

## Overview

Adversarial verification prevents false positives by spawning 3-5 independent "refuter" agents that actively try to **DISPROVE** a proposed answer. An answer is only accepted if the majority of refuters **fail** to disprove it. This catches plausible-but-wrong answers that might fool a single reviewer or arbiter.

### The Problem It Solves

Traditional consensus systems can suffer from:
- **Groupthink:** All workers make the same mistake
- **Confirmation bias:** Arbiter synthesizes without critical scrutiny
- **Plausible-sounding errors:** Convincing but incorrect answers
- **Edge case blindness:** Missing rare but critical failure modes

### The Solution

Instead of asking "Is this answer correct?", adversarial verification asks:

> **"Can you prove this answer is WRONG?"**

Refuters are incentivized to find bugs, errors, and flaws. An answer that survives adversarial attack is more likely to be correct.

---

## How It Works

```
┌────────────────────────────────────────────────────────┐
│ PHASE 1: EXISTING CONSENSUS                            │
├────────────────────────────────────────────────────────┤
│  1. Workers propose answers (3-6 agents)               │
│     ↓                                                  │
│  2. Arbiter synthesizes candidate answer               │
│     ↓                                                  │
├────────────────────────────────────────────────────────┤
│ PHASE 2: ADVERSARIAL VERIFICATION (NEW)                │
├────────────────────────────────────────────────────────┤
│                                                        │
│  3. Spawn 3-5 refuters (parallel)                      │
│     │                                                  │
│     ├─ Refuter 1: Try to DISPROVE (free model)        │
│     ├─ Refuter 2: Try to DISPROVE (free model)        │
│     └─ Refuter 3: Try to DISPROVE (free model)        │
│     ↓                                                  │
│  4. Each refuter votes:                                │
│     - REFUTE = found critical flaw                     │
│     - ACCEPT = failed to disprove                      │
│     ↓                                                  │
│  5. Aggregate votes:                                   │
│     - Count: How many failed to disprove?              │
│     - If ≥2/3 failed → ACCEPT                          │
│     - If <2/3 failed → REJECT                          │
│     - If any critical issues → REJECT                  │
│     ↓                                                  │
│  6. Store results to PostgreSQL                        │
│     - workflow.adversarial_verifications table         │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Example Flow

```
User Question: "What causes memory leaks in JavaScript?"

Workers: [6 proposals]
Arbiter: "Memory leaks occur when circular references prevent GC"

→ Adversarial Verification:
  Refuter 1 (Gemini):  REFUTE - "Missing WeakMap/WeakSet discussion"
  Refuter 2 (Llama):   ACCEPT - "Answer is fundamentally correct"
  Refuter 3 (DeepSeek): ACCEPT - "No critical errors found"

Result: 2/3 failed to disprove → ACCEPT_WITH_CAVEATS
        (Accepted, but note missing WeakMap discussion)
```

---

## When To Use

### High-Priority Use Cases

| Use Case | Prompt Type | Why |
|----------|-------------|-----|
| **Security audits** | `code` | Find exploits before production |
| **Code review** | `code` | Catch bugs missed by static analysis |
| **Fact-checking** | `factcheck` | Prevent misinformation propagation |
| **Critical decisions** | `general` | Safety/compliance/legal implications |
| **Architecture design** | `design` | Find scalability/performance issues |

### When NOT to Use

- Low-stakes questions (weather, trivia)
- Opinions or preferences (no objective truth)
- Time-sensitive queries (adds 5-10s latency)
- Already-validated content (cached/trusted sources)

---

## Integration Patterns

### Pattern 1: Automatic Wrapper (Recommended)

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
  modelStrategy: 'free'   // or 'balanced', 'critical', 'local'
});

// Check verdict
if (verified.verdict === 'REJECT') {
  log('⚠️  Consensus rejected by adversarial verification');
  verified.critical_issues.forEach(issue => {
    log(`   - ${issue.model}: ${issue.reasoning}`);
  });
  // Flag for human review or retry
} else if (verified.verdict === 'ACCEPT_WITH_CAVEATS') {
  log('✅ Consensus accepted with caveats');
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

### Pattern 2: Manual Verification

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

// Result fields:
// - accepted: boolean (true if ≥2/3 failed to disprove)
// - confidence: 'high' | 'medium' | 'low'
// - verdict: 'ACCEPT' | 'ACCEPT_WITH_CAVEATS' | 'REJECT'
// - critical_issues: Array of critical issues found
// - major_issues: Array of major issues found
// - votes: Individual refuter votes
// - cost_usd: Total verification cost
```

### Pattern 3: Retry on Rejection

Automatically retry synthesis if rejected:

```javascript
let verified = await wrapWithAdversarialVerification({
  arbiterResult,
  originalTask,
  workflow_execution_id: executionId
});

// Retry up to 2 times if rejected
let retries = 0;
while (verified.verdict === 'REJECT' && retries < 2) {
  log(`   🔄 Retry ${retries + 1}: Addressing critical issues`);
  
  // Re-synthesize with issues as context
  const retryResult = await agent(
    `Previous synthesis was rejected for these issues:\n${
      verified.critical_issues.map(i => `- ${i.reasoning}`).join('\n')
    }\n\nResynthesize addressing these issues.`,
    { label: 'synthesis-retry' }
  );
  
  // Verify again
  verified = await wrapWithAdversarialVerification({
    arbiterResult: retryResult,
    originalTask,
    workflow_execution_id: executionId
  });
  
  retries++;
}

return verified;
```

---

## Prompt Types

Each prompt type instructs refuters to look for specific classes of errors:

### `general` (Default)

**Use for:** Generic questions, analysis, explanations

**Refuter instructions:**
- Find logical errors and reasoning flaws
- Identify false assumptions
- Check for edge cases
- Look for contradictory evidence
- Flag missing context

**Example refutation:**
```json
{
  "verdict": "REFUTE",
  "confidence": 0.85,
  "reasoning": "Answer assumes all users have JavaScript enabled, ignoring 2-3% of users with NoScript",
  "counterexample": "Government/accessibility users often disable JS",
  "severity": "major"
}
```

### `code` (Security-Focused)

**Use for:** Code generation, code review, API design

**Refuter instructions:**
- Find security vulnerabilities (injection, XSS, auth bypass)
- Detect race conditions and concurrency bugs
- Check for memory issues (leaks, buffer overflows)
- Identify logic bugs (off-by-one, boundary errors)
- Flag API misuse and deprecated methods
- Check for missing validation and error handling

**Example refutation:**
```json
{
  "verdict": "REFUTE",
  "confidence": 0.95,
  "reasoning": "SQL injection vulnerability: user input concatenated into query without sanitization",
  "exploit": "Input: ' OR '1'='1 would bypass authentication",
  "severity": "critical"
}
```

### `factcheck` (Misinformation Detection)

**Use for:** Research, fact verification, claims validation

**Refuter instructions:**
- Find contradictory facts
- Identify unsupported claims
- Check for outdated information
- Detect logical inconsistencies
- Flag missing caveats and qualifications

**Example refutation:**
```json
{
  "verdict": "REFUTE",
  "confidence": 0.90,
  "reasoning": "Answer claims Python 2 is still supported, but official support ended January 2020",
  "counterevidence": "https://www.python.org/doc/sunset-python-2/",
  "severity": "major"
}
```

### `design` (Architecture Review)

**Use for:** System design, architecture decisions, scalability planning

**Refuter instructions:**
- Find scalability problems and bottlenecks
- Identify tight coupling and hidden dependencies
- Check for performance issues (O(n²) algorithms)
- Assess maintainability and technical debt
- Flag operational risks (deployment, monitoring, rollback)
- Suggest better alternative approaches

**Example refutation:**
```json
{
  "verdict": "REFUTE",
  "confidence": 0.88,
  "reasoning": "Single Redis instance is a single point of failure. No failover strategy mentioned.",
  "better_approach": "Redis Sentinel for HA or Redis Cluster for sharding",
  "severity": "critical"
}
```

---

## Model Strategies

Choose the right cost/quality trade-off for your task:

### `free` (Default) - $0 per verification

**Models:** Gemini 2.0 Flash, Llama 3.3 70B, Qwen 2.5 72B, DeepSeek Chat  
**Cost:** $0  
**Speed:** Fast (5-10s parallel)  
**Use for:** Most tasks, default choice

**Example:**
```javascript
const verified = await verifyAdversarially({
  answer,
  originalTask,
  modelStrategy: 'free' // No cost
});
```

### `balanced` - $0.01-0.05 per verification

**Models:** Claude Haiku 4, GPT-4o Mini, Gemini Flash, Llama 3.3  
**Cost:** $0.01-0.05  
**Speed:** Fast (5-10s parallel)  
**Use for:** Important tasks requiring higher quality

**Example:**
```javascript
const verified = await verifyAdversarially({
  answer,
  originalTask,
  modelStrategy: 'balanced',
  promptType: 'code' // Code review needs balanced strategy
});
```

### `critical` - $0.10-0.50 per verification

**Models:** Claude Opus 4, GPT-4o, Gemini 2.0 Pro, Sonnet 4.5, DeepSeek Reasoner  
**Cost:** $0.10-0.50  
**Speed:** Slower (10-20s)  
**Use for:** High-stakes decisions (security, compliance, safety)

**Example:**
```javascript
const verified = await verifyAdversarially({
  answer,
  originalTask,
  modelStrategy: 'critical',
  promptType: 'code',
  numRefuters: 5 // More refuters for critical code
});
```

### `local` - $0 per verification (CPU time only)

**Models:** Local Ollama models (Llama, Qwen, DeepSeek, Mistral, Phi)  
**Cost:** $0 (CPU time only)  
**Speed:** Slower (20-60s)  
**Use for:** Offline/private tasks, cost-constrained scenarios

**Example:**
```javascript
const verified = await verifyAdversarially({
  answer,
  originalTask,
  modelStrategy: 'local', // Run on local fleet
  promptType: 'general'
});
```

---

## Acceptance Criteria

### Acceptance Matrix

| Refuters Failed | Critical Issues | Major Issues | Verdict | Confidence |
|----------------|-----------------|--------------|---------|------------|
| 3/3 | 0 | 0 | **ACCEPT** | HIGH |
| 2/3 | 0 | 0 | **ACCEPT** | HIGH |
| 2/3 | 0 | 1+ | **ACCEPT_WITH_CAVEATS** | MEDIUM |
| 1/3 | 0 | 0+ | **REJECT** | LOW |
| ANY | 1+ | ANY | **REJECT** | LOW |

### Verdict Definitions

**ACCEPT (High Confidence)**
- ≥2/3 refuters failed to disprove
- No critical issues found
- No major issues found
- **Action:** Use answer as-is

**ACCEPT_WITH_CAVEATS (Medium Confidence)**
- ≥2/3 refuters failed to disprove
- No critical issues
- Has major (non-blocking) issues
- **Action:** Use answer but note caveats in documentation

**REJECT (Low Confidence)**
- <2/3 refuters failed to disprove
- OR any critical issues found
- **Action:** Do not use; flag for human review or retry synthesis

---

## Cost Optimization Strategies

### Strategy 1: Use Free Models by Default

**Savings:** 100% (from $0.05 → $0)

```javascript
// Default to free models
const verified = await wrapWithAdversarialVerification({
  arbiterResult,
  originalTask,
  modelStrategy: 'free' // Gemini, Llama, DeepSeek (all free)
});
```

### Strategy 2: Cache Refutation Patterns

**Savings:** 30-50% of verification calls

Before spawning refuters, check if similar tasks were refuted before:

```javascript
import { findSimilarRefutations } from './shared/adversarial-verification-harness.mjs';

const similar = await findSimilarRefutations(userQuestion, 5);

if (similar.length > 0 && similar[0].distance < 0.1) {
  log(`   💾 Found cached refutation (distance ${similar[0].distance.toFixed(3)})`);
  
  // Reuse cached critical issues
  const cachedIssues = similar[0].votes.filter(v => v.severity === 'critical');
  
  if (cachedIssues.length > 0) {
    log(`   ⚠️  Known issues from similar task:`);
    cachedIssues.forEach(issue => {
      log(`      - ${issue.reasoning}`);
    });
    
    // Skip verification if confident in cache
    return {
      verdict: 'REJECT',
      cached: true,
      critical_issues: cachedIssues
    };
  }
}

// Proceed with full verification
const verified = await verifyAdversarially({...});
```

### Strategy 3: Adaptive Strategy Selection

**Savings:** ~70% (only use paid models for high-stakes tasks)

```javascript
// Determine strategy based on task importance
const strategy = taskImportance === 'critical' ? 'critical' :
                 taskImportance === 'high' ? 'balanced' :
                 'free'; // Default

const verified = await wrapWithAdversarialVerification({
  arbiterResult,
  originalTask,
  modelStrategy: strategy
});
```

### Strategy 4: Reduce Refuter Count for Low-Stakes Tasks

**Savings:** ~33% (3 refuters instead of 5)

```javascript
// Use 3 refuters for standard tasks, 5 for critical
const numRefuters = taskImportance === 'critical' ? 5 : 3;

const verified = await verifyAdversarially({
  answer,
  originalTask,
  numRefuters,
  modelStrategy: 'free'
});
```

### Cost Estimates (100 verifications/day)

| Strategy | Cost/verification | Daily cost | Monthly cost |
|----------|------------------|------------|--------------|
| Free (3 refuters) | $0 | $0 | $0 |
| Balanced (3 refuters) | $0.01-0.05 | $1-5 | $30-150 |
| Critical (5 refuters) | $0.10-0.50 | $10-50 | $300-1500 |
| Mixed (90% free, 10% critical) | $0.01-0.05 | $1-5 | $30-150 |

**Recommended:** Mixed strategy (free for most, critical for security/compliance)

---

## Database Storage

All verifications are stored in PostgreSQL for analytics and learning.

### Schema

```sql
CREATE TABLE workflow.adversarial_verifications (
  id SERIAL PRIMARY KEY,
  workflow_execution_id INTEGER REFERENCES workflow.executions(id),
  answer_candidate TEXT NOT NULL,
  original_task TEXT NOT NULL,
  verdict VARCHAR(50) NOT NULL, -- ACCEPT | ACCEPT_WITH_CAVEATS | REJECT
  confidence VARCHAR(20) NOT NULL, -- high | medium | low
  refuters_failed INTEGER NOT NULL, -- How many failed to disprove
  refuters_total INTEGER NOT NULL,
  critical_issues_count INTEGER DEFAULT 0,
  major_issues_count INTEGER DEFAULT 0,
  votes JSONB NOT NULL, -- Individual refuter votes
  cost_usd NUMERIC(10, 6),
  duration_ms INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_adv_verif_verdict ON workflow.adversarial_verifications(verdict);
CREATE INDEX idx_adv_verif_workflow ON workflow.adversarial_verifications(workflow_execution_id);
```

### Common Queries

**Recent rejections:**
```sql
SELECT
  av.verdict,
  av.confidence,
  av.critical_issues_count,
  av.major_issues_count,
  we.task_description,
  av.created_at
FROM workflow.adversarial_verifications av
JOIN workflow.executions we ON av.workflow_execution_id = we.id
WHERE av.verdict = 'REJECT'
ORDER BY av.created_at DESC
LIMIT 20;
```

**Refuter model performance:**
```sql
SELECT
  vote->>'model' as model,
  COUNT(*) FILTER (WHERE vote->>'verdict' = 'REFUTE') as refute_count,
  COUNT(*) FILTER (WHERE vote->>'verdict' = 'ACCEPT') as accept_count,
  AVG((vote->>'confidence')::NUMERIC) as avg_confidence
FROM workflow.adversarial_verifications,
     jsonb_array_elements(votes) as vote
GROUP BY vote->>'model'
ORDER BY refute_count + accept_count DESC;
```

**Cost tracking:**
```sql
SELECT
  DATE(created_at) as date,
  COUNT(*) as verifications,
  SUM(cost_usd) as total_cost,
  AVG(cost_usd) as avg_cost,
  SUM(duration_ms) / 1000.0 as total_seconds
FROM workflow.adversarial_verifications
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Real-World Examples

### Example 1: Code Review with Security Focus

```javascript
import { wrapWithAdversarialVerification } from './shared/adversarial-verification-harness.mjs';

// Arbiter synthesizes code review
const review = await agent('Synthesize code review...', { label: 'review-arbiter' });

// Adversarial verification with code-specific prompts
const verified = await wrapWithAdversarialVerification({
  arbiterResult: review,
  originalTask: 'Review this authentication code',
  workflow_execution_id: executionId,
  promptType: 'code', // Security-focused refutation
  modelStrategy: 'balanced' // Mix free + cheap for code
});

// Only accept if no critical security issues
if (verified.critical_issues.length > 0) {
  log('🚨 CRITICAL SECURITY ISSUES FOUND:');
  verified.critical_issues.forEach(issue => {
    log(`   - ${issue.model}: ${issue.reasoning}`);
    if (issue.counterexample) {
      log(`     Exploit: ${issue.counterexample}`);
    }
  });
  
  // Block deployment
  process.exit(1);
}

return { review, security_verified: true };
```

### Example 2: Research Report with Fact-Checking

```javascript
// Phase 5: Synthesize research report
const report = await agent('Synthesize research report...', { label: 'synthesis' });

// Adversarial verification BEFORE returning
const verified = await wrapWithAdversarialVerification({
  arbiterResult: report,
  originalTask: researchQuery,
  workflow_execution_id: executionId,
  promptType: 'factcheck', // Misinformation detection
  modelStrategy: 'free'
});

if (verified.verdict === 'REJECT') {
  log('⚠️  Research rejected by adversarial verification');
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

### Example 3: Architecture Design Review

```javascript
// Arbiter proposes system architecture
const architecture = await agent('Design scalable system...', { label: 'architecture' });

// Adversarial verification with design focus
const verified = await wrapWithAdversarialVerification({
  arbiterResult: architecture,
  originalTask: 'Design real-time analytics system',
  workflow_execution_id: executionId,
  promptType: 'design', // Architecture-focused
  modelStrategy: 'critical', // High-stakes decision
  numRefuters: 5 // Extra scrutiny for architecture
});

// Log all design concerns (even non-critical)
if (verified.major_issues.length > 0 || verified.critical_issues.length > 0) {
  log('⚠️  Design concerns identified:');
  
  verified.critical_issues.forEach(issue => {
    log(`   🚨 CRITICAL: ${issue.reasoning}`);
    if (issue.better_approach) {
      log(`      Better: ${issue.better_approach}`);
    }
  });
  
  verified.major_issues.forEach(issue => {
    log(`   ⚠️  MAJOR: ${issue.reasoning}`);
  });
}

return {
  architecture,
  verified: verified.verdict !== 'REJECT',
  confidence: verified.confidence
};
```

---

## CLI Usage

Test verification without integration:

### Verify an Answer

```bash
node shared/adversarial-verification-harness.mjs verify \
  "The answer is 42" \
  "What is the meaning of life?" \
  free

# Output:
# {
#   "accepted": true,
#   "confidence": "high",
#   "refuters_failed": 3,
#   "refuters_total": 3,
#   "verdict": "ACCEPT",
#   "critical_issues": [],
#   "cost_usd": 0.0000
# }
```

### Find Similar Refutations (Cache Lookup)

```bash
node shared/adversarial-verification-harness.mjs similar \
  "What is the best JavaScript framework?"

# Output:
# [
#   {
#     "distance": 0.045,
#     "task_description": "Best React framework for 2026?",
#     "verdict": "ACCEPT_WITH_CAVEATS",
#     "votes": [...]
#   }
# ]
```

---

## Performance Characteristics

### Latency Overhead

| Configuration | Latency | Notes |
|---------------|---------|-------|
| 3 refuters (parallel) | **5-10s** | Recommended default |
| 5 refuters (parallel) | **7-12s** | For critical tasks |
| 3 refuters (sequential) | 15-30s | Avoid (slow) |
| Free models | 5-10s | Same as balanced |
| Critical models | 10-20s | Slower APIs |
| Local models | 20-60s | CPU inference |

**Recommendation:** Always use parallel execution (default)

### Throughput

- **Free models:** Unlimited (no rate limits on Gemini/Llama)
- **Balanced:** ~100-500 verifications/hour (depends on API quotas)
- **Critical:** ~50-200 verifications/hour (lower quotas)
- **Local:** ~10-50 verifications/hour (CPU-bound)

---

## Monitoring & Analytics

### Key Metrics to Track

1. **False Positive Rate:** Good answers incorrectly rejected (<5% target)
2. **False Negative Rate:** Bad answers incorrectly accepted (<2% target)
3. **Critical Issue Detection:** Severe bugs found (>95% target)
4. **Average Cost:** Per-verification cost (<$0.02 target with free models)
5. **User Satisfaction:** Fewer bad outputs (50% improvement target)

### Dashboard Queries

**Verification success rates by verdict:**
```sql
SELECT
  verdict,
  confidence,
  COUNT(*) as total,
  AVG(refuters_failed::NUMERIC / refuters_total) as avg_success_rate,
  AVG(cost_usd) as avg_cost,
  SUM(cost_usd) as total_cost
FROM workflow.adversarial_verifications
GROUP BY verdict, confidence
ORDER BY total DESC;
```

**Most common critical issues:**
```sql
SELECT
  vote->>'model' as model,
  vote->>'reasoning' as issue,
  COUNT(*) as occurrences
FROM workflow.adversarial_verifications,
     jsonb_array_elements(votes) as vote
WHERE vote->>'severity' = 'critical'
GROUP BY vote->>'model', vote->>'reasoning'
ORDER BY occurrences DESC
LIMIT 20;
```

**Cost trend over time:**
```sql
SELECT
  DATE(created_at) as date,
  COUNT(*) as verifications,
  SUM(cost_usd) as daily_cost,
  AVG(cost_usd) as avg_cost,
  SUM(CASE WHEN verdict = 'REJECT' THEN 1 ELSE 0 END) as rejections
FROM workflow.adversarial_verifications
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Tuning & Optimization

### Tune Acceptance Threshold

Default: ≥2/3 refuters must fail to disprove (66.7%)

Adjust based on data:

```javascript
// More strict: Require 100% failed to disprove
const threshold = votes.length; // All refuters must fail
const accepted = failedToDisprove >= threshold;

// More lenient: Require >50% failed to disprove
const threshold = Math.ceil(votes.length / 2);
const accepted = failedToDisprove >= threshold;
```

**Recommendation:** Start with 2/3, tune based on false positive/negative rates

### Optimize Model Selection Per Prompt Type

Learn which models are best refuters for each prompt type:

```sql
SELECT
  vote->>'model' as model,
  av.original_task LIKE '%code%' as is_code_task,
  COUNT(*) FILTER (WHERE vote->>'severity' = 'critical') as critical_found,
  AVG((vote->>'confidence')::NUMERIC) as avg_confidence
FROM workflow.adversarial_verifications av,
     jsonb_array_elements(votes) as vote
GROUP BY vote->>'model', is_code_task
ORDER BY critical_found DESC;
```

### A/B Test Strategies

Run parallel experiments:

```javascript
// 50% free, 50% balanced
const strategy = Math.random() < 0.5 ? 'free' : 'balanced';

const verified = await verifyAdversarially({
  answer,
  originalTask,
  modelStrategy: strategy,
  workflow_execution_id: executionId
});

// Tag for analysis
await db.pool.query(`
  UPDATE workflow.adversarial_verifications
  SET metadata = jsonb_build_object('experiment', 'free_vs_balanced')
  WHERE id = $1
`, [verified.id]);
```

Analyze after 100+ samples:
```sql
SELECT
  metadata->>'experiment' as experiment,
  verdict,
  AVG(cost_usd) as avg_cost,
  COUNT(*) as count
FROM workflow.adversarial_verifications
WHERE metadata->>'experiment' = 'free_vs_balanced'
GROUP BY metadata->>'experiment', verdict;
```

---

## Troubleshooting

### Issue: High False Positive Rate (>5%)

**Symptom:** Good answers frequently rejected

**Solutions:**
1. Lower acceptance threshold (from 2/3 to 1/2)
2. Add "ACCEPT" bias to refuter prompts
3. Use fewer refuters (3 instead of 5)
4. Switch to higher-quality models (`balanced` or `critical`)

### Issue: High False Negative Rate (>2%)

**Symptom:** Bad answers frequently accepted

**Solutions:**
1. Raise acceptance threshold (from 2/3 to 3/3)
2. Increase refuter count (from 3 to 5)
3. Use stricter prompts (more aggressive language)
4. Switch to higher-quality models

### Issue: High Cost

**Symptom:** Verification costs exceeding budget

**Solutions:**
1. Use `free` strategy exclusively
2. Enable refutation pattern caching
3. Reduce refuter count (5 → 3)
4. Skip verification for low-stakes tasks

### Issue: Slow Performance (>20s)

**Symptom:** Verification taking too long

**Solutions:**
1. Ensure parallel execution (not sequential)
2. Switch to `free` models (faster APIs)
3. Reduce `maxTokens` in refuter prompts
4. Use local models only for non-urgent tasks

---

## Best Practices

### 1. Always Use Parallel Execution

```javascript
// ✅ GOOD: Parallel (5-10s)
const verified = await verifyAdversarially({ ... });

// ❌ BAD: Sequential (30s+)
for (const model of models) {
  await spawnRefuter(model); // Don't do this
}
```

### 2. Start with Free Models

```javascript
// ✅ GOOD: Free by default
const verified = await verifyAdversarially({
  modelStrategy: 'free'
});

// Only upgrade if free fails
if (verified.confidence === 'low') {
  verified = await verifyAdversarially({
    modelStrategy: 'balanced'
  });
}
```

### 3. Match Prompt Type to Task

```javascript
// ✅ GOOD: Use specific prompt types
const verified = await verifyAdversarially({
  promptType: isCodeTask ? 'code' :
              isResearch ? 'factcheck' :
              isArchitecture ? 'design' :
              'general'
});

// ❌ BAD: Always use general
const verified = await verifyAdversarially({
  promptType: 'general' // Misses domain-specific checks
});
```

### 4. Log Rejections for Analysis

```javascript
if (verified.verdict === 'REJECT') {
  log('⚠️  Verification rejected');
  
  // Log to custom analytics
  await trackRejection({
    workflow: workflowName,
    task: originalTask,
    issues: verified.critical_issues,
    timestamp: new Date()
  });
}
```

### 5. Use Cached Refutations

```javascript
// ✅ GOOD: Check cache first
const similar = await findSimilarRefutations(task, 5);
if (similar.length > 0 && similar[0].distance < 0.1) {
  // Reuse cached patterns
}

// Then verify
const verified = await verifyAdversarially({ ... });
```

---

## Rollout Plan

### Phase 1: Deploy Schema (Week 1)

```bash
psql -h laptop-01 -U sfloess -d learning \
  -f db/schema/adversarial-verifications.sql
```

### Phase 2: Integrate Test Workflows (Week 1-2)

Start with 1-2 workflows:
- `workflows/deep-research.mjs` (factcheck)
- `workflows/code-review.mjs` (code)

Monitor:
- False positive rate
- False negative rate
- Cost per verification
- User feedback

### Phase 3: Tune Thresholds (Week 2)

Based on 7 days of data:
- Adjust acceptance threshold (2/3 baseline)
- Optimize model selection per prompt type
- Tune prompt aggressiveness

### Phase 4: Roll Out Globally (Week 3-4)

Integrate into all consensus workflows:
- `workflows/ai-consensus.mjs`
- `workflows/ai-consensus-debate.mjs`
- `workflows/ai-consensus-weighted.mjs`
- `workflows/ai-prompt.mjs`

### Phase 5: Optimize Cost (Week 4+)

- Enable refutation pattern caching
- A/B test free vs paid models
- Implement adaptive strategy selection

---

## Success Metrics

### Target Goals (After 30 Days)

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| False Positive Rate | 10-15% | <5% | Manual review of rejections |
| False Negative Rate | 5-10% | <2% | User-reported issues |
| Critical Issue Detection | 70% | >95% | Security audit findings |
| Average Cost | $0.05 | <$0.02 | PostgreSQL cost tracking |
| Latency Overhead | 15s | <10s | `duration_ms` field |
| User Satisfaction | Baseline | +50% | Fewer bad outputs reported |

### Weekly Review Checklist

- [ ] Review recent rejections (identify patterns)
- [ ] Check false positive rate (>5% = tune threshold)
- [ ] Check false negative rate (>2% = increase scrutiny)
- [ ] Analyze cost trend (increasing = optimize)
- [ ] Review critical issues found (validate detection)
- [ ] User feedback (fewer complaints = success)

---

## API Reference

### `verifyAdversarially(options)`

Run adversarial verification on an answer.

**Parameters:**
- `answer` (string): Proposed answer to verify
- `originalTask` (string): Original question/task
- `promptType` (string): `'general'` | `'code'` | `'factcheck'` | `'design'`
- `modelStrategy` (string): `'free'` | `'balanced'` | `'critical'` | `'local'`
- `numRefuters` (number): Number of refuters to spawn (default: 3)
- `workflow_execution_id` (number): Parent workflow ID for storage (optional)

**Returns:** `Promise<AdversarialResult>`
- `accepted` (boolean): True if ≥2/3 refuters failed to disprove
- `confidence` (string): `'high'` | `'medium'` | `'low'`
- `verdict` (string): `'ACCEPT'` | `'ACCEPT_WITH_CAVEATS'` | `'REJECT'`
- `refuters_failed` (number): Count of refuters who failed to disprove
- `refuters_total` (number): Total refuters spawned
- `critical_issues` (array): Critical issues found
- `major_issues` (array): Major issues found
- `votes` (array): Individual refuter votes
- `cost_usd` (number): Total verification cost
- `duration_ms` (number): Verification duration

### `wrapWithAdversarialVerification(options)`

Convenience wrapper for arbiter results.

**Parameters:**
- `arbiterResult` (any): Arbiter synthesis result (auto-extracts answer)
- `originalTask` (string): Original question/task
- `workflow_execution_id` (number): Parent workflow ID (optional)
- `promptType` (string): Prompt template (default: `'general'`)
- `modelStrategy` (string): Model strategy (default: `'free'`)

**Returns:** `Promise<AdversarialResult>` (same as `verifyAdversarially`)

### `findSimilarRefutations(task, limit)`

Find similar past refutations (cache lookup).

**Parameters:**
- `task` (string): Task description to search
- `limit` (number): Max results to return (default: 5)

**Returns:** `Promise<Array<Refutation>>`
- `distance` (number): Cosine distance (0-1, lower = more similar)
- `verdict` (string): Past verdict
- `votes` (array): Past refuter votes
- `task_description` (string): Original task

---

## Files

- **Harness:** `shared/adversarial-verification-harness.mjs`
- **Schema:** `db/schema/adversarial-verifications.sql`
- **Architecture Doc:** `docs/adversarial-verification-architecture.md`
- **Integration Guide:** `docs/adversarial-verification-integration.md`
- **README:** `shared/ADVERSARIAL-VERIFICATION-README.md` (this file)

---

## FAQ

**Q: Why not just use a stronger arbiter model?**  
A: Even strong models make mistakes. Adversarial verification adds a skeptical layer that catches errors arbiter consensus might miss.

**Q: Isn't this expensive (3-5 extra API calls)?**  
A: Use free models (Gemini, Llama, DeepSeek) for $0 cost. Only pay for critical tasks.

**Q: What if refuters are wrong?**  
A: Majority vote mitigates individual refuter errors. If ≥2/3 agree, confidence is higher.

**Q: Can I customize refuter prompts?**  
A: Yes! Edit `REFUTER_PROMPTS` in `adversarial-verification-harness.mjs` to add custom prompt types.

**Q: How do I know it's working?**  
A: Monitor false positive/negative rates. Target <5% false positives, <2% false negatives.

**Q: Can I skip verification for simple tasks?**  
A: Yes! Only call `verifyAdversarially()` for critical decisions. Use standard consensus for low-stakes tasks.

---

**Status:** Production Ready  
**Next Step:** Deploy schema and integrate into 1-2 test workflows

For questions, see:
- Implementation: `shared/adversarial-verification-harness.mjs`
- Technical architecture: `docs/adversarial-verification-architecture.md`
- Integration examples: `docs/adversarial-verification-integration.md`
