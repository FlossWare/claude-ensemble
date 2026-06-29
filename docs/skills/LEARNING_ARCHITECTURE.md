# Learning Architecture - Self-Improving AI Orchestration

**Status**: Design Phase  
**Created**: 2026-06-13  
**Vision**: System that learns from EVERY execution and gets smarter over time

---

## WHY Self-Learning?

### The Problem

Current state:
- **Static strategies**: Every "code review" task uses the same 6-worker approach regardless of complexity
- **No memory**: Successful strategies forgotten after execution
- **Wasted compute**: Using Opus ($$$) for simple tasks that Haiku ($) handles fine
- **Missed opportunities**: Don't learn which model combinations work best

**Example waste**:
```
Task: "Fix typo in README"
Current: 6 workers (opus, sonnet, haiku, fable, gpt-4o, gemini) + opus arbiter
Cost: ~50k tokens
Time: 67 seconds

Optimal: 1 worker (haiku)
Cost: ~800 tokens (98% savings)
Time: 12 seconds (82% faster)
```

### The Vision

**Self-improving orchestration**:
- ✅ Learn what works from every execution
- ✅ Adapt strategies based on evidence
- ✅ Optimize cost/quality tradeoff automatically
- ✅ Get BETTER over time, not just faster

**Concrete goal**: After 100 security audits, the system KNOWS opus+gemini+sonnet is the optimal combo and uses it automatically.

---

## HOW It Works

### Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    USER REQUEST                          │
│  "Audit this code for security vulnerabilities"          │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│               1. SIMILARITY SEARCH (VectorDB)             │
│  Embed task → Find similar past executions                │
│  Returns: 5 past security audits with metadata           │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│           2. LEARNING EXTRACTION (Learning DB)            │
│  Analyze past executions:                                 │
│  - opus+gemini+sonnet combo: 0.95 avg quality            │
│  - temp=0.2 optimal for security tasks                   │
│  - Adversarial prompts work best                         │
│  - Avg cost: 23k tokens, time: 67s                       │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│          3. STRATEGY DESIGN (Meta-AI Consultant)          │
│  AI designs execution plan using learned knowledge:       │
│  - Workers: opus, gemini, sonnet (learned optimal)       │
│  - Parameters: temp=0.2 (learned optimal)                │
│  - Prompts: adversarial pattern (learned effective)      │
│  - Budget: ~25k tokens (learned avg + 10% margin)        │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│              4. EXECUTION (Fleet Dispatcher)              │
│  Apply model compliance → Route to servers →              │
│  Track reactions (confidence, hesitation) →               │
│  Measure outcomes (quality, cost, time)                   │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│          5. LEARNING UPDATE (Feedback Loop)               │
│  Record execution:                                         │
│  - Task embedding → VectorDB                              │
│  - Strategy + outcome → Learning DB                       │
│  - AI reactions → Reaction DB                             │
│  - Update tuning parameters                               │
│                                                            │
│  System is now SMARTER for next security audit!          │
└────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. AI Reaction Learning

**WHY**: Final outcomes don't tell the full story. AI confidence during execution predicts quality.

**WHAT TO TRACK**:
```javascript
{
  "agent_id": "wkr_opus_001",
  "model": "opus",
  "task_type": "security-audit",
  "reactions": {
    "confidence_markers": [
      {"text": "I'm highly confident", "position": 45, "sentiment": "high"},
      {"text": "This is definitely", "position": 120, "sentiment": "high"}
    ],
    "uncertainty_markers": [
      {"text": "possibly", "position": 200, "sentiment": "low"},
      {"text": "I'm not certain", "position": 350, "sentiment": "low"}
    ],
    "self_corrections": [
      {"text": "Actually, on second thought", "position": 500}
    ],
    "time_to_first_token_ms": 1200,  // Hesitation = uncertainty
    "avg_token_interval_ms": 45,
    "total_tokens": 2500,
    "verbosity_ratio": 2.1  // tokens / expected_length
  },
  "final_quality": 0.94,
  "user_rating": 5
}
```

**HOW TO USE**:
- **High confidence + high quality** → Trust this model for similar tasks
- **Low confidence + low quality** → Avoid this model for similar tasks
- **High confidence + low quality** → Model overconfident, needs calibration
- **Long hesitation** → Task is ambiguous, use more workers

**LEARNING**:
```sql
-- Find models with best confidence calibration
SELECT model, 
       AVG(confidence) as avg_confidence,
       AVG(quality) as avg_quality,
       ABS(AVG(confidence) - AVG(quality)) as calibration_error
FROM executions
WHERE task_type = 'security-audit'
GROUP BY model
ORDER BY calibration_error ASC;

-- Result: Opus has 0.03 calibration error (excellent)
--         Haiku has 0.15 calibration error (overconfident)
```

---

