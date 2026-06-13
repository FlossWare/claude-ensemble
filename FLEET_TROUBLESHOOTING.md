# Fleet Dispatcher Troubleshooting Guide

Comprehensive guide to diagnosing and resolving issues with the distributed fleet system. This document covers the 5-machine fleet architecture (aio-01 controller, server-01/02/03 workers, pi-02 sentinel) and the fleet dispatcher coordination layer.

---

## Quick Diagnosis Flowchart

```
Job fails or hangs?
  ├─ Check FLEET_ENABLED flag (line in workflow)
  │   └─ If false → Job uses direct agent(), no dispatch tracking
  │
  ├─ Check pi-02 dispatcher status (port 3004)
  │   └─ Unavailable → Silent fallback, check circuit breaker
  │
  ├─ Check job tracking (look for "Dispatching" logs)
  │   └─ No logs → wrapper not called or FLEET_ENABLED=false
  │
  └─ Check model health (endpoint has state info)
      └─ In backoff → Wait or restart model service
```

---

## Issue 1: Dispatcher Unavailable (Silent Fallback)

### Symptoms
- Jobs execute but no fleet tracking logs appear
- No "📤 Dispatching" or "✅ Dispatched to" messages
- Jobs still complete but don't show in fleet telemetry
- No network errors in logs

### Root Causes

**Cause 1a: Dispatcher service down on pi-02:3004**
- Pi-02 (sentinel) is offline or dispatcher not running
- Network connectivity issue between execution machine and pi-02

**Cause 1b: FLEET_ENABLED flag is false**
- Workflow has `const FLEET_ENABLED = false`
- Job type not detected correctly
- Wrapper function not invoked

**Cause 1c: Dispatcher endpoint incorrect**
- Config points to wrong port (e.g., 3002 or 3003 instead of 3004)
- Hostname resolution fails (pi-02 not resolvable)

### Diagnostic Commands

**Check pi-02 availability:**
```bash
# Test network connectivity
ping -c 3 pi-02
# Expected: 3 packets transmitted, 3 received (0% loss)

# Test SSH access (if needed for debugging)
ssh -v pi-02 'echo ok'
# Expected: Connection successful, prints "ok"

# Test port 3004 directly
curl -s http://pi-02:3004/fleet/status | head -20
# Expected: JSON response with fleet topology
```

**Check workflow configuration:**
```javascript
// In your workflow, add these diagnostics:
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true;  // <-- Verify this is true

console.log(`[FLEET] Dispatcher: ${FLEET_DISPATCHER}`);
console.log(`[FLEET] Enabled: ${FLEET_ENABLED}`);

// Test dispatcher connectivity
async function testDispatcher() {
  try {
    const resp = await fetch(`${FLEET_DISPATCHER}/fleet/status`, {
      method: 'GET',
      timeout: 5000
    });
    const data = await resp.json();
    console.log(`[FLEET] Status: OK, ${data.servers?.length || 0} servers online`);
    return true;
  } catch (err) {
    console.error(`[FLEET] Status: FAILED - ${err.message}`);
    return false;
  }
}

await testDispatcher();
```

**Check logs for fallback indicators:**
```bash
# Search for "Falling back" or "unavailable" messages
grep -i "falling back\|unavailable\|dispatch failed" workflow.log | tail -20
```

### Fix Procedures

**Fix 1a: Restart dispatcher on pi-02**
```bash
# SSH to pi-02 (if possible)
ssh pi-02

# Check if dispatcher is running
ps aux | grep dispatcher
# Look for: fleet-dispatcher, job-queue, or similar process

# Restart the service
systemctl restart fleet-dispatcher
# Or if running as manual process:
pkill -f "fleet-dispatcher"
cd ~/fleet-coordinator && ./start-dispatcher.sh &

# Verify it's online
curl http://localhost:3004/fleet/status
```

