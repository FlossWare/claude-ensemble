export const meta = {
  name: 'deep-code-analysis',
  description: 'Deep code analysis with chunking, vector embeddings, and knowledge graph',
  whenToUse: 'When you need to analyze code repositories and store structured knowledge',
  phases: [
    { title: 'Discovery', detail: 'Find all relevant files in repositories' },
    { title: 'Chunking', detail: 'Parse and chunk code by class/method/function' },
    { title: 'Vectorization', detail: 'Generate 384-dim embeddings per chunk' },
    { title: 'Storage', detail: 'Store in PostgreSQL pgvector' },
    { title: 'GraphDB', detail: 'Build knowledge graph in Neo4j' },
    { title: 'Summary', detail: 'Generate analysis summary' },
  ],
}

// Import storage adapters
import { getWorkflowStorage } from '../shared/workflow-storage-adapter.js'
import { Pool } from 'pg'
import { exec } from 'child_process'
import { promisify } from 'util'
import { readFileSync, existsSync } from 'fs'
import { join, relative, dirname, basename, extname } from 'path'
import { glob } from 'glob'

const execAsync = promisify(exec)
const workflowStorage = getWorkflowStorage()

// PostgreSQL connection
const pool = new Pool({
  host: '/var/run/postgresql',
  database: 'learning',
  user: process.env.USER,
})

// ============================================================================
// USAGE:
// const result = await workflow('deep-code-analysis', {
//   repositories: [
//     '/home/sfloess/Development/github/solenopsis/session',
//     '/home/sfloess/Development/github/solenopsis/soap',
//     '/home/sfloess/Development/github/FlossWare/collections-java'
//   ],
//   file_patterns: ['**/*.java', '**/*.cls', '**/*.trigger'],
//   chunk_strategy: 'method',  // 'file' | 'class' | 'method' | 'function'
//   enable_graphdb: true,
//   enable_vectordb: true
// })
// ============================================================================

const workflowStartTime = Date.now()
const workflowExecutionId = `deep_code_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

// Parse arguments
const repositories = args.repositories || []
const filePatterns = args.file_patterns || ['**/*.java']
const chunkStrategy = args.chunk_strategy || 'method'
const enableGraphDB = args.enable_graphdb !== false
const enableVectorDB = args.enable_vectordb !== false

if (!repositories.length) {
  log('ERROR: No repositories provided')
  return { error: 'No repositories provided' }
}

log('='.repeat(70))
log('DEEP CODE ANALYSIS')
log('='.repeat(70))
log(`Repositories: ${repositories.length}`)
log(`File patterns: ${filePatterns.join(', ')}`)
log(`Chunk strategy: ${chunkStrategy}`)
log(`Vector DB: ${enableVectorDB ? 'enabled' : 'disabled'}`)
log(`Graph DB: ${enableGraphDB ? 'enabled' : 'disabled'}`)
log('')

// ============================================================================
// PHASE 1: Discovery
// ============================================================================

phase('Discovery')

log('Discovering files in repositories...')

const allFiles = []
for (const repo of repositories) {
  log(`  Scanning ${repo}...`)

  for (const pattern of filePatterns) {
    const files = glob.sync(pattern, {
      cwd: repo,
      absolute: true,
      ignore: ['**/target/**', '**/build/**', '**/.git/**', '**/node_modules/**']
    })

    allFiles.push(...files.map(f => ({
      path: f,
      repository: repo,
      relativePath: relative(repo, f),
      extension: extname(f),
      name: basename(f, extname(f))
    })))
  }
}

log(`  Found ${allFiles.length} files total`)
log('')

if (allFiles.length === 0) {
  log('WARNING: No files found matching patterns')
  return { status: 'success', files_found: 0, chunks_created: 0 }
}

// ============================================================================
// PHASE 2: Chunking
// ============================================================================

phase('Chunking')

log(`Chunking ${allFiles.length} files using strategy: ${chunkStrategy}...`)

const chunks = []

// Use parallel workers to chunk files
const chunkWorkers = await parallel(
  allFiles.map((file, idx) => () => {
    return agent(`You are a code chunking expert.

TASK: Parse and chunk this code file according to the strategy: ${chunkStrategy}

FILE: ${file.relativePath}
EXTENSION: ${file.extension}
STRATEGY: ${chunkStrategy}

