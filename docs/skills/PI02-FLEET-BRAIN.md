# pi-02 Fleet Brain Deployment

## Summary

pi-02 is now the **FLEET BRAIN** - the central orchestration hub for your distributed model fleet. It provides intelligent routing, health monitoring, and node management for all models across all nodes.

## What's Deployed

### Core Components

1. **REST API Server** (`pi02-orchestrator-api.cjs`)
   - HTTP API on port 8080
   - Smart model routing based on capabilities, cost, latency
   - Node registration and heartbeat tracking
   - Real-time fleet status

2. **Model Mesh Orchestrator** (`orchestrator-model-mesh.cjs`)
   - Zero-duplication model registry
   - Intelligent routing algorithm
   - Usage tracking for optimization
   - Cost-aware routing (cloud vs local)

3. **Health Monitor** (`fleet-node-monitor.cjs`)
   - 30-second heartbeat checks
   - Auto-detects offline nodes (90s timeout)
   - Network reachability monitoring
   - Ollama service health checks

4. **Client Library** (`fleet-orchestrator-client.cjs`)
   - Auto-registration for nodes
   - Automatic heartbeat transmission
   - Simple HTTP API wrapper
   - Auto-detects Ollama models

### Systemd Services

Two services run continuously on pi-02:

1. **fleet-brain-api.service**
   - Main API server
   - Port: 8080
   - Memory limit: 256MB
   - CPU limit: 50%
   - Auto-start on boot

2. **fleet-health-monitor.service**
   - Background health checks
   - 30s interval
   - Memory limit: 128MB
   - CPU limit: 25%
   - Auto-start on boot

## Architecture

```
                    ┌─────────────────────┐
                    │       pi-02         │
                    │   (Fleet Brain)     │
                    │  ┌───────────────┐  │
                    │  │  REST API     │  │
                    │  │  Port 8080    │  │
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │ Orchestrator  │  │
                    │  │ Health Monitor│  │
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │   Registry    │  │
                    │  │  37 models    │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
                             ▲
                             │ HTTP API
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼───┐     ┌───▼────┐    ┌───▼────┐
         │server-01│     │server-02│    │server-03│
         │ Ollama │     │ Ollama │    │ Ollama │
         │ Models │     │ Models │    │ Models │
         └────────┘     └────────┘    └────────┘
              │              │              │
              └──────────────┴──────────────┘
                  Heartbeat (30s)
```

## Quick Start

### 1. Deploy to pi-02

```bash
./deploy-to-pi02.sh
```

### 2. Verify Deployment

```bash
curl http://pi-02:8080/status
```

### 3. Register Fleet Nodes

On each node (server-01, server-02, server-03):

```bash
# Copy client
scp fleet-orchestrator-client.cjs server-01:/home/user/

# SSH and register
ssh server-01
./fleet-orchestrator-client.cjs auto-register
```

### 4. Test Routing

```bash
curl -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{"capabilities": ["coding"]}'
```

### 5. Run Test Suite

```bash
./test-pi02-api.sh
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/route` | Route request to best model |
| `GET`  | `/models` | List all available models |
| `GET`  | `/nodes` | List fleet nodes |
| `GET`  | `/nodes/<name>` | Get node details |
| `GET`  | `/status` | Full fleet status |
| `GET`  | `/health` | Health check all nodes |
| `POST` | `/register-node` | Register new node |
| `POST` | `/heartbeat` | Send node heartbeat |
| `GET`  | `/logs` | API request logs |

## Usage Examples

### Route to Best Coding Model

```bash
curl -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{"capabilities": ["coding"]}'
```

Response:
```json
{
  "success": true,
  "model": "qwen2.5-coder:7b",
  "node": "localhost",
  "endpoint": "http://localhost:11434",
  "vendor": "ollama",
  "type": "local",
  "cost_per_1m_tokens": 0.0,
  "score": 152.5
}
```

### Route with Constraints

```bash
# Local models only
curl -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{
    "capabilities": ["coding"],
    "constraints": {
      "type": "local",
      "maxCost": 0,
      "preferNode": "localhost"
    }
  }'
```

### List All Models

```bash
curl http://pi-02:8080/models | jq
```

### Get Fleet Status

```bash
curl http://pi-02:8080/status | jq
```

### Check Node Health

```bash
curl http://pi-02:8080/health | jq
```

## Client Library Usage

### JavaScript/Node.js

```javascript
const FleetOrchestratorClient = require('./fleet-orchestrator-client.cjs');
const client = new FleetOrchestratorClient('pi-02', 8080);

// Auto-register this node
await client.autoRegister();

// Start heartbeat
client.startHeartbeat();

// Route request
const route = await client.routeRequest('coding');
console.log('Using model:', route.model, 'on', route.node);

// Get models
const models = await client.getModels();
console.log('Available:', models.count, 'models');
```

### Bash/Shell

