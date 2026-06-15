# Shared Memory IPC Evaluation for Session Communication

## Overview

This document evaluates using shared memory (via `mmap` or `node-shm`) for inter-process communication (IPC) between Claude sessions as an ultra-low-latency alternative to file polling and WebSocket.

## Proposed Architecture

### Memory Layout
```
┌────────────────────────────────────────────────────────────┐
│        Shared Memory Region (/dev/shm/claude-sessions)     │
├────────────────────────────────────────────────────────────┤
│  Header (1 KB)                                             │
│    - Version                                               │
│    - Session count                                         │
│    - Message queue head/tail                               │
│    - Lock flags                                            │
├────────────────────────────────────────────────────────────┤
│  Session Registry (16 KB)                                  │
│    - Session 1: {id, pid, heartbeat, capabilities}        │
│    - Session 2: {id, pid, heartbeat, capabilities}        │
│    - ... (up to 256 sessions)                             │
├────────────────────────────────────────────────────────────┤
│  Message Queue (128 KB)                                    │
│    - Ring buffer of messages                               │
│    - Each message: {from, to, type, data, timestamp}      │
│    - Circular queue (head/tail pointers)                   │
├────────────────────────────────────────────────────────────┤
│  Discovery Cache (128 KB)                                  │
│    - Recent discoveries (last 100)                         │
│    - Indexed by ID for fast lookup                        │
└────────────────────────────────────────────────────────────┘
Total: 273 KB
```

### Process Model
```
┌─────────────────────────────────────────────────────────┐
│                   /dev/shm/claude-sessions              │
│                  (Shared Memory Segment)                │
└─────────────────────────────────────────────────────────┘
     │
     ├── mmap() ──► Session 1 (PID 12345)
     ├── mmap() ──► Session 2 (PID 12346)
     ├── mmap() ──► Session 3 (PID 12347)
     └── mmap() ──► Session 4 (PID 12348)

Each session maps same memory region into its address space.
All sessions see same data (zero-copy).
```

### Synchronization

**Option 1: Atomic Operations** (Lockless)
```javascript
// Using Atomics API (SharedArrayBuffer)
const lock = new Int32Array(sharedBuffer, 0, 1);

// Try acquire lock
if (Atomics.compareExchange(lock, 0, 0, 1) === 0) {
  // Critical section
  // ... modify shared data ...
  
  // Release lock
  Atomics.store(lock, 0, 0);
}
```

**Option 2: Mutex** (node-shm)
```javascript
import shm from 'node-shm';

// Create/attach shared memory
const seg = shm.create('claude-sessions', 273 * 1024);

// Lock
shm.lock(seg);
try {
  // Critical section
  // ... modify shared data ...
} finally {
  shm.unlock(seg);
}
```

## Pros

### 1. Ultra-Low Latency
- **Sub-millisecond**: Message passing in <100μs
- **Zero-copy**: No serialization/deserialization overhead
- **Direct memory access**: Fastest possible IPC on same machine
- **No system calls**: After mmap, just memory reads/writes

**Latency Comparison:**
| Method | Latency |
|--------|---------|
| File polling | 0-5,000ms (avg 2,500ms) |
| WebSocket | 1-10ms |
| Shared memory | 0.01-0.1ms (10-100μs) |

### 2. Maximum Efficiency
- **No serialization**: Raw binary data structures
- **No network stack**: Even localhost WebSocket uses TCP/IP
- **No context switching**: No kernel involvement (after setup)
- **Cache-friendly**: Modern CPUs optimize for shared memory

### 3. Simplicity
- **No server**: Unlike WebSocket, no separate process needed
- **No ports**: No port allocation/management
- **No connections**: Sessions just attach to memory segment
- **Automatic cleanup**: Kernel cleans up on process exit

### 4. Scalability
- **Constant overhead**: Performance independent of session count
- **High throughput**: Can handle millions of messages/sec
- **Low memory**: 273 KB total (vs 1-10MB per WebSocket connection)
- **No file I/O**: Zero disk activity

### 5. Deterministic Performance
- **No network jitter**: No TCP retransmissions, congestion control
- **No GC pauses**: No serialization allocations
- **Predictable latency**: Always <100μs (99.9th percentile)
- **Real-time capable**: Suitable for hard real-time systems

## Cons

### 1. Platform-Specific
- **Linux/macOS only**: Uses POSIX shared memory (`/dev/shm`)
- **Windows different**: Requires Windows-specific APIs
- **Architecture-dependent**: Binary layout varies by CPU arch
- **Kernel version**: Some features require recent kernels