**Fix 1b: Enable FLEET_ENABLED flag**
```javascript
// In your workflow file:
const FLEET_ENABLED = true;  // Change from false to true

// Verify the _dispatchAgent and _agent wrapper are in place
// (see code-test.js lines 34-86 for reference implementation)
```

**Fix 1c: Correct dispatcher endpoint**
```javascript
// Check multi-ai-config.json for correct port
const FLEET_DISPATCHER = 'http://pi-02:3004';  // Port 3004 is correct

// NOT these:
// const FLEET_DISPATCHER = 'http://pi-02:3002';  // Legacy job queue
// const FLEET_DISPATCHER = 'http://pi-02:3003';  // Announce dispatcher
```

### Expected Behavior After Fix

When working correctly, you should see logs like:
```
[FLEET] Dispatcher: http://pi-02:3004
[FLEET] Enabled: true
[FLEET] Status: OK, 5 servers online
📤 Dispatching ai-consensus job to fleet (opus, ~60s, 2GB)
✅ Dispatched to server-03 (jobId: abc123def456)
✅ Job complete (45.3s)
```

---

## Issue 2: Circuit Breaker in Backoff

### Symptoms
- Model health endpoint shows "BACKOFF" state
- Jobs rejected with "Model in circuit breaker"
- Repeated failures for specific model
- Error message includes backoff timer (e.g., "backoff: 120s")

### Root Causes

**Cause 2a: Model service crashed or degraded**
- Too many failures for a specific model (e.g., opus)
- Model API endpoint unreachable (network issue, timeout)
- Model runs out of context/memory and starts failing

**Cause 2b: Circuit breaker triggered by threshold**
- Default threshold: 5+ consecutive failures trigger backoff
- Backoff period: 30s → 60s → 120s → 300s (exponential)
- Cannot submit jobs during backoff period

**Cause 2c: Resource exhaustion on model server**
- Server running that model (e.g., laptop-01 for opus) is overloaded
- Job queue backed up, new jobs timeout before execution
- RAM pressure causes model inference to fail

### Diagnostic Commands

**Check model health status:**
```bash
# Fetch current circuit breaker state
curl -s http://pi-02:3004/fleet/status | jq '.model_health'

# Expected output:
# {
#   "opus": {"status": "UP", "failures": 0, "backoff_until": null},
#   "sonnet": {"status": "UP", "failures": 0, "backoff_until": null},
#   "haiku": {"status": "BACKOFF", "failures": 8, "backoff_until": 1718000000}
# }
```

**Check which server runs the model:**
```bash
# From multi-ai-config.json, find model assignment:
grep -A 5 '"opus"' multi-ai-config.json
# Expected: "server": "laptop-01"

# Then check server health:
curl -s http://pi-02:3004/fleet/status | jq '.servers[] | select(.instance | contains("laptop-01"))'
```

**Check model service on that server:**
```bash
# SSH to the server running the model
ssh laptop-01

# Check if model service is running
ps aux | grep "opus\|fable\|model"
# Or check system health:
free -h
# Look for available RAM

# Check CPU load
uptime
# High load average = overloaded

# Check disk space (models may be stored on disk)
df -h ~/models
```

### Fix Procedures

**Fix 2a: Restart model service**
```bash
# SSH to server running the model
ssh laptop-01

# Find the model service (examples)
systemctl status claude-opus-service
# Or manually:
ps aux | grep opus

# Restart it
systemctl restart claude-opus-service
# Or kill and restart:
pkill -f "opus"
cd ~/model-services && ./start-opus.sh &

# Wait 30 seconds for startup
sleep 30

# Check it's responding
curl http://localhost:8000/health
```

**Fix 2b: Wait for backoff to expire**
```bash
# Option 1: Wait (check exact time)
now=$(date +%s)
curl -s http://pi-02:3004/fleet/status | jq '.model_health | to_entries[] | select(.value.status == "BACKOFF") | {model: .key, expires_in_seconds: (.value.backoff_until - '$now')}'

# Option 2: Manually reset circuit breaker (if available)
curl -X POST http://pi-02:3004/reset-breaker -d '{"model":"opus"}'

# Option 3: Switch to alternate model (if available)
# Use sonnet instead of opus if opus is in backoff
# Update the model parameter in your agent() call
```