```bash
#!/bin/bash

# Find best model
ROUTE=$(curl -s -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{"capabilities": ["coding"]}')

MODEL=$(echo "$ROUTE" | jq -r '.model')
ENDPOINT=$(echo "$ROUTE" | jq -r '.endpoint')

# Use the model
curl -X POST "$ENDPOINT/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL\", \"prompt\": \"Hello world\"}"
```

## Management

### Service Status

```bash
# Check services
ssh pi@pi-02 sudo systemctl status fleet-brain-api.service
ssh pi@pi-02 sudo systemctl status fleet-health-monitor.service
```

### View Logs

```bash
# Live logs
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -f

# Last 100 lines
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -n 100
```

### Restart Services

```bash
# Restart API
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service

# Restart health monitor
ssh pi@pi-02 sudo systemctl restart fleet-health-monitor.service
```

### Update Software

```bash
# Pull latest changes
git pull

# Redeploy
./deploy-to-pi02.sh
```

## Files Deployed

### On pi-02 (`/home/pi/fleet-brain/`)

- `pi02-orchestrator-api.cjs` - REST API server
- `orchestrator-model-mesh.cjs` - Routing orchestrator
- `fleet-node-monitor.cjs` - Health monitor
- `fleet-model-registry.json` - Model registry
- `fleet-usage-stats.json` - Usage tracking
- `fleet-cli.cjs` - CLI tools
- `fleet-hardware-prober.cjs` - Hardware detection
- `fleet-auto-distributor.cjs` - Auto-distribution
- `fleet-deployment-planner.cjs` - Deployment planning

### Systemd Services (`/etc/systemd/system/`)

- `fleet-brain-api.service` - API server service
- `fleet-health-monitor.service` - Health monitor service

## Resource Usage

Expected on pi-02 (1GB RAM):

- **API Server**: 50-150MB RAM, 5-25% CPU
- **Health Monitor**: 30-80MB RAM, 2-10% CPU
- **Total**: ~200-250MB RAM, 10-35% CPU

## Monitoring

### Check API Health

```bash
curl http://pi-02:8080/health
```

### View Request Logs

```bash
curl http://pi-02:8080/logs?limit=50 | jq
```

### Fleet Status

```bash
curl http://pi-02:8080/status | jq '.stats'
```

### Node Status

```bash
curl http://pi-02:8080/nodes | jq '.nodes[] | {name, status, models: .total_models}'
```

## Troubleshooting

### API Not Responding

```bash
# Check service
ssh pi@pi-02 sudo systemctl status fleet-brain-api.service

# View logs
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -n 50

# Restart
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service
```

### Node Not Registered

```bash
# From node, auto-register
./fleet-orchestrator-client.cjs auto-register

# Check registration on pi-02
curl http://pi-02:8080/nodes
```

### Models Unavailable

```bash
# Check node heartbeat
curl http://pi-02:8080/nodes/server-01

# Send manual heartbeat from node
./fleet-orchestrator-client.cjs heartbeat
```

## Documentation

- **Full Guide**: `docs/pi02-fleet-brain.md`
- **Quick Start**: `docs/pi02-quickstart.md`
- **API Reference**: See "API Endpoints" section above
- **Client Library**: See "Client Library Usage" section above

## Testing

Run comprehensive test suite:

```bash
./test-pi02-api.sh
```

Tests include:
- ✓ Basic connectivity
- ✓ Model listing
- ✓ Node listing
- ✓ Request routing
- ✓ Constraints handling
- ✓ Error handling
- ✓ Heartbeat functionality
- ✓ Performance tests
- ✓ Integration tests

## Next Steps

1. **Register All Nodes**
   - Deploy client to each node
   - Run `auto-register` on each

2. **Integrate with Workflows**
   - Update workflows to use pi-02 routing
   - Replace hardcoded model selection

3. **Monitor Usage**
   - Check `/logs` endpoint
   - Identify most-used models

4. **Optimize Distribution**
   - Use `fleet-cli.js rebalance`
   - Redistribute models if needed

5. **Set Up Monitoring**
   - Add Prometheus/Grafana
   - Track long-term metrics

## Support

- **Service Logs**: `ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -f`
- **Test Connectivity**: `curl http://pi-02:8080/health`
- **API Status**: `curl http://pi-02:8080/status`
- **Client Help**: `./fleet-orchestrator-client.cjs --help`

## Key Features

✅ **Zero Duplication** - Each model on exactly ONE node
✅ **Smart Routing** - Cost, latency, capability-aware
✅ **Auto-Discovery** - Nodes auto-register with Ollama detection
✅ **Health Monitoring** - 30s heartbeats, auto-failover
✅ **REST API** - Simple HTTP interface
✅ **Lightweight** - Runs on 1GB RAM Raspberry Pi
✅ **Auto-Start** - Systemd services restart on boot
✅ **Secure** - Hardened systemd configuration

pi-02 is now the authoritative fleet brain! 🧠
