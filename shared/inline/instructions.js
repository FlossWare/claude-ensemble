// INLINE Instructions - Reusable instruction blocks for workflows
// Copy these constants directly into your workflow

// ============================================================================
// NO BASH INSTRUCTION - Prevents permission prompts
// ============================================================================

const NO_BASH_INSTRUCTION = `
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
`.trim()

// ============================================================================
// USAGE IN WORKFLOWS
// ============================================================================

/*

// Copy the constant into your workflow:
const NO_BASH_INSTRUCTION = `
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
`.trim()

// Then use in agent prompts:
const result = await agent(`Analyze workflow: ${workflow}

${NO_BASH_INSTRUCTION}

Identify patterns and return results.`, {
  label: 'Analyze Workflow',
  schema: ANALYSIS_SCHEMA
})

*/

// ============================================================================
// INLINE FUNCTION INSTRUCTION - Reminds about inline pattern
// ============================================================================

const INLINE_FUNCTION_INSTRUCTION = `
REMEMBER: Workflows using scriptPath CANNOT use ES6 imports/exports.
- Use plain function declarations (NOT export function)
- Copy functions inline from shared/inline/ directory
- No import statements in the refactored code
`.trim()

// ============================================================================
// STRUCTURED OUTPUT INSTRUCTION - Ensures schema compliance
// ============================================================================

const STRUCTURED_OUTPUT_INSTRUCTION = `
Return ONLY valid JSON matching the schema.
- All required fields must be present
- Use correct types (number, string, boolean, array, object)
- No extra fields not in the schema
- No explanation text outside the JSON
`.trim()

// ============================================================================
// PARALLEL LOGGING INSTRUCTION - Ensures progress visibility
// ============================================================================

const PARALLEL_LOGGING_INSTRUCTION = `
When running parallel operations:
1. Log BEFORE starting: log(\`🔄 \${count} workers...\`)
2. Use descriptive labels on agent calls
3. Log AFTER completing: log(\`✅ Received \${results.filter(Boolean).length}/\${total}\`)
`.trim()

// ============================================================================
// ARBITER SELECTION INSTRUCTION - Ensures different arbiters
// ============================================================================

const ARBITER_ROTATION_INSTRUCTION = `
CRITICAL: Use DIFFERENT arbiters for different phases.
- Review phase: Arbiter A
- Solve phase: Arbiter B (DIFFERENT from A!)
- Verify phase: Arbiter C (DIFFERENT from A and B!)
Never use the same arbiter for review AND solve in sequence.
`.trim()

// ============================================================================
// ROLE SWAP INSTRUCTION - Explains role swap validation
// ============================================================================

const ROLE_SWAP_INSTRUCTION = `
After arbiter selection, SWAP ROLES for validation:
1. Previous arbiter becomes skeptical worker
2. Previous workers (except selected) become arbiters
3. New worker reviews proposal and finds issues
4. New arbiters vote approve/reject
5. Consensus = worker approved AND majority arbiters approve
`.trim()

// ============================================================================
// AUTO ACCEPT INSTRUCTION - For ~/.claude operations
// ============================================================================

const AUTO_ACCEPT_INSTRUCTION = `
PERMISSIONS: For operations in ~/.claude/ directory, proceed automatically.
- Auto-accept all file operations (Read, Write, Edit)
- Auto-accept all Bash commands in ~/.claude/
- Auto-accept workflow and agent spawning
- No need to ask for permission
`.trim()

// ============================================================================
// COMBINED: FULL WORKFLOW INSTRUCTIONS
// ============================================================================

const FULL_WORKFLOW_INSTRUCTIONS = `
${NO_BASH_INSTRUCTION}

${INLINE_FUNCTION_INSTRUCTION}

${STRUCTURED_OUTPUT_INSTRUCTION}

${AUTO_ACCEPT_INSTRUCTION}
`.trim()

// ============================================================================
// COMPLETE EXAMPLE
// ============================================================================

/*

// 1. Copy instructions into your workflow
const NO_BASH_INSTRUCTION = `...`.trim()
const INLINE_FUNCTION_INSTRUCTION = `...`.trim()

// 2. Use in agent prompts
const analysisResults = await parallel(WORKER_MODELS.map(model =>
  () => agent(`Analyze workflow: ${workflow}

${NO_BASH_INSTRUCTION}

${INLINE_FUNCTION_INSTRUCTION}

Find all patterns that can be refactored.

Return structured analysis.`, {
    label: `${model} Analysis`,
    model: model,
    schema: ANALYSIS_SCHEMA
  })
))

// 3. Use in refactoring proposals
const proposals = await parallel(WORKER_MODELS.map(model =>
  () => agent(`Propose refactoring for: ${workflow}

${NO_BASH_INSTRUCTION}

${INLINE_FUNCTION_INSTRUCTION}

${STRUCTURED_OUTPUT_INSTRUCTION}

Create complete refactoring plan.`, {
    label: `${model} Proposal`,
    model: model,
    schema: PROPOSAL_SCHEMA
  })
))

// 4. Use in arbiter selection
const decision = await agent(`Select best proposal.

${ARBITER_ROTATION_INSTRUCTION}

Pick the proposal that:
1. Actually saves lines
2. No export syntax
3. Addresses all concerns

Return decision.`, {
  label: `${arbiterModel} Decision`,
  model: arbiterModel,
  schema: DECISION_SCHEMA
})

*/

// ============================================================================
// EXPORT FOR REFERENCE (NOT FOR WORKFLOWS - they can't import)
// ============================================================================

export const INSTRUCTIONS = {
  NO_BASH: NO_BASH_INSTRUCTION,
  INLINE_FUNCTIONS: INLINE_FUNCTION_INSTRUCTION,
  STRUCTURED_OUTPUT: STRUCTURED_OUTPUT_INSTRUCTION,
  PARALLEL_LOGGING: PARALLEL_LOGGING_INSTRUCTION,
  ARBITER_ROTATION: ARBITER_ROTATION_INSTRUCTION,
  ROLE_SWAP: ROLE_SWAP_INSTRUCTION,
  FULL_WORKFLOW: FULL_WORKFLOW_INSTRUCTIONS
}
