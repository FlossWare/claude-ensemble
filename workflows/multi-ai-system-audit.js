export const meta = {
  name: 'multi-ai-system-audit',
  description: 'Multi-AI consensus audit of system architecture and quality',
  phases: [
    { title: 'Architecture Analysis', detail: 'Multi-model analysis of design patterns and structure' },
    { title: 'Component Inventory', detail: 'Catalog workflows, skills, and libraries' },
    { title: 'Integration Analysis', detail: 'Assess coupling, cohesion, and dependencies' },
    { title: 'Quality Assessment', detail: 'Evaluate code quality, documentation, and gaps' },
    { title: 'Audit Synthesis', detail: 'Synthesize findings with prioritized recommendations' }
  ]
}

export default async function({ args, phase, log, agent, parallel }) {

// System repository path (can be overridden via args)
const REPO_PATH = args?.repo_path || '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills'
const SYSTEM_NAME = args?.system_name || 'claude-global-skills'

// Schema for structured architecture analysis
const ARCH_SCHEMA = {
  type: 'object',
  properties: {
    patterns: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          purpose: { type: 'string' },
          implementation: { type: 'string' },
          quality: { type: 'string', enum: ['excellent', 'good', 'needs-improvement', 'problematic'] }
        },
        required: ['name', 'purpose', 'quality']
      }
    },
    strengths: { type: 'array', items: { type: 'string' } },
    weaknesses: { type: 'array', items: { type: 'string' } }
  },
  required: ['patterns', 'strengths', 'weaknesses']
}

// Schema for component inventory
const INVENTORY_SCHEMA = {
  type: 'object',
  properties: {
    workflows: { type: 'number' },
    skills: { type: 'number' },
    libraries: { type: 'number' },
    coverage: { type: 'string' },
    maturity: { type: 'string', enum: ['production', 'beta', 'experimental', 'mixed'] }
  },
  required: ['workflows', 'skills', 'libraries', 'maturity']
}

// Schema for integration analysis
const INTEGRATION_SCHEMA = {
  type: 'object',
  properties: {
    coupling: { type: 'string', enum: ['loose', 'moderate', 'tight'] },
    cohesion: { type: 'string', enum: ['high', 'moderate', 'low'] },
    dependencies: { type: 'array', items: { type: 'string' } },
    integration_quality: { type: 'string' }
  },
  required: ['coupling', 'cohesion', 'dependencies', 'integration_quality']
}

// Schema for quality assessment
const QUALITY_SCHEMA = {
  type: 'object',
  properties: {
    code_quality: { type: 'number', minimum: 0, maximum: 100 },
    documentation: { type: 'number', minimum: 0, maximum: 100 },
    test_coverage: { type: 'string' },
    critical_gaps: { type: 'array', items: { type: 'string' } },
    quick_wins: { type: 'array', items: { type: 'string' } }
  },
  required: ['code_quality', 'documentation', 'critical_gaps']
}

// Phase 1: Architecture Analysis (6 models for maximum diversity)
phase('Architecture Analysis')
log('Analyzing system architecture with 6-model consensus...')

const archPrompt = `Analyze the ${SYSTEM_NAME} repository architecture at ${REPO_PATH}.

Focus on:
1. Design patterns (arbiter-worker, fleet distribution, multi-AI consensus)
2. Orchestration quality (not AI intelligence - this is a control system)
3. Component organization (workflows, skills, shared libraries)
4. Scalability and extensibility patterns
5. Code reuse and modularity

IMPORTANT: This is NOT a learning system or AI training framework. It's a distributed
orchestration system over pre-trained LLMs. All improvements are routing/decomposition/retry logic,
NOT model intelligence gains.

Identify architectural patterns, strengths, and weaknesses. Be specific about what works
and what needs improvement.`

