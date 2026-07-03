export const meta = {
  name: 'validate-fixes-252-models',
  description: 'Validate all 6 fixed issues using 252 free models for democratic consensus',
  phases: [
    { title: 'Massive Validation', detail: 'Validate each fix with 252 free models' },
    { title: 'Consensus Analysis', detail: 'Analyze validation results and determine consensus' },
    { title: 'Store Results', detail: 'Save validation results to PostgreSQL' }
  ]
}

// Phase 1: Massive Validation
phase('Massive Validation');

// All 6 fixed issues to validate
const fixedIssues = [
  {
    issue: '273',
    title: 'fleet_executor.py moved to shared/',
    fix: 'File exists in shared/ with working imports',
    files: ['shared/fleet_executor.py']
  },
  {
    issue: '274',
    title: 'generate-embedding → generate-embeddings',
    fix: 'Updated 4 files to use correct plural filename',
    files: ['shared/vector-store-postgres.py', 'workflows/deep-research-with-autostorage.mjs', 'workflows/tests/custom-deep-research.mjs', 'learning/scripts/migrate-completed-workflows.js']
  },
  {
    issue: '265',
    title: 'consensus-replay.cjs wired to production',
    fix: 'Renamed model_regression_monitor.js → .cjs for CommonJS compatibility',
    files: ['tools/model_regression_monitor.cjs', 'shared/consensus-replay.cjs']
  },
  {
    issue: '267',
    title: 'experiment-manager.cjs integrated',
    fix: 'Wired statistical testing into consensus-replay workflow',
    files: ['shared/consensus-replay.cjs', 'docs/EXPERIMENT_MANAGER_USAGE.md']
  },
  {
    issue: '215',
    title: 'Multi-format chunking extracted',
    fix: 'Extracted to FlossWare/skills-ai with symlinks',
    files: ['shared/chunking-utils.js', 'shared/document_parser.py']
  },
  {
    issue: '216',
    title: 'Workflow primitives extracted',
    fix: 'Extracted fleet-workflow-wrapper to FlossWare/skills-ai',
    files: ['shared/fleet-workflow-wrapper.mjs']
  }
];

log(`Starting massive validation with 252 free models for 6 fixed issues...`);

const validations = await parallel(
  fixedIssues.map(issue => () =>
    agent(`Validate fix for issue #${issue.issue} using massive validator (252 free models).

Issue: ${issue.title}
Fix Applied: ${issue.fix}
Files Modified: ${issue.files.join(', ')}

Instructions:
1. Run the massive validator: python3 tools/massive_validator.py
2. Use FULL DEMOCRATIC validation (all 252 free models)
3. Validation prompt: "Verify that issue #${issue.issue} is correctly fixed. Check: ${issue.fix}. Test the files: ${issue.files.join(', ')}. Return TRUE if fix is correct and complete, FALSE if broken or incomplete."
4. Collect votes from all 252 models
5. Calculate consensus (% voting TRUE)
6. Determine verdict based on majority

Validation Strategies Available:
- full_democratic() - Use ALL 252 models (RECOMMENDED for final validation)
- provider_diverse_sample(n_per_provider=5) - 35 models (faster)
- specialist_committee(task_type, min_score=0.7) - Task-specific experts

Use full_democratic() for this validation.

Return JSON with:
- issue_number (string)
- validators_used (number - should be ~252)
- votes_true (number - models voting TRUE/PASS)
- votes_false (number - models voting FALSE/FAIL)
- consensus_percentage (number - % voting TRUE)
- verdict: "VALIDATED" | "REJECTED" | "INCONCLUSIVE"
- top_concerns (array of strings - reasons models voted FALSE)
- validation_output (string - summary from massive_validator.py)`, {
      label: `validate-#${issue.issue}`,
      phase: 'Massive Validation',
      schema: {
        type: 'object',
        properties: {
          issue_number: { type: 'string' },
          validators_used: { type: 'number' },
          votes_true: { type: 'number' },
          votes_false: { type: 'number' },
          consensus_percentage: { type: 'number' },
          verdict: { type: 'string', enum: ['VALIDATED', 'REJECTED', 'INCONCLUSIVE'] },
          top_concerns: { type: 'array', items: { type: 'string' } },
          validation_output: { type: 'string' }
        },
        required: ['issue_number', 'validators_used', 'votes_true', 'votes_false', 'consensus_percentage', 'verdict', 'top_concerns', 'validation_output']
      }
    })
  )
);

