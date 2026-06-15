# Fleet Brain Quick Start Guide

## 5-Minute Setup

### Step 1: Deploy to pi-02

```bash
./deploy-to-pi02.sh
```

Wait for deployment to complete. You should see:
```
✅ Deployment Complete!
Fleet Brain API: http://pi-02:8080
```

### Step 2: Verify API

```bash
curl http://pi-02:8080/status
```

Should return fleet status JSON.

### Step 3: Register Nodes

On each fleet node (server-01, server-02, server-03):

```bash
# Copy client library to node
scp fleet-orchestrator-client.cjs server-01:/home/user/

# SSH to node
ssh server-01

# Auto-register (detects Ollama models automatically)
./fleet-orchestrator-client.cjs auto-register
```

The client will:
- ✓ Detect node name, RAM, CPU
- ✓ Scan for Ollama models
- ✓ Register with pi-02
- ✓ Start heartbeats (30s interval)

### Step 4: Test Routing

Ask pi-02 for the best coding model:

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
  "capabilities": ["coding", "debugging"],
  "score": 152.5
}
```

### Step 5: Monitor Fleet

```bash
# List all models
curl http://pi-02:8080/models

# List all nodes
curl http://pi-02:8080/nodes

# Health check
curl http://pi-02:8080/health

# Full status
curl http://pi-02:8080/status
```

## Common Tasks

### Route Different Capabilities

```bash
# Best reasoning model
curl -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{"capabilities": ["reasoning"]}'

# Best math model
curl -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{"capabilities": ["math"]}'

# Coding + reasoning
curl -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{"capabilities": ["coding", "reasoning"]}'
```

### Prefer Local Models Only

```bash
curl -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{
    "capabilities": ["coding"],
    "constraints": {
      "type": "local",
      "maxCost": 0
    }
  }'
```

### Check Specific Node

```bash
curl http://pi-02:8080/nodes/localhost | jq
curl http://pi-02:8080/nodes/server-01 | jq
```

### View Recent Requests

```bash
curl http://pi-02:8080/logs?limit=50
```

## Use in Workflows

### JavaScript/Node.js

```javascript
const FleetOrchestratorClient = require('./fleet-orchestrator-client.cjs');
const client = new FleetOrchestratorClient('pi-02', 8080);

// Find best model
const route = await client.routeRequest('coding');
console.log('Using model:', route.model, 'on', route.node);

// Use with Ollama
const response = await fetch(`${route.endpoint}/api/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: route.model,
    prompt: 'Write a hello world function',
  })
});
```

### Bash/Shell Scripts

```bash
#!/bin/bash

# Route to best coding model
ROUTE=$(curl -s -X POST http://pi-02:8080/route \
  -H "Content-Type: application/json" \
  -d '{"capabilities": ["coding"]}')

MODEL=$(echo "$ROUTE" | jq -r '.model')
ENDPOINT=$(echo "$ROUTE" | jq -r '.endpoint')
NODE=$(echo "$ROUTE" | jq -r '.node')

echo "Using $MODEL on $NODE"

# Use the model
curl -X POST "$ENDPOINT/api/generate" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"Write a hello world function\"
  }"
```

### Python

```python
import requests

# Route request
response = requests.post('http://pi-02:8080/route', json={
    'capabilities': ['coding', 'reasoning']
})

route = response.json()
print(f"Using model: {route['model']} on {route['node']}")

# Use the model
ollama_response = requests.post(f"{route['endpoint']}/api/generate", json={
    'model': route['model'],
    'prompt': 'Write a hello world function'
})
```

## Maintenance

### Check Service Status

```bash
ssh pi@pi-02 sudo systemctl status fleet-brain-api.service
ssh pi@pi-02 sudo systemctl status fleet-health-monitor.service
```

### View Logs

```bash
# Live logs
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -f

# Last 100 lines
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -n 100

# Both services
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -u fleet-health-monitor.service -f
```

### Restart Services

```bash
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service
ssh pi@pi-02 sudo systemctl restart fleet-health-monitor.service
```

### Update Software

```bash
# Update local repo
git pull

# Redeploy to pi-02
./deploy-to-pi02.sh
```

## Troubleshooting

### "Cannot reach pi-02"

Check network connectivity:
```bash
ping pi-02
curl http://pi-02:8080/health
```

If unreachable:
1. Verify pi-02 is powered on
2. Check network/firewall
3. Verify hostname resolution: `nslookup pi-02`

### "Node not found"

Node hasn't registered. From the node:
```bash
./fleet-orchestrator-client.cjs auto-register
```

### "No matching models available"

Check available models:
```bash
curl http://pi-02:8080/models | jq '.models[].capabilities'
```

Adjust your capability request or constraints.

### Service Failed to Start

Check logs:
```bash
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -n 50
```

Common issues:
- Port 8080 already in use
- Registry file corrupted
- Node.js not installed

Fix and restart:
```bash
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service
```

## Performance Tips

### For Large Fleets (20+ nodes)

Increase heartbeat interval on pi-02:

Edit `/home/pi/fleet-brain/pi02-orchestrator-api.cjs`:
```javascript
this.heartbeatInterval = 60000; // 60 seconds instead of 30
this.heartbeatTimeout = 180000; // 180 seconds instead of 90
```

Restart:
```bash
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service
```

### For High Request Volume

If pi-02 CPU/memory limits are hit, increase in service file:

Edit `/etc/systemd/system/fleet-brain-api.service`:
```ini
MemoryMax=512M    # was 256M
CPUQuota=100%     # was 50%
```

Reload and restart:
```bash
ssh pi@pi-02 sudo systemctl daemon-reload
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service
```

## Next Steps

Once fleet brain is running:

1. **Integrate with Workflows** - Update your AI workflows to use pi-02 routing
2. **Monitor Usage** - Check `/logs` endpoint to see which models are used most
3. **Optimize Distribution** - Use `fleet-cli.js rebalance` to optimize model placement
4. **Add More Nodes** - Scale fleet by registering additional nodes
5. **Set Up Monitoring** - Add Prometheus/Grafana for long-term metrics

## Help

- Full documentation: `docs/pi02-fleet-brain.md`
- Service logs: `ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -f`
- Test connectivity: `curl http://pi-02:8080/health`
- Client help: `./fleet-orchestrator-client.cjs --help`