**Fix 2c: Reduce load on model server**
```bash
# Check running jobs on laptop-01
ssh laptop-01
ps aux | grep -i "opus\|inference\|agent"

# Kill non-essential jobs if needed (carefully!)
kill <pid>

# Check memory
free -h
# If RAM usage > 80%, reboot or kill jobs

# Check if job queue is backed up
curl -s http://pi-02:3004/fleet/status | jq '.servers[] | select(.instance | contains("laptop-01")) | .pending_jobs'

# If pending_jobs > 20, jobs are piling up
# Scale back job submission rate or distribute to other servers
```

### Expected Behavior After Fix

After fixing, circuit breaker should return to normal:
```
curl -s http://pi-02:3004/fleet/status | jq '.model_health.opus'

# Expected:
# {
#   "status": "UP",
#   "failures": 0,
#   "backoff_until": null
# }
```

---

## Issue 3: Jobs Not Tracked (Missing Job IDs)

### Symptoms
- Jobs complete successfully but no job tracking info
- No jobId in dispatch response
- Missing from job history/telemetry
- But workflow doesn't error—it just ignores the dispatcher

### Root Causes

**Cause 3a: FLEET_ENABLED constant is false**
- Workflow has `const FLEET_ENABLED = false` at top of file
- `_dispatchAgent()` immediately returns null (line 39)
- Falls back to direct agent() call (line 74)

**Cause 3b: _agent() wrapper not calling _dispatchAgent()**
- Wrapper function defined but not used in agent calls
- Agent calls use `agent()` directly instead of `_agent()`
- Or wrapper is missing job type detection

**Cause 3c: Dispatcher returns null silently**
- Network error but caught in try-catch (line 54)
- Dispatcher endpoint unreachable
- Malformed request body

### Diagnostic Commands

**Check FLEET_ENABLED flag:**
```bash
# In your workflow file, search for:
grep -n "FLEET_ENABLED" code-test.js
# Should show: const FLEET_ENABLED = true;

# If false, this explains everything
```

**Verify _agent wrapper is being used:**
```javascript
// In your workflow, check how agent() is being called:

// WRONG: Direct agent() call (bypasses dispatcher)
const result = await agent(prompt, { model: 'opus' });

// RIGHT: Using _agent wrapper
const result = await _agent(prompt, { model: 'opus' });
```

**Add dispatch tracking to workflow:**
```javascript
async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) {
    console.log('[FLEET] Dispatch disabled (FLEET_ENABLED=false)');
    return null;
  }
  
  console.log(`[FLEET] Attempting dispatch for ${model}/${jobType}`);
  
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: 1.5,
        estimated_duration: 60
      }),
      timeout: 5000
    });
    
    if (!response.ok) {
      console.error(`[FLEET] HTTP error: ${response.status}`);
      return null;
    }
    
    const data = await response.json();
    console.log(`[FLEET] Dispatched: jobId=${data.job_id}, server=${data.server}`);
    return data;
  } catch (e) {
    console.error(`[FLEET] Dispatch failed: ${e.message}`);
    return null;
  }
}
```

**Search logs for dispatch activity:**
```bash
grep -E "\[FLEET\]|Dispatching|jobId" workflow-execution.log
# Should see dispatch attempts and job IDs
```

### Fix Procedures

**Fix 3a: Enable FLEET_ENABLED**
```javascript
// In your workflow file (e.g., code-test.js):
// Change this:
const FLEET_ENABLED = false;

// To this:
const FLEET_ENABLED = true;
```

**Fix 3b: Use _agent wrapper instead of agent()**
```javascript
// Replace all direct agent() calls with _agent():

// OLD:
const result = await agent(prompt, { model: 'opus' });

// NEW:
const result = await _agent(prompt, { model: 'opus' });

// Or wrap the entire agent function:
const originalAgent = agent;
agent = _agent;
// Then all downstream code using agent() gets dispatch tracking
```

