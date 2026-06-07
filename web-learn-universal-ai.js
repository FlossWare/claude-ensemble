export const meta = {
  name: 'web-learn-universal-ai',
  description: 'Web learning using Universal AI RAG system (real ChromaDB + embeddings)',
  whenToUse: 'When you need production-grade web learning with persistent vector DB and semantic embeddings',
  phases: [
    { title: 'Setup', detail: 'Initialize Universal AI RAG system' },
    { title: 'Fetch', detail: 'Download web pages' },
    { title: 'Extract', detail: 'Multi-model fact extraction' },
    { title: 'Validate', detail: 'Arbiter consensus' },
    { title: 'Index', detail: 'Store in Universal AI ChromaDB' },
    { title: 'Query', detail: 'Semantic RAG retrieval' }
  ]
}

const UNIVERSAL_AI_DIR = `${process.env.HOME}/Development/redhat/scm/gitlab/cee/sfloess/universal-ai`
const RAG_SYSTEM = `${UNIVERSAL_AI_DIR}/cli/rag_system.py`

// Check if Universal AI is available
const hasUniversalAI = await agent(
  `Check if this file exists: ${RAG_SYSTEM}

  Return JSON: {exists: true/false}`,
  { label: 'check-universal-ai' }
)

if (!hasUniversalAI?.exists) {
  return {
    error: 'Universal AI not found',
    path_checked: RAG_SYSTEM,
    install: 'Clone from: https://gitlab.cee.redhat.com/sfloess/universal-ai.git',
    suggestion: 'Use /web-learn-mcp instead (uses Claude Code native vector store)'
  }
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
          category: { type: 'string' }
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
          cross_references: { type: 'number' }
        }
      }
    },
    rejected_facts: { type: 'array', items: { type: 'object' } },
    arbiter_model: { type: 'string' }
  },
  required: ['validated_facts', 'rejected_facts', 'arbiter_model']
}

// Parse args
const urls = args?.urls || []
const query = args?.query || null
const kbaseName = args?.kbase || 'web-learning'
const mode = args?.mode || 'both'

if (!urls.length && !query) {
  return {
    error: 'Must provide urls or query',
    usage: {
      learn: '{urls: ["https://..."], kbase: "name", mode: "learn"}',
      query: '{query: "question", kbase: "name", mode: "query"}',
      both: '{urls: ["https://..."], query: "question", mode: "both"}'
    }
  }
}

// Initialize Universal AI RAG kbase
phase('Setup')
log(`Initializing Universal AI kbase: ${kbaseName}`)

const initKbase = await agent(
  `Run this Python command to initialize a kbase:

cd ${UNIVERSAL_AI_DIR}
./kbase init ${kbaseName}

Return: {success: true/false, message: "..."}`,
  { phase: 'Setup', label: 'init-kbase' }
)

log(`Kbase initialized: ${initKbase.message}`)

// Learning mode
let validatedFacts = null
let allFacts = []

