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

export default async function({ args, phase, log, agent, parallel }) {

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

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

}
