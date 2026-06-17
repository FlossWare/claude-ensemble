# Ollama Fleet Deployment Guide

## Overview

This guide covers deploying 27 Ollama models across 5 nodes to optimize disk space usage, reduce network latency, and maximize computational efficiency.

## Fleet Architecture

### Node Distribution Strategy

| Node | RAM | CPU | Assigned GB | Model Count | Primary Role |
|------|-----|-----|-------------|-------------|--------------|
| **localhost** | ?GB | ? | 36.9 GB | 9 models | Coding workstation - high-frequency models |
| **server-03** | 31GB | 8 | 45.0 GB | 3 models | Heavy models (22b, 32b parameters) |
| **server-02** | 31GB | 8 | 45.5 GB | 7 models | General-purpose + vision |
| **server-01** | 15GB | 8 | 21.0 GB | 5 models | Small general models |
| **aio-01** | 7GB | 2 | 7.0 GB | 3 models | Tiny fallback models |
| **pi-02** | 1GB | 4 ARM | - | - | ❌ EXCLUDED (insufficient RAM) |

**Total:** 155.4 GB across 27 models on 5 nodes

### Design Principles

1. **Locality First** - Keep high-frequency coding models on localhost for zero network latency
2. **Resource Matching** - Place large models on high-RAM nodes (server-02, server-03)
3. **Category Grouping** - Group related models together (coding, reasoning, general)
4. **Future-Ready** - Design supports model duplication for redundancy/load balancing
5. **Smart Routing** - Auto-discovery with health checks and failover

---

## Detailed Model Distribution

### localhost (36.9 GB - 9 models)
**Role:** Primary coding workstation

| Model | Size | Category | Frequency | Use Case |
|-------|------|----------|-----------|----------|
| qwen2.5-coder:7b | 4 GB | Coding | High | Fast code completion |
| yi-coder:9b | 5.5 GB | Coding | High | Balanced coding model |
| starcoder2:7b | 4 GB | Coding | High | Code completion |
| granite-code:8b | 5 GB | Coding | High | IBM coding model |
| sqlcoder:7b | 4 GB | Coding | Medium | SQL specialist |
| deepseek-r1:14b | 9 GB | Reasoning | High | Fast reasoning |
| mathstral:7b | 4 GB | Reasoning | Medium | Math specialist |
| granite-embedding | 0.7 GB | Specialized | High | Embedding model |
| nomic-embed-text | 0.7 GB | Specialized | High | Text embeddings |

**Rationale:** Most-used models stay local for zero-latency access during development.

---

### server-03 (45 GB - 3 models)
**Role:** Heavy computation - largest models

| Model | Size | Category | Frequency | Use Case |
|-------|------|----------|-----------|----------|
| codestral:22b | 15 GB | Coding | High | Premium code generation |
| starcoder2:15b | 10 GB | Coding | Medium | Large code completion |
| deepseek-r1:32b | 20 GB | Reasoning | Medium | Premium reasoning |

**Rationale:** 31GB RAM handles the largest models (22b, 32b parameters) with headroom for inference.

---

### server-02 (45.5 GB - 7 models)
**Role:** General-purpose + vision

| Model | Size | Category | Frequency | Use Case |
|-------|------|----------|-----------|----------|
| llava:13b | 8 GB | Specialized | Medium | Vision/image analysis |
| vicuna:13b | 8 GB | General | Medium | General assistant |
| gemma4:12b | 7 GB | General | Medium | Google Gemma v4 |
| solar:10.7b | 6.5 GB | General | Medium | General model |
| falcon3:10b | 6 GB | General | Low | Falcon 10B variant |
| hermes3:8b | 5 GB | General | Medium | Hermes v3 |
| granite4.1:8b | 5 GB | General | Medium | IBM Granite 4.1 |

**Rationale:** Mid-to-large general models + unique vision capability.

---

### server-01 (21 GB - 5 models)
**Role:** Smaller general models

| Model | Size | Category | Frequency | Use Case |
|-------|------|----------|-----------|----------|
| aya:8b | 5 GB | General | Low | Multilingual |
| falcon3:7b | 4 GB | General | Low | Falcon 7B variant |
| wizardlm2:7b | 4 GB | General | Low | WizardLM v2 |
| openchat:7b | 4 GB | General | Low | OpenChat assistant |
| zephyr:7b | 4 GB | General | Low | Zephyr assistant |

**Rationale:** 15GB RAM constraint - hosts smaller, less-frequently used models.

---

### aio-01 (7 GB - 3 models)
**Role:** Lightweight fallback

| Model | Size | Category | Frequency | Use Case |
|-------|------|----------|-----------|----------|
| gemma3:4b | 2.5 GB | General | Low | Tiny Gemma v3 |
| phi3.5:3.8b | 2.5 GB | General | Low | Microsoft Phi 3.5 |
| stablelm-zephyr:3b | 2 GB | General | Low | Tiny StableLM |

**Rationale:** Only tiny models fit in 7GB RAM - emergency fallback node.

---

