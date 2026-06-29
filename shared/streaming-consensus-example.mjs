/**
 * Streaming Consensus Usage Example
 *
 * Demonstrates real-time consensus building with progress updates
 * Run: node shared/streaming-consensus-example.mjs
 */

import { streamConsensus, EventTypes } from './streaming-consensus.js';

// Simulated worker executor (replace with actual model execution)
async function executeWorker(worker) {
  console.log(`  🚀 Executing ${worker.model}...`);

  // Simulate varying execution times
  const delay = Math.random() * 2000 + 1000; // 1-3 seconds
  await new Promise(resolve => setTimeout(resolve, delay));

  // Simulate analysis results (3 models agree, 1 disagrees)
  const results = {
    opus: { verdict: 'SECURE', confidence: 0.92, reasoning: 'No vulnerabilities found' },
    sonnet: { verdict: 'SECURE', confidence: 0.88, reasoning: 'Passes all security checks' },
    haiku: { verdict: 'SECURE', confidence: 0.85, reasoning: 'Safe to deploy' },
    gemini: { verdict: 'VULNERABLE', confidence: 0.75, reasoning: 'Potential XSS risk detected' }
  };

  const result = results[worker.model] || results.opus;

  return {
    result,
    confidence: result.confidence,
    inputTokens: Math.floor(Math.random() * 1000) + 500,
    outputTokens: Math.floor(Math.random() * 500) + 200,
    cost: (Math.random() * 0.05).toFixed(4)
  };
}

// Main demo
async function main() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  Streaming Consensus Demo');
  console.log('  Building Block #8: Real-time Consensus Updates');
  console.log('═══════════════════════════════════════════════════\n');

  const workers = [
    { id: 'w1', model: 'opus', task: 'Analyze firmware security' },
    { id: 'w2', model: 'sonnet', task: 'Analyze firmware security' },
    { id: 'w3', model: 'haiku', task: 'Analyze firmware security' },
    { id: 'w4', model: 'gemini', task: 'Analyze firmware security' }
  ];

  console.log(`📋 Task: ${workers[0].task}`);
  console.log(`👥 Workers: ${workers.length} models\n`);

  console.log('─────────────────────────────────────────────────\n');

  let workerCount = 0;
  let partialCount = 0;

  try {
    for await (const event of streamConsensus(workers, {
      executor: executeWorker,
      emitPartialAfterEach: true,
      minWorkersForPartial: 2,
      storeInDatabase: false // Disable for demo
    })) {
      switch (event.type) {
        case EventTypes.WORKER_STARTED:
          console.log(`🟡 Worker started: ${event.data.model}`);
          break;

        case EventTypes.WORKER_COMPLETED:
          workerCount++;
          console.log(`✅ Worker completed: ${event.data.model}`);
          const workerResult = event.data.result?.result || event.data.result;
          console.log(`   Verdict: ${workerResult.verdict}`);
          console.log(`   Confidence: ${(event.data.confidence * 100).toFixed(1)}%`);
          console.log(`   Duration: ${event.data.duration}ms`);
          console.log(`   Cost: $${event.data.cost}`);
          console.log();
          break;

        case EventTypes.PARTIAL_CONSENSUS:
          partialCount++;
          console.log(`📊 Partial Consensus #${partialCount}:`);
          console.log(`   Progress: ${event.data.completedWorkers}/${workers.length} workers`);
          console.log(`   Current verdict: ${event.data.result.verdict}`);
          console.log(`   Consensus score: ${(event.data.consensusScore * 100).toFixed(1)}%`);
          console.log(`   Agreement: ${(event.data.agreementRatio * 100).toFixed(1)}% (${event.data.agreeingWorkers}/${event.data.completedWorkers})`);
          console.log(`   Diversity: ${(event.data.diversity * 100).toFixed(1)}%`);
          console.log(`   Models agreeing: ${event.data.models.join(', ')}`);
          console.log();
          break;

        case EventTypes.FINAL_CONSENSUS:
          console.log('─────────────────────────────────────────────────\n');
          console.log('🎯 FINAL CONSENSUS REACHED\n');
          console.log(`   Verdict: ${event.data.result.verdict}`);
          console.log(`   Reasoning: ${event.data.result.reasoning}`);
          console.log();
          console.log('   Metrics:');
          console.log(`   ├─ Consensus Score: ${(event.data.consensusScore * 100).toFixed(1)}%`);
          console.log(`   ├─ Agreement: ${(event.data.agreementRatio * 100).toFixed(1)}% (${event.data.agreeingWorkers}/${event.data.totalWorkers} workers)`);
          console.log(`   ├─ Diversity: ${(event.data.diversity * 100).toFixed(1)}%`);
          console.log(`   └─ Avg Confidence: ${(event.data.avgConfidence * 100).toFixed(1)}%`);
          console.log();
          console.log(`   Agreeing Models: ${event.data.models.join(', ')}`);
          console.log(`   Timestamp: ${event.data.timestamp}`);

          if (event.data.errors && event.data.errors.length > 0) {
            console.log();
            console.log(`   ⚠️  Errors: ${event.data.errors.length} worker(s) failed`);
            event.data.errors.forEach(err => {
              console.log(`      - ${err.model}: ${err.error}`);
            });
          }

          console.log('\n═══════════════════════════════════════════════════\n');

          // Interpretation
          if (event.data.consensusScore >= 0.8) {
            console.log('✅ Strong consensus - High confidence in result');
          } else if (event.data.consensusScore >= 0.6) {
            console.log('⚠️  Moderate consensus - Consider additional validation');
          } else {
            console.log('❌ Weak consensus - Results diverge significantly');
          }

          if (event.data.diversity > 0.3) {
            console.log(`⚠️  High diversity (${(event.data.diversity * 100).toFixed(1)}%) - Multiple perspectives present`);
          }

          console.log();
          break;

        case EventTypes.ERROR:
          console.error(`❌ Error: ${event.data.error}`);
          if (event.data.model) {
            console.error(`   Worker: ${event.data.model}`);
          }
          console.log();
          break;
      }
    }

    console.log(`✅ Demo complete! ${workerCount} workers executed, ${partialCount} partial updates\n`);

  } catch (error) {
    console.error('Fatal error:', error.message);
    process.exit(1);
  }
}

// Run demo
main().catch(console.error);
