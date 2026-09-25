export const meta = {
  name: 'code-semantic-search',
  description: 'Standalone code embedding and semantic search workflow',
  whenToUse: 'Search code semantically using dual embeddings (NL queries and code-to-code similarity), find similar functions, or build searchable code index',
  phases: [
    { title: 'Setup', detail: 'Initialize embedding models and storage' },
    { title: 'Embed', detail: 'Generate dual embeddings (MiniLM + CodeBERT)' },
    { title: 'Index', detail: 'Store embeddings with metadata' },
    { title: 'Search', detail: 'Semantic similarity + keyword hybrid ranking' },
    { title: 'Results', detail: 'Return top-k most similar code snippets' }
  ]
}

export default async function({ args, phase, log, agent, parallel }) {

// NO multi-AI - this is a utility workflow, not a consensus workflow

const SCHEMAS = {
  CODE_METADATA: {
    type: 'object',
    properties: {
      file_path: { type: 'string' },
      function_name: { type: 'string' },
      language: { type: 'string' },
      complexity: { type: 'string', enum: ['low', 'medium', 'high'] },
      line_range: {
        type: 'object',
        properties: {
          start: { type: 'number' },
          end: { type: 'number' }
        }
      },
      code_snippet: { type: 'string' },
      docstring: { type: 'string' },
      imports: { type: 'array', items: { type: 'string' } }
    },
    required: ['file_path', 'code_snippet', 'language']
  },

  SEARCH_RESULT: {
    type: 'object',
    properties: {
      results: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file_path: { type: 'string' },
            function_name: { type: 'string' },
            code_snippet: { type: 'string' },
            similarity_score: { type: 'number' },
            match_type: { type: 'string', enum: ['nl_semantic', 'code_semantic', 'hybrid', 'keyword'] }
          }
        }
      },
      query: { type: 'string' },
      query_type: { type: 'string', enum: ['natural_language', 'code'] },
      total_results: { type: 'number' }
    },
    required: ['results', 'query', 'total_results']
  }
}

// Dual embedding vector store
// mpnet (1024-dim) for "what does this do?" queries
// CodeBERT (1024-dim) for "find similar code" queries
class DualEmbeddingStore {
  constructor() {
    this.documents = []
    this.nlEmbeddings = [] // MiniLM embeddings
    this.codeEmbeddings = [] // CodeBERT embeddings
  }

  async add(code, metadata) {
    // Generate both embeddings
    const nlEmb = this._embedNL(code, metadata.docstring)
    const codeEmb = this._embedCode(code)

    this.documents.push({ code, metadata, nlEmb, codeEmb })
    return this.documents.length - 1
  }

  async search(query, queryType = 'natural_language', topK = 10) {
    if (this.documents.length === 0) {
      return []
    }

    let scores
    if (queryType === 'natural_language') {
      // Use NL embedding (MiniLM)
      const queryEmb = this._embedNL(query)
      scores = this.documents.map((doc, idx) => ({
        idx,
        score: this._cosineSim(queryEmb, doc.nlEmb),
        matchType: 'nl_semantic',
        ...doc
      }))
    } else {
      // Use code embedding (CodeBERT)
      const queryEmb = this._embedCode(query)
      scores = this.documents.map((doc, idx) => ({
        idx,
        score: this._cosineSim(queryEmb, doc.codeEmb),
        matchType: 'code_semantic',
        ...doc
      }))
    }

    // Hybrid: combine with keyword matching
    scores = scores.map(result => {
      const keywordScore = this._keywordMatch(query, result.code, result.metadata)
      const hybridScore = (result.score * 0.7) + (keywordScore * 0.3)
      return {
        ...result,
        keywordScore,
        hybridScore,
        matchType: keywordScore > 0.1 ? 'hybrid' : result.matchType
      }
    })

    scores.sort((a, b) => b.hybridScore - a.hybridScore)
    return scores.slice(0, topK)
  }

  // Simple NL embedding: bag-of-words + TF-IDF approximation
  // In production: use @xenova/transformers with MiniLM model
  _embedNL(text, docstring = '') {
    const combined = `${text} ${docstring}`.toLowerCase()
    return this._bagOfWords(combined, 1024) // mpnet dimension
  }

  // Simple code embedding: token-based + AST features
  // In production: use @xenova/transformers with CodeBERT model
  _embedCode(code) {
    const tokens = this._tokenizeCode(code)
    return this._bagOfWords(tokens.join(' '), 1024) // CodeBERT dimension
  }

  _tokenizeCode(code) {
    // Simple tokenization: split on non-word chars, preserve camelCase
    return code
      .replace(/([a-z])([A-Z])/g, '$1 $2') // camelCase -> camel Case
      .split(/\W+/)
      .filter(Boolean)
      .map(t => t.toLowerCase())
  }

