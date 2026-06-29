# Fleet Orchestrator Quick Start

5-minute guide to using the distributed multi-vendor model fleet orchestrator.

## Quick Commands

```bash
# Show fleet status
./fleet-cli.cjs status

# List all available models
./fleet-cli.cjs models

# Route a request to best model
./fleet-cli.cjs route coding

# Check node health
./fleet-cli.cjs health

# Show deployment plan
./fleet-cli.cjs plan

# Get help
./fleet-cli.cjs help
```

## Key Concepts

**Zero Duplication**: Each model exists on exactly ONE node. No exceptions.

**Smart Routing**: Automatically selects the best model based on:
- Capabilities (coding, reasoning, math, etc.)
- Cost (prefer free local models)
- Locality (prefer localhost = zero latency)
- Usage frequency (prefer battle-tested models)

**Fleet Topology**:
- localhost: 17 models (primary, most-used)
- server-01: 3 models (fast cloud APIs)
- server-02: 5 models (code specialist)
- server-03: 7 models (heavy/batch)
- aio-01: 5 models (lightweight)

## Common Tasks

### Find Best Model for a Task

```bash
# Find best coding model
./fleet-cli.cjs route coding

# Find best reasoning model
./fleet-cli.cjs route reasoning

# Find best math model
./fleet-cli.cjs route math
```

### Check Node Status

```bash
# Check localhost
./fleet-cli.cjs node localhost

# Check worker node
./fleet-cli.cjs node server-02
```

### Monitor Fleet Health

```bash
# One-time health check
./fleet-cli.cjs health

# Continuous monitoring (Ctrl+C to stop)
./fleet-cli.cjs monitor
```

## Use in Code

### Basic Routing

```javascript
const ModelMeshOrchestrator = require('./orchestrator-model-mesh.cjs');
const orchestrator = new ModelMeshOrchestrator();

// Route to best coding model
const result = orchestrator.routeRequest('coding');

if (result.success) {
  console.log(`Model: ${result.model}`);
  console.log(`Node: ${result.node}`);
  console.log(`Endpoint: ${result.endpoint}`);
  console.log(`Cost: $${result.cost_per_1m_tokens}/1M tokens`);
}
```

### Advanced Routing with Constraints

```javascript
// Find free local coding model
const result = orchestrator.routeRequest('coding', {
  type: 'local',           // Local models only
  maxCost: 0,              // Free only
  preferNode: 'localhost'  // Prefer localhost
});

// Find cloud API for reasoning
const result = orchestrator.routeRequest('reasoning', {
  type: 'cloud-api',
  vendor: 'anthropic'
});
```

### Multi-AI Consensus

```javascript
// Route different capabilities to different models
const workers = ['coding', 'reasoning', 'fast'].map(capability => {
  const route = orchestrator.routeRequest(capability);
  return {
    model: route.model,
    node: route.node,
    endpoint: route.endpoint
  };
});

// Execute in parallel
const results = await Promise.all(
  workers.map(w => callModel(w.endpoint, prompt))
);

// Arbiter synthesis
const arbiterRoute = orchestrator.routeRequest('reasoning');
const synthesis = await synthesize(arbiterRoute.endpoint, results);
```

## Capabilities

Models can have these capabilities:
- `coding` - Code generation, debugging
- `reasoning` - Complex reasoning, analysis
- `math` - Mathematical problem solving
- `chat` - Conversational tasks
- `fast` - Quick responses
- `heavy` - Complex, intensive tasks
- `multimodal` - Vision, images
- `vision` - Image understanding
- `debugging` - Code debugging
- `sql` - SQL generation
- `embedding` - Text embeddings
- `multilingual` - Multiple languages

## Model Types

**cloud-api**: Paid cloud APIs (Anthropic, OpenAI, Google)
- Cost: $0-$15 per 1M tokens
- Access via HTTPS endpoints
- No local resources required

**local**: Free Ollama models
- Cost: $0 (free)
- Access via HTTP on port 11434
- Requires RAM on host node

## Cost Optimization

Routing automatically prefers free local models over paid cloud APIs when capabilities match:

```javascript
// Will route to qwen2.5-coder:7b (FREE) instead of gpt-4o ($2.50)
const result = orchestrator.routeRequest('coding');

// Force cloud API if needed
const result = orchestrator.routeRequest('coding', {
  type: 'cloud-api'
});
```

## Localhost Advantage

Models on localhost have zero network latency and are heavily preferred in routing:

- Score bonus: +100 points
- Most frequently used models automatically placed on localhost
- Always available (no network dependencies)

## Health Monitoring

The fleet monitor automatically:
- Pings nodes every 30 seconds
- Marks offline after 90 seconds (3 missed heartbeats)
- Updates model availability
- Logs status changes
- Detects Ollama service failures

When a node goes offline:
- All its models marked unavailable
- Routing skips those models
- Alternative suggestions provided
- Auto-recovery when node returns

## Failure Handling

### No Matching Model

```javascript
const result = orchestrator.routeRequest('specialized-task');

if (!result.success) {
  console.log('Error:', result.error);
  console.log('Suggestions:', result.suggestion);
  // Suggestions include partial matches
}
```

### Node Offline

When routing to an offline node's model:
- Model marked unavailable
- Not included in routing candidates
- Alternatives automatically selected
- User sees next-best option

## Files

| File | Purpose |
|------|---------|
| `fleet-model-registry.json` | Model and node registry |
| `orchestrator-model-mesh.cjs` | Core orchestrator |
| `fleet-node-monitor.cjs` | Health monitoring |
| `fleet-deployment-planner.cjs` | Deployment planning |
| `fleet-cli.cjs` | CLI interface |
| `fleet-usage-stats.json` | Usage tracking |

## Testing

Run the comprehensive test suite:

```bash
node test-fleet-orchestrator.cjs
```

Expected: 21 passed, 0 failed

## Distribution Summary

**Total**: 37 models across 5 nodes

**Cloud APIs** (10):
- Anthropic: claude-opus-4, claude-sonnet-4, claude-haiku-4, claude-fable-4
- OpenAI: gpt-4o, gpt-o1
- Google: gemini-2.0-flash-exp
- Cerebras: cerebras-120b (FREE)
- Cloudflare: qwen-coder-32b (FREE), llama-70b-fast (FREE)

**Local Ollama** (27):
- 32b: deepseek-r1:32b
- 22b: codestral:22b
- 15b: starcoder2:15b
- 13b-14b: vicuna:13b, llava:13b, gemma4:12b, deepseek-r1:14b
- 10b: solar:10.7b, falcon3:10b
- 9b: yi-coder:9b
- 8b: hermes3:8b, aya:8b, granite4.1:8b, granite-code:8b
- 7b: wizardlm2:7b, openchat:7b, falcon3:7b, zephyr:7b, starcoder2:7b, qwen2.5-coder:7b, mathstral:7b, sqlcoder:7b
- Small: gemma3:4b, phi3.5:3.8b, stablelm-zephyr:3b
- Embedding: granite-embedding, nomic-embed-text

**Zero Duplication**: ✓ Enforced

## Next Steps

1. Run health check: `./fleet-cli.cjs health`
2. Test routing: `./fleet-cli.cjs route coding`
3. Monitor fleet: `./fleet-cli.cjs monitor`
4. Read full docs: `FLEET_ORCHESTRATOR.md`

## Support

For detailed documentation, see `FLEET_ORCHESTRATOR.md`.

For code examples, see the test suite: `test-fleet-orchestrator.cjs`.

For troubleshooting, check the event log: `fleet-monitor-events.json`.