**Fix 3c: Verify job type detection**
```javascript
// Improve job type inference (currently all jobs are type='agent')
async function _dispatchAgent(model, prompt, jobType) {
  // Detect better job type from prompt/model
  if (!jobType || jobType === 'agent') {
    if (prompt.includes('review') || prompt.includes('code analysis')) {
      jobType = 'code-review';
    } else if (prompt.includes('test') || prompt.includes('pytest')) {
      jobType = 'code-execute';
    } else if (model === 'fable' || model === 'opus') {
      jobType = 'ai-heavy';
    } else if (model === 'haiku') {
      jobType = 'ai-light';
    }
  }
  
  // ... rest of dispatch
}
```

### Expected Behavior After Fix

After enabling tracking, you should see:
```
[FLEET] Dispatch enabled (FLEET_ENABLED=true)
[FLEET] Attempting dispatch for opus/ai-consensus
[FLEET] Dispatched: jobId=abc123, server=server-03
📤 Dispatching ai-consensus job to fleet
✅ Dispatched to server-03 (jobId: abc123)
```

---

## Issue 4: Performance Issues (Slow Job Execution)

### Symptoms
- Jobs taking much longer than expected (2-3x normal)
- High latency before job starts executing
- Network timeouts on dispatcher communication
- Jobs report long queue wait times

### Root Causes

**Cause 4a: Network latency between machines**
- Slow WiFi or congested network
- DNS resolution delays
- High RTT to pi-02 (dispatcher)

**Cause 4b: Job backlog on target server**
- Multiple jobs queued on the selected server
- Server chosen is overloaded
- Job selection doesn't consider current load

**Cause 4c: Dispatcher is slow or overloaded**
- Pi-02 (dispatcher/sentinel) running too many tasks
- Fleet status endpoint taking >1 second to respond
- Load balancing decisions inefficient

**Cause 4d: Large prompt payloads**
- Prompts > 5KB take longer to serialize/transmit
- Each job estimated at ~45s due to prompt size
- Multiplied across multiple parallel jobs

### Diagnostic Commands

**Measure network latency:**
```bash
# Test latency to dispatcher
ping -c 10 pi-02 | tail -1
# Expected: < 5ms average (local network)
# If > 50ms: Network issue or DNS slow

# Test DNS resolution speed
time nslookup pi-02
# Should complete in < 100ms

# Test TCP connection time to dispatcher
time curl -m 5 -o /dev/null -s http://pi-02:3004/fleet/status
# Should be < 1 second
```

**Check server load:**
```bash
# Get current job queue depths
curl -s http://pi-02:3004/fleet/status | jq '.servers[] | {instance, pending_jobs, load_1m, avail_ram_gb}'

# Expected:
# {
#   "instance": "laptop-01:9100",
#   "pending_jobs": 2,        <-- Look for high values
#   "load_1m": 1.5,           <-- < num_cpus is good
#   "avail_ram_gb": 4.2       <-- > 2 GB is good
# }

# If pending_jobs > 20 on any server, it's overloaded
```

**Check job execution times:**
```bash
# Query fleet history (if available)
curl -s http://pi-02:3004/fleet/history?model=opus | jq '.[] | {started, completed, duration_seconds}'

# Or in workflow logs, measure actual times:
grep -E "Dispatched to|Job complete" workflow.log | paste - - | awk '{print $NF}'
```

