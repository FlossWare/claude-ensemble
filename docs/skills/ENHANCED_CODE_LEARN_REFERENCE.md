# ai-web-code-learn Enhanced: Implementation Reference

## Quick Architecture Overview

```
Enhanced Code Learning Workflow

Input: Git Repository
    ↓
[Phase 1] Pre-Analysis
  ├─ Language detection
  ├─ File classification (core vs test vs config)
  ├─ Import/dependency mapping
  └─ Metrics collection (LOC, importance)
    ↓
[Phase 2] Structural Analysis
  ├─ AST parsing (language-specific)
  ├─ Extract functions/classes/types
  ├─ Build call graphs
  ├─ Control flow analysis
  └─ Calculate complexity metrics
    ↓
[Phase 3] Semantic Chunking
  ├─ Identify chunk boundaries (function/class level)
  ├─ Build chunk content (signature + docstring + context)
  ├─ Assign semantic tags
  └─ Calculate importance scores
    ↓
[Phase 4] Multi-AI Extraction (ENHANCED)
  ├─ Worker A: Semantic patterns (idioms, architecture)
  ├─ Worker B: Security analysis (vulns, dependencies)
  └─ Worker C: API contract (inputs, outputs, side effects)
    ↓
[Phase 5] Validation (ENHANCED)
  ├─ Structural validation (cross-check with AST)
  ├─ Semantic deduplication (resolve worker conflicts)
  ├─ Architecture synthesis (build component diagram)
  └─ Quality assessment
    ↓
[Phase 6] Embedding & Storage (DUAL)
  ├─ Generate semantic embeddings (Xenova/all-MiniLM)
  ├─ Store metadata to JSON
  └─ Persist embeddings to ChromaDB
    ↓
[Phase 7] Query Engine (ENHANCED)
  ├─ Intent detection (semantic vs structural vs dependency)
  ├─ Dual retrieval (embeddings + JSON index)
  ├─ Hybrid ranking (combine semantic + structural)
  └─ Context assembly (include dependencies, tests, examples)
    ↓
Output: Structured Answer + Code Examples + Dependency Chain
```

---

## Phase-by-Phase Details

### Phase 1: Pre-Analysis

**Input**: Repository directory
**Output**: File catalog with metadata

**Algorithm**:
1. Walk filesystem, collect all files
2. Classify each file:
   - Language detection (by extension + magic bytes)
   - Category: `core | test | config | docs | assets`
   - Importance heuristic (API exposure, called frequency estimate)

3. Lightweight dependency scan:
   - Parse `import/require` statements (regex, not AST)
   - Build edge list: `file A imports from file B`
   - Detect circular dependencies

4. Metrics collection:
   - Lines of code (LOC)
   - Comment ratio
   - Average line length
   - Cyclomatic complexity estimate (AST in Phase 2, but rough count here)

**Code Stub**:
```javascript
phase('Pre-Analysis')

const fileMetadata = []
for (const file of repoFiles) {
  const metadata = {
    path: file,
    language: detectLanguage(file),
    category: classifyFile(file),
    size: LOC(file),
    imports: extractImports(file),  // Regex-based
    importance: scoreImportance(file),
    // ... more fields
  }
  fileMetadata.push(metadata)
}

const dependencyEdges = buildDependencyGraph(fileMetadata)
const importantFiles = fileMetadata
  .filter(f => f.category === 'core')
  .sort((a, b) => b.importance - a.importance)
  .slice(0, maxFiles)

// Proceed to Phase 2 with filtered files
```

### Phase 2: Structural Analysis

**Input**: Important files + language info
**Output**: AST-derived code structure

**Per-Language Approaches**:

#### JavaScript/TypeScript
```javascript
import acorn from 'acorn'
import { parse } from '@typescript-eslint/parser'

const ast = parse(code, {
  ecmaVersion: 'latest',
  sourceType: 'module',
  ecmaFeatures: { jsx: true }
})

// Walk AST, extract:
// - FunctionDeclaration/ArrowFunction → function info
// - ClassDeclaration → class info
// - VariableDeclarator (if exported) → constants
// - ImportDeclaration → local dependencies
// - CallExpression → call sites

const functions = []
ast.body.forEach(node => {
  if (node.type === 'FunctionDeclaration') {
    functions.push({
      name: node.id.name,
      async: node.async,
      generator: node.generator,
      params: node.params.map(p => ({...})),
      loc: node.loc,
      docstring: extractJSDoc(node),
      // ... complexity calculated below
    })
  }
})

// Control flow analysis (simplified)
const complexity = calculateCyclomaticComplexity(ast)
```

#### Python (via subprocess)
```javascript
import { execSync } from 'child_process'

const pythonScript = `
import ast
import json
import sys

with open(sys.argv[1]) as f:
    tree = ast.parse(f.read())

