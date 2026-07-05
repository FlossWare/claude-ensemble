const { syncWorkflowToNeo4j } = require('./shared/neo4j-realtime-sync.cjs');
const { Pool } = require('pg');
const neo4j = require('neo4j-driver');

const pgPool = new Pool({
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: 'claude'
});

const neo4jDriver = neo4j.driver('bolt://aio-01:7687', neo4j.auth.basic('neo4j', 'neo4j'));

async function backfillWorkflows() {
  console.log('\n=== BACKFILLING WORKFLOWS ===');
  
  const result = await pgPool.query('SELECT id FROM workflow.executions ORDER BY id');
  console.log(`Found ${result.rows.length} workflows to sync`);
  
  let synced = 0, failed = 0;
  
  for (const row of result.rows) {
    const success = await syncWorkflowToNeo4j(row.id);
    if (success) synced++; else failed++;
    
    if (synced % 50 === 0) {
      console.log(`  Progress: ${synced}/${result.rows.length}`);
    }
  }
  
  console.log(`✅ Workflows: ${synced} synced, ${failed} failed`);
  return { synced, failed };
}

async function backfillPDFKnowledge() {
  console.log('\n=== BACKFILLING PDF KNOWLEDGE ===');
  
  const result = await pgPool.query('SELECT * FROM learning.pdf_knowledge');
  console.log(`Found ${result.rows.length} PDF knowledge claims to sync`);
  
  const session = neo4jDriver.session();
  let synced = 0, failed = 0;
  
  try {
    for (const row of result.rows) {
      try {
        // Create PDFKnowledge node
        await session.run(`
          MERGE (k:PDFKnowledge {id: $id})
          SET k.category = $category,
              k.claim = $claim,
              k.confidence = $confidence,
              k.source_page = $source_page,
              k.created_at = datetime($created_at)
        `, {
          id: neo4j.int(row.id),
          category: row.category || 'unknown',
          claim: row.claim,
          confidence: row.confidence || 0.5,
          source_page: row.source_page ? neo4j.int(row.source_page) : null,
          created_at: row.created_at ? row.created_at.toISOString() : new Date().toISOString()
        });
        
        // Link to Topic if category suggests one
        if (row.category) {
          await session.run(`
            MATCH (k:PDFKnowledge {id: $id})
            MERGE (t:Topic {name: $topic})
            MERGE (k)-[:ABOUT]->(t)
          `, {
            id: neo4j.int(row.id),
            topic: row.category
          });
        }
        
        synced++;
      } catch (err) {
        console.error(`  Failed to sync PDF knowledge ${row.id}: ${err.message}`);
        failed++;
      }
    }
  } finally {
    await session.close();
  }
  
  console.log(`✅ PDF Knowledge: ${synced} synced, ${failed} failed`);
  return { synced, failed };
}

async function backfillModelsAndStrategies() {
  console.log('\n=== BACKFILLING MODELS & STRATEGIES ===');
  
  const session = neo4jDriver.session();
  let models_synced = 0, strategies_synced = 0;
  
  try {
    // Sync model capabilities
    const modelResult = await pgPool.query('SELECT * FROM learning.model_capabilities');
    console.log(`Found ${modelResult.rows.length} model capabilities to sync`);
    
    for (const row of modelResult.rows) {
      try {
        await session.run(`
          MERGE (m:Model {id: $id})
          SET m.name = $name,
              m.general_qa = $general_qa,
              m.created_at = datetime()
        `, {
          id: row.model_id,
          name: row.model_id,
          general_qa: row.general_qa || 0.0
        });
        models_synced++;
      } catch (err) {
        console.error(`  Failed to sync model ${row.model_id}: ${err.message}`);
      }
    }
    
    // Sync strategy performance
    const strategyResult = await pgPool.query('SELECT * FROM learning.strategy_performance');
    console.log(`Found ${strategyResult.rows.length} strategies to sync`);
    
    for (const row of strategyResult.rows) {
      try {
        await session.run(`
          MERGE (s:Strategy {name: $name})
          SET s.successes = $successes,
              s.failures = $failures,
              s.avg_reward = $avg_reward,
              s.total_reward = $total_reward,
              s.updated_at = datetime()
        `, {
          name: row.strategy,
          successes: neo4j.int(row.successes || 0),
          failures: neo4j.int(row.failures || 0),
          avg_reward: row.avg_reward || 0.0,
          total_reward: row.total_reward || 0.0
        });
        strategies_synced++;
      } catch (err) {
        console.error(`  Failed to sync strategy ${row.strategy}: ${err.message}`);
      }
    }
  } finally {
    await session.close();
  }
  
  console.log(`✅ Models: ${models_synced} synced`);
  console.log(`✅ Strategies: ${strategies_synced} synced`);
  
  return { models_synced, strategies_synced };
}

async function main() {
  console.log('\n╔════════════════════════════════════════════════════════════════╗');
  console.log('║       COMPREHENSIVE NEO4J BACKFILL - ALL DATA                 ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');
  
  const startTime = Date.now();
  
  try {
    const workflows = await backfillWorkflows();
    const pdf = await backfillPDFKnowledge();
    const models = await backfillModelsAndStrategies();
    
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    
    console.log('\n╔════════════════════════════════════════════════════════════════╗');
    console.log('║                    BACKFILL COMPLETE                           ║');
    console.log('╚════════════════════════════════════════════════════════════════╝\n');
    console.log(`Total time: ${duration}s\n`);
    console.log(`✅ Workflows:      ${workflows.synced} synced`);
    console.log(`✅ PDF Knowledge:  ${pdf.synced} synced`);
    console.log(`✅ Models:         ${models.models_synced} synced`);
    console.log(`✅ Strategies:     ${models.strategies_synced} synced`);
    console.log(`\nTotal nodes created: ${workflows.synced + pdf.synced + models.models_synced + models.strategies_synced}`);
    
  } catch (err) {
    console.error('Backfill failed:', err);
    process.exit(1);
  } finally {
    await pgPool.end();
    await neo4jDriver.close();
  }
}

main();
