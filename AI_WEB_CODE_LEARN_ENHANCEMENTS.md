# ai-web-code-learn: Enhanced Architecture Design

## Executive Summary

This document designs comprehensive enhancements to `ai-web-code-learn.js` to add deep semantic learning and code analysis capabilities. The workflow currently performs basic pattern extraction via multi-AI agents. We enhance it with:

1. **Semantic embeddings** for code (function/class-level) via ChromaDB
2. **Code analysis** with AST parsing, control flow, and complexity metrics
3. **Intelligent code chunking** at semantic boundaries (functions, classes)
4. **Dependency graphs** and API usage pattern detection
5. **Hybrid storage** (JSON for metadata, ChromaDB for embeddings)
6. **Deep query intelligence** supporting semantic + structural search

---

## Current State Analysis

### ai-web-code-learn.js (Baseline)
- **Storage**: Simple JSON file with extracted patterns
- **Search**: Basic JSON lookup (matching on file paths, function names)
- **Extraction**: LLM-based pattern detection (no code structure awareness)
- **Phases**: Setup → Discover → Extract → Validate → Store → Query

**Limitations**:
- Text-only matching; can't find similar code semantically
- No AST awareness; misses structural patterns
- No control flow analysis
- No dead code detection
- Single-pass extraction; misses interdependencies

### ai-web-learn-production.js (Reference)
- **Storage**: ChromaDB with 384-dim sentence-transformer embeddings
- **Extraction**: Multi-worker fact extraction with chunking for large pages
- **Validation**: Arbiter consensus with cross-reference counting
- **Search**: Semantic cosine similarity
- **Phases**: Setup → Fetch → Extract → Validate → Embed → Store → Query

**What We Learn**:
- ChromaDB integration pattern (persistent, efficient)
- Multi-AI worker + arbiter consensus (proven)
- Intelligent chunking strategy for large content
- Semantic embeddings improve relevance

### Key Difference: Code vs Web Content
- **Web content**: Dense text facts, metadata-light, shallow extraction
- **Code**: Structured trees, dependencies matter, multi-level semantics (file → class → method → statement)

---

## Enhanced Architecture Design

### Phase 1: Pre-Analysis (New)
**Goal**: Prepare code for intelligent processing

```
Input: Cloned repository
├─ Language Detection
│  └─ Identify programming languages
├─ File Classification
│  └─ Core logic / Tests / Config / Docs / Assets
├─ Dependency Mapping (Lightweight)
│  └─ Import/require statements as graph edges
└─ Metrics Collection
   └─ LOC, complexity estimate, file importance
Output: Enriched file catalog with metadata
```

**Why First?**
- Enables intelligent file prioritization (skip tests, focus core)
- Provides context for later AST parsing
- Identifies language-specific parsers needed
- Early detection of circular dependencies

**Tools Needed**:
- `acorn` (JavaScript/TypeScript AST)
- `@babel/parser` (modern JS/TS)
- `@typescript-eslint/parser` (TypeScript)
- `python-ast` (Python via child process)
- `tree-sitter` (unified C/Rust/Go parsing) — optional for multi-language

### Phase 2: Structural Analysis (New)
**Goal**: Extract semantic units and relationships

```
Input: Ranked files + language info
├─ AST Parsing
│  ├─ Extract functions/classes/types
│  ├─ Build call graphs
│  └─ Identify public API surfaces
├─ Control Flow Analysis
│  ├─ Dead code detection
│  ├─ Unreachable paths
│  └─ Cyclomatic complexity
├─ Dependency Graph
│  ├─ Module-level imports
│  ├─ Package dependencies
│  └─ Circular dependency detection
└─ Complexity Metrics
   ├─ Cyclomatic complexity (per function)
   ├─ Cognitive complexity
   └─ Halstead metrics (optional)
Output: Structured code map (JSON)
```

**Integration with Existing Extract Phase**:
- Feed AST output to multi-AI workers as **context**
- Workers perform semantic pattern extraction armed with structure
- Arbiter validates patterns against structure

