# Fleet SSH Orchestrator

Production-grade SSH-based fleet distribution for executing Claude CLI commands across remote workers.

## Overview

The Fleet SSH Orchestrator enables true distributed processing by executing `claude -p` commands on remote workers via SSH. Unlike API-only orchestration, this executes the full Claude CLI workflow (including tools, file access, etc.) on each worker.

**Architecture:**
- 8 API-only workers (server-01/02/03, laptop-01, pi-01/02, desktop-ap, server-ap)
- SSH user: `claude` (configured in fleet-topology.js)
- Load balancing: Round-robin with health checks
- Parallel execution: Up to 6 concurrent workers (configurable)
- Failure handling: Automatic retries with exponential backoff

## Quick Start

```javascript
import {
  executeOnWorker,
  executeParallel,
  getFleetHealth,
  selectWorker
} from './shared/fleet-ssh-orchestrator.js';

// Execute single task on specific worker
const result = await executeOnWorker({
  worker: 'server-01',
  prompt: 'Analyze the codebase structure in /tmp/project'
});

console.log(result.output); // Claude CLI output
console.log(result.duration_ms); // Execution time

// Execute multiple tasks in parallel (auto-distributed)
const results = await executeParallel({
  tasks: [
    { id: 'task-1', prompt: 'Review code in module A' },
    { id: 'task-2', prompt: 'Review code in module B' },
    { id: 'task-3', prompt: 'Review code in module C' }
  ],
  maxParallel: 6
});

results.forEach(r => {
  console.log(`${r.taskId}: ${r.error ? 'FAILED' : 'SUCCESS'}`);
  if (r.result) console.log(r.result.output);
});
```

## API Reference

### `executeOnWorker(options)`

Execute a Claude CLI command on a specific worker via SSH.

**Parameters:**
- `worker` (string, required): Worker hostname (e.g., 'server-01', 'laptop-01')
- `prompt` (string, required): Prompt to pass to `claude -p`
- `timeoutMs` (number, optional): Command timeout in milliseconds (default: 300000 = 5 min)
- `maxRetries` (number, optional): Max retry attempts on failure (default: 2)
- `skipHealthCheck` (boolean, optional): Skip pre-flight health check (default: false)

**Returns:** `Promise<Object>`
```javascript
{
  output: string,       // Claude CLI stdout
  stderr: string,       // Claude CLI stderr
  exitCode: number,     // Exit code (0 = success)
  worker: string,       // Worker hostname
  duration_ms: number,  // Total execution time
  ssh_overhead_ms: number // Estimated SSH overhead
}
```

**Throws:** `Error` if SSH fails after all retries or worker is invalid

**Example:**
```javascript
const result = await executeOnWorker({
  worker: 'laptop-01',
  prompt: 'Summarize the main function in src/index.js',
  timeoutMs: 120000,
  maxRetries: 1
});

if (result.exitCode === 0) {
  console.log('Success:', result.output);
} else {
  console.error('Failed:', result.stderr);
}
```

### `executeParallel(options)`

Execute multiple prompts across workers in parallel with automatic load balancing.

**Parameters:**
- `tasks` (array, required): Array of `{id: string, prompt: string}` objects
- `maxParallel` (number, optional): Max concurrent executions (default: 6)
- `timeoutMs` (number, optional): Per-task timeout in milliseconds (default: 300000)
- `maxRetries` (number, optional): Max retry attempts per task (default: 2)
- `requireRoles` (array, optional): Required worker roles (e.g., `['lightweight']`)

**Returns:** `Promise<Array<Object>>`
```javascript
[
  {
    taskId: string,
    result: Object,  // Same as executeOnWorker return value
    error: string    // Error message if failed
  },
  ...
]
```

**Example:**
```javascript
const results = await executeParallel({
  tasks: [
    { id: 'analyze-auth', prompt: 'Review authentication logic' },
    { id: 'analyze-db', prompt: 'Review database schema' },
    { id: 'analyze-api', prompt: 'Review API endpoints' }
  ],
  maxParallel: 3,
  timeoutMs: 600000  // 10 min per task
});

// Check success rate
const succeeded = results.filter(r => !r.error).length;
console.log(`${succeeded}/${results.length} tasks succeeded`);
```

### `selectWorker(options)`

Select next available worker using round-robin load balancing.

**Parameters:**
- `requireRoles` (array, optional): Required roles (e.g., `['lightweight']`)
- `excludeWorkers` (array, optional): Workers to exclude from selection
- `checkHealth` (boolean, optional): Check worker health before selection (default: true)

**Returns:** `Promise<string|null>` - Worker hostname or null if none available

**Example:**
```javascript
// Select any available worker
const worker = await selectWorker();

// Select lightweight worker (Pi nodes)
const lightworker = await selectWorker({
  requireRoles: ['lightweight']
});

// Select worker excluding busy ones
const worker = await selectWorker({
  excludeWorkers: ['server-01', 'laptop-01']
});
```

