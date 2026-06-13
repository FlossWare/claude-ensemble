/**
 * fleet-test - Test distributed fleet discovery and health checking
 *
 * Demonstrates fleet-utils.js API and verifies fleet connectivity
 */

export const meta = {
  name: 'fleet-test',
  description: 'Test distributed fleet discovery and health checking',
  phases: [
    { title: 'Discover Fleet', detail: 'Load config and probe machine health' },
    { title: 'Test Execution', detail: 'Run test commands on each machine' }
  ]
};

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await _agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


phase('Discover Fleet');

// Load fleet utilities
const fleetUtils = await _agent(
  `Read /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/fleet-utils.js and extract the API. Return JSON with available functions and their purpose.`,
  {
    label: 'load-fleet-utils',
    schema: {
      type: 'object',
      properties: {
        functions: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              purpose: { type: 'string' }
            },
            required: ['name', 'purpose']
          }
        }
      },
      required: ['functions']
    }
  }
);

log(`Fleet utilities loaded: ${fleetUtils.functions.length} functions available`);

// Discover all machines
const allMachines = await _agent(
  `Use Node.js to load fleet config from ~/.claude/fleet.json and return all machines with their specs. For each machine, include: hostname, role, cpus, memory_gb, tags, capabilities.`,
  {
    label: 'discover-all',
    schema: {
      type: 'object',
      properties: {
        machines: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              hostname: { type: 'string' },
              role: { type: 'string' },
              cpus: { type: 'number' },
              memory_gb: { type: 'number' },
              tags: { type: 'array', items: { type: 'string' } },
              capabilities: { type: 'array', items: { type: 'string' } }
            },
            required: ['hostname', 'role']
          }
        }
      },
      required: ['machines']
    }
  }
);

log(`Found ${allMachines.machines.length} machines in fleet config`);

// Health check all machines
const healthResults = await parallel(
  allMachines.machines.map(m => () =>
    agent(
      `SSH probe ${m.hostname}: Run 'ssh -o ConnectTimeout=2 -o BatchMode=yes ${m.hostname} "echo ok"' and return whether it succeeded.`,
      {
        label: `health-${m.hostname}`,
        schema: {
          type: 'object',
          properties: {
            hostname: { type: 'string' },
            online: { type: 'boolean' },
            response_time_ms: { type: 'number' }
          },
          required: ['hostname', 'online']
        }
      }
    )
  )
);

const onlineMachines = healthResults.filter(Boolean).filter(h => h.online);
log(`Health check complete: ${onlineMachines.length}/${allMachines.machines.length} machines online`);

phase('Test Execution');

// Get worker machines
const workers = onlineMachines
  .filter(h => {
    const machine = allMachines.machines.find(m => m.hostname === h.hostname);
    return machine && machine.role === 'worker';
  })
  .map(h => h.hostname);

log(`Testing remote execution on ${workers.length} workers`);

// Test command execution on each worker
const testResults = await parallel(
  workers.map(hostname => () =>
    agent(
      `Execute test command on ${hostname}: ssh ${hostname} "uname -a && df -h | grep Development && uptime". Return the output.`,
      {
        label: `test-${hostname}`,
        schema: {
          type: 'object',
          properties: {
            hostname: { type: 'string' },
            uname: { type: 'string' },
            nfs_mounted: { type: 'boolean' },
            uptime: { type: 'string' },
            success: { type: 'boolean' }
          },
          required: ['hostname', 'success']
        }
      }
    )
  )
);

const successCount = testResults.filter(Boolean).filter(r => r.success).length;
log(`Test execution complete: ${successCount}/${workers.length} workers passed`);

// Summary
return {
  status: 'success',
  fleet: {
    total_machines: allMachines.machines.length,
    online_machines: onlineMachines.length,
    workers_tested: workers.length,
    workers_passed: successCount
  },
  machines: allMachines.machines.map(m => {
    const health = healthResults.find(h => h && h.hostname === m.hostname);
    const test = testResults.find(t => t && t.hostname === m.hostname);
    return {
      hostname: m.hostname,
      role: m.role,
      specs: `${m.cpus} CPUs, ${m.memory_gb}GB RAM`,
      online: health ? health.online : false,
      test_passed: test ? test.success : false
    };
  }),
  message: `Fleet test complete: ${onlineMachines.length}/${allMachines.machines.length} machines online, ${successCount} workers operational`
};
