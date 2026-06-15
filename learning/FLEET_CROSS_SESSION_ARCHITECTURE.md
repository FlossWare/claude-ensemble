# Fleet Cross-Session Communication Architecture

## Overview

This document outlines the architecture for cross-session communication across a distributed fleet of physical machines (server-01 through server-05) where sessions run on different hosts.

## Current Fleet Topology

```
┌──────────────────────────────────────────────────────────────────┐
│                         Fleet Overview                           │
├──────────────────────────────────────────────────────────────────┤
│  server-01 (NAS/Brain)                                           │
│    - NFS server                                                  │
│    - Grafana/InfluxDB                                            │
│    - Fleet coordinator                                           │
│    - Model: opus                                                 │
├──────────────────────────────────────────────────────────────────┤
│  server-02                                                       │
│    - Model: sonnet-4.5                                           │
│    - High-memory tasks                                           │
├──────────────────────────────────────────────────────────────────┤
│  server-03                                                       │
│    - Model: sonnet                                               │
│    - Code review                                                 │
├──────────────────────────────────────────────────────────────────┤
│  server-04                                                       │
│    - Model: haiku                                                │
│    - Fast tasks                                                  │
├──────────────────────────────────────────────────────────────────┤
│  server-05                                                       │
│    - Model: fable                                                │
│    - Experimental                                                │
└──────────────────────────────────────────────────────────────────┘

All servers mount: /mnt/nas/claude-global-skills (NFS)
```

## Challenge

**Problem:** Sessions on different physical machines cannot communicate via:
- Shared memory (limited to same machine)
- WebSocket localhost (limited to same machine)
- File polling works BUT has high latency (0-5s)

**Goal:** Enable real-time cross-machine session communication with <100ms latency.

## Architecture Options

### Option 1: NFS-Shared File Polling (CURRENT)

**Architecture:**
```
server-01                           server-02
┌──────────────┐                   ┌──────────────┐
│  Session A   │                   │  Session B   │
│              │                   │              │
│  ┌────────┐  │                   │  ┌────────┐  │
│  │ Poll   │──┼──┐            ┌───┼──│ Poll   │  │
│  └────────┘  │  │            │   │  └────────┘  │
└──────────────┘  │            │   └──────────────┘
                  ▼            ▼
        ┌─────────────────────────┐
        │  /mnt/nas/session-*.json│
        │  (NFS-shared files)     │
        └─────────────────────────┘
```

**Pros:**
- Already implemented
- Works today
- No changes needed
- Durable (messages on disk)
- Audit trail

**Cons:**
- High latency (0-5s)
- NFS overhead
- File locking issues
- Network I/O on every poll

**Verdict:** Works but slow. Keep as fallback.

---

### Option 2: Fleet WebSocket Hub (RECOMMENDED)

**Architecture:**
```
                    server-01 (NAS/Brain)
              ┌───────────────────────────────┐
              │   WebSocket Hub (ws://8888)   │
              │   - Routes messages            │
              │   - Broadcasts discoveries     │
              │   - Maintains session registry │
              └───────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬──────────────┐
         │               │               │              │
    server-02       server-03       server-04      server-05
  ┌──────────┐    ┌──────────┐    ┌──────────┐   ┌──────────┐
  │Session A │    │Session B │    │Session C │   │Session D │
  │          │    │          │    │          │   │          │
  │ WS client│    │ WS client│    │ WS client│   │ WS client│
  └──────────┘    └──────────┘    └──────────┘   └──────────┘
       │               │               │              │
       └───────────────┴───────────────┴──────────────┘
                WebSocket connections to hub
```

**Components:**

1. **WebSocket Hub** (on server-01)
   - Centralized message router
   - Listens on `0.0.0.0:8888` (all interfaces)
   - Maintains session registry (which session on which server)
   - Routes messages by session ID
   - Broadcasts to all connected clients

2. **Session Client** (on all servers)
   - Connects to `ws://server-01:8888`
   - Auto-reconnect on connection loss
   - Registers session on connect
   - Sends/receives messages

