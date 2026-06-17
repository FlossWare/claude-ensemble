# Hardware-Aware Auto-Distribution: Quick Start

Get your fleet auto-distributed in 3 commands.

## Prerequisites

- SSH access to all nodes (`ssh-copy-id <hostname>` for each)
- Ollama installed on nodes that will run local models
- API keys configured (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)

## 3-Step Setup

```bash
# Step 1: Probe hardware capabilities
./fleet-cli.cjs probe-hardware

# Step 2: Preview optimal distribution
./fleet-cli.cjs auto-distribute

# Step 3: Apply distribution to registry
./fleet-cli.cjs update-registry
```

## What Just Happened?

1. **Probed** each node via SSH:
   - Detected CPU cores, RAM, disk space
   - Detected Ollama installation + models
   - Classified nodes into tiers (TIER 1-4)

2. **Calculated** optimal distribution:
   - Loaded model requirements (37 models)
   - Ran bin-packing algorithm
   - Assigned each model to best-fit node
   - Validated zero duplication + capacity limits

3. **Updated** registry:
   - Wrote optimal distribution to `fleet-model-registry.json`
   - All models now have assigned nodes
   - Zero duplication enforced

## Verify It Worked

```bash
# Check distribution status
./fleet-cli.cjs status

# Validate constraints
./fleet-cli.cjs validate

# Show node utilization
./fleet-cli.cjs show-capacity
```

## Expected Output

```
Fleet Hardware Summary
================================================================================
Reachable Nodes: 5/5
Total CPU Cores: 42
Total RAM: 115GB
Total Disk: 1350GB

Node Classification:
  ✓ localhost: TIER 1 (heavy) - 64GB RAM, 16 CPU
  ✓ server-02: TIER 2 (medium) - 31GB RAM, 8 CPU
  ✓ server-01: TIER 3 (light) - 15GB RAM, 8 CPU
  ✓ aio-01: TIER 4 (tiny) - 7GB RAM, 2 CPU
  ✗ server-03: OFFLINE

📊 Auto-Distribution:
  localhost: 17 models (72.9% utilized)
  server-02: 7 models (96.9% utilized)
  server-01: 8 models (0.8% utilized)
  aio-01: 5 models (96.0% utilized)

✅ Distribution valid: All models assigned, zero duplication
```

## When to Re-run

Re-run auto-distribution when:
- **Node added**: New hardware available
- **Node removed**: Redistribute models to remaining nodes
- **Hardware upgraded**: More RAM/CPU on existing node
- **Models added**: New models to distribute
- **Usage patterns change**: High-frequency models should move to localhost

```bash
# Re-optimize anytime
./fleet-cli.cjs probe-hardware
./fleet-cli.cjs update-registry
```

## Troubleshooting

### Node unreachable
```bash
# Fix SSH access
ssh-copy-id <hostname>
ping <hostname>
```

### Capacity violations
```bash
# Check which models don't fit
./fleet-cli.cjs auto-distribute | grep "no_capacity"

# Options:
# - Add more nodes
# - Free up RAM on existing nodes
# - Remove unused models
```

### Ollama not detected
```bash
# Install Ollama
ssh <hostname> 'curl -fsSL https://ollama.ai/install.sh | sh'

# Verify
ssh <hostname> 'which ollama'
```

## Files to Review

- `fleet-auto-distribution.json` - Detailed distribution plan
- `fleet-hardware-profiles.json` - Hardware probe results
- `fleet-model-registry.json` - Updated registry (after update-registry)
- `model-requirements.json` - Model resource requirements (edit to customize)

## Next Steps

1. **Use the fleet**:
   ```bash
   # Route requests to optimal models
   ./fleet-cli.cjs route coding
   ./fleet-cli.cjs route reasoning
   ```

2. **Monitor health**:
   ```bash
   # Continuous monitoring
   ./fleet-cli.cjs monitor
   ```

3. **Customize** `model-requirements.json`:
   - Adjust RAM requirements
   - Set priority (high/medium/low)
   - Set frequency (high → localhost preference)

## Advanced

### Run Tests
```bash
./test-hardware-aware-distribution.cjs
```

### Probe Single Node
```bash
./fleet-hardware-prober.cjs node localhost
```

### Custom Node List
```bash
./fleet-cli.cjs probe-hardware localhost server-01 server-02
```

## Architecture

```
Hardware Probe → Model Requirements → Bin-Packing → Validation → Registry Update
    (SSH)           (JSON DB)         (Algorithm)    (Constraints)   (fleet-model-registry.json)
```

## Support

See documentation:
- `HARDWARE_AWARE_DISTRIBUTION.md` - Full documentation
- `HARDWARE_AWARE_SUMMARY.md` - Implementation summary
- `FLEET_ORCHESTRATOR.md` - Overall fleet architecture
