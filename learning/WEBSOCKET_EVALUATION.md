# WebSocket Server Evaluation for Real-Time Session Communication

## Overview

This document evaluates using a WebSocket server for real-time, bidirectional communication between Claude sessions as an alternative to the current file-based polling approach.

## Proposed Architecture

### Server Design
```
┌─────────────────────────────────────┐
│   WebSocket Server (localhost:8888) │
│                                     │
│  - Manages connections              │
│  - Routes messages                  │
│  - Broadcasts discoveries           │
│  - Tracks active sessions           │
└─────────────────────────────────────┘
            │
            │ WebSocket connections
            │
    ┌───────┴────────┬──────────┬──────────┐
    │                │          │          │
┌───▼────┐      ┌───▼────┐  ┌──▼────┐  ┌──▼────┐
│Session1│      │Session2│  │Session3│  │Session4│
└────────┘      └────────┘  └────────┘  └────────┘
```

### Components

1. **WebSocket Server** (`ws-server.js`)
   - Lightweight Node.js WebSocket server (using `ws` package)
   - Listens on `localhost:8888` (configurable)
   - Manages client connections
   - Routes messages based on target session ID
   - Broadcasts to all clients when target is "broadcast"

2. **Session Client** (`ws-session-client.js`)
   - Auto-connects to WebSocket server on session start
   - Sends/receives messages in real-time
   - Auto-reconnect on connection loss
   - Maintains session registration

3. **Message Protocol**
   ```json
   {
     "type": "message",
     "from": "session-id-1",
     "to": "session-id-2",
     "messageType": "discovery",
     "data": { ... },
     "timestamp": 1234567890
   }
   ```

## Pros

### 1. Real-Time Communication
- **Zero polling delay**: Messages delivered instantly
- **Push-based**: Server pushes messages to clients immediately
- **Low latency**: Sub-millisecond message delivery
- **Live updates**: Sessions notified of discoveries as they happen

### 2. Efficiency
- **No file I/O**: Eliminates disk writes/reads for message passing
- **Lower CPU**: No constant polling loops
- **Reduced contention**: No file locking issues
- **Scalable**: Handles 100+ sessions without performance degradation

### 3. Better User Experience
- **Instant responses**: Heartbeat responses in <10ms vs 5s polling delay
- **Real-time coordination**: Sessions can coordinate in real-time
- **Live discovery feed**: See discoveries as other sessions make them
- **Interactive sessions**: Request-response patterns work naturally

### 4. Richer Communication Patterns
- **Pub/Sub**: Natural publish-subscribe model
- **Channels/Rooms**: Group sessions by topic/project
- **Presence**: Real-time awareness of active sessions
- **Typing indicators**: Sessions can show activity status

### 5. Development Experience
- **Debuggable**: Use WebSocket inspector tools (Chrome DevTools)
- **Testable**: Easy to write integration tests
- **Standards-based**: WebSocket is a W3C standard
- **Library ecosystem**: Mature libraries (ws, socket.io, etc.)

## Cons

### 1. Operational Complexity
- **Additional process**: Requires running WebSocket server alongside Claude
- **Port management**: Need to manage port allocation (8888)
- **Process lifecycle**: Must start server before sessions, stop after
- **Monitoring**: Need to monitor server health, connection count

### 2. Failure Modes
- **Single point of failure**: If server crashes, all sessions lose communication
- **Connection issues**: Network issues can break communication
- **Recovery complexity**: Need robust reconnection logic
- **State synchronization**: Need to re-sync state after reconnection

### 3. Resource Usage
- **Memory**: Server must hold all active connections in memory
- **Network**: Uses network stack even for localhost communication
- **Persistent connections**: Each session holds an open TCP connection
- **File descriptors**: Each connection uses a file descriptor (limit: 65536)

### 4. Security Considerations
- **Local only**: Must ensure server only binds to localhost
- **No authentication**: Local sessions trusted by default
- **Port exposure**: Port 8888 visible to other processes
- **Message validation**: Must validate all incoming messages

