# ai-web-code-learn Enhancement: Implementation Roadmap

## Overview

This roadmap details the step-by-step implementation plan for enhancing `ai-web-code-learn.js` with deep learning and code analysis capabilities.

**Total Effort**: ~12 weeks (60-80 engineer-days)
**Dependencies**: Add ~15-20 npm packages
**Backward Compatibility**: Full (legacy mode available)
**Testing Strategy**: Unit → Integration → End-to-end

---

## Sprint Planning

### Sprint 0: Foundation & Dependency Setup (Week 1)

**Goal**: Prepare dependencies, create scaffolding, establish test patterns

**Tasks**:
- [ ] Update package.json with new dependencies
  - AST parsers: `acorn`, `@babel/parser`, `@typescript-eslint/parser`
  - Analysis tools: `complexity-report`, `graphlib`, `uuid`, `cosine-similarity`
  - Existing: `@xenova/transformers`, `chromadb`

- [ ] Create `/lib/` folder structure:
  ```
  lib/
  ├─ analyzers/
  │  ├─ pre-analysis.js
  │  ├─ structural-analysis.js
  │  ├─ complexity.js
  │  └─ dependency-graph.js
  ├─ chunking/
  │  ├─ semantic-chunker.js
  │  └─ chunk-enricher.js
  ├─ storage/
  │  ├─ json-store.js
  │  └─ chromadb-store.js
  ├─ query/
  │  ├─ dual-retriever.js
  │  ├─ query-ranker.js
  │  └─ context-assembler.js
  ├─ schemas/
  │  ├─ extraction.js
  │  ├─ validation.js
  │  └─ query.js
  └─ utils/
     ├─ language-detection.js
     ├─ file-classification.js
     └─ cache.js
  ```

- [ ] Create test directory structure:
  ```
  test/
  ├─ unit/
  │  ├─ analyzers.test.js
  │  ├─ chunking.test.js
  │  ├─ storage.test.js
  │  └─ query.test.js
  ├─ integration/
  │  └─ full-workflow.test.js
  └─ fixtures/
     ├─ sample-js-files/
     └─ sample-responses/
  ```

- [ ] Create type definitions (optional JSDoc or TypeScript):
  ```javascript
  /**
   * @typedef {Object} Chunk
   * @property {string} chunk_id
   * @property {string} name
   * @property {string} file
   * @property {'function'|'class'|'module'} semantic_scope
   * @property {Object} structure
   * @property {Object} relationships
   * @property {Array} semantic_patterns
   * @property {Object} code_quality
   */
  ```

- [ ] Establish CI/CD pipeline:
  - [ ] npm test (unit tests)
  - [ ] npm run lint (ESLint)
  - [ ] npm run test:integration (on sample repos)

**Deliverable**: Workspace ready for development, dependency chain validated

---

### Sprint 1: Language Detection & Pre-Analysis (Week 1-2)

**Goal**: Implement Phase 1 (Pre-Analysis) with language detection and file classification

**Files to Create**:
- `lib/utils/language-detection.js`
- `lib/utils/file-classification.js`
- `lib/analyzers/pre-analysis.js`
- `test/unit/language-detection.test.js`

**Implementation Steps**:

**1. Language Detection** (`lib/utils/language-detection.js`):
```javascript
/**
 * Detect programming language from file
 * @param {string} filePath
 * @param {Buffer} fileContent (optional)
 * @returns {string} language code: 'javascript', 'typescript', 'python', etc.
 */
export function detectLanguage(filePath, fileContent) {
  // 1. Extension-based (fast path)
  const ext = path.extname(filePath).toLowerCase()
  const extensionMap = {
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.py': 'python',
    '.go': 'go',
    '.rs': 'rust',
    '.java': 'java',
    '.c': 'c',
    '.cpp': 'cpp',
  }
  
  if (extensionMap[ext]) return extensionMap[ext]
  
  // 2. Content-based (magic bytes, shebang)
  if (fileContent) {
    const content = fileContent.toString('utf8', 0, 500)
    if (content.startsWith('#!/usr/bin/env python')) return 'python'
    if (content.startsWith('#!/usr/bin/env node')) return 'javascript'
  }
  
  return 'unknown'
}
```

**2. File Classification** (`lib/utils/file-classification.js`):
```javascript
/**
 * Classify file by purpose
 * @returns {'core'|'test'|'config'|'docs'|'assets'}
 */
export function classifyFile(filePath) {
  const patterns = {
    test: [/\.test\.(js|ts)$/, /\.spec\.(js|ts)$/, /^test\//, /^__tests__\//],
    config: [/^\./, /config\.(js|ts)$/, /webpack/, /tsconfig/, /babel/, /\.json$/],
    docs: [/\.md$/, /\.txt$/, /README/],
    assets: [/\.css$/, /\.scss$/, /\.json$/, /\.png$/, /\.svg$/]
  }
  
  for (const [category, regexes] of Object.entries(patterns)) {
    if (regexes.some(r => r.test(filePath))) return category
  }
  
  return 'core'
}

/**
 * Calculate file importance score
 * @returns {number} 0-1
 */
export function scoreImportance(filePath, stats) {
  let score = 0.5  // base
  
  // API files are important
  if (filePath.includes('api') || filePath.includes('routes')) score += 0.3
  
  // Service files are important
  if (filePath.includes('service') || filePath.includes('handler')) score += 0.2
  
  // Main/index files are important
  if (filePath.endsWith('index.js') || filePath.endsWith('main.js')) score += 0.1
  
  // Smaller files might be utilities (lower priority)
  if (stats.loc < 50) score -= 0.1
  
  return Math.min(1, score)
}
```