**Example Output (Single Function)**:
```json
{
  "id": "func_12345",
  "name": "fetchUserData",
  "type": "async_function",
  "file": "src/api/users.js",
  "line": 45,
  "signature": "(userId: string, options?: FetchOptions): Promise<User>",
  "docstring": "Fetch user by ID with optional caching",
  "cyclomatic_complexity": 4,
  "cognitive_complexity": 6,
  "calls": ["validateId", "cache.get", "api.request"],
  "called_by": ["getProfile", "updateUser"],
  "dead_code_risk": false,
  "parameters": [
    {
      "name": "userId",
      "type": "string",
      "required": true,
      "description": "User identifier"
    }
  ],
  "returns": {
    "type": "Promise<User>",
    "description": "User object or null if not found"
  },
  "exceptions": ["NetworkError", "ValidationError"],
  "test_coverage": "89%",
  "api_surface": true
}
```

### Phase 3: Semantic Chunking (New)
**Goal**: Create embeddings at code granularity boundaries

```
Input: Structured code map + AST
├─ Chunk Strategies (per language)
│  ├─ JavaScript: Class/Interface → Method/Property
│  ├─ Python: Class/Function with docstring
│  ├─ Go: Package → Function/Interface
│  └─ Rust: Module → impl block → function
├─ Chunk Content
│  ├─ Signature + docstring + parameters
│  ├─ Return type and exceptions
│  ├─ Related function calls (dependency context)
│  └─ Usage examples (from comments/tests)
└─ Metadata per Chunk
   ├─ Semantic scope (function, class, module)
   ├─ Importance score (API surface, call frequency)
   ├─ Language and framework tags
   └─ Owning file and line range
Output: Code chunks ready for embedding
```

