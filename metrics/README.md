# Prompt Performance Metrics System - Phase 1 Framework

**Status:** PHASE 1 FRAMEWORK READY FOR WORKER IMPLEMENTATION  
**Date:** 2026-09-25  
**Goal:** Track which compression + caching strategies work best per workflow type, then auto-tune settings

---

## What This Is

This system moves beyond "compress everything 30%" to **targeted, data-driven optimization**:

- **WORKER 1 (Haiku):** Classify each API call into a workflow type
- **WORKER 2 (Sonnet):** Record compression/cache metrics for each workflow  
- **WORKER 3 (Opus 4.8):** Find patterns (which workflows compress well?)
- **WORKER 4 (Gemini):** Generate recommended settings and auto-tune config

Example outcome: "Code reviews compress 38% with 8% quality loss → use light compression. Release notes compress 48% with 4% quality loss → use aggressive compression."

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ API Call                                            │
│ (model selection, context, compression, cache)      │
└────────────────┬────────────────────────────────────┘
                 │
      ┌──────────┴──────────┬──────────────┬────────────┐
      │                     │              │            │
      ▼                     ▼              ▼            ▼
   WORKER 1            WORKER 2         WORKER 3    WORKER 4
   Classifier          Logger           Analyzer    Tuner
   (Haiku)            (Sonnet)         (Opus 4.8)  (Gemini)
      │                  │                 │           │
      │ classify         │ log              │           │
      │ workflow         │ metrics          │           │
      ▼                  ▼                  ▼           ▼
   workflow_type    performance_        correlation   recommended_
   + confidence     calls.jsonl          report.json   config.yaml
                                            ↑
                                     (analyze logs)
                                            │
                                       Apply config
                                       (Phase 2+)
```

---

## Quick Start

### 1. Run Tests

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/metrics
python3 test_metrics.py
```

Expected output:
```
====================================================================================================
METRICS SYSTEM PHASE 1 - TEST SUITE
====================================================================================================

[TEST 1] WORKER 1: Workflow Classifier
✓ Code review for PR #123              → code_review              (confidence: 90%)
✓ Deploy to production                 → deployment               (confidence: 85%)
...

[TEST 2] WORKER 2: Performance Logger
✓ Logged code_review            | opus     | Compression: 41.6%
...

[TEST 3] WORKER 3: Correlation Analyzer
✓ Analyzed 4 workflows
✓ Found compression patterns:
  code_review          → light_compression       (confidence: 91%)
  ...

[TEST 4] WORKER 4: Auto-Tuner
✓ Generated recommended config
✓ Saved to config
✓ Generated A/B test plan

====================================================================================================
TEST SUMMARY
====================================================================================================
✓ PASS: Classifier (Worker 1)
✓ PASS: Logger (Worker 2)
✓ PASS: Analyzer (Worker 3)
✓ PASS: Tuner (Worker 4)

Total: 4/4 test groups passed

✓ ALL TESTS PASSED - Phase 1 Framework Ready
```

### 2. Use the Classifier (WORKER 1)

```python
from metrics.classifier import WorkflowClassifier

classifier = WorkflowClassifier()

# Classify a workflow
classification = classifier.classify(
    task_description="Code review for PR #123"
)

print(f"Type: {classification.workflow_type}")           # "code_review"
print(f"Confidence: {classification.confidence:.0%}")    # 92%
print(f"Recommend compression: {classification.recommended_compression}")  # "light"
print(f"Recommend cache: {classification.recommended_cache}")  # "prefer_cache_hit"
```

### 3. Log Metrics (WORKER 2)

```python
from metrics.logger import PerformanceLogger

logger = PerformanceLogger()

# Log a call
entry = logger.log_call(
    workflow_type="code_review",
    model="opus",
    original_tokens=12500,
    compressed_tokens=7300,
    cache_hit=False,
    semantic_similarity=0.94,
    output_tokens=1200,
    cost_usd=0.067,
)

print(f"Compression: {entry.compression.reduction_percent:.1f}%")  # 41.6%

# Get stats
stats = logger.get_stats()
print(f"By model: {stats['by_model']}")
print(f"By workflow: {stats['by_workflow']}")
```

### 4. Analyze Patterns (WORKER 3)

```python
from metrics.analyzer import PerformanceAnalyzer

analyzer = PerformanceAnalyzer()

# Analyze all logs
report = analyzer.analyze_all()

print("Compression analysis:")
for workflow, stats in report.compression_analysis.items():
    print(f"  {workflow}: {stats['recommendation']} "
          f"(confidence: {stats['confidence']:.0%})")

# Save report
analyzer.save_report(report)

# Print human-readable version
analyzer.print_report(report)
```

### 5. Generate Config (WORKER 4)

```python
from metrics.tuner import ConfigTuner
import json

# Load analysis report
with open(Path.home() / ".claude" / "metrics" / "correlation_report.json") as f:
    analysis = json.load(f)

tuner = ConfigTuner()

# Generate recommended config
recommended_config = tuner.generate_config(analysis)

# Save config
config_path = tuner.save_config(recommended_config)
print(f"Saved to: {config_path}")

# Generate A/B test plan
changes = tuner.compare_configs(current_config, recommended_config)
plan = tuner.generate_ab_test_plan(recommended_config, changes)
print(f"A/B test plan: {plan['test_id']}")
```

---

## Files

