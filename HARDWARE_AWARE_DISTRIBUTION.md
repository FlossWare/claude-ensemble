# Hardware-Aware Automatic Model Distribution

Intelligent model distribution system that **probes actual hardware capabilities** on each fleet node and automatically assigns models based on real-time resource availability.

## Overview

Instead of manual model assignment, the system:
1. **Probes hardware** on each node (CPU, RAM, disk, GPU)
2. **Knows model requirements** (RAM needed, CPU cores, disk space)
3. **Auto-distributes** models using bin-packing algorithm
4. **Enforces zero duplication** (each model on exactly ONE node)
5. **Optimizes locality** (high-frequency models on localhost)

## Quick Start

```bash
# 1. Probe hardware on all nodes
./fleet-cli.cjs probe-hardware

# 2. Calculate optimal distribution (preview, no changes)
./fleet-cli.cjs auto-distribute

# 3. Apply distribution to registry
./fleet-cli.cjs update-registry

# 4. Validate distribution
./fleet-cli.cjs validate
```

## Components

### 1. Hardware Prober (`fleet-hardware-prober.cjs`)

Probes each node via SSH to detect:
- **CPU cores**: `nproc`
- **RAM**: `free -g` (total and available)
- **Disk space**: `df -BG ~` (total and free)
- **GPU**: `lspci | grep -i vga` (presence check)
- **Ollama**: `which ollama` + `ollama list` (installed models)
- **API keys**: Environment variable checks

**Tier Classification**:
- **TIER 1 (heavy)**: 60GB+ RAM, 16+ CPU cores
- **TIER 2 (medium)**: 30GB+ RAM, 8+ CPU cores
- **TIER 3 (light)**: 15GB+ RAM, 4+ CPU cores
- **TIER 4 (tiny)**: Less than 15GB RAM

**Usage**:
```bash
# Probe all default nodes
./fleet-hardware-prober.cjs probe

# Show summary with tier classification
./fleet-hardware-prober.cjs summary

# Probe specific nodes
./fleet-hardware-prober.cjs probe localhost server-01 server-02

# Probe single node
./fleet-hardware-prober.cjs node localhost
```

**Output**: `fleet-hardware-profiles.json`

### 2. Model Requirements Database (`model-requirements.json`)

Defines resource requirements for each model:

```json
{
  "deepseek-r1:32b": {
    "vendor": "ollama",
    "type": "local",
    "ram_gb": 19,
    "cpu_cores_min": 4,
    "gpu_required": false,
    "disk_gb": 19,
    "priority": "high",
    "frequency": "high"
  },
  "claude-opus-4": {
    "vendor": "anthropic",
    "type": "cloud-api",
    "ram_gb": 0.1,
    "cpu_cores_min": 1,
    "gpu_required": false,
    "disk_gb": 0,
    "requires_api_key": true,
    "api_key_env": "ANTHROPIC_API_KEY",
    "priority": "high",
    "frequency": "high"
  }
}
```

**Fields**:
- `ram_gb`: RAM required to run model
- `cpu_cores_min`: Minimum CPU cores needed
- `gpu_required`: Whether GPU is required
- `disk_gb`: Disk space needed for model storage
- `priority`: high/medium/low (affects placement preference)
- `frequency`: high/medium/low (high-frequency → localhost preference)

### 3. Auto-Distributor (`fleet-auto-distributor.cjs`)

Implements bin-packing algorithm to optimally distribute models:

**Algorithm**:
1. Probe hardware capabilities
2. Load model requirements
3. Separate cloud API vs local models
4. Sort local models by size (largest first)
5. For each model:
   - Find nodes with sufficient capacity
   - Score candidates:
     - **Localhost preference** for high-frequency models (+1000 score)
     - **Best-fit**: prefer least wasted RAM
     - **Load balancing**: penalize overloaded nodes
   - Assign to highest-scoring node
6. Validate zero duplication and capacity limits

**Scoring Function**:
```javascript
score = 0
+ (localhost && high_frequency ? 1000 : 0)  // Localhost preference
- (available_ram - model_size)              // Best-fit (minimize waste)
- (ram_used / ram_total) * 100              // Load balancing
- (local_model_count) * 10                  // Distribute evenly
```

**Usage**:
```bash
# Calculate distribution (preview)
./fleet-auto-distributor.cjs auto-distribute

# Calculate and update registry
./fleet-auto-distributor.cjs update-registry
```

**Output**: `fleet-auto-distribution.json`

### 4. Fleet CLI Integration

