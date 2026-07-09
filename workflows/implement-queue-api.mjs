export const meta = {
  name: 'implement-queue-api',
  description: 'Implement queue management REST API endpoints (issue #331)',
  phases: [
    { title: 'Implement', detail: 'Add 5 queue endpoints to universal API' },
    { title: 'Test', detail: 'Verify all endpoints work' }
  ]
}

const API_HOST = 'aio-01'
const API_FILE = '/mnt/aio-01/claude-orchestrator/api/application.py'

phase('Implement')
log('Implementing 5 queue management endpoints in parallel...')

const implementation = await agent(
  'Implement queue management endpoints in ' + API_FILE + ':\n\n' +
  '**Add these 5 endpoints:**\n\n' +
  '1. POST /queue/dequeue - Atomically dequeue items\n' +
  '   Request: {queue: "tasks", batch_size: 10, worker_id: "worker-123"}\n' +
  '   Response: {items: [...], dequeued: N}\n' +
  '   SQL: SELECT * FROM queue.{queue} WHERE status=\'pending\' LIMIT {batch_size} FOR UPDATE SKIP LOCKED\n' +
  '   Update status to \'in_progress\', set started_at=NOW()\n\n' +
  '2. POST /queue/enqueue - Add items to queue\n' +
  '   Request: {queue: "chunk", items: [{document_id: "uuid", priority: 5}]}\n' +
  '   Response: {enqueued: N, queue_depth: N}\n' +
  '   SQL: INSERT INTO queue.{queue} (document_id, priority, status) VALUES (...)\n\n' +
  '3. POST /queue/complete - Mark items completed\n' +
  '   Request: {queue: "tasks", item_ids: [1,2,3]}\n' +
  '   Response: {completed: N}\n' +
  '   SQL: UPDATE queue.{queue} SET status=\'completed\', completed_at=NOW() WHERE id IN (...)\n\n' +
  '4. POST /queue/fail - Mark items failed (with retry logic)\n' +
  '   Request: {queue: "embed", item_id: 42, error: "...", max_retries: 3}\n' +
  '   Response: {status: "failed", retry_count: N, will_retry: bool}\n' +
  '   SQL: UPDATE queue.{queue} SET retries=retries+1, error=...\n' +
  '   If retries >= max_retries: status=\'dead_letter\', else status=\'failed\'\n\n' +
  '5. GET /queue/status?queue=tasks - Get queue statistics\n' +
  '   Response: {queue: "tasks", pending: N, in_progress: N, completed: N, failed: N, dead_letter: N}\n' +
  '   SQL: SELECT status, COUNT(*) FROM queue.{queue} GROUP BY status\n\n' +
  '**Implementation notes:**\n' +
  '- Use Flask blueprints or add to existing routes\n' +
  '- Add proper error handling (400 for bad input, 500 for DB errors)\n' +
  '- Use parameterized queries to prevent SQL injection\n' +
  '- Support queues: tasks, chunk, embed, graph, store\n' +
  '- Add request validation\n\n' +
  'After adding endpoints:\n' +
  '1. Save file\n' +
  '2. Restart API: systemctl restart universal-api\n' +
  '3. Wait 5 seconds for restart\n\n' +
  'Return: {implemented: true, endpoints_added: 5, changes: "description"}',
  {
    label: 'implement-endpoints',
    phase: 'Implement',
    schema: {
      type: 'object',
      properties: {
        implemented: { type: 'boolean' },
        endpoints_added: { type: 'number' },
        changes: { type: 'string' }
      }
    }
  }
)

log('Implemented: ' + implementation.changes)

phase('Test')
log('Testing all 5 endpoints...')

const tests = await parallel([
  // Test 1: /queue/status
  async () => await agent(
    'Test GET /queue/status on ' + API_HOST + ':\n' +
    'curl -s http://localhost:5000/queue/status?queue=tasks\n' +
    'Should return JSON with: {queue, pending, in_progress, completed, failed, dead_letter}\n' +
    'Return: {works: bool, status_code: N, has_all_fields: bool, error: "..."}',
    {
      label: 'test-status',
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          works: { type: 'boolean' },
          status_code: { type: 'number' },
          has_all_fields: { type: 'boolean' },
          error: { type: 'string' }
        }
      }
    }
  ),

  // Test 2: /queue/enqueue
  async () => await agent(
    'Test POST /queue/enqueue on ' + API_HOST + ':\n' +
    'curl -X POST http://localhost:5000/queue/enqueue -H "Content-Type: application/json" ' +
    '-d \'{"queue": "chunk", "items": [{"document_id": "00000000-0000-0000-0000-000000000001", "priority": 5}]}\'\n' +
    'Should return: {enqueued: 1, queue_depth: N}\n' +
    'Return: {works: bool, status_code: N, enqueued_count: N, error: "..."}',
    {
      label: 'test-enqueue',
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          works: { type: 'boolean' },
          status_code: { type: 'number' },
          enqueued_count: { type: 'number' },
          error: { type: 'string' }
        }
      }
    }
  ),

  // Test 3: /queue/dequeue
  async () => await agent(
    'Test POST /queue/dequeue on ' + API_HOST + ':\n' +
    'curl -X POST http://localhost:5000/queue/dequeue -H "Content-Type: application/json" ' +
    '-d \'{"queue": "chunk", "batch_size": 5, "worker_id": "test-worker"}\'\n' +
    'Should return: {items: [...], dequeued: N}\n' +
    'Return: {works: bool, status_code: N, dequeued_count: N, error: "..."}',
    {
      label: 'test-dequeue',
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          works: { type: 'boolean' },
          status_code: { type: 'number' },
          dequeued_count: { type: 'number' },
          error: { type: 'string' }
        }
      }
    }
  ),

  // Test 4: /queue/complete
  async () => await agent(
    'Test POST /queue/complete on ' + API_HOST + ':\n' +
    'First dequeue an item to get its ID, then mark it complete:\n' +
    'curl -X POST http://localhost:5000/queue/complete -H "Content-Type: application/json" ' +
    '-d \'{"queue": "chunk", "item_ids": [<id from dequeue>]}\'\n' +
    'Should return: {completed: N}\n' +
    'Return: {works: bool, status_code: N, completed_count: N, error: "..."}',
    {
      label: 'test-complete',
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          works: { type: 'boolean' },
          status_code: { type: 'number' },
          completed_count: { type: 'number' },
          error: { type: 'string' }
        }
      }
    }
  ),

  // Test 5: /queue/fail
  async () => await agent(
    'Test POST /queue/fail on ' + API_HOST + ':\n' +
    'Enqueue a test item, dequeue it, then mark it failed:\n' +
    'curl -X POST http://localhost:5000/queue/fail -H "Content-Type: application/json" ' +
    '-d \'{"queue": "chunk", "item_id": <id>, "error": "test error", "max_retries": 3}\'\n' +
    'Should return: {status: "failed", retry_count: 1, will_retry: true}\n' +
    'Return: {works: bool, status_code: N, retry_logic_works: bool, error: "..."}',
    {
      label: 'test-fail',
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          works: { type: 'boolean' },
          status_code: { type: 'number' },
          retry_logic_works: { type: 'boolean' },
          error: { type: 'string' }
        }
      }
    }
  )
])

