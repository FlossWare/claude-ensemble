# HYBRID Priority System - Quick Reference

**Fixed:** 2026-07-11  
**Bug:** Priority inversion in ZSET mode  
**Solution:** Changed `ZPOPMAX` → `ZPOPMIN`

---

## Quick Summary

**Problem:** Low-priority tasks processed FIRST (complete inversion)  
**Cause:** `ZPOPMAX` pops highest score, but `(10-priority)` gives lower scores for higher priorities  
**Fix:** Use `ZPOPMIN` to pop lowest score first  

---

## Test Verification

```bash
python3 scripts/test-hybrid-priority-bug.py
```

**Expected:**
```
Test 2 (FIX #1 - ZPOPMIN): ✓ PASS
```

---

## Files Changed

1. `scripts/redis-lua-scripts.lua` - Line 91: `ZPOPMAX` → `ZPOPMIN`
2. `scripts/redis-atomic-operations.py` - Already correct (no changes)
3. `scripts/test-hybrid-priority-bug.py` - New test file
4. `docs/HYBRID_MODE_PRIORITY_FIX.md` - Full documentation

---

## Priority Formula

```python
score = (10 - priority) * 1e13 + timestamp_ms
```

- **Priority 10**: score = 0 + timestamp (LOWEST)
- **Priority 1**: score = 90e12 + timestamp (HIGHEST)
- **ZPOPMIN** pops LOWEST score → Priority 10 first ✓

---

## FIFO Within Priority

Same priority tasks pop in timestamp order (oldest first):

```
Priority 10 @ t=1000 → score = 1000
Priority 10 @ t=2000 → score = 2000
Priority 10 @ t=3000 → score = 3000

ZPOPMIN order: 1000 → 2000 → 3000 (FIFO ✓)
```

---

## Deployment

1. Deploy `scripts/redis-lua-scripts.lua` to aio-01
2. Restart workers (if using ZSET mode)
3. Verify with test script

**Status:** Ready ✓