New commands added to `fleet-cli.cjs`:

```bash
# Hardware probing
fleet-cli.cjs probe-hardware        # Probe all nodes, show tiers

# Auto-distribution
fleet-cli.cjs auto-distribute       # Calculate optimal distribution (preview)
fleet-cli.cjs update-registry       # Calculate and apply to registry

# Validation
fleet-cli.cjs validate              # Check distribution validity
fleet-cli.cjs show-capacity         # Show node utilization
```

## Example Workflow

### Initial Setup

```bash
# 1. Probe hardware to understand fleet capabilities
$ ./fleet-cli.cjs probe-hardware

Fleet Hardware Summary
================================================================================
Reachable Nodes: 5/5
Total CPU Cores: 42
Total RAM: 115GB
Total Disk: 1350GB
Nodes with GPU: 0
Nodes with Ollama: 3

Node Classification:
  ✓ localhost: TIER 1 (heavy)
     64GB RAM, 16 CPU, 500GB free
     Ollama: 15 models installed

  ✓ server-02: TIER 2 (medium)
     31GB RAM, 8 CPU, 200GB free
     Ollama: 2 models installed

  ✓ server-01: TIER 3 (light)
     15GB RAM, 8 CPU, 150GB free
     Ollama: 0 models installed

  ✓ aio-01: TIER 4 (tiny)
     7GB RAM, 2 CPU, 100GB free
     Ollama: 5 models installed

  ✗ server-03: OFFLINE (skipped)
```

### Auto-Distribution

```bash
# 2. Calculate optimal distribution
$ ./fleet-cli.cjs auto-distribute

🔬 Step 1: Probing hardware capabilities...
🧊 Step 2: Loading model requirements...
  Loaded 37 model definitions

📦 Step 3: Distributing models...
  Cloud API models: 10
  Local Ollama models: 27

🚀 Fleet Auto-Distribution Results
================================================================================

📊 Auto-Distribution:
  localhost (62GB): 17 models, 45.2GB used
    Utilization: ████████████████████ 72.9%
    Cloud: 4, Local: 13

  server-02 (29GB): 7 models, 28.1GB used
    Utilization: ██████████████████████████████ 96.9%
    Cloud: 2, Local: 5

  server-01 (13GB): 8 models, 0.1GB used
    Utilization: █ 0.8%
    Cloud: 3, Local: 0

  aio-01 (5GB): 5 models, 4.8GB used
    Utilization: ████████████████████████████████ 96.0%
    Cloud: 1, Local: 4

📈 Statistics:
  Total Models: 37
  Cloud API: 10
  Local Ollama: 27
  Total Size: 78.2GB
  Violations: 0

✅ Distribution valid: All models assigned, zero duplication, all constraints met

📌 Next steps:
  1. Review the distribution plan in fleet-auto-distribution.json
  2. Run "fleet-cli.cjs update-registry" to apply the plan
```

### Apply Distribution

```bash
# 3. Apply distribution to registry
$ ./fleet-cli.cjs update-registry

# Same output as above, plus:
✅ Registry updated: /path/to/fleet-model-registry.json

✅ Registry updated successfully!
   Run "fleet-cli.cjs status" to see the new distribution
```

### Validate

```bash
# 4. Validate distribution
$ ./fleet-cli.cjs validate

Validation Results
================================================================================

Zero Duplication: ✅ PASS
All Models Assigned: ✅ PASS
  Total: 37 models
Node Health: ✅ PASS
  Online: 4/5 nodes

✅ Fleet distribution is valid!
```

## Testing

Run comprehensive test suite:

```bash
$ ./test-hardware-aware-distribution.cjs

╔═══════════════════════════════════════════════════════════════╗
║  Hardware-Aware Auto-Distribution Test Suite                 ║
╚═══════════════════════════════════════════════════════════════╝

=== Testing Hardware Probe ===

🧪 Test: Localhost reachable
   ✅ PASS
🧪 Test: CPU cores detected
   ✅ PASS
🧪 Test: RAM detected
   ✅ PASS
🧪 Test: Disk space detected
   ✅ PASS
🧪 Test: Node classification
   ✅ PASS

=== Testing Model Requirements ===

🧪 Test: Requirements file exists
   ✅ PASS
🧪 Test: Models defined
   ✅ PASS
🧪 Test: Cloud API models defined
   ✅ PASS
🧪 Test: Local models defined
   ✅ PASS
🧪 Test: Model has RAM requirements
   ✅ PASS

=== Testing Auto-Distribution ===

🧪 Test: Distribution generated
   ✅ PASS
🧪 Test: Localhost assignment exists
   ✅ PASS
🧪 Test: Models assigned to localhost
   ✅ PASS
🧪 Test: Zero duplication
   ✅ PASS
🧪 Test: No capacity violations
   ✅ PASS
🧪 Test: Statistics calculated
   ✅ PASS
🧪 Test: Distribution is valid
   ✅ PASS

================================================================================
Test Results Summary
================================================================================
Total Tests: 19
Passed: 19 ✅
Failed: 0 ❌

✅ All tests passed!
```

