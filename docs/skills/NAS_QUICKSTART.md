# NAS Model Distribution - Quick Start Guide

Get your fleet models deployed in 5 minutes.

## Prerequisites

- ✅ NAS mounted at `/mnt/nas/ai-models` (or set `NAS_MODELS_DIR`)
- ✅ Ollama installed on all nodes
- ✅ SSH access to remote nodes
- ✅ `jq`, `rsync` installed

## Quick Start

### Step 1: Mount NAS (if not already)

```bash
# Example for NFS mount
sudo mount -t nfs nas-server:/volume1/ai-models /mnt/nas/ai-models

# Or set custom location
export NAS_MODELS_DIR=/your/nas/path
```

### Step 2: Calculate Optimal Distribution

```bash
# Calculate optimal model placement
./fleet-auto-distributor.cjs update-registry
```

Output:
```
🚀 Fleet Auto-Distribution Results
================================================================================
✅ Distribution valid: All models assigned, zero duplication
```

### Step 3: Download Models to NAS

**Option A: High-priority models only (recommended)**
```bash
./scripts/download-to-nas.sh --high-priority
```

**Option B: All models**
```bash
./scripts/download-to-nas.sh --all
```

**Option C: Specific models**
```bash
./scripts/download-to-nas.sh codestral:22b qwen2.5-coder:7b deepseek-r1:32b
```

Output:
```
[INFO] Downloading model: codestral:22b
[INFO] Pulling model from Ollama registry...
[SUCCESS] Model pulled successfully: codestral:22b
[SUCCESS] Model exported to NAS: codestral:22b (12G)
```

### Step 4: Distribute to Fleet

```bash
./scripts/distribute-to-nodes.sh
```

Output:
```
[INFO] Starting full fleet distribution...
[INFO] Found 4 nodes with local model assignments

[PROGRESS] Distributing codestral:22b to server-02...
[SUCCESS] Distribution complete: codestral:22b -> server-02

Distribution Summary
====================
Total distributions attempted: 27
[SUCCESS] Successful: 27
```

### Step 5: Verify

```bash
# Check distribution status
./nas-model-manager.cjs report
```

## One-Liner Deployment

**Complete deployment in one command:**

```bash
./nas-model-manager.cjs deploy --high-priority
```

This does:
1. Downloads high-priority models to NAS
2. Distributes to all assigned nodes
3. Shows summary

## Common Commands

### List NAS Inventory

```bash
./scripts/download-to-nas.sh --list
```

### Show Fleet Status

```bash
./fleet-cli.cjs status
```

### Calculate Savings

```bash
./nas-model-manager.cjs savings
```

### Distribute to One Node

```bash
./scripts/distribute-to-nodes.sh --node server-02
```

### Verify Distribution

```bash
./scripts/distribute-to-nodes.sh --verify
```

### Find Missing Models

```bash
./nas-model-manager.cjs missing
```

## Example Workflow

```bash
# 1. Setup
sudo mount -t nfs nas:/ai-models /mnt/nas/ai-models
./fleet-auto-distributor.cjs update-registry

# 2. Deploy (one command)
./nas-model-manager.cjs deploy --high-priority

# 3. Verify
./nas-model-manager.cjs report

# 4. Check fleet
./fleet-cli.cjs health
```

## Troubleshooting

### NAS not mounted
```bash
ls -la /mnt/nas/ai-models
# If error, mount it:
sudo mount -t nfs nas-server:/volume1/ai-models /mnt/nas/ai-models
```

### Node unreachable
```bash
ping server-02
ssh server-02 "ollama list"
```

### Model not distributing
```bash
# Re-download
./scripts/download-to-nas.sh codestral:22b

# Re-distribute
./scripts/distribute-to-nodes.sh codestral:22b
```

## Tips

1. **Start Small**: Use `--high-priority` for initial deployment
2. **Verify First**: Always check `--list` before distributing
3. **Monitor Space**: 27 models ≈ 135GB on NAS
4. **Check Savings**: Run `savings` report to see ROI
5. **Automate**: Use cron for periodic sync

## Next Steps

- Read [NAS_MODEL_DISTRIBUTION.md](./NAS_MODEL_DISTRIBUTION.md) for full docs
- Configure automated sync (cron)
- Monitor NAS capacity
- Set up alerting for failed distributions

## Performance

**Expected times (example)**:
- Download to NAS: 3 hours for 27 models (135GB @ 100 Mbps)
- Distribute to 4 nodes: 20 minutes (540GB @ 1 Gbps LAN)
- **Total: ~3.5 hours vs. 12 hours without NAS**

**Bandwidth savings**: 75% (540GB → 135GB internet bandwidth)

## Help

```bash
# Script help
./scripts/download-to-nas.sh --help
./scripts/distribute-to-nodes.sh --help
./nas-model-manager.cjs

# Fleet help
./fleet-cli.cjs --help
./fleet-auto-distributor.cjs --help
```

---

**Ready to deploy?** Run: `./nas-model-manager.cjs deploy --high-priority`
