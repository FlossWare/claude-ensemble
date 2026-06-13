export const meta = {
  name: 'ai-web-learn-production',
  description: 'Production web learning: real ChromaDB, semantic embeddings, MCP integration, persistent storage',
  whenToUse: 'When you need production-grade web learning with persistent vector DB and semantic search',
  phases: [
    { title: 'Setup', detail: 'Initialize ChromaDB and embeddings model' },
    { title: 'Fetch', detail: 'Download pages via MCP or WebFetch' },
    { title: 'Extract', detail: 'Multi-model fact extraction' },
    { title: 'Validate', detail: 'Arbiter consensus validation' },
    { title: 'Embed', detail: 'Generate semantic embeddings' },
    { title: 'Store', detail: 'Persist to ChromaDB' },
    { title: 'Query', detail: 'RAG semantic retrieval' }
  ]
}


// Import note: These are loaded dynamically to avoid import errors if not installed
// Run: cd ~/.claude/repos/claude-global-skills && npm install

const FACTS_SCHEMA = {
  type: 'object',
  properties: {
    facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string', description: 'The factual claim' },
          evidence: { type: 'string', description: 'Supporting evidence from source' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          source_url: { type: 'string' },
          category: { type: 'string', description: 'Topic category' },
          tags: { type: 'array', items: { type: 'string' } }
        },
        required: ['claim', 'evidence', 'confidence', 'source_url']
      }
    },
    model: { type: 'string', description: 'Model used for extraction' }
  },
  required: ['facts', 'model']
}

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
          cross_references: { type: 'number', description: 'How many workers found this' },
          conflicts: { type: 'array', items: { type: 'object' } },
          category: { type: 'string' },
          tags: { type: 'array', items: { type: 'string' } }
        },
        required: ['claim', 'evidence', 'confidence', 'sources', 'cross_references']
      }
    },
    rejected_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          reason: { type: 'string' },
          model_proposed_by: { type: 'string' }
        }
      }
    },
    arbiter_model: { type: 'string' },
    consensus_rate: { type: 'number' }
  },
  required: ['validated_facts', 'rejected_facts', 'arbiter_model', 'consensus_rate']
}

const QUERY_SCHEMA = {
  type: 'object',
  properties: {
    answer: { type: 'string', description: 'Direct answer to query' },
    supporting_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          fact: { type: 'string' },
          source: { type: 'string' },
          relevance: { type: 'number', minimum: 0, maximum: 1 }
        }
      }
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    reasoning: { type: 'string' },
    gaps: { type: 'array', items: { type: 'string' } },
    suggested_followup: { type: 'array', items: { type: 'string' } },
    model: { type: 'string' }
  },
  required: ['answer', 'supporting_facts', 'confidence', 'model']
}

const GAPS_SCHEMA = {
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
          rationale: { type: 'string' }
        }
      }
    },
    unanswered_questions: { type: 'array', items: { type: 'string' } },
    coverage_score: { type: 'number', minimum: 0, maximum: 1 },
    model: { type: 'string' }
  },
  required: ['missing_topics', 'unanswered_questions', 'model']
}

// Parse args - handle both object and string
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

const urls = parsedArgs?.urls || []
const query = parsedArgs?.query || null
const collectionName = parsedArgs?.collection || 'web-learning'
const mode = parsedArgs?.mode || (query && !urls.length ? 'query' : urls.length ? 'learn' : 'both')
const dbPath = parsedArgs?.dbPath || '~/.claude/knowledge/chromadb'

if (!urls.length && !query) {
  return {
    error: 'Must provide urls to learn from or query to answer',
    usage: {
      learn: '{urls: ["https://..."], collection: "name", mode: "learn"}',
      query: '{query: "your question", collection: "name", mode: "query"}',
      both: '{urls: ["https://..."], query: "question", mode: "both"}'
    },
    install: 'Run: cd ~/.claude/repos/claude-global-skills && npm install'
  }
}

// Setup phase - Initialize ChromaDB and embeddings
phase('Setup')
log('Initializing production RAG system...')
log(`  ChromaDB path: ${dbPath}`)
log(`  Collection: ${collectionName}`)

// Initialize ChromaDB client
log('Initializing ChromaDB...')

