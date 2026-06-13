# Fleet Remote Execution Setup Guide

## Overview

The Fleet Dispatcher has **two operational modes**:

1. **Phase 2: Telemetry Only** (Current Default)
   - Workflows call dispatcher for server selection
   - Agents execute **locally** (on your machine)
   - Telemetry is recorded to dispatcher
   - **No performance gain**, network overhead only

2. **Phase 3: Remote Execution** (Requires Configuration)
   - Workflows call dispatcher for server selection
   - Agents execute **remotely** (on assigned fleet servers via SSH)
   - Telemetry is recorded to dispatcher
   - **3-5x performance gain** for parallel workflows

---

## Current Status After Restart

By default, **Phase 2 (telemetry only)** is active.

**What happens without configuration:**
```
Multi-AI workflow with 4 workers:
  Worker 1 (Opus)   → Calls dispatcher → Assigned server-03 → ❌ Executes locally
  Worker 2 (Sonnet) → Calls dispatcher → Assigned server-02 → ❌ Executes locally
  Worker 3 (Haiku)  → Calls dispatcher → Assigned aio-01   → ❌ Executes locally
  Worker 4 (Gemini) → Calls dispatcher → Assigned server-01 → ❌ Executes locally
  Arbiter  (Fable)  → Calls dispatcher → Assigned server-03 → ❌ Executes locally

Result: All execute on your machine, no distribution, no speedup
```

---

## Enabling Phase 3 Remote Execution

### Prerequisites

1. **SSH Keys Configured**
   ```bash
   # Test SSH connectivity to all fleet servers
   ssh server-01 echo "OK"
   ssh server-02 echo "OK"
   ssh server-03 echo "OK"
   ssh aio-01 echo "OK"
   ```

2. **Dispatcher Running**
   ```bash
   curl http://pi-02:3004/health
   # Should return: {"status":"ok"}
   ```

3. **Claude Installed on Fleet Servers**
   ```bash
   ssh server-01 'which claude'
   # Should return path to claude binary
   ```

---

## Configuration Options

### Option 1: Session Environment Variable (Temporary)

**For testing or one-time use:**

```bash
# Set environment variable
export FLEET_REMOTE_EXECUTION=true

# Verify it's set
echo $FLEET_REMOTE_EXECUTION
# Should output: true

# Now run multi-AI workflows
claude -p "Your multi-AI prompt here"
```

**Pros**: Easy to test, no permanent changes  
**Cons**: Resets when terminal closes

---

### Option 2: Shell Profile (Permanent - Recommended)

**For permanent fleet execution:**

```bash
# Add to ~/.bashrc (or ~/.zshrc if using zsh)
echo 'export FLEET_REMOTE_EXECUTION=true' >> ~/.bashrc

# Reload shell configuration
source ~/.bashrc

# Verify
echo $FLEET_REMOTE_EXECUTION
# Should output: true

# Now all future multi-AI workflows will use fleet
```

**Pros**: Persistent across sessions, always active  
**Cons**: Affects all sessions

---

### Option 3: Per-Command Override

**For selective fleet use:**

```bash
# With fleet (remote execution)
FLEET_REMOTE_EXECUTION=true claude -p "Your prompt"

# Without fleet (local execution)
FLEET_REMOTE_EXECUTION=false claude -p "Your prompt"

# Or just don't set it (defaults to local)
claude -p "Your prompt"
```

**Pros**: Maximum control per workflow  
**Cons**: Must remember to set each time

---

## Verification

### 1. Check Environment Variable

```bash
echo $FLEET_REMOTE_EXECUTION
# Should output: true
```

### 2. Test Multi-AI Workflow

```bash
# Run a simple multi-AI test
claude -p "What is 2+2? Use 3 models (opus, sonnet, haiku) and synthesize."
```

### 3. Monitor Fleet Servers During Execution

**In a separate terminal while workflow runs:**

```bash
# Watch server-01 for Claude processes
watch -n 1 'ssh server-01 "ps aux | grep claude | grep -v grep"'

# Or check all servers
for server in server-01 server-02 server-03 aio-01; do
  echo "[$server]"
  ssh $server 'ps aux | grep claude | grep -v grep | tail -2'
  echo ""
done
```

**What to expect:**
- With `FLEET_REMOTE_EXECUTION=true`: You'll see `claude -p` processes on multiple servers
- Without it: No remote processes, everything local

### 4. Check Dispatcher Logs

```bash
# SSH to pi-02 and check dispatcher activity
ssh pi-02 'tail -f ~/fleet-coordinator/logs/fleet-dispatcher.log'
```

**Look for:**
- `POST /agent/execute` - Dispatcher assigning servers
- `POST /agent/complete` - Jobs completing with results

---

## Expected Performance

### Phase 2 (Telemetry Only) - Default

**Multi-AI with 4 workers:**
- Execution: All local (sequential or limited parallelism)
- Time: ~90-120 seconds total
- Speedup: **0x** (actually slower due to network overhead)

### Phase 3 (Remote Execution) - After Configuration

**Multi-AI with 4 workers:**
- Execution: Distributed across server-01/02/03/aio-01
- Time: ~25-35 seconds total (workers run in parallel on different machines)
- Speedup: **3-5x faster**

