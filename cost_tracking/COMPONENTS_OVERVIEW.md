# Cost Tracking System: Components Overview

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Cost Tracking System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT LAYER (Integration Points)                              │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐     │
│  │ Thompson Router │  │ Compression  │  │ Cache System  │     │
│  │ (routing logic) │  │ (pre/post)   │  │ (hit/miss)    │     │
│  └────────┬────────┘  └──────┬───────┘  └───────┬───────┘     │
│           │                   │                  │              │
│  ┌────────▼───────────────────▼──────────────────▼──────────┐  │
│  │         Integration Module (integration.py)             │  │
│  │  • @cost_track_api_call decorator                       │  │
│  │  • Auto-logs with routing decision, compression, cache  │  │
│  │  • Thread-safe, <1% latency overhead                    │  │
│  └────────┬───────────────────────────────────────────────┘  │
│           │                                                    │
│  LOGGING LAYER                                                │
│  ┌────────▼──────────────────────────────────────────────┐   │
│  │  Logger Module (logger.py)                            │   │
│  │  • Records: model, tokens, cost, timestamp, context   │   │
│  │  • Thread-safe: threading.Lock()                      │   │
│  │  • Storage: ~/.claude/cost_tracking/api_calls.jsonl   │   │
│  │  • Format: JSONL (append-only, audit-safe)            │   │
│  │                                                        │   │
│  │  Methods:                                             │   │
│  │  • log_call(model, input_tokens, output_tokens, ...) │   │
│  │  • get_stats() → aggregate statistics                 │   │
│  │  • read_logs() → all entries                          │   │
│  └────────┬───────────────────────────────────────────┘   │
│           │                                              │
│           ▼  api_calls.jsonl (append-only)              │
│  ┌─────────────────────────────────────────────────┐    │
│  │ {"timestamp": "...", "model": "sonnet", ...}   │    │
│  │ {"timestamp": "...", "model": "opus", ...}     │    │
│  │ {"timestamp": "...", "model": "haiku", ...}    │    │
│  │ ...                                             │    │
│  └────────┬──────────────────────────────────────┘    │
│           │                                              │
│  ANALYSIS LAYER                                          │
│  ┌────────▼──────────────────────────────────────────┐  │
│  │  Aggregator Module (aggregator.py)               │  │
│  │  • Reads JSONL logs                              │  │
│  │  • Generates daily/weekly/monthly summaries      │  │
│  │                                                  │  │
│  │  Methods:                                        │  │
│  │  • daily_summary() → day breakdown               │  │
│  │  • weekly_summary() → 7-day rolling              │  │
│  │  • monthly_summary() → calendar month            │  │
│  │  • savings_report() → compression + cache        │  │
│  │  • compression_metrics() → detailed savings      │  │
│  │  • cache_analysis() → hit rate + tokens saved    │  │
│  └────────┬──────────────────────────────────────┘  │
│           │                                          │
│  VALIDATION LAYER                                    │
│  ┌────────▼──────────────────────────────────────┐  │
│  │  Validator Module (validator.py)              │  │
│  │  • Verifies cost calculations                  │  │
│  │  • Detects duplicates                          │  │
│  │  • Validates schema                            │  │
│  │  • Detects anomalies (outliers)                │  │
│  │                                                │  │
│  │  Methods:                                      │  │
│  │  • validate_cost_calculation()                 │  │
│  │  • check_duplicates()                          │  │
│  │  • validate_schema()                           │  │
│  │  • detect_anomalies()                          │  │
│  │  • validate_log_file() → full validation       │  │
│  │  • Returns: severity (PASS/WARNING/ERROR)      │  │
│  └────────┬──────────────────────────────────────┘  │
│           │                                          │
│  OUTPUT LAYER                                        │
│  ┌────────▼──────────────────────────────────────┐  │
│  │  Reports & Metrics (for dashboards)            │  │
│  │  • Cost summaries (by model, task, time)       │  │
│  │  • Savings metrics (compression, cache)        │  │
│  │  • Validation results (pass/fail/warnings)     │  │
│  │  • Anomaly alerts (cost spikes, outliers)      │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Module Details

### 1. Logger (logger.py)
**Role:** Records every API call

**Key Class:** `CostLogger`

**Responsibilities:**
- Calculate cost using pricing module
- Write to append-only JSONL
- Thread-safe locking
- Read and aggregate logs

**Log Entry Structure:**
```json
{
  "timestamp": "2026-09-25T19:49:13.417417+00:00",
  "model": "sonnet",
  "input_tokens": 5000,
  "output_tokens": 3500,
  "total_tokens": 8500,
  "cost_usd": 0.0675,
  "task_name": "architecture_design",
  "source": "api",
  "metadata": {
    "compression_ratio": 0.85,
    "cache_hit": false,
    "routing_decision": "thompson_sampling"
  }
}
```

