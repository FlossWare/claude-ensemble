export const meta = {
  name: 'fix-embed-api',
  description: 'Diagnose and fix /documents/embed API endpoint (issue #332)',
  phases: [
    { title: 'Diagnose', detail: 'Parallel investigation of API failure' },
    { title: 'Fix', detail: 'Implement solution' },
    { title: 'Test', detail: 'Verify endpoint works' }
  ]
}

const API_HOST = 'aio-01'
const API_FILE = '/mnt/aio-01/claude-orchestrator/api/application.py'

phase('Diagnose')
log('Investigating /documents/embed endpoint failure in parallel...')

const diagnostics = await parallel([
  // Check API logs
  async () => await agent(
    `On ${API_HOST}, check gunicorn/API error logs for /documents/embed failures:

1. Check journalctl: journalctl -u universal-api -n 200 | grep -i embed
2. Check any error logs in /var/log/
3. Look for Python tracebacks related to embed endpoint

Return: {source: "logs", errors: ["list of errors found"], traceback: "most recent traceback"}`,
    {
      label: 'check-logs',
      phase: 'Diagnose',
      schema: {
        type: 'object',
        properties: {
          source: { type: 'string' },
          errors: { type: 'array', items: { type: 'string' } },
          traceback: { type: 'string' }
        }
      }
    }
  ),

  // Read current implementation
  async () => await agent(
    `Read ${API_FILE} and find the /documents/embed endpoint implementation:

1. Read the file
2. Find the @app.route('/documents/embed') function
3. Extract the complete implementation
4. Identify any obvious bugs (missing imports, wrong API calls, etc.)

Return: {source: "code", implementation: "full code", issues: ["list of issues found"]}`,
    {
      label: 'read-code',
      phase: 'Diagnose',
      schema: {
        type: 'object',
        properties: {
          source: { type: 'string' },
          implementation: { type: 'string' },
          issues: { type: 'array', items: { type: 'string' } }
        }
      }
    }
  ),

  // Test Jina API directly
  async () => await agent(
    `On ${API_HOST}, test Jina AI API directly:

1. Get API key: curl http://localhost:5000/secrets/PERSONAL_JINA_API_KEY
2. Test Jina API:
   curl https://api.jina.ai/v1/embeddings \\
     -H "Authorization: Bearer \$JINA_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{"input": ["test"], "model": "jina-embeddings-v3"}'

3. Check response (should return 1024-dim embeddings)

Return: {source: "jina-test", api_key_exists: true/false, jina_works: true/false, error: "error message if any"}`,
    {
      label: 'test-jina',
      phase: 'Diagnose',
      schema: {
        type: 'object',
        properties: {
          source: { type: 'string' },
          api_key_exists: { type: 'boolean' },
          jina_works: { type: 'boolean' },
          error: { type: 'string' }
        }
      }
    }
  )
])

const logsResult = diagnostics[0]
const codeResult = diagnostics[1]
const jinaResult = diagnostics[2]

log(`Diagnosis complete:`)
log(`  Logs: ${logsResult?.errors?.length || 0} errors found`)
log(`  Code: ${codeResult?.issues?.length || 0} issues found`)
log(`  Jina API: ${jinaResult?.jina_works ? 'WORKS' : 'BROKEN'}`)

phase('Fix')
log('Implementing fix based on diagnosis...')