**3. Pre-Analysis Orchestrator** (`lib/analyzers/pre-analysis.js`):
```javascript
/**
 * Phase 1: Pre-Analysis
 * - Walk repo, detect languages, classify files
 * - Build lightweight dependency graph
 * - Calculate importance scores
 */
export async function preAnalyze(repoPath, options = {}) {
  const files = walkDirectory(repoPath)
  
  const fileMetadata = files.map(file => {
    const language = detectLanguage(file)
    const category = classifyFile(file)
    const stats = {
      loc: countLinesOfCode(file),
      size: getFileSize(file)
    }
    
    return {
      path: file,
      language,
      category,
      importance: scoreImportance(file, stats),
      stats,
      imports: extractImportsRegex(file)  // Fast regex-based
    }
  })
  
  // Filter: keep core files only
  const importantFiles = fileMetadata
    .filter(f => f.category === 'core')
    .sort((a, b) => b.importance - a.importance)
    .slice(0, options.maxFiles || 50)
  
  // Build dependency graph (lightweight)
  const depGraph = buildDependencyGraph(importantFiles)
  
  return {
    files: importantFiles,
    dependencyGraph: depGraph,
    stats: {
      total_files: files.length,
      core_files: importantFiles.length,
      languages: new Set(fileMetadata.map(f => f.language))
    }
  }
}
```

**4. Unit Tests** (`test/unit/language-detection.test.js`):
```javascript
import { detectLanguage, classifyFile } from '../../lib/utils/language-detection.js'
import { test } from 'node:test'
import * as assert from 'node:assert'

test('detectLanguage - by extension', () => {
  assert.equal(detectLanguage('index.js'), 'javascript')
  assert.equal(detectLanguage('app.ts'), 'typescript')
  assert.equal(detectLanguage('main.py'), 'python')
})

test('classifyFile - identifies test files', () => {
  assert.equal(classifyFile('app.test.js'), 'test')
  assert.equal(classifyFile('__tests__/unit.js'), 'test')
})

test('classifyFile - identifies config files', () => {
  assert.equal(classifyFile('webpack.config.js'), 'config')
  assert.equal(classifyFile('tsconfig.json'), 'config')
})
```

**Deliverable**: Phase 1 complete with tests passing

---

### Sprint 2: AST Parsing & Structural Analysis (Week 2-4)

**Goal**: Implement Phase 2 (Structural Analysis) with language-specific AST parsing

**Files to Create**:
- `lib/analyzers/structural-analysis.js`
- `lib/analyzers/ast-parser.js`
- `lib/analyzers/complexity.js`
- `lib/analyzers/dependency-graph.js`
- `test/unit/structural-analysis.test.js`

**Implementation Steps**:

**1. AST Parser Abstraction** (`lib/analyzers/ast-parser.js`):
```javascript
import * as acorn from 'acorn'
import { parse as parseTS } from '@typescript-eslint/parser'

/**
 * Parse code and return AST (language-aware)
 * @param {string} code
 * @param {string} language
 * @returns {Object} AST
 */
export function parseAST(code, language) {
  switch (language) {
    case 'javascript':
    case 'jsx':
      return acorn.parse(code, {
        ecmaVersion: 'latest',
        sourceType: 'module'
      })
    
    case 'typescript':
    case 'tsx':
      return parseTS(code, {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true }
      })
    
    default:
      throw new Error(`Unsupported language: ${language}`)
  }
}

/**
 * Extract functions from AST
 */
export function extractFunctions(ast, filePath) {
  const functions = []
  
  function traverse(node, parent = null) {
    if (!node) return
    
    // Function declarations
    if (node.type === 'FunctionDeclaration') {
      functions.push({
        id: `func_${node.id.name}_${filePath}`,
        name: node.id.name,
        type: 'function',
        async: node.async,
        generator: node.generator,
        params: extractParams(node.params),
        loc: node.loc,
        body: node.body,
        parent,
        docstring: extractJSDoc(node, ast)
      })
    }
    
    // Arrow functions / function expressions (if exported)
    if (node.type === 'VariableDeclarator' && isArrowFunction(node.init)) {
      functions.push({
        id: `func_${node.id.name}_${filePath}`,
        name: node.id.name,
        type: 'arrow',
        async: node.init.async,
        // ... similar fields
      })
    }
    
    // Recurse
    for (const [, child] of Object.entries(node)) {
      if (Array.isArray(child)) {
        child.forEach(c => traverse(c, node))
      } else if (child?.type) {
        traverse(child, node)
      }
    }
  }
  
  traverse(ast)
  return functions
}

/**
 * Extract classes from AST
 */
export function extractClasses(ast, filePath) {
  const classes = []
  
  function traverse(node) {
    if (node.type === 'ClassDeclaration') {
      const methods = node.body.body
        .filter(m => m.type === 'MethodDefinition')
        .map(m => ({
          name: m.key.name,
          kind: m.kind,  // 'method', 'get', 'set', 'constructor'
          params: extractParams(m.value.params),
          // ...
        }))
      
      classes.push({
        id: `class_${node.id.name}_${filePath}`,
        name: node.id.name,
        methods,
        superClass: node.superClass?.name,
        loc: node.loc,
        docstring: extractJSDoc(node, ast)
      })
    }
    
    // Recurse...
  }
  
  traverse(ast)
  return classes
}

/**
 * Extract imports
 */
export function extractImports(ast) {
  const imports = []
  
  ast.body.forEach(node => {
    if (node.type === 'ImportDeclaration') {
      imports.push({
        from: node.source.value,
        items: node.specifiers.map(s => ({
          local: s.local.name,
          imported: s.imported?.name || 'default'
        }))
      })
    }
  })
  
  return imports
}
```

