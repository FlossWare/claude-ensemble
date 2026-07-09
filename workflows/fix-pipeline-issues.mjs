export const meta = {
  name: 'fix-pipeline-issues',
  description: 'Fix chunk failures and graph errors in parallel with iterative review',
  phases: [
    { title: 'Fix', detail: 'Parallel fixes for chunk and graph issues' },
    { title: 'Verify', detail: 'Test fixes and iterate if needed' }
  ]
}

const API_HOST = 'aio-01'
const API_FILE = '/mnt/aio-01/claude-orchestrator/api/application.py'
const MAX_ITERATIONS = 3

phase('Fix')
log('Fixing chunk and graph issues in parallel...')

const fixes = await parallel([
  // Fix 1: Chunk failures
  async () => await agent(
    'Fix chunk failures on ' + API_HOST + ':\n\n' +
    '**Root Cause:** NULL file_path crashes at line 595: Path(file_path)\n\n' +
    '**Steps:**\n' +
    '1. Read ' + API_FILE + '\n' +
    '2. Find /documents/chunk endpoint (around line 595)\n' +
    '3. Add NULL validation BEFORE Path(file_path) call:\n' +
    '   if not file_path:\n' +
    '       return jsonify({"error": "Missing file_path"}), 400\n' +
    '   file_path = Path(file_path)\n' +
    '4. Save file\n' +
    '5. Restart API: systemctl restart universal-api\n' +
    '6. Clean up orphaned queue entries:\n' +
    '   DELETE FROM queue.chunk WHERE document_id NOT IN (SELECT id FROM documents.documents);\n\n' +
    'Return: {issue: "chunk_failures", fixed: true, changes: "...", orphaned_deleted: N}',
    {
      label: 'fix-chunks',
      phase: 'Fix',
      schema: {
        type: 'object',
        properties: {
          issue: { type: 'string' },
          fixed: { type: 'boolean' },
          changes: { type: 'string' },
          orphaned_deleted: { type: 'number' }
        }
      }
    }
  ),

  // Fix 2: Graph errors
  async () => await agent(
    'Fix graph errors on ' + API_HOST + ':\n\n' +
    '**Root Causes:**\n' +
    '1. Schema mismatches (chunk_text, document_id columns missing)\n' +
    '2. UUID vs INTEGER mismatch\n' +
    '3. /documents/graph endpoint broken\n' +
    '4. Orphaned queue entries\n\n' +
    '**Steps:**\n' +
    '1. Check queue.graph and queue.store schema\n' +
    '2. Add missing columns if needed:\n' +
    '   ALTER TABLE queue.graph ADD COLUMN IF NOT EXISTS chunk_text TEXT;\n' +
    '   ALTER TABLE queue.store ADD COLUMN IF NOT EXISTS document_id INTEGER;\n' +
    '3. Read ' + API_FILE + ' and find /documents/graph endpoint\n' +
    '4. Fix endpoint to handle missing chunks parameter\n' +
    '5. Restart API: systemctl restart universal-api\n' +
    '6. Clean up orphaned entries\n\n' +
    'Return: {issue: "graph_errors", fixed: true, schema_changes: [...], api_changes: "...", orphaned_deleted: N}',
    {
      label: 'fix-graph',
      phase: 'Fix',
      schema: {
        type: 'object',
        properties: {
          issue: { type: 'string' },
          fixed: { type: 'boolean' },
          schema_changes: { type: 'array', items: { type: 'string' } },
          api_changes: { type: 'string' },
          orphaned_deleted: { type: 'number' }
        }
      }
    }
  )
])

const chunkFix = fixes[0]
const graphFix = fixes[1]

log('Chunk fix: ' + chunkFix.changes)
log('Graph fix: ' + graphFix.api_changes)

phase('Verify')
log('Testing fixes with iterative review (max ' + MAX_ITERATIONS + ' iterations)...')

let iteration = 0
let chunkWorks = false
let graphWorks = false

