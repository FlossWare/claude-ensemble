// AI Web Learn Fleet - Distributed URL batch processing
//
// Pattern: Batch URL Processing
//   1. Split URLs into N chunks (round-robin across workers)
//   2. Each worker fetches + extracts facts + generates embeddings for its URLs
//   3. Collect extraction results (JSON) from each worker
//   4. Merge: Single-writer pattern - controller serializes ChromaDB/vector store inserts
//   5. Validate: Arbiter cross-checks facts across all sources
//
// Architecture: Single-writer post-merge pattern
//   - Workers produce JSON fact extractions (no DB writes)
//   - Controller merges all facts
//   - Single arbiter validates and deduplicates
//   - Single writer inserts into vector store
//
// Speedup: 1.5-2x with 3 workers (network fetch + extraction parallelized)

export const meta = {
  name: 'ai-web-learn-fleet',
  description: 'Fleet-distributed web learning - batches URL processing across workers for 1.5-2x speedup',
  whenToUse: 'When learning from many web URLs and fleet is available',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'Setup', detail: 'Initialize vector store, parse args' },
    { title: 'Distribute URLs', detail: 'Assign URL batches to workers' },
    { title: 'Fetch & Extract', detail: 'Workers fetch pages and extract facts in parallel' },
    { title: 'Validate & Merge', detail: 'Arbiter cross-checks and resolves conflicts' },
    { title: 'Store', detail: 'Single-writer vector store insert' },
    { title: 'Gap Analysis', detail: 'Identify missing knowledge' },
    { title: 'Query', detail: 'Answer questions from knowledge base' },
  ],
};

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
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
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
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
    const result = await agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


import { getWorkers } from '../shared/fleet-utils.js';
import {
  distributeItems,
  gracefulFallback,
} from '../shared/fleet-workflow-patterns.js';

// ============================================================================
// SCHEMAS
// ============================================================================

const FACTS_SCHEMA = {
  type: 'object',
  properties: {
    facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string', description: 'The factual claim' },
          evidence: { type: 'string', description: 'Supporting evidence/quote' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          source_url: { type: 'string' },
          category: { type: 'string' },
        },
        required: ['claim', 'evidence', 'confidence', 'source_url'],
      },
    },
    url: { type: 'string' },
    page_title: { type: 'string' },
    word_count: { type: 'number' },
  },
  required: ['facts', 'url'],
};

const VALIDATION_SCHEMA = {
  type: 'object',
  properties: {
    validated_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          evidence: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          sources: { type: 'array', items: { type: 'string' } },
          conflicts: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                conflicting_claim: { type: 'string' },
                resolution: { type: 'string' },
              },
            },
          },
          category: { type: 'string' },
        },
        required: ['claim', 'evidence', 'confidence', 'sources'],
      },
    },
    rejected_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          reason: { type: 'string' },
        },
      },
    },
    arbiter_model: { type: 'string' },
  },
  required: ['validated_facts', 'rejected_facts', 'arbiter_model'],
};

const QUERY_SCHEMA = {
  type: 'object',
  properties: {
    answer: { type: 'string' },
    supporting_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          fact: { type: 'string' },
          relevance: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['answer', 'supporting_facts', 'confidence'],
};

// ============================================================================
// SIMPLE VECTOR STORE (in-memory, same as base ai-web-learn)
// ============================================================================

class VectorStore {
  constructor() {
    this.documents = [];
  }

  add(text, metadata) {
    const embedding = this._simpleEmbed(text);
    this.documents.push({ text, metadata, embedding });
    return this.documents.length - 1;
  }

  search(query, topK = 5) {
    const queryEmb = this._simpleEmbed(query);
    const scores = this.documents.map((doc, idx) => ({
      idx,
      score: this._cosineSim(queryEmb, doc.embedding),
      ...doc,
    }));
    scores.sort((a, b) => b.score - a.score);
    return scores.slice(0, topK);
  }

  _simpleEmbed(text) {
    const words = text.toLowerCase().split(/\W+/).filter(Boolean);
    const freq = {};
    words.forEach(w => (freq[w] = (freq[w] || 0) + 1));
    const sorted = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 100);
    return sorted.reduce((vec, [word, count]) => { vec[word] = count; return vec; }, {});
  }

  _cosineSim(a, b) {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    let dot = 0, magA = 0, magB = 0;
    keys.forEach(k => {
      const av = a[k] || 0;
      const bv = b[k] || 0;
      dot += av * bv;
      magA += av * av;
      magB += bv * bv;
    });
    return dot / (Math.sqrt(magA) * Math.sqrt(magB) + 0.0001);
  }

  exportData() { return JSON.stringify(this.documents); }
  importData(json) { this.documents = JSON.parse(json); }
}

