export const meta = {
  name: 'ingest-pdfs',
  description: 'Ingest 951 PDFs via queue system → universal API',
  phases: [
    { title: 'Discover', detail: 'Find all PDFs' },
    { title: 'Queue', detail: 'Add to queue.tasks' },
    { title: 'Monitor', detail: 'Check queue status' }
  ]
}

const BASE = '/mnt/aio-01/claude-orchestrator/scraped-data/raw/books-pdfs'

phase('Discover')
log('Finding all PDF files...')

const discovery = await agent(
  `Find all PDFs in ${BASE}:

Command:
find ${BASE} -name "*.pdf" -type f | wc -l

Also get breakdown by category:
find ${BASE} -name "*.pdf" -type f -printf "%h\\n" | sort -u | while read dir; do
  category=$(basename "$dir")
  count=$(find "$dir" -name "*.pdf" -type f | wc -l)
  echo "$category: $count"
done

Return: {
  total_pdfs: N,
  categories: [{name: "computer science", count: N}, ...]
}`,
  { label: 'discover-pdfs', phase: 'Discover', schema: {
    type: 'object',
    properties: {
      total_pdfs: { type: 'number' },
      categories: { type: 'array', items: { type: 'object', properties: {
        name: { type: 'string' },
        count: { type: 'number' }
      }}}
    }
  }}
)

log(`Found ${discovery.total_pdfs} PDFs across ${discovery.categories?.length || 0} categories`)

phase('Queue')
log('Adding PDFs to queue.tasks for async processing...')

const queued = await agent(
  `Add ${discovery.total_pdfs} PDFs to PostgreSQL ingestion queue:

Database: aio-01:5433/learning
Table: queue.tasks

For each PDF file in ${BASE}:
INSERT INTO queue.tasks (priority, task_type, payload, status) VALUES
(5, 'ingest', '{"file_path": "<full_path>", "source": "books-pdfs", "file_type": "pdf"}', 'pending');

Batch inserts for efficiency (100 per batch).

Workers will automatically process:
1. chunk_worker → POST /documents/chunk (PDF extraction + chunking)
2. embed_worker → POST /documents/embed (Jina AI embeddings)
3. store_worker → INSERT knowledge.scraped_data

Return: {queued: N, failed: N}`,
  { label: 'queue-pdfs', phase: 'Queue', schema: {
    type: 'object',
    properties: {
      queued: { type: 'number' },
      failed: { type: 'number' }
    }
  }}
)

phase('Monitor')
const total_queued = queued?.queued || 0
log(`✅ ${total_queued} PDFs queued for ingestion`)

// Check queue status
const status = await agent(
  `Check queue status:

psql -p 5433 learning -c "SELECT COUNT(*) FROM queue.tasks WHERE status = 'pending' AND payload->>'source' = 'books-pdfs';"

Return: {pending: N}`,
  { label: 'queue-status', phase: 'Monitor', schema: {
    type: 'object',
    properties: { pending: { type: 'number' } }
  }}
)

log(`Queue status: ${status?.pending || 0} PDFs pending processing`)

return {
  pdfs_discovered: discovery.total_pdfs,
  pdfs_queued: total_queued,
  pending_in_queue: status?.pending || 0,
  categories: discovery.categories?.length || 0
}