**2. Complexity Calculation** (`lib/analyzers/complexity.js`):
```javascript
/**
 * Calculate cyclomatic complexity
 * Higher = more branches = harder to test
 */
export function calculateCyclomaticComplexity(ast) {
  let complexity = 1
  
  function traverse(node) {
    if (!node) return
    
    // Decision points
    if (['IfStatement', 'ConditionalExpression'].includes(node.type)) {
      complexity++
    }
    if (node.type === 'SwitchStatement') {
      complexity += node.cases.length
    }
    if (['DoWhileStatement', 'WhileStatement', 'ForStatement'].includes(node.type)) {
      complexity++
    }
    if (node.type === 'ForInStatement') {
      complexity++
    }
    if (node.type === 'LogicalExpression' && node.operator === '||') {
      complexity++
    }
    if (node.type === 'CatchClause') {
      complexity++
    }
    
    // Recurse
    for (const [, child] of Object.entries(node)) {
      if (Array.isArray(child)) {
        child.forEach(traverse)
      } else if (child?.type) {
        traverse(child)
      }
    }
  }
  
  traverse(ast)
  return complexity
}

/**
 * Estimate cognitive complexity
 * Harder to understand; considers nesting level
 */
export function calculateCognitiveComplexity(ast) {
  let complexity = 0
  let nesting = 0
  
  function traverse(node, depth = 0) {
    if (!node) return
    
    if (['IfStatement', 'ForStatement', 'WhileStatement'].includes(node.type)) {
      complexity += (1 + depth)
      nesting = Math.max(nesting, depth)
    }
    
    // Recurse
    for (const [, child] of Object.entries(node)) {
      if (Array.isArray(child)) {
        child.forEach(c => traverse(c, node.type?.includes('Statement') ? depth + 1 : depth))
      } else if (child?.type) {
        traverse(child, node.type?.includes('Statement') ? depth + 1 : depth)
      }
    }
  }
  
  traverse(ast)
  return { complexity, nesting }
}
```

**3. Structural Analysis Orchestrator** (`lib/analyzers/structural-analysis.js`):
```javascript
import { parseAST, extractFunctions, extractClasses, extractImports } from './ast-parser.js'
import { calculateCyclomaticComplexity, calculateCognitiveComplexity } from './complexity.js'

/**
 * Phase 2: Structural Analysis
 * Parse files with AST, extract structure, calculate metrics
 */
export async function analyzeStructure(filePath, language) {
  const code = await readFile(filePath, 'utf8')
  
  // Parse
  let ast
  try {
    ast = parseAST(code, language)
  } catch (e) {
    log(`⚠️ Failed to parse ${filePath}: ${e.message}`)
    return null
  }
  
  // Extract components
  const functions = extractFunctions(ast, filePath)
  const classes = extractClasses(ast, filePath)
  const imports = extractImports(ast)
  
  // Calculate metrics
  const enhanced = [
    ...functions.map(f => ({
      ...f,
      cyclomatic_complexity: calculateCyclomaticComplexity(f.body),
      cognitive_complexity: calculateCognitiveComplexity(f.body)?.complexity
    })),
    ...classes.map(c => ({
      ...c,
      methods: c.methods.map(m => ({
        ...m,
        complexity: calculateCyclomaticComplexity(m.ast)
      }))
    }))
  ]
  
  // Detect dead code
  const dead = detectDeadCode(enhanced, imports)
  
  return {
    filePath,
    language,
    functions: enhanced.filter(x => x.type === 'function'),
    classes: enhanced.filter(x => x.type === 'class'),
    imports,
    deadCode: dead,
    stats: {
      total_functions: enhanced.filter(x => x.type === 'function').length,
      total_classes: enhanced.filter(x => x.type === 'class').length
    }
  }
}

/**
 * Simple dead code detection
 */
function detectDeadCode(items, imports) {
  const exported = new Set(items.filter(x => x.exported).map(x => x.name))
  const defined = new Set(items.map(x => x.name))
  const called = new Set()
  
  // Collect all function calls
  items.forEach(item => {
    if (item.calls) {
      item.calls.forEach(c => called.add(c))
    }
  })
  
  // Potentially dead: defined but not called/exported
  return Array.from(defined).filter(
    name => !called.has(name) && !exported.has(name)
  )
}
```

