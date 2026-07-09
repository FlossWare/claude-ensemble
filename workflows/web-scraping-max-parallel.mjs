export const meta = {
  name: 'web-scraping-max-parallel',
  description: 'Maximum parallelization - 20 workers under 60% CPU limit',
  phases: [
    { title: 'Scrape', detail: '20 parallel scrapers across 8 machines' },
    { title: 'Verify', detail: 'Check results' }
  ]
}

// Distribute 20 workers optimally across 8 machines
const WORKERS = [
  // laptop-01: 8 CPUs → 4 workers (50% CPU)
  { worker: 'laptop-01', id: 1, source: 'hackernews' },
  { worker: 'laptop-01', id: 2, source: 'reddit' },
  { worker: 'laptop-01', id: 3, source: 'medium' },
  { worker: 'laptop-01', id: 4, source: 'quora' },
  
  // server-01: 8 CPUs → 4 workers
  { worker: 'server-01', id: 1, source: 'stackoverflow' },
  { worker: 'server-01', id: 2, source: 'stackexchange' },
  { worker: 'server-01', id: 3, source: 'guardian' },
  { worker: 'server-01', id: 4, source: 'hackernews' },
  
  // server-02: 8 CPUs → 4 workers
  { worker: 'server-02', id: 1, source: 'mit-ocw' },
  { worker: 'server-02', id: 2, source: 'leetcode' },
  { worker: 'server-02', id: 3, source: 'kaggle-notebooks' },
  { worker: 'server-02', id: 4, source: 'arxiv_scraper' },
  
  // server-03: 8 CPUs → 4 workers
  { worker: 'server-03', id: 1, source: 'semantic-scholar' },
  { worker: 'server-03', id: 2, source: 'pubmed' },
  { worker: 'server-03', id: 3, source: 'biorxiv' },
  { worker: 'server-03', id: 4, source: 'medrxiv' },
  
  // pi-01: 4 CPUs → 2 workers (50% CPU)
  { worker: 'pi-01', id: 1, source: 'wikibooks' },
  { worker: 'pi-01', id: 2, source: 'wikisource' },
  
  // pi-02: 4 CPUs → 2 workers
  { worker: 'pi-02', id: 1, source: 'project-gutenberg' },
  { worker: 'pi-02', id: 2, source: 'internet-archive' },
  
  // desktop-ap: 4 CPUs → 2 workers
  // server-ap: 4 CPUs → 2 workers (commented out for now - only 20 sources)
]

const BASE = '/mnt/aio-01/claude-orchestrator'

phase('Scrape')
log(`Launching ${WORKERS.length} parallel workers across 8 machines (max 60% CPU per machine)`)

const results = await parallel(WORKERS.map(({ worker, id, source }) => async () =>
  await agent(
    `On ${worker} (worker ${id}), run scraper for ${source}:

Script: ${BASE}/tools/${source}_scraper.py
Output: ${BASE}/scraped-data/raw/${source}/
Limit: 1000 items

Command:
cd ${BASE}/tools && python3 ${source}_scraper.py --output ${BASE}/scraped-data/raw/${source}/ --limit 1000 2>&1 | tee /tmp/${source}_scrape.log

If script doesn't exist, try variations:
- ${source}.py
- ${source}_scraper_fixed.py
- ${source}_scraper_with_storage.py

Skip if already scraped (deduplicate).
Log every 50 items.

Return: {worker: "${worker}", source: "${source}", files: N, size_mb: N, status: "success/failed", error: "..."}`,
    { label: `${worker}-${source}`, phase: 'Scrape', schema: {
      type: 'object',
      properties: {
        worker: { type: 'string' },
        source: { type: 'string' },
        files: { type: 'number' },
        size_mb: { type: 'number' },
        status: { type: 'string' },
        error: { type: 'string' }
      }
    }}
  )
))

phase('Verify')
const ok = results.filter(Boolean)
const successful = ok.filter(r => r.status === 'success')
const failed = ok.filter(r => r.status === 'failed')

const total_files = successful.reduce((s, r) => s + (r.files||0), 0)
const total_size = successful.reduce((s, r) => s + (r.size_mb||0), 0)

log(`Workers completed: ${ok.length}/${WORKERS.length}`)
log(`Successful: ${successful.length}`)
log(`Failed: ${failed.length}`)
log(`Total files: ${total_files.toLocaleString()}`)
log(`Total size: ${Math.round(total_size)}MB`)

if (failed.length > 0) {
  log(`Failed sources: ${failed.map(f => f.source).join(', ')}`)
}

return {
  workers: ok.length,
  successful: successful.length,
  failed: failed.length,
  files: total_files,
  size_mb: Math.round(total_size),
  sources: successful.map(r => r.source)
}
