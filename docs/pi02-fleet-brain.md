# Fleet Brain - pi-02 Orchestration Hub

## Overview

pi-02 is the **FLEET BRAIN** - the central orchestration hub for the entire distributed model fleet. It provides:

- **Model Registry** - Authoritative source of truth for all models across fleet
- **Request Routing** - Intelligent routing to best available model
- **Health Monitoring** - 30-second heartbeat checks on all nodes
- **REST API** - HTTP API for all fleet operations
- **Node Management** - Registration, heartbeats, status tracking

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          pi-02                              │
│                     (Fleet Brain)                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  REST API Server (port 8080)                          │  │
│  │  - POST /route                                        │  │
│  │  - GET  /models, /nodes, /status, /health            │  │
│  │  - POST /register-node, /heartbeat                   │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Model Mesh Orchestrator                              │  │
│  │  - Smart routing (cost, latency, capabilities)       │  │
│  │  - Usage tracking                                     │  │
│  │  - Zero duplication enforcement                       │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Health Monitor                                       │  │
│  │  - 30s heartbeat interval                            │  │
│  │  - Auto mark nodes offline after 90s timeout         │  │
│  │  - Network reachability checks                       │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Model Registry (fleet-model-registry.json)          │  │
│  │  - 37 models across 5 nodes                          │  │
│  │  - Zero duplication                                   │  │
│  │  - Real-time status updates                          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ HTTP API Calls
          ┌────────────────┴─────────────────┐
          │                │                 │
     ┌────▼───┐       ┌───▼────┐       ┌───▼────┐
     │server-01│       │server-02│       │server-03│
     │        │       │        │       │        │
     │Ollama  │       │Ollama  │       │Ollama  │
     │Models  │       │Models  │       │Models  │
     └────────┘       └────────┘       └────────┘
         ▲                ▲                ▲
         │ Heartbeat (30s)│                │
         └────────────────┴────────────────┘
```

## Deployment

### Prerequisites

1. **pi-02 Hardware**
   - ARM64 Raspberry Pi
   - 1GB RAM minimum
   - Network connectivity to all fleet nodes
   - Static IP or hostname resolution

2. **SSH Access**
   - SSH key authentication to pi-02
   - User with sudo privileges

3. **Local Files**
   - All fleet orchestrator files in current directory
   - Systemd service files in pi02-systemd-services/

### Deploy to pi-02

```bash
# Deploy everything
./deploy-to-pi02.sh

# Custom host/user
PI02_HOST=192.168.1.100 PI02_USER=admin ./deploy-to-pi02.sh
```

The deployment script:
1. ✓ Checks pi-02 reachability
2. ✓ Verifies SSH access
3. ✓ Creates `/home/pi/fleet-brain/` directory
4. ✓ Copies all orchestrator files
5. ✓ Installs Node.js (if needed)
6. ✓ Deploys systemd services
7. ✓ Starts services
8. ✓ Enables auto-start on boot
9. ✓ Verifies API is responding

## Systemd Services

### fleet-brain-api.service

Main API server on port 8080.

```bash
# Status
sudo systemctl status fleet-brain-api.service

# Logs
sudo journalctl -u fleet-brain-api.service -f

# Restart
sudo systemctl restart fleet-brain-api.service
```

**Resource limits:**
- MemoryMax: 256MB
- CPUQuota: 50%

### fleet-health-monitor.service

Background health monitoring (30s interval).

```bash
# Status
sudo systemctl status fleet-health-monitor.service

# Logs
sudo journalctl -u fleet-health-monitor.service -f

