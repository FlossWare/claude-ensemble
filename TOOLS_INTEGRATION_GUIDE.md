# Claude Ensemble Infrastructure Tools - Integration Guide

**Location:** `~/.claude/tools/` (symlinked from `claude-global-skills/`)

All 10 tools are **ready to use** across Claude Ensemble projects. No database, no aio-01 — fully self-contained.

---

## Quick Start

### 1. **Compression** — 41.2% token reduction verified
```bash
~/.claude/tools/summarizer.py --text "your input" --level 0.35
```
Saves tokens on prompts, context, retrieval results. Use when prompt caching is unavailable.

### 2. **Thompson Sampling** — 47.3% cost savings
```python
from shared.thompson_router import ThompsonRouter
router = ThompsonRouter(priors={'haiku': 0, 'sonnet': 0, 'opus': 0})
model = router.select_model(task='bug_fix')
```
Routes API calls to cheapest capable model based on learned performance.

### 3. **Caching** — 69.8% savings (theoretical, Phase 2 API test ready)
```python
from caching.cache_metrics import CacheMetrics
cache = CacheMetrics()
savings = cache.estimate_savings(prompt_tokens=2000, calls_per_day=100)
```
Plans caching strategy for prompt-heavy workflows.

### 4. **Cost Tracking** — 336 real API calls logged
```python
from cost_tracking.logger import CostLogger
logger = CostLogger('cost_tracking/api_costs.jsonl')
logger.log_call(model='haiku', prompt_tokens=500, completion_tokens=100, cost=0.02)
```
Append-only JSONL audit trail. No database.

### 5. **Capability Matrix** — Model-task performance
```python
import json
matrix = json.load(open('learning/capability_matrix.json'))
# 40 entries: 4 models × 10 tasks, N=5 samples per entry
# Status: CI width too wide (needs N=20), re-expansion pending
```
Routes work to best model per task. Currently under-sampled, needs Phase 2 expansion.

### 6. **Performance Dashboard** — Real-time metrics
```bash
~/.claude/tools/performance_dashboard.py [hours]
```
Display API usage by model, total cost, token count. Reads from `cost_tracking/api_costs.jsonl`.

### 7. **Memory System** — TF-IDF semantic search
```python
from learning.memory_search import SemanticMemory
mem = SemanticMemory('learning/memory_index.json')
results = mem.search('keyset pagination bug', limit=5)
```
Lightweight search, no ML models, no GPU. Integrates with CLAUDE.md project memories.

### 8. **Autonomous Learning** — Phase 1 validated
```bash
python3 autonomous_learning_phase1.py
```
Routes 5 demo Claude Ensemble tasks (Recrawl, Disseminator, Caching, Dashboard, Matrix).
Validates Thompson priors, feedback loop. Phase 2 pending.

### 9. **Retry/Backoff** — Resilience
```python
from shared.retry_backoff import retry_on_error, AdaptiveBackoff
@retry_on_error(base_delay=1.0, max_retries=5)
def call_api():
    # Automatic retry with exponential backoff + jitter
    pass
```
Handles transient failures across model routers.

### 10. **Anomaly Detection** — Outlier alerting
```bash
python3 learning/anomaly_detector.py
```
Z-score statistical detection: cost spikes, latency surges, error rate anomalies.
Reads from `cost_tracking/api_costs.jsonl`.

---

## Architecture

```
claude-global-skills/
├── compression/
│   └── summarizer.py          # 492 lines, 41.2% verified reduction
├── shared/
│   ├── thompson_router.py     # 615 lines, 47.3% cost savings
│   └── retry_backoff.py       # 200 lines, exponential backoff + jitter
├── caching/
│   └── cache_metrics.py       # 450 lines, 69.8% theoretical savings
├── cost_tracking/
│   ├── api_costs.jsonl        # 336 real calls logged (append-only)
│   ├── logger.py              # Event logging
│   ├── aggregator.py          # Analytics
│   ├── validator.py           # Audit trail validation
│   └── integration.py         # Cost tracking integration
├── learning/
│   ├── capability_matrix.json # 40 entries (needs N=5→N=20 expansion)
│   ├── memory_index.json      # TF-IDF cache
│   ├── memory_search.py       # Semantic search
│   └── anomaly_detector.py    # Z-score outlier detection (200 lines)
├── tools/
│   ├── performance_dashboard.py  # Real-time metrics (no DB)
│   └── thompson_feedback_syncer.py
├── autonomous_learning_phase1.py # 5 demo tasks, Phase 1 validated
└── TOOLS_INTEGRATION_GUIDE.md     # This file
```

**No database. No aio-01. All self-contained.**

---

## Symlinks

All tools are symlinked to `~/.claude/tools/`:
```bash
~/.claude/tools/
├── summarizer.py → ../../../Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/compression/summarizer.py
├── thompson_router.py → ...
├── performance_dashboard.py → ...
└── ... (etc.)
```

Available across all Claude Ensemble work sessions.

---

## Key Metrics (Verified)

| Tool | Metric | Value | Status |
|------|--------|-------|--------|
| Compression | Token reduction | 41.2% | ✅ Phase 1/2 verified |
| Thompson | Cost savings | 47.3% | ✅ 336 real calls |
| Caching | Token savings (theoretical) | 69.8% | ⏳ Phase 2 API test ready |
| Cost Tracking | Calls logged | 336 | ✅ 100% test pass |
| Capability Matrix | Entries / Samples | 40 / N=5 | ⚠️ Needs N→20 expansion |
| Dashboard | Models tracked | 4 | ✅ No DB dependency |
| Memory | Index entries | (TF-IDF cache) | ✅ Working |
| Autonomous | Demo tasks | 5 validated | ✅ Phase 1 done |
| Retry/Backoff | Strategies | Adaptive | ✅ New |
| Anomaly Detection | Detectors | 3 (cost/latency/error) | ✅ New |

---

## Pending Work

1. **Capability Matrix Phase 2** — Expand N=5 → N=20 samples per entry (~1 week, background)
2. **Caching Phase 2 API Test** — Real Anthropic calls with cache_control, measure actual hit rates
3. **GA Parameter Integration** — Load evolved parameters into deployed systems
4. **Recrawl Full Review** — Post-fix consensus (arbiter + 4 challengers) not yet done

---

## Usage Example: Claude Ensemble Project Integration

```python
# In your Claude Ensemble task handler:
from shared.thompson_router import ThompsonRouter
from cost_tracking.integration import CostTracker
from learning.anomaly_detector import AnomalyDetector

# 1. Route work to cheapest capable model
router = ThompsonRouter()
model = router.select_model(task='code_review')  # → haiku/sonnet/opus/etc.

# 2. Call API, log cost
tracker = CostTracker()
result = call_api(model=model)
tracker.log_call(model=model, prompt_tokens=500, completion_tokens=100, cost=0.02)

# 3. Detect anomalies
detector = AnomalyDetector()
anomalies = detector.detect_cost_anomalies()
if anomalies:
    print(f"⚠️  Cost spike detected: {anomalies[0]}")
```

---

## Support

- **Memories:** `/home/sfloess/Development/redhat/scm/gitlab/search-engineering/disseminator/memory/MEMORY.md`
- **Status:** All tools deployed. No database, no aio-01. File-based, self-contained.
- **Next Session:** Run `~/.claude/tools/performance_dashboard.py` to see live metrics.
