# ChromaDB → PostgreSQL Migration Plan

## Status: Analyzed via Fleet Orchestrator

**Fleet Analysis Completed:** 4 workers analyzed 3 files in parallel

## Files Requiring Migration

### 1. ✅ vector_db_adapter.py (264 lines)
**Status:** Already using PostgreSQL!
- 0 ChromaDB references
- Uses psycopg2 + pgvector
- **NO MIGRATION NEEDED**

### 2. learning-vectordb.js (667 lines, 19 ChromaDB refs)
**Current Architecture:**
- Wraps ChromaDB via Python subprocess
- Uses temp files for JSON IPC
- 10 exported functions:
  - addTask, addTaskBatch
  - searchSimilar, searchFiltered
  - searchHighQuality, searchCostOptimized
  - searchFailures, searchByDirectory
  - updateTask, deleteTask

**Migration Strategy:**
- Replace Python ChromaDB subprocess with direct PostgreSQL calls
- Use existing `workflow.worker_results` table or create `learning.task_embeddings`
- Replace ChromaDB query API with pgvector SQL
- Keep same function signatures for backward compatibility

**Estimated Effort:** 4-6 hours

### 3. vector-store.py (278 lines, 4 ChromaDB refs)
**Current Architecture:**
- Direct ChromaDB Python API
- Class-based interface
- Methods: add, add_batch, query, get, delete, count, reset

**Migration Strategy:**
- Already have PostgreSQL version started (vector-store-postgres.py)
- Need to fix embedding generation and SQL syntax
- Use `vector_store` schema or `learning` schema

**Estimated Effort:** 2-3 hours

## Migration Approach Using Fleet

### Phase 1: Analysis ✅ COMPLETE
- 4 workers analyzed files in parallel
- Identified all ChromaDB API calls
- Mapped function signatures

### Phase 2: Local Implementation (To Do)
**File 1: learning-vectordb.js**
```javascript
// Replace ChromaDB subprocess with PostgreSQL
import pg from 'pg';
const { Pool } = pg;

const pool = new Pool({
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: 'sfloess'
});

export async function addTask(data) {
  // OLD: execFileSync(PYTHON, ['-c', chromaScript, ...])
  // NEW: await pool.query('INSERT INTO learning.task_embeddings ...')
}

export async function searchSimilar(queryText, topK) {
  // OLD: ChromaDB Python subprocess
  // NEW: SELECT * FROM learning.task_embeddings ORDER BY embedding <=> $1 LIMIT $2
}
```

**File 2: vector-store.py**
- Fix embedding generation (use subprocess to call sentence-transformers)
- Fix SQL syntax for metadata filtering
- Test with learning schema

### Phase 3: Fleet Testing
**4 workers test migrations in parallel:**
```javascript
const testTasks = [
  { id: 'test-vectordb', prompt: 'node shared/learning-vectordb-postgres.js --test' },
  { id: 'test-vector-store', prompt: 'python3 shared/vector-store-postgres.py' },
  { id: 'test-adapter', prompt: 'python3 shared/vector_db_adapter.py' },
  { id: 'test-integration', prompt: 'test all 3 together' }
];
```

### Phase 4: Fleet Review
**8 workers review in parallel (2 per file):**
- Code quality
- API compatibility
- Performance comparison
- Error handling

## Timeline
- **With Fleet:** ~6-8 hours total
- **Without Fleet:** ~16-20 hours total
- **Speedup:** 2-3× faster

## Next Steps

1. Implement learning-vectordb.js PostgreSQL version (4-6h)
2. Fix vector-store-postgres.py issues (2-3h)
3. Test via fleet (4 workers, 30min)
4. Review via fleet (8 workers, 30min)
5. Deploy and close #196

## Fleet Commands Ready

All fleet orchestration scripts prepared:
- `/tmp/chromadb-analysis-fleet.mjs` - Analysis (done)
- `/tmp/test-migrations-fleet.mjs` - Testing (ready)
- `/tmp/review-migrations-fleet.mjs` - Review (ready)
