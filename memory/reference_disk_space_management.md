---
name: disk-space-management
description: "GGUF models (235GB) should live on NAS, not /home partition"
metadata: 
  node_type: memory
  type: reference
  date: 2026-06-15
  issue: disk-full
  originSessionId: e8c8e210-7731-4cf4-b2b1-d1559c501374
---

# Disk Space Management

**Issue discovered:** 2026-06-15 during router firmware research

**Problem:**
- `/home` partition: 100% full (465G/475G used, only 4.7G free)
- Root cause: 235GB of GGUF models in `/home/sfloess/ai-models/gguf/`

**Models occupying space:**
- llama-3.3-70b-q4: 40GB
- mixtral-8x7b-q4: 25GB
- command-r-v01: 21GB
- Plus 12 more models (5-19GB each)
- **Total:** 235GB in `/home/sfloess/ai-models/gguf/`

**Solution:** Move GGUF models to NAS

**NAS availability:**
- Location: `/mnt/nas/` (server-ap exports)
- Free space: 829GB available
- Access: All fleet nodes can mount
- Performance: Sufficient for model loading (one-time read at startup)

## Migration Steps

```bash
# 1. Create NAS directory
mkdir -p /mnt/nas/ai-models/gguf

# 2. Move models (preserving metadata)
cd ~/ai-models/gguf
rsync -av --progress *.gguf /mnt/nas/ai-models/gguf/

# 3. Verify transfer
diff <(ls -1 ~/ai-models/gguf/) <(ls -1 /mnt/nas/ai-models/gguf/)

# 4. Update Ollama config (if using Ollama)
# Edit ~/.config/ollama/config.json or /etc/ollama/config.json
# Set: "model_path": "/mnt/nas/ai-models/gguf"

# 5. Test model loading
ollama run llama-3.3-70b-q4  # Should load from NAS

# 6. Delete local copies (after verification)
rm -rf ~/ai-models/gguf/*.gguf

# 7. Create symlink (optional, for compatibility)
ln -s /mnt/nas/ai-models/gguf ~/ai-models/gguf
```

## Why NAS is Better

**Advantages:**
- ✅ 829GB free (vs 4.7GB on /home)
- ✅ Shared across fleet (no duplication per node)
- ✅ Centralized updates (update once, all nodes see it)
- ✅ Network bandwidth sufficient (1Gbps LAN)
- ✅ Backup strategy (NAS has redundancy)

**Performance impact:**
- Model load time: +2-5 seconds vs local (one-time cost)
- Inference: NO impact (models loaded to RAM)
- Overall: Negligible for typical workflows

## Fleet Configuration

**Each node needs:**
```bash
# /etc/fstab entry (if not already present)
server-ap:/exports/nas /mnt/nas nfs defaults,_netdev 0 0

# Mount
mount /mnt/nas

# Verify
df -h /mnt/nas
```

**Nodes to update:**
- laptop-01
- server-01
- server-02
- server-03
- aio-01
- pi-02 (if running models)

## Monitoring

**Check disk usage:**
```bash
# Home partition
df -h /home | grep -v Filesystem

# NAS
df -h /mnt/nas | grep -v Filesystem

# GGUF models
du -sh ~/ai-models/gguf 2>/dev/null || echo "Not on local"
du -sh /mnt/nas/ai-models/gguf 2>/dev/null || echo "Not on NAS"
```

**Alert thresholds:**
- `/home` partition: Alert at 90% (currently at 98%)
- `/mnt/nas`: Alert at 80% (currently at 12%)

## Related Issues

**Symptoms of disk full:**
- Git clone failures
- Build failures (no temp space)
- Log rotation failures
- Database write failures
- Container image pull failures

**Quick fix (temporary):**
```bash
# Clean up package caches
sudo dnf clean all

# Clean up old container images
podman system prune -a

# Clean up old logs
sudo journalctl --vacuum-time=7d

# Remove old kernels (Fedora)
sudo dnf remove $(dnf repoquery --installonly --latest-limit=-2 -q)
```

## Best Practices Going Forward

**For large files (>1GB):**
- ✅ Store on NAS
- ❌ Do not store in `/home`

**Examples:**
- ✅ GGUF models → `/mnt/nas/ai-models/gguf/`
- ✅ Training datasets → `/mnt/nas/datasets/`
- ✅ Research codebases → `/mnt/nas/shared/apps/` (already doing)
- ✅ PDF collections → `/mnt/nas/media/books/` (already doing)
- ❌ Never keep 40GB models in home directory

**For development work:**
- ✅ Source code → `/home` or project-specific location (small)
- ✅ Build artifacts → `/home` (cleaned regularly)
- ✅ Logs → `/home` with rotation
- ❌ Large binaries/models/datasets → always NAS

## Recovery Procedure

**If /home fills up again:**

1. Identify culprit:
   ```bash
   du -sh /home/sfloess/* | sort -rh | head -20
   ```

2. Move to NAS:
   ```bash
   rsync -av --progress /path/to/large/dir /mnt/nas/
   ```

3. Verify and delete local

4. Update MEMORY.md with new pattern

## Related Patterns

- [[reference_distributed_fleet]] - NAS is central storage for fleet
- [[project_pdf_research_status]] - 846 PDFs on NAS (correct location)

## Status

**Current (2026-07-01):**
- ✅ Issue identified
- ⚠ Solution documented (not yet executed)
- ⚠ Models still in /home (235GB)
- ⚠ Partition still at ~98% full

**Next action:** Execute migration steps above
**Priority:** HIGH (blocking new work that needs disk space)

---

**Rule:** GGUF models and large datasets live on NAS, not /home.
