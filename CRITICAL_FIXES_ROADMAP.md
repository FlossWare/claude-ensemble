# Session 6 Critical Fixes Roadmap

## Status: 2/4 Critical Blockers Fixed ✅

### COMPLETED (Commit f148e6c)
✅ **BLOCKER 1:** Graph service registration — Added 'graph' to KNOWN_SERVICES
✅ **BLOCKER 2:** Thread safety in GraphDB — Added RLock to prevent race conditions

### REMAINING (High Priority)

#### BLOCKER 3: Learning Service Endpoint Registration
**File:** `server/ensemble_server.py` + `learning/learning_orchestrator.py`
**Fix:** 
- Wire learning_orchestrator into ensemble_server.handle() 
- Add case for 'learning' service that routes to orchestrator methods:
  - POST /api/v1/learning/sync-outcomes → handle_sync_request()
  - GET /api/v1/learning/status → handle_status_request()
  - POST /api/v1/learning/graph/query → handle_graph_query()
  - POST /api/v1/learning/thompson/query → handle_thompson_query()
**Time:** 30 min

#### BLOCKER 4: Type System Standardization
**Files:** 
- `learning/learning_analytics.py` (line 114)
- `learning/arbitration_advisor.py` (line 99, 267)
- `learning/diagnostic_queries.py` (multiple)
**Fix:**
- All endpoints return: `{'ok': bool, 'error': str|None, 'data': Any}`
- Callers check `response['ok']` before accessing `response['data']`
- Error messages in `response['error']`
**Time:** 45 min

### HIGH-PRIORITY ITEMS (After Blockers)

#### HIGH-1: Cost Data in Graph Edges
**File:** `learning/graph_outcomes_bridge.py` line 81
**Fix:** Add `'cost': cost` to edge properties when calling `_add_edge()`
**Time:** 15 min

#### HIGH-2: Fail-Fast in Learning Orchestrator
**File:** `learning/learning_orchestrator.py` lines 96-136
**Fix:** 
- Implement circuit breaker for critical steps
- Return error if graph population fails
- Explicit error propagation instead of silent continue
**Time:** 30 min

#### HIGH-3: Confidence Recalibration
**Files:** `learning/arbitration_advisor.py`, `learning/learning_analytics.py`
**Fix:**
- Use Bayesian credible intervals instead of simple division
- Warn explicitly when N < 5 (unreliable)
- Warn when N < 30 (high variance)
- Ensure consistent formulas across modules
**Time:** 45 min

#### HIGH-4: Data Freshness & Sample Size Warnings
**File:** `learning/decision_support_api.py` response handlers
**Fix:**
- Add `'sample_size': N` to all responses
- Add `'data_freshness': days` to all responses
- Add `'warnings': []` list with explicit warnings for low N or stale data
**Time:** 30 min

## Total Remaining Work
- 2 critical blockers: ~75 min
- 4 high-priority items: ~2 hours
- **Total: 3.25 hours** to production-ready

## Next Steps
1. Fix BLOCKER 3 (learning service registration)
2. Fix BLOCKER 4 (type system)
3. Fix HIGH-1 through HIGH-4 in order

After fixes: Run verification review again (expect 85%+ confidence for production).