**4. Unit Tests** (`test/unit/structural-analysis.test.js`):
```javascript
import { analyzeStructure } from '../../lib/analyzers/structural-analysis.js'
import { test } from 'node:test'
import * as assert from 'node:assert'

test('analyzeStructure - extracts functions', async () => {
  const result = await analyzeStructure('test/fixtures/sample.js', 'javascript')
  assert.ok(result.functions.length > 0)
  assert.ok(result.functions[0].name)
  assert.ok(result.functions[0].cyclomatic_complexity >= 1)
})

test('analyzeStructure - calculates complexity', async () => {
  // Create a file with known complexity
  const code = `function test(x) { if (x) { if (x > 5) { return x } } return 0 }`
  // Expected complexity: 1 + 2 (two if statements) = 3
  const complexity = calculateCyclomaticComplexity(parseAST(code, 'javascript').body[0])
  assert.equal(complexity, 3)
})
```

**Deliverable**: Phase 2 complete with full AST parsing and metrics

---

### Sprint 3: Semantic Chunking (Week 4-5)

**Goal**: Implement Phase 3 (Semantic Chunking) with intelligent code boundaries

**Files to Create**:
- `lib/chunking/semantic-chunker.js`
- `lib/chunking/chunk-enricher.js`
- `lib/chunking/importance-scorer.js`
- `test/unit/chunking.test.js`

**Implementation Steps**:

**1. Semantic Chunker** (`lib/chunking/semantic-chunker.js`):
```javascript
import { v4 as uuidv4 } from 'uuid'

/**
 * Phase 3: Create semantic chunks from code structure
 * Boundaries: function, class, interface
 */
export function createSemanticChunks(analysis) {
  const chunks = []
  const { filePath, language, functions, classes } = analysis
  
  // Chunk 1: Each exported function
  for (const func of functions.filter(f => f.exported)) {
    chunks.push({
      chunk_id: `chunk_${uuidv4().slice(0, 8)}`,
      name: func.name,
      file: filePath,
      language,
      semantic_scope: 'function',
      
      structure: {
        signature: func.signature || reconstructSignature(func),
        docstring: func.docstring,
        cyclomatic_complexity: func.cyclomatic_complexity,
        cognitive_complexity: func.cognitive_complexity,
        line_range: func.loc,
        is_public: func.exported,
        is_async: func.async
      },
      
      relationships: {
        calls: func.calls || [],
        called_by: [],  // Will fill from global graph
        imports: [],
        depends_on: []
      },
      
      content: buildChunkContent(func),
      metadata: {
        tags: extractSemanticTags(func),
        importance: 0.5,  // Will be scored later
        framework_specific: []
      }
    })
  }
  
  // Chunk 2: Each public class method
  for (const cls of classes) {
    for (const method of cls.methods.filter(m => m.kind !== 'private')) {
      chunks.push({
        chunk_id: `chunk_${uuidv4().slice(0, 8)}`,
        name: `${cls.name}.${method.name}`,
        file: filePath,
        language,
        semantic_scope: 'method',
        
        structure: {
          class: cls.name,
          signature: reconstructMethodSignature(method),
          docstring: method.docstring,
          cyclomatic_complexity: method.complexity,
          line_range: method.loc,
          is_public: method.kind !== 'private',
          is_async: method.async
        },
        
        relationships: {
          calls: method.calls || [],
          called_by: [],
          imports: [],
          depends_on: []
        },
        
        content: buildChunkContent(method, cls),
        metadata: {
          tags: extractSemanticTags(method),
          importance: 0.6,  // Class methods often important
          framework_specific: []
        }
      })
    }
  }
  
  // Chunk 3: Internal utilities (if heavily used)
  for (const func of functions.filter(f => !f.exported && (func.callCount > 3))) {
    chunks.push({
      chunk_id: `chunk_${uuidv4().slice(0, 8)}`,
      name: func.name,
      file: filePath,
      language,
      semantic_scope: 'utility',
      
      // ... similar structure
      
      metadata: {
        tags: ['utility', 'internal'],
        importance: Math.min(0.8, func.callCount / 10),
        framework_specific: []
      }
    })
  }
  
  return chunks
}

/**
 * Extract semantic tags from function/method
 */
function extractSemanticTags(item) {
  const tags = new Set()
  
  // From signature
  if (item.async) tags.add('async')
  if (item.generator) tags.add('generator')
  if (item.kind === 'constructor') tags.add('constructor')
  
  // From docstring
  if (item.docstring) {
    if (item.docstring.match(/http|request|fetch|api/i)) tags.add('http')
    if (item.docstring.match(/validate|verify|check/i)) tags.add('validation')
    if (item.docstring.match(/error|exception|throw/i)) tags.add('error_handling')
    if (item.docstring.match(/cach|memo/i)) tags.add('caching')
    if (item.docstring.match(/database|query|insert|update/i)) tags.add('database')
  }
  
  // From calls
  if (item.calls) {
    if (item.calls.some(c => c.includes('db'))) tags.add('database')
    if (item.calls.some(c => c.includes('cache'))) tags.add('caching')
    if (item.calls.some(c => c.includes('auth'))) tags.add('auth')
  }
  
  return Array.from(tags)
}

/**
 * Build chunk content for embedding
 */
function buildChunkContent(item, parentClass = null) {
  const parts = [
    `Name: ${item.name}`,
    `Signature: ${item.signature}`,
  ]
  
  if (parentClass) {
    parts.push(`Class: ${parentClass.name}`)
  }
  
  if (item.docstring) {
    parts.push(`Documentation: ${item.docstring}`)
  }
  
  if (item.calls && item.calls.length > 0) {
    parts.push(`Calls: ${item.calls.slice(0, 5).join(', ')}`)
  }
  
  return parts.join('\n')
}
```

