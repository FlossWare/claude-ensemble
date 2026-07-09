export const meta = {
  name: 'web-scraping-final',
  description: 'Distributed web scraping → add to queue.tasks for async processing',
  phases: [
    { title: 'Scrape', detail: 'Parallel web scraping across 8 workers' },
    { title: 'Queue', detail: 'Add files to queue.tasks' }
  ]
}

const SCRAPERS = [
  { worker: 'laptop-01', sources: ['hackernews', 'reddit'] },
  { worker: 'server-01', sources: ['stackexchange', 'guardian'] },
  { worker: 'server-02', sources: ['mit-ocw', 'leetcode'] },
  { worker: 'server-03', sources: ['kaggle-notebooks', 'quora'] },
  { worker: 'pi-01', sources: ['biorxiv', 'medrxiv'] },
  { worker: 'pi-02', sources: ['wikibooks', 'wikisource'] },
  { worker: 'desktop-ap', sources: ['project-gutenberg'] },
  { worker: 'server-ap', sources: ['internet-archive'] }
]

const BASE = '/mnt/aio-01/claude-orchestrator'

phase('Scrape')
log(`Launching ${SCRAPERS.length} workers, ${SCRAPERS.reduce((s,w)=>s+w.sources.length,0)} sources`)

const results = await parallel(SCRAPERS.map(({worker, sources}) => async () =>
  await agent(
    `On ${worker}, run scrapers and return file paths:

${sources.map(s => `
python3 ${BASE}/tools/${s}_scraper.py \\
  --output ${BASE}/scraped-data/raw/${s}/ \\
  --limit 1000
`).join('\n')}

Return: {worker: "${worker}", files: [{source: "name", path: "/full/path", count: N}]}`,
    { label: worker, phase: 'Scrape', schema: {
      type: 'object',
      properties: {
        worker: {type:'string'},
        files: {type:'array', items: {type:'object', properties: {
          source: {type:'string'},
          path: {type:'string'},
          count: {type:'number'}
        }}}
      }
    }}
  )
))

phase('Queue')
const all_files = results.filter(Boolean).flatMap(r => r.files||[])
log(`Queueing ${all_files.length} file batches to queue.tasks`)

await agent(
  `Add to PostgreSQL queue for async processing:

Database: aio-01:5433/learning

For each source batch:
INSERT INTO queue.tasks (priority, task_type, payload, status) VALUES
(5, 'ingest', '{"source": "<source>", "path": "<path>", "file_count": N}', 'pending');

Total: ${all_files.length} batches

Workers will automatically:
1. chunk_worker → POST /documents/chunk → queue.chunk
2. embed_worker → POST /documents/embed (Jina AI) → queue.embed
3. store_worker → INSERT knowledge.scraped_data

Return: {queued: N}`,
  { label: 'queue', phase: 'Queue', schema: {
    type: 'object',
    properties: { queued: {type:'number'} }
  }}
)

const successful = results.filter(Boolean).flatMap(r => r.files||[])
log(`✅ ${successful.length} source batches queued for async ingestion`)

return {
  workers: results.filter(Boolean).length,
  sources_scraped: successful.length,
  total_files: successful.reduce((s,f)=>s+(f.count||0),0)
}