if (mode === 'learn' || mode === 'both') {
  phase('Fetch')
  log(`Fetching ${urls.length} pages...`)

  const pages = await parallel(urls.map(url => () =>
    agent(
      `Fetch content from: ${url}

      Use WebFetch tool. Return just the text content.`,
      { phase: 'Fetch', label: `fetch:${url}` }
    )
  ))

  const validPages = pages.filter(Boolean)
  log(`Fetched ${validPages.length}/${urls.length} pages`)

  phase('Extract')
  log('Multi-model fact extraction...')

  const workers = [
    { model: 'opus', name: 'opus-worker' },
    { model: 'sonnet', name: 'sonnet-worker' },
    { model: 'haiku', name: 'haiku-worker' }
  ]

  const allFindings = await pipeline(
    validPages.map((page, idx) => ({ page, url: urls[idx] })),
    ({ page, url }) => {
      return parallel(workers.map(w => () =>
        agent(
          `Extract factual claims from this content:

Source: ${url}

${page}

Focus on concrete, verifiable facts.`,
          {
            schema: FACTS_SCHEMA,
            model: w.model,
            phase: 'Extract',
            label: `${w.name}:${url}`
          }
        )
      )).then(results =>
        results.filter(Boolean).flatMap(r =>
          r.facts.map(f => ({ ...f, model: r.model }))
        )
      )
    }
  )

  allFacts = allFindings.flat().filter(Boolean)
  log(`Extracted ${allFacts.length} facts from all workers`)

  phase('Validate')
  log('Arbiter validation and consensus...')

  validatedFacts = await agent(
    `Cross-check ${allFacts.length} facts from multiple workers.

Group similar claims, count cross-references, resolve conflicts, reject low-quality.

FACTS:
${JSON.stringify(allFacts.slice(0, 200), null, 2)}
${allFacts.length > 200 ? `\n... and ${allFacts.length - 200} more` : ''}`,
    {
      schema: VALIDATION_SCHEMA,
      model: 'opus',
      phase: 'Validate',
      label: 'arbiter'
    }
  )

  log(`Validated: ${validatedFacts.validated_facts.length}, Rejected: ${validatedFacts.rejected_facts.length}`)

  phase('Index')
  log(`Indexing facts in Universal AI ChromaDB...`)

  // Write facts to temp file for indexing
  const tempFile = '/tmp/web-learn-facts.json'

  const writeFacts = await agent(
    `Write this JSON to ${tempFile}:

${JSON.stringify({
  facts: validatedFacts.validated_facts,
  metadata: {
    urls,
    arbiter: validatedFacts.arbiter_model
  }
}, null, 2)}

Then run:
cd ${UNIVERSAL_AI_DIR}
python3 cli/rag_system.py --kbase ${kbaseName} --add ${tempFile}

Return: {indexed: number, message: "..."}`,
    { phase: 'Index', label: 'chromadb-index' }
  )

  log(`Indexed ${writeFacts.indexed} facts in ChromaDB`)
}

// Query mode
let queryResult = null
let ragResults = null

if (mode === 'query' || (mode === 'both' && query)) {
  phase('Query')
  log(`Querying Universal AI RAG: "${query}"`)

  ragResults = await agent(
    `Use Universal AI RAG to search for relevant facts:

cd ${UNIVERSAL_AI_DIR}
python3 cli/rag_system.py --kbase ${kbaseName} --search "${query}" --top-k 10

Return the retrieved facts as JSON: {chunks: [...], count: number}`,
    { phase: 'Query', label: 'rag-search' }
  )

  log(`Retrieved ${ragResults.count} relevant facts via semantic search`)

  if (ragResults.count === 0) {
    return {
      query,
      answer: 'No relevant knowledge found in the kbase.',
      suggestion: 'Run in learn mode first to build knowledge'
    }
  }

  // Synthesize answer using retrieved facts
  const context = ragResults.chunks.map(c =>
    `${c.content}\nSource: ${c.metadata?.source || 'unknown'}`
  ).join('\n\n')

  queryResult = await agent(
    `Answer this question using ONLY the provided facts from the knowledge base.

Question: ${query}

Retrieved Facts (semantic search):
${context}

Provide: direct answer, supporting facts used, confidence, gaps.`,
    {
      model: 'opus',
      phase: 'Query',
      label: 'synthesize-answer'
    }
  )

  log(`Answer generated with ${queryResult.confidence || 'unknown'} confidence`)
}

// Return results
const output = {
  mode,
  kbase: kbaseName,
  universal_ai_rag: true
  // Note: timestamp should be added by caller after workflow completes
}

if (mode === 'learn' || mode === 'both') {
  output.learning = {
    urls_processed: urls.length,
    facts_extracted: allFacts?.length || 0,
    facts_validated: validatedFacts.validated_facts.length,
    facts_rejected: validatedFacts.rejected_facts.length,
    arbiter: validatedFacts.arbiter_model,
    indexed_in_chromadb: true
  }
}

if (mode === 'query' || (mode === 'both' && query)) {
  output.query = {
    question: query,
    answer: queryResult,
    retrieved_chunks: ragResults?.count || 0,
    semantic_search: true
  }
}

output.rag_system = {
  type: 'Universal AI ChromaDB',
  persistent: true,
  semantic_embeddings: true,
  location: `${process.env.HOME}/.universal-ai/kbases/${kbaseName}/`
}

return output