# Extract functions, classes, etc.
functions = [...]
print(json.dumps(functions))
`

const result = JSON.parse(
  execSync(`python -c "${pythonScript}" "${filePath}"`).toString()
)
```

#### Multi-Language (tree-sitter)
```javascript
import Parser from 'tree-sitter'
import Python from 'tree-sitter-python'

const parser = new Parser()
parser.setLanguage(Python)

const tree = parser.parse(code)
const functions = queryNodes(tree, `
  (function_definition
    name: (identifier) @name
    parameters: (parameters) @params)
`)

// Works across C, Rust, Go, Python with same query API
```

**Complexity Calculation** (Cyclomatic):
```javascript
function calculateCyclomaticComplexity(ast) {
  let complexity = 1
  
  function traverse(node) {
    if (!node) return
    
    // Each branch increases complexity
    if (['IfStatement', 'ConditionalExpression'].includes(node.type)) {
      complexity++
    }
    if (['SwitchCase'].includes(node.type)) {
      complexity++
    }
    if (['DoWhileStatement', 'WhileStatement', 'ForStatement'].includes(node.type)) {
      complexity++
    }
    if (node.type === 'LogicalExpression' && node.operator === '||') {
      complexity++  // Each OR in condition
    }
    
    // Recurse
    for (const [, child] of Object.entries(node)) {
      if (Array.isArray(child)) child.forEach(traverse)
      else if (child?.type) traverse(child)
    }
  }
  
  traverse(ast)
  return complexity
}
```

**Call Graph Extraction**:
```javascript
const callGraph = new Map() // func_name → [called functions]

function extractCalls(ast, functionName) {
  const calls = []
  
  function traverse(node) {
    if (node.type === 'CallExpression') {
      const callee = node.callee
      if (callee.type === 'Identifier') {
        calls.push(callee.name)
      } else if (callee.type === 'MemberExpression') {
        // obj.method() → extract method name
        const obj = extractObject(callee.object)
        const method = callee.property.name
        calls.push(`${obj}.${method}`)
      }
    }
    // Recurse...
  }
  
  traverse(ast)
  return calls
}

// Reverse mapping (called by)
const callGraphReverse = buildReverseMap(callGraph)
```

**Dead Code Detection**:
```javascript
const exported = new Set()
const defined = new Set()
const called = new Set()

// Walk AST, build sets
ast.body.forEach(node => {
  if (node.type === 'ExportNamedDeclaration') {
    exported.add(node.declaration?.id?.name)
  }
  if (node.type === 'FunctionDeclaration') {
    defined.add(node.id.name)
  }
})

// Find unreachable function (defined but never called or exported)
const potentiallyDead = Array.from(defined).filter(
  name => !called.has(name) && !exported.has(name)
)

// Mark for review (not all are truly dead)
```

**Phase 2 Output**:
```javascript
{
  filePath: "src/api/users.js",
  language: "typescript",
  functions: [
    {
      id: "func_fetchUserData",
      name: "fetchUserData",
      signature: "(userId: string, options?: FetchOptions): Promise<User>",
      docstring: "Fetch user by ID with optional caching",
      async: true,
      exported: true,
      cyclomatic_complexity: 4,
      cognitive_complexity: 6,
      loc: { start: 45, end: 78 },
      parameters: [
        { name: "userId", type: "string", required: true },
        { name: "options", type: "FetchOptions", required: false }
      ],
      returns: { type: "Promise<User>" },
      calls: ["validateId", "cache.get", "api.request"],
      exceptions: ["NetworkError", "ValidationError"]
    }
  ],
  classes: [
    {
      id: "class_UserService",
      name: "UserService",
      methods: [
        // ... similar structure
      ],
      properties: [...]
    }
  ],
  imports: [
    { from: "./validators", items: ["validateId"] },
    { from: "@lib/cache", items: ["cache"] }
  ],
  potentiallyDeadCode: ["internalHelper", "deprecatedMethod"]
}
```

### Phase 3: Semantic Chunking

**Input**: Structured code from Phase 2
**Output**: Code chunks ready for embedding

**Chunking Strategy** (per language):