# Restart
sudo systemctl restart fleet-health-monitor.service
```

**Resource limits:**
- MemoryMax: 128MB
- CPUQuota: 25%

## API Reference

### POST /route

Route request to best available model.

**Request:**
```json
{
  "capabilities": ["coding", "reasoning"],
  "constraints": {
    "type": "local",
    "maxCost": 0,
    "preferNode": "localhost"
  }
}
```

**Response:**
```json
{
  "success": true,
  "model": "qwen2.5-coder:7b",
  "node": "localhost",
  "endpoint": "http://localhost:11434",
  "vendor": "ollama",
  "type": "local",
  "cost_per_1m_tokens": 0.0,
  "capabilities": ["coding", "debugging"],
  "score": 152.5,
  "alternatives": [...]
}
```

**Constraints:**
- `type` - "local" or "cloud-api"
- `vendor` - "anthropic", "openai", "google", "ollama", etc.
- `maxCost` - Maximum cost per 1M tokens
- `preferLocal` - Prefer local models (boolean)
- `preferCloud` - Prefer cloud models (boolean)
- `preferNode` - Prefer specific node name

### GET /models

List all available models.

**Response:**
```json
{
  "count": 37,
  "models": [
    {
      "name": "claude-opus-4",
      "vendor": "anthropic",
      "type": "cloud-api",
      "node": "localhost",
      "capabilities": ["reasoning", "coding", "writing", "analysis"],
      "cost_per_1m_tokens": 15.0
    },
    ...
  ]
}
```

### GET /nodes

List all fleet nodes.

**Response:**
```json
{
  "count": 5,
  "nodes": [
    {
      "name": "localhost",
      "status": "online",
      "last_heartbeat": "2026-06-13T12:00:00Z",
      "ram_gb": 31,
      "cpu_cores": 4,
      "roles": ["primary", "cloud-api", "local-ollama"],
      "total_models": 17,
      "cloud_models": 2,
      "local_models": 15
    },
    ...
  ]
}
```

### GET /nodes/{name}

Get specific node details.

**Response:**
```json
{
  "success": true,
  "node": "localhost",
  "status": "online",
  "last_heartbeat": "2026-06-13T12:00:00Z",
  "ram_gb": 31,
  "cpu_cores": 4,
  "roles": ["primary", "cloud-api", "local-ollama"],
  "total_models": 17,
  "available_models": 17,
  "models": [...]
}
```

### GET /status

Full fleet status.

**Response:**
```json
{
  "registry_version": "1.0",
  "last_updated": "2026-06-13T12:00:00Z",
  "stats": {
    "total_models": 37,
    "cloud_api_models": 10,
    "ollama_local_models": 27,
    "total_nodes": 5,
    "online_nodes": 5,
    "available_models": 37,
    "duplication_count": 0
  },
  "nodes": [...],
  "top_models": [...]
}
```

### GET /health

Run health check on all nodes.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-06-13T12:00:00Z",
  "nodes": {
    "localhost": {
      "status": "online",
      "latency_ms": 0,
      "checked_at": "2026-06-13T12:00:00Z"
    },
    ...
  }
}
```

### POST /register-node

Register a new node with the fleet.

**Request:**
```json
{
  "node": "server-01",
  "hostname": "server-01",
  "ram_gb": 15,
  "cpu_cores": 8,
  "roles": ["fast", "cloud-api"],
  "models": [
    {
      "name": "claude-sonnet-4",
      "vendor": "anthropic",
      "type": "cloud-api",
      "endpoint": "https://api.anthropic.com/v1/messages",
      "capabilities": ["coding", "reasoning", "fast"],
      "cost_per_1m_tokens": 3.0
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "node": "server-01",
  "models_registered": 1,
  "message": "Node server-01 registered successfully"
}
```

**Error (duplication):**
```json
{
  "success": false,
  "error": "Duplication detected",
  "duplicates": [
    {
      "model": "claude-sonnet-4",
      "existing_node": "server-02",
      "new_node": "server-01"
    }
  ],
  "message": "Each model must be on exactly ONE node"
}
```

### POST /heartbeat

Send heartbeat from node.

**Request:**
```json
{
  "node": "server-01"
}
```

**Response:**
```json
{
  "success": true,
  "node": "server-01",
  "heartbeat_received": "2026-06-13T12:00:00Z",
  "next_heartbeat_in": 30000
}
```

### GET /logs

Get recent API request logs.

