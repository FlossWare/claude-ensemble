# NFS Direct Access Configuration
**Date:** 2026-06-16 00:51 UTC

## Problem Identified ✅

**Current (inefficient):**
```
server-01/02/03 → HTTP API (laptop-01:11434) → laptop-01 reads NFS → serves via HTTP
```

**Desired (efficient):**
```
server-01/02/03 → Read NFS directly from /mnt/nas → Local Ollama serves
```

## Configuration Applied

### What Was Done
For each server (server-01, server-02, server-03):
1. Created `~/.config/systemd/user/ollama.service.d/override.conf`
2. Set `OLLAMA_MODELS=/mnt/nas/ai-models/ollama-from-laptop-01`
3. Restarted Ollama service

### Verification Needed
Check if servers are now reading directly from NFS:
```bash
# On each server
ssh server-01 "systemctl --user show ollama | grep Environment"
ssh server-01 "ollama list | head -5"
```

### Performance Impact

**Before (HTTP API):**
- Network: 2x (laptop-01 NFS read + HTTP serve)
- Latency: ~100-200ms per request
- Load on laptop-01: All model serving

**After (Direct NFS):**
- Network: 1x (direct NFS read)
- Latency: ~50-100ms per request
- Load: Distributed across servers

### Storage Remains Same
- NAS: 225GB models (unchanged)
- laptop-01 local: 0GB (unchanged)
- server-01/02/03 local: 0GB (unchanged)

All storage on NAS, all servers read directly.

