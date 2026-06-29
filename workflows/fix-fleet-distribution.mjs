#!/usr/bin/env node
export const meta = {
  name: 'fix-fleet-distribution',
  description: 'Fix critical architectural flaw - workers must actually execute API calls via SSH',
  phases: [
    { title: 'Fix Architecture', detail: 'Implement real SSH execution on workers' },
    { title: 'Verify Distribution', detail: 'Confirm workers execute tasks' }
  ]
};

phase('Fix Architecture');

log('Fixing fleet distribution - implementing REAL remote execution...');

const fix = await agent(`CRITICAL FIX: Implement actual remote execution on workers

PROBLEM: executeRemoteLLMTask runs locally on aio-01, not on workers.

Current (WRONG):
- fleet-execute.js selects worker hostname
- executeRemoteLLMTask runs fetch() LOCALLY
- execution_host is just metadata (lie)

Fix (CORRECT):
- SSH to selected worker
- Worker executes API call using ITS credentials
- Return result from worker

IMPLEMENTATION:

1. CREATE: shared/execute-on-worker.js

\`\`\`javascript
import { exec } from 'child_process';
import { promisify } from 'util';
import shellescape from 'shell-escape';

const execAsync = promisify(exec);

export async function executeOnWorker({ worker, model, task, maxTokens = 4096, timeoutMs = 120000 }) {
  // Build command that runs on worker
  const workerScript = \`
    const { executeRemoteLLMTask } = require('./shared/fleet-utils.js');
    executeRemoteLLMTask({
      task: process.argv[1],
      model: process.argv[2],
      maxTokens: parseInt(process.argv[3]),
      timeoutMs: parseInt(process.argv[4])
    }).then(result => {
      console.log(JSON.stringify(result));
    }).catch(err => {
      console.error(JSON.stringify({ error: err.message }));
      process.exit(1);
    });
  \`;

  // SSH to worker and execute
  const escapedTask = shellescape([task]);
  const escapedModel = shellescape([model]);

  const sshCmd = [
    'ssh',
    '-o', 'ConnectTimeout=5',
    '-o', 'StrictHostKeyChecking=no',
    \`claude@\${worker}\`,
    \`cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node -e '\${workerScript}' \${escapedTask} \${escapedModel} \${maxTokens} \${timeoutMs}\`
  ];

  const { stdout, stderr } = await execAsync(sshCmd.join(' '), {
    timeout: timeoutMs + 5000,
    maxBuffer: 10 * 1024 * 1024 // 10MB
  });

  if (stderr && stderr.includes('error')) {
    throw new Error('Worker execution failed: ' + stderr);
  }

  const result = JSON.parse(stdout.trim());

  if (result.error) {
    throw new Error('Worker API call failed: ' + result.error);
  }

  return {
    ...result,
    execution_host: worker,
    actually_executed_on_worker: true
  };
}
\`\`\`

2. UPDATE: mcp-servers/fleet-orchestrator/tools/fleet-execute.js

Replace line 30:
\`\`\`javascript
// OLD (runs locally):
const apiResult = await executeRemoteLLMTask({
  task,
  model: selectedModel,
  maxTokens: 4096,
  timeoutMs: timeout_ms
});

// NEW (runs on worker):
import { executeOnWorker } from '../../../shared/execute-on-worker.js';

const apiResult = await executeOnWorker({
  worker: selectedWorker,
  model: selectedModel,
  task,
  maxTokens: 4096,
  timeoutMs: timeout_ms
});
\`\`\`

3. ADD shell-escape dependency to package.json if missing

4. VERIFY:
- Read the updated files
- Confirm executeOnWorker uses SSH
- Confirm fleet-execute.js imports executeOnWorker

Return JSON:
{
  "fixed": true,
  "files_created": ["shared/execute-on-worker.js"],
  "files_updated": ["mcp-servers/fleet-orchestrator/tools/fleet-execute.js"],
  "actually_distributes": true
}`,
{ label: 'Implement real SSH execution', model: 'opus', effort: 'high' });

log('Architecture fix complete. Now verifying...');

phase('Verify Distribution');

const verify = await agent(`VERIFY: Workers actually execute tasks

TEST:

1. Sync code to all workers:
   ./scripts/sync-fleet.sh

2. Test execution on specific worker:
   - Pick a worker (e.g., pi-02)
   - Before test: ssh claude@pi-02 'ps aux | grep node'
   - Run test task via MCP
   - During test: ssh claude@pi-02 'ps aux | grep node' (should see node process)
   - After test: verify result shows execution_host: pi-02

3. Test round-robin distribution:
   - Run 8 tasks with worker='auto'
   - Check which workers executed each
   - Should distribute across multiple workers

4. Verify API calls originate from worker IPs (not aio-01):
   - Check Anthropic/OpenAI logs if available
   - Or: tcpdump on aio-01 (should NOT see API traffic)
   - Or: tcpdump on worker (SHOULD see API traffic)

Return JSON:
{
  "workers_actually_execute": true/false,
  "distribution_confirmed": true/false,
  "evidence": "...",
  "grade": "A/B/C/F"
}`,
{ label: 'Verify workers execute', model: 'sonnet', effort: 'high' });

log('Fleet distribution fix complete!');

return {
  fix,
  verify,
  production_ready: fix?.fixed && verify?.workers_actually_execute
};
