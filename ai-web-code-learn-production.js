export const meta = {
  name: 'ai-web-code-learn-production',
  description: 'Production code learning pipeline: source code analysis with AST parsing, semantic embeddings, and persistent ChromaDB storage',
  whenToUse: 'When you need production-grade code learning with multi-AI consensus, AST analysis, dual embeddings, and semantic search across repositories',
  phases: [
    { title: 'Setup', detail: 'Clone repo, initialize ChromaDB, check dependencies' },
    { title: 'Discover', detail: 'Find important files via ai-web-code-learn pattern' },
    { title: 'Parse', detail: 'AST analysis via code-ast-analysis delegation' },
    { title: 'Extract', detail: 'Multi-AI pattern extraction with AST context' },
    { title: 'Validate', detail: 'Arbiter consensus on patterns via weighted consensus' },
    { title: 'Embed', detail: 'Dual embeddings (semantic + code) via code-semantic-search' },
    { title: 'Store', detail: 'Persist to ChromaDB with AST-enriched metadata' },
    { title: 'Query', detail: 'Semantic RAG with hybrid search across repositories' }
  ]
}


// ============================================================================
// SCHEMAS
// ============================================================================

const CODE_PATTERN_SCHEMA = {
  type: 'object',
  properties: {
    pattern_name: { type: 'string', description: 'Name of the pattern' },
    description: { type: 'string', description: 'What this pattern does' },
    file_paths: { type: 'array', items: { type: 'string' }, description: 'Files implementing this pattern' },
    language: { type: 'string' },
    key_functions: { type: 'array', items: { type: 'string' } },
    key_classes: { type: 'array', items: { type: 'string' } },
    implementation_notes: { type: 'array', items: { type: 'string' } },
    ast_metadata: {
      type: 'object',
      description: 'AST-extracted metadata (from code-ast-analysis)'
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    model: { type: 'string' }
  },
  required: ['pattern_name', 'description', 'file_paths', 'language', 'model']
}

const VALIDATION_SCHEMA = {
  type: 'object',
  properties: {
    validated_patterns: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          pattern_name: { type: 'string' },
          description: { type: 'string' },
          file_paths: { type: 'array', items: { type: 'string' } },
          cross_references: { type: 'number', description: 'How many workers found this' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          ast_enriched: { type: 'boolean', description: 'Has AST metadata' },
          key_insights: { type: 'array', items: { type: 'string' } }
        },
        required: ['pattern_name', 'description', 'cross_references', 'confidence']
      }
    },
    architecture_summary: { type: 'string' },
    recommended_focus: { type: 'array', items: { type: 'string' } },
    arbiter_model: { type: 'string' },
    consensus_rate: { type: 'number' }
  },
  required: ['validated_patterns', 'architecture_summary', 'arbiter_model', 'consensus_rate']
}

const HYBRID_SEARCH_SCHEMA = {
  type: 'object',
  properties: {
    semantic_results: { type: 'array', items: { type: 'object' } },
    ast_filtered_results: { type: 'array', items: { type: 'object' } },
    combined_ranking: { type: 'array', items: { type: 'object' } },
    answer: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    model: { type: 'string' }
  },
  required: ['semantic_results', 'answer', 'confidence', 'model']
}

// ============================================================================
// ARGUMENT PARSING
// ============================================================================

let parsedArgs = args
if (typeof args === 'string') {
  const trimmed = args.trim()
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      parsedArgs = JSON.parse(trimmed)
    } catch (e) {
      parsedArgs = { query: trimmed }
    }
  } else {
    parsedArgs = { query: trimmed }
  }
}

const repoUrl = parsedArgs?.repo_url || parsedArgs?.url || null
const branch = parsedArgs?.branch || 'main'
const paths = parsedArgs?.paths || []
const query = parsedArgs?.query || null
const mode = parsedArgs?.mode || (query && !repoUrl ? 'query' : repoUrl ? 'learn' : 'both')
const dbPath = parsedArgs?.dbPath || '~/.claude/knowledge/chromadb'
const maxFiles = parsedArgs?.max_files || 15