#### JavaScript/TypeScript
```javascript
const chunks = []

// Chunk 1: Each exported function/class
for (const func of structures.functions) {
  if (func.exported) {
    chunks.push({
      id: func.id,
      type: 'function',
      scope: 'module-export',
      content: {
        signature: func.signature,
        docstring: func.docstring,
        purpose: extractIntentFromDocstring(func.docstring),
        parameters: func.parameters,
        returns: func.returns,
        exceptions: func.exceptions,
        examples: extractFromComments(func),
        calls: func.calls,  // Dependencies within chunk
      },
      metadata: {
        file: filePath,
        line_range: func.loc,
        complexity: func.cyclomatic_complexity,
        importance: scoreImportance(func),
        tags: extractTags(func),  // ["async", "http", "validation", ...]
        frameworks: detectFrameworks(func),  // ["express", "prisma", ...]
      }
    })
  }
}

// Chunk 2: Each public method in a class
for (const cls of structures.classes) {
  for (const method of cls.methods) {
    chunks.push({
      id: `${cls.id}_${method.name}`,
      type: 'method',
      scope: 'class-method',
      content: {
        class: cls.name,
        signature: method.signature,
        docstring: method.docstring,
        // ... similar to function
      },
      metadata: {
        file: filePath,
        class_id: cls.id,
        // ...
      }
    })
  }
}

// Chunk 3: Internal utilities (if heavily called)
for (const func of structures.functions) {
  if (!func.exported && callGraphReverse[func.name]?.length > 3) {
    chunks.push({
      id: func.id,
      type: 'utility',
      scope: 'internal',
      content: { /* ... */ },
      metadata: {
        file: filePath,
        called_by_count: callGraphReverse[func.name].length,
        // ...
      }
    })
  }
}

return chunks
```

**Chunk Content Assembly**:
```javascript
function buildChunkContent(func, ast, file) {
  // Gather all relevant information for embedding
  const parts = [
    `Function: ${func.name}`,
    `Signature: ${func.signature}`,
    func.docstring || 'No documentation',
    `Purpose: ${extractIntentFromDocstring(func.docstring)}`,
    `Exceptions: ${func.exceptions.join(', ')}`,
  ]
  
  // Find related code (in same file, called by/calling)
  const related = findRelatedFunctions(func, structures)
  if (related.length > 0) {
    parts.push(`Related: ${related.map(r => r.name).join(', ')}`)
  }
  
  // Extract usage examples from tests
  const examples = findTestsForFunction(func.name, testFiles)
  if (examples.length > 0) {
    parts.push(`Usage: ${examples[0].code}`)
  }
  
  return parts.join('\n\n')
}
```

**Semantic Tags**:
```javascript
function extractSemanticTags(func) {
  const tags = new Set()
  
  // From signature
  if (func.async) tags.add('async')
  if (func.generator) tags.add('generator')
  
  // From docstring keywords
  if (func.docstring?.match(/http|request|fetch|api/i)) tags.add('http')
  if (func.docstring?.match(/validate|verify|check/i)) tags.add('validation')
  if (func.docstring?.match(/error|exception|throw/i)) tags.add('error_handling')
  
  // From dependencies
  if (func.calls.some(c => c.includes('db') || c.includes('query'))) tags.add('database')
  if (func.calls.some(c => c.includes('cache'))) tags.add('caching')
  
  // From framework usage
  if (func.signature.includes('Request')) tags.add('http-server')
  if (func.signature.includes('User')) tags.add('user-management')
  
  return Array.from(tags)
}
```

**Phase 3 Output** (10 chunks per file × 45 files = 450 chunks):
```javascript
[
  {
    chunk_id: "func_fetchUserData",
    name: "fetchUserData",
    file: "src/api/users.js",
    semantic_scope: "function",
    line_range: { start: 45, end: 78 },
    content: "Function: fetchUserData\nSignature: (userId: string, ...)\n...",
    semantic_tags: ["async", "http", "user-management"],
    importance: 0.95,  // Score 0-1
    test_coverage: 0.89,
    dependencies: ["validateId", "cache.get", "api.request"],
    embedding_ready: true
  },
  // ... 449 more chunks
]
```

### Phase 4: Multi-AI Extraction (Enhanced)

**Building on Existing Pattern**:

The current workflow already has this in `ai-web-code-learn.js`. We **enhance** it:

**Current Extraction Schema** (lines 15-27 in ai-web-code-learn.js):
```javascript
const CODE_EXTRACTION_SCHEMA = {
  properties: {
    file_path, language,
    classes: [], functions: [],
    implementation_patterns: [],
    key_insights: [],
    model: string
  }
}
```

**Enhanced Extraction Schema** (add to chunks):
```javascript
const ENHANCED_EXTRACTION_SCHEMA = {
  properties: {
    chunk_id, file_path, language, semantic_scope,
    
    // Structural (from Phase 2)
    structure: {
      name, signature, docstring,
      cyclomatic_complexity, cognitive_complexity,
      line_range, is_public, is_async
    },
    
    // Relationships (from Phase 2)
    relationships: {
      calls: string[],       // What this calls
      called_by: string[],   // What calls this
      imports: string[],
      depends_on: object[]   // External packages
    },
    
    // WORKER A: Semantic Patterns
    semantic_patterns: [
      {
        pattern: "Factory Pattern",
        category: "architecture",
        description: "Creates objects without exposing creation logic",
        examples: ["UserFactory.create()"],
        confidence: "high"
      }
    ],
    
    // WORKER B: Security Analysis
    security_insights: {
      vulnerabilities: [
        { cve: "CVE-2024-1234", severity: "medium", description: "..." }
      ],
      external_apis: [
        { service: "Stripe", risk_level: "medium", calls: ["charge()", "refund()"] }
      ],
      secrets_exposure: false
    },
    
    // WORKER C: API Contract
    api_contract: {
      parameters: [ { name, type, required, description } ],
      return_type: "Promise<User>",
      exceptions: ["NetworkError"],
      side_effects: ["writes to cache", "logs to stderr"],
      validation_rules: ["userId must be non-empty", "options.timeout must be > 0"]
    },
    
    // Quality
    code_quality: {
      dead_code_risk: false,
      test_coverage: 0.89,
      documentation_quality: "good",
      maintainability_index: 75
    },
    
    key_insights: string[],
    model: string
  }
}
```

