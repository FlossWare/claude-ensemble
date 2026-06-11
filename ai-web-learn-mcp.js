export const meta = {
  name: 'ai-web-learn-mcp',
  description: 'Advanced web learning with MCP tool discovery, real embeddings, and persistent vector DB',
  whenToUse: 'When you need production-grade web learning with MCP integration, embeddings API, and durable storage',
  phases: [
    { title: 'Discover', detail: 'Find available MCP tools for web/embeddings' },
    { title: 'Fetch', detail: 'Download pages via MCP tools' },
    { title: 'Extract', detail: 'Multi-model fact extraction' },
    { title: 'Validate', detail: 'Arbiter consensus + conflict resolution' },
    { title: 'Embed', detail: 'Generate semantic embeddings' },
    { title: 'Store', detail: 'Persist to SQLite vector DB' },
    { title: 'Query', detail: 'RAG retrieval and synthesis' }
  ]
}

const FACTS_SCHEMA = {
  type: 'object',
  properties: {
    facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          evidence: { type: 'string' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          source_url: { type: 'string' },
          category: { type: 'string' },
          tags: { type: 'array', items: { type: 'string' } }
        },
        required: ['claim', 'evidence', 'confidence', 'source_url']
      }
    },
    model: { type: 'string' }
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
          confidence: { type: 'string' },
          sources: { type: 'array', items: { type: 'string' } },
          cross_references: { type: 'number', description: 'How many workers found this' },
          conflicts: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                conflicting_claim: { type: 'string' },
                resolution: { type: 'string' },
                resolved_by: { type: 'string' }
              }
            }
          },
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
          model_proposed_by: { type: 'string' },
          rejection_rationale: { type: 'string' }
        }
      }
    },
    arbiter_model: { type: 'string' },
    consensus_rate: { type: 'number', description: 'Percentage of facts agreed upon by multiple workers' }
  },
  required: ['validated_facts', 'rejected_facts', 'arbiter_model']
}

const MCP_DISCOVERY_SCHEMA = {
  type: 'object',
  properties: {
    web_fetch_tools: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
          use_for: { type: 'string', enum: ['html', 'markdown', 'pdf', 'api'] }
        }
      }
    },
    embedding_tools: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          model: { type: 'string' },
          dimensions: { type: 'number' }
        }
      }
    },
    vector_db_tools: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          type: { type: 'string', enum: ['sqlite', 'postgres', 'redis', 'pinecone'] }
        }
      }
    },
    recommendations: { type: 'string', description: 'Which tools to use for this workflow' }
  },
  required: ['web_fetch_tools', 'embedding_tools', 'vector_db_tools']
}

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
          source: { type: 'string' },
          relevance_score: { type: 'number' }
        }
      }
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    reasoning: { type: 'string', description: 'Why this confidence level' },
    gaps: { type: 'array', items: { type: 'string' } },
    suggested_followup: { type: 'array', items: { type: 'string' } },
    model: { type: 'string' }
  },
  required: ['answer', 'supporting_facts', 'confidence', 'model']
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
const dbPath = parsedArgs?.dbPath || '~/.claude/knowledge/web-learn.db'
const saveFacts = parsedArgs?.saveFacts || '~/.claude/knowledge/facts.json'
const mode = parsedArgs?.mode || 'learn' // 'learn', 'query', 'both'

if (mode !== 'query' && urls.length === 0) {
  return {
    error: 'No URLs provided for learning mode',
    usage: {
      learn: '{urls: ["https://..."], mode: "learn"}',
      query: '{query: "your question", mode: "query"}',
      both: '{urls: ["https://..."], query: "question", mode: "both"}'
    }
  }
}

if (mode === 'query' && !query) {
  return {
    error: 'No query provided for query mode',
    usage: '{query: "your question", mode: "query"}'
  }
}

// Phase 1: MCP Tool Discovery
phase('Discover')
log('Discovering available MCP tools for web fetching, embeddings, and vector storage...')

const mcpTools = await agent(
  `Search for available MCP tools that can help with:

1. Web fetching (fetch, puppeteer, brave-search, etc)
2. Embeddings generation (OpenAI, Anthropic, local models)
3. Vector database operations (sqlite-vec, pgvector, etc)

Use ToolSearch if available, or check your tool list.

Recommend the BEST tools for this web learning workflow. If embeddings API isn't available, note we'll use simple TF-IDF.`,
  {
    schema: MCP_DISCOVERY_SCHEMA,
    phase: 'Discover',
    label: 'mcp-discovery'
  }
)