### 2. Complexity
- **Manual memory management**: Must carefully manage memory layout
- **Synchronization**: Must implement locking correctly (hard!)
- **Race conditions**: Easy to introduce subtle bugs
- **Debugging**: Harder to debug than file or WebSocket

### 3. Fixed Size Limitations
- **Pre-allocated**: Must decide memory size upfront (273 KB)
- **Bounded queue**: Message queue can overflow if not drained
- **Session limit**: Fixed max sessions (256)
- **Discovery limit**: Fixed max cached discoveries (100)

### 4. Process Lifecycle
- **Cleanup required**: Must explicitly detach/unlink shared memory
- **Stale data**: Crashed processes can leave stale sessions
- **Initialization**: First process must initialize memory
- **Versioning**: Must handle schema changes carefully

### 5. Security
- **Shared /dev/shm**: All users can see `/dev/shm` contents
- **Permissions**: Must set correct file permissions (0600)
- **Memory exposure**: Other processes can attach if permissions wrong
- **No encryption**: Data stored in plaintext in memory

### 6. Node.js Limitations
- **Limited libraries**: Few mature Node.js shared memory libraries
  - `node-shm`: Works but unmaintained (last update 2016)
  - `SharedArrayBuffer`: Disabled by default (Spectre mitigations)
  - `mmap-io`: Low-level, requires careful use
- **No TypedArray support**: Can't use convenient ArrayBuffer views
- **Manual packing**: Must manually pack/unpack data structures

## Implementation Complexity

### High Complexity Items
1. **Lock-free algorithms**: Avoid deadlocks, ensure progress
2. **Memory layout**: Design efficient binary format
3. **Versioning**: Handle schema evolution
4. **Error recovery**: Detect and recover from corruption
5. **Testing**: Race conditions hard to test

### Example: Message Queue (Lockless Ring Buffer)
```javascript
// Simplified lockless ring buffer
class MessageQueue {
  constructor(buffer, offset, capacity) {
    this.buffer = buffer;
    this.offset = offset;
    this.capacity = capacity;
    
    // Head/tail use atomic operations
    this.head = new Int32Array(buffer, offset, 1);
    this.tail = new Int32Array(buffer, offset + 4, 1);
    this.messages = new Uint8Array(buffer, offset + 8, capacity);
  }
  
  // Producer (lock-free)
  enqueue(msg) {
    while (true) {
      const tail = Atomics.load(this.tail, 0);
      const nextTail = (tail + 1) % this.capacity;
      const head = Atomics.load(this.head, 0);
      
      // Queue full?
      if (nextTail === head) {
        return false;
      }
      
      // Try to claim slot
      if (Atomics.compareExchange(this.tail, 0, tail, nextTail) === tail) {
        // Write message
        this._writeMessage(tail, msg);
        return true;
      }
      // CAS failed, retry
    }
  }
  
  // Consumer (lock-free)
  dequeue() {
    while (true) {
      const head = Atomics.load(this.head, 0);
      const tail = Atomics.load(this.tail, 0);
      
      // Queue empty?
      if (head === tail) {
        return null;
      }
      
      // Try to claim slot
      const nextHead = (head + 1) % this.capacity;
      if (Atomics.compareExchange(this.head, 0, head, nextHead) === head) {
        // Read message
        return this._readMessage(head);
      }
      // CAS failed, retry
    }
  }
}
```

**Complexity:** 200+ lines of careful, bug-free code

## Performance Comparison

| Metric | File Polling | WebSocket | Shared Memory |
|--------|-------------|-----------|---------------|
| Latency (avg) | 2,500ms | 5ms | 0.05ms |
| Latency (p99) | 5,000ms | 10ms | 0.1ms |
| Throughput | 1 msg/s | 10,000 msg/s | 1,000,000 msg/s |
| CPU usage | High (polling) | Low | Minimal |
| Memory | Low (file) | Medium (conns) | Very Low (273KB) |
| Reliability | High (durable) | Medium (network) | High (kernel) |

## Use Cases

### Perfect for Shared Memory
1. **Ultra-low latency** requirements (<1ms)
2. **High-frequency** messaging (1000s of msgs/sec)
3. **Single machine** only
4. **Tight coordination** between sessions
5. **Real-time** model selection coordination