const archResults = await parallel([
  () => agent(archPrompt, { model: 'opus', label: 'opus-arch', schema: ARCH_SCHEMA, phase: 'Architecture Analysis' }),
  () => agent(archPrompt, { model: 'sonnet', label: 'sonnet-arch', schema: ARCH_SCHEMA, phase: 'Architecture Analysis' }),
  () => agent(archPrompt, { model: 'haiku', label: 'haiku-arch', schema: ARCH_SCHEMA, phase: 'Architecture Analysis' }),
  () => agent(archPrompt, { model: 'gpt-4o', label: 'gpt4o-arch', schema: ARCH_SCHEMA, phase: 'Architecture Analysis' }),
  () => agent(archPrompt, { model: 'gemini', label: 'gemini-arch', schema: ARCH_SCHEMA, phase: 'Architecture Analysis' }),
  () => agent(archPrompt, { model: 'fable', label: 'fable-arch', schema: ARCH_SCHEMA, phase: 'Architecture Analysis' })
])

const validArchResults = archResults.filter(Boolean)
log(`Architecture: ${validArchResults.length}/6 models responded`)

// Phase 2: Component Inventory (3 models)
phase('Component Inventory')
log('Cataloging system components...')

const inventoryPrompt = `Inventory the ${SYSTEM_NAME} system components.

Count and categorize:
- Total workflows (by phase: SDLC, RAG, research, utilities)
- Total skills (interactive vs autonomous variants)
- Shared libraries (JavaScript, Python, Bash)
- Supporting infrastructure (monitoring, fleet scripts, etc.)

Assess:
1. SDLC coverage (what development phases are automated)
2. Component maturity (production-ready vs experimental)
3. Documentation completeness
4. Deprecated/planned components

Be precise with counts. Note gaps in coverage.`

const inventoryResults = await parallel([
  () => agent(inventoryPrompt, { model: 'opus', label: 'opus-inventory', schema: INVENTORY_SCHEMA, phase: 'Component Inventory' }),
  () => agent(inventoryPrompt, { model: 'sonnet', label: 'sonnet-inventory', schema: INVENTORY_SCHEMA, phase: 'Component Inventory' }),
  () => agent(inventoryPrompt, { model: 'haiku', label: 'haiku-inventory', schema: INVENTORY_SCHEMA, phase: 'Component Inventory' })
])

const validInventoryResults = inventoryResults.filter(Boolean)
log(`Inventory: ${validInventoryResults.length}/3 models responded`)

// Phase 3: Integration Analysis (3 models)
phase('Integration Analysis')
log('Analyzing component integration...')

const integrationPrompt = `Analyze how ${SYSTEM_NAME} components integrate.

Key integration points:
- Skills → Workflows (via Claude Code Skill tool)
- Workflows → Shared libraries (fleet-utils, consensus-engine, etc.)
- Fleet orchestration (SSH multi-session vs in-process parallelism)
- Memory persistence (ChromaDB, PostgreSQL + pgvector)
- Multi-AI consensus (arbiter-worker pattern)
- Compliance system (path-based model restrictions)

Assess:
1. Coupling (how tightly components depend on each other)
2. Cohesion (how well-focused each component is)
3. Dependency management
4. Integration reliability and error handling

Identify integration anti-patterns or brittleness.`

const integrationResults = await parallel([
  () => agent(integrationPrompt, { model: 'opus', label: 'opus-integration', schema: INTEGRATION_SCHEMA, phase: 'Integration Analysis' }),
  () => agent(integrationPrompt, { model: 'sonnet', label: 'sonnet-integration', schema: INTEGRATION_SCHEMA, phase: 'Integration Analysis' }),
  () => agent(integrationPrompt, { model: 'gpt-4o', label: 'gpt4o-integration', schema: INTEGRATION_SCHEMA, phase: 'Integration Analysis' })
])

const validIntegrationResults = integrationResults.filter(Boolean)
log(`Integration: ${validIntegrationResults.length}/3 models responded`)

// Phase 4: Quality Assessment (4 models)
phase('Quality Assessment')
log('Assessing system quality...')