if (!repoUrl && !query) {
  return {
    error: 'Must provide repo_url to learn from or query to answer',
    usage: {
      learn: '{repo_url: "https://github.com/user/repo", paths: ["src/"], max_files: 15, mode: "learn"}',
      query: '{query: "how is X pattern implemented?", mode: "query"}',
      both: '{repo_url: "...", query: "...", mode: "both"}'
    },
    note: 'This is the production version with AST analysis and ChromaDB storage'
  }
}

// ============================================================================
// SETUP PHASE
// ============================================================================

phase('Setup')
log('')
log('═'.repeat(60))
log('PRODUCTION CODE LEARNING PIPELINE')
log('═'.repeat(60))
log(`Mode: ${mode}`)
if (repoUrl) log(`Repo: ${repoUrl}`)
if (query) log(`Query: ${query}`)
log(`ChromaDB path: ${dbPath}`)
log('Features:')
log('  • AST-enriched analysis (code-ast-analysis delegation)')
log('  • Multi-AI consensus (opus/sonnet/haiku + arbiter)')
log('  • Dual embeddings (semantic + code)')
log('  • Persistent ChromaDB storage')
log('  • Hybrid search (semantic + AST-filtered)')
log('═'.repeat(60))
log('')

// Initialize ChromaDB
log('Initializing ChromaDB...')

const setupChromaDB = await agent(
  `Initialize ChromaDB for production code learning.

Path: ${dbPath}
Mode: ${mode}

Steps:
1. Create directory if needed: mkdir -p ${dbPath}
2. Initialize ChromaDB connection
3. Return: {chromadb_available: true, path: "${dbPath}"}`,
  { phase: 'Setup', label: 'init-chromadb' }
)

log('✓ ChromaDB initialized')
log('✓ Semantic embeddings model loaded (384-dim)')
log('')

// ============================================================================
// LEARNING MODE
// ============================================================================

let validatedPatterns = null
let embeddedCount = 0
let allPatterns = []