**Parallel Worker Processing**:
```javascript
// Existing pattern (lines 133-141 in ai-web-code-learn.js)
const extractions = await parallel(
  chunks.slice(0, maxChunks).map(chunk => () =>
    agent(
      `Analyze code chunk: ${chunk.name}
      
      Signature: ${chunk.content.signature}
      Docstring: ${chunk.content.docstring}
      Calls: ${chunk.dependencies.join(', ')}
      
      Extract: semantic patterns, security insights, API contract, code quality.
      Format as JSON matching ENHANCED_EXTRACTION_SCHEMA.`,
      {
        label: `extract-${chunk.chunk_id}`,
        schema: ENHANCED_EXTRACTION_SCHEMA
      }
    )
  )
)
```

### Phase 5: Validation (Enhanced)

**Current Validation** (lines 145-157 in ai-web-code-learn.js):
```javascript
const validation = await agent(`Validate patterns from ${valid.length} files...`, {
  label: 'validate',
  model: arbiter.arbiter,
  schema: VALIDATION_SCHEMA
})
```

**Enhanced Validation Additions**:

1. **Structural Cross-Check**:
   ```javascript
   // Verify extracted patterns match AST reality
   for (const extraction of valid) {
     const chunk = chunks.find(c => c.chunk_id === extraction.chunk_id)
     const ast = parseAST(chunk.file)
     
     // Verify: function exists, signature matches, calls are valid
     const funcExists = ast.functions.some(f => f.id === extraction.structure.name)
     const callsExist = extraction.relationships.calls.every(call =>
       ast.functions.some(f => f.id === call) ||
       ast.classes.some(c => c.methods.some(m => m.id === call)) ||
       chunk.dependencies.includes(call)
     )
     
     if (!funcExists) {
       log(`⚠️ Extracted function ${extraction.structure.name} not found in AST`)
     }
     if (!callsExist) {
       log(`⚠️ Some calls don't resolve: ${extraction.relationships.calls}`)
     }
   }
   ```

2. **Semantic Deduplication**:
   ```javascript
   // Find duplicate patterns across workers
   const patternCounts = {}
   for (const extraction of valid) {
     for (const pattern of extraction.semantic_patterns) {
       const key = pattern.pattern
       patternCounts[key] = (patternCounts[key] || 0) + 1
     }
   }
   
   // High consensus = high confidence
   const consensusPatterns = Object.entries(patternCounts)
     .filter(([, count]) => count >= 2)
     .map(([pattern]) => ({ pattern, consensus: 'high' }))
   ```

3. **Architecture Synthesis**:
   ```javascript
   // Build dependency graph from all extractions
   const graph = new Map()
   for (const extraction of valid) {
     const name = extraction.structure.name
     graph.set(name, {
       calls: extraction.relationships.calls,
       called_by: [],
       file: extraction.file_path,
       scope: extraction.semantic_scope,
       complexity: extraction.structure.cyclomatic_complexity
     })
   }
   
   // Identify layers (presentation → business → data)
   const layers = identifyArchitecturalLayers(graph, validationPrompt)
   
   // Find hotspots (high complexity + high call frequency)
   const hotspots = Array.from(graph.values())
     .filter(node => node.complexity > 8 && node.called_by.length > 5)
     .map(node => ({ name: node.name, reason: "complexity + high coupling" }))
   ```

**Enhanced Validation Schema**:
```javascript
const ENHANCED_VALIDATION_SCHEMA = {
  type: 'object',
  properties: {
    validated_chunks: [
      {
        chunk_id, name,
        semantic_patterns: [],
        dependencies_verified: boolean,
        quality_grade: 'A|B|C|D',
        cross_references: number,  // How many workers found this
        notes: string[]
      }
    ],
    
    dependency_graph: {
      nodes: [ { id, label, scope, group } ],
      edges: [ { from, to, type: 'calls|imports|depends|inherits', weight } ]
    },
    
    architecture_summary: {
      layers: [
        { name: "API Layer", modules: [...], purpose: "..." },
        { name: "Service Layer", modules: [...], purpose: "..." },
        { name: "Data Layer", modules: [...], purpose: "..." }
      ],
      patterns_detected: string[],
      anti_patterns: [
        {
          type: "circular_dependency|god_object|tight_coupling",
          location: string,
          severity: "high|medium|low",
          recommendation: string
        }
      ],
      hotspots: [
        { name, reason, priority: "high|medium" }
      ]
    },
    
    quality_metrics: {
      documented_api_coverage: number,  // 0-1
      test_coverage_average: number,
      complexity_distribution: object,
      dead_code_ratio: number,
      security_issues_count: number
    },
    
    recommended_focus: string[],
    model: string
  }
}
```

**Arbiter Validation Prompt** (enhanced):
```javascript
const validation = await agent(`
You are the arbiter. Validate patterns from ${valid.length} code chunks.

STRUCTURAL VERIFICATION:
1. Confirm all extracted functions/classes exist in AST
2. Verify function calls are valid (do called functions exist?)
3. Check for circular dependencies
4. Validate type annotations

SEMANTIC SYNTHESIS:
1. Group similar patterns (even if workers used different names)
2. Count how many workers found each pattern (consensus)
3. Flag conflicts (workers disagree on a function's purpose)
4. Assign confidence levels

ARCHITECTURE:
1. Identify layers (API → Service → Data)
2. Spot hotspots (high complexity, high coupling)
3. Detect anti-patterns (circular deps, god objects)
4. Estimate maintainability

QUALITY:
1. Calculate average test coverage
2. Identify undocumented public APIs
3. Flag security concerns
4. Assess documentation completeness

VALIDATION OUTPUT:
${JSON.stringify(validated, null, 2).slice(0, 2000)}...

Return: validated_chunks[], dependency_graph, architecture_summary, quality_metrics`, {
  label: 'validate',
  model: arbiter.arbiter,
  schema: ENHANCED_VALIDATION_SCHEMA
})
```

### Phase 6: Embedding & Storage

**Parallel Embedding Generation**:
```javascript
phase('Embed')
log(`Generating embeddings for ${validated.length} chunks...`)