CODE:
\`\`\`
${readFileSync(file.path, 'utf-8').substring(0, 50000)}
\`\`\`

INSTRUCTIONS:
1. If strategy is 'file': Return entire file as one chunk
2. If strategy is 'class': Split by class definitions
3. If strategy is 'method': Split by method/function definitions (RECOMMENDED)
4. If strategy is 'function': Split by top-level functions only

For each chunk, extract:
- chunk_type: 'file' | 'class' | 'method' | 'function' | 'field' | 'import'
- name: The identifier name (class name, method name, etc.)
- start_line: Line number where chunk starts
- end_line: Line number where chunk ends
- signature: Method signature or class declaration
- code: The actual code (complete, executable if possible)
- dependencies: Array of imports/dependencies referenced
- complexity: Estimated cyclomatic complexity (1-10 scale)

Return structured data as JSON array of chunks.`, {
      label: `chunk-${file.name}`,
      model: 'haiku', // Fast model for chunking
      schema: {
        type: 'object',
        properties: {
          chunks: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                chunk_type: { type: 'string', enum: ['file', 'class', 'method', 'function', 'field', 'import'] },
                name: { type: 'string' },
                start_line: { type: 'number' },
                end_line: { type: 'number' },
                signature: { type: 'string' },
                code: { type: 'string' },
                dependencies: { type: 'array', items: { type: 'string' } },
                complexity: { type: 'number', minimum: 1, maximum: 10 }
              },
              required: ['chunk_type', 'name', 'code']
            }
          },
          total_chunks: { type: 'number' }
        },
        required: ['chunks', 'total_chunks']
      }
    })
  })
)

// Collect all chunks with file metadata
for (let i = 0; i < chunkWorkers.length; i++) {
  const result = chunkWorkers[i]
  const file = allFiles[i]

  if (result && result.chunks) {
    for (const chunk of result.chunks) {
      chunks.push({
        ...chunk,
        file_path: file.path,
        repository: file.repository,
        relative_path: file.relativePath,
        extension: file.extension
      })
    }
  }
}

log(`  Created ${chunks.length} chunks from ${allFiles.length} files`)
log(`  Average: ${(chunks.length / allFiles.length).toFixed(1)} chunks per file`)
log('')

// ============================================================================
// PHASE 3: Vectorization
// ============================================================================

phase('Vectorization')

if (!enableVectorDB) {
  log('Vector DB disabled, skipping vectorization')
} else {
  log(`Generating embeddings for ${chunks.length} chunks...`)

  // Generate embeddings in batches
  const BATCH_SIZE = 50
  const batches = []
  for (let i = 0; i < chunks.length; i += BATCH_SIZE) {
    batches.push(chunks.slice(i, i + BATCH_SIZE))
  }

  log(`  Processing ${batches.length} batches of ${BATCH_SIZE} chunks each...`)

  for (const [batchIdx, batch] of batches.entries()) {
    // Generate embeddings for this batch
    const texts = batch.map(c => `${c.signature || c.name}\n\n${c.code}`)

    try {
      const { generateEmbeddingsBatch } = await import('../shared/workflow-storage-adapter.js')
      const embeddings = await generateEmbeddingsBatch(texts)

      if (embeddings && embeddings.length === batch.length) {
        for (let i = 0; i < batch.length; i++) {
          batch[i].embedding = embeddings[i]
        }
        log(`  ✓ Batch ${batchIdx + 1}/${batches.length} - ${batch.length} embeddings generated`)
      } else {
        log(`  ⚠ Batch ${batchIdx + 1}/${batches.length} - Embedding generation failed, storing without embeddings`)
      }
    } catch (err) {
      log(`  ⚠ Batch ${batchIdx + 1}/${batches.length} - Error: ${err.message}`)
    }
  }

  const withEmbeddings = chunks.filter(c => c.embedding).length
  log(`  Generated ${withEmbeddings}/${chunks.length} embeddings`)
  log('')
}

// ============================================================================
// PHASE 4: Storage (PostgreSQL + pgvector)
// ============================================================================

phase('Storage')

if (!enableVectorDB) {
  log('Vector DB disabled, skipping storage')
} else {
  log('Storing chunks in PostgreSQL...')

  // Create code_chunks table if it doesn't exist
  await pool.query(`
    CREATE SCHEMA IF NOT EXISTS code_analysis;

    CREATE TABLE IF NOT EXISTS code_analysis.chunks (
      id SERIAL PRIMARY KEY,
      repository VARCHAR(512) NOT NULL,
      file_path TEXT NOT NULL,
      relative_path VARCHAR(512),
      chunk_type VARCHAR(50) NOT NULL,
      name VARCHAR(512) NOT NULL,
      signature TEXT,
      code TEXT NOT NULL,
      start_line INTEGER,
      end_line INTEGER,
      dependencies TEXT[],
      complexity INTEGER,
      embedding vector(384),
      metadata JSONB,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_chunks_repository ON code_analysis.chunks(repository);
    CREATE INDEX IF NOT EXISTS idx_chunks_type ON code_analysis.chunks(chunk_type);
    CREATE INDEX IF NOT EXISTS idx_chunks_name ON code_analysis.chunks(name);
    CREATE INDEX IF NOT EXISTS idx_chunks_file ON code_analysis.chunks(file_path);

    CREATE INDEX IF NOT EXISTS idx_chunks_embedding
      ON code_analysis.chunks USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64);
  `)

  log('  Table created/verified')

  // Insert chunks
  let insertedCount = 0
  for (const chunk of chunks) {
    try {
      await pool.query(`
        INSERT INTO code_analysis.chunks
        (repository, file_path, relative_path, chunk_type, name, signature, code,
         start_line, end_line, dependencies, complexity, embedding, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
      `, [
        chunk.repository,
        chunk.file_path,
        chunk.relative_path,
        chunk.chunk_type,
        chunk.name,
        chunk.signature || '',
        chunk.code,
        chunk.start_line || null,
        chunk.end_line || null,
        chunk.dependencies || [],
        chunk.complexity || null,
        chunk.embedding ? JSON.stringify(chunk.embedding) : null,
        JSON.stringify({ extension: chunk.extension })
      ])
      insertedCount++
    } catch (err) {
      log(`  ⚠ Failed to insert chunk ${chunk.name}: ${err.message}`)
    }
  }

  log(`  ✓ Inserted ${insertedCount}/${chunks.length} chunks`)
  log('')
}

