# NAS-Based Centralized Model Distribution System

**The Smart Way**: Download models ONCE to NAS, distribute FAST via gigabit LAN.

## Why NAS Distribution?

### The Problem
- **Without NAS**: Each node downloads models from internet (slow, wasteful)
  - Node 1: Downloads 12GB model @ 100 Mbps internet
  - Node 2: Downloads 12GB model @ 100 Mbps internet
  - Node 3: Downloads 12GB model @ 100 Mbps internet
  - Total: 36GB internet bandwidth, 3× download time

### The Solution
- **With NAS**: Download once, distribute via local network (fast, efficient)
  - NAS: Downloads 12GB model @ 100 Mbps internet (once)
  - Node 1: Copies from NAS @ 1 Gbps LAN
  - Node 2: Copies from NAS @ 1 Gbps LAN
  - Node 3: Copies from NAS @ 1 Gbps LAN
  - Total: 12GB internet bandwidth, 10× faster distribution

### Benefits
- **90% less internet bandwidth** (download once, not N times)
- **10× faster distribution** (gigabit LAN vs. internet)
- **Centralized management** (single source of truth)
- **Checksummed verification** (integrity guaranteed)
- **Version control** (track what's deployed where)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERNET (100 Mbps)                      │
│                          ▲                                  │
│                          │ Download ONCE                    │
│                          │                                  │
└──────────────────────────┼─────────────────────────────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │    NAS Central Repo   │
               │  /mnt/nas/ai-models   │
               │                       │
               │  ┌─────────────────┐  │
               │  │  ollama/        │  │
               │  │  ├─ model-1/    │  │
               │  │  ├─ model-2/    │  │
               │  │  └─ model-N/    │  │
               │  │                 │  │
               │  │  manifests/     │  │
               │  │  ├─ inventory   │  │
               │  │  ├─ versions    │  │
               │  │  └─ dist-log    │  │
               │  └─────────────────┘  │
               └───────────┬───────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │    Gigabit LAN (1000 Mbps)        │
         │                 │                 │
         ▼                 ▼                 ▼
    ┌────────┐        ┌────────┐        ┌────────┐
    │ Node 1 │        │ Node 2 │        │ Node 3 │
    │server01│        │server02│        │server03│
    └────────┘        └────────┘        └────────┘
     Ollama            Ollama            Ollama
```

## Directory Structure

```
/mnt/nas/ai-models/
├── ollama/                          # Model storage
│   ├── codestral:22b/
│   │   ├── manifests/               # Model manifests
│   │   └── blobs/                   # Model blobs (weights)
│   ├── qwen2.5-coder:7b/
│   ├── deepseek-r1:32b/
│   └── ... (27 models)
│
├── manifests/                       # Metadata & tracking
│   ├── model-inventory.json         # What's downloaded
│   ├── version-history.json         # Download history
│   └── distribution-log.json        # Distribution tracking
│
└── scripts/                         # Automation
    ├── download-to-nas.sh
    └── distribute-to-nodes.sh
```

## Components

### 1. download-to-nas.sh
Downloads models from Ollama registry to NAS central repository.

**Features:**
- Pull models using Ollama CLI
- Export model files (manifests + blobs)
- Calculate checksums for integrity
- Track inventory in JSON
- Support batch downloads

**Usage:**
```bash
# Download specific models
./scripts/download-to-nas.sh codestral:22b qwen2.5-coder:7b

# Download all local models
./scripts/download-to-nas.sh --all

# Download high-priority models only
./scripts/download-to-nas.sh --high-priority

# List inventory
./scripts/download-to-nas.sh --list

# Verify model integrity
./scripts/download-to-nas.sh --verify codestral:22b
```

### 2. distribute-to-nodes.sh
Distributes models from NAS to fleet nodes via local network.

**Features:**
- Read fleet-model-registry.json for assignments
- Copy models via rsync (fast, resumable)
- Import to node's Ollama
- Track distribution status
- Verify installation

**Usage:**
```bash
# Distribute all models per fleet registry
./scripts/distribute-to-nodes.sh

# Distribute specific model
./scripts/distribute-to-nodes.sh codestral:22b

# Distribute to specific node
./scripts/distribute-to-nodes.sh --node server-02

# Verify distribution
./scripts/distribute-to-nodes.sh --verify

# Show statistics
./scripts/distribute-to-nodes.sh --stats
```

### 3. nas-model-manager.cjs
Node.js module for programmatic access and automation.

**Features:**
- Complete deployment workflow
- Integration with fleet-auto-distributor
- Bandwidth savings calculator
- Distribution analytics
- Report generation

**Usage:**
```bash
# Download high-priority models
./nas-model-manager.cjs download --high-priority

# Distribute to fleet
./nas-model-manager.cjs distribute

# Complete deployment workflow
./nas-model-manager.cjs deploy --all

# Show inventory summary
./nas-model-manager.cjs summary

# Calculate bandwidth savings
./nas-model-manager.cjs savings

# Generate comprehensive report
./nas-model-manager.cjs report

# Find missing models
./nas-model-manager.cjs missing
```

## Workflows

### Initial Setup

```bash
# 1. Mount NAS (adjust path for your system)
sudo mount -t nfs nas-server:/volume1/ai-models /mnt/nas/ai-models

# 2. Calculate optimal distribution
./fleet-auto-distributor.cjs update-registry

# 3. Download high-priority models to NAS
./scripts/download-to-nas.sh --high-priority

# 4. Distribute to nodes
./scripts/distribute-to-nodes.sh

# 5. Verify deployment
./nas-model-manager.cjs report
```

### Add New Model

```bash
# 1. Add to model-requirements.json (if needed)
# Edit model-requirements.json to add new model

# 2. Recalculate distribution
./fleet-auto-distributor.cjs update-registry

# 3. Download to NAS
./scripts/download-to-nas.sh new-model:7b

# 4. Distribute to assigned node
./scripts/distribute-to-nodes.sh new-model:7b
```

### Full Re-sync

```bash
# Complete re-sync of all models
./nas-model-manager.cjs deploy --all
```

### Update Existing Model

```bash
# 1. Download latest version
./scripts/download-to-nas.sh codestral:22b

# 2. Redistribute
./scripts/distribute-to-nodes.sh codestral:22b

# 3. Verify
./scripts/download-to-nas.sh --verify codestral:22b
```

## Data Schemas

### model-inventory.json

```json
{
  "_comment": "NAS Model Inventory",
  "_version": "1.0",
  "_last_updated": "2026-06-13T17:00:00Z",
  "nas_path": "/mnt/nas/ai-models",
  "models": {
    "codestral:22b": {
      "size_gb": 12.0,
      "disk_usage": "12G",
      "downloaded": "2026-06-13T17:00:00Z",
      "version": "latest",
      "checksum": "sha256:abc123...",
      "distributed_to": ["server-02"],
      "nas_path": "/mnt/nas/ai-models/ollama/codestral:22b"
    }
  }
}
```

### distribution-log.json

```json
{
  "_comment": "Distribution log",
  "distributions": [
    {
      "model": "codestral:22b",
      "node": "server-02",
      "timestamp": "2026-06-13T17:30:00Z",
      "status": "success"
    }
  ]
}
```

## Performance Metrics

### Bandwidth Savings Example

**Scenario**: 27 local models, average 5GB each, distributed to 4 nodes

| Method | Bandwidth | Time |
|--------|-----------|------|
| **Internet (each node)** | 540 GB | 12 hours |
| **NAS (centralized)** | 135 GB + LAN | 3 hours + 20 min |
| **Savings** | **75% less** | **74% faster** |

### Speed Comparison

| Transfer Type | Speed | Time for 12GB Model |
|---------------|-------|---------------------|
| Internet download | 100 Mbps | 16 minutes |
| NAS LAN copy | 1000 Mbps | 1.6 minutes |
| **Speedup** | **10×** | **10× faster** |

## Integration with Fleet System

### With fleet-auto-distributor

```bash
# 1. Calculate optimal placement
./fleet-auto-distributor.cjs update-registry

# 2. Download assigned models to NAS
./nas-model-manager.cjs download --all

# 3. Distribute per registry
./nas-model-manager.cjs distribute

# 4. Verify deployment
./fleet-cli.cjs health
```

### With fleet-cli

```bash
# Check fleet status
./fleet-cli.cjs status

# Route requests (uses NAS-distributed models)
./fleet-cli.cjs route coding

# Verify node has models
./fleet-cli.cjs node server-02
```

### Programmatic Integration

```javascript
const NASModelManager = require('./nas-model-manager.cjs');
const FleetAutoDistributor = require('./fleet-auto-distributor.cjs');

// Calculate distribution
const distributor = new FleetAutoDistributor();
const distribution = await distributor.autoDistribute();
await distributor.updateRegistry(distribution);

// Deploy to NAS + nodes
const nasManager = new NASModelManager();
await nasManager.deployFleet({ downloadAll: true });

// Verify
const report = nasManager.generateReport();
console.log('Deployment complete:', report);
```

## Monitoring & Verification

### Check Inventory

```bash
./scripts/download-to-nas.sh --list
```

Output:
```
NAS Model Inventory
===================

codestral:22b:
  Size: 12GB (12G)
  Downloaded: 2026-06-13T17:00:00Z
  Checksum: sha256:abc123...
  Distributed to: server-02

qwen2.5-coder:7b:
  Size: 4.7GB (4.7G)
  Downloaded: 2026-06-13T17:05:00Z
  Checksum: sha256:def456...
  Distributed to: localhost

Total models: 27
Last updated: 2026-06-13T17:30:00Z
```

### Verify Distribution

```bash
./scripts/distribute-to-nodes.sh --verify
```

Output:
```
Node: server-02
  ✓ codestral:22b (distributed)
  ✓ deepseek-r1:32b (distributed)

Node: localhost
  ✓ qwen2.5-coder:7b (distributed)
  ✗ starcoder2:7b (not distributed)
```

### Calculate Savings

```bash
./nas-model-manager.cjs savings
```

Output:
```json
{
  "total_models": 27,
  "total_model_size_gb": "135.00",
  "total_data_transferred_gb": "540.00",
  "nodes_served": 4,
  "internet_approach": {
    "time_minutes": "720.0",
    "time_hours": "12.00"
  },
  "nas_approach": {
    "time_minutes": "180.0",
    "time_hours": "3.00"
  },
  "savings": {
    "time_minutes": "540.0",
    "time_hours": "9.00",
    "bandwidth_gb": "405.00",
    "efficiency_gain": "75.0%"
  }
}
```

### Generate Report

```bash
./nas-model-manager.cjs report
```

## Troubleshooting

### NAS Not Mounted

```bash
# Check if NAS is mounted
ls -la /mnt/nas/ai-models

# If not mounted, mount it
sudo mount -t nfs nas-server:/volume1/ai-models /mnt/nas/ai-models

# Or set custom path
export NAS_MODELS_DIR=/path/to/nas
```

### Model Not Distributing

```bash
# 1. Verify model in NAS
./scripts/download-to-nas.sh --list

# 2. Check if node is reachable
ping server-02

# 3. Verify SSH access
ssh server-02 "ollama list"

# 4. Re-download if needed
./scripts/download-to-nas.sh codestral:22b

# 5. Re-distribute
./scripts/distribute-to-nodes.sh codestral:22b
```

### Checksum Mismatch

```bash
# Verify model integrity
./scripts/download-to-nas.sh --verify codestral:22b

# If failed, re-download
./scripts/download-to-nas.sh codestral:22b
```

### Missing Models

```bash
# Find missing models
./nas-model-manager.cjs missing

# Download missing models
./nas-model-manager.cjs download --high-priority
```

## Best Practices

1. **Download Once**: Always download to NAS first, never directly to nodes
2. **Verify First**: Check inventory before distributing
3. **Track Versions**: Use version-history.json for auditing
4. **Monitor Space**: NAS capacity monitoring (27 models ≈ 135GB)
5. **Use High-Priority**: Start with high-priority models for critical services
6. **Automate**: Use nas-model-manager.cjs for complete workflows
7. **Check Savings**: Regularly run savings report to justify NAS approach

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NAS_MODELS_DIR` | `/mnt/nas/ai-models` | NAS mount point |
| `OLLAMA_HOST` | `localhost:11434` | Ollama server for downloads |

## File Permissions

```bash
# Ensure scripts are executable
chmod +x scripts/*.sh
chmod +x nas-model-manager.cjs

# Ensure NAS is writable
sudo chown -R $USER:$USER /mnt/nas/ai-models
```

## Backup Recommendations

```bash
# Backup inventory and logs (small)
rsync -av /mnt/nas/ai-models/manifests/ backup-location/

# Backup models (large, optional - can re-download if needed)
rsync -av /mnt/nas/ai-models/ollama/ backup-location/
```

## ROI Analysis

### Cost Savings

**Internet Bandwidth Costs** (example: $0.10/GB egress):
- Without NAS: 540 GB × $0.10 = **$54.00**
- With NAS: 135 GB × $0.10 = **$13.50**
- **Savings: $40.50 (75%)**

**Time Savings** (example: $50/hour DevOps time):
- Without NAS: 12 hours × $50 = **$600.00**
- With NAS: 3 hours × $50 = **$150.00**
- **Savings: $450.00 (75%)**

### Total ROI
- **Per deployment cycle: $490.50 saved**
- **Per month (4 updates): $1,962.00**
- **Per year: $23,544.00**

**NAS Cost**: ~$500 one-time
**Break-even**: Less than 1 month

## Future Enhancements

- [ ] Automated background sync (cron job)
- [ ] Delta/incremental updates (only changed blobs)
- [ ] Parallel distribution (distribute to multiple nodes simultaneously)
- [ ] BitTorrent-style P2P distribution (nodes seed to each other)
- [ ] Automated capacity monitoring and alerts
- [ ] Web dashboard for monitoring
- [ ] Integration with CI/CD for automated model updates

## Summary

The NAS-based centralized model distribution system provides:

✅ **90% bandwidth savings** (download once vs. N times)  
✅ **10× faster distribution** (gigabit LAN vs. internet)  
✅ **Centralized management** (single source of truth)  
✅ **Integrity verification** (checksums tracked)  
✅ **Version control** (audit trail)  
✅ **ROI in < 1 month** (massive cost/time savings)

**The smart choice for fleet model management.**