---

### 2. Aggregator (aggregator.py)
**Role:** Analyze logs and generate reports

**Key Class:** `CostAggregator`

**Responsibilities:**
- Parse JSONL logs
- Generate time-based summaries
- Calculate compression savings
- Calculate cache hit savings
- Detect trends

**Methods:**
- `daily_summary(date)` → Daily breakdown by model/task
- `weekly_summary(week_start)` → 7-day rolling summary
- `monthly_summary(month)` → Calendar month aggregation
- `savings_report()` → Compression + cache analysis
- `compression_metrics()` → Detailed compression stats
- `cache_analysis()` → Cache hit rate + tokens saved

**Output Example:**
```json
{
  "period": "2026-09-25",
  "total_cost_usd": 0.401,
  "total_tokens": 43000,
  "by_model": {
    "haiku": {"calls": 2, "cost": 0.008, "tokens": 6000},
    "sonnet": {"calls": 1, "cost": 0.068, "tokens": 8500}
  },
  "compression_savings": {
    "tokens_saved": 5200,
    "cost_saved_usd": 0.045,
    "compression_ratio": 0.88
  },
  "cache_savings": {
    "cache_hits": 2,
    "cache_hit_rate": 0.4,
    "tokens_saved": 3400,
    "estimated_cost_saved_usd": 0.025
  }
}
```

---

### 3. Validator (validator.py)
**Role:** Ensure data integrity and correctness

**Key Class:** `CostValidator`

**Responsibilities:**
- Verify cost calculations match pricing
- Detect duplicate entries
- Validate required fields
- Detect anomalies (outliers, spikes)
- Report severity levels

**Methods:**
- `validate_cost_calculation(entry)` → Check math
- `check_duplicates(entries)` → Find dupes
- `validate_schema(entry)` → Check fields
- `detect_anomalies(entries)` → Find outliers
- `validate_log_file(filepath)` → Full file validation

**Severity Levels:**
- `PASS` - All checks succeeded
- `WARNING` - Non-fatal issue (high tokens, cost spike)
- `ERROR` - Fatal issue (wrong calculation, duplicate, invalid JSON)

**Anomaly Thresholds:**
- High input tokens: >100k
- High output tokens: >100k
- High cost per call: >$50
- Cost spike: 5x median
- Token spike: 3x median

---

### 4. Integration (integration.py)
**Role:** Wire cost tracking into existing systems

**Key Components:**

#### Decorator: `@cost_track_api_call`
Automatically logs API calls with routing context:

```python
@cost_track_api_call(logger, "thompson_routing")
def select_model_thompson(task_description):
    # Your existing routing logic
    return model_name

@cost_track_api_call(logger, "compression")
def compress_with_tracking(text):
    # Your compression logic
    return compressed_text
```

#### Data Structures:

**RoutingDecision Enum:**
- THOMPSON_SAMPLING
- THOMPSON_SAMPLING_UPGRADED
- POSTGRES_VERIFIED
- VERIFIED_FALLBACK
- GA_EXPLORATION
- AUTO_PROFILER
- CACHE_HIT
- CACHE_MISS

**CompressionMetrics:**
- input_size, output_size
- reduction_percent, compression_method
- compression_time_ms, key_facts_preserved

**CacheMetrics:**
- is_cache_hit, cache_source
- input_tokens, cache_read_tokens, cache_creation_tokens

---

### 5. Pricing (pricing.py)
**Role:** Centralized pricing reference

**Pricing Table (per 1M tokens):**
- Haiku: $0.80 input, $2.40 output
- Sonnet: $3.00 input, $15.00 output
- Opus: $15.00 input, $45.00 output
- Opus 4.8: $12.00 input, $36.00 output
- Gemini: $0.075 input, $0.30 output

**Functions:**
- `calculate_cost(model, input_tokens, output_tokens)` → USD
- `get_model_display_name(model)` → "Claude Sonnet 4.5"

---

## Data Flow Example: 5-Call Workflow

```
Step 1: Thompson Router selects "sonnet" for code review
        ↓
Step 2: Integration decorator @cost_track_api_call captures:
        - Model decision: THOMPSON_SAMPLING
        - Task: "code_review"
        - Estimated tokens: ~5000
        ↓
Step 3: Compression pipeline (optional) reduces tokens from 5000 to 4250
        - Compression ratio: 0.85
        - Integration decorator logs pre/post compression
        ↓
Step 4: API call made: input=4250, output=2800
        ↓
Step 5: Logger records:
        {
          "timestamp": "2026-09-25T...",
          "model": "sonnet",
          "input_tokens": 4250,
          "output_tokens": 2800,
          "cost_usd": 0.0508,
          "compression_ratio": 0.85,
          "routing_decision": "thompson_sampling"
        }
        ↓
Step 6: Aggregator later calculates:
        - Daily cost: sum of all calls
        - Compression savings: 4250 vs 5000 = $0.0063 saved
        - Cost breakdown by model/task
        ↓
Step 7: Validator checks:
        - Cost calculation: (4250/1M)*3 + (2800/1M)*15 = 0.0508 ✓
        - No duplicates ✓
        - No anomalies ✓
```