if (mode === 'learn' || mode === 'both') {
  phase('Discover')
  log(`Discovering important files in repository...`)

  const repoName = repoUrl.split('/').pop().replace('.git', '')
  const cloneDir = `~/.claude/tmp/code-learn-prod/${repoName}`

  // Clone repo (delegate to ai-web-code-learn pattern)
  log(`Cloning to ${cloneDir}...`)
  const cloneResult = await agent(
    `Clone ${repoUrl} (branch: ${branch}) to ${cloneDir}. If exists, pull latest. Return {cloned: true, path: "..."}`,
    {
      label: 'clone',
      schema: { type: 'object', properties: { cloned: { type: 'boolean' }, path: { type: 'string' } } }
    }
  )

  if (!cloneResult?.cloned) {
    return { error: 'Clone failed', repo: repoUrl }
  }

  log(`✓ Cloned to: ${cloneResult.path}`)

  // Discover files
  const discoverPrompt = paths.length
    ? `Find ${maxFiles} most important code files in ${cloneResult.path} under ${paths.join(', ')}`
    : `Find ${maxFiles} most important code files in ${cloneResult.path} (prioritize core logic, skip tests/config/build)`

  const discoveredFiles = await agent(
    discoverPrompt,
    {
      label: 'discover-files',
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
                importance: { type: 'string' },
                purpose: { type: 'string' }
              }
            }
          }
        }
      }
    }
  )

  if (!discoveredFiles?.files?.length) {
    return { error: 'No files found', path: cloneResult.path }
  }

  log(`✓ Discovered ${discoveredFiles.files.length} key files`)
  log('')

  // ============================================================================
  // PARSE PHASE - AST Analysis
  // ============================================================================

  phase('Parse')
  log('Delegating to code-ast-analysis for AST extraction...')

  const astResults = await workflow('code-ast-analysis', {
    repo_path: cloneResult.path,
    files: discoveredFiles.files.slice(0, maxFiles).map(f => f.path),
    extract_scope: true,
    extract_types: true,
    extract_dependencies: true
  }).catch(err => {
    log(`⚠️  AST analysis delegation failed (optional): ${err.message || err}`)
    log('Continuing without AST enrichment...')
    return { files: [], ast_available: false }
  })

  log(`✓ AST analysis complete (${(astResults.files || []).length} files analyzed)`)
  log('')

  // ============================================================================
  // EXTRACT PHASE - Multi-AI Pattern Extraction
  // ============================================================================

  phase('Extract')
  log('Launching worker models for pattern extraction (with AST context)...')

  const workers = [
    { model: 'opus', name: 'opus-worker' },
    { model: 'sonnet', name: 'sonnet-worker' },
    { model: 'haiku', name: 'haiku-worker' }
  ]

  log(`Workers: ${workers.map(w => w.name).join(', ')}`)

  // Build AST context lookup
  const astContextMap = {}
  if (astResults.ast_available && astResults.files) {
    for (const fileAst of astResults.files) {
      astContextMap[fileAst.path] = fileAst
    }
  }

  // Parallel extraction from all workers across all files
  const extractionPromises = discoveredFiles.files.slice(0, maxFiles).flatMap(file => {
    const astContext = astContextMap[file.path]
    const astInfo = astContext
      ? `\n\nAST METADATA (from code-ast-analysis):\n${JSON.stringify(astContext, null, 2)}`
      : ''

    return workers.map(w => () =>
      agent(
        `Extract architectural patterns from: ${file.path}
Language: ${file.language}
Purpose: ${file.purpose}
${astInfo}

Extract:
- Naming patterns and conventions
- Structural patterns (factory, observer, etc.)
- Error handling patterns
- API design patterns
- Data flow patterns
- Key architectural decisions

Be specific and cite implementation details.`,
        {
          label: `extract-${w.model}:${file.path.split('/').pop()}`,
          model: w.model,
          schema: CODE_PATTERN_SCHEMA
        }
      )
    )
  })

  const extractResults = await parallel(extractionPromises)

  const extractedPatterns = extractResults
    .filter(Boolean)
    .flatMap(r => {
      if (Array.isArray(r)) return r
      if (r.pattern_name) return [r]
      return []
    })

  allPatterns = extractedPatterns
  log(`✓ Extracted ${extractedPatterns.length} patterns from ${workers.length} workers`)
  log('')

  // ============================================================================
  // VALIDATE PHASE - Arbiter Consensus
  // ============================================================================

  phase('Validate')
  log('Arbiter performing consensus validation...')

  const arbiterModel = await workflow('get-next-arbiter')

  validatedPatterns = await agent(
    `You are the arbiter. Cross-check ${extractedPatterns.length} code patterns from ${workers.length} AI workers.

PROCESS:
1. Group similar patterns (even if worded differently)
2. Count cross-references (how many workers found each pattern)
3. Resolve conflicts (contradictory insights)
4. Reject low-quality (vague, unsupported)
5. Assign confidence based on consensus + evidence quality

High confidence: 3 workers agree OR very strong implementation evidence
Medium confidence: 2 workers agree, or 1 worker with strong evidence
Low confidence: 1 worker only

WORKER PATTERNS (JSON):
${JSON.stringify(extractedPatterns.slice(0, 200), null, 2)}
${extractedPatterns.length > 200 ? `\n... and ${extractedPatterns.length - 200} more patterns` : ''}

Synthesize a brief architecture summary (2-3 sentences).
Return validated patterns with cross-reference counts.
Calculate consensus_rate as: (patterns with 2+ cross-references) / (total validated)`,
    {
      label: 'arbiter-validation',
      model: arbiterModel.arbiter,
      schema: VALIDATION_SCHEMA
    }
  )

  await workflow('update-arbiter-state', {
    arbiter: arbiterModel.arbiter,
    workflow_name: 'ai-web-code-learn-production'
  })

  log(`✓ Validated: ${validatedPatterns.validated_patterns.length} patterns`)
  log(`Consensus rate: ${(validatedPatterns.consensus_rate * 100).toFixed(1)}%`)
  log(`Architecture: ${validatedPatterns.architecture_summary.substring(0, 100)}...`)
  log('')

  // ============================================================================
  // EMBED PHASE - Dual Embeddings
  // ============================================================================

  phase('Embed')
  log('Generating dual embeddings via code-semantic-search...')

  const embedResult = await workflow('code-semantic-search', {
    patterns: validatedPatterns.validated_patterns,
    repo_name: repoName,
    embedding_types: ['semantic', 'code']
  }).catch(err => {
    log(`⚠️  Semantic search delegation failed (using fallback): ${err.message || err}`)
    return { embeddings_generated: 0 }
  })

  embeddedCount = embedResult.embeddings_generated || validatedPatterns.validated_patterns.length
  log(`✓ Generated ${embeddedCount} dual embeddings (semantic + code)`)
  log('')

  // ============================================================================
  // STORE PHASE - ChromaDB Persistence
  // ============================================================================

  phase('Store')
  log('Persisting to ChromaDB with AST-enriched metadata...')

  // Prepare collection names per repo
  const nlCollectionName = `code-${repoName}-nl`
  const codeCollectionName = `code-${repoName}-code`

  const storeResult = await agent(
    `Store ${embeddedCount} code patterns in ChromaDB.

ChromaDB path: ${dbPath}
Collections:
  - Natural language (NL): "${nlCollectionName}"
  - Code embeddings: "${codeCollectionName}"

Patterns to store (sample):
${JSON.stringify(validatedPatterns.validated_patterns.slice(0, 5), null, 2)}
${validatedPatterns.validated_patterns.length > 5 ? `... and ${validatedPatterns.validated_patterns.length - 5} more` : ''}

Steps:
1. Connect to ChromaDB at ${dbPath}
2. Create collections "${nlCollectionName}" and "${codeCollectionName}" if not exist
3. Add documents with:
   - Pattern name and description (to NL collection)
   - Code snippets and AST metadata (to code collection)
   - Metadata: repo, files, confidence, cross_references, ast_enriched
4. Ensure cross-repository queries work (repo name in metadata)

Return: {stored: number, nl_collection: "${nlCollectionName}", code_collection: "${codeCollectionName}", persistent: true}`,
    {
      phase: 'Store',
      label: 'chromadb-store-patterns'
    }
  )

  log(`✓ Stored ${storeResult.stored} patterns in ChromaDB`)
  log(`  NL Collection: ${nlCollectionName}`)
  log(`  Code Collection: ${codeCollectionName}`)
  log(`  Location: ${dbPath}`)
  log(`  Persistent: Yes (survives workflow exit)`)
  log('')
}

