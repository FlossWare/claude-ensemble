export const meta = {
  name: 'queue-workers-fanout',
  description: 'Fan-out queue architecture - parallel chunk/embed/graph processing',
  phases: [
    { title: 'Dispatch', detail: 'Fan out from main queue to specialized queues' },
    { title: 'Process', detail: 'Chunk, embed, graph workers in parallel' },
    { title: 'Store', detail: 'Converge and store to PostgreSQL' }
  ]
}

const API = 'http://aio-01:5000'

phase('Dispatch')
log('Dispatchers: Pull from queue.tasks → fan out to chunk/embed/graph queues')

const dispatchers = await parallel([
  { worker: 'laptop-01', batch: 20 },
  { worker: 'server-01', batch: 20 },
  { worker: 'server-02', batch: 20 }
].map(({ worker, batch }) => async () =>
  await agent(
    `On ${worker}, run DISPATCHER worker:

REST API: ${API}/queue/*
Worker ID: ${worker}

1. Dequeue ${batch} items from queue.tasks:
   curl -X POST ${API}/queue/dequeue \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "tasks", "batch_size": ${batch}, "worker_id": "${worker}"}'

   Response: {items: [{id, payload, ...}], dequeued: N}

2. For each task:
   - Extract file_path from payload
   - Fan out to ALL 3 queues (parallel processing):

   curl -X POST ${API}/queue/enqueue \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "chunk", "items": [{"document_id": "uuid", "file_path": "...", "priority": 5}]}'

   curl -X POST ${API}/queue/enqueue \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "embed", "items": [{"document_id": "uuid", "file_path": "...", "priority": 5}]}'

   curl -X POST ${API}/queue/enqueue \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "graph", "items": [{"document_id": "uuid", "file_path": "...", "priority": 5}]}'

   - Mark main task as completed:
   curl -X POST ${API}/queue/complete \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "tasks", "item_ids": [id], "worker_id": "${worker}"}'

3. Run for 3 minutes or until no items returned from dequeue

4. Error handling:
   - On API failure: curl -X POST ${API}/queue/fail -d '{"queue": "tasks", "item_id": id, "error": "...", "max_retries": 3, "worker_id": "${worker}"}'
   - Retry failed API calls up to 3 times with exponential backoff

Return: {worker: "${worker}", dispatched: N, queues_populated: ['chunk','embed','graph']}`,
    { label: `dispatcher-${worker}`, phase: 'Dispatch', schema: {
      type: 'object',
      properties: {
        worker: { type: 'string' },
        dispatched: { type: 'number' },
        queues_populated: { type: 'array', items: { type: 'string' } }
      }
    }}
  )
))

phase('Process')
log('Specialized workers: chunk, embed, graph - all in parallel')

