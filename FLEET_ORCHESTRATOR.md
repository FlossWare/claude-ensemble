# Fleet Model Orchestrator

Intelligent orchestration system for distributed multi-vendor AI model fleet with zero duplication, smart routing, health monitoring, and dynamic node management.

## Overview

The Fleet Model Orchestrator manages a distributed fleet of AI models across multiple nodes, supporting:

- **All vendors**: Anthropic, OpenAI, Google, Meta, Mistral, Cerebras, Cloudflare, Ollama
- **Zero duplication**: Each model exists on exactly ONE node
- **Smart routing**: Route requests to the optimal model based on capabilities, cost, and availability
- **Health monitoring**: Automatic node health checks and failure detection
- **Dynamic management**: Nodes can join/leave the fleet dynamically
- **Cost awareness**: Prefer free local models over paid cloud APIs when possible

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Fleet Model Orchestrator                   │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────┐ │
│  │ Model Registry   │  │ Node Monitor     │  │ Planner   │ │
│  │ - 37 models      │  │ - Health checks  │  │ - Deploy  │ │
│  │ - 5 nodes        │  │ - Heartbeats     │  │ - Balance │ │
│  │ - Zero dup       │  │ - Lifecycle      │  │ - Optimal │ │
│  └──────────────────┘  └──────────────────┘  └───────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Smart Routing Engine                     │  │
│  │  - Capability matching                                │  │
│  │  - Cost optimization                                  │  │
│  │  - Locality preference (localhost > remote)           │  │
│  │  - Usage tracking (Thompson Sampling)                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    ┌───▼────┐         ┌────▼────┐         ┌───▼────┐
    │ Node 1 │         │ Node 2  │         │ Node N │
    │ Models │         │ Models  │         │ Models │
    └────────┘         └─────────┘         └────────┘
```

## Fleet Topology

### Current Distribution (Zero Duplication)

| Node       | RAM   | CPU | Models | Cloud | Local | Role              |
|------------|-------|-----|--------|-------|-------|-------------------|
| localhost  | 31GB  | 4   | 17     | 2     | 15    | Primary/Most-used |
| server-01  | 15GB  | 8   | 3      | 3     | 0     | Fast cloud APIs   |
| server-02  | 31GB  | 8   | 5      | 3     | 2     | Code specialist   |
| server-03  | 31GB  | 8   | 7      | 2     | 5     | Heavy/batch       |
| aio-01     | 7GB   | 2   | 5      | 0     | 5     | Lightweight       |
| **Total**  |       |     | **37** | **10**| **27**|                   |

### Model Distribution Strategy

**localhost (Primary)**
- Most frequently used models
- Zero network latency
- Cloud APIs: claude-opus-4, claude-fable-4
- Local: qwen2.5-coder:7b, granite-code:8b, mathstral:7b, sqlcoder:7b, etc.

**server-01 (Fast)**
- Fast cloud APIs only
- 8 cores for parallel execution
- Models: claude-sonnet-4, claude-haiku-4, llama-70b-fast

**server-02 (Code Specialist)**
- Code-focused models
- High RAM for large coding models
- Cloud: gpt-4o, gpt-o1, qwen-coder-32b
- Local: deepseek-r1:32b, codestral:22b

**server-03 (Heavy/Batch)**
- Large models (13b-15b parameters)
- High RAM for batch processing
- Cloud: gemini-2.0-flash-exp, cerebras-120b
- Local: starcoder2:15b, vicuna:13b, llava:13b, etc.

**aio-01 (Lightweight)**
- Small models only (3b-8b parameters)
- Low RAM node (7GB)
- Local: hermes3:8b, aya:8b, gemma3:4b, phi3.5:3.8b, stablelm-zephyr:3b

## Components

### 1. Model Mesh Orchestrator (`orchestrator-model-mesh.js`)

Core orchestration engine for routing and coordination.

**Key Features:**
- Model registry management
- Smart routing algorithm
- Node registration/unregistration
- Usage tracking for Thompson Sampling
- Health monitoring integration
- Zero-duplication enforcement

**API:**

```javascript
const ModelMeshOrchestrator = require('./orchestrator-model-mesh');
const orchestrator = new ModelMeshOrchestrator();