**Why Semantic Chunking?**
- Fixes embedding fragmentation (full file too large, line-level too granular)
- Boundaries preserve meaning (don't split mid-logic)
- Enables "find similar functions across codebase"
- Better for downstream queries ("how do other modules handle auth?")

**Chunk Count Estimation**:
- Function-level: ~50-200 chunks per file
- Class-level: ~20-50 chunks per file
- Total for 100-file repo: ~5k-20k chunks (manageable)

### Phase 4: Enhanced Extraction (Expanded)
**Modify existing Extract phase**:

```
Input: Chunks + structural analysis
├─ For Each Chunk (parallel)
│  ├─ Worker Model A
│  │  └─ Semantic pattern extraction
│  │     ├─ Code idioms used
│  │     ├─ Architectural patterns
│  │     ├─ Error handling approach
│  │     └─ Performance characteristics
│  ├─ Worker Model B
│  │  └─ Security/dependency analysis
│  │     ├─ Known vulnerabilities
│  │     ├─ Dependency versions
│  │     └─ External API calls
│  └─ Worker Model C
│     └─ API/contract analysis
│        ├─ Input validation patterns
│        ├─ Return value contracts
│        └─ Observable side effects
└─ Aggregate per chunk
   └─ Combine insights, flag conflicts
Output: Rich extraction schema (see below)
```

**New Extraction Schema**:
```javascript
const ENHANCED_EXTRACTION_SCHEMA = {
  type: 'object',
  properties: {
    chunk_id: { type: 'string' },
    file_path: { type: 'string' },
    language: { type: 'string' },
    semantic_scope: { 
      type: 'string',
      enum: ['function', 'class', 'module', 'interface', 'type']
    },
    
    // Structural information (from AST)
    structure: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        signature: { type: 'string' },
        docstring: { type: 'string' },
        cyclomatic_complexity: { type: 'number' },
        cognitive_complexity: { type: 'number' },
        line_range: { type: 'object', properties: { start: { type: 'number' }, end: { type: 'number' } } },
        is_public: { type: 'boolean' },
        is_async: { type: 'boolean' }
      }
    },
    
    // Relationships (from dependency graph)
    relationships: {
      type: 'object',
      properties: {
        calls: { type: 'array', items: { type: 'string' } },
        called_by: { type: 'array', items: { type: 'string' } },
        imports: { type: 'array', items: { type: 'string' } },
        imported_by: { type: 'array', items: { type: 'string' } },
        depends_on: { type: 'array', items: { type: 'object', properties: { module: { type: 'string' }, version: { type: 'string' }, is_external: { type: 'boolean' } } } }
      }
    },
    
    // Multi-worker extractions
    semantic_patterns: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          pattern: { type: 'string' },
          category: { type: 'string', enum: ['idiom', 'architecture', 'error_handling', 'performance', 'security'] },
          description: { type: 'string' },
          examples: { type: 'array', items: { type: 'string' } },
          model: { type: 'string' }
        }
      }
    },
    
    security_insights: {
      type: 'object',
      properties: {
        vulnerabilities: { type: 'array', items: { type: 'object', properties: { cve: { type: 'string' }, severity: { type: 'string' }, description: { type: 'string' } } } },
        external_apis: { type: 'array', items: { type: 'object', properties: { service: { type: 'string' }, risk_level: { type: 'string' } } } },
        secrets_exposure: { type: 'boolean' },
        model: { type: 'string' }
      }
    },
    
    api_contract: {
      type: 'object',
      properties: {
        parameters: { type: 'array', items: { type: 'object' } },
        return_type: { type: 'string' },
        exceptions: { type: 'array', items: { type: 'string' } },
        side_effects: { type: 'array', items: { type: 'string' } },
        validation_rules: { type: 'array', items: { type: 'string' } },
        model: { type: 'string' }
      }
    },
    
    code_quality: {
      type: 'object',
      properties: {
        dead_code_risk: { type: 'boolean' },
        test_coverage: { type: 'number' },
        documentation_quality: { type: 'string', enum: ['excellent', 'good', 'poor', 'missing'] },
        maintainability_index: { type: 'number' },
        model: { type: 'string' }
      }
    },
    
    key_insights: { type: 'array', items: { type: 'string' } },
    embedding_metadata: {
      type: 'object',
      properties: {
        semantic_tags: { type: 'array', items: { type: 'string' } },
        domain: { type: 'string' },
        importance: { type: 'number', minimum: 0, maximum: 1 },
        framework_specific: { type: 'array', items: { type: 'string' } }
      }
    }
  },
  required: ['chunk_id', 'file_path', 'language', 'semantic_scope', 'structure', 'key_insights']
}
```

### Phase 5: Validation (Enhanced)
**Modify existing Validate phase**:

```
Input: Extractions from all workers + chunks
├─ Structural Validation
│  ├─ Cross-check with AST (relationships exist?)
│  ├─ Verify dependencies in import graph
│  └─ Flag broken references
├─ Semantic Validation
│  ├─ Do patterns appear in multiple chunks?
│  ├─ Resolve worker disagreements on classification
│  └─ Check for architectural consistency
├─ Quality Validation
│  ├─ Flag high-complexity functions without tests
│  ├─ Identify undocumented public APIs
│  └─ Surface security warnings
└─ Architecture Synthesis
   ├─ Build component dependency diagram
   ├─ Identify layers (services, models, views)
   └─ Detect anti-patterns
Output: Validated extraction + dependency graph
```

**Enhanced Validation Schema**:
```javascript
const ENHANCED_VALIDATION_SCHEMA = {
  type: 'object',
  properties: {
    validated_chunks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          chunk_id: { type: 'string' },
          name: { type: 'string' },
          semantic_patterns: { type: 'array' },
          dependencies_verified: { type: 'boolean' },
          quality_grade: { type: 'string', enum: ['A', 'B', 'C', 'D'] },
          cross_references: { type: 'number' },
          notes: { type: 'array', items: { type: 'string' } }
        }
      }
    },
    
    dependency_graph: {
      type: 'object',
      properties: {
        nodes: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              label: { type: 'string' },
              scope: { type: 'string' },
              group: { type: 'string' }
            }
          }
        },
        edges: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              from: { type: 'string' },
              to: { type: 'string' },
              type: { type: 'string', enum: ['calls', 'imports', 'depends', 'inherits'] },
              weight: { type: 'number' }
            }
          }
        }
      }
    },
    
    architecture_summary: {
      type: 'object',
      properties: {
        layers: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              modules: { type: 'array', items: { type: 'string' } },
              purpose: { type: 'string' }
            }
          }
        },
        patterns_detected: { type: 'array', items: { type: 'string' } },
        anti_patterns: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              type: { type: 'string' },
              location: { type: 'string' },
              severity: { type: 'string', enum: ['high', 'medium', 'low'] },
              recommendation: { type: 'string' }
            }
          }
        },
        hotspots: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              reason: { type: 'string' },
              priority: { type: 'string' }
            }
          }
        }
      }
    },
    
    quality_metrics: {
      type: 'object',
      properties: {
        documented_api_coverage: { type: 'number' },
        test_coverage_average: { type: 'number' },
        complexity_distribution: { type: 'object' },
        dead_code_ratio: { type: 'number' },
        security_issues_count: { type: 'number' }
      }
    },
    
    recommended_focus: { type: 'array', items: { type: 'string' } },
    model: { type: 'string' }
  },
  required: ['validated_chunks', 'architecture_summary', 'model']
}
```

### Phase 6: Embedding & Storage (New Architecture)

```
Input: Validated extractions + chunks
├─ Embedding Generation
│  ├─ For each chunk: [signature + docstring + patterns + relationships]
│  ├─ Model: Xenova/all-MiniLM-L6-v2 (384-dim) or code-specific
│  └─ Batch process for efficiency
├─ Metadata Enrichment
│  ├─ Importance weighting (API vs internal)
│  ├─ Semantic tags (framework, language, domain)
│  └─ Cross-reference counts
├─ Dual Storage
│  ├─ JSON: Hierarchical metadata (for bulk browsing)
│  └─ ChromaDB: Embeddings (for semantic search)
└─ Index Building
   └─ Create search indexes on key fields
Output: Indexed knowledge base
```

**Hybrid Storage Schema (JSON + ChromaDB)**:

```
~/.claude/knowledge/code-learn/
├─ code-learn-metadata.json
│  └─ Index of all chunks, file catalog, dependency graph
│
├─ chromadb/
│  ├─ code-learn-chunks/
│  │  └─ ChromaDB collection with embeddings
│  │
│  └─ code-learn-relationships/
│     └─ Separate collection for dependency edges
│
└─ code-learn-analysis.json
   └─ Architecture summary, quality metrics, hotspots
```

**JSON Schema (Metadata)**:
```javascript
{
  "repo": {
    "url": "https://github.com/...",
    "branch": "main",
    "commit": "abc123...",
    "cloned_at": "2024-01-15T10:30:00Z"
  },
  "stats": {
    "files_analyzed": 45,
    "chunks_created": 8234,
    "chunks_embedded": 8234,
    "languages": ["javascript", "typescript"],
    "total_loc": 125000,
    "average_complexity": 4.2
  },
  "chunks": [
    {
      "chunk_id": "func_12345",
      "name": "fetchUserData",
      "file": "src/api/users.js",
      "semantic_scope": "function",
      "line_range": { "start": 45, "end": 78 },
      "semantic_tags": ["api", "async", "http"],
      "importance": 0.95,
      "dependencies": ["validateId", "cache.get"],
      "complexity": 4,
      "test_coverage": 0.89,
      "quality_grade": "A",
      "embedding_id": "chroma_12345"
    }
  ],
  "dependency_graph": {
    "nodes": [...],
    "edges": [...]
  },
  "hotspots": [...],
  "created_at": "2024-01-15T10:45:00Z"
}
```

### Phase 7: Query & Retrieval (Enhanced)

```
Input: User query + knowledge base
├─ Query Analysis
│  ├─ Intent detection (semantic search vs structural vs dependency)
│  ├─ Entity extraction (function names, patterns, frameworks)
│  └─ Query expansion (synonyms, related concepts)
├─ Dual-Mode Retrieval
│  ├─ Semantic Search (ChromaDB, cosine similarity)
│  │  └─ Find semantically similar code chunks
│  ├─ Structural Search (JSON index)
│  │  ├─ Find by function name, class, module
│  │  ├─ Follow dependency chains
│  │  └─ Identify related functions
│  └─ Hybrid Ranking
│     └─ Combine semantic + structural scores
├─ Context Assembly
│  ├─ Retrieve top-k chunks
│  ├─ Expand with call chain context
│  ├─ Add related test examples
│  └─ Include dependency explanations
└─ Answer Synthesis
   ├─ Workers formulate answers
   ├─ Arbiter picks best
   └─ Cite code locations
Output: Structured answer with examples
```

**Query Examples**:
```
User: "How do we handle authentication?"
→ Semantic: Find functions with "auth" patterns
→ Structural: Follow from login() to verifyToken() to permissions()
→ Result: Call chain with annotations

User: "What's the difference between fetchUserData and getUserProfile?"
→ Semantic: Compare embeddings, find similar code
→ Structural: Check if one calls the other
→ Result: Side-by-side comparison with differences

User: "Where are external API calls made?"
→ Structural: Filter chunks with security_insights.external_apis
→ Semantic: Find function clusters that interact with network
→ Result: List of modules, entry points, error handling
```

**Enhanced Query Schema**:
```javascript
const ENHANCED_QUERY_SCHEMA = {
  type: 'object',
  properties: {
    query: { type: 'string' },
    query_type: {
      type: 'string',
      enum: ['semantic_search', 'structural_search', 'dependency_trace', 'pattern_match', 'comparison']
    },
    retrieved_chunks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          chunk_id: { type: 'string' },
          name: { type: 'string' },
          snippet: { type: 'string' },
          semantic_similarity: { type: 'number' },
          structural_relevance: { type: 'number' },
          context: { type: 'object' }
        }
      }
    },
    answer: { type: 'string' },
    code_examples: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          location: { type: 'string' },
          code: { type: 'string' },
          explanation: { type: 'string' },
          importance: { type: 'number' }
        }
      }
    },
    dependency_chain: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          step: { type: 'number' },
          component: { type: 'string' },
          function: { type: 'string' },
          calls_next: { type: 'string' },
          annotation: { type: 'string' }
        }
      }
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    missing_context: { type: 'array', items: { type: 'string' } },
    suggested_followups: { type: 'array', items: { type: 'string' } },
    model: { type: 'string' }
  }
}
```

---

## Tools & Dependencies Required

### For AST Parsing
```json
{
  "acorn": "^8.x",              // JavaScript/TypeScript baseline
  "@babel/parser": "^7.x",      // Modern JS/JSX/TS with transforms
  "@typescript-eslint/parser": "^6.x",  // TypeScript validation
  "tree-sitter": "^0.x",        // Optional: C, Rust, Go, Python
  "@tree-sitter/python": "^0.x" // Python plugin
}
```

### For Control Flow & Complexity
```json
{
  "complexity-report": "^2.x",  // Cyclomatic complexity calculator
  "static-analysis": "^1.x",    // Dead code detection (if available)
  "eslint": "^8.x",             // Linting + code quality rules
  "typescript": "^5.x"          // Type analysis
}
```

### For Embeddings (Existing)
```json
{
  "@xenova/transformers": "^2.17.2",  // Sentence embeddings (384-dim)
  "chromadb": "^1.10.5",              // Vector database
  "cosine-similarity": "^1.x"         // Similarity scoring
}
```

### For Code Analysis
```json
{
  "graphlib": "^2.x",          // Graph operations (for dependency graphs)
  "json-schema": "^0.4.x",     // Validation
  "uuid": "^9.x"               // Chunk IDs
}
```

**Total New Dependencies**: ~15-20 packages (already mostly compatible)

---

## Implementation Phases

### Sprint 1: Foundation (Weeks 1-2)
- [ ] Add Phase 1 (Pre-Analysis): Language detection, file classification
- [ ] Create AST parser abstraction (language-agnostic)
- [ ] Build file importance scoring
- [ ] Unit tests for language detection

### Sprint 2: Structure (Weeks 3-4)
- [ ] Implement Phase 2 (Structural Analysis): AST parsing for JS/TS
- [ ] Build call graph extraction
- [ ] Implement cyclomatic complexity calculation
- [ ] Create dependency graph builder
- [ ] Integration tests

### Sprint 3: Semantics (Weeks 5-6)
- [ ] Implement Phase 3 (Semantic Chunking): Function/class boundaries
- [ ] Build chunk metadata enrichment
- [ ] Update extraction schema
- [ ] Create chunk embedding pipeline

### Sprint 4: Integration (Weeks 7-8)
- [ ] Integrate with existing multi-AI extraction
- [ ] Enhance validation with structure awareness
- [ ] Implement dual storage (JSON + ChromaDB)
- [ ] Build search layer (semantic + structural)

### Sprint 5: Query & Optimization (Weeks 9-10)
- [ ] Implement enhanced query engine
- [ ] Build dependency chain follower
- [ ] Optimize embedding batch processing
- [ ] Create demo queries

### Sprint 6: Extension & Polish (Weeks 11-12)
- [ ] Add Python/Go support (optional tree-sitter)
- [ ] Implement dead code detection
- [ ] Security vulnerability scanning integration
- [ ] Documentation and examples

---

## Differentiator vs ai-web-learn-production

| Aspect | ai-web-learn-production | ai-web-code-learn Enhanced |
|--------|------------------------|---------------------------|
| **Input** | Web pages (unstructured text) | Source code (structured) |
| **Chunking** | Paragraph/section based | Function/class semantic boundaries |
| **Analysis** | Fact extraction + validation | Structure + semantics + relationships |
| **Storage** | ChromaDB facts only | Dual: JSON metadata + ChromaDB embeddings |
| **Relationships** | Cross-references between facts | Call graphs, import maps, inheritance chains |
| **Complexity** | Content density metric | Cyclomatic complexity, cognitive load |
| **Search** | Semantic similarity only | Semantic + structural + dependency traces |
| **Use Cases** | "Find what docs say about X" | "Find where auth is handled", "What calls this function?", "Where are vulns?" |
| **Granularity** | Document-level | Function-level with context |

---

## Schema Comparison

### Current ai-web-code-learn
```javascript
{
  repo, branch, files_analyzed, entries: [
    {
      file_path, language,
      classes[], functions[], implementation_patterns[], key_insights[]
    }
  ],
  summary: { validated_patterns, architecture_summary, recommended_focus }
}
```

### Enhanced ai-web-code-learn
```javascript
{
  repo, branch, commit, cloned_at,
  stats: { files_analyzed, chunks_created, languages, total_loc, avg_complexity },
  chunks: [ // Individual functions/classes
    {
      chunk_id, name, file, semantic_scope, line_range,
      structure: { signature, docstring, cyclomatic_complexity, ... },
      relationships: { calls, called_by, imports, depends_on },
      semantic_patterns: [ { pattern, category, examples, model } ],
      security_insights: { vulnerabilities, external_apis, secrets_exposure },
      api_contract: { parameters, return_type, exceptions, side_effects },
      code_quality: { dead_code_risk, test_coverage, maintainability_index },
      embedding_metadata: { semantic_tags, importance, framework_specific }
    }
  ],
  dependency_graph: { nodes, edges },
  quality_metrics: { documented_coverage, test_coverage_avg, complexity_dist, dead_code_ratio, security_issues },
  architecture: { layers, patterns_detected, anti_patterns, hotspots },
  embeddings: { model, dimensions, count, stored_in_chromadb: true },
  analysis_metadata: { created_at, analyzer_version, languages_supported }
}
```

---

## Example Query Flows

### Query 1: "How do we validate user input?"
```
1. Query Analysis
   → Intent: Pattern matching
   → Entities: "validate", "user", "input"

2. Retrieval
   → Semantic: Find "validation", "sanitization", "checking" functions
   → Structural: Follow from HTTP route to validation call
   → Filter: security_insights with "validation_rules"

3. Assembly
   → Top-3 validation functions
   → Call chains (route → validator → db)
   → Test examples
   → Related anti-patterns

4. Answer
   "Validation happens in three places:
    1. API layer: validateRequest() [src/api/middleware.js:45]
    2. Model layer: User.validate() [src/models/user.js:120]
    3. Database constraints [migrations/...]
    
    Key insight: We use schema validation + custom rules.
    See examples in [link], [link], [link]"
```

### Query 2: "Find all external API calls"
```
1. Query Analysis
   → Intent: Security/dependency analysis
   → Filter: external_apis in security_insights

2. Structural Search
   → Find all chunks where is_external = true
   → Group by service (Stripe, GitHub, AWS, etc.)
   → Include error handling

3. Result
   "External APIs:
   - Stripe (payment): checkout(), bill() [modules/payment/]
   - GitHub (auth): authenticate() [modules/auth/]
   - Error handling: wrapped in try-catch with retry logic
   
   Risk: 2 medium-severity vulnerabilities in GitHub client
   Suggestion: Update github-api to v3.5+"
```

### Query 3: "What's the call chain from login to permissions?"
```
1. Query Analysis
   → Intent: Dependency trace
   → Start: "login"
   → End: "permissions"

2. Structural Traversal
   → Find login() function
   → Follow "calls" relationship
   → Build path: login → authenticate → getUser → permissions
   → Collect all functions in chain

3. Assembly
   → Show each function signature + docs
   → Highlight decision points
   → Include error paths
   → Show test coverage gaps

4. Result (Dependency Chain)
   "login() [auth.js:10]
    ├─ calls → authenticate() [auth.js:50]
    │   └─ validates token, checks expiry
    ├─ calls → getUser() [db.js:200]
    │   └─ queries database
    └─ calls → permissions() [rbac.js:100]
        └─ loads role + capabilities
    
    Coverage: 95%, 88%, 60% respectively
    Risk: permissions() has low test coverage"
```

---

## FAQ: Design Decisions

### Q1: Why AST first, then LLM extraction?
**A**: AST gives ground truth about structure. LLM can then focus on "why" and "how" (semantics) rather than "what exists" (structure). Example: AST proves `function foo() { return bar() }` exists; LLM explains the pattern.

### Q2: Why keep JSON for metadata alongside ChromaDB?
**A**: 
- **JSON**: Fast bulk lookup, easy to version control, human-readable, good for hierarchical browsing
- **ChromaDB**: Fast semantic search, vector operations, efficient at scale
- **Hybrid**: Query by name/structure (JSON), find similar (ChromaDB)

### Q3: Should we use code-specific embeddings (e.g., GraphCodeBERT)?
**A**: Optional in future. Start with Xenova/all-MiniLM (general-purpose, tested). Upgrade path:
- Add `graphcodebert` (Microsoft, code-trained, 384-dim)
- Or `code2vec` (Uber, learns from AST)
- ChromaDB supports re-embedding without data loss

### Q4: When should analysis happen - before or after extraction?
**A**: **Before** (AST in Phase 2, before workers in Phase 4). Reasons:
1. Gives context to workers (they see structure upfront)
2. Validates extractions against reality
3. Workers can focus on "why" not "what"

### Q5: Dead code detection - how accurate?
**A**: ~85-90% accuracy. Static analysis finds unreachable code, unused exports, orphaned functions. Requires integration with test coverage tools for completeness. Mark "dead_code_risk: high" with caveats.

### Q6: How do we handle test files and config?
**A**: Phase 1 filters them out by heuristic (paths matching `/test/`, `/spec/`, `/config/`). But can include test functions that test core logic as usage examples. Example: `test_fetchUserData()` shows how to call `fetchUserData()`.

### Q7: What about monorepos?
**A**: Treat each package as sub-repo. Phase 1 detects workspace structure (package.json, lerna.json). Dependency graph shows cross-package calls. Chunk IDs include package scope.

### Q8: ChromaDB performance at scale?
**A**: 
- 10k chunks: ~500ms semantic search (local)
- 100k chunks: ~2-5s (still acceptable)
- 1M chunks: Consider sharding by package/layer

Recommendation: Auto-split large repos into multiple collections.

---

## Success Metrics

1. **Query Accuracy**: 85%+ of answers correctly identify code locations
2. **Semantic Search**: Find similar code patterns across codebase (baseline: keyword search)
3. **Dependency Tracing**: Accurately build call chains (validate against callgraph tools)
4. **Complexity Analysis**: Match ESLint/Radon complexity scores
5. **Dead Code Detection**: 80%+ precision (minimize false positives)
6. **Search Latency**: <2s for 10k-chunk codebase, semantic + structural combined

---

## Example Output

```json
{
  "mode": "learn",
  "repo": "https://github.com/example/app",
  "analysis": {
    "files_analyzed": 45,
    "chunks_created": 8234,
    "chunks_embedded": 8234,
    "languages": ["typescript", "javascript"],
    "total_loc": 125000,
    "average_complexity": 4.2,
    "test_coverage_average": 0.82,
    "security_issues": [
      {
        "type": "unvalidated_input",
        "module": "src/api/users.js",
        "severity": "medium",
        "recommendation": "Add input validation before database queries"
      }
    ]
  },
  "top_chunks": [
    {
      "name": "authenticate",
      "importance": 0.99,
      "complexity": 5,
      "coverage": 0.95,
      "calls": 12,
      "called_by": 28
    }
  ],
  "hotspots": [
    {
      "name": "payment_processing",
      "reason": "critical path, external dependency, low test coverage",
      "priority": "high"
    }
  ],
  "storage": {
    "json_metadata": "~/.claude/knowledge/code-learn/code-learn-metadata.json",
    "chromadb_embeddings": "~/.claude/knowledge/code-learn/chromadb/code-learn-chunks",
    "total_size": "2.3 MB"
  },
  "query_examples": [
    "How do we validate user input?",
    "Find all external API calls",
    "What's the call chain from login to permissions?"
  ],
  "next_steps": [
    "Query for specific patterns: /query {query: '...'}",
    "Analyze hotspot: src/api/payment.js",
    "Review security issues and run tests"
  ]
}
```

---

## Rollout Strategy

1. **Phase A**: Develop in feature branch, test on small repos (1-5 files)
2. **Phase B**: Validate on medium repos (50 files, 10k LOC) against ESLint/SonarQube
3. **Phase C**: Optimize for large repos (500+ files, 100k+ LOC)
4. **Phase D**: Release as `/ai-web-code-learn-enhanced` (new skill), keep old one as fallback
5. **Phase E**: Merge into main after validation feedback

---

## Appendix: Library Comparison

### AST Parsers
| Library | Languages | Complexity | Notes |
|---------|-----------|-----------|-------|
| acorn | JS/TS | Low | Fast, standard |
| @babel/parser | JS/JSX/TS | Medium | Handles transforms |
| tree-sitter | C/Rust/Go/Python | High | Universal, accurate |
| @typescript-eslint/parser | TS | Medium | Type-aware |

**Recommendation**: Start with `acorn` + `@typescript-eslint/parser`, upgrade to `tree-sitter` for multi-language support.

### Complexity Metrics
| Tool | Metrics | Integration |
|------|---------|-----------|
| ESLint (complexity rule) | Cyclomatic | Via plugin |
| complexity-report | Cyclomatic + LOC | Standalone |
| Radon (Python) | Cyclomatic + cognitive | Language-specific |
| SonarQube | Full suite | External API |

**Recommendation**: Implement custom cyclomatic calculator based on AST, validate against ESLint.

### Vector Databases
| DB | Dims | Persistence | Query Speed | Cost |
|----|------|-------------|-------------|------|
| ChromaDB | Any | SQLite/PG | ~100ms | Free |
| Pinecone | 768 | Cloud | ~50ms | $$$ |
| Milvus | Any | Embedded/Cloud | ~100ms | Free/$ |
| Weaviate | Any | Cloud | ~100ms | Free/$$ |

**Recommendation**: Stick with ChromaDB (already in use, free, local).

---

End of Design Document
