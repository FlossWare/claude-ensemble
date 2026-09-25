# Phase 1 CREATE - Prompt Performance Metrics Framework
## Adaptive Compression/Caching Tuning System

**Date:** 2026-09-25  
**Status:** FRAMEWORK READY FOR WORKER IMPLEMENTATION  
**Goal:** Track which compression + caching strategies work best per workflow type  

---

## Executive Summary

Phase 1 creates the infrastructure to **measure and auto-tune compression/caching settings by workflow type**. This moves beyond blanket 30% compression to **targeted, data-driven optimization**: aggressive compression for workflows that tolerate it, light compression for those that don't.

**What We're Building:**
- WORKER 1: Classify each API call into a workflow type (release notes, code review, deployment, etc)
- WORKER 2: Log compression/cache effectiveness metrics for each workflow
- WORKER 3: Analyze patterns to find correlations (which workflows compress well?)
- WORKER 4: Generate recommended settings and auto-tune configuration

**Why This Matters:**
- Compression doesn't work equally across all workflows
- Some workflows need semantic fidelity (security reviews), others tolerate lossy compression (documentation)
- Cache hit rate varies dramatically by workflow type
- Current compression is one-size-fits-all; Phase 1 enables targeted tuning

---

## 4-Worker Pipeline

### WORKER 1 (Haiku) - Workflow Classifier
**Role:** Identify and tag workflow type for every API call

**Input:** API call metadata
- Model used
- Task description or prompt snippet
- Context size
- Compression/cache flags

**Output:** Workflow classification
```json
{
  "call_id": "abc123",
  "workflow_type": "code_review",
  "confidence": 0.92,
  "characteristics": ["code_analysis", "consensus_required", "security_critical"],
  "recommended_compression": "light",
  "recommended_cache": "prefer_cache_hit"
}
```

**Workflow Categories (Initial):**
- `release_notes` - Bi-weekly announcements (high documentation quality needed)
- `code_review` - Bug/feature reviews (semantic fidelity critical)
- `deployment` - AWX/CI orchestration (deterministic, repeatable)
- `architecture_design` - System design (comprehensive understanding needed)
- `security_review` - Vulnerability analysis (zero false negatives)
- `refactoring` - Code simplification (quality of suggestions matters)
- `documentation` - Writing docs (can tolerate style compression)
- `data_analysis` - Metrics/reporting (accuracy critical, tokens less so)
- `bug_diagnosis` - Finding root causes (requires full context)
- `alternative_review` - External validation (quality > cost savings)

**Implementation:** `/metrics/classifier.py` (~200 LOC)
- Rules-based + simple heuristics (no ML needed)
- Pattern matching on task name, context size, model choice
- Confidence scores
- Extensible for new workflow types

---

### WORKER 2 (Sonnet) - Performance Logger
**Role:** Capture compression/cache metrics for each workflow

**Input:** Completed API call + post-processing results
- Original tokens (pre-compression)
- Compressed tokens (post-compression)
- Cache hit/miss
- Cache source (prompt_cache, redis, memory, none)
- Quality metrics (if available: test pass rate, semantic similarity, cost savings)
- Latency impact (compression time overhead)

**Output:** Detailed performance log
```json
{
  "call_id": "abc123",
  "timestamp": "2026-09-25T10:30:45Z",
  "workflow_type": "code_review",
  "model": "opus",
  "compression": {
    "original_tokens": 12500,
    "compressed_tokens": 7300,
    "reduction_percent": 41.6,
    "method": "hierarchical_summarizer",
    "latency_ms": 45
  },
  "cache": {
    "is_hit": true,
    "source": "prompt_cache",
    "cache_tokens_used": 6800,
    "cache_creation_tokens": 0,
    "cache_read_tokens": 0
  },
  "quality": {
    "test_pass_rate": 1.0,
    "semantic_similarity": 0.94,
    "output_tokens": 2100,
    "cost_usd": 0.067
  }
}
```

**Storage:** Append-only JSONL at `~/.claude/metrics/performance_calls.jsonl`
- Thread-safe writes
- Full audit trail
- Queryable for Phase 3 analysis

**Implementation:** `/metrics/logger.py` (~250 LOC)
- Mirrors cost_tracking/logger.py pattern
- Integrates with compression module
- Integrates with cache system
- Records workflow context

---

### WORKER 3 (Opus 4.8) - Correlation Analyzer
**Role:** Find patterns in which workflows benefit from compression/caching

**Input:** Aggregated performance logs from Worker 2
- Per-workflow metrics (compression reduction %, cache hit rate, quality impact)
- Latency impact per workflow
- Cost savings per strategy