**Message Flow:**
```
Session A (server-02) wants to send discovery to Session B (server-03):

1. Session A → WebSocket → Hub (server-01)
2. Hub checks session registry: Session B on server-03
3. Hub → WebSocket → Session B (server-03)
4. Session B receives discovery

Latency: ~10-50ms (vs 0-5000ms file polling)
```

**Pros:**
- **Low latency:** 10-50ms (100x faster than file polling)
- **Real-time:** Push-based, no polling delay
- **Scalable:** Handles 100+ sessions across fleet
- **Mature protocol:** WebSocket is proven, widely supported
- **Good tooling:** Easy to debug, monitor
- **Efficient:** Persistent connections, no file I/O

**Cons:**
- **Single point of failure:** Hub crash breaks all communication
- **Network dependency:** Requires stable network
- **Resource usage:** Hub uses memory/CPU on server-01
- **Firewall:** May need to open port 8888 on server-01

**Mitigation:**
- Monitor hub with systemd (auto-restart on crash)
- Fall back to file polling if hub unavailable
- Use lightweight hub implementation (low resource usage)
- Restrict to private network (no internet exposure)

**Verdict:** Best option. Implement this.

---

### Option 3: Distributed Message Queue (Redis/RabbitMQ)

**Architecture:**
```
                    server-01 (NAS/Brain)
              ┌───────────────────────────────┐
              │   Redis/RabbitMQ              │
              │   - Pub/Sub                   │
              │   - Message queue             │
              │   - Session channels          │
              └───────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬──────────────┐
         │               │               │              │
    server-02       server-03       server-04      server-05
  ┌──────────┐    ┌──────────┐    ┌──────────┐   ┌──────────┐
  │Session A │    │Session B │    │Session C │   │Session D │
  │          │    │          │    │          │   │          │
  │Redis cli │    │Redis cli │    │Redis cli │   │Redis cli │
  └──────────┘    └──────────┘    └──────────┘   └──────────┘
```

**Pros:**
- **Production-ready:** Battle-tested in production
- **High performance:** Redis very fast
- **Pub/Sub built-in:** Natural message passing
- **Persistence:** Messages can be durable
- **Clustering:** Redis Cluster for HA

**Cons:**
- **Heavy dependency:** Requires Redis/RabbitMQ installation
- **Operational overhead:** Must manage Redis server
- **Over-engineered:** Too complex for this use case
- **Resource usage:** Redis uses 10-100MB memory
- **Learning curve:** Must learn Redis API

**Verdict:** Overkill. Use lightweight WebSocket hub instead.

---

### Option 4: SSH Tunnels + Local WebSocket

**Architecture:**
```
Each server runs local WebSocket server
Sessions connect to local server
Servers connect to each other via SSH tunnels

server-02                    server-01                    server-03
┌──────────┐  SSH tunnel  ┌──────────┐  SSH tunnel   ┌──────────┐
│Local WS  │◄────────────►│Local WS  │◄─────────────►│Local WS  │
│  :8888   │              │  :8888   │               │  :8888   │
└──────────┘              └──────────┘               └──────────┘
     │                         │                          │
┌────┴────┐              ┌────┴────┐                ┌────┴────┐
│Session A│              │Session B│                │Session C│
└─────────┘              └─────────┘                └─────────┘
```

**Pros:**
- **No single point of failure:** Decentralized
- **Secure:** SSH encryption
- **Local perf:** Sessions get local WebSocket latency
- **Redundant:** Multiple paths between nodes

**Cons:**
- **Complex:** Must manage SSH tunnels between all pairs
- **O(N²) connections:** 5 servers = 20 tunnels
- **Routing complexity:** Messages must route through graph
- **Failure modes:** Tunnel failures break routes
- **Operational overhead:** Monitor all tunnels

**Verdict:** Too complex. Not worth it.

---

### Option 5: HTTP API (REST)