const embeddings = await parallel(
  validated.map((chunk, idx) => () =>
    agent(`
Generate semantic embedding for:

Name: ${chunk.structure.name}
Signature: ${chunk.structure.signature}
Docstring: ${chunk.structure.docstring}
Patterns: ${chunk.semantic_patterns.map(p => p.pattern).join(', ')}
Calls: ${chunk.relationships.calls.join(', ')}

Use @xenova/transformers with model: Xenova/all-MiniLM-L6-v2
Return: { embedding: [384 floats], chunk_id: "${chunk.chunk_id}" }`,
      { label: `embed-${idx}` }
    )
  )
)

const validEmbeddings = embeddings.filter(Boolean)
log(`✓ Generated ${validEmbeddings.length} embeddings`)
```

**Dual Storage Persistence**:

```javascript
phase('Store')

// 1. JSON Metadata (hierarchical, human-readable)
const metadata = {
  repo: repoUrl,
  branch,
  commit: getCommitHash(),
  cloned_at: new Date().toISOString(),
  stats: {
    files_analyzed: validFiles.length,
    chunks_created: validated.length,
    languages: ['typescript', 'javascript'],
    total_loc: sumLOC(validFiles),
    average_complexity: avg(validated.map(c => c.structure.cyclomatic_complexity))
  },
  chunks: validated.map(chunk => ({
    chunk_id: chunk.chunk_id,
    name: chunk.structure.name,
    file: chunk.file_path,
    semantic_scope: chunk.semantic_scope,
    line_range: chunk.structure.line_range,
    semantic_tags: chunk.metadata.tags,
    importance: chunk.metadata.importance,
    dependencies: chunk.relationships.calls,
    complexity: chunk.structure.cyclomatic_complexity,
    test_coverage: chunk.code_quality.test_coverage,
    quality_grade: chunk.code_quality.quality_grade,
    embedding_id: `embedding_${chunk.chunk_id}`
  })),
  dependency_graph: validation.dependency_graph,
  architecture: validation.architecture_summary,
  quality_metrics: validation.quality_metrics,
  created_at: new Date().toISOString()
}

await writeFile(
  `${dbPath}/code-learn-metadata.json`,
  JSON.stringify(metadata, null, 2)
)
log(`✓ Stored metadata: ${dbPath}/code-learn-metadata.json`)

// 2. ChromaDB Embeddings (vector search)
const chromaResult = await agent(`
Store ${validEmbeddings.length} embeddings in ChromaDB.

Collection: code-learn-chunks
Vector DB path: ${dbPath}/chromadb

For each embedding:
1. Connect to ChromaDB
2. Add document with:
   - id: chunk_id
   - embedding: [384-dim vector]
   - metadata: {
       name, file, scope, tags, importance,
       complexity, coverage, grade
     }
   - document: signature + docstring (for retrieval)

Return: { stored: number, collection: "code-learn-chunks" }`,
  { label: 'chromadb-persist' }
)

