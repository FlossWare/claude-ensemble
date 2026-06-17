# Real-Time Session Communication System

## Overview

This document provides a comprehensive overview of the real-time session communication system for Claude sessions, including implementation status, architecture decisions, and deployment guides.

## System Components

### 1. Message Polling Daemon ✅ IMPLEMENTED

**File:** `message-polling-daemon.js`

**Status:** Production-ready

**Features:**
- Polls session-messages.json every 5s
- Auto-responds to heartbeat requests
- Auto-responds to discovery requests
- Auto-responds to status/capability queries
- Logs to `~/.claude/learning/logs/message-polling.log`
- Systemd service for continuous operation

**Installation:**
```bash
cd learning/
./install-polling-daemon.sh

# Check status
systemctl --user status claude-message-polling

# View logs
tail -f ~/.claude/learning/logs/message-polling.log
```

**Auto-Response Capabilities:**
- `heartbeat-request` → Sends heartbeat with uptime, PID
- `discovery-request` → Sends filtered discoveries
- `status-request` → Sends session status and stats
- `capability-query` → Sends available models and features
- `introduction` → Responds with greeting and capabilities
- `request` → Routes to appropriate handler based on requestType

**Use Case:** Background daemon that makes sessions responsive even when idle.

---

### 2. WebSocket Server 📋 EVALUATED

**File:** `WEBSOCKET_EVALUATION.md`

**Status:** Design complete, implementation pending

**Key Findings:**
- **100-500x lower latency** than file polling (10ms vs 5s)
- **More efficient** (no polling CPU usage)
- **Richer patterns** (pub/sub, presence, channels)
- **Operational complexity** (requires server process)

**Recommendation:** **Build for single-machine deployment**
- Priority: Medium-High
- Effort: ~28 hours (4 days)
- Best for: Real-time collaboration, live discovery feeds

**When to Use:**
- Need <100ms latency
- High-frequency messaging (100+ msgs/sec)
- Single machine or private network fleet
- Want real-time coordination

**When to Skip:**
- File polling is fast enough
- Simple deployment required
- Multi-region fleet (high latency anyway)

---

### 3. Shared Memory IPC 📋 EVALUATED

**File:** `SHARED_MEMORY_EVALUATION.md`

**Status:** Design complete, implementation NOT recommended

