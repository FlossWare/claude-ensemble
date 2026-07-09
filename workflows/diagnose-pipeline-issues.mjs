export const meta = {
  name: 'diagnose-pipeline-issues',
  description: 'Diagnose chunk failures, graph errors, and storage issues',
  phases: [
    { title: 'Diagnose', detail: 'Parallel investigation of 3 major issues' },
    { title: 'Recommendations', detail: 'Summarize findings and next steps' }
  ]
}

const API_HOST = 'aio-01'
const API_PORT = '5000'

phase('Diagnose')
log('Investigating 3 major issues in parallel...')

const diagnostics = await parallel([
  // Issue 1: 24,187 chunk failures
  async () => await agent(
    `Investigate chunk failures on ${API_HOST}:

**Problem:** 24,187 chunk failures in queue.chunk

**Steps:**
1. Query PostgreSQL for sample failed chunks:
   SELECT id, file_path, error_message, created_at
   FROM queue.chunk
   WHERE status='failed'
   ORDER BY created_at DESC
   LIMIT 20;

2. Check API logs for /documents/chunk errors:
   journalctl -u universal-api -n 500 | grep -A5 "POST /documents/chunk"

3. Test the endpoint manually:
   curl -X POST http://localhost:${API_PORT}/documents/chunk \\
     -H "Content-Type: application/json" \\
     -d '{"file_path": "/mnt/aio-01/claude-orchestrator/scraped-data/raw/stackoverflow/test.json"}'

4. Identify root cause:
   - File not found?
   - JSON parsing errors?
   - pypdf issues?
   - API crashes?

Return: {
  issue: "chunk_failures",
  sample_errors: ["list of error messages"],
  root_cause: "description",
  affected_count: 24187,
  fix_needed: "description of fix"
}`,
    {
      label: 'diagnose-chunks',
      phase: 'Diagnose',
      schema: {
        type: 'object',
        properties: {
          issue: { type: 'string' },
          sample_errors: { type: 'array', items: { type: 'string' } },
          root_cause: { type: 'string' },
          affected_count: { type: 'number' },
          fix_needed: { type: 'string' }
        }
      }
    }
  ),

  // Issue 2: 30,820 graph errors
  async () => await agent(
    `Investigate graph errors on ${API_HOST}:

**Problem:** 30,820 graph errors in queue.graph

**Steps:**
1. Query PostgreSQL for sample graph errors:
   SELECT id, file_path, error_message, created_at
   FROM queue.graph
   WHERE status='error'
   ORDER BY created_at DESC
   LIMIT 20;

2. Check if /documents/graph endpoint exists and works:
   curl -X POST http://localhost:${API_PORT}/documents/graph \\
     -H "Content-Type: application/json" \\
     -d '{"text": "test text", "file_path": "/test.json"}'

3. Check API logs:
   journalctl -u universal-api -n 500 | grep -A5 "POST /documents/graph"

4. Identify root cause:
   - Endpoint missing/broken?
   - NER model issues?
   - Timeout errors?
   - Invalid input format?

Return: {
  issue: "graph_errors",
  sample_errors: ["list of error messages"],
  root_cause: "description",
  affected_count: 30820,
  fix_needed: "description of fix"
}`,
    {
      label: 'diagnose-graph',
      phase: 'Diagnose',
      schema: {
        type: 'object',
        properties: {
          issue: { type: 'string' },
          sample_errors: { type: 'array', items: { type: 'string' } },
          root_cause: { type: 'string' },
          affected_count: { type: 'number' },
          fix_needed: { type: 'string' }
        }
      }
    }
  ),

  // Issue 3: Storage mismatch (expected 6,401, only 2,034 stored)
  async () => await agent(
    `Investigate storage discrepancy on ${API_HOST}:

**Problem:** Expected 6,401 documents stored, but only 2,034 in knowledge.scraped_data

**Steps:**
1. Check queue.store status:
   SELECT status, COUNT(*)
   FROM queue.store
   GROUP BY status;

2. Check if items in queue.store have ALL required data:
   SELECT COUNT(*) as incomplete
   FROM queue.store
   WHERE chunk_result IS NULL
      OR embed_result IS NULL
      OR graph_result IS NULL;

3. Check knowledge.scraped_data table:
   SELECT COUNT(*) FROM knowledge.scraped_data;
   SELECT * FROM knowledge.scraped_data LIMIT 5;

4. Identify root cause:
   - Store workers not processing?
   - Missing required fields?
   - Database constraints failing?
   - Items stuck in queue.store?

Return: {
  issue: "storage_mismatch",
  store_queue_status: {pending: N, completed: N},
  knowledge_count: 2034,
  root_cause: "description",
  fix_needed: "description of fix"
}`,
    {
      label: 'diagnose-storage',
      phase: 'Diagnose',
      schema: {
        type: 'object',
        properties: {
          issue: { type: 'string' },
          store_queue_status: {
            type: 'object',
            properties: {
              pending: { type: 'number' },
              completed: { type: 'number' }
            }
          },
          knowledge_count: { type: 'number' },
          root_cause: { type: 'string' },
          fix_needed: { type: 'string' }
        }
      }
    }
  )
])

const chunkIssue = diagnostics[0]
const graphIssue = diagnostics[1]
const storageIssue = diagnostics[2]

phase('Recommendations')
log('Synthesizing findings and recommendations...')

const synthesis = await agent(
  `Synthesize diagnostic findings and recommend fixes:

**Chunk Failures (24,187):**
Root cause: ${chunkIssue.root_cause}
Fix needed: ${chunkIssue.fix_needed}
Sample errors: ${JSON.stringify(chunkIssue.sample_errors?.slice(0, 3))}

**Graph Errors (30,820):**
Root cause: ${graphIssue.root_cause}
Fix needed: ${graphIssue.fix_needed}
Sample errors: ${JSON.stringify(graphIssue.sample_errors?.slice(0, 3))}

**Storage Mismatch (6,401 expected, 2,034 actual):**
Root cause: ${storageIssue.root_cause}
Fix needed: ${storageIssue.fix_needed}

**Provide:**
1. Priority ranking (which to fix first)
2. Estimated impact of each fix
3. Whether we should:
   - Fix all 3 issues now
   - Fix critical ones first, continue processing
   - Stop processing until all fixed

Return: {
  priority_order: ["issue1", "issue2", "issue3"],
  critical_blockers: ["list of must-fix issues"],
  can_continue_processing: true/false,
  recommended_action: "description"
}`,
  {
    label: 'synthesize',
    phase: 'Recommendations',
    schema: {
      type: 'object',
      properties: {
        priority_order: { type: 'array', items: { type: 'string' } },
        critical_blockers: { type: 'array', items: { type: 'string' } },
        can_continue_processing: { type: 'boolean' },
        recommended_action: { type: 'string' }
      }
    }
  }
)

log('')
log('=== DIAGNOSTIC SUMMARY ===')
log(`Chunk failures: ${chunkIssue.root_cause}`)
log(`Graph errors: ${graphIssue.root_cause}`)
log(`Storage issue: ${storageIssue.root_cause}`)
log('')
log(`Priority: ${synthesis.priority_order.join(' → ')}`)
log(`Critical blockers: ${synthesis.critical_blockers.join(', ')}`)
log(`Can continue: ${synthesis.can_continue_processing ? 'YES' : 'NO'}`)
log(`Action: ${synthesis.recommended_action}`)

return {
  chunk_issue: chunkIssue,
  graph_issue: graphIssue,
  storage_issue: storageIssue,
  synthesis: synthesis
}