**Measure actual dispatch overhead:**
```javascript
// Add timing measurements:
async function _dispatchAgent(model, prompt, jobType) {
  const t0 = Date.now();
  
  // ... dispatch request
  
  const t1 = Date.now();
  console.log(`[TIMING] Dispatch request: ${t1 - t0}ms`);
}

async function _agent(prompt, opts = {}) {
  const t0 = Date.now();
  const dispatch = await _dispatchAgent(...);
  const t1 = Date.now();
  
  if (!dispatch) {
    console.log(`[TIMING] Dispatch overhead: ${t1 - t0}ms (fell back to direct)`);
    return agent(prompt, opts);
  }
  
  const result = await someRemoteExecution(...);
  const t2 = Date.now();
  
  console.log(`[TIMING] Total: ${t2 - t0}ms (dispatch: ${t1 - t0}ms, execution: ${t2 - t1}ms)`);
  return result;
}
```

### Fix Procedures

**Fix 4a: Optimize network**
```bash
# Check WiFi signal strength (if on WiFi)
iwconfig wlan0 | grep "Signal level"
# < -70dBm is weak, try wired connection

# Check if NFS is bottleneck (Development/ directory)
# Switch to local temp directory for workflow execution
cd /tmp && node workflow.js

# Test direct SSH to workers (faster than HTTP)
ssh server-03 'echo test' | time cat
```

**Fix 4b: Implement load-aware job selection**
```javascript
// Current: Round-robin or random selection
// Better: Query load and select least-loaded

async function selectBestServer(jobType) {
  // Get current fleet status
  const resp = await fetch('http://pi-02:3004/fleet/status');
  const status = await resp.json();
  
  // Find servers by role that match jobType
  const candidates = status.servers.filter(s => {
    if (jobType === 'code') return s.roles.includes('code');
    if (jobType === 'heavy') return s.roles.includes('heavy');
    if (jobType === 'fast') return s.roles.includes('fast');
    return true;  // Any server
  });
  
  // Sort by load, select least-loaded
  const selected = candidates
    .sort((a, b) => (a.pending_jobs || 0) - (b.pending_jobs || 0))[0];
  
  return selected?.instance || 'server-03:9100';
}
```

**Fix 4c: Use dispatcher async/don't wait for full response**
```javascript
// Instead of waiting for dispatcher to select server:
// Dispatch job asynchronously and execute on local machine

const dispatchPromise = _dispatchAgent(...).catch(() => null);

// Execute locally while dispatch happens in background
const result = await agent(prompt, opts);

// Later, log the dispatch result if it succeeded
const dispatch = await dispatchPromise;
if (dispatch) {
  console.log(`[FLEET] Also dispatched to ${dispatch.server} (jobId: ${dispatch.job_id})`);
}
```

**Fix 4d: Compress large prompts**
```javascript
// Break large prompts into smaller chunks
function chunkPrompt(prompt, maxSize = 5000) {
  if (prompt.length <= maxSize) return [prompt];
  
  // Split on sentence boundaries
  const sentences = prompt.match(/[^.!?]+[.!?]+/g) || [];
  const chunks = [];
  let current = '';
  
  for (const sentence of sentences) {
    if ((current + sentence).length > maxSize && current) {
      chunks.push(current);
      current = sentence;
    } else {
      current += sentence;
    }
  }
  
  if (current) chunks.push(current);
  return chunks;
}

// Use chunks for dispatch estimation
const chunks = chunkPrompt(prompt);
const estimatedDuration = chunks.length * 30;  // 30s per chunk
```

### Expected Behavior After Fix

After optimization, job latency should be < 2 seconds end-to-end:
```
[TIMING] Dispatch request: 250ms
[TIMING] Server selected: server-03
[TIMING] Job execution: 35000ms (35 seconds)
[TIMING] Total: 35250ms
```

---

## Issue 5: Common Error Messages and Solutions

### Error: "HTTP 503 Service Unavailable"

**Context:** Dispatcher returns 503

**Cause:** All servers overloaded or dispatcher itself down

**Solution:**
```bash
# Check dispatcher health
curl -i http://pi-02:3004/health

# Check server availability
curl -s http://pi-02:3004/fleet/status | jq '.servers[] | select(.is_overloaded == true)'

# If overloaded: Wait 1-2 minutes for jobs to complete
# Or kill non-essential jobs
```

