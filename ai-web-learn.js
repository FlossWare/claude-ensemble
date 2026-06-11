export const meta = {
  name: 'ai-web-learn',
  description: 'Learn from web pages: fetch, extract facts via arbiter/worker, store in vector DB with RAG retrieval',
  whenToUse: 'When user wants to build knowledge from web sources, learn from documentation, or create searchable knowledge base',
  phases: [
    { title: 'Setup', detail: 'Initialize vector DB and MCP tools' },
    { title: 'Fetch', detail: 'Download web pages via MCP' },
    { title: 'Extract', detail: 'Workers extract facts in parallel' },
    { title: 'Validate', detail: 'Arbiter cross-checks and resolves conflicts' },
    { title: 'Store', detail: 'Embed and store in vector DB' },
    { title: 'Expand', detail: 'Identify knowledge gaps' }
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
          claim: { type: 'string', description: 'The factual claim' },
          evidence: { type: 'string', description: 'Supporting evidence/quote from source' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          source_url: { type: 'string' },
          category: { type: 'string', description: 'Topic category (tech, science, business, etc)' }
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
          conflicts: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                conflicting_claim: { type: 'string' },
                resolution: { type: 'string' }
              }
            }
          },
          category: { type: 'string' }
        },
        required: ['claim', 'evidence', 'confidence', 'sources']
      }
    },
    rejected_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          reason: { type: 'string', description: 'Why this was rejected' },
          model_proposed_by: { type: 'string' }
        }
      }
    },
    arbiter_model: { type: 'string' }
  },
  required: ['validated_facts', 'rejected_facts', 'arbiter_model']
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
          suggested_urls: { type: 'array', items: { type: 'string' } }
        }
      }
    },
    unanswered_questions: { type: 'array', items: { type: 'string' } },
    model: { type: 'string' }
  },
  required: ['missing_topics', 'unanswered_questions', 'model']
}

const QUERY_SCHEMA = {
  type: 'object',
  properties: {
    answer: { type: 'string', description: 'Direct answer to the query' },
    supporting_facts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          fact: { type: 'string' },
          relevance: { type: 'string', enum: ['high', 'medium', 'low'] }
        }
      }
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    gaps: { type: 'array', items: { type: 'string' }, description: 'What info is missing' },
    model: { type: 'string' }
  },
  required: ['answer', 'supporting_facts', 'confidence', 'model']
}

// Simple in-memory vector store (could swap for sqlite-vec, pgvector, etc)
class VectorStore {
  constructor() {
    this.documents = []
    this.embeddings = []
  }

  async add(text, metadata) {
    // Simple embedding: bag-of-words + TF-IDF approximation
    // In production, use OpenAI embeddings, sentence-transformers, etc
    const embedding = this._simpleEmbed(text)
    this.documents.push({ text, metadata, embedding })
    return this.documents.length - 1
  }

  async search(query, topK = 5) {
    const queryEmb = this._simpleEmbed(query)

    // Cosine similarity
    const scores = this.documents.map((doc, idx) => ({
      idx,
      score: this._cosineSim(queryEmb, doc.embedding),
      ...doc
    }))

    scores.sort((a, b) => b.score - a.score)
    return scores.slice(0, topK)
  }

  _simpleEmbed(text) {
    // Extremely simple: word frequency vector
    // Real implementation would use actual embeddings
    const words = text.toLowerCase().split(/\W+/).filter(Boolean)
    const freq = {}
    words.forEach(w => freq[w] = (freq[w] || 0) + 1)

    // Get top 100 words as vector
    const sorted = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 100)
    return sorted.reduce((vec, [word, count]) => {
      vec[word] = count
      return vec
    }, {})
  }

  _cosineSim(a, b) {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)])
    let dot = 0, magA = 0, magB = 0

    keys.forEach(k => {
      const av = a[k] || 0
      const bv = b[k] || 0
      dot += av * bv
      magA += av * av
      magB += bv * bv
    })

    return dot / (Math.sqrt(magA) * Math.sqrt(magB) + 0.0001)
  }

  export() {
    return JSON.stringify(this.documents)
  }

  import(json) {
    this.documents = JSON.parse(json)
  }
}

// Main workflow
phase('Setup')
log('Initializing vector store and checking MCP tools...')

const vectorStore = new VectorStore()

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
const loadExisting = parsedArgs?.load || null

if (loadExisting) {
  log(`Loading existing knowledge base from: ${loadExisting}`)
  // In real implementation, would read from file
  // vectorStore.import(fs.readFileSync(loadExisting, 'utf8'))
}