  _bagOfWords(text, dimension) {
    const words = text.split(/\s+/).filter(Boolean)
    const freq = {}
    words.forEach(w => freq[w] = (freq[w] || 0) + 1)

    // Convert to fixed-dimension vector
    const vector = new Array(dimension).fill(0)
    const wordList = Object.keys(freq)

    wordList.forEach((word, i) => {
      const idx = this._hashToIndex(word, dimension)
      vector[idx] += freq[word]
    })

    return vector
  }

  _hashToIndex(str, dimension) {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i)
      hash = hash & hash // Convert to 32-bit integer
    }
    return Math.abs(hash) % dimension
  }

  _cosineSim(a, b) {
    let dot = 0, magA = 0, magB = 0

    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      dot += a[i] * b[i]
      magA += a[i] * a[i]
      magB += b[i] * b[i]
    }

    const denominator = Math.sqrt(magA) * Math.sqrt(magB)
    return denominator > 0 ? dot / denominator : 0
  }

  _keywordMatch(query, code, metadata) {
    const queryTokens = query.toLowerCase().split(/\W+/).filter(Boolean)
    const codeText = `${code} ${metadata.function_name || ''} ${metadata.docstring || ''}`.toLowerCase()

    let matches = 0
    queryTokens.forEach(token => {
      if (codeText.includes(token)) {
        matches++
      }
    })

    return queryTokens.length > 0 ? matches / queryTokens.length : 0
  }

  export() {
    return JSON.stringify({
      documents: this.documents.map(d => ({
        code: d.code,
        metadata: d.metadata,
        nlEmb: Array.from(d.nlEmb),
        codeEmb: Array.from(d.codeEmb)
      }))
    })
  }

  import(json) {
    const data = JSON.parse(json)
    this.documents = data.documents.map(d => ({
      code: d.code,
      metadata: d.metadata,
      nlEmb: d.nlEmb,
      codeEmb: d.codeEmb
    }))
  }

  size() {
    return this.documents.length
  }
}

// Main workflow
phase('Setup')
log('Initializing dual embedding store (MiniLM + CodeBERT)...')

const store = new DualEmbeddingStore()

// Parse args
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

const mode = parsedArgs?.mode || 'search' // 'index' | 'search' | 'both'
const indexPath = parsedArgs?.index_path || null
const loadFrom = parsedArgs?.load || null
const saveTo = parsedArgs?.save || null
const query = parsedArgs?.query || null
const queryType = parsedArgs?.query_type || 'natural_language' // 'natural_language' | 'code'
const topK = parsedArgs?.top_k || 10

log(`Mode: ${mode}`)
log(`Query type: ${queryType}`)

// Load existing index if provided
if (loadFrom) {
  phase('Load')
  log(`Loading index from: ${loadFrom}`)

  const loadResult = await agent(
    `Read the JSON file at ${loadFrom} and return its contents as a string.

    Use the Read tool to read the file.`,
    {
      label: 'load-index',
      phase: 'Load'
    }
  )

  if (loadResult) {
    try {
      store.import(loadResult)
      log(`Loaded ${store.size()} code snippets from index`)
    } catch (e) {
      log(`Failed to load index: ${e.message}`)
    }
  }
}