**Output:** Correlation analysis report
```json
{
  "period": "2026-09-25",
  "workflows_analyzed": 10,
  "compression_analysis": {
    "by_workflow": {
      "code_review": {
        "avg_reduction_percent": 38.2,
        "quality_impact": -0.08,
        "latency_impact_ms": 52,
        "recommendation": "light_compression",
        "confidence": 0.91
      },
      "release_notes": {
        "avg_reduction_percent": 48.1,
        "quality_impact": -0.04,
        "latency_impact_ms": 38,
        "recommendation": "aggressive_compression",
        "confidence": 0.87
      },
      "security_review": {
        "avg_reduction_percent": 22.3,
        "quality_impact": -0.15,
        "latency_impact_ms": 28,
        "recommendation": "no_compression",
        "confidence": 0.94
      }
    }
  },
  "cache_analysis": {
    "by_workflow": {
      "deployment": {
        "avg_hit_rate": 0.72,
        "tokens_saved_per_hit": 8400,
        "recommendation": "aggressive_caching",
        "confidence": 0.89
      },
      "code_review": {
        "avg_hit_rate": 0.18,
        "tokens_saved_per_hit": 4200,
        "recommendation": "light_caching",
        "confidence": 0.82
      }
    }
  },
  "latency_impact": {
    "compression_only": 42,
    "caching_only": 8,
    "combined": 50,
    "recommendation": "latency_acceptable_for_savings"
  }
}
```

**Key Findings:**
- Which workflows compress best (highest reduction + lowest quality impact)
- Which workflows benefit most from caching
- Latency tradeoffs per strategy
- Quality thresholds (red line: stop compressing when quality drops >20%)
- Cost-benefit ratio per workflow

**Implementation:** `/metrics/analyzer.py` (~300 LOC)
- Aggregates logs by workflow type
- Computes correlations (compression ↔ quality)
- Detects anomalies (this workflow suddenly compresses worse)
- Confidence scoring for recommendations
- Outputs JSON + human-readable report

---

### WORKER 4 (Gemini) - Auto-Tuner
**Role:** Generate recommended settings per workflow type and update config dynamically

**Input:** Analyzer correlation report + current settings

**Output:** 
1. Recommended config file (YAML/JSON)
2. Auto-tuning script that updates settings
3. Rollback plan if changes degrade performance

**Recommended Config Structure:**
```yaml
compression:
  default:
    enabled: true
    method: "hierarchical_summarizer"
    target_reduction: 0.35
    quality_threshold: 0.10  # stop if quality drops >10%

  by_workflow:
    code_review:
      enabled: true
      method: "hierarchical_summarizer"
      target_reduction: 0.25  # conservative
      quality_threshold: 0.08
      
    release_notes:
      enabled: true
      method: "hierarchical_summarizer"
      target_reduction: 0.50  # aggressive
      quality_threshold: 0.12
      
    security_review:
      enabled: false  # don't compress
      
    deployment:
      enabled: true
      method: "hierarchical_summarizer"
      target_reduction: 0.40
      quality_threshold: 0.15  # deterministic, can tolerate more

cache:
  default:
    enabled: true
    prefer_cache_hit: true
    ttl_seconds: 3600
    
  by_workflow:
    deployment:
      enabled: true
      prefer_cache_hit: true
      ttl_seconds: 7200  # longer TTL, deployment contexts are stable
      
    code_review:
      enabled: true
      prefer_cache_hit: false  # cache isn't helping much
      ttl_seconds: 1800
      
    alternative_review:
      enabled: true
      prefer_cache_hit: false  # external reviews are unique
      ttl_seconds: 600
```

**Auto-Tuning Script:**
- Reads analyzer output
- Compares with current settings
- Suggests changes with confidence > 0.85
- Updates config file
- Adds rollback marker (if A/B test regresses, revert)
- Logs all changes to audit trail

**Implementation:** `/metrics/tuner.py` (~250 LOC)
- Reads JSON from analyzer
- Generates YAML config
- Implements A/B test framework
- Rollback detection
- Change logging and audit trail

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ API CALL EXECUTION                                              │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ├─→ WORKER 1 (Haiku Classifier)
               │   "Is this code_review or deployment?"
               │   Output: workflow_type, recommended_compression
               │
               ├─→ WORKER 2 (Sonnet Logger)
               │   "Record: tokens, cache hit, quality, latency"
               │   Output: /metrics/performance_calls.jsonl
               │
               ├─→ WORKER 3 (Opus Analyzer)  [Periodic - daily/weekly]
               │   "Analyze all logs, find patterns"
               │   Output: /metrics/correlation_report.json
               │
               └─→ WORKER 4 (Gemini Tuner)    [Periodic - weekly]
                   "Generate recommended settings"
                   Output: /metrics/recommended_config.yaml
                   Auto-update: /config/compression.yaml
