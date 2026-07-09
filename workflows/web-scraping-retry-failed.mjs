export const meta = {
  name: 'web-scraping-retry-failed',
  description: 'Retry 8 failed web scraping sources from previous run',
  phases: [
    { title: 'Scrape', detail: '8 workers scraping failed sources' }
  ]
}

const SOURCES = [
  { name: 'reddit', worker: 'laptop-01', url_patterns: ['reddit.com/r/programming', 'reddit.com/r/machinelearning', 'reddit.com/r/datascience'] },
  { name: 'guardian', worker: 'server-01', url_patterns: ['theguardian.com/technology', 'theguardian.com/science'] },
  { name: 'mit-ocw', worker: 'server-02', url_patterns: ['ocw.mit.edu/courses/'] },
  { name: 'kaggle-notebooks', worker: 'server-03', url_patterns: ['kaggle.com/code'] },
  { name: 'wikibooks', worker: 'pi-01', url_patterns: ['en.wikibooks.org/wiki/'] },
  { name: 'wikisource', worker: 'pi-02', url_patterns: ['en.wikisource.org/wiki/'] },
  { name: 'project-gutenberg', worker: 'desktop-ap', url_patterns: ['gutenberg.org/ebooks/'] },
  { name: 'arxiv', worker: 'server-ap', url_patterns: ['arxiv.org/abs/', 'arxiv.org/list/cs/recent'] }
]

const OUTPUT_DIR = '/mnt/aio-01/claude-orchestrator/scraped-data/raw'

phase('Scrape')
log(`Starting 8 web scraping workers for failed sources`)

const results = await parallel(
  SOURCES.map(({ name, worker, url_patterns }) => async () =>
    await agent(
      `On ${worker}, scrape ${name}:

Output directory: ${OUTPUT_DIR}/${name}/

1. Use wget/curl/scrapy to scrape from these patterns:
   ${url_patterns.map(p => `   - ${p}`).join('\n')}

2. Save to ${OUTPUT_DIR}/${name}/
3. Respect robots.txt
4. Rate limit: max 1 request/second
5. Run for 10 minutes max
6. Skip already-downloaded files

Return: {source: "${name}", worker: "${worker}", files: N, size_mb: N, success: true/false}`,
      {
        label: `scrape-${name}`,
        phase: 'Scrape',
        schema: {
          type: 'object',
          properties: {
            source: { type: 'string' },
            worker: { type: 'string' },
            files: { type: 'number' },
            size_mb: { type: 'number' },
            success: { type: 'boolean' }
          }
        }
      }
    )
  )
)

const successful = results.filter(Boolean).filter(r => r.success)
const failed = results.filter(Boolean).filter(r => !r.success)
const total_files = successful.reduce((sum, r) => sum + (r.files || 0), 0)
const total_size_mb = successful.reduce((sum, r) => sum + (r.size_mb || 0), 0)

log(`✅ Scraped ${total_files} files (${total_size_mb}MB) from ${successful.length} sources`)

return {
  workers: SOURCES.length,
  successful: successful.length,
  failed: failed.length,
  total_files,
  total_size_mb,
  sources_successful: successful.map(r => r.source),
  sources_failed: failed.map(r => r.source)
}
