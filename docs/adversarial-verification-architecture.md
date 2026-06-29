# Adversarial Verification Architecture

**Created:** 2026-06-28  
**Component:** Always-On Adversarial Verification System  
**Integration:** Post-consensus, pre-acceptance validation layer

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MULTI-AI CONSENSUS WORKFLOW                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ User Question
                                     ▼
                      ┌──────────────────────────┐
                      │   PHASE 1: DECOMPOSE     │
                      │  (Planning/Scoping)      │
                      └──────────────────────────┘
                                     │
                                     ▼
                      ┌──────────────────────────┐
                      │   PHASE 2: WORKERS       │
                      │  (Parallel Execution)    │
                      │                          │
                      │  ┌────┐ ┌────┐ ┌────┐  │
                      │  │ W1 │ │ W2 │ │ W3 │  │
                      │  └────┘ └────┘ └────┘  │
                      │  ┌────┐ ┌────┐ ┌────┐  │
                      │  │ W4 │ │ W5 │ │ W6 │  │
                      │  └────┘ └────┘ └────┘  │
                      └──────────────────────────┘
                                     │
                                     │ Worker Results
                                     ▼
                      ┌──────────────────────────┐
                      │   PHASE 3: ARBITER       │
                      │  (Weighted Voting +      │
                      │   Synthesis)             │
                      └──────────────────────────┘
                                     │
                                     │ Candidate Answer
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    🛡️  ADVERSARIAL VERIFICATION LAYER                       │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ Spawn 3-5 Refuter Agents (Parallel)                               │    │
│  │                                                                    │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │    │
│  │  │  Refuter 1   │  │  Refuter 2   │  │  Refuter 3   │           │    │
│  │  │              │  │              │  │              │           │    │
│  │  │ Model: Free  │  │ Model: Free  │  │ Model: Free  │           │    │
│  │  │ (Gemini)     │  │ (Llama)      │  │ (DeepSeek)   │           │    │
│  │  │              │  │              │  │              │           │    │
│  │  │ Task:        │  │ Task:        │  │ Task:        │           │    │
│  │  │ Try to       │  │ Try to       │  │ Try to       │           │    │
│  │  │ DISPROVE     │  │ DISPROVE     │  │ DISPROVE     │           │    │
│  │  │ the answer   │  │ the answer   │  │ the answer   │           │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │    │
│  │         │                  │                  │                   │    │
│  │         └──────────────────┴──────────────────┘                   │    │
│  │                            │                                      │    │
│  │                            ▼                                      │    │
│  │                  ┌──────────────────┐                            │    │
│  │                  │  Vote Aggregator │                            │    │
│  │                  │                  │                            │    │
│  │                  │  Count refutes:  │                            │    │
│  │                  │  - REFUTE = 1    │                            │    │
│  │                  │  - ACCEPT = 2    │                            │    │
│  │                  │                  │                            │    │
│  │                  │  Failed to       │                            │    │
│  │                  │  disprove: 2/3   │                            │    │
│  │                  └──────────────────┘                            │    │
│  │                            │                                      │    │
│  └────────────────────────────┼──────────────────────────────────────┘    │
│                               │                                           │
│                               ▼                                           │
│                    ┌──────────────────────┐                              │
│                    │  Acceptance Decision │                              │
│                    │                      │                              │
│                    │  IF critical issues: │                              │
│                    │    → REJECT          │                              │
│                    │                      │                              │
│                    │  IF ≥2/3 failed:     │                              │
│                    │    → ACCEPT          │                              │
│                    │                      │                              │
│                    │  IF <2/3 failed:     │                              │
│                    │    → REJECT          │                              │
│                    └──────────────────────┘                              │
│                               │                                           │
└───────────────────────────────┼───────────────────────────────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────┐
                 │  PostgreSQL Storage          │
                 │                              │
                 │  workflow.adversarial_       │
                 │    verifications             │
                 │                              │
                 │  - Verdict                   │
                 │  - Confidence                │
                 │  - Refuter votes (JSONB)     │
                 │  - Critical issues           │
                 │  - Cost                      │
                 └──────────────────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────┐
                 │  Learning & Optimization     │
                 │                              │
                 │  - Cache refutation patterns │
                 │  - Model performance         │
                 │  - Cost optimization         │
                 └──────────────────────────────┘
                                │
                                ▼
                      ┌──────────────────┐
                      │  FINAL RESULT    │
                      │                  │
                      │  - Answer        │
                      │  - Verification  │
                      │  - Confidence    │
                      └──────────────────┘
```

## Refuter Prompt Strategy

Each refuter receives a specialized adversarial prompt:

```
🎯 Your role: ADVERSARIAL REFUTER

You are NOT trying to confirm this answer.
You are trying to DISPROVE it.

Default stance: "This answer is WRONG because..."

Analyze for:
1. Logical errors
2. False assumptions
3. Edge cases
4. Contradictory evidence
5. Missing context