### 2. VectorDB Integration

**WHY**: Tasks are natural language. "Audit code for bugs" is similar to "Find security issues" but keyword matching won't find it.

**WHAT TO EMBED**:
```javascript
{
  "task_id": "exec_20260613_001",
  "embedding": [0.123, -0.456, 0.789, ...],  // 1536-dim vector
  "metadata": {
    "task_description": "Audit this code for security vulnerabilities",
    "task_type": "security-audit",
    "directory": "/home/sfloess/project-x",
    "file_count": 45,
    "complexity": "high",
    "strategy_used": "adversarial-3-worker",
    "models_used": ["opus", "gemini", "sonnet"],
    "final_quality": 0.95,
    "total_cost": 23400,
    "total_time_sec": 67,
    "user_rating": 5,
    "timestamp": "2026-06-13T10:30:00Z"
  }
}
```

**HOW TO QUERY**:
```javascript
// User asks: "Review this PR for security issues"
const embedding = await embed("Review this PR for security issues")

const similar = await vectordb.search({
  embedding,
  top_k: 5,
  filter: {
    task_type: "security-audit",
    final_quality: { $gte: 0.85 }  // Only high-quality past executions
  }
})

// Returns: 5 similar security audits with quality >= 0.85
// Extract common patterns:
const learnedStrategy = {
  models: mostCommon(similar.map(s => s.metadata.models_used)),
  avg_cost: mean(similar.map(s => s.metadata.total_cost)),
  success_rate: similar.length / total_security_audits
}
```

**BENEFITS**:
- **Semantic matching**: Finds similar tasks regardless of wording
- **Quality filtering**: Learn from successes, not failures
- **Context-aware**: Can filter by directory, file count, complexity
- **Fast**: Vector search is O(log n), not O(n) like SQL scans

---

### 3. Model Lifecycle Management

**WHY**: Models change. New versions launch. Old ones deprecated. Tuning data must adapt.

#### Scenario 1: Model Update (opus-4.6 → opus-4.7)

**PROBLEM**: Do we keep old tuning or start fresh?

**SOLUTION - Transfer Learning with Decay**:
```javascript
// When opus-4.7 launches:
1. Copy opus-4.6 tuning data → opus-4.7 with confidence=0.5
2. As opus-4.7 executes, blend old + new data:
   
   tuned_param = (old_param * old_confidence * old_count + 
                  new_param * new_count) / (old_count + new_count)
   
3. After 20 opus-4.7 executions, old data decays to 20% influence
4. After 50 executions, old data decays to 5% influence

// Example:
opus-4.6: temperature=0.2 (100 executions, quality=0.90)
opus-4.7: temperature=0.3 (5 executions, quality=0.95)

Blended temp = (0.2 * 0.5 * 100 + 0.3 * 5) / (100 + 5)
             = (10 + 1.5) / 105
             = 0.11 initially, shifts toward 0.3 as more opus-4.7 data arrives
```

**WHY THIS WORKS**:
- ✅ Don't lose valuable opus-4.6 knowledge
- ✅ Don't blindly assume opus-4.7 behaves identically
- ✅ Gradual transition as new evidence accumulates
- ✅ Bad old data gets overridden by good new data

#### Scenario 2: New Model (fable-5 launches)

**PROBLEM**: No tuning data exists.

**SOLUTION - Bootstrap from Similar Models**:
```javascript
// Fable-5 is in the "large, powerful" class like Opus
// Bootstrap from Opus tuning:

fable5_initial_tuning = {
  temperature: opus_tuning.temperature,  // Start with Opus defaults
  top_p: opus_tuning.top_p,
  confidence: 0.3,  // Low confidence = eager to learn
  source: "bootstrapped_from_opus"
}

// After first execution, blend bootstrap + real data
// After 10 executions, bootstrap influence drops to 10%
```

#### Scenario 3: Model Removed (haiku-3.5 deprecated)

**SOLUTION - Archive, Don't Delete**:
```sql
-- Move to archive table
INSERT INTO model_tuning_archive 
SELECT *, NOW() as archived_at, 'deprecated' as reason
FROM model_tuning 
WHERE model = 'haiku-3.5';

-- Keep for historical analysis:
-- "How did haiku-3.5 performance compare to haiku-4.0?"
```

#### Scenario 4: Local Model Downloaded (ollama-qwen-2.5-coder)

**SOLUTION - Detect Parameter Compatibility**:
```javascript
// Ollama models may not support temperature
const model_schema = await detectParameters('ollama-qwen-2.5-coder')
// Returns: {supports_temperature: false, supports_top_k: true, ...}

// Initialize with compatible defaults only
ollama_qwen_tuning = {
  top_k: 40,  // Supported
  repeat_penalty: 1.1,  // Supported
  // temperature: NOT included (not supported)
  confidence: 0.1,  // Very low = learn aggressively
  source: "local_model_defaults"
}
```