### Error: "Connection timeout to pi-02:3004"

**Context:** Cannot reach dispatcher at all

**Cause:** Pi-02 offline, network issue, or port wrong

**Solution:**
```bash
# Verify pi-02 is reachable
ping pi-02
ssh pi-02 'uptime'

# Check port is correct in config
grep -n "3004" multi-ai-config.json fleet-utils.js

# Try alternate ports (3002, 3003)
curl http://pi-02:3002/fleet/status
curl http://pi-02:3003/nodes
```

### Error: "Circuit breaker open for model X"

**Context:** Specific model is in failure state

**Cause:** Model service crashed or overloaded

**Solution:**
```bash
# Wait for backoff to expire (automatically)
# Or reset manually:
curl -X POST http://pi-02:3004/reset-breaker -H "Content-Type: application/json" -d '{"model":"opus"}'

# Or switch to alternate model:
const result = await _agent(prompt, { model: 'sonnet' });  // instead of opus
```

### Error: "Job exceeded estimated duration"

**Context:** Job ran longer than estimated time

**Cause:** Resource estimates too conservative, or actual job is slow

**Solution:**
```javascript
// Increase estimated duration in dispatch
async function _dispatchAgent(model, prompt, jobType) {
  // Current: 60 seconds
  // New: 120 seconds (double)
  
  const dispatch = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
    method: 'POST',
    body: JSON.stringify({
      model,
      prompt: prompt.slice(0, 200),
      job_type: jobType,
      estimated_ram: 2.0,
      estimated_duration: 120  // <-- Increased
    })
  });
}
```

### Error: "Dispatch returned null"

**Context:** Dispatcher accepted request but returned no data

**Cause:** Malformed response, network corruption, or dispatcher bug

**Solution:**
```javascript
// Add response validation
async function _dispatchAgent(model, prompt, jobType) {
  const resp = await fetch(`${FLEET_DISPATCHER}/dispatch`, {...});
  const data = await resp.json();
  
  // Validate response has required fields
  if (!data.job_id || !data.server) {
    console.error('Invalid dispatch response:', data);
    return null;  // Trigger fallback
  }
  
  return data;
}
```

### Error: "Remote agent failed: SSH timeout"

**Context:** Executing on remote server timed out

**Cause:** Server overloaded, SSH connection issue, or execution took too long

**Solution:**
```bash
# Check SSH connectivity to server
ssh -o ConnectTimeout=5 server-03 'echo ok'

# Check server load
ssh server-03 'top -bn1 | head -20'

# Check if job is still running
ssh server-03 'ps aux | grep agent'

# Increase SSH timeout in fleet-utils.js
// Add timeout option: { timeout: 120000 } (120 seconds)
```

---

## Diagnostic Checklist

When debugging fleet issues, work through this checklist:

```
[ ] 1. FLEET_ENABLED is true in workflow
[ ] 2. Pi-02 dispatcher is running (curl pi-02:3004/fleet/status)
[ ] 3. Network connectivity OK (ping pi-02, low latency)
[ ] 4. Model health shows no "BACKOFF" states
[ ] 5. Server loads reasonable (< 5 pending jobs each)
[ ] 6. _dispatchAgent and _agent functions defined
[ ] 7. _agent wrapper used instead of direct agent()
[ ] 8. Job type detection working (not all "agent" type)
[ ] 9. Prompts are reasonable size (< 5KB is optimal)
[ ] 10. Dispatcher response has job_id and server fields
```

---

## Advanced Debugging

### Enable verbose logging

```javascript
// Add at top of workflow:
process.env.DEBUG = 'fleet*';

// Then add detailed logging to fleet functions:
async function _dispatchAgent(model, prompt, jobType) {
  console.log(`[DEBUG] Dispatching: model=${model}, jobType=${jobType}, promptLen=${prompt.length}`);
  
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: 1.5,
        estimated_duration: 60
      })
    });
    
    console.log(`[DEBUG] Response status: ${response.status}`);
    const data = await response.json();
    console.log(`[DEBUG] Dispatch result: jobId=${data.job_id}, server=${data.server}`);
    return data;
  } catch (e) {
    console.error(`[DEBUG] Dispatch error: ${e.message}`, e.stack);
    return null;
  }
}
```

