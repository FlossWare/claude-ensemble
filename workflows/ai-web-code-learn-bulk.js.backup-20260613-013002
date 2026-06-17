/**
 * ai-web-code-learn-bulk.js
 *
 * Fleet-distributed code repository learning and semantic indexing.
 * Use case: 50+ open-source repositories analyzed and indexed in parallel.
 *
 * Multi-session orchestration:
 *   - Controller: Discovers repositories to learn from (GitHub, GitLab, local)
 *   - Splits repos into 3 batches
 *   - Worker-01-03: Clone, analyze, and index each repo via independent session
 *   - Workers call ai-web-code-learn for their repo batch
 *   - Workers output embeddings JSON
 *   - Controller merges embeddings into single vector DB
 *
 * Per-repository timing:
 *   - Clone from GitHub: 10-30s
 *   - Discover files: 5s
 *   - AST parse and semantic analysis: 2-3 min
 *   - Generate embeddings: 1-2 min
 *   - Total: ~5-6 min per repo
 *   - Sequential (50 repos): 4+ hours
 *   - Fleet (3 workers): 1.5 hours
 *
 * Embedding strategy:
 *   - Each worker generates function/class embeddings locally
 *   - Worker outputs JSON with embeddings
 *   - Controller merges and inserts into ChromaDB
 *
 * Use cases:
 *   - Build semantic search index across 50 popular libraries
 *   - Learn patterns from open-source projects
 *   - Architecture analysis across multiple codebases
 */

export const meta = {
  name: 'ai-web-code-learn-bulk',
  description: 'Fleet-distributed code learning - analyze 50+ repositories with semantic indexing',
  whenToUse: 'When you need to learn from multiple open-source projects and build cross-repo semantic index',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'Repository Discovery', detail: 'Find or validate repositories to analyze' },
    { title: 'Batch Distribution', detail: 'Split repositories across workers' },
    { title: 'Parallel Analysis', detail: 'Each worker clones and analyzes repos' },
    { title: 'Embedding Merge', detail: 'Collect embeddings from all workers' },
    { title: 'Cross-Repo Index', detail: 'Build semantic search index' },
  ],
};

import { bulkOrchestrate, mergeEmbeddingResults } from '../shared/fleet-bulk-orchestration.js';
import fs from 'fs';
import path from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const DRY_RUN = args?.dryRun === true;
const TEMP_CLONE_DIR = args?.tempDir || '/tmp/code-learn-bulk';
const CHROMA_HOST = args?.chromaHost || 'localhost';
const CHROMA_PORT = args?.chromaPort || 8000;
const COLLECTION_NAME = args?.collection || 'code-learning';

log('');
log('='.repeat(70));
log('Bulk Code Repository Learning - Fleet Distribution');
log('='.repeat(70));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`Temp clone dir: ${TEMP_CLONE_DIR}`);
log(`ChromaDB: ${CHROMA_HOST}:${CHROMA_PORT}`);
log(`Collection: ${COLLECTION_NAME}`);
if (DRY_RUN) log('DRY RUN MODE');
log('');

// ============================================================================
// PHASE 1: Input Validation - Repositories
// ============================================================================

phase('Input Validation');

// Repositories can come from:
// 1. args.repos - Array of { url, name } or { path } for local repos
// 2. args.repoFile - File with one repo URL per line
// 3. args.searchTerm - Search GitHub for popular repos matching term

let repos = [];

