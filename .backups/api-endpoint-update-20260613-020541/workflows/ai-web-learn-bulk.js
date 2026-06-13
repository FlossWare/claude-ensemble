/**
 * ai-web-learn-bulk.js
 *
 * Fleet-distributed web page ingestion and semantic embedding.
 * Use case: 1000 URLs to learn from, processed in parallel.
 *
 * Multi-session orchestration:
 *   - Controller: Splits 1000 URLs into 3 batches (333 each)
 *   - Worker-01-03: Each processes batch via independent Claude Code session
 *   - Each worker calls ai-web-learn for its URL batch
 *   - Workers output JSON with embeddings
 *   - Controller merges embeddings and inserts into single ChromaDB
 *
 * Per-URL timing:
 *   - Fetch URL: 2-3s
 *   - Extract claims (multi-model): 5s
 *   - Generate embeddings: 2-3s
 *   - Total: ~10s per URL
 *   - Sequential (1000 URLs): 2.8 hours
 *   - Fleet (3 workers): 55 minutes
 *
 * ChromaDB strategy:
 *   - Each worker generates embeddings JSON locally
 *   - Controller collects all JSON outputs
 *   - Controller merges into single ChromaDB instance
 *   - Alternative: Each worker writes to shared ChromaDB (requires locking)
 */

export const meta = {
  name: 'ai-web-learn-bulk',
  description: 'Fleet-distributed web learning - ingest 1000+ URLs with semantic embeddings',
  whenToUse: 'When you need to learn from 100+ URLs and build semantic search index',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'URL Distribution', detail: 'Split URLs across 3 workers' },
    { title: 'Parallel Learning', detail: 'Each worker processes URLs via ai-web-learn' },
    { title: 'Embedding Merge', detail: 'Collect embeddings from all workers' },
    { title: 'ChromaDB Insert', detail: 'Insert merged embeddings into persistent vector DB' },
    { title: 'Semantic Index', detail: 'Verify index and enable RAG queries' },
  ],
};

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await _agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


import { bulkOrchestrate, mergeEmbeddingResults } from '../shared/fleet-bulk-orchestration.js';
import fs from 'fs';
import path from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const DRY_RUN = args?.dryRun === true;
const CHROMA_HOST = args?.chromaHost || 'localhost';
const CHROMA_PORT = args?.chromaPort || 8000;
const COLLECTION_NAME = args?.collection || 'web-learning';
const METADATA_REQUIRED = args?.metadata || false;

log('');
log('='.repeat(70));
log('Bulk Web Learning - Fleet Distribution');
log('='.repeat(70));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`ChromaDB: ${CHROMA_HOST}:${CHROMA_PORT}`);
log(`Collection: ${COLLECTION_NAME}`);
if (DRY_RUN) log('DRY RUN MODE');
log('');

// ============================================================================
// PHASE 1: Input Validation - URLs
// ============================================================================

phase('Input Validation');

// URLs can come from:
// 1. args.urls - JSON array of URLs
// 2. args.urlFile - File with one URL per line
// 3. args.urlPattern - Glob pattern to find files containing URLs

let urls = [];

if (args?.urls && Array.isArray(args.urls)) {
  urls = args.urls;
  log(`Using ${urls.length} URLs from args.urls`);
} else if (args?.urlFile) {
  const urlContent = fs.readFileSync(args.urlFile, 'utf8');
  urls = urlContent
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#'));
  log(`Loaded ${urls.length} URLs from ${args.urlFile}`);
} else if (args?.urlPattern) {
  const filesResult = await _agent(`Find files matching pattern and extract URLs.

Pattern: ${args.urlPattern}

For each matching file:
1. Read the file
2. Extract lines that look like URLs (start with http:// or https://)
3. Deduplicate

Return all unique URLs found.`, {
    label: 'Extract URLs',
    schema: {
      type: 'object',
      properties: {
        urls: { type: 'array', items: { type: 'string' } },
        files_processed: { type: 'number' },
      }
    }
  });
  urls = filesResult.urls || [];
  log(`Extracted ${urls.length} URLs from ${filesResult.files_processed} files`);
} else {
  return {
    status: 'error',
    message: 'No URLs specified. Provide args.urls, args.urlFile, or args.urlPattern',
    examples: {
      'Array of URLs': { urls: ['https://example.com', 'https://docs.example.com'] },
      'File with URLs': { urlFile: '/path/to/urls.txt' },
      'Pattern': { urlPattern: '/docs/**/*.md' },
    }
  };
}

if (urls.length === 0) {
  return {
    status: 'error',
    message: 'No URLs found',
  };
}

// Deduplicate
const uniqueUrls = Array.from(new Set(urls));
if (uniqueUrls.length < urls.length) {
  log(`Deduplicated ${urls.length - uniqueUrls.length} duplicate URLs`);
  urls = uniqueUrls;
}

log(`Total URLs to process: ${urls.length}`);
log('Sample URLs:');
urls.slice(0, 3).forEach(u => log(`  - ${u.slice(0, 80)}${u.length > 80 ? '...' : ''}`));
if (urls.length > 3) log(`  ... and ${urls.length - 3} more`);
log('');

// ============================================================================
// PHASE 2: Bulk Orchestration
// ============================================================================

phase('Fleet Orchestration');