const qualityPrompt = `Assess ${SYSTEM_NAME} quality and identify improvement opportunities.

Current status:
- 31 workflows (14,000+ LOC)
- Multi-AI consensus: Implemented in select workflows, planned for full deployment
- Fleet orchestrator: DOWN (NFS/autofs conflict on pi-02)
- Documentation: README.md (1480 lines), plus multiple docs/ files
- Testing: Fleet connectivity tests, some unit tests
- Monitoring: Prometheus + Grafana (21 alert rules)
- Known issues: 6 documented limitations, npm vulnerabilities in dev deps

Score (0-100):
1. Code quality (readability, maintainability, consistency)
2. Documentation quality (completeness, accuracy, usefulness)

Identify:
3. Test coverage gaps
4. Critical issues requiring immediate attention
5. Quick wins (high-value, low-effort improvements)

Be honest and specific about problems.`

const qualityResults = await parallel([
  () => agent(qualityPrompt, { model: 'opus', label: 'opus-quality', schema: QUALITY_SCHEMA, phase: 'Quality Assessment' }),
  () => agent(qualityPrompt, { model: 'sonnet', label: 'sonnet-quality', schema: QUALITY_SCHEMA, phase: 'Quality Assessment' }),
  () => agent(qualityPrompt, { model: 'haiku', label: 'haiku-quality', schema: QUALITY_SCHEMA, phase: 'Quality Assessment' }),
  () => agent(qualityPrompt, { model: 'gemini', label: 'gemini-quality', schema: QUALITY_SCHEMA, phase: 'Quality Assessment' })
])

const validQualityResults = qualityResults.filter(Boolean)
log(`Quality: ${validQualityResults.length}/4 models responded`)

// Phase 5: Audit Synthesis (Fable arbiter)
phase('Audit Synthesis')
log('Synthesizing audit findings...')

const synthesisPrompt = `Synthesize multi-AI audit findings for ${SYSTEM_NAME}.

Architecture findings (${validArchResults.length} models): ${JSON.stringify(validArchResults, null, 2)}

Inventory findings (${validInventoryResults.length} models): ${JSON.stringify(validInventoryResults, null, 2)}

Integration findings (${validIntegrationResults.length} models): ${JSON.stringify(validIntegrationResults, null, 2)}

Quality findings (${validQualityResults.length} models): ${JSON.stringify(validQualityResults, null, 2)}

Create comprehensive audit report (markdown format):

# ${SYSTEM_NAME} System Audit Report

## Executive Summary
3-5 key insights from the audit

## System Strengths
What works exceptionally well (with evidence from model consensus)

## System Weaknesses
What needs improvement (with severity assessment)

## Critical Issues
Blockers or high-priority problems requiring immediate attention

## Recommended Actions
Prioritized list (P0/P1/P2) with effort estimates:
- P0: Critical (blocks progress or creates risk)
- P1: Important (high value, should do soon)
- P2: Nice-to-have (quality improvements)

## Strategic Recommendations
Long-term architectural or process improvements

## Model Consensus Summary
- Architecture: ${validArchResults.length}/6 models
- Inventory: ${validInventoryResults.length}/3 models
- Integration: ${validIntegrationResults.length}/3 models
- Quality: ${validQualityResults.length}/4 models

Note areas of model agreement vs disagreement.`

const synthesis = await agent(synthesisPrompt, {
  model: 'fable',
  label: 'fable-arbiter',
  phase: 'Audit Synthesis'
})

log('Audit complete - synthesis generated')

return {
  system: SYSTEM_NAME,
  audit_date: new Date().toISOString().split('T')[0],
  architecture: validArchResults,
  inventory: validInventoryResults,
  integration: validIntegrationResults,
  quality: validQualityResults,
  synthesis,
  model_coverage: {
    architecture: `${validArchResults.length}/6`,
    inventory: `${validInventoryResults.length}/3`,
    integration: `${validIntegrationResults.length}/3`,
    quality: `${validQualityResults.length}/4`,
    total_agents: validArchResults.length + validInventoryResults.length + validIntegrationResults.length + validQualityResults.length + 1
  }
}

}
