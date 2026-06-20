#!/usr/bin/env node

/**
 * Test similarity search using pgvector
 */

const { Pool } = require('pg');
const { execSync } = require('child_process');

async function testSimilaritySearch() {
  console.log('Testing pgvector similarity search...\n');
  
  const pool = new Pool({
    host: '/var/run/postgresql',
    database: 'learning',
    user: process.env.USER
  });

  try {
    // Generate embedding for query
    const query = 'parallel processing performance optimization';
    
    console.log(`Query: "${query}"\n`);
    
    const embeddingScript = `
from sentence_transformers import SentenceTransformer
import json
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
embedding = model.encode('${query}')
print(json.dumps(embedding.tolist()))
`;
    
    const queryEmbedding = JSON.parse(execSync(`python3 -c "${embeddingScript}"`, {
      encoding: 'utf8',
      stdio: 'pipe'
    }));
    
    console.log('Finding similar learnings using cosine similarity...\n');
    
    // Similarity search using pgvector cosine distance (<=>)
    const results = await pool.query(`
      SELECT 
        l.learning_type,
        l.description,
        l.importance,
        1 - (l.learning_embedding <=> $1::vector) as similarity,
        e.workflow_name
      FROM workflow.learnings l
      JOIN workflow.executions e ON l.workflow_execution_id = e.id
      WHERE l.learning_embedding IS NOT NULL
      ORDER BY l.learning_embedding <=> $1::vector
      LIMIT 5
    `, [JSON.stringify(queryEmbedding)]);
    
    console.log('Top 5 similar learnings:\n');
    results.rows.forEach((row, idx) => {
      console.log(`${idx + 1}. [${row.learning_type}] ${row.description}`);
      console.log(`   Similarity: ${(row.similarity * 100).toFixed(1)}% | Importance: ${row.importance} | Workflow: ${row.workflow_name}`);
      console.log('');
    });
    
    await pool.end();
    
    return true;
    
  } catch (error) {
    console.error('Error:', error.message);
    await pool.end();
    return false;
  }
}

testSimilaritySearch()
  .then(success => process.exit(success ? 0 : 1))
  .catch(err => {
    console.error('Fatal:', err);
    process.exit(1);
  });
