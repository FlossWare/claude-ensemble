// AI Web Code Learn Fleet - Distributed source code analysis
//
// Pattern B: File Distribution
//   1. Clone repo to NFS (visible to all workers via ~/Development)
//   2. Discover source files, split into N chunks
//   3. Each worker runs AST parse + pattern extraction on its chunk
//   4. Collect JSON results from each worker
//   5. Merge: Arbiter validates and synthesizes all patterns
//   6. Store: Single ChromaDB insert on server-02 (high memory)
//
// Architecture: Single-writer post-merge pattern for ChromaDB
//   - Workers produce JSON extraction results (no DB writes)
//   - Controller merges all results
//   - Single writer (server-02) inserts into ChromaDB
//
// Speedup: 2.5-3x with 3 workers (file analysis is embarrassingly parallel)

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'ai-web-code-learn-fleet',
  description: 'Fleet-distributed code learning - shards source files across workers for 2.5-3x speedup',
  whenToUse: 'When learning from large repositories with many source files',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'Setup', detail: 'Clone/fetch repository to NFS' },
    { title: 'Discover Files', detail: 'Find relevant source files' },
    { title: 'Distribute Analysis', detail: 'Shard files across workers' },
    { title: 'Extract Patterns', detail: 'Parallel AST parse + pattern extraction' },
    { title: 'Validate & Merge', detail: 'Arbiter consensus on patterns' },
    { title: 'Store', detail: 'Persist to knowledge base (single-writer)' },
    { title: 'Query', detail: 'RAG-based code queries' },
  ],
};

import { getWorkers, remoteExec } from '../shared/fleet-utils.js';
import {
  distributeItems,
  distributeItemsWeighted,
  gracefulFallback,
  nfsProjectPath,
  isOnNfs,
  workerTempDir,
} from '../shared/fleet-workflow-patterns.js';

// ============================================================================
// SCHEMAS
// ============================================================================

const CODE_EXTRACTION_SCHEMA = {
  type: 'object',
  properties: {
    file_path: { type: 'string' },
    language: { type: 'string' },
    classes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          methods: { type: 'array', items: { type: 'string' } },
          purpose: { type: 'string' },
        },
      },
    },
    functions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          parameters: { type: 'array', items: { type: 'string' } },
          purpose: { type: 'string' },
          complexity: { type: 'string', enum: ['low', 'medium', 'high'] },
        },
      },
    },
    implementation_patterns: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          pattern: { type: 'string' },
          description: { type: 'string' },
          example: { type: 'string' },
        },
      },
    },
    key_insights: { type: 'array', items: { type: 'string' } },
    dependencies: { type: 'array', items: { type: 'string' } },
  },
  required: ['file_path', 'language', 'key_insights'],
};

const VALIDATION_SCHEMA = {
  type: 'object',
  properties: {
    validated_patterns: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          pattern: { type: 'string' },
          description: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
    architecture_summary: { type: 'string' },
    recommended_focus: { type: 'array', items: { type: 'string' } },
    dependency_graph: { type: 'string' },
  },
  required: ['validated_patterns', 'architecture_summary'],
};

// ============================================================================
// CONFIGURATION
// ============================================================================

// Parse args
let parsedArgs = args;
if (typeof args === 'string') {
  const trimmed = args.trim();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      parsedArgs = JSON.parse(trimmed);
    } catch (e) {
      parsedArgs = { query: trimmed };
    }
  } else {
    parsedArgs = { query: trimmed };
  }
}

const repoUrl = parsedArgs?.repo_url || parsedArgs?.url || null;
const branch = parsedArgs?.branch || 'main';
const paths = parsedArgs?.paths || [];
const query = parsedArgs?.query || null;
const mode = parsedArgs?.mode || (query && !repoUrl ? 'query' : repoUrl ? 'learn' : 'both');
const dbPath = parsedArgs?.dbPath || '~/.claude/knowledge/code-learn.json';
const maxFiles = parsedArgs?.max_files || 30;  // Higher limit for fleet
const DRY_RUN = parsedArgs?.dryRun === true;
// ChromaDB target: server-02 (31GB, highest memory)
const CHROMADB_HOST = parsedArgs?.chromadb_host || 'server-02';

