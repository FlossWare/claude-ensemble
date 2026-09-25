/**
 * Distributed PDF Learning Workflow
 * Uses fleet orchestration to process PDFs in parallel
 */

export const meta = {
  name: 'pdf-learning-distributed',
  description: 'Distributed PDF learning across 8-worker fleet with pgvector storage',
  phases: [
    { title: 'Extract', detail: 'Extract text from PDFs in parallel' },
    { title: 'Chunk', detail: 'Split into semantic chunks' },
    { title: 'Embed', detail: 'Generate embeddings via sentence-transformers' },
    { title: 'Store', detail: 'Store in PostgreSQL pgvector' },
    { title: 'Index', detail: 'Build searchable index' }
  ]
};

export default async function({ phase, parallel, agent, log, args }) {
  const { getDB } = await import('../shared/workflow-storage-adapter.js');
  const db = getDB();
  
  // Get PDF paths from args
  const pdfPaths = args?.pdfs || [];
  if (!pdfPaths.length) {
    throw new Error('No PDF paths provided. Pass --args \'{"pdfs":["path1.pdf","path2.pdf"]}\'');
  }
  
  log(`Processing ${pdfPaths.length} PDFs across 8-worker fleet`);
  
  // Phase 1: Extract text from PDFs (distributed)
  phase('Extract');
  const extractions = await parallel(pdfPaths.map((pdf, idx) => async () => {
    return agent(
      `Extract all text from PDF: ${pdf}
      
      Use PyPDF2 or similar to extract text.
      Return: {
        "pdf": "${pdf}",
        "text": "full extracted text",
        "pages": number of pages,
        "metadata": {title, author, etc}
      }`,
      {
        label: `extract-${idx}`,
        phase: 'Extract',
        schema: {
          type: 'object',
          properties: {
            pdf: { type: 'string' },
            text: { type: 'string' },
            pages: { type: 'number' },
            metadata: { type: 'object' }
          },
          required: ['pdf', 'text', 'pages']
        }
      }
    );
  }));
  
  const validExtractions = extractions.filter(Boolean);
  log(`Extracted text from ${validExtractions.length}/${pdfPaths.length} PDFs`);
  
  // Phase 2: Chunk into semantic segments (distributed)
  phase('Chunk');
  const chunks = await parallel(validExtractions.map((ext, idx) => async () => {
    return agent(
      `Split this text into semantic chunks (500-1000 words each):
      
      PDF: ${ext.pdf}
      Text: ${ext.text.substring(0, 50000)}
      
      Return array of chunks with metadata:
      {
        "chunks": [
          {
            "text": "chunk text",
            "start_page": page number,
            "chunk_index": index,
            "topic": "brief topic summary"
          }
        ]
      }`,
      {
        label: `chunk-${idx}`,
        phase: 'Chunk',
        schema: {
          type: 'object',
          properties: {
            chunks: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  text: { type: 'string' },
                  start_page: { type: 'number' },
                  chunk_index: { type: 'number' },
                  topic: { type: 'string' }
                }
              }
            }
          },
          required: ['chunks']
        }
      }
    );
  }));
  
  const allChunks = chunks.filter(Boolean).flatMap((c, pdfIdx) => 
    c.chunks.map(chunk => ({
      ...chunk,
      pdf: validExtractions[pdfIdx].pdf,
      pdf_metadata: validExtractions[pdfIdx].metadata
    }))
  );
  
  log(`Created ${allChunks.length} semantic chunks`);
  
  // Phase 3: Generate embeddings (using sentence-transformers on aio-01)
  phase('Embed');
  log('Generating embeddings via sentence-transformers...');
  
  const embeddings = await agent(
    `Generate embeddings for these ${allChunks.length} text chunks using sentence-transformers.
    
    Use model: sentence-transformers/all-mpnet-base-v2 (384-dim)
    
    Python code:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
    
    Chunks: ${JSON.stringify(allChunks.map(c => c.text.substring(0, 200)))}
    
    Return: Array of 384-dimensional vectors`,
    {
      label: 'generate-embeddings',
      phase: 'Embed',
      schema: {
        type: 'object',
        properties: {
          embeddings: {
            type: 'array',
            items: {
              type: 'array',
              items: { type: 'number' }
            }
          }
        },
        required: ['embeddings']
      }
    }
  );
  
  // Phase 4: Store in PostgreSQL pgvector
  phase('Store');
  log('Storing embeddings in PostgreSQL...');
  
  const conn = await db.pool.connect();
  try {
    // Create table if not exists
    await conn.query(`
      CREATE TABLE IF NOT EXISTS knowledge.pdf_embeddings (
        id SERIAL PRIMARY KEY,
        pdf_path TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        chunk_text TEXT NOT NULL,
        topic TEXT,
        start_page INTEGER,
        embedding vector(1024),
        pdf_metadata JSONB,
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);
    
    // Create HNSW index for fast similarity search
    await conn.query(`
      CREATE INDEX IF NOT EXISTS pdf_embeddings_hnsw_idx 
      ON knowledge.pdf_embeddings 
      USING hnsw (embedding vector_cosine_ops)
    `);
    
    // Insert chunks with embeddings
    let inserted = 0;
    for (let i = 0; i < allChunks.length; i++) {
      const chunk = allChunks[i];
      const embedding = embeddings.embeddings[i];
      
      if (embedding && embedding.length === 384) {
        await conn.query(`
          INSERT INTO knowledge.pdf_embeddings 
          (pdf_path, chunk_index, chunk_text, topic, start_page, embedding, pdf_metadata)
          VALUES ($1, $2, $3, $4, $5, $6, $7)
        `, [
          chunk.pdf,
          chunk.chunk_index,
          chunk.text,
          chunk.topic,
          chunk.start_page,
          JSON.stringify(embedding),
          JSON.stringify(chunk.pdf_metadata)
        ]);
        inserted++;
      }
    }
    
    log(`Stored ${inserted} chunks with embeddings in PostgreSQL`);
    
  } finally {
    conn.release();
  }
  
  // Phase 5: Build search index
  phase('Index');
  const indexStats = await agent(
    `Create semantic search index for the ${allChunks.length} PDF chunks.
    
    Group by topics, extract key concepts, build inverted index.
    
    Return: {
      "total_chunks": count,
      "unique_topics": count,
      "key_concepts": [array of main concepts],
      "ready_for_search": true
    }`,
    {
      label: 'build-index',
      phase: 'Index',
      schema: {
        type: 'object',
        properties: {
          total_chunks: { type: 'number' },
          unique_topics: { type: 'number' },
          key_concepts: { type: 'array', items: { type: 'string' } },
          ready_for_search: { type: 'boolean' }
        }
      }
    }
  );
  
  log('PDF learning complete!');
  
  return {
    pdfs_processed: validExtractions.length,
    total_chunks: allChunks.length,
    embeddings_stored: inserted,
    index_stats: indexStats,
    search_ready: true,
    query_example: `
      -- Search for similar chunks:
      SELECT chunk_text, topic, pdf_path, 
             embedding <=> '[your 384-dim query vector]'::vector as similarity
      FROM knowledge.pdf_embeddings
      ORDER BY similarity
      LIMIT 10;
    `
  };
}