while (iteration < MAX_ITERATIONS && (!chunkWorks || !graphWorks)) {
  iteration++
  log('Iteration ' + iteration + '/' + MAX_ITERATIONS + ': Testing...')

  const tests = await parallel([
    // Test chunk
    async () => !chunkWorks ? await agent(
      'Test /documents/chunk on ' + API_HOST + ':\n' +
      '1. Test valid: curl -X POST http://localhost:5000/documents/chunk -H "Content-Type: application/json" -d \'{"file_path": "/mnt/aio-01/claude-orchestrator/scraped-data/raw/stackoverflow/test.json"}\'\n' +
      '2. Test NULL (should return 400): curl -X POST http://localhost:5000/documents/chunk -H "Content-Type: application/json" -d \'{}\'\n' +
      '3. Check logs: journalctl -u universal-api -n 50 | grep chunk\n' +
      'Return: {works: bool, status_code: N, handles_null: bool, error: "..."}',
      {
        label: 'test-chunk-' + iteration,
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            works: { type: 'boolean' },
            status_code: { type: 'number' },
            handles_null: { type: 'boolean' },
            error: { type: 'string' }
          }
        }
      }
    ) : null,

    // Test graph
    async () => !graphWorks ? await agent(
      'Test /documents/graph on ' + API_HOST + ':\n' +
      '1. Test valid: curl -X POST http://localhost:5000/documents/graph -H "Content-Type: application/json" -d \'{"text": "Red Hat Enterprise Linux 9", "file_path": "/test.json"}\'\n' +
      '2. Check logs: journalctl -u universal-api -n 50 | grep graph\n' +
      'Return: {works: bool, status_code: N, entities_extracted: N, error: "..."}',
      {
        label: 'test-graph-' + iteration,
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            works: { type: 'boolean' },
            status_code: { type: 'number' },
            entities_extracted: { type: 'number' },
            error: { type: 'string' }
          }
        }
      }
    ) : null
  ])

  const chunkTest = tests[0]
  const graphTest = tests[1]

  if (chunkTest) {
    chunkWorks = chunkTest.works && chunkTest.handles_null
    if (!chunkWorks) {
      log('Chunk still broken: ' + chunkTest.error)

      const chunkRefix = await agent(
        'Fix remaining chunk issues on ' + API_HOST + ':\n' +
        'Test showed: works=' + chunkTest.works + ', handles_null=' + chunkTest.handles_null + '\n' +
        'Error: ' + chunkTest.error + '\n' +
        '1. Read ' + API_FILE + ' /documents/chunk\n' +
        '2. Review logs\n' +
        '3. Fix the specific issue\n' +
        '4. Restart API\n' +
        'Return: {fixed: true, issue_found: "...", fix_applied: "..."}',
        {
          label: 'refix-chunk-' + iteration,
          phase: 'Verify',
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
      log('  Chunk refix: ' + chunkRefix.fix_applied)
    } else {
      log('✅ Chunk endpoint working!')
    }
  }

  if (graphTest) {
    graphWorks = graphTest.works
    if (!graphWorks) {
      log('Graph still broken: ' + graphTest.error)

      const graphRefix = await agent(
        'Fix remaining graph issues on ' + API_HOST + ':\n' +
        'Test showed: works=' + graphTest.works + ', status=' + graphTest.status_code + '\n' +
        'Error: ' + graphTest.error + '\n' +
        '1. Read ' + API_FILE + ' /documents/graph\n' +
        '2. Review logs\n' +
        '3. Fix the specific issue\n' +
        '4. Restart API\n' +
        'Return: {fixed: true, issue_found: "...", fix_applied: "..."}',
        {
          label: 'refix-graph-' + iteration,
          phase: 'Verify',
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
      log('  Graph refix: ' + graphRefix.fix_applied)
    } else {
      log('✅ Graph endpoint working!')
    }
  }
}

log('')
log('=== FIX SUMMARY ===')
log('Iterations: ' + iteration + '/' + MAX_ITERATIONS)
log('Chunk endpoint: ' + (chunkWorks ? '✅ WORKING' : '❌ STILL BROKEN'))
log('Graph endpoint: ' + (graphWorks ? '✅ WORKING' : '❌ STILL BROKEN'))
log('Orphaned data cleaned: ' + (chunkFix.orphaned_deleted + graphFix.orphaned_deleted) + ' entries')

return {
  chunk_fix: chunkFix,
  graph_fix: graphFix,
  verification: {
    iterations: iteration,
    chunk_works: chunkWorks,
    graph_works: graphWorks
  },
  ready_to_resume: chunkWorks && graphWorks
}