**Query params:**
- `limit` - Number of logs to return (default: 100)

**Response:**
```json
{
  "count": 100,
  "logs": [
    {
      "timestamp": "2026-06-13T12:00:00Z",
      "method": "POST",
      "path": "/route",
      "statusCode": 200,
      "responseTime": 45,
      "userAgent": "fleet-client/server-01"
    },
    ...
  ]
}
```

## Client Library

### Auto-Register Node

Each node should auto-register on startup:

```bash
# On server-01, server-02, server-03, etc.
cd /path/to/fleet
./fleet-orchestrator-client.cjs auto-register
```

This will:
1. Detect node name (hostname)
2. Probe hardware (RAM, CPU)
3. Detect Ollama models
4. Register with pi-02
5. Start automatic heartbeats (30s interval)

### Programmatic Usage

```javascript
const FleetOrchestratorClient = require('./fleet-orchestrator-client.cjs');
const client = new FleetOrchestratorClient('pi-02', 8080);

// Auto-register
await client.autoRegister();

// Start heartbeat
client.startHeartbeat();

// Route request
const route = await client.routeRequest(['coding', 'reasoning']);
if (route.success) {
  console.log('Use model:', route.model);
  console.log('On node:', route.node);
  console.log('Endpoint:', route.endpoint);
}

// Get models
const models = await client.getModels();
console.log('Available models:', models.count);

// Get fleet status
const status = await client.getStatus();
console.log('Online nodes:', status.stats.online_nodes);
```

## Integration with Workflows

Update your workflows to use pi-02 for routing:

```javascript
const FleetOrchestratorClient = require('./fleet-orchestrator-client.cjs');
const client = new FleetOrchestratorClient('pi-02', 8080);

// Instead of hardcoding model selection:
// const model = 'qwen2.5-coder:7b';

// Ask pi-02 for best model:
const route = await client.routeRequest('coding');
const model = route.model;
const endpoint = route.endpoint;

// Use the routed model
const response = await fetch(`${endpoint}/api/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: model,
    prompt: 'Write a function...',
  })
});
```

## Monitoring

### Check API health

```bash
curl http://pi-02:8080/health
```

### List available models

```bash
curl http://pi-02:8080/models | jq '.models[].name'
```

### Get fleet status

```bash
curl http://pi-02:8080/status | jq
```

### Watch logs

```bash
# API server logs
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -f

# Health monitor logs
ssh pi@pi-02 sudo journalctl -u fleet-health-monitor.service -f

# Combined
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -u fleet-health-monitor.service -f
```

## Troubleshooting

### API not responding

```bash
# Check service status
ssh pi@pi-02 sudo systemctl status fleet-brain-api.service

# Check logs
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -n 50

# Restart service
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service
```

### Node not appearing in registry

```bash
# Check if node can reach pi-02
ping pi-02

# Try manual registration
./fleet-orchestrator-client.cjs auto-register

# Check pi-02 logs for registration attempts
ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service | grep register
```

### Models showing as unavailable

```bash
# Check node heartbeat
curl http://pi-02:8080/nodes/server-01

# Node heartbeat might have timed out (90s)
# Send manual heartbeat from node
./fleet-orchestrator-client.cjs heartbeat

# Or restart auto-registration
./fleet-orchestrator-client.cjs auto-register
```

### High memory usage on pi-02

```bash
# Check current memory usage
ssh pi@pi-02 free -h

# Check service memory limits
ssh pi@pi-02 systemctl show fleet-brain-api.service | grep Memory