**Architecture:**
```
                    server-01 (NAS/Brain)
              ┌───────────────────────────────┐
              │   HTTP API (:8888)            │
              │   POST /message               │
              │   GET  /messages/:sessionId   │
              └───────────────────────────────┘
                         │
    server-02       server-03       server-04      server-05
  ┌──────────┐    ┌──────────┐    ┌──────────┐   ┌──────────┐
  │Session A │    │Session B │    │Session C │   │Session D │
  │          │    │          │    │          │   │          │
  │HTTP poll │    │HTTP poll │    │HTTP poll │   │HTTP poll │
  └──────────┘    └──────────┘    └──────────┘   └──────────┘
```

**Pros:**
- **Simple:** Just HTTP requests
- **Stateless:** No persistent connections
- **Easy to debug:** curl, httpie
- **Language agnostic:** Any client works

**Cons:**
- **Higher latency:** HTTP overhead (vs WebSocket)
- **Polling required:** Still need to poll for messages
- **More network traffic:** New connection per request
- **Less efficient:** No push notifications

**Verdict:** Worse than WebSocket. Skip.

---

## Recommended Architecture: Fleet WebSocket Hub

### Deployment

**server-01 (Hub):**
```bash
# Install WebSocket hub
cd /mnt/nas/claude-global-skills/learning
npm install ws

# Start hub
systemctl --user start claude-websocket-hub

# Hub listens on 0.0.0.0:8888
```

**server-02 through server-05 (Clients):**
```bash
# Sessions auto-connect to ws://server-01:8888
# No installation needed (uses existing SessionManager)
```

### Implementation

**1. WebSocket Hub** (`ws-hub.js`)
```javascript
import WebSocket, { WebSocketServer } from 'ws';

const wss = new WebSocketServer({ 
  host: '0.0.0.0',
  port: 8888 
});

const sessions = new Map(); // sessionId -> ws connection

wss.on('connection', (ws) => {
  let sessionId = null;

  ws.on('message', (data) => {
    const msg = JSON.parse(data);

    // Register session
    if (msg.type === 'register') {
      sessionId = msg.sessionId;
      sessions.set(sessionId, ws);
      console.log(`Registered: ${sessionId}`);
      return;
    }

    // Route message
    if (msg.to === 'broadcast') {
      // Broadcast to all
      for (const [id, client] of sessions) {
        if (id !== msg.from && client.readyState === WebSocket.OPEN) {
          client.send(JSON.stringify(msg));
        }
      }
    } else {
      // Send to specific session
      const target = sessions.get(msg.to);
      if (target && target.readyState === WebSocket.OPEN) {
        target.send(JSON.stringify(msg));
      }
    }
  });

  ws.on('close', () => {
    if (sessionId) {
      sessions.delete(sessionId);
      console.log(`Disconnected: ${sessionId}`);
    }
  });
});

console.log('WebSocket Hub listening on 0.0.0.0:8888');
```

**2. Session Client** (integrate into `SessionManager`)
```javascript
import WebSocket from 'ws';

class SessionManager {
  constructor(options) {
    // ... existing code ...
    
    // Try to connect to WebSocket hub
    this._connectToHub();
  }

  async _connectToHub() {
    try {
      this.ws = new WebSocket('ws://server-01:8888');
      
      this.ws.on('open', () => {
        // Register session
        this.ws.send(JSON.stringify({
          type: 'register',
          sessionId: this.sessionId,
        }));
        
        console.log(`Connected to WebSocket hub`);
        this.useWebSocket = true;
      });

      this.ws.on('message', (data) => {
        const msg = JSON.parse(data);
        this._handleMessage(msg);
      });

      this.ws.on('error', () => {
        // Fall back to file polling
        this.useWebSocket = false;
      });

      this.ws.on('close', () => {
        // Auto-reconnect after 5s
        setTimeout(() => this._connectToHub(), 5000);
      });
    } catch (err) {
      // Hub not available, use file polling
      this.useWebSocket = false;
    }
  }

  async sendMessage(to, message) {
    if (this.useWebSocket && this.ws.readyState === WebSocket.OPEN) {
      // Send via WebSocket
      this.ws.send(JSON.stringify({
        from: this.sessionId,
        to,
        ...message,
      }));
    } else {
      // Fall back to file polling
      this._sendViaFile(to, message);
    }
  }
}
```