## Deployment Steps

### Phase 1: Install Ollama on Remote Nodes

```bash
# Install Ollama on each node (runs official install script)
./ollama-fleet-deploy.sh install-ollama server-01
./ollama-fleet-deploy.sh install-ollama server-02
./ollama-fleet-deploy.sh install-ollama server-03
./ollama-fleet-deploy.sh install-ollama aio-01
```

This will:
1. SSH to the node
2. Run Ollama install script: `curl -fsSL https://ollama.com/install.sh | sh`
3. Enable and start Ollama systemd service
4. Verify Ollama API is responding

### Phase 2: Full Fleet Deployment

```bash
# Deploy all models according to registry
./ollama-fleet-deploy.sh deploy-all
```

This will:
1. Verify all nodes have Ollama installed
2. For each model:
   - If target is localhost: verify it exists (pull if missing)
   - If target is remote: export from localhost → rsync to node → import
3. Log all operations to `~/.claude/learning/logs/ollama-deploy-*.log`

### Phase 3: Verify Deployment

```bash
# Check all models are deployed correctly
./ollama-fleet-deploy.sh verify
```

Expected output:
```
Checking localhost...
  ✓ qwen2.5-coder:7b
  ✓ yi-coder:9b
  ...

Checking server-03...
  ✓ codestral:22b
  ✓ starcoder2:15b
  ✓ deepseek-r1:32b

Verification complete: 27/27 models deployed successfully
```

---

## Smart Router Usage

The `ollama-fleet-router.js` provides intelligent routing to the distributed fleet.

### Features

- **Auto-discovery** - Finds correct host for each model from registry
- **Health checks** - Periodic checks (every 30s) with automatic failover
- **Localhost preference** - Routes to localhost first when available
- **Load balancing** - Distributes load across duplicated models
- **Metrics tracking** - Tracks requests, latency, failures per model

### CLI Examples

```bash
# Route to best host for a model
node ollama-fleet-router.js route "qwen2.5-coder:7b"
# Output: {"host": "localhost", "port": 11434, "url": "http://localhost:11434", "latency": 45}

# Get fleet health status
node ollama-fleet-router.js status
# Shows: per-host health, per-model metrics, success rates

# Recommend best model for a task
node ollama-fleet-router.js recommend coding
# Output: {"modelName": "qwen2.5-coder:7b", "size_gb": 4, "category": "coding", ...}

# List models by category
node ollama-fleet-router.js list coding
node ollama-fleet-router.js list reasoning
node ollama-fleet-router.js list general
```

### Programmatic Usage

```javascript
import OllamaFleetRouter from './ollama-fleet-router.js';

const router = new OllamaFleetRouter();

// Route a request
const routing = await router.route('qwen2.5-coder:7b');
console.log(`Using ${routing.url} (latency: ${routing.latency}ms)`);

// Make actual request to routed host
const response = await fetch(`${routing.url}/api/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'qwen2.5-coder:7b',
    prompt: 'Write a Python function to...',
    stream: false
  })
});

// Get fleet status
const status = router.getStatus();
console.log('Healthy hosts:', 
  Object.entries(status.hosts)
    .filter(([_, s]) => s.healthy)
    .map(([h, _]) => h)
);
```

---

## Migration Without Re-downloading

Ollama stores models in `~/.ollama/models/` with this structure:

```
~/.ollama/models/
├── blobs/
│   └── sha256-<digest>  (actual model weights)
└── manifests/
    └── registry.ollama.ai/library/<model>/<tag>  (metadata)
```

### Manual Migration (Alternative to deploy script)

```bash
# 1. Export model from localhost
MODEL="qwen2.5-coder:7b"
EXPORT_DIR="/tmp/ollama-export-$MODEL"
mkdir -p "$EXPORT_DIR"

# Find manifest
MANIFEST="$HOME/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5-coder/7b"

# Extract blob digests from manifest
jq -r '.layers[].digest, .config.digest' "$MANIFEST" | while read digest; do
  cp "$HOME/.ollama/models/blobs/$digest" "$EXPORT_DIR/"
done

# Copy manifest
cp "$MANIFEST" "$EXPORT_DIR/manifest.json"

# 2. Transfer to target node
rsync -avz --progress "$EXPORT_DIR/" server-02:/tmp/ollama-import/

# 3. Import on target node
ssh server-02 << 'EOF'
  mkdir -p ~/.ollama/models/blobs
  mkdir -p ~/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5-coder
  
  cp /tmp/ollama-import/sha256-* ~/.ollama/models/blobs/
  cp /tmp/ollama-import/manifest.json \
     ~/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5-coder/7b
  
  # Verify
  ollama list | grep qwen2.5-coder
EOF