### `checkWorkerHealth(worker)`

Check if a worker is healthy (can accept SSH connections).

Uses cached health status if available and fresh (< 60s old).

**Parameters:**
- `worker` (string, required): Worker hostname

**Returns:** `Promise<boolean>` - true if healthy, false otherwise

**Example:**
```javascript
const healthy = await checkWorkerHealth('server-01');
if (!healthy) {
  console.error('server-01 is not responding to SSH');
}
```

### `getFleetHealth()`

Get health status for all workers.

**Returns:** `Promise<Array<Object>>`
```javascript
[
  {
    worker: string,
    healthy: boolean,
    lastCheck: number,    // Unix timestamp
    error: string,        // Error message if unhealthy
    roles: string[],
    architecture: string,
    cpu_cores: number,
    ram_gb: number
  },
  ...
]
```

**Example:**
```javascript
const health = await getFleetHealth();

// Find unhealthy workers
const unhealthy = health.filter(w => !w.healthy);
if (unhealthy.length > 0) {
  console.error('Unhealthy workers:', unhealthy.map(w => w.worker));
}

// Find high-capacity workers
const highCapacity = health.filter(w =>
  w.healthy && w.cpu_cores >= 8 && w.ram_gb >= 28
);
```

### `getAvailableWorkers(options)`

Get list of available workers.

**Parameters:**
- `requireRoles` (array, optional): Required roles
- `onlyHealthy` (boolean, optional): Only return healthy workers (default: false)

**Returns:** `Promise<string[]>` - Worker hostnames

**Example:**
```javascript
// All workers
const all = await getAvailableWorkers();

// Only healthy workers
const healthy = await getAvailableWorkers({ onlyHealthy: true });

// Lightweight workers (Pi nodes)
const pis = await getAvailableWorkers({
  requireRoles: ['lightweight'],
  onlyHealthy: true
});
```

### `clearHealthCache()`

Clear health cache (force fresh checks on next request).

Useful after making infrastructure changes or when workers have recovered.

**Example:**
```javascript
// After restarting SSH on workers
clearHealthCache();
const health = await getFleetHealth(); // Fresh checks
```

## Load Balancing Strategies

### Round-Robin (Default)

Workers are selected in rotation. Automatically skips unhealthy workers.

```javascript
const worker1 = await selectWorker(); // server-01
const worker2 = await selectWorker(); // server-02
const worker3 = await selectWorker(); // server-03
const worker4 = await selectWorker(); // laptop-01 (cycles back)
```

### Capability-Based

Filter workers by roles before selection.

```javascript
// High-capacity workers only (8+ cores, high RAM)
const highCap = await selectWorker({
  requireRoles: ['worker'], // Exclude 'lightweight'
  excludeWorkers: ['pi-01', 'pi-02']
});

// Lightweight workers (Pi nodes)
const lightweight = await selectWorker({
  requireRoles: ['lightweight']
});
```

### Manual Assignment

Bypass automatic selection and assign tasks to specific workers.

```javascript
// Critical task on most powerful worker
await executeOnWorker({
  worker: 'laptop-01', // 8 cores, 28GB RAM
  prompt: 'Perform complex analysis on large dataset'
});

// Background task on Pi node
await executeOnWorker({
  worker: 'pi-02',
  prompt: 'Monitor logs for errors'
});
```

## Error Handling

### Automatic Retries

Failed executions are automatically retried with exponential backoff (1s → 2s → 4s → max 10s).

```javascript
const result = await executeOnWorker({
  worker: 'server-01',
  prompt: 'Analyze code',
  maxRetries: 3 // Try up to 4 times (1 initial + 3 retries)
});
```

### Health Check Failures

Workers that fail health checks are automatically excluded from selection.

```javascript
// Worker selection automatically skips unhealthy workers
const worker = await selectWorker({ checkHealth: true });
if (!worker) {
  console.error('No healthy workers available');
}

// Or handle manually
const healthy = await checkWorkerHealth('server-01');
if (healthy) {
  await executeOnWorker({ worker: 'server-01', prompt: '...' });
} else {
  console.error('server-01 is down, trying fallback');
  await executeOnWorker({ worker: 'server-02', prompt: '...' });
}
```

### Timeout Handling

Tasks that exceed `timeoutMs` are killed and reported as failures.

```javascript
try {
  const result = await executeOnWorker({
    worker: 'server-01',
    prompt: 'Long-running analysis',
    timeoutMs: 600000 // 10 minutes
  });
} catch (error) {
  if (error.message.includes('timed out')) {
    console.error('Task exceeded 10-minute limit');
  }
}
```

### Partial Failures in Parallel Execution

`executeParallel` returns results for all tasks, including failures.