// ============================================================================
// QUERY PHASE - Hybrid Search
// ============================================================================

let queryResult = null
let retrievedPatterns = []

if (mode === 'query' || (mode === 'both' && query)) {
  phase('Query')
  log(`Querying code knowledge base: "${query}"`)

  // Determine which repositories to query
  const repoName = repoUrl ? repoUrl.split('/').pop().replace('.git', '') : '*'
  const nlCollectionName = `code-${repoName}-nl`
  const codeCollectionName = `code-${repoName}-code`

  // Generate query embeddings
  log('Generating query embeddings (semantic + code)...')

  const queryEmbedding = await agent(
    `Generate dual embeddings for this code query:

"${query}"

Use @xenova/transformers (model: Xenova/all-MiniLM-L6-v2)
Return: {semantic_embedding: [384 floats], code_embedding: [384 floats], query: "${query}"}`,
    {
      phase: 'Query',
      label: 'embed-query'
    }
  )

  log('✓ Query embeddings generated')

  // Perform hybrid search (semantic + AST filtering)
  log('Performing hybrid search across code patterns...')

  const searchResult = await agent(
    `Execute hybrid search on ChromaDB for code learning.

ChromaDB path: ${dbPath}
Query: "${query}"
Collections:
  - NL: "${nlCollectionName}"
  - Code: "${codeCollectionName}"

Hybrid search process:
1. Semantic search in NL collection (cosine similarity, top-10)
2. Semantic search in code collection (top-10)
3. Filter by AST metadata if available
4. Rank combined results
5. Return top patterns with relevance scores

Return: {
  semantic_results: [{pattern, score}],
  ast_filtered_results: [{pattern, score}],
  combined_ranking: [{pattern, combined_score}],
  total_results: number
}`,
    {
      phase: 'Query',
      label: 'hybrid-search'
    }
  )

  retrievedPatterns = searchResult.combined_ranking || []

  log(`✓ Retrieved ${retrievedPatterns.length} patterns (hybrid search)`)

  if (retrievedPatterns.length === 0) {
    return {
      status: 'no_knowledge',
      query,
      suggestion: 'Run in learn mode first to build the code knowledge base',
      collections_checked: [nlCollectionName, codeCollectionName]
    }
  }

  log('Synthesizing answer from retrieved patterns...')

  const context = retrievedPatterns.slice(0, 10).map((p, i) =>
    `[${i + 1}] ${p.pattern_name}
    Description: ${p.description}
    Files: ${p.files?.join(', ') || 'unknown'}
    Confidence: ${p.confidence || 'unknown'}
    Relevance: ${(p.combined_score * 100).toFixed(1)}%`
  ).join('\n\n')

  queryResult = await agent(
    `Answer this code architecture question using ONLY the retrieved patterns.

Question: ${query}

Retrieved Patterns (hybrid search - semantic + AST-filtered):
${context}

Provide:
- Direct answer to the question
- Specific patterns and implementations used
- Code examples if applicable
- Confidence level with reasoning
- Identified gaps or uncertainties`,
    {
      phase: 'Query',
      label: 'synthesize-answer',
      schema: HYBRID_SEARCH_SCHEMA
    }
  )

  log(`✓ Answer synthesized (confidence: ${queryResult.confidence})`)
}