# 4. Cleanup
rm -rf "$EXPORT_DIR"
ssh server-02 "rm -rf /tmp/ollama-import"
```

---

## Space Savings

### Before Distribution (localhost only)
- **Total:** ~155 GB on localhost
- **Disk usage:** 87% full on /home

### After Distribution
- **localhost:** 36.9 GB (freed **~100 GB**)
- **server-03:** 45 GB
- **server-02:** 45.5 GB
- **server-01:** 21 GB
- **aio-01:** 7 GB

**Result:** Localhost disk usage drops from 87% to manageable levels while maintaining local access to most-used models.

---

## Performance Considerations

### Latency Expectations

| Scenario | Latency | Notes |
|----------|---------|-------|
| localhost model | 0-5ms | Direct local API call |
| LAN model (e.g., server-03) | 5-50ms | Gigabit Ethernet overhead |
| Model loading (cold) | 2-30s | One-time cost when model not in RAM |
| Model loading (warm) | 0ms | Model already in RAM from previous request |

### Optimization Tips

1. **Keep hot models local** - High-frequency coding models stay on localhost
2. **Duplicate critical models** - Can add `codestral:22b` to localhost if used frequently
3. **Pre-warm models** - Send dummy request to load model into RAM before real usage
4. **Monitor metrics** - Use `ollama-fleet-router.js status` to track usage patterns

### When to Duplicate Models

Add a model to multiple nodes if:
- Used frequently (>10 requests/hour)
- Critical to workflows (coding assistants)
- Source node shows high latency or frequent failures

Example duplication strategy:
```json
"codestral:22b": {
  "hosts": [
    {"hostname": "server-03", "port": 11434, "priority": 1},
    {"hostname": "localhost", "port": 11434, "priority": 2}  // Fallback
  ]
}
```

---

## Troubleshooting

### Model not found after import

```bash
# On target node, force refresh
ssh server-02 "sudo systemctl restart ollama"

# Or manually pull model (re-downloads, but guaranteed to work)
ssh server-02 "ollama pull qwen2.5-coder:7b"
```

### Health check failing

```bash
# Check Ollama is running
ssh server-02 "sudo systemctl status ollama"

# Check port is accessible
curl http://server-02:11434/api/tags

# Check firewall
ssh server-02 "sudo firewall-cmd --list-all"
```

### Insufficient RAM for model

Symptoms: Model loads slowly or crashes

```bash
# Check RAM usage during inference
ssh server-01 "htop"

# Move model to larger node
./ollama-fleet-deploy.sh migrate-model "vicuna:13b" server-02
```

### Disk space issues on node

```bash
# Check disk usage
ssh server-03 "df -h"

# Remove unused models
ssh server-03 "ollama rm <unused-model>"

# Clean up Ollama cache
ssh server-03 "rm -rf ~/.ollama/tmp"
```

---

## Future Enhancements

### 1. Load Balancing
Duplicate high-demand models across multiple nodes:
```json
"qwen2.5-coder:7b": {
  "hosts": [
    {"hostname": "localhost", "port": 11434, "priority": 1},
    {"hostname": "server-01", "port": 11434, "priority": 2}
  ]
}
```

### 2. Auto-scaling
Monitor usage and automatically migrate models:
```bash
# If localhost shows high latency, migrate to server
if [[ $(ollama-fleet-router.js status | jq '.models["qwen2.5-coder:7b"].avgLatency') -gt 100 ]]; then
  ./ollama-fleet-deploy.sh migrate-model "qwen2.5-coder:7b" server-01
fi
```

### 3. Model Registry API
Expose registry as HTTP API:
```javascript
// GET /api/models/qwen2.5-coder:7b
// Returns: routing info, health status, metrics

// GET /api/fleet/status
// Returns: all nodes health, capacity, load
```

### 4. Prometheus Metrics
Export metrics for monitoring:
```
ollama_requests_total{model="qwen2.5-coder:7b", node="localhost"} 1543
ollama_request_latency_ms{model="qwen2.5-coder:7b", node="localhost"} 42
ollama_failures_total{model="qwen2.5-coder:7b", node="localhost"} 3
```

---

## Quick Reference

### Essential Commands

```bash
# Full deployment
./ollama-fleet-deploy.sh deploy-all

# Verify deployment
./ollama-fleet-deploy.sh verify

# Route a request
node ollama-fleet-router.js route "qwen2.5-coder:7b"

# Check fleet health
node ollama-fleet-router.js status

# Recommend model for task
node ollama-fleet-router.js recommend coding
```

### Registry File Location
`~/.claude/learning/ollama-fleet-distribution.json`

### Logs Location
`~/.claude/learning/logs/ollama-deploy-*.log`

### Model Storage
- **localhost:** `~/.ollama/models/`
- **Remote nodes:** `~/.ollama/models/` (same structure)

---

## Summary

This distributed Ollama fleet design achieves:

✅ **Space savings:** Frees ~100 GB on localhost  
✅ **Low latency:** High-frequency models stay local  
✅ **Resource optimization:** Large models on high-RAM nodes  
✅ **Smart routing:** Auto-discovery with health checks  
✅ **Scalability:** Easy to add nodes or duplicate models  
✅ **Reliability:** Automatic failover to healthy nodes  

The fleet is ready for deployment when you run `./ollama-fleet-deploy.sh deploy-all`.