// Route request to best model
const result = orchestrator.routeRequest(['coding', 'reasoning'], {
  type: 'local',           // Prefer local models
  maxCost: 0,              // Free models only
  preferNode: 'localhost', // Prefer localhost
  vendor: 'ollama'         // Specific vendor
});

if (result.success) {
  console.log(`Use: ${result.model} on ${result.node}`);
  console.log(`Endpoint: ${result.endpoint}`);
  console.log(`Cost: $${result.cost_per_1m_tokens}/1M tokens`);
}

// Get available models
const models = orchestrator.getAvailableModels();

// Get node status
const status = orchestrator.getNodeStatus('localhost');

// Run health check
await orchestrator.healthCheck();

// Get fleet status
const fleetStatus = orchestrator.getFleetStatus();

// Rebalance suggestions
const rebalance = orchestrator.rebalance();
```

### 2. Fleet Node Monitor (`fleet-node-monitor.js`)

Health monitoring and node lifecycle management.

**Key Features:**
- Periodic health checks (30s interval)
- Node reachability via ping
- Ollama service validation
- Status change tracking
- Event logging
- Network discovery

**API:**

```javascript
const FleetNodeMonitor = require('./fleet-node-monitor');
const monitor = new FleetNodeMonitor();

// One-time health check
const results = await monitor.monitorFleet();

// Start continuous monitoring
await monitor.startMonitoring();

// Get health summary
const summary = await monitor.getHealthSummary();

// Discover Ollama nodes on network
const discovered = await monitor.discoverNodes('192.168.1');

// Get monitoring statistics
const stats = monitor.getStatistics();
```

### 3. Fleet Deployment Planner (`fleet-deployment-planner.js`)

Optimal model distribution planning.

**Key Features:**
- Resource-aware placement (RAM, CPU)
- Zero-duplication enforcement
- Locality optimization
- Load balancing
- Deployment script generation
- Violation detection

**API:**

```javascript
const FleetDeploymentPlanner = require('./fleet-deployment-planner');
const planner = new FleetDeploymentPlanner();

// Generate deployment plan
const plan = planner.planFromRegistry();

// Generate visual deployment map
const registry = planner.loadRegistry();
const map = planner.generateDeploymentMap(plan, registry.nodes);
console.log(map);

// Generate deployment script
const script = planner.generateDeploymentScript(plan);
fs.writeFileSync('deploy-fleet.sh', script, { mode: 0o755 });

// Export plan
planner.exportPlan(plan, '/tmp/deployment-plan.json');
```

### 4. Fleet CLI (`fleet-cli.js`)

Unified command-line interface.

**Commands:**

```bash
# Show fleet status
./fleet-cli.js status

# List all available models
./fleet-cli.js models

# Show node details
./fleet-cli.js node localhost

# Route request to best model
./fleet-cli.js route coding

# Run health check
./fleet-cli.js health

# Start continuous monitoring
./fleet-cli.js monitor

# Show deployment plan
./fleet-cli.js plan

# Rebalancing suggestions
./fleet-cli.js rebalance

# Help
./fleet-cli.js help
```

## Model Registry Schema

### Model Entry

```json
{
  "claude-opus-4": {
    "vendor": "anthropic",
    "type": "cloud-api",
    "node": "localhost",
    "endpoint": "https://api.anthropic.com/v1/messages",
    "capabilities": ["reasoning", "coding", "writing"],
    "cost_per_1m_tokens": 15.0,
    "context_window": 200000,
    "fallback_nodes": [],
    "status": "available"
  },
  "deepseek-r1:32b": {
    "vendor": "ollama",
    "type": "local",
    "node": "server-02",
    "endpoint": "http://server-02:11434",
    "capabilities": ["reasoning", "coding", "math"],
    "cost_per_1m_tokens": 0.0,
    "context_window": 64000,
    "model_size_gb": 19,
    "params": "32b",
    "fallback_nodes": [],
    "status": "available"
  }
}
```

### Node Entry

```json
{
  "localhost": {
    "hostname": "localhost",
    "status": "online",
    "last_heartbeat": "2026-06-13T12:00:00Z",
    "ram_gb": 31,
    "cpu_cores": 4,
    "roles": ["primary", "cloud-api", "local-ollama"],
    "models": ["claude-opus-4", "qwen2.5-coder:7b", ...],
    "total_models": 17,
    "cloud_models": 2,
    "local_models": 15,
    "priority": 1
  }
}
```

## Smart Routing Algorithm

The routing algorithm scores candidate models and selects the highest-scoring match:

```javascript
// Scoring factors (higher = better)
score += 100   // localhost (zero network latency)
score += 50    // local model (zero cost)
score -= cost * 2  // Lower cost preferred
score += log(usage_count + 1) * 10  // Frequently used
score += (10 - node_priority) * 5   // Node priority
score += 30    // Constraint preferences
```

**Routing Constraints:**

```javascript
const result = orchestrator.routeRequest(capabilities, {
  type: 'local' | 'cloud-api',  // Model type
  vendor: 'anthropic' | 'openai' | 'ollama' | ...,
  maxCost: 0,                    // Maximum cost per 1M tokens
  preferLocal: true,             // Prefer local models
  preferCloud: true,             // Prefer cloud APIs
  preferNode: 'localhost'        // Prefer specific node
});
```

## Usage Examples

### Example 1: Route coding task to best model

```javascript
const orchestrator = new ModelMeshOrchestrator();