```javascript
const results = await executeParallel({
  tasks: [
    { id: 'task-1', prompt: '...' },
    { id: 'task-2', prompt: '...' },
    { id: 'task-3', prompt: '...' }
  ]
});

// Separate successes and failures
const succeeded = results.filter(r => !r.error);
const failed = results.filter(r => r.error);

console.log(`${succeeded.length} succeeded, ${failed.length} failed`);

// Retry failed tasks
for (const failure of failed) {
  console.error(`Task ${failure.taskId} failed: ${failure.error}`);
  // Optionally retry on different worker
}
```

## Security

### SSH Key Authentication

The orchestrator uses SSH public key authentication (no passwords). Ensure SSH keys are configured:

```bash
# On orchestrator (aio-01):
ssh-keygen -t ed25519 -C "claude@aio-01"

# Copy to each worker:
ssh-copy-id claude@server-01
ssh-copy-id claude@server-02
# ... etc

# Test connection:
ssh claude@server-01 echo OK
```

### Command Injection Prevention

Prompts are base64-encoded before being passed to SSH, preventing shell injection.

```javascript
// Safe even with shell metacharacters
await executeOnWorker({
  worker: 'server-01',
  prompt: 'Analyze files matching pattern: *.js; rm -rf /'
});
// Prompt is base64-encoded, never interpreted by shell
```

### Hostname Validation

Worker hostnames are validated against the fleet topology allowlist (from `fleet-topology.js`).

```javascript
// Valid (in fleet topology)
await executeOnWorker({ worker: 'server-01', prompt: '...' });

// Invalid (throws error)
await executeOnWorker({ worker: 'attacker.com', prompt: '...' });
// Error: Unknown worker: attacker.com. Valid workers: server-01, server-02, ...
```

### SSH Hardening

SSH connections use hardened settings:
- `BatchMode=yes` - Prevents password prompts (requires key auth)
- `StrictHostKeyChecking=accept-new` - Prevents MITM on first connect
- `ConnectTimeout=5` - Prevents indefinite hangs

## Performance

### Parallel Execution Limits

Default: 6 concurrent workers (configurable via `maxParallel`)

**Rationale:**
- 8 total workers available
- Reserve 2 workers for overhead/failures
- Prevents network saturation

**Tuning:**
```javascript
// Conservative (high reliability)
await executeParallel({ tasks, maxParallel: 3 });

// Aggressive (max throughput)
await executeParallel({ tasks, maxParallel: 8 });
```

### Health Check Caching

Health status is cached for 60 seconds to avoid redundant SSH checks.

**Benefits:**
- Reduces SSH overhead
- Faster worker selection
- Lower network traffic

**Invalidation:**
```javascript
// Force fresh health checks
clearHealthCache();
const health = await getFleetHealth();
```

### SSH Overhead

Typical SSH overhead: 50-200ms per execution.

**Mitigation:**
- Use `executeParallel` for batch tasks (amortizes overhead)
- Enable SSH connection multiplexing (ControlMaster in `~/.ssh/config`)
- Skip health checks for repeated executions on same worker

**Example (SSH multiplexing):**
```bash
# In ~/.ssh/config:
Host server-* laptop-* pi-* desktop-* aio-*
  ControlMaster auto
  ControlPath ~/.ssh/cm-%r@%h:%p
  ControlPersist 10m
```

## Troubleshooting

### "Cannot SSH to worker"

**Symptoms:** `Error: Cannot SSH to worker server-01. Ensure: ssh claude@server-01 echo OK`

**Causes:**
1. SSH not running on worker
2. Firewall blocking port 22
3. SSH keys not configured

**Solutions:**
```bash
# Test SSH connection manually
ssh claude@server-01 echo OK

# Check SSH service on worker
ssh root@server-01 systemctl status sshd

# Verify SSH keys
ssh-copy-id claude@server-01

# Check firewall
ssh root@server-01 firewall-cmd --list-all
```

### "Worker failed health check"

**Symptoms:** `Error: Worker server-01 failed health check: Connection refused`

**Causes:**
1. Worker is down
2. SSH service stopped
3. Network connectivity issues

**Solutions:**
```bash
# Check worker status
ping server-01

# SSH manually
ssh claude@server-01

# Clear cache and retry
clearHealthCache();
const healthy = await checkWorkerHealth('server-01');
```

### "SSH command timed out"

**Symptoms:** `Error: SSH command on worker server-01 timed out after 300000ms`

**Causes:**
1. Task too complex (exceeds timeout)
2. Worker overloaded (high CPU/RAM usage)
3. Network latency

**Solutions:**
```javascript
// Increase timeout
await executeOnWorker({
  worker: 'server-01',
  prompt: '...',
  timeoutMs: 600000 // 10 minutes
});

// Check worker load
const health = await getFleetHealth();
const loaded = health.find(w => w.worker === 'server-01');
console.log(loaded); // Check cpu_cores, ram_gb

// Use different worker
const worker = await selectWorker({
  excludeWorkers: ['server-01']
});
```