// ============================================================================
// PHASE 5: Graph DB (Neo4j)
// ============================================================================

phase('GraphDB')

if (!enableGraphDB) {
  log('Graph DB disabled, skipping')
} else {
  log('Building knowledge graph in Neo4j...')

  // TODO: Neo4j integration
  // For now, just create relationship data structure

  const relationships = []

  // Build dependency graph
  for (const chunk of chunks) {
    if (chunk.dependencies && chunk.dependencies.length > 0) {
      for (const dep of chunk.dependencies) {
        relationships.push({
          from: chunk.name,
          to: dep,
          type: 'DEPENDS_ON',
          repository: chunk.repository
        })
      }
    }

    // Class-method relationships
    if (chunk.chunk_type === 'method' && chunk.signature) {
      const className = chunk.signature.split(/[.( ]/)[ 0]
      if (className && className !== chunk.name) {
        relationships.push({
          from: chunk.name,
          to: className,
          type: 'MEMBER_OF',
          repository: chunk.repository
        })
      }
    }
  }

  log(`  Built ${relationships.length} relationships`)
  log(`  (Neo4j sync pending - see learning/NEO4J_WORKFLOW_SYNC.md)`)
  log('')
}

// ============================================================================
// PHASE 6: Summary
// ============================================================================

phase('Summary')

log('Generating analysis summary...')

const summary = {
  repositories_analyzed: repositories.length,
  files_discovered: allFiles.length,
  chunks_created: chunks.length,
  chunks_with_embeddings: chunks.filter(c => c.embedding).length,
  chunk_types: {},
  repositories_breakdown: {},
  avg_complexity: 0,
  total_lines_analyzed: 0
}

// Count by chunk type
for (const chunk of chunks) {
  summary.chunk_types[chunk.chunk_type] = (summary.chunk_types[chunk.chunk_type] || 0) + 1
  summary.avg_complexity += (chunk.complexity || 0)
  summary.total_lines_analyzed += ((chunk.end_line || 0) - (chunk.start_line || 0) + 1)
}

summary.avg_complexity = summary.avg_complexity / chunks.length

// Count by repository
for (const chunk of chunks) {
  if (!summary.repositories_breakdown[chunk.repository]) {
    summary.repositories_breakdown[chunk.repository] = {
      files: 0,
      chunks: 0,
      types: {}
    }
  }
  summary.repositories_breakdown[chunk.repository].chunks++
  summary.repositories_breakdown[chunk.repository].types[chunk.chunk_type] =
    (summary.repositories_breakdown[chunk.repository].types[chunk.chunk_type] || 0) + 1
}

// Count unique files per repo
for (const file of allFiles) {
  if (summary.repositories_breakdown[file.repository]) {
    summary.repositories_breakdown[file.repository].files++
  }
}

log('  Analysis Summary:')
log(`    Repositories: ${summary.repositories_analyzed}`)
log(`    Files: ${summary.files_discovered}`)
log(`    Chunks: ${summary.chunks_created}`)
log(`    Embeddings: ${summary.chunks_with_embeddings}`)
log(`    Avg Complexity: ${summary.avg_complexity.toFixed(2)}`)
log(`    Total Lines: ${summary.total_lines_analyzed}`)
log('')

for (const [type, count] of Object.entries(summary.chunk_types)) {
  log(`      ${type}: ${count}`)
}
log('')

// ============================================================================
// WORKFLOW STORAGE
// ============================================================================

try {
  const workflowDuration = Date.now() - workflowStartTime

  const dbExecutionId = await workflowStorage.storeExecution({
    workflow_id: workflowExecutionId,
    workflow_name: 'deep-code-analysis',
    task_description: `Analyze ${repositories.length} repositories: ${repositories.map(r => basename(r)).join(', ')}`,
    total_workers: 0,
    total_duration_ms: workflowDuration,
    outcome: 'success',
    metadata: {
      repositories,
      file_patterns: filePatterns,
      chunk_strategy: chunkStrategy,
      summary
    }
  })

  log(`✓ Workflow execution stored (DB ID: ${dbExecutionId})`)
} catch (err) {
  log(`⚠ Workflow storage failed: ${err.message}`)
}

return {
  status: 'success',
  execution_id: workflowExecutionId,
  summary,
  chunks_stored: enableVectorDB ? chunks.length : 0,
  graphdb_enabled: enableGraphDB,
  vectordb_enabled: enableVectorDB
}