// Find best coding model (any type, any cost)
const result = orchestrator.routeRequest('coding');

if (result.success) {
  console.log(`Model: ${result.model}`);
  console.log(`Node: ${result.node}`);
  console.log(`Endpoint: ${result.endpoint}`);
  console.log(`Cost: $${result.cost_per_1m_tokens}/1M`);

  // Use the model
  const response = await callModel(result.endpoint, prompt);
}
```

### Example 2: Route to free local model only

```javascript
// Find free local coding model
const result = orchestrator.routeRequest('coding', {
  type: 'local',
  maxCost: 0
});

if (result.success) {
  // Will route to qwen2.5-coder:7b, granite-code:8b, or similar
  console.log(`Using free local model: ${result.model}`);
}
```

### Example 3: Multi-AI consensus with fleet routing

```javascript
// Route different roles to different models
const workers = ['coding', 'reasoning', 'fast'].map(capability => {
  const route = orchestrator.routeRequest(capability);
  return {
    capability,
    model: route.model,
    node: route.node,
    endpoint: route.endpoint
  };
});

// Execute consensus in parallel
const results = await Promise.all(
  workers.map(w => callModel(w.endpoint, prompt))
);

// Arbiter synthesis
const arbiterRoute = orchestrator.routeRequest('reasoning');
const synthesis = await synthesize(arbiterRoute.endpoint, results);
```

### Example 4: Health monitoring

```javascript
const monitor = new FleetNodeMonitor();

// Start continuous monitoring
await monitor.startMonitoring();

// Check results
const summary = await monitor.getHealthSummary();

console.log('Fleet Health:');
console.log(`  Nodes: ${summary.totals.nodes}`);
console.log(`  Online: ${summary.totals.online}`);
console.log(`  Offline: ${summary.totals.offline}`);
console.log(`  Models: ${summary.totals.models}`);
console.log(`  Available: ${summary.totals.available_models}`);
```

### Example 5: Deployment planning

```javascript
const planner = new FleetDeploymentPlanner();

// Generate optimal deployment plan
const plan = planner.planFromRegistry();

console.log('Deployment Plan:');
console.log(`  Total Models: ${plan.total_models}`);
console.log(`  Zero Duplication: ${plan.zero_duplication}`);
console.log(`  Violations: ${plan.violations.length}`);

// Show deployment map
const registry = planner.loadRegistry();
const map = planner.generateDeploymentMap(plan, registry.nodes);
console.log(map);