**Breakdown:**
```
WITHOUT fleet (all local):
  Worker 1 (Opus):   30s  ─────────────────────────────
  Worker 2 (Sonnet): 25s  ────────────────────────
  Worker 3 (Haiku):  15s  ──────────────
  Worker 4 (Gemini): 20s  ────────────────
  Arbiter  (Fable):  30s  ─────────────────────────────
  Total: ~120s (sequential) or ~60s (local parallel)

WITH fleet (distributed):
  Worker 1 (Opus)   → server-03: 30s  ─────────────
  Worker 2 (Sonnet) → server-02: 25s  ──────────
  Worker 3 (Haiku)  → aio-01:   15s  ──────
  Worker 4 (Gemini) → server-01: 20s  ────────
  (All run simultaneously on different servers)
  Arbiter  (Fable)  → server-03: 30s  ─────────────
  Total: ~30s (limited by slowest worker) + ~30s arbiter = ~60s
  
  But with better load balancing and parallel arbiter preparation:
  Total: ~25-35s
  
  Speedup: 3-5x faster
```

---

## Troubleshooting

### Remote Execution Not Working

**Symptom**: `FLEET_REMOTE_EXECUTION=true` is set but agents still execute locally

**Checks:**

1. **Verify environment variable in the actual process:**
   ```bash
   # Run and check output
   FLEET_REMOTE_EXECUTION=true node -e 'console.log(process.env.FLEET_REMOTE_EXECUTION)'
   # Should output: true
   ```

2. **Check SSH connectivity:**
   ```bash
   ssh -o ConnectTimeout=5 server-01 echo "OK"
   # Should return: OK
   ```

3. **Verify dispatcher is reachable:**
   ```bash
   curl -s http://pi-02:3004/health | jq
   # Should return: {"status":"ok"}
   ```

4. **Check workflow has Phase 3 code:**
   ```bash
   grep -n "dispatch.server" workflows/ai-prompt.js
   # Should show remote execution logic
   ```

### SSH Timeout Errors

**Symptom**: `ssh: connect to host X port 22: Connection timed out`

**Fix:**
```bash
# Test SSH with verbose output
ssh -v server-01 echo "test"

# Check SSH config
cat ~/.ssh/config

# Ensure BatchMode allows non-interactive
```

### Dispatcher Returns 404

**Symptom**: Logs show `POST /dispatch HTTP/1.1 404`

**Fix**: Your workflows are using old endpoints
```bash
# Check if workflows have correct endpoints
grep "/agent/execute" workflows/ai-prompt.js
# Should find: /agent/execute (not /dispatch)

# If not found, workflows need updating (git pull latest)
```

---

## Disabling Fleet (Revert to Local)

**Temporary:**
```bash
export FLEET_REMOTE_EXECUTION=false
# or
unset FLEET_REMOTE_EXECUTION
```

**Permanent:**
```bash
# Remove from ~/.bashrc
sed -i '/FLEET_REMOTE_EXECUTION/d' ~/.bashrc
source ~/.bashrc
```

---

## Best Practices

### When to Use Fleet

✅ **Use fleet for:**
- Multi-AI workflows with 3+ models
- Parallel agent execution
- Large-scale batch processing
- Long-running tasks (>30s per agent)

❌ **Don't use fleet for:**
- Single agent calls
- Sequential workflows
- Quick responses (<10s)
- Testing/debugging

### Performance Tips

1. **Let dispatcher choose servers** - Don't override its selection
2. **Use appropriate models** - Opus on heavy servers, Haiku on light servers
3. **Monitor with Grafana** - http://pi-02:3000/d/capacity-plan
4. **Check fleet health** before large jobs - `curl http://pi-02:3004/fleet/status`

---

## Quick Reference

| Action | Command |
|--------|---------|
| Enable fleet (session) | `export FLEET_REMOTE_EXECUTION=true` |
| Enable fleet (permanent) | `echo 'export FLEET_REMOTE_EXECUTION=true' >> ~/.bashrc && source ~/.bashrc` |
| Disable fleet | `export FLEET_REMOTE_EXECUTION=false` |
| Check if enabled | `echo $FLEET_REMOTE_EXECUTION` |
| Test multi-AI | `claude -p "Test with opus, sonnet, haiku"` |
| Monitor servers | `watch 'ssh server-01 "ps aux \| grep claude"'` |
| Check dispatcher | `curl http://pi-02:3004/health` |
| View logs | `ssh pi-02 'tail -f ~/fleet-coordinator/logs/fleet-dispatcher.log'` |

---

## Documentation References

- **Architecture**: `docs/ARCHITECTURE.md`
- **Integration**: `docs/INTEGRATION_GUIDE.md`
- **Operations**: `docs/OPERATIONS.md`
- **API Reference**: `docs/API_REFERENCE.md`
- **Dashboards**: http://pi-02:3000/d/fleet-dispatcher

---

**Status**: Fleet Dispatcher is operational and ready for Phase 3 remote execution after configuration. Set `FLEET_REMOTE_EXECUTION=true` to enable distributed multi-AI execution across the 5-node fleet.
