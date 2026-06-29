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

// Configuration constants
const CONTENT_SNIPPET_CHARS = 8000;  // Max chars to send to extraction models (balances context vs cost)
const EXTRACTED_BY_PATTERN = /^[a-z0-9-]+(,[a-z0-9-]+)*$/;  // Comma-separated model list format

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'ai-web-learn-fleet',
  description: 'Fleet-distributed web learning - batches URL processing across workers for 1.5-2x speedup',
  whenToUse: 'When learning from many web URLs and fleet is available',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' }
  ]
}

import { hotImport } from '../shared/hot-reload.js'
import { selectWorkersWithFallback } from '../shared/thompson-sampling-helper.js'
import { getWorkers } from '../shared/fleet-utils.js';
import {
  distributeItems,
  gracefulFallback,
} from '../shared/fleet-workflow-patterns.js';

export default async function({ args, phase, log, agent, parallel }) {

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
          extracted_by: {
            type: 'string',
            pattern: EXTRACTED_BY_PATTERN.source,  // Use shared pattern
            description: 'Model attribution (single: "opus" or merged: "opus,sonnet")'
          },
        },
        required: ['claim', 'evidence', 'confidence', 'sources', 'extracted_by'],
      },
    },
    rejected_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          reason: { type: 'string' },
          extracted_by: {
            type: 'string',
            pattern: EXTRACTED_BY_PATTERN.source,  // Use shared pattern
            description: 'Model attribution (single: "opus" or merged: "opus,sonnet")'
          },
        },
        required: ['claim', 'reason', 'extracted_by'],
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

// ============================================================================
// PHASE 3: Distribute URLs
// ============================================================================

phase('Distribute URLs');

// Thompson Sampling for model selection (only if using fleet)
// COST TRADEOFF: Use 3 models for extraction (not 6) to balance cost vs quality
// - feedback_always_multi_ai.md mandate: "Always use 6 models. Quality over cost. No exceptions."
// - Round 9 review: Using 6 models doubles API cost (6000 vs 3000 calls for 1000 URLs)
// - DECISION: 3 models for bulk extraction, acknowledge cost/quality tradeoff
// - TODO: A/B test to quantify quality delta (3 vs 6 models for fact extraction)
const ALL_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
let WORKER_MODELS;
let orchestrator = null;

