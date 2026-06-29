#!/bin/bash
set -e

echo "🔧 FIXING ALL 8 WORKERS - NO MORE LIES"
echo "======================================"
echo

WORKERS=(server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap)

for worker in "${WORKERS[@]}"; do
  echo "=== Fixing $worker ==="

  # Check Node version
  node_version=$(ssh claude@$worker 'bash -lc "node --version 2>/dev/null || echo none"')
  echo "  Node version: $node_version"

  # Check if node is in PATH during non-login SSH
  node_path=$(ssh claude@$worker 'which node 2>/dev/null || echo "NOT IN PATH"')
  echo "  Node in PATH: $node_path"

  # If node not in PATH, add to ~/.bash_profile (loaded by bash -l)
  if [[ "$node_path" == "NOT IN PATH" ]]; then
    echo "  → Adding node to PATH in ~/.bash_profile"
    ssh claude@$worker 'bash -lc "
      # Find node
      NODE_PATH=\$(find /usr -name node -type f 2>/dev/null | head -1)
      if [ -z \"\$NODE_PATH\" ]; then
        NODE_PATH=\$(find /opt -name node -type f 2>/dev/null | head -1)
      fi
      if [ -z \"\$NODE_PATH\" ]; then
        NODE_PATH=\$(find \$HOME -name node -type f 2>/dev/null | head -1)
      fi

      if [ -n \"\$NODE_PATH\" ]; then
        NODE_DIR=\$(dirname \$NODE_PATH)
        echo \"export PATH=\$NODE_DIR:\\\$PATH\" >> ~/.bash_profile
        echo \"Node found at: \$NODE_PATH\"
      else
        echo \"ERROR: Node not found on system\"
        exit 1
      fi
    "'
  fi

  # Test that node works with bash -lc
  test_result=$(ssh claude@$worker 'bash -lc "node --version"' 2>&1 || echo "FAILED")
  if [[ "$test_result" == "FAILED" ]] || [[ "$test_result" == *"not found"* ]]; then
    echo "  ❌ STILL BROKEN: $test_result"
  else
    echo "  ✅ Working: $test_result"
  fi

  echo
done

echo "======================================"
echo "Testing distributed execution..."
echo

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

node -e "
import { executeOnWorker } from './shared/execute-on-worker.js';

const WORKERS = ['server-01', 'server-02', 'server-03', 'laptop-01', 'pi-01', 'pi-02', 'desktop-ap', 'server-ap'];

console.log('Testing all 8 workers...\n');

const results = await Promise.all(
  WORKERS.map(worker => executeOnWorker({
    worker,
    model: 'llama-3.3-70b-versatile',
    task: 'Say OK',
    maxTokens: 5,
    timeoutMs: 20000
  }).catch(err => ({ worker, error: err.message.slice(0, 80) })))
);

const working = results.filter(r => !r.error).length;

results.forEach(r => {
  if (r.error) {
    console.log('❌ ' + r.worker.padEnd(12) + ': ' + r.error);
  } else {
    console.log('✅ ' + r.execution_host.padEnd(12) + ': ' + r.output);
  }
});

console.log('\nRESULT: ' + working + '/8 workers operational');

if (working === 8) {
  console.log('\n🎉 ALL 8 WORKERS ACTUALLY WORKING!');
  process.exit(0);
} else {
  console.log('\n❌ STILL BROKEN: ' + (8 - working) + ' workers failed');
  process.exit(1);
}
"
