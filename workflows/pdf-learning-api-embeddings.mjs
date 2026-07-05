/**
 * Distributed PDF Learning Workflow - API-Based Embeddings
 * Uses Mistral Embed API (FREE via OpenRouter) instead of downloading models
 */

export const meta = {
  name: 'pdf-learning-api',
  description: 'Distributed PDF learning using FREE Mistral Embed API (1024-dim)',
  phases: [
    { title: 'Extract', detail: 'Extract text from PDFs via fleet workers' },
    { title: 'Chunk', detail: 'Split into semantic chunks' },
    { title: 'Embed', detail: 'Generate embeddings via Mistral API (FREE)' },
    { title: 'Store', detail: 'Store in PostgreSQL pgvector (1024-dim)' }
  ]
};

export default async function({ phase, parallel, agent, log, args }) {
  const { execSync } = await import('child_process');

  // Get PDF paths from args
  const pdfPaths = args?.pdfs || [];
  if (!pdfPaths.length) {
    throw new Error('No PDF paths provided. Pass --args \'{"pdfs":["path1.pdf"]}\'');
  }

  log(`Processing ${pdfPaths.length} PDFs with API-based embeddings (no model download!)`);

  // Phase 1: Extract text from PDFs (distributed across 8 workers)
  phase('Extract');
  const extractions = await parallel(pdfPaths.map((pdf, idx) => async () => {
    return agent(
      `Extract all text from PDF: ${pdf}

      Use PyPDF2 or similar to extract text.
      Return JSON: {
        "pdf": "${pdf}",
        "text": "full extracted text",
        "pages": number_of_pages,
        "metadata": {"title": "...", "author": "..."}
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
  log(`Extracted ${validExtractions.length}/${pdfPaths.length} PDFs`);

  // Phase 2: Chunk into semantic segments (distributed)
  phase('Chunk');
  const chunked = await parallel(validExtractions.map((ext, idx) => async () => {
    return agent(
      `Split this PDF text into semantic chunks (300-800 words each):

      PDF: ${ext.pdf}
      Text: ${ext.text.substring(0, 30000)}...

      Return: {
        "chunks": [
          {"text": "chunk 1 text...", "start_page": 1, "topic": "brief topic"},
          {"text": "chunk 2 text...", "start_page": 2, "topic": "brief topic"}
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
                  topic: { type: 'string' }
                }
              }
            }
          }
        }
      }
    );
  }));

  const allChunks = chunked.filter(Boolean).flatMap((c, pdfIdx) =>
    c.chunks.map((chunk, chunkIdx) => ({
      ...chunk,
      chunk_index: chunkIdx,
      pdf: validExtractions[pdfIdx].pdf,
      pdf_metadata: validExtractions[pdfIdx].metadata
    }))
  );

  log(`Created ${allChunks.length} chunks`);

  // Phase 3: Generate embeddings via Mistral API (FREE, 1024-dim, NO DOWNLOAD!)
  phase('Embed');
  log('Generating embeddings via Mistral API (FREE)...');

  const embeddings = [];
  for (let i = 0; i < allChunks.length; i++) {
    const chunk = allChunks[i];
    try {
      // Call our API proxy which routes to Mistral via OpenRouter
      const cleanText = chunk.text.substring(0, 8000)
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, ' ')
        .replace(/\r/g, ' ');

      const result = execSync(
        `curl -s -m 30 http://aio-01:8002/v1/embeddings -H "Content-Type: application/json" -d '{"model":"mistral-embed","input":"${cleanText}"}'`,
        { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 }
      );

      const parsed = JSON.parse(result);
      if (parsed.data?.[0]?.embedding) {
        embeddings.push(parsed.data[0].embedding);
        if ((i + 1) % 10 === 0) log(`  ${i + 1}/${allChunks.length} embeddings generated`);
      } else {
        log(`Warning: No embedding for chunk ${i}`);
        embeddings.push(null);
      }
    } catch (e) {
      log(`Error chunk ${i}: ${e.message}`);
      embeddings.push(null);
    }
  }

  const validEmbeddings = embeddings.filter(e => e);
  log(`Generated ${validEmbeddings.length}/${allChunks.length} embeddings (1024-dim)`);

  // Phase 4: Store in PostgreSQL pgvector
  phase('Store');
  log('Storing in PostgreSQL...');

  const { getDB } = await import('../shared/workflow-storage-adapter.js');
  const db = getDB();
  const conn = await db.pool.connect();

  try {
    // Create table with 1024-dim vectors
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

    // Create HNSW index for fast search
    await conn.query(`
      CREATE INDEX IF NOT EXISTS pdf_embeddings_hnsw_idx
      ON knowledge.pdf_embeddings
      USING hnsw (embedding vector_cosine_ops)
    `);

    // Insert chunks with embeddings
    let inserted = 0;
    for (let i = 0; i < allChunks.length; i++) {
      if (!embeddings[i]) continue;

      const chunk = allChunks[i];
      await conn.query(`
        INSERT INTO knowledge.pdf_embeddings
        (pdf_path, chunk_index, chunk_text, topic, start_page, embedding, pdf_metadata)
        VALUES ($1, $2, $3, $4, $5, $6::vector, $7)
      `, [
        chunk.pdf,
        chunk.chunk_index,
        chunk.text,
        chunk.topic,
        chunk.start_page,
        JSON.stringify(embeddings[i]),
        JSON.stringify(chunk.pdf_metadata)
      ]);
      inserted++;
    }

    log(`Stored ${inserted} chunks in PostgreSQL`);

  } finally {
    conn.release();
  }

  log('✅ PDF learning complete!');

  return {
    pdfs_processed: validExtractions.length,
    total_chunks: allChunks.length,
    embeddings_generated: validEmbeddings.length,
    embeddings_stored: inserted,
    embedding_model: 'mistral-embed (FREE, 1024-dim)',
    no_download: true,
    query_example: `
-- Search similar chunks:
SELECT chunk_text, topic, pdf_path,
       embedding <=> $1::vector as distance
FROM knowledge.pdf_embeddings
ORDER BY distance
LIMIT 10;
    `
  };
}
