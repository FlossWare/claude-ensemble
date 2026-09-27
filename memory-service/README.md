# RH Memory Service

Central memory authority for all Claude Code sessions. Runs as a systemd user service, manages concurrent access to memory files across multiple simultaneous sessions.

## Architecture

```
[System Startup]
     ↓
[Memory Service Daemon] ← runs continuously
     ↑
     ├─ Claude Code Session 1 (connects via Unix socket)
     ├─ Claude Code Session 2 (connects via Unix socket)
     └─ Claude Code Session N (connects via Unix socket)
```

**Key properties:**
- **Single instance:** Only one memory service per user (systemd manages it)
- **Concurrent-safe:** All file operations protected by lock
- **Always available:** Auto-restarts on crash, survives machine reboot
- **Graceful degradation:** If service down, sessions continue with cached memory
- **Version controlled:** Service file symlinked from gitlab repo

## Installation

```bash
cd /path/to/repo
./rh-memory-service/install.sh
```

This:
1. Symlinks `rh-memory.service` to `~/.config/systemd/user/`
2. Reloads systemd
3. Enables service (auto-start on login)
4. Starts service immediately

## Operations

**View service status:**
```bash
systemctl --user status rh-memory
```

**View logs:**
```bash
journalctl --user -u rh-memory -f
```

**Restart service:**
```bash
systemctl --user restart rh-memory
```

**Stop service:**
```bash
systemctl --user stop rh-memory
```

**Disable auto-start:**
```bash
systemctl --user disable rh-memory
```

## API

Services communicate via JSON over Unix socket `/tmp/rh-memory.sock`.

### Ping
```json
{"op": "ping"}
→ {"ok": true, "message": "pong"}
```

### Read
```json
{"op": "read", "name": "project_rh_arbitration"}
→ {"ok": true, "content": "...file contents..."}
```

### Write (overwrite)
```json
{"op": "write", "name": "my_memory", "content": "..."}
→ {"ok": true}
```

### Append (JSONL)
```json
{"op": "append", "name": "decisions", "entry": {"decision": "use arbitration", "date": "2026-09-26"}}
→ {"ok": true}
```

### List
```json
{"op": "list"}
→ {"ok": true, "files": ["project_rh_toolkit_activation", "feedback_model_selection", ...]}
```

### Search
```json
{"op": "search", "keywords": ["thompson", "routing"]}
→ {"ok": true, "results": [{"file": "project_rh_toolkit_activation", "matched_keywords": 2, "size_bytes": 1234}, ...]}
```

## Client Usage

In `rh-tools-init.sh`:

```python
from rh_memory_service.memory_client import MemoryClient

# Connect (fails gracefully if service down)
client = MemoryClient()
if client.connect():
    content = client.read('project_rh_arbitration')
    results = client.search(['arbitration', 'phases'])
```

## Failure Modes

**Service crashes:**
- Systemd auto-restarts after 10 seconds
- Sessions that were connected degrade to read-only (cached at startup)
- Next request reconnects automatically

**Service stuck:**
```bash
systemctl --user restart rh-memory
```

**Socket stale:**
Service cleans up on startup. If socket file lingers:
```bash
rm /tmp/rh-memory.sock
systemctl --user restart rh-memory
```

## Files

- `memory_service.py` — Daemon (Unix socket, file I/O, threading)
- `memory_client.py` — Client library for sessions
- `rh-memory.service` — Systemd unit file
- `install.sh` — Installation script

## Thread Safety

All file operations use `threading.Lock()`:
- Concurrent reads: OK (multiple threads)
- Write + read: Serialized (lock blocks)
- Write + write: Serialized (lock blocks)

Service handles up to 5 concurrent connections (socket.listen(5)).