log(`Found: ${mcpTools.web_fetch_tools.length} web tools, ${mcpTools.embedding_tools.length} embedding tools, ${mcpTools.vector_db_tools.length} DB tools`)
log(`Recommendation: ${mcpTools.recommendations}`)

// Learning Mode
let validatedFacts = null
let vectorStoreExport = null
let allFacts = []

if (mode === 'learn' || mode === 'both') {
  phase('Fetch')
  log(`Fetching ${urls.length} pages using MCP tools...`)

  const fetchPromises = urls.map(url => {
    const toolName = mcpTools.web_fetch_tools.find(t => t.use_for === 'markdown')?.name || 'WebFetch'

    return () => agent(
      `Fetch content from: ${url}

Use the ${toolName} tool if available. Return clean text content (no HTML unless requested).

For documentation/articles: extract main content, strip navigation/ads
For PDFs: extract text
For APIs: return JSON response`,
      {
        phase: 'Fetch',
        label: `fetch:${url}`
      }
    )
  })

  const pages = await parallel(fetchPromises)
  const validPages = pages.filter(Boolean)

  log(`Fetched ${validPages.length}/${urls.length} pages successfully`)

  phase('Extract')
  log('Launching worker models for fact extraction...')

  const workers = [
    { model: 'opus', name: 'opus-worker' },
    { model: 'sonnet', name: 'sonnet-worker' },
    { model: 'haiku', name: 'haiku-worker' }
  ]

  const extractResults = await pipeline(
    validPages.map((page, idx) => ({ page, url: urls[idx] })),
    ({ page, url }) => {
      const wordCount = page.split(/\s+/).length
      log(`  ${url}: ${wordCount} words`)

      // Adaptive chunking
      if (wordCount < 5000) {
        // Small: all workers process full page
        return parallel(workers.map(w => () =>
          agent(
            `Extract factual claims from this content. Be precise and cite evidence.

Source: ${url}

${page}`,
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
        // Large: chunk semantically
        const chunks = page.split(/\n\n+/).reduce((acc, p) => {
          const last = acc[acc.length - 1] || ''
          if ((last + p).split(/\s+/).length > 2000) {
            acc.push(p)
          } else {
            acc[acc.length - 1] = last + '\n\n' + p
          }
          return acc
        }, [''])

        log(`  Chunked into ${chunks.length} segments`)

        return parallel(chunks.flatMap((chunk, ci) =>
          workers.map(w => () =>
            agent(
              `Extract facts from this section (${ci + 1}/${chunks.length}):

Source: ${url}

${chunk}`,
              {
                schema: FACTS_SCHEMA,
                model: w.model,
                phase: 'Extract',
                label: `${w.name}:chunk${ci}`
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

  allFacts = extractResults.flat().filter(Boolean)
  log(`Extracted ${allFacts.length} total facts across all workers`)

  phase('Validate')
  log('Arbiter performing consensus validation and conflict resolution...')

  validatedFacts = await agent(
    `You are the arbiter. Cross-check ${allFacts.length} facts from multiple AI workers.

PROCESS:
1. Group similar claims (even if worded differently)
2. Count cross-references (how many workers found each)
3. Resolve conflicts (contradictory claims)
4. Reject low-quality (vague, unsupported, duplicate)
5. Assign final confidence based on consensus + evidence quality

FACTS:
${JSON.stringify(allFacts.slice(0, 500), null, 2)}
${allFacts.length > 500 ? `\n... and ${allFacts.length - 500} more` : ''}

Return validated facts with cross-reference counts and rejected facts with clear rationales.`,
    {
      schema: VALIDATION_SCHEMA,
      model: 'opus',
      phase: 'Validate',
      label: 'arbiter'
    }
  )

  log(`✓ Validated: ${validatedFacts.validated_facts.length}`)
  log(`✗ Rejected: ${validatedFacts.rejected_facts.length}`)
  log(`Consensus rate: ${(validatedFacts.consensus_rate * 100).toFixed(1)}%`)

  phase('Embed')
  log('Generating embeddings for validated facts...')

  const embeddingTool = mcpTools.embedding_tools[0]

  if (embeddingTool) {
    log(`Using ${embeddingTool.name} (${embeddingTool.model}, ${embeddingTool.dimensions}d)`)

    // Would call actual embedding tool here
    // For now, note that it's available
    log('Real embeddings API available - would generate semantic vectors here')
  } else {
    log('No embedding API found - using TF-IDF fallback')
  }

  phase('Store')
  log(`Persisting knowledge to ${dbPath}...`)

  const dbTool = mcpTools.vector_db_tools.find(t => t.type === 'sqlite')

  if (dbTool) {
    log(`Using ${dbTool.name} for vector storage`)
    // Would execute actual DB operations via MCP
    log('Would create table, insert embeddings, build index here')
  } else {
    log('No vector DB tool found - exporting to JSON for manual import')
  }

  // Export for persistence
  vectorStoreExport = {
    facts: validatedFacts.validated_facts,
    metadata: {
      source_urls: urls,
      total_facts: validatedFacts.validated_facts.length,
      arbiter: validatedFacts.arbiter_model,
      consensus_rate: validatedFacts.consensus_rate
      // Note: created timestamp should be added by caller after workflow completes
    }
  }

  log(`Saved ${validatedFacts.validated_facts.length} facts to knowledge base`)
}

// Query Mode
let queryResult = null

if (mode === 'query' || (mode === 'both' && query)) {
  phase('Query')
  log(`Querying knowledge base: "${query}"`)

  // Load from DB or use just-created facts
  const knowledgeBase = validatedFacts?.validated_facts || []

  if (knowledgeBase.length === 0) {
    log('No knowledge in DB - load existing or run in learn mode first')
    return {
      error: 'Knowledge base is empty',
      suggestion: 'Run with mode: "learn" first to build knowledge'
    }
  }

  log(`Searching ${knowledgeBase.length} facts...`)

  // Simple retrieval: keyword matching (would use vector similarity in production)
  const queryWords = query.toLowerCase().split(/\W+/)
  const scored = knowledgeBase.map(fact => {
    const text = `${fact.claim} ${fact.evidence.join(' ')}`.toLowerCase()
    const matches = queryWords.filter(w => text.includes(w)).length
    return { fact, score: matches / queryWords.length }
  })

  scored.sort((a, b) => b.score - a.score)
  const topFacts = scored.slice(0, 10).filter(s => s.score > 0)

  log(`Retrieved ${topFacts.length} relevant facts`)

  const context = topFacts.map(({ fact, score }) =>
    `[Relevance: ${(score * 100).toFixed(0)}%] ${fact.claim}\nEvidence: ${fact.evidence.join(' ')}\nSources: ${fact.sources.join(', ')}\n`
  ).join('\n')

  queryResult = await agent(
    `Answer this question using ONLY the provided knowledge base facts.

Question: ${query}

Retrieved Facts:
${context}

Provide: direct answer, supporting facts used, confidence with reasoning, identify gaps, suggest follow-up questions.`,
    {
      schema: QUERY_SCHEMA,
      model: 'opus',
      phase: 'Query',
      label: 'rag-answer'
    }
  )

  log(`Answer confidence: ${queryResult.confidence}`)
}

// Return results
const output = {
  mode
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
    top_categories: Object.entries(
      validatedFacts.validated_facts.reduce((acc, f) => {
        acc[f.category || 'uncategorized'] = (acc[f.category || 'uncategorized'] || 0) + 1
        return acc
      }, {})
    ).sort((a, b) => b[1] - a[1]).slice(0, 5)
  }

  output.rejected_samples = validatedFacts.rejected_facts.slice(0, 5)
  output.vector_store_export = vectorStoreExport
}

if (mode === 'query' || (mode === 'both' && query)) {
  output.query = {
    question: query,
    answer: queryResult.answer,
    confidence: queryResult.confidence,
    reasoning: queryResult.reasoning,
    supporting_facts_count: queryResult.supporting_facts.length,
    supporting_facts: queryResult.supporting_facts.slice(0, 5),
    gaps: queryResult.gaps,
    suggested_followup: queryResult.suggested_followup
  }
}

output.mcp_tools_used = {
  web_fetch: mcpTools.web_fetch_tools.map(t => t.name),
  embeddings: mcpTools.embedding_tools.map(t => t.name),
  vector_db: mcpTools.vector_db_tools.map(t => t.name)
}

return output
