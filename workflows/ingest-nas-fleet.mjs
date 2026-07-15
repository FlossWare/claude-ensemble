export const meta = {
  name: 'ingest-nas-fleet',
  description: 'Distribute 37GB NAS data ingestion across 5-worker fleet',
  phases: [
    { title: 'Distribute', detail: 'Assign categories to workers' },
    { title: 'Process', detail: 'Chunk + embed on each worker' },
    { title: 'Store', detail: 'Insert into PostgreSQL' },
    { title: 'Verify', detail: 'Check ingestion stats' }
  ]
};

/**
 * Fleet-Wide NAS Data Ingestion
 *
 * Distributes 37GB of scraped data (446,814 files) across entire fleet:
 * - laptop-01 (8c, 31GB) - 7 categories
 * - server-01 (8c, 16GB) - 6 categories
 * - server-02 (8c, 31GB) - 6 categories
 * - server-03 (8c, 31GB) - 6 categories
 * - pi-01 (4c, 0.9GB) - 6 categories (light tasks only)
 *
 * Process:
 * 1. Chunk files (512-1024 tokens, tiktoken)
 * 2. Generate embeddings (all-mpnet-base-v2, 768-dim)
 * 3. Insert into knowledge.code_embeddings (PostgreSQL + pgvector)
 */
export default async function({ phase, parallel, agent, log, args}) {

  // Category distribution
  const WORKERS = {
    'laptop-01': [
      'raw-blockchain-cloud',
      'raw-electronics',
      'raw-law-history',
      'raw-news',
      'raw-papers',
      'raw-stackexchange',
      'raw-wikisource'
    ],
    'server-01': [
      'raw-chip-design',
      'raw-firmware-code',
      'raw-mdn',
      'raw-news-multi',
      'raw-pubmed',
      'raw-stackoverflow'
    ],
    'server-02': [
      'raw-consciousness',
      'raw-github',
      'raw-mit-ocw',
      'raw-official-docs',
      'raw-reddit',
      'raw-theses'
    ],
    'server-03': [
      'raw-db-languages',
      'raw-guardian',
      'raw-ml-frameworks',
      'raw-os-code',
      'raw-rfcs',
      'raw-w3c'
    ],
    'pi-01': [
      'raw-devto',
      'raw-hackernews',
      'raw-modern-langs',
      'raw-packages',
      'raw-semantic-scholar',
      'raw-wikipedia'
    ]
  };

  const BASE_PATH = '/mnt/aio-01/claude-orchestrator/scraped-data/nas-archive/web-scrape';

  // Phase 1: Distribute work
  phase('Distribute');
  log('Assigning 31 categories across 5 workers');

  const assignments = [];
  for (const [worker, categories] of Object.entries(WORKERS)) {
    assignments.push({
      worker,
      categories,
      count: categories.length
    });
    log(`${worker}: ${categories.length} categories`);
  }

  // Phase 2: Process on each worker
  phase('Process');
  log('Starting parallel ingestion on all workers');

  const results = await parallel(
    assignments.map(({ worker, categories }) => async () => {
      const startTime = Date.now();

      return await agent(
        `Ingest scraped data on ${worker}:

        Categories to process:
        ${categories.map(c => `- ${BASE_PATH}/${c}`).join('\n')}

        For each category:
        1. Find all text files (*.txt, *.md, *.html, *.json)
        2. Chunk content (512-1024 tokens, tiktoken cl100k_base)
        3. Generate embeddings (all-mpnet-base-v2, 768-dim)
        4. Insert into knowledge.code_embeddings via API:
           POST http://aio-01:8006/api/documents

        Progress:
        - Log every 100 files processed
        - Report total files, chunks, time

        Return:
        {
          "worker": "${worker}",
          "categories": ${categories.length},
          "files_processed": <count>,
          "chunks_created": <count>,
          "embeddings_generated": <count>,
          "duration_minutes": <minutes>,
          "status": "success|error"
        }`,
        {
          label: `ingest-${worker}`,
          phase: 'Process',
          schema: {
            type: 'object',
            properties: {
              worker: { type: 'string' },
              categories: { type: 'number' },
              files_processed: { type: 'number' },
              chunks_created: { type: 'number' },
              embeddings_generated: { type: 'number' },
              duration_minutes: { type: 'number' },
              status: { type: 'string', enum: ['success', 'error'] }
            },
            required: ['worker', 'files_processed', 'chunks_created', 'status']
          }
        }
      );
    })
  );

  // Phase 3: Aggregate results
  phase('Verify');
  log('Aggregating results from all workers');

  const successful = results.filter(Boolean).filter(r => r.status === 'success');
  const failed = results.filter(Boolean).filter(r => r.status === 'error');

  const totals = successful.reduce((acc, r) => ({
    files: acc.files + r.files_processed,
    chunks: acc.chunks + r.chunks_created,
    embeddings: acc.embeddings + r.embeddings_generated,
    time: Math.max(acc.time, r.duration_minutes || 0)
  }), { files: 0, chunks: 0, embeddings: 0, time: 0 });

  log(`Results:`);
  log(`  Workers completed: ${successful.length}/5`);
  log(`  Total files: ${totals.files.toLocaleString()}`);
  log(`  Total chunks: ${totals.chunks.toLocaleString()}`);
  log(`  Total embeddings: ${totals.embeddings.toLocaleString()}`);
  log(`  Wall-clock time: ${Math.round(totals.time)} minutes`);

  if (failed.length > 0) {
    log(`  ⚠️ Failed workers: ${failed.map(r => r.worker).join(', ')}`);
  }

  // Verify PostgreSQL storage
  log('Verifying PostgreSQL storage...');

  const verifyResult = await agent(
    `Query PostgreSQL to verify ingestion:

    psql -h aio-01 -p 5433 -U claude -d learning -c "
      SELECT
        COUNT(*) as total_chunks,
        COUNT(DISTINCT file_path) as unique_files,
        pg_size_pretty(pg_total_relation_size('knowledge.code_embeddings')) as table_size
      FROM knowledge.code_embeddings;
    "

    Return the counts.`,
    {
      label: 'verify-storage',
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          total_chunks: { type: 'number' },
          unique_files: { type: 'number' },
          table_size_gb: { type: 'number' }
        }
      }
    }
  );

  log(`PostgreSQL verification:`);
  log(`  Chunks in DB: ${verifyResult?.total_chunks?.toLocaleString() || 'unknown'}`);
  log(`  Unique files: ${verifyResult?.unique_files?.toLocaleString() || 'unknown'}`);

  return {
    status: successful.length === 5 ? 'complete' : 'partial',
    workers_completed: successful.length,
    workers_failed: failed.length,
    totals,
    verification: verifyResult
  };
}