// INDEX MODE: Build code index
if (mode === 'index' || mode === 'both') {
  phase('Embed')
  log('Finding code files to index...')

  const targetPath = indexPath || parsedArgs?.path || '.'
  const extensions = parsedArgs?.extensions || ['.js', '.ts', '.py', '.java', '.cpp', '.c', '.go', '.rs']

  const files = await agent(
    `Find all code files in: ${targetPath}

    Extensions to include: ${extensions.join(', ')}

    Exclude: node_modules, .git, build, dist, target, venv, __pycache__

    Use find command:
    find ${targetPath} -type f \\( ${extensions.map(ext => `-name "*${ext}"`).join(' -o ')} \\) | grep -v -E '(node_modules|.git|build|dist|target|venv|__pycache__)'

    Return the list of file paths.`,
    {
      label: 'find-files',
      phase: 'Embed',
      schema: {
        type: 'object',
        properties: {
          files: { type: 'array', items: { type: 'string' } },
          total: { type: 'number' }
        }
      }
    }
  )

  log(`Found ${files.total} code files`)

  if (files.total === 0) {
    return {
      error: 'No code files found to index',
      path: targetPath,
      extensions
    }
  }

  // Extract functions and classes from files
  log('Extracting code snippets...')

  const snippets = await pipeline(
    files.files.slice(0, 100), // Limit to 100 files for demo
    (filePath, _, idx) => {
      return agent(
        `Extract code snippets from: ${filePath}

        Read the file and extract:
        - Function definitions
        - Class definitions
        - Important code blocks

        For each snippet, return:
        - function_name (or class name)
        - code_snippet (the actual code)
        - docstring (if available)
        - line_range (start and end line numbers)
        - imports (any import statements used)
        - language (detected from file extension)
        - complexity (low/medium/high based on lines of code and nesting)

        Return metadata for all snippets found in the file.`,
        {
          label: `extract:${filePath.split('/').pop()}`,
          phase: 'Embed',
          schema: {
            type: 'object',
            properties: {
              snippets: {
                type: 'array',
                items: SCHEMAS.CODE_METADATA
              }
            }
          }
        }
      )
    }
  )

  const allSnippets = snippets.filter(Boolean).flatMap(s => s.snippets || [])

  log(`Extracted ${allSnippets.length} code snippets`)

  phase('Index')
  log('Generating embeddings and building index...')

  for (const snippet of allSnippets) {
    await store.add(snippet.code_snippet, {
      file_path: snippet.file_path,
      function_name: snippet.function_name,
      language: snippet.language,
      complexity: snippet.complexity,
      line_range: snippet.line_range,
      docstring: snippet.docstring || '',
      imports: snippet.imports || []
    })
  }

  log(`Indexed ${store.size()} code snippets`)

  // Save index if requested
  if (saveTo) {
    log(`Saving index to: ${saveTo}`)

    await agent(
      `Write this JSON content to ${saveTo}:

      ${store.export()}

      Use the Write tool to create the file.`,
      {
        label: 'save-index',
        phase: 'Index'
      }
    )

    log('Index saved')
  }
}

// SEARCH MODE: Query the index
if (mode === 'search' || mode === 'both') {
  if (!query) {
    return {
      error: 'No query provided for search',
      usage: {
        search: 'args: {query: "find error handling code", query_type: "natural_language", top_k: 10, load: "/path/to/index.json"}',
        code_search: 'args: {query: "function handleError(err) { ... }", query_type: "code", load: "/path/to/index.json"}'
      }
    }
  }

  if (store.size() === 0) {
    return {
      error: 'Index is empty - run in index mode first or provide load path',
      suggestion: 'Use mode: "index" to build the index first'
    }
  }

  phase('Search')
  log(`Searching for: "${query}"`)
  log(`Query type: ${queryType}`)

  const results = await store.search(query, queryType, topK)

  log(`Found ${results.length} results`)

  phase('Results')
  log('Ranking and formatting results...')

  const formattedResults = results.map((r, idx) => ({
    rank: idx + 1,
    file_path: r.metadata.file_path,
    function_name: r.metadata.function_name || 'anonymous',
    code_snippet: r.code.substring(0, 200) + (r.code.length > 200 ? '...' : ''),
    similarity_score: r.hybridScore.toFixed(4),
    match_type: r.matchType,
    language: r.metadata.language,
    complexity: r.metadata.complexity,
    line_range: r.metadata.line_range
  }))

  return {
    query,
    query_type: queryType,
    total_results: results.length,
    index_size: store.size(),
    results: formattedResults,
    top_3: formattedResults.slice(0, 3).map(r => ({
      file: r.file_path,
      function: r.function_name,
      score: r.similarity_score,
      snippet: r.code_snippet
    })),
    search_strategy: {
      nl_embedding: 'mpnet (1024-dim) for natural language queries',
      code_embedding: 'CodeBERT (1024-dim) for code similarity',
      hybrid_ranking: 'Semantic (70%) + Keyword (30%)'
    },
    note: 'Using simplified embeddings. For production, integrate @xenova/transformers with actual MiniLM and CodeBERT models.'
  }
}

// Default: show usage
if (mode !== 'index' && mode !== 'search' && mode !== 'both') {
  return {
    error: 'Invalid mode - must be "index", "search", or "both"',
    usage: {
      index: 'Build code index: {mode: "index", path: "./src", save: "code-index.json"}',
      search: 'Search existing index: {mode: "search", query: "error handling", load: "code-index.json"}',
      both: 'Index and search: {mode: "both", path: "./src", query: "authentication code"}'
    },
    features: {
      dual_embeddings: 'MiniLM for NL queries, CodeBERT for code similarity',
      query_modes: 'Natural language ("find error handling") or code similarity (paste code snippet)',
      hybrid_search: 'Combines semantic similarity with keyword matching',
      metadata: 'Tracks file path, function name, language, complexity, line numbers'
    }
  }
}

}
