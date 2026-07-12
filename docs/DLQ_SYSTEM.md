# Dead-Letter Queue (DLQ) System

**Version:** 1.0  
**Date:** 2026-07-11  
**Component:** Auto Storage System

## Overview

The Dead-Letter Queue (DLQ) system handles items that fail processing after multiple retry attempts. Instead of losing failed items or retrying indefinitely, the system:

1. **Tracks retry attempts** for each failed item
2. **Retries up to MAX_RETRIES times** (default: 3)
3. **Moves to DLQ** after max retries exceeded
4. **Preserves failure metadata** for debugging and recovery

## Architecture

```
┌─────────────────┐
│  Memory Files   │
│  Session Files  │
│  Workflow Files │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Auto Storage System        │
│  - Semantic chunking        │
│  - Embedding generation     │
│  - Vector storage           │
│  - Graph relationships      │
└────────┬────────────────────┘
         │
         ├─────► Success ──────► Mark as processed
         │                       Clear retry tracker
         │
         ├─────► Failure ──────► Track retry count
         │                       Increment counter
         │
         └─────► Max Retries ──► Send to DLQ
                  (3 attempts)    Remove from retry tracker
```

## Configuration

**File:** `tools/auto_storage_system_FIXED.py`

```python
MAX_RETRIES = 3  # Max attempts before DLQ

# Paths
DLQ_DIR = Path.home() / ".claude" / "learning" / "dlq"
RETRY_TRACKER_FILE = Path.home() / ".claude" / "learning" / "auto_storage_retries.json"
```

## Retry Tracking

The system maintains a retry tracker file that stores:

```json
{
  "/path/to/failed/file.md": {
    "count": 2,
    "hash": "sha256...",
    "first_failed": "2026-07-11T12:00:00",
    "last_failed": "2026-07-11T12:10:00",
    "last_error": {
      "type": "api_error",
      "status_code": 500,
      "error": "Internal Server Error"
    }
  }
}
```

## DLQ Entry Format

When an item is sent to DLQ, a JSON file is created with full metadata:

```json
{
  "original_path": "/path/to/failed/file.md",
  "item_type": "memory",
  "failed_at": "2026-07-11T12:15:00",
  "retry_count": 3,
  "error_info": {
    "type": "api_error",
    "status_code": 500,
    "error": "Internal Server Error"
  },
  "last_hash": "sha256..."
}
```

**Fields:**

- `original_path` - Full path to the original file
- `item_type` - Type of item (`memory`, `session`, `workflow`, `chunk`)
- `failed_at` - ISO timestamp when sent to DLQ
- `retry_count` - Number of attempts before DLQ (should be MAX_RETRIES)
- `error_info` - Detailed error information
- `last_hash` - SHA256 hash of file content when it failed

## Failure Types

The system handles different failure types:

### 1. API Errors

HTTP errors from REST API endpoints (4xx, 5xx).

```python
error_info = {
    'type': 'api_error',
    'status_code': 500,
    'error': 'Internal Server Error'
}
```

### 2. Network Errors

Connection timeouts, DNS failures, unreachable endpoints.

```python
error_info = {
    'type': 'network_error',
    'error': 'Connection timeout'
}
```

### 3. Partial Chunk Failures

When chunking is used and some chunks fail.

```python
error_info = {
    'type': 'partial_chunk_failure',
    'total_chunks': 10,
    'successful_chunks': 7,
    'failed_chunks': [
        {'chunk_index': 3, 'status_code': 500, 'error': '...'},
        {'chunk_index': 8, 'status_code': 503, 'error': '...'}
    ]
}
```

### 4. Exceptions

Uncaught exceptions during processing.

```python
error_info = {
    'type': 'exception',
    'error': 'KeyError: embedding',
    'traceback': 'Traceback (most recent call last):\n...'
}
```

## DLQ File Naming

DLQ files are named with timestamp for uniqueness:

```
{item_type}_{original_filename}_{timestamp}.json
```

**Examples:**