if (!repoUrl && !query) {
  return {
    error: 'Must provide repo_url to learn from or query to answer',
    usage: {
      learn: '{repo_url: "https://github.com/user/repo", paths: ["src/"], max_files: 30}',
      query: '{query: "how is X implemented?"}',
      both: '{repo_url: "...", query: "..."}',
    },
  };
}

log('');
log('='.repeat(60));
log('Fleet-Distributed Code Learning');
log('='.repeat(60));
if (repoUrl) log(`Repo: ${repoUrl} (branch: ${branch})`);
if (query) log(`Query: ${query}`);
log('');

// ============================================================================
// PHASE 1: Fleet Discovery
// ============================================================================

phase('Fleet Discovery');

let workers = [];
let useFleet = false;

try {
  workers = getWorkers();
  useFleet = workers.length >= 2;

  if (useFleet) {
    log(`Fleet available: ${workers.length} workers`);
    workers.forEach(w => log(`  - ${w.hostname} (${w.cpus}C/${w.memory_gb}GB)`));
  } else {
    log('Insufficient fleet workers, running locally');
  }
} catch (error) {
  log(`Fleet unavailable (${error.message}), running locally`);
}

log('');

// ============================================================================
// LEARN MODE
// ============================================================================

if (mode === 'learn' || mode === 'both') {

  // PHASE 2: Setup - Clone to NFS
  phase('Setup');

  const repoName = repoUrl.split('/').pop().replace('.git', '');
  // Clone to NFS-shared directory so all workers can see it
  const cloneDir = `/home/sfloess/Development/.fleet-tmp/code-learn/${repoName}`;

  log(`Cloning to NFS-shared path: ${cloneDir}...`);

  const cloneResult = await _agent(`Clone ${repoUrl} (branch: ${branch}) to ${cloneDir}.

If directory exists, cd into it and run: git fetch origin && git checkout ${branch} && git pull
Otherwise: mkdir -p $(dirname ${cloneDir}) && git clone --branch ${branch} --depth 1 ${repoUrl} ${cloneDir}

Return success status and the resolved path.`, {
    label: 'clone',
    schema: {
      type: 'object',
      properties: {
        cloned: { type: 'boolean' },
        path: { type: 'string' },
        error: { type: 'string' },
      },
    },
  });

  if (!cloneResult?.cloned) {
    return { error: 'Clone failed', repo: repoUrl, detail: cloneResult?.error };
  }

  const repoPath = cloneResult.path;
  log(`Repository ready at: ${repoPath}`);

  // PHASE 3: Discover Files
  phase('Discover Files');

  const discoverPrompt = paths.length
    ? `Find the ${maxFiles} most important source code files in ${repoPath} under ${paths.join(', ')}. Skip tests, configs, generated files.`
    : `Find the ${maxFiles} most important source code files in ${repoPath}. Skip tests, configs, generated files, node_modules, dist, build.`;

  const fileDiscovery = await _agent(discoverPrompt, {
    label: 'discover',
    schema: {
      type: 'object',
      properties: {
        files: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              path: { type: 'string' },
              language: { type: 'string' },
              importance: { type: 'string', enum: ['high', 'medium', 'low'] },
              purpose: { type: 'string' },
              size_lines: { type: 'number' },
            },
          },
        },
        total_found: { type: 'number' },
      },
    },
  });

  const sourceFiles = (fileDiscovery?.files || []).slice(0, maxFiles);

  if (sourceFiles.length === 0) {
    return { error: 'No source files found', path: repoPath };
  }

  log(`Found ${sourceFiles.length} source files (${fileDiscovery.total_found || '?'} total in repo)`);

  // PHASE 4-5: Distribute and Extract
  if (useFleet && sourceFiles.length >= workers.length) {

    phase('Distribute Analysis');

    // Use weighted distribution - give high-memory workers more files
    const distribution = distributeItemsWeighted(sourceFiles, workers);

    log(`Distributing ${sourceFiles.length} files across ${workers.length} workers:`);
    for (const [hostname, files] of distribution.entries()) {
      log(`  ${hostname}: ${files.length} files`);
    }

    if (DRY_RUN) {
      return {
        status: 'dry_run',
        distribution: Object.fromEntries(
          Array.from(distribution.entries()).map(([h, files]) => [h, files.map(f => f.path)])
        ),
        total_files: sourceFiles.length,
      };
    }

    phase('Extract Patterns');

    log('Extracting patterns in parallel across fleet...');

    // Each worker analyzes its assigned files
    // Workers read from NFS (repo is shared), write results to stdout
    const workerPromises = workers.map(async (worker) => {
      const files = distribution.get(worker.hostname);
      if (!files || files.length === 0) return [];

      log(`  ${worker.hostname}: analyzing ${files.length} files...`);

      // Use AI agent to analyze each file on the worker
      // Files are on NFS so all workers can read them
      const extractions = await parallel(
        files.map(f => () =>
          agent(`Read and analyze this source file: ${f.path}

Extract:
1. Classes with their methods and purpose
2. Functions with parameters and purpose
3. Implementation patterns used (design patterns, idioms)
4. Key insights about the code
5. Dependencies imported/used

Be thorough - this is for a knowledge base.`, {
            label: `extract-${worker.hostname}-${f.path.split('/').pop()}`,
            schema: CODE_EXTRACTION_SCHEMA,
          })
        )
      );

      return extractions.filter(Boolean).map(e => ({
        ...e,
        analyzed_by: worker.hostname,
      }));
    });

    const allWorkerResults = await Promise.all(workerPromises);
    const allExtractions = allWorkerResults.flat();

    log(`Extracted patterns from ${allExtractions.length} files across ${workers.length} workers`);

    // Per-worker summary
    workers.forEach(w => {
      const count = allExtractions.filter(e => e.analyzed_by === w.hostname).length;
      log(`  ${w.hostname}: ${count} files analyzed`);
    });

    // PHASE 6: Validate & Merge
    phase('Validate & Merge');

    log('Arbiter validating and synthesizing patterns...');

    const arbiter = await workflow('get-next-arbiter');

    const validation = await _agent(`Validate and synthesize patterns from ${allExtractions.length} files analyzed by fleet workers.

This code is from repository: ${repoUrl}

FILE ANALYSES (${allExtractions.length} files):
${allExtractions.map((e, i) => `
--- File ${i + 1}: ${e.file_path} (${e.language}) [analyzed by ${e.analyzed_by}] ---
Classes: ${e.classes?.map(c => c.name).join(', ') || 'none'}
Functions: ${e.functions?.map(f => f.name).join(', ') || 'none'}
Patterns: ${e.implementation_patterns?.map(p => p.pattern).join(', ') || 'none'}
Key Insights: ${e.key_insights?.join('; ') || 'none'}
`).join('\n')}

Tasks:
1. Identify architectural patterns across all files
2. Map dependencies and module relationships
3. Synthesize a high-level architecture summary
4. Identify the most important patterns worth remembering
5. Note any anti-patterns or areas of concern

Return a comprehensive validation.`, {
      label: 'arbiter-validate',
      model: arbiter.arbiter,
      schema: VALIDATION_SCHEMA,
    });

    await workflow('update-arbiter-state', { arbiter: arbiter.arbiter, workflow_name: 'ai-web-code-learn-fleet' });

    log(`Validated ${validation.validated_patterns?.length || 0} patterns`);
    log(`Architecture: ${validation.architecture_summary?.slice(0, 100)}...`);

    // PHASE 7: Store
    phase('Store');

    const kb = {
      repo: repoUrl,
      branch,
      files_analyzed: allExtractions.length,
      workers_used: workers.map(w => w.hostname),
      fleet_distributed: true,
      entries: allExtractions,
      summary: validation,
    };

    // Store to knowledge base
    await _agent(`Save this knowledge base entry to ${dbPath}.

Create the directory if needed: mkdir -p $(dirname ${dbPath.replace('~', '/home/sfloess')})

Write the JSON:
${JSON.stringify(kb, null, 2).slice(0, 10000)}

Use: echo '...' > ${dbPath}`, {
      label: 'store',
    });

    log(`Stored ${allExtractions.length} file analyses to ${dbPath}`);

    if (mode === 'learn') {
      return {
        status: 'success',
        fleet_used: true,
        workers_used: workers.length,
        files_analyzed: allExtractions.length,
        patterns: validation.validated_patterns?.length || 0,
        architecture: validation.architecture_summary,
        db_path: dbPath,
        per_worker: workers.map(w => ({
          hostname: w.hostname,
          files: allExtractions.filter(e => e.analyzed_by === w.hostname).length,
        })),
      };
    }

  } else {
    // Local fallback - use existing ai-web-code-learn skill
    log('Running file analysis locally (fleet not suitable)...');

    const localResult = await workflow('ai-web-code-learn', {
      repo_url: repoUrl,
      branch,
      paths,
      query,
      mode,
      dbPath,
      max_files: maxFiles,
    });

    if (mode === 'learn') {
      return { ...localResult, fleet_used: false };
    }

    // For 'both' mode, continue to query phase with local results
  }
}