if (args?.repos && Array.isArray(args.repos)) {
  repos = args.repos;
  log(`Using ${repos.length} repositories from args.repos`);
} else if (args?.repoFile && fs.existsSync(args.repoFile)) {
  const repoContent = fs.readFileSync(args.repoFile, 'utf8');
  repos = repoContent
    .split('\n')
    .map(line => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) return null;

      // Parse: url [name]
      const [url, ...nameParts] = trimmed.split(' ');
      return {
        url,
        name: nameParts.join(' ') || url.split('/').pop().replace(/\.git$/, ''),
      };
    })
    .filter(Boolean);
  log(`Loaded ${repos.length} repositories from ${args.repoFile}`);
} else if (args?.searchTerm) {
  log(`Searching GitHub for popular repos matching: ${args.searchTerm}`);

  const searchResult = await agent(`Search GitHub for popular repositories matching: ${args.searchTerm}

Return top 10-20 most popular repositories (by stars).
Focus on:
- Well-maintained projects
- Large codebases suitable for learning
- Diverse programming languages

Return: { repos: [{ url, stars, description, language }] }`, {
    label: 'Search GitHub',
    schema: {
      type: 'object',
      properties: {
        repos: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              url: { type: 'string' },
              name: { type: 'string' },
              stars: { type: 'number' },
              language: { type: 'string' },
            },
            required: ['url', 'name']
          }
        }
      }
    }
  });

  repos = searchResult.repos || [];
  log(`Found ${repos.length} repositories`);
} else if (args?.localDir) {
  // Local repositories
  log(`Discovering local repositories in: ${args.localDir}`);

  const localReposResult = await agent(`Find all git repositories in directory.

Directory: ${args.localDir}

Find all .git directories and return parent paths.

Return: { repos: [{ path, name }] }`, {
    label: 'Discover Local Repos',
    schema: {
      type: 'object',
      properties: {
        repos: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              path: { type: 'string' },
              name: { type: 'string' },
            }
          }
        }
      }
    }
  });

  repos = localReposResult.repos || [];
  log(`Found ${repos.length} local repositories`);
} else {
  return {
    status: 'error',
    message: 'No repositories specified. Provide args.repos, args.repoFile, args.searchTerm, or args.localDir',
    examples: {
      'Array of repos': {
        repos: [
          { url: 'https://github.com/expressjs/express.git', name: 'express' },
          { url: 'https://github.com/lodash/lodash.git', name: 'lodash' },
        ]
      },
      'File with URLs': { repoFile: '/path/to/repos.txt' },
      'Search GitHub': { searchTerm: 'machine learning' },
      'Local repositories': { localDir: '~/projects' },
    }
  };
}

if (repos.length === 0) {
  return {
    status: 'error',
    message: 'No repositories found',
  };
}

log(`Total repositories to analyze: ${repos.length}`);
log('Sample repositories:');
repos.slice(0, 3).forEach(r => {
  const name = r.name || r.url?.split('/').pop();
  const stars = r.stars ? ` (${r.stars} stars)` : '';
  log(`  - ${name}${stars}`);
});
if (repos.length > 3) log(`  ... and ${repos.length - 3} more`);
log('');

// ============================================================================
// PHASE 2: Bulk Orchestration
// ============================================================================

phase('Fleet Orchestration');

const orchestrationResult = await bulkOrchestrate({
  skill: 'ai-web-code-learn-bulk',
  items: repos,
  workerScript: 'workflows/ai-web-code-learn.js',
  mergeStrategy: mergeEmbeddingResults,
  itemSerializer: (repos) => JSON.stringify({
    repos,
    temp_dir: TEMP_CLONE_DIR,
  }),
  resultDeserializer: (stdout) => {
    try {
      return JSON.parse(stdout);
    } catch {
      return { embeddings: [], total_chunks: 0 };
    }
  },
  log,
  fleetOptions: { capabilities: ['code-analysis'] },
  minWorkers: 2,
  timeout: 900000, // 15 min per batch (repos can be large)
  dryRun: DRY_RUN,
  useWeightedDistribution: true,
});

log('');

if (orchestrationResult.status === 'failed') {
  return {
    status: 'failed',
    message: 'All workers failed',
    reposProcessed: orchestrationResult.itemsProcessed,
    totalRepos: orchestrationResult.totalItems,
    errors: orchestrationResult.errors,
  };
}

// ============================================================================
// PHASE 3: ChromaDB Integration
// ============================================================================

phase('ChromaDB Integration');

const embeddingData = orchestrationResult.result || { embeddings: [], total_chunks: 0 };
const totalChunks = embeddingData.total_chunks || embeddingData.embeddings?.length || 0;

log(`Total code chunks to index: ${totalChunks}`);

if (totalChunks === 0) {
  log('Warning: No code embeddings generated');
}