### "No healthy workers available"

**Symptoms:** `selectWorker()` returns `null`

**Causes:**
1. All workers down
2. All workers overloaded
3. Network partition

**Solutions:**
```javascript
// Check fleet health
const health = await getFleetHealth();
const unhealthy = health.filter(w => !w.healthy);
console.error('Unhealthy workers:', unhealthy);

// Clear cache (may be stale)
clearHealthCache();
const workers = await getAvailableWorkers({ onlyHealthy: true });

// Relax requirements
const worker = await selectWorker({
  checkHealth: false // Skip health check (fallback)
});
```

## Integration Examples

### Deep Research Workflow

```javascript
import { executeParallel } from './shared/fleet-ssh-orchestrator.js';

// Fan-out search tasks to 6 workers
const searchResults = await executeParallel({
  tasks: [
    { id: 'search-1', prompt: 'Search web for: firmware reverse engineering' },
    { id: 'search-2', prompt: 'Search web for: OpenWrt porting guide' },
    { id: 'search-3', prompt: 'Search web for: QEMU router emulation' },
    { id: 'search-4', prompt: 'Search web for: bootloader analysis' },
    { id: 'search-5', prompt: 'Search web for: GPL compliance routers' },
    { id: 'search-6', prompt: 'Search web for: device tree bindings' }
  ],
  maxParallel: 6,
  timeoutMs: 120000
});

// Aggregate results
const sources = searchResults
  .filter(r => !r.error)
  .flatMap(r => extractSources(r.result.output));
```

### Distributed Code Review

```javascript
import { executeParallel } from './shared/fleet-ssh-orchestrator.js';
import { readdir } from 'fs/promises';

// Get all source files
const files = await readdir('./src', { recursive: true });
const jsFiles = files.filter(f => f.endsWith('.js'));

// Create review tasks
const tasks = jsFiles.map(file => ({
  id: `review-${file}`,
  prompt: `Review code quality and security in src/${file}`
}));

// Execute in parallel
const reviews = await executeParallel({
  tasks,
  maxParallel: 6,
  timeoutMs: 300000
});

// Aggregate findings
const issues = reviews
  .filter(r => !r.error)
  .flatMap(r => extractIssues(r.result.output));

console.log(`Found ${issues.length} issues across ${jsFiles.length} files`);
```

### Adversarial Verification

```javascript
import { executeParallel } from './shared/fleet-ssh-orchestrator.js';

// Generate claim
const claim = await generateClaim();

// Assign workers to verify/refute
const tasks = [
  { id: 'verify-1', prompt: `Verify this claim: ${claim}` },
  { id: 'verify-2', prompt: `Verify this claim: ${claim}` },
  { id: 'refute-1', prompt: `Find flaws in this claim: ${claim}` },
  { id: 'refute-2', prompt: `Find flaws in this claim: ${claim}` },
  { id: 'neutral', prompt: `Analyze this claim objectively: ${claim}` }
];

const results = await executeParallel({ tasks, maxParallel: 5 });

// Count votes
const verified = results.filter(r =>
  !r.error && r.result.output.includes('VERIFIED')
).length;

const refuted = results.filter(r =>
  !r.error && r.result.output.includes('REFUTED')
).length;

console.log(`Claim verdict: ${verified} verify, ${refuted} refute`);
```

## Differences from Other Fleet Modules

| Module | Purpose | Execution Model |
|--------|---------|----------------|
| `fleet-ssh-orchestrator.js` | Execute Claude CLI commands | SSH to workers, run `claude -p` |
| `execute-on-worker.js` | Execute LLM API calls | SSH to workers, run Node.js script |
| `fleet-utils.js` | Multi-model orchestration | Local execution, API calls from orchestrator |
| `fleet-multisession.js` | Multi-session coordination | WebSocket to workers, session management |

**Use this module when:**
- You need full Claude CLI capabilities (tools, file access, etc.)
- Tasks require different working directories per worker
- You want workers to use their own credentials/settings

**Use `execute-on-worker.js` when:**
- You only need LLM API responses (no tools)
- Faster execution (no CLI overhead)
- Fine-grained control over API parameters

## Future Enhancements

- [ ] Worker capability scoring (CPU/RAM/network)
- [ ] Dynamic task routing based on load
- [ ] SSH connection pooling (ControlMaster automation)
- [ ] Task priority queues
- [ ] Worker affinity (same worker for related tasks)
- [ ] Execution metrics (throughput, latency, success rate)
- [ ] Integration with workflow-storage-adapter.js
- [ ] Grafana dashboard for fleet monitoring

## License

Same as parent project.