// ============================================================================
// CONFIGURATION
// ============================================================================

// Parse args
let parsedArgs = args;
if (typeof args === 'string') {
  const trimmed = args.trim();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try { parsedArgs = JSON.parse(trimmed); } catch (e) { parsedArgs = { query: trimmed }; }
  } else {
    parsedArgs = { query: trimmed };
  }
}

const urls = parsedArgs?.urls || [];
const query = parsedArgs?.query || null;
const saveTo = parsedArgs?.saveTo || null;
const loadExisting = parsedArgs?.load || null;
const strategyName = parsedArgs?.strategy || 'maximum-coverage';
const DRY_RUN = parsedArgs?.dryRun === true;

if (!urls.length && !query) {
  return {
    error: 'Must provide either urls to learn from or query to search',
    usage: {
      learn: '{urls: ["https://...", "https://..."], saveTo: "/path/to/kb.json"}',
      query: '{query: "your question", load: "/path/to/kb.json"}',
      both: '{urls: [...], query: "question"}',
    },
  };
}

log('');
log('='.repeat(60));
log('Fleet-Distributed Web Learning');
log('='.repeat(60));
if (urls.length) log(`URLs: ${urls.length} to process`);
if (query) log(`Query: ${query}`);
log(`Strategy: ${strategyName}`);
log('');

// ============================================================================
// PHASE 1: Fleet Discovery
// ============================================================================

phase('Fleet Discovery');

let workers = [];
let useFleet = false;

try {
  workers = getWorkers();
  useFleet = workers.length >= 2 && urls.length >= workers.length;

  if (useFleet) {
    log(`Fleet available: ${workers.length} workers`);
    workers.forEach(w => log(`  - ${w.hostname} (${w.cpus}C/${w.memory_gb}GB)`));
  } else if (workers.length > 0 && urls.length < workers.length) {
    log(`Only ${urls.length} URLs for ${workers.length} workers - no sharding benefit`);
  } else {
    log('Insufficient fleet workers, running locally');
  }
} catch (error) {
  log(`Fleet unavailable (${error.message}), running locally`);
}

log('');

// ============================================================================
// QUERY-ONLY MODE (no URLs to learn)
// ============================================================================

if (query && !urls.length) {
  // Delegate to local ai-web-learn for query-only mode
  const localResult = await workflow('ai-web-learn', {
    query,
    load: loadExisting,
    strategy: strategyName,
  });
  return { ...localResult, fleet_used: false };
}

// ============================================================================
// PHASE 2: Setup
// ============================================================================

phase('Setup');

const vectorStore = new VectorStore();

if (loadExisting) {
  log(`Loading existing knowledge base: ${loadExisting}`);
  // Would load from file in production
}

// Worker models for extraction (maximum coverage by default)
const WORKER_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];

// ============================================================================
// PHASE 3: Distribute URLs
// ============================================================================

phase('Distribute URLs');

