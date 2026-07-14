#!/usr/bin/env node
export const meta = {
  name: 'review-fix-verify-loop',
  description: 'Fleet reviews all changes, meta-reviews findings, fixes validated issues, verifies',
  phases: [
    { title: 'Deep Review', detail: '8 agents review all recent changes for issues' },
    { title: 'Meta-Review', detail: 'Independent panel challenges review findings before fixes' },
    { title: 'Fix Broken', detail: 'Fix all validated issues in parallel' },
    { title: 'Verify Fixes', detail: 'Test that fixes work' },
    { title: 'Pending Tasks', detail: 'Complete tasks #106-111' }
  ]
};

export default async function({ args, phase, log, agent, parallel }) {

phase('Deep Review');

log('8 agents reviewing all changes for broken items...');

const reviews = await parallel([
  // Review 1: Import/Module issues
  () => agent(`Review for import/module errors:

Check these files for broken imports:
- workflows/deep-research.mjs
- All shared/*.js files
- All mcp-servers/**/*.js files

Test each file:
1. node -c <file> (syntax check)
2. Try importing: node -e "import {...} from './file.js'"
3. Check for missing dependencies

Return JSON:
{
  "broken_imports": [],
  "missing_dependencies": [],
  "syntax_errors": []
}`,
  { label: 'Import/module review', model: 'opus', effort: 'high' }),

  // Review 2: Database schema mismatches
  () => agent(`Review database schema issues:

Check postgres-adapter.js table names vs actual schema:
1. Read shared/workflow-storage-adapter.cjs
2. Check table references
3. Query PostgreSQL: psql -h aio-01 -U sfloess -d learning -c "\\dt workflow.*"
4. Compare table names used in code vs actual schema

Return JSON:
{
  "table_mismatches": [],
  "missing_tables": [],
  "column_mismatches": []
}`,
  { label: 'Database schema review', model: 'sonnet', effort: 'medium' }),

  // Review 3: Test failures
  () => agent(`Review test failures:

Run existing tests:
1. Find all test files: find . -name "*.test.js" -o -name "*.test.mjs"
2. Run tests: node --test test/**/*.test.js
3. Identify failures

Return JSON:
{
  "tests_run": 0,
  "tests_passed": 0,
  "tests_failed": 0,
  "failures": []
}`,
  { label: 'Test review', model: 'haiku', effort: 'medium' }),

  // Review 4: Workflow execution
  () => agent(`Review workflow execution issues:

Test deep-research.mjs:
1. Check if it runs: node --check workflows/deep-research.mjs
2. Test with minimal args
3. Check for runtime errors

Return JSON:
{
  "workflow_executable": true/false,
  "runtime_errors": [],
  "import_errors": []
}`,
  { label: 'Workflow review', model: 'opus', effort: 'high' }),

  // Review 5: API provider configuration
  () => agent(`Review API provider configuration:

Check shared/fleet-utils.js:
1. Verify all 12 providers configured correctly
2. Test model mapping: mapModelToProvider()
3. Check for syntax errors in PROVIDER_CONFIG

Return JSON:
{
  "providers_configured": 0,
  "providers_broken": [],
  "mapping_errors": []
}`,
  { label: 'API config review', model: 'sonnet', effort: 'medium' }),

  // Review 6: Credential distribution
  () => agent(`Verify credentials on workers:

For each worker, check:
1. ~/.bashrc has all API keys
2. ~/.claude/credentials.json exists and valid
3. Can source .bashrc without errors

Return JSON:
{
  "workers_configured": [],
  "workers_broken": [],
  "missing_keys": []
}`,
  { label: 'Credentials review', model: 'haiku', effort: 'medium' }),

  // Review 7: Fleet execution
  () => agent(`Test actual fleet execution:

Run real distributed test:
1. Use executeOnWorker on 3 different workers
2. Verify each executes successfully
3. Check database tracking

Return JSON:
{
  "workers_tested": [],
  "workers_working": [],
  "workers_broken": [],
  "errors": []
}`,
  { label: 'Fleet execution test', model: 'opus', effort: 'high' }),

  // Review 8: Documentation completeness
  () => agent(`Review documentation:

Check if docs are complete:
1. MCP_FLEET_ORCHESTRATOR_COMPLETE.md - up to date?
2. FLEET_REVIEW_RESULTS.md - accurate?
3. README files - exist and accurate?

Return JSON:
{
  "docs_complete": true/false,
  "outdated_docs": [],
  "missing_docs": []
}`,
  { label: 'Documentation review', model: 'haiku', effort: 'low' })
]);

const reviewResults = reviews.filter(Boolean);
log('Reviews complete: ' + reviewResults.length + '/8');

// Collect all issues
const allIssues = reviewResults.flatMap(r => [
  ...(r.broken_imports || []),
  ...(r.syntax_errors || []),
  ...(r.table_mismatches || []),
  ...(r.failures || []),
  ...(r.runtime_errors || []),
  ...(r.providers_broken || []),
  ...(r.workers_broken || []),
  ...(r.errors || [])
]).filter(Boolean);

log('Total issues found: ' + allIssues.length);

if (allIssues.length === 0) {
  log('No broken items found! Moving to pending tasks...');
} else {

  // Meta-Review: independent panel validates findings before fixing
  phase('Meta-Review');

  // Meta-review panel: strong models with ZERO overlap to the review models
  // Uses fleet API for non-Claude models to get true independence
  const META_PANEL = [
    { name: 'fable', type: 'claude' },
    { name: 'nousresearch/hermes-3-llama-3.1-405b:free', type: 'fleet' },
    { name: 'nvidia/nemotron-3-ultra-550b-a55b:free', type: 'fleet' },
    { name: 'qwen/qwen3-next-80b-a3b-instruct:free', type: 'fleet' },
  ];
  log('Meta-reviewing ' + allIssues.length + ' findings with independent panel (' + META_PANEL.map(m => m.name).join(', ') + ')...');
  log('ZERO overlap with review panel — prevents self-confirmation bias');

  const metaVerdictSchema = {
    type: 'object',
    properties: {
      verdict: { type: 'string', enum: ['confirmed', 'likely_valid', 'questionable', 'false_positive'] },
      reasoning: { type: 'string' }
    },
    required: ['verdict', 'reasoning']
  };

  const metaResults = await parallel(allIssues.map((issue, idx) =>
    () => parallel(META_PANEL.map(m => {
      const metaPrompt = 'You are an ADVERSARIAL reviewer. Try to REFUTE this finding. Default to skepticism.\n\nFinding: ' + JSON.stringify(issue) + '\n\n1. Read the actual code mentioned\n2. Is this issue REAL or a false positive?\n3. Could the framework handle this automatically?\n\nReturn verdict: confirmed, likely_valid, questionable, or false_positive.';

      if (m.type === 'claude') {
        return () => agent(metaPrompt,
          { label: m.name + ' meta-review #' + idx, model: m.name, phase: 'Meta-Review', schema: metaVerdictSchema });
      } else {
        return () => agent('You are a meta-review proxy. Call model "' + m.name + '" to adversarially challenge a finding.\n\n' +
          'Get the API key:\ncurl -s http://aio-01:5000/secrets/OPENROUTER_API_KEY | python3 -c "import json,sys; print(json.load(sys.stdin).get(\'value\',\'\'))" > /tmp/.api_key_tmp 2>/dev/null\n\n' +
          'Call the model:\ncurl -s https://openrouter.ai/api/v1/chat/completions -H "Authorization: Bearer $(cat /tmp/.api_key_tmp)" -H "Content-Type: application/json" ' +
          '-d \'{"model":"' + m.name + '","messages":[{"role":"user","content":' + JSON.stringify(metaPrompt + '\\n\\nReturn JSON: {"verdict":"confirmed|likely_valid|questionable|false_positive","reasoning":"string"}') + '}],"max_tokens":2048}\'\n\n' +
          'Parse the response and return the verdict. Clean up: rm -f /tmp/.api_key_tmp',
          { label: m.name.split('/').pop() + ' meta-review #' + idx, phase: 'Meta-Review', schema: metaVerdictSchema });
      }
    })).then(votes => {
      const valid = (votes || []).filter(Boolean);
      const confirmed = valid.filter(v => v.verdict === 'confirmed' || v.verdict === 'likely_valid').length;
      const rejected = valid.filter(v => v.verdict === 'false_positive' || v.verdict === 'questionable').length;
      return { issue, confirmed: confirmed > rejected, votes: valid.length, confirmedCount: confirmed, rejectedCount: rejected };
    })
  ));

  const validatedIssues = metaResults.filter(Boolean).filter(r => r.confirmed).map(r => r.issue);
  const rejectedIssues = metaResults.filter(Boolean).filter(r => !r.confirmed);

  log('Meta-review complete: ' + validatedIssues.length + ' confirmed, ' + rejectedIssues.length + ' rejected as false positives');
  if (rejectedIssues.length > 0) {
    rejectedIssues.forEach(r => {
      log('  Rejected: ' + JSON.stringify(r.issue).slice(0, 80) + ' (' + r.rejectedCount + '/' + r.votes + ' reviewers rejected)');
    });
  }

  if (validatedIssues.length === 0) {
    log('All findings were false positives! Moving to pending tasks...');
  } else {

  phase('Fix Broken');

  log('Fixing ' + validatedIssues.length + ' validated issues in parallel...');

  const fixes = await parallel(validatedIssues.slice(0, 8).map(issue =>
    () => agent('Fix this issue: ' + JSON.stringify(issue) + '\\n\\nRead the relevant files, identify the problem, and fix it. Return JSON with fixed:true when done.',
    { label: 'Fix: ' + issue.file || issue.description, model: 'opus', effort: 'high' })
  ));

  const fixedCount = fixes.filter(Boolean).filter(f => f.fixed).length;
  log('Fixed: ' + fixedCount + '/' + Math.min(allIssues.length, 8));

  phase('Verify Fixes');

  const verify = await agent('Verify all fixes work:\\n\\n1. Re-run syntax checks\\n2. Re-run tests\\n3. Test fleet execution\\n\\nReturn JSON with all_working:true if everything passes',
  { label: 'Verify all fixes', model: 'sonnet', effort: 'high' });

  if (!verify?.all_working) {
    log('Some fixes failed verification. Issues remaining: ' + (verify?.issues_remaining || 'unknown'));
  }
  } // end if (validatedIssues.length > 0)
} // end if (allIssues.length > 0)

phase('Pending Tasks');

log('Completing pending tasks #106-111...');

const pendingTasks = await parallel([
  // Task 106: Documentation
  () => agent('Create docs/fleet-routing-consolidation.md documenting how all fleet routing works. Include PROVIDER_CONFIG, mapModelToProvider, model selection logic. Return JSON with created:true',
  { label: 'Task #106: Routing docs', model: 'haiku', effort: 'medium' }),

  // Task 107: Verify implementation
  () => agent('Verify entire implementation works end-to-end:\\n1. MCP server responds\\n2. Fleet distributes tasks\\n3. Workers execute\\n4. Database tracks\\n5. All 6 APIs work\\n\\nReturn JSON with verified:true',
  { label: 'Task #107: Verify all', model: 'opus', effort: 'high' }),

  // Task 108: Fix deep-research.mjs
  () => agent('Fix deep-research.mjs import paths and API usage:\\n1. Check imports are correct\\n2. Update API calls to use new provider config\\n3. Test execution\\n\\nReturn JSON with fixed:true',
  { label: 'Task #108: Fix deep-research', model: 'sonnet', effort: 'medium' }),

  // Task 109: Fix table mismatches
  () => agent('Fix table name mismatches in postgres-adapter.js:\\n1. Check actual schema: psql -h aio-01\\n2. Update code to match\\n3. Test queries work\\n\\nReturn JSON with fixed:true',
  { label: 'Task #109: Fix schema', model: 'opus', effort: 'medium' }),

  // Task 110: Fix test assertions
  () => agent('Fix test assertions for schema names:\\n1. Update test files\\n2. Match actual schema\\n3. Run tests\\n\\nReturn JSON with fixed:true',
  { label: 'Task #110: Fix tests', model: 'haiku', effort: 'low' }),

  // Task 111: Run all tests
  () => agent('Run all tests to verify fixes:\\n1. Find all test files\\n2. Run: node --test\\n3. Report results\\n\\nReturn JSON with all_passing:true',
  { label: 'Task #111: Run tests', model: 'sonnet', effort: 'medium' })
]);

const tasksComplete = pendingTasks.filter(Boolean).filter(t => t.fixed || t.created || t.verified || t.all_passing).length;
log('Pending tasks complete: ' + tasksComplete + '/6');

const validatedCount = typeof validatedIssues !== 'undefined' ? validatedIssues.length : 0;
const rejectedCount = typeof rejectedIssues !== 'undefined' ? rejectedIssues.length : 0;

return {
  reviews: reviewResults.length,
  issues_found: allIssues.length,
  meta_review: {
    validated: validatedCount,
    rejected_as_false_positives: rejectedCount
  },
  issues_fixed: validatedCount > 0 && typeof fixedCount !== 'undefined' ? fixedCount : 0,
  pending_tasks_complete: tasksComplete,
  all_working: allIssues.length === 0 || (typeof verify !== 'undefined' && verify?.all_working && tasksComplete === 6)
};

}