if (!urls.length && !query) {
  return {
    error: 'Must provide either urls to learn from or query to search',
    usage: {
      learn: 'args: {urls: ["https://...", "https://..."], saveTo: "/path/to/kb.json"}',
      query: 'args: {query: "your question", load: "/path/to/kb.json"}',
      learn_and_query: 'args: {urls: [...], query: "question"}'
    }
  }
}

// RAG Query Mode
if (query && !urls.length) {
  log(`Querying knowledge base: "${query}"`)
  const results = await vectorStore.search(query, 10)

  if (results.length === 0) {
    return {
      answer: 'No relevant knowledge found in the database.',
      suggestion: 'Add URLs to learn from first'
    }
  }

  log(`Found ${results.length} relevant facts, synthesizing answer...`)

  const context = results.map(r =>
    `[Score: ${r.score.toFixed(2)}] ${r.text}\nSource: ${r.metadata.source}\n`
  ).join('\n')

  const answer = await agent(
    `Answer this question using ONLY the provided facts. If the facts don't contain enough info, say so clearly.

Question: ${query}

Relevant Facts:
${context}

Provide a direct answer, cite which facts you used, note your confidence, and identify any gaps.`,
    {
      schema: QUERY_SCHEMA,
      model: 'opus',
      phase: 'Query',
      label: 'rag-synthesis'
    }
  )

  return {
    query,
    answer: answer.answer,
    confidence: answer.confidence,
    supporting_facts: answer.supporting_facts,
    gaps: answer.gaps,
    retrieved_count: results.length,
    top_sources: results.slice(0, 3).map(r => r.metadata.source)
  }
}

// Learning Mode
if (urls.length === 0) {
  return { error: 'No URLs provided for learning' }
}

phase('Fetch')
log(`Fetching ${urls.length} pages...`)

// Try to use MCP fetch tools if available, fallback to WebFetch
const pages = await parallel(urls.map(url => () =>
  agent(
    `Fetch the content from this URL and return the full text: ${url}

If you have MCP web-fetching tools available, use them. Otherwise use WebFetch.
Return just the text content, no HTML tags.`,
    {
      label: `fetch:${url}`,
      phase: 'Fetch'
    }
  )
))

const validPages = pages.filter(Boolean)
log(`Successfully fetched ${validPages.length}/${urls.length} pages`)

phase('Extract')

// Worker models
const workers = [
  { model: 'opus', name: 'opus-worker' },
  { model: 'sonnet', name: 'sonnet-worker' },
  { model: 'haiku', name: 'haiku-worker' }
]

const hasGemini = false // Would check MCP registry in real impl
if (hasGemini) {
}

const allFindings = await pipeline(
  validPages,
  (page, _, idx) => {
    const url = urls[idx]
    log(`Processing page ${idx + 1}/${validPages.length}: ${url}`)

    // Decide if chunking needed
    const wordCount = page.split(/\s+/).length
    const needsChunking = wordCount > 10000

    if (needsChunking) {
      log(`  Large page (${wordCount} words), chunking...`)
      // Simple paragraph chunking
      const paragraphs = page.split(/\n\n+/)
      const chunks = []
      let current = ''

      paragraphs.forEach(p => {
        if ((current + p).split(/\s+/).length > 2000) {
          if (current) chunks.push(current)
          current = p
        } else {
          current += '\n\n' + p
        }
      })
      if (current) chunks.push(current)

      log(`  Split into ${chunks.length} chunks`)

      // Process chunks in parallel by workers
      return parallel(chunks.map((chunk, chunkIdx) => () =>
        parallel(workers.map(w => () =>
          agent(
            `Extract factual claims from this text. Focus on concrete, verifiable facts.

Source URL: ${url}
Chunk ${chunkIdx + 1}/${chunks.length}:

${chunk}

Extract clear facts with supporting evidence.`,
            {
              schema: FACTS_SCHEMA,
              model: w.model,
              phase: 'Extract',
              label: `${w.name}:chunk-${chunkIdx}`
            }
          )
        ))
      )).then(chunkResults => {
        // Flatten: [chunk][worker] -> [fact]
        return chunkResults.flat().filter(Boolean).flatMap(r =>
          r.facts.map(f => ({...f, model: r.model}))
        )
      })
    } else {
      // Small page: process whole by all workers
      return parallel(workers.map(w => () =>
        agent(
          `Extract factual claims from this webpage. Focus on concrete, verifiable facts.

Source URL: ${url}

${page}

Extract clear facts with supporting evidence.`,
          {
            schema: FACTS_SCHEMA,
            model: w.model,
            phase: 'Extract',
            label: `${w.name}:${url}`
          }
        )
      )).then(results =>
        results.filter(Boolean).flatMap(r =>
          r.facts.map(f => ({...f, model: r.model}))
        )
      )
    }
  }
)