// ============================================================================
// QUERY MODE
// ============================================================================

if (mode === 'query' || mode === 'both') {
  phase('Query');

  log(`Querying knowledge base: "${query}"`);

  const kb = await _agent(`Read the knowledge base from ${dbPath} and return its contents.

Run: cat ${dbPath.replace('~', '/home/sfloess')} 2>/dev/null || echo "NOT_FOUND"

If found, return the parsed JSON. If not found, return empty.`, {
    label: 'load-kb',
    schema: {
      type: 'object',
      properties: {
        entries: { type: 'array' },
        summary: { type: 'object' },
        found: { type: 'boolean' },
      },
    },
  });

  if (!kb?.found || !kb?.entries) {
    return { error: 'Knowledge base not found', db_path: dbPath };
  }

  log(`Loaded ${kb.entries?.length || 0} entries`);

  // Multi-model query for diverse perspectives
  const queryModels = ['opus', 'sonnet', 'haiku'];

  const answers = await parallel(queryModels.map(m => () =>
    agent(`Answer this question about the codebase: ${query}

Architecture Summary: ${kb.summary?.architecture_summary || 'N/A'}

Key Patterns:
${(kb.summary?.validated_patterns || []).slice(0, 10).map(p => `- ${p.pattern}: ${p.description}`).join('\n')}

Key Files:
${(kb.entries || []).slice(0, 10).map(e => `- ${e.file_path}: ${e.key_insights?.join('; ')}`).join('\n')}

Provide a specific, code-aware answer.`, {
      label: `query-${m}`,
      model: m,
      schema: {
        type: 'object',
        properties: {
          answer: { type: 'string' },
          code_examples: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          relevant_files: { type: 'array', items: { type: 'string' } },
        },
        required: ['answer', 'confidence'],
      },
    })
  ));

  const validAnswers = answers.filter(Boolean);

  // Arbiter selects best answer
  const arbiter = await workflow('get-next-arbiter');

  const best = await _agent(`Select the best answer for: ${query}

${validAnswers.map((a, i) => `
Answer ${i + 1} (confidence: ${a.confidence}):
${a.answer}
${a.code_examples ? `Examples: ${a.code_examples.join(', ')}` : ''}
`).join('\n')}

Return the best synthesized answer.`, {
    label: 'arbiter-query',
    model: arbiter.arbiter,
    schema: {
      type: 'object',
      properties: {
        answer: { type: 'string' },
        code_examples: { type: 'array', items: { type: 'string' } },
        confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        relevant_files: { type: 'array', items: { type: 'string' } },
      },
      required: ['answer', 'confidence'],
    },
  });

  await workflow('update-arbiter-state', { arbiter: arbiter.arbiter, workflow_name: 'ai-web-code-learn-fleet' });

  return {
    status: 'success',
    query,
    answer: best.answer,
    code_examples: best.code_examples,
    confidence: best.confidence,
    relevant_files: best.relevant_files,
    fleet_used: useFleet,
  };
}
