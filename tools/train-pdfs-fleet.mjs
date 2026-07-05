#!/usr/bin/env node
/**
 * Train on PDFs - TRUE Fleet Orchestrator Parallel Execution
 * Uses shared/fleet-ssh-orchestrator.js for actual SSH distribution
 */

import { executeParallel } from '../shared/fleet-ssh-orchestrator.js';
import { getDB } from '../learning/postgres-adapter.js';
import { execSync } from 'child_process';

const PDF_DIR = '/mnt/nas/media/books';

async function main() {
  console.log('='.repeat(60));
  console.log('TRAIN ON PDFs - FLEET ORCHESTRATOR');
  console.log('='.repeat(60));

  // Phase 1: Find PDFs
  console.log('\nPhase 1: Finding PDFs...');
  const findCmd = `find ${PDF_DIR} -name "*.pdf" -type f | head -50`;
  const allPDFs = execSync(findCmd, { maxBuffer: 10 * 1024 * 1024 }).toString().trim().split('\n');
  console.log(`✓ Found ${allPDFs.length} PDFs (first 50)`);

  // Phase 2: Create extraction tasks
  console.log(`\nPhase 2: Processing ${allPDFs.length} PDFs IN PARALLEL`);

  const tasks = allPDFs.map((pdf, idx) => ({
    id: `pdf-${idx}`,
    prompt: `Extract claims from PDF: ${pdf}

1. Use pdftotext to extract text: pdftotext "${pdf}" -
2. Parse the text
3. Extract 5-10 key claims that are:
   - Falsifiable (can be proven true/false)
   - Specific (not vague)
   - Important to the document

Return JSON:
{
  "pdf": "${pdf}",
  "claims": ["claim 1", "claim 2", "claim 3"],
  "category": "computer science|electronics|methodology|other"
}`
  }));

  console.log(`\nDistributing ${tasks.length} tasks across fleet...`);
  console.log('Workers: server-01, server-02, server-03, laptop-01, pi-01, pi-02, desktop-ap, server-ap');

  // Execute in PARALLEL
  const startTime = Date.now();

  const results = await executeParallel({
    tasks,
    executionId: 'pdf-training-' + Date.now(),
    skipPreValidation: true  // Skip health checks
  });

  const elapsed = (Date.now() - startTime) / 1000;

  console.log(`\n✓ Completed in ${elapsed.toFixed(1)}s`);
  console.log(`  Throughput: ${(tasks.length / elapsed).toFixed(1)} PDFs/sec`);

  // Phase 3: Process results
  console.log('\nPhase 3: Processing results...');

  const extractions = results.workers || [];
  const successful = extractions.filter(e => e.status === 'success');

  console.log(`  Successful: ${successful.length}/${extractions.length}`);

  // Aggregate all claims
  const allClaims = [];

  successful.forEach(extraction => {
    try {
      const data = JSON.parse(extraction.result);
      if (data.claims) {
        data.claims.forEach(claim => {
          allClaims.push({
            pdf: data.pdf,
            claim,
            category: data.category || 'other'
          });
        });
      }
    } catch (err) {
      console.error(`  Warning: Could not parse result from ${extraction.worker}`);
    }
  });

  console.log(`  Total claims extracted: ${allClaims.length}`);

  // Phase 4: Store in PostgreSQL
  console.log('\nPhase 4: Storing in PostgreSQL...');

  const db = getDB();

  // Create table if not exists
  await db.query(`
    CREATE TABLE IF NOT EXISTS learning.pdf_knowledge (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      pdf_path TEXT NOT NULL,
      category TEXT,
      claim TEXT NOT NULL,
      embedding VECTOR(384),
      confidence FLOAT,
      verified_by TEXT[],
      created_at TIMESTAMPTZ DEFAULT NOW()
    )
  `);

  // Insert claims
  let inserted = 0;

  for (const item of allClaims) {
    await db.query(`
      INSERT INTO learning.pdf_knowledge (pdf_path, category, claim)
      VALUES ($1, $2, $3)
    `, [item.pdf, item.category, item.claim]);
    inserted++;
  }

  console.log(`✓ Inserted ${inserted} claims into PostgreSQL`);

  // Create index
  try {
    await db.query(`
      CREATE INDEX IF NOT EXISTS pdf_knowledge_category_idx
      ON learning.pdf_knowledge (category)
    `);
    console.log('✓ Created index');
  } catch (err) {
    console.log('  Index already exists');
  }

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('PDF TRAINING COMPLETE');
  console.log('='.repeat(60));
  console.log(`PDFs processed: ${successful.length}`);
  console.log(`Claims extracted: ${allClaims.length}`);
  console.log(`Stored in PostgreSQL: ${inserted}`);
  console.log(`Fleet throughput: ${(tasks.length / elapsed).toFixed(1)} PDFs/sec`);
  console.log(`\nNext: Process more PDFs in batches`);
  console.log('='.repeat(60));

  process.exit(0);
}

main().catch(err => {
  console.error('FATAL ERROR:', err);
  process.exit(1);
});
