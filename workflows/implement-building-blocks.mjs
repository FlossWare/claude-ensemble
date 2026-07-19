#!/usr/bin/env node
/**
 * Implement Building Blocks #2-8 (Parallel Fleet Implementation)
 *
 * Phase 1: Implement (7 parallel agents)
 * Phase 2: Review (fleet reviews all implementations)
 *
 * Building blocks:
 * #2: Model capability matrix (task-specific routing)
 * #3: Confidence calibration (overconfident detection)
 * #4: Consensus caching (exact + semantic)
 * #5: Batch processing (parallel consensus)
 * #6: OrientDB integration (graph relationships)
 * #7: Real fleet distribution (SSH to workers)
 * #8: Streaming responses (real-time updates)
 */

export const meta = {
  name: 'implement-building-blocks',
  description: 'Implement building blocks #2-8 in parallel, then fleet review',
  phases: [
    { title: 'Implement', detail: '7 parallel agents implement building blocks' },
    { title: 'Review', detail: 'Fleet reviews all implementations' },
    { title: 'Report', detail: 'Summary and next steps' }
  ]
};

const BUILDING_BLOCKS = [
  {
    id: 2,
    name: 'model-capability-matrix',
    title: 'Model Capability Matrix',
    description: 'Task-specific model routing based on capability scores',
    files: [
      'shared/model-capability-matrix.js',
      'shared/MODEL-CAPABILITY-MATRIX-README.md',
      'shared/model-capability-matrix.test.cjs'
    ],
    requirements: `
Implement a model capability matrix that routes tasks to best-suited models.

Requirements:
- JSON file: learning/model-capability-matrix.json
- Capability scores per model per task type (0.0-1.0)
- Task types: code_review, research, math, security, creative_writing, etc.
- Function: selectModelsByCapability(taskType) → sorted list of models
- Updates from execution history (track actual performance)
- PostgreSQL storage: monitoring.model_capabilities table

Example:
{
  "opus": { "code_review": 0.95, "research": 0.90, "math": 0.85 },
  "haiku": { "code_review": 0.75, "research": 0.70, "math": 0.65 },
  "gpt-4o": { "code_review": 0.85, "math": 0.92, "research": 0.88 }
}

Integration: Use in weighted-voting to dynamically adjust tier weights based on task type.
`
  },
  {
    id: 3,
    name: 'confidence-calibration',
    title: 'Confidence Calibration',
    description: 'Detect and penalize overconfident models',
    files: [
      'shared/confidence-calibration.js',
      'shared/CONFIDENCE-CALIBRATION-README.md',
      'shared/confidence-calibration.test.cjs'
    ],
    requirements: `
Implement confidence calibration to detect models that are systematically overconfident.

Requirements:
- Track: claimed_confidence vs actual_correctness per model
- Calibration error = |claimed - actual| (0 = perfect, 1 = worst)
- PostgreSQL: workflow.confidence_calibration table
- Penalty: reduce tier weight for overconfident models
- Update: after each workflow with human feedback or verified outcome

Example:
Model claims 95% confidence but is only 70% correct → calibration_error = 0.25
Apply penalty: tier_weight *= (1 - calibration_error) = 1.0 * 0.75 = 0.75

Detection algorithm:
1. Bin claimed confidence (0-10%, 10-20%, ... 90-100%)
2. For each bin: calculate actual correctness rate
3. Calibration curve: perfect = diagonal line (claimed = actual)
4. Penalize models with large deviations

Integration: Modify weighted-voting to apply calibration penalty before final vote.
`
  },
  {
    id: 4,
    name: 'consensus-cache',
    title: 'Consensus Caching',
    description: 'Cache consensus results (exact match + semantic similarity)',
    files: [
      'shared/consensus-cache.cjs',
      'shared/CONSENSUS-CACHE-README.md',
      'shared/consensus-cache.test.cjs'
    ],
    requirements: `
Implement consensus caching to avoid re-running identical or very similar queries.

Requirements:
- Level 1: Exact match (hash of question + models + task_type)
- Level 2: Semantic similarity (embedding cosine distance < 0.1)
- PostgreSQL: workflow.consensus_cache table
- TTL: 7 days (configurable)
- Cache hit → return cached result instantly (<10ms)
- Cache miss → run consensus, store result + embedding

Schema:
- question_hash TEXT (SHA256 of normalized question)
- question_embedding VECTOR(384) (for semantic search)
- models TEXT[] (array of model names used)
- task_type TEXT
- consensus_answer TEXT
- confidence NUMERIC
- created_at TIMESTAMP
- expires_at TIMESTAMP

Cache invalidation:
- TTL expires
- Model weights change significantly
- Human feedback contradicts cached result

Integration: Wrap weighted-voting with cache lookup/store.
`
  },
  {
    id: 5,
    name: 'batch-consensus',
    title: 'Batch Processing',
    description: 'Parallel consensus for multiple questions',
    files: [
      'shared/batch-consensus.cjs',
      'shared/BATCH-CONSENSUS-README.md',
      'shared/batch-consensus.test.cjs'
    ],
    requirements: `
Implement batch consensus processing for multiple questions in parallel.

Requirements:
- Input: array of questions (up to 100)
- Process: parallel consensus (up to 8 concurrent)
- Output: array of results (same order as input)
- Progress callback: (completed, total) => {}
- Error handling: failed questions return null, don't block others
- Optimizations:
  - Cache lookup before consensus
  - Batch embedding generation (single API call)
  - Worker pooling (reuse workers across questions)

Example:
const questions = [
  'Is this code vulnerable to XSS?',
  'Does this API handle rate limits?',
  'Is this function thread-safe?'
];

const results = await processBatch(questions, {
  models: ['opus', 'sonnet', 'haiku'],
  task_type: 'code_review',
  concurrency: 3,
  progressCallback: (done, total) => console.log(\`\${done}/\${total}\`)
});

// Returns: [result1, result2, result3] (or null for failures)

Performance target: 3x faster than sequential for 10+ questions.
`
  },
  {
    id: 6,
    name: 'orientdb-integration',
    title: 'OrientDB Integration',
    description: 'Graph database for workflow relationships',
    files: [
      'learning/orientdb-sync-service.js',
      'learning/ORIENTDB-INTEGRATION-README.md',
      'learning/orientdb-sync.test.cjs'
    ],
    requirements: `
Implement OrientDB graph database integration for workflow relationships.

Requirements:
- Nodes: Workflow, Phase, Worker, ArbiterDecision, Learning, Model
- Relationships:
  - (Workflow)-[:CONTAINS]->(Phase)
  - (Phase)-[:NEXT_PHASE]->(Phase)
  - (Worker)-[:EXECUTES]->(Task)
  - (Worker)-[:USES_MODEL]->(Model)
  - (Workflow)-[:ARBITRATED_BY]->(ArbiterDecision)
  - (Workflow)-[:PRODUCED]->(Learning)
  - (Learning)-[:RELATED_TO]->(Learning) [via semantic similarity]

- Sync service: sync PostgreSQL → OrientDB every 5 min
- Queries:
  - Find workflows using same model
  - Find related learnings (graph traversal)
  - Trace workflow lineage (which workflows led to this learning)

Connection: http://aio-01:2480 (REST API) / binary on aio-01:2424
Credentials: orientdb / (password in env)

Graph algorithms:
- PageRank: identify most influential learnings
- Community detection: cluster related workflows
- Shortest path: trace how knowledge propagated

Integration: Optional (doesn't block other features), but provides rich querying.
`
  },
  {
    id: 7,
    name: 'fleet-ssh-distribution',
    title: 'Real Fleet Distribution',
    description: 'SSH to workers for true distributed execution',
    files: [
      'shared/fleet-ssh-orchestrator.js',
      'shared/FLEET-SSH-README.md',
      'shared/fleet-ssh-orchestrator.test.cjs'
    ],
    requirements: `
Implement SSH-based fleet distribution for true distributed execution.

Requirements:
- SSH to workers: ssh claude@server-01, server-02, server-03, laptop-01, etc.
- Execute: ssh claude@server-01 'claude -p "your prompt here"'
- Load balancing: round-robin or capability-based
- Worker health checks: ssh + 'echo OK' (timeout: 5s)
- Failure handling: retry on next worker, mark failed worker as down
- Concurrency: up to 8 workers in parallel
- Logs: capture stdout/stderr from each worker

Worker selection:
1. Check worker health (cache for 1 min)
2. Filter by capability (if task_type specified)
3. Round-robin or least-loaded

SSH command template:
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \\
  claude@{worker} \\
  'cd ~/workspace && claude -p "{prompt}"'

Integration: Replace local agent() calls with SSH distribution in workflows.

Config: lib/fleet-api-policy.json (8 workers defined)
`
  },
  {
    id: 8,
    name: 'streaming-consensus',
    title: 'Streaming Responses',
    description: 'Real-time consensus updates as workers respond',
    files: [
      'shared/streaming-consensus.js',
      'shared/STREAMING-CONSENSUS-README.md',
      'shared/streaming-consensus.test.cjs'
    ],
    requirements: `
Implement streaming consensus for real-time updates as workers respond.

Requirements:
- Emit events as each worker completes (not just final result)
- Event types:
  - worker_started: { worker_id, model }
  - worker_completed: { worker_id, result, confidence }
  - partial_consensus: { current_answer, confidence, workers_completed }
  - final_consensus: { answer, confidence, all_results }

- Progressive consensus: update answer as more workers complete
- WebSocket support (optional): real-time dashboard updates
- Async iterators: for await (const update of streamConsensus(...)) {}

Example:
for await (const update of streamConsensus(question, models)) {
  if (update.type === 'worker_completed') {
    console.log(\`Worker \${update.worker_id} done\`);
  } else if (update.type === 'partial_consensus') {
    console.log(\`Current answer: \${update.current_answer} (\${update.confidence})\`);
  }
}

Use case: Long-running consensus where user wants to see progress, not just final answer.

Integration: Optional enhancement to weighted-voting (add streaming mode flag).
`
  }
];

