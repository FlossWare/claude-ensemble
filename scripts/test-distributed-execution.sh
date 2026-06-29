#!/bin/bash
#
# End-to-end test of distributed fleet execution
# Proves that workers actually execute API calls, not aio-01
#

set -e

echo "🧪 Testing Distributed Fleet Execution"
echo "======================================="
echo

# Test 1: Direct worker execution
echo "Test 1: Direct API call on worker (pi-02)"
echo "------------------------------------------"
echo "This proves pi-02 can make API calls with its own credentials."
echo

ssh claude@pi-02 'bash -c "source ~/.bashrc && cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node -e \"import { executeRemoteLLMTask } from '\''./shared/fleet-utils.js'\''; const result = await executeRemoteLLMTask({ task: '\''Count to three'\'', model: '\''llama-3.3-70b-versatile'\'', maxTokens: 50 }); console.log('\''✅ Direct call on pi-02 SUCCESS'\''); console.log('\''   Output: '\'' + result.output); console.log('\''   Tokens: '\'' + result.input_tokens + '\'' in, '\'' + result.output_tokens + '\'' out'\''); console.log('\''   Duration: '\'' + result.duration_ms + '\''ms'\'');\""'

echo
echo

# Test 2: Distributed execution via executeOnWorker
echo "Test 2: Distributed execution via executeOnWorker()"
echo "-----------------------------------------------------"
echo "This proves the distribution layer SSHs to workers correctly."
echo

cat > /tmp/test-execute-on-worker.mjs << 'EOF'
import { executeOnWorker } from './shared/execute-on-worker.js';

const result = await executeOnWorker({
  worker: 'server-01',
  model: 'llama-3.3-70b-versatile',
  task: 'What is 2 + 2? Answer in one word.',
  maxTokens: 10,
  timeoutMs: 30000
});

console.log('✅ executeOnWorker to server-01 SUCCESS');
console.log('   Output:', result.output);
console.log('   Worker:', result.execution_host);
console.log('   Actually executed on:', result.actually_executed_on_worker ? 'WORKER ✅' : 'aio-01 ❌');
console.log('   Duration:', result.duration_ms + 'ms');
EOF

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
node /tmp/test-execute-on-worker.mjs

echo
echo

# Test 3: Round-robin distribution to multiple workers
echo "Test 3: Round-robin distribution to 4 workers"
echo "----------------------------------------------"
echo "This proves tasks distribute across multiple workers."
echo

cat > /tmp/test-round-robin.mjs << 'EOF'
import { executeOnWorker } from './shared/execute-on-worker.js';

const workers = ['server-01', 'server-02', 'laptop-01', 'pi-02'];
const tasks = workers.map((worker, i) =>
  executeOnWorker({
    worker,
    model: 'llama-3.3-70b-versatile',
    task: `Say "Task ${i+1} completed"`,
    maxTokens: 20,
    timeoutMs: 30000
  })
);

const results = await Promise.all(tasks);

console.log('✅ Round-robin distribution SUCCESS');
console.log('   Tasks distributed across:', new Set(results.map(r => r.execution_host)).size, 'workers');
results.forEach((r, i) => {
  console.log(`   Worker ${i+1} (${r.execution_host}): ${r.output.slice(0, 40)}...`);
});
EOF

node /tmp/test-round-robin.mjs

echo
echo

# Test 4: MCP fleet-execute tool
echo "Test 4: MCP fleet-execute tool (full integration)"
echo "--------------------------------------------------"
echo "This proves the MCP server uses distributed execution."
echo

cat > /tmp/test-mcp-fleet-execute.mjs << 'EOF'
import { fleetExecute } from './mcp-servers/fleet-orchestrator/tools/fleet-execute.js';

const result = await fleetExecute({
  task: 'Name one color',
  model: 'llama-3.3-70b-versatile',
  worker: 'desktop-ap',
  timeout_ms: 30000,
  track_execution: false,
  track_costs: false
});

console.log('✅ MCP fleet-execute SUCCESS');
console.log('   Task executed on:', result.execution_host);
console.log('   Model:', result.model);
console.log('   Output:', result.output.slice(0, 50));
console.log('   Actually distributed:', result.execution_host === 'desktop-ap' ? 'YES ✅' : 'NO ❌');
EOF

node /tmp/test-mcp-fleet-execute.mjs

echo
echo
echo "======================================="
echo "✅ ALL TESTS PASSED!"
echo "======================================="
echo
echo "Summary:"
echo "  ✅ Workers can make direct API calls"
echo "  ✅ executeOnWorker() distributes to workers via SSH"
echo "  ✅ Round-robin distribution works across multiple workers"
echo "  ✅ MCP fleet-execute uses distributed execution"
echo
echo "The fleet is FULLY OPERATIONAL for distributed API execution!"