**2. Importance Scorer** (`lib/chunking/importance-scorer.js`):
```javascript
/**
 * Score importance of chunk (0-1)
 * Factors: API surface, call frequency, complexity, file importance
 */
export function scoreChunkImportance(chunk, globalGraph, fileImportance) {
  let score = 0.5  // base
  
  // API surface: exported = more important
  if (chunk.structure.is_public) {
    score += 0.3
  }
  
  // Call frequency: called by many = more important
  const callCount = chunk.relationships.called_by?.length || 0
  score += Math.min(0.2, callCount / 20)
  
  // Complexity: very high complexity = more important (needs attention)
  if (chunk.structure.cyclomatic_complexity > 10) {
    score += 0.15
  }
  
  // File importance cascades
  score += (fileImportance - 0.5) * 0.1
  
  // Cap at 1.0
  return Math.min(1.0, score)
}

/**
 * Detect framework-specific patterns
 */
export function detectFrameworkPatterns(chunk, code) {
  const patterns = []
  
  // React
  if (code.includes('useState') || code.includes('useEffect')) {
    patterns.push('react-hook')
  }
  if (code.includes('class') && code.includes('extends React')) {
    patterns.push('react-class-component')
  }
  
  // Express
  if (code.includes('app.get') || code.includes('app.post')) {
    patterns.push('express-route-handler')
  }
  if (code.includes('req.') && code.includes('res.')) {
    patterns.push('express-middleware')
  }
  
  // Async patterns
  if (chunk.structure.is_async) {
    if (code.includes('await')) {
      patterns.push('async-await')
    }
    if (code.includes('.then(')) {
      patterns.push('promise-chain')
    }
  }
  
  return patterns
}
```

**3. Chunk Enricher** (`lib/chunking/chunk-enricher.js`):
```javascript
/**
 * Enrich chunks with cross-references and importance
 */
export function enrichChunks(chunks, globalGraph, fileMetadata) {
  // Build call-by relationships
  const callByMap = new Map()
  
  chunks.forEach(chunk => {
    chunk.relationships.calls?.forEach(callee => {
      if (!callByMap.has(callee)) {
        callByMap.set(callee, [])
      }
      callByMap.get(callee).push(chunk.name)
    })
  })
  
  // Enrich each chunk
  return chunks.map(chunk => ({
    ...chunk,
    relationships: {
      ...chunk.relationships,
      called_by: callByMap.get(chunk.name) || []
    },
    metadata: {
      ...chunk.metadata,
      importance: scoreChunkImportance(
        chunk,
        globalGraph,
        fileMetadata[chunk.file]?.importance || 0.5
      ),
      framework_specific: detectFrameworkPatterns(chunk, chunk.content)
    }
  }))
}
```

**Deliverable**: Phase 3 complete with ~8,000+ chunks ready for embedding

---

### Sprint 4: Enhanced Extraction Integration (Week 5-7)

**Goal**: Integrate new schemas with existing multi-AI extraction and validation

**Files to Modify**:
- `ai-web-code-learn.js` (main workflow)
- `lib/schemas/extraction.js` (new schema definitions)
- `lib/schemas/validation.js` (enhanced validation)

**Changes to ai-web-code-learn.js**:

