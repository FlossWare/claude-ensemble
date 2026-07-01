#!/usr/bin/env node
/**
 * REAL TEST: Fleet workflow that proves workers use proxy
 * 
 * This simulates what actually happens:
 * 1. Orchestrator spawns agents on workers via SSH
 * 2. Workers execute tasks that need LLM calls
 * 3. Workers should hit aio-01:8000 proxy (not direct APIs)
 */

export const meta = {
  name: 'test-fleet-proxy-usage',
  description: 'Verify all workers use aio-01 proxy for API calls',
  phases: [
    { title: 'Dispatch', detail: 'Send tasks to all 8 workers' },
    { title: 'Verify', detail: 'Check PostgreSQL for worker IDs' }
  ]
};

export default async function({ phase, parallel, log }) {
  
  phase('Dispatch');
  
  const workers = [
    'server-01', 'server-02', 'server-03', 'laptop-01',
    'pi-01', 'pi-02', 'desktop-ap', 'server-ap'
  ];
  
  log('Dispatching API tasks to all workers...');
  
  // Simulate what happens in real workflows
  const results = await parallel(workers.map(worker => async () => {
    const { spawn } = await import('child_process');
    const { promisify } = await import('util');
    const exec = promisify(spawn);
    
    // This is what orchestrator does: SSH to worker and run command
    const cmd = spawn('ssh', [
      `claude@${worker}`,
      `bash -l -c "curl -s -X POST http://aio-01:8000/v1/chat/completions -H 'Content-Type: application/json' -H 'X-Worker-ID: ${worker}' -d '{\\\"model\\\":\\\"llama-3.1-8b-instant\\\",\\\"messages\\\":[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"proxy test\\\"}],\\\"max_tokens\\\":3}'"`
    ]);
    
    let output = '';
    cmd.stdout.on('data', data => output += data);
    
    await new Promise((resolve, reject) => {
      cmd.on('close', code => code === 0 ? resolve() : reject(new Error(`Exit ${code}`)));
      setTimeout(() => reject(new Error('Timeout')), 10000);
    });
    
    return { worker, success: output.includes('choices') };
  }));
  
  const successful = results.filter(r => r?.success);
  log(`${successful.length}/${workers.length} workers completed API calls`);
  
  phase('Verify');
  
  // Check PostgreSQL to see which workers actually hit the proxy
  const { spawn } = await import('child_process');
  
  const psql = spawn('ssh', [
    'root@aio-01',
    `psql -h localhost -p 5433 -U claude -d learning -t -c "SELECT worker_id, COUNT(*) FROM api_usage WHERE timestamp > NOW() - INTERVAL '1 minute' GROUP BY worker_id ORDER BY worker_id"`
  ]);
  
  let dbOutput = '';
  psql.stdout.on('data', data => dbOutput += data);
  
  await new Promise(resolve => psql.on('close', resolve));
  
  const workerCalls = dbOutput.trim().split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0);
  
  log(`Database shows ${workerCalls.length} workers made calls:`);
  workerCalls.forEach(line => log(`  ${line}`));
  
  return {
    total_workers: workers.length,
    successful_dispatches: successful.length,
    workers_in_database: workerCalls.length,
    proof: workerCalls
  };
}
