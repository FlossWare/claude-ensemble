export const meta = {
  name: 'web-scraping-fleet',
  description: 'Distributed web scraping across 8 workers - NEW sources only',
  phases: [
    { title: 'Distribute', detail: 'Assign scrapers to 8 workers' },
    { title: 'Scrape', detail: 'Parallel web scraping' },
    { title: 'Verify', detail: 'Check results' }
  ]
}

// 13 new sources to scrape
const SCRAPERS = [
  { worker: 'laptop-01', id: 1, scrapers: ['hackernews', 'reddit'] },
  { worker: 'server-01', id: 2, scrapers: ['stackexchange', 'guardian'] },
  { worker: 'server-02', id: 3, scrapers: ['mit-ocw', 'leetcode'] },
  { worker: 'server-03', id: 4, scrapers: ['kaggle-notebooks', 'quora'] },
  { worker: 'pi-01', id: 5, scrapers: ['biorxiv', 'medrxiv'] },
  { worker: 'pi-02', id: 6, scrapers: ['wikibooks', 'wikisource'] },
  { worker: 'desktop-ap', id: 7, scrapers: ['project-gutenberg'] },
  { worker: 'server-ap', id: 8, scrapers: ['internet-archive'] }
]

const BASE = '/mnt/aio-01/claude-orchestrator'
const TOOLS = `${BASE}/tools`
const OUTPUT = `${BASE}/scraped-data/raw`

phase('Distribute')
log(`Launching ${SCRAPERS.length} workers with ${SCRAPERS.reduce((sum, w) => sum + w.scrapers.length, 0)} scrapers`)

phase('Scrape')
const results = await parallel(SCRAPERS.map(({ worker, id, scrapers }) => async () => {
  return await agent(
    `On ${worker} (worker ${id}), run web scrapers:

${scrapers.map(s => `
Scraper: ${s}
Script: ${TOOLS}/${s}_scraper.py
Output: ${OUTPUT}/${s}/
Command: cd ${TOOLS} && python3 ${s}_scraper.py --output ${OUTPUT}/${s}/ --limit 1000

Run each scraper sequentially. If script doesn't exist or fails, skip and note error.
`).join('\n')}

Log progress every 100 items scraped.
Return: {
  worker: "${worker}",
  agent: ${id},
  results: [
    {scraper: "name", files: N, size_mb: N, status: "success/failed", error: "..."}
  ]
}`,
    {
      label: `${worker}-${id}`,
      phase: 'Scrape',
      schema: {
        type: 'object',
        properties: {
          worker: { type: 'string' },
          agent: { type: 'number' },
          results: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                scraper: { type: 'string' },
                files: { type: 'number' },
                size_mb: { type: 'number' },
                status: { type: 'string' },
                error: { type: 'string' }
              }
            }
          }
        }
      }
    }
  )
}))

phase('Verify')
const ok = results.filter(Boolean)
const all_results = ok.flatMap(r => r.results || [])
const successful = all_results.filter(r => r.status === 'success')
const failed = all_results.filter(r => r.status === 'failed')

const total_files = successful.reduce((sum, r) => sum + (r.files || 0), 0)
const total_size_mb = successful.reduce((sum, r) => sum + (r.size_mb || 0), 0)

log(`Workers completed: ${ok.length}/${SCRAPERS.length}`)
log(`Scrapers successful: ${successful.length}`)
log(`Scrapers failed: ${failed.length}`)
log(`Total files scraped: ${total_files.toLocaleString()}`)
log(`Total size: ${Math.round(total_size_mb)}MB`)

if (failed.length > 0) {
  log(`Failed scrapers: ${failed.map(f => f.scraper).join(', ')}`)
}

return {
  workers: ok.length,
  successful: successful.length,
  failed: failed.length,
  files: total_files,
  size_mb: Math.round(total_size_mb),
  scrapers: successful.map(r => r.scraper)
}
