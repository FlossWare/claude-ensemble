export const meta = {
  name: 'ingest-web-scraped',
  description: 'Queue 427K web-scraped files for chunk/embed/graph processing',
  phases: [
    { title: 'Discover', detail: 'Find all web-scraped files' },
    { title: 'Queue', detail: 'Insert to queue.tasks for processing' }
  ]
}

const SCRAPED_DATA_DIR = '/mnt/aio-01/claude-orchestrator/scraped-data/raw'

phase('Discover')
log('Finding all web-scraped files...')

const discovery = await agent(
  `Find all web-scraped files in ${SCRAPED_DATA_DIR}:

1. Use find to get all files (not directories)
2. Exclude:
   - books-pdfs/ (already queued separately)
   - .git/ directories
   - hidden files
3. Get full paths
4. Count total files

Return: {total_files: N, sample_paths: [first 10 paths]}`,
  {
    label: 'discover-files',
    phase: 'Discover',
    schema: {
      type: 'object',
      properties: {
        total_files: { type: 'number' },
        sample_paths: { type: 'array', items: { type: 'string' } }
      }
    }
  }
)

log(`Discovered ${discovery.total_files} web-scraped files`)

phase('Queue')
log('Queueing files to PostgreSQL queue.tasks...')

const BATCH_SIZE = 10000
const batches = Math.ceil(discovery.total_files / BATCH_SIZE)

log(`Splitting into ${batches} batches of ${BATCH_SIZE} files each`)

const queueResults = await parallel(
  Array.from({ length: batches }, (_, i) => i).map(batchNum => async () =>
    await agent(
      `Queue batch ${batchNum + 1}/${batches} of web-scraped files:

Database: aio-01:5433/learning

1. Find files in ${SCRAPED_DATA_DIR} (skip books-pdfs/)
2. Skip ${batchNum * BATCH_SIZE} files, take ${BATCH_SIZE}
3. For each file, INSERT into queue.tasks:

   INSERT INTO queue.tasks (payload, priority, status)
   VALUES (
     '{"file_path": "/path/to/file.json", "source": "web-scrape"}'::jsonb,
     5,
     'pending'
   )
   ON CONFLICT DO NOTHING

4. Return count inserted

Run as user 'claude' connecting to aio-01:5433

Return: {batch: ${batchNum + 1}, queued: N}`,
      {
        label: `queue-batch-${batchNum + 1}`,
        phase: 'Queue',
        schema: {
          type: 'object',
          properties: {
            batch: { type: 'number' },
            queued: { type: 'number' }
          }
        }
      }
    )
  )
)

const total_queued = queueResults.filter(Boolean).reduce((sum, r) => sum + (r.queued || 0), 0)

log(`✅ Queued ${total_queued} web-scraped files for ingestion`)

return {
  discovered: discovery.total_files,
  queued: total_queued,
  batches: batches
}