log(`✓ Stored embeddings: ${dbPath}/chromadb/code-learn-chunks`)
```

**File Structure**:
```
~/.claude/knowledge/
├─ code-learn/
│  ├─ code-learn-metadata.json       (45 KB, JSON index)
│  ├─ code-learn-analysis.json       (150 KB, architecture + quality)
│  │
│  └─ chromadb/
│     ├─ code-learn-chunks/
│     │  ├─ data/
│     │  │  ├─ index.db              (SQLite with embeddings)
│     │  │  ├─ 0.parquet             (vector storage)
│     │  │  └─ metadata.parquet      (chunk metadata)
│     │  │
│     │  └─ hnswlib_data.bin         (HNSW index for fast search)
│     │
│     └─ code-learn-relationships/   (Optional: separate collection)
│        └─ ...
│
└─ web-learning/                     (Existing ai-web-learn storage)
   └─ ...
```

**Total Storage**: ~2-5 MB for 1000-chunk codebase (metadata + embeddings)

### Phase 7: Enhanced Query & Retrieval

**Query Entry Point**:
```javascript
phase('Query')

// Parse query intent
const analysis = await agent(`
Analyze this code query and determine the search strategy:

Query: "${userQuery}"

Classify as one of:
- semantic_search: "Find similar code patterns"
- structural_search: "Find by name/structure"
- dependency_trace: "Follow call chains"
- pattern_match: "Find specific coding pattern"
- comparison: "Compare two pieces of code"

Return: { type: string, entities: string[], focus: string }`,
  { label: 'query-analysis' }
)

log(`Query type: ${analysis.type}`)
```

**Dual Retrieval**:
```javascript
let results = []

if (analysis.type === 'semantic_search') {
  // Generate query embedding
  const queryEmbedding = await agent(`
Generate embedding for query: "${userQuery}"
Use: Xenova/all-MiniLM-L6-v2
Return: { embedding: [384 floats] }`,
    { label: 'embed-query' }
  )
  
  // Search ChromaDB
  const semanticResults = await agent(`
Search ChromaDB with cosine similarity.

Collection: code-learn-chunks
Query embedding: [384 floats]
Top-k: 10

Return: { chunks: [{id, name, similarity_score}] }`,
    { label: 'semantic-search' }
  )
  
  results = semanticResults.chunks
    .map(r => ({
      ...r,
      method: 'semantic',
      score: r.similarity_score
    }))
} else if (analysis.type === 'structural_search') {
  // Look up by name in JSON index
  const structuralResults = metadata.chunks.filter(c =>
    c.name.includes(analysis.entities[0]) ||
    c.semantic_tags.some(t => t.includes(analysis.entities[0]))
  )
  
  results = structuralResults.map(r => ({
    ...r,
    method: 'structural',
    score: 1.0  // Exact match
  }))
} else if (analysis.type === 'dependency_trace') {
  // Follow dependency graph
  const startNode = findNode(analysis.entities[0])
  const path = traceDependencies(startNode, analysis.entities[1])
  
  results = path.map((node, idx) => ({
    ...node,
    method: 'dependency',
    score: 1.0 - (idx * 0.1)  // Decay with distance
  }))
}

// Hybrid ranking
results.sort((a, b) => b.score - a.score)
const top10 = results.slice(0, 10)
```

**Context Assembly**:
```javascript
// For each top result, gather context
const contextualResults = await Promise.all(top10.map(async result => {
  const chunk = metadata.chunks.find(c => c.chunk_id === result.chunk_id)
  const file = await readFile(chunk.file)
  const lines = file.split('\n').slice(
    chunk.line_range.start - 1,
    chunk.line_range.end
  )
  
  return {
    chunk_id: chunk.chunk_id,
    name: chunk.name,
    file: chunk.file,
    code_snippet: lines.join('\n'),
    similarity: result.score,
    
    // Related items
    calls: chunk.dependencies.map(dep =>
      metadata.chunks.find(c => c.name === dep)
    ),
    called_by: metadata.chunks.filter(c =>
      c.dependencies.includes(chunk.name)
    ).slice(0, 3),
    
    // Test coverage
    tests: findTestsForChunk(chunk.name),
    
    // Quality indicator
    quality_grade: chunk.quality_grade,
    complexity: chunk.complexity
  }
}))
```

**Answer Synthesis** (multi-worker + arbiter):
```javascript
const answers = await parallel(['opus', 'sonnet', 'haiku'].map(model => () =>
  agent(`
Answer this code question using the retrieved code chunks:

Question: ${userQuery}

Retrieved Chunks:
${contextualResults.map(r =>
  `${r.name} [${r.file}:${r.line}]
   Similarity: ${(r.similarity * 100).toFixed(1)}%
   Complexity: ${r.complexity}, Grade: ${r.quality_grade}
   Calls: ${r.calls.map(c => c?.name).join(', ')}
   Code:
   ${r.code_snippet}`.trim()
).join('\n\n---\n\n')}

Provide:
1. Direct answer to the question
2. Code examples with line numbers
3. Complexity/quality notes
4. Related functions or call chains`,
    {
      model,
      schema: {
        type: 'object',
        properties: {
          answer: { type: 'string' },
          code_examples: { type: 'array' },
          complexity_notes: { type: 'string' },
          related_functions: { type: 'array' },
          confidence: { type: 'string' }
        }
      }
    }
  )
))

