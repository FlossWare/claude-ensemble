export const meta = {
  name: 'memory-rag-index',
  description: 'Index all memories in ChromaDB with semantic embeddings for intelligent retrieval',
  whenToUse: 'Run when memories are added/updated to rebuild the semantic index',
  phases: [
    { title: 'Load Memories', detail: 'Read all memory files' },
    { title: 'Generate Embeddings', detail: 'Create semantic vectors' },
    { title: 'Index in ChromaDB', detail: 'Store in vector database' },
    { title: 'Verify Index', detail: 'Test semantic search' },
  ],
}

// ============================================================================
// STRATEGY CLASSES
// ============================================================================

class BaseStrategy {
  getWorkers() { return ['opus', 'sonnet', 'haiku'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
}

class MaximumCoverageStrategy extends BaseStrategy {
  getWorkers() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
}

class QuantizedStrategy extends BaseStrategy {
  getWorkers() { return ['ollama/llama3', 'ollama/mistral', 'ollama/codellama', 'haiku', 'sonnet'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
}

class QuintupleVerificationStrategy extends BaseStrategy {
  getWorkers() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }

  getVerificationStages() {
    return [
      { name: 'initial-review', workers: ['fable', 'opus', 'sonnet'], arbiter: 'fable' },
      { name: 'deep-analysis', workers: ['haiku', 'gpt-4o', 'gemini'], arbiter: 'opus' },
      { name: 'cross-validation', workers: ['fable', 'sonnet', 'gpt-4o'], arbiter: 'fable' },
      { name: 'edge-case-check', workers: ['opus', 'haiku', 'gemini'], arbiter: 'opus' },
      { name: 'final-consensus', workers: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o'], arbiter: 'fable' },
    ]
  }
}

const STRATEGIES = {
  'base': BaseStrategy,
  'maximum-coverage': MaximumCoverageStrategy,
  'quantized': QuantizedStrategy,
  'quintuple-verification': QuintupleVerificationStrategy,
}

function getStrategy(name) {
  const StrategyClass = STRATEGIES[name] || STRATEGIES['base']
  return new StrategyClass()
}

const strategy = getStrategy(args?.strategy)

log('═'.repeat(60))
log('🧠 MEMORY RAG INDEXING')
log('═'.repeat(60))
log('Indexing memories with semantic embeddings for intelligent retrieval')
log(`📊 Strategy: ${args?.strategy || 'base'}`)
log(`   Workers: ${strategy.getWorkers().join(', ')}`)
log(`   Arbiters: ${strategy.getArbiters().join(', ')}`)
log('')

const MEMORY_DIR = `${process.env.HOME}/.claude/memory`
const CHROMA_COLLECTION = 'claude-memories'

// PHASE 1: Load all memory files with multi-AI consensus
phase('Load Memories')

const FILE_WORKERS = strategy.getWorkers().slice(0, 3)  // Use top 3 workers for file discovery
log(`📂 Multi-AI file discovery (${FILE_WORKERS.join('/')})...`)

const fileWorkers = await parallel(FILE_WORKERS.map(model => () =>
  agent(`[${model.toUpperCase()}] List all memory files:

cd ${MEMORY_DIR}
find . -name "*.md" -not -name "MEMORY.md" -type f | sort

Count files and return structured list.`, {
    label: `${model}-list`,
    model,
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        files: { type: 'array', items: { type: 'string' } },
        count: { type: 'number' }
      }
    }
  })
))

const validFileWorkers = fileWorkers.filter(Boolean)
log(`✅ ${validFileWorkers.length}/${FILE_WORKERS.length} workers completed`)

log('⚖️  Arbiter selecting most complete file list...')

const fileArbiter = await agent(`[ARBITER] Review ${validFileWorkers.length} worker file lists.

Worker Responses:
${validFileWorkers.map((w, i) => `
Worker ${i + 1} (${w.model || 'unknown'}):
Count: ${w.count}
Files: ${w.files.length}
`).join('\n')}

Task:
1. Select the most COMPLETE file list (longest array, highest count)
2. Explain why you chose it
3. Rate confidence (0-100)

Return structured decision.`, {
  label: 'arbiter-files',
  schema: {
    type: 'object',
    properties: {
      winning_worker: { type: 'string' },
      why_selected: { type: 'string' },
      confidence: { type: 'number' },
      result: {
        type: 'object',
        properties: {
          files: { type: 'array', items: { type: 'string' } },
          count: { type: 'number' }
        }
      }
    }
  }
})

log(`✅ Winner: ${fileArbiter.winning_worker} (confidence: ${fileArbiter.confidence}%)`)

const memoryFiles = fileArbiter.result
log(`📊 Consensus: ${memoryFiles.count} memory files found`)

// PHASE 2: Read and parse memories with multi-AI sampling
log('')
log('📖 Reading memory contents...')

const allFiles = memoryFiles.files
const BATCH_SIZE = 50

// For the first batch, use multi-AI sampling to validate parsing quality
const firstBatch = allFiles.slice(0, Math.min(5, allFiles.length))

const SAMPLE_WORKERS = strategy.getWorkers().slice(0, 3)
log(`🤖 Multi-AI sampling on first 5 files (${SAMPLE_WORKERS.join('/')})...`)

const sampleParsing = await parallel(SAMPLE_WORKERS.map(model => () =>
  agent(`[${model.toUpperCase()}] Parse sample memory files: ${firstBatch.join(', ')}

For each file in ${MEMORY_DIR}:
1. Read and extract frontmatter (name, description, type)
2. Extract full content
3. Identify key topics/concepts

Return array of parsed memories.`, {
    label: `${model}-parse-sample`,
    model,
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        memories: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              filename: { type: 'string' },
              name: { type: 'string' },
              description: { type: 'string' },
              type: { type: 'string' },
              content: { type: 'string' },
              topics: { type: 'array', items: { type: 'string' } }
            }
          }
        }
      }
    }
  })
))

