# ai-web-code-learn Enhanced: Executive Design Summary

## Challenge

Current `ai-web-code-learn.js` performs basic LLM-based pattern extraction on repository files. It lacks:
- Semantic understanding of code structure (AST-blind)
- Relationship mapping (which functions call which)
- Deep analysis (complexity, dead code, security)
- Intelligent vector search (text-only matching)
- Architecture-level insights

## Solution Architecture

A 7-phase enhanced workflow adding deep learning and code analysis:

```
Input: Git Repository
    ↓
[1] Pre-Analysis          → Language detection, file classification, import mapping
    ↓
[2] Structural Analysis   → AST parsing, function/class extraction, complexity metrics
    ↓
[3] Semantic Chunking     → Create chunks at semantic boundaries (function/class level)
    ↓
[4] Multi-AI Extraction   → ENHANCED: Semantic patterns + security + API contracts
    ↓
[5] Validation            → ENHANCED: Structural verification + architecture synthesis
    ↓
[6] Dual Storage          → JSON metadata + ChromaDB embeddings
    ↓
[7] Enhanced Query        → Semantic + structural + dependency trace retrieval
    ↓
Output: Structured Answer + Call Chain + Examples
```

## Key Components

### 1. Pre-Analysis (Phase 1)
- **What**: Scan repo, detect languages, classify files (core vs test vs config)
- **Why**: Enables intelligent file prioritization, language-specific parsing
- **Output**: File catalog with importance scores, lightweight dependency graph

### 2. Structural Analysis (Phase 2)
- **What**: Parse AST, extract functions/classes, calculate metrics
- **Why**: Gives ground truth about code structure; LLM can focus on "why" not "what"
- **Metrics**: Cyclomatic complexity, cognitive complexity, dead code detection
- **Output**: Detailed function/class metadata with relationships

### 3. Semantic Chunking (Phase 3)
- **What**: Create chunks at function/class boundaries (not line or file level)
- **Why**: Preserves semantic meaning; enables "find similar functions across codebase"
- **Size**: ~50-200 chunks per file, total 5k-20k for typical repo
- **Output**: Code chunks ready for embedding + semantic tagging

### 4. Enhanced Extraction (Phase 4)
- **What**: Multi-worker pattern extraction using chunks + structure as context
- **Workers**:
  - Worker A: Semantic patterns (idioms, architecture, best practices)
  - Worker B: Security analysis (vulnerabilities, external APIs)
  - Worker C: API contract (parameters, return types, exceptions)
- **Output**: Rich extraction schema with 5 dimensions per chunk

### 5. Enhanced Validation (Phase 5)
- **What**: Arbiter validates with structural awareness + synthesis
- **Validation**:
  - Structural: Cross-check extracted items exist in AST
  - Semantic: Resolve worker conflicts, count consensus
  - Architecture: Identify layers, hotspots, anti-patterns
- **Output**: Validated chunks + dependency graph + quality metrics

### 6. Dual Storage (Phase 6)
- **JSON Storage**: Hierarchical metadata, human-readable, fast lookup
  ```
  ~/.claude/knowledge/code-learn/
  ├─ code-learn-metadata.json       (chunks, graph, architecture)
  └─ chromadb/
     └─ code-learn-chunks/         (embeddings, semantic search)
  ```
- **ChromaDB**: 384-dim semantic embeddings, cosine similarity search
- **Why Both**: JSON for structure/relationships, ChromaDB for semantic similarity

### 7. Enhanced Query (Phase 7)
- **Dual Retrieval**:
  - Semantic: ChromaDB embeddings (find similar code)
  - Structural: JSON index (find by name, tags, relationships)
- **Hybrid Ranking**: Combine semantic + structural scores
- **Context Assembly**: Return code snippets + related functions + test examples
- **Answer Synthesis**: Workers formulate, arbiter picks best

## Data Schemas

### Chunk Schema (Input to Extraction)
```javascript
{
  chunk_id: "chunk_abc123",
  name: "fetchUserData",
  file: "src/api/users.js",
  semantic_scope: "function",
  
  structure: {
    signature: "(userId: string): Promise<User>",
    docstring: "Fetch user by ID with optional caching",
    cyclomatic_complexity: 4,
    cognitive_complexity: 6,
    line_range: { start: 45, end: 78 },
    is_public: true,
    is_async: true
  },
  
  relationships: {
    calls: ["validateId", "cache.get", "api.request"],
    called_by: ["getProfile", "updateUser"],
    imports: ["@lib/cache"],
    depends_on: [{ module: "lodash", version: "^4.17.0" }]
  },
  
  content: "Function: fetchUserData\nSignature: ...",
  metadata: {
    semantic_tags: ["async", "http", "user-management"],
    importance: 0.95,
    framework_specific: ["express"]
  }
}
```

