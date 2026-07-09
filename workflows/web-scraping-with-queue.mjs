export const meta = {
  name: 'web-scraping-with-queue',
  description: 'Distributed web scraping + queue files for ingestion',
  phases: [
    { title: 'Scrape', detail: 'Parallel web scraping across 8 workers' },
    { title: 'Queue', detail: 'Add scraped files to ingestion queue' },
    { title: 'Verify', detail: 'Check queue status' }
  ]
}

// 13 new sources to scrape
const SCRAPERS = [
  { worker: 'laptop-01', scrapers: ['hackernews', 'reddit'] },
  { worker: 'server-01', scrapers: ['stackexchange', 'guardian'] },
  { worker: 'server-02', scrapers: ['mit-ocw', 'leetcode'] },
  { worker: 'server-03', scrapers: ['kaggle-notebooks', 'quora'] },
  { worker: 'pi-01', scrapers: ['biorxiv', 'medrxiv'] },
  { worker: 'pi-02', scrapers: ['wikibooks', 'wikisource'] },
  { worker: 'desktop-ap', scrapers: ['project-gutenberg'] },
  { worker: 'server-ap', scrapers: ['internet-archive'] }
]

const BASE = '/mnt/aio-01/claude-orchestrator'
const TOOLS = `${BASE}/tools`
const OUTPUT = `${BASE}/scraped-data/raw`

phase('Scrape')
log(`Launching ${SCRAPERS.length} workers scraping ${SCRAPERS.reduce((s, w) => s + w.scrapers.length, 0)} sources`)

const scrape_results = await parallel(SCRAPERS.map(({ worker, scrapers }) => async () =>
  await agent(
    `On ${worker}, run web scrapers and save to local storage:

${scrapers.map(s => `
Source: ${s}
Script: ${TOOLS}/${s}_scraper.py
Output: ${OUTPUT}/${s}/
Command: python3 ${TOOLS}/${s}_scraper.py --output ${OUTPUT}/${s}/ --limit 1000 2>&1 | tee /tmp/${s}_scrape.log

If scraper fails, log error and continue to next.
`).join('\n')}

Return list of files created per scraper:
{
  worker: "${worker}",
  results: [{scraper: "name", files: ["path1", "path2"], count: N, status: "success/failed"}]
}`,
    { label: worker, phase: 'Scrape', schema: {
      type: 'object',
      properties: {
        worker: { type: 'string' },
        results: { type: 'array', items: { type: 'object', properties: {
          scraper: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          count: { type: 'number' },
          status: { type: 'string' }
        }}}
      }
    }}
  )
))

phase('Queue')
log('Adding scraped files to ingestion queue...')

const all_files = scrape_results.filter(Boolean)
  .flatMap(r => r.results || [])
  .filter(r => r.status === 'success')
  .flatMap(r => r.files || [])

log(`Found ${all_files.length} files to queue for ingestion`)

const queue_result = await agent(
  `Add ${all_files.length} files to PostgreSQL ingestion queue:

Database: aio-01:5433/learning
Table: queue.tasks

For each file:
INSERT INTO queue.tasks (priority, task_type, payload, status)
VALUES (5, 'ingest', '{"file_path": "<path>", "source": "<category>"}', 'pending');

Return: {queued: N, failed: N}`,
  { label: 'queue-files', phase: 'Queue', schema: {
    type: 'object',
    properties: { queued: { type: 'number' }, failed: { type: 'number' } }
  }}
)

phase('Verify')
const successful = scrape_results.filter(Boolean)
  .flatMap(r => r.results || [])
  .filter(r => r.status === 'success')

log(`Scrapers completed: ${successful.length}`)
log(`Files scraped: ${all_files.length}`)
log(`Files queued: ${queue_result?.queued || 0}`)

return {
  scrapers_completed: successful.length,
  files_scraped: all_files.length,
  files_queued: queue_result?.queued || 0,
  sources: successful.map(r => r.scraper)
}