// Use consensus from multi-AI sample (prefer Opus if available)
const sampleMemories = (sampleParsing.filter(Boolean)[0]?.memories || [])
log(`✅ Multi-AI sampling complete - ${sampleMemories.length} sample memories parsed`)

// Now parse remaining files in batches
const memories = [...sampleMemories]

for (let i = firstBatch.length; i < allFiles.length; i += BATCH_SIZE) {
  const batch = allFiles.slice(i, Math.min(i + BATCH_SIZE, allFiles.length))

  log(`   Batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(allFiles.length / BATCH_SIZE)} (${batch.length} files)`)

  const batchMemories = await parallel(batch.map(file => () =>
    agent(`Read and parse memory file: ${MEMORY_DIR}/${file}

Extract:
1. Filename (without extension)
2. Frontmatter (name, description, type, metadata)
3. Full content
4. Key concepts/topics

Return structured data.`, {
      label: `read-${file.replace(/[^a-z0-9]/gi, '-').slice(0, 30)}`,
      schema: {
        type: 'object',
        properties: {
          filename: { type: 'string' },
          name: { type: 'string' },
          description: { type: 'string' },
          type: { type: 'string' },
          content: { type: 'string' },
          topics: { type: 'array', items: { type: 'string' } }
        }
      }
    })
  ))

  memories.push(...batchMemories.filter(Boolean))
}

log(`✅ Loaded ${memories.length} memories total`)

// PHASE 3: Generate embeddings and index
phase('Generate Embeddings')

log('')
log('🔢 Initializing ChromaDB...')
log('🔢 Generating semantic embeddings...')

const validMemories = memories.filter(m => m && m.filename && m.content)

const embeddingResults = await agent(`Generate embeddings for ${validMemories.length} memories and index in ChromaDB.

Requirements:
1. Install ChromaDB if needed: pip install chromadb
2. Create/connect to collection: ${CHROMA_COLLECTION}
3. For each memory, create embedding from:
   - Memory name + description
   - Full content
   - Topics/concepts
4. Store in ChromaDB with metadata:
   - filename
   - name
   - description
   - type
   - topics

Python code to run:

import chromadb
from chromadb.config import Settings
import hashlib

# Initialize ChromaDB
client = chromadb.PersistentClient(path=f"{process.env.HOME}/.claude/chroma")

# Get or create collection
collection = client.get_or_create_collection(
    name="${CHROMA_COLLECTION}",
    metadata={"description": "Claude global memories with semantic embeddings"}
)

# Index each memory
memories = ${JSON.stringify(validMemories, null, 2)}

documents = []
metadatas = []
ids = []

for mem in memories:
    # Create rich text for embedding
    doc_text = f"""
Name: {mem.get('name', mem['filename'])}
Description: {mem.get('description', '')}
Type: {mem.get('type', 'unknown')}
Topics: {', '.join(mem.get('topics', []))}

Content:
{mem['content']}
    """.strip()

    documents.append(doc_text)
    metadatas.append({
        'filename': mem['filename'],
        'name': mem.get('name', mem['filename']),
        'description': mem.get('description', '')[:500],  # Limit metadata size
        'type': mem.get('type', 'unknown'),
        'topics': ','.join(mem.get('topics', [])[:10])
    })

    # Generate stable ID from filename
    mem_id = hashlib.md5(mem['filename'].encode()).hexdigest()
    ids.append(mem_id)

# Add to collection (will generate embeddings automatically)
collection.upsert(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

print(f"✅ Indexed {len(documents)} memories in ChromaDB")
print(f"Collection: {collection.name}")
print(f"Total items: {collection.count()}")

Return results.`, {
  label: 'generate-embeddings',
  schema: {
    type: 'object',
    properties: {
      indexed_count: { type: 'number' },
      collection_name: { type: 'string' },
      total_items: { type: 'number' },
      success: { type: 'boolean' }
    }
  }
})