## Algorithm Details

### Bin-Packing for Local Models

The system uses a **best-fit decreasing (BFD)** bin-packing algorithm:

1. **Sort models** by RAM requirement (largest → smallest)
2. For each model:
   - Find **candidate nodes** with sufficient capacity
   - **Score each candidate**:
     - Localhost bonus for high-frequency models
     - Best-fit: minimize wasted RAM
     - Load balancing: penalize overloaded nodes
   - **Assign to highest-scoring node**
3. **Update node capacity** after each assignment

This ensures:
- Large models placed first (better packing efficiency)
- Minimal RAM waste
- Balanced load across nodes
- Zero duplication (each model assigned exactly once)

### Cloud API Distribution

Cloud models have minimal resource requirements, so distribution focuses on:
1. **High-frequency models → localhost** (zero network latency)
2. **Even distribution** across nodes (load balancing)
3. **Role-based placement** (coding models → code-specialist nodes)

## Constraints and Validation

The system enforces:

1. **Zero duplication**: Each model on exactly ONE node
2. **Capacity limits**: Node RAM - 2GB buffer > model size
3. **CPU requirements**: Node CPU cores >= model minimum
4. **Ollama requirement**: Local models only on nodes with Ollama installed
5. **API key requirement**: Cloud models only if API key present (future enhancement)

## Files Generated

- `fleet-hardware-profiles.json`: Hardware probe results
- `fleet-auto-distribution.json`: Optimal distribution plan
- `fleet-model-registry.json`: Updated registry (if applied)
- `test-results-distribution.json`: Test results

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Fleet CLI (fleet-cli.cjs)                              │
│  - probe-hardware                                       │
│  - auto-distribute                                      │
│  - update-registry                                      │
│  - validate                                             │
└────────────┬────────────────────────────────────────────┘
             │
             ├──► Fleet Hardware Prober
             │    - SSH to nodes
             │    - Detect CPU, RAM, disk, GPU
             │    - Classify into tiers
             │    - Export profiles
             │
             ├──► Fleet Auto-Distributor
             │    - Load hardware profiles
             │    - Load model requirements
             │    - Run bin-packing algorithm
             │    - Validate constraints
             │    - Update registry
             │
             └──► Model Requirements Database
                  - RAM, CPU, disk for each model
                  - Priority and frequency
                  - Vendor and type
```

## Benefits

1. **Dynamic**: Uses real-time hardware probes, not static config
2. **Optimal**: Bin-packing minimizes wasted resources
3. **Smart**: High-frequency models on localhost (low latency)
4. **Balanced**: Distributes load evenly across nodes
5. **Safe**: Enforces zero duplication, validates constraints
6. **Flexible**: Re-run anytime to adapt to hardware changes

## Future Enhancements

1. **GPU-aware placement**: Assign GPU-requiring models to GPU nodes
2. **Dynamic rebalancing**: Monitor usage and rebalance automatically
3. **Cost optimization**: Factor in model cost for cloud APIs
4. **Network latency**: Measure and optimize for network topology
5. **Multi-tier fallback**: Assign fallback nodes for high-availability
6. **Predictive scaling**: Predict future resource needs

## Troubleshooting

### Node unreachable
- Ensure SSH access is configured: `ssh-copy-id <hostname>`
- Check network connectivity: `ping <hostname>`

### Ollama not detected
- Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
- Verify installation: `which ollama`

### Capacity violations
- Free up RAM on nodes
- Add more nodes to fleet
- Remove unused models

### Distribution fails
- Check `fleet-auto-distribution.json` for violations
- Review node capacities: `./fleet-cli.cjs show-capacity`
- Validate requirements: ensure `model-requirements.json` is accurate

## See Also

- `FLEET_ORCHESTRATOR.md`: Overall fleet architecture
- `FLEET_OPTIMAL_DISTRIBUTION.md`: Distribution strategies
- `FLEET_QUICKSTART.md`: Getting started guide