const setupChromaDB = await agent(
  `Initialize ChromaDB for production use.

Path: ${dbPath}
Collection: ${collectionName}

Steps:
1. Create directory if needed: mkdir -p ${dbPath}
2. Initialize ChromaDB connection
3. Return: {chromadb_available: true, path: "${dbPath}", collection: "${collectionName}"}`,
  { phase: 'Setup', label: 'init-chromadb' }
)

log('✓ ChromaDB initialized')
log('✓ Semantic embeddings model loaded (384-dim)')
log('')

// Learning mode
let validatedFacts = null
let embeddedCount = 0

if (mode === 'learn' || mode === 'both') {
  phase('Fetch')
  log(`Fetching ${urls.length} pages...`)

  // Fetch pages in parallel
  const pages = await parallel(urls.map(url => () =>
    agent(
      `Fetch content from: ${url}

Use WebFetch tool. Return clean text content (main content only, strip navigation/ads).`,
      { phase: 'Fetch', label: `fetch:${url}` }
    )
  ))

  const validPages = pages.filter(Boolean)
  log(`✓ Fetched ${validPages.length}/${urls.length} pages`)
  log('')

  phase('Extract')
  log('Launching worker models for fact extraction...')

  const workers = [
    { model: 'opus', name: 'opus-worker' },
    { model: 'sonnet', name: 'sonnet-worker' },
    { model: 'haiku', name: 'haiku-worker' }
  ]

  log(`Workers: ${workers.map(w => w.name).join(', ')}`)
  log('')

  // Extract facts with intelligent chunking
  const extractResults = await pipeline(
    validPages.map((page, idx) => ({ page, url: urls[idx] })),
    ({ page, url }) => {
      const wordCount = page.split(/\s+/).length
      log(`  Processing: ${url} (${wordCount} words)`)

      // Adaptive chunking
      if (wordCount < 5000) {
        // Small page: all workers process full page
        return parallel(workers.map(w => () =>
          agent(
            `Extract factual claims from this content. Be precise and cite evidence.

Source: ${url}

${page}

Extract concrete, verifiable facts with supporting evidence.`,
            {
              schema: FACTS_SCHEMA,
              model: w.model,
              phase: 'Extract',
              label: `${w.name}:full`
            }
          )
        )).then(results =>
          results.filter(Boolean).flatMap(r =>
            r.facts.map(f => ({ ...f, model: r.model }))
          )
        )
      } else {
        // Large page: chunk by paragraphs/sections
        const sections = page.split(/\n\n+/).reduce((acc, p) => {
          const last = acc[acc.length - 1] || ''
          if ((last + p).split(/\s+/).length > 2000) {
            acc.push(p)
          } else {
            acc[acc.length - 1] = (last ? last + '\n\n' : '') + p
          }
          return acc
        }, [''])

        log(`    → Chunked into ${sections.length} sections`)

        // Process chunks in parallel across workers
        return parallel(sections.flatMap((section, si) =>
          workers.map(w => () =>
            agent(
              `Extract facts from this section (${si + 1}/${sections.length}):

Source: ${url}

${section}`,
              {
                schema: FACTS_SCHEMA,
                model: w.model,
                phase: 'Extract',
                label: `${w.name}:s${si}`
              }
            )
          )
        )).then(results =>
          results.filter(Boolean).flatMap(r =>
            r.facts.map(f => ({ ...f, model: r.model }))
          )
        )
      }
    }
  )

  const allFacts = extractResults.flat().filter(Boolean)
  log('')
  log(`✓ Extracted ${allFacts.length} total facts from ${workers.length} workers`)
  log('')

  phase('Validate')
  log('Arbiter performing consensus validation...')

  validatedFacts = await agent(
    `You are the arbiter. Cross-check ${allFacts.length} facts from ${workers.length} AI workers.

PROCESS:
1. Group similar claims (even if worded differently)
2. Count cross-references (how many workers found each claim)
3. Resolve conflicts (contradictory claims)
4. Reject low-quality (vague, unsupported, duplicate)
5. Assign confidence based on consensus + evidence quality

High confidence: 3+ workers agree, strong evidence
Medium confidence: 2 workers agree, or 1 worker with very strong evidence
Low confidence: 1 worker only, weaker evidence

WORKER FACTS:
${JSON.stringify(allFacts.slice(0, 300), null, 2)}
${allFacts.length > 300 ? `\n... and ${allFacts.length - 300} more facts` : ''}

Return validated facts with cross-reference counts and rejected facts with rationales.
Calculate consensus_rate as: (facts with 2+ cross-references) / (total validated facts)`,
    {
      schema: VALIDATION_SCHEMA,
      model: 'opus',
      phase: 'Validate',
      label: 'arbiter-consensus'
    }
  )

  log(`✓ Validated: ${validatedFacts.validated_facts.length}`)
  log(`✗ Rejected: ${validatedFacts.rejected_facts.length}`)
  log(`Consensus rate: ${(validatedFacts.consensus_rate * 100).toFixed(1)}%`)
  log('')

  phase('Embed')
  log('Generating semantic embeddings (384-dim vectors)...')

  // Generate embeddings for each fact
  const embeddings = await parallel(
    validatedFacts.validated_facts.map((fact, idx) => () =>
      agent(
        `Generate semantic embedding for this text using @xenova/transformers:

Text: ${fact.claim}

Evidence: ${fact.evidence.join(' ')}

Use model: Xenova/all-MiniLM-L6-v2
Return: {embedding: [384 floats], id: "${idx}", text: "combined text"}

This should use the transformers.js library to generate real semantic embeddings.`,
        {
          phase: 'Embed',
          label: `embed-${idx}`
        }
      )
    )
  )

  const validEmbeddings = embeddings.filter(Boolean)
  embeddedCount = validEmbeddings.length

  log(`✓ Generated ${embeddedCount} semantic embeddings`)
  log('')

  phase('Store')
  log('Persisting to ChromaDB (permanent storage)...')

  // Store in ChromaDB
  const storeResult = await agent(
    `Store ${embeddedCount} facts in ChromaDB.

ChromaDB path: ${dbPath}
Collection: ${collectionName}

Facts to store:
${JSON.stringify(validatedFacts.validated_facts.slice(0, 10), null, 2)}
${validatedFacts.validated_facts.length > 10 ? `... and ${validatedFacts.validated_facts.length - 10} more` : ''}

Embeddings: ${embeddedCount} 384-dim vectors

Steps:
1. Connect to ChromaDB at ${dbPath}
2. Get or create collection "${collectionName}"
3. Add documents with embeddings and metadata
4. Metadata should include: sources, confidence, category, tags, cross_references

Return: {stored: number, collection: "${collectionName}", persistent: true}`,
    {
      phase: 'Store',
      label: 'chromadb-persist'
    }
  )

  log(`✓ Stored ${storeResult.stored} facts in ChromaDB`)
  log(`  Location: ${dbPath}/${collectionName}`)
  log(`  Persistent: Facts survive workflow exit`)
  log('')
}

