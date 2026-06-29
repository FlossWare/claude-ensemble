#!/usr/bin/env node
export const meta = {
  name: 'fleet-fixes-all-mcp-criticals',
  description: 'Fix all 10 critical MCP server issues in parallel',
  phases: [
    { title: 'Critical Fixes', detail: '8 security and reliability fixes' },
    { title: 'Missing Features', detail: '3 core features' },
    { title: 'Verification', detail: 'Comprehensive testing' }
  ]
};

export default async function({ args, phase, log, agent, parallel }) {

phase('Critical Fixes');

log('Fixing 10 critical issues across 8+ agents in parallel...');

const criticalFixes = await parallel([
  // Fix 1: SSH command injection
  () => agent('Fix SSH command injection in mcp-servers/fleet-orchestrator/tools/fleet-execute.js by installing and using shell-escape package. Replace vulnerable line 21 with proper shell escaping. Return JSON with fixed:true',
  { label: 'Fix SSH injection', model: 'opus', effort: 'high' }),

  // Fix 2: Worker validation + memory leak
  () => agent('Fix worker hostname validation in fleet-execute.js by checking against WORKERS array. Fix CircuitBreaker memory leak by adding cleanup interval to remove old entries. Return JSON with fixed:true',
  { label: 'Fix validation + leak', model: 'sonnet', effort: 'medium' }),

  // Fix 3: Replace dummy echo with real API calls
  () => agent('Replace dummy echo command in fleet-execute.js with real LLM API execution using executeRemoteLLMTask from shared/fleet-utils.js. Return JSON with implemented:true',
  { label: 'Implement real API calls', model: 'opus', effort: 'high' }),

  // Fix 4: Database integration
  () => agent('Add database integration to fleet-execute.js by importing workflow-storage-adapter and calling storeWorkerResult after successful execution. Return JSON with integrated:true',
  { label: 'Add DB integration', model: 'haiku', effort: 'medium' }),

  // Fix 5: Retry filtering + circuit breaker race
  () => agent('Add retry filtering to lib/retry.js to skip retrying 401/403/400 errors. Fix circuit breaker race condition with atomic counter operations. Return JSON with fixed:true',
  { label: 'Fix retry + race', model: 'opus', effort: 'high' }),

  // Fix 6: Total timeout + jitter
  () => agent('Add total timeout tracking across all retry attempts and jitter to exponential backoff in lib/retry.js. Return JSON with implemented:true',
  { label: 'Add timeout + jitter', model: 'sonnet', effort: 'medium' }),

  // Fix 7: Implement fleet-consensus tool
  () => agent('Create mcp-servers/fleet-orchestrator/tools/fleet-consensus.js for multi-model voting. Execute task on multiple models and return consensus results. Update index.js TOOLS array. Return JSON with implemented:true',
  { label: 'Implement consensus tool', model: 'opus', effort: 'high' }),

  // Fix 8: Integrate shared/fleet-utils.js
  () => agent('Remove hardcoded WORKERS arrays from all tool files. Import getFleetWorkers from shared/fleet-utils.js instead. Return JSON with integrated:true',
  { label: 'Integrate fleet-utils', model: 'haiku', effort: 'medium' })
]);

const criticalSuccess = criticalFixes.filter(Boolean);
log('Critical fixes: ' + criticalSuccess.length + '/8 completed');

phase('Missing Features');

const missingFeatures = await parallel([
  // Feature 1: Cost tracking
  () => agent('Implement real cost/token tracking in fleet-execute.js with per-model pricing. Calculate cost_usd from input/output tokens. Return JSON with implemented:true',
  { label: 'Add cost tracking', model: 'haiku', effort: 'low' }),

  // Feature 2: Prometheus metrics
  () => agent('Create lib/metrics.js with Prometheus metrics endpoint tracking requests, errors, duration, cost. Export metrics singleton. Return JSON with implemented:true',
  { label: 'Add Prometheus metrics', model: 'sonnet', effort: 'medium' }),

  // Feature 3: SIGTERM handler
  () => agent('Add SIGTERM and SIGINT handlers to index.js for graceful shutdown with 5 second grace period. Return JSON with implemented:true',
  { label: 'Add SIGTERM handler', model: 'haiku', effort: 'low' })
]);

const featuresSuccess = missingFeatures.filter(Boolean);
log('Missing features: ' + featuresSuccess.length + '/3 completed');

phase('Verification');

const verification = await agent('Run comprehensive tests on all fixes: SSH injection prevention, worker validation, real API calls, database writes, retry filtering, circuit breaker, fleet-consensus tool, metrics, SIGTERM handler. Report tests_passed, tests_failed, production_ready boolean, grade A/B/C',
{ label: 'Comprehensive verification', model: 'opus', effort: 'high' });

log('All fixes and verification complete!');

return {
  critical_fixes: criticalSuccess.length,
  missing_features: featuresSuccess.length,
  verification,
  total_agents: 12,
  production_ready: verification?.production_ready || false
};

}
