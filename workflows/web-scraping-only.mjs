export const meta = {
  name: 'web-scraping-only',
  description: 'Distributed web scraping - collect data only, no ingestion',
  phases: [
    { title: 'Scrape', detail: 'Parallel web scraping across 8 workers' },
    { title: 'Verify', detail: 'Check results' }
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
log(`Launching ${SCRAPERS.length} workers scraping ${SCRAPERS.reduce((s,w)=>s+w.sources.length,0)} new sources`)

const results = await parallel(SCRAPERS.map(({worker, sources}) => async () =>
  await agent(
    `On ${worker}, run web scrapers (NEW sources only - skip existing data):

${sources.map(s => `
Source: ${s}
Script: ${BASE}/tools/${s}_scraper.py
Output: ${BASE}/scraped-data/raw/${s}/
Limit: 1000 items per source

Command:
python3 ${BASE}/tools/${s}_scraper.py --output ${BASE}/scraped-data/raw/${s}/ --limit 1000

If script doesn't exist, log error and continue.
Log progress every 100 items.
`).join('\n')}

Return: {
  worker: "${worker}",
  results: [
    {source: "name", files: N, size_mb: N, status: "success|failed", error: "..."}
  ]
}`,
    { label: worker, phase: 'Scrape', schema: {
      type: 'object',
      properties: {
        worker: {type:'string'},
        results: {type:'array', items: {type:'object', properties: {
          source: {type:'string'},
          files: {type:'number'},
          size_mb: {type:'number'},
          status: {type:'string'},
          error: {type:'string'}
        }}}
      }
    }}
  )
))

phase('Verify')
const ok = results.filter(Boolean)
const all_results = ok.flatMap(r => r.results || [])
const successful = all_results.filter(r => r.status === 'success')
const failed = all_results.filter(r => r.status === 'failed')

const total_files = successful.reduce((s, r) => s + (r.files||0), 0)
const total_size = successful.reduce((s, r) => s + (r.size_mb||0), 0)

log(`Workers: ${ok.length}/${SCRAPERS.length}`)
log(`Sources successful: ${successful.length}`)
log(`Sources failed: ${failed.length}`)
log(`Total files: ${total_files.toLocaleString()}`)
log(`Total size: ${Math.round(total_size)}MB`)

if (failed.length > 0) {
  log(`Failed: ${failed.map(f => f.source).join(', ')}`)
}

return {
  workers: ok.length,
  successful: successful.length,
  failed: failed.length,
  files: total_files,
  size_mb: Math.round(total_size),
  sources: successful.map(r => r.source)
}