### Capture full request/response

```javascript
// Proxy dispatcher calls to log details
async function dispatchWithLogging(model, prompt, jobType) {
  const requestBody = {
    model,
    prompt: prompt.slice(0, 200),
    job_type: jobType,
    estimated_ram: 1.5,
    estimated_duration: 60
  };
  
  console.log('[REQUEST]', JSON.stringify(requestBody, null, 2));
  
  const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody)
  });
  
  console.log('[RESPONSE_STATUS]', response.status);
  const data = await response.json();
  console.log('[RESPONSE_BODY]', JSON.stringify(data, null, 2));
  
  return data;
}
```

### Monitor Pi-02 directly

```bash
# SSH to pi-02 and monitor dispatcher logs
ssh pi-02 'tail -f ~/fleet-dispatcher.log | grep -i "dispatch\|error\|backoff"'

# Check dispatcher process
ssh pi-02 'ps aux | grep dispatcher'

# Check port is listening
ssh pi-02 'netstat -tlnp | grep 3004'

# Check dispatcher memory/CPU
ssh pi-02 'top -bn1 -p <PID> | head -20'
```

---

## Prevention Best Practices

### 1. Always enable FLEET_ENABLED in production

```javascript
// Good: Fleet tracking enabled
const FLEET_ENABLED = process.env.NODE_ENV !== 'development' || process.env.FORCE_FLEET === 'true';
```

### 2. Use _agent wrapper pattern consistently

```javascript
// Define early in workflow, use everywhere
const _agent = createFleetAgent(FLEET_ENABLED, agent);

// All agent calls use _agent:
const result = await _agent(prompt, { model: 'opus' });
```

### 3. Implement job type detection

```javascript
// Classify jobs for better load balancing
function detectJobType(prompt, label) {
  if (prompt.includes('review')) return 'code-review';
  if (prompt.includes('test')) return 'code-execute';
  if (label?.includes('arbiter')) return 'ai-consensus';
  return 'agent';  // default
}
```

### 4. Monitor dispatcher regularly

```bash
# Add to crontab to check health every 5 minutes
*/5 * * * * curl -s http://pi-02:3004/fleet/status | jq '.model_health' >> ~/fleet-health.log
```

### 5. Implement fallback gracefully

```javascript
// If dispatcher unavailable, fall back to direct agent()
const result = dispatch ? remoteResult : directResult;

// Don't let dispatcher failure block workflow
try {
  const result = await _agent(...);
} catch (err) {
  console.warn('Fleet dispatch failed, using fallback:', err.message);
  const result = await agent(...);  // Direct fallback
}
```

---

## Related Documentation

- **Fleet Operations Guide:** `learnings/fleet_operations_guide.md`
- **Fleet Architecture:** `learnings/fleet_architecture_complete.md`
- **Fleet Discovery:** `learnings/fleet_discovery_static_vs_dynamic.md`
- **Multi-AI Config:** `multi-ai-config.json` (server assignments, job types)
- **Dispatcher Source:** `fleet-agent-dispatcher.js` (resource estimation, job type detection)
- **Utils:** `fleet-utils.js` (API wrappers, health checks)

---

## Support Contacts

If issues persist:

1. Check pi-02 directly (if SSH access available)
2. Review dispatcher logs: `ssh pi-02 'tail -100 ~/dispatcher.log'`
3. Verify network connectivity and DNS resolution
4. Enable verbose logging and capture full request/response cycles
5. Test dispatcher with curl before assuming workflow issue

---

**Last Updated:** 2026-06-13
**Fleet Version:** 2.x with Circuit Breaker
**Dispatcher Ports:** 3004 (primary), 3002 (legacy), 3003 (announce)