**1. Inject Phase 1-3 Before Existing Extract**:
```javascript
// At line ~80, after Setup phase:

// NEW: Phase 1 - Pre-Analysis
phase('Pre-Analysis')
log('Detecting languages, classifying files, building dependency graph...')

const preAnalysisResult = await agent(
  `Analyze repository structure:
  Path: ${cloneResult.path}
  Tasks:
  1. Detect programming languages
  2. Classify files (core vs test vs config)
  3. Calculate file importance scores
  4. Extract import/dependency edges
  
  Return: {
    files: [{path, language, category, importance, imports}],
    stats: {total_files, core_files, languages}
  }`,
  {
    label: 'pre-analysis',
    schema: { type: 'object', properties: { files: { type: 'array' }, stats: { type: 'object' } } }
  }
)

// NEW: Phase 2 - Structural Analysis
phase('Structural Analysis')
log(`Parsing ${preAnalysisResult.files.length} files for structure...`)

const structuralAnalysis = await parallel(
  preAnalysisResult.files.slice(0, maxFiles).map(f => () =>
    agent(
      `Analyze code structure in ${f.path}:
      Language: ${f.language}
      
      Extract using AST parsing:
      1. Functions: name, signature, docstring, complexity, calls
      2. Classes: name, methods, properties, inheritance
      3. Imports/exports
      4. Estimated dead code
      
      Return schema matching STRUCTURAL_ANALYSIS_SCHEMA`,
      {
        label: `structural-${f.path.split('/').pop()}`,
        schema: STRUCTURAL_ANALYSIS_SCHEMA
      }
    )
  )
)

const validStructure = structuralAnalysis.filter(Boolean)
log(`Analyzed structure of ${validStructure.length} files`)

// NEW: Phase 3 - Semantic Chunking
phase('Semantic Chunking')
log('Creating semantic chunks at function/class boundaries...')

const chunkingResult = await agent(
  `Create semantic chunks from analyzed code.
  
  Input: ${JSON.stringify(validStructure.slice(0, 3), null, 2)}...
  
  For each function/class:
  1. Create chunk with signature, docstring, params, returns
  2. Tag with semantic categories (async, http, database, etc.)
  3. Calculate importance score (0-1)
  4. Build relationship edges (calls, imports)
  
  Return: { chunks: [{chunk_id, name, semantic_scope, structure, relationships, metadata}], stats }`,
  {
    label: 'chunking',
    schema: CHUNKING_SCHEMA
  }
)

log(`Created ${chunkingResult.chunks.length} semantic chunks`)

// Use chunks instead of files for Extract phase
const chunksToAnalyze = chunkingResult.chunks.slice(0, maxFiles)
```

**2. Enhanced Extract Phase** (replace lines 133-141):
```javascript
phase('Extract')

const extractions = await parallel(
  chunksToAnalyze.map(chunk => () =>
    agent(`Analyze code chunk and extract patterns:

Name: ${chunk.name}
Signature: ${chunk.structure.signature}
Docstring: ${chunk.structure.docstring}
Semantic Tags: ${chunk.metadata.tags.join(', ')}
Calls: ${chunk.relationships.calls.slice(0, 5).join(', ')}

Extract three perspectives:

WORKER A: SEMANTIC PATTERNS
- Architectural patterns (factory, observer, strategy)
- Idioms and best practices
- Code style observations

WORKER B: SECURITY & DEPENDENCIES
- Known vulnerabilities in dependencies
- External API calls and risk levels
- Potential security issues

WORKER C: API CONTRACT
- Parameter validation rules
- Return value documentation
- Exceptions and error handling
- Observable side effects

Format as JSON matching ENHANCED_EXTRACTION_SCHEMA`,
      {
        label: `extract-${chunk.chunk_id}`,
        schema: ENHANCED_EXTRACTION_SCHEMA
      }
    )
  )
)
```

**3. Enhanced Validation Phase** (replace lines 145-157):
```javascript
phase('Validate')

const validationPrompt = `You are the arbiter. Synthesize and validate extracted patterns.

EXTRACTIONS (${valid.length} chunks):
${JSON.stringify(valid.slice(0, 20), null, 2)}...

VALIDATION TASKS:

1. STRUCTURAL VERIFICATION:
   - Do extracted functions exist in analyzed code?
   - Are dependency references valid?
   - Check for circular dependencies

2. SEMANTIC DEDUPLICATION:
   - Group similar patterns (even if named differently)
   - Count worker consensus (how many found each pattern)
   - Mark high-consensus patterns as "high confidence"

3. ARCHITECTURE SYNTHESIS:
   - Identify layers (API, Service, Data)
   - Spot hotspots (high complexity + high coupling)
   - Detect anti-patterns (god objects, tight coupling)

4. QUALITY ASSESSMENT:
   - Count undocumented public APIs
   - Identify security warnings
   - Note low test coverage areas

Return JSON matching ENHANCED_VALIDATION_SCHEMA`

const validation = await agent(validationPrompt, {
  label: 'validate',
  model: arbiter.arbiter,
  schema: ENHANCED_VALIDATION_SCHEMA
})
```

**Deliverable**: ai-web-code-learn.js now has Phases 1-5, with enhanced schemas

---

### Sprint 5: Dual Storage & Query Engine (Week 7-9)

**Goal**: Implement Phase 6 (Storage) and Phase 7 (Query) with ChromaDB + JSON