# Adjust limits in /etc/systemd/system/fleet-brain-api.service
# Then reload
ssh pi@pi-02 sudo systemctl daemon-reload
ssh pi@pi-02 sudo systemctl restart fleet-brain-api.service
```

## Performance

### pi-02 Resource Usage

Expected resource consumption on pi-02 (1GB RAM):

- **fleet-brain-api.service**
  - Memory: 50-150MB (limit: 256MB)
  - CPU: 5-25% (limit: 50%)
  - Network: ~10KB/s (heartbeats + occasional routing)

- **fleet-health-monitor.service**
  - Memory: 30-80MB (limit: 128MB)
  - CPU: 2-10% (limit: 25%)
  - Network: ~5KB/s (health checks)

**Total:** ~200-250MB RAM, 10-35% CPU under normal load

### Scaling Considerations

Current limits:
- **Nodes:** Tested with 5 nodes, can scale to 50+
- **Models:** 37 models registered, can scale to 500+
- **Requests:** ~100 requests/sec on pi-02 hardware
- **Heartbeats:** 30s interval = 2 heartbeats/min/node

For larger fleets (50+ nodes):
- Increase heartbeat interval to 60s
- Increase timeout to 180s
- Consider deploying to more powerful hardware (2GB+ RAM)

## Security

### Network

- API binds to 0.0.0.0:8080 (all interfaces)
- **No authentication** by default
- Intended for trusted internal network only

**For production:**
1. Add firewall rules restricting access to fleet nodes
2. Use VPN or private network
3. Add API authentication (bearer token, API keys)

### Systemd Hardening

Services run with security features:
- `NoNewPrivileges=true` - Cannot gain new privileges
- `PrivateTmp=true` - Private /tmp directory
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=true` - No access to /home except working directory
- `ReadWritePaths=/home/pi/fleet-brain` - Only fleet-brain directory is writable

## Backup & Recovery

### Backup Registry

```bash
# Manual backup
ssh pi@pi-02 cp /home/pi/fleet-brain/fleet-model-registry.json \
  /home/pi/fleet-brain/fleet-model-registry.json.backup

# Automated daily backup (cron)
ssh pi@pi-02
crontab -e
# Add:
0 2 * * * cp /home/pi/fleet-brain/fleet-model-registry.json /home/pi/fleet-brain/backups/registry-$(date +\%Y\%m\%d).json
```

### Restore from Backup

```bash
# Stop services
ssh pi@pi-02 sudo systemctl stop fleet-brain-api.service fleet-health-monitor.service

# Restore registry
ssh pi@pi-02 cp /home/pi/fleet-brain/fleet-model-registry.json.backup \
  /home/pi/fleet-brain/fleet-model-registry.json

# Start services
ssh pi@pi-02 sudo systemctl start fleet-brain-api.service fleet-health-monitor.service
```

### Disaster Recovery

If pi-02 fails completely:

1. Deploy to new pi-02 instance:
   ```bash
   ./deploy-to-pi02.sh
   ```

2. Restore registry from backup:
   ```bash
   scp fleet-model-registry.json.backup pi@pi-02:/home/pi/fleet-brain/fleet-model-registry.json
   ```

3. All nodes will auto-reconnect on next heartbeat (within 30s)

## Maintenance

### Update Fleet Brain Software

```bash
# Update local files
git pull

# Redeploy to pi-02
./deploy-to-pi02.sh
```

The script will:
- Stop existing services
- Deploy new files
- Restart services
- Preserve registry data

### Clean Old Logs

```bash
# Limit journal size
ssh pi@pi-02 sudo journalctl --vacuum-size=100M

# Or limit by time
ssh pi@pi-02 sudo journalctl --vacuum-time=7d
```

## Future Enhancements

Planned features:

1. **Authentication** - API key/bearer token support
2. **HTTPS** - TLS encryption for API
3. **Model Performance Tracking** - Success rates, latency metrics
4. **Auto-scaling** - Dynamic model distribution based on usage
5. **Web Dashboard** - Real-time fleet visualization
6. **Prometheus Metrics** - Integration with monitoring stack
7. **High Availability** - Multi-brain redundancy
8. **Model Migration** - Live model movement between nodes

## Support

Questions or issues:
- Check logs: `sudo journalctl -u fleet-brain-api.service -f`
- Verify connectivity: `curl http://pi-02:8080/health`
- Review registry: `cat /home/pi/fleet-brain/fleet-model-registry.json`
- Test client: `./fleet-orchestrator-client.cjs status`