### 5. Deployment Complexity
- **Systemd service**: Need separate systemd service for WebSocket server
- **Startup order**: Server must start before sessions
- **Graceful shutdown**: Need to handle server shutdown cleanly
- **Version coordination**: Server and clients must use compatible protocol

## Implementation Complexity

### Easy
- Basic WebSocket server (100 lines of code)
- Simple message routing
- Connection management
- Broadcast support

### Medium
- Reconnection logic with exponential backoff
- Message queuing during disconnection
- Session presence tracking
- Error handling

### Hard
- State synchronization after reconnection
- Message delivery guarantees (at-least-once, exactly-once)
- Partitioning/scaling to multiple servers
- Conflict resolution for concurrent updates

## Performance Comparison

| Metric | File Polling | WebSocket |
|--------|-------------|-----------|
| Message latency | 0-5s | <10ms |
| CPU usage (per session) | ~2% (polling) | <0.1% (idle) |
| Disk I/O | High (constant reads) | None |
| Memory | Low (shared file) | Medium (connections) |
| Scalability | 10-20 sessions | 100+ sessions |
| Network overhead | None | Minimal (localhost) |

## Use Cases

### Better with WebSocket
1. Real-time collaboration between sessions
2. Live discovery feeds
3. Interactive request-response patterns
4. Session coordination (model selection, task distribution)
5. Presence awareness (who's online)

### Better with File Polling
1. Simple deployments (no server needed)
2. Stateless communication (fire-and-forget)
3. Cross-machine communication (NFS-shared files)
4. Audit trail (messages persisted to disk)
5. Legacy compatibility (works with existing tools)

## Hybrid Approach

**Recommendation:** Use both approaches for different purposes:

1. **WebSocket for live communication** (when server available)
   - Real-time discoveries
   - Interactive requests
   - Presence awareness
   - Coordination

2. **File polling as fallback** (when server unavailable)
   - Persistent messages
   - Cross-machine communication
   - Audit trail
   - Works without server

**Implementation:**
- Sessions try WebSocket connection first
- Fall back to file polling if connection fails
- Gracefully handle server restarts
- Sync state between both channels

## Deployment Strategy

### Phase 1: WebSocket Server (Optional)
```bash
# Start WebSocket server (optional)
systemctl --user start claude-websocket-server

# Sessions auto-detect and connect
# If server not running, fall back to file polling
```

### Phase 2: Integration
- Modify SessionManager to support both transports
- Add auto-detection of WebSocket server
- Implement fallback to file polling
- Add monitoring/metrics

### Phase 3: Optimization
- Connection pooling
- Message compression
- Batching for efficiency
- Heartbeat optimization

## Recommendation

### For Single-Machine Deployment
**Use WebSocket** - Better performance, lower latency, richer features

### For Multi-Machine Fleet
**Use File Polling** - Works across NFS, simpler deployment, better reliability

### For Production
**Use Hybrid** - WebSocket when available, file polling as fallback

## Estimated Effort

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| WebSocket Server | 4 hours | ws package |
| Session Client | 4 hours | ws package |
| Integration | 8 hours | SessionManager refactor |
| Testing | 8 hours | Jest/Mocha |
| Documentation | 4 hours | - |
| **Total** | **28 hours** | **~4 days** |

## Next Steps

1. **Prototype** (2 hours)
   - Basic WebSocket server
   - Simple client
   - Proof-of-concept message passing

2. **Evaluate** (1 hour)
   - Test latency
   - Measure resource usage
   - Validate approach

3. **Decision** (1 hour)
   - Review with team
   - Decide: Build, defer, or skip
   - Document decision

## Conclusion

WebSocket provides **significant benefits** for real-time communication:
- 100-500x lower latency (10ms vs 5s)
- More efficient (no polling)
- Richer communication patterns
- Better user experience

**However**, it adds operational complexity:
- Additional server process
- More failure modes
- Deployment complexity
- State synchronization challenges

**Recommendation:**
- **Build WebSocket for single-machine deployment** (worth the effort)
- **Keep file polling for multi-machine fleet** (simpler, more reliable)
- **Use hybrid approach** for best of both worlds

**Priority:** **Medium-High** - Implement after message polling daemon is stable.