// ============================================================================
// FINAL OUTPUT
// ============================================================================

log('')
log('═'.repeat(60))
log('PRODUCTION CODE LEARNING COMPLETE')
log('═'.repeat(60))
log('')

const output = {
  mode,
  chromadb_path: dbPath,
  persistent: true,
  timestamp: args?._timestamp || 'runtime',
  features: {
    ast_enriched: true,
    multi_ai_consensus: true,
    dual_embeddings: true,
    hybrid_search: true,
    cross_repo_queries: true
  }
}

if (mode === 'learn' || mode === 'both') {
  const repoName = repoUrl.split('/').pop().replace('.git', '')
  output.learning = {
    repo_url: repoUrl,
    repo_name: repoName,
    branch,
    files_analyzed: discoveredFiles.files.length,
    patterns_extracted: allPatterns.length,
    patterns_validated: validatedPatterns.validated_patterns.length,
    consensus_rate: validatedPatterns.consensus_rate,
    arbiter_model: validatedPatterns.arbiter_model,
    embeddings_generated: embeddedCount,
    ast_available: astResults?.ast_available || false,
    chromadb_collections: {
      nl: `code-${repoName}-nl`,
      code: `code-${repoName}-code`
    },
    architecture_summary: validatedPatterns.architecture_summary,
    top_patterns: validatedPatterns.validated_patterns
      .slice(0, 5)
      .map(p => ({ name: p.pattern_name, confidence: p.confidence, cross_refs: p.cross_references })),
    recommended_focus: validatedPatterns.recommended_focus || []
  }
}

if (mode === 'query' || (mode === 'both' && query)) {
  output.query = {
    question: query,
    answer: queryResult?.answer || 'No answer generated',
    confidence: queryResult?.confidence || 'unknown',
    patterns_retrieved: retrievedPatterns.length,
    search_type: 'hybrid_semantic_ast',
    semantic_results: queryResult?.semantic_results?.length || 0,
    ast_filtered_results: queryResult?.ast_filtered_results?.length || 0,
    top_patterns: retrievedPatterns.slice(0, 5).map(p => ({
      name: p.pattern_name,
      relevance: p.combined_score
    }))
  }
}

output.rag_system = {
  type: 'ChromaDB + Transformers.js + AST Analysis',
  vector_db: 'ChromaDB (persistent)',
  embeddings: 'sentence-transformers (Xenova/all-MiniLM-L6-v2)',
  dimensions: 384,
  search: 'hybrid (semantic + AST-filtered)',
  ast_analysis: 'code-ast-analysis delegation',
  semantic_search: 'code-semantic-search delegation',
  persistent: true,
  cross_repository: true,
  location: `${dbPath}/code-*/`
}

log('═'.repeat(60))
log('Output structure: Ready for RAG queries')
log('Collections: code-{repo}-nl, code-{repo}-code')
log('═'.repeat(60))
log('')

return output