```

---

## Storage Structure

```
~/.claude/metrics/
├── performance_calls.jsonl          # Worker 2 output (append-only log)
├── daily_summary_2026-09-25.json    # Worker 3 aggregation (daily)
├── weekly_summary_2026-w39.json     # Worker 3 aggregation (weekly)
├── correlation_report.json          # Worker 3 analysis (latest)
├── recommended_config.yaml          # Worker 4 suggestions
├── config_history.json              # Audit trail of config changes
└── tuning_results/                  # A/B test results
    ├── baseline_2026-09-25.json
    ├── variant_a_2026-09-26.json
    └── variant_b_2026-09-27.json
```

---

## Integration Points

### With Cost Tracking (`/cost_tracking/`)
- Logger logs cost_usd for each call
- Analyzer calculates ROI: "saving X% tokens at Y% quality drop = Z% cost savings"
- Tuner recommends settings that maximize cost savings per workflow

### With Compression (`/compression/`)
- Classifier recommends compression level
- Logger captures compression_ratio and latency
- Analyzer identifies which workflows compress well
- Tuner adjusts target_reduction per workflow

### With Caching (`/caching/`)
- Logger captures cache_hit and cache_source
- Analyzer identifies cache hit rates by workflow
- Tuner adjusts cache strategy per workflow

### With Orchestrator (`orchestrate_smart.py`)
- Each API call gets classified by Worker 1
- Classification influences model selection (don't use cheap model for security reviews)
- Auto-tuning results fed back into routing decision

---

## Phase 1 Readiness Checklist

| Component | Description | LOC | Status |
|-----------|-------------|-----|--------|
| WORKER 1 - Classifier | Identify workflow type per call | ~200 | READY |
| WORKER 2 - Logger | Record compression/cache metrics | ~250 | READY |
| WORKER 3 - Analyzer | Correlate workflows with effectiveness | ~300 | READY |
| WORKER 4 - Tuner | Auto-generate config recommendations | ~250 | READY |
| Aggregator | Daily/weekly summaries | ~200 | READY |
| Tests | Unit + integration tests | ~300 | READY |
| Documentation | Usage guides, examples | ~200 | READY |
| **Total Production Code** | | **~1,700** | **FRAMEWORK READY** |

---

## Phase 1 Verdict Criteria

**READY FOR PHASE 2 when:**
- ✅ All 4 workers implemented and tested
- ✅ Integration with compression/caching modules verified
- ✅ Performance logs being collected
- ✅ Daily/weekly reports generating
- ✅ Config recommendations appearing in recommended_config.yaml
- ✅ At least 1 week of data collected for analysis
- ✅ All tests passing

**Phase 2:** Multi-AI consensus review + production validation
- Opus 5: Review analyzer edge cases
- Sonnet: Review logger integration
- Gemini: Review tuner recommendations
- User: Validate 1st auto-tuned config change

**Phase 3:** Production deployment
- Auto-tuning activated
- A/B testing framework enabled
- Continuous improvement loop running

---

## Next Steps

1. **WORKER 1 (Haiku):** Implement classifier.py
   - Define workflow categories
   - Rules-based classification
   - Confidence scoring

2. **WORKER 2 (Sonnet):** Implement logger.py
   - Mirror cost_tracking/logger.py pattern
   - Capture all metrics
   - Thread-safe JSONL writes

3. **WORKER 3 (Opus 4.8):** Implement analyzer.py
   - Aggregate logs by workflow
   - Compute correlations
   - Generate reports

4. **WORKER 4 (Gemini):** Implement tuner.py
   - Parse analyzer output
   - Generate YAML config
   - Implement A/B test framework

5. **Integration:** Wire into orchestrate_smart.py
   - Call classifier on each API call
   - Call logger for metrics
   - Use recommended_config.yaml for settings

6. **Testing:** Full test suite
   - Unit tests per worker
   - Integration tests
   - Data consistency checks

---

## Success Metrics for Phase 1

- [ ] Classifier: >90% accuracy on workflow type
- [ ] Logger: 100% of API calls captured with all metrics
- [ ] Analyzer: Identifies at least 3 workflows with different compression/caching profiles
- [ ] Tuner: Generates config with >85% confidence recommendations
- [ ] Cost tracking: ROI analysis shows X% cost savings possible
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Ready for Phase 2 consensus review

---

**Framework Status:** READY FOR WORKER IMPLEMENTATION  
**Estimated Timeline:** 2-3 days (parallel worker execution)  
**Next Approval Gate:** Phase 1 completion before Phase 2 consensus review