// Generate deployment script
const script = planner.generateDeploymentScript(plan);
fs.writeFileSync('deploy.sh', script, { mode: 0o755 });
```

## Zero Duplication Policy

**Rule**: Each model exists on exactly ONE node.

**Why?**
- No confusion about which instance to use
- Clean separation of responsibilities
- Simplified routing logic
- Easier to track usage and costs
- No synchronization issues

**Enforcement:**
- Registry validation on load
- Duplicate detection in `registerNode()`
- Deployment planner validation
- Test suite verification

**Violations:**
If a duplicate is detected, the system:
1. Logs a violation
2. Refuses to register the duplicate
3. Returns error with details
4. Suggests remediation

## Health Monitoring

**Heartbeat Interval**: 30 seconds  
**Timeout Threshold**: 90 seconds (3 missed heartbeats)

**Health States:**
- `online`: Node reachable, services responding
- `offline`: Node unreachable via ping
- `degraded`: Node reachable but Ollama service down

**Automatic Actions:**
- Mark node offline after timeout
- Mark all node's models as unavailable
- Log status change events
- Update registry
- Re-enable when node comes back online

## Failure Handling

### Node Failure

When a node fails:
1. Health monitor detects missed heartbeat
2. Node marked offline
3. All models on node marked unavailable
4. Routing skips unavailable models
5. Alternative suggestions provided

### Model Unavailable

When no matching model available:
```javascript
const result = orchestrator.routeRequest('specialized-capability');

if (!result.success) {
  console.log('Error:', result.error);
  console.log('Suggestions:', result.suggestion);
  // Suggestions include partial matches with missing capabilities
}
```

### Network Partition

If localhost loses connectivity to workers:
- localhost models still available (most frequently used)
- Cloud APIs still accessible from localhost
- Degraded service but not complete failure

## Performance Optimization

**Locality Preference:**
- localhost models have zero network latency
- Most frequently used models placed on localhost
- Routing algorithm heavily weights localhost (+100 score)

**Cost Optimization:**
- Free local models preferred over paid cloud APIs
- Usage tracking identifies high-frequency tasks → move to local
- Cost-per-million-tokens factored into routing score

**Load Balancing:**
- Rebalance analyzer detects overutilized nodes
- Suggests model migration
- Deployment planner optimizes initial distribution

## Testing

Run the comprehensive test suite:

```bash
./test-fleet-orchestrator.js
```

**Tests:**
- Registry loads successfully
- Zero duplication enforcement
- Model-node assignment validation
- Routing with capabilities
- Routing with constraints
- Localhost preference
- Health monitoring
- Deployment planning
- Distribution statistics
- All models have required fields
- All nodes have required fields

## Files

| File                              | Purpose                              |
|-----------------------------------|--------------------------------------|
| `fleet-model-registry.json`       | Model and node registry              |
| `orchestrator-model-mesh.js`      | Core orchestration engine            |
| `fleet-node-monitor.js`           | Health monitoring and lifecycle      |
| `fleet-deployment-planner.js`     | Deployment planning and optimization |
| `fleet-cli.js`                    | Unified CLI interface                |
| `test-fleet-orchestrator.js`      | Comprehensive test suite             |
| `fleet-usage-stats.json`          | Usage tracking for Thompson Sampling |
| `fleet-monitor-events.json`       | Health monitoring event log          |
| `fleet-deployment-plan.json`      | Generated deployment plan            |
| `FLEET_ORCHESTRATOR.md`           | This documentation                   |

## Integration with Multi-AI Workflows

The orchestrator integrates seamlessly with existing multi-AI workflows:

```javascript
// In your workflow
const orchestrator = new ModelMeshOrchestrator();

// Route arbiter
const arbiterRoute = orchestrator.routeRequest('reasoning');
const arbiter = { model: arbiterRoute.model, server: arbiterRoute.node };

// Route workers
const workers = config.workers.models.map(capability => {
  const route = orchestrator.routeRequest(capability);
  return {
    name: route.model,
    server: route.node,
    endpoint: route.endpoint
  };
});

// Execute multi-AI workflow with optimal routing
const result = await multiAIConsensus({ arbiter, workers, prompt });
```

## Future Enhancements

**Planned:**
- [ ] Auto-scaling: Spin up nodes based on load
- [ ] GPU awareness: Track GPU availability for large models
- [ ] Cost tracking: Per-model cost accumulation
- [ ] Performance metrics: Latency, throughput tracking
- [ ] Model migration: Automated model movement for rebalancing
- [ ] Fleet dashboard: Web UI for monitoring and control
- [ ] Thompson Sampling: Adaptive routing based on success rates
- [ ] Cache coordination: Distributed prompt caching
- [ ] Backup/restore: Registry and stats backup
- [ ] Multi-region: Geographic distribution

## License

Part of claude-global-skills project.

## Author

Generated by Claude Sonnet 4.5 (June 2026)