// Insert embeddings into ChromaDB
const insertResult = await agent(`Insert code embeddings into ChromaDB.

ChromaDB location: ${CHROMA_HOST}:${CHROMA_PORT}
Collection name: ${COLLECTION_NAME}

Embeddings data:
${JSON.stringify(embeddingData, null, 2).slice(0, 5000)}

Steps:
1. Connect to ChromaDB
2. Get or create collection "${COLLECTION_NAME}"
3. Insert embeddings with metadata (repo, file, function/class name)
4. Verify insertion

Return: { success, chunks_inserted, collection_size }`, {
  label: 'ChromaDB Insert',
  schema: {
    type: 'object',
    properties: {
      success: { type: 'boolean' },
      chunks_inserted: { type: 'number' },
      collection_size: { type: 'number' },
    }
  }
});

log(`Inserted: ${insertResult.chunks_inserted} code chunks`);
log(`Collection size: ${insertResult.collection_size}`);
log('');

// ============================================================================
// PHASE 4: Build Cross-Repository Index
// ============================================================================

phase('Cross-Repository Index');

log('Analyzing patterns across repositories...');

const indexResult = await agent(`Extract architecture patterns from indexed code.

Collection: ${COLLECTION_NAME}
Total chunks: ${totalChunks}

Analyze:
1. Most common patterns/functions across repos
2. Language distribution
3. Architecture styles (MVC, microservices, etc.)
4. Integration opportunities between repos

Return: { patterns: [...], languages: [...], architectures: [...] }`, {
  label: 'Build Cross-Repo Index',
  schema: {
    type: 'object',
    properties: {
      patterns: { type: 'array', items: { type: 'string' } },
      languages: { type: 'array', items: { type: 'string' } },
      architectures: { type: 'array', items: { type: 'string' } },
    }
  }
});

log(`Patterns identified: ${indexResult.patterns?.length || 0}`);
log(`Languages: ${(indexResult.languages || []).join(', ')}`);
log(`Architecture styles: ${(indexResult.architectures || []).join(', ')}`);
log('');

// ============================================================================
// PHASE 5: Save Metadata
// ============================================================================

phase('Save Metadata');

const reportDir = path.join(process.cwd(), '.claude', 'bulk-reports');
if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

// Save index metadata
const indexFile = path.join(reportDir, `code-learn-${Date.now()}.json`);
const metadata = {
  timestamp: new Date().toISOString(),
  totalRepos: orchestrationResult.totalItems,
  reposProcessed: orchestrationResult.itemsProcessed,
  totalCodeChunks: totalChunks,
  chromadb: {
    host: CHROMA_HOST,
    port: CHROMA_PORT,
    collection: COLLECTION_NAME,
    size: insertResult.collection_size,
  },
  patterns: indexResult.patterns || [],
  languages: indexResult.languages || [],
  architectures: indexResult.architectures || [],
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  status: orchestrationResult.status,
  errors: orchestrationResult.errors,
};

fs.writeFileSync(indexFile, JSON.stringify(metadata, null, 2));
log(`Metadata saved: ${indexFile}`);

// Save repository list
const reposListFile = path.join(reportDir, `code-learn-repos-${Date.now()}.json`);
fs.writeFileSync(reposListFile, JSON.stringify(repos, null, 2));
log(`Repository list saved: ${reposListFile}`);
log('');

log('='.repeat(70));
log('BULK CODE REPOSITORY LEARNING COMPLETE');
log('='.repeat(70));
log(`Repositories processed: ${orchestrationResult.itemsProcessed}/${orchestrationResult.totalItems}`);
log(`Code chunks indexed: ${totalChunks}`);
log(`ChromaDB collection: ${COLLECTION_NAME} (${insertResult.collection_size} chunks)`);
log(`Architecture patterns: ${indexResult.patterns?.length || 0}`);
log(`Fleet used: ${orchestrationResult.fleetUsed ? 'YES' : 'NO'}`);
log(`Workers: ${orchestrationResult.workersUsed}`);
log('='.repeat(70));

return {
  status: orchestrationResult.status,
  totalRepos: orchestrationResult.totalItems,
  reposProcessed: orchestrationResult.itemsProcessed,
  codeChunksIndexed: totalChunks,
  chromadbCollection: COLLECTION_NAME,
  chromadbSize: insertResult.collection_size,
  patternsIdentified: indexResult.patterns || [],
  languages: indexResult.languages || [],
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  indexFile,
  reposListFile,
  errors: orchestrationResult.errors,
};