if (!embeddingResults.success) {
  log('❌ Embedding generation failed')
  return { status: 'failed', error: 'Could not generate embeddings' }
}

log(`✅ Indexed ${embeddingResults.indexed_count} memories`)
log(`   Collection: ${embeddingResults.collection_name}`)
log(`   Total items: ${embeddingResults.total_items}`)

// PHASE 4: Multi-AI verification with arbiter/worker pattern
phase('Verify Index')

log('')
const VERIFY_WORKERS = strategy.getWorkers().slice(0, 3)
log(`🔍 Multi-AI index verification (${VERIFY_WORKERS.length} workers: ${VERIFY_WORKERS.join('/')})...`)

const testQuery = "workflow registration and naming patterns"

const searchCode = `
import chromadb
import json

client = chromadb.PersistentClient(path=f"{process.env.HOME}/.claude/chroma")
collection = client.get_collection("${CHROMA_COLLECTION}")

# Semantic search
results = collection.query(
    query_texts=["${testQuery}"],
    n_results=5
)

# Format results
output = {
    'query': "${testQuery}",
    'results': [],
    'success': True
}

for doc, meta, distance in zip(
    results['documents'][0],
    results['metadatas'][0],
    results['distances'][0]
):
    output['results'].append({
        'name': meta['name'],
        'filename': meta['filename'],
        'type': meta['type'],
        'distance': float(distance),
        'preview': doc[:200]
    })

print(json.dumps(output, indent=2))
`

log('📝 Phase 1: Workers test search quality...')

const workers = await parallel(VERIFY_WORKERS.map(model => () =>
  agent(`[${model.toUpperCase()} WORKER] Test semantic search quality for: "${testQuery}"

Python code:
${searchCode}

Task:
1. Run the search
2. Rate result quality (0-100)
3. Check if results are semantically relevant
4. Identify any issues with embeddings
5. Recommend improvements

Return structured analysis.`, {
    label: `${model}-verify`,
    model,
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        search_results: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              filename: { type: 'string' },
              type: { type: 'string' },
              distance: { type: 'number' }
            }
          }
        },
        quality_rating: { type: 'number' },
        semantically_relevant: { type: 'boolean' },
        issues: { type: 'array', items: { type: 'string' } },
        improvements: { type: 'array', items: { type: 'string' } }
      }
    }
  })
))

const validWorkers = workers.filter(Boolean)
log(`✅ ${validWorkers.length} workers completed`)

log('⚖️  Phase 2: Arbiter synthesizes quality assessment...')

const verification = await agent(`[ARBITER] Review ${validWorkers.length} worker verifications and synthesize quality assessment.

Query: "${testQuery}"

Worker Assessments:
${validWorkers.map((w, i) => `
Worker ${i + 1} (${w.model || 'unknown'}):
Quality Rating: ${w.quality_rating}/100
Semantically Relevant: ${w.semantically_relevant ? 'YES' : 'NO'}
Top Results: ${w.search_results?.slice(0, 3).map(r => r.name).join(', ')}
Issues: ${w.issues?.join('; ') || 'none'}
Improvements: ${w.improvements?.join('; ') || 'none'}
`).join('\n')}

Task:
1. Calculate consensus quality rating
2. Determine if index is production-ready
3. Synthesize common issues
4. Prioritize improvements
5. Final verdict: PASS or NEEDS_WORK

Return structured decision.`, {
  label: 'arbiter-verify',
  schema: {
    type: 'object',
    properties: {
      consensus_quality: { type: 'number' },
      production_ready: { type: 'boolean' },
      verdict: { type: 'string' },
      common_issues: { type: 'array', items: { type: 'string' } },
      recommended_improvements: { type: 'array', items: { type: 'string' } },
      sample_results: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            distance: { type: 'number' }
          }
        }
      }
    }
  }
})

log(`✅ Consensus Quality: ${verification.consensus_quality}/100`)
log(`   Production Ready: ${verification.production_ready ? 'YES' : 'NO'}`)
log(`   Verdict: ${verification.verdict}`)

if (verification.sample_results?.length) {
  log('')
  log('Top Search Results:')
  verification.sample_results.forEach((r, i) => {
    log(`  ${i + 1}. ${r.name} (distance: ${r.distance.toFixed(3)})`)
  })
}

log('')
log('═'.repeat(60))
log('🎉 MEMORY RAG INDEX COMPLETE')
log('═'.repeat(60))
log(`📊 Indexed: ${embeddingResults.indexed_count} memories`)
log(`🔍 Search: Ready for semantic queries`)
log(`📍 Location: ~/.claude/chroma/${CHROMA_COLLECTION}`)
log('═'.repeat(60))

return {
  status: 'success',
  indexed_count: embeddingResults.indexed_count,
  collection: embeddingResults.collection_name,
  total_items: embeddingResults.total_items,
  test_query: testQuery,
  test_results: searchResults.results?.length || 0
}