### Not Suitable for Shared Memory
1. **Multi-machine** fleet (can't share memory across network)
2. **Message durability** (need persistence)
3. **Audit trail** (messages not logged)
4. **Simple deployment** (adds complexity)
5. **Cross-platform** (Linux/macOS/Windows differences)

## Comparison to WebSocket

### When Shared Memory Wins
- **Latency**: 50x faster (0.05ms vs 5ms)
- **Throughput**: 100x higher (1M msg/s vs 10K msg/s)
- **No server**: Simpler deployment (no extra process)
- **Efficiency**: Zero serialization, zero network stack

### When WebSocket Wins
- **Multi-machine**: Works over network
- **Tooling**: Better debugging (WebSocket inspector)
- **Libraries**: Mature ecosystem (ws, socket.io)
- **Simplicity**: Easier to implement correctly
- **Cross-platform**: Works everywhere

## Hybrid Architecture

**Best of Both Worlds:**

```
┌───────────────────────────────────────────┐
│  Same Machine: Use Shared Memory          │
│  - Ultra-low latency                      │
│  - High throughput                        │
│  - Zero serialization                     │
└───────────────────────────────────────────┘
                  │
                  │ NFS mount
                  ▼
┌───────────────────────────────────────────┐
│  Different Machines: Use File Polling     │
│  - Works over NFS                         │
│  - Durable messages                       │
│  - Simpler deployment                     │
└───────────────────────────────────────────┘
```

Sessions auto-detect:
1. Check if shared memory segment exists
2. If yes, use shared memory
3. If no, fall back to file polling

## Libraries

### Option 1: `node-shm` (System V Shared Memory)
```bash
npm install node-shm
```

**Pros:**
- Simple API
- Works on Linux/macOS
- Mutex support built-in

**Cons:**
- Unmaintained (last update 2016)
- Limited to 32-bit int keys
- No ARM64 support

### Option 2: `mmap-io` (POSIX mmap)
```bash
npm install mmap-io
```

**Pros:**
- Modern, maintained
- Full POSIX mmap support
- Works on all platforms

**Cons:**
- Low-level API
- Must implement locking yourself
- More error-prone

### Option 3: `SharedArrayBuffer` (Native)
```javascript
// Requires --enable-shared-array-buffer flag
const sab = new SharedArrayBuffer(1024);
const view = new Int32Array(sab);
```

**Pros:**
- Native to Node.js
- Atomic operations built-in
- Cross-platform

**Cons:**
- Disabled by default (Spectre mitigations)
- Limited to ArrayBuffer (no complex objects)
- No persistence across process restart

## Recommendation

### For Current Use Case
**NOT RECOMMENDED** - Complexity outweighs benefits

**Reasons:**
1. **Over-engineered**: 0.05ms vs 5ms doesn't matter for session communication
2. **High complexity**: Lock-free algorithms are hard to get right
3. **Limited library support**: Unmaintained or low-level libraries
4. **Multi-machine future**: Won't work for fleet deployment

### When to Reconsider
- **High-frequency trading** style coordination (>1000 msgs/sec)
- **Real-time model selection** across 100+ sessions
- **Sub-millisecond latency** requirements
- **Single-machine deployment** guarantee

## Estimated Effort

| Component | Effort | Risk |
|-----------|--------|------|
| Memory layout design | 8 hours | Medium |
| Lock-free queue implementation | 16 hours | **High** |
| Session manager integration | 8 hours | Medium |
| Testing (race conditions!) | 24 hours | **High** |
| Documentation | 4 hours | Low |
| **Total** | **60 hours** | **High** |

**Note:** High risk due to:
- Subtle race conditions
- Platform-specific bugs
- Limited library support
- Difficult debugging

## Conclusion

Shared memory offers **unmatched performance**:
- 50-100x lower latency than WebSocket
- 100x higher throughput
- Minimal resource usage

**However**, the complexity is **not justified**:
- Over-engineered for current use case
- High implementation risk (race conditions)
- Doesn't work for multi-machine fleet
- Limited library ecosystem

**Recommendation:**
1. **Skip for now** - Use file polling or WebSocket instead
2. **Reconsider later** if proven performance bottleneck
3. **Only implement** if hard requirement for <1ms latency

**Priority:** **Low** - Not worth the effort unless proven critical.

## Alternative: Memory-Mapped Files

**Middle ground** between shared memory and file polling:

```javascript
import mmap from 'mmap-io';

// Memory-map session-messages.json
const fd = fs.openSync('session-messages.json', 'r+');
const buffer = mmap.map(fd, mmap.PROT_READ | mmap.PROT_WRITE);

// Read/write like normal buffer (but backed by file)
// Changes visible to other processes immediately
// Kernel handles synchronization
```

**Pros:**
- Simpler than shared memory
- Faster than read/write
- Persistent to disk
- Works with existing JSON files

**Cons:**
- Still needs locking
- File size changes problematic
- Not as fast as pure shared memory

**Recommendation:** Consider memory-mapped files if file polling becomes bottleneck.