### Fallback Strategy

**Auto-detect hub availability:**
1. Session tries to connect to `ws://server-01:8888`
2. If connection succeeds, use WebSocket
3. If connection fails, fall back to file polling
4. Retry WebSocket connection every 30s

**Graceful degradation:**
- Hub crash → sessions fall back to file polling
- Hub restart → sessions auto-reconnect
- Network partition → sessions use file polling until resolved
- Mixed state OK (some sessions WebSocket, some file polling)

### Monitoring

**Metrics to track:**
- Hub uptime
- Connected session count
- Messages routed per second
- Average message latency
- WebSocket vs file polling ratio

**Grafana Dashboard:**
```sql
-- Hub health
SELECT mean("uptime") FROM "websocket_hub" 
WHERE time > now() - 1h

-- Connected sessions
SELECT count("session_id") FROM "websocket_hub"
WHERE "status" = 'connected'

-- Message throughput
SELECT derivative(mean("messages_routed"), 1s) 
FROM "websocket_hub" 
WHERE time > now() - 5m
```

### Security

**Network isolation:**
- Hub only binds to private network interface
- Firewall rules: Allow 8888 from fleet IPs only
- No internet exposure

**Authentication (future):**
- Shared secret token
- TLS/SSL encryption
- Client certificates

**Current:** Trusted private network (no authentication needed)

## Multi-Region Fleet (Future)

For geographically distributed fleet across multiple data centers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Global Architecture                      │
├─────────────────────────────────────────────────────────────┤
│  Region 1 (US-East)                                         │
│    - WebSocket Hub (region-1-hub)                           │
│    - Servers 01-05                                          │
├─────────────────────────────────────────────────────────────┤
│  Region 2 (US-West)                                         │
│    - WebSocket Hub (region-2-hub)                           │
│    - Servers 06-10                                          │
├─────────────────────────────────────────────────────────────┤
│  Hub-to-Hub Bridge                                          │
│    - Cross-region message routing                           │
│    - Eventual consistency                                   │
│    - Discovery propagation                                  │
└─────────────────────────────────────────────────────────────┘
```

**Cross-region latency:** 50-200ms (vs 10-50ms local)

## Estimated Effort

| Component | Effort | Priority |
|-----------|--------|----------|
| WebSocket Hub | 8 hours | High |
| SessionManager integration | 8 hours | High |
| Systemd service | 2 hours | High |
| Monitoring | 4 hours | Medium |
| Testing | 8 hours | High |
| Documentation | 4 hours | Medium |
| **Total** | **34 hours** | **~5 days** |

## Implementation Phases

### Phase 1: Single-Machine WebSocket (Week 1)
- Implement WebSocket hub (localhost only)
- Integrate into SessionManager
- Test on single machine
- Fallback to file polling

### Phase 2: Fleet Deployment (Week 2)
- Deploy hub on server-01
- Configure clients on server-02 to server-05
- Test cross-machine communication
- Monitor performance

### Phase 3: Production Hardening (Week 3)
- Add monitoring/metrics
- Implement auto-recovery
- Security hardening
- Documentation

## Recommendation

**Implement Fleet WebSocket Hub**

**Why:**
1. **100x faster** than file polling (10-50ms vs 0-5000ms)
2. **Real-time** discovery propagation across fleet
3. **Proven technology** (WebSocket is mature)
4. **Graceful fallback** to file polling
5. **Scalable** to 100+ sessions across fleet

**Priority:** **High** - Implement after message polling daemon is stable.

**Next Steps:**
1. Build WebSocket hub (8 hours)
2. Test on single machine (4 hours)
3. Deploy to fleet (8 hours)
4. Monitor and optimize (ongoing)
