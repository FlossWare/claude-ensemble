# Fleet Configuration

**Last Updated:** 2026-06-29
**Fleet Size:** 9 workers
**Executor:** Python 3.13+ (universal compatibility)

## Workers

| Worker | Architecture | Python | Role | Notes |
|--------|--------------|--------|------|-------|
| aio-01 | x86_64 | 3.14.5 | Orchestrator + Worker | This machine |
| server-01 | x86_64 | 3.13.5 | Worker | |
| server-02 | x86_64 | 3.13.5 | Worker | Node v14 too old, Python better |
| server-03 | x86_64 | 3.13.5 | Worker | Node v14 too old, Python better |
| laptop-01 | x86_64 | 3.14.5 | Worker | Work machine but included |
| pi-01 | arm64 | 3.13.5 | Worker | |
| pi-02 | arm64 | 3.13.5 | Worker | |
| desktop-ap | armhf | 3.13.5 | Worker | Node crashes (bus error), Python works |
| server-ap | armhf | 3.13.5 | Worker | Node crashes (bus error), Python works |

**Excluded:**
- util-ap: Only 120MB RAM (would OOM during API calls)

## Executor

**Primary:** `shared/fleet-executor.py`
- Pure Python 3.8+
- Stdlib only (no dependencies)
- Works on ALL architectures
- Handles all API providers

**Usage:**
```python
from fleet_executor import execute_on_worker

result = execute_on_worker(
    worker='server-01',
    model='gpt-4o-mini',
    task='Analyze this code',
    max_tokens=500
)
```

**Parallel execution:**
```python
from fleet_executor import execute_on_fleet_parallel

results = execute_on_fleet_parallel(
    workers=['server-01', 'server-02', 'pi-01'],
    model='gpt-4o-mini',
    tasks=['Task 1', 'Task 2', 'Task 3'],
    max_tokens=500
)
```

## Why Python (not Node.js)

1. ✅ **100% compatibility** (8/8 workers) vs 62.5% (5/8 for Node)
2. ✅ **No version issues** (Python 3.13-3.14) vs Node v14/v20/v22
3. ✅ **No polyfills** vs AbortController + fetch hacks
4. ✅ **Works on armhf** vs Node bus errors
5. ✅ **Simpler code** - one implementation, not architecture detection

## Deprecated

- `shared/execute-on-worker.js` (Node.js) - **DO NOT USE**
- Node.js polyfills in `shared/fleet-utils.js` - **DELETE**

## Testing

Test all 9 workers:
```bash
for w in aio-01 server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
  echo "$w: $(ssh claude@$w 'python3 --version' 2>&1)"
done
```

Expected: All show Python 3.13 or 3.14.

**Verified 2026-06-29:** All 9 workers operational with Python.