const allFacts = allFindings.flat().filter(Boolean)
log(`Extracted ${allFacts.length} total facts from all workers`)

phase('Validate')
log('Arbiter cross-checking facts and resolving conflicts...')

const validated = await agent(
  `You are the arbiter. Review all facts extracted by multiple AI workers.

TASKS:
1. Cross-reference claims - if multiple workers found the same fact, that's high confidence
2. Detect conflicts - if workers disagree, resolve based on evidence quality
3. Filter low-quality facts - reject vague, unsupported, or duplicate claims
4. Categorize validated facts

WORKER FACTS (${allFacts.length} total):
${JSON.stringify(allFacts, null, 2)}

Return validated facts with conflict resolutions and rejected facts with reasons.`,
  {
    schema: VALIDATION_SCHEMA,
    model: 'opus',
    phase: 'Validate',
    label: 'arbiter-validation'
  }
)

log(`Validated ${validated.validated_facts.length} facts, rejected ${validated.rejected_facts.length}`)

phase('Store')
log('Embedding facts and storing in vector DB...')

for (const fact of validated.validated_facts) {
  const text = `${fact.claim}\n\nEvidence: ${fact.evidence.join(' ')}`
  await vectorStore.add(text, {
    claim: fact.claim,
    sources: fact.sources,
    confidence: fact.confidence,
    category: fact.category,
    conflicts: fact.conflicts || []
  })
}

log(`Stored ${validated.validated_facts.length} facts in vector store`)

phase('Expand')
log('Identifying knowledge gaps...')

const gaps = await agent(
  `Review the validated knowledge and identify what's missing.

VALIDATED FACTS:
${JSON.stringify(validated.validated_facts.map(f => f.claim), null, 2)}

ORIGINAL URLS:
${urls.join('\n')}

Identify:
1. Topics mentioned but not fully explored
2. Questions raised but not answered
3. Suggested URLs to fill gaps (prioritize high value)`,
  {
    schema: GAPS_SCHEMA,
    model: 'sonnet',
    phase: 'Expand',
    label: 'gap-analysis'
  }
)

log(`Found ${gaps.missing_topics.length} missing topics, ${gaps.unanswered_questions.length} unanswered questions`)

// If query provided, answer it
let queryResult = null
if (query) {
  log(`Answering query: "${query}"`)
  const results = await vectorStore.search(query, 10)
  const context = results.map(r =>
    `${r.text}\nSource: ${r.metadata.sources.join(', ')}`
  ).join('\n\n')

  queryResult = await agent(
    `Answer using the knowledge base:

Question: ${query}

Knowledge:
${context}`,
    {
      schema: QUERY_SCHEMA,
      model: 'opus',
      phase: 'Query',
      label: 'answer'
    }
  )
}

// Final output
const result = {
  learning: {
    urls_processed: validPages.length,
    facts_extracted: allFacts.length,
    facts_validated: validated.validated_facts.length,
    facts_rejected: validated.rejected_facts.length,
    worker_models: workers.map(w => w.model),
    arbiter_model: validated.arbiter_model
  },
  knowledge: {
    facts_by_category: validated.validated_facts.reduce((acc, f) => {
      acc[f.category || 'uncategorized'] = (acc[f.category || 'uncategorized'] || 0) + 1
      return acc
    }, {}),
    confidence_distribution: validated.validated_facts.reduce((acc, f) => {
      acc[f.confidence] = (acc[f.confidence] || 0) + 1
      return acc
    }, {})
  },
  gaps: {
    missing_topics: gaps.missing_topics,
    unanswered_questions: gaps.unanswered_questions
  },
  rejected: validated.rejected_facts,
  vector_store: {
    total_documents: vectorStore.documents.length,
    export: vectorStore.export() // For persistence
  }
}

if (queryResult) {
  result.query = {
    question: query,
    answer: queryResult.answer,
    confidence: queryResult.confidence,
    supporting_facts: queryResult.supporting_facts,
    gaps: queryResult.gaps
  }
}

if (parsedArgs?.saveTo) {
  log(`Saving knowledge base to: ${parsedArgs.saveTo}`)
  // In real impl: fs.writeFileSync(parsedArgs.saveTo, vectorStore.export())
}

return result