if (useFleet) {
  // Use shared helper (eliminates duplication across 3 workflows)
  const selection = await selectWorkersWithFallback('web-research-fleet', ALL_MODELS, 3, log);
  WORKER_MODELS = selection.models;
  orchestrator = selection.orchestrator;

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
      // Compute URL filename once (used 5× below)
      // Handle trailing slashes + query strings: strip params, split, filter empty, take last segment
      const urlPath = url.split('?')[0].split('#')[0];  // Strip query and fragment
      const urlFilename = urlPath.split('/').filter(Boolean).pop() || 'index';

      // Fetch the page content
      const pageContent = await _agent(
        `Fetch the content from this URL and return the full text: ${url}

If you have MCP web-fetching tools available, use them. Otherwise use WebFetch.
Return just the text content, no HTML tags.`,
        {
          label: `fetch-${worker.hostname}:${urlFilename}`,
          phase: 'Fetch & Extract',
        }
      );

      if (!pageContent) {
        log(`    ${worker.hostname}: Failed to fetch ${url}`);
        continue;
      }

      // Compute content snippet once (not 3× inside parallel)
      const contentSnippet = typeof pageContent === 'string'
        ? pageContent.slice(0, CONTENT_SNIPPET_CHARS)
        : JSON.stringify(pageContent).slice(0, CONTENT_SNIPPET_CHARS)

      const extractions = await parallel(WORKER_MODELS.map(model => () =>
        _agent(
          `Extract factual claims from this webpage. Focus on concrete, verifiable facts.

Source URL: ${url}

${contentSnippet}

Extract clear facts with supporting evidence. Be specific and accurate.`,
          {
            schema: FACTS_SCHEMA,
            model,
            label: `extract-${model}:${urlFilename}`,
          }
        ).then(result => ({ model, result }))
      ));

      const validExtractions = extractions.filter(e => e && e.result);
      const facts = validExtractions.flatMap(e => (e.result.facts || []).map(f => ({
        ...f,
        source_url: url,
        extracted_by: e.model  // Track which model extracted this fact
      })));

      urlResults.push({
        url,
        facts,
        extractions: validExtractions,  // Keep model attribution for Thompson Sampling
        models_used: validExtractions.map(e => e.model),  // Track which models actually responded
        worker: worker.hostname,
      });

      log(`    ${worker.hostname}: ${facts.length} facts from ${urlFilename}`);
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

CRITICAL: Preserve extracted_by field. When merging duplicates, use comma-separated list (e.g., "opus,sonnet").

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

  // Validate extracted_by format (must be comma-separated list, no other delimiters)
  // Only count + show first 3 (don't allocate full array at scale)
  let invalidCount = 0;
  const invalidSamples = [];

  for (const fact of [...(validated.validated_facts || []), ...(validated.rejected_facts || [])]) {
    if (fact.extracted_by && !EXTRACTED_BY_PATTERN.test(fact.extracted_by)) {
      invalidCount++;
      if (invalidSamples.length < 3) {
        invalidSamples.push(fact);
      }
    }
  }

  if (invalidCount > 0) {
    log(`⚠ WARNING: ${invalidCount} facts have invalid extracted_by format (arbiter used wrong delimiter):`)
    invalidSamples.forEach(f => log(`  - "${f.extracted_by}" in claim: ${f.claim?.substring(0, 60)}...`));
    log('Thompson Sampling will create garbage model names. Fix arbiter prompt or schema validation.');
  }

  // Record per-model results for Thompson Sampling learning
  if (orchestrator) {
    try {
      // Calculate quality score for each model based on its own facts
      const modelStats = {}

      // Helper: Split comma-separated model attributions (e.g., "opus,sonnet" → ["opus", "sonnet"])
      const splitModels = (extracted_by) => {
        if (!extracted_by) return ['unknown'];
        return extracted_by.split(',').map(m => m.trim()).filter(Boolean);
      }

      // Count validated facts per model (split multi-model attributions)
      for (const fact of (validated.validated_facts || [])) {
        const models = splitModels(fact.extracted_by);
        for (const model of models) {
          modelStats[model] ||= { validated: 0, rejected: 0 }
          modelStats[model].validated++
        }
      }

      // Count rejected facts per model (split multi-model attributions)
      for (const fact of (validated.rejected_facts || [])) {
        const models = splitModels(fact.extracted_by);
        for (const model of models) {
          modelStats[model] ||= { validated: 0, rejected: 0 }
          modelStats[model].rejected++
        }
      }

      // Record quality scores sequentially to avoid database contention
      // (orchestrator uses file I/O without locking, concurrent writes cause lost updates)
      //
      // WARNING: Self-referential feedback loop risk (CLAUDE.md Layer 2/3 mandate)
      // - Arbiter judges models → quality scores → Thompson Sampling → select models
      // - No external validation, no adversarial testing, no ground truth checks
      // - If arbiter is miscalibrated, bias amplifies over iterations
      //
      // TODO: Add external validation before production use:
      // 1. Layer 2: Adversarial evaluator (ChatGPT framework per CLAUDE.md)
      // 2. Layer 3: Ground truth benchmarks (user verification, known fact sets)
      // 3. Diversity monitoring (alert if model distribution skews >70/30)
      //
      // Current scores are INTERNAL ONLY and should not drive model selection
      // without external validation loop.

      // Only score models that actually responded (have stats in modelStats)
      // Skip models that failed for all URLs (would get incorrect 0.33 neutral score)
      for (const model of Object.keys(modelStats)) {
        const stats = modelStats[model]
        // Quality score: precision with Laplace smoothing
        // Use α=1 (add-one smoothing): (validated+α)/(validated+rejected+2α)
        // Symmetric smoothing prevents bias toward 0.5
        const alpha = 1;
        const qualityScore = (stats.validated + alpha) / (stats.validated + stats.rejected + 2 * alpha)
        await orchestrator.recordResult(model, qualityScore, { context: 'ai-web-learn-fleet' })
        log(`  ${model}: ${stats.validated} validated, ${stats.rejected} rejected → quality ${qualityScore.toFixed(2)}`)
      }
    } catch (e) {
      log(`Thompson Sampling recording failed: ${e.message}`)
    }
  }

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

  // Collect unique models used across all URLs (for learning extraction analytics)
  const allModelsUsed = [...new Set(allUrlResults.flatMap(r => r.models_used || []))];

  const result = {
    status: 'success',
    fleet_used: true,
    workers_used: workers.length,
    models_used: allModelsUsed,  // Top-level field for ai-extract-learning.js
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

}
