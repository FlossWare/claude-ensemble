export const meta = {
  name: 'queue-workers',
  description: 'Distributed queue processing - chunk, embed, store workers via orchestrator',
  phases: [
    { title: 'Workers', detail: 'Run queue workers across fleet' }
  ]
}

// Distribute workers across fleet
const WORKERS = [
  // Chunk workers (4 workers - process queue.tasks)
  { worker: 'laptop-01', type: 'chunk', batch: 10 },
  { worker: 'server-01', type: 'chunk', batch: 10 },
  { worker: 'server-02', type: 'chunk', batch: 10 },
  { worker: 'server-03', type: 'chunk', batch: 10 },
  
  // Embed workers (4 workers - process queue.chunk)
  { worker: 'laptop-01', type: 'embed', batch: 5 },
  { worker: 'server-01', type: 'embed', batch: 5 },
  { worker: 'server-02', type: 'embed', batch: 5 },
  { worker: 'server-03', type: 'embed', batch: 5 },
  
  // Store workers (2 workers - process queue.store)
  { worker: 'pi-01', type: 'store', batch: 20 },
  { worker: 'pi-02', type: 'store', batch: 20 }
]

const API = 'http://aio-01:5000'

phase('Workers')
log(`Starting ${WORKERS.length} queue workers distributed across fleet`)

await parallel(WORKERS.map(({ worker, type, batch }) => async () =>
  await agent(
    `On ${worker}, run ${type} queue worker:

Process ${batch} items per cycle from PostgreSQL queue:

Database: aio-01:5433/learning

${type === 'chunk' ? `
1. Poll queue.tasks for pending items (LIMIT ${batch})
2. For each task:
   - Extract file_path from payload
   - POST ${API}/documents/chunk with {"file_path": "<path>"}
   - If success: INSERT into queue.chunk with chunk IDs
   - If error: UPDATE queue.tasks SET status='failed', retry_count++
   - Mark task as completed
` : type === 'embed' ? `
1. Poll queue.chunk for pending items (LIMIT ${batch})
2. For each item:
   - Get chunks from payload
   - POST ${API}/documents/embed with {"chunks": [...]}
   - If success: INSERT into queue.store with embeddings
   - If error: Mark failed with retry
` : `
1. Poll queue.store for pending items (LIMIT ${batch})
2. For each item:
   - INSERT INTO knowledge.scraped_data (file_path, chunk_id, chunk_text, embedding, source)
   - Mark as completed
`}

Run continuously for 5 minutes or until queue empty.
Log every 10 items processed.

Return: {
  worker: "${worker}",
  type: "${type}",
  processed: N,
  failed: N,
  queue_empty: true|false
}`,
    { label: `${worker}-${type}`, phase: 'Workers', schema: {
      type: 'object',
      properties: {
        worker: { type: 'string' },
        type: { type: 'string' },
        processed: { type: 'number' },
        failed: { type: 'number' },
        queue_empty: { type: 'boolean' }
      }
    }}
  )
))

const results = await parallel(WORKERS.map(({ worker, type, batch }) => async () =>
  await agent(
    `On ${worker}, run ${type} queue worker:

Process ${batch} items per cycle from PostgreSQL queue:

Database: aio-01:5433/learning

${type === 'chunk' ? `
1. Poll queue.tasks for pending items (LIMIT ${batch})
2. For each task:
   - Extract file_path from payload
   - POST ${API}/documents/chunk with {"file_path": "<path>"}
   - If success: INSERT into queue.chunk with chunk IDs
   - If error: UPDATE queue.tasks SET status='failed', retry_count++
   - Mark task as completed
` : type === 'embed' ? `
1. Poll queue.chunk for pending items (LIMIT ${batch})
2. For each item:
   - Get chunks from payload
   - POST ${API}/documents/embed with {"chunks": [...]}
   - If success: INSERT into queue.store with embeddings
   - If error: Mark failed with retry
` : `
1. Poll queue.store for pending items (LIMIT ${batch})
2. For each item:
   - INSERT INTO knowledge.scraped_data (file_path, chunk_id, chunk_text, embedding, source)
   - Mark as completed
`}

Run continuously for 5 minutes or until queue empty.
Log every 10 items processed.

Return: {
  worker: "${worker}",
  type: "${type}",
  processed: N,
  failed: N,
  queue_empty: true|false
}`,
    { label: `${worker}-${type}`, phase: 'Workers', schema: {
      type: 'object',
      properties: {
        worker: { type: 'string' },
        type: { type: 'string' },
        processed: { type: 'number' },
        failed: { type: 'number' },
        queue_empty: { type: 'boolean' }
      }
    }}
  )
))

const total_processed = results.filter(Boolean).reduce((s, r) => s + (r.processed || 0), 0)
const total_failed = results.filter(Boolean).reduce((s, r) => s + (r.failed || 0), 0)

log(`✅ Queue processing complete: ${total_processed} processed, ${total_failed} failed`)

return {
  workers: results.filter(Boolean).length,
  total_processed,
  total_failed
}
