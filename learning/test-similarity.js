const { WorkflowStorageAdapter } = require('./workflow-storage-adapter.js');

async function test() {
  const db = new WorkflowStorageAdapter();
  
  const similar = await db.findSimilarWorkflows('Test Google embeddings', 5);
  
  console.log('\n🔍 Similar workflows:');
  similar.forEach((w, i) => {
    console.log(`\n${i + 1}. ${w.description}`);
    console.log(`   Workflow: ${w.workflow_name}`);
    console.log(`   Distance: ${w.distance.toFixed(4)}`);
    console.log(`   Created: ${w.created_at}`);
  });
  
  await db.disconnect();
}

test().catch(console.error);