const bestAnswer = await agent(`
Select the best answer: ${answers.map(a => a.answer).join('\n---\n')}

Pick the most concise, accurate, well-cited answer.`,
  { label: 'arbiter-query', model: 'opus' }
)
```

**Final Query Result**:
```javascript
{
  query: "How do we validate user input?",
  query_type: "pattern_match",
  answer: "Validation happens at three layers...",
  code_examples: [
    {
      location: "src/api/middleware.js:45",
      name: "validateRequest",
      code: "...",
      explanation: "API layer validation",
      complexity: 4,
      quality_grade: "A"
    }
  ],
  call_chain: [
    {
      step: 1,
      component: "HTTP Route Handler",
      function: "POST /users",
      calls_next: "validateRequest",
      annotation: "Middleware validates request before handler"
    },
    {
      step: 2,
      component: "Validation Service",
      function: "validateRequest",
      calls_next: "User.validate",
      annotation: "Delegates to model validation"
    },
    {
      step: 3,
      component: "User Model",
      function: "User.validate",
      calls_next: "db.insert",
      annotation: "Database constraints as final check"
    }
  ],
  retrieved_chunks: 8,
  confidence: "high",
  related_topics: [
    "Error handling strategy",
    "Security best practices",
    "Test coverage for validation"
  ]
}
```

---

## Integration with Existing Workflow

**Current Structure** (ai-web-code-learn.js):
```
Phase: Setup (lines 82-99)
Phase: Discover (lines 101-129)
Phase: Extract (lines 131-143)
Phase: Validate (lines 145-157)
Phase: Store (lines 159-174)
Phase: Query (lines 188-244)
```

**Enhanced Insertion Points**:
1. **Between Setup and Discover**: Add Phase 1 (Pre-Analysis)
2. **After Discover**: Add Phase 2 (Structural Analysis) + Phase 3 (Semantic Chunking)
3. **Replace Extract**: Expand to use chunks + enhanced schema
4. **Enhance Validate**: Add structural checks + architecture synthesis
5. **Enhance Store**: Add ChromaDB + JSON dual storage
6. **Replace Query**: Implement Phase 7 (dual retrieval + ranking)

**Backward Compatibility**:
- Keep old Extract/Validate schemas in constants
- Auto-detect if user provides mode: "legacy" or mode: "enhanced"
- Old: patterns extracted at file level
- New: patterns extracted at function/class level

---

## Example Queries & Their Processing

### Example 1: Semantic Pattern Search

```
User Query: "How do you handle async operations and error handling together?"

Step 1: Query Analysis
→ type: "pattern_match"
→ entities: ["async", "error_handling"]
→ focus: "implementation patterns"

Step 2: Dual Retrieval
→ Semantic: Find chunks mentioning "async" + "error" patterns
   ChromaDB returns: fetchUserData, processPayment, loadCache
→ Structural: Filter semantic_tags for ["async", "error_handling"]
   JSON index returns: 23 functions with both tags

Step 3: Ranking
→ Combine semantic similarity + structural exactness
→ Boost importance score (API surface > internals)
→ Result: fetchUserData (0.92), processPayment (0.89), handleErrors (0.87)

Step 4: Context Assembly
→ For each: code snippet, related calls, test examples
→ fetchUserData calls: validateId, cache.get, api.request
→ Test example: test_fetchUserData_withError

Step 5: Answer Synthesis
→ Workers (Opus, Sonnet, Haiku) formulate answers
→ Arbiter picks best

Result:
"We combine async/await with try-catch blocks in all API handlers.
Example: fetchUserData() [src/api/users.js:45]
  - Uses async/await for clarity
  - try-catch wraps all external calls
  - Logs errors but doesn't crash process
Related: processPayment() shows similar pattern with retry logic"
```

### Example 2: Dependency Trace

```
User Query: "What's the complete call chain from login() to database?"

Step 1: Query Analysis
→ type: "dependency_trace"
→ entities: ["login", "database"]
→ focus: "call chain"

Step 2: Structural Search (Graph Traversal)
→ Find node: login() [src/api/auth.js:50]
→ Follow "calls" edges
→ login → authenticate → validateToken → getUser → db.query
→ Extract full path with nodes

