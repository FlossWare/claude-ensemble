# Model Performance Drift Detection

**Automated monitoring system for detecting model performance degradation in the multi-AI consensus framework.**

**Created:** 2026-06-28  
**Status:** Production-ready (pending postgres migration)  
**Database:** `postgresql://sfloess@aio-01:5433/learning`  
**Last Updated:** 2026-06-28 (Priority fixes implemented)

---

## Quick Start

### 1. Run Manual Detection

```bash
node monitoring/check-drift.cjs
```

### 2. Add to Cron (Daily 3 AM)

```bash
crontab -e
# Add: 0 3 * * * cd /path/to/project && node monitoring/check-drift.cjs >> /var/log/drift-detection.log 2>&1
```

---

## What It Does

Tracks 30-day rolling performance and alerts when performance drops >10%.

- **Baseline:** 30-day average (excluding last 7 days)
- **Current:** 7-day average
- **Alert:** Current < Baseline × 0.9 (10% drop)

---

## Files

| File | Purpose |
|------|---------|
| `schema-drift-detection.sql` | PostgreSQL schema (updated with fixes) |
| `drift-detector.cjs` | Core detection module (minSamples=20) |
| `check-drift.cjs` | CLI tool |
| `drift-detection-cron.md` | Complete guide |
| `test-drift-detection.cjs` | Test suite (validates all fixes) |
| `migrate-drift-alerts.sql` | Migration: Add deduplication columns |
| `migrate-model-drift-view.sql` | Migration: Rename confidence → quality |
| `DRIFT_DETECTION_FIXES.md` | Implementation summary and migration guide |

---

## CLI Usage

```bash
# Daily check
node monitoring/check-drift.cjs

# Custom threshold (15%)
node monitoring/check-drift.cjs --threshold=0.15

# Show unacknowledged
node monitoring/check-drift.cjs --unacknowledged

# Acknowledge alert
node monitoring/check-drift.cjs --acknowledge=42

# Model history
node monitoring/check-drift.cjs --history=opus
```

---

## Recent Updates (2026-06-28)

### Priority Fixes Implemented

1. **Quality metric tracking** - Renamed confidence → quality in materialized view
2. **Alert deduplication** - Added unique constraint, prevents duplicate alerts per day
3. **Minimum sample size** - Raised from 5 to 20 to reduce false positives

### Migration Required

Run as postgres user:
```bash
psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-drift-alerts.sql
psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-model-drift-view.sql
```

### Verify Fixes
```bash
node monitoring/test-drift-detection.cjs
```

**Full details:** See `DRIFT_DETECTION_FIXES.md`

---

## Documentation

See `drift-detection-cron.md` for complete operational guide.