**Files to Create**:
- `lib/storage/json-store.js`
- `lib/storage/chromadb-store.js`
- `lib/query/dual-retriever.js`
- `lib/query/context-assembler.js`
- `lib/query/query-ranker.js`

**1. JSON Store** (`lib/storage/json-store.js`):
```javascript
export async function storeMetadataJSON(validation, dbPath) {
  const metadata = {
    repo: validation.repo,
    branch: validation.branch,
    commit: validation.commit,
    cloned_at: new Date().toISOString(),
    
    stats: {
      files_analyzed: validation.files_analyzed,
      chunks_created: validation.chunks.length,
      chunks_embedded: validation.chunks.length,
      languages: [...new Set(validation.chunks.map(c => c.language))],
      total_loc: validation.total_loc,
      average_complexity: avg(validation.chunks.map(c => c.structure.cyclomatic_complexity))
    },
    
    chunks: validation.chunks.map(c => ({
      chunk_id: c.chunk_id,
      name: c.name,
      file: c.file,
      semantic_scope: c.semantic_scope,
      line_range: c.structure.line_range,
      semantic_tags: c.metadata.tags,
      importance: c.metadata.importance,
      dependencies: c.relationships.calls,
      complexity: c.structure.cyclomatic_complexity,
      test_coverage: c.code_quality?.test_coverage,
      quality_grade: c.code_quality?.quality_grade,
      embedding_id: `emb_${c.chunk_id}`
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
  
  return metadata
}

export async function queryMetadataJSON(dbPath, query) {
  const metadata = JSON.parse(
    await readFile(`${dbPath}/code-learn-metadata.json`, 'utf8')
  )
  
  // Text search in JSON
  return metadata.chunks.filter(c =>
    c.name.includes(query) ||
    c.semantic_tags.some(t => t.includes(query)) ||
    c.dependencies.some(d => d.includes(query))
  )
}
```

**2. ChromaDB Store** (`lib/storage/chromadb-store.js`):
```javascript
import { ChromaClient } from 'chromadb'

export async function initChromaDB(dbPath) {
  const client = new ChromaClient({ path: dbPath })
  return client
}

export async function storeEmbeddingsChromaDB(chunks, embeddings, client, collectionName = 'code-learn-chunks') {
  const collection = await client.getOrCreateCollection({
    name: collectionName,
    metadata: { 'hnsw:space': 'cosine' }
  })
  
  // Batch store
  for (let i = 0; i < chunks.length; i += 100) {
    const batch = chunks.slice(i, i + 100)
    const batchEmbeddings = embeddings.slice(i, i + 100)
    
    await collection.add({
      ids: batch.map(c => c.chunk_id),
      embeddings: batchEmbeddings.map(e => e.embedding),
      documents: batch.map(c => c.content),
      metadatas: batch.map(c => ({
        name: c.name,
        file: c.file,
        scope: c.semantic_scope,
        tags: c.metadata.tags.join(','),
        importance: c.metadata.importance,
        complexity: c.structure.cyclomatic_complexity
      }))
    })
  }
  
  return { stored: chunks.length, collection: collectionName }
}

export async function semanticSearchChromaDB(queryEmbedding, client, k = 10) {
  const collection = await client.getCollection({ name: 'code-learn-chunks' })
  
  const results = await collection.query({
    query_embeddings: [queryEmbedding],
    n_results: k
  })
  
  return results.ids[0].map((id, idx) => ({
    chunk_id: id,
    similarity: results.distances[0][idx],
    metadata: results.metadatas[0][idx],
    document: results.documents[0][idx]
  }))
}
```

**3. Dual Retriever** (`lib/query/dual-retriever.js`):
```javascript
export async function dualRetrieve(userQuery, metadata, chromaClient, embeddings) {
  // 1. Semantic search
  const queryEmbedding = await generateEmbedding(userQuery)
  const semanticResults = await semanticSearchChromaDB(queryEmbedding, chromaClient, 10)
  
  const semantic = semanticResults.map(r => ({
    ...r,
    method: 'semantic',
    score: 1 - r.similarity  // Convert distance to similarity
  }))
  
  // 2. Structural search (JSON lookup)
  const structural = metadata.chunks
    .filter(c =>
      c.name.includes(userQuery) ||
      c.semantic_tags.some(t => t.includes(userQuery))
    )
    .slice(0, 10)
    .map((c, idx) => ({
      chunk_id: c.chunk_id,
      name: c.name,
      method: 'structural',
      score: 1 - (idx * 0.05)  // Decay with position
    }))
  
  // 3. Hybrid ranking
  const allResults = [...semantic, ...structural]
  const scored = allResults.reduce((map, r) => {
    const key = r.chunk_id
    if (!map[key]) {
      map[key] = { ...r, scores: [] }
    }
    map[key].scores.push(r.score)
    return map
  }, {})
  
  const ranked = Object.values(scored)
    .map(r => ({
      ...r,
      final_score: avg(r.scores),  // Average all scores
      methods: [...new Set(r.scores.map(s => r.method))]
    }))
    .sort((a, b) => b.final_score - a.final_score)
  
  return ranked.slice(0, 10)
}
```