// Phase 2: Consensus Analysis
phase('Consensus Analysis');

const validated = validations.filter(v => v?.verdict === 'VALIDATED');
const rejected = validations.filter(v => v?.verdict === 'REJECTED');
const inconclusive = validations.filter(v => v?.verdict === 'INCONCLUSIVE');

log(`Massive validation complete: ${validated.length} validated, ${rejected.length} rejected, ${inconclusive.length} inconclusive`);

// Analyze consensus patterns
const consensusAnalysis = await agent(`Analyze 252-model validation results and provide final recommendation.

Validation Results:
${JSON.stringify(validations.filter(Boolean), null, 2)}

Instructions:
1. Review consensus percentages for each issue
2. Identify which issues have strong consensus (>80% agreement)
3. Identify which issues have concerns (>20% voting FALSE)
4. Analyze top concerns from models that voted FALSE
5. Provide final recommendation for each issue

Return JSON with:
- overall_validation_rate (number - % of issues that passed)
- strong_consensus (array of issue numbers with >80% TRUE votes)
- weak_consensus (array of issue numbers with 50-80% TRUE votes)
- failed_validation (array of issue numbers with <50% TRUE votes)
- safe_to_merge (array of issue numbers safe to merge to main)
- needs_rework (array of issue numbers that need additional fixes)
- summary (string - overall assessment)`, {
  label: 'consensus-analysis',
  phase: 'Consensus Analysis',
  schema: {
    type: 'object',
    properties: {
      overall_validation_rate: { type: 'number' },
      strong_consensus: { type: 'array', items: { type: 'string' } },
      weak_consensus: { type: 'array', items: { type: 'string' } },
      failed_validation: { type: 'array', items: { type: 'string' } },
      safe_to_merge: { type: 'array', items: { type: 'string' } },
      needs_rework: { type: 'array', items: { type: 'string' } },
      summary: { type: 'string' }
    },
    required: ['overall_validation_rate', 'strong_consensus', 'weak_consensus', 'failed_validation', 'safe_to_merge', 'needs_rework', 'summary']
  }
});

log(`Consensus analysis: ${consensusAnalysis.safe_to_merge.length} safe to merge, ${consensusAnalysis.needs_rework.length} need rework`);

// Phase 3: Store Results
phase('Store Results');

const storageResult = await agent(`Store 252-model validation results to PostgreSQL.

Validation Results:
${JSON.stringify(validations.filter(Boolean), null, 2)}

Consensus Analysis:
${JSON.stringify(consensusAnalysis, null, 2)}

Instructions:
1. Use workflow-storage-adapter.js to connect to PostgreSQL
2. Store each validation in learning.massive_validations table
3. Include: validation_id, strategy ('full_democratic'), total_validators, mean_quality, consensus_verdict
4. Create workflow learnings for validation insights

Return JSON with:
- records_stored (number)
- validation_ids (array of validation IDs)
- storage_status: "SUCCESS" | "FAILED"`, {
  label: 'store-validations',
  phase: 'Store Results',
  schema: {
    type: 'object',
    properties: {
      records_stored: { type: 'number' },
      validation_ids: { type: 'array', items: { type: 'string' } },
      storage_status: { type: 'string', enum: ['SUCCESS', 'FAILED'] }
    },
    required: ['records_stored', 'validation_ids', 'storage_status']
  }
});

log(`Validation results stored: ${storageResult.records_stored} records in PostgreSQL`);

// Final Results
return {
  validation_summary: {
    total_issues: fixedIssues.length,
    validated: validated.length,
    rejected: rejected.length,
    inconclusive: inconclusive.length,
    total_validators: 252,
    safe_to_merge: consensusAnalysis.safe_to_merge,
    needs_rework: consensusAnalysis.needs_rework
  },
  validations: validations.filter(Boolean),
  consensus_analysis: consensusAnalysis,
  storage: storageResult
};