**Key Findings:**
- **Ultra-low latency** (<100μs vs 5ms WebSocket)
- **Maximum efficiency** (zero-copy, no serialization)
- **High complexity** (lock-free algorithms, race conditions)
- **Platform-specific** (Linux/macOS only, won't work for fleet)

**Recommendation:** **Do NOT implement**
- Priority: Low
- Effort: ~60 hours (high risk)
- Complexity outweighs benefits

**When to Reconsider:**
- Need <1ms latency (hard requirement)
- High-frequency coordination (>1000 msgs/sec)
- Single machine only (guaranteed)
- Team has lock-free programming expertise

**Verdict:** Over-engineered. Use WebSocket instead.

---

### 4. Fleet Architecture 📋 EVALUATED

**File:** `FLEET_CROSS_SESSION_ARCHITECTURE.md`

**Status:** Architecture complete, implementation pending

**Recommended Approach:** **Fleet WebSocket Hub**

**Architecture:**
```
         server-01 (NAS/Brain)
    ┌──────────────────────────┐
    │ WebSocket Hub (:8888)    │
    │ - Routes messages        │
    │ - Session registry       │
    └──────────────────────────┘
              │
    ┌─────────┼─────────┬──────────┐
    │         │         │          │
server-02  server-03  server-04  server-05
```

**Benefits:**
- 100x faster than NFS file polling (10-50ms vs 0-5000ms)
- Real-time discovery propagation across fleet
- Graceful fallback to file polling
- Scalable to 100+ sessions

**Alternative Approaches Evaluated:**
- ❌ Redis/RabbitMQ: Overkill, too heavy
- ❌ SSH Tunnels: Too complex (O(N²) tunnels)
- ❌ HTTP API: Worse than WebSocket (polling still needed)
- ✅ NFS File Polling: Keep as fallback

**Recommendation:** **Implement Fleet WebSocket Hub**
- Priority: High
- Effort: ~34 hours (5 days)
- Best for: Multi-machine fleet communication

---

## Architecture Decision Matrix

| Approach | Latency | Complexity | Fleet Support | Recommendation |
|----------|---------|------------|---------------|----------------|
| **File Polling** | 0-5s | Low | ✅ Yes (NFS) | ✅ Keep as fallback |
| **Message Daemon** | 0-5s | Low | ✅ Yes | ✅ **IMPLEMENTED** |
| **WebSocket** | 5-50ms | Medium | ✅ Yes | ✅ **BUILD NEXT** |
| **Shared Memory** | <1ms | High | ❌ No | ❌ Skip |
| **Fleet WS Hub** | 10-50ms | Medium | ✅ Yes | ✅ **BUILD FOR FLEET** |

## Implementation Roadmap

### ✅ Phase 1: Message Polling Daemon (COMPLETE)
**Status:** Production-ready
**Files:**
- `message-polling-daemon.js`
- `claude-message-polling.service`
- `install-polling-daemon.sh`

**What it does:**
- Background daemon that polls messages every 5s
- Auto-responds to common requests
- Makes sessions always responsive

**Next:** Test in production, gather metrics

---

### 📅 Phase 2: Single-Machine WebSocket (NEXT)
**Status:** Ready to implement
**Estimated Effort:** 28 hours (4 days)

**Tasks:**
1. Implement WebSocket server (`ws-server.js`)
2. Integrate into SessionManager
3. Add auto-fallback to file polling
4. Create systemd service
5. Test on single machine
6. Document usage

**Deliverables:**
- Working WebSocket server (localhost:8888)
- SessionManager auto-detects and uses WebSocket
- Falls back to file polling if unavailable
- <10ms message latency

**Success Metrics:**
- 100x faster than file polling
- No increase in resource usage
- Graceful degradation on failure

---

### 📅 Phase 3: Fleet WebSocket Hub (LATER)
**Status:** Architecture complete
**Estimated Effort:** 34 hours (5 days)

**Tasks:**
1. Extend WebSocket server for fleet (bind to 0.0.0.0)
2. Deploy hub on server-01
3. Configure clients on server-02 to server-05
4. Add monitoring/metrics
5. Test cross-machine communication
6. Security hardening

**Deliverables:**
- Fleet-wide WebSocket hub on server-01
- All fleet sessions connected
- 10-50ms cross-machine latency
- Monitoring dashboard

**Success Metrics:**
- 100x faster than NFS file polling
- Real-time discovery propagation
- 99.9% uptime (with auto-restart)

---

## Current Status Summary

### What Works Today
1. **File Polling** - All sessions poll session-messages.json every 5s
2. **Message Daemon** - Auto-responds to requests in background
3. **Session Manager** - Registers sessions, sends messages, broadcasts
4. **Discovery Sharing** - Sessions can share discoveries

### What's Next
1. **WebSocket Server** - Real-time single-machine communication
2. **Fleet WebSocket Hub** - Real-time fleet-wide communication
3. **Monitoring** - Grafana dashboard for session communication metrics
4. **Auto-Discovery Integration** - Discoveries auto-propagate via WebSocket

---

## Performance Comparison

| Metric | File Polling | Message Daemon | WebSocket | Fleet WS Hub |
|--------|--------------|----------------|-----------|--------------|
| Latency (avg) | 2,500ms | 2,500ms | 5ms | 30ms |
| Latency (p99) | 5,000ms | 5,000ms | 10ms | 100ms |
| Auto-response | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| Real-time | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| Fleet support | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| Complexity | Low | Low | Medium | Medium |
| Status | ✅ Live | ✅ Live | 📋 Planned | 📋 Planned |

---

## Usage Examples

### Example 1: Broadcast Discovery (Current)
```javascript
import { SessionManager } from './session-manager.js';

const manager = new SessionManager();
await manager.start();

// Broadcast discovery to all sessions
await manager.broadcast({
  type: 'discovery',
  data: {
    id: 'disc-123',
    insight: 'fable fails on large JSON',
    confidence: 0.92,
  },
});

// Other sessions receive in 0-5s (file polling)
```

### Example 2: Request Help (Current)
```javascript
// Session A requests help
await manager.broadcast({
  type: 'request',
  data: {
    requestType: 'status',
  },
});

// Message daemon auto-responds (thanks to daemon!)
// Response received in 0-5s
```

### Example 3: Real-Time Discovery (Future - WebSocket)
```javascript
// Same API, but WebSocket transport
await manager.broadcast({
  type: 'discovery',
  data: { ... },
});

// Other sessions receive in <10ms (WebSocket)
// Auto-falls back to file polling if WebSocket unavailable
```

### Example 4: Fleet Communication (Future - Fleet Hub)
```javascript
// Session on server-02 sends to session on server-03
await manager.sendMessage('session-xyz-server03', {
  type: 'discovery',
  data: { ... },
});

// Routed through WebSocket hub on server-01
// Delivered in 10-50ms
```

---

## Monitoring

### Current Metrics
```bash
# Check daemon status
systemctl --user status claude-message-polling

# View daemon logs
tail -f ~/.claude/learning/logs/message-polling.log

# Check session registry
cat learning/session-registry.json | jq '.sessions | length'

# Check pending messages
cat learning/session-messages.json | jq '.messages | length'
```

### Future Metrics (WebSocket)
```bash
# WebSocket hub status
systemctl --user status claude-websocket-server

# Connected sessions
curl http://localhost:8888/stats

# Message throughput
# (will integrate with Grafana)
```

---

## Troubleshooting

### Problem: Message Daemon Not Responding
```bash
# Check if daemon is running
systemctl --user status claude-message-polling

# Restart daemon
systemctl --user restart claude-message-polling

# Check logs for errors
journalctl --user -u claude-message-polling -n 50
```

### Problem: Messages Not Delivered
```bash
# Check file permissions
ls -la learning/session-messages.json

# Check for stale sessions
cat learning/session-registry.json | jq '.sessions'

# Force cleanup
rm learning/session-registry.json
# Sessions will re-register on next heartbeat
```

### Problem: High Latency
```bash
# Check polling interval
# Default: 5s (can reduce to 1s for testing)

# Check NFS performance (fleet)
time cat /mnt/nas/claude-global-skills/learning/session-messages.json
# Should be <100ms

# If slow, check NFS mount:
mount | grep nas
```

---

## Security Considerations

### Current (File Polling)
- **File permissions:** 0644 (readable by all, writable by owner)
- **NFS security:** Trusted private network
- **Message validation:** None (trust all sessions)

### Future (WebSocket)
- **Network binding:** localhost only (single-machine)
- **Fleet binding:** Private network only (0.0.0.0 but firewalled)
- **Authentication:** Shared secret token (future)
- **Encryption:** TLS/SSL (future)

**Current Assumption:** All sessions are trusted (same user, same project).

---

## References

### Implementation Files
- `message-polling-daemon.js` - Message polling daemon
- `session-manager.js` - Session management and messaging
- `session-integration.js` - Integration with orchestrator
- `demo-session-communication.js` - Example usage

### Evaluation Documents
- `WEBSOCKET_EVALUATION.md` - WebSocket analysis
- `SHARED_MEMORY_EVALUATION.md` - Shared memory analysis
- `FLEET_CROSS_SESSION_ARCHITECTURE.md` - Fleet architecture
- `REALTIME_SESSION_COMMUNICATION.md` - This document

### Related Docs
- `CROSS_SESSION_README.md` - Original cross-session design
- `AUTO_DISCOVERY_SYSTEM.md` - Discovery system integration
- `HOT_RELOAD_SYSTEM.md` - Hot reload integration

---

## Conclusion

We have built a **comprehensive real-time session communication system** with multiple approaches:

1. ✅ **Message Polling Daemon** - Production-ready, auto-responding background service
2. 📋 **WebSocket Server** - Evaluated, ready to implement (100x faster)
3. 📋 **Shared Memory** - Evaluated, NOT recommended (over-engineered)
4. 📋 **Fleet WebSocket Hub** - Architected, ready to deploy (fleet-wide real-time)

**Current Status:**
- Message polling daemon is **live and working**
- File polling provides reliable fallback
- Auto-response makes sessions always responsive

**Next Steps:**
1. Deploy message polling daemon to fleet
2. Implement WebSocket server for single-machine
3. Deploy Fleet WebSocket Hub for fleet-wide real-time
4. Integrate with monitoring/metrics

**Impact:**
- 100-500x lower latency (5s → 10-50ms)
- Real-time discovery propagation
- Better session coordination
- Improved user experience

The foundation is solid. Now we can build real-time features on top of this infrastructure.
