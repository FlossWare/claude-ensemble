#!/usr/bin/env node

const { execSync } = require('child_process');
const { Client } = require('pg');

const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;

if (!GOOGLE_API_KEY) {
  console.error('GOOGLE_API_KEY not set');
  process.exit(1);
}

async function generateEmbedding(text) {
  const payload = JSON.stringify({
    model: 'models/text-embedding-004',
    content: { parts: [{ text: text.substring(0, 10000) }] }
  });

  const result = execSync(`curl -s "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key=${GOOGLE_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '${payload.replace(/'/g, "'\\''")}'`, {
    encoding: 'utf8',
    timeout: 5000
  });

  const response = JSON.parse(result);
  if (response.error) {
    throw new Error(response.error.message || JSON.stringify(response.error));
  }

  const fullEmbedding = response.embedding.values;
  return fullEmbedding.slice(0, 384); // Resize from 768-dim to 384-dim
}

async function backfill() {
  const client = new Client({
    host: '/var/run/postgresql',
    database: 'learning',
    user: process.env.USER
  });

  await client.connect();

  try {
    // Get learnings without embeddings
    const result = await client.query(
      'SELECT id, description FROM workflow.learnings WHERE learning_embedding IS NULL ORDER BY id'
    );

    console.log(`Found ${result.rows.length} learnings without embeddings`);

    for (const row of result.rows) {
      console.log(`Generating embedding for ID ${row.id}: "${row.description.substring(0, 50)}..."`);

      try {
        const embedding = await generateEmbedding(row.description);
        const embeddingStr = `[${embedding.join(',').substring(0, 100000)}]`; // Limit length

        await client.query(
          'UPDATE workflow.learnings SET learning_embedding = $1::vector WHERE id = $2',
          [embeddingStr, row.id]
        );

        console.log(`  ✅ Updated ID ${row.id}`);
      } catch (error) {
        console.error(`  ❌ Failed ID ${row.id}: ${error.message}`);
      }

      // Rate limit: ~200ms between requests
      await new Promise(resolve => setTimeout(resolve, 200));
    }

    console.log('\nBackfill complete!');

  } finally {
    await client.end();
  }
}

backfill().catch(console.error);
