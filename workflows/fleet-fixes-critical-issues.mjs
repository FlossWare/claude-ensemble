export const meta = {
  name: 'fleet-fixes-critical-issues',
  description: 'Fleet fixes critical issues from implementation review in parallel',
  phases: [
    { title: 'Critical Fixes', detail: 'Fix Phase 4 benchmark, Phase 0 PostgreSQL, Phase 1 vendor neutrality' },
    { title: 'Verification', detail: 'Fleet reviews fixes' }
  ]
};

export default async function({ args, phase, log, agent, parallel }) {

phase('Critical Fixes');

log('Fleet fixing 3 critical issues in parallel...');

const fixes = await parallel([
  // Priority 1: Fix Phase 4 Benchmark Dataset (Grade C)
  () => agent(
    `**CRITICAL FIX: Phase 4 Benchmark Dataset Quality**

**Problems identified by fleet review:**
1. 920+ duplicate questions out of 1000 (only 80 unique)
2. 79 ground truth mismatches (wrong vulnerability labels)
3. MySQL syntax in PostgreSQL migration (will fail on execution)

**Your task:**
1. Read evaluation/benchmark-dataset.json
2. Remove all duplicate questions (keep only unique)
3. Fix ground truth mismatches:
   - innerHTML/XSS should NOT be labeled 'Buffer overflow' or 'Race condition'
   - File upload vulnerabilities should be 'remote_code_execution' not 'privilege_escalation'
   - Plaintext credentials should be 'credential_exposure' not 'remote_code_execution'
4. Fix db/migrations/023_evaluation_schema.sql:
   - Replace MySQL INDEX() syntax with PostgreSQL CREATE INDEX statements
   - Fix CREATE INDEX USING subquery (invalid PostgreSQL)
   - Add UNIQUE INDEX for MATERIALIZED VIEW CONCURRENTLY
5. Regenerate missing questions to reach 1000 UNIQUE questions with correct ground truth
6. Verify: jq '. | unique_by(.question) | length' evaluation/benchmark-dataset.json returns 1000

**Return JSON:**
{
  "unique_questions": 1000,
  "ground_truth_fixed": 79,
  "migration_fixed": true,
  "tests_passing": true,
  "issues": []
}`,
    {
      label: 'Fix Phase 4 Benchmark',
      phase: 'Critical Fixes',
      model: 'opus',
      effort: 'xhigh',
      schema: {
        type: 'object',
        properties: {
          unique_questions: { type: 'number' },
          ground_truth_fixed: { type: 'number' },
          migration_fixed: { type: 'boolean' },
          tests_passing: { type: 'boolean' },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['unique_questions', 'migration_fixed', 'tests_passing']
      }
    }
  ),

  // Priority 2: Fix Phase 0 PostgreSQL Integration (Grade B)
  () => agent(
    `**CRITICAL FIX: Phase 0 PostgreSQL Integration**

**Problems identified by fleet review:**
1. experiment-executor.js uses SQLite instead of PostgreSQL (lines 30, 38, 52)
2. Writes to execution_log table instead of experiments.registry/runs
3. Missing postgres-adapter.js integration

**Your task:**
1. Read shared/experiment-executor.js (or similar experiment execution file)
2. Replace SQLite with PostgreSQL:
   - Import: const { getDB } = require('../learning/postgres-adapter.js');
   - Replace: sqlite3.Database() with getDB()
   - Update all queries to use PostgreSQL syntax
3. Fix table names:
   - execution_log → experiments.runs
   - Match schema from db/migrations/020_experiment_framework.sql
4. Add input validation for experiment.type and experiment.opportunity
5. Fix error handling to throw instead of silently swallowing DB failures
6. Run tests to verify

**Return JSON:**
{
  "sqlite_removed": true,
  "postgres_integrated": true,
  "table_names_fixed": true,
  "tests_passing": true,
  "issues": []
}`,
    {
      label: 'Fix Phase 0 PostgreSQL',
      phase: 'Critical Fixes',
      model: 'sonnet',
      effort: 'high',
      schema: {
        type: 'object',
        properties: {
          sqlite_removed: { type: 'boolean' },
          postgres_integrated: { type: 'boolean' },
          table_names_fixed: { type: 'boolean' },
          tests_passing: { type: 'boolean' },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['sqlite_removed', 'postgres_integrated', 'tests_passing']
      }
    }
  ),

  // Priority 3: Fix Phase 1 Vendor Neutrality (Grade B)
  () => agent(
    `**CRITICAL FIX: Phase 1 Vendor Neutrality**

**Problems identified by fleet review:**
1. role-based-routing.cjs hardcodes 7 vendor model IDs (claude-opus-4, gpt-4o, gemini-2.0-flash-exp, etc.)
2. Static quality/latency/cost values (not dynamic from capability-registry)
3. Capability taxonomy mismatch: capabilities.cjs (6 types) vs role-based-routing.cjs (9 types)
4. No integration between capability-registry.cjs and role-based-routing.cjs

**Your task:**
1. Read shared/role-based-routing.cjs
2. Remove hardcoded MODEL_CAPABILITIES constant
3. Integrate with capability-registry.cjs:
   - Import: const { getCapableModels } = require('./capability-registry.cjs');
   - Replace static lookup with: await getCapableModels(capability, requirements)
4. Fix capability taxonomy mismatch:
   - Align with capabilities.cjs (reasoner, verifier, critic, planner, summarizer, code_reviewer)
   - Remove incompatible role types or map them to capabilities
5. Make it truly vendor-neutral (adding new models = config, not code change)
6. Fix capability-registry.cjs to not expose raw pg Pool
7. Run tests to verify

**Return JSON:**
{
  "hardcoded_models_removed": true,
  "capability_registry_integrated": true,
  "taxonomy_aligned": true,
  "vendor_neutral": true,
  "tests_passing": true,
  "issues": []
}`,
    {
      label: 'Fix Phase 1 Vendor Neutrality',
      phase: 'Critical Fixes',
      model: 'haiku',
      effort: 'high',
      schema: {
        type: 'object',
        properties: {
          hardcoded_models_removed: { type: 'boolean' },
          capability_registry_integrated: { type: 'boolean' },
          taxonomy_aligned: { type: 'boolean' },
          vendor_neutral: { type: 'boolean' },
          tests_passing: { type: 'boolean' },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['hardcoded_models_removed', 'capability_registry_integrated', 'tests_passing']
      }
    }
  )
]);

const allFixed = fixes.filter(Boolean);
log(`Critical fixes complete: ${allFixed.length}/3 successful`);

// Verification
phase('Verification');

log('Fleet reviewing fixes...');

const verifications = await parallel([
  () => agent(
    `Verify Phase 4 fix:
- Benchmark has 1000 UNIQUE questions (no duplicates)
- Ground truth labels are correct
- PostgreSQL migration syntax is valid
- Tests pass

Grade A/B/C/F.`,
    {
      label: 'Verify Phase 4',
      model: 'opus',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          phase: { type: 'string' },
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          verified: { type: 'boolean' },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['phase', 'grade', 'verified']
      }
    }
  ),

  () => agent(
    `Verify Phase 0 fix:
- No SQLite (only PostgreSQL)
- Uses postgres-adapter.js
- Correct table names (experiments.registry/runs)
- Tests pass

Grade A/B/C/F.`,
    {
      label: 'Verify Phase 0',
      model: 'sonnet',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          phase: { type: 'string' },
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          verified: { type: 'boolean' },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['phase', 'grade', 'verified']
      }
    }
  ),

  () => agent(
    `Verify Phase 1 fix:
- No hardcoded model IDs
- Integrated with capability-registry
- Taxonomy aligned (6 capabilities)
- Truly vendor-neutral
- Tests pass

Grade A/B/C/F.`,
    {
      label: 'Verify Phase 1',
      model: 'haiku',
      effort: 'medium',
      schema: {
        type: 'object',
        properties: {
          phase: { type: 'string' },
          grade: { type: 'string', enum: ['A', 'B', 'C', 'F'] },
          verified: { type: 'boolean' },
          issues: { type: 'array', items: { type: 'string' } }
        },
        required: ['phase', 'grade', 'verified']
      }
    }
  )
]);

const allVerified = verifications.filter(Boolean).every(v => v.verified && v.grade !== 'F');
log(`Verification: ${verifications.filter(v => v?.grade === 'A').length}/3 graded A`);

return {
  workflow: 'fleet-fixes-critical-issues',
  fixes_applied: allFixed.length,
  fixes: allFixed,
  verifications: verifications.filter(Boolean),
  all_verified: allVerified,
  upgraded_grades: verifications.filter(Boolean).map(v => ({ phase: v.phase, new_grade: v.grade })),
  remaining_issues: verifications.filter(Boolean).flatMap(v => v.issues || [])
};

}