export default async function({ args, phase, log, agent, parallel }) {
  log('🚀 Implementing Building Blocks #2-8 with Fleet');
  log('═'.repeat(80));

  // Phase 1: Implement (7 parallel agents)
  const implementations = await phase('Implement', async () => {
    log('Spawning 7 parallel implementation agents...');
    log('');

    const results = await parallel(
      BUILDING_BLOCKS.map(block => () =>
        agent(`
You are implementing building block #${block.id}: ${block.title}

${block.description}

REQUIREMENTS:
${block.requirements}

FILES TO CREATE:
${block.files.map(f => `- ${f}`).join('\n')}

DELIVERABLES:
1. Implementation file (shared/${block.name}.js or .cjs)
2. README (shared/${block.name.toUpperCase()}-README.md)
3. Test file (shared/${block.name}.test.cjs)

IMPORTANT:
- Write production-quality code (error handling, logging, tests)
- Follow existing patterns (see shared/weighted-voting.cjs as example)
- Use PostgreSQL via learning/postgres-adapter.js
- Include comprehensive README with usage examples
- Write at least 3 test cases

Return JSON with:
{
  "block_id": ${block.id},
  "block_name": "${block.name}",
  "status": "success" | "error",
  "files_created": ["file1", "file2", ...],
  "implementation_summary": "Brief summary of what was implemented",
  "test_results": "Test status",
  "notes": "Any important notes or caveats"
}
        `, {
          label: `implement-block-${block.id}`,
          phase: 'Implement',
          schema: {
            type: 'object',
            properties: {
              block_id: { type: 'number' },
              block_name: { type: 'string' },
              status: { type: 'string', enum: ['success', 'error'] },
              files_created: { type: 'array', items: { type: 'string' } },
              implementation_summary: { type: 'string' },
              test_results: { type: 'string' },
              notes: { type: 'string' }
            },
            required: ['block_id', 'block_name', 'status', 'implementation_summary']
          }
        })
      )
    );

    log('');
    log('Implementation phase complete!');
    log('');

    // Filter out nulls (failed agents)
    const successful = results.filter(Boolean);
    log(`✅ Successful: ${successful.filter(r => r.status === 'success').length}/${BUILDING_BLOCKS.length}`);
    log(`❌ Failed: ${results.filter(r => !r || r.status === 'error').length}/${BUILDING_BLOCKS.length}`);
    log('');

    return successful;
  });

  // Phase 2: Fleet Review (6 models review all implementations)
  const reviews = await phase('Review', async () => {
    log('Fleet review: 6 models reviewing all implementations...');
    log('');

    const reviewers = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'];

    const reviewResults = await parallel(
      implementations.map(impl => () =>
        parallel(
          reviewers.map(model => () =>
            agent(`
Review the implementation of building block #${impl.block_id}: ${impl.block_name}

IMPLEMENTATION SUMMARY:
${impl.implementation_summary}

FILES CREATED:
${impl.files_created?.join('\n') || 'Unknown'}

TEST RESULTS:
${impl.test_results || 'Unknown'}

NOTES:
${impl.notes || 'None'}

Review for:
1. Code quality (A/B/C grade)
2. Completeness (does it meet requirements?)
3. Testing (adequate test coverage?)
4. Documentation (clear README?)
5. Integration (fits with existing system?)

Return JSON with:
{
  "reviewer_model": "${model}",
  "block_id": ${impl.block_id},
  "grade": "A" | "B" | "C",
  "completeness": 0-100,
  "issues_found": ["issue1", "issue2", ...],
  "recommendations": ["rec1", "rec2", ...],
  "verdict": "APPROVED" | "NEEDS_FIXES" | "REJECT"
}
            `, {
              label: `review-block-${impl.block_id}-${model}`,
              phase: 'Review',
              model: model,
              schema: {
                type: 'object',
                properties: {
                  reviewer_model: { type: 'string' },
                  block_id: { type: 'number' },
                  grade: { type: 'string', enum: ['A', 'B', 'C'] },
                  completeness: { type: 'number' },
                  issues_found: { type: 'array', items: { type: 'string' } },
                  recommendations: { type: 'array', items: { type: 'string' } },
                  verdict: { type: 'string', enum: ['APPROVED', 'NEEDS_FIXES', 'REJECT'] }
                },
                required: ['reviewer_model', 'block_id', 'grade', 'verdict']
              }
            })
          )
        )
      )
    );

    log('');
    log('Fleet review complete!');
    log('');

    return reviewResults;
  });

  // Phase 3: Report
  await phase('Report', async () => {
    log('');
    log('═'.repeat(80));
    log('📊 IMPLEMENTATION REPORT');
    log('═'.repeat(80));
    log('');

    // Summary by block
    implementations.forEach((impl, idx) => {
      const blockReviews = reviews[idx]?.filter(Boolean) || [];
      const grades = blockReviews.map(r => r.grade);
      const verdicts = blockReviews.map(r => r.verdict);
      const avgCompleteness = blockReviews.reduce((sum, r) => sum + (r.completeness || 0), 0) / blockReviews.length;

      const gradeCount = {
        A: grades.filter(g => g === 'A').length,
        B: grades.filter(g => g === 'B').length,
        C: grades.filter(g => g === 'C').length
      };

      const approved = verdicts.filter(v => v === 'APPROVED').length;
      const needsFixes = verdicts.filter(v => v === 'NEEDS_FIXES').length;
      const rejected = verdicts.filter(v => v === 'REJECT').length;

      log(`Building Block #${impl.block_id}: ${impl.block_name}`);
      log(`  Status: ${impl.status === 'success' ? '✅ SUCCESS' : '❌ FAILED'}`);
      log(`  Files: ${impl.files_created?.length || 0}`);
      log(`  Grades: A=${gradeCount.A}, B=${gradeCount.B}, C=${gradeCount.C}`);
      log(`  Completeness: ${avgCompleteness.toFixed(0)}%`);
      log(`  Verdicts: ✅ ${approved} | ⚠️ ${needsFixes} | ❌ ${rejected}`);

      // Show common issues
      const allIssues = blockReviews.flatMap(r => r.issues_found || []);
      if (allIssues.length > 0) {
        const issueFreq = {};
        allIssues.forEach(issue => {
          issueFreq[issue] = (issueFreq[issue] || 0) + 1;
        });
        const topIssues = Object.entries(issueFreq)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([issue, count]) => `${issue} (${count} reviewers)`);

        if (topIssues.length > 0) {
          log(`  Top Issues:`);
          topIssues.forEach(issue => log(`    - ${issue}`));
        }
      }

      log('');
    });

    log('═'.repeat(80));
    log('OVERALL STATS');
    log('═'.repeat(80));
    log(`Total blocks: ${BUILDING_BLOCKS.length}`);
    log(`Implemented: ${implementations.length}`);
    log(`Reviewed by: 6 models`);
    log(`Total reviews: ${reviews.flat().filter(Boolean).length}`);
    log('');

    const allGrades = reviews.flat().filter(Boolean).map(r => r.grade);
    const gradeStats = {
      A: allGrades.filter(g => g === 'A').length,
      B: allGrades.filter(g => g === 'B').length,
      C: allGrades.filter(g => g === 'C').length
    };
    log(`Grade distribution: A=${gradeStats.A}, B=${gradeStats.B}, C=${gradeStats.C}`);

    const allVerdicts = reviews.flat().filter(Boolean).map(r => r.verdict);
    const approved = allVerdicts.filter(v => v === 'APPROVED').length;
    const needsFixes = allVerdicts.filter(v => v === 'NEEDS_FIXES').length;
    const rejected = allVerdicts.filter(v => v === 'REJECT').length;
    log(`Verdict distribution: ✅ ${approved} | ⚠️ ${needsFixes} | ❌ ${rejected}`);
    log('');

    log('═'.repeat(80));
    log('NEXT STEPS');
    log('═'.repeat(80));
    log('1. Review implementation files in shared/');
    log('2. Run tests: find shared -name "*.test.cjs" -exec node {} \\;');
    log('3. Fix issues flagged by fleet review');
    log('4. Commit all building blocks');
    log('5. Update README.md with new building blocks');
    log('');
  });

  return {
    total_blocks: BUILDING_BLOCKS.length,
    implemented: implementations.length,
    successful: implementations.filter(i => i.status === 'success').length,
    reviews: reviews.flat().filter(Boolean).length,
    fleet_consensus: 'See report above'
  };
}
