#!/usr/bin/env node
/**
 * Fleet Finish All Fixes - Parallel completion of remaining work
 */

export const meta = {
  name: 'fleet-finish-fixes',
  description: 'Fleet completes all remaining MCP critical fixes in parallel',
  phases: [
    { title: 'Remaining Fixes', detail: '7 failure tests + integration + deployment script' }
  ]
};

const { writeFileSync } = await import('fs');
const { join } = await import('path');

phase('Remaining Fixes');

log('Fleet completing 7 failure-mode tests + integration + deployment...');

const fixes = await parallel([
  // Fix 1: Create all 7 failure-mode tests
  () => agent(
    `Create all 7 failure-mode test files in mcp-servers/fleet-orchestrator/test/failure-modes/

Tests needed:
1. ssh-timeout.test.js - Test SSH timeout triggers retry
2. ssh-refused.test.js - Test connection refused opens circuit breaker
3. api-rate-limit.test.js - Test 429 triggers exponential backoff
4. api-auth-failure.test.js - Test 401/403 doesn't retry
5. worker-unavailable.test.js - Test graceful degradation to localhost
6. partial-consensus.test.js - Test 2/5 models responding is valid
7. database-write-failure.test.js - Test DB write retry with backoff

Use node:test framework. Import retry.js and circuit-breaker.js from ../../lib/

Return JSON with test_files array.`,
    {
      label: 'Create 7 failure tests',
      model: 'opus',
      effort: 'high'
    }
  ),

  // Fix 2: Complete deployment script
  () => agent(
    `Create complete deployment script at scripts/deploy-mcp-server.sh

Must include:
- SSH connectivity checks to all 8 workers
- PostgreSQL connection check
- API credential validation
- npm install in MCP directory
- Update ~/.claude/claude_desktop_config.json (with backup)
- Smoke test
- Rollback procedure

Make it executable. Return JSON with script_created: true.`,
    {
      label: 'Create deployment script',
      model: 'sonnet',
      effort: 'medium'
    }
  ),

  // Fix 3: Integrate error handling into fleet-orchestrator
  () => agent(
    `Update shared/fleet-orchestrator.js to integrate error handling:

1. Import withRetry from ../mcp-servers/fleet-orchestrator/lib/retry.js
2. Import CircuitBreaker from ../mcp-servers/fleet-orchestrator/lib/circuit-breaker.js
3. Import getCredentialManager from ./credential-manager.cjs
4. Wrap executeOnModel() with retry + circuit breaker
5. Use credential manager to get API keys
6. Add proper error handling

Return JSON with integrated: true, functions: ['selectModel', 'executeOnModel'].`,
    {
      label: 'Integrate error handling',
      model: 'haiku',
      effort: 'medium'
    }
  ),

  // Fix 4: Update workflow-storage-adapter to use execution_host
  () => agent(
    `Update shared/workflow-storage-adapter.cjs to populate execution_host:

1. In storeWorkerResult(), add execution_host parameter
2. Update INSERT to include execution_host column
3. In storeExecution(), add execution_hosts array parameter
4. Update INSERT to include execution_hosts column
5. Update all existing usages

Return JSON with updated: true, columns_added: ['execution_host', 'execution_hosts'].`,
    {
      label: 'Update workflow storage',
      model: 'opus',
      effort: 'medium'
    }
  ),

  // Fix 5: Create package.json for MCP server
  () => agent(
    `Create mcp-servers/fleet-orchestrator/package.json:

{
  "name": "@sfloess/mcp-fleet-orchestrator",
  "version": "1.0.0",
  "type": "module",
  "main": "index.js",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.4"
  },
  "scripts": {
    "test": "node --test test/**/*.test.js",
    "start": "node index.js"
  }
}

Return JSON with package_json_created: true.`,
    {
      label: 'Create package.json',
      model: 'haiku',
      effort: 'low'
    }
  ),

  // Fix 6: Audit API credentials across all 8 workers
  () => agent(
    `Document API credential distribution across 8 workers:

Create docs/api-credential-matrix.md showing:
- Which workers have which API keys (ANTHROPIC, OPENAI, GOOGLE, etc.)
- How to add new credentials
- Security best practices
- Validation procedure

Return JSON with documented: true, workers_audited: 8.`,
    {
      label: 'Document credentials',
      model: 'sonnet',
      effort: 'low'
    }
  ),

  // Fix 7: Create monitoring guide
  () => agent(
    `Create docs/mcp-monitoring.md:

Include:
- Key metrics to monitor (latency p95, error rate, queue depth, cost)
- Alert thresholds (error rate >5%, latency p99 >10s)
- Grafana dashboard queries
- Troubleshooting common issues
- Health check endpoints

Return JSON with monitoring_guide_created: true.`,
    {
      label: 'Create monitoring guide',
      model: 'haiku',
      effort: 'low'
    }
  )
]);

const successful = fixes.filter(Boolean);
log(`Fixes complete: ${successful.length}/7 successful`);

// Write summary
const summary = {
  workflow: 'fleet-finish-fixes',
  completed: successful.length,
  total: 7,
  fixes: successful,
  timestamp: new Date().toISOString()
};

writeFileSync(
  join(process.cwd(), 'fleet-finish-fixes-results.json'),
  JSON.stringify(summary, null, 2)
);

return summary;