const fix = await agent(
  `Fix /documents/embed endpoint in ${API_FILE}:

**Diagnosis:**
- Logs: ${JSON.stringify(logsResult?.errors || [])}
- Code issues: ${JSON.stringify(codeResult?.issues || [])}
- Jina API works: ${jinaResult?.jina_works}
- Jina error: ${jinaResult?.error || 'none'}

**Current implementation:**
${codeResult?.implementation || 'Not found'}

**Fix steps:**
1. Read ${API_FILE}
2. Fix the /documents/embed endpoint based on diagnosis
3. Ensure:
   - Correct imports (requests)
   - Correct Jina API endpoint (https://api.jina.ai/v1/embeddings)
   - Correct request format: {"input": ["text"], "model": "jina-embeddings-v3"}
   - Correct response parsing: data[i]['embedding']
   - Proper error handling

4. Save fixed file
5. Restart gunicorn: systemctl restart universal-api

Return: {fixed: true/false, changes_made: "description of changes"}`,
  {
    label: 'fix-endpoint',
    phase: 'Fix',
    schema: {
      type: 'object',
      properties: {
        fixed: { type: 'boolean' },
        changes_made: { type: 'string' }
      }
    }
  }
)

log(`Fix applied: ${fix.changes_made}`)

phase('Test')
log('Testing fixed endpoint with fix → review → fix loop...')

let test, iteration = 0
const MAX_ITERATIONS = 5

while (iteration < MAX_ITERATIONS) {
  iteration++
  log(`Iteration ${iteration}/${MAX_ITERATIONS}: Testing...`)

  test = await agent(
    `Test the /documents/embed endpoint on ${API_HOST}:

1. Wait 5 seconds for gunicorn to restart
2. Test endpoint:
   curl -s http://localhost:5000/documents/embed \\
     -X POST \\
     -H "Content-Type: application/json" \\
     -d '{"chunks": ["test chunk"]}'

3. Verify:
   - Returns 200 status
   - Returns JSON with "embeddings" array
   - Each embedding has 1024 dimensions
   - No errors

4. Test with multiple chunks:
   curl -s http://localhost:5000/documents/embed \\
     -X POST \\
     -H "Content-Type: application/json" \\
     -d '{"chunks": ["chunk 1", "chunk 2", "chunk 3"]}'

Return: {works: true/false, status_code: N, dimensions: N, error: "error if any", full_response: "first 200 chars of response"}`,
    {
      label: `test-iter-${iteration}`,
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          works: { type: 'boolean' },
          status_code: { type: 'number' },
          dimensions: { type: 'number' },
          error: { type: 'string' },
          full_response: { type: 'string' }
        }
      }
    }
  )

  if (test.works) {
    log(`✅ Endpoint working after ${iteration} iteration(s)!`)
    break
  }

  log(`❌ Still broken: ${test.error}`)
  log(`   Response: ${test.full_response}`)

  if (iteration >= MAX_ITERATIONS) {
    log(`Max iterations reached - manual intervention needed`)
    break
  }

  // Review and fix again
  log(`Iteration ${iteration}: Reviewing and fixing...`)

  const reviewAndFix = await agent(
    `Review the /documents/embed endpoint failure and fix it on ${API_HOST}:

**Test result:**
- Works: ${test.works}
- Status: ${test.status_code}
- Error: ${test.error}
- Response: ${test.full_response}

**Steps:**
1. Read ${API_FILE}
2. Find the /documents/embed endpoint
3. Read gunicorn logs: journalctl -u universal-api -n 50 | grep -A10 embed
4. Identify the SPECIFIC error causing the failure
5. Fix the bug
6. Restart gunicorn: systemctl restart universal-api

Return: {fixed: true, issue_found: "description", fix_applied: "description"}`,
    {
      label: `fix-iter-${iteration}`,
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          fixed: { type: 'boolean' },
          issue_found: { type: 'string' },
          fix_applied: { type: 'string' }
        }
      }
    }
  )

  log(`   Issue: ${reviewAndFix.issue_found}`)
  log(`   Fix: ${reviewAndFix.fix_applied}`)
}

return {
  diagnosis: {
    logs_errors: logsResult?.errors?.length || 0,
    code_issues: codeResult?.issues?.length || 0,
    jina_works: jinaResult?.jina_works
  },
  fix_applied: fix.fixed,
  changes: fix.changes_made,
  test_result: {
    works: test.works,
    status: test.status_code,
    dimensions: test.dimensions
  }
}
