# Running Services on Windows

Three options for Windows deployment.

---

## Option 1: WSL2 (Windows Subsystem for Linux) — RECOMMENDED

**Best for:** Windows 10/11, development, easiest setup

### Setup

```powershell
# PowerShell (admin)
wsl --install
# Install Ubuntu from Microsoft Store

# Inside WSL:
cd /mnt/c/Users/YourUser/projects/claude-global-skills
git clone https://gitlab.cee.redhat.com/sfloess/claude-global-skills.git
cd claude-global-skills

# Start services in WSL
systemctl --user start rh-thompson.service
systemctl --user start rh-learning.service
systemctl --user start rh-alert.service
```

### From Windows

```powershell
# Call services from Windows Python (uses WSL's Unix sockets)
python3 tools/feedback_capture.py --model cursor --rating 5 --task refactoring
```

### Pros
- Native Linux systemd (no changes needed)
- Unix sockets work exactly as-is
- Seamless Windows/Linux integration
- Services persist across sessions

### Cons
- Requires Windows 10/11 Pro/Enterprise
- WSL2 must be running
- ~500MB disk space

---

## Option 2: Docker — ROBUST

**Best for:** Production, team deployment, isolation

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Services run directly (no systemd needed)
CMD ["python3", "-m", "supervisord", "-c", "supervisord.conf"]
```

### supervisord.conf

```ini
[supervisord]
nodaemon=true

[program:thompson]
command=python3 thompson-service/thompson_service.py
autostart=true
autorestart=true

[program:learning]
command=python3 learning-service/learning_service.py
autostart=true
autorestart=true

[program:alert]
command=python3 alert_service/alert_service.py
autostart=true
autorestart=true
```

### Run on Windows

```powershell
# Build image
docker build -t rh-toolkit .

# Run container
docker run -d -v rh-toolkit-data:/app/learning rh-toolkit

# Access services
docker exec rh-toolkit python3 tools/feedback_capture.py --model cursor --rating 5 --task refactoring
```

### Pros
- Works anywhere (Windows, Mac, Linux, cloud)
- Services isolated
- Easy scaling
- No Windows-specific code

### Cons
- Requires Docker
- Slightly more overhead
- Network sockets instead of Unix sockets

---

## Option 3: Windows Task Scheduler — LIGHTWEIGHT

**Best for:** Light usage, no WSL/Docker

### Create batch script: `start_services.bat`

```batch
@echo off
cd C:\path\to\claude-global-skills

REM Start each service in background
start "Thompson" python3 thompson-service/thompson_service.py
start "Learning" python3 learning-service/learning_service.py
start "Alert" python3 alert_service/alert_service.py

echo Services started
```

### Schedule with Task Scheduler

```powershell
# PowerShell (admin)
$action = New-ScheduledTaskAction -Execute 'C:\path\to\start_services.bat'
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "RH-AI-Toolkit"
```

### Modifications Needed

1. **Socket paths:** Change from `/tmp/rh-*.sock` to named pipes
2. **Logging:** Change from journalctl to files
3. **Python path:** Use absolute paths

### Example socket change (learning_service.py)

```python
# Linux
SOCKET_PATH = Path('/tmp/rh-learning.sock')

# Windows
SOCKET_PATH = Path(r'\\.\pipe\rh-learning')
```

### Pros
- No external tools
- Native Windows
- Low overhead

### Cons
- Requires code modifications
- No systemd equivalence
- Manual startup/shutdown
- Harder to monitor

---

## Comparison

| Feature | WSL2 | Docker | Task Scheduler |
|---------|------|--------|----------------|
| Setup | Easy | Moderate | Easy |
| Changes needed | None | Supervisord | Code mods |
| Cross-platform | No | Yes | No |
| Production-ready | Yes | Yes | No |
| Team deployment | Good | Excellent | Poor |
| Monitoring | journalctl | Docker logs | Event log |
| **Recommended** | ✅ | ✅ | ❌ |

---

## My Recommendation

**WSL2** if you're developing on Windows and want it to just work.
- Services run in native Linux
- No code changes
- Works exactly like on Linux
- Services persist

**Docker** if you need to share with team or deploy to cloud.
- More robust
- Works anywhere
- Easier scaling

---

## Quick Start: WSL2

```bash
# 1. Install WSL2 and Ubuntu
wsl --install

# 2. Clone repo in WSL
wsl
cd ~
git clone https://gitlab.cee.redhat.com/sfloess/claude-global-skills.git
cd claude-global-skills

# 3. Start services
systemctl --user start rh-thompson.service
systemctl --user start rh-learning.service
systemctl --user start rh-alert.service

# 4. From Windows or WSL, use normally
python3 tools/feedback_capture.py --model cursor --rating 5 --task refactoring
```

---

## What Works as-is on All Platforms

- Python code (Thompson, Learning, Alert services)
- feedback_capture.py
- Any pure Python tools
- Git operations

## What Needs Adaptation

- systemd services (Linux only)
- Unix sockets (can use named pipes or TCP on Windows)
- journalctl logging (use file logging on Windows)
- /tmp paths (use temp directory on Windows)