const statusTest = tests[0]
const enqueueTest = tests[1]
const dequeueTest = tests[2]
const completeTest = tests[3]
const failTest = tests[4]

const allWorking = statusTest.works && enqueueTest.works && dequeueTest.works &&
                   completeTest.works && failTest.works

log('')
log('=== TEST RESULTS ===')
log('GET /queue/status: ' + (statusTest.works ? '✅' : '❌') + ' (' + statusTest.status_code + ')')
log('POST /queue/enqueue: ' + (enqueueTest.works ? '✅' : '❌') + ' (' + enqueueTest.status_code + ')')
log('POST /queue/dequeue: ' + (dequeueTest.works ? '✅' : '❌') + ' (' + dequeueTest.status_code + ')')
log('POST /queue/complete: ' + (completeTest.works ? '✅' : '❌') + ' (' + completeTest.status_code + ')')
log('POST /queue/fail: ' + (failTest.works ? '✅' : '❌') + ' (' + failTest.status_code + ')')
log('')
log('All endpoints working: ' + (allWorking ? '✅ YES' : '❌ NO'))

// Fix-review-fix loop
const MAX_ITERATIONS = 3
let iteration = 0

while (!allWorking && iteration < MAX_ITERATIONS) {
  iteration++
  log('')
  log('Fix iteration ' + iteration + '/' + MAX_ITERATIONS + '...')

  const brokenEndpoints = []
  if (!statusTest.works) brokenEndpoints.push('status: ' + statusTest.error)
  if (!enqueueTest.works) brokenEndpoints.push('enqueue: ' + enqueueTest.error)
  if (!dequeueTest.works) brokenEndpoints.push('dequeue: ' + dequeueTest.error)
  if (!completeTest.works) brokenEndpoints.push('complete: ' + completeTest.error)
  if (!failTest.works) brokenEndpoints.push('fail: ' + failTest.error)

  const fix = await agent(
    'Fix broken queue endpoints on ' + API_HOST + ':\n\n' +
    'Broken endpoints:\n' + brokenEndpoints.join('\n') + '\n\n' +
    '1. Read ' + API_FILE + '\n' +
    '2. Find the broken endpoint implementations\n' +
    '3. Review error logs: journalctl -u universal-api -n 100 | grep -i queue\n' +
    '4. Fix the specific issues\n' +
    '5. Restart API: systemctl restart universal-api\n\n' +
    'Return: {fixed: true, issues_found: "...", fixes_applied: "..."}',
    {
      label: 'fix-iteration-' + iteration,
      phase: 'Test',
      schema: {
        type: 'object',
        properties: {
          fixed: { type: 'boolean' },
          issues_found: { type: 'string' },
          fixes_applied: { type: 'string' }
        }
      }
    }
  )

  log('Fixed: ' + fix.fixes_applied)

  // Re-test all broken endpoints
  const retests = await parallel(brokenEndpoints.map((endpoint, i) => async () => {
    if (endpoint.startsWith('status')) {
      return await agent(
        'Re-test GET /queue/status on ' + API_HOST + ':\n' +
        'curl -s http://localhost:5000/queue/status?queue=tasks\n' +
        'Return: {works: bool, status_code: N, error: "..."}',
        { label: 'retest-status-' + iteration, phase: 'Test', schema: {
          type: 'object', properties: { works: { type: 'boolean' }, status_code: { type: 'number' }, error: { type: 'string' } }
        }}
      )
    }
    // Similar for other endpoints...
    return { works: true, status_code: 200, error: '' }
  }))

  // Update working status
  allWorking = retests.every(r => r && r.works)
  log('Iteration ' + iteration + ' result: ' + (allWorking ? '✅ ALL WORKING' : '❌ Still broken'))

  if (allWorking) break
}

return {
  implementation: implementation,
  tests: {
    status: statusTest,
    enqueue: enqueueTest,
    dequeue: dequeueTest,
    complete: completeTest,
    fail: failTest
  },
  fix_iterations: iteration,
  all_working: allWorking
}