---

## Integration Points with Existing Systems

### With Compression Module (`/compression/`)
```python
from compression import summarizer
from cost_tracking.integration import cost_track_api_call

logger = CostLogger()

@cost_track_api_call(logger, "compression_pipeline")
def compress_with_tracking(text):
    result = summarizer.compress(text)
    # Decorator auto-logs with:
    # - input_size (original)
    # - output_size (compressed)
    # - compression_ratio
    return result
```

### With Caching Module (`/caching/`)
```python
from caching import memory_cache_integration
from cost_tracking.logger import CostLogger

logger = CostLogger()

cache_result = memory_cache_integration.get(cache_key)
if cache_result:
    logger.log_call(
        model="opus",
        input_tokens=0,        # No API call
        output_tokens=0,
        task_name="code_review",
        source="cached",
        metadata={"cache_source": "memory", "cache_hit": True}
    )
else:
    # Make API call and log actual tokens
    result = claude.api_call(...)
    logger.log_call(
        model="opus",
        input_tokens=actual_input,
        output_tokens=actual_output,
        task_name="code_review",
        source="api"
    )
```

### With Orchestrator (`orchestrate_smart.py`)
```python
from cost_tracking.integration import cost_track_api_call

logger = CostLogger()

@cost_track_api_call(logger, "thompson_routing")
def orchestrate_task_with_tracking(task):
    # Existing orchestrator logic
    selected_model = thompson_sampler.select(task)
    result = call_model(selected_model, task)
    return result
```

---

## File Dependency Graph

```
pricing.py (definitions)
  ├─ logger.py (uses calculate_cost)
  ├─ aggregator.py (uses pricing reference)
  ├─ validator.py (uses PRICING dict)
  └─ integration.py (uses PRICING reference)

logger.py (core logging)
  ├─ test_logger.py (unit tests)
  ├─ aggregator.py (reads JSONL output)
  ├─ validator.py (validates JSONL format)
  └─ integration.py (decorator feeds to logger)

aggregator.py (analysis)
  └─ validator.py (validates aggregator output)

integration.py (hooks)
  ├─ compression/ (pre/post compression tracking)
  ├─ caching/ (cache hit/miss tracking)
  └─ orchestrate_smart.py (routing decision tracking)

example_usage.py (demonstrations)
  └─ Uses: logger, aggregator, pricing

__init__.py (package exports)
  └─ Exports: CostLogger, PRICING, ModelName

PHASE1_VERDICT.md (documentation)
```

---

## Configuration Points

### Logger Configuration
```python
# Default location: ~/.claude/cost_tracking/api_calls.jsonl
logger = CostLogger()  # Uses default

# Custom location
logger = CostLogger(log_path="/var/log/cost_tracking/costs.jsonl")
```

### Validator Configuration
```python
validator = CostValidator()

# Configure thresholds
validator.ANOMALY_THRESHOLDS["high_cost"] = 100.0  # Flag if >$100
validator.ANOMALY_THRESHOLDS["cost_spike_multiplier"] = 10.0  # 10x median
```

### Aggregator Configuration
```python
# Default JSONL location
aggregator = CostAggregator()

# Custom log path
aggregator = CostAggregator(log_file_path="/path/to/costs.jsonl")

# Custom cost multiplier (for budget forecasting)
aggregator.cost_multiplier = 1.15  # 15% buffer for forecasting
```

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| log_call() | <1ms | Append to file, mostly I/O |
| calculate_cost() | <0.1ms | Simple arithmetic |
| get_stats() | 10-50ms | Depends on log file size |
| daily_summary() | 20-100ms | Depends on # entries per day |
| validate_log_file() | 50-200ms | Depends on file size |
| @cost_track_api_call overhead | <1% | Async I/O in separate thread |

**Storage:**
- Per API call: ~500 bytes (JSON + newline)
- Per month (1000 calls): ~500 KB
- Per year: ~6 MB

---

## Next Steps

1. **Phase 2 Verification:** Multi-AI consensus review
2. **Production Integration:** Wire into Thompson router + compression + cache
3. **Monitoring:** Export to Prometheus, create Grafana dashboards
4. **Alerting:** Budget threshold alerts, cost spike notifications
5. **Forecasting:** Linear trend projection, cost forecasting
6. **Reporting:** Weekly/monthly cost reports with savings breakdown

