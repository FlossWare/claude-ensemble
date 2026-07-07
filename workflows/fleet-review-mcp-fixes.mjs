#!/usr/bin/env node
export const meta = {
  name: 'fleet-review-mcp-fixes',
  description: 'Independent fleet review of all MCP server fixes - adversarial verification',
  phases: [
    { title: 'Code Review', detail: '4 independent reviewers check all fixes' },
    { title: 'Security Audit', detail: '2 agents hunt for vulnerabilities' },
    { title: 'Integration Tests', detail: '4 agents run comprehensive tests' },
    { title: 'Synthesis', detail: 'Arbiter produces final verdict' }
  ]
};

export default async function({ args, phase, log, agent, parallel, workflow }) {

// Get next arbiter from rotation
phase('Get Arbiter');
const arbiterChoice = await workflow('get-next-arbiter');
log(`Arbiter for this run: ${arbiterChoice.arbiter} (previous: ${arbiterChoice.previous || 'none'})`);

phase('Code Review');

log('4 independent reviewers checking all 10 fixes...');

const codeReviews = await parallel([
  // Reviewer 1: Security focus
  () => agent(`ADVERSARIAL SECURITY REVIEW - Try to break these fixes:

Review these files for security vulnerabilities:
1. mcp-servers/fleet-orchestrator/tools/fleet-execute.js
2. mcp-servers/fleet-orchestrator/lib/retry.js
3. mcp-servers/fleet-orchestrator/lib/circuit-breaker.js

ATTACK VECTORS TO TEST:
1. SSH Injection - Is shell-escape properly used? Can you bypass it?
2. Worker validation - Can you inject invalid worker names?
3. Input validation - Are timeouts/models validated?
4. Memory exhaustion - Can you trigger the memory leak?
5. Race conditions - Can concurrent requests corrupt state?

Read the actual code. Try to find exploits.

Return JSON:
{
  "vulnerabilities_found": [],
  "fixes_verified": [],
  "grade": "A/B/C/F",
  "exploitable": true/false
}`,
  { label: 'Security audit', model: 'opus', effort: 'high' }),

  // Reviewer 2: Correctness focus
  () => agent(`CODE CORRECTNESS REVIEW - Verify fixes actually work:

Check these fixes are correctly implemented:
1. SSH injection fix - Is shell-escape imported and used correctly?
2. Worker validation - Does it check against WORKERS array?
3. Memory leak fix - Does CircuitBreaker have cleanup interval?
4. Real API calls - Is executeOnModel() actually called (not echo)?
5. Database integration - Is workflow-storage-adapter imported and called?
6. Retry filtering - Does it skip 401/403/400?
7. Race condition - Are counters atomic?
8. Jitter - Is Math.random() used in backoff?

Read the files. Check line-by-line.

Return JSON:
{
  "fixes_correct": [],
  "fixes_incomplete": [],
  "fixes_broken": [],
  "grade": "A/B/C/F"
}`,
  { label: 'Correctness review', model: 'sonnet', effort: 'high' }),

  // Reviewer 3: Integration focus
  () => agent(`INTEGRATION REVIEW - Check components work together:

Verify these integrations:
1. fleet-execute.js imports from fleet-utils.js, credential-manager.cjs, workflow-storage-adapter.cjs
2. retry.js integrates with circuit-breaker.js
3. fleet-consensus.js exists and is registered in index.js TOOLS array
4. Metrics are tracked (lib/metrics.js exists)
5. SIGTERM handler is in index.js
6. Cost tracking uses real pricing

Check import paths are correct. Verify no missing dependencies.

Return JSON:
{
  "integrations_working": [],
  "integrations_broken": [],
  "missing_files": [],
  "grade": "A/B/C/F"
}`,
  { label: 'Integration review', model: 'haiku', effort: 'medium' }),

  // Reviewer 4: Performance focus
  () => agent(`PERFORMANCE REVIEW - Check for bottlenecks:

Review for performance issues:
1. CircuitBreaker cleanup interval - Does it run too often?
2. Retry jitter - Is the range appropriate?
3. Database writes - Are they async and non-blocking?
4. Parallel SSH - Any resource exhaustion risks?
5. Memory leaks - Are Maps bounded?

Check for inefficiencies, blocking operations, resource leaks.

Return JSON:
{
  "performance_issues": [],
  "optimizations_found": [],
  "grade": "A/B/C/F"
}`,
  { label: 'Performance review', model: 'opus', effort: 'medium' })
]);

const reviewsSuccess = codeReviews.filter(Boolean);
log('Code reviews: ' + reviewsSuccess.length + '/4 completed');

phase('Security Audit');

const securityAudits = await parallel([
  // Audit 1: Injection attacks
  () => agent(`INJECTION ATTACK TESTING:

Try to exploit these injection vectors:

1. SSH Command Injection:
   - Read mcp-servers/fleet-orchestrator/tools/fleet-execute.js
   - Find the shell-escape usage
   - Try payloads: backticks, $(), semicolons, newlines, unicode escapes
   - Can ANY payload execute commands?

2. Worker Hostname Injection:
   - Check worker validation code
   - Try: evil-host, localhost, 127.0.0.1, -o ProxyCommand=evil
   - Does validation catch all invalid workers?

Test both. Report if EXPLOITABLE.

Return JSON:
{
  "ssh_injection_blocked": true/false,
  "worker_injection_blocked": true/false,
  "exploit_payloads_tested": [],
  "exploitable": true/false
}`,
  { label: 'Injection testing', model: 'opus', effort: 'high' }),

  // Audit 2: DoS and resource exhaustion
  () => agent(`DOS & RESOURCE EXHAUSTION TESTING:

Check for DoS vectors:

1. Memory exhaustion:
   - CircuitBreaker cleanup - does it prevent unbounded growth?
   - Can you trigger memory leak with unique worker names?

2. Retry bombs:
   - What happens with timeout_ms=999999999?
   - What happens with maxRetries=1000?
   - Is there a total timeout?

3. Thundering herd:
   - Is jitter properly implemented?
   - Can synchronized retries DoS the fleet?

Return JSON:
{
  "dos_vectors_found": [],
  "memory_leaks_possible": true/false,
  "retry_bombs_possible": true/false,
  "grade": "A/B/C/F"
}`,
  { label: 'DoS testing', model: 'sonnet', effort: 'high' })
]);

const auditsSuccess = securityAudits.filter(Boolean);
log('Security audits: ' + auditsSuccess.length + '/2 completed');

phase('Integration Tests');

const integrationTests = await parallel([
  // Test 1: MCP protocol
  () => agent(`TEST: MCP Protocol Compliance

Run actual MCP server tests:

1. Start MCP server: node mcp-servers/fleet-orchestrator/index.js
2. Send tools/list request
3. Send fleet-execute request
4. Send fleet-status request
5. Send fleet-consensus request (if exists)
6. Verify all responses are valid JSON

Use stdin/stdout to communicate. Check protocol compliance.

Return JSON:
{
  "tools_list_works": true/false,
  "fleet_execute_works": true/false,
  "fleet_status_works": true/false,
  "fleet_consensus_works": true/false,
  "all_passing": true/false
}`,
  { label: 'MCP protocol tests', model: 'sonnet', effort: 'high' }),

  // Test 2: Error handling
  () => agent(`TEST: Error Handling

Test retry + circuit breaker:

1. Simulate SSH timeout - does it retry 3x?
2. Simulate 5 failures - does circuit open?
3. Simulate 401 error - does it NOT retry?
4. Simulate worker offline - does it degrade gracefully?

Actually run the code with injected errors.

Return JSON:
{
  "retry_works": true/false,
  "circuit_breaker_works": true/false,
  "retry_filtering_works": true/false,
  "graceful_degradation_works": true/false,
  "all_passing": true/false
}`,
  { label: 'Error handling tests', model: 'haiku', effort: 'high' }),

  // Test 3: Database integration
  () => agent(`TEST: Database Integration

Verify PostgreSQL writes:

1. Run fleet-execute task
2. Query workflow.worker_results for execution_host
3. Check that new row was inserted
4. Verify execution_host matches worker used

Connect to PostgreSQL and check actual data.

Return JSON:
{
  "database_writes_work": true/false,
  "execution_host_tracked": true/false,
  "rows_found": 0,
  "all_passing": true/false
}`,
  { label: 'Database tests', model: 'opus', effort: 'medium' }),

  // Test 4: End-to-end
  () => agent(`TEST: End-to-End Workflow

Run complete workflow:

1. Submit task via fleet-execute
2. Task routes to worker
3. Real API call executes
4. Result written to database
5. Metrics tracked
6. Cost calculated

Trace the full path. Verify each step.

Return JSON:
{
  "task_routed": true/false,
  "api_called": true/false,
  "database_written": true/false,
  "cost_tracked": true/false,
  "all_passing": true/false
}`,
  { label: 'End-to-end tests', model: 'sonnet', effort: 'high' })
]);

const testsSuccess = integrationTests.filter(Boolean);
log('Integration tests: ' + testsSuccess.length + '/4 completed');

phase('Synthesis');

const arbiter = await agent(`ARBITER: Synthesize all reviews and produce final verdict

You have reviews from:
- 4 code reviewers (security, correctness, integration, performance)
- 2 security auditors (injection, DoS)
- 4 test runners (protocol, errors, database, e2e)

ANALYZE ALL RESULTS and produce final assessment:

1. Are all 10 critical fixes actually implemented?
2. Are there any remaining security vulnerabilities?
3. Do all tests pass?
4. Is this production-ready?

Return JSON:
{
  "fixes_implemented": 10,
  "vulnerabilities_remaining": [],
  "tests_passed": 0,
  "tests_failed": 0,
  "production_ready": true/false,
  "grade": "A/B/C/F",
  "blocking_issues": [],
  "recommendations": []
}`,
{ label: 'Final arbiter verdict', model: arbiterChoice.arbiter, effort: 'high' });

// Update arbiter state for rotation tracking
phase('Update Arbiter State');
await workflow('update-arbiter-state', { arbiter: arbiterChoice.arbiter, workflow_name: 'fleet-review-mcp-fixes' });

log('Fleet review complete!');

return {
  code_reviews: reviewsSuccess.length,
  security_audits: auditsSuccess.length,
  integration_tests: testsSuccess.length,
  arbiter_verdict: arbiter,
  total_agents: 11,
  all_reviews: {
    code: codeReviews.filter(Boolean),
    security: securityAudits.filter(Boolean),
    tests: integrationTests.filter(Boolean),
    arbiter
  }
};

}