### Extraction Output (Enhanced)
```javascript
{
  chunk_id, file_path, language, semantic_scope,
  
  structure: { /* from AST */ },
  relationships: { /* calls, imports, etc */ },
  
  semantic_patterns: [
    { pattern: "Factory Pattern", category: "architecture", examples: [...] }
  ],
  
  security_insights: {
    vulnerabilities: [{ cve, severity, description }],
    external_apis: [{ service, risk_level }]
  },
  
  api_contract: {
    parameters: [{ name, type, required }],
    return_type: "Promise<User>",
    exceptions: ["NetworkError"],
    side_effects: ["writes to cache"]
  },
  
  code_quality: {
    dead_code_risk: false,
    test_coverage: 0.89,
    maintainability_index: 75
  },
  
  key_insights: [...]
}
```

### Query Result
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
      annotation: "Middleware validates request"
    },
    // ... more steps
  ],
  
  confidence: "high"
}
```

## Implementation Phases

| Phase | Week | Task | Key Output |
|-------|------|------|------------|
| 0 | 1 | Setup dependencies & scaffolding | Ready codebase |
| 1 | 2 | Pre-analysis: language detection, file classification | File catalog |
| 2 | 3-4 | Structural analysis: AST parsing, metrics | Function/class metadata |
| 3 | 5 | Semantic chunking: create chunks at boundaries | 5k-20k chunks |
| 4-5 | 6-7 | Enhanced extraction + validation | Rich patterns + architecture |
| 6-7 | 8-9 | Storage (JSON + ChromaDB) + query engine | Searchable KB |
| 8-12 | 10-12 | Testing, optimization, documentation | Production-ready |

## Tools Required

### New Dependencies (~15-20 packages)
```json
{
  "acorn": "^8.x",                    // JS/TS AST
  "@babel/parser": "^7.x",            // Modern JS/TS
  "@typescript-eslint/parser": "^6.x", // Type-aware TS
  "tree-sitter": "^0.20.x",           // Multi-language (optional)
  "complexity-report": "^2.x",        // Cyclomatic complexity
  "graphlib": "^2.x",                 // Graph algorithms
  "uuid": "^9.x",                     // Chunk IDs
  "cosine-similarity": "^1.x",        // Similarity scoring
  "@xenova/transformers": "^2.17.2",  // Semantic embeddings (existing)
  "chromadb": "^1.10.5"               // Vector DB (existing)
}
```

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Pre-analysis (100 files) | 2-5s | Fast, regex-based |
| AST parsing (100 files) | 10-30s | Depends on file size |
| Chunking (1000 chunks) | 5s | Batch processing |
| Embedding generation (1000 chunks) | 20-40 min | Can parallelize |
| Semantic search (10k chunks) | 100-200ms | ChromaDB index |
| Structural search (JSON) | 5-50ms | In-memory lookup |
| Full query (retrieval + synthesis) | 1-2s | Including API calls |

## Differentiation vs Existing Workflows

| Aspect | Current ai-web-code-learn | **Enhanced** |
|--------|---------------------------|-------------|
| Granularity | File-level | **Function/class-level** |
| Structure Awareness | No (LLM-blind) | **Full AST with relationships** |
| Storage | JSON only | **JSON + ChromaDB dual** |
| Search | Text matching | **Semantic + structural + dependency** |
| Relationships | None | **Call graphs, import maps** |
| Complexity | No | **Cyclomatic + cognitive** |
| Architecture | No | **Layers, hotspots, patterns** |
| Security | No | **Vulnerability scanning, external APIs** |
| Queries | "What files discuss X?" | **"How does X work?", "Find all calls to Y", "Trace auth flow"** |

vs ai-web-learn-production:
- **Input**: Web pages (dense text) → **Code (structured)**
- **Chunking**: Paragraphs → **Semantic boundaries (functions)**
- **Relationships**: Cross-references → **Call graphs + imports**
- **Analysis**: Fact extraction → **Structure + patterns + dependencies**

## Query Examples

### Example 1: Pattern Search
```
Q: "How do we handle async operations and error handling?"
→ Find functions with "async" + "error" tags
→ Return call chain with annotations
→ Include test examples
```

### Example 2: Dependency Trace
```
Q: "What's the complete call chain from login to database?"
→ Start at login(), follow "calls" edges
→ Show each function: name, signature, complexity, coverage
→ Flag gaps (low test coverage, missing error handling)
```

### Example 3: Security Audit
```
Q: "Where are external API calls and what's the risk?"
→ Filter chunks with external_apis in security_insights
→ Group by service (Stripe, GitHub, AWS)
→ Flag vulnerabilities and error handling gaps
```

## Success Metrics

- **Accuracy**: 85%+ of code locations identified correctly
- **Semantic Search**: Find similar patterns across codebase (vs keyword search)
- **Dependency Tracing**: Match callgraph tools' output (validation)
- **Complexity**: Match ESLint/Radon scores (validation)
- **Latency**: <2s for 10k-chunk codebase (semantic + structural)
- **Test Coverage**: 90%+ on all libraries

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| AST-first, LLM-second | Ground truth + semantic understanding |
| Semantic chunking at function/class level | Preserves meaning, enables similarity search |
| Dual storage (JSON + ChromaDB) | Flexibility: structure (JSON) + search (vectors) |
| Xenova/all-MiniLM embeddings | General-purpose, tested, low resource cost |
| Arbiter-based validation | Multi-perspective consensus on patterns |
| Call graphs for relationships | Enables "follow the code" queries |
| Start with JS/TS, expand later | 80% of use cases, mature tooling |

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| AST parsing fails | Try/catch, skip failures, log errors |
| ChromaDB unavailable | Fallback to JSON search |
| Memory overflow (100k+ LOC) | Batch processing, lazy loading, sharding |
| Slow embedding generation | Parallel batching, caching |
| Complex Python/Go code | Start JS/TS only, add tree-sitter later |

## Files Delivered

### Design Documents (This Delivery)
1. **AI_WEB_CODE_LEARN_ENHANCEMENTS.md** (25 pages)
   - Complete architecture design
   - Phase-by-phase breakdown
   - Schema definitions
   - FAQ with design decisions

2. **ENHANCED_CODE_LEARN_REFERENCE.md** (35 pages)
   - Phase-by-phase implementation details
   - Code stubs and examples
   - Query flow documentation
   - Performance & scaling analysis

3. **CODE_LEARN_IMPLEMENTATION_ROADMAP.md** (20 pages)
   - Sprint-by-sprint plan (12 weeks)
   - Task breakdown with deliverables
   - Testing & deployment strategy
   - Risk mitigation and success metrics

## Next Steps

### Immediate (Week 1)
- [ ] Review design documents
- [ ] Validate technology stack
- [ ] Set up repository structure
- [ ] Gather team feedback

### Short-term (Weeks 2-4)
- [ ] Implement Phase 1 (Pre-analysis)
- [ ] Build Phase 2 (Structural Analysis) for JS/TS
- [ ] Create test fixtures

### Medium-term (Weeks 5-8)
- [ ] Implement Phases 3-7
- [ ] Integrate with existing workflow
- [ ] Begin testing on sample repos

### Long-term (Weeks 9-12)
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Documentation & examples
- [ ] Beta release, gather feedback
- [ ] Production release

## Estimated Effort

- **Design**: 2 engineer-weeks (complete)
- **Implementation**: 50-60 engineer-days (12 weeks, 1 FTE)
- **Testing**: 15-20 engineer-days (included in phases)
- **Documentation**: 5-10 engineer-days (weeks 11-12)
- **Total**: ~80-100 engineer-days (~4-5 months, 1 FTE)

## ROI

### Benefits
1. **Semantic code search**: Find patterns beyond keyword matching
2. **Dependency understanding**: Trace flows, identify call chains
3. **Architecture insights**: Hotspots, layers, anti-patterns
4. **Security posture**: External APIs, vulnerabilities, risk levels
5. **Quality metrics**: Complexity, coverage, maintainability
6. **Developer experience**: "Natural language code queries"

### Impact
- Faster onboarding (understand architecture quickly)
- Better code review (identify patterns, risks)
- Architecture documentation (automatically generated)
- Security scanning (built-in, low false-positive rate)

---

**Status**: Design complete, ready for implementation
**Last Updated**: 2024-06-10
**Next Review**: After Sprint 0 completion
