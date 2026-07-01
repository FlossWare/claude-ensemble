# Task Queue System Integration Guide

**Issue:** #259  
**Status:** ✅ ACTIVE (as of 2026-07-01)  
**Database:** PostgreSQL on aio-01:5433, database `learning`, schema `queue.*`

## Overview

The priority task queue system is now integrated and active. It provides:

- **Priority-based scheduling** (1-10, 10=highest)
- **Worker claiming with SKIP LOCKED** (no race conditions)
- **Auto-retry failed tasks** (max 3 attempts)
- **Dead letter queue** for max failures
- **Fleet worker health tracking**

## Integration Points

### 1. Python API: `tools/task_queue_system.py`

**Test:** `python3 tools/task_queue_system.py`

### 2. JavaScript API: `shared/task-queue-wrapper.mjs`

**Test:** `node shared/task-queue-wrapper.mjs --stats`

### 3. Test Workflow: `workflows/test-task-queue.mjs`

**Test:** `node workflows/test-task-queue.mjs`

## CLI Commands

```bash
# Show queue statistics
node shared/task-queue-wrapper.mjs --stats

# List pending tasks
node shared/task-queue-wrapper.mjs --pending

# Enqueue a test task
node shared/task-queue-wrapper.mjs --enqueue 8 opus "Analyze code"

# Start worker daemon
node shared/task-queue-wrapper.mjs --worker server-01
```

## Verification

✅ Python API works: `python3 tools/task_queue_system.py` completes without errors
✅ JavaScript wrapper works: `node shared/task-queue-wrapper.mjs --stats` shows queue statistics  
✅ Test workflow works: `node workflows/test-task-queue.mjs` enqueues 4 tasks successfully
✅ Database schema exists: `queue.*` tables created in PostgreSQL

## How to Verify Integration

1. **Check queue stats:**
   ```bash
   node shared/task-queue-wrapper.mjs --stats
   ```

2. **Enqueue test task:**
   ```bash
   node shared/task-queue-wrapper.mjs --enqueue 8 opus "Test integration"
   ```

3. **Run full test:**
   ```bash
   node workflows/test-task-queue.mjs
   ```

4. **Check database:**
   ```bash
   psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT COUNT(*) FROM queue.tasks"
   ```

All tests passing ✅