- `memory_feedback_user_preferences_20260711_121500.json`
- `session_2026-07-11_research_20260711_121530.json`
- `workflow_deep_research_execution_20260711_121600.json`

## Recovery Procedures

### Manual Recovery

1. **Inspect DLQ entries:**

```bash
ls -lh ~/.claude/learning/dlq/
```

2. **Review failure details:**

```bash
cat ~/.claude/learning/dlq/memory_*.json | jq '.'
```

3. **Fix underlying issue** (API endpoint, network, permissions, etc.)

4. **Re-process failed items:**

```python
import json
from pathlib import Path

dlq_dir = Path.home() / ".claude" / "learning" / "dlq"

for dlq_file in dlq_dir.glob("*.json"):
    with open(dlq_file, 'r') as f:
        entry = json.load(f)
    
    original_file = Path(entry['original_path'])
    
    # Re-process original file
    # (will retry up to MAX_RETRIES again)
    store_memory_via_api(original_file)
```

### Automated Recovery

Create a cron job to periodically retry DLQ items:

```bash
# Every hour, retry DLQ items
0 * * * * python3 /path/to/retry_dlq.py
```

## Monitoring

### Check DLQ Size

```bash
# Count DLQ entries
ls ~/.claude/learning/dlq/ | wc -l

# Size of DLQ directory
du -sh ~/.claude/learning/dlq/
```

### Check Retry Tracker

```bash
# View current retry attempts
cat ~/.claude/learning/auto_storage_retries.json | jq '.'

# Count items being retried
cat ~/.claude/learning/auto_storage_retries.json | jq 'keys | length'
```

### Alerts

Set up alerts if DLQ grows too large:

```bash
#!/bin/bash
DLQ_COUNT=$(ls ~/.claude/learning/dlq/ | wc -l)

if [ $DLQ_COUNT -gt 100 ]; then
    echo "WARNING: DLQ has $DLQ_COUNT items"
    # Send notification
fi
```

## Performance Impact

**Retry tracking overhead:**

- File lock acquisition: ~1-2ms
- JSON read/write: ~5-10ms per file
- SHA256 hash calculation: ~10-20ms per file

**Total overhead:** ~15-30ms per failed item

**DLQ write overhead:**

- JSON write: ~5-10ms
- Minimal impact on overall system performance

## Testing

Run the DLQ test suite:

```bash
python3 tools/test_dlq.py
```

**Test coverage:**

1. ✓ Retry tracking (counts retries correctly)
2. ✓ DLQ activation after MAX_RETRIES
3. ✓ DLQ file creation with proper metadata
4. ✓ Retry tracker cleanup after success

## Best Practices

1. **Monitor DLQ regularly** - Don't let it grow unbounded
2. **Investigate root causes** - Fix API/network issues, not just symptoms
3. **Periodic cleanup** - Archive or delete old DLQ entries
4. **Adjust MAX_RETRIES** - Based on transient vs permanent failures
5. **Alert on DLQ growth** - Detect systemic issues early

## Troubleshooting

### DLQ Growing Rapidly

**Possible causes:**

- API endpoint down
- Network connectivity issues
- Database overload
- Rate limiting

**Solution:** Check API health, network status, system resources.

### Items Not Retrying

**Possible causes:**

- Retry tracker corrupted
- File permissions issues
- File locks not released

**Solution:** Check retry tracker JSON, file permissions, running processes.

### DLQ Files Not Created

**Possible causes:**

- DLQ directory missing
- Disk full
- File permissions

**Solution:** Check directory exists, disk space, permissions.

## Future Enhancements

- **Exponential backoff** - Longer delays between retries
- **Priority queues** - Retry critical items first
- **Batch recovery** - Process DLQ in bulk
- **DLQ analytics** - Failure pattern analysis
- **Auto-recovery** - Automatically retry DLQ items when API recovers

## References

- `tools/auto_storage_system_FIXED.py` - Main implementation
- `tools/test_dlq.py` - Test suite
- `docs/AUTO_STORAGE_SYSTEM.md` - Overall system documentation