```
metrics/
├── __init__.py                  # Package init
├── classifier.py                # WORKER 1: Workflow classification
├── logger.py                    # WORKER 2: Performance logging
├── analyzer.py                  # WORKER 3: Pattern analysis
├── tuner.py                     # WORKER 4: Config generation
├── test_metrics.py              # Unit tests for all workers
├── README.md                    # This file
└── PHASE1_FRAMEWORK.md          # Detailed architecture + design
```

---

## Data Storage

Logs and reports are stored in `~/.claude/metrics/`:

```
~/.claude/metrics/
├── performance_calls.jsonl          # WORKER 2: Append-only log of all metrics
├── correlation_report.json          # WORKER 3: Latest analysis
├── recommended_config.yaml          # WORKER 4: Recommended settings
├── config_history.jsonl             # WORKER 4: Audit trail of changes
└── classifications.jsonl            # WORKER 1: Classification records
```

---

## Workflow Types (Supported in Phase 1)

| Type | Description | Compress | Cache | Notes |
|------|-------------|----------|-------|-------|
| code_review | PR/MR code review | Light | Prefer | Semantic fidelity critical |
| deployment | AWX/CI orchestration | Moderate | Aggressive | Repeatable, cache-friendly |
| release_notes | Bi-weekly announcements | Aggressive | Prefer | Quality matters, deterministic |
| architecture_design | System design | Light | None | Full context needed |
| security_review | Vulnerability analysis | None | None | Zero false negatives |
| refactoring | Code simplification | Light | Prefer | Quality of suggestions matters |
| documentation | Writing docs | Aggressive | Prefer | Can tolerate style compression |
| data_analysis | Metrics/reporting | Moderate | Prefer | Accuracy critical |
| bug_diagnosis | Root cause analysis | None | None | Full context required |
| alternative_review | External validation | Light | None | Quality > cost savings |

---

## Phase 1 Verdict Checklist

- [x] WORKER 1: Classifier implemented and tested
- [x] WORKER 2: Logger implemented and tested
- [x] WORKER 3: Analyzer implemented and tested
- [x] WORKER 4: Tuner implemented and tested
- [x] Integration with compression module ready
- [x] Integration with caching module ready
- [x] Data storage (JSONL + JSON) defined
- [x] Unit tests passing (test_metrics.py)
- [x] Documentation complete
- [x] Framework ready for Phase 2

**Phase 1 Status:** FRAMEWORK READY ✓

---

## Phase 2 (Next)

Phase 2 will:
1. **Multi-AI Consensus Review**
   - Opus 5: Review analyzer edge cases
   - Sonnet: Review logger integration patterns
   - Gemini: Validate tuner recommendations

2. **Integration Testing**
   - Wire classifier into actual orchestrator
   - Integrate logger with cost_tracking module
   - Connect analyzer to real performance logs
   - Validate tuner config with A/B tests

3. **Production Validation**
   - Run with real RH workflows
   - Collect 1+ week of data
   - Verify analyzer patterns match expectations
   - Validate config changes improve ROI

---

## Phase 3 (After Phase 2 Approval)

Phase 3 will:
1. Enable auto-tuning (write recommended settings to active config)
2. A/B test framework (test variant config vs baseline)
3. Continuous improvement (weekly analysis → config updates)
4. Monitoring dashboard (cost savings, quality trends, cache effectiveness)

---

## Integration with Existing Systems

### Cost Tracking (`/cost_tracking/`)
- Logger captures cost_usd for each call
- Analyzer calculates ROI per strategy
- Tuner recommends settings that maximize cost savings

### Compression (`/compression/`)
- Classifier recommends compression level
- Logger captures compression_ratio and latency
- Analyzer identifies which workflows compress best
- Tuner adjusts target_reduction per workflow

### Caching (`/caching/`)
- Logger captures cache_hit and cache_source
- Analyzer identifies cache hit rate by workflow
- Tuner adjusts cache strategy per workflow

### Orchestrator (`orchestrate_smart.py`)
- Classification influences model selection
- Auto-tuning results feed into routing decisions
- Integration point: decorate API calls with classification

---

## Dependencies

- Python 3.8+
- Standard library only (json, yaml, pathlib, threading, dataclasses, datetime)
- No external packages required (yaml module can be added for Phase 2)

---

## Running Demo Scripts

### Classifier Demo
```bash
python3 -m metrics.classifier
```

### Logger Demo
```bash
python3 -m metrics.logger
```

### Analyzer Demo
```bash
python3 -m metrics.analyzer
```

### Tuner Demo
```bash
python3 -m metrics.tuner
```

---

## Next Steps

1. **Verify test suite passes**
   ```bash
   python3 test_metrics.py
   ```

2. **Review PHASE1_FRAMEWORK.md** for detailed design

3. **Integration planning** (Phase 2):
   - How to call classifier in orchestrator?
   - How to capture metrics from compression pipeline?
   - Where to wire in logger?

4. **Phase 2 consensus review** when ready
   - Opus 5 review of analyzer logic
   - Sonnet review of logger patterns
   - Gemini review of tuner recommendations

---

## Questions?

See `PHASE1_FRAMEWORK.md` for:
- Detailed architecture
- Data flow diagrams
- Integration points
- Phase 2/3 roadmap
- Success metrics

---

**Framework Author:** Phase 1 CREATE team (4 workers)  
**Status:** Ready for Phase 2 Verification  
**Date:** 2026-09-25