const processors = await parallel([
  // Chunk workers (3 workers)
  { worker: 'laptop-01', type: 'chunk', batch: 10 },
  { worker: 'server-01', type: 'chunk', batch: 10 },
  { worker: 'server-02', type: 'chunk', batch: 10 },

  // Embed workers (3 workers)
  { worker: 'server-01', type: 'embed', batch: 5 },
  { worker: 'server-02', type: 'embed', batch: 5 },
  { worker: 'server-03', type: 'embed', batch: 5 },

  // Graph workers (3 workers)
  { worker: 'server-03', type: 'graph', batch: 10 },
  { worker: 'pi-01', type: 'graph', batch: 10 },
  { worker: 'pi-02', type: 'graph', batch: 10 }
].map(({ worker, type, batch }) => async () =>
  await agent(
    `On ${worker}, run ${type.toUpperCase()} worker:

REST API: ${API}/queue/*, ${API}/documents/${type}
Worker ID: ${worker}

1. Dequeue ${batch} items from queue.${type}:
   curl -X POST ${API}/queue/dequeue \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "${type}", "batch_size": ${batch}, "worker_id": "${worker}"}'

   Response: {items: [{id, document_id, file_path, ...}], dequeued: N}

2. For each item:
   - Process via API:
   curl -X POST ${API}/documents/${type} \\
     -H "Content-Type: application/json" \\
     -d '{"file_path": "...", "document_id": "..."}'

   - Enqueue result to queue.store:
   curl -X POST ${API}/queue/enqueue \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "store", "items": [{"document_id": "...", "${type}_result": {...}, "priority": 5}]}'

   - Mark as completed:
   curl -X POST ${API}/queue/complete \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "${type}", "item_ids": [id], "worker_id": "${worker}"}'

3. Run for 5 minutes or until no items returned from dequeue

4. Error handling:
   - On processing error: curl -X POST ${API}/queue/fail -d '{"queue": "${type}", "item_id": id, "error": "...", "max_retries": 3, "worker_id": "${worker}"}'
   - On API failure: retry up to 3 times with exponential backoff (1s, 2s, 4s)

Return: {worker: "${worker}", type: "${type}", processed: N, enqueued_to_store: N, failed: N}`,
    { label: `${type}-${worker}`, phase: 'Process', schema: {
      type: 'object',
      properties: {
        worker: { type: 'string' },
        type: { type: 'string' },
        processed: { type: 'number' },
        enqueued_to_store: { type: 'number' },
        failed: { type: 'number' }
      }
    }}
  )
))

phase('Store')
log('Store workers: Converge all results → PostgreSQL')

const storers = await parallel([
  { worker: 'desktop-ap', batch: 20 },
  { worker: 'server-ap', batch: 20 }
].map(({ worker, batch }) => async () =>
  await agent(
    `On ${worker}, run STORE worker:

REST API: ${API}/queue/*, ${API}/documents/store
Worker ID: ${worker}

1. Dequeue ${batch} items from queue.store:
   curl -X POST ${API}/queue/dequeue \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "store", "batch_size": ${batch}, "worker_id": "${worker}"}'

   Response: {items: [{id, document_id, chunk_result, embed_result, graph_result, ...}], dequeued: N}

2. For each complete item (must have ALL results: chunk + embed + graph):
   - Combine chunk_result + embed_result + graph_result into chunks array
   - Store via REST API:
   curl -X POST ${API}/documents/store \\
     -H "Content-Type: application/json" \\
     -d '{"chunks": [{
       "file_path": "<from queue item>",
       "chunk_id": 0,
       "chunk_text": "<from chunk_result>",
       "embedding": <from embed_result>,
       "entities": <from graph_result>,
       "source": "<from queue item>"
     }]}'

   - Mark as completed:
   curl -X POST ${API}/queue/complete \\
     -H "Content-Type: application/json" \\
     -d '{"queue": "store", "item_ids": [id], "worker_id": "${worker}"}'

3. Run for 5 minutes or until no items returned from dequeue

4. Error handling:
   - On store failure: curl -X POST ${API}/queue/fail -d '{"queue": "store", "item_id": id, "error": "...", "max_retries": 3, "worker_id": "${worker}"}'
   - Skip items missing chunk/embed/graph results (mark as failed with error "incomplete results")

Return: {worker: "${worker}", stored: N, skipped_incomplete: N, failed: N}`,
    { label: `store-${worker}`, phase: 'Store', schema: {
      type: 'object',
      properties: {
        worker: { type: 'string' },
        stored: { type: 'number' },
        skipped_incomplete: { type: 'number' },
        failed: { type: 'number' }
      }
    }}
  )
))

const total_dispatched = dispatchers.filter(Boolean).reduce((s, r) => s + (r.dispatched||0), 0)
const total_processed = processors.filter(Boolean).reduce((s, r) => s + (r.processed||0), 0)
const total_stored = storers.filter(Boolean).reduce((s, r) => s + (r.stored||0), 0)

log(`✅ Dispatched: ${total_dispatched}, Processed: ${total_processed}, Stored: ${total_stored}`)

return {
  dispatched: total_dispatched,
  processed: total_processed,
  stored: total_stored
}