**4. Context Assembler** (`lib/query/context-assembler.js`):
```javascript
export async function assembleContext(retrievedChunks, metadata, repoPath) {
  const contextual = await Promise.all(
    retrievedChunks.map(async result => {
      const chunk = metadata.chunks.find(c => c.chunk_id === result.chunk_id)
      
      // Read actual code
      const code = await readFileLines(
        `${repoPath}/${chunk.file}`,
        chunk.line_range.start,
        chunk.line_range.end
      )
      
      // Find related chunks
      const calls = metadata.chunks.filter(c =>
        chunk.dependencies.includes(c.name)
      )
      const calledBy = metadata.chunks.filter(c =>
        c.dependencies.includes(chunk.name)
      )
      
      return {
        chunk_id: chunk.chunk_id,
        name: chunk.name,
        file: chunk.file,
        code_snippet: code.join('\n'),
        similarity: result.final_score,
        
        related: {
          calls: calls.slice(0, 3),
          called_by: calledBy.slice(0, 3),
          semantic_tags: chunk.semantic_tags
        },
        
        quality: {
          complexity: chunk.complexity,
          grade: chunk.quality_grade,
          coverage: chunk.test_coverage
        }
      }
    })
  )
  
  return contextual
}
```

**Deliverable**: Storage and query engine fully implemented

---

### Sprint 6: Testing, Documentation & Polish (Week 9-12)

**Goal**: Comprehensive testing, documentation, examples, and performance optimization

**Tasks**:

**1. Test Coverage**:
- [ ] Unit tests: 90%+ coverage on /lib
- [ ] Integration tests: Full workflow on 5 sample repos
- [ ] Performance benchmarks (10k chunks, <2s query latency)
- [ ] Error handling tests (malformed AST, ChromaDB failures)

**2. Documentation**:
- [ ] Update README with enhanced features
- [ ] Create migration guide (legacy → enhanced)
- [ ] Document all schemas with examples
- [ ] Add troubleshooting guide

**3. Examples**:
- [ ] Example 1: Query "How do we validate input?" on Express app
- [ ] Example 2: Query "Find all external API calls" on complex monorepo
- [ ] Example 3: Trace dependency chain through codebase

**4. Performance Optimization**:
- [ ] Batch embed 50+ chunks in parallel
- [ ] Implement caching (query → results)
- [ ] Add progress indicators for long-running ops
- [ ] Lazy-load embeddings for large codebases

**5. Backward Compatibility**:
- [ ] Add mode: "legacy" for old behavior
- [ ] Auto-detect user preference
- [ ] Deprecation warnings for old schema

**Deliverable**: Production-ready enhanced workflow

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| AST parsing fails on edge cases | Try/catch per file, skip failures, log errors |
| ChromaDB unavailable | Fallback to JSON-only search |
| Large repos (100k+ LOC) exceed memory | Batch processing, lazy loading, collection sharding |
| Complex Python/Go code | Start with JS/TS only, add tree-sitter later |
| Embedding generation too slow | Batch in parallel, cache embeddings |

---

## Success Criteria

- [ ] Phase 1-3: Pre-analysis and structure extraction working on all JS/TS repos
- [ ] Phase 4-5: Multi-AI extraction + validation producing rich insights
- [ ] Phase 6: Dual storage (JSON + ChromaDB) fully operational
- [ ] Phase 7: Query engine returning <2s with 85%+ accuracy
- [ ] Tests: 90%+ coverage, integration tests passing
- [ ] Docs: Complete with 3+ worked examples
- [ ] Performance: 10k-chunk codebase handled in <5 minutes
- [ ] Backward compatible: Old workflows still work in legacy mode

---

## Deployment Strategy

**Phase A: Feature Branch**
- Develop on `feature/code-learn-enhanced`
- All tests passing locally
- Ready for review

**Phase B: Staging Validation**
- Test on 10 public repos (small → large)
- Benchmark performance vs legacy
- Gather feedback

**Phase C: Beta Release**
- Release as `/ai-web-code-learn-enhanced` (new skill)
- Keep `/ai-web-code-learn` as stable fallback
- Gather usage telemetry

**Phase D: Production**
- Promote enhanced to main
- Deprecate legacy (with migration warnings)
- Archive old implementation

---

## Timeline Summary

| Sprint | Duration | Focus | Deliverable |
|--------|----------|-------|-------------|
| 0 | 1 week | Setup | Dependencies, scaffolding |
| 1 | 2 weeks | Phase 1 | Pre-analysis working |
| 2 | 2 weeks | Phase 2 | AST parsing, metrics |
| 3 | 1 week | Phase 3 | Semantic chunking |
| 4 | 2 weeks | Phase 4-5 | Extraction + validation |
| 5 | 2 weeks | Phase 6-7 | Storage + query |
| 6 | 4 weeks | Testing + polish | Production-ready |
| **Total** | **12 weeks** | | **Enhanced workflow** |

---

End of Implementation Roadmap