Return JSON:
{
  "verdict": "REFUTE" | "ACCEPT",
  "confidence": 0.0-1.0,
  "reasoning": "...",
  "counterexample": "...",
  "severity": "critical" | "major" | "minor" | "none"
}

If you find ONE critical flaw → REFUTE.
Only ACCEPT if you genuinely cannot find problems.
```

## Cost Optimization Strategy

### Model Selection Tiers

**Tier 1: Free Models (Default)**
- Gemini 2.0 Flash Exp
- Llama 3.3 70B Instruct
- Qwen 2.5 72B Instruct
- DeepSeek Chat
- **Cost:** $0 per verification

**Tier 2: Balanced**
- Claude Haiku 4
- GPT-4o Mini
- Gemini 2.0 Flash Exp
- **Cost:** $0.01-0.05 per verification

**Tier 3: Critical**
- Claude Opus 4
- GPT-4o
- Gemini 2.0 Pro Exp
- **Cost:** $0.10-0.50 per verification

**Tier 4: Local**
- Ollama models (CPU inference)
- **Cost:** $0 (CPU time only)

### Caching Strategy

Before spawning refuters, check for similar past refutations:

```javascript
const similar = await findSimilarRefutations(task, 5);

if (similar.length > 0 && similar[0].distance < 0.1) {
  // Reuse cached refutation patterns
  // Skip spawning new refuters for known issues
}
```

**Estimated savings:** 30-50% of verification calls

## Acceptance Thresholds

```
┌────────────────────────────────────────────────────────────┐
│                    Acceptance Matrix                       │
├────────────┬──────────┬──────────┬──────────┬─────────────┤
│ Refuters   │ Critical │ Major    │ Verdict  │ Confidence  │
│ Failed     │ Issues   │ Issues   │          │             │
├────────────┼──────────┼──────────┼──────────┼─────────────┤
│ 3/3        │ 0        │ 0        │ ACCEPT   │ HIGH        │
│ 2/3        │ 0        │ 0        │ ACCEPT   │ HIGH        │
│ 2/3        │ 0        │ 1+       │ ACCEPT   │ MEDIUM      │
│            │          │          │ (caveat) │             │
│ 1/3        │ 0        │ 0+       │ REJECT   │ LOW         │
│ ANY        │ 1+       │ ANY      │ REJECT   │ LOW         │
└────────────┴──────────┴──────────┴──────────┴─────────────┘
```

## Performance Characteristics

### Latency Overhead

- **Parallel refuters:** ~5-10s (3 refuters @ 5s each, parallel)
- **Sequential refuters:** ~15-30s (3 refuters @ 5-10s each)
- **Recommendation:** Always use parallel execution

### Cost Analysis

**Per-verification cost (3 refuters):**
- Free models: $0
- Balanced: $0.01-0.05
- Critical: $0.10-0.50

**Daily cost estimates (100 verifications/day):**
- Free: $0/day
- Balanced: $1-5/day
- Critical: $10-50/day

### Accuracy Metrics (Target)

- **False positive rate:** <5% (good answers rejected)
- **False negative rate:** <2% (bad answers accepted)
- **Critical issue detection:** >95% (find severe bugs)
- **User satisfaction:** +50% (fewer bad outputs)

## Integration Checklist

- [x] Adversarial verification harness implemented
- [x] PostgreSQL schema designed
- [x] Cost optimization strategies defined
- [x] Example workflow integration created
- [x] Documentation written
- [ ] Deploy schema to PostgreSQL
- [ ] Test with 10-20 workflows
- [ ] Tune acceptance thresholds
- [ ] Monitor false positive/negative rates
- [ ] Roll out to all consensus workflows

## Monitoring Queries

### Recent Rejections

```sql
SELECT
  av.verdict,
  av.confidence,
  av.critical_issues_count,
  we.task_description,
  av.created_at
FROM workflow.adversarial_verifications av
JOIN workflow.executions we ON av.workflow_execution_id = we.id
WHERE av.verdict = 'REJECT'
ORDER BY av.created_at DESC
LIMIT 20;
```

### Refuter Model Performance

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

### Cost Tracking

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

## Key Benefits

1. **Quality Gate:** Catches bad consensus results before returning to user
2. **Cost-Efficient:** $0 with free models, <$0.05 with balanced strategy
3. **Fast:** 5-10s latency overhead (parallel execution)
4. **Transparent:** All refutations logged to PostgreSQL
5. **Adaptive:** Learns from past refutations (caching)
6. **Flexible:** 4 prompt types × 4 model strategies = 16 configurations

## Files

- **Harness:** `shared/adversarial-verification-harness.mjs`
- **Schema:** `db/schema/adversarial-verifications.sql`
- **Integration Guide:** `docs/adversarial-verification-integration.md`
- **Architecture:** `docs/adversarial-verification-architecture.md` (this file)
- **Example Workflow:** `workflows/deep-research-with-adversarial.mjs`

---

**Status:** Ready for deployment  
**Next Step:** Deploy schema and integrate into 1-2 test workflows
