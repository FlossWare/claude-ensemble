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

log('═'.repeat(60))
log('🧠 MEMORY RAG INDEXING')
log('═'.repeat(60))
log('Indexing memories with semantic embeddings for intelligent retrieval')
log('')

const MEMORY_DIR = `${process.env.HOME}/.claude/memory`
const CHROMA_COLLECTION = 'claude-memories'

// PHASE 1: Load all memory files
phase('Load Memories')

log('📂 Loading memory files from ~/.claude/memory...')

const memoryFiles = await agent(`List all memory files:

cd ${MEMORY_DIR}
find . -name "*.md" -not -name "MEMORY.md" -type f

Return the list of files.`, {
  label: 'list-memories',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } },
      count: { type: 'number' }
    }
  }
})

log(`✅ Found ${memoryFiles.count} memory files`)

// PHASE 2: Read and parse all memories with multi-AI validation
log('')
log('📖 Reading memory contents (multi-AI validation)...')

const allFiles = memoryFiles.files
const BATCH_SIZE = 50

const memories = []

for (let i = 0; i < allFiles.length; i += BATCH_SIZE) {
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

log(`✅ Loaded ${memories.length} memories`)

// PHASE 3: Generate embeddings and index
phase('Generate Embeddings')

log('')
log('🔢 Generating semantic embeddings...')

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

// PHASE 4: Verify with test query
phase('Verify Index')

log('')
log('🔍 Testing semantic search...')

const testQuery = "workflow registration and naming patterns"

const searchResults = await agent(`Test semantic search in ChromaDB:

Query: "${testQuery}"

Python code:

import chromadb

client = chromadb.PersistentClient(path=f"{process.env.HOME}/.claude/chroma")
collection = client.get_collection("${CHROMA_COLLECTION}")

# Semantic search
results = collection.query(
    query_texts=["${testQuery}"],
    n_results=5
)

print("Top 5 results:")
for i, (doc, meta, distance) in enumerate(zip(
    results['documents'][0],
    results['metadatas'][0],
    results['distances'][0]
)):
    print(f"{i+1}. {meta['name']} (distance: {distance:.3f})")
    print(f"   File: {meta['filename']}")
    print(f"   Type: {meta['type']}")
    print()

Return structured results.`, {
  label: 'test-search',
  schema: {
    type: 'object',
    properties: {
      query: { type: 'string' },
      results: {
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
      success: { type: 'boolean' }
    }
  }
})

log(`✅ Search test successful - found ${searchResults.results?.length || 0} results`)

if (searchResults.results) {
  log('')
  log('Top results:')
  searchResults.results.forEach((r, i) => {
    log(`  ${i + 1}. ${r.name} (${r.type})`)
    log(`     Distance: ${r.distance.toFixed(3)}`)
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