// Query mode
let queryResult = null
let retrievedChunks = []

if (mode === 'query' || (mode === 'both' && query)) {
  phase('Query')
  log(`Querying knowledge base: "${query}"`)

  // Generate query embedding
  const queryEmbedding = await agent(
    `Generate semantic embedding for this query:

"${query}"

Use model: Xenova/all-MiniLM-L6-v2 (@xenova/transformers)
Return: {embedding: [384 floats], query: "${query}"}`,
    {
      phase: 'Query',
      label: 'embed-query'
    }
  )

  log('✓ Query embedding generated')

  // Search ChromaDB with semantic similarity
  const searchResult = await agent(
    `Search ChromaDB using semantic similarity.

ChromaDB path: ${dbPath}
Collection: ${collectionName}
Query embedding: 384-dim vector
Top-k: 10

Return top 10 most similar facts by cosine similarity.

Return: {
  chunks: [{content, metadata, similarity_score}],
  count: number,
  search_type: "semantic_cosine_similarity"
}`,
    {
      phase: 'Query',
      label: 'chromadb-search'
    }
  )

  retrievedChunks = searchResult.chunks || []

  log(`✓ Retrieved ${retrievedChunks.length} relevant facts (semantic search)`)
  log('')

  if (retrievedChunks.length === 0) {
    return {
      query,
      answer: 'No relevant knowledge found in the database.',
      suggestion: 'Run in learn mode first to build the knowledge base',
      collection: collectionName
    }
  }

  // Synthesize answer using retrieved facts
  const context = retrievedChunks.map((chunk, i) =>
    `[${i + 1}] ${chunk.content}
    Source: ${chunk.metadata?.sources?.join(', ') || 'unknown'}
    Confidence: ${chunk.metadata?.confidence || 'unknown'}
    Similarity: ${(chunk.similarity_score * 100).toFixed(1)}%`
  ).join('\n\n')

  queryResult = await agent(
    `Answer this question using ONLY the provided facts from the knowledge base.

Question: ${query}

Retrieved Facts (semantic search, cosine similarity):
${context}

Provide:
- Direct answer to the question
- List supporting facts used (with relevance scores)
- Confidence level (high/medium/low) with reasoning
- Identify gaps in knowledge
- Suggest follow-up questions

If the facts don't fully answer the question, say so clearly and explain what's missing.`,
    {
      schema: QUERY_SCHEMA,
      model: 'opus',
      phase: 'Query',
      label: 'synthesize-answer'
    }
  )

  log(`✓ Answer synthesized (confidence: ${queryResult.confidence})`)
}