---

### 4. Comprehensive Integration

**ALL AI utilities working together**:

| Component | Role | Learning Integration |
|-----------|------|---------------------|
| **VectorDB** | Find similar tasks | Embeddings updated after each execution |
| **Learning DB** | Store execution history | Queries inform strategy design |
| **Multi-AI** | Execute strategy | Reactions tracked, outcomes recorded |
| **Model Compliance** | Enforce path restrictions | Filters available models before learning query |
| **Circuit Breaker** | Track health | Unhealthy models excluded from learning recommendations |
| **Fleet Dispatcher** | Route to servers | Server performance feeds into capacity learning |
| **Parameter Tuner** | Optimize configs | Auto-adjusted based on quality outcomes |
| **Workflow Engine** | Orchestrate | Execution traces stored for analysis |

**Data Flow Example**:
```
User: "Audit code for security"
  ↓
Model Compliance: Filter to allowed models [opus, sonnet, haiku, gemini]
  ↓
VectorDB: Embed task → Find 5 similar past audits
  ↓
Learning DB: Query past audits → Extract: opus+gemini best, temp=0.2 optimal
  ↓
Circuit Breaker: Check health → gemini unhealthy, exclude
  ↓
Meta-AI: Design strategy → Use opus+sonnet (gemini excluded), temp=0.2
  ↓
Fleet Dispatcher: Route opus→server-02, sonnet→server-03
  ↓
Execution: Track reactions (opus confident, sonnet uncertain)
  ↓
Outcome: Quality=0.96, cost=18k, time=52s
  ↓
Feedback Loop:
  - VectorDB: Store embedding + metadata
  - Learning DB: Update opus+sonnet stats (now 0.955 avg quality)
  - Parameter Tuner: Confirm temp=0.2 still optimal
  - Reaction DB: Record opus high confidence correlated with high quality
```

---

## WHY/HOW Documentation Patterns

### Pattern 1: Problem-First Framing

**BAD** (feature list):
```
The system uses VectorDB for task similarity matching.
```

**GOOD** (problem → solution):
```
**WHY**: Tasks described as "Audit code for bugs" and "Find security issues" 
are semantically similar but keyword matching won't find them.

**HOW**: Embed task descriptions into 1536-dim vectors, use cosine similarity 
to find past executions with similar semantic meaning. Threshold=0.85 for 
"very similar", 0.70 for "somewhat similar".

**EXAMPLE**: "Review PR" finds past "Code review", "Audit changes", "Check diff" 
tasks even though exact words differ.
```

### Pattern 2: Depth Levels

**Level 1 - Quick Understanding**:
```
Learning system finds similar past tasks and reuses successful strategies.
```

**Level 2 - Algorithm Detail**:
```
1. Embed current task description
2. Vector search for top-5 similar (cosine similarity > 0.85)
3. Extract common patterns (models used, parameters, success rate)
4. Meta-AI designs strategy informed by patterns
5. Execute and record outcome
```

**Level 3 - Code Pointers**:
```
Implementation:
- Embedding: shared/vectordb.js:45-67
- Similarity search: shared/vectordb.js:89-120
- Pattern extraction: learning/extract-patterns.js:23-89
- Meta-AI integration: orchestrator.js:156-234
```

### Pattern 3: Decision Rationale

**Include WHY decisions were made**:
```
**Q: Why VectorDB instead of SQL keyword search?**

A: SQL LIKE queries miss semantic similarity:
   - "Audit code" won't match "Review software"
   - "Find bugs" won't match "Detect issues"
   - VectorDB captures meaning, not just words

Tested: VectorDB found 87% of relevant past tasks vs 34% for SQL LIKE.
```

---

## Implementation Status

### ✅ COMPLETED
- Model compliance (path restrictions)
- Fleet dispatcher (capacity-based routing)
- Multi-AI arbiter/worker pattern
- Circuit breaker (health tracking)

### 🏗️ IN PROGRESS
- Server-side model awareness (design complete, implementing)
- Learning architecture (design phase)

### 📋 PLANNED
- AI reaction tracking
- VectorDB integration
- Model lifecycle management
- Parameter auto-tuning
- Comprehensive documentation

---

## Next Steps

1. **Complete server-side model awareness** (recommendations from workflow wxmgezcwm)
2. **Implement learning database schema** (SQLite tables)
3. **Integrate VectorDB** (embeddings + similarity search)
4. **Add reaction tracking** (confidence, hesitation, corrections)
5. **Build auto-tuner** (parameter optimization)
6. **Update all documentation** (WHY/HOW emphasis)
7. **Deploy and observe** (system learns from real usage)

---

**Last Updated**: 2026-06-13  
**Next Review**: After comprehensive design workflow completes (w06cftrrx)