const orchestrationResult = await bulkOrchestrate({
  skill: 'ai-web-learn-bulk',
  items: urls,
  workerScript: 'workflows/ai-web-learn.js',
  mergeStrategy: mergeEmbeddingResults,
  itemSerializer: (urls) => JSON.stringify(urls),
  resultDeserializer: (stdout) => {
    try {
      return JSON.parse(stdout);
    } catch {
      return { embeddings: [], total_chunks: 0 };
    }
  },
  log,
  fleetOptions: { capabilities: ['web-learning'] },
  minWorkers: 2,
  timeout: 600000, // 10 min per worker
  dryRun: DRY_RUN,
  useWeightedDistribution: true,
});

log('');

if (orchestrationResult.status === 'failed') {
  return {
    status: 'failed',
    message: 'All workers failed',
    urlsProcessed: orchestrationResult.itemsProcessed,
    totalUrls: orchestrationResult.totalItems,
    errors: orchestrationResult.errors,
  };
}

// ============================================================================
// PHASE 3: ChromaDB Integration
// ============================================================================

phase('ChromaDB Integration');

const embeddingData = orchestrationResult.result || { embeddings: [], total_chunks: 0 };
const totalChunks = embeddingData.total_chunks || embeddingData.embeddings?.length || 0;

log(`Total chunks to insert: ${totalChunks}`);

if (totalChunks === 0) {
  log('Warning: No embeddings generated');
  return {
    status: 'partial',
    message: 'Some workers failed to generate embeddings',
    urlsProcessed: orchestrationResult.itemsProcessed,
    totalUrls: orchestrationResult.totalItems,
    embeddingsGenerated: totalChunks,
    errors: orchestrationResult.errors,
  };
}

// Insert embeddings into ChromaDB
const insertResult = await _agent(`Insert embeddings into ChromaDB.

ChromaDB location: ${CHROMA_HOST}:${CHROMA_PORT}
Collection name: ${COLLECTION_NAME}

Embeddings data:
${JSON.stringify(embeddingData, null, 2).slice(0, 5000)}

Steps:
1. Connect to ChromaDB
2. Get or create collection "${COLLECTION_NAME}"
3. Insert embeddings with metadata
4. Verify insertion by querying a sample

Return: { success, chunks_inserted, verification_query_results }`, {
  label: 'ChromaDB Insert',
  schema: {
    type: 'object',
    properties: {
      success: { type: 'boolean' },
      chunks_inserted: { type: 'number' },
      collection_size: { type: 'number' },
      verification: { type: 'object' },
    }
  }
});

if (!insertResult.success) {
  log('Warning: ChromaDB insertion failed');
}

log(`Inserted: ${insertResult.chunks_inserted} chunks`);
log(`Collection size: ${insertResult.collection_size}`);
log('');

// ============================================================================
// PHASE 4: Semantic Index Verification
// ============================================================================

phase('Index Verification');

const verificationResult = await _agent(`Verify the ChromaDB semantic index is working.

Collection: ${COLLECTION_NAME}

Verification tests:
1. Query with sample text and get top 5 results
2. Verify results have similarity scores
3. Test metadata filtering if available

Return: { tests_passed: number, sample_query_results: [...], issues: [...] }`, {
  label: 'Verify Index',
  schema: {
    type: 'object',
    properties: {
      tests_passed: { type: 'number' },
      sample_results: { type: 'array' },
      index_status: { type: 'string' },
    }
  }
});

log(`Verification: ${verificationResult.tests_passed} tests passed`);
log(`Index status: ${verificationResult.index_status}`);
log('');

// ============================================================================
// PHASE 5: Save Results and Metadata
// ============================================================================

phase('Save Metadata');

const reportDir = path.join(process.cwd(), '.claude', 'bulk-reports');
if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

const indexFile = path.join(reportDir, `web-learn-${Date.now()}.json`);
const indexData = {
  timestamp: new Date().toISOString(),
  totalUrls: orchestrationResult.totalItems,
  processedUrls: orchestrationResult.itemsProcessed,
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  embeddingsGenerated: totalChunks,
  chromadb: {
    host: CHROMA_HOST,
    port: CHROMA_PORT,
    collection: COLLECTION_NAME,
    size: insertResult.collection_size,
  },
  verificationTests: verificationResult.tests_passed,
  status: orchestrationResult.status,
  errors: orchestrationResult.errors,
};

fs.writeFileSync(indexFile, JSON.stringify(indexData, null, 2));
log(`Metadata saved: ${indexFile}`);

// Save URL list for reference
const urlListFile = path.join(reportDir, `web-learn-urls-${Date.now()}.txt`);
fs.writeFileSync(urlListFile, urls.join('\n'));
log(`URL list saved: ${urlListFile}`);
log('');

log('='.repeat(70));
log('BULK WEB LEARNING COMPLETE');
log('='.repeat(70));
log(`URLs processed: ${orchestrationResult.itemsProcessed}/${orchestrationResult.totalItems}`);
log(`Embeddings generated: ${totalChunks}`);
log(`ChromaDB collection: ${COLLECTION_NAME} (${insertResult.collection_size} chunks)`);
log(`Fleet used: ${orchestrationResult.fleetUsed ? 'YES' : 'NO'}`);
log(`Workers: ${orchestrationResult.workersUsed}`);
log('='.repeat(70));

return {
  status: orchestrationResult.status,
  totalUrls: orchestrationResult.totalItems,
  processedUrls: orchestrationResult.itemsProcessed,
  embeddingsGenerated: totalChunks,
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  chromadbCollection: COLLECTION_NAME,
  chromadbSize: insertResult.collection_size,
  indexFile,
  urlListFile,
  errors: orchestrationResult.errors,
};