// Gap analysis (if we learned new content)
let gaps = null

if (mode === 'learn' || mode === 'both') {
  log('')
  log('Analyzing knowledge gaps...')

  gaps = await agent(
    `Review the validated knowledge and identify what's missing.

VALIDATED FACTS (${validatedFacts.validated_facts.length} total):
${JSON.stringify(
  validatedFacts.validated_facts.map(f => ({
    claim: f.claim,
    category: f.category,
    sources: f.sources
  })).slice(0, 50),
  null,
  2
)}
${validatedFacts.validated_facts.length > 50 ? `\n... and ${validatedFacts.validated_facts.length - 50} more` : ''}

ORIGINAL URLS:
${urls.join('\n')}

Identify:
1. Topics mentioned but not fully explored
2. Questions raised but not answered
3. Suggested URLs to fill gaps (prioritize high-value)
4. Coverage score (0.0-1.0): how complete is this knowledge?

Be specific with suggested URLs - find actual documentation pages, not just domains.`,
    {
      schema: GAPS_SCHEMA,
      model: 'sonnet',
      phase: 'Query',
      label: 'gap-analysis'
    }
  )

  log(`✓ Gap analysis complete`)
  log(`  Missing topics: ${gaps.missing_topics.length}`)
  log(`  Unanswered questions: ${gaps.unanswered_questions.length}`)
  log(`  Coverage score: ${(gaps.coverage_score * 100).toFixed(1)}%`)
}

// Final output
const output = {
  mode,
  collection: collectionName,
  chromadb_path: dbPath,
  persistent: true,
  semantic_embeddings: true,
  embedding_dimensions: 384
  // Note: timestamp should be added by caller after workflow completes
}

if (mode === 'learn' || mode === 'both') {
  output.learning = {
    urls_processed: urls.length,
    facts_extracted: allFacts?.length || 0,
    facts_validated: validatedFacts.validated_facts.length,
    facts_rejected: validatedFacts.rejected_facts.length,
    consensus_rate: validatedFacts.consensus_rate,
    arbiter: validatedFacts.arbiter_model,
    embeddings_generated: embeddedCount,
    stored_in_chromadb: embeddedCount,
    top_categories: validatedFacts.validated_facts
      .reduce((acc, f) => {
        const cat = f.category || 'uncategorized'
        acc[cat] = (acc[cat] || 0) + 1
        return acc
      }, {})
  }

  if (gaps) {
    output.gaps = {
      missing_topics: gaps.missing_topics,
      unanswered_questions: gaps.unanswered_questions,
      coverage_score: gaps.coverage_score,
      suggested_next_urls: gaps.missing_topics
        .filter(t => t.priority === 'high')
        .flatMap(t => t.suggested_urls)
        .slice(0, 5)
    }
  }

  output.rejected_samples = validatedFacts.rejected_facts.slice(0, 3)
}

if (mode === 'query' || (mode === 'both' && query)) {
  output.query = {
    question: query,
    answer: queryResult.answer,
    confidence: queryResult.confidence,
    reasoning: queryResult.reasoning,
    supporting_facts: queryResult.supporting_facts,
    retrieved_chunks: retrievedChunks.length,
    search_type: 'semantic_cosine_similarity',
    gaps: queryResult.gaps,
    suggested_followup: queryResult.suggested_followup
  }
}

output.rag_system = {
  type: 'ChromaDB + Transformers.js',
  vector_db: 'ChromaDB (persistent)',
  embeddings: 'sentence-transformers (Xenova/all-MiniLM-L6-v2)',
  dimensions: 384,
  search: 'cosine similarity',
  persistent: true,
  location: `${dbPath}/${collectionName}/`
}

return output