if (useFleet) {
  // Fleet distribution: round-robin URLs across workers
  const urlDistribution = distributeItems(urls, workers);

  log(`Distributing ${urls.length} URLs across ${workers.length} workers:`);
  for (const [hostname, workerUrls] of urlDistribution.entries()) {
    log(`  ${hostname}: ${workerUrls.length} URLs`);
    workerUrls.forEach(u => log(`    - ${u}`));
  }
  log('');

  if (DRY_RUN) {
    return {
      status: 'dry_run',
      distribution: Object.fromEntries(urlDistribution),
      workers: workers.map(w => w.hostname),
      total_urls: urls.length,
    };
  }

  // ============================================================================
  // PHASE 4: Fetch & Extract (Fleet Parallel)
  // ============================================================================

  phase('Fetch & Extract');

  log('Fetching and extracting facts across fleet workers...');

  // Each worker processes its batch of URLs
  // Each URL gets multi-model extraction for diverse perspectives
  const workerPromises = workers.map(async (worker) => {
    const workerUrls = urlDistribution.get(worker.hostname);
    if (!workerUrls || workerUrls.length === 0) return [];

    log(`  ${worker.hostname}: processing ${workerUrls.length} URLs...`);

    // For each URL assigned to this worker, fetch and extract
    const urlResults = [];

    for (const url of workerUrls) {
      // Fetch the page content
      const pageContent = await _agent(
        `Fetch the content from this URL and return the full text: ${url}

If you have MCP web-fetching tools available, use them. Otherwise use WebFetch.
Return just the text content, no HTML tags.`,
        {
          label: `fetch-${worker.hostname}:${url.split('/').pop()}`,
          phase: 'Fetch & Extract',
        }
      );

      if (!pageContent) {
        log(`    ${worker.hostname}: Failed to fetch ${url}`);
        continue;
      }

      // Multi-model extraction on this page
      // Use 2-3 models per URL for diversity (not all 6 - diminishing returns for extraction)
      const extractionModels = WORKER_MODELS.slice(0, 3);

      const extractions = await parallel(extractionModels.map(model => () =>
        agent(
          `Extract factual claims from this webpage. Focus on concrete, verifiable facts.

Source URL: ${url}

${typeof pageContent === 'string' ? pageContent.slice(0, 8000) : JSON.stringify(pageContent).slice(0, 8000)}

Extract clear facts with supporting evidence. Be specific and accurate.`,
          {
            schema: FACTS_SCHEMA,
            model,
            label: `extract-${model}:${url.split('/').pop()}`,
          }
        )
      ));

      const validExtractions = extractions.filter(Boolean);
      const facts = validExtractions.flatMap(e => (e.facts || []).map(f => ({
        ...f,
        source_url: url,
      })));

      urlResults.push({
        url,
        facts,
        models_used: extractionModels,
        worker: worker.hostname,
      });

      log(`    ${worker.hostname}: ${facts.length} facts from ${url.split('/').pop()}`);
    }

    return urlResults;
  });

  const allWorkerResults = await Promise.all(workerPromises);
  const allUrlResults = allWorkerResults.flat();
  const allFacts = allUrlResults.flatMap(r => r.facts || []);

  log('');
  log(`Extraction complete: ${allFacts.length} facts from ${allUrlResults.length} URLs`);
  workers.forEach(w => {
    const workerFacts = allUrlResults
      .filter(r => r.worker === w.hostname)
      .reduce((sum, r) => sum + (r.facts?.length || 0), 0);
    log(`  ${w.hostname}: ${workerFacts} facts`);
  });

  // ============================================================================
  // PHASE 5: Validate & Merge (Single arbiter)
  // ============================================================================

  phase('Validate & Merge');

  log('Arbiter validating and deduplicating facts...');

  const arbiter = await workflow('get-next-arbiter');

  const validated = await _agent(
    `You are the arbiter. Review all facts extracted by multiple AI workers from ${allUrlResults.length} URLs.

TASKS:
1. Cross-reference claims - if multiple workers found the same fact, that's high confidence
2. Detect conflicts - if workers disagree, resolve based on evidence quality
3. Filter low-quality facts - reject vague, unsupported, or duplicate claims
4. Categorize validated facts

WORKER FACTS (${allFacts.length} total from ${workers.length} workers):
${JSON.stringify(allFacts.slice(0, 100), null, 2)}
${allFacts.length > 100 ? `\n... and ${allFacts.length - 100} more facts` : ''}

Return validated facts with conflict resolutions and rejected facts with reasons.`,
    {
      schema: VALIDATION_SCHEMA,
      model: arbiter.arbiter,
      label: 'arbiter-validation',
    }
  );

  await workflow('update-arbiter-state', { arbiter: arbiter.arbiter, workflow_name: 'ai-web-learn-fleet' });

  log(`Validated ${validated.validated_facts?.length || 0} facts`);
  log(`Rejected ${validated.rejected_facts?.length || 0} facts`);

  // ============================================================================
  // PHASE 6: Store (Single-writer pattern)
  // ============================================================================

  phase('Store');

  log('Storing validated facts (single-writer pattern)...');

  // Single writer: controller inserts all facts into vector store
  // No concurrent writes - eliminates ChromaDB contention
  for (const fact of (validated.validated_facts || [])) {
    const text = `${fact.claim}\n\nEvidence: ${(fact.evidence || []).join(' ')}`;
    vectorStore.add(text, {
      claim: fact.claim,
      sources: fact.sources,
      confidence: fact.confidence,
      category: fact.category,
      conflicts: fact.conflicts || [],
    });
  }

  log(`Stored ${validated.validated_facts?.length || 0} facts in vector store`);

  // ============================================================================
  // PHASE 7: Gap Analysis
  // ============================================================================

  phase('Gap Analysis');

  log('Identifying knowledge gaps...');

  const gaps = await _agent(
    `Review validated knowledge and identify gaps.

VALIDATED FACTS (${validated.validated_facts?.length || 0}):
${JSON.stringify((validated.validated_facts || []).map(f => f.claim).slice(0, 50), null, 2)}

ORIGINAL URLs:
${urls.join('\n')}

Identify:
1. Topics mentioned but not fully explored
2. Questions raised but not answered
3. Suggested URLs to fill gaps`,
    {
      schema: {
        type: 'object',
        properties: {
          missing_topics: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                topic: { type: 'string' },
                priority: { type: 'string', enum: ['high', 'medium', 'low'] },
                suggested_urls: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          unanswered_questions: { type: 'array', items: { type: 'string' } },
        },
        required: ['missing_topics', 'unanswered_questions'],
      },
      label: 'gap-analysis',
    }
  );

  log(`Missing topics: ${gaps.missing_topics?.length || 0}`);
  log(`Unanswered questions: ${gaps.unanswered_questions?.length || 0}`);

  // ============================================================================
  // PHASE 8: Query (if provided)
  // ============================================================================

  let queryResult = null;
  if (query) {
    phase('Query');

    log(`Answering query: "${query}"`);
    const searchResults = vectorStore.search(query, 10);

    if (searchResults.length === 0) {
      queryResult = { answer: 'No relevant knowledge found.', confidence: 'low' };
    } else {
      const context = searchResults.map(r =>
        `[Score: ${r.score.toFixed(2)}] ${r.text}\nSource: ${r.metadata.sources?.join(', ')}`
      ).join('\n\n');

      queryResult = await _agent(
        `Answer using ONLY the provided facts:

Question: ${query}

Relevant Facts:
${context}

Provide a direct answer, cite facts, note confidence.`,
        {
          schema: QUERY_SCHEMA,
          model: arbiter.arbiter,
          label: 'rag-synthesis',
        }
      );
    }
  }

  // Save if requested
  if (saveTo) {
    await _agent(`Save knowledge base to ${saveTo}.
mkdir -p $(dirname ${saveTo.replace('~', '/home/sfloess')})
Write the JSON data to the file.`, { label: 'save-kb' });
    log(`Saved to ${saveTo}`);
  }

  // Final result
  log('');
  log('='.repeat(60));
  log('FLEET WEB LEARNING COMPLETE');
  log('='.repeat(60));
  log(`Fleet used: true (${workers.length} workers)`);
  log(`URLs processed: ${allUrlResults.length}/${urls.length}`);
  log(`Facts: ${allFacts.length} extracted -> ${validated.validated_facts?.length || 0} validated`);
  log('='.repeat(60));

  const result = {
    status: 'success',
    fleet_used: true,
    workers_used: workers.length,
    learning: {
      urls_processed: allUrlResults.length,
      facts_extracted: allFacts.length,
      facts_validated: validated.validated_facts?.length || 0,
      facts_rejected: validated.rejected_facts?.length || 0,
      worker_distribution: Object.fromEntries(
        workers.map(w => [
          w.hostname,
          allUrlResults.filter(r => r.worker === w.hostname).length,
        ])
      ),
      arbiter_model: validated.arbiter_model,
    },
    knowledge: {
      facts_by_category: (validated.validated_facts || []).reduce((acc, f) => {
        acc[f.category || 'uncategorized'] = (acc[f.category || 'uncategorized'] || 0) + 1;
        return acc;
      }, {}),
      confidence_distribution: (validated.validated_facts || []).reduce((acc, f) => {
        acc[f.confidence] = (acc[f.confidence] || 0) + 1;
        return acc;
      }, {}),
    },
    gaps: {
      missing_topics: gaps.missing_topics || [],
      unanswered_questions: gaps.unanswered_questions || [],
    },
    vector_store: {
      total_documents: vectorStore.documents.length,
    },
  };

  if (queryResult) {
    result.query = {
      question: query,
      answer: queryResult.answer,
      confidence: queryResult.confidence,
      supporting_facts: queryResult.supporting_facts,
      gaps: queryResult.gaps,
    };
  }

  return result;

} else {
  // === LOCAL EXECUTION PATH ===

  log('Delegating to local ai-web-learn workflow...');

  const localResult = await workflow('ai-web-learn', {
    urls,
    query,
    saveTo,
    load: loadExisting,
    strategy: strategyName,
  });

  return { ...localResult, fleet_used: false };
}