Step 3: Context for Each Node
→ login: async, exported, 3 params, 89% coverage
→ authenticate: internal, 2 params, 95% coverage
→ validateToken: pure function, 100% coverage
→ getUser: async, 1 param, 78% coverage
→ db.query: 500ms latency, external call

Step 4: Assembly
→ Build chain with annotations
→ Include error paths (failure at validate → return 401)
→ Show test coverage gaps (getUser at 78%)

Result:
"Call chain from login to database:
1. login() [auth.js:50] - async, validates input
   ↓ calls
2. authenticate() [auth.js:75] - generates/validates token
   ↓ calls
3. validateToken() [crypto.js:120] - pure, no side effects
   ↓ calls
4. getUser() [db.js:200] - async, queries database
   ↓ calls (implicit)
5. db.query() [db.js:50] - external PostgreSQL call

Coverage: 89% → 95% → 100% → 78% → N/A
Latency: 5ms + 10ms + 2ms + 500ms + varies
Risk: getUser() has low test coverage for error cases"
```

### Example 3: Security Scanning

```
User Query: "Where are external API calls and what's the security posture?"

Step 1: Query Analysis
→ type: "structural_search"
→ entities: ["external_api", "security"]
→ focus: "vulnerability analysis"

Step 2: Filtered Retrieval
→ JSON index: filter chunks where security_insights.external_apis exists
→ Group by service: Stripe, GitHub, AWS, etc.
→ Extract vulnerability count

Step 3: Detail Retrieval
→ For each external API chunk: function name, calls, error handling
→ Semantic search: find similar API patterns for consistency
→ Check: are all external calls behind retry logic?

Step 4: Architecture Analysis
→ Validate: Do all external calls have timeouts?
→ Flag: API keys in environment or hardcoded?
→ Check: Error handling (graceful degradation or cascade failure?)

Result:
"External API Calls:
1. Stripe API [src/payment/checkout.js:100]
   - Calls: charge(), refund(), createCustomer()
   - Error handling: try-catch with logging
   - Timeout: 30s
   - Test coverage: 95%
   
2. GitHub API [src/oauth/github.js:45]
   - Calls: getUser(), getRepositories()
   - Error handling: retry logic with backoff
   - Timeout: 10s
   - Test coverage: 88%
   
Security Issues:
⚠️ CVE-2024-1234 in github-api/2.1.0 (severity: medium)
   Recommendation: Upgrade to ^2.5.0
   
⚠️ Missing error handling in AWS S3 download [src/storage/s3.js:200]
   Risk: Could crash process on network timeout
   Suggestion: Add timeout + retry"
```

---

## Performance & Scalability

### Embedding Generation
- **Batch size**: 50 chunks at a time (respects token limits)
- **Latency**: ~100-200ms per chunk for embedding
- **Total time** (10k chunks): ~20-40 minutes
- **Memory**: ~500MB for ChromaDB client + embeddings

### Search Latency
- **Semantic search** (chromadb): ~50-200ms
- **Structural search** (JSON): ~5-50ms
- **Hybrid combined**: ~150-250ms
- **Network overhead** (to Anthropic API): ~500ms base

### Storage Efficiency
```
Per chunk:
- Metadata (JSON): ~200 bytes
- Embedding (384-dim floats): ~1.5 KB
- Total: ~1.7 KB/chunk

For 10k chunks:
- Total: ~17 MB
- Breakdown: metadata 2 MB, embeddings 15 MB
```

### Scaling to 100k+ chunks
- Split into multiple collections (by package/layer)
- Implement lazy-loading (don't load all at query time)
- Use ChromaDB filtering for pre-filtering before embedding search
- Consider external embedding provider (HuggingFace Inference API) for speed

---

## Error Handling & Validation

**Robustness Patterns**:
1. **AST Parse Failures**: Skip file, log error, continue with others
2. **Extraction Schema Mismatch**: Store as-is, flag in audit log
3. **ChromaDB Unavailable**: Fallback to JSON-only search
4. **Missing Test Files**: Flag "untested" but don't fail

**Verification Hooks**:
```javascript
// Validate chunk IDs are unique
const ids = validated.map(c => c.chunk_id)
if (new Set(ids).size !== ids.length) {
  throw new Error('Duplicate chunk IDs detected')
}

// Validate dependency graph has no invalid edges
for (const edge of validation.dependency_graph.edges) {
  const fromExists = graph.has(edge.from)
  const toExists = graph.has(edge.to)
  if (!fromExists || !toExists) {
    log(`⚠️ Invalid edge: ${edge.from} → ${edge.to}`)
  }
}

// Validate metadata consistency
for (const chunk of metadata.chunks) {
  if (!fs.existsSync(chunk.file)) {
    log(`⚠️ File not found: ${chunk.file}`)
  }
}
```

---

End of Reference Document
